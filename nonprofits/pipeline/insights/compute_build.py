"""Values (V) and chart arrays (CH) for every published insight, computed from the source tables listed in common.py.

COMPUTE[key]() -> (V, CH). spec.py holds the wording; build_insights.py renders; verify_insights.py recomputes
everything independently. Fractions are stored as fractions (0.45), dollars as dollars; charts in the units named
in their spec.
"""
import math, re
import numpy as np
import pandas as pd
from common import (cells, orgs, org_fy, fin, findings, contracts, outcomes, redteam, rt_parts, funds, defl,
                    report_text, PASS, ROOT)
from spec import disp

AREA_LABEL = {'homeless': 'Homelessness and housing', 'youth': 'Children, youth and families', 'health': 'Health and behavioral health',
              'human': 'Human services and seniors', 'workforce': 'Workforce and economic development', 'other': 'Other',
              'arts': 'Arts and culture'}
AREA_ORDER = ['homeless', 'youth', 'health', 'human', 'workforce', 'other', 'arts']


def real_total(fy, keep=None):
    c = cells()
    c = c[c.fy == fy]
    if keep is not None:
        c = c[c.org.map(keep)]
    return float(c.real.sum())


def name(o):
    return orgs().name[o]


# ------------------------------------------------------------------------------------------------ 1 growth by service area
def growth_areas():
    c = cells()
    a = c.groupby(['fy', 'area']).real.sum().unstack().fillna(0.0)
    V = {'t16': a.loc[2016].sum(), 't25': a.loc[2025].sum()}
    V['g'] = V['t25'] / V['t16'] - 1
    tot = V['t25'] - V['t16']
    V['dtot'] = tot
    for k in AREA_ORDER:
        V['d_' + k] = a.loc[2025, k] - a.loc[2016, k]
        V['sh_' + k] = V['d_' + k] / tot
        V['g_' + k] = a.loc[2025, k] / a.loc[2016, k] - 1
    V['sh_top3'] = V['sh_homeless'] + V['sh_youth'] + V['sh_health']
    V['rel'] = V['g_homeless'] / V['g_health']
    n = c.groupby('fy').amt.sum(); V['nom_x'] = n[2025] / n[2016]
    # checks
    t19 = a.loc[2019].sum()
    V['sh19_homeless'] = (a.loc[2025, 'homeless'] - a.loc[2019, 'homeless']) / (V['t25'] - t19)
    V['sh19_top3'] = sum(a.loc[2025, k] - a.loc[2019, k] for k in ('homeless', 'youth', 'health')) / (V['t25'] - t19)
    V['sh26_homeless'] = (a.loc[2026, 'homeless'] - a.loc[2016, 'homeless']) / (a.loc[2026].sum() - V['t16'])
    x = c[~c.org.isin(PASS)].groupby(['fy', 'area']).real.sum().unstack().fillna(0.0)
    V['shx_homeless'] = (x.loc[2025, 'homeless'] - x.loc[2016, 'homeless']) / (x.loc[2025].sum() - x.loc[2016].sum())
    V['shx_youth'] = (x.loc[2025, 'youth'] - x.loc[2016, 'youth']) / (x.loc[2025].sum() - x.loc[2016].sum())
    rt = redteam()['real_growth_fy2016_2025']['cite']
    V['g_us'] = rt['real_growth_us_cpi']; V['g_svc'] = rt['real_growth_services_cpi']
    CH = {'x': ['FY2016 total'] + [AREA_LABEL[k] for k in AREA_ORDER] + ['FY2025 total'],
          'v': [V['t16'] / 1e6] + [V['d_' + k] / 1e6 for k in AREA_ORDER] + [V['t25'] / 1e6]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 2 funding sources
def fund_cat(ft, fund):
    if ft == 'GEN_FUND' or fund == 'General Fund':
        return 'General Fund'
    if 'Our City Our Home' in fund or 'OCOH' in fund:
        return 'Our City Our Home'
    if fund == 'Children and Families Fund':
        return 'Children and Families Fund'
    if fund == "Children's Fund" or 'Dignity' in fund:
        return "Children's Fund and Dignity Fund"
    return 'Grants and other funds'


FUND_ORDER = ['General Fund', 'Our City Our Home', 'Children and Families Fund', "Children's Fund and Dignity Fund", 'Grants and other funds']


def funding():
    f = funds().copy()
    f['cat'] = [fund_cat(a, b) for a, b in zip(f.fund_type_code, f.fund)]
    p = f.groupby(['fiscal_year', 'cat']).paid.sum().unstack().fillna(0.0)[FUND_ORDER]
    V = {}
    V['t19'], V['t25'] = p.loc[2019].sum(), p.loc[2025].sum()
    V['dt'] = V['t25'] - V['t19']
    keys = {'General Fund': 'gf', 'Our City Our Home': 'ocoh', 'Children and Families Fund': 'cff', "Children's Fund and Dignity Fund": 'cdf', 'Grants and other funds': 'oth'}
    for cat, k in keys.items():
        V[k + '19'], V[k + '25'] = p.loc[2019, cat], p.loc[2025, cat]
        V['d_' + k] = V[k + '25'] - V[k + '19']
        V['sh_' + k] = V['d_' + k] / V['dt']
    V['sh_ded'] = V['sh_ocoh'] + V['sh_cff'] + V['sh_cdf']
    V['gf_g'] = V['gf25'] / V['gf19'] - 1
    V['gf_share19'], V['gf_share25'] = V['gf19'] / V['t19'], V['gf25'] / V['t25']
    # checks: real dollars; FY2026 endpoint; OCOH is mostly HSH
    D = defl()
    r_dt = V['t25'] - V['t19'] / D[2019]
    V['sh_ded_real'] = (V['d_ocoh'] + V['cff25'] - V['cff19'] / D[2019] + V['cdf25'] - V['cdf19'] / D[2019]) / r_dt
    V['sh_gf_real'] = (V['gf25'] - V['gf19'] / D[2019]) / r_dt
    d26 = p.loc[2026].sum() - V['t19']
    V['sh_ded26'] = sum(p.loc[2026, c_] - p.loc[2019, c_] for c_ in FUND_ORDER[1:4]) / d26
    V['sh_gf26'] = (p.loc[2026, 'General Fund'] - p.loc[2019, 'General Fund']) / d26
    oc = f[(f.cat == 'Our City Our Home') & (f.fiscal_year == 2025)]
    V['ocoh_hom_share'] = oc[oc.department_code == 'HOM'].paid.sum() / oc.paid.sum()
    cv = f[f.fund.str.contains('COVID', case=False)]
    cvy = cv.groupby('fiscal_year').paid.sum()
    V['covid_peak'] = cvy.max(); V['covid_peak_fy'] = int(cvy.idxmax())
    V['recon_25'] = V['t25'] - float(cells()[cells().fy == 2025].amt.sum())
    yrs = list(range(2019, 2027))
    CH = {'x': yrs}
    for cat, k in keys.items():
        CH[k] = [p.loc[y, cat] / 1e6 for y in yrs]
    return V, CH


# ------------------------------------------------------------------------------------------------ 3 incumbents vs entrants
def incumbents():
    oy = org_fy('real')
    V = {}

    def decomp(b, e=2025):
        cont = (oy[b] > 0) & (oy[e] > 0); ent = (oy[b] <= 0) & (oy[e] > 0); ex = (oy[b] > 0) & (oy[e] <= 0)
        return cont, ent, ex
    cont, ent, ex = decomp(2016)
    V['t16'], V['t25'] = oy[2016].sum(), oy[2025].sum()
    V['n_cont'], V['n_ent'], V['n_ex'] = int(cont.sum()), int(ent.sum()), int(ex.sum())
    V['d_cont'] = oy.loc[cont, 2025].sum() - oy.loc[cont, 2016].sum()
    V['d_ent'] = oy.loc[ent, 2025].sum()
    V['d_ex'] = -oy.loc[ex, 2016].sum()
    V['dt'] = V['t25'] - V['t16']
    V['sh_cont'] = V['d_cont'] / V['dt']; V['sh_ent'] = V['d_ent'] / V['dt']
    V['g_cont'] = oy.loc[cont, 2025].sum() / oy.loc[cont, 2016].sum() - 1
    V['g_cont_median'] = float((oy.loc[cont, 2025] / oy.loc[cont, 2016]).median() - 1)
    top = oy[2025].sort_values(ascending=False).head(20).index
    V['sh_top20_growth'] = (oy.loc[top, 2025].sum() - oy.loc[top, 2016].sum()) / V['dt']
    # checks: FY2019 base; never paid before FY2017; entrants' yearly share; excluding pass-through orgs
    c19, e19, x19 = decomp(2019)
    V['sh_cont19'] = (oy.loc[c19, 2025].sum() - oy.loc[c19, 2019].sum()) / (oy[2025].sum() - oy[2019].sum())
    never = (oy[[y for y in oy.columns if y <= 2016]] <= 0).all(axis=1) & (oy[2025] > 0)
    V['sh_never'] = oy.loc[never, 2025].sum() / V['dt']
    shares = []
    for y in range(2008, 2027):
        en = (oy[y] > 0) & (oy[y - 1] <= 0)
        shares.append(oy.loc[en, y].sum() / oy[y].sum())
    V['ent_share_avg'] = float(np.mean(shares)); V['ent_share_max'] = float(np.max(shares))
    keep = ~oy.index.isin(PASS)
    o2 = oy[keep]
    cx = (o2[2016] > 0) & (o2[2025] > 0)
    V['sh_cont_x'] = (o2.loc[cx, 2025].sum() - o2.loc[cx, 2016].sum()) / (o2[2025].sum() - o2[2016].sum())
    med = lambda y: float(oy[y][oy[y] > 0].median())
    V['med16'], V['med25'] = med(2016), med(2025)
    CH = {'x': ['FY2016 total', 'Organizations that stopped', 'Growth at continuing organizations', 'Organizations new since FY2016', 'FY2025 total'],
          'v': [V['t16'] / 1e6, V['d_ex'] / 1e6, V['d_cont'] / 1e6, V['d_ent'] / 1e6, V['t25'] / 1e6]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 4 pandemic step-up
def stepup():
    c = cells()
    r = c.groupby('fy').real.sum()
    V = {f'r{y}': r[y] for y in (2016, 2019, 2021, 2025, 2026)}
    V['g19_21'] = r[2021] / r[2019] - 1; V['g21_25'] = r[2025] / r[2021] - 1; V['g19_25'] = r[2025] / r[2019] - 1
    V['g25_26'] = r[2026] / r[2025] - 1
    rt = redteam()['real_growth_fy2016_2025']['cite']
    V['ctrl_nom'] = rt['controller_nominal_growth_2019_2025']; V['dash_nom'] = rt['nominal_growth_2019_2025']
    fv, _ = funding()
    V['covid_peak'], V['covid_peak_fy'] = fv['covid_peak'], fv['covid_peak_fy']
    n = c[c.amt > 0].groupby('fy').org.nunique()
    V['n19'], V['n25'] = int(n[2019]), int(n[2025])
    oy = org_fy('real'); V['med19'] = float(oy[2019][oy[2019] > 0].median()); V['med25'] = float(oy[2025][oy[2025] > 0].median())
    V['g19_25_x'] = (real_total(2025, lambda o: o not in PASS) / real_total(2019, lambda o: o not in PASS)) - 1
    t10 = set(org_fy('amt')[2025].sort_values(ascending=False).head(10).index)
    V['g19_25_t10'] = real_total(2025, lambda o: o not in t10) / real_total(2019, lambda o: o not in t10) - 1
    yrs = list(range(2007, 2027))
    CH = {'x': yrs, 'v': [r[y] / 1e6 for y in yrs]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 5 top-20 churn
def churn():
    oy = org_fy('amt')
    yrs = sorted(oy.columns)
    top = {y: set(oy[y][oy[y] > 0].sort_values(ascending=False).head(20).index) for y in yrs}
    new = {y: len(top[y] - top[y - 1]) for y in yrs[1:]}
    V = {'kept_16_25': len(top[2016] & top[2025]), 'always': len(set.intersection(*[top[y] for y in yrs])),
         'ever': len(set().union(*[top[y] for y in yrs]))}
    V['avg_pre'] = float(np.mean([new[y] for y in range(2009, 2018)]))
    V['avg_post'] = float(np.mean([new[y] for y in range(2019, 2027)]))
    first = {y: len(top[y] - set().union(*[top[z] for z in yrs if z < y])) for y in yrs[1:]}
    V['ft_pre'] = float(np.mean([first[y] for y in range(2009, 2018)])); V['ft_post'] = float(np.mean([first[y] for y in range(2019, 2027)]))
    sh = {y: oy.loc[list(top[y]), y].sum() / oy[y].sum() for y in yrs}
    V['sh16'], V['sh25'] = sh[2016], sh[2025]
    V['sh_min'] = min(sh[y] for y in range(2008, 2027)); V['sh_max'] = max(sh[y] for y in range(2008, 2027))
    # top 50 check
    top50 = {y: set(oy[y].sort_values(ascending=False).head(50).index) for y in yrs}
    V['t50_pre'] = float(np.mean([len(top50[y] - top50[y - 1]) for y in range(2009, 2018)]))
    V['t50_post'] = float(np.mean([len(top50[y] - top50[y - 1]) for y in range(2019, 2027)]))
    # newcomers: in FY2025 top 20, under $1M in FY2016
    nc = [o for o in oy[2025].sort_values(ascending=False).head(20).index if oy.loc[o, 2016] < 1e6]
    V['n_newcomers'] = len(nc)
    for i, o in enumerate(nc[:3]):
        V[f'nc{i}_25'] = oy.loc[o, 2025]
    V['nc_names'] = [name(o) for o in nc]
    # excluding pass-through organizations
    ox = oy[~oy.index.isin(PASS)]
    tx = {y: set(ox[y].sort_values(ascending=False).head(20).index) for y in yrs}
    V['x_pre'] = float(np.mean([len(tx[y] - tx[y - 1]) for y in range(2009, 2018)]))
    V['x_post'] = float(np.mean([len(tx[y] - tx[y - 1]) for y in range(2019, 2027)]))
    CH = {'x': yrs[1:], 'v': [new[y] for y in yrs[1:]]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 6 dependency flat
def dep_flat():
    f = fin()
    g = f[(f.city >= 1e6) & (f.total_revenue > 0)]
    s = g.groupby('fy').dep
    V = {'med16': s.median()[2016], 'med24': s.median()[2024], 'n16': int(s.size()[2016]), 'n24': int(s.size()[2024])}
    V['gt75_16'] = (g[g.fy == 2016].dep > 0.75).mean(); V['gt75_24'] = (g[g.fy == 2024].dep > 0.75).mean()
    V['med_min'] = s.median().loc[2012:2025].min(); V['med_max'] = s.median().loc[2012:2025].max()
    a = g[g.fy == 2016].set_index('org').dep; b = g[g.fy == 2024].set_index('org').dep
    j = pd.concat([a, b], axis=1, keys=['a', 'b']).dropna()
    V['panel_n'] = len(j); V['panel_a'] = j.a.median(); V['panel_b'] = j.b.median()
    # city money for the panel vs their total revenue
    rev = f.set_index(['org', 'fy']).total_revenue
    cty = f.set_index(['org', 'fy']).city
    ids = j.index
    V['panel_city_g'] = sum(cty[(o, 2024)] for o in ids) / sum(cty[(o, 2016)] for o in ids) - 1
    V['panel_rev_g'] = sum(rev[(o, 2024)] for o in ids) / sum(rev[(o, 2016)] for o in ids) - 1
    D = defl()
    gr = f[(f.city / f.fy.map(D) >= 1e6) & (f.total_revenue > 0)]
    V['med16_real'] = gr[gr.fy == 2016].dep.median(); V['med24_real'] = gr[gr.fy == 2024].dep.median()
    V['med25'] = s.median()[2025]
    gx = g[~g.org.isin(PASS)]
    V['medx16'] = gx[gx.fy == 2016].dep.median(); V['medx24'] = gx[gx.fy == 2024].dep.median()
    V['med24_pro'] = redteam()['dependency']['cite']['dep_median_prorated_2024']
    yrs = list(range(2012, 2026))
    CH = {'x': yrs, 'med': [s.median()[y] * 100 for y in yrs], 'gt75': [(g[g.fy == y].dep > 0.75).mean() * 100 for y in yrs]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 7 fastest risers
def fast_risers():
    f = fin()
    g = f[(f.total_revenue >= 5e5) & f.dep.notna()].sort_values('fy')
    rows = []
    for o, h in g.groupby('org'):
        vals = list(zip(h.fy, h.dep, h.city))
        hit = None
        for i, (y0, d0, c0) in enumerate(vals):
            if d0 < 0.25:
                for y1, d1, c1 in vals[i + 1:]:
                    if y1 - y0 <= 5 and 0.6 <= d1 <= 1.05 and c1 >= 2e6:
                        hit = (o, y0, d0, c0, y1, d1, c1); break
            if hit:
                break
        if hit:
            rows.append(hit)
    r = pd.DataFrame(rows, columns=['org', 'y0', 'd0', 'c0', 'y1', 'd1', 'c1']).sort_values('c1', ascending=False)
    V = {'n': len(r), 'n_orgs_eligible': int(g.org.nunique())}
    top = r.head(6)
    for i, (_, x) in enumerate(top.iterrows()):
        V[f'o{i}_d0'], V[f'o{i}_d1'], V[f'o{i}_y0'], V[f'o{i}_y1'], V[f'o{i}_c0'], V[f'o{i}_c1'] = x.d0, x.d1, x.y0, x.y1, x.c0, x.c1
    V['names'] = [disp(name(o)) for o in top.org]
    V['sum_c1'] = r.c1.sum()
    fi = f.set_index(['org', 'fy']).dep
    V['n_conf'] = int(sum(1 for _, x in r.iterrows() if any(fi.get((x.org, x.y1 + k), 0) >= 0.5 for k in (1, 2))))
    V['n_still'] = int(sum(1 for _, x in r.iterrows() if ((f.org == x.org) & (f.fy == f[f.org == x.org].fy.max()) & (f.dep >= 0.5)).any()))
    # checks: threshold 50% instead of 60%
    n50 = 0
    for o, h in g.groupby('org'):
        vals = list(zip(h.fy, h.dep, h.city)); ok = False
        for i, (y0, d0, c0) in enumerate(vals):
            if d0 < 0.25 and any(y1 - y0 <= 5 and 0.5 <= d1 <= 1.05 and c1 >= 2e6 for y1, d1, c1 in vals[i + 1:]):
                ok = True; break
        n50 += ok
    V['n50'] = n50
    V['n_x'] = int((~r.org.isin(PASS)).sum())
    V['x_drop'] = ', '.join(disp(name(o)) for o in r.org if o in PASS)
    CH = {'x': ['Before', 'After'], 'names': V['names'], 'd0': [x * 100 for x in top.d0], 'd1': [x * 100 for x in top.d1]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 8 reserves
BANDS = [(0, 0.25, 'Under 25%'), (0.25, 0.5, '25–50%'), (0.5, 0.75, '50–75%'), (0.75, 99, '75% or more')]


def reserves():
    f = fin()

    def sub(fy):
        return f[(f.fy == fy) & (f.city >= 1e6) & (f.total_revenue > 0) & f.months_reserves.notna()]
    g = sub(2024)
    V = {}
    for i, (lo, hi, _) in enumerate(BANDS):
        b = g[(g.dep >= lo) & (g.dep < hi)]
        V[f'b{i}_lt1'] = (b.months_reserves < 1).mean(); V[f'b{i}_n'] = len(b); V[f'b{i}_med'] = b.months_reserves.median()
    hi = g[g.dep >= 0.75]; lo = g[g.dep < 0.75]
    V['hi_lt1'], V['lo_lt1'] = (hi.months_reserves < 1).mean(), (lo.months_reserves < 1).mean()
    V['hi_n'], V['lo_n'] = len(hi), len(lo)
    V['hi_k'], V['lo_k'] = int((hi.months_reserves < 1).sum()), int((lo.months_reserves < 1).sum())
    V['hi_med'], V['lo_med'] = hi.months_reserves.median(), lo.months_reserves.median()
    V['ratio'] = V['hi_lt1'] / V['lo_lt1']
    V['hi_def'] = (hi.total_expenses > hi.total_revenue).mean(); V['lo_def'] = (lo.total_expenses > lo.total_revenue).mean()
    for fy in (2023, 2025):
        h = sub(fy)
        V[f'hi_lt1_{fy}'] = (h[h.dep >= 0.75].months_reserves < 1).mean(); V[f'lo_lt1_{fy}'] = (h[h.dep < 0.75].months_reserves < 1).mean()
    gx = g[~g.org.isin(PASS) & (g.dep <= 1)]
    V['x_hi'] = (gx[gx.dep >= 0.75].months_reserves < 1).mean(); V['x_lo'] = (gx[gx.dep < 0.75].months_reserves < 1).mean()
    V['hi_lt2'] = (hi.months_reserves < 2).mean(); V['lo_lt2'] = (lo.months_reserves < 2).mean()
    CH = {'x': [b[2] for b in BANDS], 'v': [V[f'b{i}_lt1'] * 100 for i in range(4)], 'n': [V[f'b{i}_n'] for i in range(4)]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 9 corrective action
def corrective():
    f = fin().set_index(['org', 'fy'])
    fr = findings()
    rows = []
    for _, r in fr[fr.fy.isin([2023, 2024, 2025])].iterrows():
        k = (r.org, r.fy)
        if k in f.index and f.loc[k].total_revenue > 0:
            x = f.loc[k]
            rows.append({'org': r.org, 'fy': r.fy, 'dep': x.city / x.total_revenue, 'severe': r.result in ('corrective', 'elevated', 'redflag')})
    A = pd.DataFrame(rows)
    hi = A.dep >= 0.75
    V = {'n': len(A), 'n_orgs': int(A.org.nunique()), 'n_hi': int(hi.sum()), 'sev_hi': int(A[hi].severe.sum()), 'sev_lo': int(A[~hi].severe.sum())}
    V['rate_hi'], V['rate_lo'] = A[hi].severe.mean(), A[~hi].severe.mean()
    V['n_lo'] = int((~hi).sum())
    V['ratio'] = V['rate_hi'] / V['rate_lo']
    V['sev_total'] = int(A.severe.sum()); V['sev_orgs'] = int(A[A.severe].org.nunique())
    og = A.groupby('org').agg(dep=('dep', 'median'), severe=('severe', 'max'))
    V['org_hi_n'] = int((og.dep >= 0.75).sum()); V['org_hi_sev'] = int(og[og.dep >= 0.75].severe.sum())
    V['org_lo_n'] = int((og.dep < 0.75).sum()); V['org_lo_sev'] = int(og[og.dep < 0.75].severe.sum())
    bands = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 99)]
    rates = [A[(A.dep >= a) & (A.dep < b)].severe.mean() for a, b in bands]
    ns = [int(((A.dep >= a) & (A.dep < b)).sum()) for a, b in bands]
    ck = {c['check']: c['result'] for c in redteam()['dependency_corrective_action']['checks']}
    cite = redteam()['dependency_corrective_action']['cite']
    V['or_adj'], V['or_lo'], V['or_hi'] = cite['assoc_or_adj'], cite['assoc_or_adj_lo'], cite['assoc_or_adj_hi']
    V['perm_p'] = ck['Organization-level permutation (labels shuffled by organization)']
    V['or_res'] = ck['Same, also controlling for under one month of reserves'][0]
    V['mh_min'] = min(ck['Mantel-Haenszel risk ratio stratified by size band / service area / fiscal year'])
    V['first_hi'] = ck['First monitored year per organization only (the tier policy began in FY2024, so few events)']['sev_hi']
    V['first_lo'] = ck['First monitored year per organization only (the tier policy began in FY2024, so few events)']['sev_lo']
    CH = {'x': [b[2] for b in BANDS], 'v': [x * 100 for x in rates], 'n': ns}
    return V, CH


# ------------------------------------------------------------------------------------------------ 10 contracts: longer vs bigger
def contract_growth():
    L = rt_parts('contracts_llm'); Dd = rt_parts('doubled_contracts')
    con = pd.concat([pd.DataFrame(__import__('json').load(open(p))['contracts']) for p in [ROOT + '/data/site/contracts/contracts.json']])
    V = {'n_con': len(con), 'n_dbl': len(Dd)}
    V['n_ext'] = sum((c['term_extended_days'] or 0) >= 182 for c in Dd)
    V['n_ann2'] = sum((c['annualized_ratio'] or 0) >= 2 for c in Dd)
    V['n_ann_lt15'] = sum((c['annualized_ratio'] or 9) < 1.5 for c in Dd)
    V['n_rr'] = sum(c['run_rate_ratio'] is not None for c in Dd); V['n_rr15'] = sum((c['run_rate_ratio'] or 0) >= 1.5 for c in Dd)
    cnt = pd.Series([x['primary_driver'] for x in L]).value_counts()
    for k in ('extension', 'expansion', 'funding_increment', 'rate_or_volume'):
        V['llm_' + k] = int(cnt.get(k, 0))
    V['llm_conf_med'] = float(np.median([x['confidence'] for x in L])); V['llm_low'] = sum(x['confidence'] < 0.6 for x in L)
    V['cannot_tell'] = sum(x['text_shows_new_scope_or_sites'] == 'cannot_tell' for x in L)
    V['first_2021'] = sum(c['orig_snap'] == '2021-04-22' for c in Dd)
    hi = [x for x in L if x['confidence'] >= 0.7]
    V['hi_n'] = len(hi); V['hi_ext'] = sum(x['primary_driver'] == 'extension' for x in hi)
    CH = {'x': ['Mainly a longer term', 'Mainly a larger yearly amount', 'Funding for years already in the term', 'Higher rates or volume'],
          'v': [V['llm_extension'], V['llm_expansion'], V['llm_funding_increment'], V['llm_rate_or_volume']]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 11 emergency / waiver authority
def emergency():
    c = contracts().copy()
    st = pd.to_datetime(c.start, errors='coerce')
    c['sfy'] = st.dt.year + (st.dt.month >= 7).astype(int)
    c['em'] = c.authority_class == 'emergency_or_waiver'
    V = {'em_total': c[c.em].agreed.sum(), 'all_total': c.agreed.sum(), 'n_em': int(c.em.sum()), 'n_all': len(c)}
    V['em_share'] = V['em_total'] / V['all_total']
    V['em_hom'] = c[c.em & (c.dept == 'HOM')].agreed.sum() / V['em_total']
    yrs = list(range(2018, 2027))
    sh = {y: c[c.em & (c.sfy == y)].agreed.sum() / c[c.sfy == y].agreed.sum() for y in yrs}
    shn = {y: c[c.em & (c.sfy == y)].shape[0] / c[c.sfy == y].shape[0] for y in yrs}
    V['sh19'], V['sh21'], V['sh22'], V['sh24'], V['sh25'], V['sh26'] = sh[2019], sh[2021], sh[2022], sh[2024], sh[2025], sh[2026]
    V['shn21'] = shn[2021]; V['shn25'] = shn[2025]
    big = c[c.agreed >= 1e6]
    V['big21'] = big[big.em & (big.sfy == 2021)].agreed.sum() / big[big.sfy == 2021].agreed.sum()
    nh = c[c.dept != 'HOM']
    V['nh21'] = nh[nh.em & (nh.sfy == 2021)].agreed.sum() / nh[nh.sfy == 2021].agreed.sum()
    top5 = c[c.sfy == 2021].sort_values('agreed', ascending=False).head(5).id
    r = c[(c.sfy == 2021) & ~c.id.isin(top5)]
    V['x5_21'] = r[r.em].agreed.sum() / r.agreed.sum()
    raw = pd.read_csv(ROOT + '/data/raw/supplier_contracts.csv', dtype=str, keep_default_na=False)
    auth = raw[raw['Supplier Type'] == 'Prime Contractor'].drop_duplicates('Contract Number').set_index('Contract Number')['Purchasing Authority']
    late = c[c.em & (c.sfy >= 2024)]
    V['core_share'] = late[late.id.map(auth).fillna('').str.upper().str.startswith('CORE INITIATIVES ADDRESSING HOMELESSNESS')].agreed.sum() / late.agreed.sum()
    CH = {'x': yrs, 'v': [sh[y] * 100 for y in yrs]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 12 executive pay
def exec_pay():
    f = fin()

    def gaps(fy, pool='all'):
        e = f[~f.org.isin(PASS)] if pool == 'nopass' else f
        e = e[(f.fy == fy) & (f.exec_comp > 0) & (f.total_expenses >= 1e6) & (f.city > 0) & (f.total_revenue > 0)].copy()
        if pool == 'large':
            e = e[e.city >= 1e6]
        X = np.column_stack([np.ones(len(e)), np.log(e.total_expenses)])
        y = np.log(e.exec_comp)
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e['res'] = y - X @ b
        out = {'b': b[1], 'n': len(e)}
        for i, (lo, hi, _) in enumerate(BANDS):
            s = e[(e.dep >= lo) & (e.dep < hi)]
            out[f'g{i}'] = math.exp(s.res.median()) - 1; out[f'n{i}'] = len(s)
        # with service-area dummies and dependency bands
        areas = sorted(e.area.dropna().unique())[1:]
        X2 = np.column_stack([X] + [(e.area == a).astype(float).to_numpy() for a in areas] +
                             [((e.dep >= lo) & (e.dep < hi)).astype(float).to_numpy() for lo, hi, _ in BANDS[1:]])
        b2 = np.linalg.lstsq(X2, y, rcond=None)[0]
        out['adj_hi'] = math.exp(b2[-1]) - 1
        out['med_hi'] = e[e.dep >= 0.75].exec_comp.median(); out['med_lo'] = e[e.dep < 0.25].exec_comp.median()
        return out
    g = gaps(2024)
    V = {'n': g['n'], 'b': g['b'], 'g_hi': g['g3'], 'g_lo': g['g0'], 'n_hi': g['n3'], 'adj_hi': g['adj_hi'],
         'med_hi': g['med_hi'], 'med_lo': g['med_lo']}
    for fy in (2022, 2023, 2025):
        V[f'g_hi_{fy}'] = gaps(fy)['g3']
    gl = gaps(2024, 'large')
    V['large_g_hi'] = gl['g3']; V['large_n'] = gl['n']
    V['x_g_hi'] = gaps(2024, 'nopass')['g3']
    CH = {'x': [b[2] for b in BANDS], 'v': [g[f'g{i}'] * 100 for i in range(4)], 'n': [g[f'n{i}'] for i in range(4)]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 13 homelessness and PIT
def homeless_pit():
    o = outcomes()
    pit = o[o.measure.isin(['pit_total', 'pit_unsheltered'])].pivot_table(index='fiscal_year', columns='measure', values='value')
    c = cells()
    hom = c[c.dept == 'HOM'].groupby('fy').real.sum()
    V = {'s19': hom[2019], 's26': hom[2026], 's24': hom[2024]}
    V['s_g'] = hom[2026] / hom[2019] - 1
    V['tot19'], V['tot26'], V['uns19'], V['uns26'] = pit.loc[2019, 'pit_total'], pit.loc[2026, 'pit_total'], pit.loc[2019, 'pit_unsheltered'], pit.loc[2026, 'pit_unsheltered']
    V['sh19'], V['sh26'] = V['tot19'] - V['uns19'], V['tot26'] - V['uns26']
    V['d_uns'] = V['uns19'] - V['uns26']; V['d_sh'] = V['sh26'] - V['sh19']
    V['tot_g'] = V['tot26'] / V['tot19'] - 1; V['uns_g'] = V['uns26'] / V['uns19'] - 1; V['sh_g'] = V['sh26'] / V['sh19'] - 1
    V['tot_g24'] = pit.loc[2024, 'pit_total'] / V['tot19'] - 1; V['uns_g24'] = pit.loc[2024, 'pit_unsheltered'] / V['uns19'] - 1
    V['s_g24'] = hom[2024] / hom[2019] - 1
    hh = c[(c.area == 'homeless')].groupby('fy').real.sum()
    V['area_g'] = hh[2026] / hh[2019] - 1
    V['s_g_nom'] = c[c.dept == 'HOM'].groupby('fy').amt.sum()[2026] / c[c.dept == 'HOM'].groupby('fy').amt.sum()[2019] - 1
    CH = {'x': ['HSH payments to nonprofits (real)', 'People in shelter', 'Total homeless count', 'People unsheltered'],
          'v': [V['s_g'] * 100, V['sh_g'] * 100, V['tot_g'] * 100, V['uns_g'] * 100]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 14 consistent measures
MEASURES = [('CHF', 'children_youth_served', 2019, 2025, 'Children and youth served (DCYF)'),
            ('DPH', 'unique_mental_health_clients', 2020, 2025, 'Mental health clients (DPH)'),
            ('DPH', 'unique_substance_use_clients', 2020, 2025, 'Substance use clients (DPH)'),
            ('HOM', 'households_placed_psh_rrh_ps', 2023, 2025, 'Households placed in housing (HSH)'),
            ('HSA', 'home_delivered_meals_older_adults', 2018, 2025, 'Home-delivered meals, older adults (HSA)')]


def measures():
    o = outcomes(); c = cells()
    d = c.groupby(['dept', 'fy']).real.sum()
    V = {}; sp, ms = [], []
    for i, (dept, m, a, b, _) in enumerate(MEASURES):
        s = o[(o.department_code == dept) & (o.measure == m)].set_index('fiscal_year').value
        V[f's{i}'] = d[(dept, b)] / d[(dept, a)] - 1; V[f'm{i}'] = s[b] / s[a] - 1
        V[f'c{i}'] = (1 + V[f's{i}']) / (1 + V[f'm{i}']) - 1
        sp.append(V[f's{i}'] * 100); ms.append(V[f'm{i}'] * 100)
    V['s_min'] = min(V[f's{i}'] for i in range(5)); V['s_max'] = max(V[f's{i}'] for i in range(5))
    # checks: CHF from FY2022 (after reopening); DPH from FY2021; HSH to FY2026 year-to-date
    s = o[(o.department_code == 'CHF') & (o.measure == 'children_youth_served')].set_index('fiscal_year').value
    V['chf22_s'] = d[('CHF', 2025)] / d[('CHF', 2022)] - 1; V['chf22_m'] = s[2025] / s[2022] - 1
    V['chf24_s'] = d[('CHF', 2024)] / d[('CHF', 2019)] - 1; V['chf24_m'] = s[2024] / s[2019] - 1
    h = o[(o.department_code == 'HOM') & (o.measure == 'households_placed_psh_rrh_ps')].set_index('fiscal_year').value
    V['hom26_s'] = d[('HOM', 2026)] / d[('HOM', 2023)] - 1; V['hom26_m'] = h[2026] / h[2023] - 1
    V['n_up'] = sum(1 for i in range(5) if V[f'c{i}'] > 0)
    CH = {'x': [x[4] for x in MEASURES], 'spend': sp, 'served': ms}
    return V, CH


# ------------------------------------------------------------------------------------------------ 15 monitoring normalization
def monitoring():
    fr = findings()
    V = {}
    for fy in (2022, 2023, 2024, 2025):
        g = fr[fr.fy == fy]
        V[f'n{fy}'] = len(g); V[f'f{fy}'] = (g.result != 'none').mean()
        V[f'tier{fy}'] = int(g.result.isin(['corrective', 'elevated', 'redflag']).sum())
    t19 = report_text(23)
    m = re.search(r'In FY19, (\d+)% of monitored contractors ended the cycle in full conformance', t19.replace('\n', ' '))
    V['fy19_conf'] = int(m.group(1)) / 100; V['f2019'] = 1 - V['fy19_conf']
    w = {}
    for fy, pat in ((22, r'departments granted (\d+) contractors a waiver'), (23, r'departments granted (\d+) contractors a waiver'),
                    (24, r'departments granted (\d+) contractors a waiver')):
        w[fy] = int(re.search(pat, report_text(fy).replace('\n', ' ')).group(1))
    V['w22'], V['w23'], V['w24'] = w[22], w[23], w[24]
    t = report_text(23).replace('\n', ' ')
    V['fy23_unres'] = int(re.search(r'Forty-six nonprofits \((\d+)%\) had unresolved findings', t).group(1)) / 100
    both = fr[fr.fy.isin([2022, 2023])].pivot_table(index='org', columns='fy', values='result', aggfunc='first').dropna()
    V['panel_n'] = len(both); V['panel_f22'] = (both[2022] != 'none').mean(); V['panel_f23'] = (both[2023] != 'none').mean()
    CH = {'x': [2019, 2022, 2023, 2024, 2025], 'v': [V['f2019'] * 100] + [V[f'f{y}'] * 100 for y in (2022, 2023, 2024, 2025)]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 16 pass-through organizations
def passthrough():
    oy = org_fy('amt')
    V = {'t25': oy[2025].sum()}
    pt = oy.loc[[o for o in PASS if o in oy.index], 2025].sort_values(ascending=False)
    V['pt25'] = pt.sum(); V['pt_share'] = V['pt25'] / V['t25']; V['n_pt'] = int((pt > 0).sum())
    cc = 'org-942221305'
    V['cc16'], V['cc25'] = oy.loc[cc, 2016], oy.loc[cc, 2025]; V['cc_x'] = V['cc25'] / V['cc16']
    V['cc_share_pt'] = V['cc25'] / V['pt25']
    al = pd.read_parquet(ROOT + '/data/interim/aligned.parquet', columns=['ein', 'period_end', 'grants_paid', 'total_expenses'])
    x = al[(al.ein == '942221305') & (al.period_end == '2025-06')].iloc[0]
    V['cc_grants_share'] = x.grants_paid / x.total_expenses
    fu = funds(); ccf = fu[(fu.org == cc) & (fu.fiscal_year == 2025)]
    V['cc_cff_share'] = ccf[ccf.fund == 'Children and Families Fund'].paid.sum() / ccf.paid.sum()
    V['cc_rank'] = int(list(oy[2025].sort_values(ascending=False).index).index(cc) + 1)
    rt = redteam()['real_growth_fy2016_2025']['cite']
    V['g_all'], V['g_x'] = rt['real_growth_sf_cpi'], rt['real_growth_excl_passthrough']
    V['ctrl25'] = redteam()['total_fy2025']['cite']['controller_dataset_fy2025']
    V['pt_contracts'] = redteam()['total_fy2025']['cite']['passthrough_contracts_fy2025']
    V['loans25'] = redteam()['total_fy2025']['cite']['loans_fy2025']
    V['ctrl_gap'] = V['t25'] - V['ctrl25']; V['pt_noloan'] = V['pt25'] - V['loans25']
    top = pt.head(7)
    CH = {'x': [disp(name(o)) for o in top.index], 'v': [x / 1e6 for x in top.values]}
    V['pt16'] = oy.loc[[o for o in PASS if o in oy.index], 2016].sum(); V['pt_share16'] = V['pt16'] / oy[2016].sum()
    return V, CH


# ------------------------------------------------------------------------------------------------ 17 base-year sensitivity
def base_year():
    r = cells().groupby('fy').real.sum()
    yrs = list(range(2013, 2020))
    V = {f'g{y}': r[2025] / r[y] - 1 for y in yrs}
    V['r2017'], V['r2018'], V['r2019'] = r[2017], r[2018], r[2019]
    V['g_min'] = min(V[f'g{y}'] for y in (2015, 2016, 2017)); V['g_max'] = max(V[f'g{y}'] for y in (2015, 2016, 2017))
    V['dip18'] = r[2018] / r[2017] - 1; V['jump19'] = r[2019] / r[2018] - 1
    d = cells()[cells().dept == 'DPH'].groupby('fy').amt.sum()
    V['dph17'], V['dph18'], V['dph19'] = d[2017], d[2018], d[2019]
    V['cagr'] = (r[2025] / r[2016]) ** (1 / 9) - 1
    V['cagr_1319'] = (r[2025] / r[2013]) ** (1 / 12) - 1
    V['cagr17'] = (r[2025] / r[2017]) ** (1 / 8) - 1
    rt = redteam()['real_growth_fy2016_2025']['cite']
    V['g_us'] = rt['real_growth_us_cpi']; V['rt_g2017'] = rt['real_growth_from_fy2017']
    CH = {'x': [f'From FY{y}' for y in yrs], 'v': [V[f'g{y}'] * 100 for y in yrs]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 18 subcontractors invisible
def subcontractors():
    raw = pd.read_csv(ROOT + '/data/raw/supplier_contracts.csv', dtype=str, keep_default_na=False)
    sub = set(raw[raw['Supplier Type'] != 'Prime Contractor']['Contract Number'])
    pr = raw[raw['Supplier Type'] == 'Prime Contractor'].drop_duplicates('Contract Number').copy()
    pr['np'] = pr['Non-Profit'] == 'X'; pr['hs'] = pr['Contract Number'].isin(sub)
    pr['grant'] = pr['Contract Type'].str.startswith('Grant Contract')
    pr['ps'] = pr['Contract Type'].str.startswith('Professional Services')
    V = {'np_n': int(pr.np.sum()), 'np_sub': int(pr[pr.np].hs.sum()), 'np_grant_share': pr[pr.np].grant.mean()}
    V['fp_ps'] = pr[~pr.np & pr.ps].hs.mean(); V['np_ps'] = pr[pr.np & pr.ps].hs.mean()
    V['fp_ps_n'] = int((~pr.np & pr.ps).sum()); V['np_ps_n'] = int((pr.np & pr.ps).sum())
    V['gr_any'] = pr[pr.grant].hs.mean(); V['gr_n'] = int(pr.grant.sum()); V['gr_sub'] = int(pr[pr.grant].hs.sum())
    V['fp_all'] = pr[~pr.np].hs.mean()
    fr = findings()
    V['sub_findings'] = int(fr.explode('categories').categories.eq('Subcontracts').sum())
    V['n_reviews'] = int(fr.fy.between(2022, 2025).sum())
    con = contracts()
    V['ours_n'] = len(con); V['ours_sub'] = int(con.id.isin(sub).sum())
    CH = {'x': ['For-profit professional services', 'Nonprofit professional services', 'Grant agreements (all recipients)'],
          'v': [V['fp_ps'] * 100, V['np_ps'] * 100, V['gr_any'] * 100], 'n': [V['fp_ps_n'], V['np_ps_n'], V['gr_n']]}
    return V, CH


# ------------------------------------------------------------------------------------------------ 19 dependency by service area
def share_vendor():
    t = pd.DataFrame(__import__('json').load(open(ROOT + '/data/site/aggregates/trends.json'))['rows']).set_index('fiscal_year')
    s = t.nonprofit_all / t.all_expenditure
    V = {'s16': s[2016], 's25': s[2025], 's_max': s.loc[2007:2026].max(), 's_max_fy': int(s.loc[2007:2026].idxmax()), 's07': s[2007], 's_min': s.loc[2007:2026].min(),
         's_min_fy': int(s.loc[2007:2026].idxmin())}
    V['np_g'] = t.nonprofit_all[2025] / t.nonprofit_all[2016] - 1; V['all_g'] = t.all_expenditure[2025] / t.all_expenditure[2016] - 1
    V['s19'], V['s26'] = s[2019], s[2026]
    yrs = list(range(2007, 2027))
    CH = {'x': yrs, 'v': [s[y] * 100 for y in yrs]}
    return V, CH


COMPUTE = {'growth_areas': growth_areas, 'funding': funding, 'incumbents': incumbents, 'stepup': stepup, 'churn': churn,
           'dep_flat': dep_flat, 'fast_risers': fast_risers, 'reserves': reserves, 'corrective': corrective,
           'contract_growth': contract_growth, 'emergency': emergency, 'exec_pay': exec_pay, 'homeless_pit': homeless_pit,
           'measures': measures, 'monitoring': monitoring, 'passthrough': passthrough, 'base_year': base_year,
           'subcontractors': subcontractors, 'share_vendor': share_vendor}

if __name__ == '__main__':
    import sys, json
    keys = sys.argv[1:] or list(COMPUTE)
    for k in keys:
        V, CH = COMPUTE[k]()
        print('==', k)
        for a, b in V.items():
            print(f'   {a}: {round(b, 4) if isinstance(b, (float, np.floating)) else b}')
        for a, b in CH.items():
            print(f'   CH {a}: {[round(x, 1) if isinstance(x, (float, np.floating)) else x for x in b]}')
