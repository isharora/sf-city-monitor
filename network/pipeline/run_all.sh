#!/bin/bash
# Rerun the Money network pipeline end to end (order from network/PROGRESS.md "Rerun order").
#   ./run_all.sh                 full run (downloads + entity resolution + analysis + export + insights)
#   ./run_all.sh --no-fetch      everything after the downloads, from files already in data/raw
#   ./run_all.sh --insights      only the insights page (screening, build, verify, private-name check)
# Claude calls (04, 07b, 14 adjudicate, 15, insights/classify_sectors, insights/fairness_review_insights) are logged to
# data/llm_usage.jsonl and cached in data/cache/llm; a cached rerun costs nothing. Network calls use perl alarm timeouts.
set -euo pipefail
cd "$(dirname "$0")"
T(){ perl -e "alarm $1; exec @ARGV" "${@:2}"; }
MODE="${1:-}"
if [ "$MODE" != "--insights" ]; then
  if [ "$MODE" != "--no-fetch" ]; then
    T 3600 python3 01_download.py                  # DataSF / Ethics Commission downloads -> data/raw + manifest.json
  fi
  T 1800 python3 02_normalize.py                   # -> data/interim/*.parquet
  T 1800 python3 03_mentions.py
  T 1800 python3 03b_extra_pairs.py
  T 7200 python3 04_adjudicate_orgs.py             # Claude Sonnet/Opus org-pair judgments (cached)
  T 1800 python3 05_people.py
  T 1800 python3 06_officials.py
  T 1800 python3 07_resolve.py
  T 3600 python3 07b_entity_types.py               # Claude: person-name detection (cached)
  T 1800 python3 08_network.py
  T 1800 python3 08_network.py strict
  T 1800 python3 08_network.py lenient
  T 3600 python3 09_analysis.py
  for v in strict lenient; do T 3600 python3 09_analysis.py --variant $v --tag $v; done
  for t in 0.7 0.9 0.95; do T 3600 python3 09_analysis.py --person-t $t --tag p0${t#0.}; done
  T 1800 python3 10_validate.py score
  T 1800 python3 12_redteam.py
  T 1800 python3 11_export.py
  T 3600 python3 14_redteam2.py adjudicate          # Opus person-name re-check (cached)
  T 1800 python3 11_export.py
  T 1800 python3 07c_type_exported.py
  T 1800 python3 13_extras.py
  T 3600 python3 15_commentary.py
  T 3600 python3 14_redteam2.py all
  T 1800 python3 verify_commentary.py
fi
# insights page (design/insights/INSIGHTS_CONTRACT.json) -> data/site/insights/insights.json
T 3600 python3 insights/classify_sectors.py       # Claude Sonnet sector labels for organization donors (cached)
T 1800 python3 insights/screen_candidates.py      # record of tested-and-dropped candidates -> data/redteam/insights_screening.json
T 1800 python3 insights/build_insights.py         # -> data/site/insights/insights.json + data/redteam/insights_values.json
T 1800 python3 insights/verify_insights.py        # recomputes every number from the source tables; fails on any mismatch
T 1800 python3 insights/check_private_names.py    # fails if any private individual's name appears in the insights file
# optional (cached): insights/fairness_review_insights.py [--pass2]  (Claude Opus fairness and framing review)
python3 ../../site/tools/bundle.py >/dev/null && echo "bundled"
echo "done"
