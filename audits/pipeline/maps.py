"""Vocabulary mappings shared by build, analysis and export."""

# canonical department name (04_normalize) -> Controller department code
# (codes follow performance/pipeline/common.py DEPT_NAMES so the dashboards join)
DEPT_CODE = {
    "Airport": "AIR", "Arts Commission": "ART", "Asian Art Museum": "AAM", "Assessor-Recorder": "ASR",
    "Board of Appeals": "BOA", "Board of Supervisors": "BOS", "Building Inspection": "DBI",
    "Child Support Services": "CSS", "Children, Youth and Their Families": "CHF", "City Administrator": "ADM",
    "City Attorney": "CAT", "City Planning": "CPC", "Civil Service Commission": "CSC", "Controller": "CON",
    "County Transportation Authority": "CTA", "Disability and Aging Services": "HSA", "District Attorney": "DAT",
    "Early Childhood": "DEC", "Economic and Workforce Development": "ECN", "Elections": "REG",
    "Emergency Management": "DEM", "Environment": "ENV", "Ethics Commission": "ETH", "Film Commission": "ADM",
    "Fine Arts Museums": "FAM", "Fire Department": "FIR", "Health Service System": "HSS",
    "Homelessness and Supportive Housing": "HOM", "Human Resources": "HRD", "Human Rights Commission": "HRC",
    "Human Services Agency": "HSA", "Juvenile Probation": "JUV", "Law Library": "LLB", "Library": "LIB",
    "Mayor's Office": "MYR", "Mayor's Office of Housing and Community Development": "MYR",
    "Municipal Transportation Agency": "MTA", "Office of Community Investment and Infrastructure": "CII",
    "Police Accountability": "DPA", "Police Department": "POL", "Police Commission": "POL", "Port": "PRT",
    "Public Defender": "PDR", "Public Health": "DPH", "Public Utilities Commission": "PUC",
    "Public Works": "DPW", "Recreation and Park": "REC", "Rent Board": "RNT", "Retirement System": "RET",
    "Retirement Board": "RET", "Sheriff": "SHF", "Sheriff's Department of Accountability": "SDA",
    "Status of Women": "WOM", "Superior Court": "CRT", "Technology": "TIS",
    "Treasure Island Development Authority": "TIDA", "Treasurer and Tax Collector": "TTX",
    "War Memorial": "WAR", "Youth Commission": "BOS", "Adult Probation": "ADP",
    "Animal Care and Control": "ADM", "Entertainment Commission": "ADM", "Small Business": "ECN",
    "Citywide": "CITYWIDE", "School District": "NONCITY", "Community College District": "CCD",
    "Other non-City entity": "NONCITY", "Unknown": "UNK",
}

DEPT_INFO = {  # code -> (name, group, short)
    "AAM": ("Asian Art Museum", "culture", "Asian Art"), "ADM": ("City Administrator", "admin", "City Admin"),
    "ADP": ("Adult Probation", "protection", "Adult Probation"), "AIR": ("Airport", "works", "Airport"),
    "ART": ("Arts Commission", "culture", "Arts"), "ASR": ("Assessor-Recorder", "admin", "Assessor"),
    "BOA": ("Board of Appeals", "admin", "Appeals"), "BOS": ("Board of Supervisors", "admin", "Board"),
    "CAT": ("City Attorney", "admin", "City Attorney"), "CCD": ("Community College District", "other", "CCSF"),
    "CHF": ("Children, Youth and Their Families", "welfare", "DCYF"), "CII": ("Community Investment and Infrastructure", "works", "OCII"),
    "CON": ("Controller", "admin", "Controller"), "CPC": ("Planning", "works", "Planning"),
    "CRT": ("Superior Court", "protection", "Court"), "CSC": ("Civil Service Commission", "admin", "Civil Service"),
    "CSS": ("Child Support Services", "welfare", "Child Support"), "CTA": ("County Transportation Authority", "works", "SFCTA"),
    "DAT": ("District Attorney", "protection", "DA"), "DBI": ("Building Inspection", "works", "DBI"),
    "DEC": ("Early Childhood", "welfare", "DEC"), "DEM": ("Emergency Management", "protection", "DEM"),
    "DPA": ("Police Accountability", "protection", "DPA"), "DPH": ("Public Health", "health", "DPH"),
    "DPW": ("Public Works", "works", "Public Works"), "ECN": ("Economic and Workforce Development", "admin", "OEWD"),
    "ENV": ("Environment", "works", "Environment"), "ETH": ("Ethics Commission", "admin", "Ethics"),
    "FAM": ("Fine Arts Museums", "culture", "Fine Arts"), "FIR": ("Fire Department", "protection", "Fire"),
    "HOM": ("Homelessness and Supportive Housing", "welfare", "HSH"), "HRC": ("Human Rights Commission", "admin", "HRC"),
    "HRD": ("Human Resources", "admin", "DHR"), "HSA": ("Human Services Agency", "welfare", "HSA"),
    "HSS": ("Health Service System", "admin", "HSS"), "JUV": ("Juvenile Probation", "protection", "Juvenile Probation"),
    "LIB": ("Public Library", "culture", "Library"), "LLB": ("Law Library", "culture", "Law Library"),
    "MTA": ("Municipal Transportation Agency", "works", "SFMTA"), "MYR": ("Mayor (incl. MOHCD)", "admin", "Mayor"),
    "PDR": ("Public Defender", "protection", "Public Defender"), "POL": ("Police", "protection", "Police"),
    "PRT": ("Port", "works", "Port"), "PUC": ("Public Utilities Commission", "works", "SFPUC"),
    "REC": ("Recreation and Park", "culture", "Rec & Park"), "REG": ("Elections", "admin", "Elections"),
    "RET": ("Retirement System", "admin", "SFERS"), "RNT": ("Rent Board", "welfare", "Rent Board"),
    "SDA": ("Sheriff Inspector General", "protection", "SDA"), "SHF": ("Sheriff", "protection", "Sheriff"),
    "TIS": ("Technology", "admin", "DT"), "TTX": ("Treasurer-Tax Collector", "admin", "Treasurer"),
    "WAR": ("War Memorial", "culture", "War Memorial"), "WOM": ("Status of Women", "welfare", "Women"),
    "TIDA": ("Treasure Island Development Authority", "works", "TIDA"),
    "CITYWIDE": ("Citywide / multiple departments", "other", "Citywide"),
    "NONCITY": ("Non-City entity (e.g., school district, contractor)", "other", "Non-City"),
    "UNK": ("Department not identified", "other", "Unknown"),
}

# extraction category -> contract topic id
TOPIC = {
    "contracting_procurement": "contracts", "grants_nonprofit_oversight": "grants",
    "it_data_systems": "it", "staffing_hr_payroll": "hr", "financial_controls": "finance",
    "revenue_billing": "revenue", "safety_health": "safety", "capital_assets_inventory": "facilities",
    "service_delivery": "service", "governance_oversight": "governance",
    "performance_measurement": "performance", "ethics_integrity": "ethics",
    "compliance_legal": "compliance", "planning_policy": "planning", "other": "other",
}
TOPIC_LABELS = [
    ("contracts", "Contracting and procurement"), ("grants", "Grants and nonprofit oversight"),
    ("it", "IT and data"), ("hr", "Staffing, HR and payroll"), ("finance", "Financial controls"),
    ("revenue", "Revenue, fees and billing"), ("safety", "Public safety and health"),
    ("facilities", "Facilities, capital and assets"), ("service", "Service delivery"),
    ("governance", "Governance and oversight"), ("performance", "Performance measurement"),
    ("ethics", "Ethics and integrity"), ("compliance", "Legal and regulatory compliance"),
    ("planning", "Planning and policy"), ("other", "Other"),
]

# extraction response -> contract agreed id (CSA/BLA report responses)
AGREED = {"agree": "agree", "partially_agree": "partial", "disagree": "disagree",
          "not_stated": "none", "other": "none"}

# CGJ Penal Code 933.05(b) recommendation response -> agreed id (documented mapping)
CGJ_AGREED = {"has_been_implemented": "agree", "will_be_implemented": "agree",
              "requires_further_analysis": "partial", "will_not_be_implemented": "disagree",
              "other": "none", "not_applicable": "none"}

# extraction status -> contract status id
STATUS = {"implemented": "implemented", "partially_implemented": "in_progress",
          "in_progress": "in_progress", "open": "open", "not_implementing": "not_implementing",
          "closed_other": "closed_other", "contested": "open", "unknown": "unknown"}

STATUS_LABELS = [
    ("implemented", "Implemented"), ("in_progress", "In progress (incl. partially implemented)"),
    ("open", "Open, not started (incl. requires further analysis)"),
    ("not_implementing", "Department will not implement"),
    ("closed_other", "Closed without implementation (superseded / no longer applicable / abandoned)"),
    ("unknown", "No follow-up status found"),
]

STATUS_MAPPING = {
    "cgj": {"implemented": "Has been implemented / Recommendation implemented",
            "in_progress": "Will be implemented in the future / being implemented / partially implemented",
            "open": "Requires further analysis",
            "not_implementing": "Will not be implemented because it is not warranted or is not reasonable",
            "closed_other": "Abandoned / no longer relevant (Controller tracking documents)",
            "unknown": "No response found",
            "agree": "Response: has been implemented or will be implemented",
            "partial": "Response: requires further analysis",
            "disagree": "Response: will not be implemented",
            "none": "No response found"},
    "csa": {"implemented": "Recommendation closed as implemented, or report closed by CSA follow-up (all recommendations resolved)",
            "in_progress": "Open - partially implemented / in progress",
            "open": "Open / not implemented",
            "not_implementing": "Department declined to implement",
            "closed_other": "Closed - no longer applicable / superseded",
            "unknown": "No follow-up record found in CSA follow-up reports",
            "agree": "Concur / agree", "partial": "Partially concur", "disagree": "Do not concur",
            "none": "No response in report"},
    "bla": {"implemented": "Not tracked (BLA publishes no follow-up)",
            "unknown": "BLA does not publish recommendation follow-up; status unknown",
            "agree": "Agree", "partial": "Partially agree", "disagree": "Disagree", "none": "No response in report"},
}

CONSEQUENCE_RULE = (
    "score = 1 + priority (high +3, medium +1.5, unrated +1, low 0) + dollars at stake stated in the report "
    "(>= $10M +3, >= $1M +2, > $0 +1) + age when the latest follow-up records it as open or in progress (> 5 years +2, > 2 years +1) "
    "+ department declined or disputed (+1) + repeats an earlier recommendation (+1) + topic is public safety/health or ethics (+1); "
    "rounded and clamped to 1-10. A reading aid for ranking, not an audit judgment."
)


def consequence(row, as_of):
    """Deterministic consequence score from row fields; returns (score, parts)."""
    from datetime import date
    parts = []
    s = 1.0
    pri = row.get("priority")
    if pri == "high":
        s += 3; parts.append("auditor rated high priority")
    elif pri == "medium":
        s += 1.5
    elif pri is None:
        s += 1
    d = row.get("dollars_at_stake") or 0
    if d >= 10_000_000:
        s += 3; parts.append(f"${d/1e6:,.1f} million at stake per the report")
    elif d >= 1_000_000:
        s += 2; parts.append(f"${d/1e6:,.1f} million at stake per the report")
    elif d > 0:
        s += 1; parts.append(f"${d:,.0f} at stake per the report")
    if row.get("status") in ("open", "in_progress") and row.get("date_issued"):
        # age counts only when a follow-up actually recorded the item as open / in progress
        y, m, dd = map(int, row["date_issued"].split("-"))
        a = as_of if isinstance(as_of, date) else date(*map(int, as_of.split("-")))
        age = (a - date(y, m, dd)).days / 365.25
        if age > 5:
            s += 2; parts.append(f"recorded as open or in progress, issued {age:.0f} years ago")
        elif age > 2:
            s += 1; parts.append(f"recorded as open or in progress, issued {age:.0f} years ago")
    if row.get("agreed") == "disagree" or row.get("status") == "not_implementing":
        s += 1; parts.append("department declined or disputed it")
    if row.get("repeat_of"):
        s += 1; parts.append("repeats an earlier recommendation to the same department")
    if row.get("topic") in ("safety", "ethics"):
        s += 1; parts.append("public safety/health or ethics topic")
    score = int(max(1, min(10, round(s + 1e-9))))
    return score, parts
