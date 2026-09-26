"""Screening record for candidate insights that were tested and NOT published (data/insights/insights_screening.json).

Each entry has the test numbers and the reason for dropping or folding it. Published insights are built by
build_insights.py and verified by verify_insights.py.
"""
import os, sys, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
from common import cells, orgs, org_fy, fin, contracts, redteam, DATA, PASS

OUT = os.path.join(DATA, 'insights', 'insights_screening.json')


def f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else (round(float(x), 4) if isinstance(x, (float, np.floating)) else x)


def main():
    R = []
    # 1 nonprofit share of all vendor payments
    t = pd.DataFrame(json.load(open(os.path.join(DATA, 'site', 'aggregates', 'trends.json')))['rows']).set_index('fiscal_year')
    s = t.nonprofit_all / t.all_expenditure
    R.append({'candidate': "Nonprofits' share of all city vendor payments rose from 15% to 21% (FY2016-FY2025)",
              'result': {str(y): f(s[y]) for y in (2007, 2014, 2016, 2019, 2023, 2025, 2026)},
              'decision': 'dropped',
              'reason': 'Not monotonic (19% in FY2007, 12% in FY2014, 23% in FY2023); the denominator swings with construction and capital '
                        'payments and the FY2018 accounting change, so the share says more about other vendors than about nonprofits.'})
    # 2 geography by headquarters ZIP
    al = pd.read_parquet(os.path.join(DATA, 'interim', 'aligned.parquet'), columns=['ein', 'zip', 'filer_zip', 'period_end'])
    z = al.sort_values('period_end').groupby('ein').tail(1).set_index('ein')
    zz = z.filer_zip.fillna(z.zip).astype(str).str[:5]
    c = cells()
    c25 = c[c.fy == 2025].assign(zip=lambda d: d.org.str[4:].map(zz))
    top = (c25.groupby('zip').amt.sum() / c25.amt.sum()).sort_values(ascending=False).head(5)
    R.append({'candidate': 'Geography: where city-funded nonprofits are located', 'result': {k: f(v) for k, v in top.items()},
              'decision': 'dropped',
              'reason': 'Only headquarters addresses are available (Form 990); services are delivered at sites across the city, so a ZIP split '
                        'would describe where offices are, not where money is spent. Service-site data would be needed.'})
    # 3 Schedule I regranting by city-funded organizations
    g = pd.read_csv(os.path.join(DATA, 'interim', 'results', 'schedule_i_by_grantor.csv'), dtype={'ein': str})
    g['yr'] = g.period_end.str[:4].astype(int)
    x = g[(g.yr == 2024) & (g.city_paid_aligned >= 1e6)]
    R.append({'candidate': 'Pass-throughs: city-funded nonprofits regrant money to other city vendors (Form 990 Schedule I)',
              'result': {'grantors_with_city_ge_1m_2024': int(len(x)), 'grants_total': f(x.grants_total.sum()), 'to_city_vendors': f(x.to_city_vendors.sum()),
                         'largest_grantor_dependency': f((x.city_paid_aligned / x.total_revenue).max())},
              'decision': 'folded',
              'reason': 'Schedule I grants by large city recipients are dominated by organizations that get little of their revenue from the city '
                        '(a hospital system, foundations), so the grants cannot be traced to city money. Folded into the pass-through and '
                        'subcontracting insights as context.'})
    # 4 dependency by service area
    ff = fin()
    d = ff[(ff.fy == 2024) & (ff.city >= 1e6) & (ff.total_revenue > 0)]
    R.append({'candidate': 'Dependency by service area', 'result': {k: {'n': int(v.size), 'median': f(v.median())} for k, v in d.groupby('area').dep},
              'decision': 'dropped', 'reason': 'Medians range from 35% to 57% with 11 to 47 organizations per area and no clear ordering; not robust enough to discuss.'})
    # 5 executive pay growth panel
    D = {int(k): v for k, v in json.load(open(os.path.join(DATA, 'site', 'meta.json')))['deflator']['index'].items()}
    ff = ff.assign(rc=ff.exec_comp / ff.fy.map(D), rx=ff.total_expenses / ff.fy.map(D))
    A = ff[(ff.fy == 2016) & (ff.exec_comp > 0) & (ff.city >= 1e6)].set_index('org'); B = ff[(ff.fy == 2024) & (ff.exec_comp > 0)].set_index('org')
    j = A[['rc', 'rx']].join(B[['rc', 'rx']], rsuffix='_b', how='inner')
    R.append({'candidate': 'Executive pay grew faster than organizations', 'result': {'panel_n': int(len(j)), 'median_real_pay_change': f((j.rc_b / j.rc).median() - 1),
                                                                                       'median_real_expense_change': f((j.rx_b / j.rx).median() - 1)},
              'decision': 'dropped', 'reason': 'Opposite of the hypothesis and expected from the size elasticity (about 0.4): top pay grew more slowly than budgets. '
                                               'Small panel (57 organizations with pay reported in both years).'})
    # 6 IRS revocations
    rv = redteam()['paid_after_irs_revocation']['rederived']
    R.append({'candidate': 'Organizations paid after the IRS revoked their tax exemption', 'result': rv, 'decision': 'dropped',
              'reason': 'Five small organizations and $1.6 million over many years (under 0.01% of payments), mostly automatic revocations for '
                        'not filing; shown on organization profiles, not significant enough for the insights page.'})
    # 7 year-end timing
    jj = pd.read_csv(os.path.join(DATA, 'interim', 'results', 'june_july_share.csv'))
    R.append({'candidate': 'June (year-end) payment spikes to nonprofits', 'result': jj[jj.fy.isin([2019, 2025])].round(3).to_dict('records'),
              'decision': 'dropped', 'reason': 'The only date field (data_as_of) records when the source system updated the row, not the payment date; not reliable for timing.'})
    # 8 deficits by dependency
    d24 = fin()[(fin().fy == 2024) & (fin().city >= 1e6) & (fin().total_revenue > 0)]
    R.append({'candidate': 'Highly city-dependent organizations run deficits more often',
              'result': {'hi': f((d24[d24.dep >= 0.75].total_expenses > d24[d24.dep >= 0.75].total_revenue).mean()),
                         'lo': f((d24[d24.dep < 0.75].total_expenses > d24[d24.dep < 0.75].total_revenue).mean())},
              'decision': 'folded', 'reason': 'No difference (about 35% each); reported as the surprise in the reserves insight.'})
    # 9 990-N filers with large payments / stopped filing
    n = pd.read_csv(os.path.join(DATA, 'interim', 'results', '990n_filers_large_payments.csv'))
    s2 = pd.read_csv(os.path.join(DATA, 'interim', 'results', 'stopped_filing.csv'))
    R.append({'candidate': 'Large city payments to organizations that file only the postcard Form 990-N, or stopped filing',
              'result': {'990n_ge_1m': int(len(n)), 'stopped_filing_ge_1m': int(len(s2))}, 'decision': 'dropped',
              'reason': 'Two organizations and none respectively; the IRS filing-requirement code can lag actual filings (one of the two has Form 990 returns on record), and the amounts are small.'})
    # 10 sole-source share by start year
    con = contracts().copy()
    st_ = pd.to_datetime(con.start, errors='coerce'); con['sfy'] = st_.dt.year + (st_.dt.month >= 7).astype(int)
    gu = con[con.authority_class == 'grant_unspecified'].agreed.sum() / con.agreed.sum()
    ss = {int(y): f(g[g.authority_class == 'sole_source_or_not_bid'].agreed.sum() / g.agreed.sum()) for y, g in con[con.sfy.between(2018, 2026)].groupby('sfy')}
    R.append({'candidate': 'Sole-source share of nonprofit contract dollars', 'result': ss, 'decision': 'dropped',
              'reason': f'Small and erratic (one or two large contracts move a year); {gu:.0%} of contract dollars are grants whose authority text does not say whether they were competed.'})
    # 11 HSH spending vs placements (spliced series)
    h = redteam()['hsh_spending_vs_placements']['cite']
    R.append({'candidate': "HSH's real nonprofit spending rose 222% while households housed rose 62% (FY2018-FY2026)",
              'result': {k: f(v) for k, v in h.items() if k.startswith('hsh_')}, 'decision': 'replaced',
              'reason': 'Red team: spliced placement series and HSH start-up base year (fragile). Replaced by the consistent-series comparison '
                        '(FY2023-FY2025) in the outcomes insight and by the Point-in-Time comparison.'})
    # 12 median dependency on all recipients
    dd = redteam()['dependency']['cite']
    R.append({'candidate': 'Most city-funded nonprofits depend on the city', 'result': {'all_orgs_median_2025': f(dd['dep_all_median_2025']), 'large_median_2024': f(dd['dep_median_2024'])},
              'decision': 'reframed', 'reason': 'Across all ~920 organizations with a 990 the median is 7%; only large recipients are typically dependent. '
                                                'Published as the stable-dependency insight for organizations paid at least $1 million.'})
    json.dump({'as_of': '2026-09-26', 'candidates_tested': len(R) + 18, 'published': 18, 'not_published': R}, open(OUT, 'w'), indent=1, default=str)
    for r in R:
        print(f"- [{r['decision']}] {r['candidate']}")


if __name__ == '__main__':
    main()
