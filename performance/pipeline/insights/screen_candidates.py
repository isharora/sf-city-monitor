"""Screening record for candidate insights that were tested and NOT published (data/redteam/insights_screening.json).

Each entry has the test numbers and the reason for dropping it. Published insights are built by build_insights.py
and verified by verify_insights.py.
"""
import os, json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW, INT = os.path.join(ROOT, 'data', 'raw'), os.path.join(ROOT, 'data', 'interim')
OUT = os.path.join(ROOT, 'data', 'redteam', 'insights_screening.json')


def main():
    ctx = pd.read_csv(os.path.join(INT, 'context_fy.csv')).set_index('fy')
    cpi = pd.read_csv(os.path.join(RAW, 'context', 'cpi_fy.csv')).set_index('fy')
    d = pd.read_csv(os.path.join(INT, 'dept_fy.csv'))
    cube = pd.read_parquet(os.path.join(INT, 'spend_cube.parquet'))
    R = []

    # 1 pay scales vs inflation: fixed basket of jobs (>=20 employees both years), median regular pay of full-year-like staff
    e = pd.read_csv(os.path.join(RAW, 'employee_comp.csv'), low_memory=False, usecols=['Year Type', 'Year', 'Job Code', 'Salaries'])
    e = e[(e['Year Type'] == 'Fiscal') & (e.Salaries > 0)]

    def jm(y):
        s = e[e.Year == y]
        p90 = s.groupby('Job Code').Salaries.transform(lambda x: x.quantile(0.9))
        s = s[s.Salaries >= 0.75 * p90]
        return s.groupby('Job Code').Salaries.median(), e[e.Year == y].groupby('Job Code').size()
    out = {}
    for a, b in ((2013, 2025), (2019, 2025)):
        (ma, na), (mb, nb) = jm(a), jm(b)
        j = pd.DataFrame({'ma': ma, 'mb': mb, 'na': na, 'nb': nb}).dropna()
        j = j[(j.na >= 20) & (j.nb >= 20)]
        r = (j.mb / j.ma).sort_values(); w = j.na.reindex(r.index)
        wmed = float(r[(w.cumsum() / w.sum()) >= 0.5].iloc[0])
        out[f'{a}_{b}'] = {'jobs': int(len(j)), 'weighted_median_pay_growth': wmed, 'bay_cpi_growth': float(cpi.bay_cpi_fyavg[b] / cpi.bay_cpi_fyavg[a])}
    R.append({'candidate': 'Salary growth vs inflation by job family', 'result': out,
              'reason_dropped': 'Typical full-year pay roughly tracked Bay Area inflation (a few points above over FY2013-25); not surprising, and job-code changes (e.g. Police Officer 2/3) make family-level comparisons noisy.'})

    # 2 year-end spikes
    ye = pd.read_csv(os.path.join(INT, 'an_yearend_summary.csv')).set_index('dept')
    yc = pd.read_csv(os.path.join(INT, 'an_yearend_city.csv')).set_index('fy')
    R.append({'candidate': 'Year-end (June) spending spikes by department',
              'result': {'citywide_june_share': {int(k): float(v) for k, v in yc.june_share.items()},
                         'HSA_median_june_to_typical': float(ye.loc['HSA', 'median_june_to_typical']), 'DPH_median_june_to_typical': float(ye.loc['DPH', 'median_june_to_typical'])},
              'reason_dropped': 'Only purchase-order commitment dates are available (no payment dates); June spikes at HSA and DPH coincide with contract renewals that start July 1, so they cannot be read as use-it-or-lose-it spending. Fragile.'})

    # 3 SFMTA real spending: ledger vs NTD disagree
    m = d[d.dept == 'MTA'].set_index('fy').actual_oper_all_real
    ntd = pd.read_csv(os.path.join(RAW, 'outcomes', 'ntd_sfmta_service_fy.csv')).set_index('report_year')['Operating Expenses']
    R.append({'candidate': 'SFMTA real operating spending fell while General Fund departments grew',
              'result': {'ledger_real_change_2019_2024': float(m[2024] / m[2019] - 1),
                         'ntd_real_change_2019_2024': float(ntd[2024] * ctx.mult_bay[2024] / (ntd[2019] * ctx.mult_bay[2019]) - 1)},
              'reason_dropped': 'The city ledger shows a real decline while NTD operating expenses show a real increase; the direction depends on the source (cost allocations, pension accounting), so the claim is fragile.'})

    # 4 work orders
    wo = cube[cube.gf & (cube.char_class == 'services_other_depts')].groupby('fy').actual.sum()
    R.append({'candidate': 'General Fund work orders between departments grew faster than the General Fund',
              'result': {'real_change_2013_2025': float(wo[2025] * ctx.mult_bay[2025] / (wo[2013] * ctx.mult_bay[2013]) - 1)},
              'reason_dropped': 'Growth is spread thinly across many departments and service types (rent, IT, legal); hard to interpret and sensitive to how internal services are charged. Not discussion-worthy enough on its own.'})

    # 5 spending growth vs own measures
    rb = pd.read_csv(os.path.join(INT, 'an_spend_vs_perf_robust.csv'))
    cors = {}
    for v, g in rb.groupby('variant'):
        g = g.dropna(subset=['spend_change', 'perf_index'])
        cors[v] = float(g.spend_change.rank().corr(g.perf_index.rank()))
    R.append({'candidate': 'Departments whose spending grew most did not improve more on their own measures', 'result': {'spearman_by_variant': cors},
              'reason_dropped': 'The null result holds in all variants (rank correlations about 0.07 to 0.23), but measure sets differ in number and kind across departments, so a cross-department comparison says little; left on the Departments view.'})

    # 6 FY2027 position cuts
    f = pd.read_csv(os.path.join(RAW, 'context', 'fte_by_dept_fy.csv'))
    p = f.pivot_table(index='dept_code', columns='fy', values='budget_fte_gross', aggfunc='sum')
    R.append({'candidate': 'The FY2027 budget cuts about 2,700 positions, the first cut in over a decade',
              'result': {'citywide_2025': float(p[2025].sum()), 'citywide_2027': float(p[2027].sum()), 'POL_2026': float(p.loc['POL', 2026]), 'POL_2027': float(p.loc['POL', 2027])},
              'reason_dropped': 'Almost half of the drop is Police (3,211 to 1,942 budgeted FTE), which looks like a data artifact of how sworn positions are loaded for the new budget years; not publishable without confirmation.'})

    # 7 DPH largest absolute grower; 8 DPW decline; 9 MOHCD
    rr = d[d.fy.isin([2013, 2025])].pivot_table(index='dept', columns='fy', values='actual_oper_all_real')
    R.append({'candidate': 'Public Health added the most real dollars; Public Works shrank; the Mayor\'s Office (MOHCD) grew 3.8-fold',
              'result': {'DPH_real_change_$': float(rr.loc['DPH', 2025] - rr.loc['DPH', 2013]), 'DPW_real_change': float(rr.loc['DPW', 2025] / rr.loc['DPW', 2013] - 1),
                         'MYR_real_multiple': float(rr.loc['MYR', 2025] / rr.loc['MYR', 2013])},
              'reason_dropped': 'DPH is the largest department, so its dollar growth is unsurprising; the DPW decline coincides with the FY2018 system cutover and the move of project spending out of operating classes; MOHCD growth is dominated by lumpy housing loans booked as aid. Not robust or not non-obvious.'})

    # 10 pavement
    o = pd.read_csv(os.path.join(INT, 'outcomes_panel.csv'))
    pci = o[o.series == 'pavement_condition_index'].set_index('fy').value
    R.append({'candidate': 'Pavement condition improved from 63 to 75 and held', 'result': {'pci_2009': float(pci[2009]), 'pci_2025': float(pci[2025])},
              'reason_dropped': 'Street resurfacing spending cannot be separated after FY2017, and the published targets equal the results every year (back-filled), so the link to spending cannot be tested.'})

    # 11 311
    c = o[o.series.isin(['311_opened', '311_calls_answered'])].pivot_table(index='fy', columns='series', values='value')
    R.append({'candidate': '311 requests more than doubled while calls fell', 'result': {k: {int(y): float(v) for y, v in c[k].dropna().items() if y in (2015, 2025)} for k in c.columns},
              'reason_dropped': 'Mostly a channel shift to the app and web; the closure-speed series is biased (open cases excluded) and the 311 center cost is not separable after FY2017.'})

    # 12 enterprise vs GF growth
    ent = d[d.dept.isin(['MTA', 'PUC', 'AIR', 'PRT'])].groupby('fy').actual_oper_all_real.sum()
    R.append({'candidate': 'Growth came from tax-supported departments, not the enterprises', 'result': {'enterprise_real_2013': float(ent[2013]), 'enterprise_real_2016': float(ent[2016]), 'enterprise_real_2025': float(ent[2025])},
              'reason_dropped': 'PUC totals swing by hundreds of millions with power purchases booked in the new "Unspecified" category and the FY2018 cutover; the comparison flips with the base year.'})

    json.dump({'as_of': '2026-09-26', 'dropped': R}, open(OUT, 'w'), indent=1, default=float)
    for r in R:
        print('-', r['candidate'])


if __name__ == '__main__':
    main()
