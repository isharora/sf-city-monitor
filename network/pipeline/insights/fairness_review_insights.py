"""Claude Opus fairness and framing review of the Money network insights page (RULES.md, including the network module's
extra rules: private individuals only in aggregate; timing links are "a pattern worth checking, not proof"; the exact rule
next to any "appears to warrant review"; base rates shown). Cached and logged via pipeline/llm.py.
Output: data/redteam/fairness_review_insights.json (or _pass2 with --pass2). Fixes are applied by editing spec.py, then
rebuilding and re-verifying; the decision on each suggestion is recorded in data/redteam/fairness_review_decisions.json.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import call_json, OPUS

ROOT = os.path.dirname(os.path.dirname(HERE))
PUB = os.path.join(ROOT, 'data', 'site', 'insights', 'insights.json')
PASS2 = '--pass2' in sys.argv
OUT = os.path.join(ROOT, 'data', 'redteam', 'fairness_review_insights_pass2.json' if PASS2 else 'fairness_review_insights.json')
RULES = open(os.path.join(os.path.dirname(ROOT), 'RULES.md')).read()
LEGAL = json.load(open(os.path.join(ROOT, 'pipeline', 'rules_network.json')))

SYSTEM = """You are a senior editor for a nonpartisan civic-data newsroom and an expert in San Francisco campaign-finance, lobbying and
ethics law. You review findings about political money before publication. Standards: report facts with context; never imply
wrongdoing the data do not show; distinguish "unusual" from "improper"; name organizations, officials in their public roles and
registered lobbyists only, and private individuals only in aggregate; any timing link must be framed as a pattern worth checking,
not proof; any "appears to warrant review" must cite the exact rule and explain why; base rates must be shown where a rate is
compared; legal statements must match the cited rule text; titles must not overstate the numbers beneath them; plain American
English for smart non-experts; no causal claims the data cannot support; give the most plausible innocent explanations. Be fair
to every official and organization named. Be rigorous and specific; do not ask for changes for their own sake."""

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
                    | {'chart': {'type': c['type'], 'title': c['title'], 'subtitle': c['subtitle'], 'x': c['x']['values'],
                                 'series': [{'name': s['name'], 'values': s['values']} for s in c['series']], 'note': c['note']}})
    titles = [f"{i['rank']}. {i['title']}" for i in d['insights']]
    legal = '\n\n'.join(f"[{r['id']}] {r['cite']}\n{r['text']}" for r in LEGAL)
    res = {'overall': [], 'set_level_issues': [], 'insights': []}
    for k in range(0, len(slim), 6):
        batch = slim[k:k + 6]
        pre = ('SECOND PASS: this set was already revised after a first fairness review. Report only remaining high or medium issues '
               '(or none); do not repeat low-severity style points. ' if PASS2 else '')
        prompt = (pre + 'Review these insights (a batch of the ranked set) for the "Money network" dashboard (campaign donors, officials, lobbyists, contractors), '
                  'the most sensitive dashboard of the site. For each insight return verdict (publish / revise / drop) and specific issues with the exact field '
                  '(title, dek, why_it_matters, surprise, numbers[i].label, numbers[i].value, robustness.checks[i], robustness.what_could_make_it_wrong, caveats[i], chart.title, ...) '
                  'and replacement wording. Keep every number as it is unless it is misleading; if a number is framed unfairly say so. Flag: overclaiming titles, causal language, '
                  'implied wrongdoing, missing innocent explanations, missing base rates, loaded words, private individuals named or identifiable, officials treated unfairly, '
                  'legal statements that do not match the rule text below, "appears to warrant review" without the exact rule, timing links not framed as patterns worth checking, '
                  'and inconsistencies with other insights in the set. At most five issues per insight, most important first. Also list set-level issues '
                  '(balance, repetition, ordering, anything missing a careful reader would expect).\n\n'
                  'RULES.md (project rules):\n' + RULES + '\n\nLegal rules as verified against the enacted text (rules_network.json):\n' + legal +
                  '\n\nFull set of titles for context:\n' + '\n'.join(titles) + '\n\nIntro: ' + d['intro'] +
                  '\n\nInsights to review:\n' + json.dumps(batch, ensure_ascii=False, indent=1))
        r = call_json('insights_fairness_review_pass2' if PASS2 else 'insights_fairness_review', prompt, SCHEMA, system=SYSTEM, model=OPUS, effort='high', max_tokens=64000)
        res['overall'].append(r['overall']); res['set_level_issues'] += r['set_level_issues']; res['insights'] += r['insights']
    json.dump({'model': OPUS, 'effort': 'high', 'reviewed_file': 'network/data/site/insights/insights.json', 'review': res},
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
