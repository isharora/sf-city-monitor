# SF City Monitor — design specification

One site, four analysis dashboards about San Francisco's government, with a shared visual system: **(1) Follow the nonprofit money**, **(2) Budget vs outcomes**, **(3) Audit recommendations tracker**, **(4) Money network**. This document is the build spec. The clickable prototype in `design/prototype/` (open `index.html` from `file://`; add `?view=<id>&theme=dark` for any state) is the visual and interaction reference; the four `DATA_CONTRACT_<module>.md` files are the data reference. Where they disagree, the prototype wins for interaction and this document wins for copy and rules.

Audience: smart non-experts (a software product person new to civic data), plus journalists, supervisors' staff and advocates who want to check numbers. It is an accountability and analysis tool: precise, fair and useful; never sensational; it always distinguishes *unusual* from *improper*.

## 1. Principles

1. **Every filter shown applies to everything on the view, or it is visibly absent.** A view declares the filters it supports; the filter bar renders exactly those, and prints "Not on this view: *Dollars* (no dollar amounts on this view)" for the dashboard's other filters. Each card is computed from the same filtered scope, and every view registers the record counts it filtered so the data strip can prove it. In development a view that declares a filter but registers no filtered counts logs a warning (`[filters] …`). Views whose data cannot be sliced at all (network › Concentration) have no filter bar, only a sentence saying why.
2. **Every page says how much data is feeding it.** A data strip under the live sentence: records matched by the current filters (with totals), number of source datasets, files loaded with total size, and the as-of date; "Details" opens a three-column panel (record counts with bars · source datasets with publisher, id, rows used / total, as-of, notes, links · files loaded with size and sample badge). Also reachable by URL (`&data=1`) for review.
3. **Commentary is first-class.** Headline finding, live filter-aware sentences with small-sample fallbacks, analyst paragraphs with "numbers trace to", chart callouts, severity-tagged caveats, inline "why this might be wrong" under specific charts, and a guided story per dashboard.
4. **Fair by construction.** Organizations and officials in public roles are named; private individuals appear only in aggregates; "unusual" is labelled as such and never as "improper"; every "appears to warrant review" tag sits next to the legal rule it refers to and the reason; base rates are shown wherever coincidence could be over-read; audit findings cite their report.
5. **One axis, thin marks, quiet chrome; colour follows the entity.** No dual axes (series of different scale are indexed to 100 or shown as separate charts). Categorical colours are fixed per entity type / service area / recommender; sequential for magnitude; diverging (blue/red) only for polarity (over/under, met/missed, agree/disagree); status colours reserved.
6. **Shareable, keyboard-operable, light and dark.** All state in the URL; every chart mark focusable with the hover tooltip; a table twin on every chart; dark is a selected palette, not an inversion.

## 2. Information architecture

```
Home (landing)                         ?view=home
├─ 1 Follow the nonprofit money        np-overview · np-flows · np-dependency · np-pay · np-growth · np-reviews · np-orgs
├─ 2 Budget vs outcomes                pf-overview · pf-spending · pf-staffing · pf-outcomes · pf-cost · pf-integrity · pf-gaps · pf-depts
├─ 3 Audit recommendations tracker     au-overview · au-status · au-time · au-agreement · au-repeat · au-open · au-reports
├─ 4 Money network                     nw-overview · nw-graph · nw-ban · nw-behested · nw-lobby · nw-concentration · nw-loop · nw-entities
├─ Entity pages                        org (?id=org-…|con-…) · dept (?id=DPH) · report (?id=R-…) · official (?id=off-…)
├─ Search                              search (?q=…)  + typeahead in the top bar
└─ Methods and data                    methods
```

**Shell.** Left sidebar: brand, dashboard switcher (Home + 4 numbered dashboards), then the current dashboard's views (numbered, in reading order) or the site pages. Top bar: search box (`/`), sample-data notice, Story toggle (visible inside a dashboard), Dark, Copy link. Under it the sticky filter bar. Bottom: story bar when story mode is on.

**Cross-links (all implemented in the prototype).**
- Organization profile → its funding departments' scorecards; audit recommendations about those departments (contracting-related or open) with report links; network flows with counterparties (officials, departments, lobbyists); "See in the network graph" (focus). Contractor profile (same `org` view with a network id) → contracts, payments, contributions by affiliated individuals with the ban-window strip.
- Department scorecard → filtered dashboard views ("Budget vs outcomes, this department", "Audit tracker, this department", "Nonprofit money, this department"), open recommendations with report pages, largest nonprofit recipients (→ org profiles), lobbying of the department by client (→ profiles).
- Report page → department scorecards, "all recommendations from this body" (filtered au-status).
- Official profile → committees' contributions by source type, ban-window strip, behested payments (payors → profiles, payees → org/department pages), lobbying contacts by client, "Focus in the network graph".
- Within dashboards: bars, rows, cells and dots that represent an entity are clickable (tooltip says "Click to open"); the audits overview's year columns set the year filter.

**Reader paths.** (a) *Story mode* per dashboard (6–7 steps; each sets view and filters; Back/Next/dots, `←`/`→`, Exit; charts remain live). (b) *Explore*: dashboard nav + filter bar. (c) *Deep links*: every state is a URL; landing cards, tiles and cross-links are links. (d) *Search*: typeahead (top 8 hits) or Enter for a grouped results page.

**Page anatomy (every dashboard view, top to bottom):** kicker (`N · Dashboard` + "Sample commentary" badge while sample) → title → one-line "what this shows" → **Finding** (left-ruled card) → "How to read this view" (`<details>`) → **For your current filters** (live sentences; amber "Too few records" tag when a template's `requires` fails) → **Data on this page** strip (+ details panel) → rule / fairness boxes where relevant → stat tiles (overviews) → cards in a 12-column grid → **Analyst's read** (2–3 paragraphs + "Numbers trace to") → **Why this might be wrong** (severity-tagged). Entity pages replace the finding with a header of facts and links, and use section headings between card groups.

## 3. Global model

### 3.1 Filters (per dashboard; each view lists the subset it applies)

| Dashboard | Filter | Control | Applies to |
|---|---|---|---|
| Nonprofits | Fiscal years (2016–2025) | two selects | payment cells by `fy`; org-level data by `fy` |
| | Department (12) | multi-select popover | payment cells by `dept`; organizations = those paid by a selected department in the selected years (so 990, contracts and reviews filter too) |
| | Service area (7 chips with colour dots) · Size (4 chips) | chips, multi-select | organization attributes |
| | Dollars: Real (FY base) / Nominal | segmented | every dollar figure and chart; live sentences name which is in use |
| Performance | Fiscal years · Department group (6) · Department (20) · Dollars | as above | spending, staffing and measure rows via the department set |
| Audits | Years issued (2014–2025) · Recommended by (CSA/BLA/CGJ chips) · Department · Topic | | the one recommendation table; reports = those with a surviving recommendation |
| Network | Years (2019–2026) · Flow type (6 chips) · Entity type (popover) · Minimum amount (select) | | flows by date, type, either endpoint's type, amount (flows without an amount drop out when a minimum is set) |

Rules: chips are toggles (empty = all); "Reset filters" appears only when a filter is active and resets only that dashboard's filters; switching dashboards keeps unrelated filters untouched; per-view controls (year of a snapshot, stack-by, edge count, focus) live in the card header or view tools and are stored as `v.<key>` in the URL and cleared on view change.

**Absent filters, view by view:** `np-reviews`, `pf-outcomes`, `pf-integrity`: no Dollars (no dollar amounts). `nw-ban`, `nw-behested`: no Flow type (single flow). `nw-lobby`: no Flow type, no Minimum amount (contacts have no dollar value). `nw-loop`: no Flow type (fixed set), no Entity type (all rows are nonprofits). `nw-concentration`: no filters (precomputed per committee per cycle; the bar says so). Entity pages, Home, Search, Methods: no filter bar ("Profile pages show all years; filters live in the dashboards").

### 3.2 URL state
`?view=<id>&years=2019-2025&dept=DPH,HSH&area=homeless&size=25m+&group=protection&real=0&source=csa,cgj&topic=contracts&flow=contribution&etype=contractor&amt=10000&id=org-014&q=housing&theme=dark&mode=story&step=2&data=1&v.<key>=<value>`. Defaults omitted; `history.replaceState` on every change; "Copy link" copies `location.href`. Theme: URL > saved preference > OS. Year bounds come from each dashboard's `meta` and out-of-range values are clamped. See `js/state.js`.

### 3.3 Small samples and uncertainty
- Each module's `meta.small_n` (nonprofits 5, performance 3, audits 5, network 5). Groups below it render at 42% opacity with italic labels and the value replaced by "too few records"; heat cells show the value in parentheses; live templates carry `requires` (`orgs_min`, `recs_min`, …) and a `fallback` ("Too few records match to summarize; widen the years or clear a filter.") that turns the card tag amber.
- `n` appears at the right of every row, in every tooltip and tile foot, and in every live sentence.
- Distributions use range bars (p25–p75 box, median tick, p90 dot). Time-to-implement curves include never-implemented recommendations and stop where a cohort cannot yet be observed (survivor bias stated inline).
- Base rates: the ban-window view shows the share of contributions expected inside a window by chance next to the observed share, and its caveat says only the gap and the covered-official rows carry information.

### 3.4 Loading, empty, error
Loading holds the previous render at 55% opacity (no layout jump; a single skeleton block on first paint). Empty cards show a centred title and the concrete fix ("Widen the fiscal years or clear a filter."), never a blank SVG. A chart error shows "Chart failed to render" in that card only. A missing file shows "Could not load data: <file>". Unknown entity ids show "Unknown organization / department / report / official".

### 3.5 Keyboard
`/` focus search · `[` `]` previous/next view within a dashboard · `s` story mode · `←` `→` story steps · `d` dark · `?` help. Nav items, chips, popover checkboxes, controls, table headers (sortable), rows with links and **every chart mark** (rows, columns, cells, dots, nodes, edges) are in the tab order and show the tooltip on focus. Focus ring 2px `--focus`. Skip link to content.

## 4. The commentary layer

| Element | Where | Source | Behaviour |
|---|---|---|---|
| **Finding** | under the title | `commentary/<view>.json › headline` | one sentence, static, written from the final analysis; numbers computed from the data files (the sample generator formats them from the same data so text never disagrees with charts) |
| **Live sentences** | "For your current filters" | `templates[]` + slots computed by the view | recomputed on every filter change; `requires` (`<slot>_min`, `<slot>_max`, exact) → `fallback`; the view sets numeric slots (`orgs`, `recs`, `flows` …) and formatted twins (`orgs_fmt`) |
| **Analyst's read** | after the cards | `paragraphs[]`, `sources[]` | 2–3 short paragraphs: what stands out, mechanism, what is contested, implication, caveats plainly; followed by "Numbers trace to: file paths / ANALYSIS.md anchors" |
| **Callouts** | on charts | `annotations[]` (`chart`, `x`, `series?`, `text ≤ 90 chars`, `placement`) | dot + leader + boxed label clamped inside the SVG; chart ids used: `np_trend`, `pf_trend` (add per chart) |
| **Why this might be wrong** | after the analyst's read, and inline under specific cards | `caveats[]` + card `caveat` | severity tag: *Could move the finding* (high) / *Worth knowing* (medium) / *Minor* (low) |
| **Fairness and rule boxes** | above the cards | view code + `network/meta.json › rules, fairness` | grey box: "Fairness note" / "Read this view with the base rate" / "Appearing here is not improper"; ruled box: rule name, plain-language text, `cite`, and an italic "To verify before publication" line for the data agent |
| **Tags** | tables, lists | view code | `appears to warrant review` (amber; only beside a cited rule and a reason), `pattern` (grey: "interested party", "after a miss", "was being missed"), `met`/`missed` (blue/amber-red), `unusual` (blue) |
| **Story mode** | bottom bar | `commentary/story_<dash>.json` | ordered steps `{view, title, text, filters}`; the same charts and controls remain live |

Writing rules: American English, sentence case, no exclamation marks; state population and n with every number; say "median" when it is one; always pair a striking number with its context ("the city contracts out large services by design"); name organizations and officials in public roles, never employees below executive level; for network views, say "pattern worth checking, not proof" wherever a timing link appears; cite the report for every audit finding.

## 5. Views

Format: question · cards (form + why) · interactions · live slots · filters (§3.1) · copy is in the prototype (`title`, `what`, `how`).

### 5.1 Home (`home`)
Hero; data strip (source datasets per dashboard); four dashboard cards (number, title, what, three KPIs from `meta.counts`, view list; click → first view); "How the dashboards connect" (three cross-link examples with live links); "How to read this site" (filters that apply, how much data, unusual is not improper); search pointer; link to methods.

### 5.2 Dashboard 1 — Follow the nonprofit money (`np-*`)
Scope function (`views-np.js › scope`): payment cells filtered by years, department and organization attributes; the surviving organizations form the org set for 990, contract and review cards. Registers "payment records" and "organizations" counts.
- **`np-overview`** — What are the 4 things to know? Tiles: total paid (real/nominal), organizations paid in the last selected year, share of that year's dollars to the 10 largest, organizations ever rated elevated concern/red flag. Cards: real vs nominal lines by fiscal year (gap = inflation); top-10 recipients bars coloured by service area (click → profile). Slots: `orgs, orgs_fmt, rows, rows_fmt, total, years, fy, dollars`.
- **`np-flows`** — Who gets paid, by whom? Stacked columns by fiscal year (stack by service area or by top-6 departments + Other; control `v.stack`); horizontal stacked bars department × service area with n = organizations (click → scorecard); top-20 organizations. Slots add `depts_fmt, top_dept, top_dept_share`. Callout `np_trend`.
- **`np-dependency`** — How dependent are they on the city? Scatter (x city dollars log, y city share of 990 revenue, colour service area with legend, 75% reference line; y clamped at 120%); dependency-band histogram (orange ≥ 75%); table "large and dependent" (> 75% and ≥ $5M) with reserves. Year control `v.fy`. Inline caveat on 990/FY misalignment. Slots `fy, orgs, median_share, hi_fmt`.
- **`np-pay`** — Executive pay and reserves. Fairness note ("High compensation is unusual, not improper…"). Scatter pay vs expenses (log x; colour = size band, ordinal ramp, legend); range bars of pay by size band (greyed under small_n); range bars of months of reserves by service area; table of organizations under one month of reserves. Slots `fy, orgs, median_pay, n_low_fmt`.
- **`np-growth`** — Contract growth. Histogram of growth ratio (orange ≥ 2×); slope chart original → latest agreed for the 12 largest dollar increases (sole-source and amendment count in the label; click → profile); stacked columns of new contracts by start year (grant vs professional services, n = contracts); full contract table. Slots `contracts, amended_fmt, median_ratio, doubled_fmt`.
- **`np-reviews`** — Controller monitoring results. Reading note. 100% stacked columns by fiscal year on the five-step ordinal scale; finding categories bars; table of elevated concern / red flag with report title and page. Dollars filter absent. Slots `reviews, orgs_fmt, none_share, elev_fmt`.
- **`np-orgs`** — Directory: sortable, searchable table (name → profile, area, size, departments, paid in selection, paid latest FY, first FY, 990 match method and confidence).

### 5.3 Dashboard 2 — Budget vs outcomes (`pf-*`)
Scope: department set from group + department filters; spending, staffing and measure rows filtered by that set and the years; `real(amount, fy)` deflates when Real is on. Registers spending records, departments, measures, measure-year values, staffing records.
- **`pf-overview`** — Tiles: actual spending latest FY (real) with change vs first FY; per resident (population of the FY) with change; overtime; share of measures met. Cards: real vs nominal lines; per-resident bars by department (click → scorecard). Slots `depts_fmt, total, dollars, fy, measures, met_share`.
- **`pf-spending`** — Indexed real spending lines (first selected FY = 100) for the 7 largest departments + dashed total (no dual axis; legend); per-resident dumbbell first vs last FY on a log axis with % change; 100% stacked bars by spending category (7 fixed slots). Callout `pf_trend`. Slots `change_real, change_nominal, change_per_res`.
- **`pf-staffing`** — Overtime share bars (n = headcount; click → scorecard); overtime dollars stacked by department group per FY; headcount lines (top 7); table of where overtime goes (largest job family, employees over $100k in overtime). Nobody below executive level is named. Slots `headcount_fmt, ot_total, ot_share, ot100k_fmt`.
- **`pf-outcomes`** — Heat grid department × FY of the share of measures met (grey/parenthesised under 3 measures; click → scorecard); 100% stacked bars met / missed / not reported by measure type (polarity colours); table of every measure for the latest FY with met tag and target movement. Dollars absent. Slots `measures, met_fmt, met_share, met_share_outcome, met_share_output`.
- **`pf-cost`** — Indexed real unit-cost lines for up to 8 linked measures; table of unit cost first/last FY with real change and program cost; card caveat on the mapping. Slots `measures, median_change, fy0, fy1`.
- **`pf-integrity`** — Stacked columns by FY: measures dropped, targets made easier, of which the year after a miss (subset drawn separately); bars of easier-target share by department (n = target changes); full list with `pattern` tags ("was being missed", "after a miss"). Dollars absent. Slots `dropped_fmt, dropped_missed_fmt, lowered_fmt, lowered_after_miss_fmt`.
- **`pf-gaps`** — Diverging horizontal bars of actual ÷ original budget − 1 for the latest FY (blue over, red under; legend; tooltip carries budget, actual and dollar gap); diverging heat grid department × FY clamped at ±15% (short year labels when narrow); bars of gap by spending category. Slots `gap_total, gap_pct, over_fmt, under_fmt`.
- **`pf-depts`** — Directory table (→ scorecard).

### 5.4 Dashboard 3 — Audit recommendations tracker (`au-*`)
Scope: one recommendation table filtered by year issued, source, department, topic; reports = those with a surviving recommendation. Registers recommendations and reports.
- **`au-overview`** — Tiles: recommendations, implemented share, median months to implement, open or in progress (with count issued > 2 years ago). Cards: 100% stacked status by recommender (5-step ordinal scale; grey = closed without implementation, red = will not implement); recommendations issued by year stacked by source (click a column → that year).
- **`au-status`** — 100% stacked status by department sorted by open share (click → scorecard; small departments greyed); status by topic; implemented share by year issued as lines per source (blank under small_n). Slots `impl_share, prog_share, open_share, notimpl_share`.
- **`au-time`** — Range bars of months to implement by recommender and by priority; 6-month histogram; step curves "share implemented within N months" by year issued (cumulative incidence with never-implemented as not-yet; cohorts truncated where unobservable). Inline caveat on rounding to follow-up cadence. Slots `impl, median_months, p75_months, p90_months`.
- **`au-agreement`** — 100% stacked response by recommender (agree blue, disagree red, partial/none grey); heat grid response × status (short column labels); table of every disagreement with report links. Slots `agree_share, partial_share, disagree_share, impl_agreed, impl_disagreed`.
- **`au-repeat`** — Repeats by department (n = all recommendations); repeat share by topic; chains table linking each repeat to its predecessor's report. High-severity caveat on coding. Slots `repeats_fmt, repeat_share, top_topic, top_topic_fmt`.
- **`au-open`** — Reading note on the consequence score; histogram of open recommendations by score (7+ orange); range bars of age by recommender; ranked list with score tag, reason, response, status pill, dollars, report link. Slots `open, high_fmt, dollars`.
- **`au-reports`** — Report directory (counts reflect filters; → report page).

### 5.5 Dashboard 4 — Money network (`nw-*`)
Scope: flows filtered by date, type, either endpoint's type, minimum amount; entity map; `link(id)` routes officials → official page, departments → scorecard, others → org profile. Fairness box on every analysis view; rule boxes (`meta.rules`) cite the code section and carry a "to verify" line.
- **`nw-overview`** — Tiles: flows in filter (with dollar total), entities connected (with aggregate-individual node count), behested payments, contributions that appear to warrant review ("not proof"). Cards: dollars by year stacked by flow type (contacts excluded, stated); entities by type bars (individuals counted as aggregate nodes).
- **`nw-graph`** — The interactive network. Tools: find-an-entity (datalist), edge budget (top 40/80/160/all), clear focus, table twin. Pruning keeps the strongest edges by amount (contacts weighted by count at a stated constant) plus the selected node's whole neighborhood; layout is a deterministic force simulation with a gravity well per cluster (officials and committees · city departments · lobbyists · nonprofits · contractors, PACs and affiliated individuals) so the same filters always give the same picture; node size = connected dollars; colour = entity type; edges curved, thickness by amount; labels only for the top 10 nodes plus the focused neighborhood (halo stroke); individuals are dashed grey aggregate nodes. Side panel: selected entity's type, individuals aggregated (if any), "Open profile", flows in/out, neighbors, ten largest flows with `appears to warrant review · §1.126` where flagged. Live: entities and edges shown, hidden weaker edges. `v.focus`, `v.edges`.
- **`nw-ban`** — Rule box §1.126; fairness box with base rate. Dot strip of contractor-affiliated contribution records by days from the nearest contract approval, shaded window (drawn at its typical position; each record is judged against its own contract's exact window and the rule in force that day), colour outside / inside / inside and covered official; bars observed vs expected by chance; table of records that appear to warrant review with the reason (why) and profile links. Flow type absent. Slots `records, contracts_fmt, inside_fmt, inside_share, expected_share, covered_fmt`.
- **`nw-behested`** — Rule box; stacked columns by year × payor type with a 2022 ordinance marker; bars by official (click → profile); payments table with `interested party` pattern tag and filed-on-time column. Slots `payments, total, officials_fmt, interested_share, late_fmt`.
- **`nw-lobby`** — Rule box; heat grid clients × targets (contacts; click → client profile); topic bars; client → lobbyist payments bars (colour = client type). Flow type and amount absent. Slots `contacts, lobbyists_fmt, clients_fmt, top_target, top_target_fmt, payments_total`.
- **`nw-concentration`** — No filter bar (note). Rule box §1.114; 100% stacked bars by committee (individuals aggregate · contractor-affiliated aggregate · PACs/orgs · nonprofits; click → official); top-10 named-source share bars (n = named sources); committee table. Slots `committees, ind_share, org_share, contr_share`.
- **`nw-loop`** — "Appearing here is not improper" box; rule box. Scatter city payments (log) vs behested received (click → profile); bars of nonprofits whose lobbyists contacted a department that funds them; row-by-row table. Flow type and entity type absent. Slots `orgs, city_total, beh_total, lob_total`.
- **`nw-entities`** — Directory (type dot, flows, dollars in/out, note; individuals not linked).

### 5.6 Entity pages
- **Organization profile (`org`)** — header facts (service area, size, EIN, funded-by links, 990 match method/confidence; for contractors: type, sector, disclosed principals counted not named), badges, links. Sections: *City money* (stacked columns by FY and department; 990 table with city share, reserves, top-executive pay with the "public figure in the filing" note) · *Contracts* · *Controller monitoring results* (each citing report and page) · *Audit findings about the departments that fund this organization* (with the note that an audit of a department is not a finding about its grantees) · *Network connections* (fairness note; flows by type; connections table with counterparty links, behest-of links, review tags; for contractors the ban-window strip with caveat), or "Not in the network data — absence means no disclosed transaction was found".
- **Department scorecard (`dept`)** — header facts (group, actual, vs budget, employees, overtime share) and three filtered-dashboard links. Sections: *Spending and staffing* (real/nominal/budget lines with legend; overtime-share line with headcount as text, never a second axis) · *Performance measures* (every measure, latest year, met tag, target movement, met history) · *Audits* (status by recommender; open recommendations ranked by consequence with report links) · *Nonprofit spending* (largest recipients → profiles) · *Lobbying of this department* (contacts by client → profiles).
- **Report page (`report`)** — facts (issued, by, topic, departments, pages, follow-ups), PDF link (or "URL to be supplied"), summary, recommendations in report order with response, priority, months to implement, dollars, repeat flag, status pill and date; a source-specific note (CGJ mapping / BLA self-report / CSA verification).
- **Official profile (`official`)** — public-role kicker; facts (office, committees, contributions, behested, contacts); fairness note; contributions by source type (individuals aggregated); ban-window strip with caveat; behested payments table; lobbying contacts by client.

### 5.7 Search (`search`)
Index built lazily from `nonprofits/orgs/index.json`, `network/entities.json` (not individuals), `audits/reports/reports.json`, `performance/measures/measures.json`, `site.json › departments` and the view registry. Scoring: prefix > substring in label > substring in key; typeahead shows 8 hits with kind; Enter opens the grouped results page (Department, Nonprofit, Contractor, Official, Committee, Lobbyist firm, Organization, Audit report, Performance measure, Dashboard view). Production may precompute `search/index.json`.

### 5.8 Methods and data (`methods`)
Sources table (dashboard, dataset with id and link, publisher, rows used / total, as-of, notes) · dollars and population · filters that apply (the rule and the dev warning) · small samples · audit status scale and CGJ mapping · consequence score rule · network fairness rules and every legal rule box · file manifest with sizes.

## 6. Shared visual system

### 6.1 Typography
System sans (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`); no display face. Base 15px/1.5. View title 28/700/−0.015em; landing h1 36; finding 18/600; card title 15/650; card subtitle 13 secondary; chart text 11.5–13; tile value 32/650; `tabular-nums` only in tables, ticks and n labels; `--mono` for dataset ids, file paths and rule citations.

### 6.2 Colour roles (validated palette, CSS custom properties in `css/app.css`; charts reference roles, never hex)
| Role | Light | Dark | Used for |
|---|---|---|---|
| Categorical slots 1–8 | `#2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7 #e34948` | `#3987e5 #d95926 #199e70 #c98500 #d55181 #008300 #9085e9 #e66767` | fixed assignments below; adjacent pairs pass CVD ΔE ≥ 8 in both modes; slots 1–3 pass all-pairs (used alone for the three audit recommenders) |
| Nonprofit service areas | slots 1–7 in dimension order (`--c-homeless … --c-other`) | | chips, stacks, scatter, bars |
| Spending categories | slots 1–7 (`--c-salaries … --c-other-char`) | | 100% stacks |
| Audit recommenders | CSA 1 · BLA 2 · CGJ 3 | | chips, stacks, lines, range bars |
| Network entity types | nonprofit 1 · contractor 2 · lobbyist 3 · PAC/other org 4 · committee & official 7 · individuals (aggregate) neutral grey · department ink | | graph nodes, bars, dots |
| Flow types | contribution 7 · behested 5 · lobby contact 3 · lobby payment 4 · contract 2 · city payment 1 | | dollars-by-year stacks, profile bars |
| Ordinal `--ord-1..5` | `#86b6ef #5598e7 #2a78d6 #1c5cab #0d366b` | anchor flipped so the high-contrast end stays "more" | monitoring results, audit status progress, size bands, cohort curves |
| Sequential `--seq-1..7` | `#cde2fb → #0d366b` | flipped | heat grids of shares and counts |
| Diverging | pos `#2a78d6`/`#9ec5f4` · mid `#f0efec` · neg `#f3b0af`/`#e34948` | dark equivalents | over/under budget, met/missed, agree/disagree, ban-window band (neg-1 at 35–45% opacity) |
| Neutral | `#b5b3aa` / `#8f8d85` | `#55544f` / `#75736c` | not reported, closed-other, nominal line, individuals |
| Status (reserved) | good `#0ca30c` warn `#fab219` serious `#ec835a` critical `#d03b3b` | | tags only, with a label |
| Surfaces / ink / grid | page `#f6f6f3` card `#fcfcfb` inset `#f0efec` · ink `#0b0b0b` `#52514e` `#898781` · grid `#e1e0d9` axis `#c3c2b7` | `#0f0f0e #1a1a19 #232322` · `#fff #c3c2b7 #898781` · `#2c2c2a #383835` | |

Rules: colour follows the entity (filtering never recolours survivors); stacking and legend order = slot order; a series count above 7 folds into "Other"; text never wears series colour; UI selection is ink-on-surface (black chips) so the accent is never confused with a series; the amber sample badge and review tag are the only warm UI accents. Three light-mode slots (aqua, yellow, magenta) are under 3:1 on the light surface, so every chart using them carries direct labels or a legend and a table twin.

### 6.3 Light and dark
`data-theme` on `<html>`, set before first paint from URL / localStorage / OS. Dark is its own selected set; ordinal and sequential anchors flip; the review tag, sample badge and severity tags have dark variants; graph labels use a surface-coloured halo stroke. Every view was screenshotted in both modes (`design/shots/`).

### 6.4 Layout
Sidebar 248px; content max 1280px, 28px gutters; 12-column grid with 16px gaps (spans 5/7, 6/6, 4/8, 12); cards 15–18px padding, radius 10, hairline border, soft shadow; tiles 4-up; everything collapses to one column under 1100px. Sticky top bar (51px) and filter bar; story bar fixed at the bottom with 130px content padding.

### 6.5 Chart specs (`js/charts.js`)
Bars ≤ 26px thick (18–24 typical), 4px rounded data end, square at the baseline; 2px surface gap between stacked segments; value label at the bar tip, moved inside the bar (white) or clamped when it would run into the n column; n at the right margin (muted). Lines 2px round-joined, markers r 3.5 with a 2px surface ring when ≤ 20 points; step form for cumulative curves; end labels for ≤ 4 series with 14px collision nudging, else a legend. Gridlines solid hairline, baseline darker; tick count derived from width; a tick above the plot is dropped. Heat grids: 7-step sequential or 5-step diverging with a scale legend; in-cell values when the cell is ≥ 34px wide; column labels shortened when cells are narrow; small-n cells parenthesised. Range bars: p25–p75 box, median tick, p90 dot. Dumbbell: grey first dot, blue second, difference at right. Dot strip: relative-time axis, shaded window with label, dots sized by amount with deterministic row jitter. Slope: labels nudged on both sides, log option. Histogram: highlight set in slot 2. Scatter: log-x option, reference line, trend line, legend. Tooltip: one fixed element (title; colour key · **value** · label; muted rows for n / notes / "Click to open"); crosshair on line charts snapping to the nearest x; hit targets ≥ 24px (whole row/column band, 12px radius on dots).

### 6.6 Network graph (`js/network.js`)
Deterministic layout (hash-seeded positions, 160–240 iterations, repulsion, edge springs, per-cluster gravity, centre gravity, clamped to the canvas); nodes r 5–27 by connected dollars; edges curved (12% of length) with width 1–10 by amount and opacity by weight; dimmed to 6% outside the selected neighborhood; cluster labels above each group; ≤ ~150 nodes after pruning stays readable and renders in < 100 ms.

### 6.7 Tables
`dataTable`: sortable headers (`aria-sort`), filter box, "x of y rows", "Show N more" paging, entity links, tags and status pills in cells; the table twin of a chart is a plain table with the same data. Column text uses `text()` for both display and search.

## 7. Accessibility and performance
- Contrast: body ≥ 7:1, secondary ≥ 4.5:1, muted 3.6:1 at 11.5px+ paired with a value; series below 3:1 always carry labels/legend plus a table twin; status and review colours ship with a label, never alone.
- Every SVG has `role="img"` and a `<title>`; every mark group is focusable with an equivalent tooltip; the graph's nodes are `role="button"` with `aria-label`; popovers are `aria-haspopup`/`aria-expanded`; the data strip is a labelled region; skip link; `prefers-reduced-motion` disables all motion; print stylesheet hides chrome.
- Colour is never the only channel: legends, direct labels, n, italic small-n, dashed aggregate nodes, tags with text.
- Sample total 3.4 MB uncompressed (synthetic scale); production targets: ≤ 400 KB per file, split by year where noted in the contracts, ≤ 1.5 MB per view. Boot loads only the four `meta.json`, `site.json` and four story files (≈ 60 KB). Each view declares `files`; the loader caches in memory; filter changes re-filter arrays in the browser (≤ 20k rows, < 10 ms) and re-render plain SVG (< 60 ms). On `file://` the loader falls back to `sample-data/bundle.js`.

## 8. Notes for the engineer
- Start from the prototype's modules: `js/state.js` (URL + filters), `js/data.js` (loader), `js/stats.js` (deflation, quantiles, incidence, formats), `js/charts.js` (every chart form used), `js/network.js` (graph), `js/commentary.js` (templates, header, caveats, **data panel**), `js/app.js` (shell, filter bar that renders only applicable filters, card/table twin, story, search, keyboard), `js/views-*.js` (one `scope()` per dashboard + one `render(ctx)` per view = the interaction spec), `css/app.css` (tokens).
- Keep the invariants: a view's `filters` list is the only thing the filter bar reads; every card in a view must consume the same scope; register `ctx.feed()` for every dataset a view filters; add an `absent` reason whenever a dashboard filter is omitted; never add a per-chart filter or a dual axis.
- Swap `sample-data/` for the modules' `data/site/` exports; `sample: false` removes the badges; `meta.files` drives the file panel sizes.
- Test: headless Chrome screenshots of every `?view=` in both themes, console clean (`--enable-logging=stderr --dump-dom`), and the `[filters]` warning absent for every filter combination.
