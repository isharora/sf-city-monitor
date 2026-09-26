"""Resolve officials: elected officers, candidates, commissioners and department heads.

Sources: candidate committees (Ethics filers), Form 700 cover pages, 126f4 approving officers, behested-payment filers,
lobbyist contact reports (official name + department).

Fairness rule: individual city employees below the executive/elected level are not named. Lobbying contacts with such
staff are aggregated to "<Department> staff". An official is "nameable" if they are an elected officer or candidate, a
commissioner/board member, or a department head (evidence: Form 700 position, or filing as an officer on a
behested-payment report).

Outputs data/er/officials.parquet and data/er/lobby_official_map.parquet
"""
import os, re
import numpy as np
import pandas as pd
from names import basic, canon_first

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.join(HERE, '..', 'data', 'interim')
ER = os.path.join(HERE, '..', 'data', 'er')

CITY_OFFICES = ['Mayor', 'Board of Supervisors', 'City Attorney', 'District Attorney', 'Sheriff', 'Treasurer',
                'Assessor-Recorder', 'Public Defender', 'Board of Education', 'Community College Board']
DEPT_TO_OFFICE = [(r'SUPERVISOR', 'Board of Supervisors'), (r'^MAYOR|MAYOR S OFFICE|OFFICE OF THE MAYOR|MAYOR OFFICE', 'Mayor'),
                  (r'CITY ATTORNEY', 'City Attorney'), (r'DISTRICT ATTORNEY', 'District Attorney'), (r'SHERIFF', 'Sheriff'),
                  (r'TREASURER', 'Treasurer'), (r'ASSESSOR', 'Assessor-Recorder'), (r'PUBLIC DEFENDER', 'Public Defender'),
                  (r'SCHOOL|EDUCATION|SFUSD', 'Board of Education'), (r'COLLEGE', 'Community College Board')]


def lastkey(l):
    l = basic(l)
    l = re.sub(r'\b(JR|SR|II|III|IV|MD|PHD|ESQ)\b', '', l)
    return re.sub(r'\s+', ' ', l).strip()


def nk_from_lastfirst(s):
    if not isinstance(s, str) or not s.strip():
        return ''
    if ',' in s:
        last, first = s.split(',', 1)
    else:
        parts = s.split()
        if len(parts) < 2:
            return ''
        first, last = parts[0], parts[-1]
    return lastkey(last) + '|' + canon_first(first)


def dept_office(d):
    b = basic(d)
    for rx, off in DEPT_TO_OFFICE:
        if re.search(rx, b):
            return off
    return None


EXEC_EXACT = {'SUPERVISOR', 'MAYOR', 'CITY ATTORNEY', 'DISTRICT ATTORNEY', 'SHERIFF', 'TREASURER', 'ASSESSOR RECORDER',
              'PUBLIC DEFENDER', 'COMMISSIONER', 'MEMBER', 'BOARD MEMBER', 'TRUSTEE', 'EXECUTIVE DIRECTOR',
              'GENERAL MANAGER', 'DEPARTMENT HEAD', 'CITY ADMINISTRATOR', 'CONTROLLER', 'CHIEF OF POLICE', 'FIRE CHIEF',
              'PRESIDENT', 'VICE PRESIDENT', 'CHAIR', 'DIRECTOR OF PLANNING', 'ZONING ADMINISTRATOR', 'PORT DIRECTOR',
              'AIRPORT DIRECTOR', 'CHIEF EXECUTIVE OFFICER', 'SUPERINTENDENT', 'CHANCELLOR', 'CITY ARCHITECT', 'CITY ENGINEER'}


def position_is_exec(pos, dept):
    if not isinstance(pos, str):
        return False
    for piece in re.split(r'[,;]', pos):
        p = basic(piece)
        if not p or re.search(r'\b(DEPUTY|ASSISTANT|ASSOCIATE|ALL DEPARTMENTS|ALL STAFF|LEVEL|I|II|III|IV)\b', p):
            continue
        if p in EXEC_EXACT or p.startswith('DIRECTOR OF') or 'GENERAL MANAGER' in p or p.endswith('COMMISSIONER'):
            if p == 'SUPERVISOR' and 'SUPERVISORS' not in basic(dept):
                continue
            return True
    return False


def main():
    com = pd.read_parquet(os.path.join(INT, 'committees.parquet'))
    cc = com[com.office.isin(CITY_OFFICES) & com.kind.eq('candidate') & com.candidate_name.notna()].copy()
    cc['nk'] = cc.candidate_name.map(nk_from_lastfirst)
    cc['year'] = pd.to_numeric(cc.filer_name.str.extract(r'((?:19|20)\d\d)', expand=False), errors='coerce')
    cand = cc.groupby('nk').agg(display=('candidate_name', 'first'), offices_sought=('office', lambda s: ', '.join(sorted(set(s)))),
                                committees=('filer_nid', lambda s: ','.join(s.astype(str))), n_committees=('filer_nid', 'size'),
                                first_year=('year', 'min'), last_year=('year', 'max')).reset_index()

    f7 = pd.read_parquet(os.path.join(INT, 'f700_cover.parquet'))
    f7['nk'] = f7.lastname.map(lastkey) + '|' + f7.firstname.map(canon_first)
    f7['year'] = pd.to_numeric(f7.year, errors='coerce')
    f7['eobcdh'] = f7.departmentname.fillna('').str.contains('EOBCDH') | (f7.year < 2021)
    f7['exec'] = f7.eobcdh | [position_is_exec(p, d) for p, d in zip(f7.positionname, f7.departmentname)]
    f7x = f7.groupby('nk').agg(f700_exec=('exec', 'any'), f700_positions=('positionname', lambda s: ' | '.join(s.dropna().astype(str).value_counts().index[:3])),
                               f700_depts=('departmentname', lambda s: ' | '.join(s.dropna().astype(str).str.replace('EOBCDH_', '').value_counts().index[:3])),
                               f700_years=('year', lambda s: f'{int(s.min())}-{int(s.max())}' if s.notna().any() else '')).reset_index()

    bp = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    bp['nk'] = bp.official.map(nk_from_lastfirst)
    bpo = bp.groupby('nk').agg(bp_agency=('agency', 'first'), bp_n=('amount', 'size')).reset_index()

    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    lc['nk'] = lc.officialname.map(nk_from_lastfirst)
    lc['dept_office'] = lc.departmentname.map(dept_office)
    lo = lc.groupby(['nk', 'departmentname']).agg(n=('id', 'size'), name=('officialname', 'first'), dept_office=('dept_office', 'first')).reset_index()
    lo = lo.merge(cand[['nk', 'offices_sought', 'display']], on='nk', how='left').merge(f7x, on='nk', how='left').merge(bpo, on='nk', how='left')

    def classify(r):
        if isinstance(r.offices_sought, str) and r.dept_office and r.dept_office in r.offices_sought:
            return 'elected'
        if r.f700_exec is True or (isinstance(r.bp_agency, str)):
            return 'appointed_exec'
        return 'staff'
    lo['category'] = [classify(r) for r in lo.itertuples()]
    lo['official_id'] = np.where(lo.category == 'staff', 'STAFF:' + lo.departmentname.fillna('Unknown').map(basic), 'O:' + lo.nk)
    lo['label'] = np.where(lo.category == 'staff', lo.departmentname.fillna('Unknown department') + ' staff', lo.name)
    lo.to_parquet(os.path.join(ER, 'lobby_official_map.parquet'), index=False)

    # official registry: candidates for city office + nameable officials seen in lobbying/behested/126
    reg = cand.merge(f7x, on='nk', how='left')
    reg['category'] = 'candidate_or_elected'
    extra = lo[lo.category == 'appointed_exec'].groupby('nk').agg(display=('name', 'first'), departments=('departmentname', lambda s: ' | '.join(s.dropna().unique()[:3]))).reset_index()
    extra = extra[~extra.nk.isin(reg.nk)].merge(f7x, on='nk', how='left')
    extra['category'] = 'appointed_exec'
    def swap_fix(nk, name):
        if nk in set(reg.nk):
            return nk
        parts = str(name).replace(',', ' ').split()
        if len(parts) >= 2:
            alt = lastkey(parts[0]) + '|' + canon_first(parts[-1])
            if alt in set(reg.nk):
                return alt
        return nk
    bp['nk'] = [swap_fix(n, x) for n, x in zip(bp.nk, bp.official)]
    bpx = bp[~bp.nk.isin(reg.nk) & ~bp.nk.isin(extra.nk) & (bp.nk != '')].groupby('nk').agg(display=('official', 'first'), departments=('agency', 'first')).reset_index()
    bpx['category'] = 'appointed_exec'
    officials = pd.concat([reg, extra, bpx], ignore_index=True)
    officials['official_id'] = 'O:' + officials.nk
    # contacts summary
    lsum = lo[lo.category != 'staff'].groupby('official_id').n.sum()
    officials['lobby_contacts'] = officials.official_id.map(lsum).fillna(0).astype(int)
    officials.to_parquet(os.path.join(ER, 'officials.parquet'), index=False)
    print(officials.category.value_counts())
    print(lo.groupby('category').n.sum())
    print(lo[lo.category != 'staff'].groupby('label').n.sum().sort_values().tail(25))


if __name__ == '__main__':
    main()
