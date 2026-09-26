"""Year-end spending test data: new purchase-order commitments (encumbrances) by department x fiscal year x month
of PO issue date, from Purchasing Commodity Data (ebsh-uavg; po_dt populated FY2018+).
Also saves citywide monthly totals by commodity group for context.
(Vendor Payments PO Summary p5r5-fd7g was rejected: vouchers_paid is not a per-year flow; sums reach $265B+/yr.)
Output: data/raw/yearend/po_dept_fy_month.csv
"""
import os, sys, json, subprocess, urllib.parse
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import RAW

OUT = os.path.join(RAW, 'yearend')
os.makedirs(OUT, exist_ok=True)


def soql(dataset, q, timeout=600):
    url = f'https://data.sf.gov/resource/{dataset}.json?' + urllib.parse.urlencode({'$query': q})
    r = subprocess.run(['perl', '-e', f'alarm {timeout}; exec @ARGV', 'curl', '-s', '-f', url], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'query failed rc={r.returncode}: {q[:120]}')
    return json.loads(r.stdout)


def main():
    rows = []
    for fy in range(2018, 2027):
        q = (f"SELECT purchasing_department, date_extract_y(po_dt) AS y, date_extract_m(po_dt) AS m, count(*) AS n, "
             f"sum(encumbered_amount) AS amt WHERE fiscal_year='{fy}' GROUP BY purchasing_department, y, m LIMIT 50000")
        d = pd.DataFrame(soql('ebsh-uavg', q))
        d['fy'] = fy
        rows.append(d)
        print(fy, len(d), flush=True)
    d = pd.concat(rows)
    d['amt'] = d.amt.astype(float)
    d['n'] = d.n.astype(int)
    d.to_csv(os.path.join(OUT, 'po_dept_fy_month.csv'), index=False)
    with open(os.path.join(OUT, 'po_dept_fy_month.source.txt'), 'w') as f:
        f.write('https://data.sf.gov/resource/ebsh-uavg.json (Purchasing Commodity Data), SoQL aggregate by purchasing_department, month of po_dt, fiscal_year 2018-2026\n')


def fetch_go_bonds():
    """GO Bond program status (m793-kis4) and project list (d3dc-v5yr) for the capital-pace analysis."""
    out = os.path.join(RAW, 'capital'); os.makedirs(out, exist_ok=True)
    for ds in ['m793-kis4', 'd3dc-v5yr']:
        for url, fn in [(f'https://data.sf.gov/api/views/{ds}.json', f'meta_{ds}.json'),
                        (f'https://data.sf.gov/api/views/{ds}/rows.csv?accessType=DOWNLOAD', f'{ds}.csv')]:
            r = subprocess.run(['perl', '-e', 'alarm 300; exec @ARGV', 'curl', '-s', '-f', '-o', os.path.join(out, fn), url])
            if r.returncode != 0:
                raise RuntimeError(f'download failed: {url}')


if __name__ == '__main__':
    main()
    fetch_go_bonds()
