"""Verify the Budget-vs-outcomes commentary: zero untraced numbers.

For every commentary surface (commentary/pf-*.json, story_pf.json, facts_pf.json, and the `commentary` block of every
scorecards/<DEPT>.json) this script
  1. extracts every number from every piece of text (headline, paragraphs, callouts, caveats, live templates with the
     {slots} removed, fallbacks, story steps, fact headlines);
  2. requires each one to match a traced number for that file in data/redteam/commentary_trace.json;
  3. re-derives every traced number from its declared source with code written here (not imported from the generator)
     and requires the formatted result to equal the text;
  4. checks constants against their documents and spot-checks red-team values against the site files.
Exempt by rule, and counted: calendar and fiscal years, dates (June 30, July 1), and fixed names (911, 311, First 5, Code 3,
Priority A, Section 10B). Exit code 1 on any failure. Writes data/redteam/verify_commentary.json.
"""
import json, os, re, sys, glob
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, 'data', 'site')
RT = os.path.join(ROOT, 'data', 'redteam')
INTERIM = os.path.join(ROOT, 'data', 'interim')
J = lambda p: json.load(open(p))
TR = J(os.path.join(RT, 'commentary_trace.json'))
R2 = J(os.path.join(RT, 'redteam2.json'))
fails, exempt = [], {}

# ---------------------------------------------------------------- formats (the display rules; must match the text)
def mmss(v):
    m, s = int(v), int(round((v - int(v)) * 60))
    return f'{m + 1} min 00 s' if s == 60 else f'{m} min {s:02d} s'
FMT = {'pct': lambda v: f'{v*100:.0f}%', 'pct1': lambda v: f'{v*100:.1f}%', 'spct': lambda v: f'{v*100:+.0f}%', 'apct': lambda v: f'{abs(v)*100:.0f}%',
       'apct1': lambda v: f'{abs(v)*100:.1f}%', 'pts': lambda v: f'{v*100:.0f}', 'usd': lambda v: f'${v:,.0f}', 'usd2': lambda v: f'${v:,.2f}',
       'm': lambda v: f'${v/1e9:,.1f} billion' if abs(v) >= 1e9 else f'${v/1e6:,.0f} million', 'm1': lambda v: f'${v/1e6:,.1f} million',
       'b': lambda v: f'${v/1e9:,.1f} billion', 'int': lambda v: f'{v:,.0f}', 'x1': lambda v: f'{v:.1f}', 'x2': lambda v: f'{v:.2f}',
       'yrs': lambda v: f'{v:.1f}', 'mmss': mmss, 'mins': lambda v: f'{v:.1f}', 'mil': lambda v: f'{v/1e6:.1f} million'}

# ---------------------------------------------------------------- independent recomputation from site files
meta = J(os.path.join(SITE, 'meta.json'))
defl = {int(k): float(v) for k, v in meta['deflator']['index'].items()}
popn = {int(k): int(v) for k, v in meta['population']['by_fy'].items()}
cells = J(os.path.join(SITE, 'spending/cells.json'))['cells']
staff = J(os.path.join(SITE, 'staffing/cells.json'))['cells']
meas = J(os.path.join(SITE, 'measures/measures.json'))['measures']
vals = J(os.path.join(SITE, 'measures/values.json'))['rows']
series = J(os.path.join(SITE, 'outcomes/series.json'))['rows']
links = {l['pair']: l['measure'] for l in J(os.path.join(SITE, 'measures/cost_links.json'))['links']}
real_ids = {m['id'] for m in meas if not m.get('derived')}
mtype = {m['id']: m['type'] for m in meas}
mdept = {m['id']: m['dept'] for m in meas}
scored = [v for v in vals if v['measure'] in real_ids and v['met'] is not None]
OPER_CHARS = {'salaries', 'fringe', 'overtime', 'nonpersonnel', 'aid'}
FIVE = {'POL', 'MTA', 'DPH', 'FIR', 'SHF'}


def oper_real(dept, fy):
    return sum(c['actual'] / defl[fy] for c in cells if c['dept'] == dept and c['fy'] == fy and c['char'] in OPER_CHARS and c['actual'] is not None)


def met_rows(fy, dept=None):
    return [v for v in scored if v['fy'] == fy and (dept is None or mdept[v['measure']] == dept)]


def share(rows):
    return sum(1 for v in rows if v['met']) / len(rows)


def panel_ids(a, b):
    yrs = {}
    for v in scored:
        if a <= v['fy'] <= b:
            yrs.setdefault(v['measure'], set()).add(v['fy'])
    return {m for m, s in yrs.items() if len(s) == b - a + 1}


def st(fy, dept=None):
    return [s for s in staff if s['fy'] == fy and (dept is None or s['dept'] == dept)]


def cpu(pair, fy):
    r = [v for v in vals if v['measure'] == links[pair] and v['fy'] == fy][0]
    return r


SITEF = {
    'oper_real': lambda d, fy: oper_real(d, int(fy)),
    'oper_real_change': lambda d, a, b: oper_real(d, int(b)) / oper_real(d, int(a)) - 1,
    'all_nominal': lambda fy: sum(c['actual'] for c in cells if c['fy'] == int(fy) and c['actual'] is not None),
    'all_real_per_res': lambda fy: sum(c['actual'] / defl[int(fy)] for c in cells if c['fy'] == int(fy) and c['actual'] is not None) / popn[int(fy)],
    'fund_oper_ratio': lambda f, fy: (lambda rs: sum(c['actual'] or 0 for c in rs) / sum(c['budget'] or 0 for c in rs))(
        [c for c in cells if c['fy'] == int(fy) and c['fund'] == f and c['char'] in OPER_CHARS]),
    'met_share': lambda fy: share(met_rows(int(fy))),
    'met_n': lambda fy: len(met_rows(int(fy))),
    'met_share_type': lambda t, fy: share([v for v in met_rows(int(fy)) if mtype[v['measure']] == t]),
    'panel_n': lambda a, b: len(panel_ids(int(a), int(b))),
    'panel_share': lambda a, b, fy: (lambda ids: share([v for v in met_rows(int(fy)) if v['measure'] in ids]))(panel_ids(int(a), int(b))),
    'met_share_dept': lambda d, fy: share(met_rows(int(fy), d)),
    'met_n_dept': lambda d, fy: len(met_rows(int(fy), d)),
    'met_count_dept': lambda d, fy: sum(1 for v in met_rows(int(fy), d) if v['met']),
    'ot_share_city': lambda fy: (lambda rs: sum(s['overtime'] for s in rs) / sum(s['salaries'] + s['overtime'] for s in rs))(st(int(fy))),
    'ot_total_city': lambda fy: sum(s['overtime'] for s in st(int(fy))),
    'ot_top5_share': lambda fy: sum(s['overtime'] for s in st(int(fy)) if s['dept'] in FIVE) / sum(s['overtime'] for s in st(int(fy))),
    'ot_share_dept': lambda d, fy: st(int(fy), d)[0]['ot_share'],
    'ot_dept': lambda d, fy: st(int(fy), d)[0]['overtime'],
    'ot100k_dept': lambda d, fy: st(int(fy), d)[0]['employees_ot_over_100k'],
    'cpu_real': lambda p, fy: cpu(p, int(fy))['cost_per_unit'] / defl[int(fy)],
    'cpu_real_change': lambda p, a, b: (cpu(p, int(b))['cost_per_unit'] / defl[int(b)]) / (cpu(p, int(a))['cost_per_unit'] / defl[int(a)]) - 1,
    'cpu_cost_real': lambda p, fy: cpu(p, int(fy))['program_cost'] / defl[int(fy)],
}

REPORT = open(os.path.join(ROOT, 'data', 'raw', 'capital', 'reports', 'FY24-FY25_Capital_Report.txt')).read()
CONST_OK = {  # constant key -> check (document evidence)
    'k85': lambda v: v == 0.85, 'irs': lambda v: v == 0.85 and 'expend at least 85%' in REPORT,
    'arb': lambda v: v == 1.46e6 and 'rebated $1.46' in REPORT, 'dly1': lambda v: v == 9 and 'delayed by 9 and 10 years' in REPORT,
    'dly2': lambda v: v == 10 and 'delayed by 9 and 10 years' in REPORT, 'k5': lambda v: v == 0.05, 'k05': lambda v: v == 0.005,
    'even': lambda v: abs(v - 1 / 12) < 1e-12, 'k100k': lambda v: v == 100000, 'k430': lambda v: v == 4.5,
    'npairs': lambda v: v == len(links),
}


def rt2(path):
    o = R2
    for p in path.split('.'):
        o = o[int(p)] if isinstance(o, list) else o[p]
    return o


def derive(key, numbers, seen=()):
    src = numbers[key]['source']
    kind, _, rest = src.partition(':')
    if kind == 'rt2':
        return float(rt2(rest))
    if kind == 'rt2dept':
        d, f = rest.split(':')
        return float(next(r for r in R2['t2_target_easing']['per_dept']['rows'] if r['dept'] == d)[f])
    if kind == 'site':
        fn, *args = rest.split(':')
        return float(SITEF[fn](*args))
    if kind == 'series':
        name, fy = rest.split(':')
        return float(next(r['value'] for r in series if r['series'] == name and r['fy'] == int(fy)))
    if kind == 'interim':
        f, kv, col = rest.split(':')
        k, v = kv.split('=')
        d = pd.read_csv(os.path.join(INTERIM, f))
        return float(d[d[k].astype(str) == v][col].iloc[0])
    if kind == 'ratio':
        a, b = rest.split(':')[0].split('/')
        return derive(a, numbers) / derive(b, numbers) - (1 if rest.endswith(':minus1') else 0)
    if kind == 'diff':
        a, b = rest.split('-')
        return derive(a, numbers) - derive(b, numbers)
    if kind == 'const':
        v = numbers[key]['value']
        if key not in CONST_OK or not CONST_OK[key](v):
            fails.append(f'constant {key} not verified against its document ({rest})')
        return v
    raise ValueError(src)


# ---------------------------------------------------------------- text extraction
EXEMPT = [(r'\bFY\d{4}\b', 'fiscal year'), (r'\b(?:19|20)\d{2}\b(?!%|,\d|\.\d)', 'calendar year'), (r'\bJune 30\b|\bJuly 1\b', 'date'),
          (r'\b911\b', 'name'), (r'\b311\b', 'name'), (r'\bFirst 5\b', 'name'), (r'\bCode 3\b', 'name'), (r'\bSection 10B\b', 'name'), (r'\bPriority [ABC]\b', 'name')]
TOKEN = re.compile(r'\d+ min \d{2} s|[+-]?\$\d[\d,]*(?:\.\d+)?(?: (?:million|billion))?|[+-]?\d[\d,]*(?:\.\d+)?%|[+-]?\d[\d,]*(?:\.\d+)?(?: million)?')


def texts(obj, path):
    out = []
    if path.startswith('scorecards/'):
        c = obj.get('commentary') or {}
        out += [c.get('headline') or ''] + c.get('paragraphs', []) + [x['text'] for x in c.get('caveats', [])]
        return out
    out += [obj.get('headline') or ''] + (obj.get('paragraphs') or [])
    out += [a['text'] for a in obj.get('annotations') or []] + [c['text'] for c in obj.get('caveats') or []]
    for t in obj.get('templates') or []:
        out += [re.sub(r'\{[a-z0-9_]+\}', ' ', t['template']), t.get('fallback') or '']
    for s in obj.get('steps') or []:
        out += [s.get('title') or '', s.get('text') or '']
    out += [obj.get('title') or ''] + [f.get('headline') or '' for f in obj.get('facts') or []]
    return out


def tokens(text):
    for pat, lab in EXEMPT:
        for m in re.finditer(pat, text):
            exempt[lab] = exempt.get(lab, 0) + 1
        text = re.sub(pat, ' ', text)
    return [t.strip() for t in TOKEN.findall(text)]


def main():
    numbers, trace = TR['numbers'], TR['trace']
    files = sorted(glob.glob(os.path.join(SITE, 'commentary', '*.json'))) + sorted(glob.glob(os.path.join(SITE, 'scorecards', '*.json')))
    n_tokens, per_file = 0, {}
    for p in files:
        rel = os.path.relpath(p, SITE)
        obj = J(p)
        from collections import Counter
        allowed = Counter(t['text'].lstrip('+') for t in trace.get(rel, []))  # each traced use can back one occurrence
        toks = [t for x in texts(obj, rel) for t in tokens(x)]
        n_tokens += len(toks)
        bad = []
        for t in toks:
            k = t.lstrip('+')
            if allowed[k] > 0:
                allowed[k] -= 1
            else:
                bad.append(t)
        per_file[rel] = {'numbers': len(toks), 'untraced': bad}
        fails.extend(f'{rel}: untraced number "{t}"' for t in bad)
        if rel.startswith('scorecards/') and 'commentary' not in obj:
            fails.append(f'{rel}: no commentary block')
    checked = 0
    for rel, entries in trace.items():
        for e in entries:
            v = derive(e['key'], numbers)
            if FMT[e['kind']](v) != e['text']:
                fails.append(f"{rel}: {e['key']} re-derives to {FMT[e['kind']](v)} but text says {e['text']} ({numbers[e['key']]['source']})")
            checked += 1
    # spot-check red-team values against the site files
    for fy in (2013, 2021, 2025):
        gf = sum(c['actual'] for c in cells if c['fy'] == fy and c['fund'] == 'gf' and c['char'] in OPER_CHARS and c['actual'] is not None) / defl[fy] / popn[fy]
        if abs(gf - R2['t1_gf_per_resident']['per_res_real'][str(fy)]) > 0.5:
            fails.append(f'redteam2 t1 per resident FY{fy} disagrees with site cells')
    f25 = next(r['value'] for r in series if r['series'] == 'fire_code3_medical_first_unit_median_min' and r['fy'] == 2025)
    if abs(f25 - R2['t3_fire']['by_fy']['2025']['final']['call_to_arrival_median']) > 0.05:
        fails.append('redteam2 fire median FY2025 differs from outcomes/series.json by more than 3 seconds')
    rep = {'files': len(files), 'numbers_in_text': n_tokens, 'traced_uses_rederived': checked, 'distinct_traced_numbers': len(numbers),
           'exempt_tokens': exempt, 'failures': fails, 'per_file': per_file}
    json.dump(rep, open(os.path.join(RT, 'verify_commentary.json'), 'w'), indent=1)
    print(f"{len(files)} files, {n_tokens} numbers in text, {checked} traced uses re-derived, exempt {exempt}")
    print('FAILURES:' if fails else 'OK: zero untraced or mismatched numbers')
    for f in fails:
        print('  ', f)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
