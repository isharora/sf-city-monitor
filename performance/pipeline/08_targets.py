"""Target analyses on the Controller's current measure set (6dpt-7w23), with direction from the measure map.
 A. Attainment: met target? by measure-year (direction-aware), rates by dept and year.
 B. Target easing: year-over-year target changes classified easier/harder (direction-aware); test whether easing
    is more likely after a miss than after a hit. Timing: the FY t+1 target is set in spring of FY t, when the FY t-1
    result and FY t mid-year result are known. "Prior miss" = FY t-1 full-year result missed its target, or FY t
    mid-year projection below target.
 C. Restatements: FY2011-FY2016 values in the FY13/FY14 snapshots (5x94-tptc, 6h77-suve) vs the same measure-years
    in today's dataset (exact department + title match).
Outputs: data/interim/an_attainment.csv, an_attainment_dept.csv, an_target_changes.csv, an_target_easing_test.csv,
         an_restatements.csv
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

TOL = 0.005  # relative tolerance for "met"


def met(result, target, direction):
    if pd.isna(result) or pd.isna(target) or direction == 'neutral':
        return np.nan
    tol = abs(target) * TOL
    return float(result >= target - tol) if direction == 'higher_better' else float(result <= target + tol)


def main():
    cur = pd.read_csv(os.path.join(INTERIM, 'measures_current.csv'))
    mp = pd.read_csv(os.path.join(INTERIM, 'measure_map.csv'))[['measure_id', 'direction', 'measure_kind', 'producing_dept', 'service_area']]
    d = cur.merge(mp, on='measure_id', how='left')
    d['met'] = [met(r, t, dr) for r, t, dr in zip(d.result, d.target, d.direction)]
    d['mid_met'] = [met(r, t, dr) for r, t, dr in zip(d.mid_projection, d.target, d.direction)]
    d.to_csv(os.path.join(INTERIM, 'an_attainment.csv'), index=False)
    a = d[d.fy.between(2013, 2025) & d.met.notna()]
    by = a.groupby(['dept', 'fy']).met.agg(['mean', 'count']).reset_index().rename(columns={'mean': 'share_met', 'count': 'n_measures'})
    by.to_csv(os.path.join(INTERIM, 'an_attainment_dept.csv'), index=False)
    city = a.groupby('fy').met.agg(['mean', 'count'])
    print('citywide share of targets met:\n', city.round(3).to_string())

    # B: target changes
    d = d.sort_values(['measure_id', 'fy'])
    g = d.groupby('measure_id')
    d['next_target'] = g.target.shift(-1)
    d['next_fy'] = g.fy.shift(-1)
    d['prev_met'] = g.met.shift(1)          # FY t-1 full-year
    ch = d[(d.next_fy == d.fy + 1) & d.target.notna() & d.next_target.notna() & d.direction.isin(['higher_better', 'lower_better'])].copy()
    ch['rel_change'] = (ch.next_target - ch.target) / ch.target.abs().replace(0, np.nan)
    sign = np.where(ch.direction == 'higher_better', 1, -1)
    ch['easier'] = (sign * ch.rel_change < -0.05)
    ch['harder'] = (sign * ch.rel_change > 0.05)
    ch['prior_miss'] = (ch.prev_met == 0) | (ch.mid_met == 0)
    ch['prior_hit'] = (ch.prev_met == 1) & (ch.mid_met != 0)
    ch.to_csv(os.path.join(INTERIM, 'an_target_changes.csv'), index=False)
    t = ch[ch.fy.between(2013, 2026)]
    rows = []
    for lab, sub in [('after_miss', t[t.prior_miss]), ('after_hit', t[t.prior_hit]), ('all', t)]:
        rows.append({'group': lab, 'n_changes': len(sub), 'share_eased': sub.easier.mean(), 'share_raised': sub.harder.mean()})
    et = pd.DataFrame(rows)
    # simple two-proportion z-test
    m1, m2 = t[t.prior_miss], t[t.prior_hit]
    p1, p2, n1, n2 = m1.easier.mean(), m2.easier.mean(), len(m1), len(m2)
    p = (m1.easier.sum() + m2.easier.sum()) / (n1 + n2)
    z = (p1 - p2) / np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    et['z_miss_vs_hit'] = z
    et.to_csv(os.path.join(INTERIM, 'an_target_easing_test.csv'), index=False)
    print(et.round(3).to_string())
    # measures with cumulative easing: first vs last target, direction-aware, for measures with >=5 target years
    span = d[d.target.notna() & d.direction.isin(['higher_better', 'lower_better']) & d.fy.between(2013, 2026)]
    fl = span.groupby('measure_id').agg(first_fy=('fy', 'min'), last_fy=('fy', 'max'), first_target=('target', 'first'),
                                        last_target=('target', 'last'), direction=('direction', 'first'), dept=('dept', 'first'),
                                        title=('title', 'first'), n=('fy', 'nunique'), share_met=('met', 'mean'))
    fl = fl[fl.n >= 5]
    fl['rel'] = (fl.last_target - fl.first_target) / fl.first_target.abs().replace(0, np.nan)
    fl['cum_easier'] = np.where(fl.direction == 'higher_better', fl.rel < -0.10, fl.rel > 0.10)
    fl.reset_index().to_csv(os.path.join(INTERIM, 'an_target_cumulative.csv'), index=False)
    print('measures with >=5 target-years:', len(fl), 'cumulatively eased >10%:', int(fl.cum_easier.sum()))

    # C: restatements
    s = pd.read_csv(os.path.join(INTERIM, 'measures_snapshot_fy13_14.csv'))
    s = s[s.kind.isin(['actual', 'target'])].dropna(subset=['value'])
    s['key'] = s.dept.astype(str) + '|' + s.title.str.lower().str.strip()
    cur['key'] = cur.dept + '|' + cur.title.str.lower().str.strip()
    rows = []
    for kind, col in [('actual', 'result'), ('target', 'target')]:
        a_ = s[s.kind == kind].groupby(['key', 'fy', 'report']).value.first().reset_index()
        b_ = cur[['key', 'fy', col, 'data_type', 'measure_id']].rename(columns={col: 'now'})
        j = a_.merge(b_, on=['key', 'fy'])
        # snapshot stores percents as 0-100 in some rows; align scale where current is a fraction
        j['then'] = np.where((j.data_type == 'Percent') & (j.value > 1.5) & (j.now <= 1.5), j.value / 100, j.value)
        j['kind'] = kind
        rows.append(j)
    r = pd.concat(rows)
    r = r.dropna(subset=['now'])
    r['rel_diff'] = (r.now - r.then) / r.then.abs().replace(0, np.nan)
    r['restated'] = r.rel_diff.abs() > 0.05  # >5%; smaller differences are rounding
    r.to_csv(os.path.join(INTERIM, 'an_restatements.csv'), index=False)
    print(r.groupby('kind').agg(pairs=('restated', 'size'), measures=('measure_id', 'nunique'), restated=('restated', 'sum')).to_string())


if __name__ == '__main__':
    main()
