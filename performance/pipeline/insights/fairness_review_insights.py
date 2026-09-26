"""Claude Opus fairness and framing review of the insights page (RULES.md: facts with context, unusual != improper,
name organizations not employees, plain language). Cached and logged via pipeline/llm.py.
Output: data/redteam/fairness_review_insights.json. Fixes are applied by editing pipeline/insights/spec.py (templates),
then rebuilding and re-verifying; the applied/declined decision for each suggestion is recorded in the output file
by --record (see apply notes in PROGRESS.md).
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json

ROOT = os.path.dirname(os.path.dirname(HERE))
PUB = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
PASS2 = '--pass2' in sys.argv
OUT = os.path.join(ROOT, 'data', 'redteam', 'fairness_review_insights_pass2.json' if PASS2 else 'fairness_review_insights.json')

SYSTEM = """You are a senior editor for a nonpartisan civic-data newsroom and an experienced municipal budget analyst. You review
findings about San Francisco city government before publication. Standards: report facts with context; never imply
wrongdoing the data does not show; distinguish "unusual" from "improper"; name organizations, never individual employees
below executive level; plain American English for smart non-experts; no causal claims the data cannot support; give
the most plausible innocent explanations; titles must not overstate the numbers beneath them; every insight must be fair
to the department concerned. You are rigorous and specific, and you do not ask for changes for their own sake."""

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
                    | {'chart': {'type': c['type'], 'title': c['title'], 'subtitle': c['subtitle'], 'series': [s['name'] for s in c['series']], 'note': c['note']}})
    titles = [f"{i['rank']}. {i['title']}" for i in d['insights']]
    res = {'overall': [], 'set_level_issues': [], 'insights': []}
    for k in range(0, len(slim), 6):
        batch = slim[k:k + 6]
        pre = ('SECOND PASS: this set was already revised after a first fairness review. Report only remaining high or medium issues '
               '(or none); do not repeat low-severity style points. ' if PASS2 else '')
        prompt = (pre + 'Review these insights (a batch of the ranked set) for the "Budget vs outcomes" dashboard. For each insight, return verdict '
                  '(publish / revise / drop), specific issues with the exact field (title, dek, why_it_matters, surprise, numbers[i].label, '
                  'robustness.checks[i], robustness.what_could_make_it_wrong, caveats, chart.title, ...) and replacement wording. '
                  'Keep every number as it is unless it is misleading; say so if a number is framed unfairly. Flag: overclaiming titles, causal language, '
                  'implied wrongdoing, missing innocent explanations, loaded words, individual employees singled out, inconsistencies with other insights in the set, '
                  'and anything a department could fairly object to. Be concise: at most four issues per insight, most important first. '
                  'Also list set-level issues you notice (balance, repetition, ordering).\n\nFull set of titles for context:\n' + '\n'.join(titles)
                  + '\n\nIntro: ' + d['intro'] + '\n\nInsights to review:\n' + json.dumps(batch, ensure_ascii=False, indent=1))
        r = call_json('insights_fairness_review_pass2' if PASS2 else 'insights_fairness_review', 'claude-opus-5-5', SYSTEM, prompt, SCHEMA, effort='high', max_tokens=64000)
        res['overall'].append(r['overall']); res['set_level_issues'] += r['set_level_issues']; res['insights'] += r['insights']
    r = res
    json.dump({'model': 'claude-opus-5-5', 'effort': 'high', 'reviewed_file': 'performance/data/site/insights/insights.json', 'review': r},
              open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('\n'.join(r['overall']))
    for s in r['set_level_issues']:
        print(' SET:', s)
    for i in r['insights']:
        print(f"\n[{i['verdict']}] {i['id']} (conf {i['confidence']}): {i['rationale']}")
        for x in i['issues']:
            print(f"  - {x['severity']} {x['field']}: {x['problem']}\n      -> {x['suggested_text']}")


if __name__ == '__main__':
    main()
