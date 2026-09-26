"""Direct outcome panel + cost per unit of outcome.

Inputs: data/raw/outcomes/* (fork B; see SOURCES.csv), data/interim/dept_fy.csv, spend_cube.parquet, measures_current.csv
Outputs:
  data/interim/outcomes_panel.csv    long: series, label, dept, fy, value, unit, direction, source, caveat
  data/interim/cost_per_outcome.csv  pair, dept, fy, numerator (nominal, real FY2026 $), denominator, unit cost, definitions
Unit costs are ratios of spending to the main output of that spending; they include all overhead in the numerator and are
not marginal costs. Where the city publishes its own unit cost we carry it alongside for cross-checking.
"""
import pandas as pd, numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

OUT = os.path.join(RAW, 'outcomes')


def panel():
    rows = []
    add = lambda **k: rows.append(k)
    f = pd.read_csv(os.path.join(OUT, 'fire_ems_response_fy.csv'))
    f = f[f.months_covered == 12]
    for col, lab, unit, dr in [('code3_medical_first_unit_median_min', 'Fire/EMS: median response to life-threatening medical calls (911 received to first unit on scene)', 'minutes', 'lower_better'),
                               ('code3_medical_first_unit_p90_min', 'Fire/EMS: 90th-percentile response to life-threatening medical calls', 'minutes', 'lower_better'),
                               ('calls_total', 'Fire/EMS: calls for service (unique calls)', 'calls', 'neutral'),
                               ('medical_calls', 'Fire/EMS: medical calls', 'calls', 'neutral')]:
        for r in f.itertuples():
            add(series='fire_' + col, label=lab, dept='FIR', fy=r.fy, value=getattr(r, col), unit=unit, direction=dr,
                source='nuek-vuh3 (fork B aggregation)', caveat='Call-level; first unit of any type')
    p = pd.read_csv(os.path.join(OUT, 'police_response_fy.csv'))
    p = p[p.months_covered == 12]
    for r in p.itertuples():
        add(series=f'police_median_{r.priority}', label=f'Police: median response to Priority {r.priority} 911 calls (received to on scene)',
            dept='POL', fy=r.fy, value=r.median_recv_to_onscene_min, unit='minutes', direction='lower_better', source='2zdj-bwza', caveat='')
        add(series=f'police_calls_{r.priority}', label=f'Police: 911-originated Priority {r.priority} calls', dept='POL', fy=r.fy,
            value=r.calls, unit='calls', direction='neutral', source='2zdj-bwza', caveat='')
    s = pd.read_csv(os.path.join(OUT, '311_citywide_fy.csv'))
    s = s[s.months_covered == 12]
    for r in s.itertuples():
        add(series='311_opened', label='311: service requests opened', dept='ADM', fy=r.fy, value=r.opened, unit='cases', direction='neutral', source='vw6y-z8j6', caveat='')
        add(series='311_closed_in_fy', label='311: service requests closed in year', dept='ADM', fy=r.fy, value=r.closed_in_fy, unit='cases', direction='neutral', source='vw6y-z8j6', caveat='')
        add(series='311_share_closed_3d', label='311: share of requests closed within 3 days (all responding agencies)', dept='CITY', fy=r.fy,
            value=r.share_closed_within_3_days, unit='share', direction='higher_better', source='vw6y-z8j6', caveat='Mix of request types changes over time')
    cm = pd.read_csv(os.path.join(OUT, '311_call_metrics_fy.csv'))
    cm = cm[cm.months == 12]
    for r in cm.itertuples():
        add(series='311_calls_answered', label='311: calls answered', dept='ADM', fy=r.fy, value=getattr(r, '_2'), unit='calls', direction='neutral', source='mwjb-biik', caveat='')
        add(series='311_svc_level_60s', label='311: share of calls answered within 60 seconds', dept='ADM', fy=r.fy, value=getattr(r, '_3') / 100.0,
            unit='share', direction='higher_better', source='mwjb-biik', caveat='')
    k = pd.read_csv(os.path.join(OUT, 'citywide_metrics_key_series.csv'))
    kd = {'hsh_exits_to_permanent_housing': ('HOM', 'people', 'higher_better'), 'library_visits': ('LIB', 'visits', 'higher_better'),
          'library_physical_circulation': ('LIB', 'items', 'higher_better'), 'library_ebook_circulation': ('LIB', 'items', 'higher_better'),
          'library_expenditure_per_visit_dept_reported': ('LIB', 'dollars (nominal)', 'lower_better'),
          'muni_on_time_performance': ('MTA', 'share', 'higher_better'), 'muni_scheduled_service_hours_delivered_pct': ('MTA', 'share', 'higher_better'),
          'muni_total_annual_ridership': ('MTA', 'trips', 'higher_better'), 'muni_customer_satisfaction': ('MTA', 'rating', 'higher_better'),
          'hsh_psh_move_ins': ('HOM', 'households', 'higher_better'), 'hsh_rrh_move_ins': ('HOM', 'households', 'higher_better'),
          'paratransit_on_time_performance': ('MTA', 'share', 'higher_better')}
    k = k[k.fy <= 2025]
    for r in k.itertuples():
        if r.series in kd and pd.notna(r.actual):
            dpt, unit, dr = kd[r.series]
            add(series=r.series, label=r.measure_title, dept=dpt, fy=r.fy, value=r.actual, unit=unit, direction=dr,
                source='6dpt-7w23', caveat='department self-reported', target=r.target)
    sc = pd.read_csv(os.path.join(OUT, 'scorecard_outcome_extracts.csv'))
    for ser, dpt, unit, dr in [('pit_count_total_homeless', 'HOM', 'people', 'lower_better'), ('pit_count_unsheltered', 'HOM', 'people', 'lower_better'),
                               ('pavement_condition_index', 'DPW', 'index 0-100', 'higher_better'),
                               ('dem_911_answered_10s_pct', 'DEM', 'share', 'higher_better'),
                               ('muni_collisions_per_100k_miles', 'MTA', 'rate', 'lower_better')]:
        x = sc[(sc.series == ser) & sc.value.notna()]
        for r in x.itertuples():
            v = r.value
            if unit == 'share' and v > 1.5:
                v = v / 100.0
            add(series=ser, label=r.measure_title, dept=dpt, fy=r.fy, value=v, unit=unit, direction=dr, source='kc49-udxn',
                caveat='PIT counts are January point-in-time counts (biennial)' if ser.startswith('pit') else '')
    n = pd.read_csv(os.path.join(OUT, 'ntd_sfmta_service_fy.csv'))
    for fy_, vrh, upt in zip(n.report_year, n['Vehicle Revenue Hours'], n['Unlinked Passenger Trips']):
        add(series='muni_vehicle_revenue_hours', label='Muni: vehicle revenue hours (NTD)', dept='MTA', fy=fy_,
            value=vrh, unit='hours', direction='higher_better', source='NTD ectq-t3k3', caveat='')
        add(series='muni_unlinked_trips_ntd', label='Muni: unlinked passenger trips (NTD)', dept='MTA', fy=fy_,
            value=upt, unit='trips', direction='higher_better', source='NTD ectq-t3k3', caveat='')
    st = pd.read_csv(os.path.join(OUT, 'street_eval_2022_2025_summary.csv'))
    st = st[st.group_type == 'Evaluation Period']
    for r in st.itertuples():
        fy = 2025 if '2025' in r.group else (2024 if 'July 2023' in r.group else (2023 if '2023' in r.group else 2022))
        add(series='street_litter_mean', label='Streets: mean street litter score (1 best to 5 worst), Controller evaluations', dept='DPW', fy=fy,
            value=r.mean_street_litter_1to5, unit='score', direction='lower_better', source='qya8-uhsz', caveat=f'period: {r.group}; 2022+ method only')
        add(series='street_feces_share', label='Streets: share of evaluated routes with any feces', dept='DPW', fy=fy,
            value=r.share_routes_any_feces, unit='share', direction='lower_better', source='qya8-uhsz', caveat=f'period: {r.group}')
    cs = pd.read_csv(os.path.join(OUT, 'city_survey_ratings_by_year.csv'))
    qd = {'lib_rate': 'LIB', 'lib_books': 'LIB', 'muni_rate': 'MTA', 'muni_reliable': 'MTA', 'rec_rate': 'REC', 'rec_grounds': 'REC',
          'inf_clean_st': 'DPW', 'inf_clean': 'DPW', 'inf_stcond': 'DPW', 'safe_day': 'POL', 'safe_night': 'POL', 'general_rate': 'CITY',
          'u311_rate': 'ADM', 'u311_svc_phone': 'ADM'}
    for r in cs.itertuples():
        if r.question in qd:
            add(series='survey_' + r.question, label=f'City Survey: {r.question} (share A or B)', dept=qd[r.question], fy=r.survey_year,
                value=r.weighted_share_A_or_B, unit='share', direction='higher_better', source='nufj-bfbw',
                caveat='Survey year (calendar); mode changed mail->phone 2015, +online 2023')
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(INTERIM, 'outcomes_panel.csv'), index=False)
    return out


def cost_pairs(panel):
    d = pd.read_csv(os.path.join(INTERIM, 'dept_fy.csv'))
    ctx = pd.read_csv(os.path.join(INTERIM, 'context_fy.csv')).set_index('fy')
    cube = pd.read_parquet(os.path.join(INTERIM, 'spend_cube.parquet'))
    oper = ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'services_other_depts', 'overhead', 'other']
    prog = cube[cube.char_class.isin(oper)].groupby(['dept', 'program_code', 'fy']).actual.sum()
    dep = d.set_index(['dept', 'fy']).actual_oper_all
    P = panel.set_index(['series', 'fy']).value
    rows = []

    def add(pair, label, dept, num_series, num_def, den_series, den_def, caveat, max_fy=2026):
        for fy in sorted(set(num_series.index) & set(den_series.index)):
            if fy > max_fy:
                continue
            num, den = num_series.get(fy), den_series.get(fy)
            if pd.isna(num) or pd.isna(den) or den <= 0 or fy > 2026:
                continue
            m = ctx.mult_bay.get(fy, np.nan)
            rows.append({'pair': pair, 'label': label, 'dept': dept, 'fy': fy, 'numerator_nominal': num, 'numerator_real': num * m,
                         'denominator': den, 'unit_cost_nominal': num / den, 'unit_cost_real': num * m / den,
                         'numerator_def': num_def, 'denominator_def': den_def, 'caveat': caveat})

    def s(series):
        return P.xs(series, level='series') if series in P.index.get_level_values(0) else pd.Series(dtype=float)
    add('library_cost_per_visit', 'Library: spending per visit', 'LIB', dep.xs('LIB'),
        'Public Library gross operating spending, all funds (actuals)', s('library_visits'), 'Library visits (6dpt, department-reported)',
        'FY2021-22 visits depressed by COVID closures; spending also funds e-circulation, programs and online services')
    n = pd.read_csv(os.path.join(OUT, 'ntd_sfmta_service_fy.csv')).set_index('report_year')
    add('muni_cost_per_revenue_hour', 'Muni: operating cost per vehicle revenue hour', 'MTA', n['Operating Expenses'],
        'NTD operating expenses, all Muni modes incl. purchased transportation (paratransit)', n['Vehicle Revenue Hours'],
        'NTD vehicle revenue hours', 'Federal NTD definitions; excludes capital, depreciation')
    add('muni_cost_per_trip', 'Muni: operating cost per passenger trip', 'MTA', n['Operating Expenses'], 'NTD operating expenses',
        n['Unlinked Passenger Trips'], 'NTD unlinked passenger trips (boardings)', 'COVID ridership collapse FY2020-22')
    add('fire_cost_per_call', 'Fire Department: spending per call for service', 'FIR', dep.xs('FIR'),
        'Fire Department gross operating spending, all funds (includes suppression, EMS, prevention, airport and port stations)',
        s('fire_calls_total'), 'Unique Fire/EMS calls for service (nuek-vuh3)', 'About 70% of calls are medical; no EMS-only budget line exists')
    pc = panel[panel.series.isin(['police_calls_A', 'police_calls_B', 'police_calls_C'])].groupby('fy').value.sum()
    add('police_cost_per_911_call', 'Police: spending per 911-dispatched call', 'POL', dep.xs('POL'),
        'Police gross operating spending, all funds (includes investigations, Airport Bureau, admin)', pc,
        '911-originated Priority A/B/C dispatched calls (2zdj-bwza)', 'Police work extends far beyond answering calls; ratio, not a unit cost')
    add('hsh_spend_per_exit', 'Homelessness & Supportive Housing: spending per person exiting to permanent housing', 'HOM', dep.xs('HOM'),
        'HSH gross operating spending, all funds', s('hsh_exits_to_permanent_housing'),
        'People exiting homelessness to permanent housing (6dpt)',
        'Most HSH spending sustains people already housed (supportive housing) and shelter; this ratio is NOT the cost of a placement')
    # legacy-program pairs (FY2010-FY2017, where program detail exists)
    p311 = prog.xs(('ADM', 'FFO')) if ('ADM', 'FFO') in prog.index.droplevel(2) else pd.Series(dtype=float)
    add('311_cost_per_request', '311 Customer Service Center: spending per service request', 'ADM', p311,
        'ADM program FFO "311 Call Center" actuals (program detail ends FY2017)', s('311_opened'), '311 service requests opened (vw6y-z8j6)',
        'Covers intake only; the cost of resolving requests falls on responding departments', max_fy=2017)
    add('311_cost_per_call', '311 Customer Service Center: spending per call answered', 'ADM', p311, 'ADM program FFO actuals',
        s('311_calls_answered'), '311 calls answered (mwjb-biik)', 'Intake cost only', max_fy=2017)
    mc = pd.read_csv(os.path.join(INTERIM, 'measures_current.csv'))
    miles = mc[mc.title == 'Number of curb miles mechanically swept'].set_index('fy').result
    bz = prog.xs(('DPW', 'BAZ')) if ('DPW', 'BAZ') in prog.index.droplevel(2) else pd.Series(dtype=float)
    add('street_env_cost_per_curb_mile_swept', 'Public Works Street Environmental Services: spending per curb mile mechanically swept', 'DPW', bz,
        'DPW program BAZ "Street Environmental Services" actuals (program detail ends FY2017)', miles,
        'Curb miles mechanically swept (6dpt)', 'Program also pays for manual cleaning, steam cleaning, graffiti and encampment work; upper bound per mile', max_fy=2017)
    out = pd.DataFrame(rows)
    # cross-checks with department-reported unit costs
    libx = s('library_expenditure_per_visit_dept_reported')
    out['dept_reported_unit_cost_nominal'] = [libx.get(fy) if p == 'library_cost_per_visit' else np.nan for p, fy in zip(out.pair, out.fy)]
    out.to_csv(os.path.join(INTERIM, 'cost_per_outcome.csv'), index=False)
    return out


if __name__ == '__main__':
    pn = panel()
    print(pn.groupby('series').fy.agg(['min', 'max', 'count']).to_string())
    c = cost_pairs(pn)
    pd.set_option('display.width', 250)
    print(c.pivot_table(index='fy', columns='pair', values='unit_cost_real').round(1).to_string())
    print(c[c.pair == 'library_cost_per_visit'][['fy', 'unit_cost_nominal', 'dept_reported_unit_cost_nominal']].to_string())
