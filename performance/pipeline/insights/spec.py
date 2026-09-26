"""Text and chart templates for the insights page, shared by build_insights.py and verify_insights.py.

Every number shown to readers is a placeholder {key|fmt} filled from a computed value (V) or an @CH:key chart
array, so verify_insights.py can recompute each one independently from the source tables. Template text itself may
contain only years (FY2019, 2024), and a few fixed tokens (911, 311, Priority A, 10B...), which verify checks.
"""
import re

AS_OF = '2026-09-26'
INTRO = ('Eighteen findings about what San Francisco spends and what it gets, chosen from about thirty candidates we tested '
         'against the city\'s own budget, payroll, performance and service data; some are about how the budget itself works. '
         'Each held up under at least three robustness checks drawn from real vs nominal dollars, other start and end years, per-resident '
         'vs total figures, alternative sources, reorganizations and one-time items, and a separate script recomputes every number from the '
         'source tables. Most comparisons end in FY2025, the latest year with matching outcome data, and start when each dataset begins or when the change began; '
         'FY2026 (July 2025 to June 2026) figures are full-year actuals as published in September 2026 and are shown as a check. The findings describe '
         'patterns worth discussing, not wrongdoing; the dashboard behind each one lets you explore further.')

MINUS = '−'


def _signed(v, s):
    return ('+' if v > 0 else (MINUS if v < 0 else '')) + s


FMT = {
    'int': lambda v: f'{round(round(v, 6)):,}',
    'pct': lambda v: f'{v * 100:.0f}%',
    'pct1': lambda v: f'{v * 100:.1f}%',
    'apct': lambda v: f'{abs(v) * 100:.0f}%',
    'spct': lambda v: _signed(round(v * 100), f'{abs(v) * 100:.0f}%'),
    'pts': lambda v: f'{abs(v) * 100:.0f}',
    'usd': lambda v: f'${round(v):,}',
    'usd2': lambda v: f'${v:,.2f}',
    'mil': lambda v: f'${v / 1e6:,.0f} million',
    'mil1': lambda v: f'${v / 1e6:,.1f} million',
    'bil2': lambda v: f'${v / 1e9:,.2f} billion',
    'bil1': lambda v: f'${v / 1e9:,.1f} billion',
    'x1': lambda v: f'{v:.1f}',
    'x2': lambda v: f'{v:.2f}',
    'f1': lambda v: f'{v:.1f}',
    'f2': lambda v: f'{v:.2f}',
    'cm1': lambda v: f'{v / 1e6:.1f} million',
    'cm2': lambda v: f'{v / 1e6:.2f} million',
    'mmss': lambda v: f'{int(round(v * 60)) // 60} min {int(round(v * 60)) % 60:02d} s',
    'fy': lambda v: f'FY{int(v)}',
    'mins': lambda v: f'{v:.1f} min',
    'r100': lambda v: f'{int(round(v / 100.0)) * 100:,}',
    'usd100': lambda v: f'${int(round(v / 100.0)) * 100:,}',
    'aint': lambda v: f'{abs(round(round(v, 6))):,}',
    'amil': lambda v: f'${abs(v) / 1e6:,.0f} million',
    'abil2': lambda v: f'${abs(v) / 1e9:,.2f} billion',
}
PH = re.compile(r'\{(\w+)\|(\w+)\}')


def render_str(s, V):
    def rep(m):
        k, f = m.group(1), m.group(2)
        if k not in V:
            raise KeyError(f'missing value {k}')
        return FMT[f](V[k])
    return PH.sub(rep, s)


def render(obj, V, CH):
    """Recursively render a template object. Strings get placeholders filled; '@CH:key' pulls a chart array."""
    if isinstance(obj, str):
        if obj.startswith('@CH:'):
            return [None if v is None else (round(float(v), 2) if isinstance(v, float) or hasattr(v, 'dtype') else v) for v in CH[obj[4:]]]
        return render_str(obj, V)
    if isinstance(obj, list):
        return [render(o, V, CH) for o in obj]
    if isinstance(obj, dict):
        return {k: render(v, V, CH) for k, v in obj.items()}
    return obj


# Tokens allowed to contain digits in template text (outside placeholders)
ALLOWED_DIGIT_TOKENS = [r'FY\d{4}–\d{2}\b', r'FY\d{2}-\d{2}', r'FY\d{4}', r'\b(19|20)\d{2}\b', r'\b911\b', r'\b311\b',
                        r'\b10B\b', r'CPI-U', r'E-4', r'COVID-19', r'\b3/E\b', r'= 100\b', r'\b[a-z0-9]{4}-[a-z0-9]{4}\b',
                        r'CUURS49BSA0', r'ntd_id \d+', r'TS2\.2', r'measure \d{4}', r'\b90th\b', r'First 5', r'June 30']

SRC = {
    'dept_fy': 'performance/data/interim/dept_fy.csv',
    'cube': 'performance/data/interim/spend_cube.parquet',
    'long': 'performance/data/interim/spend_long.parquet',
    'ec': 'performance/data/raw/employee_comp.csv (DataSF 88g8-5mnd, fiscal years)',
    'sr': 'performance/data/raw/spending_revenue.csv (DataSF bpnb-jwfb)',
    'fte': 'performance/data/raw/context/fte_citywide_fy.csv (DataSF 4zfx-f2ts budgeted, 43jt-u7yn actual)',
    'fte_dept': 'performance/data/raw/context/fte_by_dept_fy.csv (DataSF 4zfx-f2ts, 43jt-u7yn)',
    'ctx': 'performance/data/interim/context_fy.csv (Bay Area CPI-U CUURS49BSA0; CA DOF E-4 population)',
    'fire': 'performance/data/raw/outcomes/fire_ems_response_fy.csv (DataSF nuek-vuh3, call level)',
    'police': 'performance/data/raw/outcomes/police_response_fy.csv (DataSF 2zdj-bwza, call level)',
    'pit': 'performance/data/raw/outcomes/scorecard_outcome_extracts.csv (DataSF kc49-udxn, measure 7169)',
    'ntd': 'performance/data/raw/outcomes/ntd_sfmta_service_fy.csv (FTA NTD TS2.2, ntd_id 90015)',
    'survey': 'performance/data/raw/outcomes/city_survey_microdata.csv (DataSF nufj-bfbw)',
    'pm': 'performance/data/raw/perf_measures/citywide_performance_metrics.csv (DataSF 6dpt-7w23)',
    'bonds': 'performance/data/site/analyses/go_bond_programs.json (DataSF m793-kis4, FY24-25 snapshot)',
    'targets': 'performance/data/interim/an_target_changes.csv; performance/data/redteam/redteam2.json#t2_target_easing',
    'lineage': 'performance/data/interim/an_lineage_events.csv; performance/data/interim/an_drop_test.csv',
    'rt2': 'performance/data/redteam/redteam2.json',
}

FY_NOTE = 'Fiscal years run July to June and are labeled by the year they end.'
REAL_NOTE = 'Real dollars are FY2026 dollars, deflated with the Bay Area CPI-U.'


DEM_NOTE = ('Response time runs from when the 911 call is received, so it includes call handling by the Department of '
            'Emergency Management as well as travel.')

INSIGHTS = [
    # 1 ------------------------------------------------------------------------------------------------------------------
    dict(key='police_staffing', id='police-sworn-staff-down-overtime-up', theme='staffing',
         title='Police full-year sworn staff fell {full_chg|apct} since FY2019; paid hours fell only {hours_chg|apct}',
         dek='Sworn Police employees on regular payroll for most of the year fell from {full_2019|int} in FY2019 to {full_2025|int} in FY2025, '
             'and all sworn staff paid fell {n_chg|apct}. Total paid hours fell only {hours_chg|apct}, while overtime pay rose from {ot_2019|mil} to {ot_2025|mil} '
             '({ot_real_x|x1} times after inflation).',
         why_it_matters='Police departments across the country have reported hiring and retention difficulties since 2020. Overtime lets the department cover vacancies while hiring catches up, but it is paid at a premium and concentrates hours on fewer people: '
                        'paid hours per sworn employee rose about {hpe_chg|apct}. How long vacancies can be covered this way, and whether hiring or overtime is '
                        'cheaper over time, is a live budget question.',
         surprise='Fewer officers would usually mean fewer hours of police work; here total hours barely moved and overtime grew.',
         numbers=[
             dict(label='Sworn employees on regular payroll most of the year (see caveats), FY2019 → FY2025', value='{full_2019|int} → {full_2025|int} ({full_chg|spct})', source=SRC['ec'] + '#Job Family=Police Services, POL'),
             dict(label='All sworn employees paid, FY2019 → FY2025', value='{n_2019|int} → {n_2025|int} ({n_chg|spct})', source=SRC['ec'] + '#POL'),
             dict(label='Paid hours, all sworn staff (includes overtime hours and leave)', value='{hours_2019|cm2} → {hours_2025|cm2} ({hours_chg|spct})', source=SRC['ec'] + '#Hours'),
             dict(label='Overtime pay, sworn staff (nominal)', value='{ot_2019|mil} → {ot_2025|mil}', source=SRC['ec'] + '#Overtime'),
             dict(label='Overtime pay, real (FY2026 dollars)', value='{ot_real_x|x1} times the FY2019 level', source=SRC['ec'] + '; ' + SRC['ctx']),
             dict(label='Police ledger overtime vs original adopted overtime budget, FY2025', value='{ledger_ot_2025|mil} vs {budget_ot_2025|mil} ({ledger_ratio_2025|x1} times)', source=SRC['dept_fy'] + '#actual_overtime,budget_overtime (POL)'),
         ],
         chart=dict(type='line', title='Fewer sworn staff, nearly the same hours, far more overtime',
                    subtitle='Police sworn staff (Police Services job family), index FY2019 = 100; overtime in real dollars; hours are reported from FY2017',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Index (FY2019 = 100)', unit='index'),
                    series=[dict(name='Overtime pay (real)', values='@CH:ot_real'), dict(name='Paid hours', values='@CH:hours'),
                            dict(name='Full-year sworn staff', values='@CH:full')],
                    annotations=[dict(x=2020, label='COVID-19')], highlight='Overtime pay (real)',
                    note='Source: Employee Compensation (DataSF 88g8-5mnd), fiscal years. Hours include overtime hours and paid leave. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Counting everyone paid, not just full-year staff: {n_chg|spct} FY2019–FY2025, against paid hours {hours_chg|spct}.',
             'From FY2017 instead of FY2019: employees {n_chg_17|spct}, paid hours {hours_chg_17|spct}.',
             'FY2026 continues the pattern: overtime pay {ot_2026|mil} with {full_2026|int} full-year sworn staff.',
             'The city ledger, a separate source that classifies some pay differently, shows the same surge: Police overtime {ledger_ot_2019|mil} in FY2019 → {ledger_ot_2025|mil} in FY2025.'],
             what_could_make_it_wrong='Payroll hours include overtime and paid leave and are not split, so the hours comparison is approximate. Some overtime is for events billed to outside sponsors (Section 10B) or investigations and court time, not vacant shifts.'),
         caveats=['"Full-year" staff = regular pay at least half the median for the same job and year.',
                  'Adopted overtime budgets are routinely set low and topped up during the year (see the overtime-budget finding).'],
         explore=dict(view='pf-staffing', params={'dept': 'POL', 'years': '2017-2026'}, label='See Police staffing and overtime'),
         departments=['POL'], tags=['overtime', 'vacancies', 'police']),

    # 2 ------------------------------------------------------------------------------------------------------------------
    dict(key='fire', id='fire-calls-spending-response', theme='outcomes',
         title='Fire/EMS calls rose {calls_chg|apct} since FY2013; real Fire spending rose {sp_chg|apct}',
         dek='Unique Fire and EMS calls grew from {calls_2013|int} in FY2013 to {calls_2025|int} in FY2025. Real operating spending grew {sp_chg|apct} and budgeted '
             'positions {fte_chg|apct}; filled positions grew {fta_chg|apct} from a FY2013 base with many vacancies, roughly matching the growth in calls. '
             'The median response to life-threatening medical calls still slowed, from {med_2013|mins} to {med_2025|mins}.',
         why_it_matters='Most of the growth is medical calls. Response times depend on unit staffing, on how long ambulances wait at hospitals, on traffic and on 911 call '
                        'handling; even from dispatch to arrival the median rose from {d2a_2013|mins} to {d2a_2025|mins}. Adding fire companies, adding ambulances and '
                        'alternative responders, or reducing low-acuity calls are the main levers.',
         numbers=[
             dict(label='Fire/EMS calls, FY2013 → FY2025', value='{calls_2013|int} → {calls_2025|int} ({calls_chg|spct})', source=SRC['fire'] + '#calls_total'),
             dict(label='Real Fire operating spending, FY2013 → FY2025', value='{sp_2013|mil} → {sp_2025|mil} ({sp_chg|spct})', source=SRC['dept_fy'] + '#actual_oper_all_real (FIR)'),
             dict(label='Budgeted / filled Fire positions (FTE)', value='{fte_2013|int} → {fte_2025|int} ({fte_chg|spct}) / {fta_2013|int} → {fta_2025|int} ({fta_chg|spct})', source=SRC['fte_dept'] + '#budget_fte_gross, actual_fte (FIR)'),
             dict(label='Median response, life-threatening medical calls (911 to first unit)', value='{med_2013|mins} → {med_2025|mins}', source=SRC['fire'] + '#code3_medical_first_unit_median_min'),
             dict(label='90th-percentile response, same calls', value='{p90_2013|mins} → {p90_2025|mins}', source=SRC['fire'] + '#code3_medical_first_unit_p90_min'),
         ],
         chart=dict(type='line', title='Calls rose {calls_chg|apct} and filled positions {fta_chg|apct}, real spending {sp_chg|apct}; response times slipped',
                    subtitle='Index, FY2013 = 100: unique Fire/EMS calls, filled positions, real operating spending, median response to life-threatening medical calls',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Index (FY2013 = 100)', unit='index'),
                    series=[dict(name='Calls', values='@CH:calls'), dict(name='Filled positions', values='@CH:filled'),
                            dict(name='Median response time', values='@CH:median'), dict(name='Real operating spending', values='@CH:spend')],
                    annotations=[dict(x=2021, label='COVID-19 dip in calls')], highlight='Calls',
                    note='Sources: Fire Department and EMS Dispatched Calls for Service (DataSF nuek-vuh3); Spending and Revenue (bpnb-jwfb); Spending - FTE (43jt-u7yn). '
                         'Life-threatening medical = final priority 3/E medical calls. ' + DEM_NOTE + ' ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Dispatch-to-arrival only (excludes call handling): median {d2a_2013|mins} → {d2a_2025|mins}.',
             'Using the original, not final, call priority: median {orig_med_2013|mins} → {orig_med_2025|mins}.',
             'Starting in FY2019: calls {calls_chg_19|spct}, real spending {sp_chg_19|spct}.',
             'National CPI-U instead of Bay Area CPI: real spending {sp_chg_us|spct} FY2013–FY2025.',
             'Calls per budgeted position rose {calls_per_pos_chg|apct}; real spending per call fell {per_call_chg|apct}.'],
             what_could_make_it_wrong='Filled positions are measured as paid FTE (paid hours), not people on duty per shift; hospital wall times and traffic affect response times independently of Fire staffing.'),
         caveats=['Calls count unique incidents; one call can draw several units.', DEM_NOTE],
         explore=dict(view='pf-outcomes', params={'dept': 'FIR', 'years': '2013-2025'}, label='See Fire\'s measures and response times'),
         departments=['FIR'], tags=['demand', 'response times', 'EMS']),

    # 3 ------------------------------------------------------------------------------------------------------------------
    dict(key='homeless', id='homelessness-spending-and-shelter', theme='spending-growth',
         title='Homelessness spending rose to {x_19_25|x1} times FY2019; the count held steady as more moved indoors',
         dek='Real spending by the Department of Homelessness and Supportive Housing rose from {hom_2019|mil} in FY2019 to {hom_2025|mil} in FY2025. '
             'Between the 2019 and 2024 point-in-time counts, people sleeping unsheltered fell from {unsh_2019|int} to {unsh_2024|int} while people in shelter rose from {sh_2019|int} to {sh_2024|int}.',
         why_it_matters='Shelter capacity grew alongside the budget: the total count barely moved ({tot_chg|spct}), but the share of people indoors rose from {sh_share_2019|pct} to {sh_share_2024|pct}. '
                        'Much of the budget also pays for supportive housing for formerly homeless people, who no longer appear in the count at all. The count cannot show how many people programs moved out of homelessness, because it also reflects people newly becoming homeless; that flow is the open question.',
         surprise='A much larger budget coincided with a one-night count of about the same size; what changed is where people sleep.',
         numbers=[
             dict(label='HSH real operating spending, FY2019 → FY2025', value='{hom_2019|mil} → {hom_2025|mil} ({x_19_25|x1} times)', source=SRC['dept_fy'] + '#actual_oper_all_real (HOM)'),
             dict(label='Unsheltered people, 2019 → 2024 count', value='{unsh_2019|int} → {unsh_2024|int} ({unsh_chg|spct})', source=SRC['pit']),
             dict(label='Sheltered people, 2019 → 2024 count', value='{sh_2019|int} → {sh_2024|int} ({sh_chg|spct})', source=SRC['pit']),
             dict(label='Total people counted, 2019 → 2024', value='{tot_2019|int} → {tot_2024|int} ({tot_chg|spct})', source=SRC['pit']),
         ],
         chart=dict(type='stacked', title='More people indoors, about the same number counted',
                    subtitle='People experiencing homelessness in the January point-in-time count, sheltered and unsheltered',
                    x=dict(label='Count year', values='@CH:x'), y=dict(label='People', unit='count'),
                    series=[dict(name='Unsheltered', values='@CH:unsheltered'), dict(name='Sheltered', values='@CH:sheltered')],
                    annotations=[dict(x=2017, label='HSH created (FY2017)')], highlight='Sheltered',
                    note='Source: point-in-time counts reported in the city scorecard (DataSF kc49-udxn, measure 7169). The 2021 count was postponed to 2022. Counts are biennial.'),
         robustness=dict(verdict='robust', checks=[
             'From FY2017, the department\'s first year: {x_17_25|x1} times; from FY2018, after programs finished moving in: {x_18_25|x1} times.',
             'Against the 2022 count, unsheltered is nearly flat ({unsh_chg_22|spct}); the drop happened by 2022.',
             'FY2026 spending eased to {hom_2026|mil}, still far above FY2019.'],
             what_could_make_it_wrong='Part of the shelter expansion was pandemic-era hotel rooms with outside funding; point-in-time counts are one-night snapshots with method changes between years.'),
         caveats=['Part of the growth is funded by a business tax dedicated to homelessness that voters approved in 2018, not only by the General Fund.',
                  'Other departments (Public Health, Human Services, MOHCD) also spend on homelessness and are not included.'],
         explore=dict(view='pf-spending', params={'dept': 'HOM', 'years': '2017-2026'}, label='See homelessness spending'),
         departments=['HOM'], tags=['homelessness', 'shelter']),

    # 4 ------------------------------------------------------------------------------------------------------------------
    dict(key='pension', id='pension-costs-fell-as-share-of-pay', theme='spending-growth',
         title='Pension costs fell from {rshare_2021|pct1} of regular pay in FY2021 to {rshare_2025|pct1} in FY2025',
         dek='Employer retirement contributions dropped from {ret_2021|mil} in FY2021 to {ret_2025|mil} in FY2025 even as salaries grew {sal_chg_21_25|apct}, '
             'reflecting lower contribution rates, which follow the pension fund\'s investment returns. At FY2021\'s peak ratio to regular (non-overtime) pay, FY2025 retirement costs would have been about {rsavings_2025|mil} higher.',
         why_it_matters='Lower contribution rates reduced the city\'s retirement bill by hundreds of millions of dollars a year compared with FY2021 rates, easing pressure on the rest of the budget. '
                        'Rates follow investment returns and actuarial assumptions, so this cushion can reverse.',
         surprise='Pension costs are usually described as an ever-rising burden. In San Francisco they peaked at {rshare_2021|pct1} of regular pay in FY2021, then fell below the FY2013 level of {rshare_2013|pct1}.',
         numbers=[
             dict(label='Retirement contributions as % of regular pay, excluding overtime (city ledger), FY2021 → FY2025', value='{rshare_2021|pct1} → {rshare_2025|pct1}', source=SRC['long'] + '#benefits, object Retirement; salaries minus overtime objects'),
             dict(label='Retirement contributions (nominal)', value='{ret_2021|mil} → {ret_2025|mil}', source=SRC['long']),
             dict(label='Salaries incl. overtime (nominal)', value='{sal_2021|bil2} → {sal_2025|bil2} ({sal_chg_21_25|spct})', source=SRC['long'] + '#salaries'),
             dict(label='Same ratio from payroll records (regular plus other pay)', value='{pay_rshare_2021|pct1} → {pay_rshare_2025|pct1}', source=SRC['ec'] + '#Retirement/(Salaries+Other Salaries)'),
         ],
         chart=dict(type='line', title='Employer retirement costs as a share of regular pay',
                    subtitle='Percent of pay excluding overtime; city ledger (all funds) and payroll records',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='% of regular pay', unit='%'),
                    series=[dict(name='City ledger', values='@CH:ledger'), dict(name='Payroll records', values='@CH:payroll')],
                    annotations=[dict(x=2021, label='Peak')], highlight='City ledger',
                    note='Sources: Spending and Revenue (DataSF bpnb-jwfb), Mandatory Fringe Benefits objects named Retirement; Employee Compensation (88g8-5mnd).'),
         robustness=dict(verdict='robust', checks=[
             'Two independent sources agree: payroll records give {pay_rshare_2021|pct1} → {pay_rshare_2025|pct1}.',
             'Including overtime in the pay base: {share_2021|pct1} → {share_2025|pct1}; General Fund only: {gf_share_2021|pct1} → {gf_share_2025|pct1}.',
             'Not just a peak-year effect: FY2026 stayed low at {rshare_2026|pct1}, below the FY2013 level of {rshare_2013|pct1}.'],
             what_could_make_it_wrong='Contribution rates are set each year from investment returns and actuarial assumptions, and a weak market year would raise them again.'),
         caveats=['Retiree health costs are budgeted separately and are not included.', 'Regular pay excludes overtime, which is mostly not pensionable.'],
         explore=dict(view='pf-spending', params={'years': '2013-2026'}, label='See spending by category'),
         departments=[], tags=['pensions', 'benefits']),

    # 5 ------------------------------------------------------------------------------------------------------------------
    dict(key='police_calls', id='police-fewer-calls-slower-response', theme='outcomes',
         title='Police 911 calls fell {calls_tot_chg|apct} since FY2016, mostly low-priority; urgent responses slowed',
         dek='911-originated Priority A, B and C calls fell from {calls_tot_2016|int} in FY2016 to {calls_tot_2025|int} in FY2025, mostly lower-priority calls. '
             'Median response to the most urgent (Priority A) calls rose from {med_A_2016|mins} to {med_A_2025|mins}, and to Priority B calls from {med_B_2016|mins} to {med_B_2025|mins}.',
         why_it_matters='The slowdown is almost entirely in travel after dispatch, not call handling. Full-year sworn staff fell sharply since FY2019 while total paid hours fell much less (see the Police staffing finding), '
                        'so how many hours go to patrol is the key unknown. Deployment choices, longer time spent on each call, the mix and location of calls, and officer-initiated work not counted here could also contribute.',
         surprise='With fewer calls, other things equal, officers would be free to respond faster; instead urgent responses slowed even though urgent calls fell only {calls_A_chg|apct}.',
         numbers=[
             dict(label='Priority A calls, FY2016 → FY2025', value='{calls_A_2016|int} → {calls_A_2025|int} ({calls_A_chg|spct})', source=SRC['police'] + '#calls'),
             dict(label='Priority B calls', value='{calls_B_2016|int} → {calls_B_2025|int} ({calls_B_chg|spct})', source=SRC['police'] + '#calls'),
             dict(label='Priority C calls', value='{calls_C_2016|int} → {calls_C_2025|int} ({calls_C_chg|spct})', source=SRC['police'] + '#calls'),
             dict(label='Median response, Priority A', value='{med_A_2016|mins} → {med_A_2025|mins}', source=SRC['police'] + '#median_recv_to_onscene_min'),
             dict(label='Median response, Priority B', value='{med_B_2016|mins} → {med_B_2025|mins}', source=SRC['police'] + '#median_recv_to_onscene_min'),
             dict(label='Real Police operating spending, FY2016 → FY2025', value='{sp_chg|spct}', source=SRC['dept_fy'] + '#actual_oper_all_real (POL)'),
         ],
         chart=dict(type='dumbbell', title='Median police response time, FY2016 vs FY2025',
                    subtitle='Minutes from 911 call received to first officer on scene, by final priority',
                    x=dict(label='Priority', values='@CH:cats'), y=dict(label='Minutes', unit='min'),
                    series=[dict(name='FY2016', values='@CH:a'), dict(name='FY2025', values='@CH:b')],
                    annotations=[], highlight='FY2025',
                    note='Source: Law Enforcement Dispatched Calls for Service: Closed (DataSF 2zdj-bwza): 911-originated, Police agency, duplicates removed. ' + DEM_NOTE),
         robustness=dict(verdict='robust', checks=[
             'From FY2019 instead: Priority A {med_A_2019|mins} → {med_A_2025|mins}; Priority B {med_B_2019|mins} → {med_B_2025|mins}.',
             '90th percentile, Priority A: {p90_A_2016|mins} → {p90_A_2025|mins}.',
             'The delay is in travel, not call handling: Priority A dispatch-to-scene {d2o_A_2016|mins} → {d2o_A_2025|mins}, while call-to-dispatch was {r2d_A_2016|mins} → {r2d_A_2025|mins}.'],
             what_could_make_it_wrong='Some lower-priority calls now go to non-police responders (such as street crisis teams) or online reports, so the remaining calls may be harder or farther away; changes in how calls are prioritized could shift which calls count as Priority A or B.'),
         caveats=['Priority C median response improved after FY2023 but is still above FY2016.',
                  'Response times measure speed, not the outcome of the call.'],
         explore=dict(view='pf-outcomes', params={'dept': 'POL', 'years': '2016-2025'}, label='See Police measures'),
         departments=['POL'], tags=['response times', '911', 'police']),

    # 6 ------------------------------------------------------------------------------------------------------------------
    dict(key='grants', id='city-grants-tripled-real', theme='spending-growth',
         title='City grants to outside organizations hit {tot_2025|bil2}, {real_x|x1} times FY2013 after inflation',
         dek='Spending in the City Grant Program category rose from {tot_2013|mil} in FY2013 to {tot_2025|bil2} in FY2025 ({real_x|x1} times in real terms), '
             'from {share_2013|pct} to {share_2025|pct} of direct operating spending. The homelessness, children\'s and early-education departments account for most of it.',
         why_it_matters='Much of the growth follows voter-approved taxes for homelessness and early childhood and the move of First 5 funds into the city budget. Those programs work mainly through '
                        'nonprofits and other providers, which makes contract and grant monitoring a larger part of how the city ensures results. General Fund-supported grants have fallen {gf_chg_23_26|apct} '
                        'from their FY2023 peak, while total grants held near {tot_2026|bil2}.',
         numbers=[
             dict(label='City Grant Program spending, FY2013 → FY2025 (nominal)', value='{tot_2013|mil} → {tot_2025|bil2}', source=SRC['cube'] + '#char_class=grants'),
             dict(label='Real growth', value='{real_2013|mil} → {real_2025|bil2} ({real_x|x1} times)', source=SRC['cube'] + '; ' + SRC['ctx']),
             dict(label='Share of direct operating spending', value='{share_2013|pct} → {share_2025|pct}', source=SRC['cube']),
             dict(label='Largest grant-making departments, FY2025', value='HSH {HOM_2025|mil}; Children, Youth & Families {CHF_2025|mil}; Early Childhood {DEC_2025|mil}; MOHCD {MYR_2025|mil}', source=SRC['cube']),
             dict(label='General Fund-supported grants only, FY2023 → FY2026 (nominal)', value='{gf_2023|mil} → {gf_2026|mil} ({gf_chg_23_26|spct})', source=SRC['cube'] + '#gf'),
         ],
         chart=dict(type='stacked', title='City grants to outside organizations, by department',
                    subtitle='City Grant Program spending, real FY2026 dollars, millions',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='$ millions (real)', unit='$M'),
                    series=[dict(name='Homelessness & Supportive Housing', values='@CH:HOM'), dict(name='Children, Youth & Families', values='@CH:CHF'),
                            dict(name='Early Childhood', values='@CH:DEC'), dict(name='Mayor (incl. MOHCD)', values='@CH:MYR'),
                            dict(name='Human Services', values='@CH:HSA'), dict(name='Economic & Workforce Dev.', values='@CH:ECN'),
                            dict(name='All other', values='@CH:other')],
                    annotations=[dict(x=2017, label='HSH created'), dict(x=2023, label='Early Childhood created')], highlight='',
                    note='Source: Spending and Revenue (DataSF bpnb-jwfb), character "City Grant Program". Nonprofit contracts booked as professional services are not included. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Excluding the two new departments (HSH and Early Childhood): still {exn_real_x|x1} times in real terms.',
             'Not a relabeling of existing contracts: if professional-services contracts had been reclassified as grants, other non-personnel spending in these departments would have fallen; instead it rose from {np_real_2013|mil} to {np_real_2025|mil} (real).',
             'Held through FY2026 at {tot_2026|bil2}.'],
             what_could_make_it_wrong='Early Childhood brought in First 5 funds that earlier sat outside the city\'s budget, so part of the rise is a change in what the budget covers.'),
         caveats=['Grants are one of several ways the city pays nonprofits; many nonprofit contracts are booked as professional services.',
                  'Recipients include child-care providers and other organizations, not only community nonprofits. The nonprofit dashboard tracks payments to individual organizations.'],
         explore=dict(view='pf-spending', params={'dept': 'HOM,CHF,DEC,MYR,HSA,ECN', 'years': '2013-2026'}, label='See spending by category'),
         departments=['HOM', 'CHF', 'DEC', 'MYR', 'HSA', 'ECN'], tags=['nonprofits', 'grants', 'spending mix']),

    # 7 ------------------------------------------------------------------------------------------------------------------
    dict(key='gf', id='pandemic-step-up-persisted', theme='spending-growth',
         title='General Fund spending per resident jumped {chg_19_21|apct} in the pandemic and has stayed near that level',
         dek='Real General Fund operating spending per resident rose from {pr_2019|usd} in FY2019 to {pr_2021|usd} in FY2021 and was {pr_2025|usd} in FY2025 '
             'and {pr_2026|usd} in FY2026. Over the longer run it is up {chg_13_25|apct} since FY2013.',
         why_it_matters='Spending did not return to its pre-pandemic level, though these data do not show whether pandemic programs continued or other costs, such as new programs, '
                        'voter-required set-asides and wage increases, took their place. Part of the per-resident rise is a smaller population ({pop_chg|spct} since FY2019); '
                        'in total real dollars the General Fund is up {real_tot_chg_19_25|apct}.',
         surprise='Pandemic response costs, some later reimbursed by FEMA and other aid, would be expected to fade after FY2022; spending per resident did not fall back.',
         numbers=[
             dict(label='Real GF operating spending per resident, FY2019 → FY2021', value='{pr_2019|usd} → {pr_2021|usd} ({chg_19_21|spct})', source=SRC['cube'] + '#gf; ' + SRC['ctx']),
             dict(label='FY2021 → FY2026', value='{pr_2021|usd} → {pr_2026|usd} ({chg_21_26|spct})', source=SRC['cube'] + '#gf'),
             dict(label='FY2013 → FY2025', value='{pr_2013|usd} → {pr_2025|usd} ({chg_13_25|spct})', source=SRC['cube'] + '#gf'),
             dict(label='Population (CA DOF), FY2019 → FY2025', value='{pop_2019|int} → {pop_2025|int} ({pop_chg|spct})', source=SRC['ctx']),
         ],
         chart=dict(type='line', title='General Fund operating spending per resident',
                    subtitle='Real FY2026 dollars per resident; excludes capital, debt service and overhead allocations',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='$ per resident (real)', unit='$'),
                    series=[dict(name='Per resident', values='@CH:per_res')],
                    annotations=[dict(x=2020, label='COVID-19'), dict(x=2021, label='New plateau')], highlight='Per resident',
                    note='Source: Spending and Revenue (DataSF bpnb-jwfb), General Fund; population CA DOF E-4. ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'National CPI-U: {chg_us_13_25|spct} FY2013–FY2025.',
             'Census population instead of DOF: {chg_census_13_25|spct}.',
             'Excluding all work orders between departments (a lower bound): {chg_exwo_13_25|spct} FY2013–FY2025, and {chg_exwo_19_21|spct} FY2019–FY2021.'],
             what_could_make_it_wrong='Some pandemic costs were later reimbursed by FEMA and state and federal aid, which the ledger records as revenue rather than lower spending.'),
         caveats=['General Fund only; enterprises such as the Airport and Muni are excluded.'],
         explore=dict(view='pf-overview', params={'years': '2013-2026'}, label='See citywide spending trends'),
         departments=['GEN'], tags=['pandemic', 'per resident', 'General Fund']),

    # 8 ------------------------------------------------------------------------------------------------------------------
    dict(key='vacancy', id='unfilled-positions-doubled', theme='staffing',
         title='The gap between budgeted and paid positions doubled after the pandemic, peaking at {vrate_2023|pct}',
         dek='Paid staffing ran {vrate_min_13_18|pct} to {vrate_max_13_18|pct} below budgeted positions in FY2013–17, but {vrate_min_21_24|pct} to {vrate_max_21_24|pct} below in FY2021–24 '
             '({vac_min_21_24|int} to {vac_max_21_24|int} FTEs). By FY2026 the gap was back to {vrate_2026|pct}.',
         why_it_matters='Gaps this large can strain services and leave salary money unspent during the year, which typically helps cover overtime (see the overtime findings). '
                        'The pandemic hiring freeze, a slow civil-service hiring process and a tight labor market are the usual explanations.',
         numbers=[
             dict(label='Budgeted positions (gross FTE), FY2023', value='{bud_2023|int}', source=SRC['fte'] + '#budget_fte_gross'),
             dict(label='Paid FTE, FY2023', value='{act_2023|int} ({vrate_2023|pct} below budget)', source=SRC['fte'] + '#actual_fte'),
             dict(label='Gap between gross budgeted and paid FTE, FY2013–17 vs FY2021–24', value='{vrate_min_13_18|pct}–{vrate_max_13_18|pct} vs {vrate_min_21_24|pct}–{vrate_max_21_24|pct}', source=SRC['fte']),
             dict(label='Paid FTE below gross budgeted FTE, FY2023: SFMTA / Sheriff / Police', value='{MTA_vrate_2023|pct} / {SHF_vrate_2023|pct} / {POL_vrate_2023|pct}', source=SRC['fte_dept']),
         ],
         chart=dict(type='line', title='Budgeted vs paid positions',
                    subtitle='Full-time equivalents; "net" subtracts the turnover (attrition) allowance in years the positions data publish it',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='FTE', unit='count'),
                    series=[dict(name='Budgeted (gross)', values='@CH:budgeted'), dict(name='Budgeted net of attrition', values='@CH:net'),
                            dict(name='Paid FTE', values='@CH:filled')],
                    annotations=[dict(x=2023, label='Widest gap')], highlight='Paid FTE',
                    note='Sources: Budget - FTE (DataSF 4zfx-f2ts) and Spending - FTE (43jt-u7yn). Paid FTE is unreliable in FY2018–20 and not used; the positions data carry no attrition lines for FY2019–24.'),
         robustness=dict(verdict='robust', checks=[
             'Not one department: excluding SFMTA, the largest gap, paid FTE was still {vrate_exMTA_2023|pct} below budget in FY2023.',
             'Broad-based: in FY2023, {n_big_gap10|int} of {n_big|int} departments with at least {hundred_fte|int} budgeted FTEs ran more than {ten|pct} below budget.',
             'By FY2026 the gap narrowed to about {vac_2026|r100} FTEs ({vrate_2026|pct}), close to the pre-pandemic range.'],
             what_could_make_it_wrong='Paid FTE counts paid hours, not people in positions, and gross budgets include a normal turnover allowance (about a tenth of positions in years it is published), so part of any gap is expected.'),
         caveats=['Paid FTE figures for FY2018–20 are unreliable and are not used.'],
         explore=dict(view='pf-staffing', params={'years': '2013-2026'}, label='See budgeted vs filled positions'),
         departments=['MTA', 'SHF', 'POL'], tags=['vacancies', 'hiring']),

    # 9 ------------------------------------------------------------------------------------------------------------------
    dict(key='ot_budget', id='overtime-over-budget-every-year', theme='budgeting-practice',
         title='Citywide overtime has exceeded its adopted budget every year for {n_over|int} years',
         dek='Every year from FY2010 to FY2026, citywide overtime spending exceeded the amount in the original adopted budget, coming in at {min_ratio|x2} to {max_ratio|x2} times the budgeted figure. '
             'The cumulative difference is {cum_over|bil2} (nominal).',
         why_it_matters='A line that comes in over budget in the same direction every year suggests the adopted overtime figure works as a planning placeholder rather than a forecast. The difference is typically covered '
                        'by savings from vacant positions (see the budgeted-vs-paid positions finding) and mid-year supplemental appropriations. The FY2026 budget narrowed the gap by raising overtime budgets to {bud_2026|mil} ({bud_x_13_26|x1} times FY2013), though spending still came in at {min_ratio|x2} times the budget.',
         numbers=[
             dict(label='Years overtime spending exceeded the adopted overtime budget, FY2010–FY2026', value='{n_over|int} of {n_years|int}', source=SRC['long'] + '#overtime objects, budget vs actual'),
             dict(label='Ratio range (actual ÷ budget)', value='{min_ratio|x2} ({min_fy|fy}) to {max_ratio|x2} ({max_fy|fy})', source=SRC['long']),
             dict(label='FY2025 overtime, actual vs budget (ledger)', value='{act_2025|mil} vs {bud_2025|mil}', source=SRC['long']),
             dict(label='Cumulative difference, FY2010–FY2026 (nominal)', value='{cum_over|bil2}', source=SRC['long']),
         ],
         chart=dict(type='line', title='Citywide overtime: original adopted budget vs actual',
                    subtitle='Nominal $ millions; ledger objects named Overtime',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='$ millions (nominal)', unit='$M'),
                    series=[dict(name='Actual', values='@CH:actual'), dict(name='Adopted budget', values='@CH:budget')],
                    annotations=[dict(x=2022, label='Widest gap')], highlight='Actual',
                    note='Sources: Budget (DataSF xdgd-c79v, original adopted Annual Appropriation Ordinance) and Spending and Revenue (bpnb-jwfb).'),
         robustness=dict(verdict='robust', checks=[
             'Excluding Police: still over budget in {n_over_expol|int} of {n_years|int} years.',
             'Payroll overtime (Employee Compensation, a separate source) also exceeds the adopted overtime budget in {n_over_payroll|int} of {n_payroll_years|int} years.',
             'FY2026, a complete fiscal year, is the closest yet at {min_ratio|x2} times, after the budget was raised.'],
             what_could_make_it_wrong='Revised budgets after supplemental appropriations are not in the published data, so the gap against the final approved amount is smaller than shown.'),
         caveats=['Compares with the original adopted budget, not the revised budget.',
                  'Ledger overtime ({act_2025|mil} in FY2025) is lower than payroll-record overtime ({pay_ot_2025|mil}) because the two sources classify some pay differently.'],
         explore=dict(view='pf-gaps', params={'years': '2010-2026'}, label='See budget vs actual by department'),
         departments=['POL', 'SHF', 'FIR', 'MTA'], tags=['overtime', 'budget accuracy']),

    # 10 -----------------------------------------------------------------------------------------------------------------
    dict(key='ot100k', id='overtime-over-100k-pay-records', theme='staffing',
         title='Pay records with over {thr|usd} in overtime rose {x_real|x1} times since FY2013, to {n_2025|int}',
         dek='Payroll records with more than {thr|usd} of overtime (in FY2025 dollars) rose from {nreal_2013|int} in FY2013 and {nreal_2019|int} in FY2019 to {n_2025|int} in FY2025. '
             'In FY2025 they received {share_2025|pct} of all overtime pay, up from {sharereal_2013|pct} for the comparable group in FY2013.',
         why_it_matters='Overtime is increasingly concentrated in a small group, mostly in Police ({POL_2025|int}), the Sheriff ({SHF_2025|int}) and Fire ({FIR_2025|int}). '
                        'Very high individual overtime raises questions about fatigue and safety, alongside the cost. In these round-the-clock services overtime is often required to meet minimum staffing while positions are vacant.',
         numbers=[
             dict(label='Pay records with overtime over {thr|usd} (FY2025 dollars)', value='{nreal_2013|int} (FY2013) → {nreal_2019|int} (FY2019) → {n_2025|int} (FY2025)', source=SRC['ec'] + '#Overtime'),
             dict(label='Same count at a fixed nominal {thr|usd}', value='{n_2013|int} → {n_2019|int} → {n_2025|int}', source=SRC['ec'] + '#Overtime'),
             dict(label='Share of all overtime pay going to records above the inflation-adjusted threshold, FY2013 → FY2025', value='{sharereal_2013|pct1} → {share_2025|pct1}', source=SRC['ec']),
             dict(label='Police, Sheriff and Fire share of the group, FY2025', value='{ps_share_2025|pct}', source=SRC['ec'] + '#Department Code'),
         ],
         chart=dict(type='stacked', title='Pay records with more than {thr|usd} in overtime pay',
                    subtitle='Per fiscal year, by department; threshold in FY2025 dollars (Bay Area CPI-U)',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Pay records', unit='count'),
                    series=[dict(name='Police', values='@CH:POL'), dict(name='Sheriff', values='@CH:SHF'), dict(name='Fire', values='@CH:FIR'),
                            dict(name='All other', values='@CH:other')],
                    annotations=[dict(x=2022, label='Post-pandemic surge')], highlight='Police',
                    note='Source: Employee Compensation (DataSF 88g8-5mnd), fiscal years. One record = one employee in one job in one department; employees are not named.'),
         robustness=dict(verdict='robust', checks=[
             'At a fixed nominal {thr|usd}: {n_2013|int} → {n_2025|int}; the inflation-adjusted threshold is about {thr_2013|usd100} in FY2013.',
             'Excluding Police (nominal threshold): {exPOL_2019|int} in FY2019 → {exPOL_2025|int} in FY2025.',
             'FY2026 continues the rise: {nreal_2026|int} records above the inflation-adjusted threshold.'],
             what_could_make_it_wrong='Pay raises push hourly overtime rates up, so part of the rise reflects higher pay per overtime hour, not only more hours.'),
         caveats=['Some high overtime is reimbursed by outside parties (for example Police Section 10B events).',
                  'Payroll overtime ({ot_2025|mil} in FY2025) is higher than ledger overtime ({ledger_ot_2025|mil}) because the two sources classify some pay differently.'],
         explore=dict(view='pf-staffing', params={'dept': 'POL,SHF,FIR', 'years': '2013-2026'}, label='See overtime by department'),
         departments=['POL', 'SHF', 'FIR'], tags=['overtime', 'concentration']),

    # 11 -----------------------------------------------------------------------------------------------------------------
    dict(key='muni_fares', id='muni-fares-cover-far-less', theme='other',
         title='Muni fares covered {rr_2019|pct} of operating costs in FY2019 and {rr_2024|pct} in FY2024',
         dek='Fare revenue reported to the National Transit Database fell from {ntd_fares_2019|mil} to {ntd_fares_2024|mil} while operating costs rose from '
             '{ntd_opex_2019|mil} to {ntd_opex_2024|bil2}. City-ledger fares have since partly recovered, to {fares_2026|mil} in FY2026 vs {fares_2019|mil} in FY2019, but transit pass revenue was still {pass_chg|apct} below FY2019 in FY2025.',
         why_it_matters='Ridership remains well below 2019 while costs have risen with wages and inflation, and riders who commute fewer days a week likely buy fewer passes. '
                        'Federal and state pandemic relief helped fill the gap; as it runs out, the difference has to come from some mix of parking revenue, the General Fund, state or regional funding, new taxes, cost savings or service cuts, which is the core of the SFMTA budget debate.',
         numbers=[
             dict(label='Fares ÷ operating expenses (NTD), FY2019 → FY2024', value='{rr_2019|pct1} → {rr_2024|pct1}', source=SRC['ntd'] + '#Fares, Operating Expenses'),
             dict(label='Unlinked trips, FY2019 → FY2024', value='{trips_2019|cm1} → {trips_2024|cm1} ({trips_chg|spct})', source=SRC['ntd']),
             dict(label='Fare revenue per trip', value='{fare_per_trip_2019|usd2} → {fare_per_trip_2024|usd2}', source=SRC['ntd']),
             dict(label='Transit pass revenue in the city ledger, FY2019 → FY2025', value='{pass_2019|mil} → {pass_2025|mil} ({pass_chg|spct})', source=SRC['sr'] + '#MTA revenue, Transit Pass Revenue'),
         ],
         chart=dict(type='line', title='Share of Muni operating costs paid by fares',
                    subtitle='Percent: NTD fares ÷ NTD operating expenses, and city-ledger fares ÷ SFMTA operating spending',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='% of operating costs', unit='%'),
                    series=[dict(name='NTD', values='@CH:ntd'), dict(name='City ledger', values='@CH:ledger')],
                    annotations=[dict(x=2021, label='COVID-19')], highlight='NTD',
                    note='Sources: FTA National Transit Database TS2.2 (ntd_id 90015; through FY2024); Spending and Revenue (DataSF bpnb-jwfb) fare objects (cash, passes, cable car, tokens, paratransit) vs SFMTA operating spending, which also covers parking and streets.'),
         robustness=dict(verdict='robust', checks=[
             'City ledger instead of NTD: fares covered {lrr_2019|pct1} of SFMTA operating spending in FY2019 and {lrr_2024|pct1} in FY2024.',
             'Real fare revenue FY2019–FY2025: {fares_real_chg|spct}.',
             'Partial recovery since: ledger fares {fares_2025|mil} in FY2025 and {fares_2026|mil} in FY2026, vs {fares_2019|mil} in FY2019.'],
             what_could_make_it_wrong='Fare policy (free or discounted fares for youth and some seniors and people with disabilities) and fare evasion lower revenue per trip regardless of ridership; operating costs are nominal, so part of their rise is inflation.'),
         caveats=['NTD data run through FY2024.'],
         explore=dict(view='pf-cost', params={'dept': 'MTA', 'years': '2015-2025'}, label='See Muni cost per trip and per hour'),
         departments=['MTA'], tags=['Muni', 'fares', 'transit']),

    # 12 -----------------------------------------------------------------------------------------------------------------
    dict(key='survey', id='survey-muni-up-everything-else-down', theme='outcomes',
         title='In the 2023 City Survey, Muni was the only one of {n_q|int} ratings to improve from 2019',
         dek='Of {n_q|int} service and safety ratings asked in both years, {n_down|int} fell. Muni\'s A-or-B share rose from {muni_rate_2019|pct} to {muni_rate_2023|pct}, while '
             'the library fell from {lib_rate_2019|pct} to {lib_rate_2023|pct} and feeling safe during the day from {safe_day_2019|pct} to {safe_day_2023|pct}.',
         why_it_matters='Ratings did not move with budgets: the Library\'s real operating spending rose {lib_real_chg|apct} between FY2019 and FY2023 while its grade fell, and Muni\'s grade rose despite budget stress. '
                        'Library funding is largely set by a voter-approved Charter set-aside, so it grows by formula. The survey cannot say why ratings changed; pandemic-era library closures and shorter hours, less crowded buses and trains, and changes in who uses each service are plausible factors.',
         surprise='Muni, still carrying far fewer riders than in 2019, is the one service residents rated higher.',
         numbers=[
             dict(label='Muni rated A or B, 2019 → 2023', value='{muni_rate_2019|pct} → {muni_rate_2023|pct}', source=SRC['survey'] + '#muni_rate'),
             dict(label='Library rated A or B, 2019 → 2023', value='{lib_rate_2019|pct} → {lib_rate_2023|pct}', source=SRC['survey'] + '#lib_rate'),
             dict(label='Feel safe walking alone during the day, 2019 → 2023', value='{safe_day_2019|pct} → {safe_day_2023|pct}', source=SRC['survey'] + '#safe_day'),
             dict(label='City government overall, 2019 → 2023', value='{general_rate_2019|pct} → {general_rate_2023|pct}', source=SRC['survey'] + '#general_rate'),
         ],
         chart=dict(type='dumbbell', title='Share rating each service A or B, 2019 vs 2023',
                    subtitle='Weighted percent of respondents; safety items = share feeling safe',
                    x=dict(label='Service', values='@CH:cats'), y=dict(label='% A or B', unit='%'),
                    series=[dict(name='2019', values='@CH:a'), dict(name='2023', values='@CH:b')],
                    annotations=[], highlight='Muni overall',
                    note='Source: City Survey respondent-level data (DataSF nufj-bfbw), weighted. 2019 was a phone survey; 2023 added online and in-person modes. No 2021 survey.'),
         robustness=dict(verdict='robust', checks=[
             '2023 phone respondents only (same mode as 2019): Muni {muni_phone_2023|pct}, library {lib_phone_2023|pct}.',
             'Unweighted: Muni {muni_unw_2019|pct} → {muni_unw_2023|pct}; library {lib_unw_2019|pct} → {lib_unw_2023|pct}.',
             'Muni riders only: {muni_riders_2019|pct} → {muni_riders_2023|pct}.'],
             what_could_make_it_wrong='The 2023 survey changed modes and the pandemic changed who rides Muni and uses libraries, so part of the shift is who answered, not only service quality.'),
         caveats=['Survey ratings are perceptions; measured outcomes are in the other findings.'],
         explore=dict(view='pf-outcomes', params={'dept': 'MTA,LIB', 'years': '2015-2025'}, label='See service measures'),
         departments=['MTA', 'LIB'], tags=['City Survey', 'satisfaction']),

    # 13 -----------------------------------------------------------------------------------------------------------------
    dict(key='library', id='library-visits-down-borrowing-up', theme='efficiency',
         title='Library visits are {vis_chg|apct} below FY2017, but e-books lifted total borrowing {circ_chg|apct}',
         dek='Visits fell from {vis_2017|cm1} in FY2017 to {vis_2025|cm1} in FY2025, while circulation of physical books plus e-books and e-media rose from {circ_2017|cm1} to {circ_2025|cm1}; '
             'physical circulation fell {phys_chg|apct} and e-media rose {ebk_x|x1} times. Real Library spending rose {sp_chg|apct}.',
         why_it_matters='By the Library\'s own headline unit cost, spending per visit, it looks {pv_chg|apct} more expensive; per item borrowed it is {pc_chg|apct} cheaper. '
                        'Which measure the city uses changes the story about value for money.',
         surprise='Judged by cost per visit, the Library looks {pv_chg|apct} more expensive than in FY2017; judged by cost per item borrowed, {pc_chg|apct} cheaper.',
         numbers=[
             dict(label='Visits, FY2017 → FY2025', value='{vis_2017|cm2} → {vis_2025|cm2} ({vis_chg|spct})', source=SRC['pm'] + '#Number of persons entering...'),
             dict(label='Circulation (physical books plus e-books and e-media)', value='{circ_2017|cm1} → {circ_2025|cm1} ({circ_chg|spct})', source=SRC['pm'] + '#Circulation of physical books; eBooks and eMedia'),
             dict(label='Real spending per visit', value='{pv_2017|usd2} → {pv_2025|usd2}', source=SRC['dept_fy'] + '#actual_oper_all_real (LIB); ' + SRC['pm']),
             dict(label='Real spending per item borrowed', value='{pc_2017|usd2} → {pc_2025|usd2}', source=SRC['dept_fy'] + '; ' + SRC['pm']),
         ],
         chart=dict(type='line', title='Fewer visits, more borrowing',
                    subtitle='Index, FY2017 = 100',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Index (FY2017 = 100)', unit='index'),
                    series=[dict(name='E-book and e-media circulation', values='@CH:ebooks'), dict(name='Real spending', values='@CH:spend'),
                            dict(name='Physical circulation', values='@CH:physical'), dict(name='Visits', values='@CH:visits')],
                    annotations=[dict(x=2021, label='Branches closed (COVID-19)')], highlight='Visits',
                    note='Sources: Citywide Performance Metrics (DataSF 6dpt-7w23), Public Library; Spending and Revenue (bpnb-jwfb). ' + REAL_NOTE),
         robustness=dict(verdict='robust', checks=[
             'From FY2019: visits {vis_chg_19|spct}, circulation {circ_chg_19|spct}.',
             'Physical circulation alone is {phys_chg|spct} vs FY2017, far smaller than the fall in visits.',
             'The Library\'s own published cost per visit shows the same rise: {dept_pv_2017|usd2} → {dept_pv_2025|usd2} (nominal).'],
             what_could_make_it_wrong='An e-book checkout costs the Library a license fee and is not equivalent to a visit that includes programs, study space or computer use.'),
         caveats=['Visits are still recovering after pandemic closures and remain {vis_chg_19|apct} below FY2019.',
                  'Part of the spending rise pays for e-book and e-media licenses, which cost the Library per copy or per checkout.'],
         explore=dict(view='pf-cost', params={'dept': 'LIB', 'years': '2017-2025'}, label='See Library cost per unit'),
         departments=['LIB'], tags=['library', 'unit cost']),

    # 14 -----------------------------------------------------------------------------------------------------------------
    dict(key='targets', id='targets-eased-after-misses', theme='measurement',
         title='After missing a target, departments were {ratio|x1} times as likely to ease it as after meeting it',
         dek='Across {n_measures|int} measures in the Controller\'s dataset, targets were eased (made easier to meet by more than {five|pct}) after {eased_miss|pct1} of misses but only {eased_hit|pct1} of hits. '
             'They were tightened after {raised_hit|pct1} of hits and {raised_miss|pct1} of misses. Targets tend to follow recent results, most clearly after a miss.',
         why_it_matters='Targets that follow results make "share of targets met" a weak signal of performance: a measure can be met every year while results decline.',
         numbers=[
             dict(label='Target eased after a miss vs after a hit', value='{eased_miss|pct1} vs {eased_hit|pct1} ({ratio|x1} times)', source=SRC['targets']),
             dict(label='Target tightened after a hit vs after a miss', value='{raised_hit|pct1} vs {raised_miss|pct1}', source=SRC['targets']),
             dict(label='Year-to-year target comparisons analyzed (after a miss / after a hit)', value='{n_miss|int} / {n_hit|int}', source=SRC['targets']),
         ],
         chart=dict(type='bar', title='What happens to next year\'s target',
                    subtitle='Percent of year-to-year target comparisons, by whether the department missed or met its target (unchanged targets not shown)',
                    x=dict(label='Prior result', values='@CH:cats'), y=dict(label='% of target comparisons', unit='%'),
                    series=[dict(name='Target eased', values='@CH:eased'), dict(name='Target tightened', values='@CH:raised')],
                    annotations=[], highlight='Target eased',
                    note='Source: Citywide Performance Metrics (DataSF 6dpt-7w23), FY2013–FY2026 targets; direction of improvement from the measure map. A change counts when it exceeds {five|pct} in either direction.'),
         robustness=dict(verdict='robust', checks=[
             'Excluding measures whose targets are mechanically reset to the latest result: {ratio_excl_mech|x1} times.',
             'Holds in {depts_more|int} of {depts|int} departments with enough data.',
             'Leaving out any one department: {lodo_min|x1} to {lodo_max|x1} times.'],
             what_could_make_it_wrong='Next year\'s target is usually proposed in the spring budget process, before the current year\'s result is final, so some changes respond to earlier results or funding decisions rather than the miss itself; back-filled history may reflect later edits.'),
         caveats=['Resetting a target after a miss is often sound management when a goal proved unrealistic or funding changed; this pattern is not evidence of gaming.',
                  'Only today\'s measures are in the dataset, with their history back-filled; dropped and redefined measures are covered in the next finding.'],
         explore=dict(view='pf-integrity', params={'years': '2013-2026'}, label='See target changes and dropped measures'),
         departments=[], tags=['targets', 'performance measurement']),

    # 15 -----------------------------------------------------------------------------------------------------------------
    dict(key='redefined', id='missed-measures-redefined-more-often', theme='measurement',
         title='Missed measures were redefined {redef_rr|x1} times as often as met ones; drops showed no clear gap',
         dek='In the Controller\'s annual performance reports for FY2006–FY2019 and FY2022, {dropped_miss|pct1} of measures that missed their target were dropped from the next report vs {dropped_met|pct1} that met it, '
             'a difference too small to rule out chance. But {redef_miss|pct1} of missed measures were redefined (threshold, scope or method changed) vs {redef_met|pct1} of met ones.',
         why_it_matters='These data show no clear sign that departments drop measures they miss more often than ones they meet, though a small difference cannot be ruled out. Redefinition is somewhat more common after a miss (about {extra_redef|int} extra measures over the period) '
                        'and is often a legitimate improvement, so reports should flag it, letting readers tell a changed yardstick from a changed result.',
         numbers=[
             dict(label='Dropped after a miss vs after a hit', value='{dropped_miss|pct1} vs {dropped_met|pct1} (ratio {dropped_rr|x2}, {ci|pct} interval {dropped_lo|x2}–{dropped_hi|x2})', source=SRC['lineage']),
             dict(label='Redefined after a miss vs after a hit', value='{redef_miss|pct1} vs {redef_met|pct1} (ratio {redef_rr|x2}, {ci|pct} interval {redef_lo|x2}–{redef_hi|x2})', source=SRC['lineage']),
             dict(label='Measure-years analyzed (missed / met)', value='{n_missed|int} / {n_met|int}', source=SRC['lineage']),
         ],
         chart=dict(type='bar', title='What happens to a measure in the next annual report',
                    subtitle='Percent of measures, by whether they missed or met their target',
                    x=dict(label='Outcome in next report', values='@CH:cats'), y=dict(label='% of measures', unit='%'),
                    series=[dict(name='Missed target', values='@CH:miss'), dict(name='Met target', values='@CH:met')],
                    annotations=[], highlight='Missed target',
                    note='Source: measure lineages built from the Controller\'s annual performance reports (FY2006–FY2019, FY2022), transcribed and validated against the published FY2013 and FY2014 datasets; relations classified with Claude and spot-checked.'),
         robustness=dict(verdict='robust', checks=[
             'Stratified by report year (Mantel-Haenszel): dropped {dropped_cmh|x2}, redefined {redef_cmh|x2}.',
             'Redefinition was more common after a miss in {redef_years_higher|int} of the {redef_years|int} report years with results to compare.',
             'The redefinition ratio\'s {ci|pct} interval ({redef_lo|x2}–{redef_hi|x2}) excludes one; the drop ratio\'s ({dropped_lo|x2}–{dropped_hi|x2}) does not.'],
             what_could_make_it_wrong='Links between years and the "redefined" labels come from an AI-assisted comparison of titles and definitions; a blind re-run agreed on nearly all pairs but missed some links, and a missed link turns a redefinition into an apparent drop.'),
         caveats=['Internal administrative measures are excluded.', 'Redefining a measure is often a legitimate improvement.'],
         explore=dict(view='pf-integrity', params={}, label='See dropped and redefined measures'),
         departments=[], tags=['performance measurement', 'redefinitions']),

    # 16 -----------------------------------------------------------------------------------------------------------------
    dict(key='bonds', id='seawall-bond-spend-down', theme='capital',
         title='The 2018 Seawall bond is {sw_share|pct} spent after {sw_years|x1} years, its pace tied largely to a federal study',
         dek='The {sw_bud|mil} Embarcadero Seawall bond had spent {sw_exp|mil} by June 2025 while the project remains in the design phase tied to a federal flood study. '
             'The 2020 Earthquake Safety and Emergency Response bond had spent {es_share|pct}; the Controller\'s report lists three of its five components a year or more behind schedule, one complete and one ahead. '
             'Other city bond programs at a similar age ({win_lo|x1} to {win_hi|x1} years) had spent {peer_min|pct} to {peer_max|pct}.',
         why_it_matters='Voters approved these bonds for seismic safety. Bonds already sold but not yet spent carry interest costs, partly offset by investment earnings on the unspent proceeds. The Seawall\'s timeline is set largely by the Army Corps flood study, '
                        'which pushed design milestones back; the city sells bonds in stages as work becomes ready.',
         numbers=[
             dict(label='Seawall bond spent (excluding commitments), as of June 30, 2025', value='{sw_exp|mil} of {sw_bud|mil} ({sw_share|pct1})', source=SRC['bonds']),
             dict(label='Seawall spent of bonds already issued', value='{sw_of_issued|pct} of {sw_issued|mil}', source=SRC['bonds']),
             dict(label='ESER 2020 spent', value='{es_share|pct1} of {es_bud|mil1} after {es_years|x1} years', source=SRC['bonds']),
             dict(label='Other programs {win_lo|x1}–{win_hi|x1} years after approval ({peer_prog|int} programs, {peer_n|int} snapshots)', value='{peer_min|pct} to {peer_max|pct}', source='performance/data/interim/an_go_bond_pace.csv (DataSF m793-kis4, FY22-23 and FY24-25 snapshots)'),
         ],
         chart=dict(type='hbar', title='Share of each GO bond program spent, as of June 2025',
                    subtitle='Cash expended ÷ program budget; programs at least three years old',
                    x=dict(label='Bond program (year approved)', values='@CH:cats'), y=dict(label='% spent', unit='%'),
                    series=[dict(name='% spent', values='@CH:values')],
                    annotations=[], highlight='Embarcadero Seawall Earthquake Safety (2018)',
                    note='Source: GO Bond program status (DataSF m793-kis4), FY24-25 snapshot; consistent with the Controller\'s GO Bond Program Report FY2023–24 and FY2024–25.'),
         robustness=dict(verdict='robust', checks=[
             'Including encumbered commitments: Seawall {sw_enc_share|pct}, ESER 2020 {es_enc_share|pct}.',
             'Independent source: the Controller\'s GO Bond Program Report gives the same shares with commitments (Seawall {rep_sw|pct}; ESER 2020 {rep_es|pct}).',
             'Measured against bonds already issued rather than the full authorization, the Seawall has spent {sw_of_issued|pct}.'],
             what_could_make_it_wrong='Large civil works spend slowly at first and quickly during construction; the Seawall is still in planning and design, as the federal cost-share process requires.'),
         caveats=['Unusual pace is not improper; the Controller\'s report attributes the Seawall delay to the extended Army Corps flood study.',
                  'The peer comparison is thin, drawn from a few programs and two snapshot dates.'],
         explore=dict(view='pf-gaps', params={'years': '2013-2026'}, label='See budget vs actual (the bond detail is in the evidence above)'),
         departments=['PRT', 'DPW', 'FIR', 'POL', 'DEM'], tags=['bonds', 'capital', 'seawall']),

    # 17 -----------------------------------------------------------------------------------------------------------------
    dict(key='execution', id='chronic-budget-gaps-by-department', theme='budgeting-practice',
         title='Public Health spent over {five|pct} above its adopted budget in {DPH_over105|int} of {DPH_n|int} years, mostly hospital funds',
         dek='In FY2013–FY2025, Public Health\'s operating spending exceeded its original adopted budget by more than {five|pct} in {DPH_over105|int} of {DPH_n|int} years ({DPH_cum|bil2} net over the period, {DPH_cum_pct|pct} of its budgets); '
             'almost all of that was outside the General Fund, in its hospital enterprise funds. The City Attorney was over by more than {five|pct} in {CAT_over105|int} years, while the City Administrator came in more than {five|pct} under in {ADM_under95|int} years, Building Inspection in {DBI_under95|int} and the Port in {PRT_under95|int}.',
         why_it_matters='Persistent gaps in the same direction mean the original adopted budget is a weak forecast for these departments. Spending above it is authorized through supplemental appropriations and extra revenue. '
                        'Unspent amounts often stay in restricted funds, such as permit fees or Port revenue, rather than returning to the General Fund; they can reflect vacancies, delayed projects or reserves, but they still make the adopted budget a poor guide to actual spending.',
         numbers=[
             dict(label='Public Health: years more than {five|pct} above adopted operating budget', value='{DPH_over105|int} of {DPH_n|int}; median {DPH_med|pct}', source=SRC['dept_fy'] + '#actual_opfund,budget_opfund (DPH)'),
             dict(label='Public Health spending above adopted budget, net over FY2013–FY2025: General Fund vs other funds', value='{DPH_gf_over_amt|mil} vs {DPH_nongf_over_amt|mil}', source=SRC['long'] + '#DPH, Operating fund category'),
             dict(label='City Attorney: years more than {five|pct} above budget', value='{CAT_over105|int} of {CAT_n|int}; median {CAT_med|pct}', source=SRC['dept_fy'] + '#(CAT)'),
             dict(label='City Administrator: years more than {five|pct} below budget', value='{ADM_under95|int} of {ADM_n|int}; median {ADM_med|pct}; {ADM_cum|amil} under budget in total', source=SRC['dept_fy'] + '#(ADM)'),
             dict(label='Building Inspection / Port: years more than {five|pct} below budget', value='{DBI_under95|int} / {PRT_under95|int} of {DBI_n|int}', source=SRC['dept_fy']),
         ],
         chart=dict(type='hbar', title='Median actual spending as a share of the original adopted operating budget, FY2013–FY2025',
                    subtitle='Operating fund category; {hundred|pct} = spent exactly the adopted budget',
                    x=dict(label='Department', values='@CH:cats'), y=dict(label='% of adopted budget', unit='%'),
                    series=[dict(name='Median execution', values='@CH:values')],
                    annotations=[], highlight='Public Health',
                    note='Sources: Budget (DataSF xdgd-c79v, original adopted) and Spending and Revenue (bpnb-jwfb), Operating fund category only (annual appropriations).'),
         robustness=dict(verdict='robust', checks=[
             'In General Fund dollars alone, Public Health was above its adopted budget in only {DPH_gf_over|int} of {DPH_n|int} years (by more than {five|pct} in {DPH_gf_over105|int}); the excess is concentrated in hospital funds backed by patient revenue.',
             'With a looser test (any amount over budget), Public Health was over in {DPH_over|int} years and the Fire Department in {FIR_over|int}, but Fire by far less ({FIR_med|pct} median).',
             'Enterprises also came in under budget in total (SFMTA by {MTA_cum|abil2}, the Airport by {AIR_cum|abil2} over the period) but rarely by more than {five|pct} in a year (SFMTA {MTA_under95|int}, Airport {AIR_under95|int} years).'],
             what_could_make_it_wrong='The adopted budget excludes supplemental appropriations and grants accepted during the year; the revised budgets the Board approves later are not in the published data.'),
         caveats=['Compares with the original adopted budget, which is what the Board votes on in June.',
                  'Much of the City Attorney\'s work is billed to other departments, and litigation costs are hard to predict; much of the City Administrator\'s budget is internal services paid for by other departments.'],
         explore=dict(view='pf-gaps', params={'dept': 'DPH,CAT,ADM,DBI,PRT', 'years': '2013-2025'}, label='See budget vs actual'),
         departments=['DPH', 'CAT', 'ADM', 'DBI', 'PRT'], tags=['budget accuracy', 'supplementals']),

    # 18 -----------------------------------------------------------------------------------------------------------------
    dict(key='airport', id='airport-debt-service-half-of-spending', theme='capital',
         title='SFO\'s debt payments were {ds_2025|mil} in FY2025, {share_2025|pct} of its operating and debt spending',
         dek='Airport debt service was {ds_2025|mil} in FY2025, up from {ds_2013|mil} in FY2013. Averaged over four years to smooth out refinancing swings, it grew {avg_x|x2} times in real terms. '
             'Debt payments were {share_2025|pct} of the Airport\'s operating and debt spending, up from {share_2013|pct}, and {ds_pay_x|x1} times its salaries and benefits.',
         why_it_matters='The debt pays for SFO\'s multi-year capital program, including terminal rebuilding, and is repaid from airline rates and charges, passenger facility charges and concession revenue, '
                        'not the General Fund. At this scale, debt service is a major driver of what airlines pay and of how much room SFO has for future projects.',
         numbers=[
             dict(label='Airport debt service, FY2013 → FY2025 (nominal)', value='{ds_2013|mil} → {ds_2025|mil}', source=SRC['cube'] + '#AIR, char_class=debt_service'),
             dict(label='Airport salaries and benefits, FY2025', value='{pay_2025|mil}', source=SRC['cube'] + '#AIR salaries+benefits'),
             dict(label='Four-year average, real (FY2026 dollars): FY2013–16 → FY2023–26', value='{avg_13_16|mil} → {avg_23_26|mil} ({avg_x|x2} times)', source=SRC['cube'] + '; ' + SRC['ctx']),
             dict(label='Adopted debt-service budget, FY2027 and FY2028', value='{bud_2027|mil} and {bud_2028|mil}', source=SRC['long'] + '#budget'),
         ],
         chart=dict(type='line', title='Airport debt service vs payroll',
                    subtitle='Nominal $ millions',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='$ millions (nominal)', unit='$M'),
                    series=[dict(name='Debt service', values='@CH:debt'), dict(name='Salaries and benefits', values='@CH:payroll')],
                    annotations=[dict(x=2021, label='Refinancing and federal relief')], highlight='Debt service',
                    note='Source: Spending and Revenue (DataSF bpnb-jwfb), Airport Commission. Police and fire services at SFO are billed by other departments and are not in Airport payroll.'),
         robustness=dict(verdict='robust', checks=[
             'Single-year comparison FY2013–FY2025: {ds_real_x|x1} times in real terms, larger than the smoothed {avg_x|x2}.',
             'FY2026 (complete year) debt service was {ds_2026|mil}, and the adopted budgets keep it at {bud_2027|mil} or more in FY2027–28.',
             'In the adopted budgets (a separate source), Airport debt service rose from {bud_2013|mil} in FY2013 to {bud_2025|mil} in FY2025 ({bud_x|x1} times, nominal).'],
             what_could_make_it_wrong='Debt service swings with refinancing and with federal pandemic relief applied to debt in FY2021, so single-year comparisons can overstate trends.'),
         caveats=['Debt service is paid from Airport revenues under its airline agreements; large airports commonly carry heavy debt.'],
         explore=dict(view='pf-spending', params={'dept': 'AIR', 'years': '2013-2026'}, label='See Airport spending'),
         departments=['AIR'], tags=['debt', 'capital', 'airport']),
]

# Ranking: importance x robustness, with related findings adjacent and favorable findings interleaved
ORDER = ['police_staffing', 'fire', 'homeless', 'pension', 'police_calls', 'grants', 'gf', 'vacancy', 'ot_budget', 'muni_fares',
         'survey', 'library', 'ot100k', 'targets', 'redefined', 'bonds', 'execution', 'airport']
INSIGHTS = sorted(INSIGHTS, key=lambda t: ORDER.index(t['key']))
