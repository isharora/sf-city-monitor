"""Deflate to real FY2026 dollars (Bay Area CPI-U, CUURS49BSA0, FY average) and normalize per resident
(CA DOF E-4 Jan 1 population, the FY midpoint). Also joins workforce and budgeted/actual FTE.

Outputs:
  data/interim/dept_fy.csv   dept x fy: nominal + real spending (budget/actual, all funds/GF/operating/capital),
                             per-resident, workforce, FTE/vacancy.
  data/interim/city_fy.csv   citywide equivalents.
Robustness columns: *_real_us uses national CPI-U (CUUR0000SA0).
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

CTX = os.path.join(RAW, 'context')


def context():
    cpi = pd.read_csv(os.path.join(CTX, 'cpi_fy.csv'))
    cpi = cpi[cpi.bay_complete.astype(str) == 'True'][['fy', 'bay_cpi_fyavg', 'us_cpi_fyavg']]
    base = cpi.set_index('fy').loc[2026]
    cpi['mult_bay'] = base.bay_cpi_fyavg / cpi.bay_cpi_fyavg
    cpi['mult_us'] = base.us_cpi_fyavg / cpi.us_cpi_fyavg
    pop = pd.read_csv(os.path.join(CTX, 'population_fy.csv'))[['fy', 'population_primary', 'pop_census_mid']]
    ctx = pop.merge(cpi[['fy', 'mult_bay', 'mult_us']], on='fy', how='left')
    # FY2027/28 (budget only): no complete CPI; hold at FY2026 prices (multiplier 1.0) and flag.
    ctx['cpi_note'] = np.where(ctx.mult_bay.isna(), 'no complete CPI; nominal = FY2026 prices assumed', '')
    ctx['mult_bay'] = ctx.mult_bay.fillna(1.0)
    ctx['mult_us'] = ctx.mult_us.fillna(1.0)
    return ctx


def main():
    ctx = context()
    ctx.to_csv(os.path.join(INTERIM, 'context_fy.csv'), index=False)
    d = pd.read_csv(os.path.join(INTERIM, 'spend_dept_fy.csv'))
    w = pd.read_csv(os.path.join(INTERIM, 'workforce_dept_fy.csv')).drop(columns=['dept_name'])
    w = w.add_prefix('wf_').rename(columns={'wf_dept': 'dept', 'wf_fy': 'fy'})
    f = pd.read_csv(os.path.join(CTX, 'fte_by_dept_fy.csv'))
    f['dept'] = f.dept_code.map(canon_dept)
    f = f.groupby(['dept', 'fy'])[['budget_fte_gross', 'budget_fte_net', 'actual_fte']].sum(min_count=1).reset_index()
    d = d.merge(w, on=['dept', 'fy'], how='outer').merge(f, on=['dept', 'fy'], how='outer').merge(ctx, on='fy', how='left')
    d['dept_name'] = d.dept.map(DEPT_NAMES).fillna(d.dept)
    # Data-quality masks: FY2018 (financial-system cutover year) actuals contain conversion entries
    # for DPW (+$1.2B operating, +$4.5B all) and PUC (-$3.3B). Mask all actual_* for those dept-years.
    d['dq_flag'] = ''
    for dept, fy in [('DPW', 2018), ('PUC', 2018)]:
        sel = (d.dept == dept) & (d.fy == fy)
        for c in [c for c in d.columns if c.startswith('actual_') and c != 'actual_fte']:
            d.loc[sel, c] = np.nan
        d.loc[sel, 'dq_flag'] = 'FY2018 cutover conversion entries; actuals masked'
    money = [c for c in d.columns if c.startswith(('actual_', 'budget_')) and not c.startswith('budget_fte') and c != 'actual_fte']
    money += [c for c in d.columns if c.startswith('wf_') and c not in ('wf_people_paid', 'wf_permanent_paid', 'wf_hours',
                                                                        'wf_fte_hours', 'wf_ot_share_pay', 'wf_benefit_load')]
    for c in money:
        d[c + '_real'] = d[c] * d.mult_bay
    for c in ['actual_all', 'budget_all', 'actual_gf', 'budget_gf', 'actual_oper_all', 'budget_oper_all']:
        d[c + '_real_us'] = d[c] * d.mult_us
        d[c + '_real_per_res'] = d[c + '_real'] / d.population_primary
    d['vacancy_gross'] = d.budget_fte_gross - d.actual_fte
    d['vacancy_rate_gross'] = d.vacancy_gross / d.budget_fte_gross
    d.sort_values(['dept', 'fy']).to_csv(os.path.join(INTERIM, 'dept_fy.csv'), index=False)

    c = pd.read_csv(os.path.join(INTERIM, 'spend_city_fy.csv')).merge(ctx, on='fy', how='left')
    wc = pd.read_csv(os.path.join(INTERIM, 'workforce_city_fy.csv')).drop(columns=['dept']).add_prefix('wf_').rename(columns={'wf_fy': 'fy'})
    fc = f.groupby('fy')[['budget_fte_gross', 'actual_fte']].sum(min_count=1).reset_index()
    c = c.merge(wc, on='fy', how='left').merge(fc, on='fy', how='left')
    for col in ['budget_all', 'actual_all', 'budget_gf', 'actual_gf']:
        c[col + '_real'] = c[col] * c.mult_bay
        c[col + '_real_us'] = c[col] * c.mult_us
        c[col + '_real_per_res'] = c[col + '_real'] / c.population_primary
        c[col + '_nominal_per_res'] = c[col] / c.population_primary
    c.to_csv(os.path.join(INTERIM, 'city_fy.csv'), index=False)
    show = c[['fy', 'population_primary', 'actual_all', 'actual_all_real', 'actual_all_real_per_res', 'actual_gf_real_per_res', 'budget_all_real_per_res']].copy()
    for k in ['actual_all', 'actual_all_real']:
        show[k] = (show[k] / 1e9).round(2)
    print(show.round(0).to_string())


if __name__ == '__main__':
    main()
