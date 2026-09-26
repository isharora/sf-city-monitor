"""Reliability check of the measure lineage (10b): re-run Opus for 6 departments with titles in shuffled order and without
the report-year hints, then compare with the original grouping.
Metrics: pairwise co-membership agreement (for every pair of titles, same lineage or not), precision/recall of 'same lineage'
pairs relative to the original, and agreement on the redefined label for titles in multi-title lineages.
Output: data/interim/lineage_validation.json
"""
import pandas as pd, numpy as np, os, sys, json, random, itertools
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from llm import run_many
import importlib
L = importlib.import_module('10b_lineage')

DEPTS = ['LIB', 'FIR', 'POL', 'DPW', 'REC', 'MTA']


def main():
    lin = pd.read_csv(os.path.join(INTERIM, 'measure_lineage.csv'))
    jobs, orders = [], {}
    for dept in DEPTS:
        g = lin[lin.dept == dept].reset_index(drop=True)
        idx = list(range(len(g)))
        random.Random(7).shuffle(idx)
        orders[dept] = (g, idx)
        lines = [f'{j}. "{g.loc[i, "title"]}"' for j, i in enumerate(idx)]
        prompt = (f"Department: {dept} ({DEPT_NAMES.get(dept, dept)}). Report years are not provided; judge from wording only.\n\n" + '\n'.join(lines))
        jobs.append((dept, dict(task='lineage_validation_opus', model=L.MODEL, system=L.SYSTEM, prompt=prompt, schema=L.SCHEMA,
                                effort='high', max_tokens=64000)))
    res = run_many(jobs, workers=6)
    out = {}
    for dept in DEPTS:
        g, idx = orders[dept]
        r = res[dept]
        if isinstance(r, Exception):
            out[dept] = str(r); continue
        new = {}
        newrel = {}
        for li, lin_ in enumerate(r['lineages']):
            for m in lin_['members']:
                if 0 <= m['id'] < len(idx):
                    new[idx[m['id']]] = li
                    newrel[idx[m['id']]] = m['relation']
        orig = dict(zip(range(len(g)), g.lineage_id))
        keys = [i for i in range(len(g)) if i in new]
        tp = fp = fn = tn = 0
        for a, b in itertools.combinations(keys, 2):
            o = orig[a] == orig[b]; n = new[a] == new[b]
            tp += o and n; fp += (not o) and n; fn += o and (not n); tn += (not o) and (not n)
        multi = g[g.lineage_id.map(g.lineage_id.value_counts()) > 1].index
        red_o = g.loc[multi, 'relation'].eq('redefined')
        red_n = pd.Series([newrel.get(i) == 'redefined' for i in multi], index=multi)
        out[dept] = {'titles': len(g), 'assigned_in_rerun': len(keys), 'orig_lineages': int(g.lineage_id.nunique()),
                     'rerun_lineages': len(set(new.values())), 'pair_agreement': (tp + tn) / max(1, tp + fp + fn + tn),
                     'same_lineage_pairs_orig': tp + fn, 'recall_of_orig_links': tp / max(1, tp + fn), 'precision_vs_orig': tp / max(1, tp + fp),
                     'redefined_label_agreement_multi_title': float((red_o == red_n).mean()) if len(multi) else None}
    tot = {k: sum(v[k] for v in out.values() if isinstance(v, dict)) for k in ['titles', 'same_lineage_pairs_orig']}
    out['_summary'] = {'mean_recall': float(np.mean([v['recall_of_orig_links'] for v in out.values() if isinstance(v, dict) and 'recall_of_orig_links' in v])),
                       'mean_precision': float(np.mean([v['precision_vs_orig'] for v in out.values() if isinstance(v, dict) and 'precision_vs_orig' in v])), **tot}
    json.dump(out, open(os.path.join(INTERIM, 'lineage_validation.json'), 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
