"""Claude Opus fairness and framing review of the nonprofit-money insights page (RULES.md: facts with context, unusual is
not improper, name organizations only where solid and fair, no individual employees, plain language).

Cached and logged via pipeline/lib_llm.py (data/llm_usage.jsonl). Output: data/insights/fairness_review_insights.json
(or ..._pass2.json with --pass2). Fixes are applied by editing pipeline/insights/spec.py, then rebuilding and
re-verifying; data/insights/fairness_decisions.json records what was applied or declined and why.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from lib_llm import call_json  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
PUB = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
PASS2 = '--pass2' in sys.argv
OUT = os.path.join(ROOT, 'data', 'insights', 'fairness_review_insights_pass2.json' if PASS2 else 'fairness_review_insights.json')

SYSTEM = """You are a senior editor for a nonpartisan civic-data newsroom and an experienced analyst of government funding of
nonprofits. You review findings about San Francisco's payments to nonprofit organizations before publication. Standards:
report facts with context; never imply wrongdoing beyond official findings; distinguish "unusual" from "improper"; name
organizations only where the data are solid and the context is fair; never single out individual employees; plain
American English for smart non-experts; no causal claims the data cannot support; give the most plausible innocent
explanations; titles must not overstate the numbers beneath them; be fair to the nonprofits and departments concerned,
and to the public interest in accountability. You are rigorous and specific, and you do not ask for changes for their own sake."""

SCHEMA = {'type': 'object', 'properties': {
    'overall': {'type': 'string'},
    'set_level_issues': {'type': 'array', 'items': {'type': 'string'}},
    'insights': {'type': 'array', 'items': {'type': 'object', 'properties': {
        'id': {'type': 'string'},
        'verdict': {'type': 'string', 'enum': ['publish', 'revise', 'drop']},
        'issues': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'field': {'type': 'string'}, 'severity': {'type': 'string', 'enum': ['high', 'medium', 'low']},
            'problem': {'type': 'string'}, 'suggested_text': {'type': 'string'}},
            'required': ['field', 'severity', 'problem', 'suggested_text'], 'additionalProperties': False}},
        'rationale': {'type': 'string'}, 'confidence': {'type': 'number'}},
        'required': ['id', 'verdict', 'issues', 'rationale', 'confidence'], 'additionalProperties': False}}},
    'required': ['overall', 'set_level_issues', 'insights'], 'additionalProperties': False}


def main():
    d = json.load(open(PUB))
    slim = []
    for i in d['insights']:
        c = i['chart']
        slim.append({k: i[k] for k in ('id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'robustness', 'caveats', 'departments') if k in i}
                    | {'chart': {'type': c['type'], 'title': c['title'], 'subtitle': c.get('subtitle'), 'x': c['x']['values'],
                                 'series': [{'name': s['name'], 'values': s['values']} for s in c['series']], 'note': c.get('note')}})
    titles = [f"{i['rank']}. [{i['robustness']['verdict']}] {i['title']}" for i in d['insights']]
    res = {'overall': [], 'set_level_issues': [], 'insights': []}
    for k in range(0, len(slim), 6):
        batch = slim[k:k + 6]
        pre = ('SECOND PASS: this set was already revised after a first fairness review. Report only remaining high or medium issues '
               '(or none); do not repeat low-severity style points. ' if PASS2 else '')
        prompt = (pre + 'Review these insights (a batch of the ranked set) for the "Follow the nonprofit money" dashboard. For each insight return a verdict '
                  '(publish / revise / drop) and specific issues with the exact field (title, dek, why_it_matters, surprise, numbers[i].label, '
                  'robustness.checks[i], robustness.what_could_make_it_wrong, caveats[i], chart.title, ...) and replacement wording. '
                  'Keep every number as it is unless it is misleading; say so if a number is framed unfairly. Flag: overclaiming titles, causal language, '
                  'implied wrongdoing, missing innocent explanations, loaded words, organizations named without solid data or fair context, individuals singled out, '
                  'factual statements that the numbers shown do not support, inconsistencies with other insights in the set, and anything a nonprofit or department '
                  'could fairly object to. Be concise: at most four issues per insight, most important first. Also list set-level issues you notice '
                  '(balance, repetition, ordering, missing context).\n\nFull set of titles for context:\n' + '\n'.join(titles)
                  + '\n\nIntro: ' + d['intro'] + '\n\nInsights to review:\n' + json.dumps(batch, ensure_ascii=False, indent=1))
        r = call_json('insights_fairness_review_pass2' if PASS2 else 'insights_fairness_review', prompt, SCHEMA, model='claude-opus-5-5',
                      system=SYSTEM, effort='high', max_tokens=20000)
        res['overall'].append(r['overall']); res['set_level_issues'] += r['set_level_issues']; res['insights'] += r['insights']
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({'model': 'claude-opus-5-5', 'effort': 'high', 'reviewed_file': 'nonprofits/data/site/insights/insights.json', 'review': res},
              open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('\n'.join(res['overall']))
    for s in res['set_level_issues']:
        print(' SET:', s)
    for i in res['insights']:
        print(f"\n[{i['verdict']}] {i['id']} (conf {i['confidence']}): {i['rationale']}")
        for x in i['issues']:
            print(f"  - {x['severity']} {x['field']}: {x['problem']}\n      -> {x['suggested_text']}")


if __name__ == '__main__':
    main()
