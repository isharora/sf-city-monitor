# Data contract — performance module ("Budget vs outcomes")

The dashboard reads static JSON from `performance/data/site/`. `design/prototype/sample-data/performance/` follows this contract; `sample-data/generate.py` is the reference writer. Vocabulary follows `performance/DATA_NOTES.md` (character classes, department code crosswalk, FY2018 cutover masks, measure lineage). Every rule is a *must* unless marked *may*.

## 1. Conventions
- Fiscal years are integers labelled by the ending year. Dollars are **nominal**; the dashboard deflates with `meta.deflator` (base year is a field: FY2026 per the module's notes is fine). Per-resident figures use `meta.population.by_fy[fy]` (DOF E-4, January 1 of the fiscal year).
- Department ids are the Controller codes after the crosswalk in `pipeline/common.py` (`POL`, `HOM`, `DPW`, `PUC`…), one row set per code. Real reorganizations are not merged; where a series is masked (DPW/PUC FY2018), emit `actual: null` and set `dq_flag`.
- Percent measures are exported in **percentage points (0–100)**, not fractions; `unit: "%"`.
- Never `NaN`; use `null`. Keep small groups.

## 2. Client-side computation
The dashboard filters `spending/cells` by department set (group + department filters) and years, sums `budget`/`revised`/`actual` by any of `fy, dept, fund, char`, deflates, divides by population, indexes to the first selected year, and computes gaps (`actual/budget − 1`). It filters `staffing/cells` the same way. It joins `measures/values` to `measures/measures` by `measure`, computes met shares by department × FY × type, target-change flags (already in the rows), dropped measures (`dropped_fy`), and real unit costs from `cost_per_unit`. Nothing needs precomputing except the curated cost links.

## 3. Files

### `meta.json` — boot
```
sample, module: "performance", as_of, generated_at, version,
fiscal_years: {min, max, budget_max},                          // actuals exist through max; budget through budget_max
deflator: {base_fy, source, index: {"<fy>": num}},           // BLS CUURS49BSA0, FY average; note interpolations
population: {source, by_fy: {"<fy>": int}},
dimensions: {
  dept: {label, values: [{id, name, group, short}]},          // all departments shown (exclude fiduciary/component units)
  group: {label, values: [{id, label}]},                       // organization groups
  char: {label, kind: "categorical", values: [{id, label, slot: 1..7}]},   // salaries, fringe, overtime, nonpersonnel, aid, capital, other (fold materials/grants/projects/debt as documented)
  fund: {label, values: [{id: "gf"|"other", label}]}
},
counts: {departments, spending_rows, staffing_rows, measures, measure_values},
small_n: 3, sources: [{id, name, publisher, rows, rows_used, as_of, url, note}], files: {"<path>": {bytes}}
```
Sources must include `xdgd-c79v`, `bpnb-jwfb`, `88g8-5mnd`, `6dpt-7w23` (current measures), `5x94-tptc`/`6h77-suve` (FY13/14 snapshots), the PDF report set, `4zfx-f2ts`/`43jt-u7yn` if positions are exported, DOF E-4 and BLS CPI.

### `spending/cells.json` (may split `spending/cells_<fy>.json`)
```
cells: [{fy, dept, fund: "gf"|"other", char: char id, budget: int, revised: int|null, actual: int|null, dq_flag?: str}]
```
`budget` = adopted appropriation (Budget dataset); `actual` = Spending and Revenue; `revised` may be null if unavailable. Operating vs capital: the dashboard's budget-vs-actual view reads all classes; **export `char` so the UI can exclude capital/projects/debt where the notes say the annual gap is not meaningful**, and put the operating-only guidance in the view caveat (`commentary/pf-gaps.json`). Example: `{"fy":2025,"dept":"POL","fund":"gf","char":"overtime","budget":98000000,"revised":101000000,"actual":147200000}`.

### `staffing/cells.json`
```
cells: [{fy, dept, headcount: int, fte: num|null, salaries: int, overtime: int, ot_share: num|null, employees_ot_over_100k: int,
         top_ot_job_families: [{family, overtime: int}] (≤ 3), budgeted_fte?: num, vacancy?: num}]
```
`headcount` = distinct `employee_identifier` in the department-year; `fte` = paid-hours FTE (hours/2080, includes overtime hours as noted) from FY2017; names never exported; job families only. Example in the sample file.

### `measures/measures.json`
```
measures: [{id (hash of dept + lowercased canonical title), dept, name, unit, direction: "higher"|"lower"|"neutral", type: "outcome"|"output"|"efficiency",
            first_fy, last_fy, dropped_fy: int|null, replaced_by: id|null, lineage_id?: str, lineage_note?: str, internal_admin?: bool}]
```
A measure is dropped when its lineage ends without a `replaced_by` (from `measure_lineage.csv`); `lineage_note` records *reworded* vs *redefined* transitions so the UI can flag definition changes.

### `measures/values.json` (may split by fy)
```
rows: [{measure, fy, target: num|null, actual: num|null, met: bool|null, target_change: "easier"|"harder"|"same"|"new",
        source_doc: str, program_cost?: int, cost_per_unit?: num, restated?: bool}]
```
`met` = actual vs target in `direction` (null when either is missing or direction is neutral). `target_change` compares with the previous year's target in the measure's direction. `program_cost`/`cost_per_unit` only for the **curated numerator/denominator pairs** (DATA_NOTES §6), never from the automated flag; `cost_per_unit` is nominal. Example: `{"measure":"M-0f3a…","fy":2025,"target":85,"actual":81.2,"met":false,"target_change":"easier","source_doc":"FY2025 Performance Scorecards","program_cost":41200000,"cost_per_unit":1830}`.

### `measures/cost_links.json` *(may; documents the curated pairs)*
`links: [{measure, numerator: str (program codes / characters), denominator: str, rationale, confidence}]` — shown on the methods page.

### `commentary/pf-*.json`, `commentary/story_pf.json`
Shared schema (DESIGN.md §4). Template ids and slots: `pf-overview: ov` (`depts_fmt, total, dollars, fy, measures, measures_fmt, met_share`) · `pf-spending: sp` (`depts_fmt, fy0, fy1, change_real, change_nominal, change_per_res`) · `pf-staffing: st` (`fy, depts_fmt, headcount_fmt, ot_total, ot_share, ot100k_fmt`) · `pf-outcomes: oc` (`fy, depts_fmt, met_fmt, measures, measures_fmt, met_share, met_share_outcome, met_share_output`) · `pf-cost: cost` (`measures, measures_fmt, depts_fmt, fy0, fy1, median_change`) · `pf-integrity: int` (`depts_fmt, fy0, fy1, measures, dropped_fmt, dropped_missed_fmt, lowered_fmt, lowered_after_miss_fmt`) · `pf-gaps: gap` (`fy, depts_fmt, gap_total, gap_pct, over_fmt, under_fmt`). Story filters may set `years, group, dept, real`.

## 4. Which view loads what
| View | Files |
|---|---|
| pf-overview | `spending/cells*.json`, `staffing/cells.json`, `measures/measures.json`, `measures/values*.json` |
| pf-spending, pf-gaps | `spending/cells*.json` |
| pf-staffing | `staffing/cells.json` |
| pf-outcomes, pf-cost, pf-integrity | `measures/measures.json`, `measures/values*.json` |
| pf-depts | all four |
| dept scorecard | all four + `nonprofits/payments/cells*.json`, `nonprofits/orgs/index.json`, `audits/recs/recs.json`, `audits/reports/reports.json`, `network/entities.json`, `network/flows.json` |

## 5. QA checks
1. Σ `actual` by fy over exported cells equals the module's `dept_fy.csv` operating totals (state exclusions: fiduciary, transfers, GFSUP artifact).
2. Every `dept` id in every file exists in `meta.dimensions.dept`; every `char`/`fund` id in dimensions.
3. `staffing.overtime` agrees with the ledger overtime objects within the tolerance stated in DATA_NOTES (~10%); log per-department differences.
4. For each measure, `first_fy ≤ fy ≤ last_fy` for all values; `dropped_fy = last_fy + 1` when dropped; `met` recomputes from `target`, `actual`, `direction`.
5. Percent measures are 0–100; a value > 100 with `unit: "%"` is an error unless the measure allows it.
6. `meta.files` bytes correct; commentary numbers reproduce (`15_redteam.py`).
