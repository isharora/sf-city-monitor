"""Text and chart templates for the Money network insights page, shared by build_insights.py and verify_insights.py.

Every number shown to readers is a placeholder {key|fmt} filled from a computed value (V), an @CH:key chart array or an
@V:key scalar, so verify_insights.py can recompute each one independently from the source tables. Template text itself may
contain only years, dates, legal citations and statutory thresholds (the $500 limit, $5,000, 90 days...), which the build and
verify scripts check against ALLOWED_DIGIT_TOKENS.
Fairness (RULES.md, network module): organizations, officials in public roles and registered lobbyists may be named;
private individuals appear only in aggregate; timing links are patterns worth checking, not proof; "appears to warrant
review" always sits next to the exact rule.
"""
import re

AS_OF = '2026-09-26'
INTRO = ('Sixteen findings about how money moves around San Francisco government: campaign donations, independent spending, '
         'ballot-measure money, lobbying, behested payments and the contribution bans. We screened about thirty-five candidates against '
         'the Ethics Commission\'s filings, the lobbyist disclosures, contract-approval forms and the city\'s payment records; each '
         'published finding held up under at least three robustness checks (other definitions, other years, other matching '
         'thresholds, base rates), and a separate script recomputes every number from the source tables. Timing links are patterns '
         'worth checking, never proof of improper influence; private donors appear only in aggregate. Dollars are nominal unless noted, '
         '2026 figures run through the September 2026 download, and public financing paid to candidates is not in these data.')

MINUS = '−'
MONTHS = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.']
ORD = {1: 'most', 2: 'second most', 3: 'third most', 4: 'fourth most', 5: 'fifth most'}


def _date(v):
    y, m, d = str(v)[:10].split('-')
    return f'{MONTHS[int(m) - 1]} {int(d)}, {y}'


FMT = {
    'int': lambda v: f'{round(round(v, 6)):,}',
    'yr': lambda v: f'{int(v)}',
    'pct': lambda v: f'{v * 100:.0f}%',
    'pct1': lambda v: f'{v * 100:.1f}%',
    'pts1': lambda v: f'{abs(v) * 100:.1f}',
    'usd': lambda v: f'${round(v):,}',
    'mil1': lambda v: f'${v / 1e6:,.1f} million',
    'mil2': lambda v: f'${v / 1e6:,.2f} million',
    'mM': lambda v: f'${v / 1e6:,.0f}M',
    'mM1': lambda v: f'${v / 1e6:,.1f}M',
    'x1': lambda v: f'{v:.1f}',
    'x2': lambda v: f'{v:.2f}',
    'f2': lambda v: f'{v:.2f}',
    'ord': lambda v: ORD[int(v)],
    'date': _date,
    'str': lambda v: str(v),
    'tc': lambda v: str(v).title().replace('Teamster ', 'Teamsters '),
}
PH = re.compile(r'\{(\w+)\|(\w+)\}')


def render_str(s, V):
    def rep(m):
        k, f = m.group(1), m.group(2)
        if k not in V:
            raise KeyError(f'missing value {k}')
        return FMT[f](V[k])
    return PH.sub(rep, s)


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return v
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return v


def render(obj, V, CH):
    """Recursively render a template. Strings get placeholders filled; '@CH:key' pulls a chart array; '@V:key' a scalar."""
    if isinstance(obj, str):
        if obj.startswith('@CH:'):
            return [_num(v) for v in CH[obj[4:]]]
        if obj.startswith('@V:'):
            return _num(V[obj[3:]])
        return render_str(obj, V)
    if isinstance(obj, list):
        return [render(o, V, CH) for o in obj]
    if isinstance(obj, dict):
        return {k: render(v, V, CH) for k, v in obj.items()}
    return obj


# Tokens allowed to contain digits in template text (outside placeholders): years, dates, citations, statutory thresholds
ALLOWED_DIGIT_TOKENS = [
    r'(Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)\.? \d{1,2}, (19|20)\d{2}',
    r'§\s?[\d.]+(\([a-z0-9]+\))*(-\([a-z0-9]+\))?', r'Ord\. \d+-\d+', r'SFEC-126\(f\)4', r'SFEC-3610\(b\)', r'3610\(b\)', r'Form 803',
    r'Form 496', r'Form 700', r'24-hour', r'SFEC-3600', r'Form 114\.5', r'Gov\. Code §\d+', r'Proposition [A-Z]', r'\$500\b', r'\$5,000\b', r'\$1,000\b', r'\$100,000\b',
    r'\$1 million', r'\b90 days\b', r'\b180 days\b', r'\b12 months\b', r'\bsix months\b', r'\b30 days\b', r'95%', r'\b941\d*', r'FY20\d\d',
    r'\b(19|20)\d{2}\b', r'\b[a-z0-9]{4}-[a-z0-9]{4}\b', r'Local \d+', r'Joint Council \d+', r'Section \d+',
    # definitional constants chosen by the analyst (not results): group sizes, thresholds, windows, form names
    r'[Tt]op 1%', r'\b([Tt]op|the) (50|100|200)\b', r'\b100 (most active|clients)\b', r'\$10,000\b', r'\$100\b', r'\$250\b', r'40 largest',
    r'12-month', r'180-day', r'60 random', r'pass 2', r'redteam2', r'Form 460',
]

SRC = {
    'contrib': 'network/data/interim/contributions.parquet (SF Ethics campaign transactions, DataSF pitq-e56w, Form 460 Schedules A and C)',
    'conc': 'network/data/analysis/concentration.json',
    'ie': 'network/data/interim/ie.parquet (Form 496 items, DataSF pitq-e56w); network/data/raw/cf_transactions.csv (duplicate check)',
    'edges': 'network/data/network/edges.parquet',
    'rt2': 'network/data/redteam/redteam2.json',
    'sectors': 'network/data/insights/sector_labels.parquet (Claude Sonnet labels of organization names, hand-checked)',
    'lobc': 'network/data/analysis/lobbyist_contributions.parquet',
    'contacts': 'network/data/interim/lobby_contacts.parquet (lobbyist disclosures, DataSF s4ub-8j3t)',
    'ban_rec': 'network/data/analysis/ban_base_rate_records.parquet',
    'ban_site': 'network/data/site/analyses/ban_window.json#records[].review',
    'beh': 'network/data/analysis/behested.json',
    'beh_raw': 'network/data/interim/behested.parquet (FPPC Form 803 98wa-4d49; SFEC-3610(b) b3ya-imj5)',
    'f1145': 'network/data/interim/f1145.parquet (SFEC Form 114.5, DataSF hyuc-khdi and mq45-f9zi)',
    'waivers': 'network/data/interim/bp_waivers.parquet (Board waivers of the behested-solicitation ban, DataSF 8w9a-q5s8)',
    'offmap': 'network/data/er/lobby_official_map.parquet',
    'bpb': 'network/data/analysis/behested_pending_business.parquet',
    'loop': 'network/data/analysis/nonprofit_loop.parquet',
    'enf': 'network/data/interim/enforcement.parquet (Ethics Commission enforcement summaries)',
    'officials': 'network/data/er/officials.parquet',
}

TIMING = 'A donation near a contract, approval or request is a pattern worth checking, not proof of improper influence.'
NOMINAL = 'Dollars are nominal (not adjusted for inflation).'
MEET = 'A meeting is one client, one official (or staff group) and one day; several lobbyists often report the same meeting.'
LIMIT_RULE = ('Candidate committees may take no more than $500 per person per election and nothing from corporations (C&GCC §1.114(a)-(b)); '
              'ballot-measure and independent-expenditure committees not controlled by a candidate are not subject to that limit.')

INSIGHTS = [
    # 1 ------------------------------------------------------------------------------------------------------------------
    dict(key='ie_vs_donors', id='outside-spending-outran-donations-2024', theme='campaign-money',
         title='Independent spending on 2024 City races was {ratio_2024|x1} times what donors gave candidates',
         dek='Committees acting independently of the candidates reported {ie_2024|mil1} of spending on 2024 City races, most of it in the '
             'mayor\'s race, against {cand_2024|mil1} that donors gave the candidates\' own committees. Counting the {self_2024|mil1} candidates put into '
             'their own campaigns, the two sides were about equal. In the 2011 mayoral election, independent spending equaled {ratio_2011|pct} of donations.',
         why_it_matters=LIMIT_RULE + ' Such spending is legal and disclosed, but when most of the money in a race sits outside the campaigns, the full list of who paid for '
                        'the messages voters see is in separate filings, and candidates control less of what is said about them.',
         surprise='Contribution limits are meant to cap big money in candidate races. In 2024 about {share_unlimited|pct} of the money in City races came from sources the $500 limit '
                  'does not reach: independent spending and one candidate\'s own funds.',
         numbers=[
             dict(label='Independent spending on City candidates, 2024 (Form 496, duplicates removed)', value='{ie_2024|mil1}', source=SRC['conc'] + '#independent_expenditures.ie_on_city_candidates_by_year; ' + SRC['ie']),
             dict(label='Donations to City candidate committees, 2024 (excluding candidates\' own money and committee transfers)', value='{cand_2024|mil1}', source=SRC['conc'] + '#independent_expenditures.candidate_committee_receipts_by_year; ' + SRC['contrib']),
             dict(label='Ratio of independent spending to donations: 2011 → 2018 → 2024', value='{ratio_2011|x2} → {ratio_2018|x2} → {ratio_2024|x2}', source=SRC['conc']),
             dict(label='Candidates\' own money in their committees, 2024', value='{self_2024|mil1}, of which {self_top_2024|mil1} from Daniel Lurie, now Mayor. Candidates may legally fund their own campaigns without limit', source=SRC['conc'] + '#candidate_self_funding_city_by_year, largest_self_funding'),
         ],
         chart=dict(type='bar', title='Independent spending overtook donations in the 2024 mayoral year',
                    subtitle='City races in mayoral election years, $ millions (nominal): donations to candidate committees, candidates\' own money, and independent spending',
                    x=dict(label='Election year', values='@CH:x'), y=dict(label='$ millions', unit='$M'),
                    series=[dict(name='Donations to candidate committees', values='@CH:cand'), dict(name='Candidates\' own money', values='@CH:self'),
                            dict(name='Independent spending', values='@CH:ie')],
                    highlight='Independent spending',
                    note='Sources: SF Ethics Commission campaign filings (DataSF pitq-e56w): Form 460 receipts and Form 496 independent expenditures. '
                         'Form 496 covers the final 90 days before an election, so independent spending is a floor. Public financing is not in this dataset. ' + NOMINAL),
         robustness=dict(verdict='robust', checks=[
             'Counting candidates\' own money as well, candidate committees took in {cand_self_2024|mil1} in 2024, about the same as independent spending '
             '(ratio {ratio_incl_self_2024|x2}); in 2011 independent spending was {ratio_incl_self_2011|pct} of that total.',
             'Keeping the {dup_2024|mil2} of Form 496 items that were filed twice would raise the 2024 ratio to {ratio_with_dups_2024|x1}; removing them is the conservative choice.',
             'Most of it was the mayor\'s race: in Supervisor contests alone, independent spending was {ie_bos_2024|mil1} against {cand_bos_2024|mil1} donated to Board of Supervisors candidates (ratio {ratio_bos_2024|x2}).',
             'Form 496 24-hour reports cover the final 90 days before an election; earlier independent spending reported on other forms is not counted, so a fuller count would widen the 2024 gap, not close it.',
             'The ratio compares dollars within the same year, so inflation does not affect it.'],
             what_could_make_it_wrong='Independent spending is attributed to the candidate it names, whether it supported or opposed that candidate, and some committees did both. '
                                      'Public financing paid to candidates is not in this dataset, so candidates had more to spend than donations alone.'),
         caveats=['Independent spending includes spending against candidates.', 'Public financing is not included.', NOMINAL],
         explore=dict(view='nw-concentration', params={}, label='See committees and donors (all years; this view has no year filter)'),
         departments=[], tags=['independent spending', 'contribution limits', 'mayoral race']),

    # 2 ------------------------------------------------------------------------------------------------------------------
    dict(key='ballot_sectors', id='soda-tobacco-vape-ballot-money', theme='campaign-money',
         title='Soda, tobacco and vape interests gave ballot fights {stv|mM} since 2010; candidates got {cand_total|mM}',
         dek='Since 2010, {stv_n_orgs|int} beverage, tobacco and vaping companies and trade groups gave {stv|mil1} to San Francisco ballot-measure committees '
             'in campaigns over taxes and sales limits on their own products. All donors together gave every City candidate committee {cand_total|mil1} over the same years. '
             'Ballot committees overall took in {ballot_total|mil1}, {ballot_to_cand|x1} times as much (both totals count transfers between committees at the receiving committee).',
         why_it_matters='Ballot-measure committees not controlled by a candidate are not subject to the $500 limit on contributions to candidate committees (C&GCC §1.114(a)), '
                        'so an industry whose products are on the ballot can legally spend more than the whole field of candidates. Voters see these campaigns under coalition names; '
                        'who pays shows up in the filings.',
         surprise='Races for mayor and supervisor draw most of the attention, but most of the money in San Francisco politics goes to ballot measures.',
         numbers=[
             dict(label='Beverage, tobacco and vape companies and trade groups to ballot-measure committees, 2010 to Sept. 2026', value='{stv|mil1} ({stv_share|pct} of all ballot-measure money)', source=SRC['sectors'] + '; ' + SRC['contrib']),
             dict(label='All donations to City candidate committees, same years (including transfers from other committees; excluding candidates\' own money)', value='{cand_total|mil1}', source=SRC['contrib']),
             dict(label='All money to ballot-measure committees, same years', value='{ballot_total|mil1}', source=SRC['contrib']),
             dict(label='Tech companies / real estate and development / labor unions', value='{tech|mil1} / {re|mil1} / {labor|mil1}', source=SRC['sectors']),
             dict(label='Individuals (aggregated; no individual is named)', value='{ind|mil1} ({ind_share|pct})', source=SRC['contrib']),
         ],
         chart=dict(type='hbar', title='Three consumer-product industries gave more than all City candidates\' donors combined',
                    subtitle='Money given to San Francisco ballot-measure committees, 2010 to Sept. 2026, by type of donor, $ millions (nominal); dashed line: all donations to City candidate committees',
                    x=dict(label='Donor type', values='@CH:x'), y=dict(label='$ millions', unit='$M', ref=dict(value='@V:cand_total_m', label='All donations to City candidates')),
                    series=[dict(name='Given to ballot-measure committees', values='@CH:m')],
                    highlight='Soda, tobacco and vape companies and trade groups',
                    note='Sources: SF Ethics Commission campaign filings (DataSF pitq-e56w). Organizations giving $10,000 or more were labelled by sector from their names '
                         '(Claude Sonnet, hand-checked for the 40 largest, with analyst overrides); smaller organizations are not shown. Individuals are shown only as one aggregate. ' + NOMINAL),
         robustness=dict(verdict='robust', checks=[
             'A plain name search for beverage, tobacco and vaping companies, without the model\'s labels, finds {stv_rx|mil1}.',
             'By industry: beverage groups {bev|mil1}, tobacco and vape companies {tob_vape|mil1}; together they exceed the candidate total, each alone is more than half of it.',
             'Without transfers from other committees, candidates\' donors gave {cand_no_com|mil1}, a wider gap.',
             'In 2026 dollars (national CPI-U): the three industries {stv_real|mil1}, all candidate donations {cand_real|mil1}.',
             'Candidates\' own money is excluded because it is not raised from donors; adding it (mostly one 2024 candidate) brings candidate committees to {cand_incl_self|mil1}, and the industries\' total to {stv_vs_self_total|pct} of that.',
             'Labels with confidence under {conf_cut|pct} cover {low_conf_share|pct1} of ballot money; {labelled_share_org|pct} of organization money is labelled.'],
             what_could_make_it_wrong='Sector labels come from organization names; money routed through committees whose funders are not evident stays in its own category and could hide more industry money. '
                                      'Years follow the filings: the vape company\'s contributions to its 2019 measure committee are dated Dec. 31, 2021.'),
         caveats=['The chart shows who gave, not which side won or what the other side of each measure spent; spending on ballot measures by affected industries is legal and disclosed.',
                  'Transfers between committees are counted at the receiving committee.', '2026 covers filings through the September download.', NOMINAL],
         explore=dict(view='nw-concentration', params={}, label='See ballot-measure committees and their donors'),
         departments=[], tags=['ballot measures', 'industry money', 'soda tax', 'tobacco', 'vaping']),

    # 3 ------------------------------------------------------------------------------------------------------------------
    dict(key='outside_concentration', id='few-donors-fund-outside-money', theme='campaign-money',
         title='Top 1% of donors gave {cand_top1|pct} of 2024 candidate money but {ie_top1|pct} of independent committees\' money',
         dek='Under the $500 limit, candidate fundraising is spread across many people: in 2024 the top 1% of donors to City candidate committees supplied {cand_top1|pct}. '
             'The {ie_coms|int} committees that spent independently on 2024 City races raised {ie_total|mil1} in 2023 and 2024; the top 1% of their donors, people and '
             'organizations, gave {ie_top1|pct}, and {n_ind_100k|int} individuals who each gave $100,000 or more together supplied {share_ind_100k|pct}.',
         why_it_matters='Limits on candidate committees are designed so that no single donor looms large, and inside the campaigns they appear to do that. Committees not controlled by a '
                        'candidate are not subject to the $500 limit, so a small group of large donors can legally fund much of the spending around the campaigns; their gifts are disclosed '
                        'in the committees\' filings. Individuals are shown here only in aggregate.',
         surprise='Independent committees are often assumed to run on corporate or union money; {ie_ind_share|pct} of what these committees raised came from individuals.',
         numbers=[
             dict(label='Top 1% of donors\' share, 2024: candidate / ballot-measure / general-purpose committees', value='{cand_top1|pct} / {ballot_top1|pct} / {gp_top1|pct}', source=SRC['contrib']),
             dict(label='Committees that made independent expenditures on 2024 City candidates: money raised in 2023 and 2024', value='{ie_total|mil1} from {ie_n|int} donors; top 1% gave {ie_top1|pct}', source=SRC['edges'] + ' (independent_expenditure); ' + SRC['contrib']),
             dict(label='Individuals who gave those committees $100,000 or more', value='{n_ind_100k|int} people, {share_ind_100k|pct} of the money (aggregate only)', source=SRC['contrib']),
             dict(label='Share of these committees\' receipts from individuals / from individuals who gave under $1,000 in total', value='{ie_ind_share|pct} / {share_ind_under_1k|pct1}', source=SRC['contrib']),
         ],
         chart=dict(type='hbar', title='A few donors supply half or more of the money everywhere except candidate committees',
                    subtitle='Share of money raised that came from the top 1% of donors, by committee type: 2024 receipts, except independent-spending committees (2023 and 2024); committee transfers and candidates\' own money excluded',
                    x=dict(label='Committee type', values='@CH:x'), y=dict(label='Share from top 1% of donors', unit='%'),
                    series=[dict(name='Share from the top 1% of donors', values='@CH:top1')],
                    highlight='Committees that spent independently on 2024 City races',
                    note='Sources: SF Ethics Commission campaign filings (DataSF pitq-e56w). Donors are grouped by the pipeline\'s person and organization keys. '
                         'Independent-spending committees: every committee that reported Form 496 spending on a City candidate in 2024; their receipts cover 2023 and 2024.'),
         robustness=dict(verdict='robust', checks=[
             'Every year from 2010 to 2026 the top 1% supplied between {cand_top1_min|pct} and {cand_top1_max|pct} of candidate-committee money.',
             'In the four independent committees that spent the most, individuals who gave $100,000 or more supplied {big4_share_ind_100k|pct} of receipts.',
             'A cruder donor key (last name and first initial, red-team check) gives {rt_crude|pct} for candidate committees in 2024, so the low share is not a matching artifact.',
             'Organizations supplied only {cand_org_share|pct1} of candidate-committee money in 2024, consistent with the ban on contributions from corporations, LLCs and LLPs (§1.114(b)).'],
             what_could_make_it_wrong='A donor filed under two spellings counts as two people, which understates concentration. Some of these committees also spent on ballot measures '
                                      'or voter guides, so not all of their money went to City candidates.'),
         caveats=['Private individuals appear only in aggregate.', 'Committee-to-committee transfers are excluded to avoid double counting.', NOMINAL],
         explore=dict(view='nw-concentration', params={}, label='See donor concentration by committee (all years)'),
         departments=[], tags=['concentration', 'independent expenditures', 'large donors']),

    # 4 ------------------------------------------------------------------------------------------------------------------
    dict(key='lobbyist_ban', id='lobbyist-ban-clean-break', theme='reforms',
         title='Lobbyists\' contributions tied to recent lobbying: {fl_2017|int} in 2017, none since 2019',
         dek='Before San Francisco barred lobbyists from giving to officers of agencies they lobby (C&GCC §2.115(d), operative Jan. 1, 2018), {fl_share_pre|pct} of the '
             'contributions we could match to registered lobbyists went to an officer or candidate whose agency the lobbyist had contacted in the prior 90 days: '
             '{fl_pre|int} contributions from 2010 to 2017. In 2018 there were {post_pos|int}, all refunded; from 2019 to 2025, {fl_post_1925|int}.',
         why_it_matters='The drop lines up with the ban\'s start, consistent with a bright-line rule tied to a public registration being easy to follow; yearly data cannot rule out '
                        'other causes. Lobbyists kept giving to candidates for offices they had not recently lobbied, though less often than before.',
         surprise='Campaign-finance rules are often said to push money into other channels rather than stop it. Here the direct, disclosed targeted giving stopped; the data '
                  'cannot show whether any moved to other channels, such as contributions made through other people.',
         numbers=[
             dict(label='Contributions to an agency the lobbyist had contacted in the prior 90 days, 2010-2017', value='{fl_pre|int} ({fl_pre_amt|usd})', source=SRC['rt2'] + '#rederivation.lobbyist_contributions; ' + SRC['lobc']),
             dict(label='Same, 2018 / 2019-2025', value='{post_pos|int} ({post_pos_amt|usd}, all {post_refunded|int} refunded) / {fl_post_1925|int}', source=SRC['rt2'] + '; ' + SRC['lobc']),
             dict(label='All contributions matched to lobbyists, average per year: 2010-2017 → 2019-2025', value='{avg_pre|int} → {avg_post|int}', source=SRC['lobc']),
             dict(label='Per lobbyist reporting contacts: 2015-2017 → 2019-2025', value='{per_lob_1517|x2} → {per_lob_1925|x2} contributions a year', source=SRC['lobc'] + '; ' + SRC['contacts']),
         ],
         chart=dict(type='stacked', title='The targeted contributions vanished when the ban began',
                    subtitle='Contributions by registered lobbyists to City candidates and officeholders, by year (count of positive contributions; the {post_pos|int} in 2018 to recently contacted agencies were all refunded)',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Contributions', unit='count'),
                    series=[dict(name='To an agency the lobbyist had contacted in the prior 90 days', values='@CH:flagged'),
                            dict(name='Other contributions to City candidates', values='@CH:other')],
                    annotations=[dict(x=2018, label='Ban takes effect')], highlight='To an agency the lobbyist had contacted in the prior 90 days',
                    note='Sources: lobbyist disclosures (DataSF s4ub-8j3t) and campaign filings (pitq-e56w); lobbyists matched to donors by name. '
                         '"Registered to lobby the agency" is approximated by a reported contact with it in the prior 90 days.'),
         robustness=dict(verdict='robust', checks=[
             'With a 180-day look-back, {pre_180|int} contributions from 2010 to 2017 had an earlier contact with the recipient\'s agency, against {post_180|int} from 2019 to 2025; because the ban turns on registration, which we did not check directly, we do not classify those as inside or outside it.',
             'High-confidence name matches only ({hc_cut|f2} or above): {hc_pre|int} before 2018, {hc_post|int} from 2019.',
             'Not just fewer lobbyists: about as many lobbyists reported contacts each year ({act_1517|int} in 2015-2017, {act_1925|int} in 2019-2025), while their contributions per lobbyist fell.',
             'Other giving continued: {avg_post|int} contributions a year from 2019 to 2025 went to candidates for offices the lobbyist had not recently contacted.'],
             what_could_make_it_wrong='Lobbyists are matched to donors by name, and registration is approximated by reported contacts in the prior 90 days. The pre-2018 count is a floor, and the '
                                      'post-2019 zero means none by this measure: a lobbyist still registered for an agency without a recent reported contact would be covered by the ban but not counted here. '
                                      'The data cannot show contributions made through other people.'),
         caveats=['A contribution soon after a lobbying contact is a pattern worth checking, not proof of improper influence; before 2018 such contributions were legal and disclosed.',
                  'The ban was re-enacted by Proposition D (operative Oct. 12, 2024).'],
         explore=dict(view='nw-lobby', params={'years': '2015-2025'}, label='See lobbying and lobbyists\' contributions'),
         departments=['ETH'], tags=['lobbyist ban', 'reform', 'Proposition T']),

    # 5 ------------------------------------------------------------------------------------------------------------------
    dict(key='contractor_ban', id='contractor-ban-near-chance', theme='reforms',
         title='Contractor principals gave in post-approval ban windows a bit below chance: {obs|pct1} vs {exp|pct1}',
         dek='Of {n_rec|int} contributions from 2019 to 2025 by the disclosed principals of {n_con|int} city contractors, {obs|pct1} fell inside a post-approval window '
             'while the recipient covered the contract, against {exp|pct1} expected if giving ignored contract timing (same donors and offices, weighted by the '
             'election calendar). The shortfall is small: {diff_hi|pts1} to {diff_lo|pts1} points (95% interval).',
         why_it_matters='Unlike the lobbyist ban, the contractor ban (C&GCC §1.126(b)-(c)) turns on dates donors may not see: a proposal, an approval and the 12 months after it, '
                        'one possible reason the data show only slight avoidance. {n_review|int} contributions appear to warrant review under §1.126(b)-(c), because they fell inside a '
                        'post-approval window and went to an officer who approved the contract, or a candidate for that office. Many may have innocent explanations: a different person '
                        'with a similar name, an approval date that differs from the filing date, a donor who had left the company, or a contract below the threshold. (§1.126(e) requires a '
                        'committee that accepts a prohibited contribution to pay it to the City.) This is a reason to check, not a finding of a violation.',
         surprise='A contribution ban might be expected to empty its windows; giving inside them runs only a few points below chance.',
         numbers=[
             dict(label='Share inside a covered window, observed vs expected by chance (2019-2025, public-entity contractors excluded)', value='{obs|pct1} vs {exp|pct1}', source=SRC['ban_rec'] + '#inside, e_weighted'),
             dict(label='Difference, 95% interval (contractor-cluster bootstrap)', value='{diff_lo|pts1} to {diff_hi|pts1} points below chance', source=SRC['rt2'] + '#rederivation.ban_base_rate.bootstrap_95ci'),
             dict(label='Contributions that appear to warrant review under C&GCC §1.126(b)-(c) (as amended by Ord. 129-18); the dashboard\'s review list applies stricter name-match and coverage tests than the base-rate sample, so the counts differ', value='{n_review|int}, totaling {sum_review|usd}; median {med_review|usd}; {share_500|pct} at or under $500', source=SRC['ban_site']),
             dict(label='Of those, with a possible refund or repayment in the filings (the data do not show whether it went to the donor or the City)', value='{refund_seen|int}', source=SRC['ban_site']),
         ],
         chart=dict(type='bar', title='Inside the ban window slightly less often than chance',
                    subtitle='Share of contractor principals\' contributions that fell inside a covered post-approval window, observed vs expected by chance, 2019-2025',
                    x=dict(label='Contributions made in', values='@CH:x'), y=dict(label='Share inside a window', unit='%'),
                    series=[dict(name='Observed', values='@CH:obs'), dict(name='Expected by chance', values='@CH:exp')],
                    highlight='Observed',
                    note='Sources: Form SFEC-126(f)4 contract-approval filings, campaign filings (pitq-e56w). Expected share: for each contribution, the calendar-weighted share of days '
                         'on which the same recipient was covered by one of that contractor\'s approvals. Red-team pass 2, redteam2.json.'),
         robustness=dict(verdict='robust', checks=[
             'Election years {obs_even|pct1} vs {exp_even|pct1}; off years {obs_odd|pct1} vs {exp_odd|pct1}.',
             'Applying the 12-month window to every contribution made from 2019 on (an alternative reading of the transition): {obs12|pct1} vs {exp12|pct1}.',
             'Including public-entity contractors: {obs_all|pct1} vs {exp_all|pct1}.',
             'Without the election-calendar weighting, chance would predict {exp_unif|pct1}; the gap widens a little but stays small.'],
             what_could_make_it_wrong='Approval dates are proxied by the Form SFEC-126(f)4 filing date and proposal dates are not in the data, so the pre-award part of the ban is not tested. '
                                      'Principals are matched to donors by name (confidence {conf_min|f2} or above); wrong matches would pull the observed share toward chance and understate avoidance. '
                                      'An earlier placebo comparison was dropped as unstable.'),
         caveats=[TIMING, 'Flagged contributions are small: the largest is {max_review|usd}, which may cover two elections or a committee not subject to the $500 limit.',
                  'A committee that accepts a prohibited contribution must pay it to the City (§1.126(e)); {refund_seen|int} flagged contributions show a possible refund or repayment.',
                  'The base-rate sample uses looser matching than the review list, so not every contribution inside a window would be covered by the ban.'],
         explore=dict(view='nw-ban', params={}, label='See the ban-window records'),
         departments=[], tags=['contractor ban', 'base rate', 'timing']),

    # 6 ------------------------------------------------------------------------------------------------------------------
    dict(key='behested_vanished', id='behested-records-disappeared', theme='transparency',
         title='Machine-readable behested-payment records end after 2023: {used_rows|int} payments since 2015, then none',
         dek='Payments that companies and foundations make to charities and city programs at an official\'s request can be counted only while two streams '
             'were machine-readable: state Form 803 filings in the Ethics Commission\'s dataset (2015 to March 2018) and the city\'s own forms (SFEC-3600 and SFEC-3610(b), 2018 to 2023). '
             'Together they list {used_rows|int} payments worth {total_used|mil1}; nothing after 2023. Contributions officials request for ballot committees are a separate, still-reported stream (see the Form 114.5 finding).',
         why_it_matters='State law still requires elected officers to report behested payments of $5,000 or more a year from one source within 30 days (Gov. Code §82015), '
                        'but since March 2018 those filings are PDFs only, and the city\'s own reporting was repealed effective Jan. 24, 2022 (Ord. 232-21), when a solicitation '
                        'ban took its place (C&GCC §3.620). The drop is in what can be counted, not necessarily in what was given.',
         surprise='Mayor Edwin Lee requested {lee_n|int} of the {n803|int} Form 803 payments on file, {lee_share|pct} of their value, most of it for city-affiliated funds (the Mayor\'s Fund for the Homeless, '
                  'the 2015 U.S. Conference of Mayors and the City Hall centennial), and disclosed them as state law requires. After March 2018 mayors\' Form 803 filings are PDFs only, and the city\'s '
                  'machine-readable form, which covered only payments from interested parties, lists {mayor_after|int} requested by a mayor; open data cannot show how much later mayors requested.',
         numbers=[
             dict(label='Behested payments on file, 2015', value='{n2015|int} payments, {y2015|mil1}', source=SRC['beh'] + '#by_year; ' + SRC['beh_raw']),
             dict(label='Of which to the Mayor\'s Fund for the Homeless / the San Francisco Travel Foundation (2015 U.S. Conference of Mayors, City Hall centennial)', value='{homeless_2015|mil1} / {travel_2015|mil1}', source=SRC['edges'] + ' (behested_payment)'),
             dict(label='Form 803 total (2015-2018) and share requested by Mayor Edwin Lee', value='{tot803|mil1}; {lee|mil1} ({lee_share|pct})', source=SRC['beh'] + '#by_form, officials'),
             dict(label='City Form SFEC-3610(b), 2019-2023', value='{n3610|int} payments, {t3610|mil1}', source=SRC['beh'] + '#by_form'),
         ],
         chart=dict(type='stacked', title='What can be counted stopped, first at the state level, then locally',
                    subtitle='Behested payments in machine-readable open data, by year of payment, $ millions (nominal)',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='$ millions', unit='$M'),
                    series=[dict(name='State Form 803 (Ethics Commission dataset)', values='@CH:f803'), dict(name='City Form SFEC-3610(b)', values='@CH:local')],
                    annotations=[dict(x=2018, label='Form 803 goes PDF-only'), dict(x=2022, label='City reporting repealed')],
                    note='Sources: FPPC Form 803 dataset (DataSF 98wa-4d49, April 2015 to March 2018); SFEC-3600 (commissioners, 2018) and SFEC-3610(b) (b3ya-imj5). City reporting was repealed effective Jan. 24, 2022; '
                         'the 2023 rows are one official\'s filings published in the dataset after that date. Excludes {amb_n|int} 2021 rows whose payor field lists recipients. ' + NOMINAL),
         robustness=dict(verdict='robust', checks=[
             'Counting payments instead of dollars shows the same break: {n2015|int} in 2015, {n2023|int} in 2023, none after.',
             'Original and amended copies of the same payment are counted once ({raw_rows|int} rows become {used_rows|int} payments used).',
             'Adding the {amb_n|int} ambiguous 2021 rows ({amb_amt|mil1}) would raise 2021 only; the years after 2023 stay empty.',
             'The two largest 2015 payees account for {y2015_top2_share|pct} of that year, so the peak reflects a few city-affiliated funds rather than broad giving.'],
             what_could_make_it_wrong='Behested giving may have continued at similar levels in the PDF-only Form 803 filings; transcribing them would show whether giving fell or only its visibility.'),
         caveats=['Behested payments go to charities, public programs or other organizations, not to the official. Asking for them is generally legal and, under state law, disclosed on Form 803; '
                  'since Jan. 24, 2022, City officials may not solicit them from interested parties (C&GCC §3.620(a)).',
                  'The total excludes {amb_n|int} rows from 2021 ({amb_amt|mil1}) whose payor field lists recipients rather than payors; they would change 2021 only.', NOMINAL],
         explore=dict(view='nw-behested', params={}, label='See behested payments on file'),
         departments=['MYR'], tags=['behested payments', 'disclosure gap', 'Form 803']),

    # 7 ------------------------------------------------------------------------------------------------------------------
    dict(key='form_1145', id='behests-moved-to-ballot-committees', theme='behested',
         title='Donors gave {y2026|mM1} to ballot committees at officials\' request in 2026 (to Sept.), a record',
         dek='A ballot-measure or independent-expenditure committee that receives $5,000 or more in a calendar year at a City elective officer\'s behest must file Form 114.5 '
             '(C&GCC §1.114.5(b)(2), as described by the Ethics Commission). Reported amounts reached {y2026|mil1} by September 2026, above the previous high of {y2019|mil1} in 2019, '
             '{peskin_breed_2019_share|pct} of which came at the behest of Supervisor Aaron Peskin and Mayor London Breed. {lurie_share_2026|pct} of the 2026 total was raised at '
             'Mayor Daniel Lurie\'s behest, mostly for committees that carry his name.',
         why_it_matters='These are campaign contributions, a separate category from the behested payments to charities in the Form 803 and SFEC-3610(b) records. Mayors and supervisors '
                        'routinely raise money for measures they sponsor, and the $500 per-donor limit applies only to candidate committees (C&GCC §1.114(a)). The practice is legal and '
                        'disclosed; it shows that what donors give at an official\'s request is not bounded by the candidate limit.',
         numbers=[
             dict(label='Behested contributions reported on Form 114.5, 2026 (through September)', value='{y2026|mil1} in {n_2026|int} contributions (median {med_2026|usd}) to {n_com_2026|int} committees', source=SRC['f1145']),
             dict(label='At Mayor Daniel Lurie\'s behest, 2026', value='{lurie_2026|mil1}', source=SRC['f1145'] + '#cityelectiveofficername'),
             dict(label='Previous high (2019) and total since the form began', value='{y2019|mil1}; {total|mil1} in {n_rows|int} contributions', source=SRC['f1145']),
         ],
         chart=dict(type='bar', title='Behested money for ballot committees hit a record in 2026',
                    subtitle='Contributions reported on Form 114.5 as made at a City elective officer\'s behest, by year, $ millions (nominal); 2026 through September',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='$ millions', unit='$M'),
                    series=[dict(name='Behested contributions', values='@CH:v')], highlight='2026',
                    note='Source: SFEC Form 114.5 filings and itemized contributions (DataSF hyuc-khdi, mq45-f9zi), duplicates removed. None reported for 2021. ' + NOMINAL),
         robustness=dict(verdict='robust', checks=[
             'Original filings only, without amendments: {orig_only_2026|mil1} in 2026, still above 2019.',
             'Counting contributions rather than dollars: {n_2026|int} in 2026, the most of any year.',
             'Rows repeated across a filing (same filing, contributor, date and amount) are counted once.',
             'Most of the 2026 total came at one official\'s behest: without contributions made at the Mayor\'s behest, 2026 would be {y2026_ex|mil1}.'],
             what_could_make_it_wrong='Form 114.5 depends on committees reporting what was raised at an officer\'s behest: under-reporting would hide more, while fuller reporting by new committees '
                                      'could raise totals without any change in practice. Totals also rise and fall with how many measures officials sponsor in a year. 2026 counts only what was filed by the September download.'),
         caveats=['Individual contributors are not named here.', '2026 is a partial year (through the September download).', NOMINAL],
         explore=dict(view='nw-behested', params={}, label='See behested payments and contributions'),
         departments=['MYR'], tags=['behested contributions', 'ballot measures', 'Form 114.5']),

    # 8 ------------------------------------------------------------------------------------------------------------------
    dict(key='pension_lobbying', id='pension-fund-lobbying', theme='lobbying',
         title='Pension fund\'s share of lobbying meetings rose from {s2015|pct} in 2015 to {s2022|pct} in 2022 ({s2025|pct} in 2025)',
         dek='Investment firms and their agents reported {n_meet|int} meetings with the Retirement System from 2015 to 2025, {overall|pct} of all lobbying meetings and more than '
             'with the Mayor\'s Office ({mayor_overall|pct}). {n_clients|int} clients met with {n_people|int} Retirement System board members and staff; the most active by meetings were '
             '{top1_name|str} and {top2_name|str}.',
         why_it_matters='The Retirement System chooses which firms manage the city\'s pension assets and earn fees on them. Meetings with investment staff are the routine way managers and '
                        'their placement agents seek to be considered, and a larger roster of outside managers means more of them. This lobbying almost never involves elected officials.',
         surprise='In 2022 and 2023, about one reported lobbying meeting in five was with the pension fund, whose investment decisions are made by its own board rather than the Board of Supervisors.',
         numbers=[
             dict(label='Retirement System share of lobbying meetings: 2015 → 2022 → 2025', value='{s2015|pct} → {s2022|pct} → {s2025|pct}', source=SRC['edges'] + ' (lobbying_contact); ' + SRC['contacts']),
             dict(label='Meetings with the Retirement System, 2015-2025', value='{n_meet|int} ({overall|pct} of all)', source=SRC['contacts']),
             dict(label='Clients / Retirement System people contacted', value='{n_clients|int} / {n_people|int}', source=SRC['edges']),
             dict(label='Share of those meetings with elected officials', value='{elected_share|pct1}', source=SRC['offmap']),
             dict(label='All distinct lobbying meetings: 2015 / 2022 / 2025', value='{tot_2015|int} / {tot_2022|int} / {tot_2025|int}', source=SRC['edges'] + ' (lobbying_contact)'),
         ],
         chart=dict(type='line', title='At the peak, one lobbying meeting in five was with the pension fund',
                    subtitle='Retirement System share of distinct lobbying meetings, by year',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Share of meetings', unit='%'),
                    series=[dict(name='Retirement System share', values='@CH:share')],
                    note='Source: lobbyist disclosures (DataSF s4ub-8j3t), contacts with the Retirement System department. ' + MEET),
         robustness=dict(verdict='robust', checks=[
             'Counting every contact report instead of distinct meetings: {raw2022|pct} in 2022.',
             'By subject (City Employee Benefits) instead of department: {sb2022|pct} in 2022.',
             'Without the two most active clients: {no_top2_2022|pct} in 2022.',
             'Meetings with the Retirement System more than tripled, from {n_meet_2015|int} in 2015 to {n_meet_2022|int} in 2022, while all meetings fell from {tot_2015|int} to {tot_2022|int}; both contributed to the rise in share.'],
             what_could_make_it_wrong='Registrants differ in how routinely they report calls and meetings, and the share also moves when other lobbying falls, as development lobbying did after 2019.'),
         caveats=['Retirement System staff are not named.', MEET],
         explore=dict(view='nw-lobby', params={'years': '2015-2025'}, label='See lobbying by client and department'),
         departments=['RET'], tags=['pension fund', 'investment managers', 'lobbying']),

    # 9 ------------------------------------------------------------------------------------------------------------------
    dict(key='staff_targets', id='lobbying-aimed-at-departments', theme='lobbying',
         title='{dept|pct} of lobbying meetings are with department officials, not elected officials\' offices',
         dek='From 2015 to 2025, {el_off|pct} of {n|int} distinct lobbying meetings were with elected officials or the staff of the Board of Supervisors and the Mayor\'s Office; '
             '{ex|pct} were with department heads and commissioners and {st|pct} with other department staff. {permits|pct} concerned planning and building permits.',
         why_it_matters='Many decisions lobbyists care about, such as permits, conditions of approval and contract terms, are shaped in departments before they reach an elected body, '
                        'and meeting the staff who review an application is a normal part of that process. Looking only at elected officials would miss most of the reported activity. '
                        'Only contacts with officials covered by the Lobbyist Ordinance are reported, so the true department share may be higher.',
         surprise='Most reported lobbying is with appointed and civil-service officials, who shape permits and contract terms before any elected body votes.',
         numbers=[
             dict(label='Share of meetings, 2015-2025: elected offices / department heads and commissioners / department staff', value='{el_off|pct} / {ex|pct} / {st|pct}', source=SRC['edges'] + ' (lobbying_contact); ' + SRC['offmap']),
             dict(label='Meetings with elected officials in person (the rest of the elected-office share were with their aides and office staff)', value='{el_only|pct}', source=SRC['offmap']),
             dict(label='Planning and building permits, share of meetings (share of department meetings)', value='{permits|pct} ({permits_dept|pct})', source=SRC['contacts']),
         ],
         chart=dict(type='stacked', title='Nearly three lobbying meetings in four are with departments',
                    subtitle='Distinct lobbying meetings by who was met, share of each year',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Share of meetings', unit='%'),
                    series=[dict(name='Elected officials and their offices', values='@CH:s0'), dict(name='Department heads and commissioners', values='@CH:s1'),
                            dict(name='Department staff', values='@CH:s2')],
                    note='Source: lobbyist disclosures (DataSF s4ub-8j3t). Officials classed from Form 700 positions and department names; aides in the Board and Mayor\'s offices count with elected officials. ' + MEET),
         robustness=dict(verdict='robust', checks=[
             'Counting every contact report instead of distinct meetings: {dept_raw|pct} with departments.',
             'Excluding planning and building permits: {dept_np|pct} still with departments.',
             'Every year from 2015 to 2025, elected offices got between {min_el|pct} and {max_el|pct} of meetings.',
             'Before 2015 the records differ: the 2010-2014 disclosures hold far fewer contacts and show elected offices at {el_off_old|pct}, so they are not compared.'],
             what_could_make_it_wrong='Officials are classed by Form 700 position titles and department names, so some commissioners, aides and managers may be misclassified.'),
         caveats=['Department staff are counted in aggregate and not named.', MEET],
         explore=dict(view='nw-lobby', params={'years': '2015-2025'}, label='See who lobbyists meet'),
         departments=[], tags=['lobbying', 'staff', 'permits']),

    # 10 -----------------------------------------------------------------------------------------------------------------
    dict(key='av_lobbying', id='robotaxi-lobbying-surge', theme='lobbying',
         title='Autonomous-vehicle lobbying rose from {s2019|pct1} of meetings in 2019 to {s2025|pct1} in 2025 (both sides)',
         dek='Meetings about autonomous vehicles, or held by companies that run them, reached {n2025|int} in 2025. Waymo held {waymo_share_av_2025|pct} of them and was the '
             '{waymo_rank_2025|ord} active lobbying client that year by distinct meetings. The most active, {first_2025|tc}, listed issues including autonomous-vehicle policy and a '
             'proposed ban on autonomous commercial delivery; the measure counts lobbying on both sides.',
         why_it_matters='State agencies issue the main permits for driverless cars, so the city\'s levers are streets, curbs, traffic rules and airport access. From 2018 to 2025, '
                        '{mta|pct} of Waymo\'s meetings were with the SFMTA and {airport|pct} with the Airport, and {w_elected|pct} were with elected officials and their offices. '
                        'A company seeking access to city streets or the airport would be expected to hold such meetings.',
         surprise='Waymo\'s lobbyists filed {waymo_raw_2025|int} contact reports in 2025, about {lob_per_meeting|x1} per meeting, because several of them report the same meeting; '
                  'counted by meetings, it ranks second, not first.',
         numbers=[
             dict(label='Autonomous-vehicle share of lobbying meetings: 2019 → 2024 → 2025', value='{s2019|pct1} → {s2024|pct1} → {s2025|pct1}', source=SRC['edges'] + ' (lobbying_contact); ' + SRC['contacts'] + '#issue'),
             dict(label='Waymo meetings in 2025 (contact reports)', value='{waymo_2025|int} ({waymo_raw_2025|int})', source=SRC['contacts']),
             dict(label='Autonomous-vehicle meetings held by the Teamsters, 2025', value='{teamsters_av_2025|int}', source=SRC['contacts']),
             dict(label='Waymo\'s reported payments to lobbyists, all years on file', value='{pay|mil2}', source=SRC['edges'] + ' (lobbying_payment)'),
         ],
         chart=dict(type='line', title='Autonomous vehicles became a major lobbying topic',
                    subtitle='Share of lobbying about autonomous vehicles or by companies that run them, by year: distinct meetings vs all contact reports',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Share', unit='%'),
                    series=[dict(name='Distinct meetings', values='@CH:share'), dict(name='All contact reports', values='@CH:raw')],
                    highlight='Distinct meetings',
                    note='Source: lobbyist disclosures (DataSF s4ub-8j3t). Autonomous-vehicle meetings: issue text naming autonomous, driverless or self-driving vehicles, robotaxis, AVs or AV companies, '
                         'or any meeting by Waymo, Cruise or Zoox. ' + MEET),
         robustness=dict(verdict='robust', checks=[
             'Counting every contact report: {raw2025|pct} in 2025.',
             'Without Waymo, the share still rose, from {no_waymo_2019|pct1} in 2019 to {no_waymo_2025|pct1} in 2025; {teamsters_av_2025|int} of those 2025 meetings were held by the Teamsters, who sought limits on autonomous vehicles.',
             'The rise came in steps rather than in one year: {s2024|pct1} in 2024 before {s2025|pct1} in 2025.',
             'Ranking depends on the count: in 2025 Waymo is the {waymo_raw_rank_2025|ord} active client by contact reports and the {waymo_rank_2025|ord} active by distinct meetings.'],
             what_could_make_it_wrong='Issue descriptions are free text, so AV meetings that do not name the topic are missed, and meetings by AV companies on other topics are included.'),
         caveats=[MEET, 'Lobbyists for AV companies are registered and may be named; city staff are not.'],
         explore=dict(view='nw-lobby', params={'years': '2016-2025'}, label='See lobbying by client and topic'),
         departments=['MTA', 'AIR'], tags=['autonomous vehicles', 'Waymo', 'lobbying']),

    # 11 -----------------------------------------------------------------------------------------------------------------
    dict(key='outside_sf', id='ballot-money-from-outside-sf', theme='campaign-money',
         title='{ballot_notsf|pct} of ballot-measure money is from outside SF vs {cand_notsf|pct} for candidates; {ballot_ind_notsf|pct} for individuals',
         dek='By donor address, {ballot_SF|pct} of the money given to ballot-measure committees since 2010 came from San Francisco, {ballot_CA|pct} from elsewhere in California and '
             '{ballot_OUT|pct} from outside the state. Candidate committees drew {cand_SF|pct} from the city.',
         why_it_matters='Measures set city taxes and rules. Close to half the money in those campaigns comes from donors with addresses outside the city, including national trade groups '
                        'and companies headquartered elsewhere; even among individual donors, more than a third does. That is legal, and knowing where the money comes from helps voters weigh each '
                        'campaign\'s message. Corporations may give to ballot committees but not to candidate committees (§1.114(b)), so organizational giving accounts for part of the gap.',
         surprise=None,
         numbers=[
             dict(label='Ballot-measure committees: San Francisco / rest of California / outside California', value='{ballot_SF|pct} / {ballot_CA|pct} / {ballot_OUT|pct}', source=SRC['contrib'] + '#city, state, zip5'),
             dict(label='City candidate committees: same split', value='{cand_SF|pct} / {cand_CA|pct} / {cand_OUT|pct}', source=SRC['contrib']),
             dict(label='Individuals\' ballot money from outside the city (aggregate)', value='{ballot_ind_notsf|pct} from outside the city, including {ballot_ind_out|pct} of all individuals\' ballot money from outside California', source=SRC['contrib']),
         ],
         chart=dict(type='stacked', title='Ballot measures draw far more money from outside the city',
                    subtitle='Share of money received, 2010 to Sept. 2026, by donor address',
                    x=dict(label='Committee type', values='@CH:x'), y=dict(label='Share of money', unit='%'),
                    series=[dict(name='San Francisco', values='@CH:SF'), dict(name='Rest of California', values='@CH:CA'), dict(name='Outside California', values='@CH:OUT')],
                    note='Source: SF Ethics Commission campaign filings (DataSF pitq-e56w). San Francisco = city field or a 941 ZIP code. Organizations report a business address.'),
         robustness=dict(verdict='robust', checks=[
             'Individuals only: {ballot_ind_notsf|pct} of individuals\' ballot money came from outside the city.',
             'Excluding the beverage, tobacco and vape companies: {ballot_nostv_notsf|pct} still came from outside the city.',
             'Since 2019 only: {ballot_1926_notsf|pct} of ballot-measure money from outside the city.',
             'Using the ZIP code alone (941xx = San Francisco): {ballot_zip_notsf|pct} of ballot-measure money from outside the city.'],
             what_could_make_it_wrong='Organizations report a business or headquarters address, which may be outside the city even when they operate here; a committee\'s address may be its treasurer\'s office; '
                                      'and money passed between committees carries the sender\'s address. The direction holds under every check; the outside-the-city share ranges from {ballot_1926_notsf|pct} to {ballot_zip_notsf|pct}.'),
         caveats=['No home addresses are shown; only aggregate shares by city and state.', NOMINAL],
         explore=dict(view='nw-concentration', params={}, label='See ballot-measure committees'),
         departments=[], tags=['ballot measures', 'out-of-town money']),

    # 12 -----------------------------------------------------------------------------------------------------------------
    dict(key='waivers', id='behested-ban-waivers', theme='behested',
         title='The Board granted {n|int} waivers of the behested-solicitation ban since 2023, {n2025|int} of them in 2025',
         dek='Since the ban on soliciting behested payments from interested parties took effect on Jan. 24, 2022 (C&GCC §3.620), the Board of Supervisors has granted {n|int} waivers, '
             'the first on {first|date}: {n_breed|int} under Mayor London Breed and {n_lurie|int} since Mayor Daniel Lurie took office in January 2025. {mayor|int} cover the Mayor or the '
             'Mayor\'s Office ({mayor_breed|int} of {n_breed|int} under Mayor Breed, {mayor_lurie|int} of {n_lurie|int} under Mayor Lurie), and {homeless|int} involve homelessness or shelter. '
             'Waivers last at most six months, so continuing programs need renewals, and a new administration starting its own donor-funded initiatives needs new ones.',
         why_it_matters='Waivers let officials ask parties that may have business before them for money for city priorities, such as shelter, the 2023 APEC summit or parks; public appeals '
                        'and donation programs authorized by ordinance are already exempt (§3.620(c)-(f)). The waiver dataset lists what was authorized, not what was raised or from whom. '
                        'Elected officers still report payments of $5,000 or more from one source on state Form 803, but no machine-readable behested-payment records exist after 2023 (see that finding), and '
                        'department heads covered by waivers do not file Form 803, so amounts raised under waivers cannot be totaled from open data.',
         numbers=[
             dict(label='Waivers approved: 2023 / 2025 / 2026 to date', value='{n2023|int} / {n2025|int} / {n2026|int}', source=SRC['waivers'] + '#date_of_waiver_approval'),
             dict(label='Covering the Mayor or the Mayor\'s Office', value='{mayor|int} of {n|int}', source=SRC['waivers'] + '#agency'),
             dict(label='Involving homelessness or shelter', value='{homeless|int}', source=SRC['waivers'] + '#subject'),
         ],
         chart=dict(type='bar', title='Waivers of the behested-solicitation ban jumped in 2025',
                    subtitle='Board of Supervisors waivers of C&GCC §3.620, by approval year; 2026 through the September download',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Waivers', unit='count'),
                    series=[dict(name='Waivers', values='@CH:v')], highlight='2025',
                    note='Source: behested-payment waivers (DataSF 8w9a-q5s8).'),
         robustness=dict(verdict='robust', checks=[
             'Counting by upload date instead of approval date: {upl_2025|int} in 2025.',
             'Collapsing repeated subjects: {n_subjects|int} distinct subjects, so renewals account for {repeats|int} of the {n|int} waivers.',
             'Counting only waivers for new subjects: {new_2025|int} in 2025 against {new_2324|int} in 2023 and 2024 combined.'],
             what_could_make_it_wrong='The dataset may lag Board actions, and a waiver says nothing about how much, if anything, was raised.'),
         caveats=['A waiver is lawful permission granted in public; it is not evidence of any improper payment.'],
         explore=dict(view='nw-behested', params={}, label='See behested payments and waivers'),
         departments=['MYR', 'HOM'], tags=['behested payments', 'waivers', 'solicitation ban']),

    # 13 -----------------------------------------------------------------------------------------------------------------
    dict(key='lobby_clients_donors', id='top-lobbying-clients-also-donors', theme='lobbying',
         title='{t100_n_gave|int} of the 100 most active lobbying clients also gave to SF political committees',
         dek='Among the 100 clients with the most lobbying meetings from 2015 to 2025, {t100_gave|pct} gave to San Francisco committees as organizations over the same years, '
             'against {all_gave|pct} of all {n_clients|int} lobbying clients and {vend_gave|pct} of the {n_vend|int} organizations paid by or contracting with the City. '
             '{t100_beh|pct} also made behested payments at an official\'s request.',
         why_it_matters='The organizations that lobby the City most are also more likely to give to San Francisco committees, so activity across channels overlaps at the top. Overlap shows '
                        'who is active, not that any contribution affected a decision. Lobbying clients are not covered by the lobbyist contribution ban, which applies to registered lobbyists '
                        'themselves (C&GCC §2.115(d)-(e)); corporations, LLCs and LLPs may not give to City candidate committees (§1.114(b)).',
         numbers=[
             dict(label='Share that gave to SF committees, 2015-2025: top 100 lobbying clients / all clients / City vendors and contractors', value='{t100_gave|pct} / {all_gave|pct} / {vend_gave|pct}', source=SRC['edges'] + ' (lobbying_contact, contribution, sponsors, vendor_payment, contract)'),
             dict(label='Top 100 clients\' share of all lobbying meetings', value='{t100_contacts_share|pct}', source=SRC['edges']),
             dict(label='Made behested payments (records through 2023) / held City contracts or payments: top 100 clients vs all lobbying clients', value='{t100_beh|pct} / {t100_vend|pct} vs {all_beh|pct1} / {all_vend|pct}', source=SRC['edges']),
         ],
         chart=dict(type='hbar', title='The most active lobbying clients are far more likely to give',
                    subtitle='Share of organizations that gave to San Francisco political committees, 2015-2025',
                    x=dict(label='Group', values='@CH:x'), y=dict(label='Share that gave', unit='%'),
                    series=[dict(name='Share that gave', values='@CH:v')], highlight='100 most active lobbying clients',
                    note='Sources: lobbyist disclosures (s4ub-8j3t), campaign filings (pitq-e56w), Vendor Payments (n9pm-xkyq), Supplier Contracts (cqi5-hm2d); organizations linked by entity resolution. ' + MEET),
         robustness=dict(verdict='robust', checks=[
             'Top 50 clients: {t50_gave|pct}; top 200: {t200_gave|pct}.',
             'The top 100 gave at {ratio_all|x1} times the rate of all lobbying clients and {ratio|x1} times the rate of all City vendors and contractors, many of which are small suppliers.',
             'The top 100 hold {t100_contacts_share|pct} of all meetings, so the finding describes where most lobbying activity sits.'],
             what_could_make_it_wrong='Organizations are matched across datasets by name; missed matches understate overlap, and affiliates of one company may be merged or split.'),
         caveats=['Organizations with the most business before the City, such as unions, trade groups, large employers and advocacy nonprofits, often also campaign on ballot measures that '
                  'affect them; overlap is expected for that reason alone and is not evidence that giving influenced any decision.',
                  '"Gave" means any contribution by the organization to any San Francisco committee, mostly ballot-measure and general-purpose committees; it does not mean it gave to an official it lobbied.',
                  'Giving by an organization\'s employees is not counted here.'],
         explore=dict(view='nw-graph', params={}, label='Explore the network graph'),
         departments=[], tags=['network', 'lobbying clients', 'donors']),

    # 14 -----------------------------------------------------------------------------------------------------------------
    dict(key='nonprofit_loop', id='nonprofit-giving-visible-only-where-disclosed', theme='nonprofits',
         title='Nonprofit leaders\' giving is visible almost only where boards must be listed: {rate_has|pct} vs {rate_not|pct1}',
         dek='Of {n|int} nonprofits paid $100,000 or more by the City since FY2016, {n_has|int} had a contract approved by the Board of Supervisors or the Mayor, which triggers a '
             'Form SFEC-126(f)4 filing listing the contractor\'s board members and officers (C&GCC §1.126(f)(4)). Among those, {rate_has|pct} had a listed leader who gave to Mayor or '
             'Board of Supervisors committees; among the other {n_not|int}, {rate_not|pct1}, largely because their leaders do not appear in these filings.',
         why_it_matters='Giving by the leaders of city-funded nonprofits to Mayor and Board committees looks common only where disclosure makes it visible. The giving itself is small: '
                        '{giving|mil1} since FY2016, about {giving_per_1m|usd} for every $1 million the City paid these nonprofits. A board member\'s personal giving is generally allowed '
                        'within the $500 limit (§1.114(a)); §1.126(b)-(c) bars it only when it goes to an officer who must approve the nonprofit\'s contract, a candidate for that office, '
                        'or their committees, during the ban window. This finding does not test ban windows; the ban-window finding tests timing for contractor principals as a group.',
         surprise='The largest nonprofits appear to have the most leaders who give, but they are also mostly the ones whose boards are on record; larger boards raise the odds that one member gives, and nonprofit boards often recruit civically active people.',
         numbers=[
             dict(label='Share with a listed leader who gave: approved by the Board or Mayor / not', value='{rate_has|pct} of {n_has|int} / {rate_not|pct1} of {n_not|int}', source=SRC['loop']),
             dict(label='Giving by listed leaders to Mayor or Board committees vs City payments, FY2016 on', value='{giving|mil1} vs {payments|mil1}', source=SRC['loop']),
         ],
         chart=dict(type='bar', title='Giving is visible where boards must be listed',
                    subtitle='Share of city-funded nonprofits ($100,000+ since FY2016) with a leader matched to giving to Mayor or Board of Supervisors committees; without a Board or Mayor approval, leaders are known only from approvals by other City bodies',
                    x=dict(label='Nonprofits', values='@CH:x'), y=dict(label='Share', unit='%'),
                    series=[dict(name='Share with a giving leader', values='@CH:v')],
                    note='Sources: Vendor Payments (n9pm-xkyq), Form SFEC-126(f)4 filings, campaign filings (pitq-e56w); leaders matched to donors by name and employer.'),
         robustness=dict(verdict='robust', checks=[
             'Size drives disclosure: {q4_has|pct} of the largest quarter by City payments had such an approval, against {q1_has|pct} of the smallest.',
             'Among nonprofits with approvals, the largest quarter shows a giving leader {share_gave_among_has_q4|pct} of the time and the rest {share_gave_among_has_q13|pct}.',
             'Nonprofits with a giving leader received {fund_share_gave|pct} of the funding, close to the {pay_share_has|pct} that went to nonprofits whose leaders are listed at all.'],
             what_could_make_it_wrong='Leaders are matched to donors by name and employer; board members of several organizations count for each, and giving before a person joined a board is included.'),
         caveats=['Leaders are not named here; many are private individuals serving as unpaid board members.', NOMINAL],
         explore=dict(view='nw-loop', params={}, label='See the nonprofit loop'),
         departments=[], tags=['nonprofits', 'selection effect', 'disclosure']),

    # 15 -----------------------------------------------------------------------------------------------------------------
    dict(key='behested_base_rate', id='behested-payors-pending-business', theme='behested',
         title='{obs|pct} of behested payors had business before the official\'s body; comparable firms: {base_active|pct}',
         dek='For {n|int} behested payments on file (2015 to 2023), {obs|pct} of payors lobbied the requesting official or the official\'s body, or had a contract approved by it, '
             'within 12 months before or after the payment. A random organization that was itself active with the City shows such business {base_active|pct} of the time; '
             'a random organization from the whole pool, {base_all|pct}.',
         why_it_matters='Solicitations from parties with matters pending are what the 2022 ban targets (C&GCC §3.620(a)). Before the ban, payors were no more likely than other active '
                        'organizations to have business pending, though they were {ratio_all|x1} times as likely as organizations in general. Which comparison is right depends on who could plausibly be asked.',
         numbers=[
             dict(label='Payors with business before the official\'s body within 12 months', value='{obs|pct} of {n|int} payments ({dollar_share|pct} of dollars)', source=SRC['bpb']),
             dict(label='Base rates: random active organization / random organization from the pool', value='{base_active|pct} / {base_all|pct}', source=SRC['rt2'] + '#rederivation.behested_pending_business'),
             dict(label='Payors that lobbied the requesting official directly', value='{same_official|pct}', source=SRC['bpb']),
         ],
         chart=dict(type='bar', title='Between the two base rates',
                    subtitle='Share with lobbying or a contract approval involving the official\'s body within 12 months (before or after)',
                    x=dict(label='Group', values='@CH:x'), y=dict(label='Share', unit='%'),
                    series=[dict(name='Share with business pending', values='@CH:v')], highlight='Behested payors',
                    note='Sources: Form 803 and SFEC-3610(b) behested payments; lobbyist disclosures; Form SFEC-126(f)4. Base rates from 60 random organizations per payment (red-team pass 2).'),
         robustness=dict(verdict='fragile', checks=[
             'Did not hold against all organizations: payors were {ratio_all|x1} times as likely as a random organization from the whole pool.',
             'Form 803 era {obs_803|pct}; city Form SFEC-3610(b) era {obs_3610|pct}.',
             'By dollars rather than payments: {dollar_share|pct}.',
             'Payors that contributed to the official\'s own committees within 12 months: {contrib|pct1}.'],
             what_could_make_it_wrong='The window is two-sided, so business after the payment counts too; lobbying and contract approvals cover only part of "interested party" status '
                                      '(permits and enforcement matters are not in the data).'),
         caveats=[TIMING, 'Payments before Jan. 24, 2022 were not subject to the solicitation ban.'],
         explore=dict(view='nw-behested', params={}, label='See behested payments and pending business'),
         departments=[], tags=['behested payments', 'base rate', 'interested parties']),

    # 16 -----------------------------------------------------------------------------------------------------------------
    dict(key='enforcement', id='ethics-enforcement-rare', theme='transparency',
         title='Ethics enforcement: {n|int} public cases since {first|yr}, {n126|int} under the contractor ban',
         dek='The Ethics Commission\'s public enforcement record lists {n|int} resolved cases from {first|yr} to 2026 with {pen|mil1} in penalties (median {med|usd}). '
             '{n126|int} involved the contractor contribution ban (§1.126), {nlob|int} lobbyist rules and {nbeh|int} the behested-payment rules. Most concern reporting and filing.',
         why_it_matters='The dashboard\'s review flags are prompts to check, not violations; many may be explained by facts not in the data, such as a donor who is not in fact an affiliate, '
                        'a contract below the threshold or an officer who did not approve it. Under §1.126(e) a committee that receives a barred contribution must pay it to the City, and '
                        'resolving a matter that way need not produce a public enforcement case. Contractor principals gave inside ban windows no more often than chance would predict (see the ban-window finding). '
                        'Most public cases concern reporting and filing rules rather than the contribution bans.',
         numbers=[
             dict(label='Public enforcement cases and penalties', value='{n|int} cases, {pen|mil1}; median {med|usd}, largest {pen_max|usd}', source=SRC['enf']),
             dict(label='Contractor-ban cases (§1.126) and their penalties', value='{n126|int}, {pen126|usd}', source=SRC['enf'] + '#code_sections'),
             dict(label='Contributions this dashboard flags as appearing to warrant review under C&GCC §1.126(b)-(c) (name-matched affiliate of a contractor; recipient an officer who approved the contract or a candidate for that office; date inside the ban window then in force). Not a count of violations and not comparable to case counts', value='{n_review|int}', source=SRC['ban_site']),
         ],
         chart=dict(type='hbar', title='Few public cases involve the contribution bans',
                    subtitle='Ethics Commission public enforcement cases, by rule, 2003-2026',
                    x=dict(label='Rule', values='@CH:x'), y=dict(label='Cases', unit='count'),
                    series=[dict(name='Cases', values='@CH:v')], highlight='Contractor contribution ban (§1.126)',
                    note='Source: Ethics Commission enforcement summaries (DataSF). Grouped by the code sections and category listed for each case.'),
         robustness=dict(verdict='robust', checks=[
             'Since 2019 about {n_1926|int} cases through Sept. 2026 (roughly {per_year_1926|x1} a year), against {n_0318|int} in 2003-2018 (about {per_year_0318|x1} a year).',
             'Campaign-finance cases are {n_camp|int} of {n|int}, mostly reporting and filing rules.',
             'Cases citing a lobbyist code section (§2.1xx) number {nlob_code|int}, against {nlob|int} in the Lobbyist category.'],
             what_could_make_it_wrong='The enforcement dataset may omit matters closed without a public stipulation, warning letters and cases handled by other agencies such as the FPPC, the District '
                                      'Attorney or the City Attorney; some cases list several rules. The review flags rely on name matching, which can produce false matches.'),
         caveats=['Respondents are not named here.', 'A flag in this dashboard is not an allegation.', 'Penalties are nominal dollars.'],
         explore=dict(view='nw-ban', params={}, label='See the records flagged for review'),
         departments=['ETH'], tags=['enforcement', 'Ethics Commission', 'base rate']),

    # 17 -----------------------------------------------------------------------------------------------------------------
    dict(key='maxed_checks', id='maxed-out-checks', theme='campaign-money',
         title='Contributions at the $500 limit supply {max_share|pct} of what individuals give City candidates',
         dek='From 2010 to Sept. 2026, contributions of exactly the $500 limit (C&GCC §1.114(a)) were {max_n_share|pct} of individual contributions to City candidate committees but '
             '{max_share|pct} of the dollars. Contributions under $100 supplied {u100|pct1}.',
         why_it_matters='The $500 limit keeps any one contribution small, yet most individual money to City candidates arrives in contributions at the limit; contributions under $100 are '
                        '{u100_n_share|pct} of all contributions and supply {u100|pct1} of the dollars. That describes who funds campaigns, not any wrongdoing.',
         numbers=[
             dict(label='Share of individual dollars in $500 contributions (share of contributions)', value='{max_share|pct} ({max_n_share|pct})', source=SRC['contrib']),
             dict(label='Share of dollars under $100 (share of contributions)', value='{u100|pct1} ({u100_n_share|pct})', source=SRC['contrib']),
             dict(label='Individual donations to City candidates, 2010 to Sept. 2026', value='{total|mil1} (individuals only; candidates\' own money excluded)', source=SRC['contrib']),
         ],
         chart=dict(type='bar', title='Most individual candidate money arrives at the limit',
                    subtitle='Share of individuals\' dollars to City candidate committees by contribution size, 2010 to Sept. 2026 (candidates\' own money excluded)',
                    x=dict(label='Contribution size', values='@CH:x'), y=dict(label='Share of dollars', unit='%'),
                    series=[dict(name='Share of dollars', values='@CH:v')], highlight='Exactly $500',
                    note='Source: SF Ethics Commission campaign filings (DataSF pitq-e56w), Schedule A and C, positive amounts.'),
         robustness=dict(verdict='robust', checks=[
             'Every year from 2010 to 2026 the $500 share was between {min_y|pct} and {max_y|pct}; in 2024, {y2024|pct}.',
             'San Francisco donors only: {sf_max|pct}.',
             'Contributions of $250 or more supply {ge250|pct} of the dollars.'],
             what_could_make_it_wrong='A donor who gives $500 in two installments is counted in lower bands, which understates the share at the limit; '
                                      'contributions above $500 ({over|pct1} of dollars) are shown as reported; they may reflect gifts for separate elections, reporting errors or later refunds, and are not evidence of violations.'),
         caveats=['Individuals appear only in aggregate.', 'Public matching funds paid to eligible candidates are not included; because they match only the first part of each qualifying San Francisco resident\'s contribution, counting them would give more weight to small amounts.', NOMINAL],
         explore=dict(view='nw-concentration', params={}, label='See candidate committees and their donors'),
         departments=[], tags=['contribution limits', 'small donors']),
]


# Published order (rank = importance x robustness; interleaved so the set does not read as one argument). The behested
# pending-business candidate was dropped after the Opus fairness review (see data/redteam/insights_screening.json).
ORDER = ['ie_vs_donors', 'lobbyist_ban', 'ballot_sectors', 'contractor_ban', 'outside_concentration', 'behested_vanished', 'pension_lobbying',
         'form_1145', 'staff_targets', 'av_lobbying', 'nonprofit_loop', 'waivers', 'outside_sf', 'lobby_clients_donors', 'enforcement', 'maxed_checks']
DROPPED = [t for t in INSIGHTS if t['key'] not in ORDER]
INSIGHTS = [next(t for t in INSIGHTS if t['key'] == k) for k in ORDER]
