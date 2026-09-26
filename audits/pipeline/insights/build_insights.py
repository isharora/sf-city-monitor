"""Build audits/data/site/insights/insights.json (design/insights/INSIGHTS_CONTRACT.json + INSIGHTS_DESIGN.md section 10).

Values come from compute.py; wording, quotes and chart specs from spec.py. Also writes data/insights_work/insights_values.json
(every named value and chart array per insight) for verify_insights.py and review.
Run: python3 pipeline/insights/build_insights.py
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spec
from compute import COMPUTE, ROOT, recs

OUT = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
VALS = os.path.join(ROOT, 'data', 'insights_work', 'insights_values.json')
FIELDS = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags']


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return None if np.isnan(x) else float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def literal_digit_problems(tpl):
    probs = []

    def walk(o, path):
        if isinstance(o, str):
            if o.startswith('@CH:') or path.endswith('source') or '.explore.' in path + '.' or path.endswith('.id') or path.endswith('.key'):
                return
            t = spec.PH.sub('', spec.QPH.sub('', o))
            for pat in spec.ALLOWED_DIGIT_TOKENS:
                t = re.sub(pat, '', t)
            if re.search(r'\d', t):
                probs.append((path, o))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, dict):
            for k, v in o.items():
                if k in ('x',) and isinstance(v, (int, float)):
                    continue
                walk(v, f'{path}.{k}')
    walk(tpl, tpl.get('key', 'intro'))
    return probs


def main():
    iv = {'n_ins': len(spec.INSIGHTS), 'n_rows': len(recs()), 'n_fragile': sum(t['robustness']['verdict'] == 'fragile' for t in spec.INSIGHTS)}
    probs = literal_digit_problems({'key': 'intro', 'intro': spec.INTRO})
    out = {'sample': False, 'as_of': spec.AS_OF, 'dashboard': 'audits', 'intro': spec.render_str(spec.INTRO, iv), 'insights': []}
    vals = {'_intro': {'V': iv}}
    for rank, tpl in enumerate(spec.INSIGHTS, 1):
        probs += literal_digit_problems(tpl)
        V, CH = COMPUTE[tpl['key']]()
        V, CH = clean(V), clean(CH)
        r = spec.render({k: v for k, v in tpl.items() if k != 'key'}, V, CH)
        r['rank'] = rank
        if len(r['title']) > 92:
            probs.append((tpl['id'], f'title too long ({len(r["title"])}): {r["title"]}'))
        out['insights'].append({k: r[k] for k in FIELDS if k in r})
        vals[tpl['id']] = {'key': tpl['key'], 'V': V, 'CH': CH}
    if probs:
        for p in probs:
            print('PROBLEM:', p)
        raise SystemExit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    json.dump(vals, open(VALS, 'w'), indent=1)
    print(f'wrote {OUT}: {len(out["insights"])} insights, {os.path.getsize(OUT):,} bytes')
    for i in out['insights']:
        print(f'{i["rank"]:>2}. [{i["robustness"]["verdict"]}] {i["title"]}')


if __name__ == '__main__':
    main()
