"""Contract QA (design/DATA_CONTRACT_performance.md section 5) + finalize meta.files.
Writes data/site/QA_REPORT.json and prints a summary. Run after 16_export_site.py and 17_commentary.py.
"""
import pandas as pd, numpy as np, os, sys, json, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import *

S = lambda f: json.load(open(os.path.join(SITE, f)))


def main():
    Q = {}
    meta = S('meta.json')
    C = pd.DataFrame(S('spending/cells.json')['cells'])
    CH = pd.DataFrame(S('spending/cells_pre2010.json')['cells'])
    ST = pd.DataFrame(S('staffing/cells.json')['cells'])
    M = pd.DataFrame(S('measures/measures.json')['measures'])
    V = pd.DataFrame(S('measures/values.json')['rows'])
    # 1. totals vs dept_fy.csv (actual_all = all spending classes, excluding transfers/reserves/fiduciary/GFSUP)
    d = pd.read_csv(os.path.join(INTERIM, 'dept_fy.csv'))
    dims = {x['id'] for x in meta['dimensions']['dept']['values']}
    ref = d[d.dept.isin(dims)].groupby('fy').actual_all.sum()
    allc = pd.concat([C, CH])
    got = allc.groupby('fy').actual.sum()
    comp = pd.DataFrame({'cells': got, 'dept_fy': ref}).dropna()
    comp = comp[comp.index <= 2026]
    comp['diff'] = comp.cells - comp.dept_fy
    Q['1_totals'] = {'max_abs_diff_dollars': float(comp['diff'].abs().max()), 'years_checked': int(len(comp)),
                     'exclusions': 'transfers/eliminations, reserves, fiduciary funds and component units, FY2019 GFSUP artifact, pass-through departments CCD/CTA/TJP/RDA; DPW & PUC FY2018 masked in both'}
    # 2. dimension ids
    chars = {x['id'] for x in meta['dimensions']['char']['values']}; funds = {x['id'] for x in meta['dimensions']['fund']['values']}
    Q['2_ids'] = {'cells_bad_dept': sorted(set(allc.dept) - dims), 'cells_bad_char': sorted(set(allc.char) - chars), 'cells_bad_fund': sorted(set(allc.fund) - funds),
                  'staffing_bad_dept': sorted(set(ST.dept) - dims), 'measures_bad_dept': sorted(set(M.dept) - dims)}
    # 3. payroll overtime vs ledger overtime objects
    led = C[C.char == 'overtime'].groupby(['dept', 'fy']).actual.sum()
    s = ST.set_index(['dept', 'fy']).overtime
    j = pd.DataFrame({'payroll': s, 'ledger': led}).dropna()
    j = j[(j.payroll > 1e6) | (j.ledger > 1e6)]
    j['rel'] = (j.payroll - j.ledger) / j.ledger.replace(0, np.nan)
    over = j[j.rel.abs() > 0.10].reset_index()
    Q['3_overtime'] = {'dept_years_over_1M': int(len(j)), 'within_10pct': int((j.rel.abs() <= 0.10).sum()),
                       'citywide_by_fy': {int(k): round(float(v), 4) for k, v in (j.groupby('fy').payroll.sum() / j.groupby('fy').ledger.sum() - 1).items()},
                       'outside_10pct': over.assign(rel=over.rel.round(3)).to_dict('records')}
    # 4. measures: fy range, dropped_fy, met recompute
    rng = V.groupby('measure').fy.agg(['min', 'max'])
    mm = M.set_index('id')
    bad_rng = [i for i in rng.index if i in mm.index and not (mm.loc[i, 'first_fy'] <= rng.loc[i, 'min'] and rng.loc[i, 'max'] <= mm.loc[i, 'last_fy'])]
    dr = M[M.dropped_fy.notna()]
    bad_drop = dr[dr.dropped_fy != dr.last_fy + 1].id.tolist()
    dirs = mm.direction
    def met(a, t, dd):
        if pd.isna(a) or pd.isna(t) or dd not in ('higher', 'lower'):
            return None
        return bool(a >= t) if dd == 'higher' else bool(a <= t)
    rec = [met(a, t, dirs.get(m_)) for a, t, m_ in zip(V.actual, V.target, V.measure)]
    mismatch = sum(1 for x, y in zip(rec, V.met) if not ((x is None and pd.isna(y)) or x == y))
    orphans = sorted(set(V.measure) - set(M.id))
    Q['4_measures'] = {'measures': int(len(M)), 'values': int(len(V)), 'range_violations': bad_rng[:20], 'n_range_violations': len(bad_rng),
                       'dropped_fy_violations': bad_drop[:20], 'met_recompute_mismatches': mismatch, 'value_rows_without_measure': len(orphans),
                       'replaced_by_missing_target': int(M.replaced_by.notna().sum() - M.replaced_by.isin(M.id).sum())}
    # 5. percent scale
    pctids = set(M[M.unit == '%'].id)
    pv = V[V.measure.isin(pctids)]
    over100 = pv[(pv.actual > 100) | (pv.target > 100)]
    Q['5_percent'] = {'percent_values': int(len(pv)), 'over_100': int(len(over100)),
                      'over_100_examples': over100.merge(M[['id', 'name']], left_on='measure', right_on='id')[['name', 'fy', 'target', 'actual', 'source_doc']].head(15).to_dict('records'),
                      'qa_flagged_rows': int(V.get('qa_flag', pd.Series(dtype=object)).notna().sum())}
    # 6. files
    files = {}
    for p in sorted(glob.glob(os.path.join(SITE, '**', '*.json'), recursive=True)):
        rel = os.path.relpath(p, SITE)
        if rel == 'meta.json' or rel == 'QA_REPORT.json':
            continue
        files['performance/' + rel] = {'bytes': os.path.getsize(p)}
    meta['files'] = files
    with open(os.path.join(SITE, 'meta.json'), 'w') as f:
        json.dump(meta, f, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    files['performance/meta.json'] = {'bytes': os.path.getsize(os.path.join(SITE, 'meta.json'))}
    Q['6_files'] = {'n': len(files), 'total_bytes': int(sum(v['bytes'] for v in files.values())),
                    'note': 'meta.files keys use the performance/<path> convention of design/prototype/sample-data; meta.json lists every file but itself.'}
    # NaN scan
    nan_files = []
    for p in glob.glob(os.path.join(SITE, '**', '*.json'), recursive=True):
        t = open(p).read()
        if 'NaN' in t or 'Infinity' in t:
            nan_files.append(os.path.relpath(p, SITE))
    Q['nan_scan'] = nan_files
    json.dump(Q, open(os.path.join(SITE, 'QA_REPORT.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: (v if k != '3_overtime' else {kk: vv for kk, vv in v.items() if kk != 'outside_10pct'}) for k, v in Q.items() if k != '5_percent'}, indent=1, default=str)[:4000])
    print('percent:', Q['5_percent']['percent_values'], 'over100:', Q['5_percent']['over_100'], 'flagged:', Q['5_percent']['qa_flagged_rows'])


if __name__ == '__main__':
    main()
