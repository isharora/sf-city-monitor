"""Second candidate-generation pass (added after validation showed low pair recall).

The first pass (03_mentions.py) only compared anchor keys with keys sharing a rare token, and skipped low-volume employer
strings. This pass compares ALL keys against each other within blocks (first 3 letters of the space-stripped key, and last
4 letters), using the space-insensitive string, to catch spelling variants such as DOLORES/DELORES, CANNON/CONNON, EBAY/E BAY.
Near-identical pairs (ratio >= 95, >= 10 chars, same numbers) are decided by rule; 90-95 go to Claude.
Appends new rows to data/er/org_pairs.parquet with pass='2'.
"""
import os, re
import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')


def main():
    kt = pd.read_parquet(os.path.join(ER, 'org_keys.parquet'))
    pr = pd.read_parquet(os.path.join(ER, 'org_pairs.parquet'))
    if 'pass' in pr.columns:
        pr = pr[pr['pass'] != '2']
    have = set(zip(pr.a, pr.b))
    keys = kt.key[kt.key.str.len() >= 5].tolist()
    ns = {k: k.replace(' ', '') for k in keys}
    rows = []
    for blockfn in (lambda s: s[:3], lambda s: s[-4:]):
        blocks = {}
        for k in keys:
            blocks.setdefault(blockfn(ns[k]), []).append(k)
        for b, ks in blocks.items():
            if len(ks) < 2 or len(ks) > 6000:
                continue
            strs = [ns[k] for k in ks]
            m = process.cdist(strs, strs, scorer=fuzz.ratio, score_cutoff=90, dtype=np.uint8, workers=4)
            ii, jj = np.nonzero(m)
            for i, j in zip(ii, jj):
                if i >= j:
                    continue
                a, c = sorted((ks[i], ks[j]))
                if (a, c) in have:
                    continue
                have.add((a, c))
                rows.append(dict(a=a, b=c, ratio=float(m[i, j]), tsort=float(fuzz.token_sort_ratio(a, c)), tset=float(fuzz.token_set_ratio(a, c)), shared_idf=0.0))
    new = pd.DataFrame(rows)
    print('new candidate pairs', len(new))
    digits = lambda s: tuple(re.findall(r'\d+', s))
    dec, conf, why = [], [], []
    for r in new.itertuples():
        if digits(r.a) != digits(r.b):
            dec.append('llm'); conf.append(None); why.append('numbers differ (pass 2)')
        elif (r.ratio >= 95 and min(len(r.a), len(r.b)) >= 10 and abs(len(r.a.replace(' ', '')) - len(r.b.replace(' ', ''))) <= 2
              and not (set(t for t in r.a.split() if len(t) <= 3) ^ set(t for t in r.b.split() if len(t) <= 3))
              and r.a.split()[0][:3] == r.b.split()[0][:3]):
            dec.append('same'); conf.append(0.9); why.append(f'near-identical ignoring spaces (ratio {r.ratio:.0f}, pass 2)')
        else:
            dec.append('llm'); conf.append(None); why.append('grey zone (pass 2)')
    new['prune_reason'] = ''
    new['rule_decision'] = dec; new['rule_conf'] = conf; new['rule_why'] = why
    srcs = kt.set_index('key').srcs
    new['a_srcs'] = new.a.map(srcs); new['b_srcs'] = new.b.map(srcs)
    new['cross_source'] = new.a_srcs != new.b_srcs
    new['pass'] = '2'
    pr['pass'] = '1'
    out = pd.concat([pr, new], ignore_index=True)
    out.to_parquet(os.path.join(ER, 'org_pairs.parquet'), index=False)
    print(new.rule_decision.value_counts())


if __name__ == '__main__':
    main()
