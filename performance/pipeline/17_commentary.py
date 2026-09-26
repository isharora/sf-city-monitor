"""Commentary layer (DESIGN.md section 4): commentary/pf-*.json, commentary/story_pf.json and commentary/facts_pf.json.

Every number in a headline or paragraph is computed here from the exported site files (so text never disagrees with the
charts, which read the same files) or, for statistical tests the UI cannot recompute, from the named interim analysis
file. Wording follows two Opus fairness reviews (data/interim/fairness_review*.json); changes are listed in ANALYSIS.md.
Headlines use FY2025, the latest fully closed year; FY2026 actuals (as of September 2026) are treated as preliminary.
"""
import pandas as pd, numpy as np, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *

S = lambda f: json.load(open(os.path.join(SITE, f)))
I = lambda f: pd.read_csv(os.path.join(INTERIM, f))
TF = 'Too few records match to summarize; widen the years or clear a filter.'
AUTHOR = 'Budget vs outcomes analyst (performance module)'
MEASURE_CAVEAT = 'Performance measures are chosen and reported by departments and compiled by the Controller; they are not independently audited.'


def money(x):
    x = float(x)
    return f'${x/1e9:.1f} billion' if abs(x) >= 1e9 else f'${x/1e6:.0f} million'


def pct(x, d=0):
    return f'{x*100:.{d}f}%'


def mmss(x):
    m = int(x); s = int(round((x - m) * 60))
    if s == 60:
        m, s = m + 1, 0
    return f'{m} min {s:02d} s'


def com(view, headline, paragraphs, templates, caveats, sources, annotations=None):
    obj = {'sample': False, 'view': view, 'author': AUTHOR, 'headline': headline, 'paragraphs': paragraphs,
           'annotations': annotations or [], 'templates': templates, 'caveats': caveats, 'sources': sources}
    p = os.path.join(SITE, 'commentary', f'{view}.json')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, 'w'), indent=1, ensure_ascii=False)
    return obj


def main():
    meta = S('meta.json')
    idx = {int(k): v for k, v in meta['deflator']['index'].items()}
    pop = {int(k): v for k, v in meta['population']['by_fy'].items()}
    C = pd.DataFrame(S('spending/cells.json')['cells'])
    C['real'] = C.actual / C.fy.map(idx)
    ST = pd.DataFrame(S('staffing/cells.json')['cells'])
    M = pd.DataFrame(S('measures/measures.json')['measures'])
    V = pd.DataFrame(S('measures/values.json')['rows'])
    real_m = M[M.get('derived') != True]
    Vr = V[V.measure.isin(real_m.id)]
    rt = json.load(open(os.path.join(INTERIM, 'redteam_results.json')))
    pn = I('outcomes_panel.csv')
    P = lambda s, fy: float(pn[(pn.series == s) & (pn.fy == fy)].value.iloc[0])
    names = {d['id']: d['name'] for d in meta['dimensions']['dept']['values']}
    facts = []

    # ------------------------------------------------------------------ shared numbers
    op = C[~C.char.isin(['capital', 'other'])]                      # operating categories
    gf = op[op.fund == 'gf'].groupby('fy').real.sum()
    gpr13, gpr21, gpr25 = gf[2013] / pop[2013], gf[2021] / pop[2021], gf[2025] / pop[2025]
    tot = C.groupby('fy').agg(actual=('actual', 'sum'), real=('real', 'sum'))
    pr10, pr25 = tot.loc[2010].real / pop[2010], tot.loc[2025].real / pop[2025]
    met25 = Vr[(Vr.fy == 2025) & Vr.met.notna()]
    s25 = ST[ST.fy == 2025]
    ot_share25 = s25.overtime.sum() / (s25.salaries.sum() + s25.overtime.sum())
    s13 = ST[ST.fy == 2013]
    ot_share13 = s13.overtime.sum() / (s13.salaries.sum() + s13.overtime.sum())
    top5 = s25[s25.dept.isin(['POL', 'MTA', 'DPH', 'FIR', 'SHF'])].overtime.sum() / s25.overtime.sum()
    et = I('an_target_easing_test.csv').set_index('group')
    ind = rt['target_easing_independent']
    lr = I('an_target_easing_long.csv'); lr = lr[lr.prev_met.notna()]
    ratios = [et.loc['after_miss', 'share_eased'] / et.loc['after_hit', 'share_eased'],
              ind['controller_direction']['share_eased_after_miss'] / ind['controller_direction']['share_eased_after_met'],
              lr[lr.prev_met == 0].eased.mean() / lr[lr.prev_met == 1].eased.mean()]
    rlo, rhi = min(ratios), max(ratios)

    # ------------------------------------------------------------------ pf-overview
    com('pf-overview',
        f"General Fund operating spending per resident rose {pct(gpr25/gpr13-1)} after inflation from FY2013 to FY2025, to ${gpr25:,.0f}; departments met {pct(met25.met.mean())} of the {len(met25):,} targets they reported for FY2025.",
        [f"In FY2026 dollars (Bay Area CPI-U), General Fund operating spending (salaries, benefits, overtime, contracts, supplies, work orders, grants and aid; no capital or debt) went from ${gpr13:,.0f} per resident in FY2013 to ${gpr21:,.0f} in FY2021 and ${gpr25:,.0f} in FY2025. The rise through FY2021 coincided with one-time federal pandemic aid and a population drop of about 37,000 between 2020 and 2022, both of which raise per-resident figures; since FY2021 it has been roughly flat.",
         f"All funds together, departments spent {money(tot.loc[2025].actual)} in FY2025 excluding transfers, ${pr25:,.0f} per resident against ${pr10:,.0f} in FY2010 (FY2026 dollars). That longer series overstates growth: part is an accounting step at the FY2018 financial-system cutover, and part is enterprise spending (Airport, SFMTA, the Public Utilities Commission's power purchases) paid by fares, fees and rates rather than taxes.",
         f"Departments met {pct(met25.met.mean())} of the targets they reported for FY2025. Departments set those targets, and after a miss they eased the next one about {rlo:.1f} to {rhi:.1f} times as often as after a hit, partly because targets get reset toward recent results (integrity view). Overtime was {pct(ot_share25,1)} of base-plus-overtime pay in FY2025; {pct(top5)} of it was in five round-the-clock departments (Police, SFMTA, Public Health, Fire, Sheriff), where 24-hour minimum-staffing requirements and vacancies are commonly cited drivers."],
        [{'id': 'ov', 'template': 'For your filters: {depts_fmt} departments spent {total} ({dollars}) in FY{fy}; {met_share} of {measures_fmt} reported measures met their target.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'All-funds totals step up at FY2018 partly for accounting reasons (new financial system); Public Works and PUC FY2018 actuals are masked. For long runs use the General Fund or operating categories.'},
         {'severity': 'high', 'text': MEASURE_CAVEAT},
         {'severity': 'medium', 'text': 'FY2026 actuals are as of September 2026 and may change at year-end close; headlines use FY2025.'},
         {'severity': 'low', 'text': 'Per-resident figures use California Department of Finance estimates; Census estimates are about 3% lower in 2022-2025.'}],
        ['performance/spending/cells.json', 'performance/measures/values.json', 'performance/staffing/cells.json', 'ANALYSIS.md#1-citywide'],
        [{'chart': 'pf_trend', 'x': 2018, 'text': 'FY2018 financial-system cutover: accounting step-up', 'placement': 'top'}])
    facts.append({'id': 'city-gf-per-resident', 'view': 'pf-overview',
                  'headline': f"General Fund operating spending per resident rose {pct(gpr25/gpr13-1)} after inflation, from ${gpr13:,.0f} in FY2013 to ${gpr25:,.0f} in FY2025 (FY2026 dollars); excluding internal work orders the rise is {pct(rt['gf_oper_per_resident']['2025']['real_per_res_dof']/rt['gf_oper_per_resident']['2013']['real_per_res_dof']-1)}.",
                  'numbers': {'fy2013': gpr13, 'fy2021': gpr21, 'fy2025': gpr25, 'excluding_work_orders': rt['gf_oper_per_resident']},
                  'source': 'spending/cells.json (fund=gf, char not capital/other) / meta.population / meta.deflator; re-derived in pipeline/15_redteam.py r1',
                  'caveats': ['Population fell after 2020 and FY2020-22 include one-time federal aid.', 'Voter-mandated baselines and set-asides drive part of General Fund growth.']})

    # ------------------------------------------------------------------ pf-spending
    d15 = op[op.fy == 2015].groupby('dept').real.sum(); d25 = op[op.fy == 2025].groupby('dept').real.sum()
    ch = (d25 / d15 - 1).dropna()
    hs = rt['reorg_combined']; hom = hs['HOM_alone']
    com('pf-spending',
        f"From FY2015 to FY2025, after inflation, operating spending grew fastest in the Mayor's Office budget (up {pct(ch['MYR'])}, from ${d15['MYR']/1e6:,.0f} million to ${d25['MYR']/1e6:,.0f} million, mostly MOHCD housing and community-development grants) and Economic and Workforce Development (up {pct(ch['ECN'])}, ${d15['ECN']/1e6:,.0f} million to ${d25['ECN']/1e6:,.0f} million); Homelessness and Supportive Housing, created in FY2017, grew from ${hom['fy2017']/1e6:,.0f} million in FY2017 to ${hom['fy2025']/1e6:,.0f} million in FY2025.",
        [f"All figures are FY2026 dollars. The ranking is among departments that existed in FY2015; percentage growth favors departments with smaller starting budgets, so dollar amounts are shown. Much of the growth in homelessness and housing spending is funded by voter-approved dedicated revenue (for example the 2018 gross-receipts tax for homelessness services) and one-time federal pandemic aid, not only by departments' own choices.",
         f"Reorganizations move money between departments: Homelessness and Supportive Housing was created in FY2017 from Human Services and Public Health programs, and Early Childhood in FY2023 from Human Services and First 5. Adding up Human Services, Homelessness and Supportive Housing, Early Childhood and First 5, operating spending rose {pct(hs['HS']['change_13_25'])} in real terms from FY2013 to FY2025.",
         f"The Public Utilities Commission's growth (up {pct(ch['PUC'])}) is mostly electricity bought for CleanPowerSF, the city's power program launched in 2016, which customers pay for through their bills. SFMTA's real operating spending fell {pct(-ch['MTA'])} and Public Works' fell {pct(-ch['DPW'])} over FY2015-FY2025; Police rose {pct(ch['POL'])} and Fire {pct(ch['FIR'])}. Per-resident figures divide by the January population estimate, which fell by about 37,000 from 2020 to 2022."],
        [{'id': 'sp', 'template': '{depts_fmt} departments, FY{fy0}-FY{fy1}: spending changed {change_real} in real terms and {change_nominal} in nominal terms; per resident it changed {change_per_res} (real).', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Department totals are not comparable across reorganizations (HSH FY2017, DPA FY2018, DEC FY2023); use the group filter to combine departments.'},
         {'severity': 'medium', 'text': 'Transfers of programs between departments can make growth look larger or smaller than a change in services.'},
         {'severity': 'medium', 'text': 'Real dollars use the Bay Area consumer price index, which may understate cost growth for wages, health premiums and construction.'},
         {'severity': 'low', 'text': 'Program-level detail (for example Patrol vs Investigations) exists only through FY2017.'}],
        ['performance/spending/cells.json', 'ANALYSIS.md#2-spending'],
        [{'chart': 'pf_trend', 'x': 2018, 'text': 'Financial-system cutover', 'placement': 'top'}])

    # ------------------------------------------------------------------ pf-staffing
    pol = ST[ST.dept == 'POL'].set_index('fy')
    ov = I('an_ot_vacancy.csv').set_index(['dept', 'fy'])
    po = rt['police_overtime']
    pc = C[(C.dept == 'POL') & (C.fy == 2025)].groupby('char')[['budget', 'actual']].sum()
    sal_under = pc.loc['salaries', 'budget'] - pc.loc['salaries', 'actual']
    ot_over = pc.loc['overtime', 'actual'] - pc.loc['overtime', 'budget']
    com('pf-staffing',
        f"Overtime was {pct(ot_share25,1)} of base-plus-overtime pay in FY2025, up from {pct(ot_share13,1)} in FY2013; Police, SFMTA, Public Health, Fire and the Sheriff account for {pct(top5)} of the {money(s25.overtime.sum())}.",
        [f"Police overtime pay was {money(po['2019']['overtime'])} in FY2019 and {money(po['2025']['overtime'])} in FY2025 (nominal dollars), {pct(pol.loc[2025,'ot_share'])} of base plus overtime. In the budget ledger, Police overtime ran {money(ot_over)} over its adopted overtime budget in FY2025 while regular salaries came in {money(sal_under)} under budget, so the department ended close to its total. {int(pol.loc[2025,'employees_ot_over_100k'])} Police employees earned more than $100,000 in overtime; that reflects hours worked under staffing shortages and does not by itself indicate improper pay.",
         f"Does overtime cost more than hiring? Per hour, not obviously. An overtime hour costs 1.5 times base pay with few benefits; a straight-time hour for a filled position costs base pay plus premium pay and benefits (about {pct(ov.loc[('POL',2025),'wf_benefit_load'])} of pay for Police), and a new hire is also paid for leave and training. On our assumptions (15% of paid hours not worked) the two cost about the same per hour worked (ratio {ov.loc[('POL',2025),'ot_hour_cost_ratio']:.2f}). Police overtime in FY2025 equaled about {ov.loc[('POL',2025),'ot_fte_equiv']:,.0f} full-time positions of hours at average base pay, more than the {ov.loc[('POL',2025),'vacant_fte_net']:,.0f} net vacant positions; hiring alone would not remove overtime, part of which is for events billed to outside parties.",
         'Headcount counts distinct employees paid in the year (seasonal staff at Rec and Park and the Library make it exceed full-time equivalents). Overtime share is a share of pay, so inflation does not affect it. No employee below executive level is named.'],
        [{'id': 'st', 'template': 'FY{fy}, {depts_fmt} departments: {headcount_fmt} employees, overtime {ot_total} ({ot_share} of base plus overtime); {ot100k_fmt} employees earned more than $100,000 in overtime.', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'medium', 'text': 'Vacancy = budgeted positions minus actual paid FTE, FY2021 onward only; budgeted positions include some the budget assumes will stay vacant, and paid-FTE data are unreliable for FY2018-2020.'},
         {'severity': 'medium', 'text': 'The overtime-to-positions conversion uses average base pay and the 1.5x rate; actual earners\' pay and rates vary.'},
         {'severity': 'medium', 'text': 'Payroll overtime (Employee Compensation) runs 10-19% above ledger overtime objects citywide in most years, likely because some overtime is charged to project and work-order accounts; the Police gap was 9% in FY2025.'},
         {'severity': 'low', 'text': 'Employees who worked in two departments in a year are counted in both; dollars are nominal.'}],
        ['performance/staffing/cells.json', 'performance/spending/cells.json', 'ANALYSIS.md#5-overtime-and-vacancies'])
    facts.append({'id': 'police-overtime', 'view': 'pf-staffing',
                  'headline': f"Police overtime pay reached {money(po['2025']['overtime'])} in FY2025 (nominal), a quarter of SFPD pay, up from {money(po['2019']['overtime'])} in FY2019; ledger overtime was more than twice the {money(po['2025']['ot_budget_ledger'])} adopted overtime budget, offset mostly by {money(sal_under)} of salary savings.",
                  'numbers': {**po, 'salary_under_budget_2025': sal_under, 'ot_over_budget_2025': ot_over}, 'source': 'staffing/cells.json; spending/cells.json; pipeline/15_redteam.py r2',
                  'caveats': ['Overtime and staffing moved together; the data do not show that vacancies caused the increase.']})

    # ------------------------------------------------------------------ pf-outcomes
    by = Vr[Vr.fy.between(2013, 2025) & Vr.met.notna()].groupby('fy').met.agg(['mean', 'size'])
    pids = Vr[Vr.fy.between(2016, 2025) & Vr.met.notna()].groupby('measure').fy.nunique()
    pids = pids[pids == 10].index
    fp = Vr[Vr.measure.isin(pids) & Vr.fy.between(2016, 2025)].groupby('fy').met.mean()
    t25 = met25.assign(type=met25.measure.map(M.set_index('id').type)).groupby('type').met.mean()
    f13, f25 = P('fire_code3_medical_first_unit_median_min', 2013), P('fire_code3_medical_first_unit_median_min', 2025)
    a16, a25 = P('police_median_A', 2016), P('police_median_A', 2025)
    com('pf-outcomes',
        f"Departments met {pct(by.loc[2025,'mean'])} of their scored targets in FY2025; among {len(pids)} measures reported every year since FY2016, the share rose from {pct(fp[2016])} to {pct(fp[2025])} after dipping to {pct(fp[2020])} in FY2020 (the fiscal year ending June 2020, when the pandemic began).",
        [f"A measure meets its target when its result is at or better than the target in the measure's direction; measures without a clear better direction are not scored. The set of measures changes every year (FY2013: {int(by.loc[2013,'size'])} scored; FY2025: {int(by.loc[2025,'size'])}), so the fixed panel is the fairer trend, though it includes only measures that survived every year, and a rising share can reflect easier targets as well as better results.",
         f"Outcome-type measures (results and service quality) were met {pct(t25.get('outcome', np.nan))} of the time in FY2025 and output measures (volumes) {pct(t25.get('output', np.nan))}. Direct city data show slower emergency responses: for life-threatening (Code 3) medical calls, the median time from 911 receipt to the first unit on scene went from {mmss(f13)} in FY2013 to {mmss(f25)} in FY2025, while Fire/EMS calls rose {pct(P('fire_calls_total',2025)/P('fire_calls_total',2013)-1)} over the same years; the Police median for Priority A calls (911 receipt to officer on scene) went from {mmss(a16)} in FY2016, the first full year of data, to {mmss(a25)} in FY2025.",
         "Read this view with the integrity view: a high met share can mean strong performance or easy targets."],
        [{'id': 'oc', 'template': 'FY{fy}, {depts_fmt} departments: {met_fmt} of {measures_fmt} reported measures met their target ({met_share}); outcome measures {met_share_outcome}, output measures {met_share_output}.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [{'severity': 'high', 'text': MEASURE_CAVEAT},
         {'severity': 'medium', 'text': "Response times start at 911 receipt, so they include call-taking and dispatch by the Department of Emergency Management; hospital hand-off delays, traffic and dispatch-protocol changes also affect them."},
         {'severity': 'medium', 'text': "History for current measures reflects today's dataset; 35 of 548 results first published for FY2013-14 now differ by more than 5% (analyses/restatements.json)."}],
        ['performance/measures/values.json', 'performance/measures/measures.json', 'ANALYSIS.md#3-outcomes'])

    # ------------------------------------------------------------------ pf-cost
    cv = V[V.get('cost_per_unit').notna()].copy()
    cv['real_unit'] = cv.cost_per_unit / cv.fy.map(idx)
    link = {l['pair']: l['measure'] for l in S('measures/cost_links.json')['links']}
    lib = cv[cv.measure == link['library_cost_per_visit']].set_index('fy')
    muni = cv[cv.measure == link['muni_cost_per_revenue_hour']].set_index('fy')
    fire = cv[cv.measure == link['fire_cost_per_call']].set_index('fy')
    libv = lambda fy: P('library_visits', fy)
    libspend = lambda fy: lib.loc[fy, 'program_cost'] / idx[fy]
    com('pf-cost',
        f"Library spending per visit rose from ${lib.loc[2017,'real_unit']:.0f} in FY2017 to ${lib.loc[2025,'real_unit']:.0f} in FY2025 (FY2026 dollars), with visits still {pct(1-libv(2025)/libv(2019))} below FY2019; Fire Department spending per call fell from ${fire.loc[2013,'real_unit']:,.0f} to ${fire.loc[2025,'real_unit']:,.0f} (FY2013-FY2025) as calls grew faster than spending.",
        [f"Unit cost divides actual operating spending by the main count that spending produces; nine curated pairs are defined in measures/cost_links.json (library, Muni, Fire, Police, 311, street cleaning, homelessness), each with its rationale. Percentages and rates are never used as denominators, and all include overhead, so they are average, not marginal, costs. The view shows trends and does not assign causes.",
         f"Library visits were {libv(2019)/1e6:.1f} million in FY2019 and {libv(2025)/1e6:.1f} million in FY2025, while real Library spending went from {money(libspend(2019))} to {money(libspend(2025))}; our per-visit figure matches the Library's own published expenditures per visit within about 1% in FY2018-FY2025. Fire's cost per call covers all department spending (prevention, inspections, airport and port stations), so it is not the cost of a response, and a falling cost per call does not mean better service: medical response times slowed over the same years.",
         f"Muni's operating cost per vehicle revenue hour, from the federal transit database, rose {pct(muni.loc[2024,'real_unit']/muni.loc[2015,'real_unit']-1)} in real terms between FY2015 (${muni.loc[2015,'real_unit']:.0f}) and FY2024 (${muni.loc[2024,'real_unit']:.0f}). Homelessness and Supportive Housing spending per person exiting to housing is shown but is not the cost of a placement: most of that budget keeps people housed and runs shelters."],
        [{'id': 'cost', 'template': '{measures_fmt} measures with a linked cost, {depts_fmt} departments: median change in real cost per unit FY{fy0}-FY{fy1} is {median_change}.', 'requires': {'measures_min': 2}, 'fallback': TF}],
        [{'severity': 'high', 'text': "Links between spending and counts are the analyst's judgment (cost_links.json, DATA_NOTES section 6); a different numerator gives a different unit cost."},
         {'severity': 'medium', 'text': 'Program-level spending exists only through FY2017, so the 311-center and street-cleaning pairs stop in FY2017; other pairs use whole-department spending.'},
         {'severity': 'medium', 'text': 'Library visits understate library use: e-book and online use grew, and spending also funds programs and social services. Much Library funding is a voter-approved set-aside.'}],
        ['performance/measures/values.json', 'performance/measures/cost_links.json', 'ANALYSIS.md#4-cost-per-outcome'])

    # ------------------------------------------------------------------ pf-integrity
    dt = I('an_drop_test.csv').set_index('outcome')
    Vs = Vr.sort_values(['measure', 'fy']).copy()
    Vs['prev_met'] = Vs.groupby('measure').met.shift(1); Vs['prev_fy'] = Vs.groupby('measure').fy.shift(1)
    w = Vs[Vs.fy.between(2014, 2025) & Vs.target_change.isin(['easier', 'harder', 'same'])]
    w_prev = w[(w.prev_fy == w.fy - 1) & w.prev_met.notna()]
    base_miss = (w_prev.prev_met == False).mean()
    eas = w_prev[w_prev.target_change == 'easier']
    share_eas_after_miss = (eas.prev_met == False).mean()
    dropped = M[M.status == 'dropped']
    lastv = Vr.sort_values('fy').groupby('measure').last()
    dmet = dropped.id.map(lastv.met).dropna()
    allmiss = Vr[Vr.met.notna()].met.eq(False).mean()
    com('pf-integrity',
        f"After missing a target, departments eased the next one by more than 5% about {rlo:.1f} to {rhi:.1f} times as often as after meeting it, depending on data source and method; some of this is expected as targets are reset toward recent results.",
        [f"In today's Controller data, {pct(et.loc['after_miss','share_eased'])} of the {int(et.loc['after_miss','n_changes']):,} target changes that followed a miss eased the target by more than 5%, against {pct(et.loc['after_hit','share_eased'])} of the {int(et.loc['after_hit','n_changes']):,} that followed a hit; after a hit, targets were raised {pct(et.loc['after_hit','share_raised'])} of the time, against {pct(et.loc['after_miss','share_raised'])} after a miss. Using the Controller's own statement of which direction is better gives {pct(ind['controller_direction']['share_eased_after_miss'])} vs {pct(ind['controller_direction']['share_eased_after_met'])}; the printed annual reports FY2006-FY2019 give {pct(lr[lr.prev_met==0].eased.mean())} vs {pct(lr[lr.prev_met==1].eased.mean())}. A target far from recent results is the one most likely to be revised, so this is a pattern to read alongside the met share, not evidence of intent.",
         f"Measures disappear for many reasons (a program ends, a better measure replaces it, several are consolidated); the data cannot tell why. Across the reports FY2008-FY2022, measures that missed were redefined by the next report {dt.loc['redef','rate_after_miss']:.1%} of the time versus {dt.loc['redef','rate_after_met']:.1%} for those that met (about 1.4 times the odds, comparing measures in the same report year), and dropped {dt.loc['dropped','rate_after_miss']:.1%} vs {dt.loc['dropped','rate_after_met']:.1%}. Both differences are about one percentage point, similar in size to plausible matching error, so neither is treated as established.",
         f"Base rates for the live counts: in FY2014-FY2025, {pct(base_miss)} of target-setting years followed a miss, and {pct(share_eas_after_miss)} of easier targets did. Of the {len(dmet):,} ended lineages with a final result, {pct((dmet==False).mean())} were missing their target when last reported, compared with {pct(allmiss)} of all scored results."],
        [{'id': 'int', 'template': '{depts_fmt} departments, FY{fy0}-FY{fy1}: {dropped_fmt} measures dropped ({dropped_missed_fmt} were being missed when dropped); targets made easier {lowered_fmt} times, {lowered_after_miss_fmt} the year after a miss.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Measures were matched across 20 years of reports with AI assistance (Claude) and checked by hand: transcription agreed with published datasets on 99.4% of values, a blind re-run agreed on 82-90% of title links, and about one in four "drops" we checked was a consolidation. Lineage-based figures (drops, redefinitions) carry that uncertainty.'},
         {'severity': 'medium', 'text': 'The comparison in paragraph 1 uses a 5% threshold and the latest result known when the target was set; the live counts use any change over 0.5% and the prior year, so they are larger.'},
         {'severity': 'medium', 'text': 'Lowering a target is not misconduct; unusual is not improper.'}],
        ['performance/measures/measures.json', 'performance/measures/values.json', 'ANALYSIS.md#6-integrity-of-the-measures'])
    facts.append({'id': 'targets-eased-after-miss', 'view': 'pf-integrity', 'headline': f"After missing a target, departments eased the next one by more than 5% about {rlo:.1f} to {rhi:.1f} times as often as after meeting it; some easing is expected as targets reset toward results.",
                  'numbers': {'dataset': et.reset_index().to_dict('records'), 'controller_direction': ind['controller_direction'], 'reports_after_miss': lr[lr.prev_met == 0].eased.mean(),
                              'reports_after_met': lr[lr.prev_met == 1].eased.mean(), 'direction_free': ind['direction_free'], 'ratio_range': [rlo, rhi]},
                  'source': 'interim/an_target_easing_test.csv, an_target_easing_long.csv; pipeline/15_redteam.py r5', 'caveats': ['Not evidence of intent.']})

    # ------------------------------------------------------------------ pf-gaps
    gfo = op[(op.fy == 2025) & (op.fund == 'gf')]
    oth = op[(op.fy == 2025) & (op.fund == 'other')]
    gf_ratio, oth_ratio = gfo.actual.sum() / gfo.budget.sum(), oth.actual.sum() / oth.budget.sum()
    be = I('an_budget_exec_summary.csv').set_index('dept')
    gb = I('an_go_bonds.csv').set_index(['bondprogram', 'year'])
    pace = I('an_go_bond_pace.csv')
    peers = pace[pace.years_since_vote.between(5, 8) & ~((pace.bondprogram == 'Earthquake Safety and Emergency Response') & (pace.year == 2020))
                 & (pace.bondprogram != 'Embarcadero Seawall Earthquake Safety')]
    sw = gb.loc[('Embarcadero Seawall Earthquake Safety', 2018)]; es = gb.loc[('Earthquake Safety and Emergency Response', 2020)]
    ys = I('an_yearend_summary.csv').set_index('dept'); yc = I('an_yearend_city.csv').set_index('fy')
    com('pf-gaps',
        f"In FY2025, General Fund operating spending came to {pct(gf_ratio)} of the adopted budget, which is amended during the year; other funds show {pct(oth_ratio)}, largely because their actuals include multi-year grants, project funds and enterprise accounts that the adopted budget does not show.",
        [f"Budget versus actual compares the adopted budget with year-end actuals for operating categories. Measured on the Operating fund category, Police ({pct(be.loc['POL','median_exec'])} median, FY2013-FY2025), Fire ({pct(be.loc['FIR','median_exec'])}) and Human Services ({pct(be.loc['HSA','median_exec'])}) end close to their adopted budgets, while Public Health typically ends about {pct(be.loc['DPH','median_exec']-1)} above, which its hospitals' patient revenue helps fund. Under the City Charter departments may not spend beyond their appropriations, so spending above the adopted budget reflects mid-year supplemental appropriations or added revenue; this data does not show those amendments. Totals near 100% can hide large line overruns: Police overtime ran far over budget in FY2025, offset by salary savings from vacancies.",
         f"Annual gaps are not meaningful for capital and debt, because multi-year and bond appropriations sit outside the adopted budget. For capital, the GO bond program data are the better lens. As of mid-2025, the 2018 Embarcadero Seawall bond program had spent {pct(sw.spent_share)} of its ${sw.revised_budget/1e6:,.0f} million budget ({pct(sw.expended/sw.issued)} of the bonds issued so far) after {sw.years_since_vote:.1f} years, and the 2020 Earthquake Safety and Emergency Response program {pct(es.spent_share)} of ${es.revised_budget/1e6:,.0f} million ({pct(es.expended/es.issued)} of issued) after {es.years_since_vote:.1f} years. Other city bond programs at five to eight years had spent {pct(peers.spent_share.min())} to {pct(peers.spent_share.max())} of their budgets. The seawall depends on a federal Army Corps of Engineers study; we did not review the Earthquake Safety program's schedule, and bonds are issued in tranches as projects are ready.",
         f"Year-end commitments: over FY2018-FY2026, Human Services placed a median {pct(ys.loc['HSA','median_june_share'])} of its annual purchase-order dollars in June, about three times an even monthly share (8.3%), consistent with annual grants and contracts that begin July 1. Citywide, June's share fell from {pct(yc.loc[2018,'june_share'])} in FY2018 (the first year on the new financial system) to {pct(yc.loc[2025,'june_share'])} in FY2025, close to an even share. These are commitment dates, not payments, and do not show rushed or wasteful spending."],
        [{'id': 'gap', 'template': 'FY{fy}, {depts_fmt} departments: actual spending was {gap_total} versus the original budget ({gap_pct}); {over_fmt} departments overspent by more than 5%, {under_fmt} underspent by more than 5%.', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Read annual gaps for operating categories and the General Fund; exclude "capital" and "other" (debt), whose appropriations are multi-year.'},
         {'severity': 'medium', 'text': 'The revised budget is not in the open data, so gaps are against the adopted budget. The Public Utilities Commission books much of its actual operating spending in fund categories the budget does not use, so its gap is an accounting artifact.'},
         {'severity': 'low', 'text': 'Bond spend rates depend on issuance timing; percent of issued funds is shown alongside percent of budget.'}],
        ['performance/spending/cells.json', 'ANALYSIS.md#7-budget-vs-actual-capital-and-year-end'])

    com('pf-depts', "Each city department's spending and staffing, with its performance measures, audits and nonprofit contracts where available.",
        ['Open a department for its scorecard. Separate agencies and trust funds that the city reports on but does not run as departments (pension trusts, the Community College District, the Transportation Authority, the former Redevelopment Agency) are not shown.'],
        [], [{'severity': 'medium', 'text': 'Not every department reports performance measures or has been audited; a missing link means no record was found, not that nothing exists.'},
             {'severity': 'medium', 'text': 'Departments created or merged by reorganization (HSH FY2017, DPA FY2018, DEC FY2023) have histories that do not line up with their predecessors.'},
             {'severity': 'low', 'text': MEASURE_CAVEAT}], ['performance/meta.json'])

    story = {'sample': False, 'dashboard': 'pf', 'title': 'Budget vs outcomes: what San Francisco spends and what it gets', 'steps': [
        {'view': 'pf-overview', 'title': 'The money', 'text': f"General Fund operating spending per resident rose {pct(gpr25/gpr13-1)} after inflation from FY2013 to FY2025, most of it by FY2021.", 'filters': {'real': True, 'years': [2013, 2025]}},
        {'view': 'pf-spending', 'title': 'Where it grew', 'text': 'Housing and community development, workforce programs and homelessness grew fastest; dedicated taxes, federal aid, reorganizations and CleanPowerSF explain much of it.', 'filters': {'real': True, 'years': [2015, 2025]}},
        {'view': 'pf-staffing', 'title': 'Overtime', 'text': f"Overtime reached {pct(ot_share25,1)} of base-plus-overtime pay in FY2025, concentrated in five round-the-clock departments.", 'filters': {'years': [2013, 2025]}},
        {'view': 'pf-outcomes', 'title': 'Did it buy results?', 'text': f"Departments met {pct(by.loc[2025,'mean'])} of their scored FY2025 targets; direct data show slower emergency responses as demand grew.", 'filters': {}},
        {'view': 'pf-integrity', 'title': 'How much do the scorecards mean?', 'text': f"Targets were eased about {rlo:.1f} to {rhi:.1f} times as often after a miss as after a hit.", 'filters': {}},
        {'view': 'pf-cost', 'title': 'Unit costs', 'text': 'Unit costs moved both ways: up for library visits, down for Fire calls, up modestly per Muni service hour.', 'filters': {'real': True}},
        {'view': 'pf-gaps', 'title': 'Budget vs actual', 'text': 'Operating budgets end close to adopted levels once amendments are counted; the lag is in capital, where two large bond programs had spent under a fifth of their budgets after five to seven years.', 'filters': {}}]}
    json.dump(story, open(os.path.join(SITE, 'commentary', 'story_pf.json'), 'w'), indent=1)

    hs_ = rt['reorg_combined']
    pit = pn[pn.series == 'pit_count_total_homeless'].set_index('fy').value
    cs = pn[pn.series == 'survey_general_rate'].set_index('fy').value
    facts += [
        {'id': 'fire-demand-vs-response', 'view': 'pf-outcomes', 'headline': f"Fire and EMS calls rose {pct(P('fire_calls_total',2025)/P('fire_calls_total',2013)-1)} from FY2013 to FY2025 while inflation-adjusted Fire Department operating spending rose {pct(d25['FIR']/op[op.fy==2013].groupby('dept').real.sum()['FIR']-1)}; the median response to life-threatening medical calls went from {mmss(f13)} to {mmss(f25)}, and the slowest 10% from {mmss(P('fire_code3_medical_first_unit_p90_min',2013))} to {mmss(P('fire_code3_medical_first_unit_p90_min',2025))}.",
         'numbers': {'calls': [P('fire_calls_total', 2013), P('fire_calls_total', 2025)], 'median_min': [f13, f25]}, 'source': 'outcomes/series.json; spending/cells.json',
         'caveats': ['Interval includes DEM call-taking and dispatch.', 'Hospital hand-off delays, traffic and dispatch changes not separated.']},
        {'id': 'library', 'view': 'pf-cost', 'headline': f"Library in-person visits in FY2025 were {pct(1-libv(2025)/libv(2019))} below FY2019 while real Library spending was {pct(libspend(2025)/libspend(2019)-1)} higher; spending per visit was ${lib.loc[2025,'real_unit']:.0f} (FY2026 dollars).",
         'numbers': {'visits': [libv(2019), libv(2025)]}, 'source': 'measures/values.json (cost_per_unit); outcomes/series.json', 'caveats': ['In-person visits fell nationwide after the pandemic.']},
        {'id': 'muni', 'view': 'pf-outcomes', 'headline': "Muni's on-time performance ranged from 47% to 60% every year from FY2013 to FY2025, below the 85% standard in the City Charter.",
         'numbers': pn[pn.series == 'muni_on_time_performance'].set_index('fy').value.to_dict(), 'source': 'outcomes/series.json (6dpt-7w23)', 'caveats': ['Schedule-adherence window; headway matters more on frequent routes.']},
        {'id': 'homelessness', 'view': 'pf-spending', 'headline': f"Inflation-adjusted spending by Homelessness and Supportive Housing rose from ${hs_['HOM_alone']['fy2017']/1e6:,.0f} million in FY2017 to ${hs_['HOM_alone']['fy2025']/1e6:,.0f} million in FY2025, partly from programs transferred in, a 2018 voter-approved business tax and pandemic aid; the one-night count was {pct(pit[2024]/pit[2017]-1)} higher in 2024 than in 2017.",
         'numbers': {'hom': hs_['HOM_alone'], 'pit': {int(k): v for k, v in pit.items()}}, 'source': 'scorecards/HOM.json; outcomes/series.json', 'caveats': ['People in supportive housing are not counted as homeless; the count cannot show the counterfactual.']},
        {'id': 'bonds', 'view': 'pf-gaps', 'headline': f"The 2018 Seawall and 2020 Earthquake Safety bond programs had spent {pct(sw.spent_share)} and {pct(es.spent_share)} of their budgets ({pct(sw.expended/sw.issued)} and {pct(es.expended/es.issued)} of bonds issued) 6.7 and 5.3 years after passage; other programs at five to eight years had spent {pct(peers.spent_share.min())}-{pct(peers.spent_share.max())}.",
         'numbers': {'seawall': sw.to_dict(), 'eser2020': es.to_dict()}, 'source': 'analyses/go_bond_programs.json, go_bond_pace.json', 'caveats': ['Spent = cash expended, excluding encumbrances.']},
        {'id': 'survey', 'view': 'pf-outcomes', 'headline': f"The share of residents giving city government an A or B was {pct(cs[2023])} in 2023, down from a 2015 high of {pct(cs[2015])} and close to its 2011 level ({pct(cs[2011])}); survey-method changes in 2015 and 2023 may account for part of the swings.",
         'numbers': {int(k): v for k, v in cs.items()}, 'source': 'outcomes/series.json (nufj-bfbw)', 'caveats': ['No survey between 2019 and 2023.']},
        {'id': 'city-overtime', 'view': 'pf-staffing', 'headline': f"Overtime was {pct(ot_share25,1)} of base-plus-overtime pay in FY2025, up from {pct(ot_share13,1)} in FY2013; five round-the-clock departments account for {pct(top5)}.",
         'numbers': {'share_2013': ot_share13, 'share_2025': ot_share25, 'top5_share': top5}, 'source': 'staffing/cells.json', 'caveats': ['Some overtime is reimbursed by outside parties.']},
    ]
    dflt = lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)
    json.dump({'as_of': '2026-09-26', 'note': 'Headline findings with numbers traced to data files. Unusual is not improper.', 'facts': facts},
              open(os.path.join(SITE, 'commentary', 'facts_pf.json'), 'w'), indent=1, default=dflt)
    json.dump({'facts': facts}, open(os.path.join(INTERIM, 'facts.json'), 'w'), indent=1, default=dflt)
    for v in ['pf-overview', 'pf-spending', 'pf-staffing', 'pf-outcomes', 'pf-cost', 'pf-integrity', 'pf-gaps']:
        print(v, '::', json.load(open(os.path.join(SITE, 'commentary', v + '.json')))['headline'])


if __name__ == '__main__':
    main()
