"""Second, independent red team of the Budget-vs-outcomes headline findings.
Writes data/redteam/redteam2.json (every number used by 17b_commentary.py's red-team claims) and prints a summary.

Independence: re-derives from raw downloads (data/raw) or from the exported site files with its own filters; it does
not reuse 15_redteam.py's code paths. Where it reads an interim file (target changes) it recomputes the test itself.

Tests
 T1 General Fund operating spending per resident: base-year, deflator, population and work-order sensitivity.
 T2 Target easing after misses: exclusion of mechanically reset targets, per-department ratios, Mantel-Haenszel
    odds ratio stratified by department, leave-one-department-out, and the symmetry test (easing after a miss vs
    raising after a hit).
 T3 Fire/EMS: call-to-arrival vs dispatch-to-arrival, original vs final priority, triage re-classification, calls.
 T4 Police overtime: reimbursable (10B / sponsor-billed) and outside-funded overtime, payroll vs ledger, the
    per-hour cost-ratio assumption grid.
 T5 GO bonds: our figures vs the Controller's FY2023-24/FY2024-25 GO Bond Program Report (PDF, downloaded to
    data/raw/capital/reports/), the IRS 85%-in-3-years spend-down rule, and the city's own programs as a pace curve.
 T6 Homelessness and Supportive Housing growth, alone and with its predecessor departments.
 T7 City Survey A/B share, weighted and unweighted, from respondent-level microdata.
"""
import pandas as pd, numpy as np, os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
INT = os.path.join(ROOT, 'data', 'interim')
SITE = os.path.join(ROOT, 'data', 'site')
OUT = os.path.join(ROOT, 'data', 'redteam')
os.makedirs(OUT, exist_ok=True)
R = {'as_of': '2026-09-26', 'note': 'Independent second red team; numbers feed commentary via pipeline/17b_commentary.py.'}
S = lambda f: json.load(open(os.path.join(SITE, f)))


def site_frames():
    meta = S('meta.json')
    idx = {int(k): v for k, v in meta['deflator']['index'].items()}
    pop = {int(k): v for k, v in meta['population']['by_fy'].items()}
    C = pd.DataFrame(S('spending/cells.json')['cells'])
    return meta, idx, pop, C


def t1_gf():
    meta, idx, pop, C = site_frames()
    cpi = pd.read_csv(os.path.join(RAW, 'context', 'cpi_fy.csv')).set_index('fy')
    popc = pd.read_csv(os.path.join(RAW, 'context', 'population_fy.csv')).set_index('fy')
    op = C[(C.fund == 'gf') & ~C.char.isin(['capital', 'other'])]
    nom = op.groupby('fy').actual.sum()
    pr = {fy: nom[fy] / idx[fy] / pop[fy] for fy in range(2010, 2027)}
    us = {fy: nom[fy] * cpi.us_cpi_fyavg[2026] / cpi.us_cpi_fyavg[fy] / pop[fy] for fy in range(2010, 2027)}
    cen = {fy: nom[fy] / idx[fy] / popc.pop_census_mid[fy] for fy in range(2013, 2026) if fy in popc.index and pd.notna(popc.pop_census_mid.get(fy))}
    # raw ledger: GF "Services Of Other Depts" (work orders paid to other departments) for the double-count bound
    a = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str,
                    usecols=['Fiscal Year', 'Revenue or Spending', 'Fund Type', 'Character', 'Amount'])
    a = a[(a['Revenue or Spending'] == 'Spending') & (a['Fund Type'] == 'General Fund') & a.Character.str.lower().str.startswith('services of other', na=False)]
    wo = a.assign(v=a.Amount.astype(float)).groupby(a['Fiscal Year'].astype(int)).v.sum()
    exwo = {fy: (nom[fy] - wo[fy]) / idx[fy] / pop[fy] for fy in (2013, 2019, 2021, 2025)}
    R['t1_gf_per_resident'] = {
        'per_res_real': {fy: pr[fy] for fy in pr}, 'nominal_total': {fy: float(nom[fy]) for fy in range(2010, 2027)},
        'change_13_25': pr[2025] / pr[2013] - 1, 'change_10_25': pr[2025] / pr[2010] - 1, 'change_16_25': pr[2025] / pr[2016] - 1,
        'change_19_25': pr[2025] / pr[2019] - 1, 'change_21_25': pr[2025] / pr[2021] - 1, 'change_21_26': pr[2026] / pr[2021] - 1,
        'change_13_21': pr[2021] / pr[2013] - 1,
        'us_cpi_change_13_25': us[2025] / us[2013] - 1, 'census_pop_change_13_25': cen[2025] / cen[2013] - 1 if 2013 in cen and 2025 in cen else None,
        'work_orders_gf_nominal': {fy: float(wo[fy]) for fy in (2013, 2019, 2021, 2025)},
        'excl_work_orders_per_res': exwo, 'excl_work_orders_change_13_25': exwo[2025] / exwo[2013] - 1,
        'pop': {2013: pop[2013], 2020: pop[2020], 2022: pop[2022], 2025: pop[2025]},
        'real_total_change_13_25': (nom[2025] / idx[2025]) / (nom[2013] / idx[2013]) - 1,
        'verdict': 'survives', 'note': 'Work orders between General Fund departments are counted twice at citywide level; excluding all of them is a lower bound.'}


def t2_targets():
    c = pd.read_csv(os.path.join(INT, 'an_target_changes.csv'))
    a = pd.read_csv(os.path.join(INT, 'an_attainment.csv'))[['measure_id', 'fy', 'result']]
    prev = a.rename(columns={'result': 'prev_result'}).assign(fy=lambda x: x.fy + 1)
    c = c.merge(prev, on=['measure_id', 'fy'], how='left')
    t = c[c.fy.between(2013, 2026)].copy()
    near = lambda x, y: (x - y).abs() <= 0.01 * y.abs().clip(lower=1e-9)
    moved = t.rel_change.abs() > 0.005
    t['reset'] = moved & (near(t.next_target, t.mid_projection) | near(t.next_target, t.prev_result))
    m = t[moved].groupby('measure_id').reset.agg(['mean', 'size'])
    mech = set(m[(m['size'] >= 2) & (m['mean'] >= 0.5)].index)
    anyr = set(t[t.reset].measure_id)

    def test(s):
        mi, hi = s[s.prior_miss], s[s.prior_hit]
        return {'n_after_miss': int(len(mi)), 'n_after_hit': int(len(hi)), 'eased_after_miss': float(mi.easier.mean()),
                'eased_after_hit': float(hi.easier.mean()), 'raised_after_hit': float(hi.harder.mean()), 'raised_after_miss': float(mi.harder.mean()),
                'ratio': float(mi.easier.mean() / hi.easier.mean()), 'measures': int(s.measure_id.nunique())}
    res = {'all': test(t), 'excl_mechanical_measures': test(t[~t.measure_id.isin(mech)]),
           'excl_any_reset_measures': test(t[~t.measure_id.isin(anyr)]), 'excl_reset_changes': test(t[~t.reset]),
           'n_moved': int(moved.sum()), 'share_moved_that_reset': float(t.reset[moved].mean()),
           'n_mechanical_measures': len(mech), 'n_any_reset_measures': len(anyr), 'n_measures': int(t.measure_id.nunique()),
           'mechanical_rule': 'a target change "resets" when the new target is within 1% of the latest known result (prior-year actual or current mid-year projection); a measure is mechanical when at least half of its 2+ target moves are resets'}
    u = t[t.prior_miss | t.prior_hit].copy(); u['miss'] = u.prior_miss
    rows = []
    num = den = 0.0
    for d, s in u.groupby('dept'):
        mi, hi = s[s.miss], s[~s.miss]
        A, B, Cc, D = (mi.easier).sum(), (~mi.easier).sum(), (hi.easier).sum(), (~hi.easier).sum(); n = A + B + Cc + D
        num += A * D / n; den += B * Cc / n
        rows.append({'dept': d, 'n_miss': int(len(mi)), 'n_hit': int(len(hi)), 'eased_after_miss': float(mi.easier.mean()) if len(mi) else None,
                     'eased_after_hit': float(hi.easier.mean()) if len(hi) else None, 'raised_after_hit': float(hi.harder.mean()) if len(hi) else None})
    dd = pd.DataFrame(rows)
    big = dd[(dd.n_miss >= 20) & (dd.n_hit >= 20)]
    res['per_dept'] = {'min_n_each': 20, 'depts': int(len(big)), 'depts_more_easing_after_miss': int((big.eased_after_miss > big.eased_after_hit).sum()),
                       'depts_less': big[big.eased_after_miss <= big.eased_after_hit].dept.tolist(),
                       'median_gap_pts': float((big.eased_after_miss - big.eased_after_hit).median()),
                       'mh_odds_ratio_by_dept': float(num / den),
                       'rows': big.round(4).to_dict('records')}
    lodo = {}
    for d in big.dept:
        s = u[u.dept != d]; lodo[d] = float(s[s.miss].easier.mean() / s[~s.miss].easier.mean())
    res['leave_one_dept_out_ratio'] = {'min': min(lodo.values()), 'max': max(lodo.values())}
    fir = dd.set_index('dept').loc['FIR']
    res['fire_dept'] = {k: (float(v) if v is not None else None) for k, v in fir.items()}
    res['symmetry'] = {'eased_after_miss': res['all']['eased_after_miss'], 'raised_after_hit': res['all']['raised_after_hit'],
                       'reading': 'Targets move toward results about equally often in both directions, the signature of targets reset toward recent results rather than one-sided easing.'}
    res['verdict'] = 'survives, reframed'
    R['t2_target_easing'] = res


def fy_files(folder, fy):
    ms = [(fy - 1, m) for m in range(7, 13)] + [(fy, m) for m in range(1, 7)]
    return [os.path.join(RAW, 'outcomes', 'chunks', folder, f'{y}-{m:02d}.parquet') for y, m in ms]


def t3_fire():
    out = {}
    ok = lambda s: s[(s > 0) & (s < 120)]
    for fy in range(2013, 2026):
        f = pd.concat([pd.read_parquet(p) for p in fy_files('fire', fy) if os.path.exists(p)])
        for c in ['received_dttm', 'dispatch_dttm', 'on_scene_dttm']:
            f[c] = pd.to_datetime(f[c], errors='coerce')
        f = f.sort_values(['call_number', 'received_dttm'])
        g = f.groupby('call_number').agg(rec=('received_dttm', 'min'), disp=('dispatch_dttm', 'min'), ons=('on_scene_dttm', 'min'),
                                         ctype=('call_type', 'first'), op=('original_priority', 'first'), fp=('final_priority', 'first'))
        med = g[g.ctype == 'Medical Incident']
        fp3, op3 = med.fp.astype(str).isin(['3', 'E']), med.op.astype(str).isin(['3', 'E'])
        r = {'calls': int(len(g)), 'medical_calls': int(len(med)), 'code3_medical_calls_final': int(fp3.sum()),
             'share_medical_code3_final': float(fp3.mean()), 'share_medical_code3_original': float(op3.mean()),
             'share_upgraded_to_code3': float((~op3 & fp3).mean()), 'share_downgraded_from_code3': float((op3 & ~fp3).mean())}
        for lab, sub in [('final', med[fp3]), ('original', med[op3])]:
            c2a, d2a = ok((sub.ons - sub.rec).dt.total_seconds() / 60), ok((sub.ons - sub.disp).dt.total_seconds() / 60)
            r2d = (sub.disp - sub.rec).dt.total_seconds() / 60
            r[lab] = {'call_to_arrival_median': float(c2a.median()), 'call_to_arrival_p90': float(c2a.quantile(.9)),
                      'dispatch_to_arrival_median': float(d2a.median()), 'dispatch_to_arrival_p90': float(d2a.quantile(.9)),
                      'call_to_dispatch_median': float(r2d[(r2d >= 0) & (r2d < 60)].median()),
                      'dispatch_to_arrival_within_4m30': float((d2a <= 4.5).mean()), 'n_valid': int(len(c2a))}
        out[fy] = r
        print('fire', fy, r['calls'], round(r['final']['call_to_arrival_median'], 2), round(r['final']['dispatch_to_arrival_median'], 2), flush=True)
    meta, idx, pop, C = site_frames()
    fir = C[(C.dept == 'FIR') & ~C.char.isin(['capital', 'other'])].groupby('fy').actual.sum()
    ST = pd.DataFrame(S('staffing/cells.json')['cells']).query("dept == 'FIR'").set_index('fy')
    a, b = out[2013], out[2025]
    R['t3_fire'] = {'by_fy': out,
                    'calls_change_13_25': b['calls'] / a['calls'] - 1,
                    'code3_medical_change_13_25': b['code3_medical_calls_final'] / a['code3_medical_calls_final'] - 1,
                    'real_oper_spend_change_13_25': (fir[2025] / idx[2025]) / (fir[2013] / idx[2013]) - 1,
                    'headcount': {2013: int(ST.loc[2013, 'headcount']), 2025: int(ST.loc[2025, 'headcount'])},
                    'overtime_nominal': {2013: int(ST.loc[2013, 'overtime']), 2025: int(ST.loc[2025, 'overtime'])},
                    'slowdown_min': b['final']['call_to_arrival_median'] - a['final']['call_to_arrival_median'],
                    'slowdown_after_dispatch_min': b['final']['dispatch_to_arrival_median'] - a['final']['dispatch_to_arrival_median'],
                    'slowdown_before_dispatch_min': b['final']['call_to_dispatch_median'] - a['final']['call_to_dispatch_median'],
                    'verdict': 'survives', 'note': 'Medians are per call (first unit on scene). Code 3 by final or original priority gives the same trend; triage upgrades rose but the Code 3 share of medical calls stayed near half.'}


def t4_police():
    s = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), dtype=str,
                    usecols=['Fiscal Year', 'Revenue or Spending', 'Department Code', 'Object', 'Sub-object', 'Fund', 'Amount'])
    s = s[(s['Department Code'] == 'POL') & s['Fiscal Year'].isin(['2019', '2025', '2026'])]
    s['v'] = s.Amount.astype(float)
    b = pd.read_csv(os.path.join(RAW, 'budget.csv'), dtype=str, usecols=['Fiscal Year', 'Revenue or Spending', 'Department Code', 'Object', 'Fund', 'Budget'])
    b = b[(b['Department Code'] == 'POL') & (b['Revenue or Spending'] == 'Spending') & b.Object.str.contains('overtime', case=False, na=False)]
    b['v'] = b.Budget.astype(float)
    res = {}
    for fy in ('2019', '2025', '2026'):
        o = s[(s['Fiscal Year'] == fy) & (s['Revenue or Spending'] == 'Spending') & s.Object.str.contains('overtime', case=False, na=False)]
        bb = b[b['Fiscal Year'] == fy]
        fund_a, fund_b = o.groupby('Fund').v.sum(), bb.groupby('Fund').v.sum()
        gf_a = fund_a[[f for f in fund_a.index if f.startswith('GF') and 'Work Order' not in f]].sum()
        gf_b = fund_b[[f for f in fund_b.index if f.startswith('GF') and 'Work Order' not in f]].sum()
        sr10b_a, sr10b_b = fund_a.get('SR Police Law Enforcement Svcs', 0.0), fund_b.get('SR Police Law Enforcement Svcs', 0.0)
        rev = s[(s['Fiscal Year'] == fy) & (s['Revenue or Spending'] == 'Revenue') & (s.Object == 'Public Safety Service Charges')].v.sum()
        tot_a, tot_b = o.v.sum(), bb.v.sum()
        res[fy] = {'ledger_ot': tot_a, 'budget_ot': tot_b, 'ratio_total': tot_a / tot_b,
                   'sub_object_10b': float(o[o['Sub-object'].str.contains('10B', na=False)].v.sum()),
                   'fund_10b_actual': float(sr10b_a), 'fund_10b_budget': float(sr10b_b),
                   'airport_fund_actual': float(fund_a.get('SFIA-Operating Fund', 0.0)), 'gf_work_order_actual': float(fund_a.get('GF Work Order', 0.0)),
                   'gf_own_actual': float(gf_a), 'gf_own_budget': float(gf_b), 'ratio_gf_own': float(gf_a / gf_b),
                   'ratio_excl_10b_fund': float((tot_a - sr10b_a) / (tot_b - sr10b_b)),
                   'outside_funded_actual': float(tot_a - gf_a), 'public_safety_service_charges_revenue': float(rev)}
    ST = pd.DataFrame(S('staffing/cells.json')['cells']).query("dept == 'POL'").set_index('fy')
    r25 = ST.loc[2025]
    grid = {}
    for prod in (0.80, 0.85, 0.90):
        for premium in (False, True):
            # per hour of base pay: straight-time costs base + benefits (+ premium pay if counted), spread over productive hours
            load = r25.benefits / (r25.salaries + r25.other_salaries)
            prem = (r25.other_salaries / r25.salaries) if premium else 0.0
            straight = (1 + load) * (1 + prem) / prod
            ot = 1.5 * (1 + 0.0145)  # overtime hour: 1.5x plus Medicare only (overtime is not pensionable)
            grid[f'prod{prod}_{"premium_in_base" if premium else "no_premium"}'] = float(ot / straight)
    wf = pd.read_csv(os.path.join(INT, 'an_ot_vacancy.csv')).query("dept == 'POL' and fy == 2025").iloc[0]
    payroll = float(r25.overtime)
    res['payroll_ot_2025'] = payroll
    res['payroll_vs_ledger_2025'] = payroll / res['2025']['ledger_ot'] - 1
    res['per_hour_cost_ratio_main'] = float(wf.ot_hour_cost_ratio)
    res['per_hour_cost_ratio_grid'] = grid
    res['per_hour_range'] = [min(grid.values()), max(grid.values())]
    res['benefit_load_2025'] = float(r25.benefits / r25.salaries)
    res['not_in_ratio'] = 'Academy and field-training cost of a new officer, and the fatigue cost of long shifts, are not in either side.'
    res['verdict'] = {'overtime_147m': 'survives', 'budget_multiple': 'survives with scope note', 'per_hour_ratio': 'fragile; assumption-driven'}
    R['t4_police_overtime'] = res


def t5_bonds():
    gb = pd.DataFrame(S('analyses/go_bond_programs.json')['rows']) if 'rows' in S('analyses/go_bond_programs.json') else None
    g = pd.read_csv(os.path.join(INT, 'an_go_bonds.csv')).set_index(['bondprogram', 'year'])
    pace = pd.read_csv(os.path.join(INT, 'an_go_bond_pace.csv'))
    sw, es = g.loc[('Embarcadero Seawall Earthquake Safety', 2018)], g.loc[('Earthquake Safety and Emergency Response', 2020)]
    txt = open(os.path.join(RAW, 'capital', 'reports', 'FY24-FY25_Capital_Report.txt')).read()

    def grab(pat):
        m = re.search(pat, txt, re.S)
        return float(m.group(1)) if m else None
    city = {'source': 'Controller, General Obligation Bond Program Report FY2023-24 and FY2024-25 (https://media.api.sf.gov/documents/FY24-FY25_Capital_Report.pdf), as of June 30, 2025',
            'seawall_exp_enc_m': grab(r'Seawall Earthquake Safety.{0,3000}?\$([\d.]+) million has been expended and encumbered, which is 14%'),
            'seawall_exp_enc_share': 0.14, 'seawall_issued_m': grab(r'issued approximately \$([\d.]+)\s*million as of June 30, 2025\.\s*\n?\s*AT A GLANCE:\s*\n?\s*\n?\s*Authorization: \$425'),
            'eser_exp_enc_m': grab(r'\$([\d.]+) million expended and\s*encumbered, which is 22% of the total bond'), 'eser_exp_enc_share': 0.22,
            'eser_issued_m': grab(r'issued approximately \$([\d.]+)\s*million as of June 30, 2025\.\s*\n?\s*AT A GLANCE:\s*\n?\s*\n?\s*Authorization: \$628'),
            'seawall_design_delay_years': [9, 10], 'eser_arbitrage_rebate_m': 1.46,
            'irs_rule': 'Under federal tax regulations the City must typically expend at least 85% of net bond proceeds within three years of issuance (report p. 82).',
            'seawall_reason': 'Design milestones delayed 9 and 10 years, primarily because the US Army Corps of Engineers flood study was extended (report pp. 69-75); federal cost share requires 35% design.'}
    ours = {'seawall': {'budget': float(sw.revised_budget), 'expended': float(sw.expended), 'encumbered': float(sw.encumbered), 'issued': float(sw.issued),
                        'spent_share': float(sw.spent_share), 'exp_enc_share': float((sw.expended + sw.encumbered) / sw.revised_budget),
                        'spent_of_issued': float(sw.expended / sw.issued), 'years': float(sw.years_since_vote)},
            'eser2020': {'budget': float(es.revised_budget), 'expended': float(es.expended), 'encumbered': float(es.encumbered), 'issued': float(es.issued),
                         'spent_share': float(es.spent_share), 'exp_enc_share': float((es.expended + es.encumbered) / es.revised_budget),
                         'spent_of_issued': float(es.expended / es.issued), 'spent_of_city_issued': float(es.expended / (city['eser_issued_m'] * 1e6)) if city['eser_issued_m'] else None,
                         'years': float(es.years_since_vote)}}
    peers = pace[pace.years_since_vote.between(4.5, 8.5) & ~pace.bondprogram.eq('Embarcadero Seawall Earthquake Safety')
                 & ~((pace.bondprogram == 'Earthquake Safety and Emergency Response') & (pace.year == 2020))]
    ours['peer_curve'] = {'n': int(len(peers)), 'window_years': [4.5, 8.5], 'min': float(peers.spent_share.min()), 'median': float(peers.spent_share.median()),
                          'max': float(peers.spent_share.max()),
                          'rows': peers[['bondprogram', 'year', 'fiscal_year', 'years_since_vote', 'spent_share']].round(3).to_dict('records')}
    R['t5_bonds'] = {'ours': ours, 'city_report': city,
                     'agreement': {'seawall_exp_enc_pts_diff': ours['seawall']['exp_enc_share'] - city['seawall_exp_enc_share'],
                                   'eser_exp_enc_pts_diff': ours['eser2020']['exp_enc_share'] - city['eser_exp_enc_share'],
                                   'eser_issued_diff_m': ours['eser2020']['issued'] / 1e6 - (city['eser_issued_m'] or np.nan)},
                     'verdict': 'figures survive; the Seawall peer comparison is reframed (planning-stage program tied to a federal study)'}


def t6_hsh():
    d = pd.read_csv(os.path.join(INT, 'dept_fy.csv'))
    p = d[d.dept.isin(['HOM', 'HSA', 'DPH', 'DEC', 'CFC'])].pivot_table(index='fy', columns='dept', values='actual_oper_all_real', aggfunc='sum')
    hom = p.HOM
    grp = p[['HOM', 'HSA', 'DEC', 'CFC']].sum(axis=1, min_count=1)
    R['t6_hsh'] = {'hom_real': {int(k): float(v) for k, v in hom.dropna().items() if k <= 2026},
                   'multiple_17_25': float(hom[2025] / hom[2017]), 'multiple_18_25': float(hom[2025] / hom[2018]),
                   'change_25_26': float(hom[2026] / hom[2025] - 1),
                   'dph_real': {2016: float(p.DPH[2016]), 2017: float(p.DPH[2017]), 2018: float(p.DPH[2018])},
                   'human_services_group_change_13_25': float(grp[2025] / grp[2013] - 1),
                   'human_services_group_change_17_25': float(grp[2025] / grp[2017] - 1),
                   'verdict': 'survives (2.8x FY2017-FY2025; FY2017 was the first year and programs kept moving in during FY2018)'}


def t7_survey():
    m = pd.read_csv(os.path.join(RAW, 'outcomes', 'city_survey_microdata.csv'), usecols=['year', 'weight', 'general_rate'], low_memory=False)
    m['r'] = pd.to_numeric(m.general_rate, errors='coerce')
    m = m[m.r.between(1, 5)]
    out = {}
    for y, g in m.groupby('year'):
        w = pd.to_numeric(g.weight, errors='coerce').fillna(0)
        out[int(y)] = {'weighted_ab': float((w * (g.r >= 4)).sum() / w.sum()) if w.sum() > 0 else None, 'unweighted_ab': float((g.r >= 4).mean()), 'n': int(len(g))}
    R['t7_survey'] = {'by_year': out, 'verdict': 'survives; the 2015 peak and the 2023 low both coincide with survey-mode changes',
                      'mode_changes': 'mail to phone in 2015; online and in-person added in 2023; no 2021 survey'}


if __name__ == '__main__':
    for fn in (t1_gf, t2_targets, t4_police, t5_bonds, t6_hsh, t7_survey, t3_fire):
        print('###', fn.__name__, flush=True)
        fn()
    dflt = lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else (bool(o) if isinstance(o, np.bool_) else str(o))
    json.dump(R, open(os.path.join(OUT, 'redteam2.json'), 'w'), indent=1, default=dflt)
    t = R['t2_target_easing']
    print(json.dumps({'gf': R['t1_gf_per_resident']['change_13_25'], 'ease': t['all'], 'excl_mech': t['excl_mechanical_measures'],
                      'per_dept': {k: v for k, v in t['per_dept'].items() if k != 'rows'}, 'police': {k: R['t4_police_overtime'][k] for k in ('2025', 'per_hour_range')},
                      'bonds': R['t5_bonds']['agreement'], 'city': R['t5_bonds']['city_report'], 'hsh': R['t6_hsh']['multiple_17_25'],
                      'survey': {y: R['t7_survey']['by_year'][y] for y in (2011, 2015, 2019, 2023)}}, indent=1, default=dflt))
