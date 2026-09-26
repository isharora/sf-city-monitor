"""Text and chart templates for the audits insights page, shared by build_insights.py and verify_insights.py.

Every number shown to readers is a placeholder {key|fmt} filled from a computed value (V) or an @CH:key chart array,
so verify_insights.py can recompute each one independently. Quotes are placeholders too: {Q:id} renders the verbatim
text registered in QUOTES and {C:id} renders its citation ("CON-3624 p.4"); verify_insights.py checks every quote
word for word against the PDF text of that page. Template text itself may contain only years, report ids and a few
fixed tokens (checked by build and verify).
"""
import re

AS_OF = '2026-09-26'
MINUS = '−'

INTRO = ('{n_ins|word} findings about what happens to the recommendations of San Francisco\'s three watchdogs: the Controller\'s City Services '
         'Auditor, the Board of Supervisors\' Budget and Legislative Analyst and the Civil Grand Jury. They were chosen from about thirty '
         'candidates tested against {n_rows|int} recommendation records, the follow-up reports and the report PDFs. Each was tested with at least three '
         'robustness checks; {n_fragile|word_l} are marked fragile because a check did not hold, and the card says which. Some groupings (kinds of '
         'recommendation, reasons for saying no, repeat findings) were assigned by an AI model (Claude) and spot-checked by an analyst. A separate script '
         'recomputes every number from the source tables and checks every quotation against the PDF. '
         'A status here is the last one recorded in a public follow-up, mostly reported by the departments themselves. A "will not be implemented" '
         'answer (called a refusal below, for short) is often a legitimate policy, legal or cost decision, and the cards say which reasons were given; '
         'the dashboard behind each card lets you check the underlying records.')
# (the intro is rendered like every other template; verify_insights.py recomputes n_ins and n_rows)


def _signed(v, s):
    return ('+' if v > 0 else (MINUS if v < 0 else '')) + s


FMT = {
    'int': lambda v: f'{round(round(v, 6)):,}',
    'yr': lambda v: f'{int(v)}',
    'pct': lambda v: f'{v * 100:.0f}%',
    'pct1': lambda v: f'{v * 100:.1f}%',
    'apct': lambda v: f'{abs(v) * 100:.0f}%',
    'spct': lambda v: _signed(round(v * 100), f'{abs(v) * 100:.0f}%'),
    'f0': lambda v: f'{v:,.0f}',
    'f1': lambda v: f'{v:.1f}',
    'x1': lambda v: f'{v:.1f}',
    'x0': lambda v: f'{v:.0f}',
    'mil': lambda v: f'${v / 1e6:,.0f} million',
    'mil1': lambda v: f'${v / 1e6:,.1f} million',
    'bil1': lambda v: f'${v / 1e9:,.1f} billion',
    'str': lambda v: f'{v}',
    'word_l': lambda v: ['no', 'one', 'two', 'three', 'four', 'five', 'six'][int(v)],
    'word': lambda v: ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen',
                       'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen', 'Twenty', 'Twenty-one', 'Twenty-two'][int(v)],
}
PH = re.compile(r'\{(\w+)\|(\w+)\}')
QPH = re.compile(r'\{([QC]):(\w+)\}')

# ------------------------------------------------------------------------------------------------ verbatim quotes
# Each quote is copied from the PDF text of the cited page (data/text/<doc>.json); verify_insights.py re-checks it.
QUOTES = {
    'csa_self': dict(doc='CON-1772', page=5, text='Although departments report having implemented 96 percent of the 689 recommendations issued in that period'),
    'csa_verify': dict(doc='CON-3559', page=2, text='Verified the status of the recommendations that SFMTA had reported as implemented.'),
    'bos_auth': dict(doc='CGJS-2004-05', page=1, text='The Board supports the recommendation of the Civil Grand Jury, but does not have the operational authority to implement the recommendations.'),
    'awss_f4': dict(doc='CGJ-2018-2019-a4a61434', page=44, text='does not cover large parts of Supervisorial Districts 1, 4, 7 and 11, roughly one-third of the City’s developed area'),
    'awss_r2': dict(doc='CGJS-2018-19', page=1, text='Committing to entirely funding a single program out of context and without regard for the trade-offs of that commitment would be out of step with the City’s longstanding and highly regarded capital planning process'),
    'awss_r4': dict(doc='CGJS-2018-19', page=1, text='Due to fiscal uncertainty, the City is unable to commit to purchasing 20 new PWSS hose tenders by June 2021.'),
    'civ_2024': dict(doc='BLA-48c11f71', page=109, text='all plans to move forward with civilianization stopped following the start of the COVID-19 pandemic and have not resumed'),
    'civ_2024b': dict(doc='BLA-48c11f71', page=109, text='SFPD was unable to share details on any positions that have been civilianized since FY 2019-20.'),
    'civ_resp': dict(doc='BLA-48c11f71', page=120, text='hiring civilians has little-to-no impact on sworn overtime costs'),
    'civ_2018': dict(doc='BLA-165267bf', page=91, text='SFPD has identified 25 positions for immediate civilianization as reflected in the FY 18‐ 19 Mayor\'s budget proposal.'),
    'civ_2019': dict(doc='CON-2711', page=2, text='Since FY12-13, the SFPD has successfully civilianized 60 positions recommended in a variety of prior reports'),
    'ce_1996': dict(doc='CGJ-1995-1996-52783143', page=[2, 3], text='Performance standards for contractors on city projects should be established and a formal review process instituted for each contractor and subcontractor.'),
    'ce_2016': dict(doc='CGJS-2014-15', page=1, text='The ordinance requires Chapter 6 departments to document, evaluate, and report the performance of all contractors awarded construction contracts under Chapter 6'),
    'ce_2024': dict(doc='BLA-f9cb966a', page=10, text='are not using the City’s contractor performance and evaluation database, as required by section 6.26 of the City’s Administrative Code'),
    'ce_mayor': dict(doc='CGJS-2021-22', page=2, text='The Department of Public Works, similar to all City Departments, faces budget constraints and therefore cannot currently support adding a Manager position in the Department.'),
    'air_2019': dict(doc='CON-2751', page=10, text='Develop procedures to ensure receipt of the required reports from the Tenant by the due date.'),
    'bla_2018': dict(doc='BLA-48c11f71', page=99, text='2018 BLA Audit Recommendations Were Not Implemented, Including Cost-Effectiveness Analysis'),
    'bla_2018b': dict(doc='BLA-48c11f71', page=99, text='SFPD partially implemented two of these recommendations.'),
    'pi_table': dict(doc='CON-3624', page=3, text='Total 91 79 7 2 3 2'),
    'pi_closed': dict(doc='CON-3624', page=4, text='Closed recommendations indicate that the response provided by the departments described sufficient action to implement the recommendation or an acceptable alternative or a change occurred to make the recommendation no longer applicable or feasible.'),
    'pi_ig': dict(doc='CON-3624', page=4, text='The new Inspector General may evaluate the closed and open recommendations for follow-up to confirm the department’s reported implementation status.'),
    'dph_reason': dict(doc='CON-3533', page=2, text='The department is working with other city agencies and stakeholders to manage the City Option program, which has been implementing significant policy and program changes.'),
    'puc_1567': dict(doc='CON-3047', page=7, text='Except for SFPUC informing us that support was no longer available for $156.7 million of labor, benefits and overhead expenses incurred between June 1, 2003, and June 30, 2008, we found no instances of expenditures that were not allowable under the bond resolutions'),
    'recology_2021': dict(doc='CON-2951', page=6, text='the City Attorney announced a more than $100 million refuse rate settlement with Recology'),
    'co_total': dict(doc='BLA-8208fb13', page=35, text='Total 297 1,003 $2,438,461,586 $186,785,390 8%'),
    'awss_eser': dict(doc='CGJS-2018-19', page=2, text='Now that the ESER 2020 bond has passed, the City can begin to plan with greater specificity.'),
    'ce_r3': dict(doc='CGJS-2021-22', page=2, text='the Mayor require all Chapter 6 departments to begin submitting evaluations into the database'),
    'ce_2026': dict(doc='BLA-8208fb13', page=7, text='Increase use of Best Value procurement and prequalification of bidders to avoid underperforming contractors.'),
    'pi_wn': dict(doc='CON-3624', page=19, text='OCA and the City Administrator\'s Government Operations division considered the recommended rule change and are instead pursuing a solution leveraging existing reporting systems'),
    'awss_r8': dict(doc='CGJS-2018-19', page=1, text='Consideration of a standalone bond is underway in the plan development process for the FY2024-2033 Capital Plan.'),
    'civ_sworn': dict(doc='BLA-165267bf', page=91, text='must be filled by officers, rather than non\u2010sworn personnel, as their law enforcement expertise is vital to the functions they are performing'),
    'cgj_750': dict(doc='CGJ-2016-2017-d947b9ce', page=21, text='the Unfunded Liability was increased by $750 million'),
    'recology': dict(doc='CON-3093', page=3, text='Recology agreed to pay $101 million in restitution, interest, and penalties to ratepayers'),
}


def render_str(s, V):
    def rep(m):
        k, f = m.group(1), m.group(2)
        if k not in V:
            raise KeyError(f'missing value {k}')
        return FMT[f](V[k])

    def qrep(m):
        q = QUOTES[m.group(2)]
        if m.group(1) == 'Q':
            return q['text']
        p = q['page']
        return f"{q['doc']} pp.{p[0]}–{p[-1]}" if isinstance(p, list) else f"{q['doc']} p.{p}"
    return PH.sub(rep, QPH.sub(qrep, s))


def render(obj, V, CH):
    if isinstance(obj, str):
        if obj.startswith('@CH:'):
            return [None if v is None else (round(float(v), 2) if isinstance(v, float) else v) for v in CH[obj[4:]]]
        return render_str(obj, V)
    if isinstance(obj, list):
        return [render(o, V, CH) for o in obj]
    if isinstance(obj, dict):
        return {k: render(v, V, CH) for k, v in obj.items()}
    return obj


ALLOWED_DIGIT_TOKENS = [r'FY\d{4}-\d{2}', r'FY\d{4}–\d{2}', r'FY\d{4}', r'\b(19|20)\d{2}[–-]\d{2}\b', r'Claude (Sonnet|Opus) 5(\.5)?',
                        r'Admin\. Code 2\.10', r'\bC-\d{4}\b', r'story 4\.\d', r'08a_verify_dollars\.py', r'June 30', r'September \d{1,2}, 2026', r'[Rr]ed team 2', r'\b(19|20)\d{2}\b', r'\b(CON|BLA|CGJ|CGJS)-[\w-]+', r'\bR\d+\b', r'COVID-19',
                        r'Penal Code 933\.05', r'section 6\.26', r'Chapter 6', r'\b1906\b', r'= 100\b']

THEMES = ['trends', 'verification', 'refusals', 'follow-through', 'repeat-findings', 'coverage', 'dollars', 'safety']
REC = 'audits/data/site/recs/recs_*.json'
SRC = {
    'recs': REC, 'reports': 'audits/data/site/reports/reports.json', 'clusters': 'audits/data/site/repeats/clusters.json',
    'reasons': 'audits/data/redteam/reasons.json (Claude Sonnet 5, one primary reason per refusal)',
    'actions': 'audits/data/insights_work/rec_action_types.json (Claude Sonnet 5, one action type per recommendation)',
    'field': 'audits/data/insights_work/field_followups.json (Claude Opus 5.5 reading of each field follow-up memo)',
    'status_items': 'audits/data/work/status_items.json',
    'spend': 'performance/data/site/spending/cells.json (DataSF bpnb-jwfb actuals, nominal)',
}
CGJ_NOTE = ('Grand Jury rows are one per recommendation and required respondent; statuses are the latest column of the Controller\'s '
            'tracking documents (Admin. Code 2.10), which copy the respondents\' own answers.')
CLUSTER_NOTE = ('Repeat clusters were grouped by an AI model (Claude Opus 5.5) and checked on samples: a second model agreed on {judge|pct} of {judge_n|int} sampled pairs, '
                'and an analyst agreed on {hand_ok|int} of {hand_n|int}.')
SELF_NOTE = 'Statuses are the last recorded in a public follow-up; most are reported by the departments themselves.'

INSIGHTS = [
    # 1 ---------------------------------------------------------------------------------------------------------------
    dict(key='csa_output', id='controller-recommendations-fell-three-quarters', theme='trends',
         title='Controller auditors issued a quarter as many recommendations in FY2021–25 as in FY2011–15',
         dek='Recommendations in the City Services Auditor\'s follow-up program averaged {ours_a|f0} a year in FY2011–FY2015 and {ours_b|f0} in FY2021–FY2025 '
             '({ours_chg|spct}). The Controller\'s own annual counts show the same drop: {csa_a|f0} a year, then {csa_b|f0}.',
         why_it_matters='Fewer recommendations is not necessarily less oversight. The decline began around FY2016; assessments, Public Integrity reviews and, after 2020, '
                        'emergency work produce fewer formal recommendations, and auditors may now write broader ones. The drop does mean the Controller\'s follow-up '
                        'program now tracks a much smaller set of recommendations than a decade ago, which matters when reading its implementation rates.',
         surprise='Audits of Airport and Port tenants, once about {ap_a|x0} reports a year, have almost disappeared ({ap_b|x1} a year), but the drop holds even without them ({nap_chg|spct}).',
         numbers=[
             dict(label='CSA recommendations in follow-up scope per year, FY2011–FY2015 → FY2021–FY2025 (our extraction)', value='{ours_a|f0} → {ours_b|f0} ({ours_chg|spct})', source=REC + '#source=csa, in_csa_followup_scope, fiscal year of date_issued'),
             dict(label='Same, from the Controller\'s own cumulative counts', value='{csa_a|f0} → {csa_b|f0} a year ({csa_chg|spct})', source='CON-2495 p.3 ({csa_n15|int} issued FY2011–FY2015); CON-2886 p.2 ({csa_n20|int} through FY2020); CON-3533 p.2 ({csa_n25|int} through FY2025)'),
             dict(label='CSA reports with at least one recommendation, per year', value='{rep_a|x1} → {rep_b|x1} ({rep_chg|spct})', source=SRC['reports'] + '#source=csa'),
             dict(label='Airport and Port reports per year (mostly tenant and lease audits)', value='{ap_a|x1} → {ap_b|x1}', source=SRC['reports'] + '#depts contains AIR or PRT'),
         ],
         chart=dict(type='bar', title='Recommendations the Controller\'s auditors track, by fiscal year issued',
                    subtitle='CSA audit and assessment recommendations in its follow-up program (issued from July 2010), count per fiscal year',
                    x=dict(label='Fiscal year', values='@CH:x'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Recommendations', values='@CH:scope')], highlight='2025',
                    annotations=[dict(x=2020, label='COVID-19; corruption cases')],
                    note='Source: CSA reports and follow-up reports, extracted by this project; the Controller\'s own annual counts (CON-2495, CON-2886, CON-3533) agree. '
                         'Fiscal years run July to June. City Performance, Whistleblower and Public Integrity reports are outside the follow-up program.'),
         robustness=dict(verdict='robust', checks=[
             'The Controller\'s own cumulative counts give the same drop: {csa_a|f0} a year in FY2011–FY2015, {csa_b|f0} in FY2021–FY2025 ({csa_chg|spct}).',
             'Counting every CSA recommendation, including City Performance and Public Integrity reports: {all_a|f0} → {all_b|f0} a year ({all_chg|spct}).',
             'Excluding Airport and Port reports, which include many tenant audits: {nap_a|f0} → {nap_b|f0} a year ({nap_chg|spct}).',
             'Counting reports instead of recommendations: {rep_a|x1} → {rep_b|x1} reports a year ({rep_chg|spct}).',
             'Held despite a rebound: FY2026 rose to {fy2026|int} from {fy2025|int} in FY2025; the five-year averages smooth single years.'],
             what_could_make_it_wrong='Recommendation counts depend on how auditors split their advice; one recommendation today may cover what three did in 2012. '
                                      'Our fiscal-year counts differ from the Controller\'s in some years because we split lettered sub-parts and date reports by issue date.'),
         caveats=['Counts recommendations, not audit hours or findings.', 'FY2026 (July 2025 to June 2026) had {fy2026|int} recommendations, above the FY2021–25 average; a single year is not a trend.'],
         explore=dict(view='au-overview', params={'source': 'csa', 'years': '2010-2026'}, label='See the Controller\'s recommendations by year'),
         departments=['CON'], tags=['audit volume', 'Controller', 'oversight capacity']),

    # 2 ---------------------------------------------------------------------------------------------------------------
    dict(key='csa_closure', id='controller-implemented-rate-rests-on-report-closure', theme='verification',
         title='{share_closure|pct} of CSA "implemented" statuses are report-level: a closed report or absence from a list',
         dek='Of {n_known|int} CSA recommendations with a recorded status, {rate|pct} are implemented. But {n_closed|int} of the {n_impl|int} "implemented" '
             'come from a follow-up that closed the whole report and {n_inferred|int} from a report\'s absence from the two-year open list. '
             'Where the status rests on evidence about the recommendation itself, {rate_rl|pct} are implemented (n = {n_rl|int}); that includes follow-up summaries that tend to list open items, and auditor field checks alone give {rate_ff|pct}.',
         why_it_matters='The Controller\'s first annual report put it plainly: "{Q:csa_self}" ({C:csa_self}). When auditors went into the field '
                        '({memo_docs|int} memos, {memo_n|int} recommendations), they confirmed {memo_impl|pct} as implemented, found {memo_notdone|pct} partial or '
                        'not done and closed {memo_na|pct} as no longer applicable. Field checks are targeted, so this is not a random test of self-reports, '
                        'but it adds auditor-verified evidence to a rate the Controller itself describes as department-reported.',
         surprise='In our data, closing a whole report records every recommendation in it as implemented, including {dis_impl_closure|int} of the {dis_impl|int} '
                  'disagreed-with recommendations recorded implemented. CSA may close a report when an item is resolved another way, so the label can reflect '
                  'our coding rather than the Controller\'s judgment of each item.',
         numbers=[
             dict(label='CSA recommendations implemented, of those with a status', value='{n_impl|int} of {n_known|int} ({rate|pct})', source=REC + '#source=csa, status'),
             dict(label='Share of "implemented" from whole-report closure or absence from the two-year list', value='{share_closure|pct}', source=REC + '#status_basis'),
             dict(label='Implemented, when the status is about the recommendation itself', value='{rate_rl|pct} of {n_rl|int}', source=REC + '#status_basis not report-level'),
             dict(label='Field follow-up memos: implemented / partial or not / no longer applicable', value='{memo_impl|pct} / {memo_notdone|pct} / {memo_na|pct} of {memo_n|int}', source=SRC['status_items'] + '#status_doc_type=csa_field_followup'),
             dict(label='Same memos read independently by Claude Opus 5.5', value='{opus_impl|pct} implemented ({opus_docs|int} memos with totals)', source=SRC['field']),
         ],
         chart=dict(type='hbar', title='Share recorded implemented depends on the kind of evidence',
                    subtitle='CSA recommendations with a recorded status, by the basis of that status; % implemented (n at right)',
                    x=dict(label='Basis of status', values='@CH:cats'), y=dict(label='Implemented (%)', unit='%'),
                    series=[dict(name='Implemented', values='@CH:vals', n='@CH:n')], highlight='Auditor field follow-up',
                    note='Report closure and absence from the Controller\'s list of recommendations open over two years mark every recommendation of a report implemented by construction (the second is our inference). '
                         'Field follow-ups are memos in which auditors check documents. Follow-up summaries may list mainly items still open, which lowers their rate. '
                         'The {memo_impl|pct} field figure counts all memo items; {rate_ff|pct} counts the {n_ff|int} linked to a specific recommendation. ' + SELF_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Field follow-ups alone, linked to recommendations: {rate_ff|pct} implemented (n = {n_ff|int}); only {share_verified|pct} of all "implemented" statuses rest on one.',
             'An independent Claude Opus reading of the memos gives {opus_impl|pct} implemented across {opus_docs|int} memos, against {memo_impl|pct} from the pipeline\'s extraction.',
             'Self-reports held where tested: in {sr_docs|int} memos that checked only what the department had reported implemented, auditors confirmed {sr_impl|int} of {sr_n|int} and found {sr_notdone|int} undone.',
             'Report closure applies one status to every item: {dis_impl_closure|int} of {dis_impl|int} "implemented" recommendations the department had disagreed with got that status with their report, which may reflect resolution by another route rather than implementation as written.'],
             what_could_make_it_wrong='Field follow-ups are not a random sample: auditors may pick audits with doubtful progress, which would make the field rate too low. '
                                      'Report closure can be correct; CSA closes a report when every item is resolved, including by acceptable alternatives.'),
         caveats=['"No longer applicable" closures count as not implemented in the memo shares.', 'Covers CSA audits issued from July 2010.'],
         explore=dict(view='au-status', params={'source': 'csa'}, label='See the Controller\'s recommendations by status'),
         departments=['CON'], tags=['self-reporting', 'verification', 'follow-up']),
]

INSIGHTS += [
    # 3 ---------------------------------------------------------------------------------------------------------------
    dict(key='action_types', id='grand-jury-law-changes-rarely-done', theme='refusals',
         title='Grand Jury asks for law or governance changes: {r_law_or_governance_change|pct} recorded done, vs {r_control_or_procedure|pct} for procedure fixes',
         dek='Of {n|int} Grand Jury recommendation-respondent pairs with a recorded status, those asking for an ordinance, charter change or restructuring were recorded implemented '
             '{r_law_or_governance_change|pct} of the time and answered "will not be implemented" {law_wn|pct}; asks to fix a control or procedure were recorded implemented {r_control_or_procedure|pct}, '
             'and training {r_training|pct}. Asks that need new money fared about like the rest ({mon_y|pct} vs {mon_n|pct}).',
         why_it_matters='Changing a law or who holds authority is for the Board of Supervisors, the Mayor or the voters, not a department. A department\'s refusal here is often a '
                        'statement about who decides, and a refusal by the Board or the Mayor is a policy choice within their authority, not a failure to act. Operational asks that a department can act on alone are recorded implemented about twice as often.',
         surprise='Recommendations flagged as needing new spending were recorded implemented nearly as often as the rest. And what the jury asks for explains little of its gap '
                  'with the Controller: reweighted to the Controller\'s mix of asks, the jury\'s rate would be {reweighted|pct}, barely above its actual {rate|pct} and still well below '
                  'the Controller\'s figures, though the two are recorded differently (respondents\' own answers vs CSA follow-up).',
         numbers=[
             dict(label='Implemented: change a law, charter or governance (n = {n_law_or_governance_change|int})', value='{r_law_or_governance_change|pct}', source=SRC['actions'] + '; ' + REC + '#source=cgj, status'),
             dict(label='Implemented: fix a control or procedure (n = {n_control_or_procedure|int})', value='{r_control_or_procedure|pct}', source=SRC['actions'] + '; ' + REC + '#source=cgj, status'),
             dict(label='Implemented: needs new money / does not (model flag; n = {n_mon|int} flagged)', value='{mon_y|pct} / {mon_n|pct}', source=SRC['actions'] + '#new_money'),
             dict(label='Share of asks that change a law or governance: Grand Jury vs Controller', value='{cgj_law_share|pct} vs {csa_law_share|pct}', source=SRC['actions']),
             dict(label='Grand Jury rate reweighted to the Controller\'s mix of asks', value='{reweighted|pct} (actual {rate|pct})', source=SRC['actions'] + '; ' + REC),
         ],
         chart=dict(type='hbar', title='Asks to change a law or governance are least often recorded implemented',
                    subtitle='Grand Jury recommendations by the kind of action asked for; % of recommendation-respondent pairs recorded implemented (n at right)',
                    x=dict(label='Kind of action', values='@CH:cats'), y=dict(label='Implemented (%)', unit='%'),
                    series=[dict(name='Implemented', values='@CH:vals', n='@CH:n')], highlight='Change a law, charter or governance',
                    note='Action type assigned by Claude Sonnet 5 from each recommendation\'s text (one primary type; rare types omitted). ' + CGJ_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Excluding the Board of Supervisors and the Mayor, who receive {bm_law_share|pct} of law-change asks: {ex_law|pct} implemented vs {ex_ctl|pct} for control fixes.',
             'Only classifications with confidence of at least {hc_min|f1} (n = {hc_n|int}): {hc_law|pct} vs {hc_rest|pct} for all other kinds.',
             'Using the separate "needs legislation" flag instead of the action type: {leg_y|pct} vs {leg_n|pct} implemented (n = {n_leg|int} flagged).',
             'An analyst read {hand_n|int} random classifications (law change, funding and control): {hand_ok|int} plausible, the rest debatable, none wrong.'],
             what_could_make_it_wrong='Action types are model judgments from short recommendation texts, and many recommendations mix kinds. The status is the respondent\'s own '
                                      'answer, so a law that passed later for other reasons may be recorded as not implemented.'),
         caveats=['One row per recommendation and respondent; a recommendation sent to five respondents counts five times.', 'Tracking covers jury terms 2003-04 to 2024-25.'],
         explore=dict(view='au-status', params={'source': 'cgj'}, label='See Grand Jury recommendations by status'),
         departments=['BOS', 'MYR'], tags=['Civil Grand Jury', 'legislation', 'kind of recommendation']),

    # 4 ---------------------------------------------------------------------------------------------------------------
    dict(key='further_analysis', id='further-analysis-ends-either-way', theme='follow-through',
         title='"Requires further analysis" ended about as often in "will not" as in "implemented"',
         dek='Of {fa_n|int} Grand Jury answers of "requires further analysis" that the Controller later tracked, {fa_wn|int} ended as "will not be implemented" and '
             '{fa_impl|int} as implemented; {fa_open|int} are still open or in progress. Answers of "will be implemented" were kept {wb_impl|int} times out of {wb_n|int}.',
         why_it_matters='Penal Code 933.05 lets a respondent defer a Grand Jury recommendation for analysis, and a careful look can legitimately end in a reasoned no. '
                        'The record shows these answers ended in either outcome at about the same rate, so a deferral did not predict the result either way; '
                        '"will be implemented" answers, by contrast, were mostly recorded implemented.',
         surprise='A deferral was not a likely yes: counted by respondent, {fa_wn_share|pct} ended "will not" and {fa_impl_share|pct} implemented; counted once per recommendation, the two outcomes tie.',
         numbers=[
             dict(label='"Requires further analysis" → will not / implemented', value='{fa_wn|int} / {fa_impl|int} of {fa_n|int}', source=REC + '#source=cgj, cgj_response, status_basis=cgj_status_tracker'),
             dict(label='"Will be implemented" → implemented / will not', value='{wb_impl|int} / {wb_wn|int} of {wb_n|int}', source=REC + '#cgj_response=will_be_implemented'),
             dict(label='"Will be implemented" later turned to "will not", excluding the Board of Supervisors', value='{wbx_wn|int} of {wbx_n|int}', source=REC + '#dept!=BOS'),
         ],
         chart=dict(type='stacked', title='What became of first answers that promised action or more study',
                    subtitle='Grand Jury recommendation-respondent pairs by first answer, final tracked status (% of each answer)',
                    x=dict(label='First answer', values='@CH:x'), y=dict(label='Share of answers (%)', unit='%'),
                    series=[dict(name='Implemented', values='@CH:implemented'), dict(name='In progress', values='@CH:in_progress'), dict(name='Open', values='@CH:open'),
                            dict(name='Will not be implemented', values='@CH:not_implementing'), dict(name='Closed otherwise', values='@CH:closed_other')],
                    highlight='Will not be implemented',
                    note='Only answers with at least one later tracker column. ' + CGJ_NOTE),
         robustness=dict(verdict='fragile', checks=[
             'Excluding the Board of Supervisors and the Mayor: {ex_wn|int} will not vs {ex_impl|int} implemented (n = {ex_n|int}).',
             'Jury reports from 2012 on: {late_wn|int} will not vs {late_impl|int} implemented (n = {late_n|int}).',
             'Did not hold as a lead for "will not" per recommendation: counting each recommendation once ({fa_distinct|int}), it is a tie, with {dist_any_wn|int} drawing at least one final "will not" and {dist_any_impl|int} at least one "implemented".',
             'Reversals of "will be implemented" are rarer and concentrated: {wb_bos_wn|int} of {wb_wn|int} are the Board, which often agreed by resolution and later said it lacks operational authority; without the Board, {wbx_wn|int} of {wbx_n|int} reversed.'],
             what_could_make_it_wrong='The tracker records answers, not outcomes; a respondent may say "will not" because another body did the work. First answers were mapped '
                                      'from printed labels to the four Penal Code categories, which is imperfect for letters that answer in prose.'),
         caveats=['Excludes answers that were never followed up in a tracker column.'],
         explore=dict(view='au-agreement', params={'source': 'cgj'}, label='See how Grand Jury answers relate to outcomes'),
         departments=['MYR', 'BOS'], tags=['Civil Grand Jury', 'Penal Code 933.05', 'follow-up']),

    # 5 ---------------------------------------------------------------------------------------------------------------
    dict(key='cgj_reasons', id='grand-jury-refusals-mostly-not-on-merits', theme='refusals',
         title='Only {s_policy_disagreement|pct} of Grand Jury refusals dispute the merits; authority and existing work lead',
         dek='A model reading of all {n|int} Grand Jury "will not be implemented" answers finds {s_not_our_authority|pct} cite lack of authority or jurisdiction, '
             '{s_already_done_or_existing_process|pct} say it is already done or covered, {s_legal_or_contract_constraint|pct} cite a legal or contract limit and '
             '{s_cost_or_resources|pct} cite cost. {s_policy_disagreement|pct} disagree on the merits.',
         why_it_matters='Juries address many recommendations to several officials at once, and the law requires each to answer. Most refusals say "not our authority" '
                        'or "already covered", and {s_alternative_approach|pct} say the respondent is taking a different approach. These can be accurate, or a way to sidestep '
                        'a question; the response text alone cannot tell which.',
         surprise='Cost, staffing or funding was the primary reason in only {s_cost_or_resources|pct} of refusals, the least common of the reasons (secondary reasons were not counted).',
         numbers=[
             dict(label='Refusals classified (Grand Jury)', value='{n|int}', source=SRC['reasons'] + '#source=cgj'),
             dict(label='Authority + already done + legal + cost', value='{s_four|pct}', source=SRC['reasons']),
             dict(label='Controller (CSA) refusals for comparison: no reason given / disagree on merits (CSA responses are brief matrix entries, often without a stated reason)', value='{csa_none|pct} / {csa_policy|pct} of {n_csa|int}', source=SRC['reasons'] + '#source=csa'),
         ],
         chart=dict(type='hbar', title='Why respondents said "will not be implemented"',
                    subtitle='Grand Jury refusals by the primary reason given in the printed response, % of refusals (n at right)',
                    x=dict(label='Reason', values='@CH:cats'), y=dict(label='Share of refusals (%)', unit='%'),
                    series=[dict(name='Share', values='@CH:vals', n='@CH:n')], highlight='Disagrees on the merits',
                    note='Reasons classified by Claude Sonnet 5 from the extracted response text, one primary reason each; shares are approximate.'),
         robustness=dict(verdict='robust', checks=[
             'Only classifications with confidence of at least {hc_min|f1} (n = {n_hc|int}): authority {hc_auth|pct}, merits {hc_policy|pct}; the merits share stays a minority, but the mix of other reasons shifts, so treat shares as approximate.',
             'Excluding the Board of Supervisors and the Mayor (n = {n_ex|int}): authority {ex_auth|pct}, merits {ex_policy|pct}, cost {ex_cost|pct}.',
             'Held for juries from 2016 on (n = {n_late|int}): merits {late_policy|pct}; the mix shifts from authority ({late_auth|pct}) to "already done or covered" ({late_done|pct}), and cost rises to {late_cost|pct}.'],
             what_could_make_it_wrong='The classification reads a short summary of each response, and many responses give several reasons; the primary one is a judgment call.'),
         caveats=['"Not our authority" answers can be accurate or can be a way to avoid a question; the data cannot tell which.'],
         explore=dict(view='au-agreement', params={'source': 'cgj'}, label='See Grand Jury responses and outcomes'),
         departments=['BOS', 'MYR', 'CON'], tags=['refusals', 'reasons', 'Civil Grand Jury']),

    # 6 ---------------------------------------------------------------------------------------------------------------
    dict(key='cgj_who', id='board-and-mayor-give-most-refusals', theme='refusals',
         title='The Board and the Mayor give {share_bm|pct} of all Grand Jury "will not be implemented" answers',
         dek='Of {n_wn|int} tracked refusals, the Board of Supervisors gave {bos|int} and the Mayor\'s Office (including MOHCD) {myr|int}; the two are named as respondents more '
             'often than anyone else. Without them, implemented answers outnumber refusals, {ex_impl|int} to {ex_wn|int}; with them, refusals lead.',
         why_it_matters='The Board is a legislature and a required respondent to most jury reports. Its most common single reason ({bos_auth|pct} of the {n_bos_rs|int} Board refusals whose reason could be classified) is '
                        'that it lacks authority over the matter, as in 2004-05: "{Q:bos_auth}" ({C:bos_auth}). Much of the Grand Jury\'s refusal count comes from '
                        'recommendations addressed to policymakers; other Board and Mayor refusals may reflect policy or budget choices.',
         surprise='The Board, not an operating department, answers "will not be implemented" most often: {bos_rate|pct} of its tracked answers overall ({bos_late|pct} for reports since 2012), against {rest_rate|pct} for all other respondents except the Mayor.',
         numbers=[
             dict(label='Grand Jury refusals: Board / Mayor / all', value='{bos|int} / {myr|int} / {n_wn|int}', source=REC + '#source=cgj, status=not_implementing, dept'),
             dict(label='Excluding Board and Mayor: implemented vs will not', value='{ex_impl|int} vs {ex_wn|int}', source=REC + '#source=cgj'),
             dict(label='Recommendations where at least one respondent implemented', value='{distinct_any|pct} of {n_distinct|int}', source=REC + '#source=cgj, grouped by report and rec_number'),
         ],
         chart=dict(type='hbar', title='Who answers "will not be implemented" to the Grand Jury',
                    subtitle='Refusals recorded as the latest status, top eight respondents; n at right = all of that respondent\'s tracked answers',
                    x=dict(label='Respondent', values='@CH:cats'), y=dict(label='Refusals', unit='count'),
                    series=[dict(name='Refusals', values='@CH:vals', n='@CH:n')], highlight=['Board of Supervisors', 'Mayor (incl. MOHCD)'],
                    note=CGJ_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Per distinct recommendation rather than per respondent: {distinct_any|pct} had at least one respondent implement.',
             'The Board\'s own reasons (n = {n_bos_rs|int}): {bos_auth|pct} say it lacks authority, the largest single reason.',
             'Held for reports from 2012 on: the Board and Mayor give {bm_late|pct} of refusals, though the Board\'s own refusal rate fell from {bos_early|pct} before 2012 to {bos_late|pct}.'],
             what_could_make_it_wrong='Required-respondent lists vary by report, so the Board and Mayor answer more recommendations than anyone else; their share of refusals partly reflects volume.'),
         caveats=['A Board refusal can coexist with a department implementing the same recommendation.'],
         explore=dict(view='au-status', params={'source': 'cgj', 'dept': 'BOS,MYR'}, label='See the Board\'s and Mayor\'s Grand Jury answers'),
         departments=['BOS', 'MYR'], tags=['Board of Supervisors', 'Mayor', 'Civil Grand Jury']),

    # 7 ---------------------------------------------------------------------------------------------------------------
    dict(key='repeat_after_impl', id='repeat-findings-follow-implemented-fixes', theme='repeat-findings',
         title='Repeat findings mostly follow a fix recorded as implemented, even for the Grand Jury',
         dek='{n_rep|int} recommendations repeat an earlier one at the same department. For the {n_kn|int} whose earlier recommendation has a recorded status, '
             '{n_pi|int} ({share|pct}) followed one marked implemented and {n_pwn|int} followed a refusal. For the Controller that roughly matches its {base_csa|pct} base rate; '
             'for the Grand Jury, {cg_share|pct} of repeats follow an implemented status, against a {base_cgj|pct} base rate.',
         why_it_matters='A repeat after a recorded fix can mean the fix did not last or did not reach the cause. It can also mean the fix worked and the same risk arose again, '
                        'as with tenant audits that examine a different business each time. The records cannot tell these apart, so a repeat is a reason to look closer, not a charge against any one department.',
         surprise='Repeats mostly follow recommendations recorded as implemented, not ones a department declined, even for the Grand Jury, whose recommendations are less often '
                  'recorded implemented overall ({cg_share|pct} of repeats of Grand Jury recommendations vs a {base_cgj|pct} base rate).',
         numbers=[
             dict(label='Repeat recommendations / with a known earlier status', value='{n_rep|int} / {n_kn|int}', source=REC + '#repeat_of; ' + SRC['clusters']),
             dict(label='Earlier recommendation implemented / will not', value='{n_pi|int} / {n_pwn|int}', source=REC + '#status of repeat_of'),
             dict(label='Earlier recommendation has no follow-up status', value='{n_pu|int}', source=REC),
         ],
         chart=dict(type='hbar', title='Status of the earlier recommendation, for findings that were made again',
                    subtitle='Repeat recommendations by the recorded status of the recommendation they repeat (unknown statuses excluded)',
                    x=dict(label='Earlier status', values='@CH:cats'), y=dict(label='Repeat recommendations', unit='count'),
                    series=[dict(name='Repeats', values='@CH:vals')], highlight='Implemented',
                    note='A repeat is a recommendation on the same problem at the same department in at least two reports and years. ' + CLUSTER_NOTE + ' ' + SELF_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Links with confidence of at least {hc_min|f1} only: {hc_share|pct} (n = {hc_n|int}).',
             'Excluding {n_tc|int} clusters about tenants and garage operators, where each audit covers a different business: {nt_share|pct} (n = {nt_n|int}).',
             'Controller repeating the Controller: {cc_share|pct} (n = {cc_n|int}), close to the Controller\'s {base_csa|pct} base rate, and {cc_closure|pct} of those earlier statuses are report-level closures (see the card on report-level closures); repeats of Grand Jury recommendations: {cg_share|pct} (n = {cg_n|int}) vs a {base_cgj|pct} base rate.'],
             what_could_make_it_wrong='The Controller\'s high implemented rate makes "follows an implemented fix" likely by default; a repeat can also be a new instance of an '
                                      'old risk that the first fix did address.'),
         caveats=['Clusters are a reading aid; a repeat is a reason to check, not proof a fix failed.'],
         explore=dict(view='au-repeat', params={}, label='See every repeat finding'),
         departments=[], tags=['repeat findings', 'implemented', 'follow-up']),

    # 8 ---------------------------------------------------------------------------------------------------------------
    dict(key='awss', id='emergency-water-study-yes-funding-no', theme='safety',
         title='Firefighting water: studies reported done; funding on the jury\'s timeline declined',
         dek='The 2019 Grand Jury found the high-pressure emergency water system "{Q:awss_f4}" ({C:awss_f4}). Of its {n_recs|int} recommendations, '
             '{n_all_impl|int} were reported implemented by every respondent. The two that would have committed money on the jury\'s timeline were answered "will not '
             'be implemented": a financed plan to extend the system ({r2_wn|int} of {r2_n|int} respondents; the Board reported it done through a study) and a purchase of new hose tenders ({r4_wn|int} of {r4_n|int}).',
         why_it_matters='On R2 the Mayor\'s Office, SFPUC, Fire and the City Administrator gave the same answer: "{Q:awss_r2}" ({C:awss_r2}); on R4 the Mayor said "{Q:awss_r4}" ({C:awss_r4}). '
                        'Those are budget judgments made in the open. As of the last tracker (2022), respondents said extending high-pressure coverage to the western and southern districts would go through the capital plan and a possible bond ({C:awss_r8}).',
         surprise='Plans, drills and studies were reported done; the refusals came only where the City would have had to commit money on the jury\'s timeline.',
         numbers=[
             dict(label='Recommendations reported implemented by every respondent', value='{n_all_impl|int} of {n_recs|int}', source='CGJ-2018-2019-a4a61434; CGJS-2018-19; ' + REC + '#report=CGJ-2018-2019-a4a61434'),
             dict(label='R2 (financed plan to 2034): will not', value='{r2_wn|int} of {r2_n|int} respondents', source='CGJS-2018-19 p.1'),
             dict(label='R4 (new hose tenders by mid-2021): will not', value='{r4_wn|int} of {r4_n|int} respondents', source='CGJS-2018-19 p.1'),
         ],
         chart=dict(type='stacked', title='Respondents\' last recorded answer, by recommendation',
                    subtitle='"Act Now Before It Is Too Late" (2019): each respondent\'s latest status for R1 to R10, count of respondents',
                    x=dict(label='Recommendation', values='@CH:x'), y=dict(label='Respondents', unit='count'),
                    series=[dict(name='Implemented', values='@CH:implemented'), dict(name='In progress', values='@CH:in_progress'),
                            dict(name='Will not be implemented', values='@CH:not_implementing')], highlight='Will not be implemented',
                    note='R2: financed plan for a high-pressure system in the areas without one, by 2034. R4: buy new hose tenders. R8: analyze a separate bond (last answer 2022: "Will Be Implemented in the Future"). '
                         'Source: Controller\'s tracker CGJS-2018-19; no later tracker for this term.'),
         robustness=dict(verdict='robust', checks=[
             'Checked in the tracker text: the refusal wording for R2 and R4 is on {C:awss_r2}, and the Board separately reported R2 implemented through a 2021 planning study and a BLA funding report.',
             'Not typical of safety recommendations: across the {n_sh|int} Grand Jury pairs the model flagged as life-safety or public-health, {sh_y|pct} were implemented vs {sh_n|pct} of others.',
             'Still unresolved: R8, a separate bond, was last recorded as "Will Be Implemented in the Future" in 2022, after which tracking of this jury term stopped.'],
             what_could_make_it_wrong='The tracker ends in 2022, and money did flow through the regular capital-plan route: the City\'s 2020 answer notes "{Q:awss_eser}" ({C:awss_eser}). '
                                      'The "will not" answers declined the jury\'s specific plan and timeline, not all funding.'),
         caveats=['Some hose tenders had been funded; the Mayor\'s response says funding for part of them was cut in the COVID-era budget ({C:awss_r4}).'],
         explore=dict(view='report', params={'id': 'CGJ-2018-2019-a4a61434'}, label='See this report\'s recommendations and answers'),
         departments=['FIR', 'PUC', 'MYR', 'ADM', 'BOS'], tags=['earthquake', 'fire', 'capital planning']),

    # 9 ---------------------------------------------------------------------------------------------------------------
    dict(key='civilianization', id='police-civilianization-17-years', theme='repeat-findings',
         title='Three watchdogs asked Police to civilianize sworn jobs in {n_rep|int} reports over {span|int} years',
         dek='From the {y0|yr} Grand Jury to the Budget and Legislative Analyst in {y1|yr}, {n_recs|int} recommendations asked the Police Department to move sworn officers '
             'out of jobs civilians could do. In 2024 the BLA reported that "{Q:civ_2024}" ({C:civ_2024}).',
         why_it_matters='Civilianization is meant to return sworn officers to duties that need them. SFPD has made progress: "{Q:civ_2019}" ({C:civ_2019}). '
                        'SFPD\'s position, as the BLA summarized it, is that "{Q:civ_resp}" ({C:civ_resp}), and SFPD has said that other positions "{Q:civ_sworn}" ({C:civ_sworn}).',
         surprise='SFPD has accepted the idea for specific positions: in 2018 "{Q:civ_2018}" ({C:civ_2018}).',
         numbers=[
             dict(label='Reports in the repeat cluster (Grand Jury, Controller, BLA)', value='{n_rep|int} reports, {n_recs|int} recommendations, {y0|yr}–{y1|yr}', source=SRC['clusters'] + '#C-0241'),
             dict(label='BLA 2024 on civilianization since FY2019-20', value='"{Q:civ_2024b}"', source='{C:civ_2024b}'),
             dict(label='Of the recommendations, recorded implemented / will not / no published status (BLA recommendations and older Controller reports are not tracked)', value='{n_impl|int} / {n_wn|int} / {n_unk|int}', source=REC + '#repeat_cluster=C-0241'),
         ],
         chart=dict(type='hbar', title='Civilianization recommendations to the Police Department, by report',
                    subtitle='Number of recommendations in each report that ask to move sworn officers out of civilian-type jobs',
                    x=dict(label='Report', values='@CH:cats'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Recommendations', values='@CH:vals')], highlight='@CH:hl',
                    note='The 2008 Controller reports (CON-761, CON-773) were prepared for the Controller by the Police Executive Research Forum. ' + CLUSTER_NOTE + ' Cluster C-0241.'),
         robustness=dict(verdict='robust', checks=[
             'Each report in the chain was checked against its PDF, and the description of the period after 2020 was corrected to the BLA\'s exact wording.',
             'The cluster spans all {n_bodies|int} recommending bodies, so it is not one auditor\'s concern.',
             'Progress before 2020 is on record: the Controller\'s 2019 count and SFPD\'s 2018 list, both quoted above, show conversions, so the gap is about the period since.'],
             what_could_make_it_wrong='The BLA says SFPD could not share details, not that no positions were civilianized; budget documents may show conversions the audits do not.'),
         caveats=['Grand Jury 2006-07 is a scanned report; its wording is not quoted here.'],
         explore=dict(view='au-repeat', params={'dept': 'POL'}, label='See Police repeat findings'),
         departments=['POL'], tags=['civilianization', 'overtime', 'police staffing']),

    # 10 --------------------------------------------------------------------------------------------------------------
    dict(key='contractor_eval', id='contractor-evaluations-30-years', theme='repeat-findings',
         title='Rating contractors\' past work: urged in {y0|yr}, required in 2016, database unused in 2024',
         dek='In {y0|yr} the Grand Jury urged that "{Q:ce_1996}" ({C:ce_1996}). A 2016 ordinance required it, yet in 2024 the BLA found the six construction '
             'departments "{Q:ce_2024}" ({C:ce_2024}); in {y1|yr} it again urged more use of past-performance tools ({C:ce_2026}).',
         why_it_matters='Without shared ratings, a contractor with a poor record on one City project may win the next one at another department. The rule exists; in 2024 the BLA found the shared '
                        'database was not being used as required. Budget limits are one stated reason: the 2021-22 jury asked that "{Q:ce_r3}", and in a 2024 tracker update the Mayor answered "will not be '
                        'implemented" because "{Q:ce_mayor}" ({C:ce_mayor}).',
         surprise='It was recorded as implemented: the Mayor reported the 2014-15 jury\'s recommendation done by an ordinance, noting that "{Q:ce_2016}" ({C:ce_2016}).',
         numbers=[
             dict(label='Reports in the repeat cluster', value='{n_rep|int} reports, {n_recs|int} recommendations, {y0|yr}–{y1|yr} ({span|int} years)', source=SRC['clusters'] + '#C-0137'),
             dict(label='Of those, recorded implemented / other status / no public follow-up', value='{n_impl|int} / {n_oth|int} / {n_unk|int}', source=REC + '#repeat_cluster=C-0137'),
         ],
         chart=dict(type='hbar', title='Reports asking for contractor performance evaluations in public works',
                    subtitle='Recommendations per report on evaluating contractors and using past performance in awards',
                    x=dict(label='Report', values='@CH:cats'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Recommendations', values='@CH:vals')], highlight='@CH:hl',
                    note=CLUSTER_NOTE + ' Cluster C-0137 (Public Works). The 2021-22 Grand Jury report and the 2024 BLA audit (BLA-f9cb966a) quoted above were not placed in this cluster and are not counted here; the 2024 finding covers all six Chapter 6 departments. Statuses as recorded.'),
         robustness=dict(verdict='robust', checks=[
             'Each link in the chain was checked against the PDFs, which corrected an earlier attribution: on the 2014-15 recommendation only the Board said "will not"; the Mayor reported the ordinance.',
             'The requirement is in law (Administrative Code section 6.26), so "not in routine use" is measured against a written duty, per the BLA.',
             'Held across sources: the Grand Jury, the Controller and the BLA each made the recommendation.'],
             what_could_make_it_wrong='A database pilot ran in FY2018-19 and departments may keep their own evaluations; the BLA finding is about the shared database.'),
         caveats=['The 1995-96 report does not number its recommendations.'],
         explore=dict(view='au-repeat', params={'dept': 'DPW'}, label='See Public Works repeat findings'),
         departments=['DPW', 'PUC', 'MTA', 'REC', 'PRT', 'AIR'], tags=['contracting', 'Chapter 6', 'construction']),

    # 11 --------------------------------------------------------------------------------------------------------------
    dict(key='tenant_reporting', id='tenant-reporting-most-repeated-finding', theme='repeat-findings',
         title='The most repeated finding: Airport tenants\' late revenue reports, in {air_rep|int} audits over {air_span|int} years',
         dek='From {air_y0|yr} to {air_y1|yr}, {air_rep|int} Controller audits, mostly of different Airport tenants, found annual certified revenue reports late, missing or '
             'uncertified, and in some audits lease penalties not assessed; {air_impl|int} of {air_n|int} recommendations were recorded implemented. {top10_tenant|int} of the ten most repeated '
             'findings citywide concern money the City collects from, or pays to, its tenants and operators.',
         why_it_matters='The City relies on businesses at the Airport, the Port and City garages to report their own sales, on which part of their rent is based. Each '
                        'recommendation was addressed to one tenant\'s audit, so closing it did not necessarily change practice elsewhere. The last audit in the chain asked '
                        'the Airport to "{Q:air_2019}" ({C:air_2019}).',
         surprise='The same finding appeared at tenant after tenant for {air_span|int} years while most of its recommendations were recorded implemented; the audits do not show whether Airport-wide practice changed.',
         numbers=[
             dict(label='Airport tenant-reporting chain', value='{air_rep|int} reports, {air_n|int} recommendations, {air_y0|yr}–{air_y1|yr}', source=SRC['clusters'] + '#C-0117'),
             dict(label='Recorded implemented', value='{air_impl|int} of {air_n|int}', source=REC + '#repeat_cluster=C-0117'),
             dict(label='Tenant or operator clusters among the ten most repeated', value='{top10_tenant|int}', source=SRC['clusters']),
         ],
         chart=dict(type='hbar', title='The ten most repeated audit findings',
                    subtitle='Repeat clusters by number of reports that made the finding; tenant and operator revenue findings highlighted',
                    x=dict(label='Finding', values='@CH:cats'), y=dict(label='Reports', unit='count'),
                    series=[dict(name='Reports', values='@CH:vals')], highlight='@CH:hl',
                    note=CLUSTER_NOTE + ' Rec & Park park evaluations are an annual City Performance program, repeated by design.'),
         robustness=dict(verdict='robust', checks=[
             'The {air_rep|int} are separate audit reports, mostly of different tenants, so no report is counted twice.',
             'The chain ends in {air_last|yr}, when Airport and Port tenant audits became much less frequent; its end is a record of audits, not proof the problem stopped.',
             'Held beyond the Airport: the Port and SFMTA garages show parallel chains of {prt_chain|int} and {mta_chain|int} reports.'],
             what_could_make_it_wrong='Tenant audits are chosen by risk, so the same finding at many tenants may say more about audit selection than about how common the problem is.'),
         caveats=['Clusters are a reading aid; a repeat is a reason to check, not proof a fix failed.'],
         explore=dict(view='au-repeat', params={'dept': 'AIR'}, label='See Airport repeat findings'),
         departments=['AIR', 'PRT', 'MTA'], tags=['tenants', 'lease revenue', 'repeat findings']),

    # 12 --------------------------------------------------------------------------------------------------------------
    dict(key='bla_untracked', id='board-analyst-recommendations-untracked', theme='follow-through',
         title='None of the Board\'s budget analyst\'s {n|int} audit recommendations is in a regular follow-up',
         dek='The Board of Supervisors\' analyst issued {n|int} recommendations in {n_rep|int} performance audits from {y0|yr} to {y1|yr}; departments agreed at least '
             'in part with {agree_share|pct}. None has a published status, against {known_csa|pct} of the Controller\'s and {known_cgj|pct} of the Grand Jury\'s.',
         why_it_matters='Unlike Grand Jury reports, which respondents must answer under state law, and Controller audits, which have a formal follow-up program, BLA audits '
                        'carry no published tracking requirement. When a later audit looks back, the news can be mixed: the BLA\'s 2024 Police overtime audit found '
                        '"{Q:bla_2018}" ({C:bla_2018}), and that "{Q:bla_2018b}" ({C:bla_2018b}). The Board commissions these audits; whether and how to track them is its decision.',
         surprise='Departments agreed at least in part with most BLA recommendations, but no regular public record shows whether they carried them out.',
         numbers=[
             dict(label='BLA audit recommendations / reports', value='{n|int} / {n_rep|int}', source=REC + '#source=bla'),
             dict(label='Agreed or partially agreed', value='{agree_share|pct}', source=REC + '#source=bla, agreed'),
             dict(label='With a status in a regular public follow-up report', value='{n_known|int}', source=REC + '#source=bla, status'),
             dict(label='Later recommendations that repeat a BLA recommendation', value='{n_later|int}, repeating {n_later_pred|int} BLA recommendations', source=REC + '#repeat_of'),
         ],
         chart=dict(type='hbar', title='Share of recommendations with a status in a regular public follow-up',
                    subtitle='All recommendations extracted, by recommending body (n at right)',
                    x=dict(label='Recommending body', values='@CH:cats'), y=dict(label='With a status (%)', unit='%'),
                    series=[dict(name='With a status', values='@CH:vals', n='@CH:n')], highlight='Budget and Legislative Analyst',
                    note='Controller follow-up covers audits issued from July 2010; Grand Jury tracking covers jury terms from 2003-04. The BLA publishes no follow-up series.'),
         robustness=dict(verdict='robust', checks=[
             'Later audits give only a partial trace: {n_later|int} later recommendations repeat {n_later_pred|int} BLA recommendations, and the 2024 Police audit reported on 2018 recommendations; neither amounts to a regular follow-up.',
             'Held in the full BLA listing: of {bla_docs|int} documents, {bla_fu_docs|int} have "follow-up" in the title and neither reports on audit recommendations; some later audits review earlier ones, as the 2024 Police audit did.',
             'The comparison is conservative: the Controller\'s share counts older audits outside its follow-up program as untracked.'],
             what_could_make_it_wrong='Departments may report progress to Board committees in hearings, which this project does not capture.'),
         caveats=['BLA reports without "audit" in the title were not extracted.'],
         explore=dict(view='au-status', params={'source': 'bla'}, label='See BLA recommendations'),
         departments=['BOS', 'POL'], tags=['Budget and Legislative Analyst', 'follow-up', 'Board of Supervisors']),

    # 13 --------------------------------------------------------------------------------------------------------------
    dict(key='frozen_open', id='open-recommendations-not-updated', theme='follow-through',
         title='{share_stale|pct} of recommendations recorded open over two years have had no public update in two years',
         dek='{n_o2|int} recommendations issued more than two years ago are still recorded as open or in progress; {n_stale|int} of them have had no public follow-up '
             'in two years, and {n_stale5|int} in five. The median last update was in {med_lf|yr}.',
         why_it_matters='"Open" in these records often means "last heard of", not "still being worked on". Most are Grand Jury items whose public tracking ended after a few '
                        'annual updates, as the tracking process is designed. The public record cannot tell whether these were done, dropped or overtaken.',
         surprise='The list of long-open items is mostly a list of items with no recent public follow-up.',
         numbers=[
             dict(label='Open or in progress, issued more than two years ago', value='{n_o2|int} (Grand Jury {n_cgj|int}, Controller {n_csa|int})', source=REC + '#status, date_issued'),
             dict(label='No follow-up in two years / five years', value='{n_stale|int} / {n_stale5|int}', source=REC + '#last_followup'),
             dict(label='Grand Jury / Controller items with no update in two years', value='{cgj_stale|int} / {csa_stale|int}', source=REC),
         ],
         chart=dict(type='bar', title='When long-open recommendations were last updated',
                    subtitle='Recommendations open or in progress and issued more than two years ago, by year of the latest public follow-up',
                    x=dict(label='Year of last update', values='@CH:x'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Recommendations', values='@CH:vals')], highlight='2016',
                    note='As of September 26, 2026. ' + SELF_NOTE),
         robustness=dict(verdict='robust', checks=[
             'Using five years without an update: {n_stale5|int} of {n_o2|int}.',
             'Held for both bodies: Grand Jury {cgj_stale|int} of {n_cgj|int}, Controller {csa_stale|int} of {n_csa|int}.',
             'Held for items issued before 2020: {pre_stale|int} of {pre_n|int} have had no update in two years.'],
             what_could_make_it_wrong='Some items may be tracked in documents this project did not find, such as department reports to commissions. Of the {n_csa|int} Controller items, '
                                      '{csa_pre|int} are from audits issued before July 2010, which the Controller\'s annual list of long-open items does not cover, and the other {csa_post|int} are on '
                                      'that list, which counted {n2025|int} in 2025 (see the card on the Controller\'s long-open list).'),
         caveats=['Last recorded status, not evidence the work is undone.'],
         explore=dict(view='au-open', params={}, label='See open recommendations'),
         departments=[], tags=['stale status', 'tracking', 'open items']),

    # 14 --------------------------------------------------------------------------------------------------------------
    dict(key='coverage', id='port-drew-more-reports-than-fire', theme='coverage',
         title='Per dollar spent, the Port drew {ratio_min|x0} to {ratio|x0} times as many Controller reports as Fire',
         dek='In FY2011–FY2025 the Controller issued {prt_n|int} reports with recommendations for the Port, which spent {prt_sp|x1} billion dollars, and {fir_n|int} for '
             'the Fire Department, which spent {fir_sp|x1} billion: {prt_per|x1} versus {fir_per|x1} reports per billion. Fire had the fewest per dollar of the {n_big|int} '
             'departments that spent at least {min_b|x1} billion.',
         why_it_matters='Much of the difference is lease and concession audits, which protect revenue at the Port and Airport; spending does not capture that revenue risk. '
                        'Fire\'s budget is mostly salaries, which citywide payroll audits may cover without naming the department. Over the same years Fire had {fir_oth|int} Grand Jury '
                        'and BLA reports, against {fir_n|int} from the Controller. The Controller sets its audit plan by risk; whether spending-heavy departments like Fire get enough coverage is a fair question for that plan.',
         surprise='The Airport, which spent less than the Public Utilities Commission, had more Controller reports ({air_n|int}) than any other department.',
         numbers=[
             dict(label='Port: reports / spending FY2011–FY2025', value='{prt_n|int} / {prt_sp|x1} billion dollars ({prt_fin|int} financial or compliance audits)', source=SRC['reports'] + '#source=csa, depts; ' + SRC['spend']),
             dict(label='Fire: reports / spending', value='{fir_n|int} / {fir_sp|x1} billion dollars', source=SRC['reports'] + '; ' + SRC['spend']),
             dict(label='Airport: Controller reports FY2011–FY2025 (most of any department)', value='{air_n|int}', source=SRC['reports'] + '#source=csa, depts'),
             dict(label='Median reports per billion, departments over the threshold', value='{med_per|x1}', source=SRC['reports'] + '; ' + SRC['spend']),
         ],
         chart=dict(type='hbar', title='Controller reports per billion dollars of spending, FY2011–FY2025',
                    subtitle='CSA reports with at least one recommendation naming the department, per billion dollars of actual spending (nominal); departments spending at least {min_b|x1} billion dollars over the period; n = reports',
                    x=dict(label='Department', values='@CH:cats'), y=dict(label='Reports per billion dollars', unit='ratio'),
                    series=[dict(name='Reports per billion', values='@CH:vals', n='@CH:n')], highlight=['Port', 'Fire Department'],
                    note='Spending: Spending and Revenue actuals (DataSF bpnb-jwfb) as exported by the performance module; nominal dollars summed over fiscal years. A report naming several departments counts for each.'),
         robustness=dict(verdict='robust', checks=[
             'Counting recommendations instead of reports: Port {r_prt|x1} vs Fire {r_fir|x1} per billion (median {r_med|x1}); Fire ranks {r_fir_rank|int} from the bottom.',
             'Excluding financial and compliance audits (most tenant audits): Port {x_prt|x1} vs Fire {x_fir|x1}; Fire ranks {x_fir_rank|int} from the bottom.',
             'FY2016–FY2025 only: Port {l_prt|x1} vs Fire {l_fir|x1}; Fire ranks {l_fir_rank|int} from the bottom.',
             'Held with the Grand Jury and the BLA added, though Fire is less of an outlier: {all_prt|x1} vs {all_fir|x1} reports per billion (median {all_med|x1}); Fire ranks {all_fir_rank|int} from the bottom.'],
             what_could_make_it_wrong='Reports without recommendations (such as clean audits) are not counted, and citywide audits that touch Fire without naming it are missed.'),
         caveats=['Nominal dollars; because all departments are compared over the same years, inflation affects them roughly alike.'],
         explore=dict(view='au-reports', params={'source': 'csa', 'dept': 'FIR'}, label='See Controller reports on the Fire Department'),
         departments=['PRT', 'FIR', 'AIR', 'CON'], tags=['audit coverage', 'audit plan', 'risk']),

    # 15 --------------------------------------------------------------------------------------------------------------
    dict(key='public_integrity', id='public-integrity-reforms-closed', theme='trends',
         title='After the 2020 corruption cases, {full|int} of {tot|int} integrity reforms were reported fully done',
         dek='The Controller\'s final update on its Public Integrity series (September 2026) reports {full|int} of {tot|int} recommendations implemented and closed, '
             '{part|int} closed as partially implemented, {prog|int} still in progress and {wn|int} that will not be implemented; for one of those, the update says "{Q:pi_wn}" ({C:pi_wn}).',
         why_it_matters='These reforms, on gifts, contracting, refuse rates and permitting, were a central part of the City\'s response to the Public Works corruption cases. The '
                        'Controller notes that "{Q:pi_closed}" ({C:pi_closed}), and that "{Q:pi_ig}" ({C:pi_ig}).',
         surprise='"Closed" includes the {part|int} partial implementations (fully implemented is {full_share|pct}). The Controller closed items based on departments\' descriptions of what they did; no one has yet independently tested those claims.',
         numbers=[
             dict(label='Recommendations: fully / partially implemented and closed', value='{full|int} / {part|int} of {tot|int}', source='CON-3624 p.3 (table total)'),
             dict(label='Will not be implemented / in progress', value='{wn|int} / {prog|int}', source='CON-3624 p.3'),
             dict(label='Public Integrity reports with extracted recommendations', value='{n_pi_reports|int}', source=SRC['reports'] + '#report_kind=public_integrity_review'),
         ],
         chart=dict(type='hbar', title='Status of the Public Integrity recommendations, September 2026',
                    subtitle='Recommendations in the Controller\'s Public Integrity assessments and audits, 2020–2025',
                    x=dict(label='Status', values='@CH:cats'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Recommendations', values='@CH:vals')], highlight='Partially implemented and closed',
                    note='Source: Controller, final Public Integrity status update, {C:pi_table} (September 16, 2026). Statuses are as the departments reported them.'),
         robustness=dict(verdict='robust', checks=[
             'The counts are read from the report\'s own table and re-read by the verifier from the PDF text.',
             'Our own count agrees in direction: {pi_impl|int} of the {pi_rows|int} recommendations we linked to these updates are recorded implemented (our count splits some lettered sub-parts).',
             'The table records the {part|int} partial items as closed, not open; an earlier draft of our dashboard story had described them as still in progress.'],
             what_could_make_it_wrong='The statuses rest on departments\' own descriptions, accepted by the Controller; the Inspector General may, but has not yet, independently confirm them.'),
         caveats=['Individuals named in the source reports are not named here.'],
         explore=dict(view='au-reports', params={'source': 'csa', 'years': '2020-2026'}, label='See the Controller\'s reports since 2020'),
         departments=['CON', 'DPW', 'ETH', 'ADM'], tags=['public integrity', 'corruption', 'reform']),

    # 16 --------------------------------------------------------------------------------------------------------------
    dict(key='dollars', id='largest-dollar-figures-one-refund', theme='dollars',
         title='The ten largest audit dollar figures include one refund to ratepayers, cited twice',
         dek='Of the {n_find|int} dollar findings in Controller and BLA reports, the largest are change orders across public works contracts in FY2022–24 ({a_co|mil}, {co_pct|pct} of contract value; '
             'change orders are a normal part of construction and the report does not call the amount improper), SFPUC bond-funded labor costs for which supporting documents were '
             'no longer available ({a_puc|mil}) and a Recology settlement ({a_rec|mil}) that appears in two reports. The rest are estimates, savings or cost growth.',
         why_it_matters='Dollar figures in audits measure very different things, from money owed back to ratepayers to what might be saved. Adding them up would double '
                        'count (the Recology settlement) and mix losses with forecasts, which is why this dashboard never sums them.',
         surprise='The largest amount labeled unsupported is a records gap, not a finding of misuse: "{Q:puc_1567}" ({C:puc_1567}).',
         numbers=[
             dict(label='Dollar findings kept after page verification (Controller and BLA)', value='{n_find|int} in {n_rep|int} reports', source=SRC['reports'] + '#dollar_findings'),
             dict(label='Recology refund', value='"{Q:recology}"', source='{C:recology}'),
             dict(label='Change orders, all Chapter 6 departments, FY2022–24', value='{a_co|mil1} on {co_base|bil1} of contracts ({co_pct|pct})', source='{C:co_total} (table total row)'),
             dict(label='Refunds to ratepayers among the top ten', value='{n_overcharge|int} (the same refund)', source=SRC['reports'] + '#CON-3093, CON-2951'),
         ],
         chart=dict(type='hbar', title='The ten largest dollar figures in Controller and BLA reports',
                    subtitle='Millions of dollars, nominal, as stated in each report; kind in parentheses; never summed',
                    x=dict(label='Finding', values='@CH:cats'), y=dict(label='Millions of dollars', unit='$M'),
                    series=[dict(name='Amount', values='@CH:vals')], highlight='@CH:hl',
                    note='Each amount was re-checked against the cited page (08a_verify_dollars.py). Grand Jury estimates are excluded. Kind labels are this project\'s reading of the report.'),
         robustness=dict(verdict='robust', checks=[
             'Every amount in the chart appears on its cited page in the PDF text (checked by the verifier).',
             'The two Recology figures describe one settlement: "{Q:recology_2021}" ({C:recology_2021}).',
             'With Grand Jury figures added the pattern holds: the Recology settlement is still the only refund among the largest; the largest jury figure, {cgj_top|mil}, is an estimated pension-liability increase, not a loss ({C:cgj_750}).'],
             what_could_make_it_wrong='Kinds were assigned by the extraction model and checked by the analyst for the top ten only. The checks confirm the listed amounts, not that extraction caught every dollar figure; a missed larger figure could change the top ten.'),
         caveats=['Nominal dollars as stated; amounts span 2007–2026 and are never added or compared across years.'],
         explore=dict(view='au-open', params={}, label='See recommendations with dollars at stake'),
         departments=['DPW', 'PUC', 'MTA', 'HOM', 'REC'], tags=['dollars', 'Recology', 'change orders']),

    # 17 --------------------------------------------------------------------------------------------------------------
    dict(key='already', id='grand-jury-told-already-done', theme='refusals',
         title='In {share|pct} of first answers to the Grand Jury, respondents said "has been implemented"',
         dek='In {n_hbi|int} of {n|int} recorded first answers ({share|pct}; one per recommendation and respondent), respondents said the recommendation had already been implemented. '
             'Another {n_wn_exist|int} first answers were refusals whose main reason was "already done or covered by existing work" (as classified by an AI model); together about {share_both|pct} of first answers.',
         why_it_matters='Juries serve one year; departments answer from inside. A large "already done" share can mean juries recommend work already under way, departments began '
                        'fixes during the jury\'s inquiry, or respondents count related work as the fix. The printed answers let readers judge case by case.',
         surprise='Among the {n_big|int} respondents with at least {min_ans|int} answers, {big_max_dept|str} gave this answer most often ({big_max|pct}), which may reflect juries recommending work it already had under way; the Board of Supervisors least ({bos|pct}), '
                  'as expected for a legislative body whose answers usually concern proposed laws or funding.',
         numbers=[
             dict(label='First answers "has been implemented"', value='{n_hbi|int} of {n|int}', source=REC + '#source=cgj, cgj_response'),
             dict(label='Refusals citing "already done or existing process"', value='{n_wn_exist|int}', source=SRC['reasons']),
         ],
         chart=dict(type='bar', title='Share of Grand Jury first answers saying "has been implemented", by report year',
                    subtitle='Recommendation-respondent pairs with a recorded first answer; % of answers',
                    x=dict(label='Report years', values='@CH:x'), y=dict(label='Answered "has been implemented" (%)', unit='%'),
                    series=[dict(name='Has been implemented', values='@CH:vals')],
                    note='One row per recommendation and required respondent. Shares use the respondent\'s first recorded answer (the response letter or the tracker\'s original-response column), mapped to the Penal Code 933.05 categories. '
                         'This differs from the final tracked status used on other cards.'),
         robustness=dict(verdict='robust', checks=[
             'Held in every period: between {p_min|pct} and {p_max|pct}.',
             'Excluding the Board of Supervisors, which rarely gives this answer: {ex_share|pct}.',
             'Across the {n_big|int} respondents with at least {min_ans|int} answers the share ranges from {bos|pct} (Board of Supervisors) to {big_max|pct} ({big_max_dept|str}); {n_mid|int} of the {n_big|int} fall between {mid_lo|pct} and {mid_hi|pct}.'],
             what_could_make_it_wrong='First answers were mapped to Penal Code categories from printed labels; prose letters may be misread.'),
         caveats=['"Has been implemented" is the respondent\'s claim at the time of answering.'],
         explore=dict(view='au-agreement', params={'source': 'cgj'}, label='See Grand Jury first answers'),
         departments=['FIR', 'POL', 'DPH', 'BOS'], tags=['Civil Grand Jury', 'responses', 'already implemented']),

    # 18 --------------------------------------------------------------------------------------------------------------
    dict(key='time_by_type', id='it-heavy-audits-closed-last', theme='follow-through',
         title='Controller audits heavy on IT and staffing asks took longest to be recorded closed',
         dek='Among {n|int} CSA recommendations recorded implemented with a date, the median time from report to the follow-up that recorded it done was {m_collect_or_recover_money|x0} months for '
             'collecting money and {m_control_or_procedure|x0} for control fixes, but {m_it_system|x0} for IT systems and {m_staffing_or_funding|x0} for new staff or funding. '
             'Because most dates mark when a whole report closed, this compares audits more than individual fixes.',
         why_it_matters='A report is recorded closed when its slowest item is done. Audits whose recommendations involve IT systems or new staff and funding were recorded closed later. '
                        'Budget and procurement cycles are one plausible reason, but these data cannot separate that from how the follow-up program closes reports '
                        '(see the card on report-level closures).',
         surprise=None,
         numbers=[
             dict(label='Median months, collect money / controls / IT / staffing', value='{m_collect_or_recover_money|x0} / {m_control_or_procedure|x0} / {m_it_system|x0} / {m_staffing_or_funding|x0}', source=REC + '#months_to_close; ' + SRC['actions']),
             dict(label='Recommendations with a dated implementation', value='{n|int}', source=REC + '#source=csa, months_to_close'),
         ],
         chart=dict(type='hbar', title='Median months until recorded implemented, by kind of recommendation (mostly whole-report closure)',
                    subtitle='CSA recommendations recorded implemented with a date (upper bounds: most dates are the follow-up period in which a whole report closed); n at right',
                    x=dict(label='Kind of action', values='@CH:cats'), y=dict(label='Median months', unit='count'),
                    series=[dict(name='Median months', values='@CH:vals', n='@CH:n')], highlight='Build or upgrade an IT system',
                    note='Action type assigned by Claude Sonnet 5. Months run from report date to the first implemented event.'),
         robustness=dict(verdict='fragile', checks=[
             'Recommendation-level evidence only (n = {rl_n|int}): IT {rl_it|x0} months vs controls {rl_ctl|x0}; the gap narrows.',
             'By the topic of the report instead of the kind of fix: IT {t_it|x0} months vs revenue {t_rev|x0} and contracts {t_con|x0}.',
             'Did not hold within reports: where one report has both IT and control recommendations ({wr_n|int} reports), their dates are identical {wr_same|pct} of the time, so the gap reflects which audits are IT-heavy, not item-by-item speed.'],
             what_could_make_it_wrong='Most dates are when a whole report closed, which is set by its slowest item; an IT-heavy audit closes late even if its control items were done early.'),
         caveats=['For most recommendations the true completion date may be earlier than shown, because the date recorded is when the whole report closed.', '{n_inf|int} inferred-implemented rows have no date and are excluded.'],
         explore=dict(view='au-time', params={'source': 'csa'}, label='See how long Controller recommendations took'),
         departments=['CON'], tags=['time to implement', 'IT', 'follow-up']),

    # 19 --------------------------------------------------------------------------------------------------------------
    dict(key='open_list', id='controller-long-open-list-lowest', theme='follow-through',
         title='{n2025|int} Controller audit recommendations were open over two years in 2025, the fewest since 2014',
         dek='The Controller\'s annual count of its recommendations still open two years after issue ranged from {min_pre|int} to {max_n|int} between 2014 and 2024 and was {n2025|int} in 2025, '
             'the lowest in the series. {n_dph|int} of the {n2025|int} are Public Health\'s, from the 2022 audit of City Option, the program that holds employers\' health-care contributions under the Health Care Security Ordinance.',
         why_it_matters='A short list is consistent with departments reporting most Controller recommendations closed within two years, though it may partly reflect the smaller number '
                        'issued since 2020 (see the card on the Controller\'s falling recommendation count). Public Health says "{Q:dph_reason}" ({C:dph_reason}).',
         surprise=None,
         numbers=[
             dict(label='Open more than two years, June 30 of each year', value='{min_pre|int}–{max_n|int} in 2014–2024; {n2025|int} in 2025', source='CON-1772 p.3; CON-2213 p.5; CON-2339 p.5; CON-2495 p.4; CON-2625 p.2; CON-2744 p.2; CON-2886 p.2; CON-3000 p.2; CON-3145 p.2; CON-3296 p.2; CON-3422 p.2; CON-3533 p.2'),
             dict(label='City Option audit (CON-3045) recommendations open or in progress', value='{dph_open|int} of {dph_n|int}', source=REC + '#report=CON-3045'),
         ],
         chart=dict(type='bar', title='Controller recommendations open more than two years',
                    subtitle='As stated in each annual "Recommendations Not Implemented After More Than Two Years" report, as of June 30',
                    x=dict(label='Year', values='@CH:x'), y=dict(label='Recommendations', unit='count'),
                    series=[dict(name='Open over two years', values='@CH:vals')], highlight='2025',
                    note='Counts read from the reports\' own text (CON-1772 to CON-3533) and re-read by the verifier.'),
         robustness=dict(verdict='robust', checks=[
             'Every count is the report\'s own stated number, re-read from the PDF text by the verifier.',
             'Our record-level data agree on the City Option audit: {dph_open|int} of its {dph_n|int} recommendations are open or in progress; our other long-open Controller items are from audits issued before July 2010, which the list does not cover.',
             'Noisy year to year: earlier lows in 2018 and 2020 were followed by rebounds, so 2025 could be a one-year dip; the claim is only that it is the lowest count in the series.'],
             what_could_make_it_wrong='The list covers only CSA audits in the Controller\'s follow-up program, not Grand Jury or BLA recommendations (see the card on long-open items with no update), and rests on departments\' reported status.'),
         caveats=['Fewer recommendations issued means fewer that can age past two years.'],
         explore=dict(view='report', params={'id': 'CON-3045'}, label='See the City Option audit'),
         departments=['DPH', 'CON'], tags=['open items', 'Public Health', 'City Option']),
]


_ORDER = ['csa_output', 'csa_closure', 'action_types', 'repeat_after_impl', 'cgj_reasons', 'awss', 'cgj_who', 'tenant_reporting', 'further_analysis', 'civilianization', 'bla_untracked', 'contractor_eval', 'frozen_open', 'open_list', 'coverage', 'public_integrity', 'dollars', 'already', 'time_by_type']
INSIGHTS = sorted(INSIGHTS, key=lambda t: _ORDER.index(t['key']))
