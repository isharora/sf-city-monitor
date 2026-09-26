# PROGRESS — Budget vs outcomes module

## Status log
- [done] Read RULES.md. Created folders: pipeline/, data/raw, data/interim, data/site, data/cache.
- [done] Verified core datasets exist (metadata in data/raw/meta_*.json):
  - Budget xdgd-c79v: FY2010–FY2028 (adopted Annual Appropriation Ordinance), ~24k spending rows/yr (FY2018 has 32,915, to check).
  - Spending & Revenue bpnb-jwfb: FY1999–FY2026 complete; FY2027 partial (Jul–Sep 2026).
  - Employee Compensation 88g8-5mnd: Fiscal & Calendar 2013–2026.
  - 311 Cases vw6y-z8j6: 8.95M rows, 2008-07-01 → 2026-09-25 (aggregate server-side).
- [running] pipeline/01_download_core.sh → data/raw/{budget,spending_revenue,employee_comp}.csv
- [running] Parallel discovery forks: (A) Controller performance measures, (B) direct outcome datasets, (C) CPI/population/vacancies.

## Next
- Build spending cube (pipeline/02_spending.py), deflate/per-capita, headcount (03_workforce.py)
- Outcomes ingest, LLM mapping (05_llm_map.py), cost-per-outcome, analyses, red team, export.

## Files
- pipeline/01_download_core.sh

## Update 2 (spending, workforce, measures)
- [done] pipeline/common.py (dept crosswalk, character classes, fiduciary exclusions, LLM usage logging), pipeline/llm.py (cached/logged/budget-guarded JSON calls).
- [done] pipeline/02_spending.py → data/interim/spend_long.parquet, spend_cube.parquet, spend_dept_fy.csv, spend_city_fy.csv
  - Key facts: FY2019 "GFSUP" artifact excluded; FY2018 double-coded names collapsed by code; program detail only ≤FY2017 (≈10 program types after).
- [done] pipeline/03_workforce.py → data/interim/workforce_*.csv (hours only FY2017+; hours include OT hours).
- [done] Fork A: Controller measures → data/raw/perf_measures/ (6dpt-7w23 current set; 5x94-tptc/6h77-suve FY13/14 snapshots; kc49-udxn scorecards; PDFs FY2005–FY2025).
- [running] pipeline/13_extract_pdf_measures.py (Sonnet, per-page PDF transcription) → data/interim/pdf_measures_{raw.jsonl,long.csv}; log data/interim/pdf_extract.log. Rerun is cache-backed (data/cache/llm).
- [waiting] Fork B (outcomes → data/raw/outcomes/), Fork C (CPI/pop/vacancy → data/raw/context/).

## Update 3
- [done] 04_measures.py → interim/measures_current.csv (732 measures, FY2013–FY2028; results through FY2025), measures_catalog.csv, measures_snapshot_fy13_14.csv (999 KPIs).
- [done] 05_normalize.py → interim/dept_fy.csv, city_fy.csv (real FY2026 $, Bay Area CPI-U; DOF pop). DPW & PUC FY2018 actuals masked (cutover entries).
- [done] 06_map_measures.py → interim/measure_map.csv (Sonnet all 732; Opus adjudicated 250 low-confidence + 60 blind sample). Validation: measure_map_handcheck.csv (40 manual), overrides in pipeline/measure_map_overrides.json.
- [done] 07_analyses_finance.py → an_budget_exec*.csv, an_ot_budget.csv, an_go_bonds*.csv, an_yearend*.csv, an_ot_vacancy.csv
- [done] 14_fetch_yearend.py → raw/yearend/po_dept_fy_month.csv (ebsh-uavg PO commitments by month)
- [running] 13 PDF extraction (restarted w/ 24 workers; cache-backed).
- [waiting] Fork B outcomes.
- Next: 08_lineage (measure lists across years: dropped/redefined/targets lowered), 09_outcomes+cost-per-unit, 10_trends, 11_export, ANALYSIS.md, DATA_NOTES.md, red team (15_redteam.py).

## Update 4
- [done] 13 PDF extraction (2,400 pages, $57.75) → pdf_measures_long.csv; 10a parse → pdf_values.csv, measure_occurrences.csv; validation 99.4% (pdf_extraction_validation.csv)
- [done] 10b lineage (Opus) → measure_lineage.csv (3,504 titles, 2,274 lineages); 10c → an_lineage_events.csv, an_drop_test.csv, an_lineage_transitions.csv (Sonnet pairwise, 1,115), an_target_*_long.csv
- [done] 08_targets.py (attainment, easing, restatements), 09_spend_vs_perf.py (+robust variants), 11_outcomes_cost.py (outcomes_panel.csv, cost_per_outcome.csv)
- [done] Fork B outcomes in raw/outcomes (SOURCES.csv).
- [done] 15_redteam.py → interim/redteam_results.json (all key numbers reproduced)
- Next: 16_export_site.py (JSON; follow design/DATA_CONTRACT_performance.md if present), commentary facts, ANALYSIS.md, DATA_NOTES §5–7, run_all.sh

## Update 5 (final)
- [done] Design contract received; data/site/ exported per design/DATA_CONTRACT_performance.md (16_export_site.py), commentary pf-*.json + story + facts (17_commentary.py), QA (21_qa_contract.py → data/site/QA_REPORT.json, all checks pass; gaps in data/site/CONTRACT_GAPS.md).
- [done] Extra steps: 10d_classify_titles.py, 18_budget_book_divisions.py (budget book division tables), 19_validate_lineage.py (blind Opus), 20_fairness_review.py (Opus editorial review, two passes; edits applied).
- [done] GO bond double count fixed (latest snapshot per program); pace benchmark an_go_bond_pace.csv.
- [done] DATA_NOTES.md complete (§1–7). pipeline/run_all.sh reruns end to end (--no-fetch verified, rc=0, $0 incremental with cache).
- [blocked] ANALYSIS.md: the harness blocks subagents from writing report files; full text returned to the caller in the handback for saving.
- LLM spend: $68.56 of $400 (data/llm_usage.jsonl).

## Update 6 (red team 2 + commentary rewrite)
- [done] pipeline/15b_redteam2.py -> data/redteam/redteam2.json (GF per resident sensitivity; target easing w/o mechanical resets, per dept, MH OR; Fire call- vs dispatch-to-arrival, original vs final priority; Police OT by fund incl. Section 10B, per-hour grid; GO bonds vs Controller FY24-25 GO Bond Program Report (data/raw/capital/reports/); HSH; City Survey from microdata).
- [done] pipeline/17b_commentary.py rewrites commentary/pf-*.json, story_pf.json, facts_pf.json and adds `commentary` to scorecards/*.json; `--review` = one Opus fairness pass (data/redteam/fairness_review2.json, $0.30).
- [done] pipeline/verify_commentary.py -> data/redteam/verify_commentary.json: 0 untraced numbers. All three wired into run_all.sh before 21_qa_contract.py.
- Open: site dept page does not read scorecards/*.json (commentary there is not rendered); site card note on pf-integrity calls after-miss easing "the clearest sign of target-chasing" (site copy, conflicts with finding).

## Update 7 (insights page: ~20 ranked findings)
- [done] Candidate mining and screening; code in pipeline/insights/: compute_build.py (values), spec.py (text/chart templates, all numbers as placeholders), build_insights.py -> data/site/insights/insights.json (+ data/redteam/insights_values.json).
- [done] 18 insights built (police overtime/staffing, Fire demand, homelessness, police response, grants, GF plateau, $100k OT, pensions, vacancies, Muni fares, OT vs budget, City Survey, Library, targets, Seawall bond, redefinitions, budget execution, Airport debt).
- [next] verify_insights.py (independent recomputation from raw tables), screen_candidates.py (dropped ideas), Opus fairness review (fairness_review_insights.py), wire into run_all.sh, bundle.
- [done] verify_insights.py: independent recomputation from raw tables (ledger CSVs, payroll, FTE, BLS CPI, DOF population, call-level Fire/Police chunks, NTD, survey microdata, 6dpt, m793 + Controller report text); 345 values + 1,486 chart points, 0 failures -> data/redteam/verify_insights.json. Mutation-tested (edited text, chart point and value all caught).
- [done] screen_candidates.py -> data/redteam/insights_screening.json (10 dropped candidates with numbers and reasons).
- [done] Opus fairness review, two passes (data/redteam/fairness_review_insights.json, _pass2.json, with applied/declined dispositions); fixes applied in spec.py; $2.6 total.
- [done] run_all.sh: screen_candidates, build_insights, verify_insights added after 21_qa_contract.py.
- Note: site does not read insights.json yet (bundle validates JSON only).
