# Data contract — nonprofits module ("Follow the nonprofit money")

The dashboard reads static JSON from `nonprofits/data/site/`. `design/prototype/sample-data/nonprofits/` follows this contract exactly; `sample-data/generate.py` is the reference writer and a checklist of every field. Every rule is a *must* unless marked *may*.

## 1. Conventions
- Paths relative to `data/site/`. Boot loads `meta.json`; views load the files listed in §4.
- Every file carries `"sample": true|false`, `"as_of": "YYYY-MM-DD"` and `"sources": [source ids from meta.sources]`. Production sets `sample: false`.
- Fiscal years are integers labelled by the ending year (FY2025 = Jul 2024–Jun 2025). Dollars are **nominal** in every file; the dashboard deflates with `meta.deflator` (so one deflator, one base year, everywhere).
- Ids: `org` = `"org-<n>"` (stable across all files and across modules: `network/entities.json › nonprofit_org` points here); `dept` = Controller department code as used in the Budget/Spending datasets (`DPH`, `HOM`, `HSA`, `MOHCD`…); `area` and `size_band` ids are listed in `meta.dimensions`.
- Never emit `NaN`; use `null`. Keep small groups (the UI greys them); never drop rows to hide small n.
- Sizes: ≤ 400 KB per file uncompressed; split as noted.

## 2. Client-side pooling (what the dashboard computes)
The dashboard never re-aggregates raw vouchers. It filters **payment cells** (one row per fiscal year × department × organization) by year, department and organization attributes, sums `amt`, and derives the **organization set** (organizations with ≥ 1 surviving cell). Every other file is filtered by that set and by year. Derived in the browser: real dollars, top-N shares, city share = Σ payments(org, fy) / `total_revenue`(org, fy), dependency bands, growth ratio = `agreed / original_agreed`, quantiles per group, review shares. So the exporter only needs exact cells and per-entity rows; no precomputed slices.

## 3. Files

### `meta.json` — boot
```
sample, module: "nonprofits", as_of, generated_at, version,
fiscal_years: {min: 2016, max: 2025, note},
deflator: {base_fy: int, source: str, index: {"2016": num, …}}     // index[fy] = CPI_fy / CPI_base; real = nominal / index
dimensions: {
  dept: {label, values: [{id, name, group, short}]},                   // only departments that pay nonprofits
  area: {label, kind: "categorical", values: [{id, label, slot: 1..7}]},
  size_band: {label, kind: "ordinal", values: [{id, label}]},           // lt1m | 1-5m | 5-25m | 25m+ (average city $ a year)
  result: {label, kind: "ordinal", values: [{id, label}]}               // none | findings | corrective | elevated | redflag
},
counts: {organizations, payment_rows, contracts, form_990_years, monitoring_results, total_paid_all_years},
small_n: 5,
sources: [{id, name, publisher, rows, rows_used, as_of, url, note}],
files: {"<path>": {bytes}}
```
`area` is assigned once per organization (NTEE code + funding programs; write the rule in DATA_NOTES). `deflator.base_fy` may be 2026 (the performance module's choice); the UI reads it. Example source: `{"id":"n9pm-xkyq","name":"Vendor Payments (Vouchers)","publisher":"SF Controller via data.sf.gov","rows":4218663,"rows_used":612402,"as_of":"2026-09-19","url":"https://data.sf.gov/resource/n9pm-xkyq.json","note":"Rows with non_profit_indicator = Y plus 990-matched vendors"}`.

### `orgs/index.json` — every view; search; profiles
```
orgs: [{id, name, ein: str|null, area, size_band, depts: [dept id], city_total: int (all years, nominal), city_fy_latest: int,
        first_fy, last_fy, match: {method: "ein"|"name"|"manual", confidence: 0..1}, network_id: str|null}]
```
Example: `{"id":"org-001","name":"Bayview Navigation Services","ein":"94-7859791","area":"homeless","size_band":"1-5m","depts":["HOM"],"city_total":13400000,"city_fy_latest":2450000,"first_fy":2016,"last_fy":2025,"match":{"method":"name","confidence":0.99},"network_id":"np-org-001"}`. `name` is the canonical vendor name; aliases go in DATA_NOTES. Expect ~1,500–3,000 organizations (the agent's vendor list has 10,286 vendors; include only those flagged or matched as nonprofits).

### `payments/cells_<fy>.json` (production, one per fiscal year) / `payments/cells.json` (prototype)
```
cells: [{fy, dept, org, amt: int, vouchers: int, contracts: int}]
```
One row per (fy, dept, org) with `amt > 0`; `vouchers` = voucher count, `contracts` = distinct contract numbers. Example: `{"fy":2025,"dept":"DPH","org":"org-014","amt":8120000,"vouchers":212,"contracts":3}`. The dashboard loads the years in the filter (prototype loads one file).

### `contracts/contracts.json`
```
contracts: [{id (contract_no), org, dept, title, start: date, end: date, type: "grant"|"professional_services"|"other", sole_source: bool,
             original_agreed: int, agreed: int, consumed: int, amendments: [{date, agreed_after: int}]}]
```
`original_agreed` = the earliest observed `agreed_amt` (state in DATA_NOTES how far back snapshots go; contracts already amended before the first snapshot are flagged in `note`). Example in the sample file.

### `finances/form990.json` — dependency, pay & reserves, profiles
```
rows: [{org, fy (tax year ending in that fiscal year), form: "990"|"990-EZ"|"990-N", total_revenue, total_expenses, gov_grants, program_share: 0..1,
        net_assets, unrestricted_net_assets, months_reserves: num, employees: int, exec_comp: int, exec_title: str, exec_comp_rank: 1, highest_paid_count: int}]
```
`exec_comp` is the highest-paid officer's total compensation (Part VII); the title is shown, the name is not exported. `months_reserves` = unrestricted net assets / (expenses / 12); may be negative. Example: `{"org":"org-014","fy":2024,"form":"990","total_revenue":24100000,"total_expenses":23600000,"gov_grants":19800000,"program_share":0.84,"net_assets":6100000,"unrestricted_net_assets":3900000,"months_reserves":2.0,"employees":210,"exec_comp":248000,"exec_title":"Executive Director","exec_comp_rank":1,"highest_paid_count":3}`.

### `reviews/findings.json` — Controller monitoring results
```
results: [{id, label}], categories: [str],
rows: [{id, org, fy, lead_dept, type: "fiscal_compliance"|"program", result: result id, categories: [str],
        report: {title, url, page: int|null}, note: str|null}]
```
Every row cites the report (`url` required in production). The agent's `org_findings.json` (1,021 findings) maps here one row per organization-year with categories collapsed; keep one row per organization-year-type.

### `commentary/np-*.json`, `commentary/story_np.json`
See the shared commentary schema in `DESIGN.md §4`: `{sample, view, author, headline, paragraphs[], annotations[{chart, x, series?, text, placement?}], templates[{id, template, requires?, fallback}], caveats[{text, severity}], sources[]}`. Template ids and slots used by the prototype, per view: `np-overview: total` (`orgs, orgs_fmt, rows, rows_fmt, total, years`) · `np-flows: flows` (+ `depts_fmt, top_dept, top_dept_share`) · `np-dependency: dep` (`fy, orgs, orgs_fmt, median_share, hi_fmt`) · `np-pay: pay` (`fy, orgs, median_pay, n_low_fmt`) · `np-growth: growth` (`years, contracts, contracts_fmt, amended_fmt, median_ratio, doubled_fmt`) · `np-reviews: reviews` (`reviews, reviews_fmt, orgs_fmt, none_share, elev_fmt`). Story: `{title, steps: [{view, title, text, filters?: {years?, dept?, area?, size?, real?}}]}`.

## 4. Which view loads what
| View | Files |
|---|---|
| boot | `meta.json` (+ site.json and the other modules' meta) |
| np-overview | `orgs/index.json`, `payments/cells*.json`, `finances/form990.json`, `reviews/findings.json` |
| np-flows, np-orgs | `orgs/index.json`, `payments/cells*.json` |
| np-dependency, np-pay | + `finances/form990.json` |
| np-growth | + `contracts/contracts.json` |
| np-reviews | + `reviews/findings.json` |
| org profile | all of the above + `audits/recs/recs.json`, `audits/reports/reports.json`, `network/entities.json`, `network/flows.json`, `network/analyses/ban_window.json` |
| every view | `commentary/<view>.json` |

## 5. QA checks the exporter must run
1. Σ `amt` over all cells = total nonprofit payments in the processed vouchers (state the difference from the raw `non_profit_indicator` total).
2. Every `org`, `dept`, `area`, `size_band`, `result` id exists in `meta.dimensions` / `orgs/index.json`.
3. For each org, `city_total` = Σ cells; `first_fy`/`last_fy` match the cells.
4. `form990` rows: `total_revenue > 0`; city share computed as above is reported with the share of org-years above 1.0 (expect a few percent; explain in DATA_NOTES).
5. Every `reviews.rows[].report.url` resolves; `page` present when `result != "none"`.
6. `meta.files` lists every file with bytes; commentary `sources[]` paths exist; every number in headlines/paragraphs is computed from these files (write the formulas in `ANALYSIS.md`).
7. `network_id` values exist in `network/entities.json`.
