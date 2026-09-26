"""Normalize raw downloads into tidy tables in data/interim/*.parquet.

Tables:
  committees      one row per SF campaign filer (committee) with parsed office / candidate / kind
  contributions   Form 460 Schedule A (monetary) + C (non-monetary) receipts by SF committees
  ie              Form 496 independent expenditures (supporting/opposing candidates or measures)
  lobby_contacts  lobbyist contacts of public officials
  lobby_payments  payments promised/received by lobbyists from clients
  lobby_contribs  campaign contributions made/delivered by lobbyists (self-reported)
  behested        behested payments (FPPC 803 2015-2018, SFEC 3610b 2019+, SFEC 3600)
  f126            contract approval notifications (126f4 historic + 126F combined 2026+)
  f126_parties    affiliates/principals/subcontractors listed on 126f4 (and 126F)
  f126f2          proposal-submission notifications (named parties)
  contracts       supplier contracts (Controller)
  vendor_pay      vendor payments aggregated by FY x dept x vendor
"""
import os, re, json
import numpy as np
import pandas as pd
from names import basic, org_key, zip5, person_key, split_last_first

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'data', 'raw')
OUT = os.path.join(HERE, '..', 'data', 'interim')
os.makedirs(OUT, exist_ok=True)


def rd(name, **kw):
    return pd.read_csv(os.path.join(RAW, name + '.csv'), low_memory=False, **kw)


def d10(s):
    return pd.to_datetime(s.astype(str).str[:10], errors='coerce')


def save(df, name):
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda x: x if (x is None or isinstance(x, str) or (isinstance(x, float) and np.isnan(x))) else str(x))
            df[c] = df[c].where(df[c].notna(), None)
    df.to_parquet(os.path.join(OUT, name + '.parquet'), index=False)
    print(f'{name}: {len(df):,} rows')


# ---------------------------------------------------------------- committees
OFFICE_PATTERNS = [
    ('State office', r'\bASSEMBLY|STATE SENATE|\bSENATE\b|EQUALIZATION|\bCONGRESS|GOVERNOR|LIEUTENANT|INSURANCE COMMISSIONER|SECRETARY OF STATE|STATE CONTROLLER|STATE TREASURER|ATTORNEY GENERAL|\bASM\b|\bSEN\b'),
    ('Retirement/Health boards', r'RETIREE HEALTH|HEALTH SERVICE|RETIREMENT BOARD|RETIREMENT SYSTEM'),
    ('BART Board', r'\bBART\b'),
    ('Democratic County Central Committee', r'\bDCCC\b|\bSFDCCC\b|DEMOCRATIC COUNTY|COUNTY CENTRAL|CENTRAL COMMITTEE|CENTRAL COMMITEE|DEMOCRATIC PARTY'),
    ('Republican County Central Committee', r'REPUBLICAN'),
    ('Superior Court Judge', r'JUDGE|SUPERIOR COURT'),
    ('Community College Board', r'COLLEGE BOARD|COMMUNITY COLLEGE|CITY COLLEGE|\bCCSF\b|COLLEGE'),
    ('Board of Education', r'SCHOOL BOARD|BOARD OF EDUCATION|EDUCATION|\bSFUSD\b'),
    ('Mayor', r'\bMAYOR'), ('City Attorney', r'CITY ATTORNEY'), ('District Attorney', r'DISTRICT ATTORNEY|\bDA\b'),
    ('Board of Supervisors', r'\bSUPERVISOR|\bBOARD OF SUP|\bBOS\b|\bDISTRICT \d+\b|\bD\d{1,2}\b'),
    ('Sheriff', r'\bSHERIFF'), ('Treasurer', r'TREASURER'), ('Assessor-Recorder', r'ASSESSOR'),
    ('Public Defender', r'PUBLIC DEFENDER'),
]
CAL_CODES = {'MAY': 'Mayor', 'SUP': 'Board of Supervisors', 'CAT': 'City Attorney', 'DAT': 'District Attorney',
             'SHC': 'Sheriff', 'TRE': 'Treasurer', 'ASR': 'Assessor-Recorder', 'PDR': 'Public Defender',
             'ASM': 'State office', 'SEN': 'State office', 'BOE': 'State office', 'GOV': 'State office'}
CITY_ELECTIVE = {'Mayor', 'Board of Supervisors', 'City Attorney', 'District Attorney', 'Sheriff', 'Treasurer',
                 'Assessor-Recorder', 'Public Defender', 'Board of Education', 'Community College Board'}


def parse_office(text):
    t = basic(text)
    for off, rx in OFFICE_PATTERNS:
        if re.search(rx, t):
            return off
    return None


def committees(tx):
    f = rd('cf_filers')
    f['filer_nid'] = f.filer_nid.astype(str)
    # office info reported on cover pages / transactions for each filer
    cov = tx[tx.office_description.notna() | tx.office_code.notna()][['filer_nid', 'office_code', 'office_description', 'election_date']]
    cov = cov.groupby('filer_nid').agg(office_code=('office_code', lambda s: s.dropna().mode().iat[0] if s.dropna().size else None),
                                       office_desc=('office_description', lambda s: s.dropna().mode().iat[0] if s.dropna().size else None)).reset_index()
    f = f.merge(cov, on='filer_nid', how='left')
    f['office'] = [parse_office(n) or parse_office(a) or CAL_CODES.get(str(b).upper()) if ft in ('Candidate or Officeholder', 'Primarily Formed Candidate', '470 [Officeholder]') else None
                   for a, b, n, ft in zip(f.office_desc.fillna(''), f.office_code.fillna(''), f.filer_name.fillna(''), f.filer_type)]
    n = f.filer_name.fillna('').str.upper()
    kind = np.select([
        f.filer_type.isin(['Candidate or Officeholder', '470 [Officeholder]']),
        f.filer_type.eq('Primarily Formed Candidate'),
        f.filer_type.eq('Primarily Formed Measure'),
        f.filer_type.eq('Independent Expenditure'),
        f.filer_type.eq('General Purpose'),
        f.filer_type.eq('Major Donor'),
        f.filer_type.eq('Slate Mailer'),
    ], ['candidate', 'candidate_pf', 'ballot_measure', 'independent_expenditure', 'general_purpose', 'major_donor', 'slate_mailer'], 'other')
    f['kind'] = kind
    # controlled committees: "... controlled by Supervisor X" / "Mayor X's ..." etc.
    ctl = n.str.extract(r'(?:CONTROLLED BY|SPONSORED BY)\s+(.*?)(?:\(|$|,)', expand=False)
    f['controlled_by_text'] = ctl.str.strip()
    # only the candidate's own committee counts; 'candidate_pf' committees are third-party committees formed to support/oppose a candidate
    f['is_city_candidate'] = f.office.isin(CITY_ELECTIVE) & f.kind.eq('candidate')
    return f


# ---------------------------------------------------------------- campaign transactions
def load_tx():
    tx = rd('cf_transactions', dtype=str)
    for c in ['calculated_amount', 'transaction_amount_1', 'transaction_amount_2']:
        tx[c] = pd.to_numeric(tx[c], errors='coerce')
    tx['filer_nid'] = tx.filer_nid.astype(str)
    tx['date'] = d10(tx.calculated_date.fillna(tx.transaction_date))
    return tx


def contributions(tx, com):
    c = tx[tx.form_type.isin(['A', 'C'])].copy()
    c = c[c.memo_code.astype(str).str.lower() != 'true']
    c['schedule'] = c.form_type
    c['amount'] = c.calculated_amount
    c['entity_code'] = c.entity_code.fillna('')
    c['is_individual'] = c.entity_code.eq('IND')
    c['donor_last'] = c.transaction_last_name.fillna('')
    c['donor_first'] = c.transaction_first_name.fillna('')
    c['donor_name'] = np.where(c.is_individual, (c.donor_first + ' ' + c.donor_last).str.strip(), c.donor_last)
    c['zip5'] = c.transaction_zip.map(zip5)
    c['city'] = c.transaction_city.fillna('').map(basic)
    c['state'] = c.transaction_state.fillna('').str.upper().str.strip()
    c['employer'] = c.transaction_employer.fillna('')
    c['occupation'] = c.transaction_occupation.fillna('')
    c['person_key'] = [person_key(f, l) if ind else '' for f, l, ind in zip(c.donor_first, c.donor_last, c.is_individual)]
    c['org_key'] = [org_key(n) if not ind else '' for n, ind in zip(c.donor_last, c.is_individual)]
    keep = ['element_nid', 'filing_nid', 'filer_nid', 'filer_name', 'schedule', 'date', 'amount', 'entity_code', 'is_individual',
            'donor_first', 'donor_last', 'donor_name', 'city', 'state', 'zip5', 'employer', 'occupation', 'person_key',
            'org_key', 'intermediary_first_name', 'intermediary_last_name', 'intermediary_employer', 'intermediary_committee_id',
            'transaction_description', 'transaction_type', 'filing_date']
    c = c[keep].merge(com[['filer_nid', 'fppc_id', 'filer_type', 'kind', 'office', 'candidate_name', 'is_city_candidate', 'controlled_by_text']]
                      .rename(columns={'filer_type': 'recip_filer_type', 'kind': 'recip_kind', 'office': 'recip_office',
                                       'candidate_name': 'recip_candidate', 'fppc_id': 'recip_fppc_id'}),
                      on='filer_nid', how='left')
    # transfers: contributor is itself a committee (entity COM / SCC / PTY) -> not an original source
    c['is_committee_donor'] = c.entity_code.isin(['COM', 'SCC', 'PTY'])
    return c


def independent_expenditures(tx, com):
    e = tx[tx.form_type.isin(['F496'])].copy()
    e['amount'] = e.calculated_amount
    e['target_candidate'] = (e.candidate_first_name.fillna('') + ' ' + e.candidate_last_name.fillna('')).str.strip()
    e = e[['element_nid', 'filer_nid', 'filer_name', 'date', 'amount', 'support_oppose_code', 'target_candidate',
           'ballot_name', 'ballot_number', 'office_code', 'office_description', 'transaction_description', 'filing_date']]
    e = e.merge(com[['filer_nid', 'filer_type', 'kind']], on='filer_nid', how='left')
    return e


# ---------------------------------------------------------------- lobbying
def lobbying():
    l = rd('lob_activity', dtype=str)
    l['amount'] = pd.to_numeric(l.amount, errors='coerce')
    l['date'] = d10(l.date)
    cont = l[l.type == 'ContactOfPublicOfficial'].copy()
    cont = cont[['id', 'fromfiling', 'date', 'lobbyistname', 'lobbyisttype', 'firmname', 'clientname', 'officialname',
                 'departmentname', 'subjectarea', 'issue', 'filenumber', 'outcomesought']]
    pay = l[l.type == 'PaymentReceived'][['id', 'fromfiling', 'date', 'lobbyistname', 'firmname', 'clientname', 'clientcity',
                                         'clientstate', 'clientzip', 'amount']].copy()
    contrib = l[l.type == 'CampaignContributionMade'][['id', 'fromfiling', 'date', 'lobbyistname', 'firmname', 'amount',
                                                      'candidatename', 'committeename', 'fppcid', 'sourceoffunds']].copy()
    p2i = l[l.type == 'PaymentsToInfluence'].copy()
    # drop activities on superseded filings
    fl = rd('lob_filings', dtype=str)
    sup = set(fl.loc[fl.issuperceded.astype(str).str.lower() == 'true', 'id'])
    for df in (cont, pay, contrib):
        df.drop(df[df.fromfiling.isin(sup)].index, inplace=True)
    return cont, pay, contrib, p2i, len(sup)


# ---------------------------------------------------------------- behested payments
def behested():
    rows = []
    b = rd('bp_803_2015_2018')
    for r in b.itertuples():
        rows.append(dict(source='FPPC 803 (2015-2018)', official=f'{r.elected_officer_first_name} {r.elected_officer_last_name}'.strip(),
                         agency=r.agency_name, payor=r.payor_name, payee=r.payee_name, amount=r.amount,
                         date=r.period_end_date if isinstance(r.period_end_date, str) else r.date_filed,
                         filed=r.date_filed, purpose=getattr(r, 'purpose', None), filing_type=r.amendment,
                         url=r.filing if isinstance(r.filing, str) else None, filing_id=r.filing if isinstance(r.filing, str) else None))
    j = rd('bp_3610b_payors_joined')
    j.columns = [c.replace('sfecformbcityofficerbehestedpaymentfilings_', '') for c in j.columns]
    for r in j.itertuples():
        rows.append(dict(source='SFEC 3610(b) (2019+)', official=r.officername, agency=r.agencyname, payor=r.payorname,
                         payee=r.payeename, amount=r.pmtamt, date=r.pmtdate, filed=r.datesigned, purpose=r.purposetype,
                         description=r.paymentdescription, filing_type=r.filingtype, url=r.filing, filing_id=r.docusignid,
                         payment_type=r.paymenttype))
    f36 = rd('bp_3600_filings'); p36 = rd('bp_3600_payors')
    if len(f36) and len(p36) and 'docusignid' in p36.columns:
        m = p36.merge(f36, on='docusignid', how='left', suffixes=('', '_f'))
        for r in m.to_dict('records'):
            rows.append(dict(source='SFEC 3600 (commissioners)', official=r.get('membername') or r.get('officername'),
                             agency=r.get('boardcommissionname') or r.get('agencyname'), payor=r.get('payorname'),
                             payee=r.get('payeename'), amount=r.get('pmtamt') or r.get('amount'), date=r.get('pmtdate'),
                             filed=r.get('datesigned'), filing_id=r.get('docusignid'), url=r.get('filing')))
    bp = pd.DataFrame(rows)
    bp['date'] = d10(bp.date)
    bp['filed'] = d10(bp.filed)
    bp['amount'] = pd.to_numeric(bp.amount, errors='coerce')
    return bp


# ---------------------------------------------------------------- contract notifications
def f126():
    h = rd('f126f4_filings_hist', dtype=str)
    h['date_signed'] = d10(h.datesigned.fillna(h.uploadeddate))
    h['contract_date'] = d10(h.contractdate)
    h = h.rename(columns={'contractorname': 'contractor', 'electiveofficername': 'officer', 'electiveofficeroffice': 'office',
                          'contractdescription': 'description', 'departmentcontactdepartmentname': 'department',
                          'descriptionofamount': 'amount_text', 'contractfilenumber': 'file_number', 'boardname': 'board',
                          'contractoraddress': 'contractor_address'})
    h['source'] = 'SFEC 126f4 (hist)'
    h['filing_key'] = np.where(h.docusignid.eq('legacy filing') | h.docusignid.isna(), 'legacy:' + h.filing.fillna(pd.Series(h.index.astype(str), index=h.index)), h.docusignid)
    keep = ['filing_key', 'docusignid', 'filing', 'filingtype', 'source', 'date_signed', 'contract_date', 'contractor', 'contractor_address',
            'officer', 'office', 'board', 'department', 'description', 'amount_text', 'file_number', 'bidrfpnumber']
    h = h[keep]
    m = rd('f126_combined', dtype=str)
    m4 = m[m.form_type.isin(['f4', 'f4_ceo'])].copy()
    g = m4.groupby('filing_id').agg(date_signed=('filing_date', 'first'), contract_date=('contract_approval_date', 'first'),
                                    contractor=('contractor_name', 'first'), officer=('city_elective_officer', 'first'),
                                    office=('office_or_board', 'first'), department=('office', 'first'),
                                    description=('contract_description', 'first'), amount_text=('contract_amount', 'first'),
                                    file_number=('file_number_bos', 'first'), bidrfpnumber=('bid_rfp_number', 'first'),
                                    filingtype=('type_of_filing', 'first'), board=('contract_approved_by', 'first')).reset_index()
    g['date_signed'] = d10(g.date_signed); g['contract_date'] = d10(g.contract_date)
    g['filing_key'] = g.filing_id; g['docusignid'] = None; g['filing'] = None; g['source'] = 'SFEC 126F (2026+)'
    g['contractor_address'] = None
    allf = pd.concat([h, g[keep]], ignore_index=True)
    allf['contract_amount'] = pd.to_numeric(allf.amount_text.astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce')
    allf['contractor_key'] = allf.contractor.map(org_key)

    p = rd('f126f4_parties', dtype=str)
    p = p.rename(columns={'partytype': 'party_type', 'partylastname': 'last', 'partyfirstname': 'first', 'contractorname': 'contractor'})
    p['filing_key'] = np.where(p.docusignid.eq('legacy filing') | p.docusignid.isna(), 'legacy:' + p.filing.fillna(''), p.docusignid)
    p['date_signed'] = d10(p.datesigned)
    p['contract_date'] = d10(p.contractdate)
    p = p[['filing_key', 'party_type', 'first', 'last', 'contractor', 'date_signed', 'contract_date', 'electiveofficername', 'electiveofficeroffice', 'boardname']]
    mp = m4[['filing_id', 'entity_or_contractor_type', 'first_name', 'last_name', 'entity_or_sub_contractor_name', 'contractor_name', 'filing_date', 'contract_approval_date', 'city_elective_officer', 'office_or_board']].copy()
    mp['last'] = mp.last_name.fillna(mp.entity_or_sub_contractor_name)
    mp = mp.rename(columns={'filing_id': 'filing_key', 'entity_or_contractor_type': 'party_type', 'first_name': 'first', 'contractor_name': 'contractor',
                            'city_elective_officer': 'electiveofficername', 'office_or_board': 'electiveofficeroffice'})
    mp['date_signed'] = d10(mp.filing_date); mp['contract_date'] = d10(mp.contract_approval_date); mp['boardname'] = None
    parties = pd.concat([p, mp[p.columns]], ignore_index=True)
    parties['is_person'] = parties['first'].notna() & (parties.party_type.fillna('') != 'Subcontractor')
    parties['contractor_key'] = parties.contractor.map(org_key)

    f2 = rd('f126f2_filings_hist', dtype=str); n2 = rd('f126f2_named', dtype=str)
    f2m = n2.merge(f2, on='docusignid', how='left')
    f2m['proposal_date'] = d10(f2m.proposaldate)
    f2m['date_signed'] = d10(f2m.datesigned)
    f2m = f2m[['docusignid', 'contractorname', 'contractortype', 'proposal_date', 'date_signed', 'cityagencyname', 'natureofcontract', 'bidrfpnumber', 'filenumber']]
    m2 = m[m.form_type == 'f2'][['filing_id', 'contractor_or_subcontractor_name', 'contractor_type', 'date_proposal_submitted', 'filing_date', 'office', 'contract_description', 'bid_rfp_number', 'file_number_bos']].copy()
    m2.columns = f2m.columns
    m2['proposal_date'] = d10(m2.proposal_date); m2['date_signed'] = d10(m2.date_signed)
    f2all = pd.concat([f2m, m2], ignore_index=True)
    f2all['contractor_key'] = f2all.contractorname.map(org_key)
    return allf, parties, f2all


def contracts():
    s = rd('supplier_contracts', dtype=str)
    for c in ['agreed_amt', 'consumed_amt', 'pmt_amt', 'remaining_amt']:
        s[c] = pd.to_numeric(s[c], errors='coerce')
    s['term_start'] = d10(s.term_start_date); s['term_end'] = d10(s.term_end_date)
    s['prime_key'] = s.prime_contractor.map(org_key)
    s['supplier_key'] = s.project_team_supplier.map(org_key)
    return s


def vendor_pay():
    v = rd('vendor_pay_agg', dtype={'vendor': str})
    v['fiscal_year'] = pd.to_numeric(v.fiscal_year, errors='coerce')
    v['vendor_key'] = v.vendor.map(org_key)
    return v


def main():
    tx = load_tx()
    print('transactions loaded', len(tx))
    com = committees(tx); save(com, 'committees')
    c = contributions(tx, com); save(c, 'contributions')
    save(independent_expenditures(tx, com), 'ie')
    # committee-level payments to others (Schedule D contributions made, E payments) kept for transfers/IE analysis
    d = tx[tx.form_type.isin(['D'])][['element_nid', 'filer_nid', 'filer_name', 'date', 'calculated_amount', 'transaction_last_name',
                                      'transaction_first_name', 'candidate_first_name', 'candidate_last_name', 'ballot_name',
                                      'support_oppose_code', 'office_description', 'entity_code']].rename(columns={'calculated_amount': 'amount'})
    save(d, 'contribs_made')
    del tx
    cont, pay, lcontrib, p2i, nsup = lobbying()
    print('superseded lobbyist filings dropped:', nsup)
    save(cont, 'lobby_contacts'); save(pay, 'lobby_payments'); save(lcontrib, 'lobby_contribs'); save(p2i.astype(str), 'lobby_p2i')
    save(behested(), 'behested')
    f, parties, f2 = f126()
    save(f, 'f126'); save(parties, 'f126_parties'); save(f2, 'f126f2')
    save(contracts(), 'contracts')
    save(vendor_pay(), 'vendor_pay')
    # small extras
    save(rd('f124_filings', dtype=str), 'f124_filings'); save(rd('f124_contracts', dtype=str), 'f124_contracts')
    m = rd('f1145_contribs', dtype=str).merge(rd('f1145_filings', dtype=str), on='docusignid', how='left')
    save(m, 'f1145')
    m = rd('f125_contribs', dtype=str).merge(rd('f125_filings', dtype=str), on='docusignid', how='left')
    save(m, 'f125')
    save(rd('dev_3500', dtype=str), 'dev_3500')
    save(rd('bp_waivers', dtype=str), 'bp_waivers')
    save(rd('f700_cover', dtype=str), 'f700_cover')
    save(rd('lob_directory', dtype=str), 'lob_directory')
    save(rd('enforcement', dtype=str), 'enforcement')


if __name__ == '__main__':
    main()
