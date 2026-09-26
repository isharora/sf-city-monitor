"""Check that no private individual's name appears anywhere in network/data/site/insights/insights.json (RULES.md, network module:
private individuals appear only in aggregate).

Private-name list: every individual donor in the campaign filings (first and last name), every person listed as a party on
Form SFEC-126(f)4 (board members, officers, owners), individual Form 114.5 and Form 125 contributors, behested payors, and
people named in lobbyist payment/employment disclosures. Allowed (public roles, RULES.md): City officials and candidates
(data/er/officials.parquet; elected and appointed executives in data/er/lobby_official_map.parquet; the verified citywide
office table pipeline/offices_citywide.json) and registered lobbyists (data/interim/lob_directory.parquet).
Method: every string in the insights file is upper-cased and reduced to words; a hit is any private "FIRST LAST" or
"LAST FIRST" word pair (first token of the first name) that appears in the text and is not an allowed person. Reviewed
false positives (ordinary word pairs that happen to match a donor's name, e.g. place names) are listed in REVIEWED with a
reason. Exit 1 on any unreviewed hit. Output: data/redteam/check_private_names.json.
"""
import os, re, json, unicodedata
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, 'data')
PUB = os.path.join(DATA, 'site', 'insights', 'insights.json')
OUT = os.path.join(DATA, 'redteam', 'check_private_names.json')

# word pairs that match some donor's first+last name but are ordinary words in the text (reviewed by the analyst)
REVIEWED = {
}


ORG_WORDS = re.compile(r'\b(THE|FUND|FOUNDATION|INC|LLC|LP|LLP|CORP|CORPORATION|COMPANY|CO|ASSOCIATION|ASSN|BANK|UNION|GROUP|TRUST|CENTER|'
                       r'COUNCIL|COMMITTEE|PAC|PARTNERS|HOLDINGS|SERVICES|TECHNOLOGIES|LABS|REALTY|PROPERTIES|ALLIANCE|COALITION|CLUB|'
                       r'CHURCH|UNIVERSITY|COLLEGE|HOSPITAL|HEALTH|SOCIETY|INSTITUTE|NETWORK|ACTION|ADVOCACY|INTERNATIONAL|LOCAL|OF|AND|FOR)\b')


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Z ]+', ' ', s.upper())


def words(s):
    return [w for w in norm(s).split() if w]


def pairs(first, last):
    f, l = words(first), words(last)
    if not f or not l:
        return set()
    f0 = f[0]
    ln = ' '.join(l)
    out = {f'{f0} {ln}', f'{ln} {f0}'}
    if len(l) > 1:
        out |= {f'{f0} {l[-1]}'}
    return {p for p in out if len(f0) > 1 and len(l[-1]) > 1}


def split_full(name):
    name = str(name or '').strip()
    if not name:
        return None, None
    if ',' in name:
        last, first = name.split(',', 1)
        return first, last
    w = name.split()
    if len(w) < 2:
        return None, None
    return w[0], w[-1]


def private_names():
    P = {}

    def add(first, last, src):
        for p in pairs(first, last):
            P.setdefault(p, src)
    c = pd.read_parquet(os.path.join(DATA, 'interim', 'contributions.parquet'), columns=['is_individual', 'donor_first', 'donor_last'])
    c = c[c.is_individual].drop_duplicates()
    for f, l in zip(c.donor_first, c.donor_last):
        add(f, l, 'campaign donor')
    f = pd.read_parquet(os.path.join(DATA, 'interim', 'f126_parties.parquet'), columns=['first', 'last', 'is_person'])
    for a, b in zip(f[f.is_person]['first'], f[f.is_person]['last']):
        add(a, b, 'Form SFEC-126(f)4 party')
    for fn, col in (('f1145.parquet', 'contributorname'), ('f125.parquet', 'contributorname'), ('behested.parquet', 'payor')):
        d = pd.read_parquet(os.path.join(DATA, 'interim', fn))
        for n in d[col].dropna().unique():
            if ORG_WORDS.search(norm(n)) or len(words(n)) > 4:
                continue  # organizations are not private individuals
            a, b = split_full(n)
            if a:
                add(a, b, fn)
    p2i = pd.read_parquet(os.path.join(DATA, 'interim', 'lobby_p2i.parquet'))
    for a, b in zip(p2i.employeefirstname.fillna(''), p2i.employeelastname.fillna('')):
        add(a, b, 'lobbyist disclosure (employee)')
    return P


def allowed_names():
    A = set()
    o = pd.read_parquet(os.path.join(DATA, 'er', 'officials.parquet'))
    for n in o.display.dropna():
        a, b = split_full(n)
        if a:
            A |= pairs(a, b)
    m = pd.read_parquet(os.path.join(DATA, 'er', 'lobby_official_map.parquet'))
    for n in m[m.category.isin(['elected', 'appointed_exec'])].name.dropna():
        a, b = split_full(n)
        if a:
            A |= pairs(a, b)
    for t in json.load(open(os.path.join(ROOT, 'pipeline', 'offices_citywide.json'))).get('terms', []):
        a, b = split_full(t.get('person') or '')
        if a:
            A |= pairs(a, b)
    ld = pd.read_parquet(os.path.join(DATA, 'interim', 'lob_directory.parquet'))
    for n in ld.lobbyistname.dropna():
        a, b = split_full(n)
        if a:
            A |= pairs(a, b)
    return A


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)


def main():
    pub = json.load(open(PUB))
    P, A = private_names(), allowed_names()
    # self-test: a planted private donor name must be caught
    probe = next(p for p in sorted(P) if p not in A and p not in REVIEWED and len(p.split()) == 2)
    w = words('Planted text naming ' + probe.title() + ' as a donor.')
    assert probe in {' '.join(w[i:i + 2]) for i in range(len(w) - 1)} & set(P), 'self-test failed'
    hits, allowed_hits, reviewed = [], [], []
    for s in strings(pub):
        w = words(s)
        grams = {' '.join(w[i:i + 2]) for i in range(len(w) - 1)} | {' '.join(w[i:i + 3]) for i in range(len(w) - 2)}
        for g in grams & set(P):
            rec = {'pair': g, 'source_list': P[g], 'context': s[:160]}
            if g in A:
                allowed_hits.append(rec)
            elif g in REVIEWED:
                reviewed.append(rec | {'reason': REVIEWED[g]})
            else:
                hits.append(rec)
    dedup = lambda L: list({(r['pair'], r['context']): r for r in L}.values())
    res = {'file': 'network/data/site/insights/insights.json', 'private_name_pairs': len(P), 'allowed_pairs': len(A),
           'unreviewed_hits': dedup(hits), 'allowed_public_role_hits': sorted({r['pair'] for r in allowed_hits}),
           'reviewed_false_positives': dedup(reviewed), 'ok': not hits, 'method': __doc__.strip()}
    json.dump(res, open(OUT, 'w'), indent=1)
    print(f'{len(P):,} private name pairs, {len(A):,} allowed; public-role names found: {res["allowed_public_role_hits"]}')
    print(f'reviewed false positives: {sorted({r["pair"] for r in reviewed})}')
    for h in res['unreviewed_hits']:
        print('PRIVATE NAME?', h)
    if hits:
        raise SystemExit(1)
    print('OK: no private individual names')


if __name__ == '__main__':
    main()
