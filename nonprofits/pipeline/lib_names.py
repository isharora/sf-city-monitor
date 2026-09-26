"""Name normalization shared by the matching steps."""
import re

ABBREV = {
    "SF": "SAN FRANCISCO", "S F": "SAN FRANCISCO", "SAN FRAN": "SAN FRANCISCO",
    "CTR": "CENTER", "CNTR": "CENTER", "CENTRE": "CENTER", "SVCS": "SERVICES", "SVC": "SERVICE",
    "SRVCS": "SERVICES", "SERV": "SERVICES", "SVS": "SERVICES",
    "COMM": "COMMUNITY", "CMNTY": "COMMUNITY", "CMTY": "COMMUNITY", "COMMTY": "COMMUNITY",
    "ASSN": "ASSOCIATION", "ASSOC": "ASSOCIATION", "ASSOCS": "ASSOCIATES",
    "FDN": "FOUNDATION", "FNDTN": "FOUNDATION", "FOUND": "FOUNDATION", "FOUNDTN": "FOUNDATION",
    "DEV": "DEVELOPMENT", "DEVEL": "DEVELOPMENT", "DEVLPMT": "DEVELOPMENT", "DEVELOP": "DEVELOPMENT",
    "CORP": "CORPORATION", "CO": "COMPANY", "INTL": "INTERNATIONAL", "NATL": "NATIONAL",
    "HLTH": "HEALTH", "HSG": "HOUSING", "HOUS": "HOUSING", "EDUC": "EDUCATION", "ED": "EDUCATION",
    "PRGM": "PROGRAM", "PROG": "PROGRAM", "PROGS": "PROGRAMS", "YTH": "YOUTH",
    "FAM": "FAMILY", "FAMS": "FAMILIES", "CHLDRN": "CHILDREN", "CHILDRENS": "CHILDREN",
    "UNIV": "UNIVERSITY", "HOSP": "HOSPITAL", "MED": "MEDICAL", "MGMT": "MANAGEMENT",
    "AMER": "AMERICA", "AMERICAN": "AMERICAN", "CALIF": "CALIFORNIA", "CAL": "CALIFORNIA", "CA": "CALIFORNIA",
    "BAY AREA": "BAY AREA", "NEIGHBORHD": "NEIGHBORHOOD", "NBRHD": "NEIGHBORHOOD", "NGHBRHD": "NEIGHBORHOOD",
    "ST": "SAINT", "STS": "SAINTS", "MT": "MOUNT", "BLDG": "BUILDING", "RES": "RESOURCE",
    "RESRC": "RESOURCE", "RSRC": "RESOURCE", "LEGL": "LEGAL", "SR": "SENIOR", "SRS": "SENIORS",
    "CLNC": "CLINIC", "CLIN": "CLINIC", "COUNSL": "COUNSEL", "COUNCL": "COUNCIL",
    "COALTN": "COALITION", "COAL": "COALITION", "ORG": "ORGANIZATION", "ORGS": "ORGANIZATIONS",
    "ENT": "ENTERPRISES", "ENTPR": "ENTERPRISES", "BRD": "BOARD", "DIST": "DISTRICT",
    "EMPLYMNT": "EMPLOYMENT", "EMPLMT": "EMPLOYMENT", "TRNG": "TRAINING", "TRAING": "TRAINING",
    "SUPP": "SUPPORTIVE", "SPPRTIV": "SUPPORTIVE", "MENTL": "MENTAL", "BEHAV": "BEHAVIORAL",
    "RECOV": "RECOVERY", "REHAB": "REHABILITATION", "ALLNC": "ALLIANCE", "PARTNRS": "PARTNERS",
    "PTNRS": "PARTNERS", "INST": "INSTITUTE", "INSTIT": "INSTITUTE", "LG": "LEGAL",
    "YMCA": "YOUNG MENS CHRISTIAN ASSOCIATION", "YWCA": "YOUNG WOMENS CHRISTIAN ASSOCIATION",
    "YMCA'S": "YOUNG MENS CHRISTIAN ASSOCIATION", "BGC": "BOYS AND GIRLS CLUBS",
}
LEGAL = {"INC", "INCORPORATED", "LLC", "L L C", "LTD", "LP", "CORPORATION", "COMPANY", "THE", "OF", "AND",
         "A", "AN", "NFP", "NONPROFIT", "NON PROFIT", "DBA", "FBO", "PBC", "LLP", "PC", "INCORP"}

def norm(name: str) -> str:
    if not isinstance(name, str):
        return ""
    s = name.upper()
    s = s.replace("&", " AND ").replace("'", "").replace("’", "")
    s = re.sub(r"\bC/O\b.*$", "", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = re.sub(r"\bS F\b", "SAN FRANCISCO", s)
    toks = s.split()
    out = []
    for t in toks:
        out.append(ABBREV.get(t, t))
    s = " ".join(out)
    toks = [t for t in s.split() if t not in LEGAL]
    return " ".join(toks)

def key(name: str) -> str:
    """Stricter key: normalized, no spaces."""
    return norm(name).replace(" ", "")

def split_dba(name: str):
    """Return list of name variants for vendor strings containing DBA / AKA / FKA / FBO."""
    if not isinstance(name, str):
        return []
    parts = re.split(r"\b(?:DBA|D/B/A|D B A|AKA|FKA|F/K/A|FBO|OBO)\b", name.upper())
    return [p.strip(" ,-:") for p in parts if p.strip(" ,-:")]
