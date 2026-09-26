# Contract gaps: performance module

These are the places where `design/DATA_CONTRACT_performance.md` asks for something the data cannot fully support, or
where this export adds to or interprets the contract. No values were invented. QA results are in `QA_REPORT.json`,
produced by `pipeline/21_qa_contract.py`.

## Gaps (the contract asks, the data cannot fully supply)

| Contract item | What is exported | Why |
|---|---|---|
| `spending/cells.revised` | always `null` | The open Budget dataset (`xdgd-c79v`) publishes only the adopted Annual Appropriation Ordinance. Supplemental appropriations and the revised budget are not published at this grain. Gaps are therefore against the adopted budget. |
| Budget before FY2010 | `budget: null` in `spending/cells_pre2010.json` (actuals FY1999–FY2009 only) | The Budget dataset starts in FY2010. |
| `actual` for FY2027–28 | `null` | FY2027 is partial (Jul–Sep 2026). FY2028 is budget only. |
| `actual` for DPW and PUC in FY2018 | `null`, with `dq_flag` | FY2018 financial-system cutover conversion entries: DPW about +$4.5B, PUC about −$2.9B. |
| Operating vs capital gaps | All classes are exported with `char` | Annual gaps are not meaningful for `capital` and `other` (debt service). Those appropriations are multi-year and partly sit in bond ordinances outside the adopted budget. **The gaps view should default to excluding `capital` and `other`, and ideally to `fund: gf`.** For FY2025, General Fund operating spending is 106% of adopted and other-fund operating spending is 128%. The other-fund figure is mostly grants, continuing projects and PUC accounts booked in fund categories the adopted budget does not use. |
| `staffing.fte` before FY2017 | `null` | Employee Compensation has no hours before FY2017. `fte` is paid hours / 2080 and includes overtime hours. |
| `staffing.vacancy` before FY2021 | `null` | Actual paid FTE (`43jt-u7yn`) is unreliable in FY2018–FY2020: FY2019 jumps by 3,750 FTE and FY2020 spikes. |
| `staffing.headcount` | Distinct values of the employee identifier per department-year | The identifier holds names in recent years and numeric IDs in older ones. Two different people with the same name count once, a slight undercount. Names are never exported. |
| QA 3: payroll overtime vs ledger overtime within about 10% | 101 of 195 department-years (with more than $1M) are within 10%. Citywide, payroll overtime runs 10–19% above ledger overtime objects in most years (+34% in FY2017) | Ledger overtime counts only objects named "Overtime". Some overtime is charged to project, work-order and premium-pay accounts. Police FY2025: payroll $147.2M vs ledger $135.1M (+9%). The per-department list is in `QA_REPORT.json › 3_overtime.outside_10pct`. |
| `measures.type` ∈ outcome/output/efficiency | Mapped from a richer classification | quality, satisfaction → outcome; workload, internal_admin → output (with `internal_admin: true`). The original is in `kind_detail` for current measures. Historical titles are typed by Claude Sonnet (`pipeline/10d_classify_titles.py`). |
| `measures.id` = hash of dept + lowercased canonical title | Hash of dept + lowercased **title as published** | One record per title variant, linked by `replaced_by` and `lineage_id`. The lineage label is `lineage_id`. |
| `dropped_fy = last_fy + 1` | Honored. A title is dropped only when its lineage ends without a successor and the lineage is absent from today's set | 6 successor titles had no transcribed values. Their `replaced_by` was set to null, with `replaced_by_note`. 43 titles are `status: "superseded"` (ran alongside another title of the same lineage and ended); they have no `dropped_fy`. |
| Percent measures 0–100 | Honored: current values ×100; report values ×100 when printed with "%" | 98 values exceed 100. Most are legitimate (occupancy 101%, revenue as a percent of budget, percent-change measures). 51 rows carry `qa_flag`: 46 where target and actual are on different scales *in the source* (e.g. target 9.6 vs actual 0.91), and 5 implausible values (e.g. 2,370,400 for a percentage). These are kept as published, not corrected. |
| `met` | Strict comparison in the measure's direction (actual == target counts as met) | The analysis files use a 0.5% tolerance. `pipeline/15_redteam.py` shows results are insensitive to tolerance (0–5%). |
| `target_change` | easier/harder when the target moved more than 0.5% vs the previous FY, same otherwise, new if no previous-year target, null for neutral-direction measures | The analysis (ANALYSIS.md §6) uses a 5% threshold and conditions on the latest result known when the target was set. The live UI counts will be larger. |
| `program_cost` / `cost_per_unit` | Only on the 9 curated pairs in `measures/cost_links.json` | Six of the denominators are not Controller measures but direct dataset counts: Fire/EMS calls, Police 911 calls, 311 requests and calls, Muni revenue hours and trips. They are exported as measures with `derived: true`, no targets and `met: null`. **Exclude `derived` measures from met shares and measure counts.** |
| Commentary headline years | Headlines use FY2025 | FY2026 actuals are as of September 2026 and may change at year-end close. `meta.fiscal_years.max` is 2026 because the data exist. |

## Additions (outside the contract, safe to ignore)

- `spending/cells_pre2010.json`: FY1999–FY2009 actuals, same schema.
- `meta.real_base_fy`, `meta.reorganizations`, `meta.data_quality_masks`, `meta.caveats`, extra `meta.counts`.
- Extra fields:
  - staffing: `people_paid`, `other_salaries`, `benefits`, `total_comp`, `actual_paid_fte`, `budgeted_fte_net`;
  - measures: `status`, `report_years`, `goal`, `description`, `kind_detail`, `service_area`, `mapping` (Claude measure-to-budget mapping with confidence and rationale), `derived`;
  - values: `restated`, `qa_flag`.
- `commentary/facts_pf.json`: headline findings with traced numbers.
- `scorecards/<DEPT>.json`: per-department context, including division budgets from the FY2026–28 budget book, measure change FY15–17 vs FY23–25, spending-vs-performance robustness and unit costs.
- `analyses/*.json`: cross-cutting analyses (see README_EXPORT.md).
- `outcomes/series.json`: direct outcome series (fire/EMS and police response, 311, Muni, library, homelessness, streets, City Survey). Shares here are fractions.
- `spending/divisions_budget_book.json`: division budgets FY2026–FY2028 (Mayor's proposed budget book, transcribed).
- `QA_REPORT.json`, `README_EXPORT.md`, this file.

## Conventions confirmed

- Dollars are nominal. `meta.deflator.index[fy]` = CPI(FY)/CPI(FY2026), base FY2026. Real = nominal / index. FY2027–28 are held at 1.0.
- `meta.files` keys use the `performance/<path>` convention of `design/prototype/sample-data`.
- There are no NaN values in any file (QA `nan_scan` is empty).
