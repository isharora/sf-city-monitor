"""Independent verification of network/data/site/insights/insights.json.

For every insight this script recomputes each named value (V) and chart array (CH) with its own code, from the module's
normalized source tables: data/interim/*.parquet (campaign transactions, Form 496 items, lobbyist contacts, behested
filings, Form 114.5, waivers, enforcement), data/raw/cf_transactions.csv (Form 496 re-filing check), data/network/edges.parquet
and nodes.parquet (entity-resolved flows) and data/er (officials, lobbyist-contact official map). It does not import
compute_build.py and does not read data/analysis/*.json or concentration results.
Documented exceptions, where the "source table" is itself a validated derived product:
  * red-team simulation outputs in data/redteam/redteam2.json: the contractor-cluster bootstrap interval and placebo ratio,
    the behested-payment base rates (random-organization draws) and the crude-key concentration check;
  * record-level analysis tables produced by entity resolution: data/analysis/ban_base_rate_records.parquet (per-record
    observed/expected ban-window flags), data/analysis/lobbyist_contributions.parquet (contributions matched to lobbyists;
    the prior-contact counts are recomputed here from the lobbyist contacts), data/analysis/behested_pending_business.parquet,
    data/analysis/nonprofit_loop.parquet, and data/site/analyses/ban_window.json (review flags);
  * the Claude sector labels in data/insights/sector_labels.parquet (hand-checked).

Checks (any failure -> exit 1):
  1. every placeholder value used in an insight's text is recomputed here and agrees with the build value
     (relative tolerance 0.5%, or 0.01 absolute for small values; strings exact);
  2. the insight's text re-rendered with the recomputed values equals the published text exactly;
  3. every chart array (and the chart reference line) agrees element by element (1% relative / 0.05 absolute);
  4. template text contains no literal numbers outside placeholders and allowed tokens (years, dates, citations, thresholds);
  5. contract shape: required fields, themes, chart types, verdicts, >= 3 checks, explore views and params, title length,
     ranks 1..n, unique ids, series lengths, source paths, department codes.
Writes data/redteam/verify_insights.json.
"""
import os, sys, json, re, time, importlib.util
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec

ROOT = os.path.dirname(os.path.dirname(HERE))
PROJ = os.path.dirname(ROOT)
D = os.path.join(ROOT, 'data')
OUTF = os.path.join(D, 'site', 'insights', 'insights.json')
VALS = os.path.join(D, 'redteam', 'insights_values.json')
REPORT = os.path.join(D, 'redteam', 'verify_insights.json')
_m = {}


def memo(k, f):
    if k not in _m:
        _m[k] = f()
    return _m[k]


def P(*a):
    return os.path.join(D, *a)


def rt2():
    return memo('rt2', lambda: json.load(open(P('redteam', 'redteam2.json'))))


def tx():
    def f():
        c = pd.read_parquet(P('interim', 'contributions.parquet'))
        c = c[c.amount.notna()].copy()
        c['yr'] = c.date.dt.year
        return c
    return memo('tx', f)


def E():
    return memo('E', lambda: pd.read_parquet(P('network', 'edges.parquet')))


def lab():
    return memo('lab', lambda: dict(pd.read_parquet(P('network', 'nodes.parquet'), columns=['node_id', 'label']).values))


def own_money(c):
    """Candidate's own money: individual donor with the same surname and first initial as the committee's candidate ('Last, First')."""
    out = np.zeros(len(c), dtype=bool)
    for i, (ind, dl, df, rc) in enumerate(zip(c.is_individual.values, c.donor_last.values, c.donor_first.values, c.recip_candidate.values)):
        if not ind or not isinstance(rc, str) or ',' not in rc or not isinstance(dl, str) or not dl.strip():
            continue
        cl, cf = rc.split(',', 1)
        if dl.strip().upper() == cl.strip().upper() and isinstance(df, str) and df.strip()[:1].upper() == cf.strip()[:1].upper() and cf.strip():
            out[i] = True
    return out


def donations(years):
    c = tx()
    c = c[c.yr.isin(list(years)) & (c.amount > 0) & c.is_city_candidate & ~c.is_committee_donor]
    return c[~own_money(c)]


def did(c):
    return pd.Series(np.where(c.is_individual, 'i' + c.person_key.fillna('').astype(str), 'o' + c.org_key.fillna(c.donor_name.fillna('')).astype(str)), index=c.index)


def top_share(c):
    g = c.groupby(did(c)).amount.sum().sort_values(ascending=False)
    n = len(g)
    return float(g.iloc[:max(1, int(np.ceil(0.01 * n)))].sum() / g.sum()), n


# ------------------------------------------------------------------------------------------------ independent expenditures
def f496_keep():
    def f():
        r = pd.read_csv(P('raw', 'cf_transactions.csv'), dtype=str,
                        usecols=['filing_date', 'filer_nid', 'form_type', 'transaction_id', 'calculated_amount', 'calculated_date', 'element_nid', 'transaction_last_name'])
        r = r[r.form_type == 'F496'].sort_values('filing_date')
        allel = set(r.element_nid)
        keep = set(r.drop_duplicates(['filer_nid', 'transaction_id', 'calculated_amount', 'calculated_date', 'transaction_last_name'], keep='last').element_nid)
        return allel, keep
    return memo('f496', f)


def city_officials():
    return memo('cityoff', lambda: set(pd.read_parquet(P('er', 'officials.parquet')).query("category == 'candidate_or_elected'").official_id))


def ie_city(dedup=True):
    e = E()
    ie = e[(e.edge_type == 'independent_expenditure') & e.target.isin(city_officials())].copy()
    ie['yr'] = ie.date.dt.year
    if dedup:
        allel, keep = f496_keep()
        ie = ie[~(ie.record_id.isin(allel) & ~ie.record_id.isin(keep))]
    return ie


def v_ie_vs_donors():
    ie = ie_city()
    ied = ie.groupby('yr').amount.sum()
    raw = ie_city(False).groupby('yr').amount.sum()
    V, CH = {}, {'x': [], 'cand': [], 'self': [], 'ie': []}
    c = tx()
    for y in [2011, 2015, 2018, 2019, 2024]:
        k = c[(c.yr == y) & (c.amount > 0) & c.is_city_candidate & ~c.is_committee_donor]
        om = own_money(k)
        V[f'cand_{y}'] = float(k[~om].amount.sum()); V[f'self_{y}'] = float(k[om].amount.sum()); V[f'ie_{y}'] = float(ied.get(y, 0))
        CH['x'].append(str(y)); CH['cand'].append(V[f'cand_{y}'] / 1e6); CH['self'].append(V[f'self_{y}'] / 1e6); CH['ie'].append(V[f'ie_{y}'] / 1e6)
    for y in (2011, 2018, 2024):
        V[f'ratio_{y}'] = V[f'ie_{y}'] / V[f'cand_{y}']
    V['cand_self_2024'] = V['cand_2024'] + V['self_2024']
    V['ratio_incl_self_2024'] = V['ie_2024'] / V['cand_self_2024']
    V['ratio_incl_self_2011'] = V['ie_2011'] / (V['cand_2011'] + V['self_2011'])
    V['dup_2024'] = float(raw.get(2024, 0) - ied.get(2024, 0))
    V['ratio_with_dups_2024'] = float(raw.get(2024, 0)) / V['cand_2024']
    k = c[(c.yr == 2024) & (c.amount > 0) & c.is_city_candidate & ~c.is_committee_donor]
    s = k[own_money(k)]
    V['self_top_2024'] = float(s.groupby('filer_nid').amount.sum().max())
    ip = pd.read_parquet(P('interim', 'ie.parquet'))
    ip = ip[(ip.date.dt.year == 2024) & ip.office_code.isin(['BSU', 'CSU'])]
    allel, keep = f496_keep()
    ip = ip[~(ip.element_nid.isin(allel) & ~ip.element_nid.isin(keep))]
    V['ie_bos_2024'] = float(ip.amount.sum())
    V['cand_bos_2024'] = float(k[~own_money(k) & (k.recip_office == 'Board of Supervisors')].amount.sum())
    V['ratio_bos_2024'] = V['ie_bos_2024'] / V['cand_bos_2024']
    V['share_unlimited'] = (V['ie_2024'] + V['self_top_2024']) / (V['ie_2024'] + V['cand_2024'] + V['self_2024'])
    return V, CH


def v_outside_concentration():
    c = tx()
    c = c[(c.yr == 2024) & (c.amount > 0)]
    c = c[~own_money(c) & ~c.is_committee_donor]
    V = {}
    V['cand_top1'], _ = top_share(c[c.is_city_candidate])
    V['ballot_top1'], _ = top_share(c[c.recip_kind == 'ballot_measure'])
    V['gp_top1'], _ = top_share(c[c.recip_kind.isin(['general_purpose', 'candidate_pf']) & ~c.is_city_candidate])
    k = c[c.is_city_candidate]
    V['cand_org_share'] = float(k.loc[~k.is_individual, 'amount'].sum() / k.amount.sum())
    ie = ie_city(False)
    coms = set(ie[ie.yr == 2024].source)
    a = tx()
    a = a[a.yr.isin([2023, 2024]) & (a.amount > 0) & ('C:' + a.filer_nid.astype(str)).isin(coms)]
    V['ie_coms'] = len(coms)
    V['ie_total'] = float(a.amount.sum())
    V['ie_top1'], V['ie_n'] = top_share(a)
    V['ie_ind_share'] = float(a.loc[a.is_individual, 'amount'].sum() / V['ie_total'])
    ind = a[a.is_individual].groupby(did(a[a.is_individual])).amount.sum()
    V['n_ind_100k'] = int((ind >= 1e5).sum()); V['share_ind_100k'] = float(ind[ind >= 1e5].sum() / V['ie_total'])
    V['share_ind_under_1k'] = float(ind[ind < 1e3].sum() / V['ie_total'])
    big = ie[(ie.yr == 2024)].groupby('source').amount.sum().nlargest(4).index
    b = a[('C:' + a.filer_nid.astype(str)).isin(set(big))]
    ib = b[b.is_individual].groupby(did(b[b.is_individual])).amount.sum()
    V['big4_share_ind_100k'] = float(ib[ib >= 1e5].sum() / b.amount.sum())
    shares = []
    t = tx()
    for y in range(2010, 2027):
        k = t[(t.yr == y) & (t.amount > 0) & t.is_city_candidate & ~t.is_committee_donor]
        shares.append(top_share(k[~own_money(k)])[0])
    V['cand_top1_min'], V['cand_top1_max'] = min(shares), max(shares)
    V['rt_crude'] = float(rt2()['rederivation']['concentration_2024']['independent_top1pct_share_name_key'])
    CH = {'x': ['City candidate committees', 'Ballot-measure committees', 'General-purpose committees', 'Committees that spent independently on 2024 City races'],
          'top1': [100 * V['cand_top1'], 100 * V['ballot_top1'], 100 * V['gp_top1'], 100 * V['ie_top1']]}
    return V, CH


# ------------------------------------------------------------------------------------------------ ballot sectors
NAMES = [('individuals', 'Individuals (all, aggregated)'), ('soda_tobacco_vape', 'Soda, tobacco and vape companies and trade groups'), ('tech', 'Tech companies'),
         ('real_estate', 'Real estate and development'), ('labor', 'Labor unions'), ('business_group', 'Business groups and chambers'),
         ('party_political', 'PACs and committees (funders not evident)'), ('nonprofit_advocacy', 'Nonprofits and advocacy groups')]


def v_ballot_sectors():
    lb = pd.read_parquet(P('insights', 'sector_labels.parquet'))
    sec = dict(zip(lb.donor_name, lb.sector))
    c = tx()
    b = c[(c.recip_kind == 'ballot_measure') & (c.yr >= 2010) & (c.yr <= 2026) & (c.amount > 0)].copy()
    b['s'] = [('individuals' if i else sec.get(n, '_small')) for i, n in zip(b.is_individual, b.donor_name)]
    tot = b.amount.sum()
    by = b.groupby('s').amount.sum()
    cy_all = tx()
    kk = cy_all[(cy_all.yr >= 2010) & (cy_all.yr <= 2026) & (cy_all.amount > 0) & cy_all.is_city_candidate]
    kk = kk[~own_money(kk)]  # transfers from other committees kept, candidates' own money excluded
    cand = kk.amount.sum()
    V = {'ballot_total': float(tot), 'stv': float(by.get('soda_tobacco_vape', 0)), 'cand_total': float(cand), 'cand_total_m': float(cand) / 1e6,
         'ind': float(by['individuals']), 'tech': float(by.get('tech', 0)), 're': float(by.get('real_estate', 0)), 'labor': float(by.get('labor', 0))}
    V['stv_share'] = V['stv'] / tot; V['ind_share'] = V['ind'] / tot; V['ballot_to_cand'] = tot / cand
    stv = b[b.s == 'soda_tobacco_vape']
    V['stv_n_orgs'] = int(stv.donor_name.nunique())
    up = b.donor_name.fillna('').str.upper()
    V['stv_rx'] = float(b[~b.is_individual & up.str.contains(r'AMERICAN BEVERAGE|JUUL|REYNOLDS|ALTRIA|PHILIP MORRIS|COCA|PEPSI|DR PEPPER|TOBACCO|VAPOR|VAPE')].amount.sum())
    bev = stv.donor_name.str.upper().str.contains('BEVERAGE|COCA|PEPSI')
    V['bev'] = float(stv[bev].amount.sum()); V['tob_vape'] = float(stv[~bev].amount.sum())
    k = c[c.is_city_candidate & (c.amount > 0) & (c.yr >= 2010) & (c.yr <= 2026)]
    V['cand_incl_com'] = float(k[~own_money(k)].amount.sum())
    V['cand_incl_self'] = float(k[~k.is_committee_donor].amount.sum())
    V['stv_vs_self_total'] = V['stv'] / V['cand_incl_self']
    V['conf_cut'] = 0.6
    V['cand_no_com'] = float(donations(range(2010, 2027)).amount.sum())
    fr = pd.read_csv(P('raw', 'fred_CPIAUCSL.csv'), dtype={'observation_date': str})
    ann = fr.groupby(fr.observation_date.str[:4].astype(int)).CPIAUCSL.mean()
    V['stv_real'] = float(sum(a * ann[2026] / ann[y] for a, y in zip(stv.amount, stv.yr)))
    V['cand_real'] = float(sum(a * ann[2026] / ann[y] for a, y in zip(kk.amount, kk.yr)))
    orgs = b[~b.is_individual]
    V['labelled_share_org'] = float(orgs[orgs.s != '_small'].amount.sum() / orgs.amount.sum())
    low = set(lb[lb.confidence < 0.6].donor_name)
    V['low_conf_share'] = float(orgs[orgs.donor_name.isin(low)].amount.sum() / tot)
    rest = sorted(NAMES[1:], key=lambda kn: -float(by.get(kn[0], 0)))
    order = [NAMES[0]] + rest
    CH = {'x': [n for _, n in order], 'm': [float(by.get(k, 0)) / 1e6 for k, _ in order]}
    return V, CH


# ------------------------------------------------------------------------------------------------ lobbyist ban
def m6():
    def f():
        sys.path.insert(0, os.path.join(ROOT, 'pipeline'))
        sp = importlib.util.spec_from_file_location('m6v', os.path.join(ROOT, 'pipeline', '06_officials.py'))
        m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        return m
    return memo('m6', f)


def v_lobbyist_ban():
    m = m6()
    d = pd.read_parquet(P('analysis', 'lobbyist_contributions.parquet'))
    d['yr'] = d.date.dt.year
    lc = pd.read_parquet(P('interim', 'lobby_contacts.parquet'), columns=['date', 'lobbyistname', 'departmentname'])
    lc['node'] = 'L:' + lc.lobbyistname.map(m.nk_from_lastfirst)
    lc['off'] = lc.departmentname.map(m.dept_office)
    lc = lc[lc.off.notna()]
    groups = {k: (g.off.values, g.date.values) for k, g in lc.groupby('node')}

    def prior(r, days):
        g = groups.get(r.lobbyist_node)
        if g is None:
            return False
        offs, dates = g
        t = np.datetime64(r.date)
        return bool(((offs == r.office) & (dates <= t) & (dates >= t - np.timedelta64(days, 'D'))).any())
    d['p90'] = [prior(r, 90) for r in d.itertuples()]
    d['p180'] = [prior(r, 180) for r in d.itertuples()]
    pos = d[d.amount > 0]
    pre, post = pos[(pos.yr >= 2010) & (pos.yr <= 2017)], pos[(pos.yr >= 2019) & (pos.yr <= 2025)]
    y18 = d[d.yr == 2018]
    p18 = y18[(y18.amount > 0) & y18.p90]
    n18 = y18[(y18.amount < 0) & y18.p90]
    V = {'fl_2017': int(pos[(pos.yr == 2017) & pos.p90].shape[0]), 'fl_pre': int(pre.p90.sum()), 'fl_pre_amt': float(d[(d.yr >= 2010) & (d.yr <= 2017) & d.p90].amount.sum()),
         'post_pos': int(len(p18)), 'post_pos_amt': float(p18.amount.sum()),
         'post_refunded': int(sum(((n18.lobbyist_node == r.lobbyist_node) & (n18.recipient == r.recipient) & (n18.date >= r.date)).any() for r in p18.itertuples())),
         'fl_share_pre': float(pre.p90.mean()), 'avg_pre': len(pre) / 8, 'avg_post': len(post) / 7, 'fl_post_1925': int(post.p90.sum()),
         'post_180': int(post.p180.sum()), 'pre_180': int(pre.p180.sum()), 'hc_cut': 0.95,
         'hc_pre': int((pre.p90 & (pre.match_conf >= 0.95)).sum()), 'hc_post': int((post.p90 & (post.match_conf >= 0.95)).sum())}
    lc2 = pd.read_parquet(P('interim', 'lobby_contacts.parquet'), columns=['date', 'lobbyistname'])
    act = lc2.groupby(lc2.date.dt.year).lobbyistname.nunique()
    V['act_1517'] = float(act[[2015, 2016, 2017]].mean()); V['act_1925'] = float(act[list(range(2019, 2026))].mean())
    V['per_lob_1517'] = pos[(pos.yr >= 2015) & (pos.yr <= 2017)].shape[0] / 3 / V['act_1517']
    V['per_lob_1925'] = len(post) / 7 / V['act_1925']
    yrs = range(2010, 2026)
    CH = {'x': [int(y) for y in yrs], 'flagged': [int(((pos.yr == y) & pos.p90).sum()) for y in yrs], 'other': [int(((pos.yr == y) & ~pos.p90).sum()) for y in yrs]}
    return V, CH


# ------------------------------------------------------------------------------------------------ contractor ban
def v_contractor_ban():
    r = pd.read_parquet(P('analysis', 'ban_base_rate_records.parquet'))
    x = r[r.pub == False]  # noqa: E712
    V = {'obs': x.inside.mean(), 'exp': x.e_weighted.mean(), 'n_rec': len(x), 'n_con': x.contractor.nunique(),
         'obs_even': x[x.even].inside.mean(), 'exp_even': x[x.even].e_weighted.mean(), 'obs_odd': x[~x.even].inside.mean(), 'exp_odd': x[~x.even].e_weighted.mean(),
         'obs12': x.inside12.mean(), 'exp12': x.e12_weighted.mean(), 'obs_all': r.inside.mean(), 'exp_all': r.e_weighted.mean(), 'exp_unif': x.e_uniform.mean(),
         'conf_min': 0.85}
    V = {k: (float(v) if not isinstance(v, (int, np.integer)) else int(v)) for k, v in V.items()}
    b = rt2()['rederivation']['ban_base_rate']
    V['diff_lo'], V['diff_hi'] = b['bootstrap_95ci']['difference']
    V['placebo'] = b['placebo_4y']['ratio_W0_to_4y_mean']
    rec = pd.DataFrame(json.load(open(P('site', 'analyses', 'ban_window.json')))['records'])
    rv = rec[rec.review == 'appears_to_warrant_review']
    V.update({'n_review': len(rv), 'sum_review': float(rv.amount.sum()), 'med_review': float(rv.amount.median()), 'share_500': float((rv.amount <= 500).mean()),
              'max_review': float(rv.amount.max()), 'refund_seen': int((rv.possible_refund_seen == True).sum())})  # noqa: E712
    CH = {'x': ['All years', 'Election years', 'Off years'], 'obs': [100 * V['obs'], 100 * V['obs_even'], 100 * V['obs_odd']],
          'exp': [100 * V['exp'], 100 * V['exp_even'], 100 * V['exp_odd']]}
    return V, CH


# ------------------------------------------------------------------------------------------------ behested
def beh():
    def f():
        e = E()
        b = e[e.edge_type == 'behested_payment'].copy()
        at = b['attrs'].map(json.loads)
        b['form'] = at.map(lambda a: a.get('form') or '')
        b['payee_raw'] = at.map(lambda a: a.get('payee_raw') or '')
        n_raw = len(b)
        b = b.sort_values('date', kind='stable')
        b = b[~b.duplicated(subset=['official', 'source', 'target', 'date'], keep='last')]
        amb = b.payee_raw.str.upper().str.contains('SEE ATTACHED')
        b['yr'] = b.date.dt.year
        return b[~amb], b[amb], n_raw
    return memo('beh', f)


def v_behested_vanished():
    b, amb, n_raw = beh()
    s8 = b.form.str.startswith('FPPC')
    V = {'raw_rows': n_raw, 'used_rows': len(b), 'amb_n': len(amb), 'amb_amt': float(amb.amount.sum()),
         'total_used': float(b.amount.sum()), 'y2015': float(b[b.yr == 2015].amount.sum()), 'n2015': int((b.yr == 2015).sum()), 'n2023': int((b.yr == 2023).sum()),
         'tot803': float(b[s8].amount.sum()), 'n803': int(s8.sum()),
         't3610': float(b[b.form.str.startswith('SFEC 3610')].amount.sum()), 'n3610': int(b.form.str.startswith('SFEC 3610').sum())}
    lee = b[b.official == 'O:LEE|EDWIN']
    V['lee'] = float(lee.amount.sum()); V['lee_n'] = len(lee); V['lee_share'] = V['lee'] / V['tot803']
    L = lab()
    y = b[b.yr == 2015].copy()
    y['pl'] = y.target.map(L).fillna('')
    V['homeless_2015'] = float(y[y.pl.str.upper().str.contains('HOMELESS')].amount.sum())
    V['travel_2015'] = float(y[y.pl.str.upper().str.contains('TRAVEL')].amount.sum())
    V['y2015_top2_share'] = (V['homeless_2015'] + V['travel_2015']) / V['y2015']
    V['mayor_after'] = int((b.official.isin(['O:LEE|EDWIN', 'O:FARRELL|MARK', 'O:BREED|LONDON', 'O:LURIE|DANIEL']) & (b.date > pd.Timestamp('2018-03-31'))).sum())
    yrs = range(2015, 2027)
    CH = {'x': [int(t) for t in yrs], 'f803': [float(b[(b.yr == t) & s8].amount.sum()) / 1e6 for t in yrs],
          'local': [float(b[(b.yr == t) & ~s8].amount.sum()) / 1e6 for t in yrs]}
    return V, CH


def v_form_1145():
    f = pd.read_parquet(P('interim', 'f1145.parquet'))
    f = f.drop_duplicates(subset=['docusignid', 'contributorname', 'contributiondate', 'contributionamount']).copy()
    f['amt'] = pd.to_numeric(f.contributionamount, errors='coerce')
    f['yr'] = pd.to_datetime(f.contributiondate.str[:10]).dt.year
    g = f.groupby('yr').amt.sum()
    z = f[f.yr == 2026]
    lu = z[z.cityelectiveofficername.fillna('').str.upper().str.contains('LURIE')].amt.sum()
    V = {'y2026': float(g[2026]), 'y2019': float(g[2019]), 'total': float(f.amt.sum()), 'n_rows': len(f), 'lurie_2026': float(lu),
         'n_2026': len(z), 'med_2026': float(z.amt.median()), 'n_com_2026': int(z.committeename.nunique()),
         'orig_only_2026': float(z[z.filingtype.fillna('').str.upper().str.startswith('ORIG')].amt.sum())}
    y19 = f[f.yr == 2019]
    V['peskin_breed_2019_share'] = float(y19[y19.cityelectiveofficername.fillna('').str.upper().str.contains('PESKIN|BREED')].amt.sum() / y19.amt.sum())
    V['lurie_share_2026'] = V['lurie_2026'] / V['y2026']; V['y2026_ex'] = V['y2026'] - V['lurie_2026']
    CH = {'x': [str(t) for t in range(2019, 2027)], 'v': [float(g.get(t, 0)) / 1e6 for t in range(2019, 2027)]}
    return V, CH


def v_waivers():
    w = pd.read_parquet(P('interim', 'bp_waivers.parquet'))
    d = pd.to_datetime(w.date_of_waiver_approval.str[:10])
    yc = d.dt.year.value_counts()
    V = {'n': len(w), 'n2023': int(yc.get(2023, 0)), 'n2025': int(yc.get(2025, 0)), 'n2026': int(yc.get(2026, 0)),
         'first': d.min().strftime('%Y-%m-%d'), 'mayor': int(w.agency.fillna('').str.contains('mayor', case=False).sum()),
         'homeless': int(w.subject.fillna('').str.contains('homeless|shelter', case=False).sum()),
         'n_subjects': int(w.subject.fillna('').str.upper().str[:40].nunique()), 'upl_2025': int(w.date_uploaded.fillna('').str.startswith('2025').sum())}
    before = d < pd.Timestamp('2025-01-08')
    may = w.agency.fillna('').str.upper().str.contains('MAYOR')
    V.update({'n_breed': int(before.sum()), 'n_lurie': int((~before).sum()), 'mayor_breed': int((before & may).sum()), 'mayor_lurie': int((~before & may).sum())})
    V['repeats'] = V['n'] - V['n_subjects']
    ws = pd.DataFrame({'d': d, 'k': w.subject.fillna('').str.upper().str[:40]}).sort_values('d', kind='stable')
    firsts = ws[~ws.k.duplicated()]
    V['new_2025'] = int((firsts.d.dt.year == 2025).sum()); V['new_2324'] = int(firsts.d.dt.year.isin([2023, 2024]).sum())
    CH = {'x': ['2023', '2024', '2025', '2026'], 'v': [int(yc.get(t, 0)) for t in (2023, 2024, 2025, 2026)]}
    return V, CH


# ------------------------------------------------------------------------------------------------ lobbying
def contacts():
    def f():
        e = E()
        l = e[e.edge_type == 'lobbying_contact'][['source', 'target', 'date', 'attrs']].copy()
        at = l.pop('attrs').map(json.loads)
        l['dept'] = at.map(lambda a: (a.get('department') or '')).str.upper().str.strip()
        l['subj'] = at.map(lambda a: a.get('subject'))
        l['issue'] = at.map(lambda a: a.get('issue') or '')
        l['yr'] = l.date.dt.year
        mp = pd.read_parquet(P('er', 'lobby_official_map.parquet')).drop_duplicates('official_id')
        cat = dict(zip(mp.official_id, mp.category))
        l['cat'] = [cat.get(t, 'staff') for t in l.target]
        return l
    return memo('contacts', f)


def uniq(l):
    return l[~l.duplicated(subset=['source', 'target', 'date'])]


def v_pension_lobbying():
    A = contacts()
    A = A[(A.yr >= 2015) & (A.yr <= 2025)]
    u = uniq(A)
    isr = u.dept.str.contains('RETIREMENT')
    s = isr.groupby(u.yr).mean()
    rr = A.dept.str.contains('RETIREMENT').groupby(A.yr).mean()
    r = u[isr]
    top = r.source.value_counts()
    L = lab()
    w = u[~u.source.isin(top.index[:2])]
    V = {'s2015': float(s[2015]), 's2022': float(s[2022]), 's2025': float(s[2025]), 'overall': float(isr.mean()), 'n_meet': int(isr.sum()),
         'n_clients': int(r.source.nunique()), 'n_people': int(r.target.nunique()), 'raw2022': float(rr[2022]),
         'sb2022': float((u.subj == 'City Employee Benefits').groupby(u.yr).mean()[2022]),
         'no_top2_2022': float(w[w.yr == 2022].dept.str.contains('RETIREMENT').mean()), 'mayor_overall': float((u.dept == 'MAYOR').mean()),
         'top1_name': L.get(top.index[0]), 'top2_name': L.get(top.index[1]), 'elected_share': float((r.cat == 'elected').mean()),
         'tot_2015': int((u.yr == 2015).sum()), 'tot_2022': int((u.yr == 2022).sum()), 'tot_2025': int((u.yr == 2025).sum()),
         'n_meet_2015': int(isr[u.yr == 2015].sum()), 'n_meet_2022': int(isr[u.yr == 2022].sum())}
    CH = {'x': [int(y) for y in range(2015, 2026)], 'share': [100 * float(s[y]) for y in range(2015, 2026)]}
    return V, CH


def klass(l):
    off = l.dept.str.contains('BOARD OF SUPERVISORS') | (l.dept == 'MAYOR')
    k = pd.Series('Department staff', index=l.index)
    k[l.cat == 'appointed_exec'] = 'Department heads and commissioners'
    k[(l.cat == 'elected') | off] = 'Elected officials and their offices'
    return k


def v_staff_targets():
    A = contacts()
    A = A[(A.yr >= 2015) & (A.yr <= 2025)].copy()
    A['k'] = klass(A)
    u = uniq(A)
    sh = u.k.value_counts(normalize=True)
    EO, DH, DS = 'Elected officials and their offices', 'Department heads and commissioners', 'Department staff'
    per = u.groupby('yr').k.value_counts(normalize=True).unstack().fillna(0)
    rawsh = A.k.value_counts(normalize=True)
    np_ = u[u.subj != 'Planning and Building Permits'].k.value_counts(normalize=True)
    notel = u[u.k != EO]
    old = contacts()
    old = uniq(old[(old.yr >= 2010) & (old.yr <= 2014)])
    V = {'el_off': float(sh[EO]), 'ex': float(sh[DH]), 'st': float(sh[DS]), 'dept': float(sh[DH] + sh[DS]), 'el_only': float((u.cat == 'elected').mean()),
         'n': len(u), 'permits': float((u.subj == 'Planning and Building Permits').mean()), 'dept_raw': float(rawsh[DH] + rawsh[DS]),
         'dept_np': float(np_[DH] + np_[DS]), 'min_el': float(per[EO].min()), 'max_el': float(per[EO].max()),
         'permits_dept': float((notel.subj == 'Planning and Building Permits').mean()), 'el_off_old': float((klass(old) == EO).mean())}
    CH = {'x': [int(y) for y in per.index], 's0': list(100 * per[EO].values), 's1': list(100 * per[DH].values), 's2': list(100 * per[DS].values)}
    return V, CH


def v_av_lobbying():
    L = lab()
    A = contacts()
    A = A[(A.yr >= 2016) & (A.yr <= 2025)].copy()
    cl = A.source.map(L).fillna('')
    A['av'] = A.issue.str.contains(r'autonom|driverless|robotaxi|self-driving|\bAVs?\b|waymo|zoox|cruise|tesla', case=False, regex=True) | cl.str.contains('waymo|zoox|cruise', case=False)
    u = uniq(A)
    s = u.groupby('yr').av.mean(); sr = A.groupby('yr').av.mean()
    wid = next(k for k, v in L.items() if v == 'Waymo LLC')
    u25 = u[u.yr == 2025]
    rk = u25.source.value_counts()
    rkr = A[A.yr == 2025].source.value_counts()
    av25 = u25[u25.av]
    w = u[(u.source == wid) & (u.yr >= 2018)]
    pay = E()
    pay = pay[(pay.edge_type == 'lobbying_payment') & (pay.source == wid)].amount.sum()
    V = {'s2019': float(s[2019]), 's2024': float(s[2024]), 's2025': float(s[2025]), 'raw2025': float(sr[2025]), 'n2025': len(av25),
         'waymo_rank_2025': int(list(rk.index).index(wid) + 1), 'waymo_raw_rank_2025': int(list(rkr.index).index(wid) + 1),
         'waymo_2025': int(rk[wid]), 'waymo_raw_2025': int(rkr[wid]), 'first_2025': L.get(rk.index[0]),
         'waymo_share_av_2025': float((av25.source == wid).mean()), 'lob_per_meeting': float(rkr[wid] / rk[wid]),
         'airport': float((w.dept == 'AIRPORT').mean()), 'mta': float(w.dept.str.contains('MUNICIPAL TRANSPORTATION').mean()),
         'w_elected': float((w.cat == 'elected').mean()), 'pay': float(pay),
         'teamsters_av_2025': int((av25.source.map(L) == 'TEAMSTER JOINT COUNCIL 7').sum()),
         'no_waymo_2019': float(u[(u.yr == 2019) & (u.source != wid)].av.mean()), 'no_waymo_2025': float(u25[u25.source != wid].av.mean())}
    yrs = range(2016, 2026)
    CH = {'x': [int(y) for y in yrs], 'share': [100 * float(s[y]) for y in yrs], 'raw': [100 * float(sr[y]) for y in yrs]}
    return V, CH


def v_lobby_clients_donors():
    e = E()
    e = e[(e.date.dt.year >= 2015) & (e.date.dt.year <= 2025)]
    m = uniq(e[e.edge_type == 'lobbying_contact'][['source', 'target', 'date']]).source.value_counts()
    gave = set(e.loc[(e.edge_type == 'contribution') & (e.amount > 0) & e.source.str.startswith('ORG:'), 'source']) | set(e.loc[e.edge_type == 'sponsors', 'source'])
    vend = set(e.loc[e.edge_type.isin(['contract', 'vendor_payment', 'contract_approval']), 'target'])
    beh_ = set(e.loc[e.edge_type == 'behested_payment', 'source'])
    fr = lambda ids, s: sum(1 for i in ids if i in s) / len(ids)
    t = list(m.index[:100])
    V = {'t100_gave': fr(t, gave), 'all_gave': fr(list(m.index), gave), 'vend_gave': fr(list(vend), gave), 'n_vend': len(vend), 'n_clients': len(m),
         't100_vend': fr(t, vend), 't100_beh': fr(t, beh_), 't50_gave': fr(list(m.index[:50]), gave), 't200_gave': fr(list(m.index[:200]), gave),
         't100_contacts_share': float(m.iloc[:100].sum() / m.sum())}
    V['t100_n_gave'] = sum(1 for i in t if i in gave); V['ratio'] = V['t100_gave'] / V['vend_gave']
    V['all_beh'] = fr(list(m.index), beh_); V['all_vend'] = fr(list(m.index), vend); V['ratio_all'] = V['t100_gave'] / V['all_gave']
    CH = {'x': ['100 most active lobbying clients', 'All lobbying clients', 'Organizations paid by or contracting with the City'],
          'v': [100 * V['t100_gave'], 100 * V['all_gave'], 100 * V['vend_gave']]}
    return V, CH


# ------------------------------------------------------------------------------------------------ location, loop, base rate, enforcement, bands
def place(c):
    city = c.city.fillna('').str.upper().str.strip()
    sf = city.isin(['SAN FRANCISCO', 'SF', 'S.F.']) | c.zip5.fillna('').astype(str).str[:3].eq('941')
    ca = c.state.fillna('').str.upper().str.strip() == 'CA'
    return pd.Series(np.where(sf, 'SF', np.where(ca, 'CA', 'OUT')), index=c.index)


def v_outside_sf():
    c = tx()
    c = c[(c.yr >= 2010) & (c.yr <= 2026) & (c.amount > 0)].copy()
    c['pl'] = place(c)
    V = {}
    grp = {'cand': c[c.is_city_candidate], 'ballot': c[c.recip_kind == 'ballot_measure'],
           'gp': c[c.recip_kind.isin(['general_purpose', 'candidate_pf']) & ~c.is_city_candidate]}
    for k, g in grp.items():
        s = g.groupby('pl').amount.sum() / g.amount.sum()
        for p_ in ('SF', 'CA', 'OUT'):
            V[f'{k}_{p_}'] = float(s.get(p_, 0))
    b = grp['ballot']
    bi = b[b.is_individual]
    V['ballot_ind_out'] = float(bi[bi.pl == 'OUT'].amount.sum() / bi.amount.sum())
    V['ballot_ind_notsf'] = float(bi[bi.pl != 'SF'].amount.sum() / bi.amount.sum())
    ns = b[~b.donor_name.fillna('').str.upper().str.contains(r'AMERICAN BEVERAGE|JUUL|REYNOLDS|ALTRIA|PHILIP MORRIS|COCA|PEPSI|DR PEPPER|TOBACCO|VAPOR|VAPE')]
    V['ballot_nostv_notsf'] = float(ns[ns.pl != 'SF'].amount.sum() / ns.amount.sum())
    r = b[b.yr >= 2019]
    V['ballot_1926_notsf'] = float(r[r.pl != 'SF'].amount.sum() / r.amount.sum())
    V['ballot_zip_notsf'] = float(b[~b.zip5.fillna('').astype(str).str.startswith('941')].amount.sum() / b.amount.sum())
    V['ballot_notsf'] = 1 - V['ballot_SF']; V['cand_notsf'] = 1 - V['cand_SF']
    CH = {'x': ['City candidate committees', 'Ballot-measure committees', 'General-purpose committees']}
    for p_ in ('SF', 'CA', 'OUT'):
        CH[p_] = [100 * V[f'{k}_{p_}'] for k in ('cand', 'ballot', 'gp')]
    return V, CH


def v_nonprofit_loop():
    n = pd.read_parquet(P('analysis', 'nonprofit_loop.parquet'))
    has = n.n_126f4_approvals_bos_mayor > 0
    gv = n.principal_giving_to_mayor_bos > 0
    pay = n.city_payments_fy2016_on
    rk = pay.rank(method='first')
    qs = pd.qcut(rk, 4, labels=[0, 1, 2, 3]).astype(int)
    V = {'n': len(n), 'n_has': int(has.sum()), 'n_not': int((~has).sum()), 'rate_has': float(gv[has].mean()), 'rate_not': float(gv[~has].mean()),
         'giving': float(n.principal_giving_to_mayor_bos.sum()), 'payments': float(pay.sum()), 'pay_share_has': float(pay[has].sum() / pay.sum()),
         'fund_share_gave': float(pay[gv].sum() / pay.sum()), 'q4_has': float(has[qs == 3].mean()), 'q1_has': float(has[qs == 0].mean()),
         'share_gave_among_has_q4': float(gv[has & (qs == 3)].mean()), 'share_gave_among_has_q13': float(gv[has & (qs < 3)].mean()),
         'beh_n': int((n.behested_received > 0).sum())}
    V['giving_per_1m'] = V['giving'] / V['payments'] * 1e6
    CH = {'x': ['Contracts approved by the Board or Mayor (leaders disclosed)', 'No such approval (leaders not disclosed)'], 'v': [100 * V['rate_has'], 100 * V['rate_not']]}
    return V, CH


def v_behested_base_rate():
    b = pd.read_parquet(P('analysis', 'behested_pending_business.parquet'))
    pend = (b.lobbied_same_official_12m > 0) | (b.lobbied_same_body_12m > 0) | (b.contract_approvals_same_body_12m > 0)
    r = rt2()['rederivation']['behested_pending_business']
    V = {'n': len(b), 'obs': float(pend.mean()), 'base_active': r['base_rate_random_org_active_within_12m'], 'base_all': r['base_rate_random_org_ever_active'],
         'dollar_share': float(b.amount[pend].sum() / b.amount.sum()), 'obs_803': float(pend[b.form.str.contains('803')].mean()),
         'obs_3610': float(pend[b.form.str.contains('3610')].mean()), 'same_official': float((b.lobbied_same_official_12m > 0).mean()),
         'contrib': float((b.payor_contributions_to_official_12m > 0).mean())}
    V['ratio_all'] = V['obs'] / V['base_all']
    CH = {'x': ['Behested payors', 'Random organization active with the City in the same year', 'Random organization from the whole pool'],
          'v': [100 * V['obs'], 100 * V['base_active'], 100 * V['base_all']]}
    return V, CH


ENF = ['Other campaign finance', 'Other ethics rules', 'Lobbyist rules', 'Financial-interest statements not filed', 'Contractor contribution ban (§1.126)', 'Behested-payment rules']


def v_enforcement():
    e = pd.read_parquet(P('interim', 'enforcement.parquet'))
    pen = pd.to_numeric(e.penalty_amount.astype(str).str.replace('$', '', regex=False).str.replace(',', '', regex=False), errors='coerce').fillna(0)
    yr = e.date.str[:4].astype(int)
    cat = e.case_category.fillna('')
    secs = e.code_sections.fillna('').map(lambda s: [t.strip() for t in s.split(',')])

    def g(i):
        ss = secs.iloc[i]
        if any(re.match(r'1\.126(\b|$)', t) for t in ss):
            return ENF[4]
        if 'Lobbyist' in cat.iloc[i]:
            return ENF[2]
        if any(re.match(r'C?3\.6\d\d', t) for t in ss):
            return ENF[5]
        if 'Campaign' in cat.iloc[i]:
            return ENF[0]
        if 'SEI' in cat.iloc[i]:
            return ENF[3]
        return ENF[1]
    grp = pd.Series([g(i) for i in range(len(e))])
    cnt = grp.value_counts()
    rec = json.load(open(P('site', 'analyses', 'ban_window.json')))['records']
    V = {'n': len(e), 'first': int(yr.min()), 'pen': float(pen.sum()), 'med': float(pen.median()), 'pen_max': float(pen.max()),
         'n126': int(cnt.get(ENF[4], 0)), 'pen126': float(pen[(grp == ENF[4]).values].sum()), 'nlob': int(cnt.get(ENF[2], 0)), 'nbeh': int(cnt.get(ENF[5], 0)),
         'n_review': sum(r['review'] == 'appears_to_warrant_review' for r in rec), 'n_1926': int(((yr >= 2019) & (yr <= 2026)).sum()),
         'n_camp': int(cat.str.contains('Campaign').sum()),
         'nlob_code': int(secs.map(lambda ss: any(re.match(r'2\.1\d\d', t) for t in ss)).sum())}
    V['per_year_1926'] = V['n_1926'] / 8
    V['n_0318'] = int(((yr >= 2003) & (yr <= 2018)).sum()); V['per_year_0318'] = V['n_0318'] / 16
    CH = {'x': ENF, 'v': [int(cnt.get(k, 0)) for k in ENF]}
    return V, CH


BANDS = ['Under $100', '$100–249', '$250–499', 'Exactly $500', 'Over $500']


def v_maxed_checks():
    k = donations(range(2010, 2027))
    k = k[k.is_individual]
    a = k.amount.round(2)
    b = pd.Series(np.select([a < 100, a < 250, a < 500, a == 500], BANDS[:4], BANDS[4]), index=k.index)
    sd = k.amount.groupby(b).sum() / k.amount.sum()
    sn = b.value_counts(normalize=True)
    ym = k.assign(m=(a == 500)).groupby('yr').apply(lambda g: g.amount[g.m].sum() / g.amount.sum())
    sf = k[place(k) == 'SF']
    V = {'max_share': float(sd[BANDS[3]]), 'max_n_share': float(sn[BANDS[3]]), 'u100': float(sd[BANDS[0]]), 'u100_n_share': float(sn[BANDS[0]]),
         'over': float(sd.get(BANDS[4], 0)), 'total': float(k.amount.sum()), 'min_y': float(ym.min()), 'max_y': float(ym.max()), 'y2024': float(ym[2024]),
         'sf_max': float(sf.amount[sf.amount.round(2) == 500].sum() / sf.amount.sum()), 'ge250': float(sd[BANDS[2]] + sd[BANDS[3]] + sd.get(BANDS[4], 0))}
    CH = {'x': BANDS, 'v': [100 * float(sd.get(x, 0)) for x in BANDS]}
    return V, CH


VERIFY = {k[2:]: v for k, v in globals().items() if k.startswith('v_') and callable(v)}

# =================================================================================================================== contract
THEMES = {'campaign-money', 'reforms', 'behested', 'lobbying', 'nonprofits', 'transparency'}
CHARTS = {'line', 'bar', 'hbar', 'dumbbell', 'slope', 'stacked', 'smallmultiples', 'scatter', 'waterfall'}
REQ = ['id', 'rank', 'theme', 'title', 'dek', 'why_it_matters', 'numbers', 'chart', 'robustness', 'caveats', 'explore', 'departments', 'tags']


def views():
    t = open(os.path.join(PROJ, 'site', 'js', 'app.js')).read()
    m = re.search(r"nw: \{.*?views: \[([^\]]*)\]", t)
    return set(re.findall(r"'([\w-]+)'", m.group(1)))


def depts():
    return set(pd.read_csv(os.path.join(PROJ, 'performance', 'data', 'interim', 'dept_fy.csv'), usecols=['dept']).dept)


def keys_used(tpl):
    ks = set()

    def walk(o):
        if isinstance(o, str):
            ks.update(k for k, _ in spec.PH.findall(o))
            if o.startswith('@V:'):
                ks.add(o[3:])
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, dict):
            for v in o.values(): walk(v)
    walk(tpl)
    return ks


def close(a, b, rel=0.005, ab=0.01):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (str, bool)) or isinstance(b, (str, bool)):
        return a == b
    a, b = float(a), float(b)
    return abs(a - b) <= max(ab * (1 if abs(a) < 2 else 0), rel * max(abs(a), abs(b)), 1e-9)


def py(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, list):
        return [py(v) for v in x]
    return x


def main():
    from build_insights import literal_digit_problems
    t0 = time.time()
    pub = json.load(open(OUTF))
    built = json.load(open(VALS))
    fails, per = [], []
    for k in ('sample', 'as_of', 'dashboard', 'intro', 'insights'):
        if k not in pub: fails.append(f'top-level field missing: {k}')
    if pub.get('sample') is not False: fails.append('sample must be false')
    if pub.get('dashboard') != 'network': fails.append('dashboard must be network')
    ids = [i['id'] for i in pub['insights']]; ranks = [i['rank'] for i in pub['insights']]
    if len(set(ids)) != len(ids): fails.append('duplicate ids')
    if sorted(ranks) != list(range(1, len(ranks) + 1)): fails.append('ranks are not 1..n')
    if len(pub['insights']) != len(spec.INSIGHTS): fails.append('insight count differs from spec')
    VW, DP = views(), depts()
    by_id = {i['id']: i for i in pub['insights']}
    for tpl in spec.INSIGHTS:
        iid, key = tpl['id'], tpl['key']
        ins = by_id.get(iid)
        rec = {'id': iid, 'values_checked': 0, 'chart_points_checked': 0, 'failures': []}
        F = rec['failures']
        if ins is None:
            fails.append(f'{iid}: missing from insights.json'); continue
        for f in REQ:
            if f not in ins: F.append(f'missing field {f}')
        if ins['theme'] not in THEMES: F.append(f'bad theme {ins["theme"]}')
        ch = ins['chart']
        if ch['type'] not in CHARTS: F.append(f'bad chart type {ch["type"]}')
        if ins['robustness']['verdict'] not in ('robust', 'fragile'): F.append('bad verdict')
        if len(ins['robustness']['checks']) < 3: F.append('fewer than 3 robustness checks')
        if ins['explore']['view'] not in VW: F.append(f'unknown view {ins["explore"]["view"]}')
        for pk in ins['explore'].get('params', {}):
            if pk not in ('years', 'flow', 'etype', 'amt', 'id') and not pk.startswith('v.'): F.append(f'unknown explore param {pk}')
        if len(ins['title']) > 92: F.append(f'title longer than 92 characters ({len(ins["title"])})')
        for s in ch['series']:
            if len(s['values']) != len(ch['x']['values']): F.append(f'series {s["name"]} length differs from x')
        for d in ins['departments']:
            if d not in DP: F.append(f'unknown department code {d}')
        for n in ins['numbers']:
            if not n.get('source'): F.append(f'number without source: {n["label"]}'); continue
            for part in n['source'].split(';'):
                path = part.strip().split(' ')[0].split('#')[0]
                if path.startswith('network/') and not os.path.exists(os.path.join(PROJ, path)):
                    F.append(f'source path does not exist: {path}')
        for p in literal_digit_problems(tpl):
            F.append(f'literal number in template: {p}')
        try:
            V2, CH2 = VERIFY[key]()
            V2 = {k: py(v) for k, v in V2.items()}; CH2 = {k: py(list(v)) for k, v in CH2.items()}
        except Exception as ex:  # noqa
            import traceback; traceback.print_exc()
            F.append(f'recompute error: {ex!r}'); per.append(rec); fails += [f'{iid}: {x}' for x in F]; continue
        V1, CH1 = built[iid]['V'], built[iid]['CH']
        body = {kk: vv for kk, vv in tpl.items() if kk != 'key'}
        for k in sorted(keys_used(body)):
            rec['values_checked'] += 1
            if k not in V2:
                F.append(f'value {k} not recomputed (untraced)'); continue
            if not close(V1.get(k), V2[k]):
                F.append(f'value {k}: built {V1.get(k)} vs recomputed {V2[k]}')
        try:
            r2 = spec.render(body, {**V1, **V2}, CH2)
            for fld in ('title', 'dek', 'why_it_matters', 'surprise', 'numbers', 'robustness', 'caveats'):
                if fld in r2 and json.dumps(r2[fld], ensure_ascii=False) != json.dumps(ins.get(fld), ensure_ascii=False):
                    x1, x2 = json.dumps(ins.get(fld), ensure_ascii=False), json.dumps(r2[fld], ensure_ascii=False)
                    i0 = next((i for i, (p, q) in enumerate(zip(x1, x2)) if p != q), min(len(x1), len(x2)))
                    F.append(f'text of {fld} differs when rendered from recomputed values: "...{x1[max(0, i0 - 60):i0 + 40]}" vs "...{x2[max(0, i0 - 60):i0 + 40]}"')
            for fld in ('title', 'subtitle', 'note', 'type', 'highlight'):
                if r2['chart'].get(fld) != ch.get(fld):
                    F.append(f'chart {fld} differs')
            pairs = [('x', ch['x']['values'], r2['chart']['x']['values'])] + [(f'series {a["name"]}', a['values'], b['values']) for a, b in zip(ch['series'], r2['chart']['series'])]
            if 'ref' in ch['y'] or 'ref' in r2['chart']['y']:
                pairs.append(('y.ref', [ch['y'].get('ref', {}).get('value')], [r2['chart']['y'].get('ref', {}).get('value')]))
            if len(ch['series']) != len(r2['chart']['series']): F.append('chart series count differs')
            for nm, pa, ra in pairs:
                if len(pa) != len(ra):
                    F.append(f'published chart {nm}: length differs'); continue
                for i, (x, y) in enumerate(zip(pa, ra)):
                    rec['chart_points_checked'] += 1
                    ok = (x == y) if (isinstance(x, str) or isinstance(y, str) or x is None or y is None) else close(x, y, rel=0.01, ab=0.05)
                    if not ok: F.append(f'published chart {nm}[{i}]: {x} vs recomputed {y}')
        except Exception as ex:  # noqa
            F.append(f'render error: {ex!r}')
        for ck, arr in CH1.items():
            if ck not in CH2:
                F.append(f'chart array {ck} not recomputed'); continue
            a2 = CH2[ck]
            if len(arr) != len(a2):
                F.append(f'chart array {ck} length {len(arr)} vs {len(a2)}'); continue
            for i, (x, y) in enumerate(zip(arr, a2)):
                rec['chart_points_checked'] += 1
                ok = (x == y) if (isinstance(x, str) or isinstance(y, str)) else close(x, y, rel=0.01, ab=0.05)
                if not ok: F.append(f'chart {ck}[{i}]: built {x} vs recomputed {y}')
        print(f'{iid}: {rec["values_checked"]} values, {rec["chart_points_checked"]} chart points, {len(F)} failures ({time.time() - t0:.0f}s)', flush=True)
        for f in F[:15]:
            print('   FAIL', f)
        per.append(rec)
        fails += [f'{iid}: {x}' for x in F]
    rep = {'as_of': spec.AS_OF, 'insights': len(pub['insights']), 'values_checked': sum(r['values_checked'] for r in per),
           'chart_points_checked': sum(r['chart_points_checked'] for r in per), 'failures': fails, 'per_insight': per,
           'method': __doc__.strip()}
    json.dump(rep, open(REPORT, 'w'), indent=1, default=float, ensure_ascii=False)
    print(f'\n{rep["insights"]} insights, {rep["values_checked"]} values and {rep["chart_points_checked"]} chart points checked; {len(fails)} failures')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
