"""Build the money/contact network from normalized tables + entity resolution.

Outputs (data/network/):
  nodes.parquet  node_id, node_type, label, subtype, nameable, extra
  edges.parquet  edge_type, source, target, date, amount, official, attrs(json), dataset, record_id, match_conf

Node types: org (resolved organization), committee, official, staff_group (aggregated city staff by department),
            principal (disclosed contractor principal; nameable), lobbyist (registered; nameable), department.
Private individual donors are NOT nodes. Their giving appears only as aggregated 'employee_giving' edges from their
employer organization to a committee (count of donors, total), and in aggregate statistics.

Edge types:
  contribution        org|principal|lobbyist -> committee     (Form 460 A/C)
  employee_giving     org -> committee (aggregated private individuals who named org as employer; NOT the org's money)
  controls            official -> committee
  sponsors            org -> committee (committee name says "sponsored by")
  independent_expenditure  committee -> official (support/oppose)
  behested_payment    payor org -> recipient org, official = requesting official
  lobbying_contact    client org -> official | staff_group   (attrs: lobbyist, subject, issue, file number, outcome sought)
  lobbying_payment    client org -> lobbyist
  contract            department -> org (Controller supplier contracts; amount = agreed amount; date = term start)
  vendor_payment      department -> org (sum by fiscal year; date = FY start)
  contract_approval   official|approving body -> org (SFEC 126f4; date = approval/signature date)
  principal_of        principal -> org
"""
import os, re, json, hashlib, importlib.util
import numpy as np
import pandas as pd
from names import basic, canon_first, is_non_employer

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.join(HERE, '..', 'data', 'interim')
ER = os.path.join(HERE, '..', 'data', 'er')
NET = os.path.join(HERE, '..', 'data', 'network')
os.makedirs(NET, exist_ok=True)

spec = importlib.util.spec_from_file_location('m3', os.path.join(HERE, '03_mentions.py'))
m3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m3)
spec = importlib.util.spec_from_file_location('m6', os.path.join(HERE, '06_officials.py'))
m6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m6)

PERSON_T = 0.8   # min confidence for person matches used in the network (sensitivity handled in analysis)


class OrgResolver:
    def __init__(self, variant='default'):
        em = pd.read_parquet(os.path.join(ER, 'org_entity_map.parquet'))
        self.ent = dict(zip(em.key, em[f'entity_{variant}']))
        self.conf = dict(zip(em.key, em.match_conf))
        self.cache = {}

    def key(self, raw):
        if not isinstance(raw, str) or not raw.strip():
            return ''
        r = raw.strip()
        if r not in self.cache:
            self.cache[r] = m3.key2(r)
        return self.cache[r]

    def __call__(self, raw):
        k = self.key(raw)
        return self.ent.get(k), self.conf.get(k, 1.0 if k else None)


def dept_id(code, name):
    if isinstance(code, str) and code.strip():
        return 'D:' + code.strip()
    return 'D:' + basic(name)[:40]


def build(variant='default', person_t=PERSON_T, out_suffix=''):
    R = OrgResolver(variant)
    ents = pd.read_parquet(os.path.join(ER, 'org_entities.parquet'))
    com = pd.read_parquet(os.path.join(INT, 'committees.parquet'))
    offs = pd.read_parquet(os.path.join(ER, 'officials.parquet'))
    edges = []

    def E(df):
        edges.append(df)

    # ---------------- committees and control
    com['node_id'] = 'C:' + com.filer_nid.astype(str)
    com['cand_nk'] = com.candidate_name.map(m6.nk_from_lastfirst)
    own = com[(com.kind == 'candidate') & (com.cand_nk != '')]
    ctl = pd.DataFrame({'edge_type': 'controls', 'source': 'O:' + own.cand_nk, 'target': own.node_id, 'dataset': '4c8t-ngau',
                        'record_id': own.filer_nid.astype(str), 'match_conf': 1.0, 'attrs': '{"basis":"candidate committee"}'})
    # ballot-measure / general-purpose / legal-defense committees whose name contains an official's full name
    cands = offs[offs.category == 'candidate_or_elected'][['nk', 'display']].copy()
    cands['last'] = cands.nk.str.split('|').str[0]; cands['first'] = cands.nk.str.split('|').str[1]
    rows = []
    other = com[com.kind.isin(['ballot_measure', 'general_purpose'])]
    bylast = {}
    for r in cands.itertuples():
        if len(r.last) >= 3:
            bylast.setdefault(r.last, []).append(r)
    for c in other.itertuples():
        n = basic(c.filer_name)
        toks = set(n.split())
        if 'RECALL' in toks and not re.search(r'\bNO RECALL|AGAINST (THE )?RECALL|STOP (THE )?(WASTEFUL )?RECALL|NO ON', n):
            continue
        if re.search(r'SPONSORED BY|OPPOS|\bCLUB\b', n):
            continue
        for last, lst in bylast.items():
            if last in toks or (' ' in last and last in n):
                for r in lst:
                    fn = r.first
                    if fn and (fn in toks or canon_first(fn) in {canon_first(t) for t in toks}):
                        rows.append(dict(edge_type='controls', source='O:' + r.nk, target=c.node_id, dataset='4c8t-ngau',
                                         record_id=str(c.filer_nid), match_conf=0.8, attrs=json.dumps({'basis': 'committee name contains official name', 'committee': c.filer_name})))
    ctl2 = pd.DataFrame(rows)
    E(ctl); E(ctl2)
    print('controls edges', len(ctl), 'name-based', len(ctl2))
    # sponsors
    sp = com[com.controlled_by_text.notna()]
    sres = [R(x) for x in sp.controlled_by_text]
    spd = pd.DataFrame({'edge_type': 'sponsors', 'source': [s[0] for s in sres], 'target': sp.node_id.values, 'dataset': '4c8t-ngau',
                        'record_id': sp.filer_nid.astype(str).values, 'match_conf': [s[1] for s in sres], 'attrs': '{}'})
    E(spd.dropna(subset=['source']))

    # ---------------- contributions
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'))
    c['target'] = 'C:' + c.filer_nid.astype(str)
    org = c[~c.is_individual].copy()
    res = [R(x) for x in org.donor_last]
    org['source'] = [r[0] for r in res]; org['match_conf'] = [r[1] for r in res]
    org = org.dropna(subset=['source'])
    E(pd.DataFrame({'edge_type': 'contribution', 'source': org.source, 'target': org.target, 'date': org.date, 'amount': org.amount,
                    'dataset': 'pitq-e56w', 'record_id': org.element_nid, 'match_conf': org.match_conf,
                    'attrs': np.where(org.is_committee_donor, '{"donor_kind":"committee"}', '{"donor_kind":"organization"}')}))
    ind = c[c.is_individual].copy()
    de = pd.read_parquet(os.path.join(ER, 'donor_elements.parquet'))
    ind = ind.merge(de[['element_nid', 'pid']], on='element_nid', how='left')
    pm = pd.read_parquet(os.path.join(ER, 'person_matches.parquet'))
    good = pm[(pm.decision == 'same') & (pm.confidence >= person_t)]
    # principals: person node per name key; lobbyists: L:nk
    good = good.assign(person_node=np.where(good.kind == 'principal', 'PP:' + good.nk, 'L:' + good.nk))
    pid2node = good.sort_values('kind').drop_duplicates('pid').set_index('pid')  # lobbyist first (alphabetical) wins
    ind['person_node'] = ind.pid.map(pid2node.person_node)
    ind['pconf'] = ind.pid.map(pid2node.confidence)
    named = ind[ind.person_node.notna()]
    E(pd.DataFrame({'edge_type': 'contribution', 'source': named.person_node, 'target': named.target, 'date': named.date,
                    'amount': named.amount, 'dataset': 'pitq-e56w', 'record_id': named.element_nid, 'match_conf': named.pconf,
                    'attrs': '{"donor_kind":"named individual (principal or lobbyist)"}'}))
    # employee giving aggregated per (employer entity, committee, year)
    priv = ind[~ind.employer.map(is_non_employer)].copy()
    emp = [R(x) for x in priv.employer]
    priv['emp_ent'] = [e[0] for e in emp]; priv['emp_conf'] = [e[1] for e in emp]
    priv = priv.dropna(subset=['emp_ent'])
    priv['year'] = priv.date.dt.year
    agg = priv.groupby(['emp_ent', 'target', 'year']).agg(amount=('amount', 'sum'), n_donors=('pid', 'nunique'), n=('amount', 'size'),
                                                         date=('date', 'min'), match_conf=('emp_conf', 'min')).reset_index()
    E(pd.DataFrame({'edge_type': 'employee_giving', 'source': agg.emp_ent, 'target': agg.target, 'date': agg.date, 'amount': agg.amount,
                    'dataset': 'pitq-e56w', 'record_id': '', 'match_conf': agg.match_conf,
                    'attrs': [json.dumps({'n_donors': int(a), 'n_contributions': int(b), 'year': int(y)}) for a, b, y in zip(agg.n_donors, agg.n, agg.year)]}))
    ind_all = ind  # keep for stats

    # ---------------- independent expenditures
    ie = pd.read_parquet(os.path.join(INT, 'ie.parquet'))
    ie['nk'] = ie.target_candidate.map(lambda s: m6.nk_from_lastfirst(s) if isinstance(s, str) and s.strip() else '')
    iec = ie[ie.nk != '']
    E(pd.DataFrame({'edge_type': 'independent_expenditure', 'source': 'C:' + iec.filer_nid.astype(str), 'target': 'O:' + iec.nk,
                    'date': iec.date, 'amount': iec.amount, 'dataset': 'pitq-e56w', 'record_id': iec.element_nid, 'match_conf': 0.9,
                    'attrs': [json.dumps({'support_oppose': s}) for s in iec.support_oppose_code]}))

    # ---------------- behested payments
    bp = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    known = set(offs.official_id)
    bp['off'] = bp.official.map(lambda x: resolve_official(x, known))
    pr_ = [R(x) for x in bp.payor]; pe_ = [R(x) for x in bp.payee]
    bp['src'] = [x[0] for x in pr_]; bp['tgt'] = [x[0] for x in pe_]
    bp['mc'] = [min(a[1] or 1, b[1] or 1) for a, b in zip(pr_, pe_)]
    E(pd.DataFrame({'edge_type': 'behested_payment', 'source': bp.src, 'target': bp.tgt, 'date': bp.date, 'amount': bp.amount,
                    'official': bp.off, 'dataset': bp.source.map({'FPPC 803 (2015-2018)': '98wa-4d49', 'SFEC 3610(b) (2019+)': 'b3ya-imj5'}).fillna('ibrg-quig'),
                    'record_id': bp.filing_id.astype(str), 'match_conf': bp.mc,
                    'attrs': [json.dumps({'payor_raw': a, 'payee_raw': b, 'purpose': p if isinstance(p, str) else None, 'form': s})
                              for a, b, p, s in zip(bp.payor, bp.payee, bp.purpose, bp.source)]}))

    # ---------------- lobbying
    lm = pd.read_parquet(os.path.join(ER, 'lobby_official_map.parquet'))
    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    lc['nk'] = lc.officialname.map(m6.nk_from_lastfirst)
    lc = lc.merge(lm[['nk', 'departmentname', 'official_id', 'category']], on=['nk', 'departmentname'], how='left')
    lc['official_id'] = lc.official_id.fillna('STAFF:' + lc.departmentname.fillna('UNKNOWN').map(basic))
    cr = [R(x) for x in lc.clientname]
    lc['src'] = [x[0] for x in cr]; lc['mc'] = [x[1] for x in cr]
    lc['lob'] = 'L:' + lc.lobbyistname.map(m6.nk_from_lastfirst)
    E(pd.DataFrame({'edge_type': 'lobbying_contact', 'source': lc.src, 'target': lc.official_id, 'date': lc.date, 'amount': np.nan,
                    'dataset': 's4ub-8j3t', 'record_id': lc.id, 'match_conf': lc.mc, 'official': lc.official_id,
                    'attrs': [json.dumps({'lobbyist': l, 'subject': s, 'issue': i, 'file_number': f, 'outcome_sought': o, 'department': d})
                              for l, s, i, f, o, d in zip(lc.lob, lc.subjectarea, lc.issue, lc.filenumber, lc.outcomesought, lc.departmentname)]}))
    lp = pd.read_parquet(os.path.join(INT, 'lobby_payments.parquet'))
    pr2 = [R(x) for x in lp.clientname]
    E(pd.DataFrame({'edge_type': 'lobbying_payment', 'source': [x[0] for x in pr2], 'target': 'L:' + lp.lobbyistname.map(m6.nk_from_lastfirst),
                    'date': lp.date, 'amount': lp.amount, 'dataset': 's4ub-8j3t', 'record_id': lp.id, 'match_conf': [x[1] for x in pr2],
                    'attrs': [json.dumps({'firm': f}) for f in lp.firmname]}))

    # ---------------- contracts and payments
    s = pd.read_parquet(os.path.join(INT, 'contracts.parquet'))
    s = s[s.project_team_constituent.isin(['Prime Contractor', 'Joint Venture Constituent'])]
    sr = [R(x) for x in s.project_team_supplier]
    E(pd.DataFrame({'edge_type': 'contract', 'source': [dept_id(c_, n_) for c_, n_ in zip(s.department_code, s.department)],
                    'target': [x[0] for x in sr], 'date': s.term_start, 'amount': s.agreed_amt, 'dataset': 'cqi5-hm2d',
                    'record_id': s.contract_no, 'match_conf': [x[1] for x in sr],
                    'attrs': [json.dumps({'title': t, 'type': ty, 'sole_source': ss, 'paid': p, 'term_end': str(te)[:10], 'nonprofit': npf})
                              for t, ty, ss, p, te, npf in zip(s.contract_title, s.contract_type, s.sole_source_flg, s.pmt_amt, s.term_end, s.non_profit)]}))
    v = pd.read_parquet(os.path.join(INT, 'vendor_pay.parquet'))
    v = v[v.fiscal_year >= 2016]
    vr = {x: R(x) for x in v.vendor.dropna().unique()}
    v['tgt'] = v.vendor.map(lambda x: vr.get(x, (None, None))[0]); v['mc'] = v.vendor.map(lambda x: vr.get(x, (None, None))[1])
    vg = v.groupby(['department_code', 'department', 'tgt', 'fiscal_year']).agg(amount=('paid', 'sum'), mc=('mc', 'min'),
                                                                                  npf=('non_profit_indicator', lambda x: (x == 'X').any())).reset_index()
    E(pd.DataFrame({'edge_type': 'vendor_payment', 'source': [dept_id(a, b) for a, b in zip(vg.department_code, vg.department)],
                    'target': vg.tgt, 'date': pd.to_datetime((vg.fiscal_year - 1).astype(int).astype(str) + '-07-01'),
                    'amount': vg.amount, 'dataset': 'n9pm-xkyq', 'record_id': '', 'match_conf': vg.mc,
                    'attrs': [json.dumps({'fiscal_year': int(fy), 'nonprofit': bool(n)}) for fy, n in zip(vg.fiscal_year, vg.npf)]}))

    # ---------------- 126f4 approvals
    f = pd.read_parquet(os.path.join(INT, 'f126.parquet'))
    fr = [R(x) for x in f.contractor]
    f['tgt'] = [x[0] for x in fr]; f['mc'] = [x[1] for x in fr]
    f['approver'] = [approver_node(o, off) for o, off in zip(f.officer, f.office)]
    E(pd.DataFrame({'edge_type': 'contract_approval', 'source': f.approver, 'target': f.tgt, 'date': f.date_signed,
                    'amount': f.contract_amount, 'dataset': np.where(f.source.str.contains('2026'), 'mczm-4vxi', 'ite2-5y3b'),
                    'record_id': f.filing_key, 'match_conf': f.mc,
                    'attrs': [json.dumps({'officer_text': o, 'office_text': of, 'department': d, 'description': (ds or '')[:200],
                                          'contract_date': str(cd)[:10]}) for o, of, d, ds, cd in zip(f.officer, f.office, f.department, f.description, f.contract_date)]}))
    # principals
    pmp = good[good.kind == 'principal']
    pa = pd.read_parquet(os.path.join(INT, 'f126_parties.parquet'))
    pa = pa[pa.is_person]
    pa['nk'] = pa['last'].map(m6.lastkey) + '|' + pa['first'].map(canon_first)
    prr = {x: R(x) for x in pa.contractor.dropna().unique()}
    pa['tgt'] = pa.contractor.map(lambda x: prr.get(x, (None, None))[0])
    pg = pa.groupby(['nk', 'tgt']).agg(roles=('party_type', lambda x: ', '.join(sorted(set(x.dropna())))), date=('date_signed', 'min')).reset_index()
    pg = pg[pg.nk.isin(set(pmp.nk))]  # only principals who are also (matched) donors become nodes
    E(pd.DataFrame({'edge_type': 'principal_of', 'source': 'PP:' + pg.nk, 'target': pg.tgt, 'date': pg.date, 'amount': np.nan,
                    'dataset': 'czjm-dat8', 'record_id': '', 'match_conf': 1.0, 'attrs': [json.dumps({'roles': r}) for r in pg.roles]}))

    ed = pd.concat(edges, ignore_index=True)
    ed = ed[ed.source.notna() & ed.target.notna()]
    ed['date'] = pd.to_datetime(ed.date, errors='coerce')
    ed['match_conf'] = pd.to_numeric(ed.match_conf, errors='coerce').fillna(1.0)
    for col in ['official', 'attrs', 'record_id', 'dataset']:
        ed[col] = ed[col].astype(object).where(ed[col].notna(), None)

    # ---------------- nodes
    nodes = []
    en = ents.set_index('entity_default') if variant == 'default' else None
    em = pd.read_parquet(os.path.join(ER, 'org_entity_map.parquet'))
    if variant != 'default':
        # label entities of other variants by their heaviest key's default entity name
        top = em.sort_values('n_total', ascending=False).drop_duplicates(f'entity_{variant}')
        lab = dict(zip(top[f'entity_{variant}'], top.entity_default.map(ents.set_index('entity_default').name)))
    org_ids = set(ed.source[ed.source.str.startswith('ORG:')]) | set(ed.target[ed.target.str.startswith('ORG:')])
    for o in org_ids:
        if variant == 'default' and o in en.index:
            r = en.loc[o]
            nodes.append(dict(node_id=o, node_type='org', label=r['name'], subtype=r['type'], nameable=True,
                              extra=json.dumps({'n_name_variants': int(r.n_keys), 'min_match_conf': float(r.min_match_conf), 'family_id': r.family_id})))
        else:
            nodes.append(dict(node_id=o, node_type='org', label=lab.get(o, o) if variant != 'default' else o, subtype='', nameable=True, extra='{}'))
    for r in com.itertuples():
        nodes.append(dict(node_id=r.node_id, node_type='committee', label=r.filer_name, subtype=r.kind, nameable=True,
                          extra=json.dumps({'office': r.office, 'fppc_id': r.fppc_id, 'candidate': r.candidate_name, 'city_candidate': bool(r.is_city_candidate)})))
    for r in offs.itertuples():
        nodes.append(dict(node_id=r.official_id, node_type='official', label=pretty(r.display), subtype=r.category, nameable=True,
                          extra=json.dumps({'offices_sought': r.offices_sought if isinstance(r.offices_sought, str) else None,
                                            'f700_positions': r.f700_positions if isinstance(r.f700_positions, str) else None})))
    staff = lm[lm.category == 'staff'].drop_duplicates('official_id')
    for r in staff.itertuples():
        nodes.append(dict(node_id=r.official_id, node_type='staff_group', label=r.label, subtype='aggregated city staff', nameable=False, extra='{}'))
    lob_nodes = set(ed.source[ed.source.str.startswith('L:')]) | set(ed.target[ed.target.str.startswith('L:')])
    lobnames = pm[pm.kind == 'lobbyist'].drop_duplicates('nk').set_index('nk')
    lcn = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    lcn['nk'] = lcn.lobbyistname.map(m6.nk_from_lastfirst)
    lname = lcn.drop_duplicates('nk').set_index('nk').lobbyistname
    for l in lob_nodes:
        nk = l[2:]
        nodes.append(dict(node_id=l, node_type='lobbyist', label=pretty(lname.get(nk, nk.replace('|', ', '))), subtype='registered lobbyist', nameable=True, extra='{}'))
    pp_nodes = set(ed.source[ed.source.str.startswith('PP:')])
    pname = pa.drop_duplicates('nk').set_index('nk')
    for p in pp_nodes:
        nk = p[3:]
        r = pname.loc[nk] if nk in pname.index else None
        nodes.append(dict(node_id=p, node_type='principal', label=(f"{r['first']} {r['last']}" if r is not None else nk), subtype='disclosed contractor principal',
                          nameable=True, extra='{}'))
    dep = pd.concat([s[['department_code', 'department']], v[['department_code', 'department']]]).drop_duplicates('department_code')
    for r in dep.itertuples():
        nodes.append(dict(node_id=dept_id(r.department_code, r.department), node_type='department', label=r.department, subtype='city department', nameable=True, extra='{}'))
    for a in set(f.approver.dropna()):
        if a.startswith('BODY:'):
            nodes.append(dict(node_id=a, node_type='approving_body', label=a[5:], subtype='approving body (126f4)', nameable=True, extra='{}'))
    nd = pd.DataFrame(nodes).drop_duplicates('node_id')
    # add placeholder nodes for any edge endpoint not yet defined (e.g., officials only seen as IE targets)
    missing = (set(ed.source) | set(ed.target)) - set(nd.node_id)
    add = []
    for m in missing:
        t = m.split(':')[0]
        add.append(dict(node_id=m, node_type={'O': 'official', 'STAFF': 'staff_group', 'D': 'department', 'C': 'committee'}.get(t, 'other'),
                        label=pretty(m.split(':', 1)[1].replace('|', ', ')) if t == 'O' else m.split(':', 1)[1], subtype='referenced only',
                        nameable=t in ('O', 'D', 'C'), extra='{}'))
    nd = pd.concat([nd, pd.DataFrame(add)], ignore_index=True)
    ed.to_parquet(os.path.join(NET, f'edges{out_suffix}.parquet'), index=False)
    nd.to_parquet(os.path.join(NET, f'nodes{out_suffix}.parquet'), index=False)
    print(ed.edge_type.value_counts()); print(nd.node_type.value_counts())
    return nd, ed


def resolve_official(name, known):
    """'First Last' or 'Last, First' -> O:LAST|FIRST; if not a known official, try the swapped order (some 803 rows swap fields)."""
    if not isinstance(name, str) or not name.strip():
        return None
    a = 'O:' + m6.nk_from_lastfirst(name)
    if a in known:
        return a
    parts = name.replace(',', ' ').split()
    if len(parts) >= 2:
        b = 'O:' + m6.lastkey(parts[0]) + '|' + canon_first(parts[-1])
        if b in known:
            return b
    return a


def pretty(s):
    if not isinstance(s, str):
        return s
    if ',' in s:
        last, first = [x.strip() for x in s.split(',', 1)]
        s = f'{first} {last}'
    return ' '.join(w.capitalize() if w.isupper() or w.islower() else w for w in s.split())


APPROVERS = [(r'BOARD OF SUPERVISORS|^BOS$|SUPERVISORS', 'BODY:Board of Supervisors'), (r'\bMAYOR\b', 'BODY:Mayor'),
             (r'CITY ATTORNEY', 'BODY:City Attorney'), (r'DISTRICT ATTORNEY', 'BODY:District Attorney'), (r'SHERIFF', 'BODY:Sheriff'),
             (r'TREASURER', 'BODY:Treasurer'), (r'ASSESSOR', 'BODY:Assessor-Recorder'), (r'PUBLIC DEFENDER', 'BODY:Public Defender'),
             (r'RETIREMENT', 'BODY:Retirement Board'), (r'TRANSPORTATION AUTHORITY', 'BODY:Transportation Authority'),
             (r'EDUCATION|SCHOOL', 'BODY:Board of Education'), (r'COLLEGE', 'BODY:Community College Board')]


def approver_node(officer, office):
    t = basic(f'{officer or ""} {office or ""}')
    # Board of Supervisors approvals (often jointly with the Mayor) -> body node
    if re.search(r'SUPERVISORS', t) and not re.search(r'MEMBER|RETIREMENT|TRANSPORTATION AUTHORITY', t):
        return 'BODY:Board of Supervisors'
    for rx, node in APPROVERS:
        if re.search(rx, t):
            return node
    return 'BODY:' + (office or officer or 'Unknown')[:40] if (office or officer) else None


if __name__ == '__main__':
    import sys
    v = sys.argv[1] if len(sys.argv) > 1 else 'default'
    build(variant=v, out_suffix='' if v == 'default' else f'_{v}')
