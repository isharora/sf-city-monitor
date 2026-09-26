#!/bin/zsh
# Raw downloads (every call time-limited). Run from nonprofits/.
set -e
T() { perl -e "alarm $1; exec @ARGV" "${@:2}"; }
mkdir -p data/raw/irs/efile data/raw/wayback data/raw/city_np
# City datasets
T 300 curl -s -f -o data/raw/supplier_contracts.csv "https://data.sf.gov/api/views/cqi5-hm2d/rows.csv?accessType=DOWNLOAD"
for id in qkex-vh98 rhef-rs9s 7yeh-dyn4 3v2z-djjd; do T 300 curl -s -f -o data/raw/city_np/$id.csv "https://data.sf.gov/api/views/$id/rows.csv?accessType=DOWNLOAD"; done
T 900 curl -s -f -o data/raw/sf_business_locations.csv "https://data.sf.gov/api/views/g8m3-pdis/rows.csv?accessType=DOWNLOAD"
T 300 curl -s -G "https://data.sf.gov/resource/n9pm-xkyq.json" --data-urlencode '$query=SELECT department_code, department, organization_group, max(fiscal_year) as last_fy, count(*) as n GROUP BY department_code, department, organization_group LIMIT 1000' -o data/raw/dept_groups.json
for id in n9pm-xkyq cqi5-hm2d; do T 60 curl -s "https://data.sf.gov/api/views/$id.json" -o data/raw/meta_$id.json; done
# Supplier Contracts snapshots archived by the Internet Archive (some are served gzipped)
for ts in 20210422145443 20221206220239 20251102051641; do
  f=data/raw/wayback/supplier_contracts_$ts.csv
  T 600 curl -sL -o $f "http://web.archive.org/web/${ts}id_/https://data.sfgov.org/api/views/cqi5-hm2d/rows.csv?accessType=DOWNLOAD"
  if file $f | grep -q gzip; then mv $f $f.gz; gunzip -f $f.gz; fi
done
# IRS
for f in eo1 eo2 eo3 eo4 eo_ca; do T 300 curl -s -f -o data/raw/irs/$f.csv https://www.irs.gov/pub/irs-soi/$f.csv; done
T 600 curl -s -f -o data/raw/irs/revocations.zip https://apps.irs.gov/pub/epostcard/data-download-revocation.zip && (cd data/raw/irs && unzip -o -q revocations.zip)
for y in 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026; do T 600 curl -s -f -o data/raw/irs/efile/index_$y.csv https://apps.irs.gov/pub/epostcard/990/xml/$y/index_$y.csv; done
T 60 curl -s https://www.irs.gov/charities-non-profits/form-990-series-downloads | grep -o 'https://apps.irs.gov/pub/epostcard/990/xml/[^"< ]*\.zip' | sort -u > data/raw/irs/efile/zip_list.txt
# zips not linked from the page but present on the server (found by probing)
for u in 2017/download990xml_2017_{1..7}.zip 2017/2017_TEOS_XML_CT1.zip 2018/download990xml_2018_{1..7}.zip 2018/2018_TEOS_XML_CT1.zip 2022/2022_TEOS_XML_02A.zip; do echo https://apps.irs.gov/pub/epostcard/990/xml/$u >> data/raw/irs/efile/zip_list.txt; done
sort -u data/raw/irs/efile/zip_list.txt -o data/raw/irs/efile/zip_list.txt
# CPI (BLS flat file; the API was rate-limited)
T 120 curl -s -A "sf-city-monitor research" https://download.bls.gov/pub/time.series/cu/cu.data.2.Summaries -o data/raw/cu_summaries.txt
