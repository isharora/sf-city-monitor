"""Independent verification of nonprofits/data/site/insights/insights.json.

For every insight this script recomputes each named value (V) and chart array (CH) from the source tables with its
own loaders and code (json / csv modules and plain Python; it does not import common.py or compute_build.py):
site payment cells, organization index, Form 990 rows, monitoring findings, contract files, outcome rows, the
fund-level Vendor Payments download, the raw Supplier Contracts extract, the Controller's report text and the red
team's result files. Shared inputs that are definitions rather than computations: the pass-through organization list
(pipeline/redteam/rt_findings.py) and the vendor -> EIN map (data/interim/vendor_map.parquet), plus spec.py for wording.

Checks (any failure -> exit 1):
  1. every placeholder value used in an insight's text is recomputed here and agrees with the build value
     (relative tolerance 0.5%, or 0.005 absolute for small values);
  2. the insight's text re-rendered with the recomputed values equals the published text exactly;
  3. every chart array agrees element by element (1% relative / 0.05 absolute), and the published chart equals the
     chart rendered from recomputed arrays;
  4. template text contains no literal numbers outside placeholders and allowed tokens;
  5. contract shape: required fields, chart types, verdicts, explore views, unique ids, ranks 1..n, title length,
     and every nonprofits/... path cited in a source exists.
Writes data/insights/verify_insights.json.
"""
import csv, glob, json, math, os, re, statistics as st, sys, time
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(ROOT)
D = os.path.join(ROOT, 'data')
OUTF = os.path.join(D, 'site', 'insights', 'insights.json')
VALS = os.path.join(D, 'insights', 'insights_values.json')
REPORT = os.path.join(D, 'insights', 'verify_insights.json')
sys.path.insert(0, os.path.join(ROOT, 'pipeline', 'redteam'))
from rt_findings import PASS_THROUGH_ORGS  # noqa: E402
PT = {'org-' + e for e in PASS_THROUGH_ORGS}
VIEWS = {'np-overview', 'np-flows', 'np-dependency', 'np-pay', 'np-growth', 'np-reviews', 'np-orgs', 'np-insights', 'org'}
THEMES_OK = {'spending-growth', 'outcomes', 'efficiency', 'staffing', 'budgeting-practice', 'measurement', 'capital', 'equity', 'other',
             'financial-health', 'contracting', 'concentration'}
_c = {}


def memo(k, f):
    if k not in _c:
        _c[k] = f()
    return _c[k]


def J(p):
    return json.load(open(os.path.join(D, p)))


# ------------------------------------------------------------------------------------------------ loaders
def deflator():
    return memo('d', lambda: {int(k): v for k, v in J('site/meta.json')['deflator']['index'].items()})


def org_index():
    return memo('o', lambda: {o['id']: o for o in J('site/orgs/index.json')['orgs']})


def cell_rows():
    def f():
        rows = []
        for p in sorted(glob.glob(os.path.join(D, 'site', 'payments', 'cells_*.json'))):
            rows += json.load(open(p))['cells']
        return rows
    return memo('cells', f)


def paid(real=False):
    """org -> fy -> dollars."""
    def f():
        m = defaultdict(lambda: defaultdict(float)); df = deflator()
        for r in cell_rows():
            m[r['org']][r['fy']] += r['amt'] / df[r['fy']] if real else r['amt']
        return m
    return memo(f'paid{real}', f)


def year_total(fy, real=False, keep=lambda o: True):
    return sum(v.get(fy, 0.0) for o, v in paid(real).items() if keep(o))


def area_total(fy, area, keep=lambda o: True):
    oi = org_index()
    return sum(v.get(fy, 0.0) for o, v in paid(True).items() if oi[o]['area'] == area and keep(o))


def dept_total(dept, fy, real=True):
    df = deflator()
    return sum(r['amt'] / (df[r['fy']] if real else 1.0) for r in cell_rows() if r['dept'] == dept and r['fy'] == fy)


def fin_rows():
    def f():
        out = []
        pd_ = paid(False)
        for p in sorted(glob.glob(os.path.join(D, 'site', 'finances', 'form990_20*.json'))):
            for r in json.load(open(p))['rows']:
                r = dict(r)
                r['city'] = pd_.get(r['org'], {}).get(r['fy'], 0.0)
                r['dep'] = r['city'] / r['total_revenue'] if (r['total_revenue'] or 0) > 0 else None
                out.append(r)
        return out
    return memo('fin', f)


def fin_by(org, fy):
    def f():
        return {(r['org'], r['fy']): r for r in fin_rows()}
    return memo('finby', f).get((org, fy))


def med(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return st.median(xs) if xs else None


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def top_n(fy, n, keep=lambda o: True, positive=True):
    items = [(v.get(fy, 0.0), o) for o, v in paid(False).items() if keep(o) and (v.get(fy, 0.0) > 0 or not positive)]
    return {o for _, o in sorted(items, reverse=True)[:n]}


def rt():
    return memo('rt', lambda: {f['id']: f for f in J('redteam/redteam.json')['findings']})


def rt_check(fid, name):
    return next(c['result'] for c in rt()[fid]['checks'] if c['check'] == name)


def name(o):
    return spec.disp(org_index()[o]['name'])


# ------------------------------------------------------------------------------------------------ recomputations
AREAS = ['homeless', 'youth', 'health', 'human', 'workforce', 'other', 'arts']
LAB = {'homeless': 'Homelessness and housing', 'youth': 'Children, youth and families', 'health': 'Health and behavioral health',
       'human': 'Human services and seniors', 'workforce': 'Workforce and economic development', 'other': 'Other', 'arts': 'Arts and culture'}


def v_growth_areas():
    V = {'t16': year_total(2016, True), 't25': year_total(2025, True)}
    V['g'] = V['t25'] / V['t16'] - 1; V['dtot'] = V['t25'] - V['t16']
    for a in AREAS:
        V['d_' + a] = area_total(2025, a) - area_total(2016, a)
        V['sh_' + a] = V['d_' + a] / V['dtot']; V['g_' + a] = area_total(2025, a) / area_total(2016, a) - 1
    V['sh_top3'] = V['sh_homeless'] + V['sh_youth'] + V['sh_health']
    V['rel'] = V['g_homeless'] / V['g_health']
    V['nom_x'] = year_total(2025) / year_total(2016)
    d19 = V['t25'] - year_total(2019, True)
    V['sh19_homeless'] = (area_total(2025, 'homeless') - area_total(2019, 'homeless')) / d19
    V['sh19_top3'] = sum(area_total(2025, a) - area_total(2019, a) for a in AREAS[:3]) / d19
    V['sh26_homeless'] = (area_total(2026, 'homeless') - area_total(2016, 'homeless')) / (year_total(2026, True) - V['t16'])
    k = lambda o: o not in PT
    dx = year_total(2025, True, k) - year_total(2016, True, k)
    V['shx_homeless'] = (area_total(2025, 'homeless', k) - area_total(2016, 'homeless', k)) / dx
    V['shx_youth'] = (area_total(2025, 'youth', k) - area_total(2016, 'youth', k)) / dx
    V['g_us'] = rt_check('real_growth_fy2016_2025', 'U.S. city-average CPI-U instead')
    V['g_svc'] = rt_check('real_growth_fy2016_2025', 'U.S. CPI-U services instead (nonprofit costs are mostly wages)')
    CH = {'x': ['FY2016 total'] + [LAB[a] for a in AREAS] + ['FY2025 total'],
          'v': [V['t16'] / 1e6] + [V['d_' + a] / 1e6 for a in AREAS] + [V['t25'] / 1e6]}
    return V, CH


def fund_rows():
    def f():
        import pandas as pd
        vm = pd.read_parquet(os.path.join(D, 'interim', 'vendor_map.parquet'), columns=['vendor', 'ein'])
        ids = {o[4:] for o in org_index()}
        v2e = {}
        for v, e in zip(vm.vendor, vm.ein):
            if e in ids and v not in v2e:
                v2e[v] = e
        rows = []
        for p in sorted(glob.glob(os.path.join(D, 'raw', 'insights', 'payments_fund_fy*.csv'))):
            with open(p, newline='', encoding='utf-8') as fh:
                for r in csv.DictReader(fh):
                    if r['vendor'] in v2e:
                        rows.append((int(r['fiscal_year']), r['department_code'], r['fund_type_code'], r['fund'], float(r['paid'] or 0)))
        return rows
    return memo('funds', f)


def fund_org():
    """(fy, org, fund, paid) rows for matched organizations."""
    def f():
        import pandas as pd
        vm = pd.read_parquet(os.path.join(D, 'interim', 'vendor_map.parquet'), columns=['vendor', 'ein'])
        ids = {o[4:] for o in org_index()}
        v2e = {}
        for v, e in zip(vm.vendor, vm.ein):
            if e in ids and v not in v2e:
                v2e[v] = e
        out = []
        with open(os.path.join(D, 'raw', 'insights', 'payments_fund_fy2025.csv'), newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r['vendor'] in v2e:
                    out.append((2025, 'org-' + v2e[r['vendor']], r['fund'], float(r['paid'] or 0)))
        return out
    return memo('fo', f)


def fcat(ft, fund):
    if ft == 'GEN_FUND' or fund == 'General Fund':
        return 'gf'
    if 'Our City Our Home' in fund or 'OCOH' in fund:
        return 'ocoh'
    if fund == 'Children and Families Fund':
        return 'cff'
    if fund == "Children's Fund" or 'Dignity' in fund:
        return 'cdf'
    return 'oth'


def v_funding():
    T = defaultdict(float)
    for fy, dept, ft, fund, amt in fund_rows():
        T[(fy, fcat(ft, fund))] += amt
    cats = ['gf', 'ocoh', 'cff', 'cdf', 'oth']
    tot = lambda y: sum(T[(y, c)] for c in cats)
    V = {'t19': tot(2019), 't25': tot(2025)}; V['dt'] = V['t25'] - V['t19']
    for c in cats:
        V[c + '19'], V[c + '25'] = T[(2019, c)], T[(2025, c)]; V['d_' + c] = V[c + '25'] - V[c + '19']; V['sh_' + c] = V['d_' + c] / V['dt']
    V['sh_ded'] = V['sh_ocoh'] + V['sh_cff'] + V['sh_cdf']
    V['gf_g'] = V['gf25'] / V['gf19'] - 1; V['gf_share19'] = V['gf19'] / V['t19']; V['gf_share25'] = V['gf25'] / V['t25']
    df = deflator()
    rd = V['t25'] - V['t19'] / df[2019]
    V['sh_ded_real'] = sum(T[(2025, c)] - T[(2019, c)] / df[2019] for c in ('ocoh', 'cff', 'cdf')) / rd
    V['sh_gf_real'] = (T[(2025, 'gf')] - T[(2019, 'gf')] / df[2019]) / rd
    d26 = tot(2026) - tot(2019)
    V['sh_ded26'] = sum(T[(2026, c)] - T[(2019, c)] for c in ('ocoh', 'cff', 'cdf')) / d26
    V['sh_gf26'] = (T[(2026, 'gf')] - T[(2019, 'gf')]) / d26
    oc = [(d, a) for fy, d, ft, fu, a in fund_rows() if fy == 2025 and fcat(ft, fu) == 'ocoh']
    V['ocoh_hom_share'] = sum(a for d, a in oc if d == 'HOM') / sum(a for d, a in oc)
    cv = defaultdict(float)
    for fy, d, ft, fu, a in fund_rows():
        if 'covid' in fu.lower():
            cv[fy] += a
    V['covid_peak_fy'] = max(cv, key=cv.get); V['covid_peak'] = cv[V['covid_peak_fy']]
    V['recon_25'] = V['t25'] - year_total(2025)
    yrs = list(range(2019, 2027))
    CH = {'x': yrs}
    for c in cats:
        CH[c] = [T[(y, c)] / 1e6 for y in yrs]
    return V, CH


def v_incumbents():
    P = paid(True)
    g = lambda o, y: P[o].get(y, 0.0)
    orgs = list(P)
    cont = [o for o in orgs if g(o, 2016) > 0 and g(o, 2025) > 0]
    ent = [o for o in orgs if g(o, 2016) <= 0 and g(o, 2025) > 0]
    ex = [o for o in orgs if g(o, 2016) > 0 and g(o, 2025) <= 0]
    V = {'t16': year_total(2016, True), 't25': year_total(2025, True), 'n_cont': len(cont), 'n_ent': len(ent), 'n_ex': len(ex)}
    V['d_cont'] = sum(g(o, 2025) - g(o, 2016) for o in cont); V['d_ent'] = sum(g(o, 2025) for o in ent); V['d_ex'] = -sum(g(o, 2016) for o in ex)
    V['dt'] = V['t25'] - V['t16']; V['sh_cont'] = V['d_cont'] / V['dt']; V['sh_ent'] = V['d_ent'] / V['dt']
    V['g_cont'] = sum(g(o, 2025) for o in cont) / sum(g(o, 2016) for o in cont) - 1
    V['g_cont_median'] = med([g(o, 2025) / g(o, 2016) for o in cont]) - 1
    top = top_n(2025, 20)
    V['sh_top20_growth'] = sum(g(o, 2025) - g(o, 2016) for o in top) / V['dt']
    c19 = [o for o in orgs if g(o, 2019) > 0 and g(o, 2025) > 0]
    V['sh_cont19'] = sum(g(o, 2025) - g(o, 2019) for o in c19) / (V['t25'] - year_total(2019, True))
    never = [o for o in orgs if g(o, 2025) > 0 and all(g(o, y) <= 0 for y in range(2007, 2017))]
    V['sh_never'] = sum(g(o, 2025) for o in never) / V['dt']
    sh = []
    for y in range(2008, 2027):
        sh.append(sum(g(o, y) for o in orgs if g(o, y) > 0 and g(o, y - 1) <= 0) / sum(g(o, y) for o in orgs))
    V['ent_share_avg'] = mean(sh); V['ent_share_max'] = max(sh)
    kx = [o for o in orgs if o not in PT]
    cx = [o for o in kx if g(o, 2016) > 0 and g(o, 2025) > 0]
    V['sh_cont_x'] = sum(g(o, 2025) - g(o, 2016) for o in cx) / (sum(g(o, 2025) for o in kx) - sum(g(o, 2016) for o in kx))
    V['med16'] = med([g(o, 2016) for o in orgs if g(o, 2016) > 0]); V['med25'] = med([g(o, 2025) for o in orgs if g(o, 2025) > 0])
    CH = {'x': ['FY2016 total', 'Organizations that stopped', 'Growth at continuing organizations', 'Organizations new since FY2016', 'FY2025 total'],
          'v': [V['t16'] / 1e6, V['d_ex'] / 1e6, V['d_cont'] / 1e6, V['d_ent'] / 1e6, V['t25'] / 1e6]}
    return V, CH


def v_stepup():
    r = {y: year_total(y, True) for y in range(2007, 2027)}
    V = {f'r{y}': r[y] for y in (2016, 2019, 2021, 2025, 2026)}
    V['g19_21'] = r[2021] / r[2019] - 1; V['g21_25'] = r[2025] / r[2021] - 1; V['g19_25'] = r[2025] / r[2019] - 1; V['g25_26'] = r[2026] / r[2025] - 1
    b = rt_check('real_growth_fy2016_2025', 'Benchmark: nominal growth FY2019-FY2025, this dashboard vs the Controller\'s dataset')
    V['ctrl_nom'], V['dash_nom'] = b['controller'], b['dashboard']
    fv, _ = v_funding(); V['covid_peak'], V['covid_peak_fy'] = fv['covid_peak'], fv['covid_peak_fy']
    n = defaultdict(set)
    for c in cell_rows():
        if c['amt'] > 0:
            n[c['fy']].add(c['org'])
    V['n19'], V['n25'] = len(n[2019]), len(n[2025])
    k = lambda o: o not in PT
    V['g19_25_x'] = year_total(2025, True, k) / year_total(2019, True, k) - 1
    t10 = {o for _, o in sorted(((v.get(2025, 0.0), o) for o, v in paid().items()), reverse=True)[:10]}
    V['g19_25_t10'] = year_total(2025, True, lambda o: o not in t10) / year_total(2019, True, lambda o: o not in t10) - 1
    P = paid(True)
    V['med19'] = med([v.get(2019, 0) for v in P.values() if v.get(2019, 0) > 0]); V['med25'] = med([v.get(2025, 0) for v in P.values() if v.get(2025, 0) > 0])
    CH = {'x': list(range(2007, 2027)), 'v': [r[y] / 1e6 for y in range(2007, 2027)]}
    return V, CH


def v_churn():
    yrs = list(range(2007, 2027))
    top = {y: top_n(y, 20) for y in yrs}
    new = {y: len(top[y] - top[y - 1]) for y in yrs[1:]}
    V = {'kept_16_25': len(top[2016] & top[2025]), 'always': len(set.intersection(*top.values())), 'ever': len(set.union(*top.values()))}
    V['avg_pre'] = mean(new[y] for y in range(2009, 2018)); V['avg_post'] = mean(new[y] for y in range(2019, 2027))
    seen, first = set(top[2007]), {}
    for y in yrs[1:]:
        first[y] = len(top[y] - seen); seen |= top[y]
    V['ft_pre'] = mean(first[y] for y in range(2009, 2018)); V['ft_post'] = mean(first[y] for y in range(2019, 2027))
    sh = {y: sum(paid()[o][y] for o in top[y]) / year_total(y) for y in yrs}
    V['sh16'], V['sh25'] = sh[2016], sh[2025]; V['sh_min'] = min(sh[y] for y in yrs[1:]); V['sh_max'] = max(sh[y] for y in yrs[1:])
    t50 = {y: top_n(y, 50, positive=False) for y in yrs}
    V['t50_pre'] = mean(len(t50[y] - t50[y - 1]) for y in range(2009, 2018)); V['t50_post'] = mean(len(t50[y] - t50[y - 1]) for y in range(2019, 2027))
    t25 = sorted(top[2025], key=lambda o: -paid()[o][2025])
    nc = [o for o in t25 if paid()[o].get(2016, 0) < 1e6]
    V['n_newcomers'] = len(nc)
    for i, o in enumerate(nc[:3]):
        V[f'nc{i}_25'] = paid()[o][2025]
    kx = lambda o: o not in PT
    tx = {y: top_n(y, 20, kx, positive=False) for y in yrs}
    V['x_pre'] = mean(len(tx[y] - tx[y - 1]) for y in range(2009, 2018)); V['x_post'] = mean(len(tx[y] - tx[y - 1]) for y in range(2019, 2027))
    CH = {'x': yrs[1:], 'v': [new[y] for y in yrs[1:]]}
    return V, CH


def v_dep_flat():
    big = lambda fy, real=False: [r for r in fin_rows() if r['fy'] == fy and (r['total_revenue'] or 0) > 0 and
                                  (r['city'] / (deflator()[fy] if real else 1.0)) >= 1e6]
    V = {'med16': med(r['dep'] for r in big(2016)), 'med24': med(r['dep'] for r in big(2024)), 'n16': len(big(2016)), 'n24': len(big(2024))}
    V['gt75_16'] = mean(r['dep'] > 0.75 for r in big(2016)); V['gt75_24'] = mean(r['dep'] > 0.75 for r in big(2024))
    meds = {y: med(r['dep'] for r in big(y)) for y in range(2012, 2026)}
    V['med_min'], V['med_max'] = min(meds.values()), max(meds.values()); V['med25'] = meds[2025]
    a = {r['org']: r for r in big(2016)}; b = {r['org']: r for r in big(2024)}
    ids = [o for o in a if o in b]
    V['panel_n'] = len(ids); V['panel_a'] = med(a[o]['dep'] for o in ids); V['panel_b'] = med(b[o]['dep'] for o in ids)
    V['panel_city_g'] = sum(b[o]['city'] for o in ids) / sum(a[o]['city'] for o in ids) - 1
    V['medx16'] = med(r['dep'] for r in big(2016) if r['org'] not in PT); V['medx24'] = med(r['dep'] for r in big(2024) if r['org'] not in PT)
    V['med16_real'] = med(r['dep'] for r in big(2016, True)); V['med24_real'] = med(r['dep'] for r in big(2024, True))
    V['med24_pro'] = rt_check('dependency', 'Variant: prorated_to_tax_year')['median']
    CH = {'x': list(range(2012, 2026)), 'med': [meds[y] * 100 for y in range(2012, 2026)],
          'gt75': [mean(r['dep'] > 0.75 for r in big(y)) * 100 for y in range(2012, 2026)]}
    return V, CH


def v_fast_risers():
    by = defaultdict(list)
    for r in fin_rows():
        if (r['total_revenue'] or 0) >= 5e5 and r['dep'] is not None:
            by[r['org']].append((r['fy'], r['dep'], r['city']))

    def first_hit(vals, lo_end):
        for i, (y0, d0, c0) in enumerate(vals):
            if d0 < 0.25:
                for y1, d1, c1 in vals[i + 1:]:
                    if y1 - y0 <= 5 and lo_end <= d1 <= 1.05 and c1 >= 2e6:
                        return (y0, d0, c0, y1, d1, c1)
        return None
    hits = []
    n50 = 0
    for o, vals in by.items():
        vals.sort()
        h = first_hit(vals, 0.6)
        if h:
            hits.append((o,) + h)
        n50 += first_hit(vals, 0.5) is not None
    hits.sort(key=lambda h: -h[6])
    V = {'n': len(hits), 'n50': n50, 'n_x': sum(1 for h in hits if h[0] not in PT), 'x_drop': ', '.join(name(h[0]) for h in hits if h[0] in PT)}
    for i, h in enumerate(hits[:6]):
        V[f'o{i}_y0'], V[f'o{i}_d0'], V[f'o{i}_c0'], V[f'o{i}_y1'], V[f'o{i}_d1'], V[f'o{i}_c1'] = h[1], h[2], h[3], h[4], h[5], h[6]
    latest = {}
    for r in fin_rows():
        if r['org'] not in latest or r['fy'] > latest[r['org']]['fy']:
            latest[r['org']] = r
    V['n_still'] = sum(1 for h in hits if (latest[h[0]]['dep'] or 0) >= 0.5)
    V['n_conf'] = sum(1 for h in hits if any(((fin_by(h[0], h[4] + k) or {}).get('dep') or 0) >= 0.5 for k in (1, 2)))
    CH = {'x': ['Before', 'After'], 'names': [name(h[0]) for h in hits[:6]], 'd0': [h[2] * 100 for h in hits[:6]], 'd1': [h[5] * 100 for h in hits[:6]]}
    return V, CH


BANDS = [(0, 0.25, 'Under 25%'), (0.25, 0.5, '25–50%'), (0.5, 0.75, '50–75%'), (0.75, 99, '75% or more')]


def v_reserves():
    def rows(fy):
        return [r for r in fin_rows() if r['fy'] == fy and r['city'] >= 1e6 and (r['total_revenue'] or 0) > 0 and r['months_reserves'] is not None]
    g = rows(2024)
    V = {}
    for i, (lo, hi, _) in enumerate(BANDS):
        b = [r for r in g if lo <= r['dep'] < hi]
        V[f'b{i}_lt1'] = mean(r['months_reserves'] < 1 for r in b); V[f'b{i}_n'] = len(b); V[f'b{i}_med'] = med(r['months_reserves'] for r in b)
    H = [r for r in g if r['dep'] >= 0.75]; L = [r for r in g if r['dep'] < 0.75]
    V['hi_lt1'], V['lo_lt1'] = mean(r['months_reserves'] < 1 for r in H), mean(r['months_reserves'] < 1 for r in L)
    V['hi_k'], V['lo_k'] = sum(r['months_reserves'] < 1 for r in H), sum(r['months_reserves'] < 1 for r in L)
    V['hi_n'], V['lo_n'] = len(H), len(L); V['hi_med'], V['lo_med'] = med(r['months_reserves'] for r in H), med(r['months_reserves'] for r in L)
    V['ratio'] = V['hi_lt1'] / V['lo_lt1']
    V['hi_def'] = mean(r['total_expenses'] > r['total_revenue'] for r in H); V['lo_def'] = mean(r['total_expenses'] > r['total_revenue'] for r in L)
    for fy in (2023, 2025):
        x = rows(fy)
        V[f'hi_lt1_{fy}'] = mean(r['months_reserves'] < 1 for r in x if r['dep'] >= 0.75); V[f'lo_lt1_{fy}'] = mean(r['months_reserves'] < 1 for r in x if r['dep'] < 0.75)
    gx = [r for r in g if r['org'] not in PT and r['dep'] <= 1]
    V['x_hi'] = mean(r['months_reserves'] < 1 for r in gx if r['dep'] >= 0.75); V['x_lo'] = mean(r['months_reserves'] < 1 for r in gx if r['dep'] < 0.75)
    V['hi_lt2'] = mean(r['months_reserves'] < 2 for r in H); V['lo_lt2'] = mean(r['months_reserves'] < 2 for r in L)
    CH = {'x': [b[2] for b in BANDS], 'v': [V[f'b{i}_lt1'] * 100 for i in range(4)], 'n': [V[f'b{i}_n'] for i in range(4)]}
    return V, CH


def v_corrective():
    A = []
    for r in J('site/reviews/findings.json')['rows']:
        if r['fy'] in (2023, 2024, 2025):
            f = fin_by(r['org'], r['fy'])
            if f and (f['total_revenue'] or 0) > 0:
                A.append((r['org'], f['city'] / f['total_revenue'], r['result'] in ('corrective', 'elevated', 'redflag')))
    H = [a for a in A if a[1] >= 0.75]; L = [a for a in A if a[1] < 0.75]
    V = {'n': len(A), 'n_orgs': len({a[0] for a in A}), 'n_hi': len(H), 'n_lo': len(L), 'sev_hi': sum(a[2] for a in H), 'sev_lo': sum(a[2] for a in L)}
    V['rate_hi'], V['rate_lo'] = V['sev_hi'] / V['n_hi'], V['sev_lo'] / V['n_lo']; V['ratio'] = V['rate_hi'] / V['rate_lo']
    V['sev_total'] = sum(a[2] for a in A); V['sev_orgs'] = len({a[0] for a in A if a[2]})
    og = defaultdict(list)
    for o, d, s in A:
        og[o].append((d, s))
    od = {o: (med(d for d, _ in v), any(s for _, s in v)) for o, v in og.items()}
    V['org_hi_n'] = sum(1 for d, s in od.values() if d >= 0.75); V['org_hi_sev'] = sum(1 for d, s in od.values() if d >= 0.75 and s)
    V['org_lo_n'] = sum(1 for d, s in od.values() if d < 0.75); V['org_lo_sev'] = sum(1 for d, s in od.values() if d < 0.75 and s)
    ci = rt()['dependency_corrective_action']['cite']
    V['or_adj'], V['or_lo'], V['or_hi'] = ci['assoc_or_adj'], ci['assoc_or_adj_lo'], ci['assoc_or_adj_hi']
    V['perm_p'] = rt_check('dependency_corrective_action', 'Organization-level permutation (labels shuffled by organization)')
    V['or_res'] = rt_check('dependency_corrective_action', 'Same, also controlling for under one month of reserves')[0]
    V['mh_min'] = min(rt_check('dependency_corrective_action', 'Mantel-Haenszel risk ratio stratified by size band / service area / fiscal year'))
    fy1 = rt_check('dependency_corrective_action', 'First monitored year per organization only (the tier policy began in FY2024, so few events)')
    V['first_hi'], V['first_lo'] = fy1['sev_hi'], fy1['sev_lo']
    bands = [[a for a in A if lo <= a[1] < hi] for lo, hi, _ in BANDS]
    CH = {'x': [b[2] for b in BANDS], 'v': [mean(a[2] for a in b) * 100 for b in bands], 'n': [len(b) for b in bands]}
    return V, CH


def v_contract_growth():
    L = J('redteam/parts/contracts_llm.json'); Dd = J('redteam/parts/doubled_contracts.json')
    V = {'n_con': len(J('site/contracts/contracts.json')['contracts']), 'n_dbl': len(Dd)}
    V['n_ext'] = sum(1 for c in Dd if (c['term_extended_days'] or 0) >= 182)
    V['n_ann2'] = sum(1 for c in Dd if c['annualized_ratio'] is not None and c['annualized_ratio'] >= 2)
    V['n_ann_lt15'] = sum(1 for c in Dd if c['annualized_ratio'] is not None and c['annualized_ratio'] < 1.5)
    V['n_rr'] = sum(1 for c in Dd if c['run_rate_ratio'] is not None); V['n_rr15'] = sum(1 for c in Dd if (c['run_rate_ratio'] or 0) >= 1.5)
    for k in ('extension', 'expansion', 'funding_increment', 'rate_or_volume'):
        V['llm_' + k] = sum(1 for x in L if x['primary_driver'] == k)
    V['cannot_tell'] = sum(1 for x in L if x['text_shows_new_scope_or_sites'] == 'cannot_tell')
    hi = [x for x in L if x['confidence'] >= 0.7]
    V['hi_n'] = len(hi); V['hi_ext'] = sum(1 for x in hi if x['primary_driver'] == 'extension')
    CH = {'x': ['Mainly a longer term', 'Mainly a larger yearly amount', 'Funding for years already in the term', 'Higher rates or volume'],
          'v': [V['llm_extension'], V['llm_expansion'], V['llm_funding_increment'], V['llm_rate_or_volume']]}
    return V, CH


def contracts_all():
    def f():
        out = []
        for p in sorted(glob.glob(os.path.join(D, 'site', 'contracts', 'all_*.json'))):
            for c in json.load(open(p))['contracts']:
                s = c.get('start') or ''
                m = re.match(r'(\d{4})-(\d{2})', s)
                c = dict(c); c['sfy'] = (int(m.group(1)) + (int(m.group(2)) >= 7)) if m else None
                out.append(c)
        return out
    return memo('con', f)


def raw_contracts():
    def f():
        with open(os.path.join(D, 'raw', 'supplier_contracts.csv'), newline='', encoding='utf-8') as fh:
            return list(csv.DictReader(fh))
    return memo('rawc', f)


def v_emergency():
    C = contracts_all()
    em = lambda c: c['authority_class'] == 'emergency_or_waiver'
    V = {'em_total': sum(c['agreed'] for c in C if em(c)), 'all_total': sum(c['agreed'] for c in C), 'n_em': sum(map(em, C)), 'n_all': len(C)}
    V['em_share'] = V['em_total'] / V['all_total']; V['em_hom'] = sum(c['agreed'] for c in C if em(c) and c['dept'] == 'HOM') / V['em_total']

    def share(y, pool=C, count=False):
        s = [c for c in pool if c['sfy'] == y]
        if count:
            return sum(map(em, s)) / len(s)
        return sum(c['agreed'] for c in s if em(c)) / sum(c['agreed'] for c in s)
    for y in (2019, 2021, 2022, 2024, 2025, 2026):
        V[f'sh{str(y)[2:]}'] = share(y)
    V['shn21'], V['shn25'] = share(2021, count=True), share(2025, count=True)
    V['big21'] = share(2021, [c for c in C if c['agreed'] >= 1e6]); V['nh21'] = share(2021, [c for c in C if c['dept'] != 'HOM'])
    top5 = {c['id'] for c in sorted([c for c in C if c['sfy'] == 2021], key=lambda c: -c['agreed'])[:5]}
    V['x5_21'] = share(2021, [c for c in C if c['id'] not in top5])
    auth = {}
    for r in raw_contracts():
        if r['Supplier Type'] == 'Prime Contractor' and r['Contract Number'] not in auth:
            auth[r['Contract Number']] = r['Purchasing Authority']
    late = [c for c in C if em(c) and (c['sfy'] or 0) >= 2024]
    V['core_share'] = sum(c['agreed'] for c in late if auth.get(c['id'], '').upper().startswith('CORE INITIATIVES ADDRESSING HOMELESSNESS')) / sum(c['agreed'] for c in late)
    yrs = list(range(2018, 2027))
    CH = {'x': yrs, 'v': [share(y) * 100 for y in yrs]}
    return V, CH


def v_exec_pay():
    def gaps(fy, large=False, nopass=False):
        E = [r for r in fin_rows() if (not nopass or r['org'] not in PT) and r['fy'] == fy and (r['exec_comp'] or 0) > 0 and (r['total_expenses'] or 0) >= 1e6 and r['city'] > 0
             and (r['total_revenue'] or 0) > 0 and (not large or r['city'] >= 1e6)]
        x = np.array([math.log(r['total_expenses']) for r in E]); y = np.array([math.log(r['exec_comp']) for r in E])
        b1, b0 = np.polyfit(x, y, 1)
        res = y - (b0 + b1 * x)
        out = {'b': b1, 'n': len(E)}
        for i, (lo, hi, _) in enumerate(BANDS):
            m = [res[k] for k, r in enumerate(E) if lo <= r['dep'] < hi]
            out[f'g{i}'] = math.exp(st.median(m)) - 1; out[f'n{i}'] = len(m)
        areas = sorted({org_index()[r['org']]['area'] for r in E})[1:]
        X = np.column_stack([np.ones(len(E)), x] + [np.array([org_index()[r['org']]['area'] == a for r in E], float) for a in areas] +
                            [np.array([lo <= r['dep'] < hi for r in E], float) for lo, hi, _ in BANDS[1:]])
        out['adj_hi'] = math.exp(np.linalg.lstsq(X, y, rcond=None)[0][-1]) - 1
        out['med_hi'] = st.median([r['exec_comp'] for r in E if r['dep'] >= 0.75]); out['med_lo'] = st.median([r['exec_comp'] for r in E if r['dep'] < 0.25])
        return out
    g = gaps(2024)
    V = {'n': g['n'], 'b': g['b'], 'g_hi': g['g3'], 'g_lo': g['g0'], 'n_hi': g['n3'], 'adj_hi': g['adj_hi'], 'med_hi': g['med_hi'], 'med_lo': g['med_lo']}
    for fy in (2022, 2023, 2025):
        V[f'g_hi_{fy}'] = gaps(fy)['g3']
    V['large_g_hi'] = gaps(2024, True)['g3']; V['x_g_hi'] = gaps(2024, nopass=True)['g3']
    CH = {'x': [b[2] for b in BANDS], 'v': [g[f'g{i}'] * 100 for i in range(4)], 'n': [g[f'n{i}'] for i in range(4)]}
    return V, CH


def outcome(dept, measure):
    return {r['fiscal_year']: r['value'] for r in J('site/aggregates/outcomes.json')['rows'] if r['department_code'] == dept and r['measure'] == measure}


def v_homeless_pit():
    tot, uns = outcome('HOM', 'pit_total'), outcome('HOM', 'pit_unsheltered')
    s = {y: dept_total('HOM', y) for y in (2019, 2024, 2026)}
    V = {'s19': s[2019], 's26': s[2026], 's24': s[2024], 's_g': s[2026] / s[2019] - 1, 'tot19': tot[2019], 'tot26': tot[2026], 'uns19': uns[2019], 'uns26': uns[2026]}
    V['sh19'], V['sh26'] = tot[2019] - uns[2019], tot[2026] - uns[2026]
    V['d_uns'] = uns[2019] - uns[2026]; V['d_sh'] = V['sh26'] - V['sh19']
    V['tot_g'] = tot[2026] / tot[2019] - 1; V['uns_g'] = uns[2026] / uns[2019] - 1; V['sh_g'] = V['sh26'] / V['sh19'] - 1
    V['tot_g24'] = tot[2024] / tot[2019] - 1; V['uns_g24'] = uns[2024] / uns[2019] - 1; V['s_g24'] = s[2024] / s[2019] - 1
    V['area_g'] = area_total(2026, 'homeless') / area_total(2019, 'homeless') - 1
    V['s_g_nom'] = dept_total('HOM', 2026, False) / dept_total('HOM', 2019, False) - 1
    CH = {'x': ['HSH payments to nonprofits (real)', 'People in shelter', 'Total homeless count', 'People unsheltered'],
          'v': [V['s_g'] * 100, V['sh_g'] * 100, V['tot_g'] * 100, V['uns_g'] * 100]}
    return V, CH


MEAS = [('CHF', 'children_youth_served', 2019, 2025, 'Children and youth served (DCYF)'), ('DPH', 'unique_mental_health_clients', 2020, 2025, 'Mental health clients (DPH)'),
        ('DPH', 'unique_substance_use_clients', 2020, 2025, 'Substance use clients (DPH)'), ('HOM', 'households_placed_psh_rrh_ps', 2023, 2025, 'Households placed in housing (HSH)'),
        ('HSA', 'home_delivered_meals_older_adults', 2018, 2025, 'Home-delivered meals, older adults (HSA)')]


def v_measures():
    V = {}
    for i, (d, m, a, b, _) in enumerate(MEAS):
        o = outcome(d, m)
        V[f's{i}'] = dept_total(d, b) / dept_total(d, a) - 1; V[f'm{i}'] = o[b] / o[a] - 1; V[f'c{i}'] = (1 + V[f's{i}']) / (1 + V[f'm{i}']) - 1
    V['s_min'] = min(V[f's{i}'] for i in range(5)); V['s_max'] = max(V[f's{i}'] for i in range(5)); V['n_up'] = sum(V[f'c{i}'] > 0 for i in range(5))
    c = outcome('CHF', 'children_youth_served')
    V['chf22_s'] = dept_total('CHF', 2025) / dept_total('CHF', 2022) - 1; V['chf22_m'] = c[2025] / c[2022] - 1
    V['chf24_s'] = dept_total('CHF', 2024) / dept_total('CHF', 2019) - 1; V['chf24_m'] = c[2024] / c[2019] - 1
    h = outcome('HOM', 'households_placed_psh_rrh_ps')
    V['hom26_s'] = dept_total('HOM', 2026) / dept_total('HOM', 2023) - 1; V['hom26_m'] = h[2026] / h[2023] - 1
    CH = {'x': [m[4] for m in MEAS], 'spend': [V[f's{i}'] * 100 for i in range(5)], 'served': [V[f'm{i}'] * 100 for i in range(5)]}
    return V, CH


def text(fy):
    return open(os.path.join(D, 'reviews', 'text', f'monitoring_FY{fy}_annual_report.txt'), encoding='utf-8').read().replace('\n', ' ')


def v_monitoring():
    R = J('site/reviews/findings.json')['rows']
    V = {}
    for fy in (2022, 2023, 2024, 2025):
        g = [r for r in R if r['fy'] == fy]
        V[f'n{fy}'] = len(g); V[f'f{fy}'] = mean(r['result'] != 'none' for r in g)
        V[f'tier{fy}'] = sum(r['result'] in ('corrective', 'elevated', 'redflag') for r in g)
    V['fy19_conf'] = int(re.search(r'FY19, (\d+)% of monitored contractors ended the cycle in full conformance', text(23)).group(1)) / 100
    V['f2019'] = 1 - V['fy19_conf']
    for fy in (22, 23, 24):
        V[f'w{fy}'] = int(re.search(r'granted (\d+) contractors a waiver', text(fy)).group(1))
    V['fy23_unres'] = int(re.search(r'Forty-six nonprofits \((\d+)%\) had unresolved', text(23)).group(1)) / 100
    a = {r['org']: r['result'] for r in R if r['fy'] == 2022}; b = {r['org']: r['result'] for r in R if r['fy'] == 2023}
    both = [o for o in a if o in b]
    V['panel_n'] = len(both); V['panel_f22'] = mean(a[o] != 'none' for o in both); V['panel_f23'] = mean(b[o] != 'none' for o in both)
    CH = {'x': [2019, 2022, 2023, 2024, 2025], 'v': [V['f2019'] * 100] + [V[f'f{y}'] * 100 for y in (2022, 2023, 2024, 2025)]}
    return V, CH


def v_passthrough():
    P = paid()
    V = {'t25': year_total(2025)}
    pts = sorted([o for o in PT if o in P], key=lambda o: -P[o].get(2025, 0))
    V['pt25'] = sum(P[o].get(2025, 0) for o in pts); V['pt_share'] = V['pt25'] / V['t25']; V['n_pt'] = sum(P[o].get(2025, 0) > 0 for o in pts)
    cc = 'org-942221305'
    tot_cc = sum(a for (fy, o, fu, a) in fund_org() if fy == 2025 and o == cc)
    V['cc_cff_share'] = sum(a for (fy, o, fu, a) in fund_org() if fy == 2025 and o == cc and fu == 'Children and Families Fund') / tot_cc
    import pandas as pd
    al = pd.read_parquet(os.path.join(D, 'interim', 'aligned.parquet'), columns=['ein', 'period_end', 'grants_paid', 'total_expenses'])
    row = [(g, e) for ein, pe, g, e in al.itertuples(index=False) if ein == '942221305' and pe == '2025-06'][0]
    V['cc_grants_share'] = row[0] / row[1]
    V['cc16'], V['cc25'] = P[cc][2016], P[cc][2025]; V['cc_x'] = V['cc25'] / V['cc16']; V['cc_share_pt'] = V['cc25'] / V['pt25']
    ci = rt()['real_growth_fy2016_2025']['cite']
    V['g_all'], V['g_x'] = ci['real_growth_sf_cpi'], ci['real_growth_excl_passthrough']
    t = rt()['total_fy2025']['cite']
    V['ctrl25'], V['pt_contracts'], V['loans25'] = t['controller_dataset_fy2025'], t['passthrough_contracts_fy2025'], t['loans_fy2025']
    V['ctrl_gap'] = V['t25'] - V['ctrl25']; V['pt_noloan'] = V['pt25'] - V['loans25']
    V['pt16'] = sum(P[o].get(2016, 0) for o in pts); V['pt_share16'] = V['pt16'] / year_total(2016)
    CH = {'x': [name(o) for o in pts[:7]], 'v': [P[o][2025] / 1e6 for o in pts[:7]]}
    return V, CH


def v_base_year():
    r = {y: year_total(y, True) for y in range(2013, 2026)}
    yrs = list(range(2013, 2020))
    V = {f'g{y}': r[2025] / r[y] - 1 for y in yrs}
    V['g_min'] = min(V[f'g{y}'] for y in (2015, 2016, 2017)); V['g_max'] = max(V[f'g{y}'] for y in (2015, 2016, 2017))
    V['dip18'] = r[2018] / r[2017] - 1; V['jump19'] = r[2019] / r[2018] - 1
    V['dph17'], V['dph18'], V['dph19'] = (dept_total('DPH', y, False) for y in (2017, 2018, 2019))
    V['cagr17'] = (r[2025] / r[2017]) ** (1 / 8) - 1
    V['cagr'] = (r[2025] / r[2016]) ** (1 / 9) - 1; V['cagr_1319'] = (r[2025] / r[2013]) ** (1 / 12) - 1
    ci = rt()['real_growth_fy2016_2025']['cite']
    V['g_us'], V['rt_g2017'] = ci['real_growth_us_cpi'], ci['real_growth_from_fy2017']
    CH = {'x': [f'From FY{y}' for y in yrs], 'v': [V[f'g{y}'] * 100 for y in yrs]}
    return V, CH


def v_subcontractors():
    rows = raw_contracts()
    sub = {r['Contract Number'] for r in rows if r['Supplier Type'] != 'Prime Contractor'}
    prime, seen = [], set()
    for r in rows:
        if r['Supplier Type'] == 'Prime Contractor' and r['Contract Number'] not in seen:
            seen.add(r['Contract Number']); prime.append(r)
    isnp = lambda r: r['Non-Profit'] == 'X'
    gr = lambda r: r['Contract Type'].startswith('Grant Contract'); ps = lambda r: r['Contract Type'].startswith('Professional Services')
    hs = lambda r: r['Contract Number'] in sub
    npr = [r for r in prime if isnp(r)]; fpr = [r for r in prime if not isnp(r)]
    V = {'np_n': len(npr), 'np_sub': sum(map(hs, npr)), 'np_grant_share': mean(map(gr, npr))}
    V['fp_ps'] = mean(hs(r) for r in fpr if ps(r)); V['np_ps'] = mean(hs(r) for r in npr if ps(r))
    V['fp_ps_n'] = sum(map(ps, fpr)); V['np_ps_n'] = sum(map(ps, npr))
    G = [r for r in prime if gr(r)]
    V['gr_any'] = mean(map(hs, G)); V['gr_n'] = len(G); V['gr_sub'] = sum(map(hs, G)); V['fp_all'] = mean(map(hs, fpr))
    V['sub_findings'] = sum(c == 'Subcontracts' for r in J('site/reviews/findings.json')['rows'] for c in (r['categories'] or []))
    V['n_reviews'] = sum(2022 <= r['fy'] <= 2025 for r in J('site/reviews/findings.json')['rows'])
    C = contracts_all(); V['ours_n'] = len(C); V['ours_sub'] = sum(c['id'] in sub for c in C)
    CH = {'x': ['For-profit professional services', 'Nonprofit professional services', 'Grant agreements (all recipients)'],
          'v': [V['fp_ps'] * 100, V['np_ps'] * 100, V['gr_any'] * 100], 'n': [V['fp_ps_n'], V['np_ps_n'], V['gr_n']]}
    return V, CH


VERIFY = {'growth_areas': v_growth_areas, 'funding': v_funding, 'incumbents': v_incumbents, 'stepup': v_stepup, 'churn': v_churn,
          'dep_flat': v_dep_flat, 'fast_risers': v_fast_risers, 'reserves': v_reserves, 'corrective': v_corrective,
          'contract_growth': v_contract_growth, 'emergency': v_emergency, 'exec_pay': v_exec_pay, 'homeless_pit': v_homeless_pit,
          'measures': v_measures, 'monitoring': v_monitoring, 'passthrough': v_passthrough, 'base_year': v_base_year,
          'subcontractors': v_subcontractors}


# ------------------------------------------------------------------------------------------------ checks
def keys_used(tpl):
    out = set()

    def walk(o):
        if isinstance(o, str):
            out.update(m.group(1) for m in spec.PH.finditer(o))
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(tpl)
    return out


def close(a, b, rel=0.005, ab=0.005):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    a, b = float(a), float(b)
    return abs(a - b) <= max(ab, rel * max(abs(a), abs(b)))


def literal_digits(tpl):
    probs = []

    def walk(o, path):
        if isinstance(o, str):
            if o.startswith('@') or path.endswith('source') or '.explore' in path or path.endswith('.id'):
                return
            t = spec.PH.sub('', o)
            for pat in spec.ALLOWED_DIGIT_TOKENS:
                t = re.sub(pat, '', t)
            if re.search(r'\d', t):
                probs.append(path)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, f'{path}.{k}')
    walk({k: v for k, v in tpl.items() if k != 'key'}, tpl['key'])
    return probs


def source_paths(src):
    """Every nonprofits/... path in a source string exists (a 'a.json … b.json' range checks both ends)."""
    bad = []
    for m in re.finditer(r'nonprofits/[\w./-]+', src):
        p = m.group(0).rstrip('.;,')
        if not os.path.exists(os.path.join(REPO, p)):
            bad.append(p)
    for m in re.finditer(r'(nonprofits/[\w./-]+/)[\w.-]+ … ([\w.-]+)', src):
        p = m.group(1) + m.group(2)
        if not os.path.exists(os.path.join(REPO, p)):
            bad.append(p)
    return bad


REQ = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'numbers', 'chart', 'robustness', 'explore']


def main():
    pub = json.load(open(OUTF)); built = json.load(open(VALS))
    tpls = {t['id']: t for t in spec.INSIGHTS}
    fails, per = [], []
    for k in ('sample', 'as_of', 'dashboard', 'intro', 'insights'):
        if k not in pub:
            fails.append(f'file: missing {k}')
    if pub.get('sample') is not False or pub.get('dashboard') != 'nonprofits':
        fails.append('file: sample must be false and dashboard "nonprofits"')
    ids = [i['id'] for i in pub['insights']]
    if len(set(ids)) != len(ids):
        fails.append('file: duplicate ids')
    if sorted(i['rank'] for i in pub['insights']) != list(range(1, len(ids) + 1)):
        fails.append('file: ranks are not 1..n')
    for ins in pub['insights']:
        t0 = time.time(); iid = ins['id']
        rec = {'id': iid, 'values_checked': 0, 'chart_points_checked': 0, 'sources_checked': 0, 'failures': []}
        F = rec['failures']
        tpl = tpls.get(iid)
        if tpl is None:
            F.append('no template'); per.append(rec); fails += [f'{iid}: no template']; continue
        key = tpl['key']
        # 5. shape
        for f in REQ:
            if f not in ins:
                F.append(f'missing field {f}')
        if ins['theme'] not in THEMES_OK:
            F.append(f'unknown theme {ins["theme"]}')
        if ins['chart']['type'] not in ('line', 'bar', 'hbar', 'dumbbell', 'slope', 'stacked', 'smallmultiples', 'scatter', 'waterfall'):
            F.append('bad chart type')
        if ins['robustness']['verdict'] not in ('robust', 'fragile'):
            F.append('bad verdict')
        if len(ins['robustness']['checks']) < 3:
            F.append('fewer than three robustness checks')
        if ins['explore']['view'] not in VIEWS:
            F.append(f'unknown view {ins["explore"]["view"]}')
        if len(ins['title']) > 92:
            F.append(f'title too long ({len(ins["title"])})')
        for s in ins['chart']['series']:
            if len(s['values']) != len(ins['chart']['x']['values']):
                F.append(f'series {s["name"]} length differs from x')
            if s.get('n') is not None and len(s['n']) != len(s['values']):
                F.append(f'series {s["name"]} n length differs')
        for n in ins['numbers']:
            if not n.get('source'):
                F.append(f'number without source: {n["label"]}')
            rec['sources_checked'] += 1
            for b in source_paths(n['source']):
                F.append(f'source path does not exist: {b}')
        # 4. literal numbers
        for p in literal_digits(tpl):
            F.append(f'literal number in template text: {p}')
        # 1. recompute
        try:
            V2, CH2 = VERIFY[key]()
        except Exception as ex:  # noqa
            import traceback; traceback.print_exc()
            F.append(f'recompute error: {ex!r}'); per.append(rec); fails += [f'{iid}: {x}' for x in F]; continue
        V1, CH1 = built[iid]['V'], built[iid]['CH']
        for k in sorted(keys_used({kk: vv for kk, vv in tpl.items() if kk != 'key'})):
            rec['values_checked'] += 1
            if k not in V2:
                F.append(f'value {k} not recomputed (untraced)')
            elif not close(V1.get(k), V2[k]):
                F.append(f'value {k}: built {V1.get(k)} vs recomputed {V2[k]}')
        # 3. chart arrays (build vs recompute)
        for ck, arr in CH1.items():
            if ck not in CH2:
                F.append(f'chart array {ck} not recomputed'); continue
            if len(arr) != len(CH2[ck]):
                F.append(f'chart array {ck}: length {len(arr)} vs {len(CH2[ck])}'); continue
            for i, (a, b) in enumerate(zip(arr, CH2[ck])):
                rec['chart_points_checked'] += 1
                ok = (a == b) if isinstance(a, str) or isinstance(b, str) else close(a, b, 0.01, 0.05)
                if not ok:
                    F.append(f'chart {ck}[{i}]: built {a} vs recomputed {b}')
        # 2. re-render text with recomputed values and compare
        try:
            from build_insights import render_insight, clean
            r2 = render_insight(tpl, {**clean(V1), **clean(V2)}, clean(CH2))
            for fld in ('title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'robustness', 'caveats'):
                a, b = json.dumps(ins.get(fld), ensure_ascii=False), json.dumps(r2.get(fld), ensure_ascii=False)
                if a != b:
                    i0 = next((i for i, (p, q) in enumerate(zip(a, b)) if p != q), min(len(a), len(b)))
                    F.append(f'{fld} differs when rendered from recomputed values: "...{a[max(0, i0 - 50):i0 + 30]}" vs "...{b[max(0, i0 - 50):i0 + 30]}"')
            c1, c2 = ins['chart'], r2['chart']
            for fld in ('type', 'title', 'subtitle', 'note', 'highlight'):
                if c1.get(fld) != c2.get(fld):
                    F.append(f'chart {fld} differs')
            if c1['x']['values'] != c2['x']['values'] and not all(close(a, b, 0.01, 0.05) for a, b in zip(c1['x']['values'], c2['x']['values'])):
                F.append('published chart x differs')
            if len(c1['series']) != len(c2['series']):
                F.append('series count differs')
            for s1, s2 in zip(c1['series'], c2['series']):
                if s1['name'] != s2['name']:
                    F.append(f'series name {s1["name"]} vs {s2["name"]}')
                for i, (a, b) in enumerate(zip(s1['values'], s2['values'])):
                    rec['chart_points_checked'] += 1
                    if not close(a, b, 0.01, 0.05):
                        F.append(f'published series {s1["name"]}[{i}]: {a} vs recomputed {b}')
        except Exception as ex:  # noqa
            F.append(f'render error: {ex!r}')
        print(f'{iid}: {rec["values_checked"]} values, {rec["chart_points_checked"]} chart points, {rec["sources_checked"]} sources, '
              f'{len(F)} failures ({time.time() - t0:.1f}s)', flush=True)
        for f in F[:10]:
            print('   FAIL', f)
        per.append(rec); fails += [f'{iid}: {x}' for x in F]
    rep = {'as_of': spec.AS_OF, 'insights': len(pub['insights']), 'values_checked': sum(r['values_checked'] for r in per),
           'chart_points_checked': sum(r['chart_points_checked'] for r in per), 'sources_checked': sum(r['sources_checked'] for r in per),
           'failures': fails, 'per_insight': per, 'method': __doc__.strip().split('\n\n')[1]}
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    json.dump(rep, open(REPORT, 'w'), indent=1, default=float)
    print(f'\n{rep["insights"]} insights, {rep["values_checked"]} values, {rep["chart_points_checked"]} chart points and '
          f'{rep["sources_checked"]} sources checked; {len(fails)} failures')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
