#!/usr/bin/env python3
"""Writes sample-data/insights.json from sample-data/insights.sample.js (identical object) and checks the contract shape.
Usage: python3 tools/emit_json.py   (from design/insights/prototype)"""
import json, re, sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
src = (root / 'sample-data/insights.sample.js').read_text()
body = src[src.index('{', src.index('window.SFCM_INSIGHTS_SAMPLE')):]
body = body[:body.rindex('}') + 1]
data = json.loads(body)
TYPES = ['line', 'bar', 'hbar', 'dumbbell', 'slope', 'stacked', 'smallmultiples', 'scatter', 'waterfall']
REQ = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags']
errors = []
for i in data['insights']:
    for k in REQ:
        if k not in i: errors.append(f"{i['id']}: missing {k}")
    if i['chart']['type'] not in TYPES: errors.append(f"{i['id']}: bad chart type {i['chart']['type']}")
    if len(i['title']) > 92: errors.append(f"{i['id']}: title {len(i['title'])} chars")
    for n in i['numbers']:
        if not n.get('source'): errors.append(f"{i['id']}: number without source")
    if i['robustness']['verdict'] not in ('robust', 'fragile'): errors.append(f"{i['id']}: bad verdict")
    ch = i['chart']
    if ch['type'] in ('line', 'bar', 'hbar', 'stacked', 'smallmultiples', 'waterfall', 'dumbbell'):
        for s in ch['series']:
            if len(s['values']) != len(ch['x']['values']): errors.append(f"{i['id']}: series {s['name']} has {len(s['values'])} values for {len(ch['x']['values'])} x")
    if ch['type'] == 'scatter' and len(ch['series'][0]['values']) != len(ch['x']['values']): errors.append(f"{i['id']}: scatter lengths")
ranks = sorted(i['rank'] for i in data['insights'])
if ranks != list(range(1, len(ranks) + 1)): errors.append('ranks are not 1..n')
seen = {i['chart']['type'] for i in data['insights']}
for t in TYPES:
    if t not in seen: errors.append(f'chart type not used: {t}')
if errors: print('\n'.join(errors)); sys.exit(1)
(root / 'sample-data/insights.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
print(f"ok: {len(data['insights'])} insights, {len(seen)} chart types → sample-data/insights.json ({(root / 'sample-data/insights.json').stat().st_size // 1024} KB)")
