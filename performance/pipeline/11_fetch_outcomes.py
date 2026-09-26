#!/usr/bin/env python3
"""Fetch direct outcome datasets and aggregate to fiscal year (FY = Jul-Jun, labeled by ending year).

Usage:  python3 pipeline/11_fetch_outcomes.py [fire] [police] [311] [agg]
  fire/police/311: download needed columns in monthly chunks (cached as parquet under
                   data/raw/outcomes/chunks/<name>/YYYY-MM.parquet; existing chunks are skipped)
  agg:             build fiscal-year aggregate CSVs from the cached chunks.
Every network call is time-limited (httpx timeout + perl alarm is used in shell scripts).
Static sources (PIT counts, City Survey, street evaluations, Muni, library) are fetched by
pipeline/11b_fetch_static_outcomes.py.
"""
import io, os, sys, time, datetime as dt
import httpx
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'data', 'raw', 'outcomes')
CH = os.path.join(OUT, 'chunks')
BASE = 'https://data.sf.gov/resource/{id}.csv'

SOURCES = {
    'fire': dict(id='nuek-vuh3', date='received_dttm', start=(2000, 7),
                 select='call_number,unit_id,call_type_group,call_type,original_priority,priority,final_priority,unit_type,unit_sequence_in_call_dispatch,received_dttm,entry_dttm,dispatch_dttm,response_dttm,on_scene_dttm'),
    'police': dict(id='2zdj-bwza', date='received_datetime', start=(2015, 1),
                   select='cad_number,dup_cad_number,received_datetime,entry_datetime,dispatch_datetime,enroute_datetime,onscene_datetime,priority_original,priority_final,agency,onview_flag,disposition,call_type_final',
                   where_extra=None),
    '311': dict(id='vw6y-z8j6', date='requested_datetime', start=(2008, 7),
                select='service_request_id,requested_datetime,closed_date,status_description,agency_responsible,service_name,service_subtype,source'),
}


def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def fetch_chunk(client, src, y, m):
    d0 = dt.datetime(y, m, 1)
    d1 = dt.datetime(y + (m == 12), (m % 12) + 1, 1)
    where = f"{src['date']} >= '{d0:%Y-%m-%dT%H:%M:%S}' AND {src['date']} < '{d1:%Y-%m-%dT%H:%M:%S}'"
    params = {'$select': src['select'], '$where': where, '$limit': '10000000', '$order': src['date']}
    for attempt in range(4):
        try:
            r = client.get(BASE.format(id=src['id']), params=params, timeout=httpx.Timeout(300.0, connect=30.0))
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text), dtype=str)
        except Exception as e:  # retry with backoff
            print('  retry', y, m, attempt, repr(e)[:150], flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'failed {y}-{m}')


def download(name):
    src = SOURCES[name]
    d = os.path.join(CH, name)
    os.makedirs(d, exist_ok=True)
    today = dt.date.today()
    last_full = (today.year, today.month)  # include current partial month (flagged in agg)
    with httpx.Client(headers={'Accept': 'text/csv'}) as client:
        for y, m in months(src['start'], last_full):
            fp = os.path.join(d, f'{y:04d}-{m:02d}.parquet')
            if os.path.exists(fp) and (y, m) != last_full:
                continue
            df = fetch_chunk(client, src, y, m)
            df.to_parquet(fp, index=False)
            print(name, y, m, len(df), flush=True)


def fy_of(ts):
    return ts.dt.year + (ts.dt.month >= 7).astype(int)


def load(name):
    d = os.path.join(CH, name)
    fs = sorted(f for f in os.listdir(d) if f.endswith('.parquet'))
    return pd.concat([pd.read_parquet(os.path.join(d, f)) for f in fs], ignore_index=True)


def pct(s, q):
    s = s.dropna()
    return float(np.percentile(s, q)) if len(s) else np.nan


def summarize(g, col):
    return pd.Series({'n': g[col].notna().sum(),
                      'median': g[col].median(),
                      'p90': g[col].quantile(0.9)})


def agg_fire():
    df = load('fire')
    for c in ['received_dttm', 'dispatch_dttm', 'on_scene_dttm']:
        df[c] = pd.to_datetime(df[c], errors='coerce')
    df['fy'] = fy_of(df['received_dttm'])
    df['unit_type'] = df['unit_type'].fillna('')
    # Per call: first unit on scene (any unit), first ambulance (MEDIC/PRIVATE) on scene
    df['is_amb'] = df['unit_type'].isin(['MEDIC', 'PRIVATE'])
    g = df.groupby('call_number')
    calls = g.agg(fy=('fy', 'min'), received=('received_dttm', 'min'), dispatch=('dispatch_dttm', 'min'),
                  onscene=('on_scene_dttm', 'min'), call_type_group=('call_type_group', 'first'),
                  call_type=('call_type', 'first'), orig_priority=('original_priority', 'first'),
                  final_priority=('final_priority', 'first'), units=('unit_id', 'count'))
    a = df[df['is_amb'] & df['on_scene_dttm'].notna()].sort_values('on_scene_dttm').groupby('call_number').first()
    a = pd.DataFrame({'amb_onscene': a['on_scene_dttm'],
                      'amb_disp_to_scene_min': (a['on_scene_dttm'] - a['dispatch_dttm']).dt.total_seconds() / 60})
    calls = calls.join(a)
    calls['resp_min'] = (calls['onscene'] - calls['received']).dt.total_seconds() / 60
    calls['amb_resp_min'] = (calls['amb_onscene'] - calls['received']).dt.total_seconds() / 60
    calls['dispatch_to_scene_min'] = (calls['onscene'] - calls['dispatch']).dt.total_seconds() / 60
    # drop implausible (negative or > 120 min) intervals
    for c in ['resp_min', 'amb_resp_min', 'dispatch_to_scene_min', 'amb_disp_to_scene_min']:
        calls.loc[(calls[c] < 0) | (calls[c] > 120), c] = np.nan
    calls['is_medical'] = calls['call_type'].eq('Medical Incident')
    STRUCT = ['Structure Fire', 'Structure Fire / Smoke in Building']
    calls['is_fire_call'] = calls['call_type_group'].eq('Fire') | calls['call_type'].isin(STRUCT + ['Outside Fire', 'Vehicle Fire'])
    calls['code3'] = calls['final_priority'].astype(str).isin(['3', 'E'])
    rows = []
    for fy, g in calls.groupby('fy'):
        r = {'fy': int(fy), 'calls_total': len(g), 'medical_calls': int(g.is_medical.sum()),
             'fire_calls': int(g.is_fire_call.sum()), 'structure_fire_calls': int(g.call_type.isin(STRUCT).sum()),
             'code3_calls': int(g.code3.sum()), 'months_covered': int(g.received.dt.to_period('M').nunique())}
        amb = g[g.code3 & g.is_medical]['amb_resp_min'].dropna()
        r['code3_medical_ambulance_within_10min_share'] = round(float((amb <= 10).mean()), 4) if len(amb) else np.nan
        ad = g[g.code3 & g.is_medical]['amb_disp_to_scene_min'].dropna()
        r['code3_medical_ambulance_dispatch_to_scene_within_10min_share'] = round(float((ad <= 10).mean()), 4) if len(ad) else np.nan
        sub = {
            'code3_all_first_unit': g[g.code3]['resp_min'],
            'code3_medical_first_unit': g[g.code3 & g.is_medical]['resp_min'],
            'code3_medical_first_ambulance': g[g.code3 & g.is_medical]['amb_resp_min'],
            'code2_medical_first_ambulance': g[(~g.code3) & g.is_medical]['amb_resp_min'],
            'structure_fire_first_unit': g[g.call_type.isin(STRUCT)]['resp_min'],
            'code3_all_dispatch_to_scene': g[g.code3]['dispatch_to_scene_min'],
        }
        for k, s in sub.items():
            r[f'{k}_n'] = int(s.notna().sum()); r[f'{k}_median_min'] = round(pct(s, 50), 2); r[f'{k}_p90_min'] = round(pct(s, 90), 2)
        rows.append(r)
    out = pd.DataFrame(rows)
    out['source_url'] = 'https://data.sf.gov/resource/nuek-vuh3'
    out['definition'] = ('Per call (call_number): response = first on_scene_dttm among all units minus earliest received_dttm '
                         '(911 received to first unit on scene). Ambulance = unit_type MEDIC or PRIVATE. Code 3 = final_priority 3/E. '
                         'Intervals <0 or >120 min dropped. ambulance_dispatch_to_scene_within_10min approximates the Controller scorecard measure 973 '
                         '(first ambulance dispatch_dttm -> on_scene_dttm); the scorecard definition is not published in the data, so values differ by ~2-3 pts. '
                         'Structure fire = call_type Structure Fire or Structure Fire / Smoke in Building. Rows before 2000-07-01 or with null received_dttm (46,837) not downloaded.')
    out.to_csv(os.path.join(OUT, 'fire_ems_response_fy.csv'), index=False)
    print(out[['fy', 'calls_total', 'code3_medical_first_unit_median_min', 'code3_medical_first_unit_p90_min']].to_string())


def agg_police():
    df = load('police')
    for c in ['received_datetime', 'dispatch_datetime', 'onscene_datetime']:
        df[c] = pd.to_datetime(df[c], errors='coerce')
    df['fy'] = fy_of(df['received_datetime'])
    base = df[(df.onview_flag == 'N') & (df.agency == 'Police') & df.dup_cad_number.isna()].copy()
    base['resp_min'] = (base.onscene_datetime - base.received_datetime).dt.total_seconds() / 60
    base['disp_to_scene_min'] = (base.onscene_datetime - base.dispatch_datetime).dt.total_seconds() / 60
    base['recv_to_disp_min'] = (base.dispatch_datetime - base.received_datetime).dt.total_seconds() / 60
    for c in ['resp_min', 'disp_to_scene_min', 'recv_to_disp_min']:
        base.loc[(base[c] < 0) | (base[c] > 24 * 60), c] = np.nan
    rows = []
    for (fy, p), g in base.groupby(['fy', 'priority_final']):
        if p not in ('A', 'B', 'C'):
            continue
        rows.append({'fy': int(fy), 'priority': p, 'calls': len(g), 'months_covered': int(g.received_datetime.dt.to_period('M').nunique()), 'calls_with_onscene': int(g.resp_min.notna().sum()),
                     'median_recv_to_onscene_min': round(pct(g.resp_min, 50), 2), 'p90_recv_to_onscene_min': round(pct(g.resp_min, 90), 2),
                     'median_recv_to_dispatch_min': round(pct(g.recv_to_disp_min, 50), 2),
                     'median_dispatch_to_onscene_min': round(pct(g.disp_to_scene_min, 50), 2)})
    out = pd.DataFrame(rows)
    out['source_url'] = 'https://data.sf.gov/resource/2zdj-bwza'
    out['definition'] = ('911-originated (onview_flag=N), primary agency Police, excluding duplicates (dup_cad_number null); '
                         'priority_final A/B/C; response = onscene_datetime - received_datetime (first unit on scene); intervals <0 or >24h dropped.')
    out.to_csv(os.path.join(OUT, 'police_response_fy.csv'), index=False)
    print(out.to_string())


def agg_311():
    df = load('311')
    df['req'] = pd.to_datetime(df.requested_datetime, errors='coerce')
    df['clo'] = pd.to_datetime(df.closed_date, errors='coerce')
    df = df[df.req.notna()].copy()
    df['fy'] = fy_of(df.req)
    df['days'] = (df.clo - df.req).dt.total_seconds() / 86400
    df.loc[df.days < 0, 'days'] = np.nan
    df['closed'] = df.clo.notna()
    df['within3'] = (df.days <= 3).astype(float)
    df['fyc'] = np.where(df.closed, df.clo.dt.year + (df.clo.dt.month >= 7), np.nan)
    df['service_name'] = df.service_name.fillna('(blank)')
    df['agency_responsible'] = df.agency_responsible.fillna('(blank)')
    src = 'https://data.sf.gov/resource/vw6y-z8j6'

    def grp(keys):
        g = df.groupby(keys)
        out = g.agg(opened=('req', 'size'), closed_of_opened=('closed', 'sum'),
                    median_days_to_close=('days', 'median'), share_closed_within_3_days=('within3', 'mean'))
        out['p90_days_to_close'] = g['days'].quantile(0.9)
        ck = ['fyc' if k == 'fy' else k for k in keys]
        c = df[df.closed].groupby(ck).size().rename('closed_in_fy')
        c.index = c.index.set_names(keys)
        if 'fy' in keys:
            c = c.reset_index(); c['fy'] = c['fy'].astype(int); c = c.set_index(keys)['closed_in_fy']
        out = out.join(c, how='outer').reset_index()
        out['source_url'] = src
        return out.round(4)

    t = grp(['fy'])
    t = t.merge(df.groupby('fy').req.apply(lambda s: s.dt.to_period('M').nunique()).rename('months_covered').reset_index(), on='fy')
    t.to_csv(os.path.join(OUT, '311_citywide_fy.csv'), index=False)
    grp(['fy', 'service_name']).to_csv(os.path.join(OUT, '311_by_fy_service.csv'), index=False)
    grp(['fy', 'agency_responsible']).to_csv(os.path.join(OUT, '311_by_fy_agency.csv'), index=False)
    grp(['fy', 'service_name', 'agency_responsible']).to_csv(os.path.join(OUT, '311_by_fy_service_agency.csv'), index=False)
    # definition sidecar
    open(os.path.join(OUT, '311_DEFINITIONS.txt'), 'w').write(
        'FY = fiscal year of requested_datetime (Jul-Jun, labeled by ending year). opened = cases requested in FY. '
        'closed_of_opened = of those, closed by data extract date. days_to_close = closed_date - requested_datetime (negative dropped; '
        'open cases excluded from median/p90, so recent years are biased low). closed_in_fy = cases with closed_date in FY (any request date). '
        'share_closed_within_3_days = share of opened cases closed within 3 days (open counted as not). Source: ' + src + '\n')
    print(t.to_string())


if __name__ == '__main__':
    args = sys.argv[1:] or ['fire', 'police', '311', 'agg']
    for a in args:
        if a in SOURCES:
            download(a)
    if 'agg' in args:
        agg_fire(); agg_police(); agg_311()
    for a in args:
        if a.startswith('agg_'):
            globals()[a]()
