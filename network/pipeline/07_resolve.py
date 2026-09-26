"""Cluster organization keys into canonical entities using rule + Claude pair decisions.

Thresholds: an edge merges two keys when relation == 'same' and confidence >= T.
We build three variants: T=0.70 (lenient), T=0.80 (default), T=0.90 (strict), used for sensitivity analysis.
'family' judgments (parent/subsidiary, PAC of an org, union locals) link entities into families but never merge them.

Outputs data/er/org_entity_map.parquet (one row per key) and data/er/org_entities.parquet (one row per default entity).
"""
import os, re, hashlib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')
THRESHOLDS = {'lenient': 0.70, 'default': 0.80, 'strict': 0.90}


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def eid(prefix, key):
    return prefix + hashlib.md5(key.encode()).hexdigest()[:10]


UNION_RX = re.compile(r'\b(LOCAL|UNION|BROTHERHOOD|TEAMSTERS|SEIU|AFL CIO|AFSCME|IBEW|UNITE HERE|LABORERS|CARPENTERS|PLUMBERS|PIPEFITTERS|'
                      r'ELECTRICAL WORKERS|OPERATING ENGINEERS|FIREFIGHTERS|POLICE OFFICERS ASSN|DEPUTY SHERIFFS|NURSES ASSN|TRADES COUNCIL|LABOR COUNCIL|FEDERATION OF TEACHERS|IFPTE)\b')
PAC_RX = re.compile(r'\b(PAC|POLITICAL ACTION|COMMITTEE|COPE|FOR SUPERVISOR|FOR MAYOR|YES ON|NO ON|INDEPENDENT EXPENDITURE|BALLOT|DEMOCRATIC CLUB|REPUBLICAN)\b')
GOV_RX = re.compile(r'^(CITY OF|COUNTY OF|STATE OF|CITY AND COUNTY|US DEPT|CALIFORNIA DEPT|DEPT OF)|\b(REGENTS OF|UNIFIED SCHOOL DISTRICT|TRANSIT DISTRICT|WATER DISTRICT|HOUSING AUTHORITY|TRANSPORTATION AUTHORITY|STATE OF CALIFORNIA|SUPERIOR COURT)\b')
NP_RX = re.compile(r'\b(FDN|FUND|CHARIT|MINISTR|CHURCH|COMMUNITY|COALITION|ALLIANCE|SOCIETY|INSTITUTE|MUSEUM|SYMPHONY|OPERA|BALLET|CLINIC|SHELTER|YMCA|YWCA|BOYS AND GIRLS|NEIGHBORHOOD|COUNCIL|CENTER FOR|SCHOOL|ACADEMY|LEGAL AID|PROJECT)\b')


def classify(key, srcs, np_flag):
    s = set(srcs.split(','))
    if 'committee' in s or PAC_RX.search(key):
        return 'political committee'
    if UNION_RX.search(key):
        return 'labor organization'
    if GOV_RX.search(key):
        return 'government'
    if np_flag:
        return 'nonprofit'
    if NP_RX.search(key):
        return 'likely nonprofit'
    return 'company or other organization'


def main():
    kt = pd.read_parquet(os.path.join(ER, 'org_keys.parquet'))
    ms = pd.read_parquet(os.path.join(ER, 'org_mentions.parquet'))
    pr = pd.read_parquet(os.path.join(ER, 'org_pairs.parquet'))
    jp = os.path.join(ER, 'org_pair_judgments.parquet')
    j = pd.read_parquet(jp) if os.path.exists(jp) else pd.DataFrame(columns=['a', 'b', 'relation', 'confidence', 'rationale', 'model'])
    rule = pr[pr.rule_decision == 'same'][['a', 'b', 'rule_conf', 'rule_why']].rename(columns={'rule_conf': 'confidence', 'rule_why': 'rationale'})
    rule['relation'] = 'same'; rule['method'] = 'rule'
    j = j[['a', 'b', 'relation', 'confidence', 'rationale', 'model']].rename(columns={'model': 'method'})
    edges = pd.concat([rule, j], ignore_index=True).dropna(subset=['relation'])
    edges.to_parquet(os.path.join(ER, 'org_edges_all.parquet'), index=False)

    weight = kt.set_index('key').n_total.to_dict()
    out = kt[['key', 'srcs', 'n_total', 'example']].copy()
    for name, T in THRESHOLDS.items():
        uf = UF()
        for k in kt.key:
            uf.find(k)
        se = edges[(edges.relation == 'same') & (edges.confidence >= T)].sort_values('confidence', ascending=False)
        # constrained union: never merge clusters whose names carry different numbers (union locals, fund numbers, addresses)
        nums = {k: set(re.findall(r'\d+', k)) for k in kt.key}
        cnum = {k: set(v) for k, v in nums.items()}
        refused = 0
        for a, b in zip(se.a, se.b):
            ra, rb = uf.find(a), uf.find(b)
            if ra == rb:
                continue
            na, nb = cnum.get(ra, set()), cnum.get(rb, set())
            if na and nb and not (na & nb):
                refused += 1
                continue
            uf.union(a, b)
            cnum[uf.find(a)] = na | nb
        print('  refused number-conflicting merges:', refused)
        root = {k: uf.find(k) for k in kt.key}
        # entity id from the heaviest key in the cluster
        cl = pd.DataFrame({'key': list(root), 'root': list(root.values())})
        cl['w'] = cl.key.map(weight)
        top = cl.sort_values('w', ascending=False).drop_duplicates('root').set_index('root').key
        out[f'entity_{name}'] = out.key.map(lambda k: eid('ORG:', top[root[k]]))
        sizes = cl.groupby('root').size()
        print(name, 'T=', T, 'entities', cl.root.nunique(), 'merged keys', (cl.key != cl.root).sum(), 'max cluster', sizes.max())
        if name == 'default':
            big = sizes[sizes > 25]
            for r in big.index[:10]:
                print('  big cluster:', top[r], sizes[r], cl[cl.root == r].key.tolist()[:12])
    # per-key match confidence under default: best same-edge confidence connecting it to another key in the same entity
    se = edges[edges.relation == 'same']
    ent = out.set_index('key').entity_default
    se = se[[ent.get(a) == ent.get(b) for a, b in zip(se.a, se.b)]]
    best = pd.concat([se[['a', 'confidence', 'rationale', 'method']].rename(columns={'a': 'key'}),
                      se[['b', 'confidence', 'rationale', 'method']].rename(columns={'b': 'key'})]).sort_values('confidence', ascending=False).drop_duplicates('key')
    out = out.merge(best, on='key', how='left')
    out['match_conf'] = out.confidence.fillna(1.0)
    out['match_method'] = out.method.fillna('exact normalized key')
    out['match_rationale'] = out.rationale.fillna('identical after normalization (case, punctuation, legal suffixes)')
    out = out.drop(columns=['confidence', 'rationale', 'method'])
    # families (same or family >= 0.7), using default entities as nodes
    uf = UF()
    for e in out.entity_default.unique():
        uf.find(e)
    fe = edges[(edges.relation.isin(['same', 'family'])) & (edges.confidence >= 0.7)]
    for a, b in zip(fe.a, fe.b):
        ea, eb = ent.get(a), ent.get(b)
        if ea and eb:
            uf.union(ea, eb)
    out['family_id'] = out.entity_default.map(lambda e: 'FAM:' + uf.find(e)[4:])
    # nonprofit flag and display names
    npk = set(ms[(ms.extra.fillna('').str.contains('X')) & ms.src.isin(['sc_prime', 'sc_supplier', 'vendor'])].key)
    out['np_flag'] = out.key.isin(npk)
    out.to_parquet(os.path.join(ER, 'org_entity_map.parquet'), index=False)

    # entity table (default threshold)
    ex = ms.copy()
    ex['first_example'] = ex.examples.str.split(' | ', regex=False).str[0]
    pref = {'sc_prime': 0, 'f126_contractor': 1, 'lobby_client': 2, 'vendor': 3, 'bp_payor': 4, 'bp_payee': 4, 'cf_org_donor': 5, 'committee': 5}
    ex['p'] = ex.src.map(pref).fillna(9)
    ex = ex.merge(out[['key', 'entity_default']], on='key')
    disp = ex.sort_values(['p', 'n'], ascending=[True, False]).drop_duplicates('entity_default').set_index('entity_default').first_example
    g = out.sort_values('n_total', ascending=False).groupby('entity_default').agg(keys=('key', lambda s: ' | '.join(s[:20])), n_keys=('key', 'size'),
                                          srcs=('srcs', lambda s: ','.join(sorted(set(','.join(s).split(','))))),
                                          min_match_conf=('match_conf', 'min'), np_flag=('np_flag', 'any'),
                                          family_id=('family_id', 'first'), heavy_key=('key', 'first')).reset_index()
    g['name'] = g.entity_default.map(disp)
    g['type'] = [classify(k, s, n) for k, s, n in zip(g.heavy_key, g.srcs, g.np_flag)]
    g.to_parquet(os.path.join(ER, 'org_entities.parquet'), index=False)
    print(g.type.value_counts())


if __name__ == '__main__':
    main()
