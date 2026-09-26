"""Screening record for candidate insights that were tested and NOT published, or folded into another card
(data/insights_work/insights_screening.json). Each entry has the test numbers and the reason. Published insights are
built by build_insights.py and verified by verify_insights.py.
Run: python3 pipeline/insights/screen_candidates.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd
import compute as C

OUT = os.path.join(C.WORK, 'insights_screening.json')


def rate(s, v='implemented'):
    return round(float((s == v).mean()), 4) if len(s) else None


def main():
    d = C.with_actions(C.recs())
    R = []
    cs = d[(d.source == 'csa') & (d.status != 'unknown')]
    cg = d[(d.source == 'cgj') & (d.status != 'unknown')]

    # 1 agreement predicts action
    R.append({'candidate': 'Agreement predicts action (implemented share by first response)',
              'result': {'csa': {a: {'n': int((cs.agreed == a).sum()), 'impl': rate(cs[cs.agreed == a].status)} for a in ('agree', 'partial', 'disagree')},
                         'cgj': {a: {'n': int((cg.agreed == a).sum()), 'impl': rate(cg[cg.agreed == a].status)} for a in ('agree', 'partial', 'disagree')}},
              'reason_dropped': 'Red team 2 showed the pooled 92% vs 6% is compositional and partly circular (a Grand Jury "will not" answer is usually also the final status). '
                                'The non-circular version ("requires further analysis" outcomes) is published as its own card.'})

    # 2 CSA disagreed yet implemented
    di = cs[(cs.agreed == 'disagree')]
    R.append({'candidate': 'Three in four CSA recommendations departments disagreed with were still implemented',
              'result': {'n': len(di), 'implemented': int((di.status == 'implemented').sum()),
                         'implemented_by_basis': di[di.status == 'implemented'].status_basis.value_counts().to_dict()},
              'reason_dropped': 'An artifact: almost all of these got "implemented" when the whole report was closed or dropped off the two-year list. Used as evidence in the report-closure card.'})

    # 3 promises reversed as a standalone card
    t = d[(d.source == 'cgj') & (d.status_basis == 'cgj_status_tracker') & (d.cgj_response == 'will_be_implemented')]
    rv = t[t.status == 'not_implementing']
    R.append({'candidate': '"Will be implemented" promises later reversed to "will not"',
              'result': {'n_promises': len(t), 'reversed': len(rv), 'reversed_by_dept': rv.dept.value_counts().head(8).to_dict(),
                         'excluding_board': {'n': int((t.dept != 'BOS').sum()), 'reversed': int((rv.dept != 'BOS').sum())}},
              'reason_dropped': 'Fragile as a story of broken promises: 45 of the reversals are the Board of Supervisors, which often "agreed via resolution" and later said it lacks '
                                'operational authority, and many others are respondents saying another department leads. Folded into the "requires further analysis" card as a check.'})

    # 4 funding asks refused more
    k = cg[cg.action.notna()]
    R.append({'candidate': 'Grand Jury asks that need new money are refused more often',
              'result': {'needs_money': {'n': int((k.new_money == True).sum()), 'impl': rate(k[k.new_money == True].status), 'will_not': rate(k[k.new_money == True].status, 'not_implementing')},  # noqa: E712
                         'no_money': {'n': int((k.new_money == False).sum()), 'impl': rate(k[k.new_money == False].status), 'will_not': rate(k[k.new_money == False].status, 'not_implementing')}},  # noqa: E712
              'reason_dropped': 'Did not hold: 41% vs 44% implemented. Reported as the surprise in the "law or governance" card.'})

    # 5 safety recommendations neglected
    R.append({'candidate': 'Grand Jury recommendations with life-safety or public-health stakes are neglected',
              'result': {'safety': {'n': int((k.safety_health == True).sum()), 'impl': rate(k[k.safety_health == True].status)},  # noqa: E712
                         'other': {'n': int((k.safety_health == False).sum()), 'impl': rate(k[k.safety_health == False].status)}},  # noqa: E712
              'reason_dropped': 'Did not hold: safety-flagged asks were implemented slightly more often. Used as a check on the emergency-water card.'})

    # 6 Police among the least audited
    t1 = C.coverage_table()
    t2 = C.coverage_table(unit='recs')
    t3 = C.coverage_table(src=('csa', 'bla', 'cgj'))
    names = [x for x in t1[t1.spend >= 1.5].index if x in C.dept_names() and x not in ('CITYWIDE', 'NONCITY', 'UNK')]
    R.append({'candidate': 'Police gets few Controller audits for its size',
              'result': {'reports_per_billion': {'POL': round(float(t1.loc['POL', 'per']), 2), 'median': round(float(t1.loc[names].per.median()), 2)},
                         'recs_per_billion': {'POL': round(float(t2.loc['POL', 'per']), 2), 'median': round(float(t2.reindex(names).per.median()), 2)},
                         'all_bodies_reports_per_billion': {'POL': round(float(t3.loc['POL', 'per']), 2), 'median': round(float(t3.reindex(names).per.median()), 2)}},
              'reason_dropped': 'Did not hold: Police is below the median on reports but above it on recommendations and with the Grand Jury included. Only the Port-vs-Fire contrast survived.'})

    # 7 time to fix by topic
    c = d[(d.source == 'csa') & (d.status == 'implemented') & d.months_to_close.notna()]
    R.append({'candidate': 'How long fixes take, by audit topic',
              'result': {'median_months_by_topic': {k_: float(v) for k_, v in c.groupby('topic').months_to_close.median().sort_values().items()},
                         'grand_jury_median_months_by_topic': {k_: float(v) for k_, v in d[(d.source == 'cgj') & (d.status == 'implemented')].groupby('topic').months_to_close.median().items()}},
              'reason_dropped': 'Grand Jury times are an artifact of annual tracker columns (about 18 months for every topic). For the Controller, most dates are whole-report closures, '
                                'so topic differences reflect which audits close late; published instead by kind of fix, marked fragile.'})

    # 8 Grand Jury responsiveness trend
    g = cg.assign(per=pd.cut(cg.year, [1995, 2004, 2008, 2012, 2016, 2020, 2026]).astype(str))
    R.append({'candidate': 'Grand Jury implementation rates are rising (or falling) over time',
              'result': {p: {'n': len(x), 'impl': rate(x.status)} for p, x in g.groupby('per')},
              'reason_dropped': 'No trend: the rate swings between about 33% and 59% by period, driven by which reports and respondents dominate each term.'})

    # 9 priority
    p = d[d.priority.notna() & (d.status != 'unknown')]
    R.append({'candidate': 'High-priority recommendations get done faster or more often',
              'result': {'rows_with_priority': int(d.priority.notna().sum()), 'by_priority': {k_: {'n': len(x), 'impl': rate(x.status)} for k_, x in p.groupby('priority')}},
              'reason_dropped': 'Too few rows carry an auditor priority (about 3%), and almost none of those has a recorded status yet, so no contrast is testable.'})

    # 10 ethics topic after 2020
    csa = d[d.source == 'csa']
    R.append({'candidate': 'After the 2020 corruption cases, Controller audits shifted to ethics and contracting',
              'result': {'ethics_share_2015_19': round(float((csa[csa.year.between(2015, 2019)].topic == 'ethics').mean()), 4),
                         'ethics_share_2020_26': round(float((csa[csa.year >= 2020].topic == 'ethics').mean()), 4),
                         'ethics_recs_2020_26': int(((csa.year >= 2020) & (csa.topic == 'ethics')).sum())},
              'reason_dropped': 'The shift is real but small in counts (a few dozen recommendations) and is carried by the Public Integrity series, which has its own card.'})

    # 11 self-report vs verified, per recommendation
    fo = json.load(open(os.path.join(C.WORK, 'field_followups.json')))
    R.append({'candidate': 'Per recommendation: department self-report vs auditor finding',
              'result': {'memos': len(fo), 'memos_stating_self_reported_count': sum(1 for v in fo.values() if v['n_dept_reported_implemented'] is not None),
                         'memos_scope_only_self_reported': sum(1 for v in fo.values() if v['scope'] == 'only_recs_dept_reported_implemented')},
              'reason_dropped': 'Most field memos do not state what the department had reported, so a recommendation-level gap cannot be measured; memo totals and the six memos '
                                'limited to self-reported items are used in the report-closure card instead.'})

    # 12 dollars summed or largest as losses
    t = C.dollar_table()
    R.append({'candidate': 'The largest money losses found by auditors',
              'result': {'top10_kinds': t.head(10).kind.value_counts().to_dict()},
              'reason_dropped': 'The largest figures are mostly estimates, savings and cost growth, and the only overcharge appears twice; reframed as the dollar-figures card.'})

    # 13 BLA recommendations later repeated
    b = d[d.source == 'bla']
    later = d[d.repeat_of.isin(set(b.id))]
    R.append({'candidate': 'BLA recommendations are often made again later, suggesting they were not done',
              'result': {'later_rows': len(later), 'bla_recs_repeated': int(later.repeat_of.nunique()), 'bla_recs': len(b)},
              'reason_dropped': 'Too few (about 4% of BLA recommendations) and a repeat is not proof of non-implementation; kept as a check on the BLA card.'})

    json.dump({'as_of': C.AS_OF.strftime('%Y-%m-%d'), 'published': [s['id'] for s in __import__('spec').INSIGHTS], 'dropped_or_folded': R},
              open(OUT, 'w'), indent=1, default=str)
    print(f'wrote {OUT}: {len(R)} candidates dropped or folded')
    for r in R:
        print('-', r['candidate'])


if __name__ == '__main__':
    main()
