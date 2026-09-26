#!/bin/sh
# Re-download raw inputs for pipeline/outcomes_build.py. Every call has a timeout (RULES.md).
set -e
cd "$(dirname "$0")/../data/outcomes/raw"
T() { perl -e 'alarm shift; exec @ARGV' "$@"; }
for id in 6dpt-7w23 kc49-udxn 5x94-tptc 6h77-suve ubf6-e57x; do
  T 300 curl -sf "https://data.sf.gov/api/views/$id/rows.csv?accessType=DOWNLOAD" -o "$id.csv"
  T 60 curl -sf "https://data.sf.gov/api/views/$id.json" -o "meta_$id.json"
  T 60 curl -sf "https://data.sf.gov/resource/$id.json?\$select=count(*)" -o "cnt_$id.json"
done
T 60 curl -sfL "https://www.sf.gov/2026-point-in-time-count-preliminary-results" -o sfgov_2026_PIT_prelim.html
T 120 curl -sfL "https://api.sf.gov/documents/31917/2024_San_Francisco_Point-in-Time_Count_Report_8_13_24.pdf" -o hsh_2024_PIT_report.pdf
# Archived June 2023 Scorecard snapshot (old HSH/DPH measure titles), gzip-encoded by Wayback:
T 200 curl -sfL "https://web.archive.org/web/20230605055019id_/https://data.sfgov.org/api/views/kc49-udxn/rows.csv?accessType=DOWNLOAD" -o w.gz
(gunzip -c w.gz > wayback_20230605_kc49-udxn.csv 2>/dev/null || mv w.gz wayback_20230605_kc49-udxn.csv); rm -f w.gz
