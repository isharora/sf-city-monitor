"""Commentary layer, second pass (red team 2): rewrites commentary/pf-*.json, commentary/story_pf.json,
commentary/facts_pf.json and adds a `commentary` block to every scorecards/<DEPT>.json.

Runs after 17_commentary.py and replaces its output. Every number that appears in any text is produced by `num()`,
which formats a value registered in NUM with a machine-readable source (see verify_commentary.py, which re-derives each
source independently and fails on any number in the text that is not traced):
  rt2:<dotted.path>                 data/redteam/redteam2.json (pipeline/15b_redteam2.py)
  rt2dept:<DEPT>:<field>            per-department row of the target-easing test in redteam2.json
  site:<function>:<args...>         recomputed from data/site files (functions re-implemented in verify_commentary.py)
  series:<name>:<fy>                data/site/outcomes/series.json
  interim:<file>:<key col>=<key>:<col>   an analysis table in data/interim
  const:<why>                       a fixed number from a rule or method (e.g. the IRS 85% rule, the 5% threshold)
Writes data/redteam/commentary_trace.json (every formatted number, by output file) for the verifier.
Optional: `--review` sends all text to Claude Opus once for a fairness review (cached; logged to data/llm_usage.jsonl).
"""
import pandas as pd, numpy as np, os, sys, json, glob
sys.path.insert(0, os.path.dirname(__file__))
from common import SITE, INTERIM, ROOT

RT = os.path.join(ROOT, 'data', 'redteam')
S = lambda f: json.load(open(os.path.join(SITE, f)))
R2 = json.load(open(os.path.join(RT, 'redteam2.json')))
TF = 'Too few records match to summarize; widen the fiscal years or clear a department filter.'
AUTHOR = 'SF City Monitor analysis (Budget vs outcomes)'
MEASURE_CAVEAT = {'severity': 'high', 'text': 'Performance measures are chosen, targeted and reported by the departments themselves and compiled by the Controller; they are not independently audited.'}
NUM, TRACE, CUR = {}, {}, ['']

# ------------------------------------------------------------------ formatting and tracing
FMT = {
    'pct': lambda v: f'{v*100:.0f}%', 'pct1': lambda v: f'{v*100:.1f}%', 'spct': lambda v: f'{v*100:+.0f}%'.replace('+', '+'),
    'pts': lambda v: f'{v*100:.0f}', 'usd': lambda v: f'${v:,.0f}', 'usd2': lambda v: f'${v:,.2f}',
    'm': lambda v: f'${v/1e9:,.1f} billion' if abs(v) >= 1e9 else f'${v/1e6:,.0f} million', 'm1': lambda v: f'${v/1e6:,.1f} million', 'b': lambda v: f'${v/1e9:,.1f} billion',
    'int': lambda v: f'{v:,.0f}', 'x1': lambda v: f'{v:.1f}', 'x2': lambda v: f'{v:.2f}', 'yrs': lambda v: f'{v:.1f}',
    'mmss': lambda v: (lambda m, s: f'{m} min {s:02d} s')(*((int(v) + 1, 0) if round((v - int(v)) * 60) == 60 else (int(v), int(round((v - int(v)) * 60))))),
    'mins': lambda v: f'{v:.1f}', 'apct1': lambda v: f'{abs(v)*100:.1f}%', 'apct': lambda v: f'{abs(v)*100:.0f}%', 'mil': lambda v: f'{v/1e6:.1f} million',
}


def reg(key, value, source):
    NUM[key] = {'value': float(value), 'source': source}
    return float(value)


def num(key, kind):
    t = FMT[kind](NUM[key]['value'])
    TRACE.setdefault(CUR[0], []).append({'text': t, 'key': key, 'kind': kind})
    return t


class Tok:
    """A traced number: every time it is formatted into text, the use is recorded for the current output file."""
    def __init__(self, key, kind):
        self.key, self.kind = key, kind

    def __format__(self, spec):
        return num(self.key, self.kind)

    __str__ = lambda self: num(self.key, self.kind)


def rt2(path):
    o = R2
    for p in path.split('.'):
        o = o[p] if not isinstance(o, list) else o[int(p)]
    return o


def R(key, path, kind=None):
    reg(key, rt2(path), f'rt2:{path}')
    return Tok(key, kind) if kind else NUM[key]['value']


def C_(key, value, why, kind):
    reg(key, value, f'const:{why}')
    return Tok(key, kind)


# ------------------------------------------------------------------ site computations (mirrored in verify_commentary.py)
META = S('meta.json')
IDX = {int(k): v for k, v in META['deflator']['index'].items()}
POP = {int(k): v for k, v in META['population']['by_fy'].items()}
CELLS = pd.DataFrame(S('spending/cells.json')['cells'])
CELLS['real'] = CELLS.actual / CELLS.fy.map(IDX)
OPER = CELLS[~CELLS.char.isin(['capital', 'other'])]
ST = pd.DataFrame(S('staffing/cells.json')['cells'])
MS = pd.DataFrame(S('measures/measures.json')['measures'])
VAL = pd.DataFrame(S('measures/values.json')['rows'])
REAL_IDS = set(MS[MS['derived'].astype(object).ne(True)].id) if 'derived' in MS else set(MS.id)
SCORED = VAL[VAL.measure.isin(REAL_IDS) & VAL.met.notna()]
TYPE = MS.set_index('id').type
SER = pd.DataFrame(S('outcomes/series.json')['rows'])
LINKS = {l['pair']: l['measure'] for l in S('measures/cost_links.json')['links']}
NAMES = {d['id']: d['name'] for d in META['dimensions']['dept']['values']}
TOP5 = ['POL', 'MTA', 'DPH', 'FIR', 'SHF']

SITEF = {
    'oper_real': lambda dept, fy: OPER[(OPER.dept == dept) & (OPER.fy == int(fy))].real.sum(),
    'oper_real_change': lambda dept, a, b: OPER[(OPER.dept == dept) & (OPER.fy == int(b))].real.sum() / OPER[(OPER.dept == dept) & (OPER.fy == int(a))].real.sum() - 1,
    'all_nominal': lambda fy: CELLS[CELLS.fy == int(fy)].actual.sum(),
    'all_real_per_res': lambda fy: CELLS[CELLS.fy == int(fy)].real.sum() / POP[int(fy)],
    'fund_oper_ratio': lambda fund, fy: (lambda d: d.actual.sum() / d.budget.sum())(OPER[(OPER.fy == int(fy)) & (OPER.fund == fund)]),
    'met_share': lambda fy: SCORED[SCORED.fy == int(fy)].met.astype(bool).mean(),
    'met_n': lambda fy: len(SCORED[SCORED.fy == int(fy)]),
    'met_share_type': lambda t, fy: (lambda d: d[d.measure.map(TYPE) == t].met.astype(bool).mean())(SCORED[SCORED.fy == int(fy)]),
    'panel_n': lambda a, b: int((SCORED[SCORED.fy.between(int(a), int(b))].groupby('measure').fy.nunique() == int(b) - int(a) + 1).sum()),
    'panel_share': lambda a, b, fy: (lambda ids: SCORED[SCORED.measure.isin(ids) & (SCORED.fy == int(fy))].met.astype(bool).mean())(
        set((lambda g: g[g == int(b) - int(a) + 1].index)(SCORED[SCORED.fy.between(int(a), int(b))].groupby('measure').fy.nunique()))),
    'met_share_dept': lambda dept, fy: (lambda d: d.met.astype(bool).mean())(SCORED[(SCORED.fy == int(fy)) & SCORED.measure.isin(set(MS[MS.dept == dept].id))]),
    'met_count_dept': lambda dept, fy: int(SCORED[(SCORED.fy == int(fy)) & SCORED.measure.isin(set(MS[MS.dept == dept].id))].met.astype(bool).sum()),
    'met_n_dept': lambda dept, fy: len(SCORED[(SCORED.fy == int(fy)) & SCORED.measure.isin(set(MS[MS.dept == dept].id))]),
    'ot_share_city': lambda fy: (lambda d: d.overtime.sum() / (d.salaries.sum() + d.overtime.sum()))(ST[ST.fy == int(fy)]),
    'ot_total_city': lambda fy: ST[ST.fy == int(fy)].overtime.sum(),
    'ot_top5_share': lambda fy: (lambda d: d[d.dept.isin(TOP5)].overtime.sum() / d.overtime.sum())(ST[ST.fy == int(fy)]),
    'ot_share_dept': lambda dept, fy: float(ST[(ST.dept == dept) & (ST.fy == int(fy))].ot_share.iloc[0]),
    'ot_dept': lambda dept, fy: float(ST[(ST.dept == dept) & (ST.fy == int(fy))].overtime.iloc[0]),
    'ot100k_dept': lambda dept, fy: float(ST[(ST.dept == dept) & (ST.fy == int(fy))].employees_ot_over_100k.iloc[0]),
    'cpu_real': lambda pair, fy: (lambda r: float(r.cost_per_unit.iloc[0]) / IDX[int(fy)])(VAL[(VAL.measure == LINKS[pair]) & (VAL.fy == int(fy))]),
    'cpu_real_change': lambda pair, a, b: (SITEF['cpu_real'](pair, b) / SITEF['cpu_real'](pair, a)) - 1,
    'cpu_cost_real': lambda pair, fy: (lambda r: float(r.program_cost.iloc[0]) / IDX[int(fy)])(VAL[(VAL.measure == LINKS[pair]) & (VAL.fy == int(fy))]),
}


def site(key, fn, *args, kind=None):
    reg(key, SITEF[fn](*args), 'site:' + ':'.join([fn] + [str(a) for a in args]))
    return Tok(key, kind) if kind else NUM[key]['value']


def ser(key, name, fy, kind=None):
    v = SER[(SER.series == name) & (SER.fy == fy)].value.iloc[0]
    reg(key, v, f'series:{name}:{fy}')
    return Tok(key, kind) if kind else NUM[key]['value']


def interim(key, file, keycol, keyval, col, kind=None):
    d = pd.read_csv(os.path.join(INTERIM, file))
    v = d[d[keycol].astype(str) == str(keyval)][col].iloc[0]
    reg(key, v, f'interim:{file}:{keycol}={keyval}:{col}')
    return Tok(key, kind) if kind else NUM[key]['value']


def ratio(key, a, b, kind):
    """A derived number: NUM[a] / NUM[b] (or − 1 for kind spct)."""
    v = NUM[a]['value'] / NUM[b]['value'] - (1 if kind in ('spct',) else 0)
    reg(key, v, f'ratio:{a}/{b}' + (':minus1' if kind == 'spct' else ''))
    return Tok(key, kind)


def diff(key, a, b, kind):
    reg(key, NUM[a]['value'] - NUM[b]['value'], f'diff:{a}-{b}')
    return Tok(key, kind)


# ------------------------------------------------------------------ writers
OUTPUTS = {}


def com(view, headline, paragraphs, templates, caveats, sources, annotations=None):
    obj = {'sample': False, 'view': view, 'author': AUTHOR, 'headline': headline, 'paragraphs': paragraphs,
           'annotations': annotations or [], 'templates': templates, 'caveats': caveats, 'sources': sources}
    OUTPUTS[f'commentary/{view}.json'] = obj


def start(name):
    CUR[0] = name


# ================================================================== views
def overview():
    start('commentary/pf-overview.json')
    g13, g21, g25, g26 = (R(f'gf{y}', f't1_gf_per_resident.per_res_real.{y}', 'usd') for y in (2013, 2021, 2025, 2026))
    ch = R('gf_ch', 't1_gf_per_resident.change_13_25', 'pct')
    ch1321 = R('gf_ch1321', 't1_gf_per_resident.change_13_21', 'pct')
    ch2125 = R('gf_ch2125', 't1_gf_per_resident.change_21_25', 'apct1')
    c16, c19 = R('gf_c16', 't1_gf_per_resident.change_16_25', 'pct'), R('gf_c19', 't1_gf_per_resident.change_19_25', 'pct')
    us, wo = R('gf_us', 't1_gf_per_resident.us_cpi_change_13_25', 'pct'), R('gf_wo', 't1_gf_per_resident.excl_work_orders_change_13_25', 'pct')
    ms, mn = site('met25', 'met_share', 2025, kind='pct'), site('metn25', 'met_n', 2025, kind='int')
    e_m, e_h = R('e_m', 't2_target_easing.all.eased_after_miss', 'pct'), R('e_h', 't2_target_easing.all.raised_after_hit', 'pct')
    allb = site('all25', 'all_nominal', 2025, kind='b')
    com('pf-overview',
        f"San Francisco's General Fund operating spending per resident rose {ch} after inflation between FY2013 and FY2025, from {g13} to {g25}; nearly all of the rise came by FY2021, and it has been flat since.",
        [f"The money. In FY2026 dollars, General Fund operating spending (pay, benefits, contracts, grants and aid; no capital or debt) grew {ch1321} from FY2013 to FY2021 and then fell {ch2125} to FY2025; the FY2026 figure is {g26}. How big the rise looks depends on the start year: {c16} from FY2016, {c19} from FY2019. It is {us} with the national rather than the Bay Area price index, and at least {wo} if every internal work order between departments is treated as double counting. Every version is a large real increase, concentrated in the years of pandemic federal aid and a falling population, which pushes per-resident figures up. Across all funds departments spent {allb} in FY2025, but that total mixes in fare-, rate- and fee-funded enterprises (Airport, SFMTA, the utilities) and an accounting step at the FY2018 system change.",
         f"The results. Departments met {ms} of the {mn} targets they scored for FY2025. Read that number carefully: departments set their own targets, and they move them toward recent results in both directions. After a miss, {e_m} of next-year targets were eased; after a hit, {e_h} were raised. A high met share can therefore mean good performance or realistic forecasting; the integrity view shows the pattern. Outcome data not drawn from department scorecards (Fire and Police response times, the City Survey, Muni on-time performance) are on the outcomes view; several of them worsened over the same years.",
         "What this does and does not show. More money per resident did not come with uniformly better measured results, but the data cannot say what results would have been without it: demand grew (Fire and EMS calls, homelessness), voters added dedicated set-asides, and some spending may have replaced services that other governments stopped funding. Unusual is not improper, and nothing here shows misuse of funds."],
        [{'id': 'ov', 'template': 'For your filters: {depts_fmt} departments spent {total} ({dollars}) in FY{fy}. In {met_fy}, the latest year with results, {met_share} of {measures_fmt} scored measures met their own targets.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Department-reported measures are not audited, and departments set their own targets; a met share is not an independent grade.'},
         {'severity': 'high', 'text': 'All-funds totals step up at FY2018 partly for accounting reasons (new financial system); Public Works and PUC FY2018 actuals are masked. For long comparisons use the General Fund operating series.'},
         {'severity': 'medium', 'text': 'The start year matters: FY2013 was early in the post-recession recovery, so growth measured from it is larger than growth from later years.'},
         {'severity': 'medium', 'text': 'FY2026 actuals are as of September 2026 and can change at year-end close; headlines use FY2025. With no filters set, the “For your current filters” sentence describes FY2026.'},
         {'severity': 'low', 'text': 'Per-resident figures use California Department of Finance population estimates; Census estimates are a few percent lower after 2021, which would raise per-resident figures slightly.'}],
        ['performance/spending/cells.json', 'performance/measures/values.json', 'performance/data/redteam/redteam2.json#t1_gf_per_resident', 'performance/data/redteam/redteam2.json#t2_target_easing'],
        [{'chart': 'pf_trend', 'x': 2018, 'text': 'FY2018: new financial system; part of the step is accounting', 'placement': 'top'},
         {'chart': 'pf_trend', 'x': 2021, 'text': 'FY2020 to FY2022: one-time federal pandemic aid', 'placement': 'bottom'}])


def spending():
    start('commentary/pf-spending.json')
    h17, h25 = R('h17', 't6_hsh.hom_real.2017', 'm'), R('h25', 't6_hsh.hom_real.2025', 'm')
    hx = R('hx', 't6_hsh.multiple_17_25', 'x1')
    h18x = R('h18x', 't6_hsh.multiple_18_25', 'x1')
    hs = R('hs', 't6_hsh.human_services_group_change_13_25', 'pct')
    h2526 = R('h2526', 't6_hsh.change_25_26')
    pit17, pit24 = ser('pit17', 'pit_count_total_homeless', 2017, 'int'), ser('pit24', 'pit_count_total_homeless', 2024, 'int')
    out = {d: site(f'ch_{d}', 'oper_real_change', d, 2015, 2025) for d in ['MYR', 'ECN', 'PUC', 'MTA', 'DPW', 'POL', 'FIR', 'DPH']}
    f = lambda d: num(f'ch_{d}', 'pct')
    m15, m25 = site('myr15', 'oper_real', 'MYR', 2015, kind='m'), site('myr25', 'oper_real', 'MYR', 2025, kind='m')
    com('pf-spending',
        f"The fastest operating growth since FY2015 was in housing, homelessness and workforce programs; Homelessness and Supportive Housing alone reached {hx} times its first-year (FY2017) spending in real terms ({h17} to {h25} by FY2025), partly because programs moved in after it was created, while Police grew {num('ch_POL', 'pct')} and Fire {num('ch_FIR', 'pct')}.",
        [f"Where the money went. From FY2015 to FY2025, after inflation, operating spending grew {f('MYR')} in the Mayor's Office budget ({m15} to {m25}, mostly housing and community-development grants run by MOHCD), {f('ECN')} in Economic and Workforce Development and {f('DPH')} at Public Health. Police rose {f('POL')} and Fire {f('FIR')}. SFMTA fell {num('ch_MTA', 'apct')} and Public Works {num('ch_DPW', 'apct')}, although both also run large capital programs that this operating view leaves out.",
         f"Homelessness, fairly measured. Part of the department's growth is programs moving in after it was created: measured from FY2018, its second year, the multiple is {h18x} rather than {num('hx', 'x1')}. Combining it with the departments it came out of (Human Services, Early Childhood and First 5), human-services spending rose {hs} from FY2013 to FY2025. Much of the new money came from a 2018 voter-approved business tax dedicated to homelessness and from one-time pandemic aid, and HSH's spending dipped {num('h2526', 'apct')} in FY2026. The one-night count was {pit17} people in 2017 and {pit24} in 2024; the count cannot show how many more people would be homeless without the housing the money pays for.",
         f"How to read growth. Percentages flatter small starting budgets, so check dollars. Reorganizations move money between departments without changing services, and the Public Utilities Commission's growth ({f('PUC')}) is mostly electricity bought for CleanPowerSF customers, paid through their bills."],
        [{'id': 'sp', 'template': 'For your filters ({depts_fmt} departments, FY{fy0} to FY{fy1}): spending changed {change_real} after inflation and {change_nominal} in nominal dollars; per resident it changed {change_per_res} after inflation.', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Department totals are not comparable across reorganizations (Homelessness and Supportive Housing FY2017, Police Accountability FY2018, Early Childhood FY2023); select the whole department group to compare like with like.'},
         {'severity': 'medium', 'text': 'Much of the growth in homelessness, housing and children’s spending is funded by voter-approved dedicated taxes and set-asides, so it reflects ballot decisions as well as department choices.'},
         {'severity': 'medium', 'text': 'Real dollars use the Bay Area consumer price index, which may understate cost growth for wages, health premiums and construction.'},
         {'severity': 'low', 'text': 'Program-level detail (for example Patrol vs Investigations) exists only through FY2017.'}],
        ['performance/spending/cells.json', 'performance/data/redteam/redteam2.json#t6_hsh', 'performance/outcomes/series.json'],
        [{'chart': 'pf_trend', 'x': 2018, 'text': 'FY2018: financial-system cutover', 'placement': 'top'}])


def staffing():
    start('commentary/pf-staffing.json')
    s13, s25 = site('ots13', 'ot_share_city', 2013, kind='pct1'), site('ots25', 'ot_share_city', 2025, kind='pct1')
    tot = site('ott25', 'ot_total_city', 2025, kind='m')
    top5 = site('top5', 'ot_top5_share', 2025, kind='pct')
    pay = site('polot25', 'ot_dept', 'POL', 2025, kind='m')
    psh = site('polsh25', 'ot_share_dept', 'POL', 2025, kind='pct')
    led, bud = R('led', 't4_police_overtime.2025.ledger_ot', 'm'), R('bud', 't4_police_overtime.2025.budget_ot', 'm')
    mult = R('mult', 't4_police_overtime.2025.ratio_total', 'x1')
    f10 = R('f10', 't4_police_overtime.2025.fund_10b_actual', 'm1')
    f10b = R('f10b', 't4_police_overtime.2025.fund_10b_budget', 'm1')
    rev = R('rev', 't4_police_overtime.2025.public_safety_service_charges_revenue', 'm1')
    air = R('air', 't4_police_overtime.2025.airport_fund_actual', 'm1')
    gfr = R('gfr', 't4_police_overtime.2025.ratio_gf_own', 'x1')
    gfr19 = R('gfr19', 't4_police_overtime.2019.ratio_gf_own', 'x2')
    gap = R('pgap', 't4_police_overtime.payroll_vs_ledger_2025', 'pct')
    lo, hi = R('phlo', 't4_police_overtime.per_hour_range.0', 'x2'), R('phhi', 't4_police_overtime.per_hour_range.1', 'x2')
    k100 = site('pol100k', 'ot100k_dept', 'POL', 2025, kind='int')
    com('pf-staffing',
        f"Overtime rose from {s13} to {s25} of base-plus-overtime pay between FY2013 and FY2025; five round-the-clock departments (Police, SFMTA, Public Health, Fire and the Sheriff) account for {top5} of the {tot} (nominal).",
        [f"Police is the sharpest case. Payroll records show {pay} of Police overtime in FY2025, {psh} of the department's base-plus-overtime pay. The budget ledger books {led}, {mult} times the {bud} overtime budget adopted for the year. Some of that is not a General Fund cost. {f10} ran through the fund for officers hired by event sponsors and other outside parties under Section 10B of the Administrative Code; that work is billed to the outside party (public-safety service charges brought in {rev} in FY2025), so spending above the fund's {f10b} budget is largely covered. Another {air} was paid by the Airport. Even without those, overtime paid from the department's own General Fund accounts was {gfr} times the General Fund overtime budget, compared with {gfr19} times in FY2019. The overrun was largely offset by salary savings from unfilled positions, so the department finished near its total budget.",
         f"Is overtime cheaper than hiring? It depends on assumptions. An overtime hour costs time and a half with almost no benefits; a straight-time hour carries benefits and paid leave. On reasonable assumptions about leave, training time and premium pay, an overtime hour costs {lo} to {hi} times a straight-time hour, so the data do not settle the question, and neither side counts academy costs or the fatigue of long shifts. {k100} Police employees earned more than {C_('k100k', 100000, 'staffing export threshold employees_ot_over_100k', 'usd')} in overtime; that reflects hours worked under staffing shortages and minimum-staffing rules and does not by itself indicate improper pay.",
         f"Two ledgers. Payroll overtime ran {gap} above ledger overtime for Police in FY2025 (more in some other departments), because some overtime is charged to project, work-order or premium-pay accounts. This view uses payroll; budget-versus-actual comparisons use the ledger. Headcount counts distinct people paid in the year, so seasonal and part-time staff push it above full-time equivalents, and no employee below executive level is named."],
        [{'id': 'st', 'template': f'For your filters (FY{{fy}}, {{depts_fmt}} departments): {{headcount_fmt}} people were paid; overtime was {{ot_total}}, {{ot_share}} of base-plus-overtime pay, and {{ot100k_fmt}} employees earned more than {num("k100k", "usd")} in overtime.', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Overtime for events billed to outside parties (Section 10B) and for Airport and other work orders is paid by someone other than the General Fund; overtime totals include it.'},
         {'severity': 'medium', 'text': 'Payroll overtime (Employee Compensation) usually runs above ledger overtime (Spending and Revenue) citywide; the two are not interchangeable.'},
         {'severity': 'medium', 'text': 'Vacancies are budgeted positions minus paid full-time equivalents, FY2021 onward only; the data show overtime and vacancies moving together, not that one caused the other.'},
         {'severity': 'low', 'text': 'Employees who worked in two departments in a year are counted in both; dollars follow the Dollars switch.'}],
        ['performance/staffing/cells.json', 'performance/data/redteam/redteam2.json#t4_police_overtime'],
        [{'chart': 'pf_ot', 'x': 2021, 'text': 'From FY2021, public-protection overtime climbs', 'placement': 'top'}])


def outcomes():
    start('commentary/pf-outcomes.json')
    ms, mn = site('met25', 'met_share', 2025, kind='pct'), site('metn25', 'met_n', 2025, kind='int')
    pn = site('paneln', 'panel_n', 2016, 2025, kind='int')
    p16, p20, p25 = (site(f'p{y}', 'panel_share', 2016, 2025, y, kind='pct') for y in (2016, 2020, 2025))
    to, tu = site('mto', 'met_share_type', 'outcome', 2025, kind='pct'), site('mtu', 'met_share_type', 'output', 2025, kind='pct')
    f13, f25 = ser('f13', 'fire_code3_medical_first_unit_median_min', 2013, 'mmss'), ser('f25', 'fire_code3_medical_first_unit_median_min', 2025, 'mmss')
    calls = R('fcalls', 't3_fire.calls_change_13_25', 'pct')
    fsp = R('fsp', 't3_fire.real_oper_spend_change_13_25', 'pct')
    d13, d25 = R('d13', 't3_fire.by_fy.2013.final.dispatch_to_arrival_median', 'mmss'), R('d25', 't3_fire.by_fy.2025.final.dispatch_to_arrival_median', 'mmss')
    bef, aft = R('bef', 't3_fire.slowdown_before_dispatch_min', 'mins'), R('aft', 't3_fire.slowdown_after_dispatch_min', 'mins')
    w13, w25 = R('w13', 't3_fire.by_fy.2013.final.dispatch_to_arrival_within_4m30', 'pct'), R('w25', 't3_fire.by_fy.2025.final.dispatch_to_arrival_within_4m30', 'pct')
    c3a, c3b = R('c3a', 't3_fire.by_fy.2013.share_medical_code3_final', 'pct'), R('c3b', 't3_fire.by_fy.2025.share_medical_code3_final', 'pct')
    o13, o25 = R('o13', 't3_fire.by_fy.2013.original.call_to_arrival_median', 'mmss'), R('o25', 't3_fire.by_fy.2025.original.call_to_arrival_median', 'mmss')
    a16, a25 = ser('a16', 'police_median_A', 2016, 'mmss'), ser('a25', 'police_median_A', 2025, 'mmss')
    s15, s23, s11 = (R(f'sv{y}', f't7_survey.by_year.{y}.weighted_ab', 'pct') for y in (2015, 2023, 2011))
    mu = ser('mu25', 'muni_on_time_performance', 2025, 'pct')
    k85 = C_('k85', 0.85, 'City Charter section 8A.103 Muni on-time standard', 'pct')
    com('pf-outcomes',
        f"Outside the departments' own scorecards, emergency response slowed: the median time from a 911 call to the first unit at a life-threatening medical call rose from {f13} (FY2013) to {f25} (FY2025) as calls grew {calls} and real Fire spending {fsp}; part of the delay is in 911 dispatch.",
        [f"The emergency-response slowdown is robust. Measured from dispatch instead of from the call, the first unit's median arrival went from {d13} to {d25}; of the total slowdown, about {aft} minutes came after dispatch (turnout and travel) and {bef} before it (call-taking and dispatch at the Department of Emergency Management). The share of first units arriving within {C_('k430', 4.5, 'Controller scorecard standard for first responders to life-threatening calls', 'mmss')} of dispatch fell from {w13} to {w25}. Classification did not drive it: life-threatening calls were {c3a} of medical calls in FY2013 and {c3b} in FY2025, and using the priority assigned when the call came in gives the same trend ({o13} to {o25}). Police Priority A calls, measured from 911 receipt to an officer on scene, went from {a16} in FY2016, the first full year of data, to {a25}. None of this isolates the cause; traffic, hospital hand-off delays and staffing may all play a part.",
         f"The departments' own scorecards look better. They met {ms} of {mn} scored targets in FY2025. Among {pn} measures scored every year since FY2016, the met share was {p16} in FY2016, dipped to {p20} in FY2020 and was {p25} in FY2025. Outcome measures (results and service quality) were met {to} of the time and output measures (volumes) {tu}. Because targets are reset toward recent results, a steady met share is compatible with worsening results.",
         f"What residents say. The share giving city government an A or B in the City Survey was {s23} in 2023, down from {s15} in 2015 and close to its 2011 level of {s11}. Both the 2015 peak and the 2023 low coincide with changes in how the survey was conducted, so part of the swing may be method. Muni's on-time performance was {mu} in FY2025, below the {k85} standard in the City Charter, as it has been every year in the data."],
        [{'id': 'oc', 'template': 'For your filters ({depts_fmt} departments, latest year with results in FY{fy0} to FY{fy1}): {met_fmt} of {measures_fmt} scored measures met their target ({met_share}); outcome measures {met_share_outcome}, output measures {met_share_output}.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [MEASURE_CAVEAT,
         {'severity': 'medium', 'text': 'Response times start at 911 receipt, so they include call-taking and dispatch by the Department of Emergency Management, not only the Fire Department; hospital hand-off delays, traffic and dispatch-protocol changes also affect them.'},
         {'severity': 'medium', 'text': 'The City Survey changed from mail to phone in 2015 and added online and in-person responses in 2023, and there was no 2021 survey; compare years with care.'},
         {'severity': 'medium', 'text': 'History for current measures reflects today’s dataset, and some older results have since been restated (analyses/restatements.json).'}],
        ['performance/measures/values.json', 'performance/outcomes/series.json', 'performance/data/redteam/redteam2.json#t3_fire', 'performance/data/redteam/redteam2.json#t7_survey'])


def cost():
    start('commentary/pf-cost.json')
    l17, l25 = site('l17', 'cpu_real', 'library_cost_per_visit', 2017, kind='usd'), site('l25', 'cpu_real', 'library_cost_per_visit', 2025, kind='usd')
    v19, v25 = ser('v19', 'library_visits', 2019), ser('v25', 'library_visits', 2025)
    ratio('vdrop', 'v25', 'v19', 'spct')
    ls19, ls25 = site('ls19', 'cpu_cost_real', 'library_cost_per_visit', 2019), site('ls25', 'cpu_cost_real', 'library_cost_per_visit', 2025)
    fi13, fi25 = site('fi13', 'cpu_real', 'fire_cost_per_call', 2013, kind='usd'), site('fi25', 'cpu_real', 'fire_cost_per_call', 2025, kind='usd')
    mu15, mu24 = site('mu15', 'cpu_real', 'muni_cost_per_revenue_hour', 2015, kind='usd'), site('mu24', 'cpu_real', 'muni_cost_per_revenue_hour', 2024, kind='usd')
    mch = site('much', 'cpu_real_change', 'muni_cost_per_revenue_hour', 2015, 2024, kind='pct')
    npairs = C_('npairs', len(LINKS), 'number of curated pairs in measures/cost_links.json', 'int')
    com('pf-cost',
        f"Unit costs moved in both directions: Library spending per in-person visit rose from {l17} in FY2017 to {l25} in FY2025 (FY2026 dollars) as visits stayed {num('vdrop', 'apct')} below FY2019, while Fire Department spending per call fell from {fi13} to {fi25} over FY2013 to FY2025 because calls grew faster than the budget.",
        [f"What a unit cost is here. Each of the {npairs} curated pairs divides a department's actual operating spending by the main count that spending produces, and each has a written rationale (cost_links.json). They include overhead and everything else the department does, so they are average, not marginal, costs, and a falling cost is not automatically good news.",
         f"Three readings. The Library's per-visit cost rose mostly because visits fell ({ser('v19', 'library_visits', 2019, 'mil')} in FY2019, {ser('v25', 'library_visits', 2025, 'mil')} in FY2025) while real spending went from {num('ls19', 'm')} to {num('ls25', 'm')}; e-books, online use and social-service programs are not in the denominator, and our figure matches the Library's own published cost per visit. Fire's cost per call fell because demand outran spending; over the same years the outcomes view shows slower medical response, and the data do not isolate the cause. Muni's operating cost per vehicle revenue hour, from the federal transit database, rose {mch} in real terms from FY2015 ({mu15}) to FY2024 ({mu24}).",
         "What is not here. Spending per person leaving homelessness for housing is shown but is not the cost of a placement, since most of that budget keeps people housed and runs shelters. Program-level spending exists only through FY2017, so the 311 and street-cleaning pairs stop there."],
        [{'id': 'cost', 'template': 'For your filters ({depts_fmt} departments, FY{fy0} to FY{fy1}): across {measures_fmt} measures with a linked cost, the median change in real cost per unit was {median_change}.', 'requires': {'measures_min': 2}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'The links between spending and counts are the analyst’s judgment (cost_links.json); a different numerator or denominator gives a different unit cost.'},
         {'severity': 'medium', 'text': 'Whole-department spending includes work unrelated to the count (Fire prevention and inspections, Library programs), so unit costs are indicators, not prices.'},
         {'severity': 'medium', 'text': 'Library visits understate library use; much Library funding is a voter-approved set-aside.'}],
        ['performance/measures/values.json', 'performance/measures/cost_links.json', 'performance/outcomes/series.json'])


def integrity():
    start('commentary/pf-integrity.json')
    T = 't2_target_easing'
    em, eh, rh = R('i_em', f'{T}.all.eased_after_miss', 'pct1'), R('i_eh', f'{T}.all.eased_after_hit', 'pct1'), R('i_rh', f'{T}.all.raised_after_hit', 'pct1')
    nm, nh = R('i_nm', f'{T}.all.n_after_miss', 'int'), R('i_nh', f'{T}.all.n_after_hit', 'int')
    rx = R('i_rx', f'{T}.all.ratio', 'x1')
    rmech = R('i_rmech', f'{T}.excl_mechanical_measures.ratio', 'x1')
    nmech = R('i_nmech', f'{T}.n_mechanical_measures', 'int')
    rany = R('i_rany', f'{T}.excl_any_reset_measures.ratio', 'x1')
    nd, nmore = R('i_nd', f'{T}.per_dept.depts', 'int'), R('i_nmore', f'{T}.per_dept.depts_more_easing_after_miss', 'int')
    mh = R('i_mh', f'{T}.per_dept.mh_odds_ratio_by_dept', 'x1')
    lo, hi = R('i_lo', f'{T}.leave_one_dept_out_ratio.min', 'x1'), R('i_hi', f'{T}.leave_one_dept_out_ratio.max', 'x1')
    fire = R('i_fire', f'{T}.fire_dept.eased_after_miss', 'pct')
    k5 = C_('k5', 0.05, 'threshold: a target is eased or raised when it moves more than 5% in the measure direction', 'pct')
    r_m, r_h = (interim(f'dr_{k}', 'an_drop_test.csv', 'outcome', 'redef', c, 'pct1') for k, c in (('m', 'rate_after_miss'), ('h', 'rate_after_met')))
    d_m, d_h = (interim(f'dd_{k}', 'an_drop_test.csv', 'outcome', 'dropped', c, 'pct1') for k, c in (('m', 'rate_after_miss'), ('h', 'rate_after_met')))
    com('pf-integrity',
        f"After missing a target, departments eased the next one about {rx} times as often as after meeting it ({em} vs {eh}); but after meeting one they raised it about as often ({rh}), so the pattern mostly reflects targets that track results, not one-sided easing.",
        [f"The test. We looked at {nm} year-to-year target changes that followed a miss and {nh} that followed a hit, counting a change when the target moved more than {k5} in the measure's direction. The asymmetry is real and survives every check we ran: it holds when we drop the {nmech} measures whose targets are routinely reset to the latest result ({rmech} times), when we drop every measure ever reset that way ({rany} times), in {nmore} of the {nd} departments with enough changes to test, after adjusting for department (odds ratio {mh}), and whichever single department is left out ({lo} to {hi} times).",
         f"What it means. A target that works as a forecast will be lowered after a bad year and raised after a good one, and that is mostly what we see: easing after a miss and raising after a hit happen at almost the same rate. That is defensible budgeting, but it drains meaning from the headline met share, because the bar moves with performance. Departments differ: Fire, for example, eased only {fire} of targets after a miss even as its response times slipped. Nothing here is evidence of intent.",
         f"Dropped and redefined measures. Across the annual reports, measures that were missing their target were redefined by the next report {r_m} of the time, against {r_h} for those meeting it, and dropped {d_m} against {d_h}. Both gaps are about one percentage point, within plausible matching error, so neither is treated as established."],
        [{'id': 'int', 'template': 'For your filters ({depts_fmt} departments, FY{fy0} to FY{fy1}): {dropped_fmt} measures were dropped ({dropped_missed_fmt} of them were being missed when dropped), and targets were made easier {lowered_fmt} times, {lowered_after_miss_fmt} of them the year after a miss.', 'requires': {'measures_min': 3}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Measures were matched across two decades of reports with AI assistance (Claude) and checked against published datasets and by hand; lineage-based counts (drops, redefinitions) carry that matching uncertainty.'},
         {'severity': 'medium', 'text': f"The live counts use any target change over {C_('k05', 0.005, 'export threshold for target_change', 'pct1')} and the prior year; the finding above uses a {num('k5', 'pct')} threshold and the latest result known when the target was set, so the live counts are larger."},
         {'severity': 'medium', 'text': 'Lowering a target after a miss is often sound forecasting; unusual is not improper.'}],
        ['performance/measures/values.json', 'performance/data/redteam/redteam2.json#t2_target_easing', 'performance/data/interim/an_drop_test.csv'])


def gaps():
    start('commentary/pf-gaps.json')
    gfr, otr = site('gfr25', 'fund_oper_ratio', 'gf', 2025, kind='pct'), site('otr25', 'fund_oper_ratio', 'other', 2025, kind='pct')
    B = 't5_bonds.ours'
    sw, sb, sy = R('sw', f'{B}.seawall.spent_share', 'pct'), R('sb', f'{B}.seawall.budget', 'm'), R('sy', f'{B}.seawall.years', 'yrs')
    swe = R('swe', f'{B}.seawall.exp_enc_share', 'pct')
    swi = R('swi', f'{B}.seawall.spent_of_issued', 'pct')
    es, eb, ey = R('es', f'{B}.eser2020.spent_share', 'pct'), R('eb', f'{B}.eser2020.budget', 'm1'), R('ey', f'{B}.eser2020.years', 'yrs')
    ese = R('ese', f'{B}.eser2020.exp_enc_share', 'pct')
    esi = R('esi', f'{B}.eser2020.spent_of_issued', 'pct')
    cse, cee = R('cse', 't5_bonds.city_report.seawall_exp_enc_share', 'pct'), R('cee', 't5_bonds.city_report.eser_exp_enc_share', 'pct')
    pl, pm, ph = R('pl', f'{B}.peer_curve.min', 'pct'), R('pm', f'{B}.peer_curve.median', 'pct'), R('ph', f'{B}.peer_curve.max', 'pct')
    pn = R('pn', f'{B}.peer_curve.n', 'int')
    arb = C_('arb', 1.46e6, 'Controller GO Bond Program Report FY2023-25, p. 9: ESER 2020 arbitrage rebate', 'm1')
    irs = C_('irs', 0.85, 'IRS arbitrage spend-down expectation cited in the Controller GO Bond Program Report, p. 82', 'pct')
    dly1, dly2 = (C_(f'dly{i}', v, 'Controller GO Bond Program Report FY2023-25, p. 69: Seawall design milestone delays in years', 'int') for i, v in ((1, 9), (2, 10)))
    hj = interim('hj', 'an_yearend_summary.csv', 'dept', 'HSA', 'median_june_share', 'pct')
    even = C_('even', 1 / 12, 'an even monthly share of annual commitments', 'pct1')
    j18, j25 = interim('j18', 'an_yearend_city.csv', 'fy', 2018, 'june_share', 'pct'), interim('j25', 'an_yearend_city.csv', 'fy', 2025, 'june_share', 'pct')
    pol = interim('bpol', 'an_budget_exec_summary.csv', 'dept', 'POL', 'median_exec', 'pct')
    dph = interim('bdph', 'an_budget_exec_summary.csv', 'dept', 'DPH', 'median_exec', 'pct')
    com('pf-gaps',
        f"Operating budgets land close to plan (General Fund: {gfr} of adopted in FY2025); capital lags: the 2018 Seawall and 2020 Earthquake Safety bonds had spent {sw} and {es} of their budgets after {sy} and {ey} years, the Seawall largely by design while a federal study proceeds.",
        [f"Operating budgets. Measured against the adopted budget, General Fund operating spending ran {gfr} in FY2025 and other funds {otr}; the other-fund figure mostly reflects grants, continuing projects and enterprise accounts the adopted budget does not show, and the Charter bars spending beyond appropriations, so overages mean mid-year supplemental appropriations or new revenue. Police ({pol} median over FY2013 to FY2025) ends near its budget and Public Health around {dph}, helped by hospital patient revenue. Totals near plan can hide large line overruns, such as Police overtime offset by salary savings. The cards open on all funds; switch to the General Fund for the cleanest operating comparison.",
         f"Capital bonds. As of June 30, 2025, the 2018 Seawall program had spent {sw} of its {sb} budget ({swi} of the bonds issued so far), and the {eb} 2020 Earthquake Safety and Emergency Response program {es} ({esi} of issued). Counting money committed under contract, the figures are {swe} and {ese}, matching the Controller's own GO Bond Program Report ({cse} and {cee}). Other city bond programs observed four and a half to eight and a half years after their vote had spent {pl} to {ph} (median {pm}, {pn} program snapshots).",
         f"Why they lag, and why it matters. The Seawall bond was designed to fund planning and early projects while the US Army Corps of Engineers studies the waterfront; the city's report says design milestones slipped {dly1} and {dly2} years mainly because that federal study was extended, and federal cost-sharing requires the design work first. The Earthquake Safety program reports construction-cost escalation and delays in three of five components, and under federal tax rules it returned {arb} of excess interest earnings to the IRS (a routine requirement, not a penalty); the IRS expects issuers to spend {irs} of proceeds within three years of issuance; the Controller's report itself calls such rebates a possible sign that projects are moving slower than planned. Year-end: Human Services commits a median {hj} of its annual purchase orders in June, against {even} if purchases were spread evenly across the year, consistent with grants that start July 1; citywide June's share fell from {j18} in FY2018 to {j25} in FY2025."],
        [{'id': 'gap', 'template': f'For your filters (FY{{fy}}, {{depts_fmt}} departments): actual spending differed from the adopted budget by {{gap_total}} ({{gap_pct}}); {{over_fmt}} departments were more than {num("k5", "pct")} over and {{under_fmt}} more than {num("k5", "pct")} under.', 'requires': {'depts_min': 1}, 'fallback': TF}],
        [{'severity': 'high', 'text': 'Read annual gaps for operating categories and the General Fund; capital and debt appropriations are multi-year and partly outside the adopted budget, so their annual gaps are not meaningful.'},
         {'severity': 'medium', 'text': 'The open data carry only the adopted budget, not the revised budget after supplemental appropriations, so every gap is against the original plan.'},
         {'severity': 'medium', 'text': 'Bond spend rates depend on issuance timing and project phase; a planning-stage program such as the Seawall is not comparable with a construction-ready one.'},
         {'severity': 'low', 'text': 'The Public Utilities Commission books much of its actual spending in fund categories the budget does not use, so its gap is an accounting artifact.'}],
        ['performance/spending/cells.json', 'performance/data/redteam/redteam2.json#t5_bonds', 'performance/data/raw/capital/reports/FY24-FY25_Capital_Report.pdf'])


def depts():
    start('commentary/pf-depts.json')
    com('pf-depts', "Every city department's spending, staffing, performance measures and, where they exist, audits and nonprofit contracts, one scorecard each.",
        ['Open a department for its scorecard. Separate agencies and trust funds that the city reports on but does not run as departments (pension trusts, the Community College District, the Transportation Authority, the former Redevelopment Agency) are not shown.',
         'Start with context before comparing: departments differ in demand (calls, caseloads), in how much of their money is voter-mandated or fee-funded, and in whether they were reorganized. A missing section means no record was found, not that nothing exists.'],
        [], [{'severity': 'medium', 'text': 'Not every department reports performance measures or has been audited.'},
             {'severity': 'medium', 'text': 'Departments created or merged by reorganization (Homelessness and Supportive Housing in FY2017, Police Accountability in FY2018, Early Childhood in FY2023) have histories that do not line up with their predecessors.'},
             MEASURE_CAVEAT], ['performance/meta.json'])


def story():
    start('commentary/story_pf.json')
    ch = num('gf_ch', 'pct'); hx = num('hx', 'x1'); s25 = num('ots25', 'pct1'); f13, f25 = num('f13', 'mmss'), num('f25', 'mmss')
    em, rh = num('i_em', 'pct'), num('i_rh', 'pct'); sw, es = num('sw', 'pct'), num('es', 'pct'); mult = num('mult', 'x1')
    l17, l25 = num('l17', 'usd'), num('l25', 'usd')
    OUTPUTS['commentary/story_pf.json'] = {'sample': False, 'dashboard': 'pf', 'title': 'Budget vs outcomes: what San Francisco spends and what it gets', 'steps': [
        {'view': 'pf-overview', 'title': 'The money', 'text': f"General Fund operating spending per resident rose {ch} after inflation from FY2013 to FY2025, nearly all of it by FY2021.", 'filters': {'real': True, 'years': [2013, 2025]}},
        {'view': 'pf-spending', 'title': 'Where it grew', 'text': f"Housing, homelessness and workforce programs grew fastest; homelessness spending reached {hx} times its FY2017 level, partly from programs moving in, a voter-approved tax and pandemic aid.", 'filters': {'real': True, 'years': [2015, 2025]}},
        {'view': 'pf-staffing', 'title': 'Overtime', 'text': f"Overtime reached {s25} of pay in FY2025; Police ledger overtime was {mult} times its adopted budget, part of it billed to event sponsors and offset by vacancy savings.", 'filters': {'years': [2013, 2025]}},
        {'view': 'pf-outcomes', 'title': 'What happened to results?', 'text': f"Data outside the departments' scorecards show slower emergency response ({f13} to {f25} for life-threatening medical calls) as calls grew faster than the Fire budget; part of the delay is in 911 dispatch.", 'filters': {'years': [2013, 2025]}},
        {'view': 'pf-integrity', 'title': 'How much do the scorecards mean?', 'text': f"Targets track results: eased after {em} of misses, raised after {rh} of hits. The bar moves with performance.", 'filters': {}},
        {'view': 'pf-cost', 'title': 'Unit costs', 'text': f"Library cost per visit rose from {l17} to {l25} as visits stayed below pre-pandemic levels; Fire's cost per call fell as demand outran the budget.", 'filters': {'real': True}},
        {'view': 'pf-gaps', 'title': 'Budget vs actual', 'text': f"Operating budgets land near plan; capital lags: after {num('sy', 'yrs')} and {num('ey', 'yrs')} years the Seawall (planning-stage by design, tied to an Army Corps study) and Earthquake Safety bonds had spent {sw} and {es} of their budgets.", 'filters': {}}]}


# ================================================================== scorecards
CONTEXT = {
    'FIR': lambda: f"Demand is the backdrop: Fire and EMS calls rose {num('fcalls', 'pct')} from FY2013 to FY2025 against {num('fsp', 'pct')} real spending growth, and the median response to life-threatening medical calls slowed from {num('f13', 'mmss')} to {num('f25', 'mmss')}, part of it in call-taking and dispatch by Emergency Management. Many of its targets are fixed response-time standards that it has not lowered, so its low met share partly reflects targets held constant.",
    'POL': lambda: f"Ledger overtime was {num('mult', 'x1')} times the adopted overtime budget in FY2025; {num('f10', 'm1')} of it ran through the fund repaid by event sponsors (Section 10B) and {num('air', 'm1')} was paid by the Airport. Priority A response went from {num('a16', 'mmss')} (FY2016) to {num('a25', 'mmss')} (FY2025).",
    'HOM': lambda: f"Created in FY2017 from Human Services and Public Health programs; real spending grew {num('hx', 'x1')} times by FY2025, much of it from a 2018 voter-approved business tax and pandemic aid. The one-night homeless count was {num('pit17', 'int')} in 2017 and {num('pit24', 'int')} in 2024.",
    'MTA': lambda: f"Muni's on-time performance was {num('mu25', 'pct')} in FY2025, below the {num('k85', 'pct')} Charter standard, as in every year of the data. SFMTA is the only one of the {num('i_nd', 'int')} departments tested where targets were not eased more often after misses. Much of its budget is fares, fees and state and federal funds.",
    'LIB': lambda: f"Spending per in-person visit rose from {num('l17', 'usd')} (FY2017) to {num('l25', 'usd')} (FY2025, FY2026 dollars) as visits stayed below FY2019; online use is not counted, and much funding is a voter-approved set-aside.",
    'PRT': lambda: f"The Port runs the 2018 Seawall bond program, which had spent {num('sw', 'pct')} of its {num('sb', 'm')} budget after {num('sy', 'yrs')} years; it was designed around a US Army Corps of Engineers study whose extension delayed design by {num('dly1', 'int')} to {num('dly2', 'int')} years.",
    'DPW': lambda: f"Public Works manages the 2020 Earthquake Safety and Emergency Response bond, {num('ese', 'pct')} expended or committed as of June 30, 2025. FY2018 actuals are masked because of financial-system conversion entries.",
    'DEM': lambda: f"Emergency Management takes 911 calls and dispatches Fire and Police; about {num('bef', 'mins')} minutes of the {num('fslow', 'mins')}-minute slowdown in medical response since FY2013 came before dispatch.",
    'DPH': lambda: f"Public Health usually ends above its adopted budget (median {num('bdph', 'pct')} over FY2013 to FY2025), largely funded by hospital patient revenue and mid-year appropriations.",
    'HSA': lambda: f"Human Services lost programs to Homelessness and Supportive Housing (FY2017) and Early Childhood (FY2023), so its own trend understates human-services spending, which rose {num('hs', 'pct')} in total from FY2013 to FY2025. It commits a median {num('hj', 'pct')} of annual purchase orders in June, consistent with grants that start July 1.",
    'PUC': lambda: "Growth is mostly electricity bought for CleanPowerSF customers, paid through their bills; the utilities' budget-versus-actual gap is largely an accounting artifact.",
}


def scorecards():
    R('fslow', 't3_fire.slowdown_min')
    for p in sorted(glob.glob(os.path.join(SITE, 'scorecards', '*.json'))):
        sc = json.load(open(p)); d = sc['dept']; name = sc.get('name') or NAMES.get(d, d)
        start(f'scorecards/{d}.json')
        paras, head = [], None
        has15 = SITEF['oper_real'](d, 2015) > 0 and SITEF['oper_real'](d, 2025) > 0
        if has15:
            site(f'{d}_s15', 'oper_real', d, 2015); site(f'{d}_s25', 'oper_real', d, 2025); site(f'{d}_sch', 'oper_real_change', d, 2015, 2025)
            head = f"{name}: operating spending of {num(f'{d}_s25', 'm')} in FY2025, {num(f'{d}_sch', 'spct')} after inflation since FY2015."
        elif SITEF['oper_real'](d, 2025) > 0:
            site(f'{d}_s25', 'oper_real', d, 2025)
            head = f"{name}: operating spending of {num(f'{d}_s25', 'm')} in FY2025."
        else:
            head = f"{name}: no FY2025 operating spending in the data."
        bits = []
        if SITEF['met_n_dept'](d, 2025) >= 3:
            site(f'{d}_mn', 'met_n_dept', d, 2025); site(f'{d}_ms', 'met_share_dept', d, 2025)
            bits.append((f"it met {num(f'{d}_ms', 'pct')} of its {num(f'{d}_mn', 'int')} scored targets" if SITEF['met_n_dept'](d, 2025) >= 20 else f"it met {site(f'{d}_mc', 'met_count_dept', d, 2025, kind='int')} of its {num(f'{d}_mn', 'int')} scored targets") + f" (citywide {num('met25', 'pct')})")
        elif SITEF['met_n_dept'](d, 2025) > 0:
            bits.append('it scored too few FY2025 targets to summarize')
        if ((ST.dept == d) & (ST.fy == 2025)).any() and (ST[(ST.dept == d) & (ST.fy == 2025)].ot_share.fillna(0).iloc[0] >= 0.005):
            site(f'{d}_ot', 'ot_share_dept', d, 2025)
            bits.append(f"overtime was {num(f'{d}_ot', 'pct1')} of base-plus-overtime pay (citywide {num('ots25', 'pct1')}" + ('; round-the-clock departments with minimum-staffing rules run higher)' if d in TOP5 else ')'))
        if bits:
            paras.append('In FY2025 ' + '; '.join(bits) + '.')
        rows = {r['dept']: r for r in rt2('t2_target_easing.per_dept.rows')}
        if d in rows:
            r = rows[d]
            reg(f'{d}_em', r['eased_after_miss'], f'rt2dept:{d}:eased_after_miss'); reg(f'{d}_rh', r['raised_after_hit'], f'rt2dept:{d}:raised_after_hit')
            reg(f'{d}_eh', r['eased_after_hit'], f'rt2dept:{d}:eased_after_hit')
            paras.append(f"Targets (FY2013 to FY2026 changes): it eased the next target after {num(f'{d}_em', 'pct')} of misses and {num(f'{d}_eh', 'pct')} of hits, and raised it after {num(f'{d}_rh', 'pct')} of hits." + (' Easing after a miss is often forecasting (for example, measures hit by the pandemic); unusual is not improper.' if r['eased_after_miss'] > 0.3 else ''))
        if d in CONTEXT:
            paras.append(CONTEXT[d]())
        cav = [MEASURE_CAVEAT, {'severity': 'medium', 'text': 'Spending is gross operating spending in FY2026 dollars (Bay Area CPI-U); reorganizations and demand changes are not adjusted for.'}]
        if any(d in r.get('depts', []) for r in META.get('reorganizations', [])) or d in ('HOM', 'HSA', 'DPA', 'POL', 'DEC', 'CFC'):
            cav.append({'severity': 'high', 'text': 'This department was part of a reorganization; its series before and after is not comparable without its predecessor or successor.'})
        sc['commentary'] = {'author': AUTHOR, 'headline': head, 'paragraphs': paras, 'caveats': cav,
                            'note': 'Generated by pipeline/17b_commentary.py; unusual is not improper.'}
        OUTPUTS[f'scorecards/{d}.json'] = sc


def facts():
    start('commentary/facts_pf.json')
    OUTPUTS['commentary/facts_pf.json'] = {'as_of': '2026-09-26', 'note': 'Headline findings after red team 2, with verdicts. Unusual is not improper.', 'facts': [
        {'id': 'city-gf-per-resident', 'view': 'pf-overview', 'verdict': 'survives', 'headline': f"General Fund operating spending per resident rose {num('gf_ch', 'pct')} after inflation, {num('gf2013', 'usd')} (FY2013) to {num('gf2025', 'usd')} (FY2025), with {num('gf_wo', 'pct')} to {num('gf_us', 'pct')} under alternative treatments; flat since FY2021.", 'source': 'data/redteam/redteam2.json#t1_gf_per_resident'},
        {'id': 'targets-eased-after-miss', 'view': 'pf-integrity', 'verdict': 'survives, reframed', 'headline': f"Eased after {num('i_em', 'pct1')} of misses vs {num('i_eh', 'pct1')} of hits; raised after {num('i_rh', 'pct1')} of hits. Excluding mechanically reset measures: {num('i_rmech', 'x1')} times; {num('i_nmore', 'int')} of {num('i_nd', 'int')} departments.", 'source': 'data/redteam/redteam2.json#t2_target_easing'},
        {'id': 'fire-demand-vs-response', 'view': 'pf-outcomes', 'verdict': 'survives', 'headline': f"Calls {num('fcalls', 'spct')}, real spending {num('fsp', 'spct')}; median {num('f13', 'mmss')} to {num('f25', 'mmss')} (call to arrival), {num('d13', 'mmss')} to {num('d25', 'mmss')} (dispatch to arrival); same under original priority.", 'source': 'data/redteam/redteam2.json#t3_fire'},
        {'id': 'police-overtime', 'view': 'pf-staffing', 'verdict': 'survives with scope note; per-hour ratio fragile', 'headline': f"Payroll overtime {num('polot25', 'm')}; ledger {num('mult', 'x1')} times budget ({num('gfr', 'x1')} for own General Fund accounts); {num('f10', 'm1')} in the sponsor-repaid Section 10B fund; per-hour cost ratio {num('phlo', 'x2')} to {num('phhi', 'x2')} depending on assumptions.", 'source': 'data/redteam/redteam2.json#t4_police_overtime'},
        {'id': 'bonds', 'view': 'pf-gaps', 'verdict': 'figures survive; Seawall framing changed', 'headline': f"Seawall {num('sw', 'pct')} spent ({num('swe', 'pct')} with commitments; Controller report {num('cse', 'pct')}); ESER 2020 {num('es', 'pct')} ({num('ese', 'pct')}; report {num('cee', 'pct')}); peers {num('pl', 'pct')} to {num('ph', 'pct')}.", 'source': 'data/redteam/redteam2.json#t5_bonds'},
        {'id': 'homelessness', 'view': 'pf-spending', 'verdict': 'survives', 'headline': f"HSH real spending {num('hx', 'x1')} times FY2017 to FY2025 ({num('h18x', 'x1')} times from FY2018).", 'source': 'data/redteam/redteam2.json#t6_hsh'},
        {'id': 'survey', 'view': 'pf-outcomes', 'verdict': 'survives with method caveat', 'headline': f"A or B grade {num('sv2015', 'pct')} (2015) to {num('sv2023', 'pct')} (2023), weighted, recomputed from microdata.", 'source': 'data/redteam/redteam2.json#t7_survey'}]}


def review():
    """Optional: one Opus fairness review of all generated text (cached, logged)."""
    from llm import call_json
    text = json.dumps({k: {kk: v.get(kk) for kk in ('headline', 'paragraphs', 'caveats', 'steps', 'commentary')} for k, v in OUTPUTS.items()
                       if not k.startswith('scorecards/') or k in ('scorecards/FIR.json', 'scorecards/POL.json', 'scorecards/HOM.json', 'scorecards/PRT.json', 'scorecards/MTA.json')}, ensure_ascii=False)
    schema = {'type': 'object', 'properties': {'issues': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'file': {'type': 'string'}, 'quote': {'type': 'string'}, 'problem': {'type': 'string'}, 'suggestion': {'type': 'string'},
        'severity': {'type': 'string', 'enum': ['high', 'medium', 'low']}}, 'required': ['file', 'quote', 'problem', 'suggestion', 'severity'], 'additionalProperties': False}},
        'overall': {'type': 'string'}, 'confidence': {'type': 'number'}}, 'required': ['issues', 'overall', 'confidence'], 'additionalProperties': False}
    sysmsg = ('You are an editor for a public accountability dashboard about San Francisco city government. Rules: report facts with context; '
              'never imply wrongdoing or mismanagement the data do not show; distinguish unusual from improper; department statements must note '
              'demand changes, reorganizations and that measures are self-reported; plain American English for smart non-experts; no sensationalism. '
              'Do not question the numbers (they are verified); judge framing, fairness, clarity and whether a claim outruns its evidence.')
    res = call_json('redteam2_fairness_review', 'claude-opus-5-5', sysmsg, 'Review this commentary JSON and list concrete issues:\n' + text, schema, effort='high', max_tokens=16000)
    json.dump(res, open(os.path.join(RT, 'fairness_review2.json'), 'w'), indent=1)
    for i in res['issues']:
        print(f"[{i['severity']}] {i['file']}: {i['quote'][:90]} -> {i['suggestion'][:160]}")
    print('overall:', res['overall'])


if __name__ == '__main__':
    overview(); spending(); staffing(); outcomes(); cost(); integrity(); gaps(); depts(); story(); scorecards(); facts()
    if '--review' in sys.argv:
        review()
    for path, obj in OUTPUTS.items():
        json.dump(obj, open(os.path.join(SITE, path), 'w'), indent=1, ensure_ascii=False)
    json.dump({'numbers': NUM, 'trace': TRACE}, open(os.path.join(RT, 'commentary_trace.json'), 'w'), indent=1)
    for v in ['pf-overview', 'pf-spending', 'pf-staffing', 'pf-outcomes', 'pf-cost', 'pf-integrity', 'pf-gaps']:
        print(v, '::', OUTPUTS[f'commentary/{v}.json']['headline'])
    print(len(NUM), 'traced numbers;', sum(len(v) for v in TRACE.values()), 'number uses in', len(TRACE), 'files')
