"""Dropped / redefined measures and long-run target easing, using the measure lineage.

Report sequence (measure lists): FY2006..FY2019 annual reports, FY2022 report appendix, current dataset (FY2026 set).
For each public-service lineage (internal-admin lineages excluded) present in report R with a same-year actual and target
printed in that report, we classify whether it met its target (direction from the lineage), then what happened by the
next report in the sequence:
  kept      the same title appears again
  reworded  lineage continues under a reworded title
  redefined lineage continues but a successor title is labeled 'redefined'
  dropped   no member of the lineage appears in the next report or any later one
  gap       absent from the next report but reappears later (treated as kept for drop analysis)
We compare drop and redefinition rates for measures that missed vs met their target, pooled and stratified by report
year (Cochran-Mantel-Haenszel), since some years had citywide measure overhauls that drop many measures at once.
Outputs: data/interim/an_lineage_events.csv, an_drop_test.csv, an_dropped_examples.csv, an_target_series_long.csv,
         an_target_easing_long.csv
"""
import pandas as pd, numpy as np, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from llm import run_many

PAIR_SYS = ('You compare two consecutive versions of a city performance measure (the earlier title, and the title that '
            'replaced it in the next annual report). Answer "same" (trivial wording/typo), "reworded" (same definition, '
            'different words) or "redefined" (the definition changed: threshold, population, scope, unit, time window, '
            'method, or survey question). Give a short note.')
PAIR_SCHEMA = {'type': 'object', 'properties': {'relation': {'type': 'string', 'enum': ['same', 'reworded', 'redefined']},
               'note': {'type': 'string'}}, 'required': ['relation', 'note'], 'additionalProperties': False}

SEQ = [2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2022, 2026]


def met(a, t, d):
    if pd.isna(a) or pd.isna(t) or d == 'neutral':
        return np.nan
    tol = abs(t) * 0.005
    return float(a >= t - tol) if d == 'higher_better' else float(a <= t + tol)


def main():
    lin = pd.read_csv(os.path.join(INTERIM, 'measure_lineage.csv'))
    occ = pd.read_csv(os.path.join(INTERIM, 'measure_occurrences.csv'))
    occ = occ[occ.source.isin(['pdf_report', 'current_6dpt'])]
    occ = occ.merge(lin[['dept', 'title_key', 'lineage_id', 'relation', 'direction', 'internal_admin', 'change_note']],
                    on=['dept', 'title_key'], how='inner')
    pres_l = occ.groupby('lineage_id').report_fy.apply(set).to_dict()
    pres_t = occ.groupby(['dept', 'title_key']).report_fy.apply(set).to_dict()
    v = pd.read_csv(os.path.join(INTERIM, 'pdf_values.csv'))
    v = v[(v.fy == v.report_fy) & v.kind.isin(['actual', 'target']) & v.value_num.notna()]
    vv = v.groupby(['report_fy', 'dept', 'title_key', 'kind']).value_num.first().unstack('kind').reset_index()
    vv = vv.merge(lin[['dept', 'title_key', 'lineage_id', 'direction', 'internal_admin', 'relation', 'title']], on=['dept', 'title_key'], how='inner')
    vv['met'] = [met(a, t, d) for a, t, d in zip(vv.get('actual'), vv.get('target'), vv.direction)]
    # pairwise transitions: predecessor title -> successor titles first appearing in the next report
    lin_keys = lin.groupby('lineage_id').apply(lambda g: list(zip(g.title_key, g.title))).to_dict()
    pairs = {}
    for r in vv.itertuples():
        R = r.report_fy
        if R not in SEQ or R == SEQ[-1]:
            continue
        nxt = SEQ[SEQ.index(R) + 1]
        if nxt in pres_t.get((r.dept, r.title_key), set()) or nxt not in pres_l.get(r.lineage_id, set()):
            continue
        for k, tt in lin_keys.get(r.lineage_id, []):
            if nxt in pres_t.get((r.dept, k), set()) and k != r.title_key:
                pairs[(r.title, tt)] = None
    jobs = [((a, b), dict(task='lineage_pair_sonnet', model='claude-sonnet-5', system=PAIR_SYS,
                          prompt=f'Earlier: "{a}"\nNext report: "{b}"', schema=PAIR_SCHEMA, effort='low', max_tokens=2000))
            for a, b in pairs]
    print('pairwise transitions to classify:', len(jobs))
    pres = run_many(jobs, workers=16)
    pair_rel = {k: (v['relation'] if isinstance(v, dict) else 'reworded') for k, v in pres.items()}
    pd.DataFrame([{'from': a, 'to': b, 'relation': pair_rel[(a, b)],
                   'note': pres[(a, b)].get('note', '') if isinstance(pres[(a, b)], dict) else 'error'} for a, b in pair_rel]
                 ).to_csv(os.path.join(INTERIM, 'an_lineage_transitions.csv'), index=False)
    ev = []
    for r in vv.itertuples():
        R = r.report_fy
        if R not in SEQ or R == SEQ[-1]:
            continue
        nxt = SEQ[SEQ.index(R) + 1]
        later = [y for y in SEQ if y > R]
        lp = pres_l.get(r.lineage_id, set())
        tp = pres_t.get((r.dept, r.title_key), set())
        if nxt in tp:
            outc = 'kept'
        elif nxt in lp:
            rels = [pair_rel.get((r.title, tt)) for k, tt in lin_keys.get(r.lineage_id, [])
                    if nxt in pres_t.get((r.dept, k), set()) and k != r.title_key]
            outc = 'redefined' if 'redefined' in rels else 'reworded'
        elif any(y in lp for y in later):
            outc = 'gap'
        else:
            outc = 'dropped'
        ev.append({'report_fy': R, 'next_report': nxt, 'dept': r.dept, 'lineage_id': r.lineage_id, 'title': r.title,
                   'title_key': r.title_key, 'direction': r.direction, 'internal_admin': r.internal_admin,
                   'actual': getattr(r, 'actual', np.nan), 'target': getattr(r, 'target', np.nan), 'met': r.met, 'outcome': outc})
    ev = pd.DataFrame(ev).drop_duplicates(['report_fy', 'dept', 'title_key'])
    ev.to_csv(os.path.join(INTERIM, 'an_lineage_events.csv'), index=False)
    e = ev[(ev.internal_admin == False) & ev.met.notna()].copy()
    e['dropped'] = (e.outcome == 'dropped').astype(int)
    e['redef'] = (e.outcome == 'redefined').astype(int)
    e['changed'] = e.outcome.isin(['dropped', 'redefined']).astype(int)
    rows = []
    for yv in ['dropped', 'redef', 'changed']:
        miss, hit = e[e.met == 0], e[e.met == 1]
        # CMH across report years
        num = den = 0.0
        for R, g in e.groupby('report_fy'):
            a = ((g.met == 0) & (g[yv] == 1)).sum(); b = ((g.met == 0) & (g[yv] == 0)).sum()
            c = ((g.met == 1) & (g[yv] == 1)).sum(); d = ((g.met == 1) & (g[yv] == 0)).sum()
            n = a + b + c + d
            if n:
                num += a * d / n; den += b * c / n
        rows.append({'outcome': yv, 'n_missed': len(miss), 'rate_after_miss': miss[yv].mean(), 'n_met': len(hit),
                     'rate_after_met': hit[yv].mean(), 'risk_ratio': miss[yv].mean() / hit[yv].mean() if hit[yv].mean() else np.nan,
                     'cmh_odds_ratio_by_report_year': num / den if den else np.nan})
    dt = pd.DataFrame(rows)
    dt.to_csv(os.path.join(INTERIM, 'an_drop_test.csv'), index=False)
    by = e.groupby(['report_fy', 'met']).agg(n=('dropped', 'size'), drop_rate=('dropped', 'mean'), redef_rate=('redef', 'mean')).unstack('met')
    by.to_csv(os.path.join(INTERIM, 'an_drop_by_year.csv'))
    # notable dropped-after-miss examples (large miss, public-facing)
    ex = e[(e.met == 0) & (e.outcome.isin(['dropped', 'redefined']))].copy()
    sign = np.where(ex.direction == 'higher_better', 1, -1)
    ex['shortfall'] = sign * (ex.actual - ex.target) / ex.target.abs().replace(0, np.nan)
    ex.sort_values('shortfall').to_csv(os.path.join(INTERIM, 'an_dropped_examples.csv'), index=False)
    print(dt.round(3).to_string())
    print(by.round(3).to_string())

    # Long-run target series per lineage (same/reworded members only; redefined members start a new segment)
    t = pd.read_csv(os.path.join(INTERIM, 'pdf_values.csv'))
    t = t[(t.kind == 'target') & (t.fy == t.report_fy) & t.value_num.notna()]
    t = t.merge(lin[['dept', 'title_key', 'lineage_id', 'relation', 'direction', 'internal_admin']], on=['dept', 'title_key'])
    t = t[['lineage_id', 'dept', 'title_key', 'relation', 'direction', 'internal_admin', 'fy', 'value_num']].rename(columns={'value_num': 'target'})
    a = pd.read_csv(os.path.join(INTERIM, 'pdf_values.csv'))
    a = a[(a.kind == 'actual') & (a.fy == a.report_fy) & a.value_num.notna()][['dept', 'title_key', 'fy', 'value_num']].rename(columns={'value_num': 'actual'})
    t = t.merge(a, on=['dept', 'title_key', 'fy'], how='left')
    # segment = lineage split at each 'redefined' member
    t['segment'] = t.lineage_id + np.where(t.relation == 'redefined', '-R-' + t.title_key.str[:30], '')
    t = t.sort_values(['segment', 'fy']).drop_duplicates(['segment', 'fy'])
    t['met'] = [met(x, y, d) for x, y, d in zip(t.actual, t.target, t.direction)]
    t.to_csv(os.path.join(INTERIM, 'an_target_series_long.csv'), index=False)
    g = t.groupby('segment')
    t['next_target'] = g.target.shift(-1); t['next_fy'] = g.fy.shift(-1)
    # the FY t+1 target is set during FY t, when FY t-1's result is the latest full-year result known
    t['prev_met'] = g.met.shift(1); t['prev_fy'] = g.fy.shift(1)
    t.loc[t.prev_fy != t.fy - 1, 'prev_met'] = np.nan
    c = t[(t.next_fy == t.fy + 1) & t.direction.isin(['higher_better', 'lower_better']) & (t.internal_admin == False)].copy()
    c['rel'] = (c.next_target - c.target) / c.target.abs().replace(0, np.nan)
    sg = np.where(c.direction == 'higher_better', 1, -1)
    c['eased'] = sg * c.rel < -0.05
    c['raised'] = sg * c.rel > 0.05
    c.to_csv(os.path.join(INTERIM, 'an_target_easing_long.csv'), index=False)
    s = c.groupby(c.prev_met.map({0.0: 'after_miss', 1.0: 'after_met'})).agg(n=('eased', 'size'), share_eased=('eased', 'mean'), share_raised=('raised', 'mean'))
    print('long-run (report-printed) target changes FY2006-FY2019:\n', s.round(3).to_string())


if __name__ == '__main__':
    main()
