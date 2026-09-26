#!/bin/bash
# Downloads core DataSF datasets as CSV (full exports). Each call time-limited.
set -u
cd "$(dirname "$0")/../data/raw"
dl(){ id=$1; name=$2; perl -e 'alarm 1800; exec @ARGV' curl -s -f -o "${name}.csv.tmp" "https://data.sf.gov/api/views/${id}/rows.csv?accessType=DOWNLOAD" && mv "${name}.csv.tmp" "${name}.csv" && echo "ok $name $(wc -l < ${name}.csv)" || echo "FAIL $name"; }
dl xdgd-c79v budget &
dl bpnb-jwfb spending_revenue &
dl 88g8-5mnd employee_comp &
wait
