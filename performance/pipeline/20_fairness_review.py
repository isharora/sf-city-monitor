"""Opus red-team review of the headline commentary facts for fairness, overclaiming and missing caveats.
Output: data/interim/fairness_review.json (the analyst then edits 17_commentary.py; changes logged in ANALYSIS.md)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from common import INTERIM
from llm import call_json

SYSTEM = ("You are a skeptical editor reviewing accountability-dashboard findings about San Francisco city departments before "
          "publication. Standards: report facts with context; never imply wrongdoing the data don't show; distinguish unusual from "
          "improper; plain language for smart non-experts; every number must be supported by the stated computation. For each "
          "finding, flag overclaiming, causal language the data can't support, unfair framing of a named department, missing "
          "alternative explanations or caveats, and wording that a non-expert could misread. Be specific and propose exact rewrites.")
SCHEMA = {'type': 'object', 'properties': {'reviews': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'id': {'type': 'string'}, 'verdict': {'type': 'string', 'enum': ['ok', 'minor_edit', 'major_edit', 'drop']},
    'issues': {'type': 'array', 'items': {'type': 'string'}}, 'suggested_headline': {'type': 'string'},
    'missing_caveats': {'type': 'array', 'items': {'type': 'string'}}},
    'required': ['id', 'verdict', 'issues', 'suggested_headline', 'missing_caveats'], 'additionalProperties': False}}},
    'required': ['reviews'], 'additionalProperties': False}

if __name__ == '__main__':
    import glob
    from common import SITE
    if '--site' in sys.argv:   # second pass: review the published commentary files
        items = []
        for p in sorted(glob.glob(os.path.join(SITE, 'commentary', 'pf-*.json'))):
            c = json.load(open(p))
            items.append({'id': c['view'], 'headline': c['headline'], 'text': ' '.join(c['paragraphs']), 'caveats': [x['text'] for x in c['caveats']], 'source': c['sources']})
        out = 'fairness_review_site.json'
    else:
        facts = json.load(open(os.path.join(INTERIM, 'facts.json')))['facts']
        items = [{k: f.get(k) for k in ('id', 'headline', 'text', 'caveats', 'source')} for f in facts]
        out = 'fairness_review.json'
    r = call_json('fairness_review_opus', 'claude-opus-5-5', SYSTEM, json.dumps(items, indent=1, default=str), SCHEMA, effort='high', max_tokens=32000)
    json.dump(r, open(os.path.join(INTERIM, out), 'w'), indent=1)
    for x in r['reviews']:
        print(f"\n[{x['verdict']}] {x['id']}\n  issues: {x['issues']}\n  suggested: {x['suggested_headline']}\n  caveats: {x['missing_caveats']}")
