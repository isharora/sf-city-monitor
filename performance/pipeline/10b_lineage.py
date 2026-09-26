"""Measure lineage across years (FY2004-FY2026): group each department's measure titles (from the annual reports,
FY13/FY14 snapshots and today's dataset) into lineages, labeling each title's relation to the lineage:
  same       identical meaning (trivial wording/punctuation differences)
  reworded   same concept and definition, noticeably different wording
  redefined  same topic but the definition changed (threshold, population, unit, time window, method)
Uses Claude Opus (judgment) one call per department. Every title id must be assigned exactly once; missing ids become
singleton lineages (logged).
Output: data/interim/measure_lineage.csv (dept, title_key, title, lineage_id, relation, change_note, direction, is_internal_admin)
"""
import pandas as pd, numpy as np, os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from llm import run_many

MODEL = 'claude-opus-5-5'
SYSTEM = """You are auditing how a city department's performance measures changed over ~20 years of annual reports.
You get a numbered list of measure titles for ONE department, each with the report years in which it appears.
Group titles that track the same thing into lineages. For each title give its relation to its lineage:
- "same": same measure; only trivial wording, capitalization, punctuation, or abbreviation differences.
- "reworded": same concept and definition, noticeably reworded.
- "redefined": same topic and clearly a successor/predecessor, but the definition changed (e.g. a time threshold changed
  from 48 to 72 hours, a percentile changed, the population or scope changed, a count became a percentage, a survey
  question/scale changed).
The earliest title in a lineage should be "same" (it anchors the lineage). Do not merge measures that merely share a topic
but are different quantities (e.g. "number of arrests" vs "number of citations"). Use the years: successors usually start
when predecessors stop. Also give each lineage: direction (higher_better, lower_better, neutral) and whether it is an internal
administrative measure (employee appraisals, internal HR/process) rather than a public service measure.
Every id must appear in exactly one lineage. Keep change_note to a short phrase ('' if none)."""

SCHEMA = {
    'type': 'object',
    'properties': {'lineages': {'type': 'array', 'items': {
        'type': 'object',
        'properties': {
            'label': {'type': 'string'},
            'direction': {'type': 'string', 'enum': ['higher_better', 'lower_better', 'neutral']},
            'internal_admin': {'type': 'boolean'},
            'members': {'type': 'array', 'items': {
                'type': 'object',
                'properties': {'id': {'type': 'integer'}, 'relation': {'type': 'string', 'enum': ['same', 'reworded', 'redefined']},
                               'change_note': {'type': 'string'}},
                'required': ['id', 'relation', 'change_note'], 'additionalProperties': False}},
        },
        'required': ['label', 'direction', 'internal_admin', 'members'], 'additionalProperties': False}}},
    'required': ['lineages'], 'additionalProperties': False,
}


def main():
    occ = pd.read_csv(os.path.join(INTERIM, 'measure_occurrences.csv'))
    occ = occ[occ.title_key.notna() & (occ.title_key.str.len() > 3)]
    yrs = occ.groupby(['dept', 'title_key']).agg(title=('title', 'first'), years=('report_fy', lambda s: sorted(set(s)))).reset_index()
    jobs, idx = [], {}
    for dept, g in yrs.groupby('dept'):
        g = g.sort_values(['years', 'title_key'], key=lambda s: s.map(lambda x: x[0] if isinstance(x, list) else x)).reset_index(drop=True)
        idx[dept] = g
        lines = []
        for i, r in g.iterrows():
            ys = r.years
            span = ','.join(str(y) for y in ys)
            lines.append(f'{i}. "{r.title}" [reports: {span}]')
        prompt = (f"Department: {dept} ({DEPT_NAMES.get(dept, dept)}). Report year 2026 = today's published measure set; "
                  f"2013/2014 may also come from a data snapshot.\n\n" + '\n'.join(lines))
        jobs.append((dept, dict(task='lineage_opus', model=MODEL, system=SYSTEM, prompt=prompt, schema=SCHEMA,
                                effort='high', max_tokens=64000)))
    print('departments:', len(jobs))
    res = run_many(jobs, workers=8)
    rows = []
    for dept, g in idx.items():
        r = res.get(dept)
        seen = set()
        if isinstance(r, Exception) or r is None:
            print('ERROR', dept, r)
            r = {'lineages': []}
        for li, lin in enumerate(r['lineages']):
            for m in lin['members']:
                if m['id'] in seen or m['id'] not in g.index:
                    continue
                seen.add(m['id'])
                rows.append({'dept': dept, 'title_key': g.loc[m['id'], 'title_key'], 'title': g.loc[m['id'], 'title'],
                             'years': json.dumps(g.loc[m['id'], 'years']), 'lineage_id': f'{dept}-L{li:03d}',
                             'lineage_label': lin['label'], 'relation': m['relation'], 'change_note': m['change_note'],
                             'direction': lin['direction'], 'internal_admin': lin['internal_admin']})
        missing = [i for i in g.index if i not in seen]
        if missing:
            print(dept, 'missing ids -> singletons:', len(missing))
        for i in missing:
            rows.append({'dept': dept, 'title_key': g.loc[i, 'title_key'], 'title': g.loc[i, 'title'], 'years': json.dumps(g.loc[i, 'years']),
                         'lineage_id': f'{dept}-S{i:03d}', 'lineage_label': g.loc[i, 'title'], 'relation': 'same',
                         'change_note': 'unassigned by model', 'direction': 'neutral', 'internal_admin': False})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(INTERIM, 'measure_lineage.csv'), index=False)
    print('titles:', len(out), 'lineages:', out.lineage_id.nunique(), out.relation.value_counts().to_dict())


if __name__ == '__main__':
    main()
