"""Download raw data from data.sf.gov (read-only). Every HTTP call has a hard timeout via perl alarm.

Usage: python3 01_download.py [dataset_key ...]   (no args = all)
Outputs CSV files in ../data/raw/<key>.csv and a manifest ../data/raw/manifest.json with row counts.
"""
import csv, io, json, os, subprocess, sys, time, urllib.parse

RAW = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
BASE = 'https://data.sf.gov/resource/{id}.csv'

TX_COLS = ("filing_id_number,filing_date,start_date,end_date,fppc_id,filer_name,filer_type,filer_nid,filing_nid,"
           "filing_type,calculated_amount,calculated_date,form_type,transaction_id,transaction_first_name,"
           "transaction_last_name,transaction_amount_1,transaction_amount_2,transaction_date,transaction_description,"
           "transaction_city,transaction_state,transaction_zip,transaction_occupation,transaction_employer,"
           "transaction_self,transaction_code,intermediary_committee_id,intermediary_first_name,intermediary_last_name,"
           "intermediary_employer,office_sought_held,office_code,office_description,jurisdiction_code,"
           "jurisdiction_description,support_oppose_code,ballot_name,ballot_number,ballot_jurisdiction,"
           "candidate_first_name,candidate_last_name,election_date,transaction_type,record_type,entity_code,"
           "memo_code,is_itemized,element_nid,back_reference_id,cross_reference_match,committee_id")

DATASETS = {
    # campaign finance
    'cf_transactions': dict(id='pitq-e56w', select=TX_COLS, page=100000),
    'cf_filers': dict(id='4c8t-ngau'),
    'cf_filings': dict(id='qizs-bwft'),
    'cf_summary': dict(id='9ggq-m8hp'),
    'cf_datakey': dict(id='wygs-cc76'),
    'f124_filings': dict(id='tsy6-7xfs'),
    'f124_contracts': dict(id='ssx6-3d9r'),
    'f1145_filings': dict(id='hyuc-khdi'),
    'f1145_contribs': dict(id='mq45-f9zi'),
    'f125_filings': dict(id='wv58-ismt'),
    'f125_contribs': dict(id='dzp4-4my5'),
    'f125_officers': dict(id='x9je-gi3q'),
    # behested payments
    'bp_803_2015_2018': dict(id='98wa-4d49'),
    'bp_3610b_payors_joined': dict(id='b3ya-imj5'),
    'bp_3610b_filings': dict(id='7vmk-cq9e'),
    'bp_3600_filings': dict(id='59sr-386y'),
    'bp_3600_payors': dict(id='ibrg-quig'),
    'bp_waivers': dict(id='8w9a-q5s8'),
    # lobbyists
    'lob_activity': dict(id='s4ub-8j3t', page=100000),
    'lob_filings': dict(id='vckx-s5ks'),
    'lob_directory': dict(id='b947-pj2q'),
    'lob_city_reports': dict(id='3gjj-sffk'),
    'permit_consult_reg': dict(id='umwe-sn9p'),
    'permit_consult_q': dict(id='k2rm-926a'),
    # contract notifications
    'f126_combined': dict(id='mczm-4vxi'),
    'f126f4_parties': dict(id='czjm-dat8', page=100000),
    'f126f4_filings_hist': dict(id='ite2-5y3b'),
    'f126f2_named': dict(id='djj2-gvaq'),
    'f126f2_filings_hist': dict(id='pv99-gzft'),
    # developers, Form 700, other
    'dev_3500': dict(id='8je3-gv3q'),
    'f700_cover': dict(id='pm9d-idh4'),
    'f700_schc': dict(id='u5rm-p23y'),
    'recusals_3209b': dict(id='y8qm-zrwi'),
    'enforcement': dict(id='yre9-mzkb'),
    # contracts / payments
    'supplier_contracts': dict(id='cqi5-hm2d'),
    'dept_codes': dict(id='j2hz-23ps'),
    'planning_projects': dict(id='qvu5-m3a2', select='record_id,record_type,project_name,record_status,project_address,'
                              'open_date,close_date,applicant_org,project_decision,project_decision_date,number_of_units_net,'
                              'environmental_document_type'),
    'vendor_pay_agg': dict(id='n9pm-xkyq', select='fiscal_year,department_code,department,vendor,non_profit_indicator,'
                           'sum(vouchers_paid) as paid,count(*) as n',
                           group='fiscal_year,department_code,department,vendor,non_profit_indicator',
                           where='vouchers_paid != 0', page=50000, order='fiscal_year,department_code,vendor,non_profit_indicator'),
    'vendor_pay_contract_agg': dict(id='n9pm-xkyq', select='fiscal_year,department_code,vendor,contract_number,'
                           'sum(vouchers_paid) as paid', group='fiscal_year,department_code,vendor,contract_number',
                           where="vouchers_paid != 0 AND fiscal_year >= '2016'", page=50000,
                           order='fiscal_year,department_code,vendor,contract_number'),
}


def fetch(url, t=300):
    for attempt in range(4):
        p = subprocess.run(['perl', '-e', f'alarm {t}; exec @ARGV', 'curl', '-sS', '--fail', '-A', 'sf-city-monitor-network', url],
                           capture_output=True)
        if p.returncode == 0:
            return p.stdout.decode('utf-8', errors='replace')
        print('   retry', attempt, p.returncode, p.stderr[:200], flush=True)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError('failed ' + url)


def download(key, spec):
    out = os.path.join(RAW, key + '.csv')
    page = spec.get('page', 50000)
    offset, total, header = 0, 0, None
    with open(out + '.part', 'w', newline='') as fh:
        while True:
            q = {'$limit': page, '$offset': offset}
            if spec.get('select'): q['$select'] = spec['select']
            if spec.get('group'): q['$group'] = spec['group']
            if spec.get('where'): q['$where'] = spec['where']
            q['$order'] = spec.get('order', ':id')
            url = BASE.format(id=spec['id']) + '?' + urllib.parse.urlencode(q)
            txt = fetch(url)
            rows = list(csv.reader(io.StringIO(txt)))
            if not rows:
                break
            if header is None:
                header = rows[0]
                csv.writer(fh).writerow(header)
            body = rows[1:]
            csv.writer(fh).writerows(body)
            total += len(body)
            print(f'  {key}: {total}', flush=True)
            if len(body) < page:
                break
            offset += page
    os.replace(out + '.part', out)
    return total


def main():
    keys = sys.argv[1:] or list(DATASETS)
    mpath = os.path.join(RAW, 'manifest.json')
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for k in keys:
        spec = DATASETS[k]
        t0 = time.time()
        n = download(k, spec)
        manifest[k] = dict(id=spec['id'], rows=n, downloaded=time.strftime('%Y-%m-%dT%H:%M:%S'),
                           select=spec.get('select'), group=spec.get('group'), where=spec.get('where'))
        json.dump(manifest, open(mpath, 'w'), indent=1)
        print(f'{k} ({spec["id"]}): {n} rows in {time.time()-t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
