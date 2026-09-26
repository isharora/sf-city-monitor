"""Screening record for candidate insights that were tested and NOT published, or folded into another card
(data/redteam/insights_screening.json). Each entry has the test numbers and the reason. Published insights are built by
build_insights.py and verified by verify_insights.py.
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compute_build as cb

ROOT = cb.ROOT
DATA = cb.DATA
OUT = os.path.join(DATA, 'redteam', 'insights_screening.json')


def J(p):
    return json.load(open(os.path.join(DATA, p)))


def main():
    R = []
    ref = J('analysis/reforms.json')
    R.append({'candidate': 'Contractor-affiliated money (contractor entities, listed principals, their employees) as a share of City candidate money fell after the 2019 ban',
              'result': ref['contractor_affiliated_share_by_period'],
              'decision': 'dropped',
              'reason': 'The share drifts from about 9.4% (2015-2018) to 7.7% (2021-2025), but it depends on matching free-text employer names, there is no base rate for how many '
                        'San Franciscans work for city contractors, and the timing test (published: ban windows vs chance) answers the ban question more directly.'})
    rt = J('redteam/redteam2.json')['rederivation']['ban_base_rate']
    R.append({'candidate': 'Contractor principals give 27% less in the 12 months after an approval than two years away (placebo ratio 0.73)',
              'result': {'first_pass_ratio': J('analysis/contractor_base_rates.json')['timing_placebo']['ratio_W0_to_baseline'], 'ratio_vs_4y': rt['placebo_4y']['ratio_W0_to_4y_mean'],
                         'ratio_vs_2y_same_approvals': rt['placebo_4y']['ratio_W0_to_2y_mean']},
              'decision': 'dropped', 'reason': 'Not stable: the ratio moves from 0.73 to 0.36 with the comparison window because giving swings with the election calendar.'})
    conc = J('analysis/concentration.json')
    R.append({'candidate': 'Coworker clusters: 5+ employees of one employer giving to the same candidate within 14 days',
              'result': {'n_clusters': conc['employer_clusters']['n_clusters'], 'form125_bundling_rows': conc['employer_clusters']['form125_disclosed_bundled_rows']},
              'decision': 'dropped', 'reason': 'Coworkers giving together is common (fundraisers, shared politics); without a base rate or any sign of reimbursement, publishing clusters would imply bundling the data do not show.'})
    lob = J('analysis/lobbying.json')
    pay = ref['series']['lobbying_payments_by_year']
    R.append({'candidate': 'Reported payments to lobbyists held near $13 million a year while contacts fell 40% from the 2017 peak',
              'result': {'payments_2017': pay['2017'], 'payments_2025': pay['2025'], 'contacts_2017': lob['contacts_by_year']['2017'], 'contacts_2025': lob['contacts_by_year']['2025']},
              'decision': 'dropped', 'reason': 'Payments are reported by lobbyists and firms on a different basis from contacts (retainers vs meetings), and duplicate contact reports per meeting '
                                              'change over time; the ratio is hard to interpret.'})
    L = cb.meetings(cb.lob())
    L = L[L.year.between(2015, 2025)]
    c = L.groupby('source').size().sort_values(ascending=False)
    R.append({'candidate': 'Lobbying is concentrated in a few clients',
              'result': {'clients': int(len(c)), 'top_1pct_share_of_meetings': float(c.head(max(1, len(c) // 100)).sum() / c.sum()),
                         'top_10pct_share': float(c.head(len(c) // 10).sum() / c.sum())},
              'decision': 'folded', 'reason': 'Moderate and unsurprising on its own (the top 1% of clients hold about a fifth of meetings); used as context in the top-100-clients card.'})
    top_off = lob['top_officials'][:5]
    R.append({'candidate': 'Ranking elected officials by lobbying contacts received',
              'result': {'top_by_contacts': [{'official': o['label'], 'contacts': o['contacts']} for o in top_off]},
              'decision': 'dropped', 'reason': 'Contacts track roles (Board president, Land Use chair, Planning director) and years in office; a ranking invites unfair inference and '
                                              'cannot be normalized for committee assignments with these data.'})
    gp = {r['year']: r['total'] for r in conc['by_bucket_year']['general-purpose / independent committees']}
    R.append({'candidate': 'General-purpose (slate and voter-guide) committees surged in 2023-2024',
              'result': {'2021': gp.get(2021), '2022': gp.get(2022), '2023': gp.get(2023), '2024': gp.get(2024)},
              'decision': 'folded', 'reason': 'Real, but these committees mix independent expenditures, voter guides and transfers; the spending side is covered by the 2024 independent-spending card.'})
    R.append({'candidate': 'Candidate self-funding in 2024 exceeded all other donations to City candidates',
              'result': {'self_2024': conc['candidate_self_funding_city_by_year']['2024'], 'largest': conc['largest_self_funding'][0]},
              'decision': 'folded', 'reason': 'One candidate accounts for nearly all of it; shown as context in the independent-spending card rather than as a card about one person.'})
    oc = lob['outcome_contracts']
    R.append({'candidate': 'Lobbying clients win contracts within 24 months of their first contact',
              'result': oc, 'decision': 'dropped',
              'reason': 'No usable base rate: clients that already contract with the City lobby about those contracts, so the before/after share mostly reflects who lobbies.'})
    op = lob['outcome_planning']
    R.append({'candidate': 'Lobbied planning projects are approved more often than other projects',
              'result': {'approval_rate_lobbied': op['approval_rate_lobbied_among_decided'], 'approval_rate_all': op['approval_rate_all_among_decided'],
                         'n_matched': op['n_matched_to_planning_records']},
              'decision': 'dropped', 'reason': 'Selection: lobbied projects are larger and more complex; most pre-2018 case numbers are missing from the planning dataset.'})
    dev = pd.read_parquet(os.path.join(DATA, 'interim', 'dev_3500.parquet'))
    R.append({'candidate': 'Developers\' donations to nonprofits during project approvals (Form 3500)',
              'result': {'filings': int(len(dev))}, 'decision': 'dropped', 'reason': 'Too few filings with usable amounts (totals are free text) to support a finding.'})
    b = cb.ballot_rows()
    tech = b[b.sector == 'tech'].groupby(b.year >= 2018).amount.sum()
    tot = b.groupby(b.year >= 2018).amount.sum()
    R.append({'candidate': 'Tech companies\' share of ballot-measure money is rising',
              'result': {'tech_share_2010_2017': float(tech.get(False, 0) / tot[False]), 'tech_share_2018_2026': float(tech.get(True, 0) / tot[True])},
              'decision': 'dropped', 'reason': 'Flat, not rising: about a tenth of ballot money in both periods, and dominated by a few campaigns (a 2015 short-term-rental measure, a 2018 homelessness tax).'})
    c = cb.contrib()
    y26 = c[(c.recip_kind == 'ballot_measure') & (c.year == 2026) & (c.amount > 0)].amount.sum()
    R.append({'candidate': '2026 ballot-measure fundraising is on a record pace',
              'result': {'ballot_2026_to_date': float(y26)}, 'decision': 'dropped', 'reason': 'Partial year (through September); the November campaigns are still raising money.'})
    ai = b[b.donor_name.fillna('').str.upper().str.contains('OPENAI|ANTHROPIC')]
    R.append({'candidate': 'AI companies entered SF ballot politics in 2026',
              'result': {'n_contributions': int(len(ai)), 'total': float(ai.amount.sum())},
              'decision': 'dropped', 'reason': 'Two contributions are too thin for a finding; also, this analysis used Claude (Anthropic), so we avoid singling out AI companies on thin evidence.'})
    pc = pd.read_csv(os.path.join(DATA, 'raw', 'permit_consult_q.csv'), low_memory=False) if os.path.exists(os.path.join(DATA, 'raw', 'permit_consult_q.csv')) else None
    R.append({'candidate': 'Permit consultants\' disclosed activity (registration since 2021)',
              'result': {'quarterly_report_rows': None if pc is None else int(len(pc))}, 'decision': 'dropped',
              'reason': 'A new program with few years of data and no link to permit outcomes in the open data.'})
    bj = J('analysis/behested.json')
    R.append({'candidate': 'Behested payments concentrate in one mayor',
              'result': {'lee_total': [o for o in bj['officials'] if o['official'] == 'O:LEE|EDWIN'][0]['total'], 'form803_total': bj['by_form'][0]['sum']},
              'decision': 'folded', 'reason': 'True but a product of which filings are machine-readable (2015-2018); folded into the disclosure-gap card as context.'})
    ie_coms = cb.ie_committees_2024()
    a = c[c.year.isin([2023, 2024]) & (c.amount > 0) & ('C:' + c.filer_nid.astype(str)).isin(ie_coms) & ~c.is_individual]
    lab = pd.read_parquet(os.path.join(DATA, 'insights', 'sector_labels.parquet')).set_index('donor_name').sector
    s = a.groupby(a.donor_name.map(lab).fillna('unlabelled')).amount.sum().sort_values(ascending=False)
    R.append({'candidate': 'Who funds 2024 independent committees: labor vs business (organizations only)',
              'result': {k: float(v) for k, v in s.head(8).items()},
              'decision': 'folded', 'reason': 'Most organization money arrives through PACs whose own funders are not evident, so sector shares are unstable; individuals (69%) dominate and are covered by the concentration card.'})
    pb = pd.read_parquet(os.path.join(DATA, 'analysis', 'behested_pending_business.parquet'))
    rtb = J('redteam/redteam2.json')['rederivation']['behested_pending_business']
    R.append({'candidate': 'A quarter of behested payors had lobbying or a contract approval before the official\'s body within 12 months, between two base rates',
              'result': {'observed': rtb['observed_share'], 'base_active': rtb['base_rate_random_org_active_within_12m'], 'base_all': rtb['base_rate_random_org_ever_active'],
                         'observed_3610b_era': rtb['observed_by_form']['SFEC 3610(b) (2019+)']},
              'decision': 'dropped (after the Opus fairness review)',
              'reason': 'Fragile: the reading flips with the base rate chosen (9% vs 38%), and the measure misses most interested-party relationships (every SFEC-3610(b) payor was an '
                        'interested party by definition, yet only 23% show lobbying or an approval), so the share mostly reflects data coverage.'})
    json.dump({'as_of': cb.J('analysis/summary_numbers.json') and '2026-09-26', 'n_screened': len(R) + 16, 'published': 16, 'entries': R},
              open(OUT, 'w'), indent=1, default=float)
    for r in R:
        print(f"- [{r['decision']}] {r['candidate']}")
    print(f'{len(R)} candidates recorded; {len(R) + 16} screened in total')


if __name__ == '__main__':
    main()
