"""Build performance/data/site/insights/insights.json (design/insights/INSIGHTS_CONTRACT.json).

Values come from compute_build.py; wording and chart specs from spec.py. Also writes
data/redteam/insights_values.json (every named value and chart array per insight) for verify_insights.py and review.
Run: python3 pipeline/insights/build_insights.py
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spec
from compute_build import COMPUTE, ROOT

OUT = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
VALS = os.path.join(ROOT, 'data', 'redteam', 'insights_values.json')
FIELDS = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'chart', 'robustness', 'caveats',
          'explore', 'departments', 'tags']


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, float) and np.isnan(x):
        return None
    return x


def literal_digit_problems(tpl):
    """Digits in template text outside placeholders and allowed tokens (years, dataset ids...)."""
    probs = []

    def walk(o, path):
        if isinstance(o, str):
            if o.startswith('@CH:') or path.endswith('source') or '.explore.' in path + '.' or path.endswith('.id'):
                return
            t = spec.PH.sub('', o)
            for pat in spec.ALLOWED_DIGIT_TOKENS:
                t = re.sub(pat, '', t)
            if re.search(r'\d', t):
                probs.append((path, o))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, f'{path}.{k}')
    walk({k: v for k, v in tpl.items() if k != 'key'}, tpl.get('key', ''))
    return probs


def main():
    out = {'sample': False, 'as_of': spec.AS_OF, 'dashboard': 'performance', 'intro': spec.INTRO, 'insights': []}
    vals = {}
    probs = []
    for rank, tpl in enumerate(spec.INSIGHTS, 1):
        probs += literal_digit_problems(tpl)
        V, CH = COMPUTE[tpl['key']]()
        V, CH = clean(V), clean(CH)
        r = spec.render({k: v for k, v in tpl.items() if k != 'key'}, V, CH)
        r['rank'] = rank
        out['insights'].append({k: r[k] for k in FIELDS if k in r})
        vals[tpl['id']] = {'key': tpl['key'], 'V': V, 'CH': CH}
    if probs:
        for p in probs:
            print('LITERAL NUMBER IN TEMPLATE:', p)
        raise SystemExit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    json.dump(vals, open(VALS, 'w'), indent=1)
    print(f'wrote {OUT}: {len(out["insights"])} insights')
    for i in out['insights']:
        print(f'{i["rank"]:>2}. {i["title"]}')


if __name__ == '__main__':
    main()
