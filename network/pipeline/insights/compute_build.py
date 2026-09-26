"""Build-side computations for the Money network insights page (network/data/site/insights/insights.json).

Each function c_<key>() returns (V, CH):
  V  = named scalar values used by the text templates in spec.py
  CH = chart arrays (x values and series) used by the chart templates in spec.py
Sources: the module pipeline's outputs (data/analysis/*.json|parquet, data/redteam/redteam2.json, data/site/analyses) where the
pipeline already computed the quantity, and the normalized source tables (data/interim, data/network/edges.parquet, data/er)
where it did not. verify_insights.py recomputes every value with its own code from the source tables.
Private individuals are never named: every quantity about individuals is an aggregate (counts, sums, shares).
"""
import os, sys, json, re, importlib.util
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DATA = os.path.join(ROOT, 'data')
INT, AN, RED, ER, NET, SITE = (os.path.join(DATA, d) for d in ('interim', 'analysis', 'redteam', 'er', 'network', 'site'))
INS = os.path.join(DATA, 'insights')

_c = {}


def once(k, f):
    if k not in _c:
        _c[k] = f()
    return _c[k]


def J(path):
    return once('J:' + path, lambda: json.load(open(os.path.join(DATA, path))))


def m6():
    def f():
        sp = importlib.util.spec_from_file_location('m6', os.path.join(ROOT, 'pipeline', '06_officials.py'))
        m = importlib.util.module_from_spec(sp)
        sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
        sp.loader.exec_module(m)
        return m
    return once('m6', f)


def contrib():
    def f():
        c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'),
                            columns=['filer_nid', 'date', 'amount', 'is_individual', 'donor_first', 'donor_last', 'donor_name', 'city', 'state',
                                     'zip5', 'person_key', 'org_key', 'recip_kind', 'recip_office', 'recip_candidate', 'is_city_candidate',
                                     'is_committee_donor'])
        c['year'] = c.date.dt.year
        return c
    return once('contrib', f)


def edges():
    return once('edges', lambda: pd.read_parquet(os.path.join(NET, 'edges.parquet')))


def labels():
    return once('labels', lambda: pd.read_parquet(os.path.join(NET, 'nodes.parquet'), columns=['node_id', 'label']).set_index('node_id').label)


def lob():
    """Lobbying contacts (edges) with department, subject, issue and target category."""
    def f():
        e = edges()
        l = e[e.edge_type == 'lobbying_contact'].copy()
        a = [json.loads(x) for x in l['attrs']]
        l['dept'] = [x.get('department') for x in a]
        l['subj'] = [x.get('subject') for x in a]
        l['issue'] = [x.get('issue') for x in a]
        l['year'] = l.date.dt.year
        m = pd.read_parquet(os.path.join(ER, 'lobby_official_map.parquet'))
        cat = m.drop_duplicates('official_id').set_index('official_id').category
        l['cat'] = l.target.map(cat).fillna('staff')
        return l.drop(columns=['attrs'])
    return once('lob', f)


def self_funding_mask(c):
    """Individual donor whose last name and first initial match the recipient committee's candidate (candidate's own money)."""
    rc = c.recip_candidate.fillna('').str.upper()
    last = c.donor_last.fillna('').str.upper().str.strip()
    first = c.donor_first.fillna('').str.upper().str.strip().str[:1]
    cand_last = rc.str.split(',').str[0].str.strip()
    cand_first = rc.str.split(',').str[1].fillna('').str.strip().str[:1]
    return c.is_individual & (last != '') & (last == cand_last) & (first == cand_first)


def cand_money(years):
    """Donations to City candidate committees: positive, not from other committees, not the candidate's own money."""
    c = contrib()
    k = c[c.is_city_candidate & (c.amount > 0) & ~c.is_committee_donor & c.year.isin(years)]
    return k[~self_funding_mask(k)]


# ------------------------------------------------------------------------------------------------------------ insights
MAYOR_YEARS = [2011, 2015, 2018, 2019, 2024]


def c_ie_vs_donors():
    cj = J('analysis/concentration.json')
    ie = {int(k): v for k, v in cj['independent_expenditures']['ie_on_city_candidates_by_year'].items()}
    cand = {int(k): v for k, v in cj['independent_expenditures']['candidate_committee_receipts_by_year'].items()}
    selff = {int(k): v for k, v in cj['candidate_self_funding_city_by_year'].items()}
    dup = {int(k): v for k, v in cj['independent_expenditures']['duplicate_f496_items_removed_by_year'].items()}
    top_self = max((r for r in cj['largest_self_funding'] if r['year'] == 2024), key=lambda r: r['amount'])
    V = {'ie_2024': ie[2024], 'cand_2024': cand[2024], 'ratio_2024': ie[2024] / cand[2024],
         'ie_2011': ie[2011], 'cand_2011': cand[2011], 'ratio_2011': ie[2011] / cand[2011],
         'ie_2018': ie[2018], 'cand_2018': cand[2018], 'ratio_2018': ie[2018] / cand[2018],
         'self_2024': selff[2024], 'self_top_2024': top_self['amount'],
         'cand_self_2024': cand[2024] + selff[2024], 'ratio_incl_self_2024': ie[2024] / (cand[2024] + selff[2024]),
         'ratio_incl_self_2011': ie[2011] / (cand[2011] + selff.get(2011, 0)),
         'dup_2024': dup.get(2024, 0.0), 'ratio_with_dups_2024': (ie[2024] + dup.get(2024, 0.0)) / cand[2024]}
    # Supervisor races only (Form 496 items coded to a Supervisor office; donations to Board of Supervisors candidate committees)
    iep = pd.read_parquet(os.path.join(INT, 'ie.parquet'))
    iep = iep[(iep.date.dt.year == 2024) & iep.office_code.isin(['BSU', 'CSU'])]
    raw = pd.read_csv(os.path.join(DATA, 'raw', 'cf_transactions.csv'), dtype=str,
                      usecols=['filing_date', 'filer_nid', 'form_type', 'transaction_id', 'calculated_amount', 'calculated_date', 'element_nid', 'transaction_last_name'])
    raw = raw[raw.form_type == 'F496']
    keep = set(raw.sort_values('filing_date').drop_duplicates(['filer_nid', 'transaction_id', 'calculated_amount', 'calculated_date', 'transaction_last_name'], keep='last').element_nid)
    iep = iep[iep.element_nid.isin(keep) | ~iep.element_nid.isin(set(raw.element_nid))]
    bos = cand_money([2024])
    bos = bos[bos.recip_office == 'Board of Supervisors']
    V['ie_bos_2024'] = float(iep.amount.sum())
    V['cand_bos_2024'] = float(bos.amount.sum())
    V['ratio_bos_2024'] = V['ie_bos_2024'] / V['cand_bos_2024']
    V['share_unlimited'] = (ie[2024] + top_self['amount']) / (ie[2024] + cand[2024] + selff[2024])
    CH = {'x': [str(y) for y in MAYOR_YEARS],
          'cand': [cand[y] / 1e6 for y in MAYOR_YEARS],
          'self': [selff.get(y, 0.0) / 1e6 for y in MAYOR_YEARS],
          'ie': [ie[y] / 1e6 for y in MAYOR_YEARS]}
    return V, CH


def donor_id(c):
    return np.where(c.is_individual, 'P:' + c.person_key.fillna(''), 'O:' + c.org_key.fillna(c.donor_name.fillna('')))


def top1(c):
    t = c.groupby('did').amount.sum().sort_values(ascending=False)
    k = max(1, int(np.ceil(len(t) * 0.01)))
    return float(t.head(k).sum() / t.sum()), int(len(t))


def ie_committees_2024():
    e = edges()
    ie = e[(e.edge_type == 'independent_expenditure') & (e.date.dt.year == 2024)]
    offs = pd.read_parquet(os.path.join(ER, 'officials.parquet'))
    city = set(offs[offs.category == 'candidate_or_elected'].official_id)
    return sorted(set(ie[ie.target.isin(city)].source))


def c_outside_concentration():
    c = contrib()
    c = c[(c.amount > 0) & c.year.isin([2024])].copy()
    c = c[~self_funding_mask(c)]
    c['did'] = donor_id(c)
    nc = c[~c.is_committee_donor]
    cand = nc[nc.is_city_candidate]
    ballot = nc[nc.recip_kind == 'ballot_measure']
    gp = nc[nc.recip_kind.isin(['general_purpose', 'candidate_pf']) & ~nc.is_city_candidate]
    coms = ie_committees_2024()
    a = contrib()
    a = a[(a.amount > 0) & a.year.isin([2023, 2024]) & ('C:' + a.filer_nid.astype(str)).isin(coms)].copy()
    a['did'] = donor_id(a)
    ind = a[a.is_individual].groupby('did').amount.sum()
    V = {}
    V['cand_top1'], V['cand_n'] = top1(cand)
    V['ballot_top1'], V['ballot_n'] = top1(ballot)
    V['gp_top1'], V['gp_n'] = top1(gp)
    V['ie_top1'], V['ie_n'] = top1(a)
    V['ie_coms'] = len(coms)
    V['ie_total'] = float(a.amount.sum())
    V['ie_ind_share'] = float(a[a.is_individual].amount.sum() / a.amount.sum())
    V['n_ind_100k'] = int((ind >= 100000).sum())
    V['share_ind_100k'] = float(ind[ind >= 100000].sum() / a.amount.sum())
    V['share_ind_under_1k'] = float(ind[ind < 1000].sum() / a.amount.sum())
    V['cand_org_share'] = float(cand[~cand.is_individual].amount.sum() / cand.amount.sum())
    # check: candidate committees' top-1% share in every year 2010-2026
    yrs = []
    for y in range(2010, 2027):
        k = contrib()
        k = k[(k.amount > 0) & (k.year == y) & k.is_city_candidate & ~k.is_committee_donor].copy()
        k = k[~self_funding_mask(k)]
        k['did'] = donor_id(k)
        yrs.append(top1(k)[0])
    V['cand_top1_min'], V['cand_top1_max'] = min(yrs), max(yrs)
    V['rt_crude'] = float(J('redteam/redteam2.json')['rederivation']['concentration_2024']['independent_top1pct_share_name_key'])
    # check: the four committees that spent most
    e = edges()
    ie = e[(e.edge_type == 'independent_expenditure') & (e.date.dt.year == 2024) & e.source.isin(coms)]
    big4 = list(ie.groupby('source').amount.sum().sort_values(ascending=False).head(4).index)
    b = a[('C:' + a.filer_nid.astype(str)).isin(big4)]
    ib = b[b.is_individual].groupby('did').amount.sum()
    V['big4_share_ind_100k'] = float(ib[ib >= 100000].sum() / b.amount.sum())
    CH = {'x': ['City candidate committees', 'Ballot-measure committees', 'General-purpose committees', 'Committees that spent independently on 2024 City races'],
          'top1': [V['cand_top1'] * 100, V['ballot_top1'] * 100, V['gp_top1'] * 100, V['ie_top1'] * 100]}
    return V, CH


SECTOR_NAMES = {'soda_tobacco_vape': 'Soda, tobacco and vape companies and trade groups', 'tech': 'Tech companies', 'real_estate': 'Real estate and development',
                'labor': 'Labor unions', 'business_group': 'Business groups and chambers', 'party_political': 'PACs and committees (funders not evident)',
                'nonprofit_advocacy': 'Nonprofits and advocacy groups', 'health': 'Health care', 'sports_hospitality': 'Sports, hotels and tourism',
                'utilities_waste': 'Utilities, waste and telecom', 'finance': 'Finance', 'other_business': 'Other businesses',
                'government': 'Government agencies', 'unknown': 'Unclassified organizations'}
STV_RX = r'AMERICAN BEVERAGE|JUUL|REYNOLDS|ALTRIA|PHILIP MORRIS|COCA|PEPSI|DR PEPPER|TOBACCO|VAPOR|VAPE'


def ballot_rows():
    c = contrib()
    b = c[(c.recip_kind == 'ballot_measure') & c.year.between(2010, 2026) & (c.amount > 0)].copy()
    lab = pd.read_parquet(os.path.join(INS, 'sector_labels.parquet')).set_index('donor_name').sector
    b['sector'] = np.where(b.is_individual, 'individuals', b.donor_name.map(lab).fillna('small_orgs'))
    return b


def c_ballot_sectors():
    b = ballot_rows()
    tot = b.amount.sum()
    s = b.groupby('sector').amount.sum()
    k0 = contrib()
    k0 = k0[k0.is_city_candidate & (k0.amount > 0) & k0.year.between(2010, 2026)]
    kc = k0[~self_funding_mask(k0)]
    cand = kc.amount.sum()  # transfers from other committees counted at the receiving committee, as for ballot committees
    order = [k for k in ['soda_tobacco_vape', 'tech', 'real_estate', 'labor', 'business_group', 'party_political', 'nonprofit_advocacy']]
    order = sorted(order, key=lambda k: -s.get(k, 0))
    V = {'ballot_total': float(tot), 'stv': float(s.get('soda_tobacco_vape', 0)), 'stv_share': float(s.get('soda_tobacco_vape', 0) / tot),
         'cand_total': float(cand), 'ballot_to_cand': float(tot / cand), 'ind': float(s.get('individuals', 0)), 'ind_share': float(s.get('individuals', 0) / tot),
         'tech': float(s.get('tech', 0)), 're': float(s.get('real_estate', 0)), 'labor': float(s.get('labor', 0))}
    stv = b[b.sector == 'soda_tobacco_vape']
    V['stv_n_orgs'] = int(stv.donor_name.nunique())
    rx = b[~b.is_individual & b.donor_name.fillna('').str.upper().str.contains(STV_RX)]
    V['stv_rx'] = float(rx.amount.sum())
    yrs = stv.groupby('year').amount.sum()
    V['stv_years_share'] = float(yrs[(yrs.index >= 2013) & (yrs.index <= 2019)].sum() / yrs.sum())
    V['tob_vape'] = float(stv[~stv.donor_name.fillna('').str.upper().str.contains('BEVERAGE|COCA|PEPSI')].amount.sum())
    V['bev'] = V['stv'] - V['tob_vape']
    V['ind_vs_cand'] = V['ind'] / V['cand_total']
    k = contrib()
    k = k[k.is_city_candidate & (k.amount > 0) & k.year.between(2010, 2026)]
    sf_ = self_funding_mask(k)
    V['cand_no_com'] = float(cand_money(range(2010, 2027)).amount.sum())
    cpi = pd.read_csv(os.path.join(DATA, 'raw', 'fred_CPIAUCSL.csv'))
    cpi['y'] = cpi.observation_date.str[:4].astype(int)
    cy = cpi.groupby('y').CPIAUCSL.mean()
    mult = (cy[2026] / cy)
    V['stv_real'] = float((stv.amount * stv.year.map(mult)).sum())
    V['cand_real'] = float((kc.amount * kc.year.map(mult)).sum())
    V['cand_incl_self'] = float(k[~k.is_committee_donor].amount.sum())
    V['stv_vs_self_total'] = V['stv'] / V['cand_incl_self']
    V['conf_cut'] = 0.6
    lab = pd.read_parquet(os.path.join(INS, 'sector_labels.parquet'))
    V['labelled_share_org'] = float(b[~b.is_individual & (b.sector != 'small_orgs')].amount.sum() / b[~b.is_individual].amount.sum())
    V['low_conf_share'] = float(b[b.donor_name.isin(set(lab[lab.confidence < 0.6].donor_name)) & ~b.is_individual].amount.sum() / tot)
    CH_ref = cand / 1e6
    CH = {'x': ['Individuals (all, aggregated)'] + [SECTOR_NAMES[k] for k in order],
          'm': [s.get('individuals', 0) / 1e6] + [s.get(k, 0) / 1e6 for k in order]}
    V['n_nonstv_bars'] = len(order)
    V['cand_total_m'] = CH_ref
    return V, CH


def c_lobbyist_ban():
    d = pd.read_parquet(os.path.join(AN, 'lobbyist_contributions.parquet'))
    d['year'] = d.date.dt.year
    p = d[d.amount > 0]
    yrs = list(range(2010, 2026))
    fl = p[p.contacts_with_that_agency_prior_90d > 0].groupby('year').size().reindex(yrs, fill_value=0)
    ot = p[p.contacts_with_that_agency_prior_90d == 0].groupby('year').size().reindex(yrs, fill_value=0)
    rt = J('redteam/redteam2.json')['rederivation']['lobbyist_contributions']['by_rule_period']
    pre = p[(p.year >= 2010) & (p.year <= 2017)]
    post = p[(p.year >= 2019) & (p.year <= 2025)]
    V = {'fl_2017': int(fl[2017]), 'fl_pre': int(rt['before_2018']['n_positive']), 'fl_pre_amt': float(rt['before_2018']['amount']),
         'post_pos': int(rt['from_2018']['n_positive_contributions']), 'post_pos_amt': float(rt['from_2018']['positive_amount']),
         'post_refunded': int(rt['from_2018']['positive_later_refunded_same_committee']),
         'fl_share_pre': float((pre.contacts_with_that_agency_prior_90d > 0).mean()),
         'avg_pre': float(len(pre) / 8), 'avg_post': float(len(post) / 7),
         'fl_post_1925': int((post.contacts_with_that_agency_prior_90d > 0).sum())}
    V['avg_chg'] = V['avg_post'] / V['avg_pre'] - 1
    # active lobbyists (distinct names reporting contacts) for a per-lobbyist rate
    lc = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'), columns=['date', 'lobbyistname'])
    lc['year'] = lc.date.dt.year
    act = lc.groupby('year').lobbyistname.nunique()
    V['act_1517'] = float(act.loc[2015:2017].mean()); V['act_1925'] = float(act.loc[2019:2025].mean())
    V['per_lob_1517'] = float(len(p[p.year.between(2015, 2017)]) / 3 / V['act_1517'])
    V['per_lob_1925'] = float(len(post) / 7 / V['act_1925'])
    # 180-day window and high-confidence-only checks
    m = m6()
    lc2 = pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'), columns=['date', 'lobbyistname', 'departmentname'])
    lc2['lob'] = 'L:' + lc2.lobbyistname.map(m.nk_from_lastfirst)
    lc2['office'] = lc2.departmentname.map(m.dept_office)
    lc2 = lc2.dropna(subset=['office'])
    by = {k: g for k, g in lc2.groupby('lob')}
    n180, pre180 = 0, 0
    for r in p[(p.year >= 2010) & (p.year != 2018)].itertuples():
        g = by.get(r.lobbyist_node)
        if g is None:
            continue
        if ((g.office == r.office) & (g.date <= r.date) & (g.date >= r.date - pd.Timedelta(days=180))).any():
            if r.year >= 2019:
                n180 += 1
            else:
                pre180 += 1
    V['post_180'] = n180
    V['pre_180'] = pre180
    V['hc_cut'] = 0.95
    hc = p[p.match_conf >= 0.95]
    V['hc_pre'] = int(((hc.contacts_with_that_agency_prior_90d > 0) & hc.year.between(2010, 2017)).sum())
    V['hc_post'] = int(((hc.contacts_with_that_agency_prior_90d > 0) & (hc.year >= 2019)).sum())
    CH = {'x': [int(y) for y in yrs], 'flagged': [int(v) for v in fl.values], 'other': [int(v) for v in ot.values]}
    return V, CH


def c_contractor_ban():
    rt = J('redteam/redteam2.json')['rederivation']['ban_base_rate']
    b = pd.read_parquet(os.path.join(AN, 'ban_base_rate_records.parquet'))
    x = b[~b.pub]
    ev, od = x[x.even], x[~x.even]
    bw = J('site/analyses/ban_window.json')['records']
    rv = [r for r in bw if r['review'] == 'appears_to_warrant_review']
    am = np.array([r['amount'] for r in rv], dtype=float)
    V = {'obs': float(x.inside.mean()), 'exp': float(x.e_weighted.mean()), 'n_rec': int(len(x)), 'n_con': int(x.contractor.nunique()),
         'diff_lo': float(rt['bootstrap_95ci']['difference'][0]), 'diff_hi': float(rt['bootstrap_95ci']['difference'][1]),
         'obs_even': float(ev.inside.mean()), 'exp_even': float(ev.e_weighted.mean()), 'obs_odd': float(od.inside.mean()), 'exp_odd': float(od.e_weighted.mean()),
         'obs12': float(x.inside12.mean()), 'exp12': float(x.e12_weighted.mean()),
         'obs_all': float(b.inside.mean()), 'exp_all': float(b.e_weighted.mean()), 'exp_unif': float(x.e_uniform.mean()),
         'n_review': len(rv), 'med_review': float(np.median(am)), 'share_500': float((am <= 500).mean()), 'max_review': float(am.max()),
         'sum_review': float(am.sum()), 'refund_seen': int(sum(1 for r in rv if r.get('possible_refund_seen'))),
         'placebo': float(rt['placebo_4y']['ratio_W0_to_4y_mean']), 'conf_min': 0.85}
    CH = {'x': ['All years', 'Election years', 'Off years'],
          'obs': [V['obs'] * 100, V['obs_even'] * 100, V['obs_odd'] * 100],
          'exp': [V['exp'] * 100, V['exp_even'] * 100, V['exp_odd'] * 100]}
    return V, CH


def behested_edges():
    e = edges()
    b = e[e.edge_type == 'behested_payment'].copy()
    a = [json.loads(x) for x in b['attrs']]
    b['form'] = [x.get('form') for x in a]
    b['payee_raw'] = [x.get('payee_raw') for x in a]
    b = b.sort_values('date')
    # official is null for SFEC-3600 commissioner rows; fill it so those distinct payments are not collapsed into one
    b['k'] = b.official.fillna('') + '|' + b.source.astype(str) + '|' + b.target.astype(str) + '|' + b.date.astype(str)
    b = b.drop_duplicates('k', keep='last')
    amb = b.payee_raw.fillna('').str.upper().str.contains('SEE ATTACHED')
    return b[~amb], b[amb]


def c_behested_vanished():
    bj = J('analysis/behested.json')
    yrs = list(range(2015, 2027))
    f803 = {r['y']: r['sum'] for r in bj['by_year'] if r['form'].startswith('FPPC')}
    b0, _ = behested_edges()
    loc = b0[~b0.form.str.startswith('FPPC')].groupby(b0.date.dt.year).amount.sum().to_dict()
    lee = [o for o in bj['officials'] if o['official'] == 'O:LEE|EDWIN'][0]
    tot803 = [f for f in bj['by_form'] if f['form'].startswith('FPPC')][0]
    t3610 = [f for f in bj['by_form'] if f['form'].startswith('SFEC 3610')][0]
    b, amb = behested_edges()
    lab = labels()
    y15 = b[b.date.dt.year == 2015]
    pay = y15.groupby(y15.target.map(lab)).amount.sum().sort_values(ascending=False)
    travel = float(y15[y15.target.map(lab).fillna('').str.upper().str.contains('TRAVEL')].amount.sum())
    V = {'y2015': f803.get(2015, 0) + loc.get(2015, 0), 'y2023': f803.get(2023, 0) + loc.get(2023, 0),
         'n2015': sum(r['size'] for r in bj['by_year'] if r['y'] == 2015), 'n2023': sum(r['size'] for r in bj['by_year'] if r['y'] == 2023),
         'tot803': tot803['sum'], 'n803': tot803['size'], 'lee': lee['total'], 'lee_n': lee['n'], 'lee_share': lee['total'] / tot803['sum'],
         't3610': t3610['sum'], 'n3610': t3610['size'], 'homeless_2015': float(pay.iloc[0]), 'travel_2015': travel,
         'amb_n': int(len(amb)), 'amb_amt': float(amb.amount.sum()), 'raw_rows': bj['raw_rows'], 'used_rows': int(len(b)), 'total_used': float(b.amount.sum())}
    V['y2015_top2_share'] = (V['homeless_2015'] + travel) / V['y2015']
    mayors = {'O:LEE|EDWIN', 'O:FARRELL|MARK', 'O:BREED|LONDON', 'O:LURIE|DANIEL'}
    V['mayor_after'] = int((b.official.isin(mayors) & (b.date > '2018-03-31')).sum())
    CH = {'x': [int(y) for y in yrs], 'f803': [f803.get(y, 0) / 1e6 for y in yrs], 'local': [loc.get(y, 0) / 1e6 for y in yrs]}
    return V, CH


def f1145():
    f = pd.read_parquet(os.path.join(INT, 'f1145.parquet'))
    f['amount'] = pd.to_numeric(f.contributionamount, errors='coerce')
    f = f.drop_duplicates(['docusignid', 'contributorname', 'contributiondate', 'contributionamount'])
    f['year'] = f.contributiondate.str[:4].astype(int)
    f['off'] = f.cityelectiveofficername.fillna('').str.strip().str.upper()
    return f


def c_form_1145():
    f = f1145()
    yrs = list(range(2019, 2027))
    by = f.groupby('year').amount.sum().reindex(yrs, fill_value=0)
    y26 = f[f.year == 2026]
    V = {'y2026': float(by[2026]), 'y2019': float(by[2019]), 'total': float(f.amount.sum()), 'n_rows': int(len(f)),
         'lurie_2026': float(y26[y26.off.str.contains('LURIE')].amount.sum()), 'n_2026': int(len(y26)),
         'n_off_all': int(f.off.str.replace(r'\s+', ' ', regex=True).nunique()), 'med_2026': float(y26.amount.median()),
         'n_com_2026': int(y26.committeename.nunique()), 'y2020': float(by[2020]),
         'orig_only_2026': float(y26[y26.filingtype.fillna('').str.upper().str.startswith('ORIG')].amount.sum())}
    V['lurie_share_2026'] = V['lurie_2026'] / V['y2026']
    V['y2026_ex'] = V['y2026'] - V['lurie_2026']
    y19 = f[f.year == 2019]
    V['peskin_breed_2019_share'] = float(y19[y19.off.str.contains('PESKIN|BREED')].amount.sum() / y19.amount.sum())
    CH = {'x': [str(y) for y in yrs], 'v': [float(v) / 1e6 for v in by.values]}
    return V, CH


def waivers():
    w = pd.read_parquet(os.path.join(INT, 'bp_waivers.parquet'))
    w['year'] = w.date_of_waiver_approval.str[:4].astype(int)
    return w


def c_waivers():
    w = waivers()
    yrs = [2023, 2024, 2025, 2026]
    by = w.groupby('year').size().reindex(yrs, fill_value=0)
    ag = w.agency.fillna('').str.upper()
    sub = w.subject.fillna('').str.upper()
    V = {'n': int(len(w)), 'n2025': int(by[2025]), 'n2023': int(by[2023]), 'n2026': int(by[2026]),
         'mayor': int(ag.str.contains('MAYOR').sum()), 'homeless': int(sub.str.contains('HOMELESS|SHELTER').sum()),
         'first': w.date_of_waiver_approval.min()[:10], 'n_subjects': int(sub.str[:40].nunique()),
         'upl_2025': int((w.date_uploaded.str[:4] == '2025').sum())}
    breed = w.date_of_waiver_approval.str[:10] < '2025-01-08'
    V['n_breed'] = int(breed.sum()); V['n_lurie'] = int((~breed).sum())
    V['mayor_breed'] = int((breed & ag.str.contains('MAYOR')).sum()); V['mayor_lurie'] = int((~breed & ag.str.contains('MAYOR')).sum())
    key = sub.str[:40]
    first_seen = ~key.duplicated()
    V['repeats'] = V['n'] - V['n_subjects']
    V['new_2025'] = int((first_seen & (w.year == 2025)).sum()); V['new_2324'] = int((first_seen & w.year.isin([2023, 2024])).sum())
    CH = {'x': [str(y) for y in yrs], 'v': [int(v) for v in by.values]}
    return V, CH


def meetings(l):
    """Distinct meetings: one client, one official (or staff group), one day. Several lobbyists often report the same meeting."""
    return l.drop_duplicates(['source', 'target', 'date'])


def c_pension_lobbying():
    L = lob()
    L = L[L.year.between(2015, 2025)]
    l = meetings(L)
    ret = l.dept.fillna('').str.upper().str.contains('RETIREMENT')
    sh = ret.groupby(l.year).mean()
    rraw = L.dept.fillna('').str.upper().str.contains('RETIREMENT')
    shr = rraw.groupby(L.year).mean()
    sb = (l.subj == 'City Employee Benefits').groupby(l.year).mean()
    r = l[ret]
    top = r.groupby('source').size().sort_values(ascending=False)
    lab = labels()
    x2 = l[~l.source.isin(top.head(2).index)]
    r2 = x2.dept.fillna('').str.upper().str.contains('RETIREMENT')
    mayor = l.dept.fillna('').str.upper().eq('MAYOR')
    V = {'s2015': float(sh[2015]), 's2022': float(sh[2022]), 's2025': float(sh[2025]), 'overall': float(ret.mean()),
         'n_meet': int(ret.sum()), 'n_clients': int(r.source.nunique()), 'n_people': int(r.target.nunique()),
         'raw2022': float(shr[2022]), 'sb2022': float(sb[2022]), 'no_top2_2022': float(r2[x2.year == 2022].mean()),
         'mayor_overall': float(mayor.mean()), 'top1_name': lab.get(top.index[0]), 'top2_name': lab.get(top.index[1]),
         'top2_share': float(top.head(2).sum() / top.sum()), 'elected_share': float((r.cat == 'elected').mean()),
         'n_meet_2022': int(ret[l.year == 2022].sum()), 'n_meet_2015': int(ret[l.year == 2015].sum()),
         'tot_2015': int((l.year == 2015).sum()), 'tot_2022': int((l.year == 2022).sum()), 'tot_2025': int((l.year == 2025).sum())}
    CH = {'x': [int(y) for y in range(2015, 2026)], 'share': [float(sh[y]) * 100 for y in range(2015, 2026)]}
    return V, CH


OFFICE_DEPTS = r'BOARD OF SUPERVISORS|^MAYOR$'


def lob_class(l):
    d = l.dept.fillna('').str.upper().str.strip()
    office = d.str.contains(OFFICE_DEPTS)
    return np.select([(l.cat == 'elected') | office, l.cat == 'appointed_exec'],
                     ['Elected officials and their offices', 'Department heads and commissioners'], 'Department staff')


SEG = ['Elected officials and their offices', 'Department heads and commissioners', 'Department staff']


def c_staff_targets():
    L = lob()
    L = L[L.year.between(2015, 2025)].copy()
    L['k'] = lob_class(L)
    l = meetings(L)
    tab = pd.crosstab(l.year, l.k, normalize='index').reindex(columns=SEG, fill_value=0)
    sh = l.k.value_counts(normalize=True)
    shr = L.k.value_counts(normalize=True)
    np_ = l[l.subj != 'Planning and Building Permits'].k.value_counts(normalize=True)
    V = {'el_off': float(sh[SEG[0]]), 'ex': float(sh[SEG[1]]), 'st': float(sh[SEG[2]]), 'dept': float(sh[SEG[1]] + sh[SEG[2]]),
         'el_only': float((l.cat == 'elected').mean()), 'permits': float((l.subj == 'Planning and Building Permits').mean()), 'n': int(len(l)),
         'el_off_raw': float(shr[SEG[0]]), 'dept_raw': float(shr[SEG[1]] + shr[SEG[2]]),
         'el_off_np': float(np_[SEG[0]]), 'dept_np': float(np_[SEG[1]] + np_[SEG[2]]),
         'min_el': float(tab[SEG[0]].min()), 'max_el': float(tab[SEG[0]].max()),
         'permits_dept': float(((l.subj == 'Planning and Building Permits') & (l.k != SEG[0])).sum() / (l.k != SEG[0]).sum())}
    old = lob()
    old = meetings(old[old.year.between(2010, 2014)].copy())
    V['el_off_old'] = float((lob_class(old) == SEG[0]).mean())
    CH = {'x': [int(y) for y in tab.index]}
    for i, s_ in enumerate(SEG):
        CH[f's{i}'] = [float(v) * 100 for v in tab[s_].values]
    return V, CH


AV_RX = r'autonom|driverless|robotaxi|self-driving|\bAVs?\b|waymo|zoox|cruise|tesla'
AV_CLIENT_RX = r'Waymo|Zoox|Cruise'


def c_av_lobbying():
    L = lob()
    lab = labels()
    L = L[L.year.between(2016, 2025)].copy()
    L['av'] = L.issue.fillna('').str.contains(AV_RX, case=False) | L.source.map(lab).fillna('').str.contains(AV_CLIENT_RX, case=False)
    l = meetings(L)
    yrs = list(range(2016, 2026))
    sh = l.groupby('year').av.mean()
    shr = L.groupby('year').av.mean()
    w_id = [k for k, v in lab.items() if v == 'Waymo LLC'][0]
    t25 = l[l.year == 2025].groupby('source').size().sort_values(ascending=False)
    a25 = l[(l.year == 2025) & l.av]
    w = l[(l.source == w_id) & l.year.between(2018, 2025)]
    wr = L[(L.source == w_id) & (L.year == 2025)]
    pay = edges()
    pay = pay[(pay.edge_type == 'lobbying_payment') & (pay.source == w_id)]
    V = {'s2019': float(sh[2019]), 's2025': float(sh[2025]), 's2024': float(sh[2024]), 'raw2025': float(shr[2025]), 'n2025': int(len(a25)),
         'waymo_rank_2025': int(list(t25.index).index(w_id) + 1), 'waymo_2025': int(t25[w_id]), 'first_2025': lab.get(t25.index[0]),
         'first_2025_n': int(t25.iloc[0]), 'waymo_share_av_2025': float((a25.source == w_id).mean()), 'waymo_raw_2025': int(len(wr)),
         'lob_per_meeting': float(len(wr) / t25[w_id]),
         'airport': float((w.dept.fillna('').str.upper() == 'AIRPORT').mean()),
         'mta': float(w.dept.fillna('').str.upper().str.contains('MUNICIPAL TRANSPORTATION').mean()),
         'w_elected': float((w.cat == 'elected').mean()), 'pay': float(pay.amount.sum()),
         'teamsters_av_2025': int((a25.source.map(lab) == 'TEAMSTER JOINT COUNCIL 7').sum())}
    r25 = L[L.year == 2025].groupby('source').size().sort_values(ascending=False)
    V['waymo_raw_rank_2025'] = int(list(r25.index).index(w_id) + 1)
    V['no_waymo_2025'] = float(l[(l.year == 2025) & (l.source != w_id)].av.mean())
    V['no_waymo_2019'] = float(l[(l.year == 2019) & (l.source != w_id)].av.mean())
    CH = {'x': [int(y) for y in yrs], 'share': [float(sh[y]) * 100 for y in yrs], 'raw': [float(shr[y]) * 100 for y in yrs]}
    return V, CH



def loc_class(d):
    sf = d.city.fillna('').str.upper().str.strip().isin(['SAN FRANCISCO', 'SF', 'S.F.']) | d.zip5.fillna('').str.startswith('941')
    ca = d.state.fillna('').str.upper().str.strip().eq('CA')
    return np.select([sf, ca], ['SF', 'CA'], 'OUT')


def c_outside_sf():
    c = contrib()
    c = c[c.year.between(2010, 2026) & (c.amount > 0)].copy()
    c['loc'] = loc_class(c)
    groups = {'cand': c[c.is_city_candidate], 'ballot': c[c.recip_kind == 'ballot_measure'],
              'gp': c[c.recip_kind.isin(['general_purpose', 'candidate_pf']) & ~c.is_city_candidate]}
    V, sh = {}, {}
    for k, g in groups.items():
        s = g.groupby('loc').amount.sum() / g.amount.sum()
        sh[k] = s
        for L in ('SF', 'CA', 'OUT'):
            V[f'{k}_{L}'] = float(s.get(L, 0))
    b = groups['ballot']
    bi = b[b.is_individual]
    V['ballot_ind_out'] = float(bi[bi['loc'] == 'OUT'].amount.sum() / bi.amount.sum())
    V['ballot_ind_notsf'] = float(bi[bi['loc'] != 'SF'].amount.sum() / bi.amount.sum())
    ns = b[~b.donor_name.fillna('').str.upper().str.contains(STV_RX)]
    V['ballot_nostv_notsf'] = float(ns[ns['loc'] != 'SF'].amount.sum() / ns.amount.sum())
    r = b[b.year >= 2019]
    V['ballot_1926_notsf'] = float(r[r['loc'] != 'SF'].amount.sum() / r.amount.sum())
    z = b.zip5.fillna('').str.startswith('941')
    V['ballot_zip_notsf'] = float(b[~z].amount.sum() / b.amount.sum())
    V['ballot_notsf'] = V['ballot_CA'] + V['ballot_OUT']
    V['cand_notsf'] = V['cand_CA'] + V['cand_OUT']
    CH = {'x': ['City candidate committees', 'Ballot-measure committees', 'General-purpose committees'],
          'SF': [V['cand_SF'] * 100, V['ballot_SF'] * 100, V['gp_SF'] * 100],
          'CA': [V['cand_CA'] * 100, V['ballot_CA'] * 100, V['gp_CA'] * 100],
          'OUT': [V['cand_OUT'] * 100, V['ballot_OUT'] * 100, V['gp_OUT'] * 100]}
    return V, CH


def c_lobby_clients_donors():
    e = edges()
    e = e[e.date.dt.year.between(2015, 2025)]
    lobc = meetings(e[e.edge_type == 'lobbying_contact']).groupby('source').size().sort_values(ascending=False)
    gave = set(e[(e.edge_type == 'contribution') & (e.amount > 0) & e.source.str.startswith('ORG:')].source) | set(e[e.edge_type == 'sponsors'].source)
    vend = set(e[e.edge_type.isin(['contract', 'vendor_payment', 'contract_approval'])].target)
    beh = set(e[e.edge_type == 'behested_payment'].source)

    def sh(ids, s):
        ids = set(ids)
        return len(ids & s) / len(ids)
    t100 = list(lobc.head(100).index)
    V = {'t100_gave': sh(t100, gave), 'all_gave': sh(lobc.index, gave), 'vend_gave': sh(vend, gave), 'n_vend': len(vend), 'n_clients': int(len(lobc)),
         't100_vend': sh(t100, vend), 't100_beh': sh(t100, beh), 't50_gave': sh(lobc.head(50).index, gave), 't200_gave': sh(lobc.head(200).index, gave),
         't100_contacts_share': float(lobc.head(100).sum() / lobc.sum())}
    c = contrib()
    c = c[c.year.between(2015, 2025) & (c.amount > 0) & ~c.is_individual]
    V['t100_n_gave'] = int(round(V['t100_gave'] * 100))
    V['ratio'] = V['t100_gave'] / V['vend_gave']
    # giving through committees they sponsor only
    sp = set(e[e.edge_type == 'sponsors'].source)
    V['t100_sponsor'] = sh(t100, sp)
    V['all_beh'] = sh(lobc.index, beh); V['all_vend'] = sh(lobc.index, vend); V['ratio_all'] = V['t100_gave'] / V['all_gave']
    CH = {'x': ['100 most active lobbying clients', 'All lobbying clients', 'Organizations paid by or contracting with the City'],
          'v': [V['t100_gave'] * 100, V['all_gave'] * 100, V['vend_gave'] * 100]}
    return V, CH


def c_behested_base_rate():
    pb = pd.read_parquet(os.path.join(AN, 'behested_pending_business.parquet'))
    rt = J('redteam/redteam2.json')['rederivation']['behested_pending_business']
    anyp = (pb.lobbied_same_official_12m + pb.lobbied_same_body_12m + pb.contract_approvals_same_body_12m) > 0
    V = {'obs': float(anyp.mean()), 'n': int(len(pb)), 'base_active': float(rt['base_rate_random_org_active_within_12m']),
         'base_all': float(rt['base_rate_random_org_ever_active']), 'dollar_share': float(pb[anyp].amount.sum() / pb.amount.sum()),
         'obs_803': float(anyp[pb.form.str.startswith('FPPC')].mean()), 'obs_3610': float(anyp[pb.form.str.startswith('SFEC 3610')].mean()),
         'same_official': float((pb.lobbied_same_official_12m > 0).mean()), 'contrib': float((pb.payor_contributions_to_official_12m > 0).mean())}
    V['ratio_all'] = V['obs'] / V['base_all']
    CH = {'x': ['Behested payors', 'Random organization active with the City in the same year', 'Random organization from the whole pool'],
          'v': [V['obs'] * 100, V['base_active'] * 100, V['base_all'] * 100]}
    return V, CH


def c_nonprofit_loop():
    n = pd.read_parquet(os.path.join(AN, 'nonprofit_loop.parquet'))
    has = n.n_126f4_approvals_bos_mayor > 0
    g = n.principal_giving_to_mayor_bos > 0
    q = pd.qcut(n.city_payments_fy2016_on, 4, labels=False)
    V = {'n': int(len(n)), 'n_has': int(has.sum()), 'n_gave': int(g.sum()), 'rate_has': float(g[has].mean()), 'rate_not': float(g[~has].mean()),
         'n_not': int((~has).sum()), 'pay_share_has': float(n[has].city_payments_fy2016_on.sum() / n.city_payments_fy2016_on.sum()),
         'giving': float(n.principal_giving_to_mayor_bos.sum()), 'payments': float(n.city_payments_fy2016_on.sum()),
         'q4_has': float(has[q == 3].mean()), 'q1_has': float(has[q == 0].mean()),
         'share_gave_among_has_q4': float(g[has & (q == 3)].mean()), 'share_gave_among_has_q13': float(g[has & (q < 3)].mean()),
         'fund_share_gave': float(n[g].city_payments_fy2016_on.sum() / n.city_payments_fy2016_on.sum()),
         'n_gave_in_has': int((g & has).sum())}
    V['giving_per_1m'] = V['giving'] / (V['payments'] / 1e6)
    V['beh_n'] = int((n.behested_received > 0).sum())
    CH = {'x': ['Contracts approved by the Board or Mayor (leaders disclosed)', 'No such approval (leaders not disclosed)'],
          'v': [V['rate_has'] * 100, V['rate_not'] * 100]}
    return V, CH


def enforcement():
    e = pd.read_parquet(os.path.join(INT, 'enforcement.parquet'))
    e['p'] = pd.to_numeric(e.penalty_amount.astype(str).str.replace(r'[\$,]', '', regex=True), errors='coerce').fillna(0)
    e['year'] = e.date.str[:4].astype(int)
    cs = e.code_sections.fillna('')
    e['grp'] = np.select([cs.str.contains(r'(^|[ ,])1\.126\b'), e.case_category.fillna('').str.contains('Lobbyist'),
                          cs.str.contains(r'(^|[ ,])3\.6\d\d|C3\.6', regex=True), e.case_category.fillna('').str.contains('Campaign'),
                          e.case_category.fillna('').str.contains('SEI')],
                         ['Contractor contribution ban (§1.126)', 'Lobbyist rules', 'Behested-payment rules', 'Other campaign finance', 'Financial-interest statements not filed'],
                         'Other ethics rules')
    return e


ENF_ORDER = ['Other campaign finance', 'Other ethics rules', 'Lobbyist rules', 'Financial-interest statements not filed', 'Contractor contribution ban (§1.126)', 'Behested-payment rules']


def c_enforcement():
    e = enforcement()
    bw = J('site/analyses/ban_window.json')['records']
    g = e.groupby('grp').size()
    V = {'n': int(len(e)), 'pen': float(e.p.sum()), 'med': float(e.p.median()), 'n126': int(g.get('Contractor contribution ban (§1.126)', 0)),
         'pen126': float(e[e.grp.str.contains('1.126', regex=False)].p.sum()), 'nlob': int(g.get('Lobbyist rules', 0)),
         'nbeh': int(g.get('Behested-payment rules', 0)), 'n_review': sum(1 for r in bw if r['review'] == 'appears_to_warrant_review'),
         'first': int(e.year.min()), 'n_1926': int(e.year.between(2019, 2026).sum()), 'pen_max': float(e.p.max()),
         'n_camp': int(e.case_category.fillna('').str.contains('Campaign').sum()),
         'nlob_code': int(e.code_sections.fillna('').str.contains(r'(?:^|[ ,])2\.1\d\d').sum())}
    V['per_year_1926'] = V['n_1926'] / 8
    V['n_0318'] = int(e.year.between(2003, 2018).sum()); V['per_year_0318'] = V['n_0318'] / 16
    CH = {'x': ENF_ORDER, 'v': [int(g.get(k, 0)) for k in ENF_ORDER]}
    return V, CH


BANDS = ['Under $100', '$100–249', '$250–499', 'Exactly $500', 'Over $500']


def band(a):
    return pd.cut(a, [0, 99.995, 249.995, 499.995, 500.005, 1e12], labels=BANDS)


def c_maxed_checks():
    k = cand_money(range(2010, 2027))
    k = k[k.is_individual]
    s = k.groupby(band(k.amount), observed=False).amount.sum() / k.amount.sum()
    n = k.groupby(band(k.amount), observed=False).size() / len(k)
    by = {}
    for y, g in k.groupby('year'):
        by[int(y)] = float(g[(g.amount >= 499.995) & (g.amount <= 500.005)].amount.sum() / g.amount.sum())
    sfo = k[loc_class(k) == 'SF']
    V = {'over': float(s['Over $500']), 'max_share': float(s['Exactly $500']), 'u100': float(s['Under $100']), 'max_n_share': float(n['Exactly $500']),
         'u100_n_share': float(n['Under $100']), 'min_y': min(by.values()), 'max_y': max(by.values()), 'y2024': by[2024],
         'total': float(k.amount.sum()), 'sf_max': float(sfo[(sfo.amount >= 499.995) & (sfo.amount <= 500.005)].amount.sum() / sfo.amount.sum()),
         'ge250': float(s['$250–499'] + s['Exactly $500'] + s['Over $500'])}
    CH = {'x': BANDS, 'v': [float(v) * 100 for v in s.values]}
    return V, CH


COMPUTE = {k[2:]: v for k, v in globals().items() if k.startswith('c_') and callable(v)}
