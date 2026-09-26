"""Verify that every number in the network commentary traces to data.

For each commentary file (data/site/commentary/nw-*.json and story_nw.json):
  1. every traced item in data/site/commentary_facts.json for that file is re-resolved from its source and re-formatted
     (numbers), found verbatim in meta.rules (rule phrases), or found in the source text (literals); a mismatch is an error;
  2. every string shown to readers (headline, paragraphs, annotation text and x, live templates and fallbacks, caveats, story
     titles and text) is scanned; traced items are removed, then document identifiers (§ sections, form numbers, ordinance
     and directive numbers) and {slot} placeholders are masked, and any digit left over is an UNTRACED number.
Exit status 1 if anything is untraced or does not verify. Writes data/redteam/verify_commentary.json.
"""
import os, re, sys, json, glob, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
spec = importlib.util.spec_from_file_location('c15', os.path.join(HERE, '15_commentary.py'))
c15 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c15)

IDENT = [r'§\s?\d+(?:\.\d+)*(?:\([a-z0-9]+\))*', r'\bForms? \d+\b', r'\bSFEC-\d+(?:\([a-z0-9]+\))*\d*', r'\bOrd\. \d+-\d+',
         r'\bExecutive Directive \d+-\d+', r'\{\w+\}']


def texts(obj):
    out = []
    if 'steps' in obj:
        for s in obj['steps']:
            out += [('steps.title', s.get('title', '')), ('steps.text', s.get('text', ''))]
        out.append(('title', obj.get('title', '')))
        return out
    out.append(('headline', obj.get('headline') or ''))
    out += [('paragraphs', p) for p in obj.get('paragraphs', [])]
    for a in obj.get('annotations', []):
        out += [('annotations.text', a.get('text', '')), ('annotations.x', str(a.get('x', '')))]
    for t in obj.get('templates', []):
        out += [('templates.template', t.get('template', '')), ('templates.fallback', t.get('fallback', ''))]
    out += [('caveats', c.get('text', '')) for c in obj.get('caveats', [])]
    return out


def check_item(it):
    if it['kind'] == 'rule':
        rid = re.search(r'id=(\w+)', it['source']).group(1)
        r = next(x for x in json.load(open(os.path.join(DATA, 'site/meta.json')))['rules'] if x['id'] == rid)
        return it['text'] in r['text'] or it['text'] in r['cite']
    if it['kind'] == 'literal':
        src = it['source']
        blob = json.dumps(c15.resolve(src) if '#' in src else c15.load(src.split('#')[0]), ensure_ascii=False)
        return it['must_contain'] in blob
    v = c15.resolve(it['source'])
    return c15.FMT[it['kind']](v) == it['text']


def main():
    facts = json.load(open(os.path.join(DATA, 'site/commentary_facts.json')))['facts']
    by_file = {}
    for f in facts:
        by_file.setdefault(f['file'], []).append(f)
    report = {'files': {}, 'untraced': [], 'failed_sources': [], 'n_traced_items': len(facts)}
    for f in facts:
        try:
            ok = check_item(f)
        except Exception as e:
            ok = False
            f = dict(f, error=repr(e)[:200])
        if not ok:
            report['failed_sources'].append(f)
    for p in sorted(glob.glob(os.path.join(DATA, 'site/commentary/*.json'))):
        name = os.path.basename(p)[:-5]
        obj = json.load(open(p))
        items = sorted(by_file.get(name, []), key=lambda x: -len(x['text']))
        n_numbers = 0
        for field, s in texts(obj):
            rest = s
            for rx in IDENT:
                rest = re.sub(rx, ' ', rest)
            for it in items:
                if it['text'] and it['text'] in rest:
                    n_numbers += rest.count(it['text'])
                    rest = rest.replace(it['text'], ' ')
            for m in re.finditer(r'\$?\d[\d,.]*%?', rest):
                report['untraced'].append({'file': name, 'field': field, 'token': m.group(0), 'context': rest[max(0, m.start() - 40): m.end() + 40]})
        report['files'][name] = {'traced_numbers_found': n_numbers}
    report['ok'] = not report['untraced'] and not report['failed_sources']
    os.makedirs(os.path.join(DATA, 'redteam'), exist_ok=True)
    json.dump(report, open(os.path.join(DATA, 'redteam', 'verify_commentary.json'), 'w'), indent=1, ensure_ascii=False)
    print(f"traced items {len(facts)}; failed sources {len(report['failed_sources'])}; untraced numbers {len(report['untraced'])}")
    for u in report['untraced'][:60]:
        print('  UNTRACED', u['file'], u['field'], repr(u['token']), '...', u['context'])
    for u in report['failed_sources'][:20]:
        print('  FAILED', u)
    sys.exit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
