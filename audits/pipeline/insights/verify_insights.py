"""Independent verification of audits/data/site/insights/insights.json.

Recomputes every value shown on the insights page with separate code (plain Python over the JSON source tables; it does
not import compute.py or pandas), then checks (any failure -> exit 1):
  1. every placeholder used in an insight's text or chart spec is recomputed here and agrees with the build value
     (0.5% relative or 0.005 absolute);
  2. each insight re-rendered with the recomputed values equals the published text exactly;
  3. every chart array agrees element by element (1% relative / 0.05 absolute), labels exactly;
  4. every quotation ({Q:...}) appears word for word on its cited page of the PDF text, and every quote placeholder
     used is registered; every dollar amount charted appears on its cited page;
  5. template text contains no literal numbers outside placeholders and allowed tokens;
  6. every source path resolves (files exist; report ids exist with the cited page);
  7. contract shape: required fields, themes, chart types and series lengths, verdicts, explore views and params,
     unique ids, ranks 1..n, title length;
  8. word claims in titles ("about a quarter", "most repeated", "20 times"...) hold for the recomputed values.
Writes data/insights_work/verify_insights.json.
"""
import os, sys, json, re, glob, statistics
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec  # templates only (text and chart specs); no computation

ROOT = os.path.dirname(os.path.dirname(HERE))
PROJ = os.path.dirname(ROOT)
DATA = os.path.join(ROOT, 'data')
OUTF = os.path.join(DATA, 'site', 'insights', 'insights.json')
VALS = os.path.join(DATA, 'insights_work', 'insights_values.json')
REPORT = os.path.join(DATA, 'insights_work', 'verify_insights.json')
AS_OF = date(2026, 9, 26)
_m = {}


def memo(k, f):
    if k not in _m:
        _m[k] = f()
    return _m[k]


def J(*p):
    return json.load(open(os.path.join(*p)))


def rows():
    def f():
        out = []
        for fn in sorted(glob.glob(os.path.join(DATA, 'site', 'recs', 'recs_*.json'))):
            out += J(fn)['rows']
        for r in out:
            y, mo = int(r['date_issued'][:4]), int(r['date_issued'][5:7])
            r['_y'], r['_fy'] = y, y + (1 if mo >= 7 else 0)
            r['_ak'] = f"{r['report']}|{r['rec_number']}|{(r['text'] or '')[:200]}"
        return out
    return memo('rows', f)


def byid():
    return memo('byid', lambda: {r['id']: r for r in rows()})


def reps():
    def f():
        out = J(DATA, 'site', 'reports', 'reports.json')['reports']
        for r in out:
            y, mo = int(r['date'][:4]), int(r['date'][5:7])
            r['_y'], r['_fy'] = y, y + (1 if mo >= 7 else 0)
        return out
    return memo('reps', f)


def clusters():
    return memo('cl', lambda: {c['cluster_id']: c for c in J(DATA, 'site', 'repeats', 'clusters.json')['clusters']})


def reason_items():
    return memo('rs', lambda: J(DATA, 'redteam', 'reasons.json')['items'])


def acts():
    return memo('act', lambda: J(DATA, 'insights_work', 'rec_action_types.json'))


def names():
    return memo('nm', lambda: {v['id']: v['name'] for v in J(DATA, 'site', 'meta.json')['dimensions']['dept']['values']})


def norm(s):
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-').replace('­', '').replace('‐', '-')
    return re.sub(r'\s+', ' ', s).strip()


def pages(doc):
    return memo('pg:' + doc, lambda: J(DATA, 'text', doc + '.json')['pages'])


def ptext(doc, p):
    return norm(pages(doc)[p - 1])


def share(xs, pred):
    xs = list(xs)
    return sum(1 for x in xs if pred(x)) / len(xs) if xs else None


def median(xs):
    return statistics.median(xs)


IMPL = lambda r: r['status'] == 'implemented'  # noqa: E731
WN = lambda r: r['status'] == 'not_implementing'  # noqa: E731


# ================================================================================================ recomputations
def v_csa_output():
    rs = [r for r in rows() if r['source'] == 'csa']
    scope = Counter(r['_fy'] for r in rs if r['in_csa_followup_scope'] is True)
    allc = Counter(r['_fy'] for r in rs)
    cr = [r for r in reps() if r['source'] == 'csa']
    rep = Counter(r['_fy'] for r in cr)
    ap_ids = {r['id'] for r in cr if 'AIR' in r['depts'] or 'PRT' in r['depts']}
    ap = Counter(r['_fy'] for r in cr if r['id'] in ap_ids)
    nap = Counter(r['_fy'] for r in rs if r['in_csa_followup_scope'] is True and r['report'] not in ap_ids and r['report'] in {x['id'] for x in cr})
    A, B = range(2011, 2016), range(2021, 2026)
    avg = lambda c, ys: sum(c.get(y, 0) for y in ys) / len(ys)  # noqa: E731
    V = dict(ours_a=avg(scope, A), ours_b=avg(scope, B), all_a=avg(allc, A), all_b=avg(allc, B), rep_a=avg(rep, A), rep_b=avg(rep, B),
             ap_a=avg(ap, A), ap_b=avg(ap, B), nap_a=avg(nap, A), nap_b=avg(nap, B), fy2026=scope.get(2026, 0), fy2025=scope.get(2025, 0))
    num = lambda doc, p, pat: int(re.search(pat, ptext(doc, p)).group(1).replace(',', ''))  # noqa: E731
    n15 = num('CON-2495', 3, r'98 percent of the ([\d,]+) recommendations issued from July 1, 2010, through June 30, 2015')
    n20 = num('CON-2886', 2, r'of the ([\d,]+) recommendations CSA issued from July 1, 2010, through June 30, 2020')
    n25 = num('CON-3533', 2, r'of the ([\d,]+) recommendations CSA issued from July 1, 2010, through June 30, 2025')
    V.update(csa_n15=n15, csa_n20=n20, csa_n25=n25, csa_a=n15 / 5, csa_b=(n25 - n20) / 5)
    for k in ('ours', 'all', 'rep', 'nap', 'csa', 'ap'):
        V[k + '_chg'] = V[k + '_b'] / V[k + '_a'] - 1
    xs = list(range(2011, 2027))
    return V, dict(x=xs, scope=[scope.get(y, 0) for y in xs])


BASIS = [('csa_report_closed', 'Whole report closed by a CSA follow-up'), ('inferred_absent_from_open_over_2yrs_list', "Absent from CSA's two-year open list"),
         ('csa_field_followup', 'Auditor field follow-up'), ('pi_status_update', 'Public Integrity status update'), ('csa_followup_summary', 'CSA follow-up summary')]
REPORT_LEVEL = ('csa_report_closed', 'inferred_absent_from_open_over_2yrs_list')


def v_csa_closure():
    cs = [r for r in rows() if r['source'] == 'csa' and r['status'] != 'unknown']
    im = [r for r in cs if IMPL(r)]
    V = dict(n_known=len(cs), n_impl=len(im), rate=len(im) / len(cs), n_closed=sum(r['status_basis'] == 'csa_report_closed' for r in im),
             n_inferred=sum(r['status_basis'] == 'inferred_absent_from_open_over_2yrs_list' for r in im))
    V['share_closure'] = (V['n_closed'] + V['n_inferred']) / len(im)
    rl = [r for r in cs if r['status_basis'] not in REPORT_LEVEL]
    V.update(n_rl=len(rl), rate_rl=share(rl, IMPL))
    ff = [r for r in cs if r['status_basis'] == 'csa_field_followup']
    V.update(n_ff=len(ff), rate_ff=share(ff, IMPL), share_verified=share(im, lambda r: r['status_basis'] == 'csa_field_followup'))
    it = [x for x in J(DATA, 'work', 'status_items.json') if x['status_doc_type'] == 'csa_field_followup' and x['status'] != 'unknown']
    c = Counter(x['status'] for x in it)
    n = len(it)
    V.update(memo_docs=len({x['status_doc_id'] for x in it}), memo_n=n, memo_impl=c['implemented'] / n, memo_na=c['closed_other'] / n,
             memo_notdone=1 - c['implemented'] / n - c['closed_other'] / n)
    fo = [v for v in J(DATA, 'insights_work', 'field_followups.json').values() if v['csa_found_implemented_total'] is not None]
    tot = lambda v: (v['csa_found_implemented_total'] or 0) + (v['csa_found_partial_or_not_total'] or 0) + (v['csa_found_not_applicable_total'] or 0)  # noqa: E731
    V.update(opus_docs=len(fo), opus_impl=sum(v['csa_found_implemented_total'] for v in fo) / sum(tot(v) for v in fo))
    sr = [v for v in fo if v['scope'] == 'only_recs_dept_reported_implemented']
    V.update(sr_docs=len(sr), sr_n=sum(tot(v) for v in sr), sr_impl=sum(v['csa_found_implemented_total'] for v in sr), sr_notdone=sum(v['csa_found_partial_or_not_total'] or 0 for v in sr))
    di = [r for r in cs if r['agreed'] == 'disagree' and IMPL(r)]
    V.update(dis_n=sum(r['agreed'] == 'disagree' for r in cs), dis_impl=len(di), dis_impl_closure=sum(r['status_basis'] in REPORT_LEVEL for r in di))
    CH = dict(cats=[b[1] for b in BASIS], vals=[100 * share([r for r in cs if r['status_basis'] == b], IMPL) for b, _ in BASIS],
              n=[sum(r['status_basis'] == b for r in cs) for b, _ in BASIS])
    return V, CH


REASONS = [('not_our_authority', 'Not our authority or jurisdiction'), ('already_done_or_existing_process', 'Already done or covered by existing process'),
           ('policy_disagreement', 'Disagrees on the merits'), ('alternative_approach', 'Taking a different approach'),
           ('legal_or_contract_constraint', 'Legal, Charter or contract constraint'), ('no_reason_given', 'No reason given'), ('cost_or_resources', 'Cost, staffing or funding')]
HCMIN = 0.8


def v_cgj_reasons():
    g = [x for x in reason_items() if x['source'] == 'cgj']
    sh = lambda xs, k: share(xs, lambda x: x['primary'] == k) or 0.0  # noqa: E731
    V = dict(n=len(g), hc_min=HCMIN)
    for k, _ in REASONS:
        V['s_' + k] = sh(g, k)
    V['s_four'] = V['s_not_our_authority'] + V['s_already_done_or_existing_process'] + V['s_legal_or_contract_constraint'] + V['s_cost_or_resources']
    hc = [x for x in g if x['confidence'] >= HCMIN]
    V.update(n_hc=len(hc), hc_auth=sh(hc, 'not_our_authority'), hc_policy=sh(hc, 'policy_disagreement'))
    ex = [x for x in g if x['dept'] not in ('BOS', 'MYR')]
    V.update(n_ex=len(ex), ex_auth=sh(ex, 'not_our_authority'), ex_policy=sh(ex, 'policy_disagreement'), ex_cost=sh(ex, 'cost_or_resources'))
    c = [x for x in reason_items() if x['source'] == 'csa']
    V.update(n_csa=len(c), csa_none=sh(c, 'no_reason_given'), csa_policy=sh(c, 'policy_disagreement'))
    late = [x for x in g if byid()[x['id']]['_y'] >= 2016]
    V.update(n_late=len(late), late_auth=sh(late, 'not_our_authority'), late_policy=sh(late, 'policy_disagreement'),
             late_done=sh(late, 'already_done_or_existing_process'), late_cost=sh(late, 'cost_or_resources'))
    return V, dict(cats=[l for _, l in REASONS], vals=[100 * V['s_' + k] for k, _ in REASONS], n=[sum(x['primary'] == k for x in g) for k, _ in REASONS])


def v_cgj_who():
    g = [r for r in rows() if r['source'] == 'cgj' and r['status'] != 'unknown']
    wn = [r for r in g if WN(r)]
    by = Counter(r['dept'] for r in wn)
    V = dict(n_known=len(g), n_impl=sum(map(IMPL, g)), n_wn=len(wn), bos=by['BOS'], myr=by['MYR'])
    V['share_bm'] = (by['BOS'] + by['MYR']) / len(wn)
    ex = [r for r in g if r['dept'] not in ('BOS', 'MYR')]
    V.update(ex_impl=sum(map(IMPL, ex)), ex_wn=sum(map(WN, ex)))
    b = [r for r in g if r['dept'] == 'BOS']
    V.update(bos_n=len(b), bos_rate=share(b, WN), rest_rate=share(ex, WN))
    grp = defaultdict(list)
    for r in g:
        grp[(r['report'], r['rec_number'])].append(r)
    V.update(n_distinct=len(grp), distinct_any=share(grp.values(), lambda rs: any(map(IMPL, rs))))
    bb = [x for x in reason_items() if x['source'] == 'cgj' and x['dept'] == 'BOS']
    V.update(n_bos_rs=len(bb), bos_auth=share(bb, lambda x: x['primary'] == 'not_our_authority'))
    V.update(bos_early=share([r for r in b if r['_y'] < 2012], WN), bos_late=share([r for r in b if r['_y'] >= 2012], WN))
    V['bm_late'] = share([r for r in wn if r['_y'] >= 2012], lambda r: r['dept'] in ('BOS', 'MYR'))
    top = sorted(by.items(), key=lambda t: (-t[1]))[:8]
    return V, dict(cats=[names()[k] for k, _ in top], vals=[v for _, v in top], n=[sum(r['dept'] == k for r in g) for k, _ in top])


FINAL = ['implemented', 'in_progress', 'open', 'not_implementing', 'closed_other']


def v_further_analysis():
    t = [r for r in rows() if r['source'] == 'cgj' and r['status_basis'] == 'cgj_status_tracker']
    fa = [r for r in t if r['cgj_response'] == 'requires_further_analysis']
    wb = [r for r in t if r['cgj_response'] == 'will_be_implemented']
    V = dict(fa_n=len(fa), fa_wn=sum(map(WN, fa)), fa_impl=sum(map(IMPL, fa)), wb_n=len(wb), wb_impl=sum(map(IMPL, wb)), wb_wn=sum(map(WN, wb)))
    V['fa_wn_share'] = V['fa_wn'] / len(fa); V['fa_impl_share'] = V['fa_impl'] / len(fa)
    V['fa_open'] = sum(r['status'] in ('open', 'in_progress') for r in fa)
    wbx = [r for r in wb if r['dept'] != 'BOS']
    V.update(wbx_n=len(wbx), wbx_wn=sum(map(WN, wbx)), wb_bos_wn=sum(WN(r) and r['dept'] == 'BOS' for r in wb))
    ex = [r for r in fa if r['dept'] not in ('BOS', 'MYR')]
    V.update(ex_n=len(ex), ex_wn=sum(map(WN, ex)), ex_impl=sum(map(IMPL, ex)))
    late = [r for r in fa if r['_y'] >= 2012]
    V.update(late_n=len(late), late_wn=sum(map(WN, late)), late_impl=sum(map(IMPL, late)))
    grp = defaultdict(list)
    for r in fa:
        grp[(r['report'], r['rec_number'])].append(r)
    V.update(fa_distinct=len(grp), dist_any_wn=sum(any(map(WN, v)) for v in grp.values()), dist_any_impl=sum(any(map(IMPL, v)) for v in grp.values()))
    CH = dict(x=['"Will be implemented"', '"Requires further analysis"'])
    for k in FINAL:
        CH[k] = [100 * share(wb, lambda r: r['status'] == k), 100 * share(fa, lambda r: r['status'] == k)]
    return V, CH


def validation_vals():
    v = J(DATA, 'site', 'repeats', 'clusters.json')['validation']
    h = J(DATA, 'validation', 'repeat_handcheck_summary.json')['final_clustering']
    return dict(judge=v['judge_confirms_pos'], judge_n=v['pairs_judged_pos'], hand_ok=h['analyst_confirms'], hand_n=h['n'])


TENANT_PAT = re.compile(r'tenant|concession|garage operator|monthly parker|parker|gross receipt|lessee|permittee', re.I)


def v_repeat_after_impl():
    B = byid()
    rp = [r for r in rows() if r['repeat_of']]
    kn = [r for r in rp if B[r['repeat_of']]['status'] != 'unknown']
    pst = lambda r: B[r['repeat_of']]['status']  # noqa: E731
    V = dict(n_rep=len(rp), n_kn=len(kn), n_pi=sum(pst(r) == 'implemented' for r in kn), n_pwn=sum(pst(r) == 'not_implementing' for r in kn),
             n_pu=len(rp) - len(kn), hc_min=HCMIN)
    V['share'] = V['n_pi'] / V['n_kn']
    hc = [r for r in kn if r['repeat_confidence'] >= HCMIN]
    V.update(hc_n=len(hc), hc_share=share(hc, lambda r: pst(r) == 'implemented'))
    tc = {k for k, c in clusters().items() if c['used_for_repeat_of'] and TENANT_PAT.search(c['theme'])}
    nt = [r for r in kn if r['repeat_cluster'] not in tc]
    V.update(n_tc=len(tc), nt_n=len(nt), nt_share=share(nt, lambda r: pst(r) == 'implemented'))
    cc = [r for r in kn if r['source'] == 'csa' and B[r['repeat_of']]['source'] == 'csa']
    cg = [r for r in kn if B[r['repeat_of']]['source'] == 'cgj']
    V['cc_closure'] = share(cc, lambda r: B[r['repeat_of']]['status_basis'] in REPORT_LEVEL)
    for s_ in ('csa', 'cgj'):
        V['base_' + s_] = share([r for r in rows() if r['source'] == s_ and r['status'] != 'unknown'], IMPL)
    V.update(cc_n=len(cc), cc_share=share(cc, lambda r: pst(r) == 'implemented'), cg_n=len(cg), cg_share=share(cg, lambda r: pst(r) == 'implemented'))
    V.update(validation_vals())
    cats = [('implemented', 'Implemented'), ('not_implementing', 'Will not be implemented'), ('in_progress', 'In progress'), ('open', 'Open'), ('closed_other', 'Closed otherwise')]
    return V, dict(cats=[l for _, l in cats], vals=[sum(pst(r) == k for r in kn) for k, _ in cats])


SHORT = {'AIR': 'Airport', 'PRT': 'Port', 'MTA': 'SFMTA', 'REC': 'Rec & Park'}
LABELS = {'C-0117': "tenants' certified revenue reports late or missing", 'C-0087': 'late fees on tenant payments not charged',
          'C-0173': "weak oversight of tenants' gross receipts", 'C-0000': 'garage operators not reconciling parking cards',
          'C-0001': 'monthly parking late fees not collected', 'C-0336': 'park evaluations inconsistent', 'C-0006': 'operator expenses reimbursed without support',
          'C-0119': 'tenants not keeping required records', 'C-0174': 'tenants excluding items from gross receipts', 'C-0334': 'park evaluations not used to deploy staff'}


def cluster_members(cid):
    ms = set(clusters()[cid]['members'])
    return [r for r in rows() if r['id'] in ms]


def v_tenant_reporting():
    info = []
    for k, c in clusters().items():
        if not c['used_for_repeat_of']:
            continue
        m = cluster_members(k)
        info.append((k, c['dept'], len({r['report'] for r in m}), max(r['_y'] for r in m)))
    info.sort(key=lambda t: (-t[2], -t[3]))
    top = info[:10]
    m = cluster_members('C-0117')
    ys = [r['_y'] for r in m]
    tc = {k for k, c in clusters().items() if c['used_for_repeat_of'] and TENANT_PAT.search(c['theme'])}
    V = dict(air_rep=len({r['report'] for r in m}), air_y0=min(ys), air_y1=max(ys), air_span=max(ys) - min(ys), air_n=len(m), air_impl=sum(map(IMPL, m)),
             top10_tenant=sum(k in tc for k, *_ in top), air_last=max(ys),
             prt_chain=len({r['report'] for r in cluster_members('C-0173')}), mta_chain=len({r['report'] for r in cluster_members('C-0000')}))
    V.update(validation_vals())
    lab = lambda k, d: f"{SHORT[d]}: {LABELS[k]}"  # noqa: E731
    return V, dict(cats=[lab(k, d) for k, d, *_ in top], vals=[n for _, _, n, _ in top], hl=[lab(k, d) for k, d, *_ in top if k in tc])


BODY = {'cgj': 'Civil Grand Jury', 'csa': 'Controller', 'bla': 'Budget and Legislative Analyst'}


def chain(cid):
    m = cluster_members(cid)
    g = defaultdict(list)
    for r in m:
        g[r['report']].append(r)
    order = sorted(g, key=lambda k: (min(r['_y'] for r in g[k]), k))
    cats = [f"{min(r['_y'] for r in g[k])} {BODY[g[k][0]['source']]} ({k})" for k in order]
    return m, g, cats, [len(g[k]) for k in order]


def v_civilianization():
    m, g, cats, vals = chain('C-0241')
    ys = [r['_y'] for r in m]
    V = dict(n_rep=len(g), n_recs=len(m), y0=min(ys), y1=max(ys), span=max(ys) - min(ys), n_bodies=len({r['source'] for r in m}),
             n_impl=sum(map(IMPL, m)), n_wn=sum(map(WN, m)), n_unk=sum(r['status'] == 'unknown' for r in m))
    V.update(validation_vals())
    return V, dict(cats=cats, vals=vals, hl=[cats[-1]])


def v_contractor_eval():
    m, g, cats, vals = chain('C-0137')
    ys = [r['_y'] for r in m]
    V = dict(n_rep=len(g), n_recs=len(m), y0=min(ys), y1=max(ys), span=max(ys) - min(ys), n_impl=sum(map(IMPL, m)), n_unk=sum(r['status'] == 'unknown' for r in m))
    V['n_oth'] = len(m) - V['n_impl'] - V['n_unk']
    V.update(validation_vals())
    return V, dict(cats=cats, vals=vals, hl=[cats[-1]])


SHORTN = {'MYR': 'Mayor (incl. MOHCD)', 'MTA': 'SFMTA', 'PUC': 'Public Utilities Commission', 'CHF': 'Children, Youth and Families', 'HOM': 'Homelessness and Supportive Housing',
          'TIS': 'Technology', 'HRD': 'Human Resources', 'REC': 'Recreation and Park', 'FIR': 'Fire Department'}


def spend_by_dept(y0, y1):
    c = J(PROJ, 'performance', 'data', 'site', 'spending', 'cells.json')['cells']
    s = defaultdict(float)
    for x in c:
        if y0 <= x['fy'] <= y1 and x['actual'] is not None:
            s[x['dept']] += x['actual']
    return {k: v / 1e9 for k, v in s.items()}


def cov(y0=2011, y1=2025, src=('csa',), unit='reports', excl=False):
    sp = spend_by_dept(y0, y1)
    rr = [r for r in reps() if y0 <= r['_fy'] <= y1 and r['source'] in src and not (excl and r['report_kind'] == 'financial_or_compliance_audit')]
    n = Counter()
    if unit == 'reports':
        for r in rr:
            for d in set(r['depts']):
                n[d] += 1
    else:
        ids = {r['id'] for r in rr}
        for r in rows():
            if r['report'] in ids:
                n[r['dept']] += 1
    return sp, n


def v_coverage():
    nm = names()
    sp, n = cov()
    big = [d for d in sp if d in nm and d not in ('CITYWIDE', 'NONCITY', 'UNK') and sp[d] >= 1.5]
    per = {d: n[d] / sp[d] for d in big}
    order = sorted(big, key=lambda d: per[d])
    V = dict(n_big=len(big), min_b=1.5, fir_n=n['FIR'], fir_sp=sp['FIR'], prt_n=n['PRT'], prt_sp=sp['PRT'], air_n=n['AIR'], air_sp=sp['AIR'],
             fir_per=per['FIR'], prt_per=per['PRT'], air_per=per['AIR'], med_per=median(per.values()), pol_n=n['POL'], pol_per=per['POL'])
    V['ratio'] = per['PRT'] / per['FIR']
    V['fir_oth'] = sum(1 for r in reps() if 2011 <= r['_fy'] <= 2025 and r['source'] in ('cgj', 'bla') and 'FIR' in r['depts'])
    V['_air_max'] = n['AIR'] == max(n[d] for d in big)
    V['fir_rank'] = order.index('FIR') + 1
    cr = [r for r in reps() if 2011 <= r['_fy'] <= 2025 and r['source'] == 'csa']
    V['prt_fin'] = sum('PRT' in r['depts'] and r['report_kind'] == 'financial_or_compliance_audit' for r in cr)

    def alt(**kw):
        s2, n2 = cov(**kw)
        p = {d: n2[d] / sp[d] for d in big}
        o = sorted(big, key=lambda d: p[d])
        return p, o
    p, o = alt(unit='recs'); V.update(r_fir=p['FIR'], r_prt=p['PRT'], r_med=median(p.values()), r_fir_rank=o.index('FIR') + 1)
    p, o = alt(src=('csa', 'bla', 'cgj')); V.update(all_fir=p['FIR'], all_prt=p['PRT'], all_med=median(p.values()), all_fir_rank=o.index('FIR') + 1)
    s4, n4 = cov(y0=2016)
    p4 = {d: n4[d] / s4[d] for d in big}; o4 = sorted(big, key=lambda d: p4[d])
    V.update(l_fir=p4['FIR'], l_prt=p4['PRT'], l_med=median(p4.values()), l_fir_rank=o4.index('FIR') + 1)
    p, o = alt(excl=True); V.update(x_prt=p['PRT'], x_fir=p['FIR'], x_med=median(p.values()), x_fir_rank=o.index('FIR') + 1)
    V['ratio_min'] = min(V['ratio'], V['r_prt'] / V['r_fir'], V['all_prt'] / V['all_fir'], V['l_prt'] / V['l_fir'], V['x_prt'] / V['x_fir'])
    return V, dict(cats=[SHORTN.get(d, nm[d]) for d in order], vals=[per[d] for d in order], n=[n[d] for d in order])


def v_bla_untracked():
    b = [r for r in rows() if r['source'] == 'bla']
    ys = [r['_y'] for r in b]
    V = dict(n=len(b), n_rep=len({r['report'] for r in b}), y0=min(ys), y1=max(ys), n_known=sum(r['status'] != 'unknown' for r in b))
    V['agree_share'] = share(b, lambda r: r['agreed'] in ('agree', 'partial'))
    ids = {r['id'] for r in b}
    later = [r for r in rows() if r['repeat_of'] in ids]
    V.update(n_later=len(later), n_later_pred=len({r['repeat_of'] for r in later}))
    inv = [x for x in J(DATA, 'raw', 'inventory.json') if x['source'] == 'bla']
    V.update(bla_docs=len(inv), bla_fu_docs=sum(bool(re.search(r'follow[- ]?up', x['title'], re.I)) for x in inv))
    CH = dict(cats=["Controller's City Services Auditor", 'Civil Grand Jury', 'Budget and Legislative Analyst'], vals=[], n=[])
    for s in ('csa', 'cgj', 'bla'):
        x = [r for r in rows() if r['source'] == s]
        V['known_' + s] = share(x, lambda r: r['status'] != 'unknown')
        CH['vals'].append(100 * V['known_' + s]); CH['n'].append(len(x))
    return V, CH


def years_between(a, b):
    return (b - a).days / 365.25


def v_frozen_open():
    op = [r for r in rows() if r['status'] in ('open', 'in_progress')]
    o2 = [r for r in op if years_between(date.fromisoformat(r['date_issued']), AS_OF) > 2]
    since = lambda r: years_between(date.fromisoformat(r['last_followup'][:10]), AS_OF)  # noqa: E731
    lf = [int(r['last_followup'][:4]) for r in o2]
    V = dict(n_open=len(op), n_o2=len(o2), n_stale=sum(since(r) > 2 for r in o2), med_lf=median(lf), n_cgj=sum(r['source'] == 'cgj' for r in o2),
             n_csa=sum(r['source'] == 'csa' for r in o2), n_stale5=sum(since(r) > 5 for r in o2))
    V['share_stale'] = V['n_stale'] / V['n_o2']
    V['cgj_stale'] = sum(since(r) > 2 for r in o2 if r['source'] == 'cgj'); V['csa_stale'] = sum(since(r) > 2 for r in o2 if r['source'] == 'csa')
    V['csa_pre'] = sum(r['source'] == 'csa' and r['date_issued'] < '2010-07-01' for r in o2); V['csa_post'] = V['n_csa'] - V['csa_pre']
    V['csa_out'] = sum(r['source'] == 'csa' and r['in_csa_followup_scope'] is not True for r in o2)
    V['n2025'] = v_open_list()[0]['n2025']
    pre = [r for r in o2 if r['_y'] < 2020]
    V.update(pre_n=len(pre), pre_stale=sum(since(r) > 2 for r in pre))
    ys = list(range(min(lf), 2027))
    c = Counter(lf)
    return V, dict(x=ys, vals=[c.get(y, 0) for y in ys])


DLAB = {('BLA-8208fb13', 0): 'Change orders across public works contracts, FY2022–24 (cost growth)',
        ('CON-3047', 0): 'SFPUC bond-funded labor costs, 2003–08, supporting documents no longer available (unsupported)',
        ('CON-3093', 0): 'Recology settlement paid to ratepayers, incl. interest and penalties (refund)', ('CON-2951', 0): 'The same Recology settlement, earlier report: "more than $100 million" (refund)',
        ('BLA-cf5df80b', 0): 'SFMTA savings if costs matched peer transit systems (estimate)', ('BLA-9ed5f513', 0): 'Zoo management fee never adjusted for inflation since 1994 (estimate)',
        ('BLA-953573d3', 0): 'Rehab cost increases at two supportive-housing buildings (cost growth)', ('CON-1852', 0): 'Central Subway forecast below its baseline budget (savings)',
        ('CON-2934', 0): 'SFMTA engineering cost underestimates, three sample projects (estimate)', ('CON-3093', 1): 'Recology rate over- and under-recoveries, per year (estimate)'}


def v_dollars():
    f = [(x['id'], d) for x in reps() if x['source'] != 'cgj' for d in (x['dollar_findings'] or [])]
    f.sort(key=lambda t: -t[1]['amount_usd'])
    top = f[:10]
    seen = Counter(); cats = []
    for rid, d in top:
        cats.append(DLAB[(rid, seen[rid])]); seen[rid] += 1
    V = dict(n_find=len(f), n_rep=len({rid for rid, _ in f}), n_overcharge=sum(c.endswith('(refund)') for c in cats),
             a_rec=max(d['amount_usd'] for rid, d in top if rid == 'CON-3093'), a_puc=max(d['amount_usd'] for rid, d in top if rid == 'CON-3047'),
             a_co=max(d['amount_usd'] for rid, d in top if rid == 'BLA-8208fb13'),
             co_base=float(re.search(r'Total 297 1,003 \$([\d,]+)', ptext('BLA-8208fb13', 35)).group(1).replace(',', '')),
             co_pct=(lambda m: int(m.group(2).replace(',', '')) / int(m.group(1).replace(',', '')))(re.search(r'Total 297 1,003 \$([\d,]+) \$([\d,]+)', ptext('BLA-8208fb13', 35))),
             cgj_top=max(d['amount_usd'] for x in reps() if x['source'] == 'cgj' for d in (x['dollar_findings'] or [])))
    V['_top'] = [(rid, d['page'], d['amount_usd']) for rid, d in top]
    return V, dict(cats=cats, vals=[d['amount_usd'] / 1e6 for _, d in top], hl=[c for c in cats if c.endswith('(refund)')])


def v_awss():
    a = [r for r in rows() if r['report'] == 'CGJ-2018-2019-a4a61434']
    by = defaultdict(list)
    for r in a:
        by[r['rec_number']].append(r['status'])
    order = sorted(by, key=lambda s: int(s[1:]))
    V = dict(n_rows=len(a), n_recs=len(by), n_resp=len({r['dept'] for r in a}), n_all_impl=sum(all(s == 'implemented' for s in v) for v in by.values()))
    for rn in ('R2', 'R4'):
        V[rn.lower() + '_wn'] = sum(s == 'not_implementing' for s in by[rn]); V[rn.lower() + '_n'] = len(by[rn])
    A = acts()
    k = [r for r in rows() if r['source'] == 'cgj' and r['status'] != 'unknown' and r['_ak'] in A]
    V['sh_y'] = share([r for r in k if A[r['_ak']]['safety_health']], IMPL); V['sh_n'] = share([r for r in k if not A[r['_ak']]['safety_health']], IMPL)
    V['n_sh'] = sum(bool(A[r['_ak']]['safety_health']) for r in k)
    CH = dict(x=order)
    for s in ('implemented', 'in_progress', 'open', 'not_implementing'):
        CH[s] = [sum(x == s for x in by[r]) for r in order]
    return V, CH


def v_public_integrity():
    m = re.search(r'Total (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)', ptext('CON-3624', 3))
    tot, full, part, prog, wn, _ = (int(x) for x in m.groups())
    V = dict(tot=tot, full=full, part=part, prog=prog, wn=wn, closed=full + part, full_share=full / tot)
    pi = [r for r in rows() if r['status_basis'] == 'pi_status_update']
    V.update(pi_rows=len(pi), pi_impl=sum(map(IMPL, pi)), n_pi_reports=sum(r['report_kind'] == 'public_integrity_review' for r in reps()))
    return V, dict(cats=['Implemented and closed', 'Partially implemented and closed', 'Will not be implemented', 'In progress'], vals=[full, part, wn, prog])


LISTS = [('CON-1772', 2014, 3), ('CON-2213', 2015, 5), ('CON-2339', 2016, 5), ('CON-2495', 2017, 4), ('CON-2625', 2018, 2), ('CON-2744', 2019, 2),
         ('CON-2886', 2020, 2), ('CON-3000', 2021, 2), ('CON-3145', 2022, 2), ('CON-3296', 2023, 2), ('CON-3422', 2024, 2), ('CON-3533', 2025, 2)]


def v_open_list():
    vals = []
    for doc, _, p in LISTS:
        t = ptext(doc, p)
        m = (re.search(r'(\d+) (?:CSA )?recommendations, addressed to \w+ departments, were (?:not implemented|unimplemented) more than two years', t)
             or re.search(r'recommendations that have not been implemented, (\d+) \(\d+ percent\)', t)
             or re.search(r'report having implemented \d+ percent of the [\d,]+ recommendations issued in that period, (\d+) recommendations', t)
             or re.search(r'a total of (\d+) CSA recommendations that remain outstanding', t))
        vals.append(int(m.group(1)))
    d = [r for r in rows() if r['report'] == 'CON-3045']
    mx = max(vals[:-1])
    V = dict(n2025=vals[-1], max_n=mx, min_pre=min(vals[:-1]), max_year=LISTS[vals.index(mx)][1], n2017=vals[3], dph_open=sum(r['status'] in ('open', 'in_progress') for r in d), dph_n=len(d),
             n_dph=int(re.search(r'Public Health (\d+) The department', ptext('CON-3533', 2)).group(1)))
    return V, dict(x=[y for _, y, _ in LISTS], vals=vals)


def v_already():
    g = [r for r in rows() if r['source'] == 'cgj' and r['cgj_response']]
    hb = lambda r: r['cgj_response'] == 'has_been_implemented'  # noqa: E731
    V = dict(n=len(g), n_hbi=sum(map(hb, g)), n_wn_exist=sum(x['source'] == 'cgj' and x['primary'] == 'already_done_or_existing_process' for x in reason_items()), min_ans=90)
    V['share'] = V['n_hbi'] / V['n']; V['share_both'] = (V['n_hbi'] + V['n_wn_exist']) / V['n']
    per = [(2003, 2009), (2010, 2015), (2016, 2020), (2021, 2026)]
    vals = [100 * share([r for r in g if a <= r['_y'] <= b], hb) for a, b in per]
    V.update(p_min=min(vals) / 100, p_max=max(vals) / 100)
    byd = defaultdict(list)
    for r in g:
        byd[r['dept']].append(r)
    big = {k: share(v, hb) for k, v in byd.items() if len(v) >= 90}
    k = max(big, key=big.get)
    sb = sorted(big.values())
    V.update(n_mid=len(sb) - 2, mid_lo=sb[1], mid_hi=sb[-2])
    V.update(bos=share(byd['BOS'], hb), n_big=len(big), big_max=big[k], big_max_dept=names()[k], ex_share=share([r for r in g if r['dept'] != 'BOS'], hb))
    return V, dict(x=[f'{a}–{str(b)[2:]}' for a, b in per], vals=vals)


ACT = [('training', 'Train staff or officials'), ('control_or_procedure', 'Fix a control or procedure'), ('study_or_plan', 'Study or plan'),
       ('reporting_or_transparency', 'Report or publish information'), ('staffing_or_funding', 'Add staff, funding or equipment'),
       ('it_system', 'Build or upgrade an IT system'), ('written_policy', 'Write or update a policy'), ('law_or_governance_change', 'Change a law, charter or governance')]


def v_action_types():
    A = acts()
    k = [r for r in rows() if r['source'] == 'cgj' and r['status'] != 'unknown' and r['_ak'] in A]
    a = lambda r: A[r['_ak']]  # noqa: E731
    V = dict(n=len(k), rate=share(k, IMPL), hc_min=HCMIN)
    for key, _ in ACT:
        x = [r for r in k if a(r)['action'] == key]
        V['r_' + key] = share(x, IMPL); V['n_' + key] = len(x)
    law = [r for r in k if a(r)['action'] == 'law_or_governance_change']
    V['law_wn'] = share(law, WN)
    V['bm_law_share'] = share(law, lambda r: r['dept'] in ('BOS', 'MYR'))
    ex = [r for r in k if r['dept'] not in ('BOS', 'MYR')]
    V['ex_law'] = share([r for r in ex if a(r)['action'] == 'law_or_governance_change'], IMPL)
    V['ex_ctl'] = share([r for r in ex if a(r)['action'] == 'control_or_procedure'], IMPL)
    hc = [r for r in k if a(r)['confidence'] >= HCMIN]
    V.update(hc_n=len(hc), hc_law=share([r for r in hc if a(r)['action'] == 'law_or_governance_change'], IMPL),
             hc_rest=share([r for r in hc if a(r)['action'] != 'law_or_governance_change'], IMPL))
    V.update(leg_y=share([r for r in k if a(r)['legislation']], IMPL), leg_n=share([r for r in k if not a(r)['legislation']], IMPL), n_leg=sum(bool(a(r)['legislation']) for r in k))
    V.update(mon_y=share([r for r in k if a(r)['new_money']], IMPL), mon_n=share([r for r in k if not a(r)['new_money']], IMPL), n_mon=sum(bool(a(r)['new_money']) for r in k))
    cs = [r for r in rows() if r['source'] == 'csa' and r['status'] != 'unknown' and r['_ak'] in A]
    mix = Counter(a(r)['action'] for r in cs)
    rates = {key: share([r for r in k if a(r)['action'] == key], IMPL) for key in {a(r)['action'] for r in k}}
    w = sum(mix[key] for key in rates)
    V['reweighted'] = sum(rates[key] * mix[key] for key in rates) / w
    V['csa_rate'] = share(cs, IMPL)
    V['csa_rl'] = share([r for r in cs if r['status_basis'] not in REPORT_LEVEL], IMPL)
    V['cgj_law_share'] = share(k, lambda r: a(r)['action'] == 'law_or_governance_change'); V['csa_law_share'] = share(cs, lambda r: a(r)['action'] == 'law_or_governance_change')
    h = J(DATA, 'insights_work', 'handcheck_actions.json')
    V.update(hand_n=len(h['items']), hand_ok=sum(i['verdict'] == 'plausible' for i in h['items']))
    return V, dict(cats=[l for _, l in ACT], vals=[100 * V['r_' + key] for key, _ in ACT], n=[V['n_' + key] for key, _ in ACT])


TACT = [('collect_or_recover_money', 'Collect or recover money'), ('control_or_procedure', 'Fix a control or procedure'), ('written_policy', 'Write or update a policy'),
        ('reporting_or_transparency', 'Report or publish information'), ('study_or_plan', 'Study or plan'), ('it_system', 'Build or upgrade an IT system'),
        ('staffing_or_funding', 'Add staff, funding or equipment')]


def v_time_by_type():
    A = acts()
    c = [r for r in rows() if r['source'] == 'csa' and IMPL(r) and r['months_to_close'] is not None]
    act = lambda r: A.get(r['_ak'], {}).get('action')  # noqa: E731
    V = dict(n=len(c), n_inf=sum(1 for r in rows() if r['source'] == 'csa' and IMPL(r) and r['months_to_close'] is None))
    for key, _ in TACT:
        x = [r['months_to_close'] for r in c if act(r) == key]
        V['m_' + key] = median(x); V['n_' + key] = len(x)
    rl = [r for r in c if r['status_basis'] not in REPORT_LEVEL]
    V.update(rl_n=len(rl), rl_it=median([r['months_to_close'] for r in rl if act(r) == 'it_system']),
             rl_ctl=median([r['months_to_close'] for r in rl if act(r) == 'control_or_procedure']))
    per = defaultdict(lambda: defaultdict(list))
    for r in c:
        if act(r) in ('it_system', 'control_or_procedure'):
            per[r['report']][act(r)].append(r['months_to_close'])
    both = [v for v in per.values() if len(v) == 2]
    V.update(wr_n=len(both), wr_same=share(both, lambda v: median(v['it_system']) == median(v['control_or_procedure'])))
    bt = defaultdict(list)
    for r in c:
        if r['topic']:
            bt[r['topic']].append(r['months_to_close'])
    V.update(t_it=median(bt['it']), t_rev=median(bt['revenue']), t_con=median(bt['contracts']))
    return V, dict(cats=[l for _, l in TACT], vals=[V['m_' + key] for key, _ in TACT], n=[V['n_' + key] for key, _ in TACT])


VERIFY = {k[2:]: v for k, v in globals().items() if k.startswith('v_') and callable(v)}

# ================================================================================================ word claims in titles
CLAIMS = {
    'csa_output': lambda V: 0.2 <= V['ours_b'] / V['ours_a'] <= 0.3 and 0.2 <= V['csa_b'] / V['csa_a'] <= 0.3,   # "about a quarter"
    'further_analysis': lambda V: V['fa_wn'] > V['fa_impl'],
    'cgj_reasons': lambda V: V['s_policy_disagreement'] < 0.25 and V['s_not_our_authority'] + V['s_already_done_or_existing_process'] > 0.5,  # "most cite authority or existing work"
    'awss': lambda V: V['r2_wn'] >= V['r2_n'] - 1 and V['r4_wn'] == V['r4_n'],
    'tenant_reporting': lambda V: V['air_rep'] >= max(len({r['report'] for r in cluster_members(k)}) for k, c in clusters().items() if c['used_for_repeat_of']),
    'dollars': lambda V: V['n_overcharge'] == 2,
    'already': lambda V: 0.2 <= V['share'] <= 0.3,
    'civilianization': lambda V: V['n_bodies'] == 3,
    'bla_untracked': lambda V: V['n_known'] == 0,
    'open_list': lambda V: V['n2025'] < V['min_pre'],
    'coverage': lambda V: V['fir_rank'] == 1 and V['_air_max'] and V['air_sp'] < spend_by_dept(2011, 2025)['PUC'],
}


# ================================================================================================ checks
def close(a, b, rel=0.005, ab=0.005):
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    if a is None or b is None:
        return a is b
    return abs(a - b) <= max(ab, rel * max(abs(a), abs(b)))


def placeholders(obj):
    out = set()

    def walk(o):
        if isinstance(o, str):
            out.update(m.group(1) for m in spec.PH.finditer(o))
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)
    return out


def quote_ids(obj):
    out = []

    def walk(o):
        if isinstance(o, str):
            out.extend(m.group(2) for m in spec.QPH.finditer(o))
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)
    return out


def chart_keys(obj):
    out = set()

    def walk(o):
        if isinstance(o, str) and o.startswith('@CH:'):
            out.add(o[4:])
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)
    return out


def check_quote(q):
    ps = q['page'] if isinstance(q['page'], list) else [q['page']]
    t = ' '.join(ptext(q['doc'], p) for p in ps)
    s = norm(q['text'])
    if s in t:
        return True, 'verbatim'
    if s in re.sub(r'(\w)- (\w)', r'\1\2', t) or s in re.sub(r'(\w)- (\w)', r'\1-\2', t):
        return True, 'verbatim after rejoining a line-break hyphen'
    return False, f"not found on {q['doc']} p.{ps}"


def literal_digits(tpl):
    bad = []

    def walk(o, path):
        if isinstance(o, str):
            if o.startswith('@CH:') or path.endswith('source') or '.explore' in path or path.endswith('.id') or path.endswith('.key'):
                return
            t = spec.PH.sub('', spec.QPH.sub('', o))
            for pat in spec.ALLOWED_DIGIT_TOKENS:
                t = re.sub(pat, '', t)
            if re.search(r'\d', t):
                bad.append(path)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{path}[{i}]')
        elif isinstance(o, dict):
            for k, v in o.items():
                if not (k == 'x' and isinstance(v, (int, float))):
                    walk(v, f'{path}.{k}')
    walk(tpl, tpl.get('key', 'intro') if isinstance(tpl, dict) else 'intro')
    return bad


DOC_RE = re.compile(r'\b((?:CON|BLA|CGJS?)-[\w-]+?)(?: pp?\.(\d+))?(?=[\s;,)#]|$)')
VIEWS = {'au-overview', 'au-status', 'au-time', 'au-agreement', 'au-repeat', 'au-open', 'au-reports', 'report', 'dept'}
PARAMS = {'years', 'source', 'dept', 'topic', 'id'}
TYPES = {'line', 'bar', 'hbar', 'dumbbell', 'slope', 'stacked', 'smallmultiples', 'scatter', 'waterfall'}
REQ = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags']


def check_source(src):
    probs = []
    for part in src.split(';'):
        part = part.strip()
        path = part.split('#')[0].split(' (')[0].strip()
        if '/' in path:
            full = os.path.join(PROJ, path)
            if not glob.glob(full):
                probs.append(f'missing file {path}')
        for m in DOC_RE.finditer(part):
            doc, p = m.group(1), m.group(2)
            if doc.startswith('C-'):
                continue
            if not os.path.exists(os.path.join(DATA, 'text', doc + '.json')):
                probs.append(f'unknown document {doc}')
            elif p and not (1 <= int(p) <= len(pages(doc))):
                probs.append(f'{doc} has no page {p}')
    return probs


def main():
    t0 = __import__('time').time()
    pub = J(OUTF)
    built = J(VALS)
    fails, warns, checked = [], [], Counter()
    by_id = {i['id']: i for i in pub['insights']}
    depts = set(names())
    # intro
    iv = {'n_ins': len(spec.INSIGHTS), 'n_rows': len(rows()), 'n_fragile': sum(t['robustness']['verdict'] == 'fragile' for t in spec.INSIGHTS)}
    if spec.render_str(spec.INTRO, iv) != pub['intro']:
        fails.append(('intro', 'intro text differs after re-render'))
    for k in ('n_ins', 'n_rows', 'n_fragile'):
        checked['values'] += 1
        if built['_intro']['V'][k] != iv[k]:
            fails.append(('intro', f'{k}: build {built["_intro"]["V"][k]} vs verify {iv[k]}'))
    if len(pub['insights']) != len(spec.INSIGHTS):
        fails.append(('file', 'insight count differs from spec'))
    for q_id, q in spec.QUOTES.items():
        ok, how = check_quote(q)
        checked['quotes'] += 1
        if not ok:
            fails.append((q_id, 'QUOTE ' + how))
    for rank, tpl in enumerate(spec.INSIGHTS, 1):
        iid, key = tpl['id'], tpl['key']
        V, CH = VERIFY[key]()
        bV, bCH = built[iid]['V'], built[iid]['CH']
        body = {k: v for k, v in tpl.items() if k != 'key'}
        for ph in sorted(placeholders(body)):
            checked['values'] += 1
            if ph not in V:
                fails.append((iid, f'value {ph} not recomputed by verifier'))
            elif not close(V[ph], bV.get(ph)):
                fails.append((iid, f'value {ph}: build {bV.get(ph)} vs verify {V[ph]}'))
        for ck in sorted(chart_keys(body)):
            checked['charts'] += 1
            a, b = CH.get(ck), bCH.get(ck)
            if a is None or b is None or len(a) != len(b):
                fails.append((iid, f'chart {ck}: length/shape differs')); continue
            for x, y in zip(a, b):
                if not (x == y if isinstance(x, str) or isinstance(y, str) else close(x, y, 0.01, 0.05)):
                    fails.append((iid, f'chart {ck}: {y} vs {x}')); break
        try:
            r = spec.render(body, V, CH)
        except KeyError as e:
            fails.append((iid, f'render failed: {e}')); continue
        pi = by_id.get(iid)
        if pi is None:
            fails.append((iid, 'missing from published file')); continue
        for f in ('title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags', 'theme'):
            checked['fields'] += 1
            if r.get(f) != pi.get(f):
                fails.append((iid, f'field {f} differs after re-render with verified values'))
        for q in quote_ids(body):
            if q not in spec.QUOTES:
                fails.append((iid, f'unregistered quote {q}'))
        for p in literal_digits(tpl):
            fails.append((iid, f'literal number in template at {p}'))
        for n in pi['numbers']:
            checked['sources'] += 1
            for p in check_source(n['source']):
                fails.append((iid, f'source: {p}'))
        if key == 'dollars':
            for rid, p, amt in V['_top']:
                checked['dollar_pages'] += 1
                t = ptext(rid, p)
                forms = {f'{amt:,.0f}', f'{amt / 1e6:.1f} million', f'{amt / 1e6:.2f} million', f'{amt / 1e6:.0f} million'}
                if not any(fm in t for fm in forms):
                    near = [q for q in (p - 1, p + 1) if 1 <= q <= len(pages(rid)) and any(fm in ptext(rid, q) for fm in forms)]
                    if near:
                        warns.append((iid, f'dollar amount {amt:,.0f} is on {rid} p.{near[0]}, not the exported p.{p}'))
                    else:
                        fails.append((iid, f'dollar amount {amt:,.0f} not found on {rid} p.{p} or adjacent pages'))
        if key in CLAIMS:
            checked['claims'] += 1
            if not CLAIMS[key](V):
                fails.append((iid, 'title word claim does not hold'))
        # contract shape
        for f in REQ:
            if f not in pi:
                fails.append((iid, f'missing field {f}'))
        if pi['rank'] != rank:
            fails.append((iid, 'rank out of order'))
        if pi['theme'] not in spec.THEMES:
            fails.append((iid, f'theme {pi["theme"]}'))
        if len(pi['title']) > 92:
            fails.append((iid, 'title over 92 characters'))
        ch = pi['chart']
        if ch['type'] not in TYPES:
            fails.append((iid, f'chart type {ch["type"]}'))
        nx = len(ch['x']['values'])
        for s in ch['series']:
            if len(s['values']) != nx or ('n' in s and len(s['n']) != nx):
                fails.append((iid, f'series {s["name"]} length {len(s["values"])} vs x {nx}'))
        if ch['type'] in ('bar', 'hbar') and len(ch['series']) == 1:
            hl = ch.get('highlight')
            for h in (hl if isinstance(hl, list) else [hl] if hl else []):
                if h not in ch['x']['values'] and str(h) not in [str(x) for x in ch['x']['values']]:
                    fails.append((iid, f'highlight {h} not a category'))
        if len(ch['series']) > 4 and not ch.get('highlight'):
            fails.append((iid, 'more than four series without a highlight'))
        rb = pi['robustness']
        if rb['verdict'] not in ('robust', 'fragile') or len(rb['checks']) < 3:
            fails.append((iid, 'robustness verdict or fewer than 3 checks'))
        failed_checks = [c for c in rb['checks'] if re.match(r'(did not|does not|sign flip|fail|not held|reversed)', c, re.I)]
        if rb['verdict'] == 'robust' and failed_checks:
            fails.append((iid, 'robust verdict with a failed check'))
        if rb['verdict'] == 'fragile' and not failed_checks:
            fails.append((iid, 'fragile verdict without a failed check'))
        ex = pi['explore']
        if ex['view'] not in VIEWS or any(k not in PARAMS for k in ex.get('params', {})):
            fails.append((iid, f'explore {ex}'))
        for d in pi['departments']:
            if d not in depts:
                fails.append((iid, f'unknown department {d}'))
        checked['insights'] += 1
    if len({i['id'] for i in pub['insights']}) != len(pub['insights']):
        fails.append(('file', 'duplicate ids'))
    if [i['rank'] for i in pub['insights']] != list(range(1, len(pub['insights']) + 1)):
        fails.append(('file', 'ranks are not 1..n'))
    for k in ('sample', 'as_of', 'dashboard', 'intro', 'insights'):
        if k not in pub:
            fails.append(('file', f'missing {k}'))
    res = {'checked': dict(checked), 'failures': [{'insight': a, 'problem': b} for a, b in fails], 'n_failures': len(fails),
           'warnings': [{'insight': a, 'note': b} for a, b in warns],
           'seconds': round(__import__('time').time() - t0, 1)}
    json.dump(res, open(REPORT, 'w'), indent=1)
    print(json.dumps(res['checked']), f'failures: {len(fails)}')
    for a, b in warns:
        print(' WARN', a, '|', b)
    for a, b in fails:
        print(' FAIL', a, '|', b)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
