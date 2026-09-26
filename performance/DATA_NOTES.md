# DATA NOTES: Budget vs outcomes module

Sources, field meanings, matching rules and validation for everything in `performance/`. All numbers here were computed
by the code in `pipeline/` and can be regenerated with `pipeline/run_all.sh`. Downloaded 2026-09-26.

---------------------------------------------------------------------------------------------------------------------

## 1. Spending

### 1.1 Sources (verified; row counts match the Socrata API `count(*)`)

| Dataset | ID | Rows | Coverage | What an amount means |
|---|---|---|---|---|
| Budget | `xdgd-c79v` | 409,521 | FY2010–FY2028 | `budget`: the amount in the **Annual Appropriation Ordinance** (the budget as adopted by the Board of Supervisors). FY2027–28 is the adopted two-year budget. No mid-year revisions or supplemental appropriations. |
| Spending and Revenue | `bpnb-jwfb` | 776,841 | FY1999–FY2026 complete; FY2027 partial (Jul–Sep 2026) | `amount`: actual spending (or revenue) booked in the fiscal year, from the Controller's financial system. |

Fiscal year (FY) = July 1 – June 30, labeled by ending year (FY2025 = Jul 2024–Jun 2025). Both datasets have the same
hierarchy: organization group › department › program; character › object › sub-object; fund type › fund › fund category.

### 1.2 What we include as "spending"
* **Spending rows only** (`revenue_or_spending == 'Spending'`).
* **Excluded: fiduciary funds and component units.** Rows with `Related Govt Units = Yes` (actuals) and these fund types
  in both datasets: pension trust, other employee-benefit trust, "Pension, Other Employee and Ot", agency funds,
  investment trust, private-purpose trust, retiree health trust (Prop B), Successor Agency (former Redevelopment Agency),
  component units, SF Transportation Authority, Treasure Island Development Authority, Treasurer's group. These are
  pension payments, pass-through court and school accounts, and separate legal entities, not city services.
  (Removed 4,463 budget rows and 10,844 actual rows.)
* **Character classes.** Every raw `character` label maps to a class in `pipeline/common.py:CHAR_CLASS`. Labels changed
  spelling at the FY2018 system cutover (e.g. "Non Personnel Services" → "Non-Personnel Services"); both map to the same class.
  - Counted as department spending: salaries, benefits (mandatory fringe), non_personnel (contracts, professional
    services, rents, utilities), materials, grants (City Grant Program = grants to community organizations), aid
    (aid payments/assistance, support and care of persons), capital (capital outlay, capitalized expenditures,
    facilities maintenance), projects (programmatic projects; budget-only), debt_service, services_other_depts
    (work orders paid to other City departments), overhead, other.
  - **Excluded as not spending**: transfers (intrafund transfers, transfers out, operating transfers, GF subsidy
    transfers, transfer adjustments = eliminations), reserves (unappropriated revenue retained/designated, carry-forward
    budget-only lines), fiduciary items, and one artifact (below).
* **Artifact excluded: "GFSUP GENERAL FUND SUPPORT" (Budget, FY2019 only).** It adds +$485M to Police, and similar
  amounts to other departments, offset by −$3.47B in General City. It nets to zero citywide and does not appear in any
  other year.
* **Three spending definitions used in the analysis** (all in `data/interim/dept_fy.csv`):
  - `*_all`: all spending classes, all funds (gross department spending).
  - `*_oper_all`: **gross operating spending**, i.e. operating classes (excludes capital, projects, debt service), all
    funds and all fund categories. **This is the primary series for trends** because it is continuous across the FY2018
    cutover for nearly every department (see 1.4).
  - `*_opfund`: all classes within the "Operating" fund category only (used for budget-vs-actual execution rates).
  - `*_gf`: General Fund only (`fund_type_code` in {1G, GEN_FUND}).
  - Citywide totals exclude services_other_depts and overhead, which are internal charges between departments and
    would otherwise double count.

### 1.3 Department crosswalk (renames, code changes, merges): `pipeline/common.py`
* Department codes are stable across names ("POL Police" and "Police" are both POL). FY2018 budget rows are
  double-coded: legacy names hold $9.58B and new-system names $0.92B, so collapsing by code gives the published total
  ($10.50B).
* Code remaps: DSS→HSA (Human Services Agency legacy code), ECD→DEM (Emergency Management), PAB→BOA (Board of Appeals),
  UNA→GEN (General City), and WTR/CWP/HHP/CLP (Water, Wastewater, Hetch Hetchy, CleanPowerSF)→PUC. PUC enterprises had
  separate codes until FY2017 and one code afterward. Merging them keeps the series comparable.
* **Real reorganizations are not merged**; they are listed in `REORGS` and tested in robustness checks:
  - Homelessness & Supportive Housing (HOM) was created in FY2017 from HSA and DPH programs.
  - Police Accountability (DPA, formerly the Office of Citizen Complaints) was a Police program (ACV) until FY2017 and has
    been its own department since FY2018.
  - Early Childhood (DEC) was created in FY2023 from HSA's Office of Early Care & Education and First 5 (CFC).
  - The Agency for Human Rights (AHR) appears in FY2027; Status of Women (WOM) ends in FY2026.
  - A "Sanitation and Streets" (SAS) department has one budget line ($65.9M) and no actuals. It was created by Prop B
    (2020) and abolished by Prop B (2022) before operating.

### 1.4 The FY2018 system cutover (important)
* **Program detail.** Through FY2017 both datasets carry 280–350 real programs (e.g. Police: Patrol, Investigations,
  Airport Police, Office of Citizen Complaints). From FY2018 the `program` field holds only about 10 program *types*
  (Operating, Capital, Administrative, Disaster Recovery, …). **Department × program analysis is therefore only possible
  for FY1999–FY2017 (actuals) and FY2010–FY2017 (budget).** After that, the finest level is department × program type ×
  character × fund.
* **FY2018 conversion entries.** In FY2018 actual capital jumps to $4.23B while non-personnel is −$0.12B. Public Works
  shows $5.1B of all-funds spending (vs $0.6–0.9B in neighboring years) and PUC shows −$2.9B. **DPW and PUC FY2018
  actuals are masked** (set to missing) in `dept_fy.csv`, with `dq_flag` set. An automated scan (value vs mean of adjacent
  years) found no other department-year off by more than 60% with more than $20M at stake, apart from those two and
  their neighbors.
* **New "Unspecified" fund category (FY2018+, actuals only).** It holds $1.2–2.3B a year, mostly PUC power purchases
  (CleanPowerSF), PUC debt service, MOHCD aid and SFMTA overhead. The budget has no such category. This is why
  Operating-fund-category execution rates are not meaningful for PUC (see §5).
* **Citywide actual totals therefore step up at FY2018** (+18% nominal vs +6% budget). Long-run citywide trends are shown
  for the operating-class series and for personnel cost. Personnel (salaries + benefits) is continuous through the cutover:
  $3.41B, $3.67B and $3.77B in FY2017–19.

### 1.5 Budget vs actual comparability
* The Budget dataset is the **original adopted** appropriation. Actuals include spending under supplemental
  appropriations, grants accepted mid-year, and multi-year (continuing) project appropriations from earlier years and
  from bond ordinances, none of which are in the adopted-budget figures. So:
  - For **operating** budgets (fund category "Operating", which lapses annually), actual ÷ adopted is a reasonable
    execution rate.
  - For **capital/projects**, actual regularly exceeds the adopted annual appropriation (e.g. FY2025: $4.78B actual vs
    $4.56B budget in project categories). A year-by-year budget-vs-actual gap **cannot** measure capital underspending.
    We use the GO Bond program status data instead (§5.3).
* Overtime budget vs actual uses objects whose name contains "Overtime" within the Salaries character in both datasets.

---------------------------------------------------------------------------------------------------------------------

## 2. Deflator and population (fork C; `pipeline/12_fetch_context.py`, files in `data/raw/context/`)
* **Deflator: Bay Area CPI-U, BLS series CUURS49BSA0** (San Francisco–Oakland–Hayward, all items, not seasonally
  adjusted, 1982–84 = 100), from the BLS bulk file `https://download.bls.gov/pub/time.series/cu/cu.data.2.Summaries`.
  The fiscal-year index is the simple average of the bimonthly observations falling in Jul–Jun (six readings: Aug, Oct,
  Dec, Feb, Apr, Jun). The missing October 2025 reading (not collected during the federal shutdown) is interpolated from
  its neighbors and flagged. **Real dollars are FY2026 dollars** (multiplier = CPI_FY2026 / CPI_FY). FY2027–28 budget
  figures are left at FY2026 prices (multiplier 1.0, flagged).
  Robustness deflator: national CPI-U (CUUR0000SA0), 12-month FY average.
* **Population: California Department of Finance E-4, January 1** (the midpoint of each fiscal year); FY y uses Jan 1 of
  year y. FY2027–28 are held at 2026 (845,658). Alternative: Census Population Estimates (July 1, vintage-spliced), which
  runs 20–27k (about 2.5–3.3%) below DOF in 2022–2025. Per-resident values would be about 3% higher using Census.

---------------------------------------------------------------------------------------------------------------------

## 3. Workforce (`pipeline/03_workforce.py`)
* **Employee Compensation `88g8-5mnd`** (1,180,053 rows; Fiscal and Calendar years 2013–2026). We use `Year Type = Fiscal`
  only. One row = one employee × job × department × year; a person with two jobs appears twice. Names are never exported.
  - salaries = regular pay; overtime = pay for hours over 40/week; other_salaries = premium, incentive and one-time pay;
    total_benefits = retirement + health/dental (averaged by the Controller for privacy) + other mandatory benefits.
  - `hours` exists only from FY2017. Summed hours ÷ 2,080 exceeds positions in overtime-heavy departments (Police FY2026:
    3,327 "FTE from hours" vs 3,037 people paid), so **hours include overtime hours**. We call it "paid-hours FTE".
  - Payroll overtime vs ledger overtime (Spending and Revenue objects named "Overtime"): Police FY2025 $147.2M vs
    $135.1M (+9%). Citywide, payroll runs 10–19% above the ledger in most years (+34% in FY2017), and only 101 of 195
    department-years with more than $1M agree within 10%. The likely cause is overtime charged to project, work-order or
    premium accounts not labeled "Overtime". We use payroll overtime for staffing views and ledger overtime for
    budget-vs-actual.
* **Positions (fork C)**: "Budget - FTE" `4zfx-f2ts` (budgeted positions from the Annual Salary Ordinance, FY2010–2028)
  and "Spending - FTE" `43jt-u7yn` (actual paid FTE, FY2003–2027).
  - FY2010–18 and FY2025+ include negative "attrition savings" lines, meaning positions budgeted on the assumption they
    stay vacant. FY2019–24 have none. We report **gross budgeted FTE** (positive lines) in every year and **net budgeted
    FTE** only where attrition lines exist.
  - Vacancy = budgeted − actual paid FTE. Actual FTE is unreliable in FY2018–2020 (FY2019 jumps by 3,750, FY2020
    spikes), so we use FY2021+ for vacancy analysis.

---------------------------------------------------------------------------------------------------------------------

## 4. Performance measures

### 4.1 Current measure set: "San Francisco Citywide Performance Metrics" `6dpt-7w23` (Controller, City Performance Unit)
* 10,164 rows (10,160 with a fiscal year); 732 measures; 51 departments; data as of 2026-06-03.
* Fields:
  - `target`: set at or before the start of the year.
  - `full_year_result`: the actual as of June 30.
  - `mid_year_result` / `mid_year_projection`: as of December 31.
  - `measure_data_type`: Numeric, Percent (stored as a fraction, e.g. 0.81) or Currency.
  - `measure_description`, `measure_methodology`, `strategic_goal`.
* No stable measure ID. We key measures on (department, title): `measure_id` = hash of department + lowercased title
  (`pipeline/04_measures.py`). (department, title, FY) is unique.
* **It holds only today's measures, with their history back-filled** (every one of the 732 has an FY2025-26 row). It
  therefore cannot show dropped measures, which is why we rebuilt the historical lists from the reports (4.3).
* Full-year results exist through FY2025; FY2026 has targets and mid-year values only. FY2002–FY2012 hold only 11–18
  measures each (a few long series).

### 4.2 FY2013 and FY2014 snapshots: `5x94-tptc` (1,002 rows) and `6h77-suve` (1,001 rows)
* The annual performance-report datasets. They carry a stable `KPI_CODE` (999 KPIs), program, goal, **"Performance
  Pattern"** (whether above target is good), unit, actuals for FY2011–14, targets two years ahead, and flags for the
  reports each measure appeared in. Header whitespace is collapsed on load.

### 4.3 Historical measure lists from the annual reports (PDF), FY2006–FY2019 and FY2022
* 15 reports linked from `https://www.sf.gov/san-francisco-performance-program` (fork A; saved in
  `data/raw/perf_measures/reports/`). The FY2020 and FY2021 reports are not linked. The FY2023–25 reports are narrative
  only; the FY2005 report has no tables.
* **Transcription**: `pipeline/13_extract_pdf_measures.py` sends each page (2,400 pages) as a one-page PDF to
  Claude Sonnet, which reads the page visually and as text and returns every measure row with its cells exactly as
  printed (JSON schema; no computation). FY2012's text layer is garbled (font encoding), but the visual read recovers it.
  Output: 92,804 cells; 86,773 parsed into (FY, kind = actual / target / projected / midyear) values; 75,889 numeric.
* **Validation of the transcription** (`data/interim/pdf_extraction_validation.csv`): the FY2013 and FY2014 PDFs were
  matched to the independently published FY13/FY14 snapshot datasets on department + normalized title + FY + kind. For
  same-year and past values, **99.4% of 6,865 value pairs agree** (within 3% or 0.5 absolute, allowing for percent
  scaling): FY2013 actuals 98.7%, targets 99.5%; FY2014 actuals 99.9%, targets 100%. We hand-inspected disagreements
  against the PDF text layer, for example Assessor "Number of documents recorded" FY2010-11, where the PDF prints
  217,287 and the snapshot has 97,355. The transcription was right; the published sources disagree with each other.
  Two-year-ahead targets differ more often (the snapshot and report were produced at different dates), so they are not
  used for validation.
* Department headers are mapped to codes in `pipeline/10a_parse_pdf_measures.py:DMAP`. The FY2019 and FY2022
  "scorecard theme" pages (Livability, Safety Net, …) are tagged `SCORECARD` and excluded from department lineages.

### 4.4 Measure lineage (`pipeline/10b_lineage.py`)
* Every title seen for a department (PDF reports, snapshots, current set) is listed with the report years it appears in.
  Claude Opus (effort high) groups titles into lineages and labels each title *same*, *reworded* or *redefined*
  (definition changed: threshold, population, unit, time window or method), with direction and an internal-admin flag.
  Every title must be assigned exactly once; unassigned titles become singletons (logged).

### 4.5 Measure-to-budget mapping (`pipeline/06_map_measures.py`)
* For each of the 732 current measures, Claude Sonnet (effort medium) is given the title, description, methodology, the
  reporting department's legacy budget programs (FY2013–17 average actuals) and all department codes. It returns
  producing department, legacy program codes, main budget characters, measure kind, direction, volume unit, whether
  cost per unit is meaningful, service area, confidence (0–1) and a rationale.
* Claude Opus (effort high) then:
  - independently re-mapped a random blind sample of 60 measures;
  - adjudicated all 250 Sonnet mappings with confidence below 0.7 (with Sonnet's answer shown). Opus overrides Sonnet
    for adjudicated items and where they disagree on department.
* Agreement, Sonnet vs blind Opus (n = 60): producing department 100%; direction 91.7%; measure kind 85%; program set
  exact 71.7% (any overlap 86.7%; mean Jaccard 0.77); cost-per-unit flag 75%.
* **Hand check** (`data/interim/measure_map_handcheck.csv`, 40 random final mappings reviewed manually):
  - department correct 40/40;
  - program 39.5/40 (DPA measures should point to POL program ACV before FY2018);
  - kind 39/40;
  - direction 38/40 (citations should be neutral; library visits higher-is-better);
  - cost-per-unit 38.5/40.
  Corrections are applied through `pipeline/measure_map_overrides.json`.
* Because the automated cost-per-unit flag is the weakest field (75% agreement), **headline cost-per-outcome figures use
  a curated, explicitly defined list of numerator/denominator pairs** (§6), not the automated flag.

---------------------------------------------------------------------------------------------------------------------

## 5. Direct outcome data (fork B; `pipeline/11_fetch_outcomes.py`, `11b`, `11c`; files in `data/raw/outcomes/`, index `SOURCES.csv`)

| Service | Dataset | Coverage | Definition used |
|---|---|---|---|
| Fire/EMS | `nuek-vuh3` Fire Department & EMS Dispatched Calls for Service (one row per responding unit; about 7.45M rows) | FY2001–FY2026 | Per call: first `on_scene_dttm` of any unit minus earliest `received_dttm` (911 received to first unit on scene). "Life-threatening medical" = medical call types with final priority 3/E. Intervals ≤0 or implausible are dropped. Re-derived in the red team with an independent definition (6.30 vs 6.28 min, FY2025). |
| Police | `2zdj-bwza` Law Enforcement Dispatched Calls for Service: Closed (about 7.93M rows; starts Jan 2015) | FY2016–FY2026 full years | 911-originated (`onview_flag = N`), Police agency, non-duplicate, priority A/B/C; `onscene_datetime − received_datetime`. Matches the Controller's scorecard (Priority A FY2016 6.60 vs 6.6 min). |
| 311 | `vw6y-z8j6` 311 Cases (8,945,994 rows) | FY2009–FY2026 | Opened per FY; closed within 3 days. Days-to-close is biased low in recent years because open cases are excluded. Call-center metrics come from `mwjb-biik`. |
| Streets | `i8y7-m763` (FY2007–11), `83ki-hu3p` (FY2014–18), `qya8-uhsz` (Jan 2022–FY2025) | 3 eras | Methods can't be compared across eras. There are no evaluations Jul 2018–Dec 2021. The 2022+ summaries match the Controller's FY25 report (street litter 2.44; feces on 34% of routes). |
| Muni | `6dpt-7w23` (on-time, service hours delivered) and FTA NTD TS2.2 `ectq-t3k3`, ntd_id 90015 | FY2013–25 / FY2015–24 | NTD report year = SFMTA FY. Covers operating expenses, vehicle revenue hours and unlinked trips, all modes including purchased transportation. |
| Library | `6dpt-7w23` visits (FY2017+), circulation (FY2014+), Library's own expenditures per visit | FY2013–25 | `qzz6-2jup` (Library Usage) is per patron and cannot give visits. |
| Homelessness | `kc49-udxn` point-in-time counts; `6dpt-7w23` exits to permanent housing | PIT 2005–2024 biennial; exits FY2023–25 | Some scorecard series are reported as running year-to-date totals; the year-end value is used. Fork B's scorecard-derived exits (FY2024 5,601) differ slightly from 6dpt (5,556); we use 6dpt. |
| City Survey | `nufj-bfbw` respondent-level (42,720 respondents) | 1996–2023 | Weighted share A or B; 5 = A … 1 = F per codebook. Mode changed from mail to phone in 2015; online and in-person added in 2023; no 2021 survey. |
| GO bonds | `m793-kis4` program status (two snapshots, FY22-23 and FY24-25); `d3dc-v5yr` projects | as of FY2024-25 | Components were restructured between snapshots, so we use the latest snapshot per program (the FY22-23 mix double counted the Seawall). Spent = cash expended excluding encumbrances. |
| Year-end commitments | `ebsh-uavg` Purchasing Commodity Data (`po_dt`, `encumbered_amount`) | FY2018–FY2026 | Server-side aggregation by department × month of PO issue date. Vendor Payments `n9pm-xkyq` has no payment date. `p5r5-fd7g` "vouchers_paid" is cumulative (sums above $265B per year), so it was rejected. |

## 6. Curated cost-per-outcome pairs (`pipeline/11_outcomes_cost.py`, exported to `measures/cost_links.json`)

| Pair | Numerator (actuals, nominal; real = ÷ deflator index) | Denominator | Years |
|---|---|---|---|
| Library cost per visit | Public Library gross operating spending, all funds | Library visits (6dpt) | FY2017–25 |
| Muni cost per revenue hour | NTD operating expenses | NTD vehicle revenue hours | FY2015–24 |
| Muni cost per trip | NTD operating expenses | NTD unlinked trips | FY2015–24 |
| Fire spending per call | Fire Department gross operating spending | Unique Fire/EMS calls (nuek-vuh3) | FY2001–26 |
| Police spending per 911 call | Police gross operating spending | 911-dispatched A/B/C calls (2zdj-bwza) | FY2016–26 |
| 311 center per request | ADM legacy program FFO "311 Call Center" | 311 requests opened | FY2009–17 |
| 311 center per call answered | same | Calls answered (mwjb-biik) | FY2008–17 |
| Street Environmental Services per curb mile swept | DPW legacy program BAZ | Curb miles mechanically swept (6dpt) | FY2013–17 |
| HSH spending per exit to housing | HSH gross operating spending | Exits to permanent housing (6dpt) | FY2023–25 (a ratio, not a placement cost) |

Cross-check: our library figure matches the Library's own published "Expenditures per Number of Visits" within 1% in
FY2018–FY2025 (FY2025: $40.45 vs $40.23).

## 7. Site export and QA
- `data/site/` follows `design/DATA_CONTRACT_performance.md`. Deviations and additions are in `data/site/CONTRACT_GAPS.md`, and the file map in `data/site/README_EXPORT.md` (sources for both kept in `pipeline/site_docs/`).
- `pipeline/21_qa_contract.py` runs the contract's §5 checks (results in `data/site/QA_REPORT.json`):
  - spending totals equal `dept_fy.csv` within $15;
  - all dimension ids are valid;
  - measures: 0 year-range violations, 0 `dropped_fy` violations, 0 `met` recomputation mismatches;
  - no NaN in any file.
- Payroll vs ledger overtime is within 10% for 101 of 195 department-years; the citywide gap is 10–19% (see CONTRACT_GAPS).
- Percent measures are on a 0–100 scale. 51 rows carry a `qa_flag` for source scale inconsistencies or implausible values, kept as published.
- **Validation artifacts:**
  - `data/interim/pdf_extraction_validation.csv` (transcription vs published datasets);
  - `measure_map_handcheck.csv` (40 manual checks);
  - `measure_map_opus.csv` (blind sample and adjudication);
  - `lineage_validation.json` (blind Opus re-run for 6 departments: pair agreement over 99%, link recall 90%, precision 82%);
  - `an_lineage_transitions.csv` (pairwise relation labels);
  - `redteam_results.json` (independent re-derivations);
  - `fairness_review.json`, `fairness_review_site.json` (Opus editorial reviews).
