"""Shared constants and helpers for the performance pipeline."""
import os, json, time, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
INTERIM = os.path.join(ROOT, 'data', 'interim')
SITE = os.path.join(ROOT, 'data', 'site')
CACHE = os.path.join(ROOT, 'data', 'cache')
for d in (RAW, INTERIM, SITE, CACHE):
    os.makedirs(d, exist_ok=True)

# ---------------------------------------------------------------------------
# Department crosswalk: raw department_code -> canonical department code.
# Handles renames and system-migration code changes (FY2018 PeopleSoft cutover).
# Merges that are real reorganizations are documented, not silently merged:
#  - PUC enterprises (WTR, CWP, HHP, CLP, legacy PUC bureaus) were separate
#    department codes before FY2018 and one PUC code after; we merge into PUC.
#  - DSS (legacy code for Human Services Agency) -> HSA.
#  - ECD (legacy code for Dept of Emergency Management) -> DEM.
#  - PAB (legacy code for Board of Appeals) -> BOA.
#  - UNA (legacy "General City / Unallocated") -> GEN.
# Real reorganizations that move programs between departments are NOT merged
# (HOM created FY2017 out of HSA/DPH programs; DEC created FY2023 out of HSA
# early-care programs and First 5/CFC; DPA formerly OCC inside Police; AHR FY2027).
# They are flagged in REORGS and handled in robustness checks.
DEPT_CODE_MAP = {
    'DSS': 'HSA', 'ECD': 'DEM', 'PAB': 'BOA', 'UNA': 'GEN',
    'WTR': 'PUC', 'CWP': 'PUC', 'HHP': 'PUC', 'CLP': 'PUC',
}
DEPT_NAMES = {
    'AAM': 'Asian Art Museum', 'ADM': 'City Administrator', 'ADP': 'Adult Probation',
    'AHR': 'Agency for Human Rights', 'AIR': 'Airport', 'ART': 'Arts Commission',
    'ASR': 'Assessor-Recorder', 'BOA': 'Board of Appeals', 'BOS': 'Board of Supervisors',
    'CAT': 'City Attorney', 'CCD': 'Community College District (pass-through)',
    'CFC': 'Children & Families Commission (First 5)', 'CHF': 'Children, Youth & Their Families',
    'CII': 'Community Investment & Infrastructure', 'CON': 'Controller', 'CPC': 'Planning',
    'CRT': 'Superior Court', 'CSC': 'Civil Service Commission', 'CSS': 'Child Support Services',
    'CTA': 'County Transportation Authority', 'DAT': 'District Attorney',
    'DBI': 'Building Inspection', 'DEC': 'Early Childhood', 'DEM': 'Emergency Management',
    'DPA': 'Police Accountability', 'DPH': 'Public Health', 'DPW': 'Public Works',
    'ECN': 'Economic & Workforce Development', 'ENV': 'Environment', 'ETH': 'Ethics Commission',
    'FAM': 'Fine Arts Museums', 'FIR': 'Fire Department', 'GEN': 'General City Responsibility',
    'HOM': 'Homelessness & Supportive Housing', 'HRC': 'Human Rights Commission',
    'HRD': 'Human Resources', 'HSA': 'Human Services Agency', 'HSS': 'Health Service System',
    'JUV': 'Juvenile Probation', 'LIB': 'Public Library', 'LLB': 'Law Library',
    'MTA': 'Municipal Transportation Agency (SFMTA)', 'MYR': 'Mayor (incl. MOHCD)',
    'PDR': 'Public Defender', 'POL': 'Police', 'PRT': 'Port', 'PUC': 'Public Utilities Commission',
    'REC': 'Recreation & Park', 'REG': 'Elections', 'RET': 'Retirement System',
    'RNT': 'Rent Board', 'SCI': 'Academy of Sciences', 'SDA': 'Sheriff Inspector General',
    'SHF': 'Sheriff', 'TIS': 'Technology', 'TJP': 'Transbay Joint Powers Authority',
    'TTX': 'Treasurer-Tax Collector', 'USD': 'County Education Office', 'WAR': 'War Memorial',
    'WOM': 'Status of Women', 'RDA': 'Redevelopment Agency (former)',
}
REORGS = [
    {'fy': 2017, 'what': 'Department of Homelessness and Supportive Housing (HOM) created; homeless programs moved from HSA and DPH.', 'depts': ['HOM', 'HSA', 'DPH']},
    {'fy': 2018, 'what': 'Financial system cutover (PeopleSoft). Program detail collapses to ~10 program types; legacy department codes remapped; PUC enterprises consolidated under one code.', 'depts': ['ALL']},
    {'fy': 2018, 'what': 'Department of Police Accountability (DPA) reported separately (formerly Office of Citizen Complaints).', 'depts': ['DPA', 'POL']},
    {'fy': 2023, 'what': 'Department of Early Childhood (DEC) created from HSA Office of Early Care & Education and First 5 (CFC).', 'depts': ['DEC', 'HSA', 'CFC']},
    {'fy': 2027, 'what': 'Agency for Human Rights (AHR) appears; Status of Women (WOM) ends FY2026.', 'depts': ['AHR', 'WOM', 'HRC']},
]


def canon_dept(code):
    code = code.strip() if isinstance(code, str) else 'UNK'
    return DEPT_CODE_MAP.get(code, code)


# ---------------------------------------------------------------------------
# Character crosswalk -> canonical class
CHAR_CLASS = {
    'Salaries': 'salaries',
    'Mandatory Fringe Benefits': 'benefits',
    'Non Personnel Services': 'non_personnel', 'Non-Personnel Services': 'non_personnel',
    'Materials & Supplies': 'materials',
    'City Grant Program': 'grants', 'City Grant Programs': 'grants',
    'Aid Assistance': 'aid', 'Aid Payments': 'aid',
    'Other Support & Care Of Persons': 'aid', 'Other Support/Care of Persons': 'aid',
    'Other Support&Care Of Persons': 'aid',
    'Capital Outlay': 'capital', 'Capitalized Expenditures': 'capital',
    'Facilities Maintenance': 'capital', 'Programmatic Projects': 'projects',
    'Debt Service': 'debt_service',
    'Services of Other Depts': 'services_other_depts', 'Services Of Other Depts': 'services_other_depts',
    'Overhead': 'overhead', 'Overhead and Allocations': 'overhead', 'Allocated Charges': 'overhead',
    # transfers & eliminations (excluded from spending)
    'Intrafund Transfers Out': 'transfer', 'Transfers Out': 'transfer', 'Operating Transfers Out': 'transfer',
    'General Fund Subsidy Xfer Out': 'transfer', 'Transfer Out For Captl Expend': 'transfer',
    'Transfer Out for Capital Expenditures': 'transfer', 'Transfer Adjustment - Uses': 'transfer',
    'Transfer Adjustments-Uses': 'transfer', 'Other Financing Uses': 'transfer',
    # reserves (appropriated but not spending)
    'Unappropriated Rev Retained': 'reserve', 'Unappropriated Rev-Designated': 'reserve',
    'Unappropriated Revenue Retained': 'reserve', 'Unappropriated Revenue-Designated': 'reserve',
    'Unappropriated Revenue-Charter Reserves': 'reserve', 'Unapprop Rev-Charter Reserves': 'reserve',
    'Carry-Forward Budgets Only': 'reserve', 'Project Carryforward Budgets Only': 'reserve',
    # other / fiduciary / artifacts
    'Fiduciary-Benefit Payments': 'fiduciary', 'Contribution Refund/Distrib': 'fiduciary',
    'Contribution Refund-Distrib': 'fiduciary', 'Investment Expenses': 'fiduciary',
    'Special Items': 'other', 'Special Items-Outflow': 'other', 'Extraordinary Items - Loss': 'other',
    'Other Expenses-Non Expend Type': 'other',
    'GFSUP GENERAL FUND SUPPORT': 'artifact',
}
# Classes counted as department spending ("gross department spending").
SPEND_CLASSES = ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid',
                 'capital', 'projects', 'debt_service', 'services_other_depts', 'overhead', 'other']
# Classes counted in the citywide total (avoid double counting inter-department work orders/overhead)
CITY_CLASSES = [c for c in SPEND_CLASSES if c not in ('services_other_depts', 'overhead')]
OPERATING_CLASSES = ['salaries', 'benefits', 'non_personnel', 'materials', 'grants', 'aid',
                     'services_other_depts', 'overhead', 'other']

# Fund types that are fiduciary / component units, excluded from city spending
EXCLUDED_FUND_TYPES = {
    'Pension Trust Funds', 'Other Employee Benefit Trust Funds', 'Pension, Other Employee and Ot',
    'Agency Funds', 'Investment Trust Fund', 'Private Purpose Trust Fund',
    'Retiree Health Care Trust Fund - Prop B', 'Successor Agency-Former SF Redev Agency',
    'Component Units', 'SF Transportation Authority Funds', 'Treasure Island Development Authority',
    "Treasurer's Group Of Accounts",
}
GF_FUND_TYPE_CODES = {'1G', 'GEN_FUND'}
# Departments excluded from city-service scorecards (pass-throughs, fiduciary, separate entities)
NON_SERVICE_DEPTS = {'CCD', 'USD', 'CTA', 'TJP', 'RDA', 'RET', 'HSS', 'CII'}


def fy_of_date(ts):
    """Fiscal year (ending year) for a pandas Timestamp / datetime."""
    return ts.year + (1 if ts.month >= 7 else 0)


# ---------------------------------------------------------------------------
# LLM usage logging
USAGE_LOG = os.path.join(ROOT, 'data', 'llm_usage.jsonl')
PRICES = {  # USD per million tokens (input, output) per RULES.md
    'claude-sonnet-5': (2.0, 10.0),
    'claude-opus-5-5': (4.0, 20.0),
}
BUDGET_USD = 400.0


def spent_usd():
    tot = 0.0
    if os.path.exists(USAGE_LOG):
        for line in open(USAGE_LOG):
            try:
                tot += json.loads(line)['cost_usd']
            except Exception:
                pass
    return tot


def log_usage(task, model, usage):
    pi, po = PRICES[model]
    it = getattr(usage, 'input_tokens', 0) or 0
    ot = getattr(usage, 'output_tokens', 0) or 0
    cr = getattr(usage, 'cache_read_input_tokens', 0) or 0
    cw = getattr(usage, 'cache_creation_input_tokens', 0) or 0
    # cache reads billed at 10%, cache writes at 125% of input price
    cost = (it * pi + cr * pi * 0.1 + cw * pi * 1.25 + ot * po) / 1e6
    rec = {'ts': datetime.datetime.utcnow().isoformat() + 'Z', 'task': task, 'model': model,
           'input_tokens': it, 'cache_read_tokens': cr, 'cache_write_tokens': cw,
           'output_tokens': ot, 'cost_usd': round(cost, 6)}
    with open(USAGE_LOG, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    return cost
