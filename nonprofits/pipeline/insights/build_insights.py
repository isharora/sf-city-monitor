"""Build nonprofits/data/site/insights/insights.json (design/insights/INSIGHTS_CONTRACT.json).

Values come from compute_build.py; wording and chart specs from spec.py. Also writes data/insights/insights_values.json
(every named value and chart array per insight) for verify_insights.py and review.
Run: python3 pipeline/insights/build_insights.py
"""
import os, sys, json, re, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import spec
from compute_build import COMPUTE
from common import ROOT

OUT = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
VALS = os.path.join(ROOT, 'data', 'insights', 'insights_values.json')
FIELDS = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'chart', 'robustness', 'caveats',
          'explore', 'departments', 'tags']


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else float(x)
    return x


def literal_digit_problems(tpl):
    """Digits in template text outside placeholders and allowed tokens (years, fixed thresholds, dataset ids)."""
    probs = []

    def walk(o, path):
        if isinstance(o, str):
            if o.startswith('@') or path.endswith('source') or '.explore' in path or path.endswith('.id'):
                return
            t = spec.PH.sub('', o)
            for pat in spec.ALLOWED_DIGIT_TOKENS:
                t = re.sub(pat, '', t)
            if re.search(r'\d', t):
                probs.append((path, o[:90]))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(v, f'{path}.{k}')
    walk({k: v for k, v in tpl.items() if k != 'key'}, tpl.get('key', ''))
    return probs


def render_insight(tpl, V, CH):
    t = {k: v for k, v in tpl.items() if k != 'key'}
    r = spec.render(t, V, CH)
    if r['chart'].get('series') == '@SLOPE':  # one series per organization: [start share, later share]
        r['chart']['series'] = [{'name': n, 'values': [round(float(a), 2), round(float(b), 2)]} for n, a, b in zip(CH['names'], CH['d0'], CH['d1'])]
    if r.get('surprise') == '':
        r['surprise'] = None
    return r


def main():
    out = {'sample': False, 'as_of': spec.AS_OF, 'dashboard': 'nonprofits', 'intro': spec.INTRO, 'insights': []}
    vals, probs = {}, []
    for rank, tpl in enumerate(spec.INSIGHTS, 1):
        probs += literal_digit_problems(tpl)
        V, CH = COMPUTE[tpl['key']]()
        V, CH = clean(V), clean(CH)
        r = render_insight(tpl, V, CH)
        r['rank'] = rank
        if len(r['title']) > 92:
            probs.append((tpl['id'], f'title {len(r["title"])} chars: {r["title"]}'))
        out['insights'].append({k: r[k] for k in FIELDS if k in r})
        vals[tpl['id']] = {'key': tpl['key'], 'V': V, 'CH': CH}
    if probs:
        for p in probs:
            print('PROBLEM:', p)
        raise SystemExit(1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True); os.makedirs(os.path.dirname(VALS), exist_ok=True)
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    json.dump(vals, open(VALS, 'w'), indent=1)
    print(f'wrote {OUT}: {len(out["insights"])} insights, {os.path.getsize(OUT) / 1e3:.0f} KB')
    for i in out['insights']:
        print(f'{i["rank"]:>2}. [{i["robustness"]["verdict"]}] {i["title"]}')


if __name__ == '__main__':
    main()
