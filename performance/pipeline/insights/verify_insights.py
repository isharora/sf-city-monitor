"""Independent verification of performance/data/site/insights/insights.json.

For every insight this script recomputes each named value (V) and chart array (CH) from the RAW source tables in
data/raw (DataSF downloads, BLS CPI, DOF population, NTD, call-level Fire/Police records, survey microdata, the
Controller's GO bond report text) with its own code, not the pipeline's interim tables. Exceptions, where the
"source table" is itself a validated derived product: measure directions (interim/measure_map.csv, Claude + hand
check) and measure lineage events (interim/an_lineage_events.csv, from the transcribed annual reports).

Checks (any failure -> exit 1):
  1. every placeholder value used in an insight's text is recomputed here and agrees with the build value
     (relative tolerance 0.5%, or 0.01 absolute for small values);
  2. the insight's text re-rendered with the recomputed values equals the published text exactly;
  3. every chart array agrees element by element (1% relative / 0.05 absolute);
  4. template text contains no literal numbers outside placeholders and allowed tokens (years, dataset ids);
  5. contract shape: required fields, allowed themes / chart types / verdicts, explore views, unique ids and ranks.
Writes data/redteam/verify_insights.json.
"""
import os, sys, json, re, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec

ROOT = os.path.dirname(os.path.dirname(HERE))
RAW = os.path.join(ROOT, 'data', 'raw')
INT = os.path.join(ROOT, 'data', 'interim')
OUTF = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
VALS = os.path.join(ROOT, 'data', 'redteam', 'insights_values.json')
REPORT = os.path.join(ROOT, 'data', 'redteam', 'verify_insights.json')
_c = {}


def memo(k, f):
    if k not in _c:
        _c[k] = f()
    return _c[k]


# --------------------------------------------------------------------------------------------------- deflator, population
def cpi():
    def f():
        out = {}
        for ser, key in (('CUURS49BSA0', 'bay'), ('CUUR0000SA0', 'us')):
            b = pd.read_csv(os.path.join(RAW, 'context', f'bls_raw_{ser}.csv'), dtype=str)
            b = b[b.period.str.match(r'M(0[1-9]|1[0-2])$')].copy()
            b['m'] = b.period.str[1:].astype(int); b['y'] = b.year.astype(int)
            b['v'] = pd.to_numeric(b.value, errors='coerce')
            b = b[b.y >= 1995].sort_values(['y', 'm']).reset_index(drop=True)
            if key == 'bay':  # bimonthly (even months); interpolate a missing reading from its neighbours
                b = b[b.m % 2 == 0].reset_index(drop=True)
                b['v'] = b.v.interpolate()
            b['fy'] = np.where(b.m >= 7, b.y + 1, b.y)
            g = b.groupby('fy').v.agg(['mean', 'size'])
            need = 6 if key == 'bay' else 12
            out[key] = g[g['size'] == need]['mean']
        return out
    return memo('cpi', f)


def mult(fy, key='bay'):
    c = cpi()[key]
    return float(c[2026] / c[fy])


def pop(fy, kind='dof'):
    def f():
        p = pd.read_csv(os.path.join(RAW, 'context', 'population.csv'))
        d = p[p.source.str.startswith('CA DOF') & (p.kind != 'census count') & p.reference_date.str.endswith('-01-01')]
        d = d.sort_values('source').groupby('year').population.last()  # later vintages override earlier ones
        return d
    d = memo('pop', f)
    return float(d[fy])


def pop_census_mid(fy):
    """Census July 1 estimates (intercensal to 2019, latest vintage after), averaged over the two July 1s bracketing the FY."""
    p = pd.read_csv(os.path.join(RAW, 'context', 'population.csv'))
    c = p[p.source.str.startswith('Census') & p.kind.str.startswith('Jul 1')].groupby('year').population.last()
    return float((c[fy - 1] + c[fy]) / 2)


# --------------------------------------------------------------------------------------------------- ledger (raw)
EXCL_FUND = {'Pension Trust Funds', 'Other Employee Benefit Trust Funds', 'Pension, Other Employee and Ot', 'Agency Funds',
             'Investment Trust Fund', 'Private Purpose Trust Fund', 'Retiree Health Care Trust Fund - Prop B',
             'Successor Agency-Former SF Redev Agency', 'Component Units', 'SF Transportation Authority Funds',
             'Treasure Island Development Authority', "Treasurer's Group Of Accounts"}
DEPT = {'DSS': 'HSA', 'ECD': 'DEM', 'PAB': 'BOA', 'UNA': 'GEN', 'WTR': 'PUC', 'CWP': 'PUC', 'HHP': 'PUC', 'CLP': 'PUC'}


def klass(ch):
    c = str(ch).lower()
    if c.startswith('salaries'): return 'sal'
    if 'fringe' in c: return 'ben'
    if 'non' in c and 'personnel' in c: return 'np'
    if c.startswith('materials'): return 'mat'
    if 'city grant' in c: return 'grant'
    if c.startswith('aid ') or ('support' in c and 'care' in c): return 'aid'
    if 'capital outlay' in c or 'capitalized' in c or 'facilities maint' in c: return 'cap'
    if 'programmatic' in c: return 'proj'
    if c.startswith('debt service'): return 'debt'
    if 'services of other' in c: return 'wo'
    if c.startswith('overhead') or 'allocated charges' in c: return 'oh'
    if 'special items' in c or 'extraordinary' in c or 'non expend' in c: return 'oth'
    return 'x'  # transfers, reserves, fiduciary, artifacts


def ledger(which):
    def f():
        if which == 'actual':
            cols = ['Fiscal Year', 'Related Govt Units', 'Department Code', 'Character', 'Object', 'Fund Type', 'Fund Type Code',
                    'Fund Category', 'Revenue or Spending', 'Amount']
            d = pd.read_csv(os.path.join(RAW, 'spending_revenue.csv'), usecols=cols, dtype=str)
            d = d[~d['Related Govt Units'].str.upper().eq('YES')]
            d['amt'] = pd.to_numeric(d.Amount).fillna(0)
        else:
            cols = ['Fiscal Year', 'Department Code', 'Character', 'Object', 'Fund Type', 'Fund Type Code', 'Fund Category',
                    'Revenue or Spending', 'Budget']
            d = pd.read_csv(os.path.join(RAW, 'budget.csv'), usecols=cols, dtype=str)
            d['amt'] = pd.to_numeric(d.Budget).fillna(0)
        rev = d[(d['Revenue or Spending'] == 'Revenue')].copy()
        d = d[(d['Revenue or Spending'] == 'Spending') & ~d['Fund Type'].isin(EXCL_FUND)].copy()
        d['fy'] = d['Fiscal Year'].astype(int)
        d['dept'] = d['Department Code'].str.strip().map(lambda x: DEPT.get(x, x))
        d['k'] = d.Character.map(klass)
        d['gf'] = d['Fund Type Code'].isin(['1G', 'GEN_FUND'])
        d['ot'] = (d.k == 'sal') & d.Object.str.contains('overtime', case=False, na=False)
        d = d[d.k != 'x']
        rev['fy'] = rev['Fiscal Year'].astype(int)
        return d[['fy', 'dept', 'k', 'gf', 'ot', 'Object', 'Fund Category', 'amt']], rev
    return memo('ledger_' + which, f)


def A():
    return ledger('actual')[0]


def B():
    return ledger('budget')[0]


OPS = ['sal', 'ben', 'np', 'mat', 'grant', 'aid', 'wo', 'oh', 'oth']   # pipeline "operating classes"
SPEND = OPS + ['cap', 'proj', 'debt']


def oper(dept, fy):
    a = A()
    return float(a[(a.dept == dept) & (a.fy == fy) & a.k.isin(OPS)].amt.sum())


def oper_real(dept, fy):
    return oper(dept, fy) * mult(fy)


# --------------------------------------------------------------------------------------------------- payroll (raw)
def pay():
    def f():
        e = pd.read_csv(os.path.join(RAW, 'employee_comp.csv'), low_memory=False,
                        usecols=['Year Type', 'Year', 'Department Code', 'Job Family', 'Job', 'Salaries', 'Overtime', 'Total Salary',
                                 'Retirement', 'Hours', 'Other Salaries'])
        return e[e['Year Type'].eq('Fiscal')]
    return memo('pay', f)


# --------------------------------------------------------------------------------------------------- FTE (raw)
def fte():
    def f():
        b = pd.read_csv(os.path.join(RAW, 'context', 'budget_fte.csv'), usecols=['Fiscal Year', 'Department Code', 'Budget'])
        a = pd.read_csv(os.path.join(RAW, 'context', 'spending_fte.csv'), usecols=['Fiscal Year', 'Department Code', 'Actual'])
        b = b.rename(columns={'Fiscal Year': 'fy', 'Department Code': 'dept', 'Budget': 'v'})
        a = a.rename(columns={'Fiscal Year': 'fy', 'Department Code': 'dept', 'Actual': 'v'})
        return b, a
    return memo('fte', f)


def fte_vals(fy, dept=None):
    b, a = fte()
    if dept:
        b, a = b[b.dept == dept], a[a.dept == dept]
    bb, aa = b[b.fy == fy], a[a.fy == fy]
    return float(bb.v[bb.v > 0].sum()), float(bb.v[bb.v < 0].sum()), float(aa.v.sum())


# --------------------------------------------------------------------------------------------------- Controller measures
def pm():
    def f():
        m = pd.read_csv(os.path.join(RAW, 'perf_measures', 'citywide_performance_metrics.csv'), dtype=str)
        m = m[m['Fiscal Year'].notna()].copy()
        m['fy'] = 2000 + m['Fiscal Year'].str[-2:].astype(int)
        for c in ('Target', 'Full-Year Result', 'Mid-Year Projection'):
            m[c] = pd.to_numeric(m[c], errors='coerce')
        return m
    return memo('pm', f)


def pm_series(dept_name, title_start):
    m = pm()
    s = m[(m['Department Name'] == dept_name) & m['Measure Title'].str.strip().str.startswith(title_start)]
    return s.groupby('fy')['Full-Year Result'].first()


# ===================================================================================================================
def v_police_staffing():
    e = pay()
    p = e[(e['Department Code'] == 'POL') & (e['Job Family'] == 'Police Services')].copy()
    V = {}
    med = p.groupby(['Year', 'Job'])['Salaries'].median().rename('m')
    p = p.join(med, on=['Year', 'Job'])
    for y in (2017, 2019, 2025, 2026):
        s = p[p.Year == y]
        V[f'n_{y}'] = len(s); V[f'hours_{y}'] = float(s.Hours.sum()); V[f'ot_{y}'] = float(s.Overtime.sum())
        V[f'full_{y}'] = int((s.Salaries >= s.m / 2).sum())
    V['n_chg'] = V['n_2025'] / V['n_2019'] - 1; V['full_chg'] = V['full_2025'] / V['full_2019'] - 1
    V['hours_chg'] = V['hours_2025'] / V['hours_2019'] - 1
    V['hpe_chg'] = (V['hours_2025'] / V['n_2025']) / (V['hours_2019'] / V['n_2019']) - 1
    V['ot_real_x'] = (V['ot_2025'] * mult(2025)) / (V['ot_2019'] * mult(2019))
    V['n_chg_17'] = V['n_2025'] / V['n_2017'] - 1; V['hours_chg_17'] = V['hours_2025'] / V['hours_2017'] - 1
    a, b = A(), B()
    V['ledger_ot_2025'] = float(a[(a.dept == 'POL') & (a.fy == 2025) & a.ot].amt.sum())
    V['budget_ot_2025'] = float(b[(b.dept == 'POL') & (b.fy == 2025) & b.ot].amt.sum())
    V['ledger_ratio_2025'] = V['ledger_ot_2025'] / V['budget_ot_2025']
    V['ledger_ot_2019'] = float(a[(a.dept == 'POL') & (a.fy == 2019) & a.ot].amt.sum())
    yrs = list(range(2017, 2027))
    g = p.groupby('Year').agg(n=('Salaries', 'size'), h=('Hours', 'sum'), o=('Overtime', 'sum'))
    fu = {y: V[f'full_{y}'] if f'full_{y}' in V else int(((p.Year == y) & (p.Salaries >= p.m / 2)).sum()) for y in yrs}
    CH = {'x': yrs, 'full': [100 * fu[y] / fu[2019] for y in yrs], 'hours': [100 * g.h[y] / g.h[2019] for y in yrs],
          'ot_real': [100 * g.o[y] * mult(y) / (g.o[2019] * mult(2019)) for y in yrs]}
    return V, CH


def v_ot100k():
    e = pay()
    V = {'thr': 100000}
    thr_fy13 = 100000 * mult(2025) / mult(2013)
    V['thr_2013'] = thr_fy13
    s13 = e[e.Year == 2013]; big13 = s13[s13.Overtime * mult(2013) > 100000 * mult(2025)]
    V['sharereal_2013'] = float(big13.Overtime.sum() / s13.Overtime.sum())
    V['nreal_2019'] = int((e[e.Year == 2019].Overtime * mult(2019) > 100000 * mult(2025)).sum())
    for y in (2013, 2019, 2025, 2026):
        s = e[e.Year == y]
        big = s[s.Overtime > 100000]
        V[f'n_{y}'] = len(big)
        V[f'nreal_{y}'] = int((s.Overtime * mult(y) > 100000 * mult(2025)).sum())
        V[f'share_{y}'] = float(big.Overtime.sum() / s.Overtime.sum())
        for d in ('POL', 'SHF', 'FIR'):
            V[f'{d}_{y}'] = int((big['Department Code'] == d).sum())
    V['exPOL_2019'] = V['n_2019'] - V['POL_2019']; V['exPOL_2025'] = V['n_2025'] - V['POL_2025']
    V['x_real'] = V['n_2025'] / V['nreal_2013']
    a = A(); V['ledger_ot_2025'] = float(a[a.ot & (a.fy == 2025)].amt.sum())
    V['ps_share_2025'] = (V['POL_2025'] + V['SHF_2025'] + V['FIR_2025']) / V['n_2025']
    t13, t25 = e[e.Year == 2013].Overtime.sum(), e[e.Year == 2025].Overtime.sum()
    V['ot_2013'] = float(t13); V['ot_2025'] = float(t25); V['ot_real_x'] = t25 * mult(2025) / (t13 * mult(2013))
    yrs = list(range(2013, 2027))
    CH = {'x': yrs, 'POL': [], 'SHF': [], 'FIR': [], 'other': []}
    for y in yrs:
        big = e[(e.Year == y) & (e.Overtime * mult(y) > 100000 * mult(2025))]['Department Code']
        for d in ('POL', 'SHF', 'FIR'):
            CH[d].append(int((big == d).sum()))
        CH['other'].append(int((~big.isin(['POL', 'SHF', 'FIR'])).sum()))
    return V, CH


def fire_calls():
    def f():
        folder = os.path.join(RAW, 'outcomes', 'chunks', 'fire')
        files = []
        for y in range(2012, 2026):
            for m in range(1, 13):
                fy = y + 1 if m >= 7 else y
                if 2013 <= fy <= 2025:
                    files.append(os.path.join(folder, f'{y}-{m:02d}.parquet'))
        cols = ['call_number', 'call_type', 'original_priority', 'final_priority', 'received_dttm', 'dispatch_dttm', 'on_scene_dttm']
        df = pd.concat([pd.read_parquet(p, columns=cols) for p in files if os.path.exists(p)], ignore_index=True)
        for c in ('received_dttm', 'dispatch_dttm', 'on_scene_dttm'):
            df[c] = pd.to_datetime(df[c], errors='coerce')
        df = df.sort_values(['call_number', 'received_dttm'])
        g = df.groupby('call_number').agg(rec=('received_dttm', 'min'), disp=('dispatch_dttm', 'min'), ons=('on_scene_dttm', 'min'),
                                          ctype=('call_type', 'first'), fp=('final_priority', 'first'), op=('original_priority', 'first'))
        g['fy'] = np.where(g.rec.dt.month >= 7, g.rec.dt.year + 1, g.rec.dt.year)
        g['resp'] = (g.ons - g.rec).dt.total_seconds() / 60
        g['d2a'] = (g.ons - g.disp).dt.total_seconds() / 60
        for c in ('resp', 'd2a'):
            g.loc[(g[c] < 0) | (g[c] > 120), c] = np.nan
        return g
    return memo('fire', f)


def v_fire():
    g = fire_calls()
    med = g[g.ctype.eq('Medical Incident')]
    c3 = med[med.fp.astype(str).isin(['3', 'E'])]
    o3 = med[med.op.astype(str).isin(['3', 'E'])]
    calls = g.groupby('fy').size()
    mres = c3.groupby('fy').resp.median(); p90 = c3.groupby('fy').resp.quantile(0.9)
    V = {'calls_2013': int(calls[2013]), 'calls_2025': int(calls[2025]), 'calls_2019': int(calls[2019]),
         'med_2013': float(mres[2013]), 'med_2025': float(mres[2025]), 'p90_2013': float(p90[2013]), 'p90_2025': float(p90[2025])}
    V['calls_chg'] = V['calls_2025'] / V['calls_2013'] - 1; V['calls_chg_19'] = V['calls_2025'] / V['calls_2019'] - 1
    sp = {y: oper_real('FIR', y) for y in range(2013, 2026)}
    V['sp_2013'], V['sp_2025'], V['sp_2019'] = sp[2013], sp[2025], sp[2019]
    V['sp_chg'] = sp[2025] / sp[2013] - 1; V['sp_chg_19'] = sp[2025] / sp[2019] - 1
    V['sp_chg_us'] = (oper('FIR', 2025) * mult(2025, 'us')) / (oper('FIR', 2013) * mult(2013, 'us')) - 1
    V['per_call_2013'] = sp[2013] / V['calls_2013']; V['per_call_2025'] = sp[2025] / V['calls_2025']
    V['per_call_chg'] = V['per_call_2025'] / V['per_call_2013'] - 1
    b13, _, a13 = fte_vals(2013, 'FIR'); b25, _, a25 = fte_vals(2025, 'FIR')
    V['fte_2013'], V['fte_2025'], V['fte_chg'] = b13, b25, b25 / b13 - 1
    V['fta_2013'], V['fta_2025'] = a13, a25; V['fta_chg'] = a25 / a13 - 1
    V['calls_per_pos_chg'] = (V['calls_2025'] / b25) / (V['calls_2013'] / b13) - 1
    # these two robustness values follow red team 2's definition (zero-second intervals excluded as implausible)
    pos = lambda x: x[(x > 0) & (x < 120)].median()
    d2a = c3.groupby('fy').d2a.apply(pos)
    V['d2a_2013'], V['d2a_2025'] = float(d2a[2013]), float(d2a[2025])
    om = o3.groupby('fy').resp.apply(pos)
    V['orig_med_2013'], V['orig_med_2025'] = float(om[2013]), float(om[2025])
    yrs = list(range(2013, 2026))
    fa = {y: fte_vals(y, 'FIR')[2] for y in yrs}
    CH = {'x': yrs, 'calls': [100 * calls[y] / calls[2013] for y in yrs], 'spend': [100 * sp[y] / sp[2013] for y in yrs],
          'median': [100 * mres[y] / mres[2013] for y in yrs], 'filled': [100 * fa[y] / fa[2013] for y in yrs]}
    return V, CH


def police_calls():
    def f():
        folder = os.path.join(RAW, 'outcomes', 'chunks', 'police')
        files = [os.path.join(folder, fn) for fn in sorted(os.listdir(folder)) if fn.endswith('.parquet')]
        cols = ['dup_cad_number', 'received_datetime', 'dispatch_datetime', 'onscene_datetime', 'priority_final', 'agency', 'onview_flag']
        df = pd.concat([pd.read_parquet(p, columns=cols) for p in files], ignore_index=True)
        df = df[(df.onview_flag == 'N') & (df.agency == 'Police') & df.dup_cad_number.isna() & df.priority_final.isin(['A', 'B', 'C'])].copy()
        for c in ('received_datetime', 'dispatch_datetime', 'onscene_datetime'):
            df[c] = pd.to_datetime(df[c], errors='coerce')
        r = df.received_datetime
        df['fy'] = np.where(r.dt.month >= 7, r.dt.year + 1, r.dt.year)
        mins = lambda a, b: (a - b).dt.total_seconds() / 60
        df['resp'] = mins(df.onscene_datetime, df.received_datetime)
        df['r2d'] = mins(df.dispatch_datetime, df.received_datetime)
        df['d2o'] = mins(df.onscene_datetime, df.dispatch_datetime)
        for c in ('resp', 'r2d', 'd2o'):
            df.loc[(df[c] < 0) | (df[c] > 1440), c] = np.nan
        return df
    return memo('police', f)


def v_police_calls():
    df = police_calls()
    V = {}
    for y in (2016, 2019, 2025):
        for p in 'ABC':
            s = df[(df.fy == y) & (df.priority_final == p)]
            V[f'calls_{p}_{y}'] = len(s); V[f'med_{p}_{y}'] = float(s.resp.median()); V[f'p90_{p}_{y}'] = float(s.resp.quantile(0.9))
            V[f'r2d_{p}_{y}'] = float(s.r2d.median()); V[f'd2o_{p}_{y}'] = float(s.d2o.median())
    for p in 'ABC':
        V[f'calls_{p}_chg'] = V[f'calls_{p}_2025'] / V[f'calls_{p}_2016'] - 1
        V[f'med_{p}_chg'] = V[f'med_{p}_2025'] / V[f'med_{p}_2016'] - 1
    V['calls_tot_2016'] = sum(V[f'calls_{p}_2016'] for p in 'ABC'); V['calls_tot_2025'] = sum(V[f'calls_{p}_2025'] for p in 'ABC')
    V['calls_tot_chg'] = V['calls_tot_2025'] / V['calls_tot_2016'] - 1
    V['sp_2016'], V['sp_2025'] = oper_real('POL', 2016), oper_real('POL', 2025)
    V['sp_chg'] = V['sp_2025'] / V['sp_2016'] - 1
    V['per_call_2016'] = V['sp_2016'] / V['calls_tot_2016']; V['per_call_2025'] = V['sp_2025'] / V['calls_tot_2025']
    V['per_call_chg'] = V['per_call_2025'] / V['per_call_2016'] - 1
    CH = {'cats': ['Priority A', 'Priority B', 'Priority C'], 'a': [V[f'med_{p}_2016'] for p in 'ABC'], 'b': [V[f'med_{p}_2025'] for p in 'ABC']}
    return V, CH


def v_homeless():
    s = pd.read_csv(os.path.join(RAW, 'outcomes', 'scorecard_measures_monthly.csv'), low_memory=False)
    s = s[s['Measure Code'] == 7169].copy()
    s['yr'] = s['Calendar Month'].str[:4].astype(int)
    p = s.pivot_table(index='yr', columns='Category 2', values='Actual', aggfunc='first')
    V = {f'hom_{y}': oper_real('HOM', y) for y in (2017, 2018, 2019, 2025, 2026)}
    V['x_17_25'] = V['hom_2025'] / V['hom_2017']; V['x_18_25'] = V['hom_2025'] / V['hom_2018']; V['x_19_25'] = V['hom_2025'] / V['hom_2019']
    for y in (2019, 2022, 2024):
        V[f'unsh_{y}'] = int(p.Unsheltered[y]); V[f'sh_{y}'] = int(p.Sheltered[y]); V[f'tot_{y}'] = V[f'unsh_{y}'] + V[f'sh_{y}']
    V['unsh_chg'] = V['unsh_2024'] / V['unsh_2019'] - 1; V['sh_chg'] = V['sh_2024'] / V['sh_2019'] - 1; V['tot_chg'] = V['tot_2024'] / V['tot_2019'] - 1
    V['unsh_chg_22'] = V['unsh_2024'] / V['unsh_2022'] - 1
    V['sh_share_2019'] = V['sh_2019'] / V['tot_2019']; V['sh_share_2024'] = V['sh_2024'] / V['tot_2024']
    yrs = [int(y) for y in p.index]
    CH = {'x': yrs, 'sheltered': [int(p.Sheltered[y]) for y in yrs], 'unsheltered': [int(p.Unsheltered[y]) for y in yrs]}
    return V, CH


def v_pension():
    a = A()
    ret = a[(a.k == 'ben') & a.Object.str.contains('retirement', case=False, na=False)]
    sal = a[a.k == 'sal']
    R, S = ret.groupby('fy').amt.sum(), sal.groupby('fy').amt.sum()
    RG, SG = ret[ret.gf].groupby('fy').amt.sum(), sal[sal.gf].groupby('fy').amt.sum()
    e = pay()
    pe = e.groupby('Year')[['Retirement', 'Total Salary']].sum()
    ps = pe.Retirement / pe['Total Salary']
    V = {}
    for y in (2013, 2019, 2021, 2025, 2026):
        V[f'ret_{y}'] = float(R[y]); V[f'sal_{y}'] = float(S[y]); V[f'share_{y}'] = float(R[y] / S[y])
    V['pay_share_2021'], V['pay_share_2025'] = float(ps[2021]), float(ps[2025])
    O = a[a.ot].groupby('fy').amt.sum()
    for y in (2013, 2021, 2025, 2026):
        V[f'reg_{y}'] = float(S[y] - O[y]); V[f'rshare_{y}'] = float(R[y] / (S[y] - O[y]))
    V['rsavings_2025'] = (V['rshare_2021'] - V['rshare_2025']) * V['reg_2025']
    q = e.groupby('Year')[['Retirement', 'Salaries', 'Other Salaries']].sum()
    qr = q.Retirement / (q.Salaries + q['Other Salaries'])
    V['pay_rshare_2021'], V['pay_rshare_2025'] = float(qr[2021]), float(qr[2025])
    V['sal_chg_21_25'] = V['sal_2025'] / V['sal_2021'] - 1
    V['ret_drop'] = V['ret_2021'] - V['ret_2025']
    V['savings_2025'] = (V['share_2021'] - V['share_2025']) * V['sal_2025']
    V['gf_share_2021'], V['gf_share_2025'] = float(RG[2021] / SG[2021]), float(RG[2025] / SG[2025])
    yrs = list(range(2010, 2027))
    CH = {'x': yrs, 'ledger': [100 * R[y] / (S[y] - O[y]) for y in yrs], 'payroll': [100 * qr[y] if y in qr.index else None for y in yrs]}
    return V, CH


def v_grants():
    a = A()
    g = a[(a.k == 'grant') & a.fy.between(2013, 2026)]
    T = g.groupby('fy').amt.sum(); GF = g[g.gf].groupby('fy').amt.sum()
    ops = a[a.k.isin(['sal', 'ben', 'np', 'mat', 'grant', 'aid', 'oth'])].groupby('fy').amt.sum()
    ex = g[~g.dept.isin(['HOM', 'DEC'])].groupby('fy').amt.sum()
    V = {f'tot_{y}': float(T[y]) for y in (2013, 2019, 2023, 2025, 2026)}
    V['nom_x'] = T[2025] / T[2013]
    V['real_2013'] = T[2013] * mult(2013); V['real_2025'] = T[2025] * mult(2025); V['real_x'] = V['real_2025'] / V['real_2013']
    V['share_2013'] = T[2013] / ops[2013]; V['share_2025'] = T[2025] / ops[2025]
    V['gf_2013'], V['gf_2023'], V['gf_2026'] = float(GF[2013]), float(GF[2023]), float(GF[2026])
    V['gf_chg_23_26'] = GF[2026] / GF[2023] - 1
    V['exn_real_x'] = ex[2025] * mult(2025) / (ex[2013] * mult(2013))
    by = g.groupby(['fy', 'dept']).amt.sum()
    for d in ('HOM', 'CHF', 'DEC', 'MYR', 'ECN'):
        V[f'{d}_2025'] = float(by.get((2025, d), 0))
    grp = ['HOM', 'CHF', 'DEC', 'MYR', 'HSA', 'ECN']
    npx = a[(a.k == 'np') & a.dept.isin(grp)].groupby('fy').amt.sum()
    V['np_real_2013'], V['np_real_2025'] = npx[2013] * mult(2013), npx[2025] * mult(2025)
    yrs = list(range(2013, 2027))
    CH = {'x': yrs}
    for d in grp:
        CH[d] = [float(by.get((y, d), 0)) * mult(y) / 1e6 for y in yrs]
    CH['other'] = [(T[y] - sum(float(by.get((y, d), 0)) for d in grp)) * mult(y) / 1e6 for y in yrs]
    return V, CH


def v_gf():
    a = A()
    gf = a[a.gf & a.k.isin(['sal', 'ben', 'np', 'mat', 'grant', 'aid', 'wo'])].groupby('fy').amt.sum()
    wo = a[a.gf & (a.k == 'wo')].groupby('fy').amt.sum()
    pr = {y: gf[y] * mult(y) / pop(y) for y in range(2010, 2027)}
    V = {f'pr_{y}': pr[y] for y in (2013, 2019, 2021, 2025, 2026)}
    V['chg_13_25'] = pr[2025] / pr[2013] - 1; V['chg_19_21'] = pr[2021] / pr[2019] - 1
    V['chg_21_26'] = pr[2026] / pr[2021] - 1; V['chg_21_25'] = pr[2025] / pr[2021] - 1
    V['chg_us_13_25'] = (gf[2025] * mult(2025, 'us') / pop(2025)) / (gf[2013] * mult(2013, 'us') / pop(2013)) - 1
    V['chg_census_13_25'] = (gf[2025] * mult(2025) / pop_census_mid(2025)) / (gf[2013] * mult(2013) / pop_census_mid(2013)) - 1
    ex = {y: (gf[y] - wo[y]) * mult(y) / pop(y) for y in (2013, 2019, 2021, 2025)}
    V['chg_exwo_13_25'] = ex[2025] / ex[2013] - 1; V['chg_exwo_19_21'] = ex[2021] / ex[2019] - 1
    V['real_tot_2019'], V['real_tot_2021'], V['real_tot_2025'] = gf[2019] * mult(2019), gf[2021] * mult(2021), gf[2025] * mult(2025)
    V['pop_2019'], V['pop_2025'] = int(pop(2019)), int(pop(2025)); V['pop_chg'] = pop(2025) / pop(2019) - 1
    V['real_tot_chg_19_25'] = V['real_tot_2025'] / V['real_tot_2019'] - 1
    yrs = list(range(2010, 2027))
    return V, {'x': yrs, 'per_res': [pr[y] for y in yrs]}


def v_vacancy():
    V = {}
    for y in (2013, 2021, 2022, 2023, 2024, 2025, 2026):
        b, att, act = fte_vals(y)
        V[f'bud_{y}'], V[f'act_{y}'], V[f'att_{y}'] = b, act, att
        V[f'vac_{y}'] = b - act; V[f'vrate_{y}'] = (b - act) / b
    ys = (2021, 2022, 2023, 2024)
    V['vac_min_21_24'] = min(V[f'vac_{y}'] for y in ys); V['vac_max_21_24'] = max(V[f'vac_{y}'] for y in ys)
    V['vrate_min_21_24'] = min(V[f'vrate_{y}'] for y in ys); V['vrate_max_21_24'] = max(V[f'vrate_{y}'] for y in ys)
    V['net_2025'] = V['bud_2025'] + V['att_2025']
    gg = []
    for y in range(2013, 2018):
        b_, _, a_ = fte_vals(y); gg.append((b_ - a_) / b_)
    bF, aF = fte()
    bb23 = bF[(bF.fy == 2023) & (bF.v > 0)].groupby('dept').v.sum(); aa23 = aF[aF.fy == 2023].groupby('dept').v.sum()
    bigd = bb23[bb23 >= 100]
    V['n_big'] = len(bigd); V['n_big_gap10'] = int(sum((1 - aa23.get(k, 0) / bigd[k]) > 0.10 for k in bigd.index)); V['hundred_fte'] = 100; V['ten'] = 0.10
    V['vrate_min_13_18'], V['vrate_max_13_18'] = min(gg), max(gg)
    b_all, _, a_all = fte_vals(2023); b_m, _, a_m = fte_vals(2023, 'MTA')
    V['vrate_exMTA_2023'] = 1 - (a_all - a_m) / (b_all - b_m)
    V['n_zero_att'] = sum(1 for y in range(2019, 2025) if fte_vals(y)[1] == 0)
    for d in ('MTA', 'POL', 'SHF'):
        b, _, act = fte_vals(2023, d)
        V[f'{d}_vrate_2023'] = 1 - act / b
    a, bb = A(), B()
    ex = [a[(a.fy == y) & (a.k == 'sal')].amt.sum() / bb[(bb.fy == y) & (bb.k == 'sal')].amt.sum() for y in ys]
    V['sal_exec_min'], V['sal_exec_max'] = float(min(ex)), float(max(ex))
    yrs = list(range(2013, 2027))
    CH = {'x': yrs, 'budgeted': [], 'net': [], 'filled': []}
    for y in yrs:
        b, att, act = fte_vals(y)
        CH['budgeted'].append(b); CH['net'].append(b + att if att != 0 else None); CH['filled'].append(act)
    return V, CH


def v_ot_budget():
    a, b = A(), B()
    yrs = list(range(2010, 2027))
    act = a[a.ot].groupby('fy').amt.sum(); bud = b[b.ot].groupby('fy').amt.sum()
    r = (act / bud).loc[2010:2026]
    ax = a[a.ot & (a.dept != 'POL')].groupby('fy').amt.sum(); bx = b[b.ot & (b.dept != 'POL')].groupby('fy').amt.sum()
    V = {'n_years': len(yrs), 'n_over': int((r > 1).sum()), 'min_ratio': float(r.min()), 'max_ratio': float(r.max()),
         'min_fy': int(r.idxmin()), 'max_fy': int(r.idxmax()), 'cum_over': float((act - bud).loc[2010:2026].sum()),
         'act_2025': float(act[2025]), 'bud_2025': float(bud[2025]), 'act_2026': float(act[2026]), 'bud_2026': float(bud[2026]),
         'n_over_expol': int((ax.loc[2010:2026] > bx.loc[2010:2026]).sum()), 'bud_x_13_26': float(bud[2026] / bud[2013])}
    po = pay().groupby('Year').Overtime.sum()
    V['n_over_payroll'] = int(sum(po[y] > bud[y] for y in range(2013, 2027))); V['n_payroll_years'] = len(range(2013, 2027))
    V['pay_ot_2025'] = float(po[2025])
    return V, {'x': yrs, 'budget': [bud[y] / 1e6 for y in yrs], 'actual': [act[y] / 1e6 for y in yrs]}


def v_muni_fares():
    n = pd.read_csv(os.path.join(RAW, 'outcomes', 'ntd_sfmta_timeseries_raw.csv'))
    n = n[n.ntd_id == 90015].pivot_table(index='report_year', columns='field', values='value', aggfunc='sum')
    rr = n.Fares / n['Operating Expenses']
    rev = ledger('actual')[1]
    rev = rev[rev['Department Code'].eq('MTA')]
    fo = rev.Object.str.lower()
    fare = rev[fo.str.startswith('transit') & fo.str.contains('cash fares|pass revenue|cable car|token|paratransit')]
    fare = fare.assign(v=pd.to_numeric(fare.Amount).fillna(0))
    F = fare.groupby('fy').v.sum(); P = fare[fare.Object.str.lower().str.contains('pass revenue')].groupby('fy').v.sum()
    op = {y: oper('MTA', y) for y in range(2013, 2027)}
    V = {'rr_2015': rr[2015], 'rr_2019': rr[2019], 'rr_2024': rr[2024], 'ntd_fares_2019': n.Fares[2019], 'ntd_fares_2024': n.Fares[2024],
         'ntd_opex_2019': n['Operating Expenses'][2019], 'ntd_opex_2024': n['Operating Expenses'][2024],
         'trips_2019': n['Unlinked Passenger Trips'][2019], 'trips_2024': n['Unlinked Passenger Trips'][2024]}
    V['trips_chg'] = V['trips_2024'] / V['trips_2019'] - 1
    V['fare_per_trip_2019'] = V['ntd_fares_2019'] / V['trips_2019']; V['fare_per_trip_2024'] = V['ntd_fares_2024'] / V['trips_2024']
    for y in (2013, 2019, 2024, 2025, 2026):
        V[f'fares_{y}'] = float(F[y]); V[f'pass_{y}'] = float(P[y]); V[f'lrr_{y}'] = float(F[y] / op[y])
    V['pass_chg'] = V['pass_2025'] / V['pass_2019'] - 1
    V['fares_real_chg'] = F[2025] * mult(2025) / (F[2019] * mult(2019)) - 1
    V = {k: float(v) for k, v in V.items()}
    yrs = list(range(2013, 2027))
    return V, {'x': yrs, 'ntd': [100 * rr[y] if y in rr.index else None for y in yrs], 'ledger': [100 * F[y] / op[y] for y in yrs]}


def v_survey():
    m = pd.read_csv(os.path.join(RAW, 'outcomes', 'city_survey_microdata.csv'), low_memory=False)

    def ab(df, col, w=True):
        x = pd.to_numeric(df[col], errors='coerce'); ok = (x >= 1) & (x <= 5)
        wt = pd.to_numeric(df.weight, errors='coerce').fillna(0) if w else pd.Series(1.0, index=df.index)
        return float(wt[ok & (x >= 4)].sum() / wt[ok].sum())
    y19, y23 = m[m.year == 2019], m[m.year == 2023]
    V = {}
    for q, _ in spec_survey_q():
        V[f'{q}_2019'], V[f'{q}_2023'] = ab(y19, q), ab(y23, q)
        V[f'{q}_d'] = V[f'{q}_2023'] - V[f'{q}_2019']
    qs = spec_survey_q()
    V['n_q'] = len(qs); V['n_down'] = sum(V[f'{q}_d'] < 0 for q, _ in qs)
    ph = y23[y23['mode'].isin(['Cell', 'Landline'])]
    V['muni_phone_2023'], V['lib_phone_2023'] = ab(ph, 'muni_rate'), ab(ph, 'lib_rate')
    V['muni_unw_2019'], V['muni_unw_2023'] = ab(y19, 'muni_rate', False), ab(y23, 'muni_rate', False)
    V['lib_unw_2019'], V['lib_unw_2023'] = ab(y19, 'lib_rate', False), ab(y23, 'lib_rate', False)
    rider = lambda d: d[pd.to_numeric(d.muni_user_yes, errors='coerce').eq(1)]
    V['muni_riders_2019'], V['muni_riders_2023'] = ab(rider(y19), 'muni_rate'), ab(rider(y23), 'muni_rate')
    V['lib_real_chg'] = oper_real('LIB', 2023) / oper_real('LIB', 2019) - 1
    V['mta_real_chg'] = oper_real('MTA', 2023) / oper_real('MTA', 2019) - 1
    return V, {'cats': [l for _, l in qs], 'a': [100 * V[f'{q}_2019'] for q, _ in qs], 'b': [100 * V[f'{q}_2023'] for q, _ in qs]}


def spec_survey_q():
    # the question list and labels are part of the insight definition (compute_build.SURVEY_Q); read them from the build file
    from compute_build import SURVEY_Q
    return SURVEY_Q


def v_library():
    vis = pm_series('PUBLIC LIBRARY', 'Number of persons entering')
    phys = pm_series('PUBLIC LIBRARY', 'Circulation of physical books')
    ebk = pm_series('PUBLIC LIBRARY', 'Circulation of eBooks')
    dr = pm_series('PUBLIC LIBRARY', 'Expenditures per Number of Visits')
    sp = {y: oper_real('LIB', y) for y in range(2017, 2026)}
    V = {}
    for y in (2017, 2019, 2025):
        V[f'vis_{y}'], V[f'phys_{y}'], V[f'ebk_{y}'] = float(vis[y]), float(phys[y]), float(ebk[y])
        V[f'circ_{y}'] = V[f'phys_{y}'] + V[f'ebk_{y}']; V[f'sp_{y}'] = sp[y]
        V[f'pv_{y}'] = sp[y] / V[f'vis_{y}']; V[f'pc_{y}'] = sp[y] / V[f'circ_{y}']
    V['vis_chg'] = V['vis_2025'] / V['vis_2017'] - 1; V['circ_chg'] = V['circ_2025'] / V['circ_2017'] - 1
    V['ebk_x'] = V['ebk_2025'] / V['ebk_2017']; V['phys_chg'] = V['phys_2025'] / V['phys_2017'] - 1; V['sp_chg'] = sp[2025] / sp[2017] - 1
    V['pv_chg'] = V['pv_2025'] / V['pv_2017'] - 1; V['pc_chg'] = V['pc_2025'] / V['pc_2017'] - 1
    V['vis_chg_19'] = V['vis_2025'] / V['vis_2019'] - 1; V['circ_chg_19'] = V['circ_2025'] / V['circ_2019'] - 1
    V['dept_pv_2017'], V['dept_pv_2025'] = float(dr[2017]), float(dr[2025])
    yrs = list(range(2017, 2026))
    return V, {'x': yrs, 'visits': [100 * vis[y] / vis[2017] for y in yrs], 'physical': [100 * phys[y] / phys[2017] for y in yrs],
               'ebooks': [100 * ebk[y] / ebk[2017] for y in yrs], 'spend': [100 * sp[y] / sp[2017] for y in yrs]}


def v_bonds():
    g = pd.read_csv(os.path.join(RAW, 'capital', 'm793-kis4.csv'))
    g['vote'] = pd.to_datetime(g.voter_approved_date, format='%Y/%m/%d %I:%M:%S %p', errors='coerce')
    vote = g.dropna(subset=['vote']).groupby(['bondprogram', 'year']).vote.min()
    snaps = {'FY22-23': pd.Timestamp('2023-06-30'), 'FY24-25': pd.Timestamp('2025-06-30')}
    rows = []
    for (prog, yr, fy), s in g.groupby(['bondprogram', 'year', 'fiscal_year']):
        bud = s.revisedbudget.sum()
        if not bud or (prog, yr) not in vote.index:
            continue
        rows.append({'prog': prog, 'yr': yr, 'fy': fy, 'bud': bud, 'exp': s.expended.sum(), 'enc': s.encumbrance.fillna(0).sum(),
                     'iss': s.issuedtodate.sum(), 'age': (snaps[fy] - vote[(prog, yr)]).days / 365.25})
    r = pd.DataFrame(rows); r['share'] = r.exp / r.bud
    late = r.sort_values('fy').groupby(['prog', 'yr']).last().reset_index()
    late = late[late.age >= 3].sort_values('share')
    sw = late[late.prog.str.contains('Seawall')].iloc[0]; es = late[late.prog.str.startswith('Earthquake') & (late.yr == 2020)].iloc[0]
    peer = r[(r.age >= 4.5) & (r.age <= 8.5) & ~r.prog.str.contains('Seawall') & ~(r.prog.str.startswith('Earthquake') & (r.yr == 2020))]
    V = {'sw_share': sw.share, 'sw_exp': sw.exp, 'sw_bud': sw.bud, 'sw_issued': sw.iss, 'sw_years': sw.age,
         'sw_enc_share': (sw.exp + sw.enc) / sw.bud, 'sw_of_issued': sw.exp / sw.iss, 'es_share': es.share, 'es_bud': es.bud,
         'es_years': es.age, 'es_enc_share': (es.exp + es.enc) / es.bud, 'peer_n': len(peer), 'peer_min': peer.share.min(),
         'peer_max': peer.share.max(), 'win_lo': 4.5, 'win_hi': 8.5, 'peer_prog': len(peer[['prog', 'yr']].drop_duplicates())}
    # the Controller's report (text layer of the PDF): program-level "expended and encumbered, which is N% of the total bond budget"
    lines = open(os.path.join(RAW, 'capital', 'reports', 'FY24-FY25_Capital_Report.txt'), encoding='utf-8', errors='ignore').read().split('\n')

    def rep(header_regex):
        for i, l in enumerate(lines):
            if re.search(header_regex, l) and not re.search(r'\.{5,}', l):
                for l2 in lines[i:i + 120]:
                    mm = re.search(r'which is (\d+)% of the total bond', l2)
                    if mm:
                        return int(mm.group(1)) / 100
        return None
    V['rep_sw'] = rep(r'^2018 Embarcadero Seawall Earthquake Safety\s*$')
    V['rep_es'] = rep(r'^2020 Earthquake Safety and Emergency\s*$')
    V = {k: float(v) if not isinstance(v, (int,)) else v for k, v in V.items()}
    lab = (late.prog + ' (' + late.yr.astype(str) + ')').tolist()
    return V, {'cats': lab, 'values': [100 * v for v in late.share], 'years': list(late.age)}


PM_DEPT_NAMES = None


def v_targets():
    m = pm()
    mp = pd.read_csv(os.path.join(INT, 'measure_map.csv'))[['dept', 'title', 'direction']]
    from compute_build import ROOT as _r  # noqa: F401  (same repository)
    sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
    import importlib.util
    spec_m = importlib.util.spec_from_file_location('m04', os.path.join(ROOT, 'pipeline', '04_measures.py'))
    m04 = importlib.util.module_from_spec(spec_m); spec_m.loader.exec_module(m04)
    m = m.assign(dept=m['Department Name'].map(m04.PM_DEPT), title=m['Measure Title'].str.strip())
    mp = mp.assign(title=mp.title.str.strip())
    d = m.merge(mp, on=['dept', 'title'], how='left')
    d['key'] = d.dept + '|' + d.title.str.lower()
    d = d.rename(columns={'Target': 'target', 'Full-Year Result': 'result', 'Mid-Year Projection': 'midp'})

    def met(res, tgt, dr):
        ok = res.notna() & tgt.notna() & dr.isin(['higher_better', 'lower_better'])
        tol = tgt.abs() * 0.005
        v = np.where(dr == 'higher_better', res >= tgt - tol, res <= tgt + tol).astype(float)
        return pd.Series(np.where(ok, v, np.nan), index=res.index)
    d['met'] = met(d.result, d.target, d.direction); d['midmet'] = met(d.midp, d.target, d.direction)
    d = d.sort_values(['key', 'fy'])
    g = d.groupby('key')
    d['nt'] = g.target.shift(-1); d['nfy'] = g.fy.shift(-1); d['pmet'] = g.met.shift(1); d['pres'] = g.result.shift(1)
    d['pfy'] = g.fy.shift(1)
    d.loc[d.pfy != d.fy - 1, ['pmet', 'pres']] = np.nan
    t = d[(d.nfy == d.fy + 1) & d.target.notna() & d.nt.notna() & d.direction.isin(['higher_better', 'lower_better']) & d.fy.between(2013, 2026)].copy()
    t['rel'] = (t.nt - t.target) / t.target.abs().replace(0, np.nan)
    sg = np.where(t.direction == 'higher_better', 1, -1)
    t['eas'] = sg * t.rel < -0.05; t['har'] = sg * t.rel > 0.05
    t['miss'] = (t.pmet == 0) | (t.midmet == 0); t['hit'] = (t.pmet == 1) & (t.midmet != 0)
    mi, hi = t[t.miss], t[t.hit]
    V = {'n_miss': len(mi), 'n_hit': len(hi), 'eased_miss': mi.eas.mean(), 'eased_hit': hi.eas.mean(), 'raised_hit': hi.har.mean(),
         'raised_miss': mi.har.mean(), 'n_measures': t.key.nunique(), 'five': 0.05}
    V['ratio'] = V['eased_miss'] / V['eased_hit']
    near = lambda x, y: (x - y).abs() <= 0.01 * y.abs().clip(lower=1e-9)
    moved = t.rel.abs() > 0.005
    t['reset'] = moved & (near(t.nt, t.midp) | near(t.nt, t.pres))
    st = t[moved].groupby('key').reset.agg(['mean', 'size'])
    mech = set(st[(st['size'] >= 2) & (st['mean'] >= 0.5)].index)
    u = t[~t.key.isin(mech)]
    V['ratio_excl_mech'] = u[u.miss].eas.mean() / u[u.hit].eas.mean()
    w = t[t.miss | t.hit]
    big = []
    for dep, s in w.groupby('dept'):
        a_, b_ = s[s.miss], s[~s.miss]
        if len(a_) >= 20 and len(b_) >= 20:
            big.append((dep, a_.eas.mean() > b_.eas.mean()))
    V['depts'] = len(big); V['depts_more'] = sum(x for _, x in big)
    lo = [w[(w.dept != dep) & w.miss].eas.mean() / w[(w.dept != dep) & ~w.miss].eas.mean() for dep, _ in big]
    V['lodo_min'], V['lodo_max'] = min(lo), max(lo)
    V = {k: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for k, v in V.items()}
    V['five'] = 0.05
    return V, {'cats': ['After a missed target', 'After a met target'], 'eased': [100 * V['eased_miss'], 100 * V['eased_hit']],
               'raised': [100 * V['raised_miss'], 100 * V['raised_hit']]}


def v_redefined():
    ev = pd.read_csv(os.path.join(INT, 'an_lineage_events.csv'))
    e = ev[(ev.internal_admin.astype(str) == 'False') & ev.met.notna()].copy()
    V = {'ci': 0.95}
    for k, lab in (('dropped', 'dropped'), ('redef', 'redefined')):
        y = (e.outcome == lab)
        mi, hi = e.met == 0, e.met == 1
        a_, n1, c_, n2 = int((y & mi).sum()), int(mi.sum()), int((y & hi).sum()), int(hi.sum())
        rr = (a_ / n1) / (c_ / n2)
        se = np.sqrt(1 / a_ - 1 / n1 + 1 / c_ - 1 / n2)
        V[f'{k}_miss'], V[f'{k}_met'], V[f'{k}_rr'] = a_ / n1, c_ / n2, rr
        V[f'{k}_lo'], V[f'{k}_hi'] = rr * np.exp(-1.96 * se), rr * np.exp(1.96 * se)
        V[f'{k}_n_miss'], V[f'{k}_n_met'] = a_, c_
        num = den = 0.0
        for _, s in e.groupby('report_fy'):
            ys, ms = (s.outcome == lab), (s.met == 0)
            A_, B_, C_, D_ = (ys & ms).sum(), (~ys & ms).sum(), (ys & ~ms).sum(), (~ys & ~ms).sum()
            n = A_ + B_ + C_ + D_
            num += A_ * D_ / n; den += B_ * C_ / n
        V[f'{k}_cmh'] = num / den
    V['n_missed'], V['n_met'] = int((e.met == 0).sum()), int((e.met == 1).sum())
    V['extra_redef'] = V['redef_n_miss'] - V['redef_met'] * V['n_missed']
    yr = e.assign(r=(e.outcome == 'redefined')).groupby(['report_fy', 'met']).r.mean().unstack()
    V['redef_years_higher'] = int((yr[0.0] > yr[1.0]).sum()); V['redef_years'] = int(len(yr))
    V = {k: float(v) if isinstance(v, (float, np.floating)) else v for k, v in V.items()}
    return V, {'cats': ['Dropped from the next report', 'Redefined in the next report'],
               'miss': [100 * V['dropped_miss'], 100 * V['redef_miss']], 'met': [100 * V['dropped_met'], 100 * V['redef_met']]}


def v_airport():
    a = A()
    s = a[a.dept == 'AIR']
    ds = s[s.k == 'debt'].groupby('fy').amt.sum(); py = s[s.k.isin(['sal', 'ben'])].groupby('fy').amt.sum()
    tot = s[s.k.isin(['sal', 'ben', 'np', 'mat', 'debt', 'wo', 'oh', 'oth', 'grant', 'aid'])].groupby('fy').amt.sum()
    V = {'ds_2013': ds[2013], 'ds_2019': ds[2019], 'ds_2025': ds[2025], 'ds_2026': ds[2026], 'pay_2013': py[2013], 'pay_2025': py[2025],
         'pay_2026': py[2026]}
    V['ds_real_x'] = ds[2025] * mult(2025) / (ds[2013] * mult(2013)); V['ds_pay_x'] = ds[2025] / py[2025]
    V['avg_13_16'] = np.mean([ds[y] * mult(y) for y in range(2013, 2017)]); V['avg_23_26'] = np.mean([ds[y] * mult(y) for y in range(2023, 2027)])
    V['avg_x'] = V['avg_23_26'] / V['avg_13_16']
    V['share_2013'], V['share_2025'] = ds[2013] / tot[2013], ds[2025] / tot[2025]
    b = B(); bd = b[(b.dept == 'AIR') & (b.k == 'debt')].groupby('fy').amt.sum()
    V['bud_2026'], V['bud_2027'], V['bud_2028'] = bd[2026], bd[2027], bd[2028]
    V['bud_2013'], V['bud_2025'] = bd[2013], bd[2025]; V['bud_x'] = bd[2025] / bd[2013]
    V = {k: float(v) for k, v in V.items()}
    yrs = list(range(2013, 2027))
    return V, {'x': yrs, 'debt': [ds[y] / 1e6 for y in yrs], 'payroll': [py[y] / 1e6 for y in yrs]}


def v_execution():
    from compute_build import EXEC_DEPTS, EXEC_NAMES
    a, b = A(), B()
    sp = SPEND
    aa = a[a.k.isin(sp) & (a['Fund Category'] == 'Operating')].groupby(['dept', 'fy']).amt.sum()
    bb = b[b.k.isin(sp) & (b['Fund Category'] == 'Operating')].groupby(['dept', 'fy']).amt.sum()
    V = {'cut': 0.95, 'five': 0.05, 'hundred': 1.0}
    med = {}
    for d in EXEC_DEPTS:
        ys = [y for y in range(2013, 2026) if bb.get((d, y), 0) > 0 and (d, y) in aa.index]
        r = pd.Series([aa[(d, y)] / bb[(d, y)] for y in ys])
        med[d] = float(r.median())
        V[f'{d}_med'] = med[d]; V[f'{d}_n'] = len(ys); V[f'{d}_over'] = int((r > 1).sum()); V[f'{d}_under95'] = int((r < 0.95).sum())
        V[f'{d}_cum'] = float(sum(aa[(d, y)] - bb[(d, y)] for y in ys))
    for d in EXEC_DEPTS:
        ys = [y for y in range(2013, 2026) if bb.get((d, y), 0) > 0 and (d, y) in aa.index]
        V[f'{d}_over105'] = int(sum(aa[(d, y)] / bb[(d, y)] > 1.05 for y in ys))
    ys = [y for y in range(2013, 2026)]
    V['DPH_cum_pct'] = float(sum(aa[('DPH', y)] - bb[('DPH', y)] for y in ys) / sum(bb[('DPH', y)] for y in ys))
    op_a = a[a.k.isin(sp) & (a['Fund Category'] == 'Operating') & (a.dept == 'DPH') & a.fy.between(2013, 2025)]
    op_b = b[b.k.isin(sp) & (b['Fund Category'] == 'Operating') & (b.dept == 'DPH') & b.fy.between(2013, 2025)]
    V['DPH_gf_over_amt'] = float(op_a[op_a.gf].amt.sum() - op_b[op_b.gf].amt.sum())
    V['DPH_nongf_over_amt'] = float(op_a[~op_a.gf].amt.sum() - op_b[~op_b.gf].amt.sum())
    ag = a[a.k.isin(sp) & a.gf & (a.dept == 'DPH')].groupby('fy').amt.sum(); bg = b[b.k.isin(sp) & b.gf & (b.dept == 'DPH')].groupby('fy').amt.sum()
    V['DPH_gf_over'] = int(sum(ag[y] > bg[y] for y in range(2013, 2026)))
    V['DPH_gf_over105'] = int(sum(ag[y] > 1.05 * bg[y] for y in range(2013, 2026)))
    order = sorted(EXEC_DEPTS, key=lambda k: med[k])
    return V, {'cats': [EXEC_NAMES[k] for k in order], 'values': [100 * med[k] for k in order]}


VERIFY = {'police_staffing': v_police_staffing, 'ot100k': v_ot100k, 'fire': v_fire, 'police_calls': v_police_calls,
          'homeless': v_homeless, 'pension': v_pension, 'grants': v_grants, 'gf': v_gf, 'vacancy': v_vacancy,
          'ot_budget': v_ot_budget, 'muni_fares': v_muni_fares, 'survey': v_survey, 'library': v_library, 'bonds': v_bonds,
          'targets': v_targets, 'redefined': v_redefined, 'airport': v_airport, 'execution': v_execution}


# ===================================================================================================================
THEMES = {'spending-growth', 'outcomes', 'efficiency', 'staffing', 'budgeting-practice', 'measurement', 'capital', 'equity', 'other'}
CHARTS = {'line', 'bar', 'hbar', 'dumbbell', 'slope', 'stacked', 'smallmultiples', 'scatter', 'waterfall'}
VIEWS = {'pf-overview', 'pf-spending', 'pf-staffing', 'pf-outcomes', 'pf-cost', 'pf-integrity', 'pf-gaps', 'pf-depts'}
REQ = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags']


def keys_used(tpl):
    ks = set()

    def walk(o):
        if isinstance(o, str):
            ks.update(k for k, _ in spec.PH.findall(o))
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
    walk(tpl)
    return ks


def close(a, b, rel=0.005, ab=0.01):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    a, b = float(a), float(b)
    return abs(a - b) <= max(ab * (1 if abs(a) < 2 else 0), rel * max(abs(a), abs(b)), 1e-9)


def main():
    t0 = time.time()
    pub = json.load(open(OUTF))
    built = json.load(open(VALS))
    fails, notes, per = [], [], []
    # 5. contract shape
    for k in ('sample', 'as_of', 'dashboard', 'intro', 'insights'):
        if k not in pub: fails.append(f'top-level field missing: {k}')
    if pub.get('sample') is not False: fails.append('sample must be false')
    ids = [i['id'] for i in pub['insights']]; ranks = [i['rank'] for i in pub['insights']]
    if len(set(ids)) != len(ids): fails.append('duplicate ids')
    if sorted(ranks) != list(range(1, len(ranks) + 1)): fails.append('ranks are not 1..n')
    by_id = {i['id']: i for i in pub['insights']}
    for tpl in spec.INSIGHTS:
        iid, key = tpl['id'], tpl['key']
        ins = by_id.get(iid)
        rec = {'id': iid, 'values_checked': 0, 'chart_points_checked': 0, 'failures': []}
        if ins is None:
            fails.append(f'{iid}: missing from insights.json'); continue
        for f in REQ:
            if f not in ins: rec['failures'].append(f'missing field {f}')
        if ins['theme'] not in THEMES: rec['failures'].append(f'bad theme {ins["theme"]}')
        if ins['chart']['type'] not in CHARTS: rec['failures'].append(f'bad chart type {ins["chart"]["type"]}')
        if ins['robustness']['verdict'] not in ('robust', 'fragile'): rec['failures'].append('bad verdict')
        if len(ins['robustness']['checks']) < 3: rec['failures'].append('fewer than 3 robustness checks')
        if ins['explore']['view'] not in VIEWS: rec['failures'].append(f'unknown view {ins["explore"]["view"]}')
        if len(ins['title']) > 95: rec['failures'].append(f'title longer than ~90 characters ({len(ins["title"])})')
        for n in ins['numbers']:
            path = n['source'].split(' ')[0].split('#')[0].rstrip(';')
            if path.startswith('performance/') and not os.path.exists(os.path.join(os.path.dirname(ROOT), path)):
                rec['failures'].append(f'source path does not exist: {path}')
        # 4. literal numbers
        from build_insights import literal_digit_problems
        for p in literal_digit_problems(tpl):
            rec['failures'].append(f'literal number in template: {p}')
        # 1-3. recompute
        try:
            V2, CH2 = VERIFY[key]()
        except Exception as ex:  # noqa
            import traceback; traceback.print_exc()
            rec['failures'].append(f'recompute error: {ex!r}'); per.append(rec); fails += [f'{iid}: {x}' for x in rec['failures']]; continue
        V1, CH1 = built[iid]['V'], built[iid]['CH']
        for k in sorted(keys_used({kk: vv for kk, vv in tpl.items() if kk != 'key'})):
            rec['values_checked'] += 1
            if k not in V2:
                rec['failures'].append(f'value {k} not recomputed (untraced)'); continue
            if not close(V1.get(k), V2[k]):
                rec['failures'].append(f'value {k}: built {V1.get(k)} vs recomputed {V2[k]}')
        # re-render with recomputed values and compare with the published text
        try:
            r2 = spec.render({kk: vv for kk, vv in tpl.items() if kk != 'key'}, {**V1, **V2}, CH2)
            for fld in ('title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'robustness', 'caveats'):
                if fld in r2 and json.dumps(r2[fld], ensure_ascii=False) != json.dumps(ins.get(fld), ensure_ascii=False):
                    x1, x2 = json.dumps(ins.get(fld), ensure_ascii=False), json.dumps(r2[fld], ensure_ascii=False)
                    i0 = next((i for i, (p, q) in enumerate(zip(x1, x2)) if p != q), min(len(x1), len(x2)))
                    rec['failures'].append(f'text of {fld} differs when rendered from recomputed values: published "...{x1[max(0, i0 - 60):i0 + 40]}" vs recomputed "...{x2[max(0, i0 - 60):i0 + 40]}"')
            for fld in ('title', 'subtitle', 'note', 'type', 'highlight'):
                if r2['chart'].get(fld) != ins['chart'].get(fld):
                    rec['failures'].append(f'chart {fld} differs')
            # published chart arrays vs arrays rendered from the recomputed values
            pubs = [('x', ins['chart']['x']['values'], r2['chart']['x']['values'])] + [
                (f'series {s1["name"]}', s1['values'], s2['values']) for s1, s2 in zip(ins['chart']['series'], r2['chart']['series'])]
            if len(ins['chart']['series']) != len(r2['chart']['series']):
                rec['failures'].append('chart series count differs')
            for nm, pa, ra in pubs:
                if len(pa) != len(ra):
                    rec['failures'].append(f'published chart {nm}: length differs'); continue
                for i, (x, y) in enumerate(zip(pa, ra)):
                    rec['chart_points_checked'] += 1
                    ok = (x == y) if (isinstance(x, str) or isinstance(y, str) or x is None or y is None) else close(x, y, rel=0.01, ab=0.05)
                    if not ok:
                        rec['failures'].append(f'published chart {nm}[{i}]: {x} vs recomputed {y}')
        except Exception as ex:  # noqa
            rec['failures'].append(f'render error: {ex!r}')
        # chart arrays
        for ck, arr in CH1.items():
            if ck not in CH2:
                rec['failures'].append(f'chart array {ck} not recomputed'); continue
            a2 = CH2[ck]
            if len(arr) != len(a2):
                rec['failures'].append(f'chart array {ck} length {len(arr)} vs {len(a2)}'); continue
            for i, (x, y) in enumerate(zip(arr, a2)):
                rec['chart_points_checked'] += 1
                if isinstance(x, str) or isinstance(y, str):
                    ok = x == y
                else:
                    ok = close(x, None if y is None or (isinstance(y, float) and np.isnan(y)) else float(y), rel=0.01, ab=0.05)
                if not ok:
                    rec['failures'].append(f'chart {ck}[{i}]: built {x} vs recomputed {y}')
        print(f'{iid}: {rec["values_checked"]} values, {rec["chart_points_checked"]} chart points, {len(rec["failures"])} failures ({time.time() - t0:.0f}s)', flush=True)
        for f in rec['failures'][:12]:
            print('   FAIL', f)
        per.append(rec)
        fails += [f'{iid}: {x}' for x in rec['failures']]
    rep = {'as_of': spec.AS_OF, 'insights': len(pub['insights']), 'values_checked': sum(r['values_checked'] for r in per),
           'chart_points_checked': sum(r['chart_points_checked'] for r in per), 'failures': fails, 'per_insight': per,
           'method': __doc__.strip().split('\n\n')[1] if '\n\n' in __doc__ else ''}
    json.dump(rep, open(REPORT, 'w'), indent=1, default=float)
    print(f'\n{rep["insights"]} insights, {rep["values_checked"]} values and {rep["chart_points_checked"]} chart points checked; {len(fails)} failures')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
