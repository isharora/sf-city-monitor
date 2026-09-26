#!/bin/zsh
# End-to-end rerun. LLM calls are cached in data/cache/llm (reruns cost nothing unless inputs change).
set -e
cd "$(dirname $0)/.."
zsh pipeline/00_download.sh
python3 pipeline/01_fetch_payments.py agg
python3 pipeline/01_fetch_payments.py timing
python3 pipeline/02_irs_master.py
python3 pipeline/03_build_payments.py
python3 pipeline/04_candidates.py
python3 pipeline/05_adjudicate.py
python3 pipeline/06_discover.py
python3 pipeline/05b_opus_recheck.py          # second opinion; resolutions in data/manual/match_overrides.csv
python3 pipeline/07_fetch_990.py all
python3 pipeline/08_build_990.py
python3 pipeline/10_core.py
python3 pipeline/09_link_reviews.py
python3 pipeline/11_validation_sample.py       # sample for hand review (verdicts in data/validation/hand_review.csv)
python3 pipeline/12_analysis.py                # includes the corrected IRS-revocation check (pipeline/redteam/rt_revocations.py)
python3 pipeline/13_coverage_validation.py
python3 pipeline/14_outcomes.py
python3 pipeline/15_redteam.py
python3 pipeline/16_export_site.py
python3 pipeline/17_commentary_qa.py           # commentary facts + contract QA
# Red team (independent re-derivation and robustness; Claude calls cached in data/cache/llm)
python3 pipeline/redteam/rt_revocations.py
python3 pipeline/redteam/rt_findings.py
python3 pipeline/redteam/rt_contracts_llm.py
python3 pipeline/redteam/rt_assemble.py        # -> data/redteam/redteam.json
python3 pipeline/18_commentary.py              # commentary from site data + redteam.json (-> data/redteam/commentary_trace.json)
python3 pipeline/verify_commentary.py          # every number traced; exits 1 if any is untraced
# Research inputs built by helper scripts: data/reviews/ (pipeline/reviews_*.py) and data/outcomes/ (pipeline/outcomes_*.{sh,py})
# Insights page (pipeline/insights/): fund-level payments, build, independent verification, screening, Opus fairness review (cached)
python3 pipeline/insights/fetch_funds.py                 # -> data/raw/insights/payments_fund_fy*.csv (skips existing files)
python3 pipeline/insights/build_insights.py              # -> data/site/insights/insights.json, data/insights/insights_values.json
python3 pipeline/insights/verify_insights.py             # recomputes every value from source tables; exits 1 on any failure
python3 pipeline/insights/screen_candidates.py           # -> data/insights/insights_screening.json (tested, not published)
python3 pipeline/insights/fairness_review_insights.py    # -> data/insights/fairness_review_insights.json (decisions: data/insights/fairness_decisions.json)
