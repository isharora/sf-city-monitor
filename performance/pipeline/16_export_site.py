"""Export dashboard data to data/site/ following design/DATA_CONTRACT_performance.md.

Contract files: meta.json, spending/cells.json (+ spending/cells_pre2010.json history), staffing/cells.json,
measures/measures.json, measures/values.json, measures/cost_links.json. Commentary (commentary/pf-*.json, story_pf.json) is
written by 17_commentary.py; meta.files is finalized by 21_qa_contract.py after all files exist.
Extras (outside the contract, documented in data/site/README_EXPORT.md): scorecards/<DEPT>.json, analyses/*.json,
outcomes/series.json, spending/divisions_budget_book.json.
Conventions: dollars nominal (UI deflates with meta.deflator, base FY2026); percent measures 0-100; null never NaN.
"""
import pandas as pd, numpy as np, os, sys, json, datetime, hashlib, shutil, importlib
sys.path.insert(0, os.path.dirname(__file__))
from common import *

AS_OF = '2026-09-26'
BASE_FY = 2026
tk = importlib.import_module('10a_parse_pdf_measures').title_key

CHAR7 = [('salaries', 'Salaries (regular and premium pay, excluding overtime)'), ('fringe', 'Fringe benefits'), ('overtime', 'Overtime'),
         ('nonpersonnel', 'Non-personnel services, materials and work orders'), ('aid', 'Aid, grants and city grant programs'),
         ('capital', 'Capital, equipment and projects'), ('other', 'Debt service, overhead allocations and other')]
CLASS_TO_CHAR7 = {'salaries': 'salaries', 'benefits': 'fringe', 'non_personnel': 'nonpersonnel', 'materials': 'nonpersonnel',
                  'services_other_depts': 'nonpersonnel', 'grants': 'aid', 'aid': 'aid', 'capital': 'capital', 'projects': 'capital',
                  'debt_service': 'other', 'overhead': 'other', 'other': 'other'}
GROUPS = [('protection', 'Public Protection'), ('works', 'Public Works, Transportation and Commerce'),
          ('welfare', 'Human Welfare and Neighborhood Development'), ('health', 'Community Health'),
          ('culture', 'Culture and Recreation'), ('admin', 'General Administration and Finance')]
ORG_TO_GROUP = {'Public Protection': 'protection', 'Public Works, Transportation & Commerce': 'works',
                'Human Welfare & Neighborhood Development': 'welfare', 'Community Health': 'health',
                'Culture & Recreation': 'culture', 'General Administration & Finance': 'admin', 'General City Responsibilities': 'admin'}
EXCLUDE_DEPTS = {'CCD', 'CTA', 'TJP', 'RDA', 'UNK'}   # pass-through / component units / separate entities
SHORT = {'MTA': 'SFMTA', 'POL': 'Police', 'FIR': 'Fire', 'DPH': 'Public Health', 'HSA': 'HSA', 'HOM': 'HSH', 'DPW': 'Public Works',
         'PUC': 'SFPUC', 'AIR': 'Airport', 'REC': 'Rec and Park', 'LIB': 'Library', 'SHF': 'Sheriff', 'DEM': 'DEM', 'CHF': 'DCYF',
         'MYR': 'Mayor/MOHCD', 'ADM': 'City Admin', 'GEN': 'General City', 'DEC': 'Early Childhood', 'TIS': 'Technology'}


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if (np.isnan(o) or np.isinf(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def dump(rel, obj):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        json.dump(clean(obj), f, separators=(',', ':'), allow_nan=False, ensure_ascii=False)


def recs(df):
    return [clean(r) for r in df.to_dict('records')]


def iround(x):
    return None if x is None or pd.isna(x) else int(round(float(x)))


def mid(dept, title):
    return 'M' + hashlib.sha1(f'{dept}|{str(title).strip().lower()}'.encode()).hexdigest()[:10]


def meta_asof(path):
    try:
        m = json.load(open(path))
        return datetime.datetime.utcfromtimestamp(m['rowsUpdatedAt']).strftime('%Y-%m-%d')
    except Exception:
        return None


def build_depts(cube):
    og = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str, usecols=['Fiscal Year', 'Department Code', 'Organization Group'])
    og['dept'] = og['Department Code'].map(canon_dept)
    og = og.sort_values('Fiscal Year').groupby('dept')['Organization Group'].last()
    mdepts = set(pd.read_csv(os.path.join(INTERIM, 'measure_lineage.csv')).dept) | set(pd.read_csv(os.path.join(INTERIM, 'measures_catalog.csv')).dept)
    depts = sorted((set(cube.dept.dropna()) | mdepts) - EXCLUDE_DEPTS - {'SCORECARD'})
    vals = [{'id': d, 'name': DEPT_NAMES.get(d, d), 'group': ORG_TO_GROUP.get(og.get(d), 'admin'), 'short': SHORT.get(d, DEPT_NAMES.get(d, d))} for d in depts]
    return vals, set(depts)


def spending_cells(dept_ok):
    l = pd.read_parquet(os.path.join(INTERIM, 'spend_long.parquet'), columns=['fy', 'dept', 'char_class', 'overtime', 'gf', 'measure', 'amount'])
    l = l[l.char_class.isin(SPEND_CLASSES) & l.dept.isin(dept_ok)]
    l['char'] = np.where(l.overtime, 'overtime', l.char_class.map(CLASS_TO_CHAR7))
    l['fund'] = np.where(l.gf, 'gf', 'other')
    g = l.groupby(['fy', 'dept', 'fund', 'char', 'measure']).amount.sum().unstack('measure').reset_index()
    g = g.rename_axis(None, axis=1)
    for c in ['budget', 'actual']:
        if c not in g:
            g[c] = np.nan
    g['dq_flag'] = None
    mask = (g.fy == 2018) & g.dept.isin(['DPW', 'PUC'])
    g.loc[mask, 'actual'] = np.nan
    g.loc[mask, 'dq_flag'] = 'FY2018 financial-system cutover conversion entries; actual masked'
    g.loc[g.fy >= 2027, 'actual'] = np.nan
    g.loc[g.fy <= 2009, 'budget'] = np.nan
    g = g[(g.budget.fillna(0).abs() > 0.5) | (g.actual.fillna(0).abs() > 0.5) | g.dq_flag.notna()]
    rows = []
    for r in g.itertuples():
        row = {'fy': int(r.fy), 'dept': r.dept, 'fund': r.fund, 'char': r.char, 'budget': iround(r.budget), 'revised': None, 'actual': iround(r.actual)}
        if r.dq_flag:
            row['dq_flag'] = r.dq_flag
        rows.append(row)
    return rows


def staffing(dept_ok):
    d = pd.read_csv(os.path.join(INTERIM, 'dept_fy.csv'))
    w = pd.read_csv(os.path.join(INTERIM, 'workforce_dept_fy.csv'))
    wj = pd.read_csv(os.path.join(INTERIM, 'workforce_dept_jobfamily_fy.csv'))
    fam = wj[wj.overtime > 0].sort_values('overtime', ascending=False).groupby(['dept', 'fy']).head(3)
    famd = {k: [{'family': f, 'overtime': iround(o)} for f, o in zip(g['Job Family'], g.overtime)] for k, g in fam.groupby(['dept', 'fy'])}
    x = w.merge(d[['dept', 'fy', 'budget_fte_gross', 'budget_fte_net', 'actual_fte']], on=['dept', 'fy'], how='left')
    x = x[x.dept.isin(dept_ok)]
    rows = []
    r1 = lambda v, n=1: None if pd.isna(v) else round(float(v), n)
    for r in x.itertuples():
        vac = (r.budget_fte_gross - r.actual_fte) if (r.fy >= 2021 and pd.notna(r.budget_fte_gross) and pd.notna(r.actual_fte)) else np.nan
        rows.append({'fy': int(r.fy), 'dept': r.dept, 'headcount': iround(r.headcount), 'fte': r1(r.fte_hours),
                     'salaries': iround(r.salaries), 'overtime': iround(r.overtime), 'ot_share': r1(r.ot_share_base_plus_ot, 4),
                     'employees_ot_over_100k': iround(r.employees_ot_over_100k), 'top_ot_job_families': famd.get((r.dept, r.fy), []),
                     'budgeted_fte': r1(r.budget_fte_gross), 'vacancy': r1(vac),
                     'people_paid': iround(r.people_paid), 'other_salaries': iround(r.other_salaries), 'benefits': iround(r.total_benefits),
                     'total_comp': iround(r.total_comp), 'actual_paid_fte': r1(r.actual_fte), 'budgeted_fte_net': r1(r.budget_fte_net)})
    return rows


KIND7 = {'outcome': 'outcome', 'quality': 'outcome', 'satisfaction': 'outcome', 'output': 'output', 'workload': 'output',
         'internal_admin': 'output', 'efficiency': 'efficiency'}
DIR = {'higher_better': 'higher', 'lower_better': 'lower', 'neutral': 'neutral'}


def measures_and_values(dept_ok):
    lin = pd.read_csv(os.path.join(INTERIM, 'measure_lineage.csv'))
    types = pd.read_csv(os.path.join(INTERIM, 'title_types.csv')).rename(columns={'direction': 'dir_hist', 'type': 'type_hist'})
    cat = pd.read_csv(os.path.join(INTERIM, 'measures_catalog.csv'))
    mp = pd.read_csv(os.path.join(INTERIM, 'measure_map.csv'))
    cur = pd.read_csv(os.path.join(INTERIM, 'measures_current.csv'))
    trans = pd.read_csv(os.path.join(INTERIM, 'an_lineage_transitions.csv'))
    pv = pd.read_csv(os.path.join(INTERIM, 'pdf_values.csv'), dtype={'value': str})
    rs = pd.read_csv(os.path.join(INTERIM, 'an_restatements.csv'))
    cat['title_key'] = cat.title.map(tk)
    cat = cat.merge(mp.drop(columns=['dept', 'title', 'data_type']), on='measure_id', how='left').set_index('measure_id', drop=False)
    T = lin.merge(types, on=['dept', 'title_key'], how='left')
    T = T.merge(cat[['dept', 'title_key', 'measure_id']].reset_index(drop=True), on=['dept', 'title_key'], how='left')
    T = T.drop_duplicates(['dept', 'title_key'])
    T['id'] = [m if isinstance(m, str) else mid(d, t) for m, d, t in zip(T.measure_id, T.dept, T.title)]
    T['current'] = T.measure_id.notna()
    T['years'] = T.years.map(json.loads)
    T = T[T.dept.isin(dept_ok)]
    extra = cat[~cat.measure_id.isin(T.measure_id)]
    # ---- values: 6dpt (percent fractions -> 0-100)
    cur = cur.merge(cat[['measure_id', 'data_type']].reset_index(drop=True).rename(columns={'data_type': 'dt'}), on='measure_id', how='left')
    sc = np.where(cur.dt == 'Percent', 100.0, 1.0)
    cv = pd.DataFrame({'measure': cur.measure_id, 'fy': cur.fy, 'target': cur.target * sc, 'actual': cur.result * sc,
                       'source_doc': '6dpt-7w23 Citywide Performance Metrics (Controller; data as of 2026-06-03)'})
    rsa = set(map(tuple, rs[(rs.kind == 'actual') & rs.restated][['measure_id', 'fy']].values))
    cv['restated'] = [True if (m, f) in rsa else None for m, f in zip(cv.measure, cv.fy)]
    # ---- values: annual reports
    pv = pv[pv.kind.isin(['actual', 'target']) & pv.value_num.notna() & (pv.dept != 'SCORECARD')].copy()
    pv['pct'] = pv.value.fillna('').str.contains('%')
    pv['v'] = np.where(pv.pct, pv.value_num * 100.0, pv.value_num)
    pv = pv.merge(T[['dept', 'title_key', 'id']], on=['dept', 'title_key'], how='inner')
    pv['same_year'] = pv.fy == pv.report_fy
    a = pv[pv.kind == 'actual'].sort_values('report_fy').groupby(['id', 'fy']).last()[['v', 'report_fy']]
    t = pv[pv.kind == 'target'].sort_values(['same_year', 'report_fy']).groupby(['id', 'fy']).last()[['v', 'report_fy']]
    j = a.join(t, how='outer', lsuffix='_a', rsuffix='_t').reset_index()
    j = j[j.fy.between(2001, 2022)]
    j['src'] = [int(np.nanmax([ra, rt])) for ra, rt in zip(j.report_fy_a.astype(float), j.report_fy_t.astype(float))]
    pvv = pd.DataFrame({'measure': j.id, 'fy': j.fy.astype(int), 'target': j.v_t, 'actual': j.v_a,
                        'source_doc': ['Controller annual performance report FY%d (PDF)' % s for s in j.src], 'restated': None})
    have = set(zip(cv.measure, cv.fy))
    pvv = pvv[[(m, f) not in have for m, f in zip(pvv.measure, pvv.fy)]]
    V = pd.concat([cv, pvv], ignore_index=True)
    V = V[V.target.notna() | V.actual.notna()]
    # ---- measures
    trel = {(x, y): z for x, y, z in zip(trans['from'], trans['to'], trans.relation)}
    lin_cur = set(T[T.current].lineage_id)
    pv_raw = pv.groupby('id').value.apply(lambda s: s.fillna(''))
    M = []
    for lid, g in T.groupby('lineage_id'):
        g = g.assign(first_rep=g.years.map(min), last_rep=g.years.map(max)).sort_values(['first_rep', 'last_rep'])
        members = list(g.itertuples())
        lin_last = max(m.last_rep for m in members)
        for k, r in enumerate(members):
            succ = None
            if not r.current and r.last_rep < lin_last:
                succ = next((s for s in members[k + 1:] if s.first_rep > r.first_rep and s.id != r.id), None)
            dropped = (not r.current) and succ is None and lid not in lin_cur and r.last_rep == lin_last
            if r.current:
                row = cat.loc[r.measure_id]
                unit = '%' if row.data_type == 'Percent' else ('$' if row.data_type == 'Currency' else (row.volume_unit if isinstance(row.volume_unit, str) and row.volume_unit else 'number'))
                mtype = KIND7.get(row.measure_kind, 'output'); direction = DIR.get(row.direction, 'neutral')
            else:
                raw = pv[pv.id == r.id].value.fillna('')
                unit = '%' if len(raw) and raw.str.contains('%').mean() > 0.5 else ('$' if len(raw) and raw.str.contains(r'\$').mean() > 0.5 else
                        (r.unit_hint if isinstance(r.unit_hint, str) and r.unit_hint not in ('%', '$') else 'number'))
                mtype = r.type_hist if isinstance(r.type_hist, str) else 'output'
                direction = DIR.get(r.direction, None) or (r.dir_hist if isinstance(r.dir_hist, str) else 'neutral')
            status = 'current' if r.current else ('dropped' if dropped else ('replaced' if succ is not None else 'superseded'))
            rec = {'id': r.id, 'dept': r.dept, 'name': r.title, 'unit': unit, 'direction': direction, 'type': mtype,
                   'first_fy': None, 'last_fy': None, 'dropped_fy': None, 'replaced_by': succ.id if succ is not None else None,
                   'lineage_id': lid, 'lineage_note': {'same': 'reworded'}.get(trel.get((r.title, succ.title)) or succ.relation, trel.get((r.title, succ.title)) or succ.relation) if succ is not None else None,
                   'internal_admin': bool(r.internal_admin), 'status': status, 'report_years': [int(y) for y in r.years]}
            if r.current:
                row = cat.loc[r.measure_id]
                rec.update({'goal': row.goal if isinstance(row.goal, str) else None, 'description': row.description if isinstance(row.description, str) else None,
                            'kind_detail': row.measure_kind, 'service_area': row.service_area,
                            'mapping': {'producing_dept': row.producing_dept,
                                        'legacy_programs': json.loads(row.legacy_programs) if isinstance(row.legacy_programs, str) else [],
                                        'main_characters': json.loads(row.main_characters) if isinstance(row.main_characters, str) else [],
                                        'confidence': row.confidence, 'rationale': row.rationale, 'source': row.map_source}})
            M.append(rec)
    for r in extra.itertuples():
        M.append({'id': r.measure_id, 'dept': r.dept, 'name': r.title, 'unit': '%' if r.data_type == 'Percent' else ('$' if r.data_type == 'Currency' else 'number'),
                  'direction': DIR.get(r.direction, 'neutral'), 'type': KIND7.get(r.measure_kind, 'output'), 'first_fy': None, 'last_fy': None,
                  'dropped_fy': None, 'replaced_by': None, 'lineage_id': None, 'lineage_note': None,
                  'internal_admin': r.measure_kind == 'internal_admin', 'status': 'current'})
    return M, V


def derived_measures():
    P = pd.read_csv(os.path.join(INTERIM, 'outcomes_panel.csv'))
    pol = P[P.series.isin(['police_calls_A', 'police_calls_B', 'police_calls_C'])].groupby('fy', as_index=False).value.sum()
    defs = [('FIR', 'Fire/EMS calls for service (DataSF nuek-vuh3)', 'calls', 'neutral', P[P.series == 'fire_calls_total'], 'nuek-vuh3 Fire Department and EMS Dispatched Calls for Service', 'fire_cost_per_call'),
            ('POL', 'Police 911-dispatched calls, priorities A-C (DataSF 2zdj-bwza)', 'calls', 'neutral', pol, '2zdj-bwza Law Enforcement Dispatched Calls for Service: Closed', 'police_cost_per_911_call'),
            ('ADM', '311 service requests opened (DataSF vw6y-z8j6)', 'requests', 'neutral', P[P.series == '311_opened'], 'vw6y-z8j6 311 Cases', '311_cost_per_request'),
            ('ADM', '311 calls answered (DataSF mwjb-biik)', 'calls', 'neutral', P[P.series == '311_calls_answered'], 'mwjb-biik 311 Call Metrics by Month', '311_cost_per_call'),
            ('MTA', 'Muni vehicle revenue hours (National Transit Database)', 'hours', 'higher', P[P.series == 'muni_vehicle_revenue_hours'], 'FTA National Transit Database, SFMTA (ntd_id 90015)', 'muni_cost_per_revenue_hour'),
            ('MTA', 'Muni unlinked passenger trips (National Transit Database)', 'trips', 'higher', P[P.series == 'muni_unlinked_trips_ntd'], 'FTA National Transit Database, SFMTA (ntd_id 90015)', 'muni_cost_per_trip')]
    M, V, pm = [], [], {}
    for dept, name, unit, dr, s, src, pair in defs:
        i = mid(dept, name); pm[pair] = i
        s = s[s.fy <= 2026]
        M.append({'id': i, 'dept': dept, 'name': name, 'unit': unit, 'direction': dr, 'type': 'output', 'first_fy': None, 'last_fy': None,
                  'dropped_fy': None, 'replaced_by': None, 'lineage_id': None, 'lineage_note': None, 'internal_admin': False, 'status': 'current',
                  'derived': True, 'derived_note': 'Not a Controller performance measure: a direct count from the named dataset, used as the denominator of a curated unit cost. No target; exclude from met shares.'})
        V.append(pd.DataFrame({'measure': i, 'fy': s.fy.astype(int), 'target': np.nan, 'actual': s.value.values, 'source_doc': src, 'restated': None}))
    return M, pd.concat(V, ignore_index=True), pm


def main():
    if os.path.exists(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    docs = os.path.join(os.path.dirname(__file__), 'site_docs')   # CONTRACT_GAPS.md, README_EXPORT.md (hand-written)
    for f in os.listdir(docs):
        shutil.copy(os.path.join(docs, f), os.path.join(SITE, f))
    cube = pd.read_parquet(os.path.join(INTERIM, 'spend_cube.parquet'))
    ctx = pd.read_csv(os.path.join(INTERIM, 'context_fy.csv'))
    dept_vals, dept_ok = build_depts(cube)
    cells = spending_cells(dept_ok)
    main_cells = [c for c in cells if c['fy'] >= 2010]
    hist_cells = [c for c in cells if c['fy'] < 2010]
    dump('spending/cells.json', {'sample': False, 'as_of': AS_OF, 'sources': ['xdgd-c79v', 'bpnb-jwfb'],
         'note': ('Nominal dollars. One row per (fy, dept, fund, char), FY2010-FY2028. budget = adopted Annual Appropriation Ordinance; revised = null '
                  '(not published in the open data); actual = Spending and Revenue, null for FY2027+ and for masked dept-years (dq_flag). '
                  'Excluded: transfers and eliminations, reserves, fiduciary funds and component units, the FY2019 GFSUP artifact. '
                  'Capital and debt: annual budget-vs-actual gaps are not meaningful (multi-year and bond appropriations sit outside the adopted budget).'),
         'cells': main_cells})
    dump('spending/cells_pre2010.json', {'sample': False, 'as_of': AS_OF, 'sources': ['bpnb-jwfb'],
         'note': 'Actuals FY1999-FY2009 (no adopted-budget data before FY2010). Same schema as spending/cells.json.', 'cells': hist_cells})
    st = staffing(dept_ok)
    dump('staffing/cells.json', {'sample': False, 'as_of': AS_OF, 'sources': ['88g8-5mnd', '4zfx-f2ts', '43jt-u7yn'],
         'note': ('headcount = distinct employee identifiers paid in the department-year; fte = paid hours / 2080 (FY2017+, includes overtime hours); '
                  'ot_share = overtime / (salaries + overtime); budgeted_fte = gross budgeted positions (Budget - FTE); vacancy = budgeted_fte minus actual paid FTE, '
                  'FY2021+ only (actual paid FTE unreliable FY2018-2020). Names are never exported.'), 'cells': st})

    M, V = measures_and_values(dept_ok)
    DM, DV, pm = derived_measures()
    M += DM
    V = pd.concat([V, DV], ignore_index=True)
    byname = {(m['dept'], m['name']): m['id'] for m in M}
    pm.update({'library_cost_per_visit': byname.get(('LIB', 'Number of persons entering San Francisco Main and Branch libraries, Bookmobiles, Jail and Re-Entry Services and Juvenile Justice Center')),
               'hsh_spend_per_exit': byname.get(('HOM', 'Number of people exiting homelessness to a permanent housing situation')),
               'street_env_cost_per_curb_mile_swept': byname.get(('DPW', 'Number of curb miles mechanically swept'))})
    dirs = {m['id']: m['direction'] for m in M}
    V = V.sort_values(['measure', 'fy']).drop_duplicates(['measure', 'fy'], keep='first').reset_index(drop=True)
    V['direction'] = V.measure.map(dirs)
    V = V[V.direction.notna()]

    def met(a, t, d):
        if pd.isna(a) or pd.isna(t) or d not in ('higher', 'lower'):
            return None
        return bool(a >= t) if d == 'higher' else bool(a <= t)
    V['met'] = [met(a, t, d) for a, t, d in zip(V.actual, V.target, V.direction)]
    g = V.groupby('measure')
    V['prev_target'] = g.target.shift(1); V['prev_fy'] = g.fy.shift(1)
    tc = []
    for r in V.itertuples():
        if pd.isna(r.target) or r.direction not in ('higher', 'lower'):
            tc.append(None); continue
        if pd.isna(r.prev_target) or r.prev_fy != r.fy - 1:
            tc.append('new'); continue
        if r.prev_target == 0:
            rel = 0.0 if r.target == 0 else float(np.sign(r.target))
        else:
            rel = (r.target - r.prev_target) / abs(r.prev_target)
        tc.append('same' if abs(rel) <= 0.005 else ('easier' if (rel < 0) == (r.direction == 'higher') else 'harder'))
    V['target_change'] = tc
    cpo = pd.read_csv(os.path.join(INTERIM, 'cost_per_outcome.csv'))
    cost_rows, links = {}, []
    for pair, gg in cpo.groupby('pair'):
        m_id = pm.get(pair)
        if not m_id:
            continue
        for r in gg.itertuples():
            cost_rows[(m_id, int(r.fy))] = (iround(r.numerator_nominal), float(r.unit_cost_nominal))
        r0 = gg.iloc[0]
        links.append({'measure': m_id, 'pair': pair, 'label': r0.label, 'numerator': r0.numerator_def, 'denominator': r0.denominator_def,
                      'rationale': r0.caveat, 'confidence': 'high' if pair in ('library_cost_per_visit', 'muni_cost_per_revenue_hour', 'muni_cost_per_trip') else 'medium',
                      'years': [int(gg.fy.min()), int(gg.fy.max())]})
    units = {m['id']: m['unit'] for m in M}
    out_rows = []
    for r in V.itertuples():
        row = {'measure': r.measure, 'fy': int(r.fy), 'target': None if pd.isna(r.target) else round(float(r.target), 4),
               'actual': None if pd.isna(r.actual) else round(float(r.actual), 4), 'met': r.met, 'target_change': r.target_change, 'source_doc': r.source_doc}
        if r.restated is True:
            row['restated'] = True
        if units.get(r.measure) == '%':
            a_, t_ = row['actual'], row['target']
            if (a_ is not None and abs(a_) > 1000) or (t_ is not None and abs(t_) > 1000):
                row['qa_flag'] = 'implausible percent value as published/transcribed'
            elif a_ and t_ and (abs(a_) / abs(t_) > 20 or abs(t_) / abs(a_) > 20):
                row['qa_flag'] = 'target and actual appear to be on different scales in the source'
        c = cost_rows.get((r.measure, int(r.fy)))
        if c:
            row['program_cost'] = c[0]; row['cost_per_unit'] = round(c[1], 2)
        out_rows.append(row)
    rng = V.groupby('measure').fy.agg(['min', 'max'])
    keep = []
    for m in M:
        if m['id'] not in rng.index:
            continue
        m['first_fy'], m['last_fy'] = int(rng.loc[m['id'], 'min']), int(rng.loc[m['id'], 'max'])
        m['dropped_fy'] = m['last_fy'] + 1 if m['status'] == 'dropped' else None
        keep.append(m)
    ids = {m['id'] for m in keep}
    for m in keep:
        if m['replaced_by'] and m['replaced_by'] not in ids:
            m['replaced_by_note'] = f"successor title ({m['replaced_by']}) has no exported values; link removed"
            m['replaced_by'] = None
    M = keep
    dump('measures/measures.json', {'sample': False, 'as_of': AS_OF, 'sources': ['6dpt-7w23', 'perf-reports', '5x94-tptc', '6h77-suve'],
         'note': ("One record per measure title. status: current (in the Controller's dataset today; id = hash of dept + lowercased title), replaced "
                  '(succeeded by replaced_by in the same lineage; lineage_note = reworded or redefined), dropped (lineage ended with no successor and is absent '
                  'today; dropped_fy = last_fy + 1), superseded (an earlier variant that ran alongside another title of the same lineage). Historical titles and '
                  'values come from the Controller annual reports FY2006-FY2022 (transcribed). derived = direct dataset counts used only as cost denominators.'),
         'measures': M})
    dump('measures/values.json', {'sample': False, 'as_of': AS_OF, 'sources': ['6dpt-7w23', 'perf-reports'],
         'note': ("Percent measures in percentage points (0-100). met = actual vs target in the measure's direction (strict), null if either is missing or "
                  "direction neutral. target_change vs the previous FY's target: easier / harder if it moved more than 0.5% in that direction, same otherwise, "
                  "new if there is no prior-year target. FY2013+ values for current measures come from today's dataset (history as restated by departments); "
                  'earlier and historical values come from the annual reports (latest report printing that year). program_cost / cost_per_unit are nominal and '
                  'only on the curated pairs in cost_links.json.'), 'rows': out_rows})
    dump('measures/cost_links.json', {'sample': False, 'as_of': AS_OF, 'links': links})
    extras(dept_ok, M, st)
    meta = {'sample': False, 'module': 'performance', 'as_of': AS_OF, 'generated_at': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
            'version': '1.0',
            'fiscal_years': {'min': 2010, 'max': 2026, 'budget_max': 2028, 'actual_history_min': 1999, 'measures_min': int(min(r['fy'] for r in out_rows)),
                             'measure_results_max': 2025, 'note': 'Actuals through FY2026 (FY2027 partial, excluded). Budget FY2010-FY2028. Pre-FY2010 actuals in spending/cells_pre2010.json.'},
            'real_base_fy': BASE_FY,
            'deflator': {'base_fy': BASE_FY, 'series': 'CUURS49BSA0',
                         'source': 'BLS CPI-U San Francisco-Oakland-Hayward, all items, not seasonally adjusted; fiscal-year average of the six bimonthly readings Jul-Jun; Oct 2025 (not collected during the federal shutdown) interpolated. index = CPI(FY)/CPI(FY2026); real = nominal / index.',
                         'index': {str(int(r.fy)): round(1.0 / r.mult_bay, 5) for r in ctx.itertuples() if 1999 <= r.fy <= 2028},
                         'note': 'FY2027 and FY2028 (budget-only years) have no complete CPI; index held at 1.0 (FY2026 prices).'},
            'population': {'source': 'California Department of Finance E-4, January 1 (fiscal-year midpoint); FY2027-28 held at the 2026 estimate.',
                           'by_fy': {str(int(r.fy)): int(r.population_primary) for r in ctx.itertuples() if 1999 <= r.fy <= 2028}},
            'dimensions': {'dept': {'label': 'Department', 'values': dept_vals},
                           'group': {'label': 'Department group', 'values': [{'id': a, 'label': b} for a, b in GROUPS]},
                           'char': {'label': 'Spending category', 'kind': 'categorical', 'values': [{'id': a, 'label': b, 'slot': i + 1} for i, (a, b) in enumerate(CHAR7)],
                                    'note': ('salaries excludes overtime objects; nonpersonnel = non-personnel services + materials and supplies + services of other departments '
                                             '(work orders); aid = aid payments/assistance + support and care of persons + City Grant Program; capital = capital outlay, '
                                             'capitalized expenditures, facilities maintenance, programmatic projects; other = debt service + overhead allocations + other. '
                                             'Transfers are excluded entirely.')},
                           'fund': {'label': 'Fund', 'values': [{'id': 'gf', 'label': 'General Fund'}, {'id': 'other', 'label': 'All other funds'}]}},
            'counts': {'departments': len(dept_vals), 'spending_rows': len(main_cells), 'spending_rows_pre2010': len(hist_cells), 'staffing_rows': len(st),
                       'measures': len(M), 'measures_current': sum(1 for m in M if m['status'] == 'current' and not m.get('derived')),
                       'measures_dropped': sum(1 for m in M if m['status'] == 'dropped'), 'measures_derived': sum(1 for m in M if m.get('derived')),
                       'measure_values': len(out_rows)},
            'small_n': 3, 'sources': sources(), 'files': {}, 'reorganizations': REORGS,
            'data_quality_masks': [{'dept': 'DPW', 'fy': 2018, 'what': 'actuals masked: FY2018 cutover conversion entries (about +$4.5B all funds)'},
                                   {'dept': 'PUC', 'fy': 2018, 'what': 'actuals masked: FY2018 cutover conversion entries (about -$2.9B)'}],
            'caveats': ['Performance measures are self-reported by departments and compiled by the Controller; they are not audited.',
                        'Program detail ends in FY2017 (financial-system cutover); FY2018+ all-funds actuals step up partly for accounting reasons.',
                        'Budget = adopted budget; the revised budget is not in the open data.']}
    dump('meta.json', meta)
    print('cells', len(main_cells), 'pre2010', len(hist_cells), 'staffing', len(st), 'measures', len(M), 'values', len(out_rows), 'links', len(links))


def sources():
    R = lambda f: os.path.join(RAW, f)
    def nrows(path):
        try:
            return sum(1 for _ in open(path)) - 1
        except Exception:
            return None
    emp = pd.read_csv(R('employee_comp.csv'), usecols=['Year Type'])
    fire_rows = json.load(open(R('outcomes/meta_nuek-vuh3.json'))).get('rowsUpdatedAt')
    return [
        {'id': 'xdgd-c79v', 'name': 'Budget', 'publisher': 'SF Controller via data.sf.gov', 'rows': 409521, 'rows_used': 336150, 'as_of': meta_asof(R('meta_xdgd-c79v.json')),
         'url': 'https://data.sf.gov/resource/xdgd-c79v.json', 'note': 'Adopted budget (Annual Appropriation Ordinance), spending rows FY2010-FY2028 after excluding fiduciary funds and component units; no revised budget.'},
        {'id': 'bpnb-jwfb', 'name': 'Spending and Revenue', 'publisher': 'SF Controller via data.sf.gov', 'rows': 776841, 'rows_used': 650592, 'as_of': meta_asof(R('meta_bpnb-jwfb.json')),
         'url': 'https://data.sf.gov/resource/bpnb-jwfb.json', 'note': 'Actual spending FY1999-FY2026; related government units and fiduciary funds excluded.'},
        {'id': '88g8-5mnd', 'name': 'Employee Compensation', 'publisher': 'SF Controller via data.sf.gov', 'rows': 1180053, 'rows_used': int((emp['Year Type'] == 'Fiscal').sum()),
         'as_of': meta_asof(R('meta_88g8-5mnd.json')), 'url': 'https://data.sf.gov/resource/88g8-5mnd.json', 'note': 'Fiscal-year rows FY2013-FY2026.'},
        {'id': '4zfx-f2ts', 'name': 'Budget - FTE', 'publisher': 'SF Controller via data.sf.gov', 'rows': nrows(R('context/budget_fte.csv')), 'rows_used': nrows(R('context/budget_fte.csv')),
         'as_of': meta_asof(R('context/meta_4zfx-f2ts.json')), 'url': 'https://data.sf.gov/resource/4zfx-f2ts.json', 'note': 'Budgeted positions (gross; attrition-savings lines FY2010-18 and FY2025+).'},
        {'id': '43jt-u7yn', 'name': 'Spending - FTE', 'publisher': 'SF Controller via data.sf.gov', 'rows': nrows(R('context/spending_fte.csv')), 'rows_used': nrows(R('context/spending_fte.csv')),
         'as_of': meta_asof(R('context/meta_43jt-u7yn.json')), 'url': 'https://data.sf.gov/resource/43jt-u7yn.json', 'note': 'Actual paid FTE; vacancy uses FY2021+.'},
        {'id': '6dpt-7w23', 'name': 'San Francisco Citywide Performance Metrics', 'publisher': "SF Controller's City Performance Unit via data.sf.gov", 'rows': 10164, 'rows_used': 10160,
         'as_of': '2026-06-03', 'url': 'https://data.sf.gov/resource/6dpt-7w23.json', 'note': 'Current measure set (732) with targets and results FY2013-FY2025 and targets to FY2028.'},
        {'id': '5x94-tptc', 'name': 'Performance measures, FY2013 annual report dataset', 'publisher': 'SF Controller via data.sf.gov', 'rows': 1002, 'rows_used': 1002,
         'as_of': meta_asof(R('perf_measures/meta_5x94-tptc.json')), 'url': 'https://data.sf.gov/resource/5x94-tptc.json', 'note': 'Snapshot used for restatement checks and transcription validation.'},
        {'id': '6h77-suve', 'name': 'Performance measures, FY2014 annual report dataset', 'publisher': 'SF Controller via data.sf.gov', 'rows': 1001, 'rows_used': 1001,
         'as_of': meta_asof(R('perf_measures/meta_6h77-suve.json')), 'url': 'https://data.sf.gov/resource/6h77-suve.json', 'note': "Snapshot; the Controller's 'performance pattern' (direction) is used in a red-team check."},
        {'id': 'perf-reports', 'name': "Controller's annual performance reports FY2006-FY2019 and FY2022 (PDF)", 'publisher': "SF Controller's Office",
         'rows': 2400, 'rows_used': 86773, 'as_of': '2026-09-26', 'url': 'https://www.sf.gov/san-francisco-performance-program',
         'note': 'rows = pages transcribed (Claude Sonnet, visual read); rows_used = measure-year values parsed. Agreement with the FY13/FY14 datasets: 99.4% of 6,865 values.'},
        {'id': 'budget-book-fy27-28', 'name': "Mayor's Proposed Budget FY2026-27 and FY2027-28 (division tables)", 'publisher': "Mayor's Office of Public Policy and Finance",
         'rows': 56, 'rows_used': 226, 'as_of': '2026-06-01', 'url': 'https://media.api.sf.gov/documents/Mayors_June_1st_Proposed_FY27_and_FY28_Budget_Budget_Book.pdf',
         'note': 'rows = department pages transcribed; rows_used = division lines. Used in scorecards only.'},
        {'id': 'vw6y-z8j6', 'name': '311 Cases', 'publisher': 'DataSF', 'rows': 8945994, 'rows_used': 8945994, 'as_of': meta_asof(R('meta_vw6y-z8j6.json')),
         'url': 'https://data.sf.gov/resource/vw6y-z8j6.json', 'note': 'Requests opened per FY (derived cost denominator).'},
        {'id': 'nuek-vuh3', 'name': 'Fire Department and EMS Dispatched Calls for Service', 'publisher': 'DataSF', 'rows': None, 'rows_used': None,
         'as_of': meta_asof(R('outcomes/meta_nuek-vuh3.json')), 'url': 'https://data.sf.gov/resource/nuek-vuh3.json',
         'note': 'About 7.45M unit-level rows aggregated to unique calls per FY (exact counts in raw/outcomes/SOURCES.csv).'},
        {'id': '2zdj-bwza', 'name': 'Law Enforcement Dispatched Calls for Service: Closed', 'publisher': 'DataSF', 'rows': None, 'rows_used': None,
         'as_of': meta_asof(R('outcomes/meta_2zdj-bwza.json')), 'url': 'https://data.sf.gov/resource/2zdj-bwza.json', 'note': 'About 7.93M rows; 911-originated non-duplicate Police calls, priorities A-C, FY2016+.'},
        {'id': 'mwjb-biik', 'name': '311 Call Metrics by Month', 'publisher': 'DataSF', 'rows': None, 'rows_used': None, 'as_of': meta_asof(R('outcomes/meta_mwjb-biik.json')),
         'url': 'https://data.sf.gov/resource/mwjb-biik.json', 'note': 'Calls answered per FY.'},
        {'id': 'ntd-90015', 'name': 'National Transit Database TS2.2 service and operating expenses (SFMTA)', 'publisher': 'Federal Transit Administration', 'rows': 10, 'rows_used': 10,
         'as_of': '2026-09-26', 'url': 'https://data.transportation.gov/resource/ectq-t3k3', 'note': 'Operating expenses, vehicle revenue hours and trips FY2015-FY2024.'},
        {'id': 'dof-e4', 'name': 'Population estimates (CA Department of Finance E-4)', 'publisher': 'CA DOF', 'rows': 28, 'rows_used': 28, 'as_of': '2026-05-01',
         'url': 'https://dof.ca.gov/forecasting/demographics/estimates/', 'note': 'January 1 estimates, 1999-2026.'},
        {'id': 'bls-cpi', 'name': 'CPI-U San Francisco-Oakland-Hayward (CUURS49BSA0)', 'publisher': 'BLS', 'rows': nrows(R('context/bls_raw_CUURS49BSA0.csv')), 'rows_used': 168,
         'as_of': '2026-09-26', 'url': 'https://download.bls.gov/pub/time.series/cu/cu.data.2.Summaries', 'note': 'Deflator; fiscal-year average; base FY2026. National CPI-U (CUUR0000SA0) used for robustness.'},
    ]


def extras(dept_ok, M, st):
    I = lambda f: pd.read_csv(os.path.join(INTERIM, f))
    for name, fn in [('budget_execution_summary', 'an_budget_exec_summary.csv'), ('overtime_budget_vs_actual', 'an_ot_budget.csv'),
                     ('overtime_vs_vacancy', 'an_ot_vacancy.csv'), ('go_bond_programs', 'an_go_bonds.csv'), ('go_bond_pace', 'an_go_bond_pace.csv'),
                     ('yearend_po_city', 'an_yearend_city.csv'), ('yearend_po_dept', 'an_yearend_summary.csv'), ('target_easing_test', 'an_target_easing_test.csv'),
                     ('drop_redefine_test', 'an_drop_test.csv'), ('spend_vs_perf', 'an_spend_vs_perf.csv'), ('spend_vs_perf_robustness', 'an_spend_vs_perf_robust.csv'),
                     ('dropped_or_redefined_after_miss', 'an_dropped_examples.csv'), ('cost_per_outcome', 'cost_per_outcome.csv')]:
        dump(f'analyses/{name}.json', {'as_of': AS_OF, 'rows': recs(I(fn))})
    rs = I('an_restatements.csv')
    dump('analyses/restatements.json', {'as_of': AS_OF, 'rows': recs(rs[rs.kind == 'actual'][['report', 'fy', 'key', 'then', 'now', 'rel_diff', 'restated', 'measure_id']])})
    dump('outcomes/series.json', {'as_of': AS_OF, 'note': 'Direct outcome series. Shares here are fractions (0-1), unlike measures/values.', 'rows': recs(I('outcomes_panel.csv'))})
    bb = I('budget_book_divisions.csv'); bb = bb[~bb.division.str.contains('Total', na=False)]
    dump('spending/divisions_budget_book.json', {'as_of': AS_OF, 'rows': recs(bb)})
    d = I('dept_fy.csv')
    cols = ['dept', 'fy', 'budget_all', 'actual_all', 'budget_gf', 'actual_gf', 'budget_oper_all', 'actual_oper_all', 'actual_oper_all_real',
            'actual_oper_all_real_per_res', 'actual_gf_real_per_res', 'actual_overtime', 'budget_overtime', 'dq_flag']
    svp, rob, mchg, cpo, att = I('an_spend_vs_perf.csv'), I('an_spend_vs_perf_robust.csv'), I('an_measure_change.csv'), I('cost_per_outcome.csv'), I('an_attainment_dept.csv')
    for dept in sorted(dept_ok):
        dd = d[(d.dept == dept) & d.fy.between(1999, 2026)][cols]
        if dd.actual_oper_all.fillna(0).max() < 20e6 and dept not in set(svp.dept):
            continue
        dump(f'scorecards/{dept}.json', {'dept': dept, 'name': DEPT_NAMES.get(dept, dept), 'as_of': AS_OF,
             'note': 'Extra (not in the contract): precomputed context for the department scorecard. Money nominal unless *_real (FY2026 $).',
             'reorganizations': [r for r in REORGS if dept in r['depts'] or 'ALL' in r['depts']],
             'spending_by_year': recs(dd), 'staffing_by_year': [s for s in st if s['dept'] == dept],
             'divisions_budget_fy2026_28': recs(bb[bb.dept == dept][['division', 'fy2026_original', 'fy2027_proposed', 'fy2028_proposed']]),
             'measure_ids': [m['id'] for m in M if m['dept'] == dept],
             'measure_change_fy15_17_vs_fy23_25': recs(mchg[mchg.dept == dept][['measure_id', 'title', 'direction', 'mean_b', 'mean_r', 'adj_change', 'status']]),
             'spend_vs_perf': recs(svp[svp.dept == dept]), 'spend_vs_perf_robustness': recs(rob[rob.dept == dept]),
             'cost_per_outcome': recs(cpo[cpo.dept == dept]), 'attainment_by_year': recs(att[att.dept == dept])})


if __name__ == '__main__':
    main()
