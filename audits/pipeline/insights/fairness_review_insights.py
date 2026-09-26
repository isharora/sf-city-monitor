"""Claude Opus 5.5 fairness and framing review of the audits insights page (RULES.md: departments are named, every claim
cited, facts with context, unusual is not improper, a "will not implement" is often a legitimate policy, legal or cost
decision, plain language). Cached and logged via pipeline/llm.py (task prefix insights_fairness).
Output: data/insights_work/fairness_review_insights.json (or _pass2). Fixes are applied by editing spec.py, rebuilding and
re-verifying; the decision on each suggestion is recorded in data/insights_work/fairness_decisions.json.
Run: python3 pipeline/insights/fairness_review_insights.py [--pass2]
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json, OPUS

ROOT = os.path.dirname(os.path.dirname(HERE))
PUB = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
PASS2 = '--pass2' in sys.argv
OUT = os.path.join(ROOT, 'data', 'insights_work', 'fairness_review_insights_pass2.json' if PASS2 else 'fairness_review_insights.json')

SYSTEM = """You are a senior editor for a nonpartisan civic-data newsroom and an experienced government auditor. You review
findings about San Francisco's audit and Civil Grand Jury recommendations before publication. Standards: report facts
with context; never imply wrongdoing the data does not show; distinguish "unusual" from "improper"; a department's
"will not implement" is often a legitimate policy, legal or cost decision and must be framed that way; statuses are
mostly self-reported by departments and should be described as recorded, not as proven; name organizations, never
individual employees below executive level; every claim about a report needs its report id and page; quotes must be
verbatim; plain American English for smart non-experts; no causal claims the data cannot support; titles must not
overstate the numbers beneath them; robustness verdicts must match the checks. You are rigorous and specific, and you
do not ask for changes for their own sake."""

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
                    | {'chart': {'type': c['type'], 'title': c['title'], 'subtitle': c['subtitle'], 'categories': c['x']['values'],
                                 'series': [{'name': s['name'], 'values': s['values']} for s in c['series']], 'note': c['note']}})
    titles = [f"{i['rank']}. [{i['robustness']['verdict']}] {i['title']}" for i in d['insights']]
    res = {'overall': [], 'set_level_issues': [], 'insights': []}
    for k in range(0, len(slim), 5):
        batch = slim[k:k + 5]
        pre = ('SECOND PASS: this set was already revised after a first fairness review. Report only remaining high or medium issues '
               '(or none); do not repeat low-severity style points. ' if PASS2 else '')
        prompt = (pre + 'Review these insights (a batch of the ranked set) for the "Audit recommendations tracker" dashboard. For each insight, return verdict '
                  '(publish / revise / drop), specific issues with the exact field (title, dek, why_it_matters, surprise, numbers[i].label, robustness.checks[i], '
                  'robustness.what_could_make_it_wrong, caveats, chart.title, chart.note...) and replacement wording. Keep every number as it is unless it is '
                  'misleading; say so if a number is framed unfairly. Flag: overclaiming titles, causal language, implied wrongdoing, refusals not framed as possibly '
                  'legitimate decisions, self-reported statuses presented as fact, missing innocent explanations, loaded words, individuals singled out, '
                  'inconsistencies with other insights in the set, and anything a department could fairly object to. Be concise: at most four issues per insight, '
                  'most important first. Also list set-level issues (balance, repetition, ordering).\n\nFull set of titles for context:\n' + '\n'.join(titles)
                  + '\n\nIntro: ' + d['intro'] + '\n\nInsights to review:\n' + json.dumps(batch, ensure_ascii=False, indent=1))
        r, _ = call_json('insights_fairness_review_pass2' if PASS2 else 'insights_fairness_review', OPUS, SYSTEM, prompt, SCHEMA, effort='high', max_tokens=48000)
        res['overall'].append(r['overall']); res['set_level_issues'] += r['set_level_issues']; res['insights'] += r['insights']
    json.dump({'model': OPUS, 'effort': 'high', 'reviewed_file': 'audits/data/site/insights/insights.json', 'review': res}, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('\n'.join(res['overall']))
    for s in res['set_level_issues']:
        print(' SET:', s)
    for i in res['insights']:
        print(f"\n[{i['verdict']}] {i['id']} (conf {i['confidence']}): {i['rationale']}")
        for x in i['issues']:
            print(f"  - {x['severity']} {x['field']}: {x['problem']}\n      -> {x['suggested_text']}")


if __name__ == '__main__':
    main()
