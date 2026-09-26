"""Analyses over the resolved network. Writes data/analysis/*.json and *.parquet.

Usage: python3 09_analysis.py [--person-t 0.8] [--variant default] [--tag name]
The --variant/--person-t/--tag options are used by the red-team sensitivity runs (results under data/analysis/<tag>/).

All dollar figures are nominal unless a field says *_real2025 (deflated with US CPI-U, FRED CPIAUCSL annual average).
"""
import os, re, json, argparse, importlib.util
import numpy as np
import pandas as pd
from names import basic, canon_first, is_non_employer
import roster

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.join(HERE, '..', 'data', 'interim')
ER = os.path.join(HERE, '..', 'data', 'er')
NET = os.path.join(HERE, '..', 'data', 'network')
RAW = os.path.join(HERE, '..', 'data', 'raw')

spec = importlib.util.spec_from_file_location('m6', os.path.join(HERE, '06_officials.py'))
m6 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m6)
spec = importlib.util.spec_from_file_location('m8', os.path.join(HERE, '08_network.py'))
m8 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m8)

RULES = {
    '1.126': ('S.F. Campaign & Governmental Conduct Code (C&GCC) §1.126(b): a person contracting or seeking to contract with the City '
              '(contract of $100,000+ in a fiscal year needing approval by a City elective officer, a board on which the officer serves, '
              'or a state-agency board with the officer\'s appointee) may not contribute to that officer, a candidate for that office, or '
              'their controlled committees. Covered contributors include the party, its board of directors, chair, CEO, CFO, COO, any '
              '10%+ owner, listed subcontractors, and committees it sponsors or controls. Window (current law): from submission of a '
              'proposal until 12 months after approval or termination of negotiations. Source: sfethics.org/guidance/city-officers/city-contracts '
              'and sfethics.org/guidance/contributors-third-parties/contributor-third-party-restrictions. Contracts approved before '
              '2019 were subject to an earlier version of the rule (from the start of negotiations to 6 months after approval); '
              'we apply that shorter window to pre-2019 approvals. Verified (2026-09-26) against Ord. 129-18 (File 180280, approved 5/30/2018, '
              'operative 1/1/2019) on sfbos.org and the current §1.126 on American Legal: before 2019 the ban ran from the commencement of '
              'negotiations until negotiations ended or six months after approval, for contracts of $50,000 or more.'),
    '3.620': ('C&GCC §3.620 (behested-payment rule, Article III, Chapter 6): City officers and designated employees may not solicit '
              'behested payments ($1,000+ in 12 months) from "interested parties" (parties to their proceedings, city contractors of '
              'their department or of contracts the Board approves, recent lobbyists and permit consultants, etc.), with exceptions '
              '(public appeals, competitively procured programs, contract-related solicitations, Board of Supervisors waivers). '
              'The ban took effect 2022-01-24 (Ord. 232-21) and was re-adopted as §3.620 by Proposition E (June 7, 2022, effective '
              '2022-07-10) and amended by Ord. 204-22 (effective 2022-11-06). Local disclosure (Form SFEC-3610(b), payments of $1,000+ '
              'from interested parties) applied to commissioners from 2018-01-01 (Ord. 1-17) and to all City elective officers from '
              '2019-01-01 (Ord. 129-18), to department heads from 2020-09-24 (Executive Directive 20-02), and was repealed by Ord. 232-21 '
              'effective 2022-01-24. State Form 803 applies when one source gives $5,000+ in a calendar year at an elected officer\'s '
              'behest. Sources: American Legal, C&GCC Art. III Ch. 6 history notes; sfethics.org/guidance/city-officers/behested-payments.'),
    'lobbyist_contrib': ('Lobbyist Ordinance (C&GCC Article II): no lobbyist may contribute to (or bundle for) a City elective officer, '
                         'a candidate for City elective office, or their controlled committees if the lobbyist is registered to lobby '
                         'the officer\'s agency, or the agency for which the candidate is running, or was so registered in the previous 90 days. '
                         'C&GCC §2.115(d)-(e), added by Proposition T (Nov. 8, 2016), operative Jan. 1, 2018; re-enacted by Proposition D '
                         '(Mar. 5, 2024), operative Oct. 12, 2024 (American Legal history note, fetched 2026-09-26).'),
    '1.127': ('C&GCC §1.127(b): persons (and affiliated entities) with a financial interest in a land use matter pending before '
              'specified boards may not contribute to members of the Board of Supervisors, the Mayor, the City Attorney, candidates for '
              'those offices, or their controlled committees.'),
}
CAVEAT_TIMING = ('A contribution near a contract, approval, or payment is a pattern worth checking, never proof of improper influence. '
                 'Name matches can be wrong, contributions may have been refunded, and the contract may fall outside the rule.')


def cpi_factors():
    f = pd.read_csv(os.path.join(RAW, 'fred_CPIAUCSL.csv'))
    f['year'] = f.observation_date.str[:4].astype(int)
    a = f.groupby('year').CPIAUCSL.mean()
    return (a[2025] / a).to_dict()


def J(obj, path):
    def conv(o):
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
        if isinstance(o, (pd.Timestamp,)): return str(o)[:10]
        if isinstance(o, float) and np.isnan(o): return None
        return str(o)
    with open(path, 'w') as fh:
        json.dump(obj, fh, indent=1, default=conv)


class Ctx:
    def __init__(self, variant, person_t, outdir):
        self.variant, self.person_t, self.out = variant, person_t, outdir
        os.makedirs(outdir, exist_ok=True)
        suffix = '' if variant == 'default' else f'_{variant}'
        self.nodes = pd.read_parquet(os.path.join(NET, f'nodes{suffix}.parquet'))
        self.edges = pd.read_parquet(os.path.join(NET, f'edges{suffix}.parquet'))
        self.label = dict(zip(self.nodes.node_id, self.nodes.label))
        self.ntype = dict(zip(self.nodes.node_id, self.nodes.node_type))
        self.com = pd.read_parquet(os.path.join(INT, 'committees.parquet'))
        self.com['node_id'] = 'C:' + self.com.filer_nid.astype(str)
        self.offs = pd.read_parquet(os.path.join(ER, 'officials.parquet'))
        self.R = m8.OrgResolver(variant)
        self.pm = pd.read_parquet(os.path.join(ER, 'person_matches.parquet'))
        self.contrib = pd.read_parquet(os.path.join(INT, 'contributions.parquet'))
        self.contrib['target'] = 'C:' + self.contrib.filer_nid.astype(str)
        de = pd.read_parquet(os.path.join(ER, 'donor_elements.parquet'))
        self.contrib = self.contrib.merge(de[['element_nid', 'pid']], on='element_nid', how='left')
        self.cpi = cpi_factors()
        # committee -> official control map and official offices
        ctl = self.edges[self.edges.edge_type == 'controls']
        self.com_official = ctl.groupby('target').source.first().to_dict()
        self.official_offices = {r.official_id: set(str(r.offices_sought).split(', ')) if isinstance(r.offices_sought, str) else set()
                                 for r in self.offs.itertuples()}

    def save(self, name, obj):
        J(obj, os.path.join(self.out, name + '.json'))

    def lab(self, x):
        return self.label.get(x, x)


# --------------------------------------------------------------------------------------------- A. contractors & the ban
def covered_offices(officer, office):
    t = basic(f'{officer or ""} {office or ""}')
    offs = set()
    if 'SUPERVISORS' in t or re.search(r'\bBOS\b', t):
        offs.add('Board of Supervisors')
    if re.search(r'\bMAYOR\b', t):
        offs.add('Mayor')
    for rx, o in [('CITY ATTORNEY', 'City Attorney'), ('DISTRICT ATTORNEY', 'District Attorney'), ('SHERIFF', 'Sheriff'),
                  ('TREASURER', 'Treasurer'), ('ASSESSOR', 'Assessor-Recorder'), ('PUBLIC DEFENDER', 'Public Defender'),
                  ('EDUCATION|SCHOOL', 'Board of Education'), ('COLLEGE', 'Community College Board')]:
        if re.search(rx, t):
            offs.add(o)
    return offs


class Coverage:
    """Who is covered by §1.126 for a contract approved by office(s) S, at contribution date t?
    Covered committees = committees controlled by an individual who, at t, either HOLDS an office in S
    (evidence: Form 700 filed for that office in that calendar year) or is a CANDIDATE for an office in S
    (evidence: the person's own candidate committee for that office received contributions within 30 days of t).
    Per SFEC Reg. 1.126-2(b)-(c), controlled committees include the person's committees for other local/state offices
    and ballot-measure committees they control."""
    POS = [('Board of Supervisors', r'SUPERVISOR'), ('Mayor', r'^MAYOR\b|,\s*MAYOR|\bMAYOR$'), ('City Attorney', r'CITY ATTORNEY'),
           ('District Attorney', r'DISTRICT ATTORNEY'), ('Sheriff', r'^SHERIFF'), ('Treasurer', r'TREASURER'),
           ('Assessor-Recorder', r'ASSESSOR'), ('Public Defender', r'PUBLIC DEFENDER')]

    def __init__(self, C):
        # (1) Form 700 cover pages. From 2022 on, the cover lists every position ever held on the filer's account, so only
        #     statements for 2013-2021 (single-position EOBCDH records) are used as holding evidence.
        f7 = pd.read_parquet(os.path.join(INT, 'f700_cover.parquet'))
        f7['nk'] = f7.lastname.map(m6.lastkey) + '|' + f7.firstname.map(canon_first)
        f7['year'] = pd.to_numeric(f7.year, errors='coerce')
        f7 = f7[(f7.year <= 2021) & ~f7.positionname.fillna('').str.contains(',')]
        self.hold = {}
        for r in f7.itertuples():
            pos = str(r.positionname or '').upper().strip(); dep = str(r.departmentname or '').upper()
            for off, rx in self.POS:
                if re.search(rx, pos) and not re.search(r'NURS|PORTER|SUPERVISOR I|ASSISTANT|DEPUTY|SPECIALIST|OPERATIONS|LEGISLATIVE|ANALYST|MANAGER', pos):
                    if off == 'Board of Supervisors' and 'SUPERVISORS' not in dep:
                        continue
                    if pd.notna(r.year):
                        self.hold.setdefault(('O:' + r.nk, off), set()).add(int(r.year))
        # (2) Lobbyist contact reports: a person who ran for office O and was reported as contacted in O's department in year Y
        #     is taken to hold O in Y (single-year gaps filled).
        lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
        lc['oid'] = 'O:' + lc.officialname.map(m6.nk_from_lastfirst)
        lc['off'] = lc.departmentname.map(m6.dept_office)
        lc['year'] = lc.date.dt.year
        cnt = lc.dropna(subset=['off', 'year']).groupby(['oid', 'off', 'year']).size()
        cnt = cnt[cnt >= 3].reset_index()   # at least 3 reported contacts in the year, to avoid mis-coded departments
        g = cnt.groupby(['oid', 'off']).year.agg(lambda s: set(int(x) for x in s))
        for (oid, off), yrs in g.items():
            if off not in C.official_offices.get(oid, set()):
                continue
            yrs = set(yrs)
            yrs |= {y for y in range(min(yrs), max(yrs) + 1) if (y - 1 in yrs and y + 1 in yrs)}
            self.hold.setdefault((oid, off), set()).update(yrs)
        # candidacy intervals from own city-candidate committees
        com = C.com[C.com.is_city_candidate]
        c = C.contrib[C.contrib.target.isin(set(com.node_id))].groupby('target').date.agg(['min', 'max'])
        self.cand = {}
        for r in com.itertuples():
            o = C.com_official.get(r.node_id)
            if o and r.node_id in c.index:
                self.cand.setdefault((o, r.office), []).append((c.at[r.node_id, 'min'] - pd.Timedelta(days=30), c.at[r.node_id, 'max'] + pd.Timedelta(days=30)))
        self.com_official = C.com_official
        # Red-team pass 2: replace the raw holding evidence with the roster-checked version (roster.py). The contact rule
        # alone credited legislative aides who later ran for office with holding the seat.
        f7only = {}
        for r in f7.itertuples():
            pos = str(r.positionname or '').upper().strip(); dep = str(r.departmentname or '').upper()
            for off, rx in self.POS:
                if re.search(rx, pos) and not re.search(r'NURS|PORTER|SUPERVISOR I|ASSISTANT|DEPUTY|SPECIALIST|OPERATIONS|LEGISLATIVE|ANALYST|MANAGER', pos):
                    if off == 'Board of Supervisors' and 'SUPERVISORS' not in dep:
                        continue
                    if pd.notna(r.year):
                        f7only.setdefault(('O:' + r.nk, off), set()).add(int(r.year))
        own_years = {}
        for k, ivs in self.cand.items():
            for lo_, hi_ in ivs:
                own_years.setdefault(k, set()).update(range(lo_.year, hi_.year + 1))
        nk_of = lambda full: 'O:' + m6.nk_from_lastfirst(full)
        self.hold_raw = {k: set(v) for k, v in self.hold.items()}
        self.hold, self.bos_iv, self.roster_audit = roster.build(self.hold, f7only, nk_of, own_years)
        # citywide offices: exact term dates from the verified office-history table (roster.citywide_intervals)
        self.city = roster.citywide_intervals()

    def status(self, official, offices, t):
        for o in offices:
            if o in roster.SINGLE:
                r = roster.citywide_status(self.city, official, o, t)
                if r is not None:
                    return f"held {o} on {t:%Y-%m-%d} ({r['role']} term, verified office history: offices_citywide.json)"
            elif t.year in self.hold.get((official, o), set()):
                return f'held {o} in {t.year} (' + ('sfbos.org roster' if o == 'Board of Supervisors' else 'Form 700 or lobbyist contact reports') + ')'
            for lo, hi in self.cand.get((official, o), []):
                if lo <= t <= hi:
                    return f'candidate for {o}'
        return None


def contractor_ban(C):
    f = pd.read_parquet(os.path.join(INT, 'f126.parquet'))
    f = f[f.date_signed.notna()].copy()
    f['ent'] = [C.R(x)[0] for x in f.contractor]
    f['ent_conf'] = [C.R(x)[1] for x in f.contractor]
    f['offices'] = [covered_offices(o, of) for o, of in zip(f.officer, f.office)]
    f = f[f.ent.notna()]
    # approval-date proxy: the date the 126f4 was signed/filed (due within 5 business days of approval, Reg. 1.126-4)
    f['D'] = f.date_signed
    f['window_days'] = np.where(f.D >= '2019-01-01', 365, 182)
    cov = Coverage(C)
    C.coverage = cov
    C.save('official_holding', {'note': 'Roster-checked office holding by calendar year (roster.py); used for §1.126 coverage and for labelling officials.',
                                'holding': [{'official': o, 'office': off, 'years': sorted(int(y) for y in ys)} for (o, off), ys in sorted(cov.hold.items()) if o.startswith('O:')],
                                'audit': cov.roster_audit})
    allc = gather_contractor_contributions(C, f, cov)
    d = (allc.date - allc.D).dt.days
    allc['days_from_approval'] = d
    allc['inside_post_window'] = (d > 0) & (d <= allc.window_days)
    allc['pre_180'] = (d <= 0) & (d >= -180)
    # contributions a candidate makes to their own committee (a listed principal who is also the candidate) are excluded
    allc['self_contribution'] = [(isinstance(n, str) and n.startswith('PP:') and C.com_official.get(r) == 'O:' + n[3:]) for n, r in zip(allc.contributor_node, allc.recipient)]
    PUBLIC = r'REGENTS|UNIVERSITY OF CALIFORNIA|\bUCSF\b|UNIFIED SCHOOL DISTRICT|CITY COLLEGE|COMMUNITY COLLEGE|HOUSING AUTHORITY|STATE OF CALIFORNIA|COUNTY OF|CITY OF |TRANSIT DISTRICT|\bBART\b|SUPERIOR COURT|DEPT OF|DEPARTMENT OF'
    allc['public_entity'] = allc.contractor.fillna('').str.upper().str.contains(PUBLIC)
    allc.to_parquet(os.path.join(C.out, 'contractor_affiliated_contributions.parquet'), index=False)
    # refunds (negative amounts) are not contributions; public-entity contractors reported separately (coverage by §1.126 unclear)
    cs_pub = allc[(allc.inside_post_window) & allc.covered_status.notna() & ~allc.self_contribution & (allc.amount > 0) & allc.public_entity]
    cs_pub = cs_pub.drop_duplicates(['record_id', 'contributor_node'])
    n_neg = int(((allc.inside_post_window | allc.pre_180) & allc.covered_status.notna() & (allc.amount <= 0)).sum())
    cs = allc[(allc.inside_post_window | allc.pre_180) & allc.covered_status.notna() & ~allc.self_contribution & (allc.amount > 0) & ~allc.public_entity].copy()
    cs['timing'] = np.where(cs.days_from_approval > 0, 'after approval, inside post-approval ban window',
                            'up to 180 days before approval (inside the ban only if a proposal had already been submitted)')
    cs['recipient_label'] = cs.recipient.map(C.lab)
    cs['recipient_official'] = cs.recipient.map(C.com_official).map(C.lab)
    # a contribution can sit inside windows of several filings of the same contractor: keep the nearest approval
    cs['absd'] = cs.days_from_approval.abs()
    cs['prio'] = np.where(cs.days_from_approval > 0, 0, 1)   # a post-approval window hit takes precedence over a pre-approval proximity
    cs = cs.sort_values(['record_id', 'contributor_node', 'prio', 'absd']).drop_duplicates(['record_id', 'contributor_node']).drop(columns=['absd', 'prio'])
    # refunds: negative Schedule A amounts from the same donor to the same committee within 12 months after
    neg = C.contrib[C.contrib.amount < 0]
    flags = []
    for r in cs.itertuples():
        n = neg[(neg.target == r.recipient) & (neg.date >= r.date) & (neg.date <= r.date + pd.Timedelta(days=365))]
        if r.contributor_type == 'contracting entity':
            n = n[[C.R(x)[0] == r.contributor_node for x in n.donor_last]]
        else:
            n = n[n.pid == r.pid]
        flags.append(bool(len(n)))
    cs['possible_refund_seen'] = flags
    cs['assessment'] = np.where(cs.days_from_approval > 0,
                                'appears to warrant review under C&GCC §1.126 (post-approval window), subject to the caveats',
                                'timing depends on the proposal date; review only if a proposal was pending')
    cs.to_parquet(os.path.join(C.out, 'contractor_ban_cases.parquet'), index=False)
    post = cs[cs.days_from_approval > 0]
    cols = ['contractor', 'contributor', 'contributor_type', 'role', 'recipient_label', 'recipient_official', 'covered_status', 'date', 'amount',
            'approval_proxy_date', 'days_from_approval', 'offices', 'contract_amount', 'match_conf', 'possible_refund_seen', 'filing_key']
    summ = {
        'rule': RULES['1.126'], 'caveat': CAVEAT_TIMING,
        'coverage_method': Coverage.__doc__,
        'n_126f4_filings_considered': int(len(f)), 'n_contractor_entities_on_126f4': int(f.ent.nunique()),
        'n_affiliated_contributions_to_covered_or_any': int(len(allc)),
        'post_approval': {'n_contributions': int(len(post)), 'amount': float(post.amount.sum()),
                          'n_contractors': int(post.contractor_entity.nunique()), 'n_contributors': int(post.contributor_node.nunique()),
                          'by_contributor_type': post.groupby('contributor_type').amount.agg(['size', 'sum']).reset_index().to_dict('records'),
                          'by_role': post.groupby('role').amount.agg(['size', 'sum']).reset_index().to_dict('records'),
                          'by_approval_era': post.assign(era=np.where(post.approval_proxy_date >= '2019-01-01', '2019+ (12-month window)', 'pre-2019 (6-month window)'))
                              .groupby('era').amount.agg(['size', 'sum']).reset_index().to_dict('records'),
                          'by_recipient_official': post.groupby('recipient_official').amount.agg(['size', 'sum']).reset_index().sort_values('sum', ascending=False).head(20).to_dict('records'),
                          'refund_seen': int(post.possible_refund_seen.sum()),
                          'amount_median': float(post.amount.median()) if len(post) else None},
        'pre_approval_180d': {'n_contributions': int((cs.days_from_approval <= 0).sum()), 'amount': float(cs[cs.days_from_approval <= 0].amount.sum())},
        'excluded': {'public_entity_contractors_inside_post_window': {'n': int(len(cs_pub)), 'amount': float(cs_pub.amount.sum()),
                                                                      'contractors': sorted(set(cs_pub.contractor))[:20],
                                                                      'note': 'Contracting party is a public entity (UC/UCSF, SFUSD, City College, housing authority, etc.). Whether §1.126 reaches board members of public bodies or their foundations is unclear, so these are not flagged.'},
                     'refund_or_negative_rows': n_neg, 'self_contributions': int(allc.self_contribution.sum())},
        'top_cases': post.sort_values('amount', ascending=False).head(40)[cols].to_dict('records'),
    }
    C.save('contractor_ban', summ)
    return cs, f, allc


def gather_contractor_contributions(C, f, cov):
    """All contributions (any date) by each filing's contracting entity or its listed, matched principals, with the
    covered status of the recipient committee at the contribution date (None = not covered for this filing's offices)."""
    org_c = C.edges[(C.edges.edge_type == 'contribution') & C.edges.source.str.startswith('ORG:')][['source', 'target', 'date', 'amount', 'record_id', 'match_conf']]
    by_ent = {k: g for k, g in org_c.groupby('source')}
    pa = pd.read_parquet(os.path.join(INT, 'f126_parties.parquet'))
    pa = pa[pa.is_person].copy()
    pa['nk'] = pa['last'].map(m6.lastkey) + '|' + pa['first'].map(canon_first)
    pm = C.pm[(C.pm.kind == 'principal') & (C.pm.decision == 'same')]
    pm = pm[pm.confidence >= C.person_t].copy()
    pm['pp_key'] = pm.role_id.str[2:]
    pa['pp_key'] = pa.nk + '|' + pa.contractor_key
    pa = pa.merge(pm[['pp_key', 'pid', 'confidence', 'rationale']], on='pp_key')
    pa_by = {k: g for k, g in pa.groupby('filing_key')}
    ind = C.contrib[C.contrib.is_individual & C.contrib.pid.notna()][['pid', 'target', 'date', 'amount', 'element_nid']]
    by_pid = {k: g for k, g in ind.groupby('pid')}
    rows = []
    status_cache = {}

    def st(com, offices, t):
        o = C.com_official.get(com)
        if not o:
            return None
        k = (o, tuple(sorted(offices)), t)
        if k not in status_cache:
            status_cache[k] = cov.status(o, offices, t)
        return status_cache[k]
    for r in f.itertuples():
        if not r.offices:
            continue
        base = dict(filing_key=r.filing_key, contractor_entity=r.ent, contractor=r.contractor, approval_proxy_date=r.D, D=r.D,
                    offices=', '.join(sorted(r.offices)), contract_amount=r.contract_amount, description=r.description, window_days=int(r.window_days))
        g = by_ent.get(r.ent)
        if g is not None:
            for x in g.itertuples():
                if pd.isna(x.date):
                    continue
                rows.append(dict(base, contributor_type='contracting entity', contributor=C.lab(r.ent), contributor_node=r.ent, role='party', pid=None,
                                 recipient=x.target, date=x.date, amount=x.amount, record_id=x.record_id,
                                 match_conf=min(x.match_conf, r.ent_conf or 1), match_basis='organization name resolution',
                                 covered_status=st(x.target, r.offices, x.date)))
        pp = pa_by.get(r.filing_key)
        if pp is None:
            continue
        for p in pp.itertuples():
            g = by_pid.get(p.pid)
            if g is None:
                continue
            for x in g.itertuples():
                if pd.isna(x.date):
                    continue
                rows.append(dict(base, contributor_type='listed principal', contributor=f'{p.first} {p.last}'.strip(), contributor_node='PP:' + p.nk,
                                 role=p.party_type, pid=p.pid, recipient=x.target, date=x.date, amount=x.amount, record_id=x.element_nid,
                                 match_conf=p.confidence, match_basis=p.rationale, covered_status=st(x.target, r.offices, x.date)))
    return pd.DataFrame(rows)


def contractor_base_rates(C, f, cases, allc):
    """How common are donor-contractor overlaps, and do contributions cluster inside ban windows more than chance?"""
    rng = np.random.default_rng(42)
    ents = set(f.ent)
    city_coms = set(C.com[C.com.is_city_candidate].node_id) | set(C.edges[C.edges.edge_type == 'controls'].target)
    org_c = C.edges[(C.edges.edge_type == 'contribution')]
    org_to_city = org_c[org_c.source.str.startswith('ORG:') & org_c.target.isin(city_coms)]
    pm = C.pm[(C.pm.kind == 'principal') & (C.pm.decision == 'same') & (C.pm.confidence >= C.person_t)]
    ind = C.contrib[C.contrib.is_individual & C.contrib.pid.isin(set(pm.pid)) & C.contrib.target.isin(city_coms)]
    pid_ent = {}
    for rid, pid in zip(pm.role_id, pm.pid):
        pid_ent.setdefault(pid, set()).add(C.R.ent.get(rid.split('|', 2)[-1]))
    ents_pr = set()
    for pid in set(ind.pid):
        ents_pr |= pid_ent.get(pid, set())
    emp = C.edges[(C.edges.edge_type == 'employee_giving') & C.edges.target.isin(city_coms)]
    sc = C.edges[C.edges.edge_type == 'contract']
    all_contractors = set(sc.target) | ents
    out = {
        'n_contractor_entities_126f4': len(ents),
        'share_126f4_contractors_entity_gave_to_city_candidates_ever': len(ents & set(org_to_city.source)) / max(len(ents), 1),
        'share_126f4_contractors_with_matched_principal_giving_to_city_candidates_ever': len(ents & ents_pr) / max(len(ents), 1),
        'share_126f4_contractors_with_employee_giving_to_city_candidates_ever': len(ents & set(emp.source)) / max(len(ents), 1),
        'n_all_contractor_entities_incl_controller': len(all_contractors),
        'share_all_contractors_with_employee_giving': len(all_contractors & set(emp.source)) / max(len(all_contractors), 1),
        'share_all_contractors_entity_gave': len(all_contractors & set(org_to_city.source)) / max(len(all_contractors), 1),
        'share_126f4_contractors_with_post_approval_case': cases[cases.days_from_approval > 0].contractor_entity.nunique() / max(len(ents), 1) if len(cases) else 0,
    }
    cov = allc[allc.covered_status.notna() & ~allc.self_contribution].copy()
    # Placebo: for approvals dated 2019-01-01..2023-09-25 (so every comparison window has complete data), count unique covered
    # contributions in the 12 months after approval (W0) and in same-length windows shifted by exactly -2 and +2 years
    # (same position in the two-year election calendar). Covered status is evaluated at each contribution's own date.
    sub = cov[(cov.D >= '2019-01-01') & (cov.D <= '2023-09-25')]
    def win(lo, hi):
        d = (sub.date - sub.D).dt.days
        m = (d > lo) & (d <= hi)
        return int(sub[m].drop_duplicates(['record_id', 'contributor_node']).shape[0])
    w0 = win(0, 365); wm2 = win(-730, -365); wp2 = win(730, 1095); wm1 = win(-365, 0); wp1 = win(365, 730)
    n_fil = int(sub.filing_key.nunique())
    out['timing_placebo'] = {
        'description': ('Approvals 2019-01-01 to 2023-09-25. Counts of unique contributions from the contracting entity or its listed, name-matched '
                        'principals to committees covered for that approval (evaluated at the contribution date), in 12-month windows relative to the '
                        'approval-date proxy. W0 = the post-approval ban window. W-2y and W+2y sit at the same point of the two-year election calendar '
                        'and serve as the baseline. W-1y overlaps the period when a proposal was likely pending (also inside the ban once submitted).'),
        'n_filings_with_any_covered_contribution': n_fil,
        'W0_post_approval_0_12m': w0, 'W_minus_1y': wm1, 'W_plus_1y': wp1, 'W_minus_2y': wm2, 'W_plus_2y': wp2,
        'baseline_same_parity_mean': (wm2 + wp2) / 2, 'ratio_W0_to_baseline': w0 / max((wm2 + wp2) / 2, 1),
        'expected_share_if_unrelated_days': None,
    }
    # share of days covered by the union of each contractor's post-approval windows (contract definition), weighted by records
    lo_, hi_ = pd.Timestamp('2019-01-01'), pd.Timestamp('2025-12-31')
    tot_days = (hi_ - lo_).days
    wins = f[['ent', 'D', 'window_days']].copy()
    wins['s'] = wins.D; wins['e'] = wins.D + pd.to_timedelta(wins.window_days, unit='D')
    covshare = {}
    for ent, g in wins.groupby('ent'):
        iv = sorted((max(a, lo_), min(b, hi_)) for a, b in zip(g.s, g.e) if min(b, hi_) > max(a, lo_))
        days, cur = 0, None
        for a, b in iv:
            if cur and a <= cur[1]:
                cur = (cur[0], max(cur[1], b))
            else:
                if cur: days += (cur[1] - cur[0]).days
                cur = (a, b)
        if cur: days += (cur[1] - cur[0]).days
        covshare[ent] = days / tot_days
    recs = cov[(cov.date >= lo_) & (cov.date <= hi_)].drop_duplicates(['record_id', 'contributor_node', 'contractor_entity'])
    w = recs.groupby('contractor_entity').size()
    exp = float(sum(covshare.get(e, 0) * n for e, n in w.items()) / max(w.sum(), 1))
    cc = cov[(cov.date >= lo_) & (cov.date <= hi_)]
    obs_share = float(cc.groupby(['record_id', 'contributor_node', 'contractor_entity'])['inside_post_window'].any().mean()) if len(cc) else None
    out['expected_share_if_unrelated'] = exp
    out['observed_share_inside_window_2019_2025'] = obs_share
    out['n_records_2019_2025'] = int(len(recs))
    out['redteam2'] = contractor_base_rates_v2(C, f, allc)
    C.save('contractor_base_rates', out)
    return out


def contractor_base_rates_v2(C, f, allc):
    """Red-team pass 2 (2026-09-26). Three corrections to the expected-by-chance share, plus robustness checks.
    (1) Office matching: the first-pass expected share used the windows of ALL of a contractor's approvals, but a record only
        counts as "inside" for approvals whose approving office covers the recipient. Here each record's expected share uses
        only the approvals for which that recipient was covered at the contribution date (the same approvals the observed
        flag uses).
    (2) Election calendar: contributions are not spread evenly over the year; they bunch before elections. Days are weighted
        by the monthly count of all individual contributions to City candidate committees, so a window that covers a
        pre-election autumn counts for more than one that covers a quiet spring.
    (3) Rule in force: windows use 6 months after approvals before 2019-01-01 and 12 months after approvals from then on
        (Ord. 129-18, operative 2019-01-01, verified). The sensitivity row applies the 12-month window to any contribution
        made on or after 2019-01-01, whatever the approval date (an alternative reading of the transition).
    Also: contractor-cluster bootstrap intervals (1,000 draws), a +/-4-year placebo (same point of the four-year mayoral and
    district cycle), and the observed share by election-year vs off-year contributions."""
    rng = np.random.default_rng(7)
    lo_, hi_ = pd.Timestamp('2019-01-01'), pd.Timestamp('2025-12-31')
    days = pd.date_range(lo_, hi_, freq='D'); nd = len(days)
    city_coms = set(C.com[C.com.is_city_candidate].node_id) | set(C.edges[C.edges.edge_type == 'controls'].target)
    ci = C.contrib[C.contrib.is_individual & C.contrib.target.isin(city_coms) & (C.contrib.amount > 0) & (C.contrib.date >= lo_) & (C.contrib.date <= hi_)]
    mcount = ci.groupby(ci.date.dt.to_period('M')).size()
    per = days.to_period('M')
    w = np.array([mcount.get(p, 0) / p.days_in_month for p in per], dtype=float)
    w_uniform = np.ones(nd)
    cov = allc[allc.covered_status.notna() & ~allc.self_contribution & (allc.amount > 0)].copy()
    cov = cov[(cov.date >= lo_) & (cov.date <= hi_)]
    cov['k'] = cov.record_id.astype(str) + '|' + cov.contributor_node.astype(str) + '|' + cov.contractor_entity.astype(str)
    fil = f.drop_duplicates('filing_key').set_index('filing_key')
    def win_idx(D, wd):
        a = (D + pd.Timedelta(days=1) - lo_).days; b = (D + pd.Timedelta(days=int(wd)) - lo_).days
        return max(a, 0), min(b, nd - 1)
    recs = []
    for k, g in cov.groupby('k'):
        m = np.zeros(nd, dtype=bool); m12 = np.zeros(nd, dtype=bool)
        for fk in g.filing_key.unique():
            D = fil.at[fk, 'D']; wd = fil.at[fk, 'window_days']
            a, b = win_idx(D, wd)
            if b >= a: m[a:b + 1] = True
            a2, b2 = win_idx(D, 365)
            if b2 >= a2:
                # alternative transition reading: 12 months for any day on or after 2019-01-01
                m12[a2:b2 + 1] = True
        t = g.date.iloc[0]; dd = (g.date.iloc[0] - g.D).dt.days
        inside = bool(g.inside_post_window.any())
        inside12 = bool(((dd > 0) & (dd <= 365)).any())
        recs.append(dict(k=k, contractor=g.contractor_entity.iloc[0], date=t, inside=inside, inside12=inside12, pub=bool(g.public_entity.iloc[0]),
                         e_uniform=float(m.sum() / nd), e_weighted=float((w * m).sum() / w.sum()), e12_weighted=float((w * m12).sum() / w.sum())))
    R = pd.DataFrame(recs)
    # the first-pass (naive) expected: all windows of the contractor, uniform days, weighted by records
    wins = f[['ent', 'D', 'window_days']].copy()
    naive = {}
    for ent, g in wins.groupby('ent'):
        m = np.zeros(nd, dtype=bool)
        for D, wd in zip(g.D, g.window_days):
            a, b = win_idx(D, wd)
            if b >= a: m[a:b + 1] = True
        naive[ent] = m.sum() / nd
    R['e_naive'] = R.contractor.map(naive).fillna(0)
    def summ(df):
        return dict(n_records=int(len(df)), n_contractors=int(df.contractor.nunique()), observed=float(df.inside.mean()),
                    expected_naive_all_windows_uniform=float(df.e_naive.mean()), expected_office_matched_uniform=float(df.e_uniform.mean()),
                    expected_office_matched_calendar_weighted=float(df.e_weighted.mean()),
                    observed_if_12m_for_all_2019_contributions=float(df.inside12.mean()), expected_if_12m_for_all_2019_contributions=float(df.e12_weighted.mean()))
    out = {'method': contractor_base_rates_v2.__doc__, 'all_records': summ(R), 'excluding_public_entities': summ(R[~R.pub])}
    # contractor-cluster bootstrap of observed - expected (office-matched, calendar-weighted)
    Rb = R[~R.pub]   # bootstrap on the headline population (public-entity contractors excluded, as in the flags)
    ents = Rb.contractor.unique(); by = {e: g for e, g in Rb.groupby('contractor')}
    diffs, obs_b, exp_b = [], [], []
    for _ in range(1000):
        pick = rng.choice(ents, len(ents), replace=True)
        g = pd.concat([by[e] for e in pick])
        obs_b.append(g.inside.mean()); exp_b.append(g.e_weighted.mean()); diffs.append(g.inside.mean() - g.e_weighted.mean())
    q = lambda v: [float(np.quantile(v, .025)), float(np.quantile(v, .975))]
    out['bootstrap_95ci'] = {'observed': q(obs_b), 'expected_office_matched_calendar_weighted': q(exp_b), 'difference': q(diffs), 'draws': 1000, 'cluster': 'contractor',
                             'population': 'excluding public-entity contractors'}
    # election-year vs off-year contributions
    R['even'] = R.date.dt.year % 2 == 0
    out['by_calendar'] = {('election_year' if k else 'off_year'): dict(n=int(len(g)), observed=float(g.inside.mean()), expected=float(g.e_weighted.mean())) for k, g in R[~R.pub].groupby('even')}
    # +/-4 year placebo (approvals 2019-01-01..2021-09-25 so W+4y ends inside the data)
    cv = allc[allc.covered_status.notna() & ~allc.self_contribution & (allc.amount > 0)]
    sub = cv[(cv.D >= '2019-01-01') & (cv.D <= '2021-09-25')]
    def win(lo, hi):
        d = (sub.date - sub.D).dt.days
        return int(sub[(d > lo) & (d <= hi)].drop_duplicates(['record_id', 'contributor_node']).shape[0])
    w0 = win(0, 365); wm4 = win(-1460, -1095); wp4 = win(1460, 1825); wm2 = win(-730, -365); wp2 = win(730, 1095)
    out['placebo_4y'] = {'approvals': '2019-01-01 to 2021-09-25', 'W0': w0, 'W_minus_4y': wm4, 'W_plus_4y': wp4, 'W_minus_2y': wm2, 'W_plus_2y': wp2,
                         'ratio_W0_to_4y_mean': w0 / max((wm4 + wp4) / 2, 1), 'ratio_W0_to_2y_mean': w0 / max((wm2 + wp2) / 2, 1)}
    # transition: contributions on/after 2019-01-01 that fall 183-365 days after a pre-2019 approval (inside only under the alternative reading)
    t = allc[allc.covered_status.notna() & ~allc.self_contribution & (allc.amount > 0) & ~allc.public_entity & (allc.D < '2019-01-01') & (allc.date >= '2019-01-01')]
    dd = (t.date - t.D).dt.days
    tt = t[(dd > 182) & (dd <= 365)].drop_duplicates(['record_id', 'contributor_node'])
    out['transition_sensitivity'] = {'n_contributions': int(len(tt)), 'amount': float(tt.amount.sum()),
                                     'note': ('Contributions made on or after 2019-01-01, 183-365 days after an approval dated before 2019. Outside the ban under the reading used '
                                              'here (the 6-month window of the rule in force at approval); inside it if the 12-month window is applied to every contribution made '
                                              'after the new rule became operative. Ord. 129-18 has no transition clause for existing contracts.')}
    R.drop(columns=['k']).to_parquet(os.path.join(C.out, 'ban_base_rate_records.parquet'), index=False)
    return out


# --------------------------------------------------------------------------------------------- B. behested payments
def behested(C):
    e = C.edges[C.edges.edge_type == 'behested_payment'].copy()
    bp = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    e['form'] = [json.loads(a).get('form') for a in e['attrs']]
    e['payor_raw'] = [json.loads(a).get('payor_raw') for a in e['attrs']]
    e['payee_raw'] = [json.loads(a).get('payee_raw') for a in e['attrs']]
    # de-duplicate amendments for 3610b: an Amendment supersedes the Original with the same payor/payee/date/official
    e = e.sort_values('date')
    # official is null on SFEC-3600 commissioner rows: fill it, or those distinct payments collapse into one NaN key
    e['dupkey'] = e.official.fillna('') + '|' + e.source.astype(str) + '|' + e.target.astype(str) + '|' + e.date.astype(str)
    raw_n = len(e)
    e = e.drop_duplicates('dupkey', keep='last')
    # rows whose payee is 'See Attached' (DCYF Summer Together 2021) list recipient agencies in the payor field: direction ambiguous
    e['ambiguous'] = e.payee_raw.fillna('').str.upper().str.contains('SEE ATTACHED')
    amb = e[e.ambiguous]
    e_all = e
    e = e[~e.ambiguous]
    per_off = e.groupby('official').agg(n=('amount', 'size'), total=('amount', 'sum'), n_payors=('source', 'nunique'),
                                        first=('date', 'min'), last=('date', 'max')).reset_index().sort_values('total', ascending=False)
    per_off['label'] = per_off.official.map(C.lab)
    top_payors = e.groupby('source').agg(n=('amount', 'size'), total=('amount', 'sum')).reset_index().sort_values('total', ascending=False)
    top_payors['label'] = top_payors.source.map(C.lab)
    top_payees = e.groupby('target').agg(n=('amount', 'size'), total=('amount', 'sum')).reset_index().sort_values('total', ascending=False)
    top_payees['label'] = top_payees.target.map(C.lab)
    # pending business around the payment date (+/- 12 months)
    lob = C.edges[C.edges.edge_type == 'lobbying_contact'][['source', 'target', 'date', 'attrs']]
    lob['dept'] = [json.loads(a).get('department') for a in lob['attrs']]
    appr = C.edges[C.edges.edge_type == 'contract_approval'][['source', 'target', 'date', 'amount']]
    ctr = C.edges[C.edges.edge_type == 'contract'][['source', 'target', 'date', 'amount']]
    contr = C.edges[C.edges.edge_type.isin(['contribution'])][['source', 'target', 'date', 'amount']]
    off_coms = {}
    for t, s in zip(C.edges[C.edges.edge_type == 'controls'].target, C.edges[C.edges.edge_type == 'controls'].source):
        off_coms.setdefault(s, set()).add(t)
    offmeta = C.offs.set_index('official_id')
    rows = []
    for r in e.itertuples():
        if not isinstance(r.source, str):
            continue
        lo, hi = r.date - pd.Timedelta(days=365), r.date + pd.Timedelta(days=365)
        if pd.isna(r.date):
            continue
        offices = C.official_offices.get(r.official, set())
        is_bos = 'Board of Supervisors' in offices or 'SUPERVISOR' in str(bp.agency).upper() and False
        agency = bp[bp.official.map(lambda s: 'O:' + m6.nk_from_lastfirst(s)) == r.official].agency.dropna()
        agency_txt = basic(agency.iloc[0]) if len(agency) else ''
        l = lob[(lob.source == r.source) & (lob.date >= lo) & (lob.date <= hi)]
        l_same = l[l.target == r.official]
        if 'SUPERVISORS' in agency_txt:
            l_body = l[l.dept.fillna('').str.upper().str.contains('SUPERVISORS')]
            a = appr[(appr.target == r.source) & (appr.source == 'BODY:Board of Supervisors') & (appr.date >= lo) & (appr.date <= hi)]
        elif 'MAYOR' in agency_txt:
            l_body = l[l.dept.fillna('').str.upper().str.contains('MAYOR')]
            a = appr[(appr.target == r.source) & appr.source.isin(['BODY:Mayor', 'BODY:Board of Supervisors']) & (appr.date >= lo) & (appr.date <= hi)]
        else:
            key = agency_txt.split(' ')[0] if agency_txt else '@@'
            l_body = l[l.dept.fillna('').map(basic).str.contains(re.escape(key))] if agency_txt else l.iloc[0:0]
            a = appr.iloc[0:0]
        c = contr[(contr.source == r.source) & contr.target.isin(off_coms.get(r.official, set())) & (contr.date >= lo) & (contr.date <= hi)]
        rows.append(dict(official=r.official, official_label=C.lab(r.official), payor=r.source, payor_label=C.lab(r.source), payee=r.target,
                         payee_label=C.lab(r.target), date=r.date, amount=r.amount, form=r.form,
                         lobbied_same_official_12m=len(l_same), lobbied_same_body_12m=len(l_body), lobbied_any_12m=len(l),
                         contract_approvals_same_body_12m=len(a), payor_contributions_to_official_12m=float(c.amount.sum())))
    pb = pd.DataFrame(rows)
    pb.to_parquet(os.path.join(C.out, 'behested_pending_business.parquet'), index=False)
    pb['any_pending'] = (pb.lobbied_same_official_12m + pb.lobbied_same_body_12m + pb.contract_approvals_same_body_12m) > 0
    f1145 = pd.read_parquet(os.path.join(INT, 'f1145.parquet'))
    f1145['amount'] = pd.to_numeric(f1145.contributionamount, errors='coerce')
    b1145 = f1145.drop_duplicates(['docusignid', 'contributorname', 'contributiondate', 'contributionamount'])
    by_off_1145 = b1145.groupby('cityelectiveofficername').agg(n=('amount', 'size'), total=('amount', 'sum'), committees=('committeename', lambda s: ' | '.join(s.dropna().unique()[:4]))).reset_index().sort_values('total', ascending=False)
    top_1145 = b1145.groupby('contributorname').amount.sum().sort_values(ascending=False).head(15)
    waivers = pd.read_parquet(os.path.join(INT, 'bp_waivers.parquet'))
    summ = {
        'rule': RULES['3.620'], 'caveat': CAVEAT_TIMING,
        'coverage_note': ('Machine-readable behested-payment data: FPPC Form 803 filings Apr 2015-Mar 2018 (98wa-4d49) and SFEC Form 3610(b) '
                          '(interested-party payments, 2019 onward; b3ya-imj5). Form 803 filings from March 2018 onward exist only as PDFs on the '
                          'Ethics Commission\'s NetFile portal and are NOT included, so totals understate behested giving after March 2018.'),
        'raw_rows': raw_n, 'deduplicated_rows': int(len(e_all)), 'total_amount_all': float(e_all.amount.sum()),
        'ambiguous_rows': {'n': int(len(amb)), 'amount': float(amb.amount.sum()), 'officials': sorted(set(amb.official.map(C.lab))),
                           'note': ('SFEC 3610(b) filings for the 2021 Summer Together initiative list about 49 nonprofit agencies in the payor field and '
                                    '"See Attached" as payee; the description says funds were allocated TO these agencies, so the payor field most likely '
                                    'names recipients. These rows are excluded from payor rankings and totals below, and one row dated 2012 is almost '
                                    'certainly a typo for 2021 (filed May 2021).')},
        'n_rows_used': int(len(e)), 'total_amount': float(e.amount.sum()),
        'by_form': e.groupby('form').amount.agg(['size', 'sum']).reset_index().to_dict('records'),
        'by_year': e.assign(y=e.date.dt.year).groupby(['y', 'form']).amount.agg(['size', 'sum']).reset_index().to_dict('records'),
        'officials': per_off.head(25).to_dict('records'),
        'top_payors': top_payors.head(25).to_dict('records'),
        'top_recipients': top_payees.head(25).to_dict('records'),
        'pending_business': {
            'n_payments_checked': int(len(pb)), 'share_with_lobbying_or_approval_same_official_or_body_12m': float(pb.any_pending.mean()) if len(pb) else None,
            'share_lobbied_same_official': float((pb.lobbied_same_official_12m > 0).mean()) if len(pb) else None,
            'share_contract_approval_same_body': float((pb.contract_approvals_same_body_12m > 0).mean()) if len(pb) else None,
            'by_form': pb.groupby('form').any_pending.mean().to_dict() if len(pb) else {},
            'examples': pb[pb.any_pending].sort_values('amount', ascending=False).head(20).to_dict('records'),
            'note': ('SFEC 3610(b) forms are filed only when the payor IS an interested party, so pending business is expected for those rows by construction; '
                     'the question is whether the public data make that business visible.'),
        },
        'form_114_5_behested_contributions': {
            'description': 'Contributions of $5,000+/yr made to ballot-measure or independent-expenditure committees at the behest of a City elective officer (SFEC Form 114.5, C&GCC §1.114.5).',
            'n_rows': int(len(b1145)), 'total': float(b1145.amount.sum()), 'by_official': by_off_1145.to_dict('records'),
            'top_contributors': [{'contributor': k, 'total': float(v)} for k, v in top_1145.items()],
        },
        'waivers': {'n': int(len(waivers)), 'rows': waivers[['agency', 'subject', 'payor', 'date_of_waiver_approval']].to_dict('records')},
    }
    C.save('behested', summ)
    return summ


# --------------------------------------------------------------------------------------------- C. lobbying
def lobbying(C):
    l = C.edges[C.edges.edge_type == 'lobbying_contact'].copy()
    a = [json.loads(x) for x in l['attrs']]
    l['subject'] = [x.get('subject') for x in a]; l['issue'] = [x.get('issue') for x in a]
    l['file_number'] = [x.get('file_number') for x in a]; l['dept'] = [x.get('department') for x in a]
    l['lobbyist'] = [x.get('lobbyist') for x in a]
    l['year'] = l.date.dt.year
    l['target_type'] = l.target.map(C.ntype).fillna(pd.Series(np.where(l.target.str.startswith('STAFF:'), 'staff_group', 'official'), index=l.index))
    top_clients = l.groupby('source').agg(contacts=('date', 'size'), officials=('target', 'nunique'), first=('date', 'min'), last=('date', 'max')).reset_index().sort_values('contacts', ascending=False)
    top_clients['label'] = top_clients.source.map(C.lab)
    pay = C.edges[C.edges.edge_type == 'lobbying_payment']
    paid = pay.groupby('source').amount.sum()
    top_clients['payments_reported'] = top_clients.source.map(paid).fillna(0)
    named = l[l.target.str.startswith('O:')]
    top_off = named.groupby('target').agg(contacts=('date', 'size'), clients=('source', 'nunique')).reset_index().sort_values('contacts', ascending=False)
    top_off['label'] = top_off.target.map(C.lab)
    triples = named.groupby(['source', 'target', 'subject']).size().rename('contacts').reset_index().sort_values('contacts', ascending=False)
    triples['client'] = triples.source.map(C.lab); triples['official'] = triples.target.map(C.lab)
    subj = l.groupby('subject').size().sort_values(ascending=False)
    # outcomes 1: contracts after lobbying the same department (within 24 months after first contact)
    sc = C.edges[C.edges.edge_type.isin(['contract'])]
    dept_nodes = C.nodes[C.nodes.node_type == 'department'][['node_id', 'label']]
    first_contact = l.groupby('source').date.min()
    got = sc[sc.target.isin(first_contact.index)].copy()
    got['first_contact'] = got.target.map(first_contact)
    got = got[(got.date >= got.first_contact) & (got.date <= got.first_contact + pd.Timedelta(days=730))]
    clients = set(l.source.dropna())
    contract_clients = set(got.target)
    all_orgs_with_contracts = set(sc.target)
    # outcome 2: planning projects lobbied
    pp = pd.read_csv(os.path.join(RAW, 'planning_projects.csv'), low_memory=False)
    pp['base'] = pp.record_id.str[:11]
    fn = l.file_number.fillna('').astype(str).str.extract(r'((?:19|20)\d\d)[.\-](\d{6})')
    l['prj'] = (fn[0] + '-' + fn[1]).where(fn[0].notna())
    lob_prj = set(l.prj.dropna())
    ppl = pp.drop_duplicates('base').set_index('base')
    mp = ppl.loc[ppl.index.intersection(list(lob_prj))]
    dec = lambda s: s.fillna('').str.replace('Withdawn', 'Withdrawn').replace('', 'no decision recorded').value_counts().to_dict()
    decided = ppl[ppl.project_decision.isin(['Approved', 'Disapproved', 'Withdawn', 'Withdrawn', 'Cancelled'])]
    mp_dec = mp[mp.project_decision.isin(['Approved', 'Disapproved', 'Withdawn', 'Withdrawn', 'Cancelled'])]
    # outcome 3: Board of Supervisors legislative file numbers (6 digits) lobbied
    bos_files = l.file_number.fillna('').astype(str).str.extract(r'\b(\d{6})\b')[0].dropna()
    summ = {
        'n_contacts': int(len(l)), 'n_clients_resolved': int(l.source.nunique()), 'years': [int(l.year.min()), int(l.year.max())],
        'contacts_by_target_type': l.target_type.value_counts().to_dict(),
        'contacts_by_year': l.groupby('year').size().to_dict(),
        'top_clients': top_clients.head(30).to_dict('records'),
        'top_officials': top_off.head(30).to_dict('records'),
        'top_client_official_subject': triples.head(40).to_dict('records'),
        'subjects': subj.head(20).to_dict(),
        'outcome_contracts': {
            'description': 'Lobbying clients that received a Controller-recorded contract (any department) starting within 24 months after their first reported contact.',
            'n_clients': len(clients), 'n_with_contract_within_24m': len(contract_clients),
            'share': len(contract_clients) / max(len(clients), 1),
            'share_clients_with_any_contract_ever': len(clients & all_orgs_with_contracts) / max(len(clients), 1),
        },
        'outcome_planning': {
            'description': 'Planning project records (PRJ, Accela; qvu5-m3a2) whose record number appears in a lobbying contact. Most pre-2018 case numbers are not in this dataset.',
            'n_lobbied_projects_with_file_numbers': len(lob_prj), 'n_matched_to_planning_records': int(len(mp)),
            'decisions_lobbied': dec(mp.project_decision), 'decisions_all_projects': dec(ppl.project_decision),
            'approval_rate_lobbied_among_decided': float((mp_dec.project_decision == 'Approved').mean()) if len(mp_dec) else None,
            'approval_rate_all_among_decided': float((decided.project_decision == 'Approved').mean()),
            'caveat': 'Lobbied projects are larger and more complex than typical permit applications; approval rates are not comparable causally.',
        },
        'legislation': {'n_distinct_bos_file_numbers_lobbied': int(bos_files.nunique()),
                        'note': 'Board of Supervisors legislative outcomes are not available as machine-readable open data here (Legislation dataset cz9b-x8ed is a link-only entry), so legislative outcomes are not linked.'},
    }
    C.save('lobbying', summ)
    return summ


def lobbyist_contributions(C):
    """Contributions by (matched) registered lobbyists to city elective officers/candidates of agencies they contacted in the prior 90 days."""
    lob_c = C.edges[(C.edges.edge_type == 'contribution') & C.edges.source.str.startswith('L:')].copy()
    city_coms = C.com[C.com.is_city_candidate][['node_id', 'office']]
    lob_c = lob_c.merge(city_coms, left_on='target', right_on='node_id')
    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    lc['lob'] = 'L:' + lc.lobbyistname.map(m6.nk_from_lastfirst)
    lc['office'] = lc.departmentname.map(m6.dept_office)
    lc = lc.dropna(subset=['office'])
    by = {k: g for k, g in lc.groupby('lob')}
    rows = []
    for r in lob_c.itertuples():
        g = by.get(r.source)
        if g is None or pd.isna(r.date):
            continue
        prior = g[(g.office == r.office) & (g.date <= r.date) & (g.date >= r.date - pd.Timedelta(days=90))]
        rows.append(dict(lobbyist=C.lab(r.source), lobbyist_node=r.source, recipient=C.lab(r.target), office=r.office, date=r.date,
                         amount=r.amount, contacts_with_that_agency_prior_90d=len(prior), match_conf=r.match_conf, record_id=r.record_id))
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(C.out, 'lobbyist_contributions.parquet'), index=False)
    flagged = df[df.contacts_with_that_agency_prior_90d > 0] if len(df) else df
    selfrep = pd.read_parquet(os.path.join(INT, 'lobby_contribs.parquet'))
    summ = {'rule': RULES['lobbyist_contrib'], 'caveat': CAVEAT_TIMING + ' "Registered to lobby an agency" is approximated here by having reported a contact with that agency in the prior 90 days.',
            'n_matched_lobbyist_contributions_to_city_candidates': int(len(df)), 'amount': float(df.amount.sum()) if len(df) else 0,
            'n_with_contact_same_agency_prior_90d': int(len(flagged)), 'amount_flagged': float(flagged.amount.sum()) if len(flagged) else 0,
            'flagged_by_year': flagged.assign(y=flagged.date.dt.year).groupby('y').amount.agg(['size', 'sum']).reset_index().to_dict('records') if len(flagged) else [],
            'flagged_examples': flagged.sort_values('date', ascending=False).head(30).to_dict('records') if len(flagged) else [],
            'self_reported_contributions_rows': int(len(selfrep)), 'self_reported_total': float(pd.to_numeric(selfrep.amount, errors='coerce').sum())}
    # Red-team pass 2: the contribution ban is C&GCC §2.115(d)-(e), added by Proposition T (Nov. 8, 2016), operative 2018-01-01
    # (re-enacted by Proposition D, March 5, 2024, operative 2024-10-12). Split the proxy-flagged rows by the rule's operative date.
    if len(flagged):
        fl2 = flagged.copy()
        pre = fl2[fl2.date < '2018-01-01']; post = fl2[fl2.date >= '2018-01-01']
        pos_post = post[post.amount > 0]; neg_post = post[post.amount < 0]
        refunded = []
        for r in pos_post.itertuples():
            m = neg_post[(neg_post.lobbyist_node == r.lobbyist_node) & (neg_post.recipient == r.recipient) & (neg_post.date >= r.date)]
            refunded.append(bool(len(m)))
        summ['by_rule_period'] = {
            'rule': 'C&GCC §2.115(d) (Prop. T, 2016), operative 2018-01-01',
            'before_2018': {'n': int(len(pre)), 'n_positive': int((pre.amount > 0).sum()), 'amount': float(pre.amount.sum()),
                            'note': 'Before the ban was operative; lobbyists were then subject to disclosure and the general $500 limit.'},
            'from_2018': {'n_rows': int(len(post)), 'n_positive_contributions': int(len(pos_post)), 'positive_amount': float(pos_post.amount.sum()),
                          'n_refund_rows': int(len(neg_post)), 'refund_amount': float(neg_post.amount.sum()),
                          'positive_later_refunded_same_committee': int(sum(refunded)), 'net_amount': float(post.amount.sum()),
                          'last_date': str(post.date.max().date()) if len(post) else None},
            'proxy_note': ('"Registered to lobby the agency" is approximated by a reported contact with that agency in the prior 90 days; registration '
                           'covers more lobbyists than this proxy, so the counts are a floor for the pre-2018 pattern and say nothing about compliance.'),
        }
        summ['n_positive_from_2018_not_refunded'] = int(len(pos_post) - sum(refunded))
    C.save('lobbyist_contributions', summ)
    return summ


# --------------------------------------------------------------------------------------------- D. concentration
def concentration(C):
    c = C.contrib[(C.contrib.amount > 0) & ~C.contrib.is_committee_donor].copy()
    c['year'] = c.date.dt.year
    c = c[(c.year >= 2010) & (c.year <= 2026)]
    orgres = {k: C.R.ent.get(k) for k in c.org_key.unique() if k}
    c['donor_id'] = np.where(c.is_individual, 'IND:' + c.pid.fillna(''), c.org_key.map(orgres).fillna('ORGRAW:' + c.org_key))
    # candidate self-funding: individual donor whose name key equals the recipient committee's candidate
    cand_nk = C.com.set_index('node_id').candidate_name.map(lambda x: m6.nk_from_lastfirst(x) if isinstance(x, str) else '')
    c['self_funding'] = c.is_individual & (c.pid.fillna('').str.rsplit('|', n=1).str[0] == c.target.map(cand_nk).fillna('#'))
    selfsum = c[c.self_funding].groupby([c.date.dt.year, 'target']).amount.sum().reset_index()
    selfsum['committee'] = selfsum.target.map(C.lab)
    self_by_year = c[c.self_funding & c.is_city_candidate.fillna(False)].groupby('year').amount.sum()
    c = c[~c.self_funding]
    c['bucket'] = np.select([c.is_city_candidate.fillna(False), c.recip_kind.eq('ballot_measure'),
                             c.recip_kind.isin(['general_purpose', 'candidate_pf'])], ['city candidate committees', 'ballot measure committees',
                                                                                       'general-purpose / independent committees'], 'other')
    out = {}
    for b, g in c.groupby('bucket'):
        rows = []
        for y, gg in g.groupby('year'):
            tot = gg.groupby('donor_id').amount.sum().sort_values(ascending=False)
            n = len(tot)
            k1 = max(1, int(np.ceil(n * 0.01)))
            rows.append(dict(year=int(y), total=float(tot.sum()), n_donors=n, top1pct_share=float(tot.head(k1).sum() / tot.sum()),
                             top10_share=float(tot.head(10).sum() / tot.sum()), hhi=float(((tot / tot.sum()) ** 2).sum()),
                             share_from_organizations=float(tot[~tot.index.str.startswith('IND:')].sum() / tot.sum()),
                             share_contribs_under_100=float(gg[gg.amount < 100].amount.sum() / gg.amount.sum())))
        out[b] = rows
    # cycle-level (2-year windows ending in even years) for the top-donor table: organizations named, individuals aggregated
    top_orgs = c[~c.is_individual].groupby('donor_id').amount.sum().sort_values(ascending=False).head(40)
    top_orgs_list = [{'entity': k, 'label': C.lab(k), 'total': float(v)} for k, v in top_orgs.items()]
    ind_tot = c[c.is_individual].groupby('donor_id').amount.sum().sort_values(ascending=False)
    top_ind = {'top_10_individuals_total': float(ind_tot.head(10).sum()), 'top_100_individuals_total': float(ind_tot.head(100).sum()),
               'all_individuals_total': float(ind_tot.sum()), 'n_individual_donor_profiles': int(len(ind_tot)),
               'top_10_share_of_individual_money': float(ind_tot.head(10).sum() / ind_tot.sum()),
               'note': 'Private individuals are shown only in aggregate.'}
    # bundling-like employer clusters to city candidates: >=5 distinct employees of one org giving to the same committee within 14 days
    cc = c[c.is_city_candidate.fillna(False) & c.is_individual].copy()
    empres = {e: (None if is_non_employer(e) else C.R(e)[0]) for e in cc.employer.dropna().unique()}
    cc['emp_ent'] = cc.employer.map(empres)
    cc = cc.dropna(subset=['emp_ent', 'date'])
    clusters = []
    for (emp, com), g in cc.groupby(['emp_ent', 'target']):
        if g.pid.nunique() < 5:
            continue
        g = g.sort_values('date')
        d = g.date.values
        pids = g.pid.values
        amts = g.amount.values
        j = 0
        best = (0, None, None, 0.0)
        for i in range(len(g)):
            while d[i] - d[j] > np.timedelta64(14, 'D'):
                j += 1
            n = len(set(pids[j:i + 1]))
            if n > best[0]:
                best = (n, d[j], d[i], float(amts[j:i + 1].sum()))
        if best[0] >= 5:
            clusters.append(dict(employer_entity=emp, employer=C.lab(emp), committee=C.lab(com), committee_node=com,
                                 official=C.lab(C.com_official.get(com, '')), n_employees_14d=best[0], start=pd.Timestamp(best[1]),
                                 end=pd.Timestamp(best[2]), amount_14d=best[3], n_employees_total=int(g.pid.nunique()), amount_total=float(g.amount.sum())))
    cl = pd.DataFrame(clusters).sort_values('n_employees_14d', ascending=False) if clusters else pd.DataFrame()
    cl.to_parquet(os.path.join(C.out, 'employer_clusters.parquet'), index=False)
    f125 = pd.read_parquet(os.path.join(INT, 'f125.parquet'))
    # independent expenditures on city candidates
    ie = C.edges[C.edges.edge_type == 'independent_expenditure'].copy()
    ie['so'] = [json.loads(a).get('support_oppose') for a in ie['attrs']]
    ie['year'] = ie.date.dt.year
    # Red-team pass 2: some Form 496 items appear twice (the same transaction re-filed on a second original 24-hour report).
    # Drop exact repeats (same filer, transaction id, amount, date and payee name), keeping the latest filing.
    raw = pd.read_csv(os.path.join(RAW, 'cf_transactions.csv'), dtype=str,
                      usecols=lambda c_: c_ in ('filing_date', 'filer_nid', 'form_type', 'transaction_id', 'calculated_amount', 'calculated_date', 'element_nid', 'transaction_last_name'))
    raw = raw[raw.form_type == 'F496']
    keep_el = set(raw.sort_values('filing_date').drop_duplicates(['filer_nid', 'transaction_id', 'calculated_amount', 'calculated_date', 'transaction_last_name'], keep='last').element_nid)
    ie_dups = ie[~ie.record_id.isin(keep_el) & ie.record_id.isin(set(raw.element_nid))]
    ie_dup_by_year = ie_dups.groupby('year').amount.sum()
    ie = ie[~ie.index.isin(ie_dups.index)]
    ie_city = ie[ie.target.isin(set(C.offs[C.offs.category == 'candidate_or_elected'].official_id))]
    ie_by_year = ie_city.groupby('year').amount.sum()
    cand_by_year = c[c.bucket == 'city candidate committees'].groupby('year').amount.sum()
    top_ie = ie_city.groupby('source').amount.sum().sort_values(ascending=False).head(20)
    # who funds the top IE committees
    fund = C.edges[(C.edges.edge_type == 'contribution') & C.edges.target.isin(top_ie.index)]
    ie_funders = fund.groupby('source').amount.sum().sort_values(ascending=False).head(25)
    ind_to_ie = C.contrib[C.contrib.target.isin(top_ie.index) & C.contrib.is_individual].amount.sum()
    summ = {'by_bucket_year': out, 'note': 'Candidate self-funding (a candidate giving or lending to their own committee) is excluded from these shares and reported separately.',
            'candidate_self_funding_city_by_year': {int(k): float(v) for k, v in self_by_year.items()},
            'largest_self_funding': selfsum.sort_values('amount', ascending=False).head(10)[['date', 'committee', 'amount']].rename(columns={'date': 'year'}).to_dict('records'),
            'top_organization_donors_2010_2026': top_orgs_list, 'individuals': top_ind,
            'employer_clusters': {'definition': '5+ distinct individual donors naming the same employer who gave to the same city candidate committee within 14 days',
                                  'n_clusters': int(len(cl)), 'top': cl.head(30).to_dict('records') if len(cl) else [],
                                  'form125_disclosed_bundled_rows': int(len(f125)),
                                  'caveat': 'Coworkers giving together is common (fundraisers, shared politics) and is not evidence that anyone bundled or reimbursed contributions.'},
            'independent_expenditures': {'ie_on_city_candidates_by_year': {int(k): float(v) for k, v in ie_by_year.items()},
                                         'candidate_committee_receipts_by_year': {int(k): float(v) for k, v in cand_by_year.items()},
                                         'top_ie_committees': [{'committee': C.lab(k), 'node': k, 'amount': float(v)} for k, v in top_ie.items()],
                                         'top_funders_of_top_ie_committees': [{'funder': C.lab(k), 'node': k, 'amount': float(v)} for k, v in ie_funders.items() if not str(k).startswith('PP:')],
                                         'private_individuals_to_top_ie_committees_total': float(ind_to_ie),
                                         'duplicate_f496_items_removed_by_year': {int(k): float(v) for k, v in ie_dup_by_year.items()},
                                         'note': ('IE totals come from Form 496 (24-hour) reports filed by the spending committee, after removing items re-filed on a '
                                                  'second original report; amounts are nominal. Form 496 covers expenditures made in the final 90 days before an '
                                                  'election; earlier independent spending appears only on Form 460/465 and is not included, so these totals are a floor.')}}
    C.save('concentration', summ)
    return summ


# --------------------------------------------------------------------------------------------- E. nonprofit loop
def nonprofit_loop(C):
    ents = pd.read_parquet(os.path.join(ER, 'org_entities.parquet'))
    vp = C.edges[C.edges.edge_type == 'vendor_payment'].copy()
    vp['np'] = [json.loads(a).get('nonprofit') for a in vp['attrs']]
    np_ents = set(vp[vp.np == True].target) | set(ents[ents.np_flag].entity_default)
    gov = set(ents[ents.type == 'government'].entity_default)
    tp = os.path.join(ER, 'entity_types.parquet')
    if os.path.exists(tp):
        et = pd.read_parquet(tp)
        gov |= set(et[et.llm_type == 'government'].node_id)
    gov |= {e for e in np_ents if re.search(r'REGENTS|UNIVERSITY OF CALIFORNIA|CITY COLLEGE|STATE OF|COUNTY OF|UNIFIED SCHOOL', str(C.lab(e)).upper())}
    np_ents -= gov
    if os.path.exists(tp):
        np_ents -= set(et[et.llm_type.isin(['company', 'government'])].node_id)
    np_ents = {e for e in np_ents if not re.search(r'HEALTH PLAN|DENTAL PLAN|BLUE SHIELD|VISION SERVICE PLAN|\bJV\b|JOINT VENTURE|CONSTRUCTION', str(C.lab(e)).upper())}
    funding = vp[vp.target.isin(np_ents)].groupby('target').amount.sum()
    funding = funding[funding >= 100000]
    appr = C.edges[(C.edges.edge_type == 'contract_approval') & C.edges.target.isin(funding.index)]
    bos_mayor_appr = appr[appr.source.isin(['BODY:Board of Supervisors', 'BODY:Mayor'])]
    beh_in = C.edges[(C.edges.edge_type == 'behested_payment') & C.edges.target.isin(funding.index)]
    lob = C.edges[(C.edges.edge_type == 'lobbying_contact') & C.edges.source.isin(funding.index)]
    city_coms = set(C.com[C.com.is_city_candidate & C.com.office.isin(['Mayor', 'Board of Supervisors'])].node_id)
    ctl = C.edges[C.edges.edge_type == 'controls']
    for t, s in zip(ctl.target, ctl.source):
        if C.official_offices.get(s, set()) & {'Mayor', 'Board of Supervisors'}:
            city_coms.add(t)
    # principals of these nonprofits (listed on 126f4) matched to donors, giving to Mayor/BOS committees
    pm = C.pm[(C.pm.kind == 'principal') & (C.pm.decision == 'same') & (C.pm.confidence >= C.person_t)].copy()
    pm['ent'] = pm.role_id.str.split('|', n=2).str[-1].map(C.R.ent)
    pm = pm[pm.ent.isin(funding.index)]
    ind = C.contrib[C.contrib.is_individual & C.contrib.pid.isin(set(pm.pid)) & C.contrib.target.isin(city_coms)]
    pid2ent = pm.groupby('pid').ent.agg(lambda s: set(s))
    prin_give = {}
    prin_n = {}
    for r in ind.itertuples():
        for e in pid2ent.get(r.pid, set()):
            prin_give[e] = prin_give.get(e, 0) + r.amount
            prin_n.setdefault(e, set()).add(r.pid)
    org_give = C.edges[(C.edges.edge_type == 'contribution') & C.edges.source.isin(funding.index) & C.edges.target.isin(city_coms)].groupby('source').amount.sum()
    emp_give = C.edges[(C.edges.edge_type == 'employee_giving') & C.edges.source.isin(funding.index) & C.edges.target.isin(city_coms)]
    emp_amt = emp_give.groupby('source').amount.sum()
    rows = []
    for e, fund in funding.items():
        rows.append(dict(entity=e, label=C.lab(e), city_payments_fy2016_on=float(fund),
                         n_126f4_approvals_bos_mayor=int((bos_mayor_appr.target == e).sum()),
                         behested_received=float(beh_in[beh_in.target == e].amount.sum()),
                         behested_requesting_officials=', '.join(sorted(set(C.lab(x) for x in beh_in[beh_in.target == e].official.dropna()))),
                         lobbying_contacts=int((lob.source == e).sum()),
                         principal_giving_to_mayor_bos=float(prin_give.get(e, 0)), n_principals_giving=len(prin_n.get(e, set())),
                         org_giving_to_mayor_bos=float(org_give.get(e, 0)), employee_giving_to_mayor_bos=float(emp_amt.get(e, 0))))
    df = pd.DataFrame(rows)
    df['any_political_link'] = (df.principal_giving_to_mayor_bos > 0) | (df.org_giving_to_mayor_bos > 0) | (df.behested_received > 0)
    df.to_parquet(os.path.join(C.out, 'nonprofit_loop.parquet'), index=False)
    summ = {
        'description': ('Nonprofits (flagged nonprofit in Controller data) receiving $100k+ in city vendor payments since FY2016, and whether (a) their '
                        'disclosed principals (board members/officers on 126f4 forms, matched to donors) or the organization gave to Mayor or '
                        'Board of Supervisors committees, (b) they received behested payments, (c) they lobbied. Descriptive only.'),
        'caveat': ('Nonprofit board members are often civically active and give to many candidates; giving by an unpaid board member is personal '
                   'and legal unless it falls within §1.126 windows (contracts requiring elective-officer approval). Nothing here implies that funding decisions were influenced.'),
        'n_nonprofits_funded_100k': int(len(df)), 'total_payments': float(df.city_payments_fy2016_on.sum()),
        'n_with_principal_giving': int((df.principal_giving_to_mayor_bos > 0).sum()),
        'principal_giving_total': float(df.principal_giving_to_mayor_bos.sum()),
        'n_with_org_giving': int((df.org_giving_to_mayor_bos > 0).sum()),
        'n_receiving_behested': int((df.behested_received > 0).sum()), 'behested_total': float(df.behested_received.sum()),
        'n_lobbying': int((df.lobbying_contacts > 0).sum()),
        'share_of_funding_to_nonprofits_with_principal_giving': float(df[df.principal_giving_to_mayor_bos > 0].city_payments_fy2016_on.sum() / df.city_payments_fy2016_on.sum()) if len(df) else None,
        'top_by_principal_giving': df.sort_values('principal_giving_to_mayor_bos', ascending=False).head(20).to_dict('records'),
        'top_behested_recipients_with_city_funding': df.sort_values('behested_received', ascending=False).head(15).to_dict('records'),
    }
    C.save('nonprofit_loop', summ)
    return summ


# --------------------------------------------------------------------------------------------- F. reforms
def reforms(C, cases):
    e = C.edges
    y = lambda s: s.dt.year
    beh = e[e.edge_type == 'behested_payment'].copy()
    beh['form'] = [json.loads(a).get('form') for a in beh['attrs']]
    beh['payee_raw'] = [json.loads(a).get('payee_raw') or '' for a in beh['attrs']]
    beh = beh[~beh.payee_raw.str.upper().str.contains('SEE ATTACHED')]
    beh['dupkey'] = beh.official.astype(str) + '|' + beh.source.astype(str) + '|' + beh.target.astype(str) + '|' + beh.date.astype(str)
    beh = beh.drop_duplicates('dupkey', keep='last')
    series = {'behested_note': ('Excludes the 49 ambiguous DCYF Summer Together rows (2021) and duplicate original/supplemental rows. The SFEC 3610(b) '
                                'datasets on DataSF are marked [Historical] and were last updated in March 2024, so the absence of rows after 2023 may '
                                'reflect a change in publication, not a drop in behested payments.')}
    series['behested_3610b_by_year'] = beh[beh.form.str.contains('3610', na=False)].groupby(y(beh.date)).amount.agg(['size', 'sum']).reset_index().to_dict('records')
    series['behested_803_by_year'] = beh[beh.form.str.contains('803', na=False)].groupby(y(beh.date)).amount.agg(['size', 'sum']).reset_index().to_dict('records')
    f = pd.read_parquet(os.path.join(INT, 'f126.parquet'))
    series['f126f4_filings_by_year'] = f.groupby(f.date_signed.dt.year).size().to_dict()
    lc = e[e.edge_type == 'lobbying_contact']
    series['lobbying_contacts_by_year'] = lc.groupby(y(lc.date)).size().to_dict()
    lp = e[e.edge_type == 'lobbying_payment']
    series['lobbying_payments_by_year'] = lp.groupby(y(lp.date)).amount.sum().to_dict()
    if len(cases):
        post = cases[cases.days_from_approval > 0]
        series['post_approval_window_contributions_by_approval_year'] = post.groupby(post.approval_proxy_date.dt.year).amount.agg(['size', 'sum']).reset_index().to_dict('records')
    f1145 = pd.read_parquet(os.path.join(INT, 'f1145.parquet'))
    f1145['d'] = pd.to_datetime(f1145.contributiondate.astype(str).str[:10], errors='coerce')
    series['form_114_5_by_year'] = f1145.groupby(f1145.d.dt.year).apply(lambda g: pd.to_numeric(g.contributionamount, errors='coerce').sum()).to_dict()
    # share of city-candidate money from contractor-affiliated sources (126f4 contractor entity, matched principals, or their employees) by year
    c = C.contrib[C.contrib.is_city_candidate.fillna(False) & (C.contrib.amount > 0)].copy()
    c['year'] = c.date.dt.year
    cand_nk = C.com.set_index('node_id').candidate_name.map(lambda x: m6.nk_from_lastfirst(x) if isinstance(x, str) else '')
    c = c[~(c.is_individual & (c.pid.fillna('').str.rsplit('|', n=1).str[0] == c.target.map(cand_nk).fillna('#')))]  # drop self-funding
    f['ent'] = [C.R(x)[0] for x in f.contractor]
    cents = set(f.ent.dropna())
    pm = C.pm[(C.pm.kind == 'principal') & (C.pm.decision == 'same') & (C.pm.confidence >= C.person_t)]
    ppids = set(pm.pid)
    empres = {x: (None if is_non_employer(x) else C.R(x)[0]) for x in c.employer.dropna().unique()}
    c['emp_ent'] = c.employer.map(empres)
    orgres = {k: C.R.ent.get(k) for k in c.org_key.unique() if k}
    c['org_ent'] = c.org_key.map(orgres)
    c['src'] = np.select([c.org_ent.isin(cents), c.pid.isin(ppids), c.emp_ent.isin(cents)], ['contractor entity', 'listed principal', 'contractor employee'], 'other')
    tab = c[(c.year >= 2012) & (c.year <= 2026)].pivot_table(index='year', columns='src', values='amount', aggfunc='sum', fill_value=0)
    tab = tab.div(tab.sum(axis=1), axis=0)
    series['city_candidate_money_share_by_source'] = {int(k): {kk: float(vv) for kk, vv in v.items()} for k, v in tab.iterrows()}
    periods = {'2015-2018': (2015, 2018), '2019-2020': (2019, 2020), '2021-2025': (2021, 2025)}
    comp = {}
    for p, (a, b) in periods.items():
        sub = c[(c.year >= a) & (c.year <= b)]
        comp[p] = {k: float(v) for k, v in (sub.groupby('src').amount.sum() / max(sub.amount.sum(), 1)).items()}
    summ = {'series': series, 'contractor_affiliated_share_by_period': comp,
            'context': ('Reforms in scope: the 2019 rewrite of the contractor contribution ban (window from proposal to 12 months after approval; '
                        'principals and subcontractors covered; new 126f2/126f4 notices) and the land-use contribution ban (§1.127); Mayoral Executive '
                        'Directive 20-02 (Sept. 24, 2020) extending behested-payment filing to department heads; and the behested-payment solicitation '
                        'ban (§3.620) with interested-party definitions and later exceptions/waivers. Dates of ordinances should be confirmed against the '
                        'enacted text; see DATA_NOTES.md.'),
            'caveat': 'Year-to-year changes also reflect the election calendar (mayoral years), filing-system changes, and the pandemic; before/after differences are not causal estimates.'}
    C.save('reforms', summ)
    return summ


def summary_numbers(C):
    e = C.edges
    out = {'edge_counts': e.edge_type.value_counts().to_dict(), 'node_counts': C.nodes.node_type.value_counts().to_dict()}
    c = C.contrib
    out['contributions_rows'] = int(len(c)); out['contributions_total'] = float(c.amount.sum())
    out['contributions_2015_2026_total'] = float(c[(c.date >= '2015-01-01')].amount.sum())
    C.save('summary_numbers', out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='default'); ap.add_argument('--person-t', type=float, default=0.8); ap.add_argument('--tag', default='')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    outdir = os.path.join(HERE, '..', 'data', 'analysis', a.tag) if a.tag else os.path.join(HERE, '..', 'data', 'analysis')
    C = Ctx(a.variant, a.person_t, outdir)
    only = set(a.only.split(',')) if a.only else None
    run = lambda n: only is None or n in only
    cases, f, allc = contractor_ban(C) if run('ban') or run('reforms') else (pd.DataFrame(), None, None)
    if run('ban'):
        contractor_base_rates(C, f, cases, allc); print('ban done', len(cases))
    if run('behested'):
        behested(C); print('behested done')
    if run('lobbying'):
        lobbying(C); lobbyist_contributions(C); print('lobbying done')
    if run('concentration'):
        concentration(C); print('concentration done')
    if run('nonprofit'):
        nonprofit_loop(C); print('nonprofit done')
    if run('reforms'):
        reforms(C, cases); print('reforms done')
    summary_numbers(C)


if __name__ == '__main__':
    main()
