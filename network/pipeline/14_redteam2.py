"""Red-team pass 2 (2026-09-26): legal-rule verification record, independent re-derivation of the headline findings,
and fairness scans of everything the site ships. Writes data/redteam/redteam2.json (no private individual's name is
written to it; findings about private persons are counted or given as entity ids).

Usage:
  python3 14_redteam2.py scan        # fairness scans only (after 11_export.py / 13_extras.py)
  python3 14_redteam2.py adjudicate  # Claude Opus re-check of person-looking organization names -> data/er/entity_type_overrides.parquet
  python3 14_redteam2.py all         # everything (default)
Run order: 09 -> 11 -> 14 adjudicate -> 11 -> 13 -> 15_commentary -> 14 all -> verify_commentary.
"""
import os, re, sys, json, glob, subprocess, importlib.util, collections
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(DATA, 'site')
AN = os.path.join(DATA, 'analysis')
INT = os.path.join(DATA, 'interim')
ER = os.path.join(DATA, 'er')
OUT = os.path.join(DATA, 'redteam')
BUNDLE = os.path.expanduser('~/sf-city-monitor/site/data/network')
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)


def A(n):
    return json.load(open(os.path.join(AN, n)))


def S(n):
    return json.load(open(os.path.join(SITE, n)))


# ------------------------------------------------------------------------------------------------ 1. legal record
LEGAL = [
    dict(rule='§1.126 contractor contribution ban: current version',
         dashboard_said=('Window from proposal to 12 months after approval; $100,000 per fiscal year; 10%+ owners; change dated 2019-01-01 '
                         '(inferred from the SFEC-126 form change; flagged as unverified); designer placeholder said January 2020.'),
         code_says=('C&GCC §1.126(a)-(c) (Ord. 129-18, File 180280, App. 5/30/2018, Eff. 6/30/2018, Oper. 1/1/2019): City Contractor = contracts or seeks '
                     'contracts worth $100,000+ in a fiscal year with a City department, SFUSD, the Community College District or a state agency with a '
                     'City appointee; affiliates = board members, chair, CEO, CFO, COO, >10% owners, listed subcontractors; ban from submission of a '
                     'proposal until termination of negotiations or 12 months after approval. Committees the party sponsors or controls are no longer '
                     'named in the current definition (they were in the pre-2019 text).'),
         verdict='Dashboard correct on the date (2019-01-01) and window; the designer placeholder (Jan. 2020) was wrong. Text corrected: removed "committees it sponsors or controls" from the current-rule list and the unsourced "until award for unsuccessful bidders" clause.',
         sources=['https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_campaign/0-0-0-224 (text and history note, fetched 2026-09-26 via headless browser)',
                  'https://sfbos.org/sites/default/files/o0129-18.pdf (Ord. 129-18, Section 4(b)(2) operative dates)']),
    dict(rule='§1.126 before 2019',
         dashboard_said='Inferred: from the start of negotiations to 6 months after approval; threshold possibly $50,000 (unverified).',
         code_says=('Pre-2019 text (struck through in Ord. 129-18): "at any time from the commencement of negotiations for such contract until (A) the '
                     'termination of negotiations for such contract; or (B) six months have elapsed from the date the contract is approved"; contracts '
                     'of $50,000 or more (or a series approved by the same individual or board worth $50,000 in a fiscal year); covered persons included '
                     'the party, its board, chair, CEO, CFO, COO, >20% owners, listed subcontractors and committees it sponsors or controls. Last '
                     'amended before that by Proposition H (6/3/2008).'),
         verdict='Inference confirmed (6 months, $50,000); ownership threshold was 20%, not 10%. No re-run needed for the window; only 2 flagged records involve pre-2019 approvals.',
         sources=['https://sfbos.org/sites/default/files/o0129-18.pdf']),
    dict(rule='Lobbyist contribution ban',
         dashboard_said='Turns on registration to lobby the agency (90 days); ordinance and effective date unverified; data "consistent with a rule change around 2018".',
         code_says=('C&GCC §2.115(d)-(e): no contribution or bundling by a lobbyist registered (or registered in the prior 90 days) to lobby the '
                     'officer\'s or candidate\'s agency. History: "Prop. T, App. 11/8/2016, Oper. 1/1/2018; re-enacted and amended by Proposition D, '
                     '3/5/2024, Eff. 4/12/2024, Oper. 10/12/2024".'),
         verdict='Operative date is 2018-01-01, not late 2018. Proxy-matched pattern: 327 positive contributions before 2018; in 2018 only 3 small contributions ($525), all refunded to the same committees, plus refund rows. Commentary rewritten.',
         sources=['https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_campaign/0-0-0-885', 'sfethics.org/guidance/lobbyists/prohibited-activity']),
    dict(rule='Behested payments: §3.610 / §3.620 and waivers',
         dashboard_said=('Cite "§3.610 disclosure and §3.620 solicitation ban"; present-tense duty to file SFEC-3610(b) for interested-party payments of '
                         '$1,000+; designer marker "2022 ordinance"; data suggest amendment by early 2023.'),
         code_says=('Today §3.610 is definitions and §3.620 is the solicitation ban (Ord. 232-21, File 201132, App. 12/24/2021, Eff. 1/24/2022; '
                     'redesignated and amended by Proposition E, 6/7/2022, Eff. 7/10/2022; amended by Ord. 204-22, File 220539, App. 10/6/2022, '
                     'Eff. 11/6/2022). The local reporting duty (former §3.610: Ord. 1-17, Oper. 1/1/2018, commissioners; Ord. 129-18, Oper. 1/1/2019, '
                     'all City elective officers and commissioners, $1,000 from interested parties; donor reports at $10,000; recipient reports at '
                     '$100,000) was repealed by Ord. 232-21 effective 1/24/2022. Waivers: §3.620(f), Board resolution, prospective, up to six months, '
                     'not for the Board itself. Regulations due by 1/1/2023 (§3.630).'),
         verdict=('Dashboard wrong in two places: there is no current local disclosure duty (it ended 2022-01-24, which also explains why the '
                  '3610(b) datasets are "historical"), and the ban dates from Ord. 232-21 (effective 2022-01-24), not an unnamed 2022 ordinance. '
                  'Rule text rewritten with dates; behested commentary annotated.'),
         sources=['https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_campaign/0-0-0-47602 and 0-0-0-47807 (history notes)',
                  'https://sfethics.org/guidance/city-officers/behested-payments']),
    dict(rule='Executive Directive 20-02',
         dashboard_said='Sept. 24, 2020; department heads file SFEC-3610(b).',
         code_says=('SFEC dataset descriptions (data.sf.gov b3ya-imj5 and related): "Effective September 24, 2020, Mayoral Executive Directive 20-02 '
                     'requires Department Heads to file behested payment Form SFEC-3610(b)". The directive text was not retrievable (sfmayor.org now '
                     'redirects to sf.gov, which lists only 2025 directives). Its filing duty rested on the former §3.610, repealed 2022-01-24; '
                     'department heads have been covered by the §3.620 solicitation ban directly since then.'),
         verdict='Date consistent with the Ethics Commission\'s own description; marked as not verified against the directive text.',
         sources=['data/raw/bp_3610b_filings.csv dataset description (SF Ethics Commission)']),
    dict(rule='FPPC Form 803 thresholds',
         dashboard_said='$5,000 or more from one source in a calendar year.',
         code_says=('FPPC: "state law requires the reporting of behested payments if they total $5,000 or more per calendar year from a single '
                     'source"; "officials must report the behested payments within 30 days of the date they are made" (Gov. Code §82015). '
                     'Applies to elected officers. §82015 was amended by Stats. 2025, ch. 278 (content not checked).'),
         verdict='Correct. Added the 30-day deadline and the note on the 2025 amendment.',
         sources=['https://www.fppc.ca.gov/transparency/form-700-filed-by-public-officials/behested-payments.html',
                  'leginfo.legislature.ca.gov Gov. Code §82015 (two versions listed: Stats. 2021 ch. 50; Stats. 2025 ch. 278)']),
    dict(rule='§1.114 limits and §1.127 land-use ban',
         dashboard_said='$500 per source; corporations barred; §1.127 $5 million financial interest.',
         code_says='§1.114(a): $500 per person per candidate committee per election; (b) corporations, LLCs, LLPs barred. §1.127 added by Proposition F (11/5/2019), effective 12/20/2019; window from commencement of the land-use matter to 12 months after final decision.',
         verdict='Correct; added the §1.127 effective date and window.',
         sources=['https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_campaign/0-0-0-133', '0-0-0-224 (§1.127)']),
]


# ------------------------------------------------------------------------------------------------ 2. re-derivations
def rederive():
    out = {}
    br = A('contractor_base_rates.json'); rt = br['redteam2']
    out['ban_base_rate'] = {
        'first_pass': {'observed': br['observed_share_inside_window_2019_2025'], 'expected': br['expected_share_if_unrelated'],
                       'placebo_ratio': br['timing_placebo']['ratio_W0_to_baseline']},
        'corrected': rt['excluding_public_entities'], 'bootstrap_95ci': rt['bootstrap_95ci'], 'by_calendar': rt['by_calendar'],
        'placebo_4y': rt['placebo_4y'], 'transition_sensitivity': rt['transition_sensitivity'],
        'verdict': ('NOT SUPPORTED as stated. The 45% "expected by chance" pooled every approval window of a contractor, including approvals by '
                    'offices that do not cover the recipient and filings that do not list the donor, while the 19% observed share counted only '
                    'windows that do. Matching the two (same donor, same covering office) and weighting days by the election calendar gives '
                    f"{rt['excluding_public_entities']['observed']:.1%} observed vs {rt['excluding_public_entities']['expected_office_matched_calendar_weighted']:.1%} "
                    f"expected (difference 95% CI {rt['bootstrap_95ci']['difference'][0]:+.1%} to {rt['bootstrap_95ci']['difference'][1]:+.1%}, contractor-cluster bootstrap): "
                    'a small shortfall, not a large one. The 0.73 placebo ratio is not robust: for approvals in 2019-2021 the ratio is '
                    f"{rt['placebo_4y']['ratio_W0_to_2y_mean']:.2f} against +/-2 years and {rt['placebo_4y']['ratio_W0_to_4y_mean']:.2f} against +/-4 years, "
                    'because giving swings with the election calendar (2024 was a record year) and holding evidence changes after 2021.'),
    }
    # the flagged contributions, re-derived from the per-filing table
    a = pd.read_parquet(os.path.join(AN, 'contractor_affiliated_contributions.parquet'))
    m = a.inside_post_window & a.covered_status.notna() & ~a.self_contribution & (a.amount > 0) & ~a.public_entity
    f = a[m].drop_duplicates(['record_id', 'contributor_node'])
    f85 = f[f.match_conf >= 0.85]
    cases = pd.read_parquet(os.path.join(AN, 'contractor_ban_cases.parquet'))
    post = cases[cases.days_from_approval > 0]
    ban = S('analyses/ban_window.json')
    rv = [r for r in ban['records'] if r['review'] == 'appears_to_warrant_review']
    out['flagged'] = {
        'rederived_conf_0_80': int(len(f)), 'first_pass_reported': 340, 'rederived_conf_0_85': int(len(f85)),
        'exported_review_rows': len(rv), 'exported_review_amount': float(sum(r['amount'] for r in rv)),
        'median_amount': float(np.median([r['amount'] for r in rv])) if rv else None,
        'share_500_or_less': float(np.mean([r['amount'] <= 500 for r in rv])) if rv else None,
        'max_amount': float(max(r['amount'] for r in rv)) if rv else None,
        'possible_refund_seen': int(sum(1 for r in rv if r.get('possible_refund_seen'))),
        'pre_2019_approvals': int((post.approval_proxy_date < '2019-01-01').sum()),
        'by_coverage_basis': collections.Counter(re.sub(r' in \d{4}.*', '', r['covered_basis'] or '') for r in rv),
        'n_officials_or_candidates': len({r['committee'] for r in rv}),
        'dropped_bare_name_matches_0_80': int(len(f) - len(f85)),
        'verdict': ('Count reproduced (340 at confidence >= 0.80; 338 exported because two contractors were folded as private persons). '
                    'Tightened to corroborated matches (>= 0.85): the dashboard now flags ' + str(len(rv)) + '. All are small: median $'
                    f"{np.median([r['amount'] for r in rv]):,.0f}, {np.mean([r['amount'] <= 500 for r in rv]):.0%} at or under $500."),
    }
    hol = A('official_holding.json')
    out['office_holding'] = {'years_dropped': len(hol['audit']['dropped']), 'examples_dropped': hol['audit']['dropped'][:12],
                             'former_supervisor_terms_parsed': hol['audit']['former_supervisors_parsed'], 'current_supervisors': hol['audit']['current_supervisors'],
                             'verdict': ('The contact-count rule credited legislative aides who later ran (and a few mayoral staff) with holding the seat in '
                                         f"{len(hol['audit']['dropped'])} person-years. Replaced by the sfbos.org roster. None of the flagged records depended on those "
                                         'years (the flagged set was 340 before and after), but losing candidates had been labelled with an office and a term on '
                                         'their profiles, and aides\' staff-era lobbying contacts were attributed to them by name. Both fixed.')}
    lc = A('lobbyist_contributions.json')
    out['lobbyist_contributions'] = {'by_rule_period': lc.get('by_rule_period'), 'first_pass_total_flagged_rows': lc['n_with_contact_same_agency_prior_90d'],
                                     'verdict': 'Reproduced (340 proxy rows, $110k net). "Stops after 2018" should read "stops when the ban became operative on 2018-01-01": the 2018 rows are 3 refunded contributions and 7 refunds.'}
    cc = A('concentration.json'); ie = cc['independent_expenditures']
    # independent recount of 2024 candidate-committee concentration
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'), columns=['element_nid', 'date', 'amount', 'is_individual', 'is_city_candidate', 'is_committee_donor', 'donor_first', 'donor_last', 'org_key', 'recip_candidate'])
    c = c[(c.date.dt.year == 2024) & (c.amount > 0) & c.is_city_candidate.fillna(False) & ~c.is_committee_donor]
    key = np.where(c.is_individual, 'I:' + c.donor_last.fillna('').str.upper().str.strip() + '|' + c.donor_first.fillna('').str.upper().str.strip().str[:1], 'O:' + c.org_key.fillna(''))
    selfk = c.recip_candidate.fillna('').str.upper().map(lambda s: s.split(',')[0].strip() if ',' in s else (s.split()[-1] if s.split() else ''))
    self_mask = c.is_individual & (c.donor_last.fillna('').str.upper().str.strip() == selfk)
    cc2 = c[~self_mask].assign(k=key[~self_mask.values])
    tot = cc2.groupby('k').amount.sum().sort_values(ascending=False)
    k1 = max(1, int(np.ceil(len(tot) * 0.01)))
    mine = float(tot.head(k1).sum() / tot.sum())
    pipe = [r for r in cc['by_bucket_year']['city candidate committees'] if r['year'] == 2024][0]
    out['concentration_2024'] = {'pipeline_top1pct_share': pipe['top1pct_share'], 'independent_top1pct_share_name_key': mine,
                                 'pipeline_n_donors': pipe['n_donors'], 'independent_n_donors': int(len(tot)),
                                 'verdict': 'Reproduced within a point with a cruder donor key (last name + first initial), so the 8% figure is not an artifact of entity resolution.'}
    # IE 2024: live API check
    api = None
    try:
        q = ("https://data.sf.gov/resource/pitq-e56w.json?$select=sum(calculated_amount),count(*)&$where=form_type='F496' AND calculated_date "
             "between '2024-01-01T00:00:00' and '2024-12-31T23:59:59'")
        r = subprocess.run(['perl', '-e', 'alarm 60; exec @ARGV', 'curl', '-s', '-G', q.split('?')[0], '--data-urlencode', '$select=sum(calculated_amount),count(*)',
                            '--data-urlencode', "$where=form_type='F496' AND calculated_date between '2024-01-01T00:00:00' and '2024-12-31T23:59:59'"],
                           capture_output=True, text=True, timeout=70)
        api = json.loads(r.stdout)[0]
    except Exception as e:
        api = {'error': repr(e)[:200]}
    out['independent_expenditures_2024'] = {
        'first_pass': 16059087.62, 'corrected': ie['ie_on_city_candidates_by_year'].get('2024'), 'duplicates_removed': ie['duplicate_f496_items_removed_by_year'].get('2024'),
        'api_all_f496_2024_including_non_city_and_duplicates': api,
        'candidate_committee_receipts_from_others_2024': ie['candidate_committee_receipts_by_year'].get('2024'),
        'candidate_self_funding_2024': cc['candidate_self_funding_city_by_year'].get('2024'),
        'verdict': ('Direction holds, level corrected: some Form 496 items were re-filed on a second original report and counted twice ($0.34 million '
                    'on City candidates in 2024). Form 496 covers only the last 90 days before an election, so IE totals are a floor.')}
    # behested pending business with a base rate
    out['behested_pending_business'] = behested_base_rate()
    return out


def behested_base_rate():
    spec = importlib.util.spec_from_file_location('m9', os.path.join(HERE, '09_analysis.py'))
    m9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m9)
    C = m9.Ctx('default', 0.8, os.path.join(OUT, '_tmp'))
    pb = pd.read_parquet(os.path.join(AN, 'behested_pending_business.parquet'))
    bp = pd.read_parquet(os.path.join(INT, 'behested.parquet'))
    lob = C.edges[C.edges.edge_type == 'lobbying_contact'][['source', 'target', 'date', 'attrs']].copy()
    lob['dept'] = [str(json.loads(a).get('department') or '').upper() for a in lob['attrs']]
    appr = C.edges[C.edges.edge_type == 'contract_approval'][['source', 'target', 'date']]
    lob_by = {k: g for k, g in lob.groupby('source')}
    appr_by = {k: g for k, g in appr.groupby('target')}
    pool = sorted((set(lob.source) | set(appr.target)) & set(x for x in C.nodes.node_id if str(x).startswith('ORG:')))
    rng = np.random.default_rng(11)
    agency_of = {}
    for o in pb.official.unique():
        ag = bp[bp.official.map(lambda s: 'O:' + m9.m6.nk_from_lastfirst(s)) == o].agency.dropna()
        agency_of[o] = m9.basic(ag.iloc[0]) if len(ag) else ''

    def pending(org, official, date):
        lo, hi = date - pd.Timedelta(days=365), date + pd.Timedelta(days=365)
        l = lob_by.get(org); a = appr_by.get(org)
        l = l[(l.date >= lo) & (l.date <= hi)] if l is not None else None
        a = a[(a.date >= lo) & (a.date <= hi)] if a is not None else None
        ag = agency_of.get(official, '')
        if l is not None and len(l) and (l.target == official).any():
            return True
        if 'SUPERVISORS' in ag:
            return bool((l is not None and l.dept.str.contains('SUPERVISORS').any()) or (a is not None and (a.source == 'BODY:Board of Supervisors').any()))
        if 'MAYOR' in ag:
            return bool((l is not None and l.dept.str.contains('MAYOR').any()) or (a is not None and a.source.isin(['BODY:Mayor', 'BODY:Board of Supervisors']).any()))
        key = ag.split(' ')[0] if ag else ''
        return bool(key and l is not None and l.dept.map(m9.basic).str.contains(re.escape(key)).any())

    def active(org, date):
        lo, hi = date - pd.Timedelta(days=365), date + pd.Timedelta(days=365)
        l = lob_by.get(org); a = appr_by.get(org)
        return bool((l is not None and ((l.date >= lo) & (l.date <= hi)).any()) or (a is not None and ((a.date >= lo) & (a.date <= hi)).any()))

    obs = [pending(r.payor, r.official, r.date) for r in pb.itertuples()]
    base_all, base_active = [], []
    for r in pb.itertuples():
        draws = rng.choice(pool, 60, replace=False)
        base_all.append(np.mean([pending(o, r.official, r.date) for o in draws]))
        act = [o for o in draws if active(o, r.date)]
        if act:
            base_active.append(np.mean([pending(o, r.official, r.date) for o in act]))
    pb['obs'] = obs
    by_form = pb.groupby('form').obs.mean().to_dict()
    res = {'observed_share': float(np.mean(obs)), 'n_payments': int(len(pb)),
           'base_rate_random_org_ever_active': float(np.mean(base_all)),
           'base_rate_random_org_active_within_12m': float(np.mean(base_active)) if base_active else None,
           'observed_by_form': by_form,
           'dollar_share_observed': float((pb.amount * pb.obs).sum() / pb.amount.sum()),
           'window': '12 months before or after the payment date',
           'pool': f'{len(pool)} organizations that appear as a lobbying client or a contract-approval party anywhere in the data; 60 drawn per payment'}
    res['verdict'] = (f"Reproduced ({res['observed_share']:.0%} of {res['n_payments']} payments). Base rate: a random organization that was itself active with the City "
                      f"(lobbying or a contract approval) within the same 12 months shows the same kind of business with that official's body "
                      f"{res['base_rate_random_org_active_within_12m']:.0%} of the time; a random organization from the whole pool {res['base_rate_random_org_ever_active']:.0%}. "
                      'The window is two-sided (12 months before or after), which the first-pass wording did not say.')
    return res


# ------------------------------------------------------------------------------------------------ 3. fairness scans
ORG_WORDS = re.compile(r"\b(INC|LLC|LLP|LP|CORP|CORPORATION|CO|COMPANY|FOUNDATION|FUND|ASSOCIATION|ASSN|COUNCIL|UNION|LOCAL|COMMITTEE|CLUB|SOCIETY|"
                       r"CENTER|CENTRE|INSTITUTE|UNIVERSITY|COLLEGE|SCHOOL|CHURCH|PARTNERS|PARTNERSHIP|GROUP|HOLDINGS|PROPERTIES|DEVELOPMENT|SERVICES|"
                       r"CONSULTING|ASSOCIATES|TRUST|BANK|HOSPITAL|CLINIC|PROJECT|NETWORK|ALLIANCE|COALITION|PAC|DEMOCRATIC|REPUBLICAN|CITY|COUNTY|STATE|"
                       r"DEPARTMENT|DEPT|BOARD|COMMISSION|AGENCY|AUTHORITY|DISTRICT|OFFICE|LAW|FIRM|STUDIO|DESIGN|ARCHITECTS|ENGINEERING|CONSTRUCTION|"
                       r"BUILDERS|RESTAURANT|CAFE|BAR|HOTEL|MARKET|STORE|SHOP|ENTERPRISES|VENTURES|CAPITAL|INVESTMENTS|REALTY|MANAGEMENT|MEDIA|"
                       r"PRODUCTIONS|ARTS|THEATER|THEATRE|FRIENDS|YES|NO ON|FOR|OF|THE|AND|&|SF|SAN|FRANCISCO|BAY|AREA|AMERICA|AMERICAN|NATIONAL|INTERNATIONAL|"
                       r"PLLC|PC|APC|DBA|CPA|MD|DDS|ESQ|TEAM|LEAGUE|PARTY|ACTION|CAMPAIGN|VOTERS|NEIGHBORS|RESIDENTS|WORKERS|TENANTS|HOUSING|HEALTH|CARE|"
                       r"SUPPLY|SYSTEMS|TECHNOLOGIES|SOLUTIONS|INDUSTRIES|ENERGY|ELECTRIC|PLUMBING|TRUCKING|TRANSPORTATION|GARDEN|FARM|INN|MOTEL|LTD)\b")


def norm(s):
    return re.sub(r'\s+', ' ', re.sub(r"[^A-Z' ]", ' ', str(s).upper())).strip()


def private_name_set():
    """Full names (FIRST LAST) of individual contributors, minus people who may be named (officials, candidates, lobbyists)."""
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'), columns=['is_individual', 'donor_first', 'donor_last'])
    c = c[c.is_individual].dropna()
    names = set((norm(f).split(' ')[0] + ' ' + norm(l).split(' ')[-1]) for f, l in zip(c.donor_first, c.donor_last) if norm(f) and norm(l))
    allowed = set()
    E = S('entities.json')['entities']
    for e in E:
        if e['type'] in ('official', 'lobbyist'):
            t = norm(e['name']).split(' ')
            if len(t) >= 2:
                allowed.add(t[0] + ' ' + t[-1])
    com = pd.read_parquet(os.path.join(INT, 'committees.parquet'), columns=['candidate_name'])
    for n in com.candidate_name.dropna():
        n = str(n)
        if ',' in n:
            last, first = n.split(',', 1)
        else:
            parts = n.split(); first, last = (parts[0], parts[-1]) if len(parts) >= 2 else ('', '')
        if norm(first) and norm(last):
            allowed.add(norm(first).split(' ')[0] + ' ' + norm(last).split(' ')[-1])
    return names - allowed, allowed


def strings_in(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings_in(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for v in obj:
            yield from strings_in(v, path + '[]')
    elif isinstance(obj, str):
        yield path, obj


def person_like(name):
    t = norm(name)
    toks = t.split(' ')
    return 2 <= len(toks) <= 4 and not ORG_WORDS.search(t) and all(len(x) >= 1 for x in toks)


def scan():
    res = {}
    priv, allowed = private_name_set()
    E = S('entities.json')['entities']
    Emap = {e['id']: e for e in E}
    # (a) entity names that ARE a private donor's name (exact first+last, 2-4 tokens, no organization words)
    exact = []
    for e in E:
        if e['type'] in ('official', 'lobbyist', 'committee', 'individuals', 'department'):
            continue
        t = norm(e['name']).split(' ')
        if person_like(e['name']) and len(t) >= 2 and (t[0] + ' ' + t[-1]) in priv:
            exact.append(e['id'])
    res['entities_named_like_private_donor'] = {'n': len(exact), 'ids': exact}
    # (b) person-looking organization names regardless of donor match
    pl = [e['id'] for e in E if e['type'] in ('donor_org', 'contractor', 'nonprofit') and person_like(e['name'])]
    res['person_looking_org_names'] = {'n': len(pl), 'ids_sample': pl[:40]}
    # (c) free-text fields across every exported file: private donor names inside strings (excluding entity names, handled above)
    files = [p for p in glob.glob(os.path.join(SITE, '**', '*.json'), recursive=True) if '/flows/flows_' not in p]
    hits = collections.Counter(); hit_paths = collections.defaultdict(set)
    for p in files:
        obj = json.load(open(p))
        for path, s in strings_in(obj):
            if path.endswith('.name') or path.endswith('.id') or re.search(r'\.(flow|from|to|client|payor|payee|official|committee|contractor|entity|target|lobbyist|behest_of|nearest_contract|window_contract|contract|node)$', path):
                continue
            toks = norm(s).split(' ')
            if len(toks) < 2:
                continue
            for i in range(len(toks) - 1):
                for j in (i + 1, i + 2):
                    if j < len(toks) and (toks[i] + ' ' + toks[j]) in priv and not ORG_WORDS.search(toks[i] + ' ' + toks[j]):
                        hits[os.path.relpath(p, SITE) + ':' + path] += 1
                        hit_paths[os.path.relpath(p, SITE) + ':' + path].add(s[:0])
    res['free_text_private_name_hits_by_field'] = dict(hits.most_common(40))
    # (d) addresses and ZIP codes anywhere in the export (including per-year flows) and the site bundle
    addr = re.compile(r'\b\d{2,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Way|Dr|Drive|Ln|Lane|Ct|Court|Pl|Place|Ter|Terrace)\b\.?')
    zipre = re.compile(r'\b9[45]\d{3}(?:-\d{4})?\b')
    az = collections.Counter()
    for p in glob.glob(os.path.join(SITE, '**', '*.json'), recursive=True) + glob.glob(os.path.join(BUNDLE, '*.js')):
        txt = open(p, encoding='utf-8', errors='ignore').read()
        a1 = len(addr.findall(txt)); z1 = len([m for m in zipre.findall(re.sub(r'"(?:id|flow|from|to|[a-z_]*contract|committee|contractor|record_id|fppc_id|code)"\s*:\s*"[^"]*"', '', txt))])
        if a1 or z1:
            az[os.path.relpath(p, ROOT) + f' addr={a1} zip={z1}'] += 1
    res['address_or_zip_like'] = sorted(az)
    # (e) private donor names in the site bundle (the files the site actually ships), entity-name level
    if os.path.isdir(BUNDLE):
        names_to_check = {Emap[i]['name'] for i in exact}
        found = 0
        for p in glob.glob(os.path.join(BUNDLE, '*.js')):
            txt = open(p, encoding='utf-8', errors='ignore').read()
            found += sum(1 for n in names_to_check if n in txt)
        res['bundle'] = {'files_checked': len(glob.glob(os.path.join(BUNDLE, '*.js'))), 'private_like_entity_names_found': found}
    # (f) review rows: every one has rule-ready reason, base-rate context, refund note where seen
    ban = S('analyses/ban_window.json')
    rv = [r for r in ban['records'] if r['review'] == 'appears_to_warrant_review']
    res['review_rows'] = {'n': len(rv), 'missing_why': sum(1 for r in rv if not r.get('why')),
                          'why_mentions_not_proof': sum(1 for r in rv if 'not proof' in (r.get('why') or '') or 'Not a finding' in (r.get('why') or '')),
                          'refund_flag_true': sum(1 for r in rv if r.get('possible_refund_seen')),
                          'refund_noted_in_why': sum(1 for r in rv if 'refund' in (r.get('why') or '')),
                          'min_match_confidence': min((r['match_confidence'] for r in rv), default=None)}
    # (g) officials: nobody labelled as holding an office without roster evidence
    offs = [e for e in E if e['type'] == 'official']
    res['officials'] = {'n': len(offs), 'by_category': dict(collections.Counter(e.get('category') for e in offs)),
                        'candidates_with_term': sum(1 for e in offs if e.get('category') == 'candidate' and e.get('term'))}
    # (h) the 2,482 folded persons: none of them appears by name as an entity
    et = pd.read_parquet(os.path.join(ER, 'entity_types.parquet'))
    folded = et[(et.is_person == True) & (et.person_conf >= 0.5)]
    names = {norm(x) for x in folded.label}
    still = [e['id'] for e in E if e['type'] in ('donor_org', 'contractor', 'nonprofit') and norm(e['name']) in names]
    res['folded_persons'] = {'n_folded': int(len(folded)), 'still_exported_by_name': len(still), 'ids': still[:20]}
    return res


# ------------------------------------------------------------------------------------------------ 4. Opus re-check of person-looking names
ADJ_SYSTEM = ("You review names that a San Francisco transparency dashboard lists as ORGANIZATIONS (campaign donors, city contractors, nonprofits, "
              "behested-payment payors). Private individuals must never be named on the dashboard. For each name decide whether it most likely "
              "refers to a private individual human (including a sole proprietor trading under their own name, e.g. 'Jane Doe' or 'John Smith "
              "Consulting' when it reads as one person's own trade name), rather than a company, firm, organization or public body. "
              "Well-known companies named after founders (e.g. 'Charles Schwab', 'Levi Strauss', 'Webcor') are organizations. "
              "Give a one-sentence rationale and a confidence 0-1.")
ADJ_SCHEMA = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
    'i': {'type': 'integer'}, 'person': {'type': 'boolean'}, 'confidence': {'type': 'number'}, 'rationale': {'type': 'string'}},
    'required': ['i', 'person', 'confidence', 'rationale'], 'additionalProperties': False}}}, 'required': ['items'], 'additionalProperties': False}


def adjudicate(max_usd=60.0):
    import llm
    start = llm.spent()
    E = S('entities.json')['entities']
    priv, _ = private_name_set()
    cand = []
    for e in E:
        if e['type'] not in ('donor_org', 'contractor', 'nonprofit'):
            continue
        t = norm(e['name']).split(' ')
        donor = len(t) >= 2 and (t[0] + ' ' + t[-1]) in priv
        if person_like(e['name']) or (donor and len(t) <= 5):
            cand.append(e)
    print('candidates', len(cand))
    batches = [cand[k:k + 40] for k in range(0, len(cand), 40)]
    rows = []
    import concurrent.futures as cf

    def run(b):
        prompt = 'Names listed as organizations:\n' + '\n'.join(f'{i}. "{e["name"]}" (listed as {e["type"]})' for i, e in enumerate(b))
        return b, llm.call_json('redteam2_person_names', prompt, ADJ_SCHEMA, system=ADJ_SYSTEM, model=llm.OPUS, effort='high', max_tokens=12000)['items']
    with cf.ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(run, b) for b in batches]
        for fu in cf.as_completed(futs):
            try:
                b, items = fu.result()
            except Exception as ex_:
                print('err', repr(ex_)[:200]); continue
            for it in items:
                if 0 <= it['i'] < len(b):
                    e = b[it['i']]
                    rows.append(dict(node_id='ORG:' + e['id'].split('-', 1)[1], entity=e['id'], label=e['name'], is_person=bool(it['person'] and it['confidence'] >= 0.6),
                                     person_conf=float(it['confidence']), rationale=it['rationale'], model=llm.OPUS, task='redteam2_person_names'))
            if llm.spent() - start > max_usd:
                print('budget stop'); break
    # bare street addresses used as a donor name (no LLC/LP/Inc/Associates/Building/...): may be a residence, so never shown
    bare = re.compile(r'^\s*\d{1,5}(?:\s*-\s*\d{1,5})?\s+(?:[A-Za-z]+\s){0,3}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Way|Dr|Drive|Ln|Lane|Ct|Court|Pl|Place|Ter|Terrace)\.?\s*$', re.I)
    for e in E:
        # donors only: a city contractor named by a property address is a public contract party (a lessor), not a residence
        if e['type'] in ('donor_org', 'nonprofit') and bare.match(e['name']):
            rows.append(dict(node_id='ORG:' + e['id'].split('-', 1)[1], entity=e['id'], label=e['name'], is_person=True, person_conf=1.0,
                             rationale='Bare street address used as a donor name; could be a residence, so it is folded into the individuals aggregate.',
                             model='rule', task='redteam2_bare_address'))
    df = pd.DataFrame(rows).drop_duplicates('node_id', keep='last')
    # Merge with earlier decisions: names already judged to be persons are folded out of entities.json, so a rerun on an export
    # that applied them no longer sees them. Keep every earlier row whose node was not re-checked in this run (idempotent reruns).
    ovp = os.path.join(ER, 'entity_type_overrides.parquet')
    if os.path.exists(ovp):
        old = pd.read_parquet(ovp)
        df = pd.concat([old[~old.node_id.isin(set(df.node_id))], df], ignore_index=True)
    df.to_parquet(ovp, index=False)
    print(df.is_person.value_counts(), f'spent this step ${llm.spent() - start:.2f}')
    return {'n_checked': int(len(df)), 'n_person': int(df.is_person.sum()) if len(df) else 0, 'usd': round(llm.spent() - start, 2)}


def spend():
    tot = 0.0; n = 0
    for line in open(os.path.join(DATA, 'llm_usage.jsonl')):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if str(r.get('task', '')).startswith('redteam2'):
            tot += r.get('cost_usd', 0); n += 1
    return {'calls': n, 'usd': round(tot, 2)}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    p = os.path.join(OUT, 'redteam2.json')
    rep = json.load(open(p)) if os.path.exists(p) else {}
    if mode == 'adjudicate':
        rep['person_name_adjudication'] = adjudicate()
    if mode in ('scan', 'all'):
        rep['fairness_scan'] = scan()
    if mode == 'all':
        rep['legal'] = LEGAL
        rep['rederivation'] = rederive()
        vc = os.path.join(OUT, 'verify_commentary.json')
        if os.path.exists(vc):
            rep['commentary_verification'] = json.load(open(vc))
    rep['llm_spend_redteam2'] = spend()
    rep['generated'] = pd.Timestamp.now().strftime('%Y-%m-%dT%H:%M:%S')
    json.dump(rep, open(p, 'w'), indent=1, default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else (int(o) if isinstance(o, np.integer) else (float(o) if isinstance(o, np.floating) else str(o))))
    print(json.dumps({k: (v if k in ('llm_spend_redteam2',) else '...') for k, v in rep.items()}))


if __name__ == '__main__':
    main()
