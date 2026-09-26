"""Loaders shared by compute_build.py and screen_candidates.py (the BUILD side of the insights page).

Source tables (all under nonprofits/data/):
  site/payments/cells_<fy>.json   payments per (fy, dept, org), nominal $  (red-team re-derived from raw vouchers)
  site/orgs/index.json            organizations (EIN, service area, name)
  site/meta.json                  deflator (SF-Oakland-Hayward CPI-U, FY2025 = 1)
  site/finances/form990_<fy>.json Form 990 rows aligned to city fiscal year
  site/reviews/findings.json      Controller monitoring results per org-year
  site/contracts/all_<n>.json     prime contracts >= $250k with purchasing-authority class
  site/aggregates/outcomes.json   outcome measures (Controller / HSH)
  raw/insights/payments_fund_fy<fy>.csv   Vendor Payments by fund (pipeline/insights/fetch_funds.py)
  raw/supplier_contracts.csv      Supplier Contracts (cqi5-hm2d) current extract
  redteam/redteam.json, redteam/parts/*.json   red-team results
  reviews/text/monitoring_FY*_annual_report.txt  Controller monitoring report text
verify_insights.py does NOT import this file; it has its own loaders.
"""
import glob, json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))           # nonprofits/
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(DATA, 'site')
RAW = os.path.join(DATA, 'raw')
sys.path.insert(0, os.path.join(ROOT, 'pipeline', 'redteam'))
from rt_findings import PASS_THROUGH_ORGS  # noqa: E402  (definition shared with the red team)

PASS = {'org-' + e for e in PASS_THROUGH_ORGS}
_c = {}


def memo(k, f):
    if k not in _c:
        _c[k] = f()
    return _c[k]


def jl(p):
    return json.load(open(os.path.join(DATA, p)))


def defl():
    return memo('defl', lambda: {int(k): float(v) for k, v in jl('site/meta.json')['deflator']['index'].items()})


def cells():
    def f():
        c = pd.concat([pd.DataFrame(json.load(open(p))['cells']) for p in sorted(glob.glob(os.path.join(SITE, 'payments', 'cells_*.json')))])
        D = defl()
        c['real'] = c.amt / c.fy.map(D)
        c['area'] = c.org.map(orgs().area)
        return c
    return memo('cells', f)


def orgs():
    return memo('orgs', lambda: pd.DataFrame(jl('site/orgs/index.json')['orgs']).set_index('id'))


def org_fy(col='amt'):
    return memo('ofy' + col, lambda: cells().groupby(['org', 'fy'])[col].sum().unstack().fillna(0.0))


def fin():
    def f():
        fr = []
        for p in sorted(glob.glob(os.path.join(SITE, 'finances', 'form990_20*.json'))):
            r = json.load(open(p))['rows']
            if r:
                fr.append(pd.DataFrame(r))
        f = pd.concat(fr, ignore_index=True)
        oy = cells().groupby(['org', 'fy']).amt.sum()
        f['city'] = [float(oy.get((o, y), 0.0)) for o, y in zip(f.org, f.fy)]
        f['dep'] = np.where(f.total_revenue > 0, f.city / f.total_revenue.where(f.total_revenue > 0), np.nan)
        f['area'] = f.org.map(orgs().area)
        return f
    return memo('fin', f)


def findings():
    return memo('find', lambda: pd.DataFrame(jl('site/reviews/findings.json')['rows']))


def contracts():
    return memo('con', lambda: pd.concat([pd.DataFrame(json.load(open(p))['contracts'])
                                          for p in sorted(glob.glob(os.path.join(SITE, 'contracts', 'all_*.json')))], ignore_index=True))


def outcomes():
    return memo('out', lambda: pd.DataFrame(jl('site/aggregates/outcomes.json')['rows']))


def redteam():
    return memo('rt', lambda: {f['id']: f for f in jl('redteam/redteam.json')['findings']})


def rt_parts(name):
    return memo('rtp' + name, lambda: jl(f'redteam/parts/{name}.json'))


def funds():
    """Fund-level payments to matched organizations (vendor -> EIN via the pipeline's vendor map)."""
    def f():
        vm = pd.read_parquet(os.path.join(DATA, 'interim', 'vendor_map.parquet'))
        ids = set(orgs().index.str[4:])
        v2e = vm[vm.ein.isin(ids)].drop_duplicates('vendor').set_index('vendor').ein.to_dict()
        fr = []
        for p in sorted(glob.glob(os.path.join(RAW, 'insights', 'payments_fund_fy*.csv'))):
            d = pd.read_csv(p, dtype=str, keep_default_na=False)
            d['paid'] = pd.to_numeric(d.paid, errors='coerce').fillna(0.0)
            d['org'] = d.vendor.map(v2e)
            fr.append(d[d.org.notna()].assign(org=lambda x: 'org-' + x.org))
        d = pd.concat(fr, ignore_index=True)
        d['fiscal_year'] = d.fiscal_year.astype(int)
        return d
    return memo('funds', f)


def report_text(fy):
    return open(os.path.join(DATA, 'reviews', 'text', f'monitoring_FY{fy}_annual_report.txt'), encoding='utf-8').read()
