"""Build-side computations for the insights page (performance/data/site/insights/insights.json).

Each function c_<key>() returns (V, CH):
  V  = dict of named scalar values used by the text templates in spec.py
  CH = dict of chart arrays (x values and series) used by the chart templates in spec.py
Sources: the pipeline's processed tables (data/interim, data/redteam, data/site/analyses) where they exist, and raw
downloads where no processed table holds the needed detail (payroll rows, revenue rows, NTD, survey microdata).
verify_insights.py recomputes every V and CH value independently from the raw source tables.
"""
import os, json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW = os.path.join(ROOT, 'data', 'raw')
INT = os.path.join(ROOT, 'data', 'interim')
SITE = os.path.join(ROOT, 'data', 'site')
RED = os.path.join(ROOT, 'data', 'redteam')

_cache = {}


def once(key, fn):
    if key not in _cache:
        _cache[key] = fn()
    return _cache[key]


def ctx():
    return once('ctx', lambda: pd.read_csv(os.path.join(INT, 'context_fy.csv')).set_index('fy'))


def dfy():
    return once('dfy', lambda: pd.read_csv(os.path.join(INT, 'dept_fy.csv')))


def dv(dept, col):
    d = dfy()
    return d[d.dept == dept].set_index('fy')[col]


def cube():
    return once('cube', lambda: pd.read_parquet(os.path.join(INT, 'spend_cube.parquet')))


def slong():
    return once('slong', lambda: pd.read_parquet(os.path.join(INT, 'spend_long.parquet')))


def ec():
    def load():
        e = pd.read_csv(os.path.join(RAW, 'employee_comp.csv'), low_memory=False,
                        usecols=['Year Type', 'Year', 'Department Code', 'Job Family', 'Job', 'Salaries', 'Overtime',
                                 'Other Salaries', 'Total Salary', 'Retirement', 'Hours'])
        return e[e['Year Type'] == 'Fiscal'].copy()
    return once('ec', load)


def outcomes():
    return once('out', lambda: pd.read_csv(os.path.join(INT, 'outcomes_panel.csv')))


def oser(series):
    o = outcomes()
    return o[o.series == series].set_index('fy').value


def rt2():
    return once('rt2', lambda: json.load(open(os.path.join(RED, 'redteam2.json'))))


def real(v, fy):
    return float(v) * float(ctx().mult_bay[fy])


YRS_WF = list(range(2013, 2027))


# ---------------------------------------------------------------------------------------------------------------------
def c_police_staffing():
    e = ec()
    p = e[(e['Department Code'] == 'POL') & (e['Job Family'] == 'Police Services')]
    g = p.groupby('Year').agg(n=('Salaries', 'size'), hours=('Hours', 'sum'), ot=('Overtime', 'sum'))
    # full-year proxy: regular pay at least half the median regular pay for the same job and year
    med = p.groupby(['Year', 'Job']).Salaries.transform('median')
    full = p[p.Salaries >= 0.5 * med].groupby('Year').size()
    V = {}
    for y in (2017, 2019, 2025, 2026):
        V[f'n_{y}'] = int(g.n[y]); V[f'hours_{y}'] = float(g.hours[y]); V[f'ot_{y}'] = float(g.ot[y])
        V[f'full_{y}'] = int(full[y])
    V['n_chg'] = V['n_2025'] / V['n_2019'] - 1
    V['full_chg'] = V['full_2025'] / V['full_2019'] - 1
    V['hours_chg'] = V['hours_2025'] / V['hours_2019'] - 1
    V['hpe_2019'] = V['hours_2019'] / V['n_2019']; V['hpe_2025'] = V['hours_2025'] / V['n_2025']
    V['hpe_chg'] = V['hpe_2025'] / V['hpe_2019'] - 1
    V['ot_real_2019'] = real(V['ot_2019'], 2019); V['ot_real_2025'] = real(V['ot_2025'], 2025)
    V['ot_real_x'] = V['ot_real_2025'] / V['ot_real_2019']
    V['n_chg_17'] = V['n_2025'] / V['n_2017'] - 1
    V['hours_chg_17'] = V['hours_2025'] / V['hours_2017'] - 1
    V['ot_hours_share_proxy'] = None
    V.pop('ot_hours_share_proxy')
    V['ledger_ot_2019'] = float(dv('POL', 'actual_overtime')[2019])
    ab, bb = dv('POL', 'actual_overtime')[2025], dv('POL', 'budget_overtime')[2025]
    V['ledger_ot_2025'] = float(ab); V['budget_ot_2025'] = float(bb); V['ledger_ratio_2025'] = float(ab / bb)
    yrs = list(range(2017, 2027))
    CH = {'x': yrs,
          'full': [100 * full[y] / full[2019] for y in yrs],
          'hours': [100 * g.hours[y] / g.hours[2019] for y in yrs],
          'ot_real': [100 * real(g.ot[y], y) / real(g.ot[2019], 2019) for y in yrs]}
    return V, CH


def c_ot100k():
    e = ec()
    m = ctx().mult_bay
    e = e.assign(otr=e.Overtime * e.Year.map(m))
    thr_real = 100000 * m[2025]  # $100k in FY2025 dollars, expressed in FY2026 dollars
    V = {}
    for y in (2013, 2019, 2025, 2026):
        s = e[e.Year == y]
        V[f'n_{y}'] = int((s.Overtime > 100000).sum())
        V[f'nreal_{y}'] = int((s.otr > thr_real).sum())
        V[f'share_{y}'] = float(s.Overtime[s.Overtime > 100000].sum() / s.Overtime.sum())
        for d in ('POL', 'SHF', 'FIR'):
            V[f'{d}_{y}'] = int(((s.Overtime > 100000) & (s['Department Code'] == d)).sum())
    V['thr'] = 100000
    V['x_real'] = V['n_2025'] / V['nreal_2013']
    L = slong()
    V['ledger_ot_2025'] = float(L[L.overtime & (L.fy == 2025) & (L.measure == 'actual')].amount.sum())
    V['exPOL_2019'] = V['n_2019'] - V['POL_2019']; V['exPOL_2025'] = V['n_2025'] - V['POL_2025']
    V['ps_share_2025'] = (V['POL_2025'] + V['SHF_2025'] + V['FIR_2025']) / V['n_2025']
    V['thr_2013'] = 100000 * m[2025] / m[2013]
    s13 = e[e.Year == 2013]
    V['sharereal_2013'] = float(s13.Overtime[s13.otr > thr_real].sum() / s13.Overtime.sum())
    V['nreal_2019'] = int((e[e.Year == 2019].otr > thr_real).sum())
    tot = e.groupby('Year').Overtime.sum()
    V['ot_2013'] = float(tot[2013]); V['ot_2025'] = float(tot[2025])
    V['ot_real_x'] = real(tot[2025], 2025) / real(tot[2013], 2013)
    yrs = YRS_WF
    big = e[e.otr > thr_real]   # inflation-adjusted threshold: $100,000 in FY2025 dollars
    cnt = big.groupby(['Year', 'Department Code']).size().unstack(fill_value=0)
    CH = {'x': yrs}
    for d in ('POL', 'SHF', 'FIR'):
        CH[d] = [int(cnt[d].get(y, 0)) if d in cnt else 0 for y in yrs]
    CH['other'] = [int(cnt.loc[y].sum()) - CH['POL'][i] - CH['SHF'][i] - CH['FIR'][i] if y in cnt.index else 0 for i, y in enumerate(yrs)]
    return V, CH


def c_fire():
    calls = oser('fire_calls_total'); med = oser('fire_code3_medical_first_unit_median_min'); p90 = oser('fire_code3_medical_first_unit_p90_min')
    sp = dv('FIR', 'actual_oper_all_real'); spn = dv('FIR', 'actual_oper_all')
    fte0 = pd.read_csv(os.path.join(RAW, 'context', 'fte_by_dept_fy.csv'))
    fte0 = fte0[fte0.dept_code == 'FIR'].set_index('fy')
    fte, fta = fte0.budget_fte_gross, fte0.actual_fte
    t3 = rt2()['t3_fire']['by_fy']
    V = {'calls_2013': int(calls[2013]), 'calls_2025': int(calls[2025]), 'calls_2019': int(calls[2019]),
         'med_2013': float(med[2013]), 'med_2025': float(med[2025]), 'p90_2013': float(p90[2013]), 'p90_2025': float(p90[2025]),
         'sp_2013': float(sp[2013]), 'sp_2025': float(sp[2025]), 'sp_2019': float(sp[2019]),
         'fte_2013': float(fte[2013]), 'fte_2025': float(fte[2025])}
    V['calls_chg'] = V['calls_2025'] / V['calls_2013'] - 1
    V['sp_chg'] = V['sp_2025'] / V['sp_2013'] - 1
    V['fte_chg'] = V['fte_2025'] / V['fte_2013'] - 1
    V['fta_2013'] = float(fta[2013]); V['fta_2025'] = float(fta[2025]); V['fta_chg'] = V['fta_2025'] / V['fta_2013'] - 1
    V['calls_per_pos_chg'] = (V['calls_2025'] / V['fte_2025']) / (V['calls_2013'] / V['fte_2013']) - 1
    V['calls_chg_19'] = V['calls_2025'] / V['calls_2019'] - 1
    V['sp_chg_19'] = V['sp_2025'] / V['sp_2019'] - 1
    m = ctx()
    V['sp_chg_us'] = (spn[2025] * m.mult_us[2025]) / (spn[2013] * m.mult_us[2013]) - 1
    V['per_call_2013'] = V['sp_2013'] / V['calls_2013']; V['per_call_2025'] = V['sp_2025'] / V['calls_2025']
    V['per_call_chg'] = V['per_call_2025'] / V['per_call_2013'] - 1
    V['d2a_2013'] = t3['2013']['final']['dispatch_to_arrival_median']; V['d2a_2025'] = t3['2025']['final']['dispatch_to_arrival_median']
    V['orig_med_2013'] = t3['2013']['original']['call_to_arrival_median']; V['orig_med_2025'] = t3['2025']['original']['call_to_arrival_median']
    yrs = list(range(2013, 2026))
    CH = {'x': yrs, 'calls': [100 * calls[y] / calls[2013] for y in yrs], 'spend': [100 * sp[y] / sp[2013] for y in yrs],
          'median': [100 * med[y] / med[2013] for y in yrs], 'filled': [100 * fta[y] / fta[2013] for y in yrs]}
    return V, CH


def c_police_calls():
    pr = pd.read_csv(os.path.join(RAW, 'outcomes', 'police_response_fy.csv')).set_index(['fy', 'priority'])
    sp = dv('POL', 'actual_oper_all_real')
    V = {}
    for y in (2016, 2019, 2025):
        for p in 'ABC':
            r = pr.loc[(y, p)]
            V[f'calls_{p}_{y}'] = int(r.calls); V[f'med_{p}_{y}'] = float(r.median_recv_to_onscene_min)
            V[f'p90_{p}_{y}'] = float(r.p90_recv_to_onscene_min)
            V[f'r2d_{p}_{y}'] = float(r.median_recv_to_dispatch_min); V[f'd2o_{p}_{y}'] = float(r.median_dispatch_to_onscene_min)
    for p in 'ABC':
        V[f'calls_{p}_chg'] = V[f'calls_{p}_2025'] / V[f'calls_{p}_2016'] - 1
        V[f'med_{p}_chg'] = V[f'med_{p}_2025'] / V[f'med_{p}_2016'] - 1
    V['calls_tot_2016'] = sum(V[f'calls_{p}_2016'] for p in 'ABC'); V['calls_tot_2025'] = sum(V[f'calls_{p}_2025'] for p in 'ABC')
    V['calls_tot_chg'] = V['calls_tot_2025'] / V['calls_tot_2016'] - 1
    V['sp_2016'] = float(sp[2016]); V['sp_2025'] = float(sp[2025]); V['sp_chg'] = V['sp_2025'] / V['sp_2016'] - 1
    V['per_call_2016'] = V['sp_2016'] / V['calls_tot_2016']; V['per_call_2025'] = V['sp_2025'] / V['calls_tot_2025']
    V['per_call_chg'] = V['per_call_2025'] / V['per_call_2016'] - 1
    CH = {'cats': ['Priority A', 'Priority B', 'Priority C'],
          'a': [V[f'med_{p}_2016'] for p in 'ABC'], 'b': [V[f'med_{p}_2025'] for p in 'ABC']}
    return V, CH


def c_homeless():
    hom = dv('HOM', 'actual_oper_all_real')
    s = pd.read_csv(os.path.join(RAW, 'outcomes', 'scorecard_outcome_extracts.csv'))
    s = s[s.measure_code == 7169].pivot_table(index='fy', columns='series', values='value')
    V = {'hom_2017': float(hom[2017]), 'hom_2018': float(hom[2018]), 'hom_2019': float(hom[2019]), 'hom_2025': float(hom[2025]),
         'hom_2026': float(hom[2026])}
    V['x_17_25'] = V['hom_2025'] / V['hom_2017']; V['x_18_25'] = V['hom_2025'] / V['hom_2018']; V['x_19_25'] = V['hom_2025'] / V['hom_2019']
    for y in (2019, 2022, 2024):
        V[f'unsh_{y}'] = int(s.pit_count_unsheltered[y]); V[f'sh_{y}'] = int(s.pit_count_sheltered[y]); V[f'tot_{y}'] = int(s.pit_count_total_homeless[y])
    V['unsh_chg'] = V['unsh_2024'] / V['unsh_2019'] - 1; V['sh_chg'] = V['sh_2024'] / V['sh_2019'] - 1; V['tot_chg'] = V['tot_2024'] / V['tot_2019'] - 1
    V['unsh_chg_22'] = V['unsh_2024'] / V['unsh_2022'] - 1
    V['sh_share_2019'] = V['sh_2019'] / V['tot_2019']; V['sh_share_2024'] = V['sh_2024'] / V['tot_2024']
    yrs = [int(y) for y in s.index if y >= 2005]
    CH = {'x': yrs, 'sheltered': [int(s.pit_count_sheltered[y]) for y in yrs], 'unsheltered': [int(s.pit_count_unsheltered[y]) for y in yrs]}
    return V, CH


def c_pension():
    a = slong()
    a = a[(a.measure == 'actual') & a.fy.between(2010, 2026)]
    ret = a[(a.char_class == 'benefits') & a.object.str.contains('Retirement', case=False, na=False)].groupby('fy').amount.sum()
    sal = a[a.char_class == 'salaries'].groupby('fy').amount.sum()
    w = pd.read_csv(os.path.join(INT, 'workforce_city_fy.csv')).set_index('fy')
    pay = w.retirement / w.total_salary
    V = {}
    for y in (2013, 2019, 2021, 2025, 2026):
        V[f'ret_{y}'] = float(ret[y]); V[f'sal_{y}'] = float(sal[y]); V[f'share_{y}'] = float(ret[y] / sal[y])
    for y in (2021, 2025):
        V[f'pay_share_{y}'] = float(pay[y])
    ot = a[a.overtime].groupby('fy').amount.sum()
    for y in (2013, 2021, 2025, 2026):
        V[f'reg_{y}'] = float(sal[y] - ot[y]); V[f'rshare_{y}'] = float(ret[y] / (sal[y] - ot[y]))
    V['rsavings_2025'] = (V['rshare_2021'] - V['rshare_2025']) * V['reg_2025']
    e = ec(); pe = e.groupby('Year')[['Retirement', 'Salaries', 'Other Salaries']].sum()
    pr_ = pe.Retirement / (pe.Salaries + pe['Other Salaries'])
    V['pay_rshare_2021'] = float(pr_[2021]); V['pay_rshare_2025'] = float(pr_[2025])
    V['sal_chg_21_25'] = V['sal_2025'] / V['sal_2021'] - 1
    V['ret_drop'] = V['ret_2021'] - V['ret_2025']
    V['savings_2025'] = (V['share_2021'] - V['share_2025']) * V['sal_2025']
    gf = a[a.gf]
    rg = gf[(gf.char_class == 'benefits') & gf.object.str.contains('Retirement', case=False, na=False)].groupby('fy').amount.sum()
    sg = gf[gf.char_class == 'salaries'].groupby('fy').amount.sum()
    V['gf_share_2021'] = float(rg[2021] / sg[2021]); V['gf_share_2025'] = float(rg[2025] / sg[2025])
    yrs = list(range(2010, 2027))
    CH = {'x': yrs, 'ledger': [100 * float(ret[y] / (sal[y] - ot[y])) for y in yrs],
          'payroll': [100 * float(pr_[y]) if y in pr_.index else None for y in yrs]}
    return V, CH


GRANT_GROUPS = ['HOM', 'CHF', 'DEC', 'MYR', 'HSA', 'ECN']


def c_grants():
    c = cube()
    m = ctx().mult_bay
    g = c[(c.char_class == 'grants') & c.fy.between(2013, 2026)]
    tot = g.groupby('fy').actual.sum()
    gf = g[g.gf].groupby('fy').actual.sum()
    ops = c[c.char_class.isin(['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'other']) & c.fy.between(2013, 2026)].groupby('fy').actual.sum()
    exn = g[~g.dept.isin(['HOM', 'DEC'])].groupby('fy').actual.sum()
    V = {'tot_2013': float(tot[2013]), 'tot_2019': float(tot[2019]), 'tot_2023': float(tot[2023]), 'tot_2025': float(tot[2025]), 'tot_2026': float(tot[2026])}
    V['nom_x'] = V['tot_2025'] / V['tot_2013']
    V['real_2013'] = real(tot[2013], 2013); V['real_2025'] = real(tot[2025], 2025); V['real_x'] = V['real_2025'] / V['real_2013']
    V['share_2013'] = float(tot[2013] / ops[2013]); V['share_2025'] = float(tot[2025] / ops[2025])
    V['gf_2013'] = float(gf[2013]); V['gf_2023'] = float(gf[2023]); V['gf_2026'] = float(gf[2026]); V['gf_chg_23_26'] = V['gf_2026'] / V['gf_2023'] - 1
    V['exn_real_x'] = real(exn[2025], 2025) / real(exn[2013], 2013)
    byd = g.groupby(['fy', 'dept']).actual.sum().unstack(fill_value=0)
    for d in ('HOM', 'CHF', 'DEC', 'MYR', 'ECN'):
        V[f'{d}_2025'] = float(byd.loc[2025, d])
    # not a reclassification: non-personnel in the same departments did not fall
    np_ = c[(c.char_class == 'non_personnel') & c.dept.isin(GRANT_GROUPS) & c.fy.isin([2013, 2025])].groupby('fy').actual.sum()
    V['np_real_2013'] = real(np_[2013], 2013); V['np_real_2025'] = real(np_[2025], 2025)
    yrs = list(range(2013, 2027))
    CH = {'x': yrs}
    for d in GRANT_GROUPS:
        CH[d] = [real(byd.loc[y, d], y) / 1e6 if d in byd.columns else 0.0 for y in yrs]
    CH['other'] = [real(byd.loc[y].sum() - byd.loc[y, [d for d in GRANT_GROUPS if d in byd.columns]].sum(), y) / 1e6 for y in yrs]
    return V, CH


# General Fund operating spending, same definition as the dashboard's headline (site char slots salaries, fringe,
# overtime, nonpersonnel incl. work orders, aid/grants; excludes capital, debt service, overhead allocations, other)
OPER = ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'services_other_depts']


def c_gf():
    c = cube()
    x = ctx()
    gf = c[c.gf & c.char_class.isin(OPER) & c.fy.between(2010, 2026)].groupby('fy').actual.sum()
    wo = c[c.gf & (c.char_class == 'services_other_depts') & c.fy.between(2010, 2026)].groupby('fy').actual.sum()
    pr = {y: gf[y] * x.mult_bay[y] / x.population_primary[y] for y in gf.index}
    V = {f'pr_{y}': float(pr[y]) for y in (2013, 2019, 2021, 2025, 2026)}
    V['chg_13_25'] = pr[2025] / pr[2013] - 1; V['chg_19_21'] = pr[2021] / pr[2019] - 1; V['chg_21_26'] = pr[2026] / pr[2021] - 1
    V['chg_21_25'] = pr[2025] / pr[2021] - 1
    us = {y: gf[y] * x.mult_us[y] / x.population_primary[y] for y in (2013, 2025)}
    V['chg_us_13_25'] = us[2025] / us[2013] - 1
    cen = {y: gf[y] * x.mult_bay[y] / x.pop_census_mid[y] for y in (2013, 2025)}
    V['chg_census_13_25'] = cen[2025] / cen[2013] - 1
    exw = {y: (gf[y] - wo[y]) * x.mult_bay[y] / x.population_primary[y] for y in (2013, 2019, 2021, 2025)}
    V['chg_exwo_13_25'] = exw[2025] / exw[2013] - 1; V['chg_exwo_19_21'] = exw[2021] / exw[2019] - 1
    V['real_tot_2019'] = real(gf[2019], 2019); V['real_tot_2021'] = real(gf[2021], 2021); V['real_tot_2025'] = real(gf[2025], 2025)
    V['pop_2019'] = int(x.population_primary[2019]); V['pop_2025'] = int(x.population_primary[2025])
    V['pop_chg'] = V['pop_2025'] / V['pop_2019'] - 1
    V['real_tot_chg_19_25'] = V['real_tot_2025'] / V['real_tot_2019'] - 1
    yrs = list(range(2010, 2027))
    CH = {'x': yrs, 'per_res': [float(pr[y]) for y in yrs]}
    return V, CH


def c_vacancy():
    f = pd.read_csv(os.path.join(RAW, 'context', 'fte_citywide_fy.csv')).set_index('fy')
    fd = pd.read_csv(os.path.join(RAW, 'context', 'fte_by_dept_fy.csv'))
    V = {}
    for y in (2013, 2021, 2022, 2023, 2024, 2025, 2026):
        V[f'bud_{y}'] = float(f.budget_fte_gross[y]); V[f'act_{y}'] = float(f.actual_fte[y]); V[f'att_{y}'] = float(f.budget_attrition_adj[y])
        V[f'vac_{y}'] = V[f'bud_{y}'] - V[f'act_{y}']; V[f'vrate_{y}'] = V[f'vac_{y}'] / V[f'bud_{y}']
    V['vac_min_21_24'] = min(V[f'vac_{y}'] for y in (2021, 2022, 2023, 2024)); V['vac_max_21_24'] = max(V[f'vac_{y}'] for y in (2021, 2022, 2023, 2024))
    V['vrate_min_21_24'] = min(V[f'vrate_{y}'] for y in (2021, 2022, 2023, 2024)); V['vrate_max_21_24'] = max(V[f'vrate_{y}'] for y in (2021, 2022, 2023, 2024))
    V['net_2025'] = V['bud_2025'] + V['att_2025']
    g1318 = [(f.budget_fte_gross[y] - f.actual_fte[y]) / f.budget_fte_gross[y] for y in range(2013, 2018)]
    V['vrate_min_13_18'] = float(min(g1318)); V['vrate_max_13_18'] = float(max(g1318))

    V['n_zero_att'] = int((f.loc[2019:2024].budget_attrition_adj == 0).sum())
    d23 = fd[fd.fy == 2023].groupby('dept_code')[['budget_fte_gross', 'actual_fte']].sum()
    for d in ('MTA', 'POL', 'SHF'):
        V[f'{d}_vrate_2023'] = float(1 - d23.actual_fte[d] / d23.budget_fte_gross[d])
    big = d23[d23.budget_fte_gross >= 100]
    V['n_big'] = int(len(big)); V['n_big_gap10'] = int(((1 - big.actual_fte / big.budget_fte_gross) > 0.10).sum()); V['hundred_fte'] = 100; V['ten'] = 0.10
    x23 = d23.drop(index='MTA')
    V['vrate_exMTA_2023'] = float(1 - x23.actual_fte.sum() / x23.budget_fte_gross.sum())
    # corroboration: salary spending vs adopted salary budget, all departments, FY2021-24
    dd = dfy()
    s = dd[dd.fy.between(2021, 2024)].groupby('fy')[['actual_salaries', 'budget_salaries']].sum()
    V['sal_exec_min'] = float((s.actual_salaries / s.budget_salaries).min()); V['sal_exec_max'] = float((s.actual_salaries / s.budget_salaries).max())
    yrs = list(range(2013, 2027))
    CH = {'x': yrs, 'budgeted': [float(f.budget_fte_gross[y]) for y in yrs],
          'net': [float(f.budget_fte_gross[y] + f.budget_attrition_adj[y]) if f.budget_attrition_adj[y] != 0 else None for y in yrs],
          'filled': [float(f.actual_fte[y]) for y in yrs]}
    return V, CH


def c_ot_budget():
    # from the spending cube rows directly (dept_fy masks all FY2018 DPW/PUC actuals for the cutover, which would
    # drop their overtime too; overtime objects are not affected by the conversion entries)
    L = slong()
    L = L[L.overtime & L.fy.between(2010, 2026)]
    yrs = list(range(2010, 2027))
    s = L.groupby(['fy', 'measure']).amount.sum().unstack().rename(columns={'actual': 'actual_overtime', 'budget': 'budget_overtime'})
    r = s.actual_overtime / s.budget_overtime
    xp = L[L.dept != 'POL'].groupby(['fy', 'measure']).amount.sum().unstack().rename(columns={'actual': 'actual_overtime', 'budget': 'budget_overtime'})
    V = {'n_years': len(yrs), 'n_over': int((r > 1).sum()), 'min_ratio': float(r.min()), 'max_ratio': float(r.max()),
         'min_fy': int(r.idxmin()), 'max_fy': int(r.idxmax()),
         'cum_over': float((s.actual_overtime - s.budget_overtime).sum()),
         'act_2025': float(s.actual_overtime[2025]), 'bud_2025': float(s.budget_overtime[2025]),
         'act_2026': float(s.actual_overtime[2026]), 'bud_2026': float(s.budget_overtime[2026]),
         'n_over_expol': int((xp.actual_overtime > xp.budget_overtime).sum()),
         'bud_x_13_26': float(s.budget_overtime[2026] / s.budget_overtime[2013])}
    # payroll overtime vs adopted overtime budget
    w = pd.read_csv(os.path.join(INT, 'workforce_city_fy.csv')).set_index('fy')
    pr = w.overtime / s.budget_overtime.reindex(w.index)
    V['n_over_payroll'] = int((pr.loc[2013:2026] > 1).sum()); V['n_payroll_years'] = int(pr.loc[2013:2026].notna().sum())
    V['pay_ot_2025'] = float(w.overtime[2025])
    CH = {'x': yrs, 'budget': [float(s.budget_overtime[y]) / 1e6 for y in yrs], 'actual': [float(s.actual_overtime[y]) / 1e6 for y in yrs]}
    return V, CH


FARE_OBJ = ['Transit Cash Fares', 'Transit Pass Revenue', 'Transit Cable Car Revenue', 'Transit Token Revenue',
            'Transit ParaTransit Revenue', 'Transit Paratransit Revenue']


def c_muni_fares():
    n = pd.read_csv(os.path.join(RAW, 'outcomes', 'ntd_sfmta_service_fy.csv')).set_index('report_year')
    rr = n.Fares / n['Operating Expenses']
    r = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), low_memory=False,
                    usecols=['Fiscal Year', 'Department Code', 'Revenue or Spending', 'Object', 'Amount'])
    r = r[(r['Department Code'] == 'MTA') & (r['Revenue or Spending'] == 'Revenue') & r.Object.isin(FARE_OBJ)]
    fares = r.groupby('Fiscal Year').Amount.sum()
    passes = r[r.Object == 'Transit Pass Revenue'].groupby('Fiscal Year').Amount.sum()
    op = dv('MTA', 'actual_oper_all')
    V = {'rr_2015': float(rr[2015]), 'rr_2019': float(rr[2019]), 'rr_2024': float(rr[2024]),
         'ntd_fares_2019': float(n.Fares[2019]), 'ntd_fares_2024': float(n.Fares[2024]),
         'ntd_opex_2019': float(n['Operating Expenses'][2019]), 'ntd_opex_2024': float(n['Operating Expenses'][2024]),
         'trips_2019': float(n['Unlinked Passenger Trips'][2019]), 'trips_2024': float(n['Unlinked Passenger Trips'][2024])}
    V['trips_chg'] = V['trips_2024'] / V['trips_2019'] - 1
    V['fare_per_trip_2019'] = V['ntd_fares_2019'] / V['trips_2019']; V['fare_per_trip_2024'] = V['ntd_fares_2024'] / V['trips_2024']
    for y in (2013, 2019, 2024, 2025, 2026):
        V[f'fares_{y}'] = float(fares[y]); V[f'pass_{y}'] = float(passes[y])
        V[f'lrr_{y}'] = float(fares[y] / op[y])
    V['pass_chg'] = V['pass_2025'] / V['pass_2019'] - 1
    V['fares_real_chg'] = real(fares[2025], 2025) / real(fares[2019], 2019) - 1
    yrs = list(range(2013, 2027))
    CH = {'x': yrs, 'ntd': [100 * float(rr[y]) if y in rr.index else None for y in yrs],
          'ledger': [100 * float(fares[y] / op[y]) for y in yrs]}
    return V, CH


SURVEY_Q = [('muni_rate', 'Muni overall'), ('inf_stcond', 'Street condition'), ('inf_sewer', 'Sewer system'),
            ('inf_water', 'Water system'), ('rec_rate', 'Parks overall'), ('inf_clean', 'Street and sidewalk cleanliness'),
            ('general_rate', 'City government overall'), ('safe_night', 'Feel safe at night'), ('lib_rate', 'Library overall'),
            ('inf_sidecond', 'Sidewalk condition'), ('safe_day', 'Feel safe in the day')]


def c_survey():
    r = pd.read_csv(os.path.join(RAW, 'outcomes', 'city_survey_ratings_by_year.csv'))
    p = r.pivot_table(index='question', columns='survey_year', values='weighted_share_A_or_B')
    V = {}
    for q, _ in SURVEY_Q:
        V[f'{q}_2019'] = float(p.loc[q, 2019]); V[f'{q}_2023'] = float(p.loc[q, 2023]); V[f'{q}_d'] = V[f'{q}_2023'] - V[f'{q}_2019']
    V['n_q'] = len(SURVEY_Q); V['n_down'] = sum(1 for q, _ in SURVEY_Q if V[f'{q}_d'] < 0)
    # robustness from microdata: 2023 phone respondents only (cell + landline), unweighted, and Muni riders only
    m = pd.read_csv(os.path.join(RAW, 'outcomes', 'city_survey_microdata.csv'), low_memory=False,
                    usecols=['year', 'weight', 'mode', 'muni_rate', 'lib_rate', 'muni_user_yes'])

    def ab(df, col, weighted=True):
        v = pd.to_numeric(df[col], errors='coerce'); ok = v.between(1, 5)
        w = pd.to_numeric(df.weight, errors='coerce').fillna(0) if weighted else pd.Series(1.0, index=df.index)
        return float((w[ok] * (v[ok] >= 4)).sum() / w[ok].sum())
    m19, m23 = m[m.year == 2019], m[m.year == 2023]
    ph = m23[m23['mode'].isin(['Cell', 'Landline'])]
    V['muni_phone_2023'] = ab(ph, 'muni_rate'); V['lib_phone_2023'] = ab(ph, 'lib_rate')
    V['muni_unw_2019'] = ab(m19, 'muni_rate', False); V['muni_unw_2023'] = ab(m23, 'muni_rate', False)
    V['lib_unw_2019'] = ab(m19, 'lib_rate', False); V['lib_unw_2023'] = ab(m23, 'lib_rate', False)
    rid = lambda df: df[pd.to_numeric(df.muni_user_yes, errors='coerce') == 1]
    V['muni_riders_2019'] = ab(rid(m19), 'muni_rate'); V['muni_riders_2023'] = ab(rid(m23), 'muni_rate')
    V['lib_real_chg'] = dv('LIB', 'actual_oper_all_real')[2023] / dv('LIB', 'actual_oper_all_real')[2019] - 1
    V['mta_real_chg'] = dv('MTA', 'actual_oper_all_real')[2023] / dv('MTA', 'actual_oper_all_real')[2019] - 1
    CH = {'cats': [lab for _, lab in SURVEY_Q], 'a': [100 * V[f'{q}_2019'] for q, _ in SURVEY_Q], 'b': [100 * V[f'{q}_2023'] for q, _ in SURVEY_Q]}
    return V, CH


def c_library():
    vis = oser('library_visits'); phys = oser('library_physical_circulation'); ebk = oser('library_ebook_circulation')
    sp = dv('LIB', 'actual_oper_all_real')
    circ = phys + ebk
    V = {}
    for y in (2017, 2019, 2025):
        V[f'vis_{y}'] = float(vis[y]); V[f'phys_{y}'] = float(phys[y]); V[f'ebk_{y}'] = float(ebk[y]); V[f'circ_{y}'] = float(circ[y]); V[f'sp_{y}'] = float(sp[y])
        V[f'pv_{y}'] = V[f'sp_{y}'] / V[f'vis_{y}']; V[f'pc_{y}'] = V[f'sp_{y}'] / V[f'circ_{y}']
    V['vis_chg'] = V['vis_2025'] / V['vis_2017'] - 1; V['circ_chg'] = V['circ_2025'] / V['circ_2017'] - 1
    V['ebk_x'] = V['ebk_2025'] / V['ebk_2017']; V['phys_chg'] = V['phys_2025'] / V['phys_2017'] - 1
    V['sp_chg'] = V['sp_2025'] / V['sp_2017'] - 1
    V['pv_chg'] = V['pv_2025'] / V['pv_2017'] - 1; V['pc_chg'] = V['pc_2025'] / V['pc_2017'] - 1
    V['vis_chg_19'] = V['vis_2025'] / V['vis_2019'] - 1; V['circ_chg_19'] = V['circ_2025'] / V['circ_2019'] - 1
    dr = oser('library_expenditure_per_visit_dept_reported')
    V['dept_pv_2017'] = float(dr[2017]); V['dept_pv_2025'] = float(dr[2025])
    yrs = list(range(2017, 2026))
    CH = {'x': yrs, 'visits': [100 * vis[y] / vis[2017] for y in yrs], 'physical': [100 * phys[y] / phys[2017] for y in yrs],
          'ebooks': [100 * ebk[y] / ebk[2017] for y in yrs], 'spend': [100 * sp[y] / sp[2017] for y in yrs]}
    return V, CH


def c_bonds():
    r = pd.DataFrame(json.load(open(os.path.join(SITE, 'analyses', 'go_bond_programs.json')))['rows'])
    r = r[r.spent_share.notna() & (r.years_since_vote >= 3)].copy()
    r['label'] = r.bondprogram + ' (' + r.year.astype(str) + ')'
    r = r.sort_values('spent_share')
    sw = r[r.bondprogram.str.contains('Seawall')].iloc[0]
    es = r[(r.bondprogram.str.startswith('Earthquake')) & (r.year == 2020)].iloc[0]
    # peers measured at a similar age: every program-snapshot (FY22-23 and FY24-25) 4.5-8.5 years after the vote
    pace = pd.read_csv(os.path.join(INT, 'an_go_bond_pace.csv'))
    peers = pace[(pace.years_since_vote >= 4.5) & (pace.years_since_vote <= 8.5) & ~pace.bondprogram.str.contains('Seawall')
                 & ~((pace.bondprogram.str.startswith('Earthquake')) & (pace.year == 2020))]
    V = {'sw_share': float(sw.spent_share), 'sw_exp': float(sw.expended), 'sw_bud': float(sw.revised_budget), 'sw_issued': float(sw.issued),
         'sw_years': float(sw.years_since_vote), 'sw_enc_share': float((sw.expended + sw.encumbered) / sw.revised_budget),
         'sw_of_issued': float(sw.expended / sw.issued),
         'es_share': float(es.spent_share), 'es_bud': float(es.revised_budget), 'es_years': float(es.years_since_vote),
         'es_enc_share': float((es.expended + es.encumbered) / es.revised_budget),
         'peer_n': int(len(peers)), 'peer_min': float(peers.spent_share.min()), 'peer_max': float(peers.spent_share.max()),
         'win_lo': 4.5, 'win_hi': 8.5, 'peer_prog': int(peers[['bondprogram', 'year']].drop_duplicates().shape[0])}
    cr = rt2()['t5_bonds']['city_report']
    V['rep_sw'] = float(cr['seawall_exp_enc_share']); V['rep_es'] = float(cr['eser_exp_enc_share'])
    CH = {'cats': r.label.tolist(), 'values': [100 * float(v) for v in r.spent_share], 'years': [float(v) for v in r.years_since_vote]}
    return V, CH


def c_targets():
    t2 = rt2()['t2_target_easing']
    c = pd.read_csv(os.path.join(INT, 'an_target_changes.csv'))
    t = c[c.fy.between(2013, 2026)]
    mi, hi = t[t.prior_miss], t[t.prior_hit]
    V = {'n_miss': int(len(mi)), 'n_hit': int(len(hi)), 'eased_miss': float(mi.easier.mean()), 'eased_hit': float(hi.easier.mean()),
         'raised_hit': float(hi.harder.mean()), 'raised_miss': float(mi.harder.mean()), 'n_measures': int(t.measure_id.nunique())}
    V['ratio'] = V['eased_miss'] / V['eased_hit']
    V['five'] = 0.05
    V['ratio_excl_mech'] = t2['excl_mechanical_measures']['ratio']
    V['depts'] = t2['per_dept']['depts']; V['depts_more'] = t2['per_dept']['depts_more_easing_after_miss']
    V['lodo_min'] = t2['leave_one_dept_out_ratio']['min']; V['lodo_max'] = t2['leave_one_dept_out_ratio']['max']
    CH = {'cats': ['After a missed target', 'After a met target'], 'eased': [100 * V['eased_miss'], 100 * V['eased_hit']],
          'raised': [100 * V['raised_miss'], 100 * V['raised_hit']]}
    return V, CH


def c_redefined():
    d = pd.read_csv(os.path.join(INT, 'an_drop_test.csv')).set_index('outcome')
    V = {}
    for k in ('dropped', 'redef'):
        r = d.loc[k]
        a = r.rate_after_miss * r.n_missed; b = r.rate_after_met * r.n_met
        se = np.sqrt(1 / a - 1 / r.n_missed + 1 / b - 1 / r.n_met)
        V[f'{k}_miss'] = float(r.rate_after_miss); V[f'{k}_met'] = float(r.rate_after_met); V[f'{k}_rr'] = float(r.risk_ratio)
        V[f'{k}_lo'] = float(np.exp(np.log(r.risk_ratio) - 1.96 * se)); V[f'{k}_hi'] = float(np.exp(np.log(r.risk_ratio) + 1.96 * se))
        V[f'{k}_cmh'] = float(r.cmh_odds_ratio_by_report_year)
        V[f'{k}_n_miss'] = int(round(a)); V[f'{k}_n_met'] = int(round(b))
    V['ci'] = 0.95
    V['extra_redef'] = V['redef_n_miss'] - V['redef_met'] * float(d.loc['redef'].n_missed)
    V['n_missed'] = int(d.loc['dropped'].n_missed); V['n_met'] = int(d.loc['dropped'].n_met)
    by = pd.read_csv(os.path.join(INT, 'an_drop_by_year.csv'), header=[0, 1], index_col=0)
    by = by[by.index.astype(str).str.isdigit()]
    rm, rh = by[('redef_rate', '0.0')].astype(float), by[('redef_rate', '1.0')].astype(float)
    V['redef_years_higher'] = int((rm > rh).sum()); V['redef_years'] = int(len(rm))
    CH = {'cats': ['Dropped from the next report', 'Redefined in the next report'],
          'miss': [100 * V['dropped_miss'], 100 * V['redef_miss']], 'met': [100 * V['dropped_met'], 100 * V['redef_met']]}
    return V, CH


def c_airport():
    c = cube()
    a = c[(c.dept == 'AIR') & c.fy.between(2013, 2026)]
    ds = a[a.char_class == 'debt_service'].groupby('fy').actual.sum()
    pay = a[a.char_class.isin(['salaries', 'benefits'])].groupby('fy').actual.sum()
    tot = a[a.char_class.isin(['salaries', 'benefits', 'non_personnel', 'materials', 'debt_service', 'services_other_depts', 'overhead', 'other', 'grants', 'aid'])].groupby('fy').actual.sum()
    V = {'ds_2013': float(ds[2013]), 'ds_2019': float(ds[2019]), 'ds_2025': float(ds[2025]), 'ds_2026': float(ds[2026]),
         'pay_2013': float(pay[2013]), 'pay_2025': float(pay[2025]), 'pay_2026': float(pay[2026])}
    V['ds_real_x'] = real(ds[2025], 2025) / real(ds[2013], 2013)
    V['ds_pay_x'] = V['ds_2025'] / V['pay_2025']
    V['avg_13_16'] = float(np.mean([real(ds[y], y) for y in range(2013, 2017)])); V['avg_23_26'] = float(np.mean([real(ds[y], y) for y in range(2023, 2027)]))
    V['avg_x'] = V['avg_23_26'] / V['avg_13_16']
    V['share_2013'] = float(ds[2013] / tot[2013]); V['share_2025'] = float(ds[2025] / tot[2025])
    b = slong()
    b = b[(b.measure == 'budget') & (b.dept == 'AIR') & (b.char_class == 'debt_service')].groupby('fy').amount.sum()
    V['bud_2026'] = float(b[2026]); V['bud_2027'] = float(b[2027]); V['bud_2028'] = float(b[2028])
    V['bud_2013'] = float(b[2013]); V['bud_2025'] = float(b[2025]); V['bud_x'] = V['bud_2025'] / V['bud_2013']
    yrs = list(range(2013, 2027))
    CH = {'x': yrs, 'debt': [float(ds[y]) / 1e6 for y in yrs], 'payroll': [float(pay[y]) / 1e6 for y in yrs]}
    return V, CH


EXEC_DEPTS = ['DPH', 'CAT', 'FIR', 'HSA', 'POL', 'SHF', 'REC', 'LIB', 'MTA', 'AIR', 'PRT', 'DBI', 'ADM']
EXEC_NAMES = {'DPH': 'Public Health', 'CAT': 'City Attorney', 'FIR': 'Fire', 'HSA': 'Human Services', 'POL': 'Police', 'SHF': 'Sheriff',
              'REC': 'Recreation & Park', 'LIB': 'Library', 'MTA': 'SFMTA', 'AIR': 'Airport', 'PRT': 'Port', 'DBI': 'Building Inspection',
              'ADM': 'City Administrator'}


def c_execution():
    d = dfy()
    d = d[d.fy.between(2013, 2025) & d.dept.isin(EXEC_DEPTS)].copy()
    d['r'] = d.actual_opfund / d.budget_opfund
    V = {}
    med = {}
    for k in EXEC_DEPTS:
        s = d[d.dept == k].dropna(subset=['r'])
        s = s[s.budget_opfund > 0]
        med[k] = float(s.r.median())
        V[f'{k}_med'] = med[k]; V[f'{k}_n'] = int(len(s)); V[f'{k}_over'] = int((s.r > 1).sum()); V[f'{k}_under95'] = int((s.r < 0.95).sum())
        V[f'{k}_cum'] = float((s.actual_opfund - s.budget_opfund).sum())
    V['cut'] = 0.95; V['five'] = 0.05; V['hundred'] = 1.0
    for k in EXEC_DEPTS:
        s = d[(d.dept == k) & (d.budget_opfund > 0)].dropna(subset=['r'])
        V[f'{k}_over105'] = int((s.r > 1.05).sum())
    s = d[(d.dept == 'DPH') & (d.budget_opfund > 0)]
    V['DPH_cum_pct'] = float((s.actual_opfund - s.budget_opfund).sum() / s.budget_opfund.sum())
    L = slong()
    L = L[(L.dept == 'DPH') & L.fy.between(2013, 2025) & (L.fund_category == 'Operating') & L.char_class.isin(
        ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'capital', 'projects', 'debt_service', 'services_other_depts', 'overhead', 'other'])]
    gg = L.groupby(['gf', 'measure']).amount.sum().unstack()
    V['DPH_gf_over_amt'] = float(gg.loc[True, 'actual'] - gg.loc[True, 'budget'])
    V['DPH_nongf_over_amt'] = float(gg.loc[False, 'actual'] - gg.loc[False, 'budget'])
    gf = d[d.dept == 'DPH'].set_index('fy')
    V['DPH_gf_over'] = int((gf.actual_gf > gf.budget_gf).sum())
    V['DPH_gf_over105'] = int((gf.actual_gf > 1.05 * gf.budget_gf).sum())
    order = sorted(EXEC_DEPTS, key=lambda k: med[k])
    CH = {'cats': [EXEC_NAMES[k] for k in order], 'values': [100 * med[k] for k in order]}
    return V, CH


COMPUTE = {
    'police_staffing': c_police_staffing, 'ot100k': c_ot100k, 'fire': c_fire, 'police_calls': c_police_calls,
    'homeless': c_homeless, 'pension': c_pension, 'grants': c_grants, 'gf': c_gf, 'vacancy': c_vacancy,
    'ot_budget': c_ot_budget, 'muni_fares': c_muni_fares, 'survey': c_survey, 'library': c_library, 'bonds': c_bonds,
    'targets': c_targets, 'redefined': c_redefined, 'airport': c_airport, 'execution': c_execution,
}

if __name__ == '__main__':
    import sys
    keys = sys.argv[1:] or list(COMPUTE)
    for k in keys:
        V, CH = COMPUTE[k]()
        print('==', k)
        for a, b in V.items():
            print(f'  {a}: {b:.4f}' if isinstance(b, float) else f'  {a}: {b}')
        for a, b in CH.items():
            print(f'  CH {a}: {[round(v, 1) if isinstance(v, float) else v for v in b]}')
