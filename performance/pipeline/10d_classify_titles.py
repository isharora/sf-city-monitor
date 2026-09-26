"""Classify every lineage title (historical and current) into the contract's measure types (outcome / output / efficiency)
plus direction, using Claude Sonnet in per-department batches. Current measures keep the richer 06 mapping; this fills
historical titles. Output: data/interim/title_types.csv (dept, title_key, type, direction, unit_hint)"""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import INTERIM, DEPT_NAMES
from llm import run_many

SYSTEM = ("Classify San Francisco city performance measures. type: 'outcome' (a result for residents or service quality/timeliness, "
          "satisfaction, rates), 'output' (volume of work done or demand handled, counts), 'efficiency' (cost or staff time per unit). "
          "direction: 'higher', 'lower', or 'neutral' (no normative direction). unit_hint: '%', '$', or a short unit noun.")
SCHEMA = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'integer'}, 'type': {'type': 'string', 'enum': ['outcome', 'output', 'efficiency']},
    'direction': {'type': 'string', 'enum': ['higher', 'lower', 'neutral']}, 'unit_hint': {'type': 'string'}},
    'required': ['id', 'type', 'direction', 'unit_hint'], 'additionalProperties': False}}}, 'required': ['items'], 'additionalProperties': False}

if __name__ == '__main__':
    lin = pd.read_csv(os.path.join(INTERIM, 'measure_lineage.csv'))
    jobs, idx = [], {}
    for dept, g in lin.groupby('dept'):
        g = g.reset_index(drop=True)
        for k in range(0, len(g), 80):
            part = g.iloc[k:k + 80]
            idx[(dept, k)] = part
            txt = '\n'.join(f'{i}. {t}' for i, t in zip(part.index, part.title))
            jobs.append(((dept, k), dict(task='title_types_sonnet', model='claude-sonnet-5', system=SYSTEM,
                                         prompt=f'Department {dept} ({DEPT_NAMES.get(dept, dept)}):\n{txt}', schema=SCHEMA, effort='low', max_tokens=16000)))
    res = run_many(jobs, workers=12)
    rows = []
    for key, part in idx.items():
        r = res.get(key)
        got = {x['id']: x for x in r['items']} if isinstance(r, dict) else {}
        for i, row in part.iterrows():
            x = got.get(i, {})
            rows.append({'dept': row.dept, 'title_key': row.title_key, 'type': x.get('type'), 'direction': x.get('direction'), 'unit_hint': x.get('unit_hint')})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(INTERIM, 'title_types.csv'), index=False)
    print(len(out), out.type.value_counts(dropna=False).to_dict())
