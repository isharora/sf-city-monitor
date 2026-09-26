#!/usr/bin/env python3
"""Build nonprofits/data/outcomes/outcomes.csv from raw downloads.

Inputs (downloaded into nonprofits/data/outcomes/raw/ by outcomes_fetch.sh):
  6dpt-7w23.csv   San Francisco Citywide Performance Metrics (Controller, annual by FY)
  kc49-udxn.csv   Scorecard Measures (Controller, monthly/quarterly/other)
  5x94-tptc.csv   Citywide Performance Measurement Annual Report FY13 (FY2011-FY2013 actuals)
  6h77-suve.csv   Citywide Performance Measurement Annual Report FY14 (FY2012-FY2014 actuals)
  ubf6-e57x.csv   DPH Substance Use Services
  sfgov_2026_PIT_prelim.html  sf.gov 2026 PIT preliminary results page (values typed below, quoted)

No values are invented. Derived values (sums of monthly/quarterly published values) are
flagged in value_basis = 'derived_sum_*' and explained in notes.
"""
import csv, hashlib, os, re, collections

BASE = os.path.join(os.path.dirname(__file__), '..', 'data', 'outcomes')
RAW = os.path.join(BASE, 'raw')
OUT = os.path.join(BASE, 'outcomes.csv')

URL_6DPT = 'https://data.sf.gov/api/views/6dpt-7w23/rows.csv?accessType=DOWNLOAD'
URL_KC49 = 'https://data.sf.gov/api/views/kc49-udxn/rows.csv?accessType=DOWNLOAD'
URL_FY13 = 'https://data.sf.gov/api/views/5x94-tptc/rows.csv?accessType=DOWNLOAD'
URL_FY14 = 'https://data.sf.gov/api/views/6h77-suve/rows.csv?accessType=DOWNLOAD'
URL_UBF6 = 'https://data.sf.gov/api/views/ubf6-e57x/rows.csv?accessType=DOWNLOAD'
URL_PIT26 = 'https://www.sf.gov/2026-point-in-time-count-preliminary-results'
URL_PIT24 = 'https://api.sf.gov/documents/31917/2024_San_Francisco_Point-in-Time_Count_Report_8_13_24.pdf'

COLS = ['department_code', 'department', 'measure_id', 'measure_name', 'period_type',
        'fiscal_year', 'value', 'unit', 'source_title', 'source_url', 'notes',
        'value_basis', 'period_label']

rows = []

def add(**kw):
    r = {c: '' for c in COLS}
    r.update(kw)
    rows.append(r)

def slug(prefix, title):
    return prefix + '-' + hashlib.md5(title.strip().lower().encode()).hexdigest()[:8]

def unit_of(dtype):
    d = (dtype or '').strip().lower()
    return {'percent': 'proportion (0-1)', 'numeric': 'count', 'currency': 'USD (nominal)'}.get(d, d or 'count')

def fmt(v):
    v = float(v)
    return str(int(v)) if v == int(v) else repr(round(v, 6))

# ---------------------------------------------------------------- 6dpt-7w23
DEPT_6DPT = {
    'HOMELESSNESS AND SUPPORTIVE HOUSING': ('HOM', 'Homelessness and Supportive Housing', None),
    'PUBLIC HEALTH': ('DPH', 'Public Health', [
        'Number of unique individuals receiving a mental health service in the SF Health Network and BHS',
        'Number of unique individuals receiving a substance use service in the SF Health Network and BHS',
        'Number of unique clients under 18 years old in specialty mental health care',
        'Number of unique patients on methadone (citywide)',
        'Number of unique patients on buprenorphine (citywide)',
        'Number of Naloxone doses distributed',
        'Number of Deaths due to Acute Toxicity (overdose)',
    ]),
    'CHILDREN YOUTH & THEIR FAMILIES': ('CHF', 'Children, Youth and Their Families (DCYF)', None),
    'ECONOMIC AND WORKFORCE DEVELOPMENT': ('ECN', 'Economic and Workforce Development (OEWD)', [
        'Placement rate of individuals 18 and older who complete a program in jobs that are employed either full-time or part-time',
        'Number of small businesses and entrepreneurs receiving one-on-one technical assistance',
        'Number of businesses or entrepreneurs awarded a grant',
        'Dollar amount of grants awarded to small businesses and entrepreneurs',
    ]),
    "MAYOR'S OFFICE OF HOUSING AND COMMUNITY DEVELOPMENT": ('MYR', "Mayor's Office of Housing and Community Development (MOHCD)", None),
    'HUMAN SERVICES': ('HSA', 'Human Services Agency', [
        'WDD: Job placement rate for aided individuals receiving Workforce Development Division Services',
        '12-month job retention rate for subsidized employment clients',
        'Average increase in earnings for graduates of subsidized employment program after 1 year',
        'OCP: Number of home-delivered meals provided to older people',
        'OCP: Number of meals served at centers for older people',
        'OCP: Number of unduplicated clients enrolled in OCP programs',
        'OCP: Total number of enrollments in OCP services',
    ]),
    'EARLY CHILDHOOD': ('DEC', 'Early Childhood (DEC; formerly First 5 / CFC)', [
        'Number of children 0-5 served in Family Resource Centers',
        'Number of parents served in Family Resource Centers (FRC)',
        'Number of children ages 0 to 5 receiving fully or partially funded services in an ECE setting',
        'Number of children screened for special needs',
    ]),
}

with open(os.path.join(RAW, '6dpt-7w23.csv'), encoding='utf-8') as f:
    for x in csv.DictReader(f):
        d = DEPT_6DPT.get(x['Department Name'])
        if not d:
            continue
        code, dname, keep = d
        title = x['Measure Title'].strip()
        if keep is not None and title not in keep:
            continue
        val = x['Full-Year Result'].strip()
        if not val:
            continue
        m = re.match(r'FY(\d{4})-(\d{2})', x['Fiscal Year'])
        fy = int(m.group(1)) + 1
        note = x['Data Notes'].strip()
        if note in ('No public data notes.',):
            note = ''
        tgt = x['Target'].strip()
        notes = '; '.join(p for p in [
            f"Target {tgt}" if tgt else '',
            f"Data notes: {note}" if note else '',
            f"data_as_of {x['data_as_of']}"] if p)
        add(department_code=code, department=dname, measure_id=slug('CPM-' + code, title),
            measure_name=title, period_type='fiscal_year', fiscal_year=fy, value=fmt(val),
            unit=unit_of(x['Measure Data Type']),
            source_title='DataSF 6dpt-7w23 San Francisco Citywide Performance Metrics (Controller)',
            source_url=URL_6DPT, notes=notes, value_basis='published_full_year_result',
            period_label=x['Fiscal Year'])

# ---------------------------------------------------------------- kc49-udxn
kc = list(csv.DictReader(open(os.path.join(RAW, 'kc49-udxn.csv'), encoding='utf-8')))

def fy_of(d):  # 'YYYY/MM/DD'
    y, m = int(d[:4]), int(d[5:7])
    return y + 1 if m >= 7 else y

# (a) FY2026 full-year (June 2026 year-to-date, deduplicated across FY) for HSH measures
FY26_CODES = {'7282': 'Number of people exiting homelessness to a permanent housing situation',
              '7283': 'Number of people at imminent risk of homelessness who receive prevention assistance.',
              '7284': 'Number of households who moved into housing through a Rapid Rehousing program',
              '7285': 'Number of households who moved into housing through Permanent Supportive Housing',
              '7286': 'Number of households who achieved a Problem Solving Resolution'}
for x in kc:
    c = x['Measure Code']
    if c in FY26_CODES and x['Calendar Month'].startswith('2026/06') and x['Actual'] not in ('', '-9999'):
        title = FY26_CODES[c]
        add(department_code='HOM', department='Homelessness and Supportive Housing',
            measure_id=slug('CPM-HOM', title), measure_name=title, period_type='fiscal_year',
            fiscal_year=2026, value=fmt(x['Actual']), unit='count',
            source_title=f'DataSF kc49-udxn Scorecard Measures (Controller), measure code {c}',
            source_url=URL_KC49,
            notes=('PRELIMINARY: fiscal-year-to-date value reported for month ending 2026-06-30 '
                   '(methodology says deduplicated across fiscal year). The annual dataset 6dpt-7w23 had '
                   'only a mid-year FY2026 value when downloaded; the final full-year figure may be revised. '
                   'For FY2024/FY2025 the June YTD values here differed from 6dpt full-year results by about 0-2%.'),
            value_basis='published_fytd_june', period_label='FY2025-26 (Jul 2025-Jun 2026)')

# (b) FY2018-FY2022 derived sums of monthly HSH placement counts (not deduplicated across year)
MONTHLY = {
    '7054': ('Number of households who moved into housing through a Rapid Rehousing program',
             'Households moved into Rapid Rehousing (sum of monthly counts)'),
    '7055': ('Number of households who moved into housing through Permanent Supportive Housing',
             'Households moved into Permanent Supportive Housing (sum of monthly counts)'),
    '7067': ('Number of households who achieved a Problem Solving Resolution',
             'Households with a Problem Solving resolution (sum of monthly counts)'),
}
agg = collections.defaultdict(list)
for x in kc:
    c = x['Measure Code']
    if c in MONTHLY and x['Actual'] not in ('', '-9999'):
        agg[(c, fy_of(x['Calendar Month']))].append(float(x['Actual']))
for (c, fy), vals in sorted(agg.items()):
    if fy > 2022 or len(vals) != 12:
        continue  # FY2023+ are published as deduplicated annual figures in 6dpt
    base_title, name = MONTHLY[c]
    add(department_code='HOM', department='Homelessness and Supportive Housing',
        measure_id=slug('SCM-HOM', name), measure_name=name, period_type='fiscal_year',
        fiscal_year=fy, value=fmt(sum(vals)), unit='households',
        source_title=f'DataSF kc49-udxn Scorecard Measures (Controller), measure code {c}',
        source_url=URL_KC49,
        notes=('DERIVED by this project: sum of 12 published monthly values, which HSH labels '
               '"monthly only - not deduplicated across year". A household counted in two months is counted twice. '
               'Check: the same method gives FY2023/FY2024 sums within about 2-7% of the deduplicated full-year '
               f'figures in 6dpt-7w23 for "{base_title}". Earlier Scorecard titles (June 2023 archive) described '
               'these as households "leaving homelessness" via RRH subsidy / PSH placement / Problem Solving.'),
        value_basis='derived_sum_of_monthly', period_label=f'FY{fy-1}-{str(fy)[2:]}')

# (c) Point-in-Time count (biennial, January), measure 7169
pit = collections.defaultdict(dict)
for x in kc:
    if x['Measure Code'] == '7169' and x['Actual'] not in ('', '-9999'):
        pit[int(x['Calendar Month'][:4])][x['Category 2'].strip()] = int(float(x['Actual']))
pit_title = 'DataSF kc49-udxn Scorecard Measures (Controller), measure code 7169 (Point-in-Time Count)'
for yr, d in sorted(pit.items()):
    for status in ('Sheltered', 'Unsheltered'):
        if status in d:
            add(department_code='HOM', department='Homelessness and Supportive Housing',
                measure_id=f'PIT-{status.upper()}', measure_name=f'Point-in-Time Count: people experiencing homelessness, {status.lower()}',
                period_type='calendar_year', fiscal_year=yr, value=d[status], unit='people',
                source_title=pit_title, source_url=URL_KC49,
                notes=f'One-night count in late January {yr} (FY{yr} midpoint). HUD definition of homelessness.',
                value_basis='published', period_label=f'January {yr} count')
    if 'Sheltered' in d and 'Unsheltered' in d:
        tot = d['Sheltered'] + d['Unsheltered']
        chk = ''
        if yr == 2024: chk = ' Matches 8,323 in the 2024 PIT report.'
        if yr == 2022: chk = ' Matches 7,754 in the 2024 PIT report.'
        add(department_code='HOM', department='Homelessness and Supportive Housing',
            measure_id='PIT-TOTAL', measure_name='Point-in-Time Count: people experiencing homelessness, total',
            period_type='calendar_year', fiscal_year=yr, value=tot, unit='people',
            source_title=pit_title, source_url=URL_KC49,
            notes='Sum of published sheltered + unsheltered values.' + chk,
            value_basis='derived_sum_of_components', period_label=f'January {yr} count')
# 2026 preliminary (values quoted from the sf.gov page; see raw/sfgov_2026_PIT_prelim.html)
pit26 = open(os.path.join(RAW, 'sfgov_2026_PIT_prelim.html'), encoding='utf-8', errors='replace').read()
assert '7,973' in pit26 and '3,400' in pit26, '2026 PIT page text changed; re-check values'
for mid, name, v, note in [
    ('PIT-TOTAL', 'Point-in-Time Count: people experiencing homelessness, total', 7973,
     'PRELIMINARY 2026 result: "decreasing from 8,323 people in 2024 to 7,973 people in 2026".'),
    ('PIT-UNSHELTERED', 'Point-in-Time Count: people experiencing homelessness, unsheltered', 3400,
     'PRELIMINARY 2026 result, stated as "3,400 people" (appears rounded). Page says 57% of people were sheltered; '
     'sheltered count not stated, so not included.')]:
    add(department_code='HOM', department='Homelessness and Supportive Housing', measure_id=mid,
        measure_name=name, period_type='calendar_year', fiscal_year=2026, value=v, unit='people',
        source_title='sf.gov: 2026 Point-in-Time Count: Preliminary Results (HSH)', source_url=URL_PIT26,
        notes=note, value_basis='published_preliminary', period_label='January 2026 count')

# ---------------------------------------------------------------- FY13 / FY14 annual reports
SEL = {  # dept -> list of measure-title prefixes
    'DSS': ['Number of families receiving a rental subsidy', 'Average nightly homeless shelter bed use',
            'Number of CAAP clients leaving homelessness due to obtaining housing through Care Not Cash',
            'Number of households that secured and/or maintained housing due to a one-time grant',
            'Percent of formerly homeless clients (single adults ) still in supportive housing',
            'Percentage of all available homeless shelter beds used',
            'Percentage of families exiting shelter who have stayed for 30 days or more',
            'Number of individuals that were placed in employment', 'Job placement rate for aided individuals',
            'Number of individuals that received workforce development services',
            'Number of meals delivered to homes (OOA)', 'Number of meals served at centers (OOA)',
            'Number of unduplicated individuals served meals through senior congregate'],
    'DPH': ['Number of unique mental health clients in treatment', 'Number of unique substance abuse clients in treatment',
            "San Francisco residents under 19 years of age receiving services provided by Children's Mental Health",
            'Number of bed slots in housing programs', 'Number of unduplicated clients served in supportive housing',
            'Number of unduplicated clients served by housing and housing-related programs'],
    'CHF': ['Number of high school students served at school Wellness Centers',
            'Number of children, youth, and their families participating in programs/services funded by the Children',
            'Number of youth 14-24 years old in DCYF-funded case management',
            'Number of 6 to 13 year olds attending summer programs', 'Number of children and youth attending afterschool programs',
            'Number of 14 to 17 year olds placed in a job', 'Number of 14 to 17 years old served by DCYF-funded YLEAD'],
    'ECN': ['Placement rate of individuals 18 and older who complete a program',
            'Number of businesses receiving one-on-one technical assistance'],
    'MYR': ['Number of individuals receiving emergency shelter and homeless prevention services through ESG',
            'Number of individuals receiving public services through CDBG', 'Number of individuals receiving services through HOPWA',
            'Number of newly constructed low and moderate-income rental units completed with public financial assistance',
            'Number of low-and-moderate income rental units rehabilitated or preserved',
            'Number of homeownership opportunities or assistance received by first time homebuyers'],
    'CFC': ['Number of children screened for special needs', 'Number of children participating in school readiness'],
}
DNAME = {'DSS': 'Human Services Agency (DSS code before FY2018)', 'DPH': 'Public Health',
         'CHF': 'Children, Youth and Their Families (DCYF)', 'ECN': 'Economic and Workforce Development (OEWD)',
         'MYR': "Mayor's Office of Housing and Community Development (MOHCD) / Mayor", 'CFC': 'Children and Families Commission (First 5)'}
ar = {}  # (dept, kpi, fy) -> (value, row, src)
for fname, url, title, years in [('5x94-tptc.csv', URL_FY13, 'DataSF 5x94-tptc Citywide Performance Measurement Annual Report FY13', (2011, 2012, 2013)),
                                  ('6h77-suve.csv', URL_FY14, 'DataSF 6h77-suve Citywide Performance Measurement Annual Report FY14', (2012, 2013, 2014))]:
    for x in csv.DictReader(open(os.path.join(RAW, fname), encoding='utf-8', errors='replace')):
        dept = x['Dept']
        pm = x['Performance Measure'].strip()
        if dept not in SEL or not any(pm.startswith(p) for p in SEL[dept]):
            continue
        for fy in years:
            k = [c for c in x if re.match(rf'FY {fy}\s+Total Actual Data', c)][0]
            v = x[k].strip()
            if not v or float(v) == 0:
                continue  # 0 in these extracts generally means "not reported" (see sources.md)
            prev = ar.get((dept, x['KPI_CODE'], fy))
            ar[(dept, x['KPI_CODE'], fy)] = (v, x, title, url, prev[0] if prev else None)
for (dept, kpi, fy), (v, x, title, url, prev) in sorted(ar.items()):
    ut = x['Unit of Measure'].strip()
    unit = 'proportion (0-1)' if ut.lower() == 'percent' else ('USD (nominal)' if ut.lower() in ('currency', 'dollars') else 'count')
    note = f"Program: {x['Program'].strip()}. KPI {kpi}."
    if prev is not None and float(prev) != float(v):
        note += f' FY13 report showed {prev}; FY14 report value used.'
    add(department_code=dept, department=DNAME[dept], measure_id=f'CPMAR-{kpi}', measure_name=x['Performance Measure'].strip(),
        period_type='fiscal_year', fiscal_year=fy, value=fmt(v), unit=unit, source_title=title, source_url=url,
        notes=note, value_basis='published_total_actual', period_label=f'FY{fy-1}-{str(fy)[2:]}')

# ---------------------------------------------------------------- ubf6-e57x DPH substance use services
su = list(csv.DictReader(open(os.path.join(RAW, 'ubf6-e57x.csv'), encoding='utf-8')))
for x in su:
    if x['reporting_period_type'] == 'Annual (Full)':
        add(department_code='DPH', department='Public Health', measure_id=f"SUS-{x['metric'].upper()}-CLIENTS",
            measure_name=f"People receiving {x['metric'].lower()} for opioid use disorder (calendar year)",
            period_type='calendar_year', fiscal_year=int(x['year']), value=fmt(x['metric_value']), unit='people',
            source_title='DataSF ubf6-e57x SFDPH Substance Use Services', source_url=URL_UBF6,
            notes=('Methadone: Drug Medi-Cal certified opioid treatment programs (Avatar). Buprenorphine: CURES '
                   'prescriptions citywide, all prescribers (not only city-funded). Do not add the two.'),
            value_basis='published', period_label=f"CY{x['year']}")
qagg = collections.defaultdict(dict)
for x in su:
    if x['reporting_period_type'] == 'Quarterly':
        y, q = x['reporting_period'].split()
        y, q = int(y), int(q[1])
        fy = y + 1 if q >= 3 else y
        qagg[(x['metric'], fy)][(y, q)] = float(x['metric_value'])
QNAME = {'SUD Residential Treatment Admissions': ('SUS-RES-ADMISSIONS', 'Residential substance use treatment admissions (Drug Medi-Cal certified)', 'admissions'),
         'WM Discharges': ('SUS-WM-DISCHARGES', 'Withdrawal management discharges (Drug Medi-Cal certified)', 'discharges'),
         'Naloxone': ('SUS-NALOXONE', 'Naloxone units distributed via DPH clearinghouse and DOPE program', 'units distributed')}
for (metric, fy), qs in sorted(qagg.items()):
    if len(qs) != 4:
        continue
    mid, name, unit = QNAME[metric]
    add(department_code='DPH', department='Public Health', measure_id=mid, measure_name=name,
        period_type='fiscal_year', fiscal_year=fy, value=fmt(sum(qs.values())), unit=unit,
        source_title='DataSF ubf6-e57x SFDPH Substance Use Services', source_url=URL_UBF6,
        notes=('DERIVED by this project: sum of 4 published calendar quarters (Q3+Q4 of prior year, Q1+Q2). '
               'Events, not unique people. DPH notes a pause in some updates during an EHR transition.'),
        value_basis='derived_sum_of_quarterly', period_label=f'FY{fy-1}-{str(fy)[2:]}')

rows.sort(key=lambda r: (r['department_code'], r['measure_name'], r['period_type'], int(r['fiscal_year'])))
with open(OUT, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(rows)
print('wrote', len(rows), 'rows to', OUT)

# ---------------------------------------------------------------- measure definitions (verbatim from sources)
defs = {}
def setdef(k, v):
    if k not in defs or not (defs[k][0] or defs[k][1]):
        defs[k] = v
for x in csv.DictReader(open(os.path.join(RAW, '6dpt-7w23.csv'), encoding='utf-8')):
    mid = slug('CPM-' + (DEPT_6DPT.get(x['Department Name'], ('',))[0]), x['Measure Title'].strip())
    setdef(mid, (x['Measure Description'].strip(), x['Measure Methodology'].strip(), '6dpt-7w23'))
for x in kc:
    for c, (base, name) in MONTHLY.items():
        if x['Measure Code'] == c:
            setdef(slug('SCM-HOM', name), (x['Measure Description'].strip(), x['Measure Methodology'].strip(), f'kc49-udxn code {c}'))
    if x['Measure Code'] == '7169':
        for mid in ('PIT-TOTAL', 'PIT-SHELTERED', 'PIT-UNSHELTERED'):
            setdef(mid, (x['Measure Description'].strip(), x['Measure Methodology'].strip(), 'kc49-udxn code 7169'))
for fname in ('6h77-suve.csv', '5x94-tptc.csv'):
    for x in csv.DictReader(open(os.path.join(RAW, fname), encoding='utf-8', errors='replace')):
        setdef('CPMAR-' + x['KPI_CODE'], (x['Description'].strip(), x['Technical Description'].strip(), fname[:9]))
used = {}
for r in rows:
    used.setdefault(r['measure_id'], r)
with open(os.path.join(BASE, 'measure_definitions.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['measure_id', 'department_code', 'measure_name', 'description', 'methodology', 'definition_source'])
    for mid, r in sorted(used.items(), key=lambda kv: (kv[1]['department_code'], kv[1]['measure_name'])):
        d = defs.get(mid, ('', '', 'see sources.md'))
        w.writerow([mid, r['department_code'], r['measure_name'], d[0], d[1], d[2]])
print('wrote measure_definitions.csv with', len(used), 'measures')
