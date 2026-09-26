#!/bin/zsh
# Rerun the audits pipeline end to end. Network and LLM calls are cached
# (data/cache/html, data/cache/llm), so a rerun only pays for new or changed inputs.
# Every step is wrapped with a timeout (no `timeout` binary on macOS).
set -e
cd "$(dirname "$0")"
T() { perl -e 'alarm shift; exec @ARGV' "$@"; }

T 5400 python3 01_inventory.py cgj_status cgj bla controller
T 900  python3 util_fix_missing_urls.py            # re-locate 404'd sf.gov PDFs (exact title match)
T 7200 python3 02_download.py
T 600  python3 02b_dedupe.py
T 14400 python3 03_extract.py reports --workers 8
T 14400 python3 03_extract.py status --workers 6
T 1800 python3 04_normalize.py
T 3600 python3 05_link.py
T 900  python3 07_build_rows.py
T 3600 python3 08a_verify_dollars.py
T 3600 python3 08_dollars.py
T 7200 python3 09_repeats.py cluster
T 3600 python3 09_repeats.py validate
T 900  python3 11_export_site.py prepare
T 900  python3 10_analysis.py
T 900  python3 10b_redteam.py
# red team 2 (independent re-derivation, disagreement reasons, PDF spot-check; LLM calls cached)
T 600  python3 redteam2/rederive.py
T 1800 python3 redteam2/reasons.py
T 1800 python3 redteam2/spotcheck.py
T 900  python3 12_commentary.py
T 600  python3 verify_commentary.py                  # must report 0 failures / 0 untraced numbers
T 5400 python3 11_export_site.py headcheck
T 900  python3 11_export_site.py export
T 300  python3 redteam2/build_redteam2.py            # data/redteam/redteam2.json
# insights page (audits/data/site/insights/insights.json; LLM calls cached, task prefix insights_)
T 5400 python3 insights/classify_actions.py          # Sonnet: kind of action asked for, per distinct recommendation
T 1800 python3 insights/field_followups.py           # Opus: read every CSA field follow-up memo
T 900  python3 insights/screen_candidates.py         # record of tested-and-dropped candidates
T 900  python3 insights/build_insights.py            # -> data/site/insights/insights.json
T 900  python3 insights/verify_insights.py           # recomputes every number and checks every quote; must report 0 failures
# optional (cached): python3 insights/fairness_review_insights.py [--pass2]   (Opus fairness and framing review)
# QC (optional, costs Opus calls): python3 06_qc_compare.py sample; then
#   python3 03_extract.py reports --model opus --ids <sample>; python3 03_extract.py status --model opus --ids <sample>
#   python3 06_qc_compare.py compare
