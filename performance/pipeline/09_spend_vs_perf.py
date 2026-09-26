"""Real spending vs the department's own performance measures.

For each department: real (FY2026 $, Bay Area CPI-U) gross operating spending (all funds; operating characters, excludes
capital/debt/transfers), base window vs recent window, and the direction-adjusted change in its own measures over the same
windows. Measures used: direction known (higher/lower better) and kind in outcome/quality/efficiency/satisfaction/output
(workload and internal-admin measures excluded). A measure "improved" if its direction-adjusted change exceeds +5%, "declined"
if below -5%, else "flat". Department performance index = (improved - declined) / measures.

Windows: primary base FY2015-17 vs recent FY2023-25 (>=2 years of results in each window).
Robustness: (a) FY2013-15 vs FY2023-25, (b) FY2017-19 vs FY2023-25, (c) nominal dollars, (d) per resident,
(e) personnel cost only (salaries+benefits), (f) reorg-combined human services (HSA+HOM+DEC+CFC), (g) national CPI.
Outputs: data/interim/an_measure_change.csv, an_spend_vs_perf.csv, an_spend_vs_perf_robust.csv
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

KINDS = ['outcome', 'quality', 'efficiency', 'satisfaction', 'output']
COMBINE = {'HSA': 'HSX', 'HOM': 'HSX', 'DEC': 'HSX', 'CFC': 'HSX'}  # human-services cluster for reorg robustness


def measure_change(att, base, recent, min_years=2):
    a = att[att.direction.isin(['higher_better', 'lower_better']) & att.measure_kind.isin(KINDS) & att.result.notna()]
    b = a[a.fy.between(*base)].groupby('measure_id').result.agg(['mean', 'count'])
    r = a[a.fy.between(*recent)].groupby('measure_id').result.agg(['mean', 'count'])
    j = b.join(r, lsuffix='_b', rsuffix='_r', how='inner')
    j = j[(j.count_b >= min_years) & (j.count_r >= min_years)]
    meta = a.drop_duplicates('measure_id').set_index('measure_id')[['dept', 'title', 'direction', 'measure_kind', 'data_type']]
    j = j.join(meta)
    sign = np.where(j.direction == 'higher_better', 1, -1)
    # percent measures: use change in percentage points relative to base; numeric: relative change
    j['adj_change'] = sign * (j.mean_r - j.mean_b) / j.mean_b.abs().replace(0, np.nan)
    j['adj_change'] = j.adj_change.clip(-1, 1)
    j['status'] = np.select([j.adj_change > 0.05, j.adj_change < -0.05], ['improved', 'declined'], 'flat')
    return j.reset_index()


def spend_change(dept_fy, col, base, recent, dept_col='dept'):
    s = dept_fy.groupby([dept_col, 'fy'])[col].sum(min_count=1).reset_index()
    b = s[s.fy.between(*base)].groupby(dept_col)[col].mean()
    r = s[s.fy.between(*recent)].groupby(dept_col)[col].mean()
    return (r / b - 1).rename('spend_change'), b.rename('spend_base'), r.rename('spend_recent')


def summarize(mc, dept_col='dept'):
    g = mc.groupby(dept_col)
    out = pd.DataFrame({'n_measures': g.size(), 'improved': g.status.apply(lambda s: (s == 'improved').sum()),
                        'declined': g.status.apply(lambda s: (s == 'declined').sum()),
                        'flat': g.status.apply(lambda s: (s == 'flat').sum()),
                        'median_adj_change': g.adj_change.median()})
    out['perf_index'] = (out.improved - out.declined) / out.n_measures
    return out


def run(att, d, base, recent, col, label, combine=False):
    att = att.copy(); d = d.copy()
    if combine:
        att['dept'] = att.dept.replace(COMBINE); d['dept'] = d.dept.replace(COMBINE)
    mc = measure_change(att, base, recent)
    s = summarize(mc)
    sc, sb, sr = spend_change(d, col, base, recent)
    out = s.join(sc).join(sb).join(sr)
    out['variant'] = label
    return mc, out.reset_index()


def main():
    att = pd.read_csv(os.path.join(INTERIM, 'an_attainment.csv'))
    d = pd.read_csv(os.path.join(INTERIM, 'dept_fy.csv'))
    d['pers_real'] = d.actual_salaries_real + d.actual_benefits_real
    d['oper_real_per_res'] = d.actual_oper_all_real / d.population_primary
    d['oper_real_us'] = d.actual_oper_all * d.mult_us
    P = ((2015, 2017), (2023, 2025))
    mc, main_ = run(att, d, *P, 'actual_oper_all_real', 'primary: FY15-17 vs FY23-25, real oper spending')
    mc.to_csv(os.path.join(INTERIM, 'an_measure_change.csv'), index=False)
    main_['dept_name'] = main_.dept.map(DEPT_NAMES)
    main_ = main_[main_.n_measures >= 4]

    def quad(r):
        if pd.isna(r.spend_change):
            return ''
        up = r.spend_change > 0.15
        down = r.spend_change < 0.0
        if up and r.perf_index <= 0:
            return 'spending up >15%, own measures flat or worse'
        if up and r.perf_index > 0:
            return 'spending up >15%, own measures improved'
        if (not up) and r.perf_index > 0.2:
            return 'spending flat/down, own measures improved'
        return 'other'
    main_['quadrant'] = main_.apply(quad, axis=1)
    main_.to_csv(os.path.join(INTERIM, 'an_spend_vs_perf.csv'), index=False)
    variants = [main_]
    for base, recent, col, lab, comb in [
        ((2013, 2015), (2023, 2025), 'actual_oper_all_real', 'alt window FY13-15 vs FY23-25', False),
        ((2017, 2019), (2023, 2025), 'actual_oper_all_real', 'alt window FY17-19 vs FY23-25', False),
        ((2015, 2017), (2023, 2025), 'actual_oper_all', 'nominal dollars', False),
        ((2015, 2017), (2023, 2025), 'oper_real_per_res', 'real per resident', False),
        ((2015, 2017), (2023, 2025), 'pers_real', 'real personnel cost only', False),
        ((2015, 2017), (2023, 2025), 'oper_real_us', 'national CPI-U deflator', False),
        ((2015, 2017), (2023, 2025), 'actual_oper_all_real', 'human services combined (HSA+HOM+DEC+CFC)', True)]:
        _, o = run(att, d, base, recent, col, lab, comb)
        variants.append(o[o.n_measures >= 4])
    rob = pd.concat(variants, ignore_index=True)
    rob.to_csv(os.path.join(INTERIM, 'an_spend_vs_perf_robust.csv'), index=False)
    pd.set_option('display.width', 250)
    print(main_.sort_values('spend_change', ascending=False)[['dept', 'dept_name', 'n_measures', 'improved', 'flat', 'declined',
          'perf_index', 'median_adj_change', 'spend_change', 'quadrant']].round(3).to_string())
    piv = rob.pivot_table(index='dept', columns='variant', values='spend_change')
    print(piv.round(2).to_string())


if __name__ == '__main__':
    main()
