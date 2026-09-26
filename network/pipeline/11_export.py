"""Export dashboard data to network/data/site/ following design/DATA_CONTRACT_network.md.

Fairness encoded in data:
  * Private individuals never appear as entities: individual contributions are aggregated into `individuals` entities:
      ind-all                   everyone not affiliated with a listed contractor
      ind-emp-<contractor>      donors whose employer field matches a city contractor (employees; NOT covered by §1.126)
      ind-prin-<contractor>     donors matched to principals disclosed on SFEC-126(f)4 filings (count only; names not exported)
  * Organizations whose name is a private person's name (Claude classification, data/er/entity_types.parquet) are folded
    into ind-all (contributions/behested) or dropped (vendor payments to individuals).
  * No addresses, ZIP codes or employer text are exported.
Amounts are nominal dollars. Years exported: 2015-2026 (calendar years by transaction date; vendor payments by fiscal year start).
"""
import os, re, json, hashlib, datetime, importlib.util
import numpy as np
import pandas as pd
from names import basic, canon_first, is_non_employer
import roster

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.join(HERE, '..', 'data', 'interim')
ER = os.path.join(HERE, '..', 'data', 'er')
NET = os.path.join(HERE, '..', 'data', 'network')
AN = os.path.join(HERE, '..', 'data', 'analysis')
RAW = os.path.join(HERE, '..', 'data', 'raw')
SITE = os.path.join(HERE, '..', 'data', 'site')
os.makedirs(os.path.join(SITE, 'analyses'), exist_ok=True)
os.makedirs(os.path.join(SITE, 'commentary'), exist_ok=True)

spec = importlib.util.spec_from_file_location('m6', os.path.join(HERE, '06_officials.py'))
m6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m6)
spec = importlib.util.spec_from_file_location('m8', os.path.join(HERE, '08_network.py'))
m8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m8)

Y0, Y1 = 2015, 2026
AS_OF = '2026-09-26'
GENERATED = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

LOBBY_DEPT = [(r'PLANNING', 'CPC'), (r'SUPERVISORS|SUPERVISOR ', 'BOS'), (r'RETIREMENT', 'RET'), (r'^MAYOR|MAYOR$|OFFICE OF THE MAYOR', 'MYR'),
              (r'MUNICIPAL TRANSPORTATION|SFMTA|\bMTA\b', 'MTA'), (r'BUILDING INSPECTION|BOARD INSPECTION', 'DBI'),
              (r'ECONOMIC.*WORKFORCE|WORKFORCE', 'ECN'), (r'PUBLIC WORKS', 'DPW'), (r'CITY ATTORNEY', 'CAT'),
              (r'OCII|COMMUNITY INVESTMENT|REDEVELOPMENT', 'CII'), (r'CITY ADMINISTRATOR', 'ADM'), (r'RECREATION', 'REC'),
              (r'AIRPORT', 'AIR'), (r'POLICE ACCOUNTAB', 'DPA'), (r'POLICE', 'POL'), (r'PUBLIC UTILITIES', 'PUC'), (r'^PORT', 'PRT'),
              (r'^FIRE', 'FIR'), (r'ENVIRONMENT', 'ENV'), (r'CONTROLLER', 'CON'), (r'TECHNOLOGY', 'TIS'), (r'PUBLIC HEALTH', 'DPH'),
              (r'BOARD OF APPEALS|APPEALS', 'BOA'), (r'TREASURER', 'TTX'), (r'TRANSPORTATION AUTHORITY', 'CTA'),
              (r'EMERGENCY', 'DEM'), (r'DISTRICT ATTORNEY', 'DAT'), (r'ARTS COMMISSION', 'ART'), (r'HOMELESS', 'HOM'),
              (r'ASSESSOR', 'ASR'), (r'HEALTH SERVICE', 'HSS'), (r'HUMAN SERVICES', 'HSA'), (r'HUMAN RIGHTS', 'HRC'),
              (r'ADULT PROBATION', 'ADP'), (r'HUMAN RESOURCES', 'HRD'), (r'SHERIFF', 'SHF'), (r'CHILDREN', 'CHF'),
              (r'ETHICS', 'ETH'), (r'TRANSBAY', 'TJP'), (r'ELECTIONS', 'REG'), (r'PUBLIC DEFENDER', 'PDR'), (r'LIBRARY', 'LIB'),
              (r'SMALL BUSINESS', 'ECN'), (r'SCHOOL|EDUCATION', 'USD'), (r'CITY COLLEGE', 'CCD')]


def lobby_dept_code(name):
    b = basic(name)
    for rx, code in LOBBY_DEPT:
        if re.search(rx, b):
            return code
    return None


def sid(prefix, key, n=8):
    return f'{prefix}-' + hashlib.md5(str(key).encode()).hexdigest()[:n]


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o != o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return None if pd.isna(o) else o.strftime('%Y-%m-%d')
    return o


def W(rel, obj):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as fh:
        json.dump(clean(obj), fh, separators=(',', ':'), ensure_ascii=False)
    return os.path.getsize(p)


def d10(x):
    return None if pd.isna(x) else pd.Timestamp(x).strftime('%Y-%m-%d')


def main():
    nodes = pd.read_parquet(os.path.join(NET, 'nodes.parquet'))
    edges = pd.read_parquet(os.path.join(NET, 'edges.parquet'))
    label = dict(zip(nodes.node_id, nodes.label))
    com = pd.read_parquet(os.path.join(INT, 'committees.parquet'))
    com['node_id'] = 'C:' + com.filer_nid.astype(str)
    offs = pd.read_parquet(os.path.join(ER, 'officials.parquet'))
    ents = pd.read_parquet(os.path.join(ER, 'org_entities.parquet')).set_index('entity_default')
    et = pd.read_parquet(os.path.join(ER, 'entity_types.parquet')).set_index('node_id')
    person_like = set(et[(et.is_person == True) & (et.person_conf >= 0.5)].index)
    # red-team pass 2 overrides (14_redteam2.py, Claude Opus re-adjudication of person-looking organization names)
    _ov = os.path.join(ER, 'entity_type_overrides.parquet')
    if os.path.exists(_ov):
        ov = pd.read_parquet(_ov)
        person_like |= set(ov[ov.is_person == True].node_id)
        person_like -= set(ov[ov.is_person == False].node_id)
    llm_type = et.llm_type.to_dict()
    R = m8.OrgResolver('default')

    # ------------------------------------------------------------------ id maps
    E = {}          # entity id -> entity dict
    node2ent = {}   # network node id -> export entity id

    def add(eid, **kw):
        if eid not in E:
            E[eid] = dict(id=eid, **kw)
        return eid

    add('ind-all', type='individuals', name='Individual donors not affiliated with a listed contractor (aggregate)', count=0, affiliated_with=None,
        basis='All individual contributors, behested payors and other private persons not matched to a city contractor', cluster='contractors_and_donors')

    # contractors: entities with Controller contracts or 126f4 approvals
    ctr_nodes = set(edges[edges.edge_type.isin(['contract', 'contract_approval'])].target.dropna())
    # nonprofits: vendor-payment nonprofit flag or city-data nonprofit flag
    vp = edges[edges.edge_type == 'vendor_payment']
    np_nodes = set(vp[vp['attrs'].str.contains('"nonprofit": true')].target) | set(ents[ents.np_flag].index)
    np_nodes = {n for n in np_nodes if llm_type.get(n) not in ('government', 'company') and not re.search(
        r'REGENTS|UNIVERSITY OF CALIFORNIA|CITY COLLEGE|STATE OF|COUNTY OF|HEALTH PLAN|DENTAL PLAN|BLUE SHIELD|VISION SERVICE PLAN|\bJV\b|JOINT VENTURE|CONSTRUCTION', str(label.get(n, '')).upper())}
    # nonprofits module ids
    npmod = {}
    npi = os.path.expanduser('~/sf-city-monitor/nonprofits/data/site/orgs/index.json')
    if os.path.exists(npi):
        for o in json.load(open(npi))['orgs']:
            e_ = R(o['name'])[0]
            if e_:
                npmod.setdefault(e_, o['id'])
    principals_disclosed = pd.read_parquet(os.path.join(INT, 'f126_parties.parquet'))
    principals_disclosed = principals_disclosed[principals_disclosed.is_person]
    pdc = {}
    for c_, g in principals_disclosed.groupby('contractor'):
        e_ = R(c_)[0]
        if e_:
            pdc[e_] = pdc.get(e_, 0) + g[['first', 'last']].drop_duplicates().shape[0]

    def org_entity(node):
        """Map an ORG network node to an export entity id (or ind-all for person-like names)."""
        if node is None or not isinstance(node, str) or not node.startswith('ORG:'):
            return None
        if node in node2ent:
            return node2ent[node]
        if node in person_like:
            node2ent[node] = 'ind-all'
            return 'ind-all'
        if re.match(r'^\s*(SEE ATTACHED|VARIOUS|N/?A\b|UNKNOWN|MULTIPLE)', str(label.get(node, '')), re.I):
            node2ent[node] = add('org-unspecified', type='donor_org', name='Party not itemized in the data (see the filing)', org_type='placeholder', cluster='contractors_and_donors')
            return node2ent[node]
        name = re.sub(r'\s*\(+\s*RESPONSIBLE OFFICER[^)]*\)+', '', str(label.get(node, node)), flags=re.I)
        name = re.sub(r'\s*\(([A-Z][a-z]+ [A-Z][a-z]+)\)$', '', name)   # trailing '(Firstname Lastname)'
        name = re.sub(r',?\s*c/o\s+.*$', '', name, flags=re.I).strip() or name
        if node in np_nodes:
            eid = add('np-' + node[4:], type='nonprofit', name=name, nonprofit_org=npmod.get(node), cluster='nonprofits')
        elif node in ctr_nodes:
            eid = add('con-' + node[4:], type='contractor', name=name, principals_disclosed=int(pdc.get(node, 0)),
                      sector=llm_type.get(node) or (ents.at[node, 'type'] if node in ents.index else None), cluster='contractors_and_donors')
        else:
            eid = add('org-' + node[4:], type='donor_org', name=name, org_type=llm_type.get(node) or (ents.at[node, 'type'] if node in ents.index else None),
                      cluster='contractors_and_donors')
        node2ent[node] = eid
        return eid

    # officials
    off_meta = offs.set_index('official_id')
    hj = json.load(open(os.path.join(AN, 'official_holding.json')))
    HELD = {(h['official'], h['office']): set(h['years']) for h in hj['holding']}
    _lm = pd.read_parquet(os.path.join(ER, 'lobby_official_map.parquet'))
    _lm = _lm[(_lm.category == 'appointed_exec') & ~_lm.departmentname.fillna('').str.contains('Supervisors|Mayor', case=False)]
    APPOINTED = {('O:' + k): ', '.join(sorted(set(g.departmentname.dropna()))[:3]) for k, g in _lm.groupby('nk')}
    CITY = roster.citywide_intervals()
    MON = lambda t: t.strftime('%b %Y')

    def OFFICE_LABEL(oid, off, since=2009):
        # citywide office: when any term was interim or acting, list every term with its role and dates (verified table)
        ivs = sorted((x for x in CITY.get((oid, off), []) if x[1].year >= since), key=lambda x: x[0])
        if not any(r['role'] in ('interim', 'acting') for a, b, r in ivs):
            return off
        parts = [f"{r['role']} {MON(a)} to {MON(b)}" if r.get('end') else f"{r['role']} since {MON(a)}" for a, b, r in ivs]
        return off + f" ({'; '.join(parts)})"
    hold = {}
    # term: first/last year of evidence (candidacy committees, Form 700 2013-2021, lobbyist-contact years)
    cand_years = com[com.is_city_candidate].assign(y=pd.to_numeric(com.filer_name.str.extract(r'((?:19|20)\d\d)', expand=False), errors='coerce'))
    ctl = edges[edges.edge_type == 'controls']
    com_off = ctl.groupby('target').source.first().to_dict()

    def official_entity(oid):
        if not isinstance(oid, str) or not oid.startswith('O:'):
            return None
        eid = 'off-' + oid[2:].replace('|', '-').replace(' ', '_').lower()
        if eid not in E:
            r = off_meta.loc[oid] if oid in off_meta.index else None
            office = None
            if r is not None and isinstance(r.offices_sought, str):
                office = r.offices_sought
            elif r is not None:
                office = (r.get('departments') if isinstance(r.get('departments'), str) else None)
            yrs = cand_years[cand_years.node_id.map(com_off) == oid].y.dropna()
            cat = (r.category if r is not None else 'referenced')
            held = {off_: ys for (o_, off_), ys in HELD.items() if o_ == oid}
            if cat == 'candidate_or_elected':
                # red-team pass 2: say "held" only with roster evidence (roster.py); otherwise label as a candidate
                if held:
                    hy = sorted(set().union(*held.values()))
                    sought = [x for x in str(office or '').split(', ') if x and x not in held]
                    office = ', '.join(OFFICE_LABEL(oid, h) for h in sorted(held)) + (f" (also ran for {', '.join(sought)})" if sought else '')
                    term = [hy[0], hy[-1]]
                    cat = 'elected_or_appointed'
                    tnote = ('years holding office (sfbos.org roster for the Board of Supervisors; verified office-history table with official '
                             'sources for citywide offices, including appointed, interim and acting terms; Form 700 2013-2021 or lobbyist '
                             'contact reports for other bodies); partial years count')
                elif any(o_ == oid for (o_, off_) in CITY):
                    # held a citywide office only before the 2009-2026 window (verified table), e.g. a former Treasurer who later ran
                    pre = sorted((a, b, off_) for (o_, off_), ivs in CITY.items() if o_ == oid for a, b, r in ivs)
                    office = (', '.join(sorted({f'{x[2]} (before 2009, {x[0].year} to {x[1].year})' for x in pre}))
                              + (f"; also ran for {office}" if office else ''))
                    term = [pre[0][0].year, pre[-1][1].year]
                    cat = 'elected_or_appointed'
                    tnote = ('held a citywide office before the 2009-2026 analysis window (verified office-history table, offices_citywide.json); '
                             'no City elective office in 2009-2026, so not treated as an officeholder for §1.126 coverage')
                else:
                    office = 'Candidate for ' + office if office else 'Candidate for City office'
                    ap = APPOINTED.get(oid)
                    if ap:
                        office += f'; lobbying reports list them as an official of {ap}'
                    term = None
                    cat = 'candidate'
                    tnote = (f'no evidence of holding City elective office in 2009-2026 (citywide offices checked against the complete verified '
                             f'succession, offices_citywide.json)' + (f'; own candidate committee years {int(yrs.min())}-{int(yrs.max())}' if len(yrs) else ''))
            else:
                term = [int(yrs.min()) - 1, int(yrs.max())] if len(yrs) else None
                tnote = 'approximate: from own committee years (election year minus one to election year)'
            add(eid, type='official', name=m8.pretty(r.display) if r is not None else m8.pretty(oid[2:].replace('|', ', ')), office=office, term=term,
                category=cat, term_note=tnote, cluster='officials')
        return eid

    def committee_entity(cnode):
        eid = 'cmte-' + cnode[2:]
        if eid not in E:
            r = com[com.node_id == cnode]
            if not len(r):
                return None
            r = r.iloc[0]
            add(eid, type='committee', name=r.filer_name, official=official_entity(com_off.get(cnode)), fppc_id=r.fppc_id if isinstance(r.fppc_id, str) else None,
                committee_kind=r.kind, office=r.office if isinstance(r.office, str) else None, cluster='officials')
        return eid

    depts = {}
    dnames = pd.read_parquet(os.path.join(INT, 'vendor_pay.parquet'))[['department_code', 'department']].drop_duplicates('department_code')
    dname = dict(zip(dnames.department_code, dnames.department.str.replace(r'^[A-Z]{3} ', '', regex=True)))

    def dept_entity(code):
        if not code:
            return None
        eid = 'dept-' + code
        if eid not in E:
            add(eid, type='department', name=dname.get(code, code), code=code, cluster='city')
        return eid

    lob_names = {}

    def lobbyist_entity(lnode, firm=None):
        if not isinstance(lnode, str) or not lnode.startswith('L:'):
            return None
        eid = 'lob-' + lnode[2:].replace('|', '-').replace(' ', '_').lower()
        if eid not in E:
            add(eid, type='lobbyist', name=label.get(lnode, lnode[2:]), lobbyist_type=None, registered_since=None, firm=firm, cluster='lobbying')
        return eid

    ld = pd.read_parquet(os.path.join(INT, 'lob_directory.parquet'))
    ld['lnode'] = 'L:' + ld.lobbyistname.map(m6.nk_from_lastfirst)
    ldm = ld.set_index('lnode')

    # ------------------------------------------------------------------ flows
    flows = []
    fid = [0]

    def F(frm, to, typ, date, amount, count=1, ref=None, **kw):
        if frm is None or to is None or date is None:
            return None
        fid[0] += 1
        kw = {k: v for k, v in kw.items() if v is not None and v is not False}
        f = dict(id=f'fl-{fid[0]:06d}', **{'from': frm}, to=to, type=typ, date=date, amount=None if amount is None or amount != amount else int(round(amount)),
                 count=int(count), ref=ref or {'form': None, 'id': None, 'url': None}, **kw)
        flows.append(f)
        return f['id']

    inyears = lambda d: d is not None and not pd.isna(d) and Y0 <= pd.Timestamp(d).year <= Y1

    # --- contributions
    ind_counts = {}
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'))
    c = c[(c.date.dt.year >= Y0) & (c.date.dt.year <= Y1)]
    de = pd.read_parquet(os.path.join(ER, 'donor_elements.parquet'))
    c = c.merge(de[['element_nid', 'pid']], on='element_nid', how='left')
    c['cnode'] = 'C:' + c.filer_nid.astype(str)
    # organizations (transaction level, but aggregated per org->committee->month)
    org = c[~c.is_individual].copy()
    org['node'] = [R(x)[0] for x in org.donor_last]
    org['from'] = org.node.map(org_entity)
    org['month'] = org.date.dt.to_period('M')
    for (frm, cn, mth), g in org.dropna(subset=['from']).groupby(['from', 'cnode', 'month']):
        to = committee_entity(cn)
        F(frm, to, 'contribution', g.date.min().strftime('%Y-%m-%d'), g.amount.sum(), count=len(g), aggregated=len(g) > 1,
          period='month' if len(g) > 1 else None, ref={'form': 'Form 460 Sch. A/C', 'id': g.element_nid.iloc[0] if len(g) == 1 else None, 'url': None})
    # individuals: principals (matched, conf>=0.8) -> ind-prin-<contractor>; employees of contractors -> ind-emp-<contractor>; else ind-all
    pm = pd.read_parquet(os.path.join(ER, 'person_matches.parquet'))
    prin = pm[(pm.kind == 'principal') & (pm.decision == 'same') & (pm.confidence >= 0.8)].copy()
    prin['ent'] = prin.role_id.str.split('|', n=2).str[-1].map(R.ent)
    pid_prin = prin.dropna(subset=['ent']).groupby('pid').ent.first().to_dict()
    ind = c[c.is_individual].copy()
    empres = {x: (None if is_non_employer(x) else R(x)[0]) for x in ind.employer.dropna().unique()}
    ind['emp_node'] = ind.employer.map(empres)
    ind['prin_node'] = ind.pid.map(pid_prin)

    def ind_bucket(r_prin, r_emp):
        if isinstance(r_prin, str):
            ce = org_entity(r_prin)
            base = ce if ce and ce != 'ind-all' else None
            if base:
                return add('ind-prin-' + r_prin[4:], type='individuals', name=f'Disclosed principals of {label.get(r_prin, "")} who gave (aggregate)',
                           count=0, affiliated_with=base, basis='name matched to a person listed on SFEC-126(f)4 filings (board member, officer, 10%+ owner); Claude-checked, confidence >= 0.8',
                           cluster='contractors_and_donors')
        if isinstance(r_emp, str) and r_emp in ctr_nodes:
            ce = org_entity(r_emp)
            if ce and ce != 'ind-all':
                return add('ind-emp-' + r_emp[4:], type='individuals', name=f'Individuals naming {label.get(r_emp, "")} as employer (aggregate)',
                           count=0, affiliated_with=ce, basis='employer field on Form 460 resolves to this contractor; employees are not covered by the §1.126 ban unless they are also principals',
                           cluster='contractors_and_donors')
        return 'ind-all'
    ind['bucket'] = [ind_bucket(a, b) for a, b in zip(ind.prin_node, ind.emp_node)]
    cnt = ind.groupby('bucket').pid.nunique()
    for b, n in cnt.items():
        E[b]['count'] = int(n)
    # principals & employees: one flow per contribution (needed for the ban analysis); ind-all: monthly aggregates
    emp_rows = ind[ind.bucket.str.startswith('ind-emp-')].copy()
    emp_rows['yr'] = emp_rows.date.dt.year
    for (b, cn, yr), g in emp_rows.groupby(['bucket', 'cnode', 'yr']):
        F(b, committee_entity(cn), 'contribution', g.date.min().strftime('%Y-%m-%d'), g.amount.sum(), count=g.pid.nunique(), aggregated=True, period='year',
          ref={'form': 'Form 460 Sch. A/C', 'id': None, 'url': None})
    aff = ind[ind.bucket.str.startswith('ind-prin-')]
    contrib_flow = {}
    for r in aff.itertuples():
        to = committee_entity(r.cnode)
        f = F(r.bucket, to, 'contribution', r.date.strftime('%Y-%m-%d'), r.amount, count=1, aggregated=True,
              ref={'form': 'Form 460 Sch. A/C', 'id': r.element_nid, 'url': None})
        contrib_flow[r.element_nid] = f
    rest = ind[ind.bucket == 'ind-all'].copy()
    rest['month'] = rest.date.dt.to_period('M')
    for (cn, mth), g in rest.groupby(['cnode', 'month']):
        F('ind-all', committee_entity(cn), 'contribution', g.date.min().strftime('%Y-%m-%d'), g.amount.sum(), count=g.pid.nunique(),
          aggregated=True, period='month', ref={'form': 'Form 460 Sch. A/C', 'id': None, 'url': None})
    print('contribution flows', len(flows))

    # --- behested
    beh = pd.read_parquet(os.path.join(AN, 'behested_pending_business.parquet'))
    bedges = edges[edges.edge_type == 'behested_payment'].copy()
    bedges['a'] = [json.loads(x) for x in bedges['attrs']]
    bedges['form'] = [a.get('form') for a in bedges.a]
    bedges['purpose'] = [a.get('purpose') for a in bedges.a]
    bedges['payee_raw'] = [a.get('payee_raw') or '' for a in bedges.a]
    bedges = bedges[~bedges.payee_raw.str.upper().str.contains('SEE ATTACHED')]
    bedges['dk'] = bedges.official.astype(str) + bedges.source.astype(str) + bedges.target.astype(str) + bedges.date.astype(str)
    bedges = bedges.drop_duplicates('dk', keep='last')
    bp_raw = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    filed = bp_raw.set_index('filing_id').filed.to_dict() if 'filing_id' in bp_raw else {}
    beh_rows = []
    pbk = beh.set_index(['official', 'payor', 'payee', 'date'])
    for r in bedges.itertuples():
        if not inyears(r.date):
            continue
        frm = org_entity(r.source) or 'ind-all'
        to = org_entity(r.target) or 'ind-all'
        off = official_entity(r.official)
        f = F(frm, to, 'behested', d10(r.date), r.amount, behest_of=off, purpose=r.purpose,
              ref={'form': 'SFEC 3610(b)' if '3610' in str(r.form) else ('FPPC 803' if '803' in str(r.form) else 'SFEC 3600'), 'id': r.record_id, 'url': None})
        key = (r.official, r.source, r.target, r.date)
        ip, basis = False, None
        if key in pbk.index:
            x = pbk.loc[key]
            x = x.iloc[0] if isinstance(x, pd.DataFrame) else x
            parts = []
            if x.lobbied_same_official_12m: parts.append(f'{int(x.lobbied_same_official_12m)} lobbying contacts with this official within 12 months')
            if x.lobbied_same_body_12m: parts.append(f'{int(x.lobbied_same_body_12m)} lobbying contacts with the official\'s body/department within 12 months')
            if x.contract_approvals_same_body_12m: parts.append(f'{int(x.contract_approvals_same_body_12m)} contract approvals by the official\'s body within 12 months')
            ip = bool(parts); basis = '; '.join(parts) if parts else None
        if '3610' in str(r.form) and not ip:
            basis = 'Filed on SFEC 3610(b), which is required only when the payor is an interested party; the public data used here do not show the underlying matter'
            ip = True
        fd = filed.get(r.record_id)
        # Form 803 rows have no payment date (their date is not when the payment was made), so on-time filing cannot be judged: null
        # (CONTRACT_GAPS.md). Only SFEC 3600 / 3610(b) rows carry a payment date.
        within30 = (None if '803' in str(r.form) or fd is None or pd.isna(fd) or pd.isna(r.date)
                    else bool((pd.Timestamp(fd) - pd.Timestamp(r.date)).days <= 30))
        beh_rows.append(dict(flow=f, official=off, payor=frm, payee=to, date=d10(r.date), amount=r.amount, purpose=r.purpose, payor_interested_party=ip,
                             interested_basis=basis, filed_within_30_days=within30, form=r.form))

    # --- lobbying
    lm = pd.read_parquet(os.path.join(ER, 'lobby_official_map.parquet'))
    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    lc = lc[(lc.date.dt.year >= Y0) & (lc.date.dt.year <= Y1)].copy()
    lc['nk'] = lc.officialname.map(m6.nk_from_lastfirst)
    lc = lc.merge(lm[['nk', 'departmentname', 'official_id', 'category']], on=['nk', 'departmentname'], how='left')
    lc['lnode'] = 'L:' + lc.lobbyistname.map(m6.nk_from_lastfirst)
    lc['client_node'] = [R(x)[0] for x in lc.clientname]
    lc['dcode'] = lc.departmentname.map(lobby_dept_code)
    lc['month'] = lc.date.dt.strftime('%Y-%m')
    lc['topic'] = lc.subjectarea.fillna('Unspecified')

    def target(r):
        if isinstance(r.official_id, str) and r.official_id.startswith('O:'):
            # red-team pass 2: a contact with someone who later ran for this office, dated in a year they did not hold it
            # (e.g. as a legislative aide), is a contact with department staff and is shown at the department level
            off_ = m6.dept_office(r.departmentname)
            # the Board of Supervisors and the Mayor's Office: only the supervisors and the Mayor are named; aides and advisers are staff
            if off_ and (r.category == 'elected' or off_ in ('Board of Supervisors', 'Mayor')) and r.date.year not in HELD.get((r.official_id, off_), set()):
                return dept_entity(r.dcode) if r.dcode else None
            return official_entity(r.official_id)
        return dept_entity(r.dcode) if r.dcode else None
    lc['to'] = [target(r) for r in lc.itertuples()]
    lc['from'] = [lobbyist_entity(l, f) for l, f in zip(lc.lnode, lc.firmname)]
    lc['client'] = lc.client_node.map(org_entity)
    lob_rows = []
    lc['year'] = lc.date.dt.year
    lcv = lc.dropna(subset=['from', 'to']).copy()
    lcv['client'] = lcv.client.fillna('')
    for (frm, to, cl, topic, yr), g in lcv.groupby(['from', 'to', 'client', 'topic', 'year']):
        f = F(frm, to, 'lobby_contact', g.date.min().strftime('%Y-%m-%d'), None, count=len(g), client=cl or None,
              topic=topic, aggregated=len(g) > 1, period='year', ref={'form': 'Lobbyist monthly disclosure', 'id': None, 'url': None})
        for mth, gm in g.groupby('month'):
            lob_rows.append(dict(flow=f, lobbyist=frm, client=cl or None, target=to, month=mth, topic=topic, contacts=len(gm)))
    lp = pd.read_parquet(os.path.join(INT, 'lobby_payments.parquet'))
    lp = lp[(lp.date.dt.year >= Y0) & (lp.date.dt.year <= Y1)].copy()
    lp['lnode'] = 'L:' + lp.lobbyistname.map(m6.nk_from_lastfirst)
    lp['from'] = [org_entity(R(x)[0]) for x in lp.clientname]
    lp['to'] = [lobbyist_entity(l, f) for l, f in zip(lp.lnode, lp.firmname)]
    lp['year'] = lp.date.dt.year
    for (frm, to, yr), g in lp.dropna(subset=['from', 'to']).groupby(['from', 'to', 'year']):
        if g.amount.sum() == 0:
            continue
        F(frm, to, 'lobby_payment', g.date.min().strftime('%Y-%m-%d'), g.amount.sum(), count=len(g), aggregated=len(g) > 1, period='year',
          ref={'form': 'Lobbyist monthly disclosure', 'id': None, 'url': None})
    for e_ in list(E.values()):
        if e_['type'] == 'lobbyist':
            ln = 'L:' + e_['id'][4:].replace('-', '|').replace('_', ' ').upper()
            if ln in ldm.index:
                r = ldm.loc[ln]; r = r.iloc[0] if isinstance(r, pd.DataFrame) else r
                e_['lobbyist_type'] = r.lobbyisttype
                e_['registered_since'] = int(str(r.initialregistrationdate)[:4]) if isinstance(r.initialregistrationdate, str) else None
                e_['firm'] = r.firmname

    # --- contracts: Controller supplier contracts (primes, FY2018+) matched to 126f4 approvals where possible
    s = pd.read_parquet(os.path.join(INT, 'contracts.parquet'))
    s = s[s.project_team_constituent.isin(['Prime Contractor', 'Joint Venture Constituent'])]
    s['node'] = [R(x)[0] for x in s.project_team_supplier]
    s = s[s.term_start.notna() & (s.term_start.dt.year >= Y0) & (s.term_start.dt.year <= Y1)]
    f126 = pd.read_parquet(os.path.join(INT, 'f126.parquet'))
    f126['node'] = [R(x)[0] for x in f126.contractor]
    f126['dcode'] = f126.department.map(lambda x: lobby_dept_code(x) if isinstance(x, str) else None)
    f126['approving_body'] = [m8.approver_node(o, of) for o, of in zip(f126.officer, f126.office)]
    f126 = f126[f126.date_signed.notna()]
    by_node = {k: g for k, g in f126.groupby('node')}
    contract_flow_by_filing = {}
    used_f = set()
    for r in s.itertuples():
        to = org_entity(r.node) if r.node else None
        if to in (None, 'ind-all'):
            continue
        body, fk = None, None
        g = by_node.get(r.node)
        if g is not None:
            gg = g[((g.date_signed - r.term_start).dt.days.abs() <= 180) & ((g.dcode == r.department_code) | g.dcode.isna())]
            gg = gg[~gg.filing_key.isin(used_f)]
            if len(gg):
                x = gg.iloc[0]; body = str(x.approving_body or '').replace('BODY:', ''); fk = x.filing_key; used_f.add(fk)
        if not fk and not (r.agreed_amt and r.agreed_amt >= 100000):
            continue
        f = F(dept_entity(r.department_code), to, 'contract', d10(r.term_start), r.agreed_amt, approving_body=body,
              ref={'form': 'Controller Supplier Contracts' + (' + SFEC-126(f)4' if fk else ''), 'id': r.contract_no, 'url': None}, sfec126_filing=fk)
        if fk:
            contract_flow_by_filing[fk] = f
    # 126f4 filings not matched to a Controller contract become their own contract flows
    for r in f126.itertuples():
        if r.filing_key in contract_flow_by_filing or not inyears(r.date_signed):
            continue
        to = org_entity(r.node) if r.node else None
        if to in (None, 'ind-all'):
            continue
        frm = dept_entity(r.dcode) if r.dcode else dept_entity({'BODY:Board of Supervisors': 'BOS', 'BODY:Mayor': 'MYR', 'BODY:Retirement Board': 'RET'}.get(r.approving_body, 'GEN'))
        f = F(frm, to, 'contract', d10(r.date_signed), r.contract_amount, approving_body=str(r.approving_body or '').replace('BODY:', ''),
              ref={'form': 'SFEC-126(f)4', 'id': r.filing_key if not str(r.filing_key).startswith('legacy:') else None,
                   'url': r.filing_key[7:] if str(r.filing_key).startswith('legacy:') else (r.filing if isinstance(r.filing, str) else None)}, sfec126_filing=r.filing_key)
        contract_flow_by_filing[r.filing_key] = f
    # --- payments (vendor payments by fiscal year) for network entities only
    vpe = vp.copy()
    vpe['to'] = vpe.target.map(lambda n: node2ent.get(n) if n in node2ent else (org_entity(n) if (n in ctr_nodes or n in np_nodes) else None))
    vpe = vpe[vpe.to.notna() & (vpe.to != 'ind-all')]
    vpe = vpe[(vpe.date.dt.year >= Y0 - 1) & (vpe.date.dt.year <= Y1)]
    linked = set(f['from'] for f in flows if f['type'] in ('contribution', 'behested', 'lobby_payment')) | set(f['to'] for f in flows if f['type'] == 'behested') \
        | set(f.get('client') for f in flows if f['type'] == 'lobby_contact') | {E[k]['affiliated_with'] for k in E if E[k]['type'] == 'individuals' and E[k].get('affiliated_with')}
    tot = vpe.groupby('to').amount.sum()
    vpe = vpe[vpe.to.isin(linked)]
    for r in vpe.itertuples():
        a = json.loads(r.attrs)
        F(dept_entity(r.source[2:]), r.to, 'payment', d10(r.date), r.amount, aggregated=True, period=f"FY{a.get('fiscal_year')}",
          ref={'form': 'Vendor Payments (Vouchers)', 'id': None, 'url': None})
    print('total flows', len(flows))

    # ------------------------------------------------------------------ ban window analysis
    cases_all = pd.read_parquet(os.path.join(AN, 'contractor_affiliated_contributions.parquet'))
    cases_all = cases_all[(cases_all.date.dt.year >= Y0) & (cases_all.date.dt.year <= Y1) & (cases_all.amount > 0)]
    fl_by_elem = contrib_flow
    ban_contracts = []
    filing_meta = f126.set_index('filing_key')
    windows = {}
    for fk, fl in contract_flow_by_filing.items():
        if fl is None or fk not in filing_meta.index:
            continue
        x = filing_meta.loc[fk]; x = x.iloc[0] if isinstance(x, pd.DataFrame) else x
        D = x.date_signed
        wd = 365 if D >= pd.Timestamp('2019-01-01') else 182
        start = D - pd.Timedelta(days=180)   # proposal date unknown; 180 days before approval shown as the likely pending period
        end = D + pd.Timedelta(days=wd)
        windows[fk] = (start, D, end)
        ban_contracts.append(dict(contract=fl, contractor=org_entity(x.node), dept=dept_entity(x.dcode) if x.dcode else None, approval_date=d10(D),
                                  amount=x.contract_amount, window=[d10(start), d10(end)], window_post_approval=[d10(D + pd.Timedelta(days=1)), d10(end)],
                                  approving_body=str(x.approving_body or '').replace('BODY:', ''), contributions=[]))
    bc_by = {b['contract']: b for b in ban_contracts}
    records = []
    REVIEW_MIN_CONF = 0.85
    cases = pd.read_parquet(os.path.join(AN, 'contractor_ban_cases.parquet'))
    refund = {(a, b): bool(c_) for a, b, c_ in zip(cases.record_id, cases.contributor_node, cases.possible_refund_seen)}
    ca = cases_all.copy()
    ca['d'] = (ca.date - ca.D).dt.days
    # one record per affiliated contribution (entity or listed principal) to any city committee, nearest approval
    ca['absd'] = ca.d.abs()
    ca['ins'] = (ca.d > 0) & (ca.d <= ca.window_days)
    ca['prio'] = np.where(ca.ins & ca.covered_status.notna() & ~ca.self_contribution & ~ca.public_entity, 0, np.where(ca.ins & ca.covered_status.notna(), 1, np.where(ca.ins, 2, 3)))
    ca = ca.sort_values(['record_id', 'contributor_node', 'prio', 'absd']).drop_duplicates(['record_id', 'contributor_node'])
    for r in ca.itertuples():
        if r.contributor_type == 'listed principal':
            fl = fl_by_elem.get(r.record_id)
        else:
            fl = None
        if fl is None:
            continue
        cf_ = contract_flow_by_filing.get(r.filing_key)
        inside = bool(0 < r.d <= r.window_days)
        bc = bc_by.get(cf_)
        if inside and bc is not None and not (bc['window_post_approval'][0] <= d10(r.date) <= bc['window_post_approval'][1]):
            inside = False   # duplicate filing rows with different dates: keep the export internally consistent
        covered = isinstance(r.covered_status, str)
        selfc = bool(getattr(r, 'self_contribution', False))
        pub = bool(getattr(r, 'public_entity', False))
        if float(r.match_conf) < REVIEW_MIN_CONF:
            continue   # red-team pass 2: bare name matches (confidence 0.80) are not put beside a named official; counted in redteam2.json
        review = 'appears_to_warrant_review' if (inside and covered and not selfc and not pub) else ('inside_window_not_covered' if inside else 'outside_window')
        why = None
        if inside and covered and pub:
            why = ('Inside the window for a covered official, but the contracting party is a public entity (e.g., UC/UCSF, SFUSD, Housing Authority); '
                   'whether §1.126 reaches board members of public bodies or their foundations is unclear, so this is not flagged.')
        elif inside and covered and selfc:
            why = 'The contributor is the candidate (a listed board member giving to their own committee); not flagged.'
        elif inside and not covered:
            why = 'Inside a post-approval window, but the recipient was not holding or seeking an approving office at the time.'
        if review == 'appears_to_warrant_review':
            why = (f"Dated {r.d} days after the approval-date proxy for a contract approved by {r.offices}; the recipient committee was covered at the time "
                   f"({r.covered_status}); the donor was name-matched (confidence {r.match_conf:.2f}) to a {r.role} listed on the SFEC-126(f)4 filing. "
                   "Attribution may be wrong (same-name individuals), the contribution may have been returned, the contract may fall outside §1.126 "
                   "(e.g., value or approval route), and the Ethics Commission may already have reviewed it. Not a finding of a violation.")
            if refund.get((r.record_id, r.contributor_node)):
                why += ' The committee later reported a negative entry for the same donor within 12 months, which may be a refund.'
            if r.amount <= 500:
                why += (' Context: the amount is within the $500 per-election limit (§1.114(a)); the contractor ban applies regardless of amount, '
                        'and a pattern like this is worth checking, not proof.')
        if org_entity(r.contractor_entity) in (None, 'ind-all'):
            continue
        rec = dict(flow=fl, contractor=org_entity(r.contractor_entity), committee=committee_entity(r.recipient), date=d10(r.date), amount=r.amount, count=1,
                   nearest_contract=cf_, days_from_approval=int(r.d), inside_window=inside, window_contract=cf_ if inside else None,
                   covered_official=covered, covered_basis=r.covered_status if covered else None, review=review, why=why,
                   match_confidence=float(r.match_conf), possible_refund_seen=(refund.get((r.record_id, r.contributor_node)) if inside and covered else None))
        records.append(rec)
        if inside and cf_ in bc_by:
            bc_by[cf_]['contributions'].append(fl)
        if review == 'appears_to_warrant_review':
            for f in flows:
                pass
    # flags on flows (index by id)
    fidx = {f['id']: f for f in flows}
    for rec in records:
        if rec['review'] == 'appears_to_warrant_review':
            fidx[rec['flow']]['flags'] = {'in_ban_window': True, 'ban_contract': rec['window_contract']}
    cases = pd.read_parquet(os.path.join(AN, 'contractor_ban_cases.parquet'))
    refund = {(a, b): c_ for a, b, c_ in zip(cases.record_id, cases.contributor_node, cases.possible_refund_seen)}
    br = json.load(open(os.path.join(AN, 'contractor_base_rates.json')))
    n_inside = sum(1 for r in records if r['inside_window'])
    n_cov = sum(1 for r in records if r['review'] == 'appears_to_warrant_review')
    ban = dict(sample=False, as_of=AS_OF, sources=['sfec-460', 'sfec-126f'], rule='ban',
               base_rates=dict(contributions_by_contractor_affiliated=len(records), inside_any_window=n_inside, inside_window_covered_official=n_cov,
                               expected_share_if_unrelated=round(br['expected_share_if_unrelated'], 3),
                               observed_share_inside_window_2019_2025=round(br['observed_share_inside_window_2019_2025'], 3),
                               expected_note=('For each contractor, the share of days from 2019-01-01 to 2025-12-31 covered by the union of its post-approval '
                                              'windows (12 months after each approval-date proxy; 6 months for approvals before 2019), weighted by that '
                                              "contractor's number of affiliated contribution records. If timing were unrelated to contracts, about this share "
                                              'of records would land inside a window by chance.'),
                               placebo=br['timing_placebo'],
                               # red-team pass 2: the contract's expected share pools every window of the contractor. The matched figure uses,
                               # for each record, only the approvals that list that donor and whose approving office covered the recipient,
                               # with days weighted by the election calendar. Compare it with observed_share_matched (same records).
                               expected_share_matched=round(br['redteam2']['excluding_public_entities']['expected_office_matched_calendar_weighted'], 3),
                               observed_share_matched=round(br['redteam2']['excluding_public_entities']['observed'], 3),
                               matched_n_records=br['redteam2']['excluding_public_entities']['n_records'],
                               matched_difference_95ci=[round(x, 3) for x in br['redteam2']['bootstrap_95ci']['difference']],
                               matched_note=('Same 2019-2025 records as the observed share, restricted to recipients covered for the approval (the only case the ban '
                                             'reaches), excluding public-entity contractors. Expected = average, over records, of the share of 2019-2025 days inside '
                                             'the post-approval windows of the approvals that list the donor and whose approving office covered the recipient, '
                                             'weighted by the monthly volume of all individual contributions to City candidates (the election calendar). '
                                             'The contract-defined expected_share_if_unrelated pools all of a contractor\'s windows and overstates chance.'),
                               placebo_4y=br['redteam2']['placebo_4y'],
                               share_126f4_contractors_with_principal_giving_ever=round(br['share_126f4_contractors_with_matched_principal_giving_to_city_candidates_ever'], 3),
                               share_126f4_contractors_with_employee_giving_ever=round(br['share_126f4_contractors_with_employee_giving_to_city_candidates_ever'], 3)),
               scope_note=('Records cover contributions by disclosed principals (board members, officers, 10%+ owners on SFEC-126(f)4 filings) name-matched to '
                           'donors with confidence >= 0.85 (bare name matches at 0.80 are left out so that no named official is listed beside a weak '
                           'attribution), to candidate/officeholder and controlled committees, 2015-2026. Contributions by the contracting '
                           'entity itself are rare (corporations cannot give to candidates) and are listed in ANALYSIS.md. Employees are not covered persons '
                           'and are not included here.'),
               contracts=[b for b in ban_contracts if b['contributions']] + [b for b in ban_contracts if not b['contributions']][:0],
               records=records)
    # keep contracts referenced by records (nearest or window) so the file stays small
    ref_contracts = {r['nearest_contract'] for r in records} | {r['window_contract'] for r in records}
    ban['contracts'] = [b for b in ban_contracts if b['contract'] in ref_contracts]

    # ------------------------------------------------------------------ concentration per committee per cycle
    fl_df = pd.DataFrame([f for f in flows if f['type'] == 'contribution'])
    fl_df['etype'] = fl_df['from'].map(lambda x: E[x]['type'] if x in E else None)
    fl_df['year'] = fl_df.date.str[:4].astype(int)
    fl_df['cycle'] = fl_df.year.map(lambda y: str(y if y % 2 == 0 else y + 1))
    conc = []
    comE = {k: v for k, v in E.items() if v['type'] == 'committee'}
    for (cm, cyc), g in fl_df[fl_df.to.isin(comE.keys())].groupby(['to', 'cycle']):
        if comE[cm].get('committee_kind') != 'candidate':
            continue
        by = {}
        for t, gg in g.groupby(g['from'].map(lambda x: 'individuals' if x == 'ind-all' else ('contractor_affiliated' if str(x).startswith('ind-') else E[x]['type']))):
            by[t] = int(round(gg.amount.sum()))
        named = g[~g['from'].str.startswith('ind-')].groupby('from').amount.sum().sort_values(ascending=False)
        conc.append(dict(committee=cm, official=comE[cm].get('official'), cycle=cyc, total=int(round(g.amount.sum())), n_contributions=int(g['count'].sum()),
                         by_source_type=by, top10_share_named=round(float(named.head(10).sum() / named.sum()), 3) if named.sum() > 0 else None,
                         n_named_sources=int(len(named))))
    # ------------------------------------------------------------------ nonprofit loop
    loopdf = pd.read_parquet(os.path.join(AN, 'nonprofit_loop.parquet'))
    fy_latest = int(vp.date.dt.year.max()) + 1
    vp_latest = vp[vp.date.dt.year == fy_latest - 1].groupby('target').amount.sum()
    loop_rows = []
    depts_fund = vp.groupby('target').source.agg(lambda s: sorted(set(x[2:] for x in s)))
    lcd = lc.dropna(subset=['client_node']).groupby('client_node').dcode.agg(lambda s: sorted(set(x for x in s if x)))
    beh_made = bedges.groupby('source').amount.sum()
    beh_recv = bedges.groupby('target').amount.sum()
    lpay = edges[edges.edge_type == 'lobbying_payment'].groupby('source').amount.sum()
    lcon = edges[edges.edge_type == 'lobbying_contact'].groupby('source').size()
    for n in np_nodes:
        br_, bm_, lp_, lc_ = beh_recv.get(n, 0), beh_made.get(n, 0), lpay.get(n, 0), lcon.get(n, 0)
        if not (br_ or bm_ or lp_ or lc_):
            continue
        e_ = org_entity(n)
        if e_ == 'ind-all':
            continue
        loop_rows.append({'entity': e_, 'org': npmod.get(n), f'city_paid_fy{fy_latest}': int(vp_latest.get(n, 0)), 'behested_received': int(br_),
                          'behested_made': int(bm_), 'lobby_payments': int(lp_), 'lobby_contacts': int(lc_),
                          'depts_funding': [f'dept-{d}' for d in depts_fund.get(n, [])], 'depts_lobbied': [f'dept-{d}' for d in lcd.get(n, [])]})
    # ------------------------------------------------------------------ write
    ents_out = list(E.values())
    ind_total = sum(e_['count'] for e_ in ents_out if e_['type'] == 'individuals')
    files = {}
    # flows split by year (production) + combined file
    fl_all = sorted(flows, key=lambda f: f['date'])
    years = sorted(set(f['date'][:4] for f in fl_all))
    for y in years:
        files[f'network/flows/flows_{y}.json'] = {'bytes': W(f'flows/flows_{y}.json', dict(sample=False, as_of=AS_OF, year=int(y), flows=[f for f in fl_all if f['date'][:4] == y]))}
    files['network/flows.json'] = {'bytes': W('flows.json', dict(sample=False, as_of=AS_OF, sources=['sfec-460', 'sfec-126f', 'sfec-3610', 'fppc-803', 'sfec-lobby', 'cqi5-hm2d', 'n9pm-xkyq'],
                                                                 note='One row per (from, to, type, date/period) after aggregating individuals; also split by year in flows/flows_<year>.json.',
                                                                 flows=fl_all))}
    files['network/entities.json'] = {'bytes': W('entities.json', dict(sample=False, as_of=AS_OF, sources=['sfec-460', 'sfec-126f', 'sfec-3610', 'sfec-lobby', 'cqi5-hm2d'], entities=ents_out))}
    files['network/analyses/ban_window.json'] = {'bytes': W('analyses/ban_window.json', ban)}
    files['network/analyses/behested.json'] = {'bytes': W('analyses/behested.json', dict(sample=False, as_of=AS_OF, sources=['fppc-803', 'sfec-3610'], rule='behested',
        note=('FPPC 803 filings Apr 2015-Mar 2018 and SFEC 3610(b) filings 2019-2023 (the DataSF 3610(b) datasets are marked [Historical]). Form 803 filings after March 2018 '
              'are PDF-only on the Ethics Commission NetFile portal and are not included. 49 rows from the 2021 DCYF Summer Together filing, which list recipient agencies in '
              'the payor field, are excluded. payor_interested_party is a check against public lobbying and contract data within 12 months, not a finding.'), rows=beh_rows))}
    topics = sorted(set(r['topic'] for r in lob_rows))
    files['network/analyses/lobbying.json'] = {'bytes': W('analyses/lobbying.json', dict(sample=False, as_of=AS_OF, sources=['sfec-lobby'], rule='lobby', topics=topics, rows=lob_rows))}
    files['network/analyses/concentration.json'] = {'bytes': W('analyses/concentration.json', dict(sample=False, as_of=AS_OF, sources=['sfec-460'], rule='limits',
        note='Candidate committees only (own committees of candidates for City office), 2015-2026, cycle = even year (odd-year elections folded into the next even year). Self-funding by the candidate is inside `individuals`.', rows=conc))}
    files['network/analyses/loop.json'] = {'bytes': W('analyses/loop.json', dict(sample=False, as_of=AS_OF, sources=['sfec-3610', 'fppc-803', 'sfec-lobby', 'n9pm-xkyq'],
        note=('Nonprofits that receive city money and also appear as behested payors or payees, or as lobbying clients. Appearing here is not improper: nonprofits may lawfully '
              'lobby, and behested payments to charities are legal and disclosed. City payments are for the latest complete fiscal year in the vendor data.'), rows=loop_rows))}
    manifest = json.load(open(os.path.join(RAW, 'manifest.json')))
    rows_of = lambda k: manifest.get(k, {}).get('rows')
    sources = [
        dict(id='sfec-460', name='Campaign Finance - Transactions (Form 460/461/496/497 all schedules)', publisher='SF Ethics Commission via data.sf.gov', rows=rows_of('cf_transactions'),
             rows_used=int(len(c)), as_of=AS_OF, url='https://data.sf.gov/resource/pitq-e56w.json', note='Schedules A and C (receipts) used, 2015-2026 in the site export (1998-2026 in analyses); individuals aggregated; addresses and employers not exported. Committees: 4c8t-ngau.'),
        dict(id='sfec-126f', name='SFEC Form 126f4 contract approval notices (historical filings ite2-5y3b, parties czjm-dat8; 2026+ mczm-4vxi) and 126f2 proposals (pv99-gzft, djj2-gvaq)',
             publisher='SF Ethics Commission via data.sf.gov', rows=(rows_of('f126f4_filings_hist') or 0) + (rows_of('f126_combined') or 0), rows_used=int(len(f126)), as_of=AS_OF,
             url='https://data.sf.gov/resource/ite2-5y3b.json', note='Approval-date proxy = date the elected officer signed the notice (due within 5 business days of approval).'),
        dict(id='sfec-3610', name='SFEC Form 3610(b) behested payments, payors joined with cover (b3ya-imj5)', publisher='SF Ethics Commission via data.sf.gov', rows=rows_of('bp_3610b_payors_joined'),
             rows_used=sum(1 for r in beh_rows if '3610' in str(r['form'])), as_of=AS_OF, url='https://data.sf.gov/resource/b3ya-imj5.json', note='Dataset marked [Historical]; last rows 2023.'),
        dict(id='fppc-803', name='FPPC Form 803 behested payment reports filed with SFEC, Apr 2015-Mar 2018 (98wa-4d49)', publisher='SF Ethics Commission via data.sf.gov', rows=rows_of('bp_803_2015_2018'),
             rows_used=sum(1 for r in beh_rows if '803' in str(r['form'])), as_of=AS_OF, url='https://data.sf.gov/resource/98wa-4d49.json', note='Later 803 filings are PDF-only (not included).'),
        dict(id='sfec-lobby', name='Lobbyist Activity Directory (contacts, payments, contributions) (s4ub-8j3t) and Lobbyist Directory (b947-pj2q)', publisher='SF Ethics Commission via data.sf.gov',
             rows=rows_of('lob_activity'), rows_used=int(len(lc) + len(lp)), as_of=AS_OF, url='https://data.sf.gov/resource/s4ub-8j3t.json', note='Contacts with staff below executive level are shown at the department level.'),
        dict(id='cqi5-hm2d', name='Supplier Contracts', publisher='SF Controller via data.sf.gov', rows=rows_of('supplier_contracts'), rows_used=int(len(s)), as_of=AS_OF,
             url='https://data.sf.gov/resource/cqi5-hm2d.json', note='Prime contractors and JV constituents; term start 2015-2026.'),
        dict(id='n9pm-xkyq', name='Vendor Payments (Vouchers)', publisher='SF Controller via data.sf.gov', rows=8171891, rows_used=int(len(vpe)), as_of=AS_OF,
             url='https://data.sf.gov/resource/n9pm-xkyq.json', note='Aggregated server-side by fiscal year x department x vendor; exported only for contractors and nonprofits in the network.'),
    ]
    rules = json.load(open(os.path.join(HERE, 'rules_network.json')))
    ETYPES = [('committee', 'Candidate or officeholder committee', 7), ('contractor', 'City contractor', 2), ('nonprofit', 'Nonprofit with city funding', 1),
              ('lobbyist', 'Registered lobbyist', 3), ('donor_org', 'Other organization or PAC', 4), ('individuals', 'Individuals (aggregated)', 0),
              ('department', 'City department', 0), ('official', 'Official or candidate (public role)', 7)]
    FLOWS = [('contribution', 'Campaign contribution', 'Form 460 Schedules A and C', 'Contributions'), ('behested', 'Behested payment', 'FPPC Form 803 / SFEC-3610(b) (2019-2022)', 'Behested'),
             ('lobby_contact', 'Lobbying contact', 'Lobbyist monthly disclosure', 'Lobby contacts'), ('lobby_payment', 'Payment to lobbyist', 'Lobbyist monthly disclosure', 'Lobby payments'),
             ('contract', 'Contract', 'Supplier Contracts / SFEC-126(f)4', 'Contracts'), ('payment', 'City payment', 'Vendor Payments', 'City payments')]
    meta = dict(sample=False, module='network', as_of=AS_OF, generated_at=GENERATED, version='1.0',
                years=dict(min=Y0, max=Y1, note='Calendar years by transaction date (vendor payments: fiscal-year start). 2026 is partial (through September).'),
                dimensions=dict(etype=dict(label='Entity type', kind='categorical', values=[dict(id=a, label=l, slot=s_) for a, l, s_ in ETYPES]),
                                flow=dict(label='Flow type', values=[dict(id=a, label=l, form=f_, short=sh) for a, l, f_, sh in FLOWS]),
                                amount_bands=[dict(id=0, label='Any amount'), dict(id=1000, label='≥ $1,000'), dict(id=10000, label='≥ $10,000'), dict(id=100000, label='≥ $100,000')]),
                rules=rules,
                fairness=dict(individuals=('Private individuals appear only in aggregates (never named; addresses, ZIP codes and employer text are not exported). Named entities are '
                                           'organizations, officials in their public roles, registered lobbyists, committees and departments. Contractor principals are counted, not named.'),
                              timing='A donation near a contract or approval is a pattern worth checking, never proof of improper influence.',
                              review=("'Appears to warrant review' is shown only when a contribution appears to fall inside the §1.126 window for a covered official and the donor's "
                                      'match to a listed principal is corroborated beyond the name (confidence 0.85 or higher); name matching can still be wrong, '
                                      'the contribution may have been returned, and the Ethics Commission may already have reviewed it. It is never a finding of a violation.')),
                counts=dict(entities=len(ents_out), flows=len(fl_all), contracts_with_126f=len(contract_flow_by_filing), behested_payments=len(beh_rows),
                            lobby_contact_rows=len(lob_rows), individuals_aggregated=int(ind_total)),
                small_n=5, sources=sources, files={})
    fp = os.path.join(SITE, 'meta.json')
    meta['files'] = files
    files['network/meta.json'] = {'bytes': W('meta.json', meta)}
    meta['files'] = files
    W('meta.json', meta)
    json.dump({'ban_contracts': len(ban['contracts']), 'ban_records': len(ban['records']), 'review': n_cov}, open(os.path.join(SITE, '_export_stats.json'), 'w'))
    print({k: v['bytes'] for k, v in files.items() if 'flows_' not in k})
    print('entities', len(ents_out), 'flows', len(fl_all), 'ban records', len(records), 'review', n_cov)


if __name__ == '__main__':
    main()
