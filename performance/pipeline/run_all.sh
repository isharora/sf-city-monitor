#!/bin/bash
# Rerun the Budget-vs-outcomes pipeline end to end.
#   ./run_all.sh            full run (downloads + analysis; Claude steps reuse the on-disk cache in data/cache/llm)
#   ./run_all.sh --no-fetch analysis only, from files already in data/raw
# Every network call inside the scripts is wrapped in a perl alarm timeout (RULES.md). Claude calls are logged to
# data/llm_usage.jsonl and cached; a cached rerun costs nothing.
set -euo pipefail
cd "$(dirname "$0")"
T(){ perl -e "alarm $1; exec @ARGV" "${@:2}"; }
if [ "${1:-}" != "--no-fetch" ]; then
  T 3600 ./01_download_core.sh                     # Budget, Spending & Revenue, Employee Compensation
  T 3600 python3 10_fetch_perf_measures.py         # Controller measures datasets + report PDFs + budget book
  T 7200 python3 11_fetch_outcomes.py              # Fire/EMS, Police, 311 (chunked) + aggregation
  T 1800 python3 11b_fetch_static_outcomes.py      # street evaluations, City Survey, scorecards, NTD
  T 1800 python3 11c_aggregate_static_outcomes.py
  T 1800 python3 12_fetch_context.py               # CPI, population, budgeted/actual FTE
  T 1800 python3 14_fetch_yearend.py               # PO commitments by month; GO bond status
fi
python3 02_spending.py                             # spending cube (budget vs actual)
python3 03_workforce.py                            # headcount, FTE, overtime
python3 04_measures.py                             # Controller measures (current set + FY13/14 snapshots)
python3 05_normalize.py                            # deflate (Bay Area CPI-U) and per resident (DOF)
T 7200 python3 06_map_measures.py                  # Claude Sonnet + Opus: measure -> department/program/budget lines
python3 07_analyses_finance.py                     # budget execution, overtime budget, GO bonds, year-end, OT vs vacancy
python3 08_targets.py                              # attainment, target easing, restatements
python3 09_spend_vs_perf.py                        # real spending vs own measures (+ robustness variants)
T 10800 python3 13_extract_pdf_measures.py         # Claude Sonnet: transcribe annual report PDFs
python3 10a_parse_pdf_measures.py
T 5400 python3 10b_lineage.py                      # Claude Opus: measure lineages across years
T 1800 python3 10c_lineage_analysis.py             # dropped/redefined tests (+ Sonnet pairwise transitions)
T 1800 python3 10d_classify_titles.py              # Claude Sonnet: types for historical titles
python3 11_outcomes_cost.py                        # direct outcome panel, cost per outcome
T 1800 python3 18_budget_book_divisions.py         # Claude Sonnet: budget-book division tables
python3 15_redteam.py                              # independent re-derivations and robustness
python3 16_export_site.py                          # data/site/ per design/DATA_CONTRACT_performance.md
python3 17_commentary.py                           # commentary/pf-*.json, story, facts (first pass)
T 3600 python3 15b_redteam2.py                     # red team 2 -> data/redteam/redteam2.json
python3 17b_commentary.py                          # commentary rewrite (replaces 17's output) + scorecard commentary; --review for Opus fairness pass
python3 verify_commentary.py                       # fails the run on any untraced or mismatched number
python3 21_qa_contract.py                          # contract QA + meta.files
python3 insights/screen_candidates.py              # insights page: record of tested-and-dropped candidates
python3 insights/build_insights.py                 # insights page -> data/site/insights/insights.json
python3 insights/verify_insights.py                # recomputes every insight number from raw tables; fails on any mismatch
# optional (cached): insights/fairness_review_insights.py [--pass2]  (Opus fairness and framing review of the insights)
# optional validation passes (cached): 19_validate_lineage.py (Opus blind re-run), 20_fairness_review.py [--site]
echo "done"
