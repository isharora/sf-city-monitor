"""Red team: re-derive the key numbers with independent code paths (raw files, separate filters, no shared mappings)
and run robustness tests. Writes data/interim/redteam_results.json and prints a report.

Independence: this script does not import pipeline/common.py mappings. It re-implements filters with its own
string logic directly on the raw CSV/parquet downloads.
"""
import pandas as pd, numpy as np, os, json, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
INT = os.path.join(ROOT, 'data', 'interim')
R = {}


def cpi_pop():
    cpi = pd.read_csv(os.path.join(RAW, 'context', 'cpi_fy.csv')).set_index('fy')
    pop = pd.read_csv(os.path.join(RAW, 'context', 'population_fy.csv')).set_index('fy')
    return cpi.bay_cpi_fyavg, cpi.us_cpi_fyavg, pop.pop_dof_jan1, pop.pop_census_mid


def r1_gf_per_resident():
    """General Fund operating spending per resident, FY2013 vs FY2025, real FY2026 $."""
    a = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str,
                    usecols=['Fiscal Year', 'Revenue or Spending', 'Related Govt Units', 'Fund Type', 'Character', 'Amount'])
    a = a[(a['Revenue or Spending'] == 'Spending') & (a['Fund Type'] == 'General Fund') & (a['Related Govt Units'].str.upper() != 'YES')]
    a['Amount'] = a.Amount.astype(float)
    ch = a.Character.fillna('').str.lower()
    keep = ch.str.contains('salar|fringe|personnel|materials|grant|aid |aid$|aid pay|aid ass|support|care of|special items|other expenses')
    keep &= ~ch.str.contains('transfer|capital|debt|services of other|overhead|allocat')
    g = a[keep].groupby('Fiscal Year').Amount.sum()
    g.index = g.index.astype(int)
    bay, us, dof, cen = cpi_pop()
    out = {}
    for fy in (2013, 2019, 2025):
        nominal = g[fy]
        out[fy] = {'nominal_total': nominal, 'real_per_res_dof': nominal * bay[2026] / bay[fy] / dof[fy],
                   'real_per_res_census': nominal * bay[2026] / bay[fy] / cen[fy],
                   'real_per_res_uscpi': nominal * us[2026] / us[fy] / dof[fy], 'nominal_per_res': nominal / dof[fy]}
    R['gf_oper_per_resident'] = out
    main = pd.read_parquet(os.path.join(INT, 'spend_cube.parquet'))
    return out


def r2_police_ot():
    e = pd.read_csv(os.path.join(RAW, 'employee_comp.csv'), dtype=str, usecols=['Year Type', 'Year', 'Department Code', 'Overtime', 'Total Salary'])
    e = e[(e['Year Type'] == 'Fiscal') & (e['Department Code'] == 'POL')]
    for c in ['Overtime', 'Total Salary']:
        e[c] = pd.to_numeric(e[c], errors='coerce')
    y = e.groupby('Year')[['Overtime', 'Total Salary']].sum()
    res = {fy: {'overtime': y.loc[str(fy), 'Overtime'], 'ot_share': y.loc[str(fy), 'Overtime'] / y.loc[str(fy), 'Total Salary']} for fy in (2019, 2025, 2026)}
    b = pd.read_csv(os.path.join(RAW, 'budget.csv'), dtype=str, usecols=['Fiscal Year', 'Revenue or Spending', 'Department Code', 'Object', 'Budget'])
    b = b[(b['Revenue or Spending'] == 'Spending') & (b['Department Code'] == 'POL') & b.Object.str.contains('overtime', case=False, na=False)]
    s = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str, usecols=['Fiscal Year', 'Revenue or Spending', 'Department Code', 'Object', 'Amount'])
    s = s[(s['Revenue or Spending'] == 'Spending') & (s['Department Code'] == 'POL') & s.Object.str.contains('overtime', case=False, na=False)]
    for fy in (2019, 2025, 2026):
        res[fy]['ot_budget_ledger'] = b[b['Fiscal Year'] == str(fy)].Budget.astype(float).sum()
        res[fy]['ot_actual_ledger'] = s[s['Fiscal Year'] == str(fy)].Amount.astype(float).sum()
    R['police_overtime'] = res
    return res


def fy_files(folder, fy):
    months = [f'{fy-1}-{m:02d}' for m in range(7, 13)] + [f'{fy}-{m:02d}' for m in range(1, 7)]
    return [os.path.join(RAW, 'outcomes', 'chunks', folder, m + '.parquet') for m in months]


def r3_fire_ems(fy=2025):
    f = pd.concat([pd.read_parquet(p) for p in fy_files('fire', fy) if os.path.exists(p)])
    f = f[f.call_type.eq('Medical Incident') & f.final_priority.astype(str).isin(['3', 'E'])]
    rec = pd.to_datetime(f.received_dttm, errors='coerce'); ons = pd.to_datetime(f.on_scene_dttm, errors='coerce')
    f = f.assign(rec=rec, ons=ons)
    g = f.groupby('call_number').agg(rec=('rec', 'min'), ons=('ons', 'min')).dropna()
    m = (g.ons - g.rec).dt.total_seconds() / 60
    m = m[(m > 0) & (m < 120)]
    out = {'fy': fy, 'calls': int(len(m)), 'median_min': float(m.median()), 'p90_min': float(m.quantile(0.9)),
           'definition': 'call_type == Medical Incident, final_priority 3/E; first on-scene minus earliest received'}
    R['fire_ems_' + str(fy)] = out
    return out


def r4_police_a(fy=2025):
    p = pd.concat([pd.read_parquet(x) for x in fy_files('police', fy) if os.path.exists(x)])
    p = p[(p.onview_flag.astype(str).str.upper() == 'N') & p.dup_cad_number.isna() & (p.priority_final == 'A')
          & p.agency.astype(str).str.contains('Police', case=False)]
    d = (pd.to_datetime(p.onscene_datetime, errors='coerce') - pd.to_datetime(p.received_datetime, errors='coerce')).dt.total_seconds() / 60
    d = d[(d > 0) & (d < 24 * 60)]
    out = {'fy': fy, 'calls_with_onscene': int(len(d)), 'median_min': float(d.median())}
    R['police_A_' + str(fy)] = out
    return out


def r5_target_easing():
    """Independent test of 'targets eased after misses' on the raw 6dpt file.
    (a) direction from the Controller's own 'Performance Pattern' (FY13/FY14 snapshots) instead of the LLM map;
    (b) direction-free: did the next target move TOWARD the latest known result (by >5%)?"""
    m = pd.read_csv(os.path.join(RAW, 'perf_measures', 'citywide_performance_metrics.csv'), dtype=str)
    m = m[m['Fiscal Year'].notna()]
    m['fy'] = m['Fiscal Year'].str[-2:].astype(int) + 2000
    m['key'] = m['Department Name'].str.upper().str.strip() + '|' + m['Measure Title'].str.strip().str.lower()
    for c in ['Target', 'Full-Year Result']:
        m[c] = pd.to_numeric(m[c], errors='coerce')
    m = m.sort_values(['key', 'fy'])
    g = m.groupby('key')
    m['prev_res'] = g['Full-Year Result'].shift(1); m['prev_tgt'] = g['Target'].shift(1); m['prev_fy'] = g.fy.shift(1)
    m['next_tgt'] = g['Target'].shift(-1); m['next_fy'] = g.fy.shift(-1)
    x = m[(m.prev_fy == m.fy - 1) & (m.next_fy == m.fy + 1) & m.prev_res.notna() & m.prev_tgt.notna() & m.Target.notna() & m.next_tgt.notna()
          & m.fy.between(2014, 2026)].copy()
    # (b) direction-free: 'gap' = last known result - its target; 'move' = next target - current target
    gap = x.prev_res - x.prev_tgt
    move = x.next_tgt - x.Target
    big = (move.abs() > 0.05 * x.Target.abs())
    x['toward_result'] = big & (np.sign(move) == np.sign(gap)) & (gap != 0)
    x['away_from_result'] = big & (np.sign(move) == -np.sign(gap)) & (gap != 0)
    x['result_below_target'] = gap < 0
    df = {'n': int(len(x)),
          'share_moved_toward_last_result_when_result_differs': float(x[gap != 0].toward_result.mean()),
          'share_moved_away': float(x[gap != 0].away_from_result.mean())}
    # (a) Controller direction via snapshots
    s = pd.read_csv(os.path.join(RAW, 'perf_measures', 'annual_report_fy14.csv'), dtype=str)
    s.columns = [re.sub(r'\s+', ' ', c).strip() for c in s.columns]
    s['key'] = s['Department'].str.upper().str.strip() + '|' + s['Performance Measure'].str.strip().str.lower()
    pat = s.drop_duplicates('key').set_index('key')['Performance Pattern']
    x['pattern'] = x.key.map(pat)
    y = x[x.pattern.isin(['Above target is positive', 'Below target is positive'])].copy()
    sign = np.where(y.pattern == 'Above target is positive', 1, -1)
    y['missed'] = sign * (y.prev_res - y.prev_tgt) < -0.005 * y.prev_tgt.abs()
    y['eased'] = sign * (y.next_tgt - y.Target) < -0.05 * y.Target.abs()
    ctrl = {'n_changes_with_controller_direction': int(len(y)), 'n_measures': int(y.key.nunique()),
            'share_eased_after_miss': float(y[y.missed].eased.mean()), 'share_eased_after_met': float(y[~y.missed].eased.mean())}
    R['target_easing_independent'] = {'direction_free': df, 'controller_direction': ctrl}
    return R['target_easing_independent']


def r6_attainment_tolerance():
    a = pd.read_csv(os.path.join(INT, 'an_attainment.csv'))
    a = a[a.direction.isin(['higher_better', 'lower_better']) & a.result.notna() & a.target.notna()]
    out = {}
    for tol in (0.0, 0.005, 0.02, 0.05):
        t = a.target.abs() * tol
        met = np.where(a.direction == 'higher_better', a.result >= a.target - t, a.result <= a.target + t)
        s = pd.Series(met, index=a.index).groupby(a.fy).mean()
        out[f'tol_{tol}'] = {int(k): round(float(v), 3) for k, v in s.items() if 2013 <= k <= 2025}
    # fixed panel: measures with results in every year FY2016-FY2025
    full = a[a.fy.between(2016, 2025)].groupby('measure_id').fy.nunique()
    ids = full[full == 10].index
    b = a[a.measure_id.isin(ids) & a.fy.between(2016, 2025)]
    t = b.target.abs() * 0.005
    met = np.where(b.direction == 'higher_better', b.result >= b.target - t, b.result <= b.target + t)
    out['fixed_panel_fy16_25'] = {'n_measures': int(len(ids)), **{int(k): round(float(v), 3) for k, v in pd.Series(met, index=b.index).groupby(b.fy).mean().items()}}
    R['attainment_sensitivity'] = out
    return out


def r7_library():
    s = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str, usecols=['Fiscal Year', 'Revenue or Spending', 'Department Code', 'Character', 'Related Govt Units', 'Amount'])
    s = s[(s['Revenue or Spending'] == 'Spending') & (s['Department Code'] == 'LIB') & (s['Related Govt Units'].str.upper() != 'YES')]
    ch = s.Character.fillna('').str.lower()
    s = s[~ch.str.contains('transfer|capital|debt|unapprop|carry')]
    tot = s.groupby('Fiscal Year').Amount.apply(lambda v: v.astype(float).sum())
    m = pd.read_csv(os.path.join(RAW, 'perf_measures', 'citywide_performance_metrics.csv'), dtype=str)
    v = m[m['Measure Title'].str.startswith('Number of persons entering San Francisco Main and Branch', na=False)]
    v = v.assign(fy=v['Fiscal Year'].str[-2:].astype(int) + 2000, res=pd.to_numeric(v['Full-Year Result'], errors='coerce')).set_index('fy').res
    own = m[m['Measure Title'].eq('Expenditures per Number of Visits')]
    own = own.assign(fy=own['Fiscal Year'].str[-2:].astype(int) + 2000, res=pd.to_numeric(own['Full-Year Result'], errors='coerce')).set_index('fy').res
    out = {fy: {'spend_nominal': float(tot[str(fy)]), 'visits': float(v[fy]), 'per_visit_nominal': float(tot[str(fy)] / v[fy]),
                'dept_reported': float(own.get(fy, np.nan))} for fy in (2019, 2023, 2025)}
    R['library_cost_per_visit'] = out
    return out


def r8_spend_perf_robust():
    rob = pd.read_csv(os.path.join(INT, 'an_spend_vs_perf_robust.csv'))
    rob = rob[rob.dept != 'HSX']
    rob['up_flat'] = (rob.spend_change > 0.15) & (rob.perf_index <= 0)
    rob['down_improve'] = (rob.spend_change <= 0.0) & (rob.perf_index > 0.2)
    rob['fire_like'] = (rob.spend_change > 0.05) & (rob.perf_index < -0.3)
    k = rob.groupby('dept').agg(variants=('variant', 'nunique'), up_flat=('up_flat', 'sum'), down_improve=('down_improve', 'sum'),
                                spend_up_perf_down=('fire_like', 'sum'), min_spend=('spend_change', 'min'), max_spend=('spend_change', 'max'),
                                perf_min=('perf_index', 'min'), perf_max=('perf_index', 'max'))
    R['spend_vs_perf_robustness'] = k.round(3).reset_index().to_dict('records')
    return k


def r9_window_medians():
    """One-time items: use window medians instead of means for spending change (FY15-17 vs FY23-25)."""
    d = pd.read_csv(os.path.join(INT, 'dept_fy.csv'))
    b = d[d.fy.between(2015, 2017)].groupby('dept').actual_oper_all_real.median()
    r = d[d.fy.between(2023, 2025)].groupby('dept').actual_oper_all_real.median()
    ch = (r / b - 1).dropna()
    main = pd.read_csv(os.path.join(INT, 'an_spend_vs_perf.csv')).set_index('dept').spend_change
    j = pd.DataFrame({'mean_based': main, 'median_based': ch}).dropna()
    R['one_time_items_window_median'] = j.round(3).reset_index().rename(columns={'index': 'dept'}).to_dict('records')
    return j


def r10_reorg():
    d = pd.read_csv(os.path.join(INT, 'dept_fy.csv'))
    grp = {'HSA': 'HS', 'HOM': 'HS', 'DEC': 'HS', 'CFC': 'HS', 'POL': 'PD', 'DPA': 'PD'}
    d['g'] = d.dept.map(grp)
    x = d[d.g.notna()].groupby(['g', 'fy']).actual_oper_all_real.sum(min_count=1).unstack(0)
    out = {g: {'fy2013': float(x.loc[2013, g]), 'fy2017': float(x.loc[2017, g]), 'fy2025': float(x.loc[2025, g]),
               'change_13_25': float(x.loc[2025, g] / x.loc[2013, g] - 1)} for g in x.columns}
    hom = d[d.dept == 'HOM'].set_index('fy').actual_oper_all_real
    out['HOM_alone'] = {'fy2017': float(hom[2017]), 'fy2025': float(hom[2025]), 'change_17_25': float(hom[2025] / hom[2017] - 1)}
    R['reorg_combined'] = out
    return out


def compare_to_main():
    """Pull the main pipeline's versions of the same numbers for side-by-side comparison."""
    c = pd.read_csv(os.path.join(INT, 'city_fy.csv')).set_index('fy')
    p = pd.read_csv(os.path.join(INT, 'outcomes_panel.csv'))
    w = pd.read_csv(os.path.join(INT, 'workforce_dept_fy.csv'))
    cpo = pd.read_csv(os.path.join(INT, 'cost_per_outcome.csv'))
    et = pd.read_csv(os.path.join(INT, 'an_target_easing_test.csv')).set_index('group')
    main = {
        'fire_ems_median_2025': float(p[(p.series == 'fire_code3_medical_first_unit_median_min') & (p.fy == 2025)].value.iloc[0]),
        'police_A_median_2025': float(p[(p.series == 'police_median_A') & (p.fy == 2025)].value.iloc[0]),
        'police_ot_2025': float(w[(w.dept == 'POL') & (w.fy == 2025)].overtime.iloc[0]),
        'library_per_visit_nominal_2025': float(cpo[(cpo.pair == 'library_cost_per_visit') & (cpo.fy == 2025)].unit_cost_nominal.iloc[0]),
        'easing_after_miss_main': float(et.loc['after_miss', 'share_eased']), 'easing_after_hit_main': float(et.loc['after_hit', 'share_eased']),
    }
    R['main_pipeline_values'] = main
    return main


if __name__ == '__main__':
    steps = [r1_gf_per_resident, r2_police_ot, r3_fire_ems, r4_police_a, r5_target_easing, r6_attainment_tolerance,
             r7_library, r8_spend_perf_robust, r9_window_medians, r10_reorg, compare_to_main]
    for fn in steps:
        print('\n###', fn.__name__, fn.__doc__.split('\n')[0] if fn.__doc__ else '')
        out = fn()
        print(out if not isinstance(out, pd.DataFrame) else out.round(3).to_string())
    with open(os.path.join(INT, 'redteam_results.json'), 'w') as f:
        json.dump(R, f, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o))
