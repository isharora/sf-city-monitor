#!/usr/bin/env python3
"""Download smaller outcome datasets (full CSV exports) from data.sf.gov into data/raw/outcomes/.
Rerunnable; overwrites. All requests time-limited (httpx timeout)."""
import os, sys, httpx, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'data', 'raw', 'outcomes')
DATASETS = {
    'nufj-bfbw': 'city_survey_microdata',
    '83ki-hu3p': 'street_eval_fy13_fy18',
    'qya8-uhsz': 'street_eval_2022_2025',
    'mwjb-biik': '311_call_metrics_monthly',
    'kc49-udxn': 'scorecard_measures_monthly',
    '6dpt-7w23': 'citywide_performance_metrics',
    'i8y7-m763': 'street_eval_fy07_fy11',
}
URL = 'https://data.sf.gov/api/views/{id}/rows.csv?accessType=DOWNLOAD'

def main(ids=None):
    os.makedirs(OUT, exist_ok=True)
    with httpx.Client(follow_redirects=True) as c:
        for i, name in DATASETS.items():
            if ids and i not in ids:
                continue
            r = c.get(URL.format(id=i), timeout=httpx.Timeout(600.0, connect=30.0))
            r.raise_for_status()
            fp = os.path.join(OUT, name + '.csv')
            open(fp, 'wb').write(r.content)
            n = len(pd.read_csv(fp, low_memory=False))
            print(i, name, n, 'rows', flush=True)
            with open(fp.replace('.csv', '.source.txt'), 'w') as f:
                f.write(f'dataset_id={i}\nsource_url={URL.format(id=i)}\nrows={n}\n')

def ntd():
    """FTA NTD Time Series 2.2 (service data & operating expenses by agency), SFMTA ntd_id 90015."""
    url = 'https://data.transportation.gov/resource/ectq-t3k3.csv'
    r = httpx.get(url, params={'$where': "ntd_id='90015'", '$limit': '50000'}, timeout=httpx.Timeout(120.0, connect=30.0))
    r.raise_for_status()
    raw = os.path.join(OUT, 'ntd_sfmta_timeseries_raw.csv')
    open(raw, 'wb').write(r.content)
    d = pd.read_csv(raw)
    p = d.pivot_table(index='report_year', columns='field', values='value', aggfunc='sum')
    p['source_url'] = 'https://data.transportation.gov/resource/ectq-t3k3 (ntd_id=90015)'
    p['note'] = 'NTD report year = SFMTA fiscal year ending June 30 of report_year; all transit modes incl. purchased transportation'
    p.to_csv(os.path.join(OUT, 'ntd_sfmta_service_fy.csv'))
    print('ntd', len(d), 'rows', p.index.min(), '-', p.index.max())


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or 'ntd' in args:
        ntd()
    ids = [a for a in args if a != 'ntd']
    if not args or ids:
        main(ids or None)
