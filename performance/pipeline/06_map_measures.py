"""Map each Controller performance measure to the department, program and budget lines that produce it.

Step 1 (Sonnet, bulk): one call per current measure (6dpt-7w23 catalog). Inputs: measure title/description/methodology,
  reporting department, that department's legacy budget programs (FY2013-17 actuals) and the list of departments.
Step 2 (Opus, judgment): re-adjudicate every mapping with confidence < 0.7, plus a random validation sample (n=60),
  independently (Opus does not see Sonnet's answer for the sample; for low-confidence cases it sees it and decides).
Outputs:
  data/interim/measure_map_sonnet.csv, measure_map_opus.csv, measure_map.csv (final)
"""
import pandas as pd, numpy as np, os, sys, json, random
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from llm import run_many

SONNET, OPUS = 'claude-sonnet-5', 'claude-opus-5-5'

SYSTEM = """You are a public-finance analyst linking San Francisco city performance measures to the budget lines that produce them.
San Francisco's budget is organized by department (3-letter code) and, until FY2017, by program within department; from FY2018 the
public budget data only has department-level detail (program types such as Operating/Capital). Budget "characters" are: salaries,
benefits, non_personnel (contracts, professional services), materials, grants (City grants to community-based organizations), aid
(cash aid / support & care of persons), services_other_depts (work orders paid to other departments), capital, debt_service.
For the measure given, decide:
- producing_dept: the department code whose spending mainly produces this result (usually the reporting department; differs when
  e.g. the Controller reports a survey result about another department's service, or when a service is delivered by another department).
- legacy_programs: codes (from the list provided for the producing department) of the program(s) that produce the measure; empty if
  none fits or the measure is department-wide/administrative.
- main_characters: budget characters that mainly drive the measure (e.g. salaries for a patrol response time; grants for services
  delivered by nonprofits under contract).
- measure_kind: one of outcome (change in conditions for residents), output (volume of service delivered), efficiency
  (cost or time per unit), quality (timeliness, accuracy, compliance), satisfaction (survey rating), workload (demand/inputs
  received, not controlled by the department), internal_admin (HR/appraisals/internal process).
- direction: higher_better, lower_better, or neutral (no normative direction, e.g. counts of demand).
- volume_unit: if the measure is a count of service units delivered that a department's spending pays for (e.g. "library visits",
  "EMS responses", "cases closed", "people placed in housing"), give a short unit name; else "".
- cost_per_unit_meaningful: true only if dividing the producing department/program spending by this count is a meaningful
  unit cost (the count is a primary output of that spending, not a minor by-product), else false.
- service_area: short plain-English label (e.g. "Emergency medical response", "Street cleaning").
- confidence: 0-1 that producing_dept and legacy_programs are right.
- rationale: 1-3 sentences.
Use only codes you are given. Do not invent programs."""

SCHEMA = {
    'type': 'object',
    'properties': {
        'producing_dept': {'type': 'string'},
        'legacy_programs': {'type': 'array', 'items': {'type': 'string'}},
        'main_characters': {'type': 'array', 'items': {'type': 'string', 'enum': [
            'salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid', 'services_other_depts', 'capital', 'debt_service']}},
        'measure_kind': {'type': 'string', 'enum': ['outcome', 'output', 'efficiency', 'quality', 'satisfaction', 'workload', 'internal_admin']},
        'direction': {'type': 'string', 'enum': ['higher_better', 'lower_better', 'neutral']},
        'volume_unit': {'type': 'string'},
        'cost_per_unit_meaningful': {'type': 'boolean'},
        'service_area': {'type': 'string'},
        'confidence': {'type': 'number'},
        'rationale': {'type': 'string'},
    },
    'required': ['producing_dept', 'legacy_programs', 'main_characters', 'measure_kind', 'direction', 'volume_unit',
                 'cost_per_unit_meaningful', 'service_area', 'confidence', 'rationale'],
    'additionalProperties': False,
}


def prog_block(progs, dept):
    p = progs[progs.dept == dept].sort_values('actual', ascending=False)
    if p.empty:
        return f'(no legacy programs for {dept})'
    return '\n'.join(f'  {r.program_code}: {r.program} (avg actual FY13-17 ${r.actual_avg_m}M/yr)' for r in p.itertuples())


def prompt_for(r, progs, depts_txt, extra=''):
    return (f"Measure reported by department {r.dept} ({r.department_name}).\n"
            f"Title: {r.title}\nStrategic goal: {r.goal}\nDescription: {r.description}\nMethodology: {r.methodology}\n"
            f"Data type: {r.data_type}\n\nLegacy budget programs of {r.dept}:\n{prog_block(progs, r.dept)}\n\n"
            f"All department codes: {depts_txt}\n"
            + (f"\nIf the service is delivered by another department, use that department's programs:\n{extra}\n" if extra else ''))


def main():
    cat = pd.read_csv(os.path.join(INTERIM, 'measures_catalog.csv')).fillna('')
    progs = pd.read_csv(os.path.join(INTERIM, 'legacy_programs.csv'))
    depts_txt = '; '.join(f'{k}={v}' for k, v in sorted(DEPT_NAMES.items()))
    # For measures that plausibly belong to another dept (Controller/City Survey/Admin), give other depts' programs too
    big = ['DPW', 'MTA', 'POL', 'FIR', 'DPH', 'REC', 'LIB', 'HSA', 'HOM', 'DEM', 'ADM']
    extra_all = '\n'.join(f'{d}:\n{prog_block(progs, d)}' for d in big)
    jobs = []
    for r in cat.itertuples():
        extra = extra_all if r.dept in ('CON', 'ADM', 'MYR', 'BOS', 'GEN') else ''
        jobs.append((r.measure_id, dict(task='measure_map_sonnet', model=SONNET, system=SYSTEM,
                                        prompt=prompt_for(r, progs, depts_txt, extra), schema=SCHEMA,
                                        effort='medium', max_tokens=8000)))
    print('sonnet jobs', len(jobs))
    res = run_many(jobs, workers=16)
    retry = [(k, {**kw, 'max_tokens': 16000, 'effort': 'low'}) for k, kw in jobs if isinstance(res.get(k), Exception)]
    if retry:
        print('retrying', len(retry))
        res.update(run_many(retry, workers=4))
    rows = []
    for k, v in res.items():
        if isinstance(v, Exception):
            print('ERR', k, v); continue
        rows.append({'measure_id': k, **{kk: (json.dumps(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()}})
    s = pd.DataFrame(rows)
    s.to_csv(os.path.join(INTERIM, 'measure_map_sonnet.csv'), index=False)

    # Opus: low-confidence adjudication (sees Sonnet answer) + blind validation sample
    random.seed(20260926)
    sample_ids = set(random.sample(sorted(s.measure_id), 60))
    low_ids = set(s[s.confidence < 0.7].measure_id)
    ojobs = []
    by_id = cat.set_index('measure_id')
    for mid_ in sorted(sample_ids | low_ids):
        r = SimpleNamespace(measure_id=mid_, **by_id.loc[mid_].to_dict())
        extra = extra_all if r.dept in ('CON', 'ADM', 'MYR', 'BOS', 'GEN') else ''
        p = prompt_for(r, progs, depts_txt, extra)
        if mid_ in low_ids and mid_ not in sample_ids:
            prev = s.set_index('measure_id').loc[mid_].to_dict()
            p += f"\nA first-pass analyst proposed (low confidence): {json.dumps(prev, default=str)}\nReview critically and give your own final answer."
            task = 'measure_map_opus_adjudicate'
        else:
            task = 'measure_map_opus_blind'
        ojobs.append((mid_, dict(task=task, model=OPUS, system=SYSTEM, prompt=p, schema=SCHEMA, effort='high', max_tokens=16000)))
    print('opus jobs', len(ojobs), 'low-conf', len(low_ids), 'sample', len(sample_ids))
    ores = run_many(ojobs, workers=8)
    orows = []
    for k, v in ores.items():
        if isinstance(v, Exception):
            print('ERR', k, v); continue
        orows.append({'measure_id': k, 'opus_role': 'blind_sample' if k in sample_ids else 'adjudicate',
                      **{kk: (json.dumps(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()}})
    o = pd.DataFrame(orows)
    o.to_csv(os.path.join(INTERIM, 'measure_map_opus.csv'), index=False)

    # Final: Opus overrides for adjudicated low-confidence; for blind-sample items keep Opus when they disagree on dept
    final = s.set_index('measure_id').copy()
    final['map_source'] = 'sonnet'
    for r in o.itertuples():
        if r.opus_role == 'adjudicate' or r.producing_dept != final.loc[r.measure_id, 'producing_dept']:
            for c in SCHEMA['required']:
                final.loc[r.measure_id, c] = getattr(r, c)
            final.loc[r.measure_id, 'map_source'] = 'opus'
    # manual overrides from the hand-checked validation sample (pipeline/measure_map_overrides.json)
    ov = json.load(open(os.path.join(os.path.dirname(__file__), 'measure_map_overrides.json')))
    for o_ in ov:
        if o_['measure_id'] in final.index:
            for k, v in o_['set'].items():
                final.loc[o_['measure_id'], k] = json.dumps(v) if isinstance(v, list) else v
            final.loc[o_['measure_id'], 'map_source'] = 'manual_override'
    final = final.reset_index().merge(cat[['measure_id', 'dept', 'title', 'data_type']], on='measure_id')
    final.to_csv(os.path.join(INTERIM, 'measure_map.csv'), index=False)
    print(final.map_source.value_counts(), final.measure_kind.value_counts(), final.cost_per_unit_meaningful.value_counts())


if __name__ == '__main__':
    main()
