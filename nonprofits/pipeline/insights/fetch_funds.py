"""Fetch Vendor Payments (n9pm-xkyq) aggregated by fund, FY2016-FY2026, for the insights page.

The main pipeline's aggregates (01_fetch_payments.py) carry fund TYPE only; the growth-by-funding-source insight needs
the fund itself (e.g. 'SR Our City Our Home Fund'). One row per (fiscal_year, vendor, department_code, fund_type_code,
fund_code, fund, character_code) with sum(vouchers_paid), for the expenditure characters used by the pipeline.
Output: data/raw/insights/payments_fund_fy{YYYY}.csv (skips files that exist). Every call has a timeout.
"""
import csv, io, os, subprocess, sys, time, urllib.parse

BASE = "https://data.sf.gov/resource/n9pm-xkyq.csv"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "raw", "insights")
PAGE = 50000
CHARS = ("'521','538','539','540','560','520','NON_PERS_SVCS','AID_ASSIST','OTH_SUP_CARE_PERS','CITY_GR_PROG','MTL_SUPP',"
         "'CAP_OUTLAY','AID_PMTS','FAC_MNTC','PROG_PROJ','CAP_EXP'")
GROUP = "fiscal_year, vendor, department_code, fund_type_code, fund_code, fund, character_code"


def soql(query, timeout=300):
    url = BASE + "?" + urllib.parse.urlencode({"$query": query})
    for attempt in range(5):
        r = subprocess.run(["perl", "-e", f"alarm {timeout}; exec @ARGV", "curl", "-s", "-f", url], capture_output=True)
        if r.returncode == 0:
            return list(csv.DictReader(io.StringIO(r.stdout.decode("utf-8"))))
        print("  retry", attempt, r.returncode, file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError("query failed: " + query[:200])


def fetch_year(fy):
    path = os.path.join(OUT, f"payments_fund_fy{fy}.csv")
    if os.path.exists(path):
        return
    rows, off = [], 0
    while True:
        q = (f"SELECT {GROUP}, sum(vouchers_paid) as paid WHERE fiscal_year='{fy}' AND character_code in ({CHARS}) "
             f"GROUP BY {GROUP} ORDER BY {GROUP} LIMIT {PAGE} OFFSET {off}")
        page = soql(q)
        rows += page
        print(fy, off, len(page), flush=True)
        if len(page) < PAGE:
            break
        off += PAGE
    cols = [c.strip() for c in GROUP.split(",")] + ["paid"]
    with open(path + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.rename(path + ".tmp", path)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    years = [int(a) for a in sys.argv[1:]] or list(range(2016, 2027))
    for fy in years:
        fetch_year(fy)
