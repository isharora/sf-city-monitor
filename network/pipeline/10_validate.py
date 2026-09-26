"""Entity-resolution validation.

Step 1 (python3 10_validate.py sample): draw samples to data/validation/:
  org_precision_sample.csv   pairs of distinct raw names the system treats as the SAME entity (default threshold), stratified by method
  org_recall_sample.csv      random anchor organizations with their closest-looking name candidates; label which are truly the same
  person_precision_sample.csv  person<->donor matches accepted at confidence >= 0.8
  person_recall_sample.csv     person<->donor candidates the system did NOT accept (rare names), to look for misses
Step 2: the analyst labels each row (column `label`: 1 = same, 0 = different, blank = can't tell) in *_labels.csv files.
Step 3 (python3 10_validate.py score): computes precision / recall with Wilson intervals, overall and at stricter thresholds.
"""
import os, sys, json, math
import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz

HERE = os.path.dirname(os.path.abspath(__file__))
ER = os.path.join(HERE, '..', 'data', 'er')
VAL = os.path.join(HERE, '..', 'data', 'validation')
os.makedirs(VAL, exist_ok=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(p, 3), round(c - h, 3), round(c + h, 3))


def sample():
    rng = np.random.default_rng(2026)
    em = pd.read_parquet(os.path.join(ER, 'org_entity_map.parquet'))
    edges = pd.read_parquet(os.path.join(ER, 'org_edges_all.parquet'))
    ms = pd.read_parquet(os.path.join(ER, 'org_mentions.parquet'))
    ent = em.set_index('key').entity_default
    ex = ms.groupby('key').examples.first()
    srcs = em.set_index('key').srcs
    same = edges[(edges.relation == 'same')].copy()
    same['merged_default'] = [ent.get(a) == ent.get(b) for a, b in zip(same.a, same.b)]
    same = same[same.merged_default]
    rule = same[same.method == 'rule'].sample(40, random_state=1)
    llm_hi = same[(same.method != 'rule') & (same.confidence >= 0.9)].sample(40, random_state=2)
    llm_mid = same[(same.method != 'rule') & (same.confidence >= 0.8) & (same.confidence < 0.9)]
    llm_mid = llm_mid.sample(min(40, len(llm_mid)), random_state=3)
    # exact-key merges: different raw strings with the same normalized key (from mention examples)
    multi = ms[ms.examples.str.contains(r' \| ', regex=True)].sample(40, random_state=4)
    exact = pd.DataFrame({'a': multi.examples.str.split(' | ', regex=False).str[0], 'b': multi.examples.str.split(' | ', regex=False).str[1],
                          'confidence': 1.0, 'method': 'exact normalized key', 'rationale': 'same key: ' + multi.key})
    ps = pd.concat([rule.assign(stratum='rule'), llm_hi.assign(stratum='llm>=0.9'), llm_mid.assign(stratum='llm 0.8-0.9'), exact.assign(stratum='exact key')], ignore_index=True)
    ps['a_examples'] = ps.a.map(ex).fillna(ps.a); ps['b_examples'] = ps.b.map(ex).fillna(ps.b)
    ps['a_srcs'] = ps.a.map(srcs); ps['b_srcs'] = ps.b.map(srcs)
    ps['label'] = ''
    ps[['stratum', 'a', 'b', 'a_examples', 'b_examples', 'a_srcs', 'b_srcs', 'confidence', 'method', 'rationale', 'label']].to_csv(os.path.join(VAL, 'org_precision_sample.csv'), index=False)

    # recall: random anchors from contracting / lobbying / behested sources; candidate names = top 8 most similar keys (WRatio >= 80)
    anchors = em[em.srcs.str.contains('f126_contractor|sc_prime|lobby_client|bp_payor|vendor')].sample(60, random_state=5)
    universe = em.key.tolist()
    rows = []
    for a in anchors.itertuples():
        cands = process.extract(a.key, universe, scorer=fuzz.WRatio, limit=9, score_cutoff=80)
        for (k, sc, _) in cands:
            if k == a.key:
                continue
            rows.append(dict(anchor=a.key, anchor_examples=ex.get(a.key, a.key), candidate=k, candidate_examples=ex.get(k, k), score=round(sc),
                             system_same=ent.get(a.key) == ent.get(k), anchor_srcs=a.srcs, candidate_srcs=srcs.get(k), label=''))
    pd.DataFrame(rows).to_csv(os.path.join(VAL, 'org_recall_sample.csv'), index=False)

    pm = pd.read_parquet(os.path.join(ER, 'person_matches.parquet'))
    cols = ['kind', 'first', 'last', 'org', 'roles', 'first_d', 'last_d', 'city', 'zip5', 'employers', 'occupations', 'name_profiles', 'emp_sim', 'decision', 'confidence', 'decided_by', 'rationale']
    acc = pm[(pm.decision == 'same') & (pm.confidence >= 0.8)]
    pps = pd.concat([acc[acc.decided_by == 'rule'].sample(20, random_state=6), acc[acc.decided_by != 'rule'].sample(40, random_state=7)])
    pps['label'] = ''
    pps[cols + ['label']].to_csv(os.path.join(VAL, 'person_precision_sample.csv'), index=False)
    rej = pm[((pm.decision != 'same') | (pm.confidence < 0.8)) & (pm.name_profiles <= 2)]
    prs = rej.sample(min(40, len(rej)), random_state=8)
    prs['label'] = ''
    prs[cols + ['label']].to_csv(os.path.join(VAL, 'person_recall_sample.csv'), index=False)
    print('samples written')


def score():
    res = {}
    p = pd.read_csv(os.path.join(VAL, 'org_precision_labels.csv'))
    p = p[p.label.isin([0, 1, '0', '1'])].copy(); p['label'] = p.label.astype(int)
    res['org_precision_overall'] = wilson(p.label.sum(), len(p))
    res['org_precision_by_stratum'] = {s: wilson(g.label.sum(), len(g)) for s, g in p.groupby('stratum')}
    res['org_precision_n'] = int(len(p))
    # stricter threshold: only pairs with confidence >= 0.9
    st = p[p.confidence >= 0.9]
    res['org_precision_conf_ge_0.9'] = wilson(st.label.sum(), len(st))
    r = pd.read_csv(os.path.join(VAL, 'org_recall_labels.csv'))
    r = r[r.label.isin([0, 1, '0', '1'])].copy(); r['label'] = r.label.astype(int)
    em = pd.read_parquet(os.path.join(ER, 'org_entity_map.parquet'))
    kt = em.set_index('key')
    for v in ('lenient', 'default', 'strict'):
        ent = kt[f'entity_{v}']
        r[f'same_{v}'] = [ent.get(a) == ent.get(b) for a, b in zip(r.anchor, r.candidate)]
    tp = r[(r.label == 1)].copy()
    w = tp.candidate.map(kt.n_total).fillna(1).astype(float) + tp.anchor.map(kt.n_total).fillna(1).astype(float)
    for v in ('lenient', 'default', 'strict'):
        res[f'org_recall_pairs_{v}'] = wilson(int(tp[f'same_{v}'].sum()), len(tp))
        res[f'org_recall_record_weighted_{v}'] = round(float((w * tp[f'same_{v}']).sum() / w.sum()), 3)
        res[f'org_recall_sample_false_merges_{v}'] = int(((r.label == 0) & r[f'same_{v}']).sum())
    res['org_recall_pairs_first_pass_only'] = wilson(int(tp.system_same.sum()), len(tp))
    res['org_recall_n_true_pairs'] = int(len(tp))
    pp = pd.read_csv(os.path.join(VAL, 'person_precision_labels.csv'))
    pp = pp[pp.label.isin([0, 1, '0', '1'])].copy(); pp['label'] = pp.label.astype(int)
    res['person_precision'] = wilson(pp.label.sum(), len(pp))
    res['person_precision_by_method'] = {('rule' if m else 'claude'): wilson(g.label.sum(), len(g)) for m, g in pp.groupby(pp.decided_by == 'rule')}
    res['person_precision_conf_ge_0.9'] = wilson(pp[pp.confidence >= 0.9].label.sum(), int((pp.confidence >= 0.9).sum()))
    pr = pd.read_csv(os.path.join(VAL, 'person_recall_labels.csv'))
    pr = pr[pr.label.isin([0, 1, '0', '1'])].copy(); pr['label'] = pr.label.astype(int)
    res['person_rejected_sample_n'] = int(len(pr))
    res['person_rejected_sample_true_matches'] = int(pr.label.sum())
    # recall estimate for the rare-name stratum (<=2 donor profiles with the name), where the recall sample was drawn
    pm = pd.read_parquet(os.path.join(ER, 'person_matches.parquet'))
    rare = pm[pm.name_profiles <= 2]
    acc = rare[(rare.decision == 'same') & (rare.confidence >= 0.8)]
    rej = rare[~((rare.decision == 'same') & (rare.confidence >= 0.8))]
    prec = pp.label.mean() if len(pp) else 1
    tp_acc = prec * len(acc)
    fn = pr.label.mean() * len(rej) if len(pr) else 0
    res['person_recall_estimate_rare_names'] = round(float(tp_acc / (tp_acc + fn)), 3) if (tp_acc + fn) else None
    res['person_counts_rare'] = {'accepted': int(len(acc)), 'rejected_or_below_0.8': int(len(rej))}
    lo = rare[(rare.decision == 'same') & (rare.confidence >= 0.7) & (rare.confidence < 0.8)]
    res['person_candidates_same_0.7_to_0.8'] = int(len(lo))
    json.dump(res, open(os.path.join(VAL, 'validation_results.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    {'sample': sample, 'score': score}[sys.argv[1]]()
