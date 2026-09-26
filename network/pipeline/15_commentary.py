"""Commentary for the Money network dashboard (red-team pass 2, 2026-09-26).

Writes data/site/commentary/nw-*.json, commentary/story_nw.json and data/site/commentary_facts.json.
Every number in the text is produced by T.n(), which formats a value read from an exported or analysis file and records
where it came from (file#path, or file#function(path)). verify_commentary.py re-reads each source, re-formats the value and
checks that every number in every commentary string is traced. Rule citations and dates come from meta.rules (T.rule()).

Run after 11_export.py and 13_extras.py.
"""
import os, re, json, collections, statistics
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
SITE = os.path.join(DATA, 'site')


def load(rel):
    return json.load(open(os.path.join(DATA, rel)))


# ------------------------------------------------------------------------------------------------ formatting (mirrored in verify_commentary.py)
def money(x):
    a = abs(x)
    if a >= 1e9: return f'${x/1e9:.1f} billion'
    if a >= 1e6: return f'${x/1e6:.1f} million'
    if a >= 1e4: return f'${x/1e3:,.0f}k'
    return f'${x:,.0f}'


FMT = {
    'int': lambda v: f'{int(round(v)):,}',
    'pct0': lambda v: f'{v*100:.0f}%',
    'pct1': lambda v: f'{v*100:.1f}%',
    'pts1': lambda v: f'{abs(v)*100:.1f}',
    'money': money,
    'dollars': lambda v: f'${v:,.0f}',
    'ratio2': lambda v: f'{v:.2f}',
    'year': lambda v: f'{int(v)}',
    'yearof': lambda v: str(v)[:4],
}


class Trace:
    def __init__(self):
        self.items = []
        self.view = None

    def n(self, source, kind):
        """source: 'site/x.json#path' or 'site/x.json#fn(path)'; value is resolved by the same resolver the verifier uses."""
        v = resolve(source)
        s = FMT[kind](v)
        self.items.append(dict(file=self.view, text=s, kind=kind, source=source))
        return s

    def lit(self, text, source, must_contain=None):
        """A literal (a year, a method constant) whose basis is quoted in the source file: `must_contain` (default: text) must
        occur in the JSON text of `source` (a file, or file#path)."""
        mc = must_contain or text
        f = source.split('#', 1)[0]
        blob = json.dumps(resolve(source) if '#' in source else load(f), ensure_ascii=False)
        assert mc in blob, (text, source, mc)
        self.items.append(dict(file=self.view, text=text, kind='literal', source=source, must_contain=mc))
        return text

    def rule(self, rid, phrase):
        """A phrase (citation or date) that must appear verbatim in meta.rules[id].text/cite."""
        r = next(x for x in load('site/meta.json')['rules'] if x['id'] == rid)
        assert phrase in r['text'] or phrase in r['cite'], (rid, phrase)
        self.items.append(dict(file=self.view, text=phrase, kind='rule', source=f'site/meta.json#rules[id={rid}]'))
        return phrase


# ------------------------------------------------------------------------------------------------ resolver (shared with verify_commentary.py)
def _walk(obj, path):
    for part in re.findall(r'[^.\[\]]+|\[[^\]]*\]', path):
        if part.startswith('['):
            inner = part[1:-1]
            if re.fullmatch(r'-?\d+', inner):
                obj = obj[int(inner)]
            else:
                ops = re.split(r'&', inner)
                def ok(x):
                    for op in ops:
                        m = re.match(r'(\w+)(<=|>=|!=|=|<|>|\^)(.*)', op)
                        k, o, val = m.group(1), m.group(2), m.group(3)
                        xv = x.get(k)
                        if o == '^':
                            if not str(xv or '').startswith(val):
                                return False
                            continue
                        try:
                            num = float(val); xn = float(xv) if xv is not None and not isinstance(xv, bool) else None
                        except ValueError:
                            num, xn = None, None
                        if val in ('true', 'false'):
                            if (xv is True) != (val == 'true'): return False
                        elif o == '=':
                            if str(xv) != val: return False
                        elif o == '!=':
                            if str(xv) == val: return False
                        elif xn is None or num is None: return False
                        elif o == '<=' and not xn <= num: return False
                        elif o == '>=' and not xn >= num: return False
                        elif o == '<' and not xn < num: return False
                        elif o == '>' and not xn > num: return False
                    return True
                obj = [x for x in obj if ok(x)]
        elif isinstance(obj, list):
            obj = [x.get(part) if isinstance(x, dict) else None for x in obj]
        else:
            obj = obj[part]
    return obj


FUNCS = {
    'len': lambda v: len(v), 'sum': lambda v: float(sum(x or 0 for x in v)), 'median': lambda v: float(statistics.median(v)),
    'mean': lambda v: float(np.mean([float(x) for x in v])), 'nuniq': lambda v: len(set(v)), 'max': lambda v: float(max(v)),
    'compl': lambda v: 1.0 - float(v), 'minstr': lambda v: min(v), 'maxstr': lambda v: max(v),
}


def resolve(source):
    f, expr = source.split('#', 1)
    obj = load(f)
    m = re.fullmatch(r'(\w+)\((.*)\)', expr)
    if m and m.group(1) in FUNCS:
        return FUNCS[m.group(1)](_walk(obj, m.group(2)))
    m = re.fullmatch(r'ratio\((.*)\|(.*)\)', expr)
    if m:
        return resolve(f + '#' + m.group(1)) / resolve(f + '#' + m.group(2))
    m = re.fullmatch(r'diff\((.*)\|(.*)\)', expr)
    if m:
        return resolve(f + '#' + m.group(1)) - resolve(f + '#' + m.group(2))
    return _walk(obj, expr)


# ------------------------------------------------------------------------------------------------ commentary
def main():
    T = Trace()
    out = {}
    TF = 'Too few records match to summarize; widen the years or clear a filter.'
    AU = 'SF City Monitor network analysis (red-team pass 2, 2026-09-26; every number traced by verify_commentary.py)'
    BAN = 'site/analyses/ban_window.json'
    RV = 'records[review=appears_to_warrant_review]'
    BR = 'analysis/contractor_base_rates.json'
    M2 = BR + '#redteam2.excluding_public_entities'
    RT = 'redteam/redteam2.json'
    CONC = 'analysis/concentration.json'
    BEH = 'analysis/behested.json'
    META = 'site/meta.json'
    LOB = 'site/analyses/lobbying.json'
    LC = 'analysis/lobbyist_contributions.json'
    NPL = 'analysis/nonprofit_loop.json'
    n, lit, rule = T.n, T.lit, T.rule

    def com(view, headline, paragraphs, templates=None, caveats=None, sources=None, annotations=None):
        out[view] = {'sample': False, 'view': view, 'author': AU, 'headline': headline, 'paragraphs': paragraphs,
                     'annotations': annotations or [], 'templates': templates or [], 'caveats': caveats or [], 'sources': sources or []}

    obs, exp_ = M2 + '.observed', M2 + '.expected_office_matched_calendar_weighted'
    y1925 = lambda: f"from {lit('2019', BAN + '#base_rates.matched_note', '2019-2025')} to {lit('2025', BAN + '#base_rates.matched_note', '2019-2025')}"

    # ---------------------------------------------------------------- nw-overview
    T.view = 'nw-overview'
    com('nw-overview',
        (f"Board members and officers of city contractors give to the officials who approve their contracts inside the §1.126 ban window slightly less often than "
         f"chance would predict ({n(obs, 'pct0')} of their contributions against {n(exp_, 'pct0')} expected); "
         f"{n(BAN + '#len(' + RV + ')', 'int')} small contributions still appear to warrant review, a pattern worth checking, not proof."),
        [(f"This dashboard joins four public disclosure systems: campaign contributions (Form 460), behested payments (Form 803 and SFEC-3610(b)), lobbyist reports, "
          f"and city contracts and payments. It holds {n(META + '#counts.flows', 'int')} flows among {n(META + '#counts.entities', 'int')} named or aggregate "
          f"entities since {n(META + '#years.min', 'year')}. Organizations were resolved across the systems by rule and with Claude review; private individuals "
          f"({n(META + '#counts.individuals_aggregated', 'int')} of them) appear only inside aggregate nodes, never by name."),
         (f"The central question is whether contractors' principals time their giving around the approvals they win. San Francisco bars a contractor and its "
          f"affiliates from giving to the officials who approve its contract from the proposal until {rule('ban', '12 months')} after approval (§1.126, in this form "
          f"since {rule('ban', 'Jan. 1, 2019')}; six months before that). Measured against the approvals that list the donor and whose approving office covered the "
          f"recipient, with days weighted by the election calendar, {n(obs, 'pct1')} of {n(M2 + '.n_records', 'int')} contributions {y1925()} fell inside a "
          f"window, against {n(exp_, 'pct1')} expected by chance. The shortfall is small ({n(BR + '#redteam2.bootstrap_95ci.difference[1]', 'pts1')} to "
          f"{n(BR + '#redteam2.bootstrap_95ci.difference[0]', 'pts1')} points, {lit('95%', BR, 'bootstrap_95ci')} interval) and fits a rule that is mostly "
          f"followed; it does not show that the ban changes behavior."),
         (f"The {n(BAN + '#len(' + RV + ')', 'int')} contributions that appear to warrant review are small: median {n(BAN + '#median(' + RV + '.amount)', 'dollars')}, "
          f"and {n(BAN + '#ratio(len(records[review=appears_to_warrant_review&amount<=500])|len(' + RV + '))', 'pct0')} are {rule('limits', '$500')} or less, within "
          f"the per-election limit. Most ({n(BAN + '#ratio(len(records[review=appears_to_warrant_review&contractor^np-])|len(' + RV + '))', 'pct0')}) come from "
          f"board members or officers of nonprofits that hold city contracts, and "
          f"{n(BAN + '#len(records[review=appears_to_warrant_review&possible_refund_seen=true])', 'int')} show a later negative entry from the same donor to the same "
          f"committee that may be a refund. Each row cites the rule and the reason and is not a finding of a violation; the Ethics Commission may already have reviewed them.")],
        templates=[{'id': 'ov', 'template': ('For your filters: {flows_fmt} disclosed flows totalling {total} among {entities_fmt} entities, {years}. Contract and '
                                             'city-payment dollars are orders of magnitude larger than political money; choose a flow type to compare like with like.'),
                    'requires': {'flows_min': 5}, 'fallback': TF}],
        caveats=[{'severity': 'high', 'text': ('Donors are linked to contractors by name, employer and location with Claude review. Accepted matches were correct in every '
                                               f"hand-checked case, but about {n('validation/validation_results.json#compl(person_recall_estimate_rare_names)', 'pct0')} of true "
                                               'matches among uncommon names are missed, so contractor-affiliated giving is undercounted.')},
                 {'severity': 'high', 'text': (f"Behested-payment coverage is uneven: Form 803 filings after {lit('March 2018', BEH + '#coverage_note')} exist only as PDFs and "
                                               f"are not included, and San Francisco's own reporting form was repealed on {rule('behested', 'Jan. 24, 2022')}, when the "
                                               'solicitation ban replaced it.')},
                 {'severity': 'medium', 'text': ('Office holding is taken from the Board of Supervisors roster (sfbos.org) and, for the citywide offices (Mayor, District '
                                                 'Attorney, City Attorney, Sheriff, Treasurer, Assessor-Recorder, Public Defender), from a verified office-history table '
                                                 'with an official source for every term, including appointed, interim and acting terms; partial years count as held. '
                                                 'Candidates who never held City office are labelled as candidates.')},
                 {'severity': 'low', 'text': (f"All dollars are nominal. Individual gifts to a candidate are capped at {rule('limits', '$500')} per election, so dollar totals "
                                              'understate how many people give.')}],
        sources=['network/data/site/meta.json', 'network/data/site/analyses/ban_window.json', 'network/data/analysis/contractor_base_rates.json (redteam2)', 'network/data/redteam/redteam2.json'],
        annotations=[{'chart': 'nw_dollars', 'x': lit('2019', META + '#rules[id=ban]', 'Jan. 1, 2019'), 'text': f"Contractor ban widened to {rule('ban', '12 months')} after approval (Ord. 129-18)"}])

    # ---------------------------------------------------------------- nw-graph
    T.view = 'nw-graph'
    com('nw-graph',
        'The strongest flows run in separate channels: departments pay contractors and nonprofits, PACs and unions fund committees, and clients pay lobbyists to reach the same departments.',
        ['The graph keeps only the strongest flows so it stays readable, and folds each committee into its official or candidate. City payments and contract values are orders '
         'of magnitude larger than contributions, so the default picture is dominated by departments; filter by flow type to see political money on its own scale.',
         (f"Individuals are shown only as aggregate nodes, for example the disclosed principals of one contractor or the people who name one employer; there are "
          f"{n('site/entities.json#len(entities[type=individuals])', 'int')} such nodes. A thick line between an aggregate node and a committee is many small, "
          "lawful contributions, not one large gift.")],
        templates=[{'id': 'graph', 'template': 'Showing {nodes_fmt} entities and {edges_fmt} flows ({total}); {hidden_fmt} weaker flows are hidden by the current pruning. Search or click a node to expand its neighborhood.',
                    'requires': {'edges_min': 1}, 'fallback': 'No flows match; widen the years, lower the minimum amount or add a flow type.'}],
        caveats=[{'severity': 'medium', 'text': 'Pruning changes the picture: an organization absent from the default graph may still have many small flows. Use the table twin or the entity directory to check.'},
                 {'severity': 'low', 'text': f"Lobbying contacts have no dollar value; for pruning only they are weighted as {lit('$1,000', 'site/graph.json#note')} each."}],
        sources=['network/data/site/flows.json', 'network/data/site/entities.json', 'network/data/site/graph.json'])

    # ---------------------------------------------------------------- nw-ban
    T.view = 'nw-ban'
    com('nw-ban',
        (f"Of {n(BAN + '#base_rates.contributions_by_contractor_affiliated', 'int')} contributions by contractors' disclosed principals since "
         f"{n(META + '#years.min', 'year')}, {n(BAN + '#base_rates.inside_any_window', 'int')} fall inside a post-approval window and "
         f"{n(BAN + '#len(' + RV + ')', 'int')} went to an official who held or sought an approving office; those appear to warrant review under §1.126, "
         "a pattern worth checking, not proof, and overall the timing is close to chance."),
        [(f"The rule: a City contractor and its affiliates (board members, top officers, owners of more than {rule('ban', '10%')}, listed subcontractors) may not give "
          f"to an official who approves its contract, a candidate for that office, or their committees, from the proposal until {rule('ban', '12 months')} after "
          f"approval ({rule('ban', 'Ord. 129-18')}, operative {rule('ban', 'Jan. 1, 2019')}). Before that the window ended six months after approval and covered "
          f"contracts of {rule('ban', '$50,000')} or more. Each contribution is judged against its own contract's window and the rule in force at approval."),
         (f"The \"expected by chance\" bar is matched like with like: it counts only the approvals that list the donor and whose approving office covered the "
          f"recipient, with days weighted by the election calendar. On that basis {n(exp_, 'pct1')} of contributions would land in a window by chance, and "
          f"{n(obs, 'pct1')} did. A simpler benchmark that pools every window a contractor has, including approvals by offices that do not cover the recipient, "
          f"reads much higher and overstates chance, so it is not used. A placebo that shifts each "
          f"window by two years gave a ratio of {n(BR + '#timing_placebo.ratio_W0_to_baseline', 'ratio2')} for approvals from "
          f"{lit('2019', BR + '#timing_placebo.description', '2019-01-01 to 2023-09-25')} to {lit('2023', BR + '#timing_placebo.description', '2019-01-01 to 2023-09-25')} "
          f"but {n(BR + '#redteam2.placebo_4y.ratio_W0_to_2y_mean', 'ratio2')} for approvals from {lit('2019', BR + '#redteam2.placebo_4y.approvals', '2019-01-01 to 2021-09-25')} "
          f"to {lit('2021', BR + '#redteam2.placebo_4y.approvals', '2019-01-01 to 2021-09-25')} alone, because giving swings with the election calendar; it is too "
          "unstable to carry a finding."),
         (f"The {n(BAN + '#len(' + RV + ')', 'int')} flagged rows total {n(BAN + '#sum(' + RV + '.amount)', 'money')}, with a median of "
          f"{n(BAN + '#median(' + RV + '.amount)', 'dollars')} and a maximum of {n(BAN + '#max(' + RV + '.amount)', 'dollars')}; they involve "
          f"{n(BAN + '#nuniq(' + RV + '.contractor)', 'int')} contractors and {n(BAN + '#nuniq(' + RV + '.committee)', 'int')} committees. A flag needs a "
          f"corroborated name match (confidence {lit('0.85', META + '#fairness.review')} or higher); {n(RT + '#rederivation.flagged.dropped_bare_name_matches_0_80', 'int')} "
          "otherwise similar contributions matched on name alone are left unflagged. Contracts with public bodies such as UC or SFUSD are listed but not flagged, "
          "because whether §1.126 reaches their board members is unclear.")],
        templates=[{'id': 'ban', 'template': ('{records_fmt} contractor-affiliated contribution records for {contracts_fmt} contracts, {years}: {inside_fmt} fall inside a '
                                              'post-approval window ({inside_share}; over all years, matched like with like, {observed_matched} fell inside a window against '
                                              '{expected_share} expected by chance); {covered_fmt} went to a covered official and appear to warrant review under §1.126, a pattern worth checking, not proof.'),
                    'requires': {'records_min': 5}, 'fallback': TF}],
        caveats=[{'severity': 'high', 'text': (f"The \"expected by chance\" bar is the matched benchmark ({n(exp_, 'pct1')}) for all years; it rests on the approval-date "
                                               "proxy and the election-calendar weighting, and it does not change with your filters.")},
                 {'severity': 'high', 'text': ('The proposal date that starts the ban is not in the data, so contributions made while a proposal was pending but before approval '
                                               f"are not judged ({n('analysis/contractor_ban.json#pre_approval_180d.n_contributions', 'int')} fall in the half-year before an "
                                               'approval). The flags are a floor.')},
                 {'severity': 'high', 'text': ('The approval date is the date the elected officer signed Form SFEC-126(f)4, due within five business days of approval; a '
                                               'contribution a few days either side of a window edge may be misclassified.')},
                 {'severity': 'medium', 'text': ('Whether a committee was covered depends on who held or sought the approving office that day: the Board of Supervisors roster, '
                                                 'the verified office-history table for citywide offices (exact term dates, including interim and acting terms), '
                                                 f"Form 700 ({lit('2013-2021', 'site/entities.json#entities[category=elected_or_appointed].term_note')}) and lobbyist contact "
                                                 "reports for other bodies, and the dates the candidate's own committee raised money.")},
                 {'severity': 'medium', 'text': ('Ord. 129-18 has no transition clause. Applying the new window to contributions made after it took effect but tied to earlier '
                                                 f"approvals would add {n(BR + '#redteam2.transition_sensitivity.n_contributions', 'int')} contributions "
                                                 f"({n(BR + '#redteam2.transition_sensitivity.amount', 'dollars')}).")},
                 {'severity': 'low', 'text': "A refund is inferred from a later negative entry for the same donor and committee; the Ethics Commission's own records are the authority."}],
        sources=['network/data/site/analyses/ban_window.json', 'network/data/analysis/contractor_base_rates.json (redteam2)', 'network/data/analysis/contractor_ban.json', 'network/data/redteam/redteam2.json'])

    # ---------------------------------------------------------------- nw-behested
    T.view = 'nw-behested'
    EL = BEH + '#officials[label=Edwin Lee]'
    com('nw-behested',
        (f"{n(BEH + '#total_amount', 'money')} in behested payments appear in machine-readable filings, "
         f"{n(BEH + '#ratio(by_form[form^FPPC].sum[0]|total_amount)', 'pct0')} of it on Form 803 reports filed before {lit('March 2018', BEH + '#coverage_note')}; since "
         f"{rule('behested', 'Jan. 24, 2022')}, City officials may not solicit such payments from interested parties at all."),
        [(f"Two regimes apply. State law requires elected officers to report on Form 803 when one source gives {rule('behested', '$5,000')} or more in a calendar year at "
          f"their behest. San Francisco required its own report (SFEC-3610(b)) for payments of {rule('behested', '$1,000')} or more from interested parties: from "
          f"commissioners starting {rule('behested', 'Jan. 1, 2018')}, from all City elective officers starting {rule('behested', 'Jan. 1, 2019')}, and from department "
          f"heads under Executive Directive 20-02. {rule('behested', 'Ord. 232-21')} replaced that reporting with an outright ban on soliciting interested parties, "
          "which is why the local filings stop."),
         (f"Most of the dollars trace to one official and period: Mayor Edwin Lee's Form 803 filings list {n(EL + '.total[0]', 'money')} across "
          f"{n(EL + '.n[0]', 'int')} payments from {n(EL + '.first[0]', 'yearof')} to {n(EL + '.last[0]', 'yearof')}. For "
          f"{n(RT + '#rederivation.behested_pending_business.observed_share', 'pct0')} of all payments, the payor also lobbied the official or their body, or had a "
          f"contract approved by that body, within {lit('12 months before or after', RT + '#rederivation.behested_pending_business.window')} the payment. For context, "
          f"{n(RT + '#rederivation.behested_pending_business.base_rate_random_org_ever_active', 'pct0')} of organizations drawn at random from the lobbying and contract "
          f"records show the same kind of business in the same window, and {n(RT + '#rederivation.behested_pending_business.base_rate_random_org_active_within_12m', 'pct0')} "
          "of those that were active with the City at all. Payors are more connected than a random organization, not more than an active one."),
         (f"The Board of Supervisors has granted {n(BEH + '#waivers.n', 'int')} waivers of the solicitation ban (§3.620(f)), each prospective and limited to six months. "
          "Waived solicitations are lawful, and before the ban took effect such solicitations were allowed but had to be reported.")],
        templates=[{'id': 'beh', 'template': ('{payments_fmt} behested payments totalling {total}, {years}, at the behest of {officials_fmt} officials; {interested_share} of the '
                                              'dollars came from payors flagged as interested parties, a check against public lobbying and contract data, not a finding.'),
                    'requires': {'payments_min': 3}, 'fallback': TF}],
        caveats=[{'severity': 'high', 'text': (f"Coverage is incomplete: Form 803 reports after {lit('March 2018', BEH + '#coverage_note')} are PDF-only and not included, and local "
                                               f"reporting ended on {rule('behested', 'Jan. 24, 2022')}. The near absence of recent rows reflects the law and the data, not a drop "
                                               'in behested giving.')},
                 {'severity': 'medium', 'text': ('SFEC-3610(b) reports were required only for interested-party payors, so those rows are interested by construction; the flag '
                                                 'matters mostly for the Form 803 rows.')},
                 {'severity': 'medium', 'text': ('The filed-on-time column compares the filing date with the payment date. Form 803 rows have no payment date, so that column is '
                                                 'blank for them; do not read those rows as late.')},
                 {'severity': 'low', 'text': (f"{n(BEH + '#ambiguous_rows.n', 'int')} rows for the Summer Together program list recipient agencies in the payor field and are "
                                              'excluded as ambiguous.')}],
        sources=['network/data/site/analyses/behested.json', 'network/data/analysis/behested.json', 'network/data/redteam/redteam2.json (behested_pending_business)'],
        annotations=[{'chart': 'nw_behested', 'x': lit('2019', META + '#rules[id=behested]', 'Jan. 1, 2019'), 'text': 'Local reporting extended to all City elective officers (Ord. 129-18)',
                      'placement': 'top'},   # the two callouts sit three bars apart: one above its bar, the other to the right, so they never overlap
                     {'chart': 'nw_behested', 'x': lit('2022', META + '#rules[id=behested]', 'Jan. 24, 2022'), 'text': 'Solicitation ban replaces local reporting (Ord. 232-21)',
                      'placement': 'right'}])

    # ---------------------------------------------------------------- nw-lobby
    T.view = 'nw-lobby'
    com('nw-lobby',
        (f"Lobbyists reported {n(LOB + '#sum(rows.contacts)', 'int')} contacts with City officials and staff from {n(LOB + '#minstr(rows.month)', 'yearof')} to "
         f"{n(LOB + '#maxstr(rows.month)', 'yearof')}; {n(LOB + '#ratio(sum(rows[target^dept-].contacts)|sum(rows.contacts))', 'pct0')} were with staff below the "
         f"executive level, shown by department, and City Planning drew the most ({n(LOB + '#sum(rows[target=dept-CPC].contacts)', 'int')})."),
        [('Each registered lobbyist reports contacts monthly, with the client, the official or department, the subject and the outcome sought. Staff below the executive '
          'level are never named here; their contacts, including contacts with aides who later ran for office, are shown at the department level.'),
         (f"Lobbyists may not give to City candidates of an agency they are registered to lobby (§2.115(d), Proposition T, operative {rule('lobby', 'Jan. 1, 2018')}). "
          f"Approximating registration by a reported contact in the prior {rule('lobby', '90 days')}, matched lobbyists made "
          f"{n(LC + '#by_rule_period.before_2018.n_positive', 'int')} such contributions before the ban, when they were allowed. After it there are "
          f"{n(LC + '#by_rule_period.from_2018.n_positive_contributions', 'int')}, totalling {n(LC + '#by_rule_period.from_2018.positive_amount', 'dollars')}, and each "
          "was followed by a refund from the same committee; no later ones appear. That is what compliance with a new rule looks like, though the proxy is narrower than registration.")],
        templates=[{'id': 'lob', 'template': ('{contacts_fmt} reported contacts by {lobbyists_fmt} lobbyists for {clients_fmt} clients, {years}; most-contacted target: {top_target} '
                                              '({top_target_fmt} contacts); payments to lobbyists in view: {payments_total}.'),
                    'requires': {'contacts_min': 5}, 'fallback': TF}],
        caveats=[{'severity': 'medium', 'text': 'Outcomes are linked only for contracts and Planning projects; Board of Supervisors legislative outcomes are not open data.'},
                 {'severity': 'medium', 'text': 'Lobbyists, clients and officials are matched by name; a client listed under several names may be split.'},
                 {'severity': 'low', 'text': 'A contact is one reported interaction; reports differ in how finely they itemize meetings, calls and emails.'}],
        sources=['network/data/site/analyses/lobbying.json', 'network/data/analysis/lobbyist_contributions.json (by_rule_period)'])

    # ---------------------------------------------------------------- nw-concentration
    T.view = 'nw-concentration'
    y24 = lambda b: f"{CONC}#by_bucket_year.{b}[year=2024].top1pct_share[0]"
    Y24 = lambda: lit('2024', CONC + '#independent_expenditures.ie_on_city_candidates_by_year', '2024')
    REF = 'analysis/reforms.json#compl(contractor_affiliated_share_by_period.'
    com('nw-concentration',
        (f"The {rule('limits', '$500')} limit keeps candidate money spread out: in {Y24()} the top {lit('1%', CONC, 'top1pct_share')} of donors gave {n(y24('city candidate committees'), 'pct0')} of what "
         f"candidate committees raised from others, against {n(y24('ballot measure committees'), 'pct0')} for ballot-measure committees and "
         f"{n(y24('general-purpose / independent committees'), 'pct0')} for general-purpose committees."),
        [(f"Big money reaches City races around the limit rather than through it. In {Y24()}, independent expenditures on City candidates reported on Form 496 came to "
          f"at least {n(CONC + '#independent_expenditures.ie_on_city_candidates_by_year.2024', 'money')}, compared with "
          f"{n(CONC + '#independent_expenditures.candidate_committee_receipts_by_year.2024', 'money')} that others gave candidate committees directly and "
          f"{n(CONC + '#candidate_self_funding_city_by_year.2024', 'money')} that candidates gave or lent their own campaigns."),
         (f"Contractor-affiliated sources (contracting entities, their listed principals and their employees) supplied {n(REF + '2015-2018.other)', 'pct0')} of City "
          f"candidate-committee money in {lit('2015-2018', 'analysis/reforms.json#contractor_affiliated_share_by_period')} and "
          f"{n(REF + '2021-2025.other)', 'pct0')} in {lit('2021-2025', 'analysis/reforms.json#contractor_affiliated_share_by_period')}, a small and stable share.")],
        templates=[{'id': 'conc', 'template': '{committees_fmt} committee-cycles, {years}: individuals gave {ind_share} of dollars, PACs and organizations {org_share}, contractor-affiliated individuals {contr_share}.',
                    'requires': {'committees_min': 2}, 'fallback': TF}],
        caveats=[{'severity': 'high', 'text': ('Form 496 covers independent spending in the final weeks before an election; earlier spending appears only on other forms and is '
                                               'not counted, so the independent-expenditure totals are a floor. Items re-filed on a second report were removed '
                                               f"({n(CONC + '#independent_expenditures.duplicate_f496_items_removed_by_year.2024', 'money')} in {Y24()}).")},
                 {'severity': 'medium', 'text': 'This view keeps candidate self-funding inside "individuals"; the shares in the headline exclude it.'},
                 {'severity': 'low', 'text': 'Donors are grouped by resolved identity; a person listed under two spellings counts twice, which slightly lowers measured concentration.'}],
        sources=['network/data/analysis/concentration.json', 'network/data/analysis/reforms.json', 'network/data/site/analyses/concentration.json'])

    # ---------------------------------------------------------------- nw-loop
    T.view = 'nw-loop'
    com('nw-loop',
        (f"{n('site/analyses/loop.json#len(rows)', 'int')} city-funded nonprofits also appear as behested payors or payees, or as lobbying clients; "
         "appearing here is not improper."),
        [(f"Of {n(NPL + '#n_nonprofits_funded_100k', 'int')} nonprofits paid at least {lit('$100k', NPL + '#description')} since "
          f"{lit('FY2016', NPL + '#description')}, {n(NPL + '#n_with_principal_giving', 'int')} have disclosed principals who gave "
          f"{n(NPL + '#principal_giving_total', 'money')} to Mayor or Board of Supervisors committees, and those organizations received "
          f"{n(NPL + '#share_of_funding_to_nonprofits_with_principal_giving', 'pct0')} of the funding. That share mostly reflects size: large nonprofits file more "
          "contract notices, and each notice lists their board, so their board members are more likely to be matched."),
         ('Nonprofits may lawfully lobby, receive behested payments and have board members who give to candidates as private citizens. The loop is worth seeing in one '
          'place because the same City offices fund some of these organizations, are lobbied by them, and requested behested payments to or from them; it is not '
          'evidence that any funding decision was influenced.')],
        templates=[{'id': 'loop', 'template': '{orgs_fmt} nonprofits in the loop, {years}: {city_total} in latest-year city payments, {beh_total} in behested payments received, {lob_total} paid to lobbyists.',
                    'requires': {'orgs_min': 1}, 'fallback': TF}],
        caveats=[{'severity': 'medium', 'text': 'City payments are for the latest complete fiscal year in the vendor data; behested and lobbying amounts cover all years.'},
                 {'severity': 'medium', 'text': 'Nonprofit names are matched to the nonprofits module by the entity resolver; unmatched organizations show no link.'}],
        sources=['network/data/site/analyses/loop.json', 'network/data/analysis/nonprofit_loop.json'])

    # ---------------------------------------------------------------- nw-entities
    T.view = 'nw-entities'
    com('nw-entities',
        (f"{n('site/entities.json#len(entities)', 'int')} entities: organizations, officials and candidates in their public roles, committees, departments and "
         f"registered lobbyists, plus {n('site/entities.json#len(entities[type=individuals])', 'int')} aggregate nodes that stand for private individuals."),
        [(f"Officials are labelled by evidence: {n('site/entities.json#len(entities[category=elected_or_appointed])', 'int')} with a roster entry, verified office record or "
          f"filing showing they held City elective office, {n('site/entities.json#len(entities[category=candidate])', 'int')} candidates with no such evidence, and appointed officials such as "
          "commissioners and department heads. Names that read as a private person's, and bare street addresses used as donor names, are folded into the individuals "
          "aggregate and never shown.")],
        caveats=[{'severity': 'low', 'text': 'An organization listed under several names may appear more than once where the resolver could not confirm a match.'}],
        sources=['network/data/site/entities.json', 'network/data/er/entity_type_overrides.parquet'])

    # ---------------------------------------------------------------- story
    T.view = 'story_nw'
    story = {'title': 'Money network', 'steps': [
        {'view': 'nw-overview', 'title': 'Four disclosure systems, one map',
         'text': 'Contributions, behested payments, lobbying and contracts, joined through the organizations that appear in more than one. Private individuals appear only in aggregate; timing is never proof.'},
        {'view': 'nw-graph', 'title': 'The shape of the network', 'filters': {'amt': 10000},
         'text': 'Separate channels: departments to contractors, PACs and unions to committees, clients to lobbyists. Thick lines between aggregate nodes and committees are many small gifts.'},
        {'view': 'nw-ban', 'title': 'The ban window, with a fair base rate', 'filters': {},
         'text': (f"{n(obs, 'pct0')} of principals' contributions land in a window against {n(exp_, 'pct0')} expected by chance; "
                  f"{n(BAN + '#len(' + RV + ')', 'int')} small ones appear to warrant review, each with the rule and the reason.")},
        {'view': 'nw-behested', 'title': 'Behested payments', 'filters': {},
         'text': (f"{n(BEH + '#total_amount', 'money')} in machine-readable filings, most of it from Form 803 reports. Local reporting ended when the solicitation ban took "
                  f"effect on {rule('behested', 'Jan. 24, 2022')}.")},
        {'view': 'nw-lobby', 'title': 'Who lobbies whom', 'filters': {},
         'text': f"Most contacts are with department staff, led by City Planning. Lobbyists' gifts to candidates they lobby stop once the ban took effect on {rule('lobby', 'Jan. 1, 2018')}."},
        {'view': 'nw-concentration', 'title': 'Concentration', 'filters': {},
         'text': (f"Candidate money is spread out under the {rule('limits', '$500')} limit; in {Y24()} independent spending (at least "
                  f"{n(CONC + '#independent_expenditures.ie_on_city_candidates_by_year.2024', 'money')}) outran direct gifts from others.")},
        {'view': 'nw-loop', 'title': 'The nonprofit loop', 'filters': {},
         'text': f"{n('site/analyses/loop.json#len(rows)', 'int')} city-funded nonprofits also receive behested payments or hire lobbyists. Lawful, disclosed, and worth seeing in one place."}]}

    # ---------------------------------------------------------------- write
    for v, c in out.items():
        json.dump(c, open(os.path.join(SITE, 'commentary', v + '.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(story, open(os.path.join(SITE, 'commentary', 'story_nw.json'), 'w'), ensure_ascii=False, indent=1)
    facts = [dict({'id': f'n{i:03d}'}, **t) for i, t in enumerate(T.items)]
    json.dump({'sample': False, 'as_of': load('site/meta.json')['as_of'], 'note': 'Every number in network commentary, with its source; checked by pipeline/verify_commentary.py.',
               'facts': facts}, open(os.path.join(SITE, 'commentary_facts.json'), 'w'), ensure_ascii=False, indent=1)
    print('commentary views', len(out), 'traced numbers', len(facts))
    stats = os.path.join(SITE, '_export_stats.json')   # exporter scratch file; not part of the contract
    if os.path.exists(stats):
        os.remove(stats)


if __name__ == '__main__':
    main()
