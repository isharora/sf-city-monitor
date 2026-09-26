"""Red team: independent re-derivation of key numbers and sensitivity runs.

1. Re-derive totals with server-side SoQL aggregates on data.sf.gov (independent of our download, normalization and entity
   resolution) and compare with pipeline numbers.
2. Re-derive the contractor-ban window count with a deliberately simple, separate code path working from the raw CSVs:
   exact (normalized) first+last name equality between 126f4 principals and donors, no Claude, no entity resolution,
   covered committees = own candidate committees for the filing's office(s).
3. Collect the sensitivity runs (09_analysis.py with --variant strict/lenient and --person-t 0.7/0.9/0.95).
Writes data/analysis/redteam.json
"""
import os, re, json, subprocess, urllib.parse, importlib.util
import numpy as np
import pandas as pd
from names import basic, canon_first

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'data', 'raw')
INT = os.path.join(HERE, '..', 'data', 'interim')
AN = os.path.join(HERE, '..', 'data', 'analysis')


def soql(ds, **q):
    url = f'https://data.sf.gov/resource/{ds}.json?' + urllib.parse.urlencode({f'${k}': v for k, v in q.items()})
    out = subprocess.run(['perl', '-e', 'alarm 120; exec @ARGV', 'curl', '-sS', '--fail', url], capture_output=True, text=True)
    return json.loads(out.stdout)


def main():
    res = {}
    # ---- 1. server-side aggregates
    api = soql('pitq-e56w', select='date_extract_y(calculated_date) as y, sum(calculated_amount) as s, count(*) as n',
               where="form_type in ('A','C') and calculated_date >= '2015-01-01' and calculated_date < '2026-01-01' and (memo_code is null or memo_code = false)",
               group='y', order='y', limit=50)
    c = pd.read_parquet(os.path.join(INT, 'contributions.parquet'), columns=['date', 'amount'])
    ours = c[(c.date >= '2015-01-01') & (c.date < '2026-01-01')].groupby(c.date.dt.year).amount.agg(['sum', 'size'])
    res['schedule_A_C_by_year'] = [dict(year=int(float(r['y'])), api_sum=float(r['s']), api_n=int(r['n']), ours_sum=float(ours.loc[int(float(r['y'])), 'sum']),
                                        ours_n=int(ours.loc[int(float(r['y'])), 'size'])) for r in api if r.get('y')]
    api126 = soql('ite2-5y3b', select='count(*) as n')
    res['f126f4_hist_rows_api'] = int(api126[0]['n'])
    res['f126f4_hist_rows_ours'] = int(len(pd.read_csv(os.path.join(RAW, 'f126f4_filings_hist.csv'), usecols=[0])))
    a803 = soql('98wa-4d49', select='sum(amount) as s, count(*) as n')
    res['fppc803_api'] = {'sum': float(a803[0]['s']), 'n': int(a803[0]['n'])}
    a3610 = soql('b3ya-imj5', select='sum(pmtamt) as s, count(*) as n')
    res['sfec3610b_api'] = {'sum': float(a3610[0]['s']), 'n': int(a3610[0]['n'])}
    alob = soql('s4ub-8j3t', select='count(*) as n', where="type='ContactOfPublicOfficial'")
    res['lobby_contacts_api'] = int(alob[0]['n'])
    res['lobby_contacts_ours'] = int(len(pd.read_parquet(os.path.join(INT, 'lobby_contacts.parquet'))))
    # the largest case, checked directly against the source rows
    g = soql('pitq-e56w', select='filer_name, transaction_first_name, transaction_last_name, calculated_amount, calculated_date, transaction_employer, form_type',
             where="upper(transaction_last_name)='GANDHI' and upper(transaction_first_name) like 'SAMEER%' and upper(filer_name) like '%FARRELL%'", limit=20)
    res['largest_case_source_rows'] = [{k: v for k, v in r.items() if k != 'transaction_employer'} | {'employer_given': bool(r.get('transaction_employer'))} for r in g]
    p = soql('czjm-dat8', select='partytype, partyfirstname, partylastname, contractorname, datesigned, electiveofficername',
             where="upper(partylastname)='GANDHI' and upper(partyfirstname) like 'SAMEER%'", limit=20)
    res['largest_case_126f4_rows'] = p

    # ---- 2. simple independent recount of the post-approval window count (2019+ approvals)
    f = pd.read_csv(os.path.join(RAW, 'f126f4_filings_hist.csv'), low_memory=False, dtype=str)
    f['D'] = pd.to_datetime(f.datesigned.fillna(f.uploadeddate).str[:10], errors='coerce')
    f['key'] = np.where(f.docusignid.eq('legacy filing') | f.docusignid.isna(), 'legacy:' + f.filing.fillna(''), f.docusignid)
    txt = (f.electiveofficername.fillna('') + ' ' + f.electiveofficeroffice.fillna('')).str.upper()
    f['bos'] = txt.str.contains('SUPERVISORS'); f['mayor'] = txt.str.contains(r'\bMAYOR\b')
    f = f[(f.D >= '2019-01-01') & (f.bos | f.mayor)]
    pa = pd.read_csv(os.path.join(RAW, 'f126f4_parties.csv'), low_memory=False, dtype=str)
    pa = pa[pa.partyfirstname.notna() & (pa.partytype != 'Subcontractor')]
    pa['key'] = np.where(pa.docusignid.eq('legacy filing') | pa.docusignid.isna(), 'legacy:' + pa.filing.fillna(''), pa.docusignid)
    pa['nk'] = pa.partylastname.map(basic) + '|' + pa.partyfirstname.map(lambda s: basic(s).split(' ')[0] if basic(s) else '')
    pa = pa.merge(f[['key', 'D', 'bos', 'mayor']], on='key')
    com = pd.read_csv(os.path.join(RAW, 'cf_filers.csv'), dtype=str)
    com = com[com.filer_type == 'Candidate or Officeholder']
    nm = com.filer_name.str.upper()
    com_bos = set(com[nm.str.contains('SUPERVISOR')].filer_nid)
    com_may = set(com[nm.str.contains('MAYOR')].filer_nid)
    tx = pd.read_csv(os.path.join(RAW, 'cf_transactions.csv'), dtype=str, usecols=['form_type', 'entity_code', 'transaction_first_name', 'transaction_last_name',
                                                                                  'calculated_amount', 'calculated_date', 'filer_nid', 'element_nid'])
    tx = tx[tx.form_type.isin(['A', 'C']) & (tx.entity_code == 'IND')]
    tx['nk'] = tx.transaction_last_name.map(basic) + '|' + tx.transaction_first_name.map(lambda s: basic(s).split(' ')[0] if basic(s) else '')
    tx['date'] = pd.to_datetime(tx.calculated_date.str[:10], errors='coerce')
    tx['amt'] = pd.to_numeric(tx.calculated_amount, errors='coerce')
    tx = tx[tx.nk.isin(set(pa.nk))]
    m = pa.merge(tx, on='nk')
    d = (m.date - m.D).dt.days
    m = m[(d > 0) & (d <= 365)]
    m = m[(m.bos & m.filer_nid.isin(com_bos)) | (m.mayor & m.filer_nid.isin(com_may))]
    u = m.drop_duplicates(['element_nid', 'nk'])
    res['simple_recount_post_window_2019plus'] = {
        'method': 'exact normalized name equality (no nickname handling, no Claude, no employer check), own candidate committees for Supervisor/Mayor only, approvals 2019+ by BOS/Mayor',
        'n_contributions': int(len(u)), 'amount': float(u.amt.sum()), 'n_distinct_names': int(u.nk.nunique())}
    ours = pd.read_parquet(os.path.join(AN, 'contractor_ban_cases.parquet'))
    o = ours[(ours.days_from_approval > 0) & (ours.approval_proxy_date >= '2019-01-01')]
    res['pipeline_post_window_2019plus'] = {'n_contributions': int(len(o)), 'amount': float(o.amount.sum()), 'n_distinct_contributors': int(o.contributor_node.nunique())}

    # ---- 3. sensitivity runs
    sens = {}
    for tag in ['', 'strict', 'lenient', 'p070', 'p090', 'p095']:
        pth = os.path.join(AN, tag, 'contractor_ban.json') if tag else os.path.join(AN, 'contractor_ban.json')
        if not os.path.exists(pth):
            continue
        b = json.load(open(pth))
        br = json.load(open(os.path.join(os.path.dirname(pth), 'contractor_base_rates.json')))
        bh = json.load(open(os.path.join(os.path.dirname(pth), 'behested.json'))) if os.path.exists(os.path.join(os.path.dirname(pth), 'behested.json')) else {}
        nl = json.load(open(os.path.join(os.path.dirname(pth), 'nonprofit_loop.json'))) if os.path.exists(os.path.join(os.path.dirname(pth), 'nonprofit_loop.json')) else {}
        sens[tag or 'default'] = {
            'post_window_contributions': b['post_approval']['n_contributions'], 'post_window_amount': b['post_approval']['amount'],
            'post_window_contractors': b['post_approval']['n_contractors'], 'post_window_contributors': b['post_approval'].get('n_contributors'),
            'share_contractors_with_principal_giving_ever': br['share_126f4_contractors_with_matched_principal_giving_to_city_candidates_ever'],
            'placebo_ratio_W0_to_baseline': br['timing_placebo']['ratio_W0_to_baseline'],
            'observed_vs_expected_share': [br.get('observed_share_inside_window_2019_2025'), br.get('expected_share_if_unrelated')],
            'behested_pending_share': (bh.get('pending_business') or {}).get('share_with_lobbying_or_approval_same_official_or_body_12m'),
            'nonprofits_with_principal_giving': nl.get('n_with_principal_giving'),
        }
    res['sensitivity'] = sens
    json.dump(res, open(os.path.join(AN, 'redteam.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k not in ('largest_case_source_rows',)}, indent=1, default=str)[:6000])


if __name__ == '__main__':
    main()
