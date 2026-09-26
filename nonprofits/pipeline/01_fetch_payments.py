"""Fetch Vendor Payments (n9pm-xkyq), aggregated server-side.

Output: data/raw/payments_agg_fy{YYYY}.csv, one row per
(fiscal_year, vendor, department, program, character, object, fund_type,
 contract_number, contract_title, purchasing_authority_title, non_profit_indicator)
with sums of vouchers_paid / vouchers_pending / count of voucher lines.

Also fetches a timing table for year-end-spike analysis: payments by
(fiscal_year, vendor, department_code, character_code, data_as_of date).
data_as_of is "timestamp the data was updated in the source system" -- the best
available proxy for voucher date (there is no explicit payment date field).
"""
import csv, io, json, os, subprocess, sys, time, urllib.parse

BASE = "https://data.sf.gov/resource/n9pm-xkyq.csv"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PAGE = 50000

def soql(query, timeout=600):
    url = BASE + "?" + urllib.parse.urlencode({"$query": query})
    for attempt in range(5):
        r = subprocess.run(["perl", "-e", f"alarm {timeout}; exec @ARGV", "curl", "-s", "-f", url],
                           capture_output=True)
        if r.returncode == 0:
            return list(csv.DictReader(io.StringIO(r.stdout.decode("utf-8"))))
        print("  retry", attempt, r.returncode, r.stderr[:200], file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("query failed: " + query[:200])

GROUP = ("fiscal_year, vendor, department_code, department, program_code, program, "
         "character_code, character, object_code, object, fund_type_code, contract_number, "
         "contract_title, purchasing_authority_title, non_profit_indicator")

def fetch_year(fy):
    path = os.path.join(OUT, f"payments_agg_fy{fy}.csv")
    if os.path.exists(path):
        return
    rows, off = [], 0
    while True:
        q = (f"SELECT {GROUP}, sum(vouchers_paid) as paid, sum(vouchers_pending) as pending, "
             f"count(*) as n_lines WHERE fiscal_year='{fy}' GROUP BY {GROUP} "
             f"ORDER BY {GROUP} LIMIT {PAGE} OFFSET {off}")
        page = soql(q)
        rows += page
        print(fy, off, len(page), flush=True)
        if len(page) < PAGE:
            break
        off += PAGE
    cols = [c.strip() for c in GROUP.split(",")] + ["paid", "pending", "n_lines"]
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.rename(tmp, path)

TGROUP = "fiscal_year, vendor, department_code, character_code, data_as_of"

def fetch_timing(fy):
    path = os.path.join(OUT, f"payments_timing_fy{fy}.csv")
    if os.path.exists(path):
        return
    rows, off = [], 0
    while True:
        q = (f"SELECT {TGROUP}, sum(vouchers_paid) as paid, count(*) as n_lines "
             f"WHERE fiscal_year='{fy}' AND character_code in ('521','538','539','NON_PERS_SVCS','CITY_GR_PROG','OTH_SUP_CARE_PERS','AID_ASSIST') "
             f"GROUP BY {TGROUP} ORDER BY {TGROUP} LIMIT {PAGE} OFFSET {off}")
        page = soql(q)
        rows += page
        print("timing", fy, off, len(page), flush=True)
        if len(page) < PAGE:
            break
        off += PAGE
    cols = [c.strip() for c in TGROUP.split(",")] + ["paid", "n_lines"]
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.rename(tmp, path)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    years = range(2007, 2028)
    what = sys.argv[1] if len(sys.argv) > 1 else "agg"
    for fy in years:
        if what in ("agg", "all"):
            fetch_year(fy)
        if what in ("timing", "all"):
            fetch_timing(fy)
