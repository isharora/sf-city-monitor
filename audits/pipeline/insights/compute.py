"""Build-side computations for the audits insights page (audits/data/site/insights/insights.json).

Each c_<key>() returns (V, CH): V = named scalar values used by the text templates in spec.py; CH = chart arrays.
Sources: the published export (data/site/recs, reports, repeats), the red team's refusal-reason classification
(data/redteam/reasons.json), this folder's classification of recommendation types and field follow-up reading
(data/insights_work/), the raw inventory, the PDF text (data/text/) and, read-only, the performance module's
spending cells. verify_insights.py recomputes every value with separate code.
"""
import os, re, json, glob
from collections import Counter, defaultdict
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # audits/
PROJ = os.path.dirname(ROOT)
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(DATA, 'site')
WORK = os.path.join(DATA, 'insights_work')
_c = {}


def once(k, f):
    if k not in _c:
        _c[k] = f()
    return _c[k]


def recs():
    def f():
        rows = []
        for fn in sorted(glob.glob(os.path.join(SITE, 'recs', 'recs_*.json'))):
            rows += json.load(open(fn))['rows']
        d = pd.DataFrame(rows)
        d['year'] = d.date_issued.str[:4].astype(int)
        dt = pd.to_datetime(d.date_issued)
        d['fy'] = dt.dt.year + (dt.dt.month >= 7).astype(int)
        d['akey'] = d.report + '|' + d.rec_number.astype(str) + '|' + d.text.fillna('').str[:200]
        return d
    return once('recs', f)


def reports():
    def f():
        r = pd.DataFrame(json.load(open(os.path.join(SITE, 'reports', 'reports.json')))['reports'])
        dt = pd.to_datetime(r.date)
        r['year'] = dt.dt.year
        r['fy'] = dt.dt.year + (dt.dt.month >= 7).astype(int)
        return r
    return once('reports', f)


def clusters():
    return once('cl', lambda: {c['cluster_id']: c for c in json.load(open(os.path.join(SITE, 'repeats', 'clusters.json')))['clusters']})


def reasons():
    return once('rs', lambda: pd.DataFrame(json.load(open(os.path.join(DATA, 'redteam', 'reasons.json')))['items']))


def actions():
    return once('act', lambda: json.load(open(os.path.join(WORK, 'rec_action_types.json'))))


def status_items():
    return once('si', lambda: json.load(open(os.path.join(DATA, 'work', 'status_items.json'))))


def page(doc, p):
    t = once('txt:' + doc, lambda: json.load(open(os.path.join(DATA, 'text', doc + '.json')))['pages'])
    return re.sub(r'\s+', ' ', t[p - 1])


HC_MIN = 0.8


def rate(n, d):
    return n / d if d else None


# ------------------------------------------------------------------------------------------------ 1 CSA output fell
AIRPORT_PORT = ('AIR', 'PRT')


def c_csa_output():
    d = recs()
    cs = d[(d.source == 'csa') & (d.in_csa_followup_scope == True)]  # noqa: E712
    per = cs.groupby('fy').size()
    allc = d[d.source == 'csa'].groupby('fy').size()
    r = reports()
    rc = r[r.source == 'csa']
    rep = rc.groupby('fy').size()
    ap = rc[rc.depts.apply(lambda l: any(x in l for x in AIRPORT_PORT))].groupby('fy').size()
    nap = rc[~rc.depts.apply(lambda l: any(x in l for x in AIRPORT_PORT))]
    nap_ids = set(nap.id)
    cs_nap = cs[cs.report.isin(nap_ids)].groupby('fy').size()
    A, B = range(2011, 2016), range(2021, 2026)
    avg = lambda s, yrs: float(sum(s.get(y, 0) for y in yrs) / len(yrs))
    V = dict(ours_a=avg(per, A), ours_b=avg(per, B), all_a=avg(allc, A), all_b=avg(allc, B),
             rep_a=avg(rep, A), rep_b=avg(rep, B), ap_a=avg(ap, A), ap_b=avg(ap, B),
             nap_a=avg(cs_nap, A), nap_b=avg(cs_nap, B), fy2026=float(per.get(2026, 0)), fy2025=float(per.get(2025, 0)))
    # CSA's own cumulative counts, parsed from its annual letters
    t15 = page('CON-2495', 3); t20 = page('CON-2886', 2); t25 = page('CON-3533', 2)
    n15 = int(re.search(r'of the ([\d,]+) recommendations issued from July 1, 2010, through June 30, 2015', t15).group(1).replace(',', ''))
    n20 = int(re.search(r'of the ([\d,]+) recommendations CSA issued from July 1, 2010, through June 30, 2020', t20).group(1).replace(',', ''))
    n25 = int(re.search(r'of the ([\d,]+) recommendations CSA issued from July 1, 2010, through June 30, 2025', t25).group(1).replace(',', ''))
    V.update(csa_n15=n15, csa_n20=n20, csa_n25=n25, csa_a=n15 / 5, csa_b=(n25 - n20) / 5)
    for k in ('ours', 'all', 'rep', 'nap', 'csa', 'ap'):
        V[k + '_chg'] = V[k + '_b'] / V[k + '_a'] - 1
    xs = list(range(2011, 2027))
    CH = dict(x=xs, scope=[int(per.get(y, 0)) for y in xs])
    return V, CH


# ------------------------------------------------------------------------------------------------ 2 CSA closure vs verification
BASIS_ORDER = [('csa_report_closed', 'Whole report closed by a CSA follow-up'),
               ('inferred_absent_from_open_over_2yrs_list', "Absent from CSA's two-year open list"),
               ('csa_field_followup', 'Auditor field follow-up'),
               ('pi_status_update', 'Public Integrity status update'),
               ('csa_followup_summary', 'CSA follow-up summary')]


def c_csa_closure():
    d = recs()
    cs = d[(d.source == 'csa') & (d.status != 'unknown')]
    impl = cs[cs.status == 'implemented']
    V = dict(n_known=len(cs), n_impl=len(impl), rate=len(impl) / len(cs),
             n_closed=int((impl.status_basis == 'csa_report_closed').sum()),
             n_inferred=int((impl.status_basis == 'inferred_absent_from_open_over_2yrs_list').sum()))
    V['share_closure'] = (V['n_closed'] + V['n_inferred']) / V['n_impl']
    rl = cs[~cs.status_basis.isin(['csa_report_closed', 'inferred_absent_from_open_over_2yrs_list'])]
    V.update(n_rl=len(rl), rate_rl=float((rl.status == 'implemented').mean()))
    ff = cs[cs.status_basis == 'csa_field_followup']
    V.update(n_ff=len(ff), rate_ff=float((ff.status == 'implemented').mean()))
    V['share_verified'] = float((impl.status_basis == 'csa_field_followup').mean())
    # field follow-up memos, every item the pipeline extracted from them (linked or not)
    items = [x for x in status_items() if x['status_doc_type'] == 'csa_field_followup' and x['status'] != 'unknown']
    c = Counter(x['status'] for x in items)
    n = sum(c.values())
    V.update(memo_docs=len({x['status_doc_id'] for x in items}), memo_n=n, memo_impl=c['implemented'] / n,
             memo_na=c['closed_other'] / n, memo_notdone=(n - c['implemented'] - c['closed_other']) / n)
    # the independent Opus reading of the same memos
    fo = json.load(open(os.path.join(WORK, 'field_followups.json')))
    ti = sum(v['csa_found_implemented_total'] or 0 for v in fo.values() if v['csa_found_implemented_total'] is not None)
    tp = sum(v['csa_found_partial_or_not_total'] or 0 for v in fo.values() if v['csa_found_implemented_total'] is not None)
    tn = sum(v['csa_found_not_applicable_total'] or 0 for v in fo.values() if v['csa_found_implemented_total'] is not None)
    V.update(opus_docs=sum(1 for v in fo.values() if v['csa_found_implemented_total'] is not None), opus_impl=ti / (ti + tp + tn))
    sr = [v for v in fo.values() if v['scope'] == 'only_recs_dept_reported_implemented' and v['csa_found_implemented_total'] is not None]
    V.update(sr_docs=len(sr), sr_n=sum((v['csa_found_implemented_total'] or 0) + (v['csa_found_partial_or_not_total'] or 0) + (v['csa_found_not_applicable_total'] or 0) for v in sr),
             sr_impl=sum(v['csa_found_implemented_total'] or 0 for v in sr), sr_notdone=sum(v['csa_found_partial_or_not_total'] or 0 for v in sr))
    dis = cs[cs.agreed == 'disagree']
    di = dis[dis.status == 'implemented']
    V.update(dis_n=len(dis), dis_impl=len(di), dis_impl_closure=int(di.status_basis.isin(['csa_report_closed', 'inferred_absent_from_open_over_2yrs_list']).sum()))
    CH = dict(cats=[lab for _, lab in BASIS_ORDER],
              vals=[100 * float((cs[cs.status_basis == b].status == 'implemented').mean()) for b, _ in BASIS_ORDER],
              n=[int((cs.status_basis == b).sum()) for b, _ in BASIS_ORDER])
    return V, CH


# ------------------------------------------------------------------------------------------------ 3 why the Grand Jury hears no
REASON_LABELS = [('not_our_authority', 'Not our authority or jurisdiction'), ('already_done_or_existing_process', 'Already done or covered by existing process'),
                 ('policy_disagreement', 'Disagrees on the merits'), ('alternative_approach', 'Taking a different approach'),
                 ('legal_or_contract_constraint', 'Legal, Charter or contract constraint'), ('no_reason_given', 'No reason given'),
                 ('cost_or_resources', 'Cost, staffing or funding')]


def c_cgj_reasons():
    rs = reasons()
    g = rs[rs.source == 'cgj']
    sh = g.primary.value_counts(normalize=True)
    V = dict(n=len(g), **{'s_' + k: float(sh.get(k, 0)) for k, _ in REASON_LABELS})
    V['s_four'] = V['s_not_our_authority'] + V['s_already_done_or_existing_process'] + V['s_legal_or_contract_constraint'] + V['s_cost_or_resources']
    hc = g[g.confidence >= HC_MIN]
    V['hc_min'] = HC_MIN
    shc = hc.primary.value_counts(normalize=True)
    V.update(n_hc=len(hc), hc_auth=float(shc.get('not_our_authority', 0)), hc_policy=float(shc.get('policy_disagreement', 0)))
    ex = g[~g.dept.isin(['BOS', 'MYR'])]
    she = ex.primary.value_counts(normalize=True)
    V.update(n_ex=len(ex), ex_auth=float(she.get('not_our_authority', 0)), ex_policy=float(she.get('policy_disagreement', 0)), ex_cost=float(she.get('cost_or_resources', 0)))
    c = rs[rs.source == 'csa']
    shs = c.primary.value_counts(normalize=True)
    V.update(n_csa=len(c), csa_none=float(shs.get('no_reason_given', 0)), csa_policy=float(shs.get('policy_disagreement', 0)))
    d = recs()
    yr = d.set_index('id').year
    g2 = g.assign(year=g.id.map(yr))
    late = g2[g2.year >= 2016]
    shl = late.primary.value_counts(normalize=True)
    V.update(n_late=len(late), late_auth=float(shl.get('not_our_authority', 0)), late_policy=float(shl.get('policy_disagreement', 0)),
             late_done=float(shl.get('already_done_or_existing_process', 0)), late_cost=float(shl.get('cost_or_resources', 0)))
    CH = dict(cats=[lab for _, lab in REASON_LABELS], vals=[100 * V['s_' + k] for k, _ in REASON_LABELS],
              n=[int((g.primary == k).sum()) for k, _ in REASON_LABELS])
    return V, CH


# ------------------------------------------------------------------------------------------------ 4 who says no
def c_cgj_who():
    d = recs()
    g = d[(d.source == 'cgj') & (d.status != 'unknown')]
    wn = g[g.status == 'not_implementing']
    by = wn.dept.value_counts()
    V = dict(n_known=len(g), n_impl=int((g.status == 'implemented').sum()), n_wn=len(wn),
             bos=int(by.get('BOS', 0)), myr=int(by.get('MYR', 0)))
    V['share_bm'] = (V['bos'] + V['myr']) / V['n_wn']
    ex = g[~g.dept.isin(['BOS', 'MYR'])]
    V.update(ex_impl=int((ex.status == 'implemented').sum()), ex_wn=int((ex.status == 'not_implementing').sum()))
    b = g[g.dept == 'BOS']
    V.update(bos_n=len(b), bos_rate=float((b.status == 'not_implementing').mean()))
    rest = g[~g.dept.isin(['BOS', 'MYR'])]
    V['rest_rate'] = float((rest.status == 'not_implementing').mean())
    gg = g.groupby(['report', 'rec_number'])
    anyimpl = gg.status.apply(lambda s: (s == 'implemented').any())
    V.update(n_distinct=int(len(anyimpl)), distinct_any=float(anyimpl.mean()))
    rs = reasons()
    bb = rs[(rs.source == 'cgj') & (rs.dept == 'BOS')]
    V['bos_auth'] = float((bb.primary == 'not_our_authority').mean())
    b0, b1 = b[b.year < 2012], b[b.year >= 2012]
    V.update(bos_early=float((b0.status == 'not_implementing').mean()), bos_late=float((b1.status == 'not_implementing').mean()))
    gl = g[g.year >= 2012]; wl = gl[gl.status == 'not_implementing']
    V['bm_late'] = float(wl.dept.isin(['BOS', 'MYR']).mean())
    V['n_bos_rs'] = len(bb)
    top = by.head(8)
    names = dept_names()
    CH = dict(cats=[names.get(k, k) for k in top.index], vals=[int(v) for v in top.values],
              n=[int((g.dept == k).sum()) for k in top.index])
    return V, CH


def dept_names():
    def f():
        m = json.load(open(os.path.join(SITE, 'meta.json')))
        return {v['id']: v['name'] for v in m['dimensions']['dept']['values']}
    return once('dn', f)


# ------------------------------------------------------------------------------------------------ 5 'requires further analysis'
FINAL = [('implemented', 'Implemented'), ('in_progress', 'In progress'), ('open', 'Open'), ('not_implementing', 'Will not be implemented'), ('closed_other', 'Closed otherwise')]


def c_further_analysis():
    d = recs()
    t = d[(d.source == 'cgj') & (d.status_basis == 'cgj_status_tracker')]
    fa = t[t.cgj_response == 'requires_further_analysis']
    wb = t[t.cgj_response == 'will_be_implemented']
    V = dict(fa_n=len(fa), fa_wn=int((fa.status == 'not_implementing').sum()), fa_impl=int((fa.status == 'implemented').sum()),
             wb_n=len(wb), wb_impl=int((wb.status == 'implemented').sum()), wb_wn=int((wb.status == 'not_implementing').sum()))
    V['fa_wn_share'] = V['fa_wn'] / V['fa_n']; V['fa_impl_share'] = V['fa_impl'] / V['fa_n']
    V['fa_open'] = V['fa_n'] - V['fa_wn'] - V['fa_impl'] - int((fa.status == 'closed_other').sum())
    wbx = wb[wb.dept != 'BOS']
    V.update(wbx_n=len(wbx), wbx_wn=int((wbx.status == 'not_implementing').sum()), wb_bos_wn=int(((wb.dept == 'BOS') & (wb.status == 'not_implementing')).sum()))
    ex = fa[~fa.dept.isin(['BOS', 'MYR'])]
    V.update(ex_n=len(ex), ex_wn=int((ex.status == 'not_implementing').sum()), ex_impl=int((ex.status == 'implemented').sum()))
    late = fa[fa.year >= 2012]
    V.update(late_n=len(late), late_wn=int((late.status == 'not_implementing').sum()), late_impl=int((late.status == 'implemented').sum()))
    di = fa.drop_duplicates(['report', 'rec_number'])
    V['fa_distinct'] = len(di)
    grp = fa.groupby(['report', 'rec_number']).status
    V['dist_any_wn'] = int(grp.apply(lambda s: (s == 'not_implementing').any()).sum())
    V['dist_any_impl'] = int(grp.apply(lambda s: (s == 'implemented').any()).sum())
    CH = dict(x=['"Will be implemented"', '"Requires further analysis"'])
    for k, lab in FINAL:
        CH[k] = [100 * float((wb.status == k).mean()), 100 * float((fa.status == k).mean())]
    return V, CH


# ------------------------------------------------------------------------------------------------ 8 repeats after "implemented"
TENANT_CLUSTERS = None


def tenant_clusters():
    """Clusters about tenant, concessionaire or garage-operator revenue reporting and payments (theme text match)."""
    pat = re.compile(r'tenant|concession|garage operator|monthly parker|parker|gross receipt|lessee|permittee', re.I)
    return {k for k, c in clusters().items() if c['used_for_repeat_of'] and pat.search(c['theme'])}


def validation():
    v = json.load(open(os.path.join(SITE, 'repeats', 'clusters.json')))['validation']
    h = json.load(open(os.path.join(DATA, 'validation', 'repeat_handcheck_summary.json')))['final_clustering']
    return dict(judge=float(v['judge_confirms_pos']), judge_n=int(v['pairs_judged_pos']), hand_ok=int(h['analyst_confirms']), hand_n=int(h['n']))


def c_repeat_after_impl():
    d = recs()
    idx = d.set_index('id')
    r = d[d.repeat_of.notna()].copy()
    r['pst'] = r.repeat_of.map(idx.status)
    kn = r[r.pst != 'unknown']
    V = dict(n_rep=len(r), n_kn=len(kn), n_pi=int((kn.pst == 'implemented').sum()), n_pwn=int((kn.pst == 'not_implementing').sum()),
             n_pu=int((r.pst == 'unknown').sum()))
    V['share'] = V['n_pi'] / V['n_kn']
    hc = kn[kn.repeat_confidence >= HC_MIN]
    V['hc_min'] = HC_MIN
    V.update(hc_n=len(hc), hc_share=float((hc.pst == 'implemented').mean()))
    tc = tenant_clusters()
    nt = kn[~kn.repeat_cluster.isin(tc)]
    V.update(nt_n=len(nt), nt_share=float((nt.pst == 'implemented').mean()), n_tc=len(tc))
    cc = kn[(kn.source == 'csa') & (kn.repeat_of.map(idx.source) == 'csa')]
    V.update(cc_n=len(cc), cc_share=float((cc.pst == 'implemented').mean()))
    V['cc_closure'] = float(cc.repeat_of.map(idx.status_basis).isin(['csa_report_closed', 'inferred_absent_from_open_over_2yrs_list']).mean())
    for s_ in ('csa', 'cgj'):
        x = d[(d.source == s_) & (d.status != 'unknown')]
        V['base_' + s_] = float((x.status == 'implemented').mean())
    cg = kn[kn.repeat_of.map(idx.source) == 'cgj']
    V.update(cg_n=len(cg), cg_share=float((cg.pst == 'implemented').mean()))
    V.update(validation())
    cats = [('implemented', 'Implemented'), ('not_implementing', 'Will not be implemented'), ('in_progress', 'In progress'), ('open', 'Open'), ('closed_other', 'Closed otherwise')]
    CH = dict(cats=[lab for _, lab in cats], vals=[int((kn.pst == k).sum()) for k, _ in cats])
    return V, CH


# ------------------------------------------------------------------------------------------------ 9 tenant reporting, most repeated
def cluster_rows(cid):
    d = recs()
    return d[d.id.isin(clusters()[cid]['members'])]


def c_tenant_reporting():
    d = recs()
    rows = []
    for k, c in clusters().items():
        if not c['used_for_repeat_of']:
            continue
        m = d[d.id.isin(c['members'])]
        rows.append((k, c['dept'], c['theme'], m.report.nunique(), int(m.year.min()), int(m.year.max()), len(m), int((m.status == 'implemented').sum())))
    t = pd.DataFrame(rows, columns=['cid', 'dept', 'theme', 'nrep', 'y0', 'y1', 'n', 'nimpl']).sort_values(['nrep', 'y1'], ascending=[False, False])
    top = t.head(10)
    tc = tenant_clusters()
    a = t[t.cid == 'C-0117'].iloc[0]
    V = dict(air_rep=int(a.nrep), air_y0=int(a.y0), air_y1=int(a.y1), air_n=int(a.n), air_impl=int(a.nimpl), air_span=int(a.y1 - a.y0),
             top10_tenant=int(top.cid.isin(tc).sum()), n_clusters=len(t))
    m = cluster_rows('C-0117')
    V['air_tenants'] = int(m.report.nunique())
    V['prt_chain'] = int(t[t.cid == 'C-0173'].nrep.iloc[0]); V['mta_chain'] = int(t[t.cid == 'C-0000'].nrep.iloc[0])
    V.update(validation())
    V['air_last'] = int(m.year.max())
    names = dept_names()
    CH = dict(cats=[f"{SHORT.get(r.dept, names.get(r.dept, r.dept))}: {LABEL.get(r.cid, r.theme)}" for r in top.itertuples()],
              vals=[int(v) for v in top.nrep], hl=[f"{SHORT.get(r.dept, names.get(r.dept, r.dept))}: {LABEL.get(r.cid, r.theme)}" for r in top.itertuples() if r.cid in tc],
              cids=list(top.cid))
    return V, CH


SHORT = {'AIR': 'Airport', 'PRT': 'Port', 'MTA': 'SFMTA', 'REC': 'Rec & Park', 'POL': 'Police', 'ART': 'Arts', 'DPW': 'Public Works'}
LABEL = {'C-0117': "tenants' certified revenue reports late or missing", 'C-0087': 'late fees on tenant payments not charged',
         'C-0173': "weak oversight of tenants' gross receipts", 'C-0000': 'garage operators not reconciling parking cards',
         'C-0001': 'monthly parking late fees not collected', 'C-0336': 'park evaluations inconsistent',
         'C-0006': 'operator expenses reimbursed without support', 'C-0119': 'tenants not keeping required records',
         'C-0174': 'tenants excluding items from gross receipts', 'C-0334': 'park evaluations not used to deploy staff'}


# ------------------------------------------------------------------------------------------------ 10 Police civilianization
def c_civilianization():
    m = cluster_rows('C-0241')
    r = reports().set_index('id')
    g = m.groupby('report').agg(n=('id', 'size'), year=('year', 'min'), src=('source', 'first')).reset_index().sort_values(['year', 'report']).set_index('report')
    V = dict(n_rep=int(len(g)), n_recs=int(len(m)), y0=int(g.year.min()), y1=int(g.year.max()))
    V['span'] = V['y1'] - V['y0']
    V['n_bodies'] = int(m.source.nunique())
    V.update(n_impl=int((m.status == 'implemented').sum()), n_wn=int((m.status == 'not_implementing').sum()), n_unk=int((m.status == 'unknown').sum()))
    V.update(validation())
    body = {'cgj': 'Civil Grand Jury', 'csa': 'Controller', 'bla': 'Budget and Legislative Analyst'}
    CH = dict(cats=[f"{int(y)} {body[s]} ({rid})" for rid, y, s in zip(g.index, g.year, g.src)], vals=[int(v) for v in g.n], ids=list(g.index))
    CH['hl'] = [CH['cats'][-1]]
    return V, CH


# ------------------------------------------------------------------------------------------------ 11 contractor evaluation
def c_contractor_eval():
    m = cluster_rows('C-0137')
    g = m.groupby('report').agg(n=('id', 'size'), year=('year', 'min'), src=('source', 'first')).reset_index().sort_values(['year', 'report']).set_index('report')
    V = dict(n_rep=int(len(g)), n_recs=int(len(m)), y0=int(g.year.min()), y1=int(g.year.max()), n_impl=int((m.status == 'implemented').sum()),
             n_unk=int((m.status == 'unknown').sum()))
    V['n_oth'] = V['n_recs'] - V['n_impl'] - V['n_unk']
    V.update(validation())
    V['span'] = V['y1'] - V['y0']
    body = {'cgj': 'Civil Grand Jury', 'csa': 'Controller', 'bla': 'Budget and Legislative Analyst'}
    CH = dict(cats=[f"{int(y)} {body[s]} ({rid})" for rid, y, s in zip(g.index, g.year, g.src)], vals=[int(v) for v in g.n], ids=list(g.index))
    CH['hl'] = [CH['cats'][-1]]
    return V, CH


# ------------------------------------------------------------------------------------------------ 12 audit coverage
def spend():
    def f():
        c = pd.DataFrame(json.load(open(os.path.join(PROJ, 'performance', 'data', 'site', 'spending', 'cells.json')))['cells'])
        return c
    return once('sp', f)


def coverage_table(y0=2011, y1=2025, src=('csa',), unit='reports', exclude_tenant=False):
    c = spend()
    sp = c[(c.fy >= y0) & (c.fy <= y1)].groupby('dept').actual.sum() / 1e9
    r = reports()
    r = r[(r.fy >= y0) & (r.fy <= y1) & r.source.isin(src)]
    if exclude_tenant:
        r = r[r.report_kind != 'financial_or_compliance_audit']
    if unit == 'reports':
        n = r.explode('depts').groupby('depts').id.nunique()
    else:
        d = recs()
        d = d[d.report.isin(set(r.id))]
        n = d.groupby('dept').size()
    t = pd.DataFrame({'spend': sp, 'n': n}).fillna(0)
    t = t[t.spend > 0]
    t['per'] = t.n / t.spend
    return t


def c_coverage():
    names = dept_names()
    t = coverage_table()
    t = t[t.index.isin([k for k in names if k not in ('CITYWIDE', 'NONCITY', 'UNK')])]
    big = t[t.spend >= COVER_MIN_B].sort_values('per')
    V = dict(n_big=len(big), min_b=COVER_MIN_B, fir_n=int(t.loc['FIR', 'n']), fir_sp=float(t.loc['FIR', 'spend']), prt_n=int(t.loc['PRT', 'n']),
             prt_sp=float(t.loc['PRT', 'spend']), air_n=int(t.loc['AIR', 'n']), air_sp=float(t.loc['AIR', 'spend']),
             fir_per=float(t.loc['FIR', 'per']), prt_per=float(t.loc['PRT', 'per']), air_per=float(t.loc['AIR', 'per']), med_per=float(big.per.median()),
             pol_n=int(t.loc['POL', 'n']), pol_per=float(t.loc['POL', 'per']))
    V['ratio'] = V['prt_per'] / V['fir_per']
    oth = reports()
    oth = oth[(oth.fy >= 2011) & (oth.fy <= 2025) & oth.source.isin(['cgj', 'bla'])]
    V['fir_oth'] = int(oth.depts.apply(lambda l: 'FIR' in l).sum())
    V['fir_rank'] = list(big.index).index('FIR') + 1
    V['prt_rank_desc'] = list(big.index[::-1]).index('PRT') + 1
    pr = reports()
    pr = pr[(pr.fy >= 2011) & (pr.fy <= 2025) & (pr.source == 'csa')]
    prt = pr[pr.depts.apply(lambda l: 'PRT' in l)]
    V['prt_fin'] = int((prt.report_kind == 'financial_or_compliance_audit').sum())
    air = pr[pr.depts.apply(lambda l: 'AIR' in l)]
    V['air_fin'] = int((air.report_kind == 'financial_or_compliance_audit').sum())

    def alt(**kw):
        x = coverage_table(**kw).reindex(big.index).fillna(0)
        x['per'] = x.n / x.spend
        return x.sort_values('per')
    t2 = alt(unit='recs')
    V.update(r_fir=float(t2.loc['FIR', 'per']), r_prt=float(t2.loc['PRT', 'per']), r_med=float(t2.per.median()), r_fir_rank=list(t2.index).index('FIR') + 1)
    t3 = alt(src=('csa', 'bla', 'cgj'))
    V.update(all_fir=float(t3.loc['FIR', 'per']), all_prt=float(t3.loc['PRT', 'per']), all_med=float(t3.per.median()), all_fir_rank=list(t3.index).index('FIR') + 1)
    t4 = alt(y0=2016)
    V.update(l_fir=float(t4.loc['FIR', 'per']), l_prt=float(t4.loc['PRT', 'per']), l_med=float(t4.per.median()), l_fir_rank=list(t4.index).index('FIR') + 1)
    t5 = alt(exclude_tenant=True)
    V.update(x_prt=float(t5.loc['PRT', 'per']), x_fir=float(t5.loc['FIR', 'per']), x_med=float(t5.per.median()), x_fir_rank=list(t5.index).index('FIR') + 1)
    V['ratio_min'] = min(V['ratio'], V['r_prt'] / V['r_fir'], V['all_prt'] / V['all_fir'], V['l_prt'] / V['l_fir'], V['x_prt'] / V['x_fir'])
    CH = dict(cats=[SHORTN.get(k, names.get(k, k)) for k in big.index], vals=[float(v) for v in big.per], n=[int(v) for v in big.n], codes=list(big.index))
    return V, CH


COVER_MIN_B = 1.5
SHORTN = {'MYR': 'Mayor (incl. MOHCD)', 'MTA': 'SFMTA', 'PUC': 'Public Utilities Commission', 'CHF': 'Children, Youth and Families', 'HOM': 'Homelessness and Supportive Housing',
          'TIS': 'Technology', 'HRD': 'Human Resources', 'REC': 'Recreation and Park', 'FIR': 'Fire Department'}


# ------------------------------------------------------------------------------------------------ 13 BLA untracked
def c_bla_untracked():
    d = recs()
    b = d[d.source == 'bla']
    V = dict(n=len(b), n_rep=int(b.report.nunique()), y0=int(b.year.min()), y1=int(b.year.max()),
             n_known=int((b.status != 'unknown').sum()),
             agree=int(b.agreed.isin(['agree', 'partial']).sum()))
    V['agree_share'] = V['agree'] / V['n']
    inv = json.load(open(os.path.join(DATA, 'raw', 'inventory.json')))
    bl = [x for x in inv if x['source'] == 'bla']
    V['bla_docs'] = len(bl)
    V['bla_fu_docs'] = sum(1 for x in bl if re.search(r'follow[- ]?up', x['title'], re.I))
    ids = set(b.id)
    later = d[d.repeat_of.isin(ids)]
    V.update(n_later=len(later), n_later_pred=int(later.repeat_of.nunique()))
    CH = dict(cats=[], vals=[], n=[])
    for s, lab in (('csa', "Controller's City Services Auditor"), ('cgj', 'Civil Grand Jury'), ('bla', 'Budget and Legislative Analyst')):
        x = d[d.source == s]
        CH['cats'].append(lab); CH['vals'].append(100 * float((x.status != 'unknown').mean())); CH['n'].append(len(x))
        V['known_' + s] = float((x.status != 'unknown').mean())
    return V, CH


# ------------------------------------------------------------------------------------------------ 14 frozen open items
AS_OF = pd.Timestamp('2026-09-26')


def c_frozen_open():
    d = recs()
    op = d[d.status.isin(['open', 'in_progress'])].copy()
    op['age'] = (AS_OF - pd.to_datetime(op.date_issued)).dt.days / 365.25
    op['lf'] = pd.to_datetime(op.last_followup)
    op['since'] = (AS_OF - op.lf).dt.days / 365.25
    o2 = op[op.age > 2]
    V = dict(n_open=len(op), n_o2=len(o2), n_stale=int((o2.since > 2).sum()), med_lf=float(o2.lf.dt.year.median()),
             n_cgj=int((o2.source == 'cgj').sum()), n_csa=int((o2.source == 'csa').sum()), n_o5=int((op.age > 5).sum()))
    V['share_stale'] = V['n_stale'] / V['n_o2']
    s5 = o2[o2.since > 5]
    V['n_stale5'] = len(s5)
    cg = o2[o2.source == 'cgj']
    V['cgj_stale'] = int((cg.since > 2).sum())
    cs = o2[o2.source == 'csa']
    V['csa_stale'] = int((cs.since > 2).sum())
    V['csa_out'] = int((cs.in_csa_followup_scope != True).sum())  # noqa: E712
    V['csa_pre'] = int((cs.date_issued < '2010-07-01').sum()); V['csa_post'] = V['n_csa'] - V['csa_pre']
    V['n2025'] = open_list_count('CON-3533', 2)
    pre = o2[o2.year < 2020]
    V.update(pre_n=len(pre), pre_stale=int((pre.since > 2).sum()))
    ys = list(range(int(o2.lf.dt.year.min()), 2027))
    CH = dict(x=ys, vals=[int((o2.lf.dt.year == y).sum()) for y in ys])
    return V, CH


# ------------------------------------------------------------------------------------------------ 15 largest dollar findings
KIND_LABEL = {'overpayment_or_loss': 'money lost or overpaid', 'unrecovered_or_uncollected_revenue': 'revenue not collected',
              'questioned_costs': 'costs questioned', 'potential_savings': 'possible savings', 'cost_overrun': 'cost overrun', 'other': 'other'}


def dollar_table():
    r = reports()
    rows = []
    for x in r.itertuples():
        if x.source == 'cgj':
            continue
        for i, f in enumerate(x.dollar_findings or []):
            rows.append(dict(rep=x.id, date=x.date, year=x.year, depts=x.depts, i=i, **{k: f.get(k) for k in ('amount_usd', 'kind', 'description', 'page')}))
    return pd.DataFrame(rows).sort_values('amount_usd', ascending=False)


def c_dollars():
    t = dollar_table()
    top = t.head(10)
    V = dict(n_find=len(t), n_rep=int(t.rep.nunique()), top_loss=int(top.kind.isin(['overpayment_or_loss']).sum()),
             top_est=int(top.kind.isin(['potential_savings', 'cost_overrun']).sum()))
    for k, row in enumerate(top.itertuples()):
        V[f'a{k}'] = float(row.amount_usd)
    seen = Counter(); cats = []
    for row in top.itertuples():
        cats.append(DOLLAR_LABELS[(row.rep, seen[row.rep])]); seen[row.rep] += 1
    V['n_overcharge'] = sum(1 for c in cats if c.endswith('(refund)'))
    cg = [f['amount_usd'] for x in reports().itertuples() if x.source == 'cgj' for f in (x.dollar_findings or [])]
    V['cgj_top'] = float(max(cg))
    V['a_rec'] = float(top[top.rep == 'CON-3093'].amount_usd.max())
    V['a_puc'] = float(top[top.rep == 'CON-3047'].amount_usd.max())
    V['a_co'] = float(top[top.rep == 'BLA-8208fb13'].amount_usd.max())
    m = re.search(r'Total \d+ [\d,]+ \$([\d,]+) \$([\d,]+) \d+%', page('BLA-8208fb13', 35))
    V['co_pct'] = int(m.group(2).replace(',', '')) / int(m.group(1).replace(',', ''))
    V['co_base'] = float(int(m.group(1).replace(',', '')))
    CH = dict(cats=cats, vals=[float(v) / 1e6 for v in top.amount_usd], hl=[c for c in cats if c.endswith('(refund)')],
              kinds=list(top.kind), reps=list(top.rep), pages=[int(p) for p in top.page])
    return V, CH


DOLLAR_LABELS = {
    ('BLA-8208fb13', 0): 'Change orders across public works contracts, FY2022–24 (cost growth)',
    ('CON-3047', 0): 'SFPUC bond-funded labor costs, 2003–08, supporting documents no longer available (unsupported)',
    ('CON-3093', 0): 'Recology settlement paid to ratepayers, incl. interest and penalties (refund)',
    ('CON-2951', 0): 'The same Recology settlement, earlier report: "more than $100 million" (refund)',
    ('BLA-cf5df80b', 0): 'SFMTA savings if costs matched peer transit systems (estimate)',
    ('BLA-9ed5f513', 0): 'Zoo management fee never adjusted for inflation since 1994 (estimate)',
    ('BLA-953573d3', 0): 'Rehab cost increases at two supportive-housing buildings (cost growth)',
    ('CON-1852', 0): 'Central Subway forecast below its baseline budget (savings)',
    ('CON-2934', 0): 'SFMTA engineering cost underestimates, three sample projects (estimate)',
    ('CON-3093', 1): 'Recology rate over- and under-recoveries, per year (estimate)'}


# ------------------------------------------------------------------------------------------------ 16 emergency firefighting water
AWSS = 'CGJ-2018-2019-a4a61434'


def c_awss():
    d = recs()
    a = d[d.report == AWSS]
    by = a.groupby('rec_number').status.agg(list)
    V = dict(n_rows=len(a), n_recs=int(a.rec_number.nunique()), n_resp=int(a.dept.nunique()))
    impl_recs = [k for k, v in by.items() if all(s == 'implemented' for s in v)]
    V['n_all_impl'] = len(impl_recs)
    V['r2_wn'] = int(((a.rec_number == 'R2') & (a.status == 'not_implementing')).sum()); V['r2_n'] = int((a.rec_number == 'R2').sum())
    V['r4_wn'] = int(((a.rec_number == 'R4') & (a.status == 'not_implementing')).sum()); V['r4_n'] = int((a.rec_number == 'R4').sum())
    k = with_actions(d)
    k = k[(k.source == 'cgj') & (k.status != 'unknown') & k.safety_health.notna()]
    V['sh_y'] = float((k[k.safety_health == True].status == 'implemented').mean())  # noqa: E712
    V['sh_n'] = float((k[k.safety_health == False].status == 'implemented').mean())  # noqa: E712
    V['n_sh'] = int((k.safety_health == True).sum())  # noqa: E712
    order = sorted(by.index, key=lambda s: int(s[1:]))
    CH = dict(x=order)
    for k, _ in FINAL[:4]:
        CH[k] = [int(sum(1 for s in by[r] if s == k)) for r in order]
    return V, CH


# ------------------------------------------------------------------------------------------------ 18 public integrity
def c_public_integrity():
    t = page('CON-3624', 3)
    m = re.search(r'Total (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)', t)
    tot, full, part, prog, wn, openn = (int(x) for x in m.groups())
    V = dict(tot=tot, full=full, part=part, prog=prog, wn=wn, open=openn)
    V['closed'] = full + part
    V['full_share'] = full / tot
    d = recs()
    pi = d[d.status_basis == 'pi_status_update']
    V.update(pi_rows=len(pi), pi_impl=int((pi.status == 'implemented').sum()))
    r = reports()
    V['n_pi_reports'] = int((r.report_kind == 'public_integrity_review').sum())
    CH = dict(cats=['Implemented and closed', 'Partially implemented and closed', 'Will not be implemented', 'In progress'], vals=[full, part, wn, prog])
    return V, CH


# ------------------------------------------------------------------------------------------------ 19 CSA two-year open list
OPEN_LISTS = [('CON-1772', 2014, 3), ('CON-2213', 2015, 5), ('CON-2339', 2016, 5), ('CON-2495', 2017, 4), ('CON-2625', 2018, 2), ('CON-2744', 2019, 2),
              ('CON-2886', 2020, 2), ('CON-3000', 2021, 2), ('CON-3145', 2022, 2), ('CON-3296', 2023, 2), ('CON-3422', 2024, 2), ('CON-3533', 2025, 2)]
OPEN_PAT = [r'total of (\d+) CSA recommendations that remain outstanding', r'(\d+) recommendations from [\w-]+ reports? (?:or|and) memorandums remain open',
            r'Of the [\d,]+ recommendations that have not been implemented, (\d+) \(', r'(\d+) (?:CSA )?recommendations, addressed to [\w-]+ departments, were (?:not implemented|unimplemented) more than two years']


def open_list_count(doc, p):
    t = page(doc, p)
    for pat in OPEN_PAT:
        m = re.search(pat, t)
        if m:
            return int(m.group(1))
    raise ValueError(doc)


def c_open_list():
    vals = [open_list_count(doc, p) for doc, _, p in OPEN_LISTS]
    d = recs()
    m = d[(d.report == 'CON-3045')]
    n_dph = int(re.search(r'Public Health (\d+) The department', page('CON-3533', 2)).group(1))
    V = dict(n_dph=n_dph, n2025=vals[-1], max_n=max(vals[:-1]), min_pre=min(vals[:-1]), max_year=OPEN_LISTS[vals.index(max(vals))][1], n2017=vals[3],
             dph_open=int(m.status.isin(['open', 'in_progress']).sum()), dph_n=len(m))
    CH = dict(x=[y for _, y, _ in OPEN_LISTS], vals=vals)
    return V, CH


# ------------------------------------------------------------------------------------------------ 20 "already implemented"
MIN_ANS = 90


def c_already():
    d = recs()
    g = d[(d.source == 'cgj') & d.cgj_response.notna()]
    V = dict(n=len(g), n_hbi=int((g.cgj_response == 'has_been_implemented').sum()))
    V['share'] = V['n_hbi'] / V['n']
    rs = reasons()
    V['n_wn_exist'] = int(((rs.source == 'cgj') & (rs.primary == 'already_done_or_existing_process')).sum())
    V['share_both'] = (V['n_hbi'] + V['n_wn_exist']) / V['n']
    per = [(2003, 2009), (2010, 2015), (2016, 2020), (2021, 2026)]
    CH = dict(x=[f'{a}–{str(b)[2:]}' for a, b in per], vals=[])
    for a, b in per:
        x = g[g.year.between(a, b)]
        CH['vals'].append(100 * float((x.cgj_response == 'has_been_implemented').mean()))
    V['p_min'] = min(CH['vals']) / 100; V['p_max'] = max(CH['vals']) / 100
    by = g.groupby('dept').cgj_response.apply(lambda s: (s == 'has_been_implemented').mean())
    cnt = g.dept.value_counts()
    big = by[cnt[cnt >= MIN_ANS].index]
    V['min_ans'] = MIN_ANS
    sb = sorted(big.values)
    V.update(n_mid=len(sb) - 2, mid_lo=float(sb[1]), mid_hi=float(sb[-2]))
    V['bos'] = float(by['BOS']); V['n_big'] = len(big); V['big_max'] = float(big.max()); V['big_max_dept'] = dept_names().get(big.idxmax(), big.idxmax())
    ex = g[g.dept != 'BOS']
    V['ex_share'] = float((ex.cgj_response == 'has_been_implemented').mean())
    return V, CH


# ------------------------------------------------------------------------------------------------ 3 what kind of ask gets done
ACTION_LABELS = [('training', 'Train staff or officials'), ('control_or_procedure', 'Fix a control or procedure'), ('study_or_plan', 'Study or plan'),
                 ('reporting_or_transparency', 'Report or publish information'), ('staffing_or_funding', 'Add staff, funding or equipment'),
                 ('it_system', 'Build or upgrade an IT system'), ('written_policy', 'Write or update a policy'),
                 ('law_or_governance_change', 'Change a law, charter or governance')]


def with_actions(d):
    a = actions()
    d = d.copy()
    for f in ('action', 'new_money', 'legislation', 'safety_health', 'confidence'):
        d[f] = d.akey.map(lambda k: a.get(k, {}).get(f))
    return d


def c_action_types():
    d = with_actions(recs())
    k = d[(d.source == 'cgj') & (d.status != 'unknown') & d.action.notna()]
    ir = lambda x: float((x.status == 'implemented').mean())
    V = dict(n=len(k), n_class=int(sum(1 for _ in actions())), rate=ir(k))
    for a_, _ in ACTION_LABELS:
        x = k[k.action == a_]
        V['r_' + a_] = ir(x); V['n_' + a_] = len(x)
    law = k[k.action == 'law_or_governance_change']
    V['law_wn'] = float((law.status == 'not_implementing').mean())
    V['bm_law_share'] = float(law.dept.isin(['BOS', 'MYR']).mean())
    V['ratio'] = V['r_control_or_procedure'] / V['r_law_or_governance_change']
    ex = k[~k.dept.isin(['BOS', 'MYR'])]
    V.update(ex_law=ir(ex[ex.action == 'law_or_governance_change']), ex_ctl=ir(ex[ex.action == 'control_or_procedure']))
    hc = k[k.confidence >= HC_MIN]
    V['hc_min'] = HC_MIN
    V.update(hc_n=len(hc), hc_law=ir(hc[hc.action == 'law_or_governance_change']), hc_rest=ir(hc[hc.action != 'law_or_governance_change']))
    V.update(leg_y=ir(k[k.legislation == True]), leg_n=ir(k[k.legislation == False]), n_leg=int((k.legislation == True).sum()))  # noqa: E712
    V.update(mon_y=ir(k[k.new_money == True]), mon_n=ir(k[k.new_money == False]), n_mon=int((k.new_money == True).sum()))  # noqa: E712
    cs = d[(d.source == 'csa') & (d.status != 'unknown') & d.action.notna()]
    mix = cs.action.value_counts(normalize=True)
    r = k.groupby('action').status.apply(lambda s: (s == 'implemented').mean())
    V['reweighted'] = float((r * mix).sum() / mix[r.index].sum())
    V['csa_rate'] = ir(cs)
    V['csa_rl'] = ir(cs[~cs.status_basis.isin(['csa_report_closed', 'inferred_absent_from_open_over_2yrs_list'])])
    hc_ = json.load(open(os.path.join(WORK, 'handcheck_actions.json')))
    V.update(hand_n=int(hc_['n']), hand_ok=int(hc_['plausible']))
    V['cgj_law_share'] = float((k.action == 'law_or_governance_change').mean()); V['csa_law_share'] = float((cs.action == 'law_or_governance_change').mean())
    V['cgj_fund_share'] = float((k.action == 'staffing_or_funding').mean()); V['csa_fund_share'] = float((cs.action == 'staffing_or_funding').mean())
    CH = dict(cats=[lab for _, lab in ACTION_LABELS], vals=[100 * V['r_' + a_] for a_, _ in ACTION_LABELS], n=[V['n_' + a_] for a_, _ in ACTION_LABELS])
    return V, CH


# ------------------------------------------------------------------------------------------------ 18 how long fixes take, by kind
TIME_LABELS = [('collect_or_recover_money', 'Collect or recover money'), ('control_or_procedure', 'Fix a control or procedure'), ('written_policy', 'Write or update a policy'),
               ('reporting_or_transparency', 'Report or publish information'), ('study_or_plan', 'Study or plan'), ('it_system', 'Build or upgrade an IT system'),
               ('staffing_or_funding', 'Add staff, funding or equipment')]


def c_time_by_type():
    d = with_actions(recs())
    c = d[(d.source == 'csa') & (d.status == 'implemented') & d.months_to_close.notna()]
    med = c.groupby('action').months_to_close.median(); cnt = c.groupby('action').size()
    V = dict(n=len(c), n_inf=int(((d.source == 'csa') & (d.status == 'implemented') & d.months_to_close.isna()).sum()))
    for a_, _ in TIME_LABELS:
        V['m_' + a_] = float(med[a_]); V['n_' + a_] = int(cnt[a_])
    rl = c[~c.status_basis.isin(['csa_report_closed', 'inferred_absent_from_open_over_2yrs_list'])]
    mr = rl.groupby('action').months_to_close.median(); nr = rl.groupby('action').size()
    V.update(rl_n=len(rl), rl_it=float(mr['it_system']), rl_ctl=float(mr['control_or_procedure']), rl_n_it=int(nr['it_system']),
             rl_col=float(mr['collect_or_recover_money']))
    x = c[c.action.isin(['it_system', 'control_or_procedure'])]
    g = x.groupby(['report', 'action']).months_to_close.median().unstack().dropna()
    V.update(wr_n=len(g), wr_same=float((g.it_system == g.control_or_procedure).mean()))
    t = c[c.topic.notna()]
    mt = t.groupby('topic').months_to_close.median()
    V.update(t_it=float(mt['it']), t_rev=float(mt['revenue']), t_con=float(mt['contracts']))
    CH = dict(cats=[lab for _, lab in TIME_LABELS], vals=[V['m_' + a_] for a_, _ in TIME_LABELS], n=[V['n_' + a_] for a_, _ in TIME_LABELS])
    return V, CH


COMPUTE = {k[2:]: v for k, v in globals().items() if k.startswith('c_') and callable(v)}
