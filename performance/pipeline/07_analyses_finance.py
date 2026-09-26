"""Cross-cutting finance analyses (no outcome data needed):
 A. Budget vs actual: operating-fund execution rate by dept-year (adopted budget vs actual, Operating fund category),
    General Fund execution, overtime budget vs actual; GO bond capital: authorized vs spent, schedule slippage.
 B. Year-end commitments: June share of new purchase-order commitments by dept (FY2018-FY2026).
 C. Overtime vs vacancies: cost of overtime vs estimated cost of filling vacant budgeted positions.
Outputs: data/interim/an_budget_exec.csv, an_ot_budget.csv, an_go_bonds.csv, an_yearend.csv, an_ot_vacancy.csv
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

SP = ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'capital', 'projects', 'debt_service',
      'services_other_depts', 'overhead', 'other']


def budget_exec():
    c = pd.read_parquet(os.path.join(INTERIM, 'spend_cube.parquet'))
    c = c[c.char_class.isin(SP) & c.fy.between(2010, 2026)]
    op = c[c.fund_category == 'Operating']
    out = []
    opcls = c[c.char_class.isin(OPERATING_CLASSES)]  # robustness: operating characters, every fund category
    for scope, df in [('all_funds', op), ('general_fund', op[op.gf]), ('oper_classes_all_categories', opcls)]:
        g = df.groupby(['dept', 'fy'])[['budget', 'actual']].sum().reset_index()
        g['scope'] = scope
        out.append(g)
    g = pd.concat(out)
    g['exec_rate'] = g.actual / g.budget.replace(0, np.nan)
    g['gap'] = g.budget - g.actual
    g.loc[(g.dept.isin(['DPW', 'PUC'])) & (g.fy == 2018), ['actual', 'exec_rate', 'gap']] = np.nan
    g.to_csv(os.path.join(INTERIM, 'an_budget_exec.csv'), index=False)
    # summary: chronic under-execution (median exec rate over FY2013-FY2026, dept operating budget >= $50M)
    s = g[(g.scope == 'all_funds') & g.fy.between(2013, 2026) & (g.budget >= 50e6)].groupby('dept').agg(
        years=('fy', 'nunique'), median_exec=('exec_rate', 'median'), min_exec=('exec_rate', 'min'),
        cum_budget=('budget', 'sum'), cum_actual=('actual', 'sum'), yrs_below_95=('exec_rate', lambda s: (s < 0.95).sum())).reset_index()
    s['cum_unspent'] = s.cum_budget - s.cum_actual
    s['dept_name'] = s.dept.map(DEPT_NAMES)
    rob = g[(g.scope == 'oper_classes_all_categories') & g.fy.between(2013, 2026)].groupby('dept').exec_rate.median()
    gfm = g[(g.scope == 'general_fund') & g.fy.between(2013, 2026)].groupby('dept').exec_rate.median()
    s['median_exec_oper_classes_all_cats'] = s.dept.map(rob)
    s['median_exec_gf'] = s.dept.map(gfm)
    s['caveat'] = np.where(s.dept == 'PUC', 'Actual PUC operating spending is booked largely under Unspecified/project fund categories; operating-category rate is not meaningful', '')
    s.to_csv(os.path.join(INTERIM, 'an_budget_exec_summary.csv'), index=False)
    # overtime: budget vs actual (Object contains 'Overtime', salaries character, all funds)
    l = pd.read_parquet(os.path.join(INTERIM, 'spend_long.parquet'), columns=['fy', 'dept', 'overtime', 'measure', 'amount'])
    ot = l[l.overtime & l.fy.between(2010, 2026)].groupby(['dept', 'fy', 'measure']).amount.sum().unstack().fillna(0).reset_index()
    ot['ot_actual_to_budget'] = ot.actual / ot.budget.replace(0, np.nan)
    ot.to_csv(os.path.join(INTERIM, 'an_ot_budget.csv'), index=False)
    return s, ot


def go_bonds():
    b = pd.read_csv(os.path.join(RAW, 'capital', 'm793-kis4.csv'))
    b.columns = [c.lower() for c in b.columns]
    for c in ['originalenddate', 'projectedenddate', 'actualenddate', 'voter_approved_date']:
        b[c] = pd.to_datetime(b[c], errors='coerce', format='%Y/%m/%d %I:%M:%S %p')
    # Two snapshots (FY22-23, FY24-25). Components were restructured between them (e.g. the Seawall's components were
    # replaced), so mixing snapshots double counts. Use the FY24-25 snapshot for every program present in it; progress
    # between snapshots is measured at program level.
    b['asof_date'] = pd.to_datetime(np.where(b.fiscal_year == 'FY24-25', '2025-06-30', '2023-06-30'))
    prev_prog = b[b.fiscal_year == 'FY22-23'].groupby(['bondprogram', 'year']).expended.sum()
    latest = b.groupby(['bondprogram', 'year']).fiscal_year.transform(lambda s: 'FY24-25' if (s == 'FY24-25').any() else 'FY22-23')
    # pace benchmark: program-level spent share at each snapshot, by years since the vote
    pace = b.groupby(['bondprogram', 'year', 'fiscal_year']).agg(budget=('revisedbudget', 'sum'), expended=('expended', 'sum'),
                                                                 vote=('voter_approved_date', 'min'), snap_date=('asof_date', 'max')).reset_index()
    pace['years_since_vote'] = (pace.snap_date - pace.vote).dt.days / 365.25
    pace['spent_share'] = pace.expended / pace.budget.replace(0, np.nan)
    pace.to_csv(os.path.join(INTERIM, 'an_go_bond_pace.csv'), index=False)
    b = b[b.fiscal_year == latest].copy()
    b['years_since_vote'] = (b.asof_date - b.voter_approved_date).dt.days / 365.25
    asof = pd.Timestamp('2025-06-30')
    end = b.actualenddate.fillna(b.projectedenddate)
    b['slip_years'] = (end - b.originalenddate).dt.days / 365.25
    b['spent_share_of_budget'] = b.expended / b.revisedbudget.replace(0, np.nan)
    b['issued_share_of_auth'] = b.issuedtodate / b.bondauthamount.replace(0, np.nan)
    b.to_csv(os.path.join(INTERIM, 'an_go_bonds_components.csv'), index=False)
    p = b.groupby(['bondprogram', 'year']).agg(components=('component_programitem', 'size'),
                                              authorized=('bondauthamount', 'sum'), revised_budget=('revisedbudget', 'sum'),
                                              issued=('issuedtodate', 'sum'), expended=('expended', 'sum'),
                                              encumbered=('encumbrance', 'sum'), vote=('voter_approved_date', 'min'),
                                              median_slip_years=('slip_years', 'median'),
                                              share_components_late=('slip_years', lambda s: (s > 0.5).mean())).reset_index()
    p['spent_share'] = p.expended / p.revised_budget
    p['expended_fy23_snapshot'] = [prev_prog.get((a, y), np.nan) for a, y in zip(p.bondprogram, p.year)]
    p['spent_fy24_fy25'] = p.expended - p.expended_fy23_snapshot
    p['years_since_vote'] = (asof - p.vote).dt.days / 365.25
    p.to_csv(os.path.join(INTERIM, 'an_go_bonds.csv'), index=False)
    return p


def yearend():
    y = pd.read_csv(os.path.join(RAW, 'yearend', 'po_dept_fy_month.csv'))
    y = y[y.m.notna()]
    y['dept'] = y.purchasing_department.map(canon_dept)
    g = y.groupby(['dept', 'fy', 'm']).amt.sum().unstack('m').fillna(0)
    tot = g.sum(axis=1)
    r = pd.DataFrame({'total': tot, 'june_share': g.get(6.0, 0) / tot, 'may_june_share': (g.get(5.0, 0) + g.get(6.0, 0)) / tot,
                      'july_share': g.get(7.0, 0) / tot, 'mean_other_month_share': g.drop(columns=[6.0, 7.0]).mean(axis=1) / tot}).reset_index()
    r['june_to_typical'] = r.june_share / r.mean_other_month_share
    r.to_csv(os.path.join(INTERIM, 'an_yearend.csv'), index=False)
    city = y.groupby(['fy', 'm']).amt.sum().unstack('m')
    cs = pd.DataFrame({'june_share': city[6.0] / city.sum(axis=1), 'july_share': city[7.0] / city.sum(axis=1),
                       'total': city.sum(axis=1)}).reset_index()
    cs.to_csv(os.path.join(INTERIM, 'an_yearend_city.csv'), index=False)
    s = r[r.total > 20e6].groupby('dept').agg(years=('fy', 'nunique'), median_june_share=('june_share', 'median'),
                                              median_june_to_typical=('june_to_typical', 'median'),
                                              avg_annual_commit=('total', 'mean')).reset_index()
    s = s[s.years >= 6]
    s.to_csv(os.path.join(INTERIM, 'an_yearend_summary.csv'), index=False)
    return cs, s


def ot_vacancy():
    d = pd.read_csv(os.path.join(INTERIM, 'dept_fy.csv'))
    d = d[d.fy.between(2017, 2026)].copy()
    # straight-time cost per filled FTE: (salaries + other salaries + benefits) / actual paid FTE (Spending-FTE dataset)
    d['straight_cost_per_fte'] = (d.wf_salaries + d.wf_other_salaries + d.wf_total_benefits) / d.actual_fte
    d['base_pay_per_fte'] = d.wf_salaries / d.actual_fte
    # vacancies: net budgeted FTE (after attrition savings) minus actual where net exists; else gross
    d['vacant_fte_net'] = d.budget_fte_net - d.actual_fte
    d['vacant_fte_gross'] = d.budget_fte_gross - d.actual_fte
    d['cost_to_fill_net'] = d.vacant_fte_net.clip(lower=0) * d.straight_cost_per_fte
    d['cost_to_fill_gross'] = d.vacant_fte_gross.clip(lower=0) * d.straight_cost_per_fte
    # OT expressed as FTE-equivalents of straight-time labor: OT$/(1.5 * base pay per FTE)
    d['ot_fte_equiv'] = d.wf_overtime / (1.5 * d.base_pay_per_fte)
    # per-hour premium: overtime hour costs 1.5x base; straight-time hour costs base x (1+benefit load),
    # and a new FTE is paid for leave/training too (productive-hours factor ~0.85 assumed, see ANALYSIS.md)
    d['ot_hour_cost_ratio'] = 1.5 / ((1 + d.wf_benefit_load) / 0.85)
    keep = ['dept', 'dept_name', 'fy', 'wf_overtime', 'wf_total_salary', 'wf_ot_share_pay', 'actual_overtime', 'budget_overtime',
            'budget_fte_gross', 'budget_fte_net', 'actual_fte', 'vacant_fte_net', 'vacant_fte_gross', 'straight_cost_per_fte',
            'cost_to_fill_net', 'cost_to_fill_gross', 'ot_fte_equiv', 'wf_benefit_load', 'ot_hour_cost_ratio']
    d[keep].to_csv(os.path.join(INTERIM, 'an_ot_vacancy.csv'), index=False)
    return d[keep]


if __name__ == '__main__':
    s, ot = budget_exec()
    print(s.sort_values('median_exec').head(12).round(3).to_string())
    p = go_bonds()
    print(p.round(2).to_string())
    cs, ys = yearend()
    print(cs.round(3).to_string()); print(ys.sort_values('median_june_share', ascending=False).head(12).round(3).to_string())
    ov = ot_vacancy()
    big = ov[ov.dept.isin(['POL', 'FIR', 'SHF', 'MTA', 'DPH', 'DEM']) & ov.fy.isin([2023, 2024, 2025, 2026])]
    print(big[['dept', 'fy', 'wf_overtime', 'vacant_fte_net', 'vacant_fte_gross', 'cost_to_fill_net', 'cost_to_fill_gross',
               'ot_fte_equiv', 'straight_cost_per_fte', 'ot_hour_cost_ratio']].round(2).to_string())
