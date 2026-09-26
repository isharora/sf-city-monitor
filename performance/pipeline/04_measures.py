"""Normalize the Controller's performance measures.

Inputs:
  data/raw/perf_measures/citywide_performance_metrics.csv  (6dpt-7w23; current measure set with history)
  data/raw/perf_measures/annual_report_fy13.csv / _fy14.csv (5x94-tptc / 6h77-suve; FY13/FY14 snapshot, KPI codes)
Outputs:
  data/interim/measures_current.csv   one row per (measure_id, fy): target, result, mid-year
  data/interim/measures_catalog.csv   one row per current measure (id, dept, title, description, methodology, type)
  data/interim/measures_snapshot_fy13_14.csv  long: kpi_code, fy, kind(actual/target/projected), value, report
"""
import pandas as pd, numpy as np, os, sys, re, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from common import *

PM_DEPT = {
    'HUMAN SERVICES': 'HSA', 'SHERIFF': 'SHF', 'PUBLIC WORKS': 'DPW', 'FIRE DEPARTMENT': 'FIR',
    'PUBLIC LIBRARY': 'LIB', 'CONTROLLER': 'CON', 'ELECTIONS': 'REG', 'PORT': 'PRT',
    'PUBLIC UTILITIES COMMISSION': 'PUC', 'BOARD OF SUPERVISORS': 'BOS', 'AIRPORT COMMISSION': 'AIR',
    'CHILDREN YOUTH & THEIR FAMILIES': 'CHF', 'PUBLIC HEALTH': 'DPH', 'POLICE': 'POL',
    'RECREATION AND PARK COMMISSION': 'REC', 'PUBLIC DEFENDER': 'PDR', 'TREASURER/TAX COLLECTOR': 'TTX',
    'ACADEMY OF SCIENCES': 'SCI', 'CITY PLANNING': 'CPC', 'ADMINISTRATIVE SERVICES': 'ADM',
    'BUILDING INSPECTION': 'DBI', 'HUMAN RESOURCES': 'HRD', 'DISTRICT ATTORNEY': 'DAT',
    'FINE ARTS MUSEUM': 'FAM', 'HEALTH SERVICE SYSTEM': 'HSS', 'MUNICIPAL TRANSPORTATION AGENCY': 'MTA',
    'ADULT PROBATION': 'ADP', 'ENVIRONMENT': 'ENV', 'EMERGENCY MANAGEMENT': 'DEM', 'STATUS OF WOMEN': 'WOM',
    'CITY ATTORNEY': 'CAT', 'CHILD SUPPORT SERVICES': 'CSS', 'CIVIL SERVICE COMMISSION': 'CSC',
    'ARTS COMMISSION': 'ART', 'RENT ARBITRATION BOARD': 'RNT',
    "MAYOR'S OFFICE OF HOUSING AND COMMUNITY DEVELOPMENT": 'MYR', 'ASIAN ART MUSEUM': 'AAM',
    'TECHNOLOGY': 'TIS', 'ECONOMIC AND WORKFORCE DEVELOPMENT': 'ECN', 'POLICE ACCOUNTABILITY': 'DPA',
    'HOMELESSNESS AND SUPPORTIVE HOUSING': 'HOM', 'WAR MEMORIAL': 'WAR', 'RETIREMENT SYSTEM': 'RET',
    'EARLY CHILDHOOD': 'DEC', 'LAW LIBRARY': 'LLB', 'BOARD OF APPEALS': 'BOA',
    'COMMUNITY INVESTMENT AND INFRASTRUCTURE': 'CII', 'ETHICS COMMISSION': 'ETH',
    'JUVENILE PROBATION': 'JUV', 'ASSESSOR / RECORDER': 'ASR', 'HUMAN RIGHTS COMMISSION': 'HRC',
    'MAYOR': 'MYR', 'CHILDREN AND FAMILIES COMMISSION': 'CFC',
}


def mid(dept, title):
    return 'M' + hashlib.sha1(f'{dept}|{title.strip().lower()}'.encode()).hexdigest()[:10]


def main():
    m = pd.read_csv(os.path.join(RAW, 'perf_measures', 'citywide_performance_metrics.csv'), dtype=str)
    m = m[m['Fiscal Year'].notna()].copy()
    m['fy'] = m['Fiscal Year'].str.extract(r'FY\d{4}-(\d{2})')[0].astype(int) + 2000
    m['dept'] = m['Department Name'].map(PM_DEPT)
    assert m.dept.notna().all(), m[m.dept.isna()]['Department Name'].unique()
    m['title'] = m['Measure Title'].str.strip()
    m['measure_id'] = [mid(d, t) for d, t in zip(m.dept, m.title)]
    for src, dst in [('Target', 'target'), ('Full-Year Result', 'result'), ('Mid-Year Result', 'mid_result'),
                     ('Mid-Year Projection', 'mid_projection')]:
        m[dst] = pd.to_numeric(m[src], errors='coerce')
    m['data_type'] = m['Measure Data Type']
    dup = m.duplicated(['measure_id', 'fy'], keep=False)
    if dup.any():
        print('WARNING duplicate measure-year rows:', dup.sum())
    cur = m[['measure_id', 'dept', 'title', 'fy', 'data_type', 'target', 'result', 'mid_result', 'mid_projection', 'Data Notes']]
    cur.to_csv(os.path.join(INTERIM, 'measures_current.csv'), index=False)
    cat = m.sort_values('fy').groupby('measure_id').agg(
        dept=('dept', 'first'), department_name=('Department Name', 'first'), title=('title', 'first'),
        goal=('Strategic Goal', 'last'), description=('Measure Description', 'last'),
        methodology=('Measure Methodology', 'last'), data_type=('data_type', 'last'),
        first_fy_with_result=('result', lambda s: np.nan), n_years=('fy', 'nunique')).reset_index()
    fr = cur.dropna(subset=['result']).groupby('measure_id').fy.agg(['min', 'max'])
    cat['first_fy_with_result'] = cat.measure_id.map(fr['min'])
    cat['last_fy_with_result'] = cat.measure_id.map(fr['max'])
    cat.to_csv(os.path.join(INTERIM, 'measures_catalog.csv'), index=False)
    print('current measures:', len(cat), 'rows:', len(cur))
    print(cur.groupby('fy').agg(n=('measure_id', 'size'), with_result=('result', 'count'), with_target=('target', 'count')).to_string())

    # FY13/FY14 snapshots
    out = []
    for rep, fn in [('FY13', 'annual_report_fy13.csv'), ('FY14', 'annual_report_fy14.csv')]:
        a = pd.read_csv(os.path.join(RAW, 'perf_measures', fn), dtype=str)
        a.columns = [re.sub(r'\s+', ' ', c).strip() for c in a.columns]
        a = a[a['KPI_CODE'].notna()]
        for c in a.columns:
            mm = re.match(r'FY (\d{4}) (June |Total )?(Actual|Target|Projected) Data', c)
            if mm and mm.group(2) != 'June ':
                v = pd.to_numeric(a[c].str.replace(',', '').str.replace('%', ''), errors='coerce')
                out.append(pd.DataFrame({'report': rep, 'kpi_code': a['KPI_CODE'].values, 'dept_raw': a['Dept'].values,
                                         'department': a['Department'].values, 'program': a['Program'].values,
                                         'goal': a['Goal'].values, 'title': a['Performance Measure'].str.strip().values,
                                         'description': a['Description'].values, 'pattern': a['Performance Pattern'].values,
                                         'unit': a['Unit of Measure'].values, 'fy': int(mm.group(1)),
                                         'kind': mm.group(3).lower(), 'value': v.values}))
    s = pd.concat(out)
    s['dept'] = s.dept_raw.map(lambda x: canon_dept(x) if isinstance(x, str) else None)
    s.to_csv(os.path.join(INTERIM, 'measures_snapshot_fy13_14.csv'), index=False)
    print('snapshot KPIs:', s.kpi_code.nunique())


if __name__ == '__main__':
    main()
