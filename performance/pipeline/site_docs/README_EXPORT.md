# Performance module: site export

Written by `pipeline/16_export_site.py`, `17_commentary.py` and `21_qa_contract.py`. The contract is
`design/DATA_CONTRACT_performance.md`; deviations are listed in `CONTRACT_GAPS.md`. As of 2026-09-26.

| File | Contents |
|---|---|
| `meta.json` | Boot: fiscal years, deflator (base FY2026), population, dimensions (dept/group/char/fund), counts, sources with rows and as-of dates, and every file's size. |
| `spending/cells.json` | FY2010–FY2028, one row per (fy, dept, fund gf/other, char in 7 slots): adopted `budget`, `actual`, `revised: null`, and `dq_flag` on masked rows. Nominal dollars. |
| `spending/cells_pre2010.json` | Actuals FY1999–FY2009, same schema. |
| `spending/divisions_budget_book.json` | Division budgets FY2026 original to FY2028 proposed (budget book). |
| `staffing/cells.json` | Department × FY2013–FY2026: headcount, paid-hours FTE, salaries, overtime, overtime share, employees with more than $100k in overtime, top 3 overtime job families, budgeted FTE, vacancy (FY2021+). |
| `measures/measures.json` | 3,400+ measure titles. `current` means in today's Controller dataset; `replaced`/`dropped`/`superseded` titles come from the annual reports FY2006–FY2022. Linked by `lineage_id` and `replaced_by`. Current measures carry the Claude measure-to-budget `mapping`. |
| `measures/values.json` | Measure × FY targets and actuals (percent on a 0–100 scale), `met`, `target_change`, `source_doc`, `restated`, and `program_cost`/`cost_per_unit` on curated pairs. |
| `measures/cost_links.json` | The 9 curated numerator/denominator pairs, with rationale. |
| `commentary/pf-*.json`, `story_pf.json` | Commentary layer (DESIGN.md §4). Every number is computed from these files. |
| `commentary/facts_pf.json` | Headline findings with numbers and source traces. |
| `analyses/*.json` | budget_execution_summary, overtime_budget_vs_actual, overtime_vs_vacancy, go_bond_programs, go_bond_pace, yearend_po_city, yearend_po_dept, target_easing_test, drop_redefine_test, restatements, dropped_or_redefined_after_miss, spend_vs_perf (+ robustness), cost_per_outcome. |
| `outcomes/series.json` | Direct outcome series by FY. Shares are fractions (0–1). |
| `scorecards/<DEPT>.json` | Per-department precomputed context for the scorecard page. |
| `QA_REPORT.json` | Contract §5 checks. |
