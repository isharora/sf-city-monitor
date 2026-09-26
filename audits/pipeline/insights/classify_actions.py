"""Classify every distinct recommendation by the kind of action it asks for (Claude Sonnet 5, cached).

Input: data/site/recs/recs_*.json (distinct key = report | rec_number | first 200 chars of text).
Output: data/insights_work/rec_action_types.json  {key: {action, new_money, legislation, safety_health, rationale, confidence}}
Used by the insights page to test which kinds of recommendations get done. Task prefix in llm_usage.jsonl: insights_.
Run: python3 pipeline/insights/classify_actions.py [--limit N]
"""
import os, sys, json, glob
from concurrent.futures import ThreadPoolExecutor, as_completed
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json, SONNET

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'data', 'insights_work', 'rec_action_types.json')
ACTIONS = ['control_or_procedure', 'written_policy', 'reporting_or_transparency', 'study_or_plan', 'training',
           'it_system', 'staffing_or_funding', 'law_or_governance_change', 'collect_or_recover_money', 'other']
SYSTEM = """You classify recommendations made to San Francisco city departments by auditors (Controller's City Services
Auditor, Budget and Legislative Analyst) and the Civil Grand Jury, by the KIND OF ACTION each asks for.
Pick exactly one primary action:
- control_or_procedure: tighten an internal control or operating procedure, reconcile, document, monitor or enforce existing rules or contract terms (including oversight of tenants, contractors, grantees)
- written_policy: adopt or update a written policy, guideline or manual (without new law)
- reporting_or_transparency: report, publish, disclose or present information (to the public, a board, a commission)
- study_or_plan: conduct a study, analysis, assessment, survey or plan; consider or evaluate an option
- training: train staff or officials
- it_system: acquire, build, upgrade or integrate an IT or data system
- staffing_or_funding: add or fund positions, staff, budget, equipment or capital projects; hire; appropriate money
- law_or_governance_change: change the charter, an ordinance, state law, a ballot measure; create, merge or restructure a body; change who has authority
- collect_or_recover_money: recover overpayments, collect fees, rent, taxes or penalties, bill correctly
- other
Also set booleans: new_money = implementing it clearly requires significant new spending or positions;
legislation = it requires an ordinance, charter amendment, ballot measure or state law;
safety_health = failure to act has direct life-safety or public-health stakes (fire, seismic, emergency response,
violence, overdose, disease, patient or inmate safety), not just financial or administrative stakes.
Give a rationale of at most 12 words and a confidence 0-1. Judge only from the text given."""
SCHEMA = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'i': {'type': 'integer'}, 'action': {'type': 'string', 'enum': ACTIONS}, 'new_money': {'type': 'boolean'},
    'legislation': {'type': 'boolean'}, 'safety_health': {'type': 'boolean'}, 'rationale': {'type': 'string'},
    'confidence': {'type': 'number'}}, 'required': ['i', 'action', 'new_money', 'legislation', 'safety_health', 'rationale', 'confidence'],
    'additionalProperties': False}}}, 'required': ['items'], 'additionalProperties': False}


def key(r):
    return f"{r['report']}|{r['rec_number']}|{(r['text'] or '')[:200]}"


def main():
    lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    reps = {r['id']: r for r in json.load(open(os.path.join(ROOT, 'data', 'site', 'reports', 'reports.json')))['reports']}
    by = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'site', 'recs', 'recs_*.json'))):
        for r in json.load(open(f))['rows']:
            by.setdefault(r['report'], {}).setdefault(key(r), r)
    batches = []
    for rep, recs in sorted(by.items()):
        items = list(recs.items())
        for k in range(0, len(items), 40):
            batches.append((rep, items[k:k + 40]))
    if lim:
        batches = batches[:lim]
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}

    def run(b):
        rep, items = b
        title = reps.get(rep, {}).get('title', '')
        lines = [f"[{i}] {r['text'] or r.get('finding') or ''}" for i, (_, r) in enumerate(items)]
        prompt = f'Report: {rep} "{title}"\nRecommendations:\n' + '\n'.join(lines) + '\nClassify each item [i].'
        d, _ = call_json('insights_action_type', SONNET, SYSTEM, prompt, SCHEMA, effort='low', max_tokens=16000)
        res = {}
        for it in d['items']:
            if 0 <= it['i'] < len(items):
                res[items[it['i']][0]] = {k: it[k] for k in it if k != 'i'}
        return res
    done = 0
    with ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(run, b) for b in batches]
        for f in as_completed(futs):
            try:
                out.update(f.result())
            except Exception as e:
                print('ERR', e)
            done += 1
            if done % 50 == 0:
                print(done, len(batches), flush=True)
                json.dump(out, open(OUT, 'w'))
    json.dump(out, open(OUT, 'w'), indent=0)
    n = sum(len(i) for _, i in batches)
    print(f'classified {len(out)} of {n} distinct recommendations')


if __name__ == '__main__':
    main()
