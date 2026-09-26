"""Parse the Sonnet transcriptions of annual performance reports into tidy measure-year values.

Input: data/interim/pdf_measures_long.csv (from 13_extract_pdf_measures.py)
Output: data/interim/pdf_values.csv    report, report_fy, dept, measure, title_key, fy, kind, value, value_raw
        data/interim/measure_occurrences.csv  one row per (source, report_fy, dept, title_key, title) listing
             every measure title seen in each report / snapshot / current dataset.
Report FY = the fiscal year the report covers (e.g. FY2010 report = FY2009-10 year-end).
"""
import pandas as pd, numpy as np, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from common import *

DMAP = {
    'HUMAN SERVICES': 'HSA', 'HUMAN SERVICES AGENCY': 'HSA', 'PUBLIC LIBRARY': 'LIB', 'PUBLIC HEALTH': 'DPH',
    'PUBLIC UTILITIES COMMISSION': 'PUC', 'PUBLIC UTILITIES': 'PUC', 'SHERIFF': 'SHF', 'CONTROLLER': 'CON', 'POLICE': 'POL',
    'FIRE DEPARTMENT': 'FIR', 'ADMINISTRATIVE SERVICES': 'ADM', 'GENERAL SERVICES AGENCY - CITY ADMINISTRATOR': 'ADM',
    'JUVENILE PROBATION': 'JUV', 'RECREATION AND PARK COMMISSION': 'REC', 'RECREATION & PARK': 'REC',
    'MUNICIPAL TRANSPORTATION AGENCY': 'MTA', 'MTA-MUNICIPAL TRANSPORTATION AGENCY': 'MTA', 'TAXI COMMISSION': 'MTA',
    'CITY PLANNING': 'CPC', 'MAYOR': 'MYR', 'EMERGENCY MANAGEMENT': 'DEM', 'DEPARTMENT OF EMERGENCY MANAGEMENT': 'DEM',
    'EMERGENCY COMMUNICATIONS DEPARTMENT': 'DEM', 'PUBLIC WORKS': 'DPW', 'DEPARTMENT OF PUBLIC WORKS': 'DPW',
    'GENERAL SERVICES AGENCY - PUBLIC WORKS': 'DPW', 'SANITATION AND STREETS': 'DPW', 'ADULT PROBATION': 'ADP',
    'ELECTIONS': 'REG', 'ELECTIONS (FCH)': 'REG', 'CITY ATTORNEY': 'CAT', 'BUILDING INSPECTION': 'DBI',
    'DEPARTMENT OF BUILDING INSPECTION': 'DBI', 'PORT': 'PRT', 'ENVIRONMENT': 'ENV', 'HUMAN RESOURCES': 'HRD',
    'ACADEMY OF SCIENCES': 'SCI', 'HEALTH SERVICE SYSTEM': 'HSS', 'ECONOMIC AND WORKFORCE DEVELOPMENT': 'ECN',
    'ECONOMIC & WORKFORCE DEVELOPMENT': 'ECN', 'PUBLIC DEFENDER': 'PDR', 'TREASURER/TAX COLLECTOR': 'TTX',
    'TREASURER / TAX COLLECTOR': 'TTX', 'BOARD OF SUPERVISORS': 'BOS', 'ARTS COMMISSION': 'ART',
    'CHILDREN YOUTH & THEIR FAMILIES': 'CHF', 'CHILDREN, YOUTH & THEIR FAMILIES': 'CHF',
    'CHILDREN AND FAMILIES COMMISSION': 'CFC', 'CHILDREN & FAMILIES COMMISSION': 'CFC', 'STATUS OF WOMEN': 'WOM',
    'DEPARTMENT OF THE STATUS OF WOMEN': 'WOM', 'ASSESSOR / RECORDER': 'ASR', 'TECHNOLOGY': 'TIS',
    'GENERAL SERVICES AGENCY - TELECOM & INFO SERVICES': 'TIS', 'TELECOMMUNICATIONS & INFORMATION SVCS': 'TIS',
    'AIRPORT COMMISSION': 'AIR', 'AIRPORT': 'AIR', 'DISTRICT ATTORNEY': 'DAT', 'WAR MEMORIAL': 'WAR',
    'HUMAN RIGHTS COMMISSION': 'HRC', 'HUMAN RIGHTS': 'HRC', 'CHILD SUPPORT SERVICES': 'CSS', 'FINE ARTS MUSEUM': 'FAM',
    'FINE ARTS MUSEUMS': 'FAM', 'RENT ARBITRATION BOARD': 'RNT', 'ASIAN ART MUSEUM': 'AAM', 'ETHICS COMMISSION': 'ETH',
    'ETHICS': 'ETH', 'CIVIL SERVICE COMMISSION': 'CSC', 'CIVIL SERVICE': 'CSC', 'RETIREMENT SYSTEM': 'RET',
    'BOARD OF APPEALS': 'BOA', 'LAW LIBRARY': 'LLB', 'HOMELESSNESS AND SUPPORTIVE HOUSING': 'HOM',
    'POLICE ACCOUNTABILITY': 'DPA', 'COMMUNITY INVESTMENT AND INFRASTRUCTURE': 'CII', 'EARLY CHILDHOOD': 'DEC',
    # citywide scorecard theme pages (FY2019 / FY2022 reports), not departments
    'SAFETY NET': 'SCORECARD', 'LIVABILITY': 'SCORECARD', 'TRANSPORTATION': 'SCORECARD', 'PUBLIC SAFETY': 'SCORECARD',
    'ECONOMY': 'SCORECARD', 'FINANCE': 'SCORECARD', 'PUBLIC FINANCE AND BUSINESS AFFAIRS': 'SCORECARD',
    'HOMELESSNESS': 'SCORECARD',
}


def norm_dept(s):
    s = (s if isinstance(s, str) else '').upper()
    s = re.sub(r'\s*-\s*(DEPARTMENT PERFORMANCE MEASURES|SUMMARY YEAR END REPORT).*$', '', s)
    s = re.sub(r'^\d+\.\d+\s+', '', s)
    s = re.sub(r'PAGE \d+', '', s).strip()
    return DMAP.get(s, 'UNMAPPED:' + s)


def title_key(t):
    t = (t if isinstance(t, str) else '').lower()
    t = re.sub(r'[‘’“”"\'`]', '', t)
    t = re.sub(r'[^a-z0-9%$#]+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def parse_col(c):
    c = str(c).strip()
    m = re.match(r'^(?:FY\s*)?(\d{4})\s*-\s*(\d{2,4})\s+(.*)$', c)
    if m:
        y2 = int(m.group(2)[-2:]) + 2000 if len(m.group(2)) <= 2 else int(m.group(2))
        if int(m.group(1)) < 2000 and len(m.group(2)) <= 2:
            y2 = int(m.group(2)[-2:]) + 1900 if int(m.group(2)[-2:]) > 50 else int(m.group(2)[-2:]) + 2000
        rest = m.group(3).lower()
    else:
        m = re.match(r'^FY\s*(\d{2})\s+(.*)$', c)
        if not m:
            return None, None
        y2 = 2000 + int(m.group(1)); rest = m.group(2).lower()
    if '6 mos' in rest or 'mid' in rest:
        kind = 'midyear'
    elif 'target' in rest:
        kind = 'target'
    elif 'actual' in rest or 'result' in rest:
        kind = 'actual'
    elif 'projected' in rest or 'projection' in rest:
        kind = 'projected'
    else:
        kind = None
    return y2, kind


def parse_val(v):
    s = str(v).strip()
    if s == '' or s.lower() in ('n/a', 'na', 'nan', '-', '--', 'tbd', 'n.a.', '*'):
        return np.nan
    s2 = s.replace(',', '').replace('$', '').replace('≥', '').replace('≤', '').replace('<', '').replace('>', '').strip()
    pct = s2.endswith('%')
    s2 = s2.rstrip('%').strip()
    mult = 1.0
    if s2.lower().endswith('m'):
        s2 = s2[:-1]; mult = 1e6
    try:
        x = float(s2) * mult
    except ValueError:
        return np.nan
    return x / 100.0 if pct else x


def main():
    l = pd.read_csv(os.path.join(INTERIM, 'pdf_measures_long.csv'), dtype={'value': str})
    l['report_fy'] = l.report.str[2:].astype(int)
    l['dept'] = l.department.map(norm_dept)
    un = l[l.dept.str.startswith('UNMAPPED')].dept.value_counts()
    if len(un):
        print('unmapped departments:\n', un.to_string())
    l['title_key'] = l.measure.map(title_key)
    pc = l.column.map(parse_col)
    l['fy'] = [p[0] for p in pc]
    l['kind'] = [p[1] for p in pc]
    l['flag_new'] = l.column.str.contains(r'New\?', na=False) & l.value.fillna('').str.strip().ne('')
    l['flag_del'] = l.column.str.contains(r'Del\?', na=False) & l.value.fillna('').str.strip().ne('')
    flags = l.groupby(['report', 'page', 'row']).agg(flag_new=('flag_new', 'any'), flag_del=('flag_del', 'any'))
    v = l[l.kind.notna()].copy()
    v['value_num'] = v.value.map(parse_val)
    v = v.merge(flags.reset_index(), on=['report', 'page', 'row'], how='left', suffixes=('_x', ''))
    v = v[['report', 'report_fy', 'page', 'row', 'dept', 'goal', 'measure', 'title_key', 'fy', 'kind', 'value', 'value_num', 'flag_new', 'flag_del']]
    v.to_csv(os.path.join(INTERIM, 'pdf_values.csv'), index=False)
    print('parsed values:', len(v), 'numeric:', v.value_num.notna().sum())

    occ = l[~l.dept.str.startswith('UNMAPPED') & (l.dept != 'SCORECARD')].groupby(['report_fy', 'dept', 'title_key']).agg(
        title=('measure', 'first')).reset_index()
    occ['source'] = 'pdf_report'
    s = pd.read_csv(os.path.join(INTERIM, 'measures_snapshot_fy13_14.csv'))
    s = s.drop_duplicates(['report', 'dept', 'title'])
    so = pd.DataFrame({'report_fy': s.report.str[2:].astype(int) + 2000, 'dept': s.dept, 'title_key': s.title.map(title_key),
                       'title': s.title, 'source': 'snapshot_' + s.report})
    cat = pd.read_csv(os.path.join(INTERIM, 'measures_catalog.csv'))
    co = pd.DataFrame({'report_fy': 2026, 'dept': cat.dept, 'title_key': cat.title.map(title_key), 'title': cat.title,
                       'source': 'current_6dpt', 'measure_id': cat.measure_id})
    allocc = pd.concat([occ, so.dropna(subset=['dept']), co], ignore_index=True)
    allocc.to_csv(os.path.join(INTERIM, 'measure_occurrences.csv'), index=False)
    u = allocc.groupby('dept').title_key.nunique().sort_values(ascending=False)
    print('unique titles per dept:\n', u.to_string())


if __name__ == '__main__':
    main()
