"""Collect organization-name mentions across all sources and generate candidate match pairs.

Outputs (data/er/):
  org_mentions.parquet   one row per (source, org_key) with raw-name examples, amounts, locations
  org_keys.parquet       one row per org_key (union over sources) with per-source flags
  org_pairs.parquet      candidate pairs of distinct org_keys with string-similarity features and a rule decision
"""
import os, re, collections, math
import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from names import org_key, is_non_employer, basic, zip5

HERE = os.path.dirname(os.path.abspath(__file__))
INT = os.path.join(HERE, '..', 'data', 'interim')
ER = os.path.join(HERE, '..', 'data', 'er')
os.makedirs(ER, exist_ok=True)

# extra abbreviation expansions seen in Controller vendor names (truncated, abbreviated)
ABBR = [(r'\bCALIF\b', 'CALIFORNIA'), (r'\bCNTY\b', 'COUNTY'), (r'\bSVCS?\b', 'SERVICE'), (r'\bCMNTY\b', 'COMMUNITY'),
        (r'\bHSG\b', 'HOUSING'), (r'\bCONSTR?S?\b', 'CONSTRUCTION'), (r'\bCONSTRUCTORS\b', 'CONSTRUCTION'),
        (r'\bBLDRS\b', 'BUILDERS'), (r'\bENGRG\b', 'ENGINEERING'), (r'\bENGRS\b', 'ENGINEERS'), (r'\bMGMT\b', 'MGMT'),
        (r'\bHLTH\b', 'HEALTH'), (r'\bHOSP\b', 'HOSPITAL'), (r'\bUNIV\b', 'UNIV'), (r'\bDEPT\b', 'DEPT'),
        (r'\bAMER\b', 'AMERICA'), (r'\bNATL\b', 'NATL'), (r'\bTRANS\b', 'TRANSPORTATION'), (r'\bENVIRON\b', 'ENVIRONMENTAL'),
        (r'\bJT VENTURE\b', 'JV'), (r'\bJOINT VENTURE\b', 'JV'), (r'\bCNST\b', 'CONSTRUCTION')]
ABBR = [(re.compile(a), b) for a, b in ABBR]


def key2(s):
    k = org_key(s)
    for rx, rep in ABBR:
        k = rx.sub(rep, k)
    return re.sub(r'\s+', ' ', k).strip()


def add(rows, src, names, amount=None, city=None, state=None, zipc=None, extra=None):
    df = pd.DataFrame({'raw': names})
    df['amount'] = amount if amount is not None else 0.0
    df['city'] = city if city is not None else ''
    df['state'] = state if state is not None else ''
    df['zip5'] = [zip5(z) for z in zipc] if zipc is not None else ''
    df['extra'] = extra if extra is not None else ''
    df = df[df.raw.notna() & (df.raw.astype(str).str.strip() != '')]
    df['src'] = src
    rows.append(df)


def collect():
    rows = []
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'),
                        columns=['is_individual', 'donor_last', 'employer', 'amount', 'city', 'state', 'zip5', 'is_committee_donor', 'date'])
    o = c[~c.is_individual]
    add(rows, 'cf_org_donor', o.donor_last.values, o.amount.values, o.city.values, o.state.values, o.zip5.values,
        np.where(o.is_committee_donor, 'committee', ''))
    e = c[c.is_individual & (c.employer.str.strip() != '')]
    e = e[~e.employer.map(is_non_employer)]
    add(rows, 'cf_employer', e.employer.values, e.amount.values, e.city.values, e.state.values, e.zip5.values)
    del c
    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))
    add(rows, 'lobby_client', lc.clientname.values)
    lp = pd.read_parquet(os.path.join(INT, 'lobby_payments.parquet'))
    add(rows, 'lobby_client', lp.clientname.values, lp.amount.fillna(0).values, lp.clientcity.fillna('').map(basic).values,
        lp.clientstate.fillna('').values, lp.clientzip.fillna('').values)
    add(rows, 'lobby_firm', pd.concat([lc.firmname, lp.firmname]).dropna().values)
    bp = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    add(rows, 'bp_payor', bp.payor.values, bp.amount.fillna(0).values)
    add(rows, 'bp_payee', bp.payee.values, bp.amount.fillna(0).values)
    f = pd.read_parquet(os.path.join(INT, 'f126.parquet'))
    add(rows, 'f126_contractor', f.contractor.values, f.contract_amount.fillna(0).values)
    p = pd.read_parquet(os.path.join(INT, 'f126_parties.parquet'))
    sub = p[~p.is_person]
    add(rows, 'f126_subcontractor', sub['last'].values)
    f2 = pd.read_parquet(os.path.join(INT, 'f126f2.parquet'))
    add(rows, 'f126f2_party', f2.contractorname.values)
    s = pd.read_parquet(os.path.join(INT, 'contracts.parquet'))
    add(rows, 'sc_prime', s.prime_contractor.values, s.agreed_amt.fillna(0).values, extra=s.non_profit.fillna('').values)
    add(rows, 'sc_supplier', s.project_team_supplier.values, s.agreed_amt.fillna(0).values, extra=s.non_profit.fillna('').values)
    v = pd.read_parquet(os.path.join(INT, 'vendor_pay.parquet'))
    v = v[v.fiscal_year >= 2016]
    vg = v.groupby('vendor').agg(paid=('paid', 'sum'), np_=('non_profit_indicator', lambda s: 'X' if (s == 'X').any() else '')).reset_index()
    vg = vg[vg.paid >= 25000]
    add(rows, 'vendor', vg.vendor.values, vg.paid.values, extra=vg.np_.values)
    f124 = pd.read_parquet(os.path.join(INT, 'f124_filings.parquet'))
    add(rows, 'f124_entity', f124.businessentityname.values, pd.to_numeric(f124.contributiontotal, errors='coerce').fillna(0).values,
        f124.businessentitycity.fillna('').map(basic).values, f124.businessentitystate.fillna('').values, f124.businessentityzip.fillna('').values)
    d = pd.read_parquet(os.path.join(INT, 'dev_3500.parquet'))
    add(rows, 'dev_3500', d.developername.values)
    m = pd.read_parquet(os.path.join(INT, 'f1145.parquet'))
    add(rows, 'f1145_contributor', m.contributorname.values, pd.to_numeric(m.contributionamount, errors='coerce').fillna(0).values)
    com = pd.read_parquet(os.path.join(INT, 'committees.parquet'))
    add(rows, 'committee', com.filer_name.values, extra=com.filer_nid.astype(str).values)
    allm = pd.concat(rows, ignore_index=True)
    allm['raw'] = allm.raw.astype(str).str.strip()
    # compute keys once per distinct raw string
    uniq = pd.Series(allm.raw.unique())
    kmap = dict(zip(uniq, uniq.map(key2)))
    allm['key'] = allm.raw.map(kmap)
    allm = allm[allm.key.str.len() >= 2]
    return allm


def summarize(allm):
    g = allm.groupby(['src', 'key'])
    ms = g.agg(n=('raw', 'size'), amount=('amount', 'sum')).reset_index()
    ex = allm.groupby(['src', 'key']).raw.agg(lambda s: ' | '.join(s.value_counts().index[:3])).rename('examples').reset_index()
    loc = allm[allm.city.astype(str) != ''].groupby(['src', 'key']).city.agg(lambda s: ' | '.join(s.value_counts().index[:2])).rename('cities').reset_index()
    zp = allm[allm.zip5.astype(str) != ''].groupby(['src', 'key']).zip5.agg(lambda s: ' | '.join(s.value_counts().index[:2])).rename('zips').reset_index()
    xt = allm[allm.extra.astype(str) != ''].groupby(['src', 'key']).extra.agg(lambda s: ' | '.join(s.astype(str).value_counts().index[:2])).rename('extra').reset_index()
    ms = ms.merge(ex, on=['src', 'key']).merge(loc, on=['src', 'key'], how='left').merge(zp, on=['src', 'key'], how='left').merge(xt, on=['src', 'key'], how='left')
    return ms


ANCHOR_SRCS = {'cf_org_donor', 'lobby_client', 'bp_payor', 'bp_payee', 'f126_contractor', 'f126_subcontractor', 'f126f2_party',
               'sc_prime', 'sc_supplier', 'vendor', 'f124_entity', 'dev_3500', 'f1145_contributor', 'lobby_firm'}


def keys_table(ms):
    piv = ms.pivot_table(index='key', columns='src', values='n', aggfunc='sum', fill_value=0)
    amt = ms.pivot_table(index='key', columns='src', values='amount', aggfunc='sum', fill_value=0)
    kt = pd.DataFrame(index=piv.index)
    kt['srcs'] = piv.apply(lambda r: ','.join(sorted(c for c in piv.columns if r[c] > 0)), axis=1)
    kt['n_total'] = piv.sum(axis=1)
    kt['emp_n'] = piv.get('cf_employer', 0)
    kt['emp_amount'] = amt.get('cf_employer', 0)
    kt['is_anchor'] = kt.srcs.map(lambda s: any(x in ANCHOR_SRCS for x in s.split(',')))
    ex = ms.sort_values('n', ascending=False).groupby('key').examples.first()
    kt['example'] = ex
    kt = kt.reset_index()
    return kt


STOP = set('SF CITY COUNTY OF THE FOR AND INC CALIFORNIA CA GROUP SERVICE ASSN COMMUNITY CENTER FDN COMMITTEE PAC LOCAL '
           'NORTHERN BAY AREA AMERICA US NATL INTL COUNCIL HOUSING DEV MGMT PARTNERS HOLDING TRUST FUND UNION ST CO'.split())


def candidate_pairs(kt):
    # eligible: anchors, plus employer keys with some weight
    elig = kt[kt.is_anchor | (kt.emp_n >= 3) | (kt.emp_amount >= 1000)].copy()
    keys = elig.key.tolist()
    anchor = set(elig.key[elig.is_anchor])
    toks = {k: set(k.split()) for k in keys}
    df = collections.Counter(t for k in keys for t in toks[k])
    inv = collections.defaultdict(list)
    for k in keys:
        for t in toks[k]:
            if df[t] <= 400 and t not in STOP and len(t) >= 2:
                inv[t].append(k)
    pairs = {}
    for a in anchor:
        cands = set()
        for t in toks[a]:
            if t in inv:
                cands.update(inv[t])
        for b in cands:
            if b == a:
                continue
            key = (a, b) if a < b else (b, a)
            if key in pairs:
                continue
            r = fuzz.ratio(a, b)
            ts = fuzz.token_sort_ratio(a, b)
            tset = fuzz.token_set_ratio(a, b)
            if max(r, ts) >= 85 or tset >= 95:
                shared = toks[a] & toks[b]
                idf = sum(math.log(len(keys) / df[t]) for t in shared)
                pairs[key] = (r, ts, tset, idf)
    rows = [dict(a=k[0], b=k[1], ratio=v[0], tsort=v[1], tset=v[2], shared_idf=v[3]) for k, v in pairs.items()]
    pr = pd.DataFrame(rows)
    return pr


ROMAN = {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XX', 'XXI', 'XXII'}


def digits(s):
    return tuple(re.findall(r'\d+', s)) + tuple(t for t in s.split() if t in ROMAN)


def prune(pr, kt):
    """Drop pairs that cannot be useful or are near-certainly distinct (logged with a reason)."""
    srcs = kt.set_index('key').srcs.to_dict()
    ntok = lambda k: len(k.split())
    drop = []
    for r in pr.itertuples():
        sa, sb = set(srcs[r.a].split(',')), set(srcs[r.b].split(','))
        short, long_ = (r.a, r.b) if len(r.a) <= len(r.b) else (r.b, r.a)
        reason = ''
        # committee names only matter when matched against organizational donors (committee-to-committee transfers)
        if (sa == {'committee'} and not (sb & {'cf_org_donor'})) or (sb == {'committee'} and not (sa & {'cf_org_donor'})):
            reason = 'committee vs non-donor'
        elif ntok(short) == 1 and r.ratio < 60 and len(short) < 6:
            reason = 'short single-token subset'
        elif ntok(short) == 1 and r.ratio < 45:
            reason = 'single-token subset of much longer name'
        elif ('FOR' in long_.split() and ('SUPERVISOR' in long_ or 'BOARD' in long_ or 'MAYOR' in long_ or 'ATTORNEY' in long_)
              and ('cf_employer' in (sa | sb)) and ntok(short) <= 2 and r.ratio < 70):
            reason = 'candidate committee vs employer string'
        drop.append(reason)
    pr['prune_reason'] = drop
    return pr


def rule_decide(pr):
    dec, conf, why = [], [], []
    for r in pr.itertuples():
        if getattr(r, 'prune_reason', ''):
            dec.append('pruned'); conf.append(None); why.append(r.prune_reason); continue
        da, db = digits(r.a), digits(r.b)
        short = min(len(r.a), len(r.b))
        if da != db and (da or db):
            dec.append('llm'); conf.append(None); why.append('numbers differ')
        elif r.ratio >= 96 and short >= 8:
            dec.append('same'); conf.append(0.93); why.append(f'near-identical normalized names (ratio {r.ratio:.0f})')
        elif r.tsort >= 98 and short >= 8:
            dec.append('same'); conf.append(0.92); why.append('same tokens in different order')
        else:
            dec.append('llm'); conf.append(None); why.append('grey zone')
    pr['rule_decision'] = dec; pr['rule_conf'] = conf; pr['rule_why'] = why
    return pr


def main():
    allm = collect()
    print('mentions', len(allm))
    ms = summarize(allm)
    ms.to_parquet(os.path.join(ER, 'org_mentions.parquet'), index=False)
    kt = keys_table(ms)
    kt.to_parquet(os.path.join(ER, 'org_keys.parquet'), index=False)
    print('distinct keys', len(kt), 'anchors', kt.is_anchor.sum())
    pr = candidate_pairs(kt)
    pr = prune(pr, kt)
    pr = rule_decide(pr)
    # attach source info for the pair
    srcs = kt.set_index('key').srcs
    pr['a_srcs'] = pr.a.map(srcs); pr['b_srcs'] = pr.b.map(srcs)
    pr['cross_source'] = [len(set(x.split(',')) ^ set(y.split(','))) > 0 or set(x.split(',')) != {'cf_employer'} for x, y in zip(pr.a_srcs, pr.b_srcs)]
    pr.to_parquet(os.path.join(ER, 'org_pairs.parquet'), index=False)
    print('pairs', len(pr)); print(pr.rule_decision.value_counts())


if __name__ == '__main__':
    main()
