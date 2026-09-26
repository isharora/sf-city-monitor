"""Office-holding roster for City elective offices (red-team pass 2, 2026-09-26).

Why: the first pass inferred "held office in year Y" from Form 700 cover pages (2013-2021) OR from >= 3 lobbyist-reported
contacts in the office's department. The contact rule credits legislative aides who later ran for office with holding
the seat (e.g. aides to supervisors who were contacted as staff years before they ran). That can wrongly mark a
committee as "covered" by C&GCC §1.126 and labels losing candidates as officials.

Sources (saved in data/raw/):
  * sfbos_former_supervisors.html  https://sfbos.org/former-supervisors (fetched 2026-09-26): every former member of the
    Board of Supervisors with appointed/elected term dates. Used as the authority for former members (date level).
  * sfbos_home.html                https://sfbos.org/ (fetched 2026-09-26): current members, District 1-11.
Rules:
  * Board of Supervisors, former members: held on date t iff t falls inside a listed term (min start .. max end; an
    "effective" date after a recall/resignation note ends the term).
  * Board of Supervisors, current members: the contiguous run of evidence years (Form 700 or lobbyist contacts) that
    reaches the current year; with no evidence, from the year after their last even-year campaign.
  * Anyone else with Board of Supervisors evidence who is not on either list: NOT holding (aides, staff).
  * Citywide offices (Mayor, City Attorney, District Attorney, Sheriff, Treasurer, Assessor-Recorder, Public Defender):
    since the office-history pass (2026-09-26) holding comes ONLY from the verified table pipeline/offices_citywide.json,
    one row per term (elected, appointed, interim, acting) with start/end dates and a source URL and quote per row, from
    official sources (sfmayor.org releases, Board of Supervisors minutes, department sites, archived copies via the Internet
    Archive; Wikipedia only as a pointer for exact days). The table holds the complete succession of every citywide office
    from 2009-01-01 to the as-of date, so anyone absent from it held none of these offices in 2009-2026. Form 700 and
    lobbyist-contact evidence for these offices is no longer used (it missed appointments such as Suzy Loftus as interim
    District Attorney and credited Mayor's Office staff with the Mayor's seat). `python3 roster.py verify` re-checks every
    row's quote against the cached source (data/raw/offices/) and the succession for gaps and overlaps.
    Coverage (09_analysis.Coverage.status) uses the table's exact dates; labels and terms use calendar years (partial years
    count).
  * A person cannot hold two City elective offices at once: contact-only evidence for another office in a year where the
    person is roster-confirmed on the Board of Supervisors is dropped, except in the last year (or the year before the
    listed end) of their Board service, when a move to another office is plausible (e.g. Board to Mayor in 2018).
"""
import os, re, html, json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'data', 'raw')
AS_OF_YEAR = 2026


def _text(path):
    t = open(path, encoding='utf-8', errors='ignore').read()
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<(br|p|div|h\d|li|tr|td)[^>]*>', '\n', t)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return [re.sub(r'\s+', ' ', x).strip() for x in t.split('\n') if x.strip()]


def _date(s):
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if not m:
        return None
    mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000 if y < 50 else 1900
    try:
        return pd.Timestamp(year=y, month=mo, day=d)
    except ValueError:
        return None


def former_supervisors():
    """[{name, start, end, source}] from the sfbos.org former-supervisors page (term detail section)."""
    lines = _text(os.path.join(RAW, 'sfbos_former_supervisors.html'))
    out, cur = [], None
    for i, ln in enumerate(lines):
        is_name = (i + 1 < len(lines) and lines[i + 1] in ('Elected', 'Appointed') and not re.search(r'\d', ln) and ln not in ('Elected', 'Appointed')
                   and ',' not in ln and len(ln.split()) >= 2)
        if is_name:
            cur = {'name': re.sub(r'^J eff', 'Jeff', ln), 'dates': [], 'effective_end': None}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r'effective\s+(\d{1,2}/\d{1,2}/\d{2,4})', ln)
        if m:
            cur['effective_end'] = _date(m.group(1))
        ds = [_date(d) for d in re.findall(r'\d{1,2}/\d{1,2}/\d{2,4}', ln) if not m or d != m.group(1)]
        ds = [d for d in ds if d is not None and d.year >= 1900]
        if ds:
            cur['dates'].append(ds)
        if ln.startswith('About the Board'):
            break
    res = []
    for c in out:
        ds = c['dates']
        if not ds:
            continue
        # one term per line: "start - end"; a line with a single date runs to the next term's start (or is a single day)
        pairs = []
        for j, line_dates in enumerate(ds):
            if len(line_dates) >= 2:
                pairs.append((line_dates[0], line_dates[-1]))
            else:
                nxt = ds[j + 1][0] if j + 1 < len(ds) else line_dates[0]
                pairs.append((line_dates[0], max(nxt, line_dates[0])))
        if c['effective_end'] is not None:
            pairs = [(a, min(b, c['effective_end'])) if a <= c['effective_end'] else (a, a) for a, b in pairs if a <= c['effective_end']]
            pairs = [(a, b) for a, b in pairs if b >= a]
        for a, b in pairs:
            if b < a:
                a, b = b, a
            res.append({'name': c['name'], 'start': a, 'end': b, 'source': 'https://sfbos.org/former-supervisors (fetched 2026-09-26)'})
    return res


def current_supervisors():
    lines = _text(os.path.join(RAW, 'sfbos_home.html'))
    names = set()
    for ln in lines:
        for m in re.finditer(r'(?:Supervisor|President of the Board)\s+([A-Z][A-Za-z\.\'\-]+(?:\s+[A-Z][A-Za-z\.\'\-]+){1,2}?)\s+(?:Supervisor\s+)?District\s+\d+', ln):
            names.add(m.group(1).strip())
    return sorted(names)


SINGLE = ['Mayor', 'City Attorney', 'District Attorney', 'Sheriff', 'Treasurer', 'Assessor-Recorder', 'Public Defender']


def build(hold, f700_hold, nk_of, own_committee_years):
    """Return (clean_hold, bos_intervals, audit).
    hold:  {(oid, office): set(years)} from the first pass (Form 700 + contacts);  f700_hold: same, Form 700 only.
    nk_of: function(full name) -> 'O:' + name key.   own_committee_years: {(oid, office): set(years with receipts)}."""
    former = former_supervisors()
    current = current_supervisors()
    bos_iv = {}
    for r in former:
        bos_iv.setdefault(nk_of(r['name']), []).append((r['start'], r['end']))
    cur_keys = {nk_of(n): n for n in current}
    # fallback match on last name + first initial (e.g. "Christine" vs "Christina" Olague)
    by_last = {}
    for k in list(bos_iv) + list(cur_keys):
        last, first = k[2:].split('|', 1)
        by_last.setdefault((last, first[:1]), set()).add(k)
    def alias(oid):
        if oid in bos_iv or oid in cur_keys or '|' not in oid:
            return oid
        last, first = oid[2:].split('|', 1)
        c = by_last.get((last, first[:1]), set())
        return next(iter(c)) if len(c) == 1 else oid
    for (oid, off) in list(hold):
        a = alias(oid)
        if a != oid and a in bos_iv:
            bos_iv.setdefault(oid, bos_iv[a])
        if a != oid and a in cur_keys:
            cur_keys.setdefault(oid, cur_keys[a])
    audit = {'former_supervisors_parsed': len(former), 'current_supervisors': current, 'dropped': [], 'kept_contact_only': []}
    clean = {}
    # Board of Supervisors
    for (oid, off), yrs in hold.items():
        if off != 'Board of Supervisors':
            continue
        if oid in bos_iv:
            lo_y, hi_y = min(a.year for a, b in bos_iv[oid]), max(b.year for a, b in bos_iv[oid])
            ok = {y for y in yrs if lo_y <= y <= hi_y}   # evidence inside the member's overall service span (the page has a few date typos)
        elif oid in cur_keys:
            run, y = set(), AS_OF_YEAR
            while y in yrs or (y == AS_OF_YEAR and y - 1 in yrs):
                if y in yrs:
                    run.add(y)
                y -= 1
            ok = run
        else:
            ok = set()
        for y in sorted(set(yrs) - ok):
            audit['dropped'].append({'official': oid, 'office': off, 'year': y, 'reason': 'not a member of the Board of Supervisors that year per sfbos.org roster'})
        if ok:
            clean[(oid, off)] = ok
    for oid, iv in bos_iv.items():
        ev = hold.get((oid, 'Board of Supervisors'), set())
        yrs = set()
        for a, b in iv:
            # full years from the start year up to the year before the end; the end year only when the term ended
            # after January and there is evidence of activity that year (the roster has a few imprecise end dates)
            yrs |= set(range(max(a.year, 2009), min(b.year, AS_OF_YEAR + 1)))
            if a.year == b.year or (b.month > 1 and b.year in ev):
                yrs.add(b.year) if b.year >= 2009 and (b.year in ev or a.year == b.year) else None
        if yrs:
            clean[(oid, 'Board of Supervisors')] = clean.get((oid, 'Board of Supervisors'), set()) | yrs
    for oid, n in cur_keys.items():
        if (oid, 'Board of Supervisors') not in clean:
            camp = [y for y in own_committee_years.get((oid, 'Board of Supervisors'), set()) if y % 2 == 0 and y < AS_OF_YEAR]
            if camp:
                clean[(oid, 'Board of Supervisors')] = set(range(max(camp) + 1, AS_OF_YEAR + 1))
                audit['kept_contact_only'].append({'official': oid, 'office': 'Board of Supervisors', 'years': sorted(clean[(oid, 'Board of Supervisors')]), 'reason': 'current member (sfbos.org) without contact evidence; from the year after the last campaign'})
    bos_years = {oid: ys for (oid, off), ys in clean.items() if off == 'Board of Supervisors'}
    # citywide offices: verified office-history table only (offices_citywide.json)
    city = citywide_intervals()
    for (oid, off), yrs in hold.items():
        if off not in SINGLE:
            continue
        tab = _years_of(city.get((oid, off), []))
        for y in sorted(set(yrs) - tab):
            audit['dropped'].append({'official': oid, 'office': off, 'year': y, 'reason': 'not in the verified office-history table (offices_citywide.json)'})
    for (oid, off), ivs in city.items():
        ys = _years_of(ivs)
        if ys:
            clean[(oid, off)] = ys
            added = sorted(ys - set(hold.get((oid, off), set())))
            if added:
                audit.setdefault('added_from_office_table', []).append({'official': oid, 'office': off, 'years': added,
                                                                        'roles': sorted({r['role'] for a, b, r in ivs})})
    # other bodies (Board of Education, Community College Board): first-pass evidence with the conflict rules below
    f7_by_off_year = {}
    for (oid, off), yrs in f700_hold.items():
        for y in yrs:
            f7_by_off_year.setdefault((off, y), set()).add(oid)
    for (oid, off), yrs in hold.items():
        if off == 'Board of Supervisors' or off in SINGLE:
            continue
        f7y = f700_hold.get((oid, off), set())
        ok = set()
        for y in yrs:
            if y in f7y:
                ok.add(y); continue
            last = oid[2:].split('|', 1)[0]
            others = {o for o in (f7_by_off_year.get((off, y), set()) if off in SINGLE else set()) if o[2:].split('|', 1)[0] != last}
            transition = any((y - 1 not in f700_hold.get((o, off), set())) or (y + 1 not in f700_hold.get((o, off), set())) for o in others)
            if others and not transition:
                audit['dropped'].append({'official': oid, 'office': off, 'year': y, 'reason': f'another person filed Form 700 for {off} that year'})
                continue
            span_end = max((b.year for a, b in bos_iv.get(oid, [])), default=None)
            if y in bos_years.get(oid, set()) and not (span_end is not None and span_end - 1 <= y <= span_end):
                audit['dropped'].append({'official': oid, 'office': off, 'year': y, 'reason': 'roster shows this person on the Board of Supervisors that year'})
                continue
            ok.add(y)
            audit['kept_contact_only'].append({'official': oid, 'office': off, 'year': y, 'reason': 'contact evidence, no conflict'})
        if ok:
            clean[(oid, off)] = clean.get((oid, off), set()) | ok
    return clean, bos_iv, audit


OFFICES_JSON = os.path.join(HERE, 'offices_citywide.json')
OFFICES_RAW = os.path.join(RAW, 'offices')


def _load_offices():
    return json.load(open(OFFICES_JSON, encoding='utf-8'))


def citywide_intervals():
    """{('O:' + official_key, office): [(start, end, row)]} from the verified table; an open term ends on the table's as_of date."""
    d = _load_offices()
    as_of = pd.Timestamp(d['as_of'])
    out = {}
    for r in d['terms']:
        a = pd.Timestamp(r['start'])
        b = pd.Timestamp(r['end']) if r.get('end') else as_of
        for k in [r['official_key']] + r.get('key_aliases', []):
            out.setdefault(('O:' + k, r['office']), []).append((a, b, r))
    return out


def _years_of(ivs, lo=2009):
    ys = set()
    for a, b, r in ivs:
        ys |= set(range(max(a.year, lo), min(b.year, AS_OF_YEAR) + 1))
    return ys


def citywide_status(city, oid, office, t):
    """The term covering date t for (official, office), or None."""
    if t < pd.Timestamp('2009-01-01'):   # same scope as the rest of the roster (2009-2026); earlier holding is not used for coverage
        return None
    for a, b, r in city.get((oid, office), []):
        if a <= t <= b:
            return r
    return None


def _src_text(url):
    """Visible text of a cached source (data/raw/offices/<name>); fetched with curl on first use."""
    import subprocess
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', re.sub(r'^https?://', '', url))[:150] + ('.pdf' if url.lower().endswith('.pdf') else '.html')
    p = os.path.join(OFFICES_RAW, name)
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        os.makedirs(OFFICES_RAW, exist_ok=True)
        import time
        for attempt in range(3):
            r = subprocess.run(['perl', '-e', 'alarm 60; exec @ARGV', 'curl', '-sL', '-A', 'Mozilla/5.0 (Macintosh)', '-o', p, '-w', '%{http_code}', url],
                               capture_output=True, text=True)
            if r.stdout.startswith('200'):
                break
            if os.path.exists(p):
                os.remove(p)
            time.sleep(10 * (attempt + 1))
    if not os.path.exists(p):
        return ''
    if p.endswith('.pdf'):
        import pypdf
        t = ' '.join(pg.extract_text() or '' for pg in pypdf.PdfReader(p).pages)
    else:
        t = open(p, encoding='utf-8', errors='ignore').read()
        t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
        t = html.unescape(re.sub(r'<[^>]+>', ' ', t))
    return re.sub(r'\s+', ' ', t)


def verify():
    """Check every quote against its cached source, and the succession of each office for gaps and overlaps from 2009."""
    d = _load_offices()
    res = {'rows': [], 'succession': {}, 'ok': True}
    norm = lambda x: re.sub(r'\s+', ' ', x.replace('\u2019', "'").replace('\u2018', "'")).strip().lower()
    for r in d['terms']:
        for src in [{'url': r['source_url'], 'quote': r['source_quote'], 'archived_url': r.get('archived_url')}] + r.get('more_sources', []):
            found = norm(src['quote']) in norm(_src_text(src.get('archived_url') or src['url']))
            res['rows'].append({'id': r['id'], 'url': src['url'], 'quote_found': found})
            res['ok'] &= found
    as_of = pd.Timestamp(d['as_of'])
    for off in SINGLE:
        ts = sorted(((pd.Timestamp(r['start']), pd.Timestamp(r['end']) if r.get('end') else as_of, r['id']) for r in d['terms']
                     if r['office'] == off and not r.get('concurrent_with') and (not r.get('end') or r['end'] >= '2009-01-01')), key=lambda x: x[0])
        vac = [(pd.Timestamp(v['from']), pd.Timestamp(v['to'])) for v in d.get('known_vacancies', []) if v['office'] == off]
        gaps, overlaps = [], []
        if not ts or ts[0][0] > pd.Timestamp('2009-01-01'):
            gaps.append('no holder on 2009-01-01')
        for (a1, b1, i1), (a2, b2, i2) in zip(ts, ts[1:]):
            g = (a2 - b1).days
            if g > 31 and not any(va <= b1 + pd.Timedelta(days=1) and vb >= a2 - pd.Timedelta(days=1) for va, vb in vac):
                gaps.append(f'{i1} -> {i2}: {g} days')
            if g < -1:
                overlaps.append(f'{i1} -> {i2}: {-g} days')
        if ts and ts[-1][1] < as_of:
            gaps.append('no holder on the as-of date')
        res['succession'][off] = {'terms': [i for a, b, i in ts], 'gaps_over_31_days': gaps, 'overlaps': overlaps}
        res['ok'] &= not gaps and not overlaps
    return res


def bos_held_on(bos_iv, oid, t):
    return any(a <= t <= b for a, b in bos_iv.get(oid, []))


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        r = verify()
        out = os.path.join(HERE, '..', 'data', 'redteam', 'offices_citywide_verify.json')
        json.dump(r, open(out, 'w'), indent=1)
        bad = [x for x in r['rows'] if not x['quote_found']]
        print('quotes checked', len(r['rows']), 'not found', len(bad), [b['id'] + ' ' + b['url'] for b in bad])
        for off, v in r['succession'].items():
            print(off, v['terms'], v['gaps_over_31_days'], v['overlaps'])
        print('OK' if r['ok'] else 'PROBLEMS')
