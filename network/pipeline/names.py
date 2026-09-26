"""Name normalization helpers shared by the pipeline."""
import re, unicodedata

LEGAL_SUFFIXES = [
    'INCORPORATED', 'INC', 'LLC', 'L L C', 'LLP', 'L L P', 'LP', 'L P', 'CORPORATION', 'CORP', 'CO', 'COMPANY',
    'LTD', 'LIMITED', 'PC', 'P C', 'PLLC', 'PLC', 'NA', 'N A', 'GMBH', 'SA', 'S A', 'AG', 'BV', 'NV', 'LLLP', 'PBC',
    'APC', 'A PROFESSIONAL CORPORATION', 'A CALIFORNIA CORPORATION', 'A CALIFORNIA NONPROFIT CORPORATION',
    'A CALIFORNIA NONPROFIT PUBLIC BENEFIT CORPORATION', 'A NONPROFIT CORPORATION', 'A DELAWARE CORPORATION',
    'A CALIFORNIA LIMITED LIABILITY COMPANY', 'A DELAWARE LIMITED LIABILITY COMPANY', 'A CALIFORNIA LIMITED PARTNERSHIP',
    'A JOINT VENTURE', 'THE',
]
_SUFFIX_RE = re.compile(r'\b(' + '|'.join(sorted((re.escape(s) for s in LEGAL_SUFFIXES), key=len, reverse=True)) + r')\b')
_WORD_SUBS = [
    (r'\bSAN FRANCISCO\b', 'SF'), (r'\bS F\b', 'SF'), (r'\bASSOCIATION\b', 'ASSN'), (r'\bASSOC\b', 'ASSN'),
    (r'\bDEPARTMENT\b', 'DEPT'), (r'\bINTERNATIONAL\b', 'INTL'), (r'\bNATIONAL\b', 'NATL'), (r'\bSERVICES\b', 'SERVICE'),
    (r'\bCENTRE\b', 'CENTER'), (r'\bCTR\b', 'CENTER'), (r'\bUNIVERSITY\b', 'UNIV'), (r'\bFOUNDATION\b', 'FDN'),
    (r'\bFOUND\b', 'FDN'), (r'\bBROTHERS\b', 'BROS'), (r'\bMANAGEMENT\b', 'MGMT'), (r'\bMGT\b', 'MGMT'),
    (r'\bDEVELOPMENT\b', 'DEV'), (r'\bDEVELOPERS\b', 'DEV'), (r'\bPARTNERS\b', 'PARTNERS'), (r'\bAMERICA\b', 'AMERICA'),
    (r'\bSAINT\b', 'ST'), (r'\bTECHNOLOGIES\b', 'TECHNOLOGY'), (r'\bTECH\b', 'TECHNOLOGY'), (r'\bSYSTEMS\b', 'SYSTEM'),
    (r'\bGROUP\b', 'GROUP'), (r'\bHOLDINGS\b', 'HOLDING'), (r'\bUNITED STATES\b', 'US'), (r'\bU S\b', 'US'), (r'\bUSA\b', 'US'),
]
_WORD_SUBS = [(re.compile(a), b) for a, b in _WORD_SUBS]

# employer strings that are not organizations
NON_EMPLOYERS = set('''
NONE N A NA NOT EMPLOYED UNEMPLOYED RETIRED SELF SELF EMPLOYED SELFEMPLOYED HOMEMAKER STUDENT INFORMATION REQUESTED
REQUESTED BEST EFFORTS UNKNOWN NOT APPLICABLE REFUSED DISABLED HOME MAKER SELF EMPLOY SELF EMPLOYED ATTORNEY
N A RETIRED NONE RETIRED NOT EMPLOYED RETIRED RETIRED NONE STAY AT HOME PARENT INFO REQUESTED INFORMATION REQUESTED PER BEST EFFORTS
'''.split('\n'))
_NON_EMP_PATTERNS = re.compile(r'^(N ?A|NONE|NOT ?EMPLOYED|UNEMPLOYED|RETIRED.*|SELF.*|HOME ?MAKER|STUDENT|INFO(RMATION)? REQUESTED.*|'
                               r'REQUESTED|BEST EFFORT.*|UNKNOWN|NOT APPLICABLE|REFUSED|DISABLED|STAY AT HOME.*|X+|NO EMPLOYER|'
                               r'OWNER|PRIVATE|PRIVATE PRACTICE|CONSULTANT|INDEPENDENT.*|FREELANCE.*|VOLUNTEER|MOM|PARENT|'
                               r'HOUSEWIFE|NOT WORKING|EMPLOYED|EMPLOYER|SAME|SEE ABOVE|NONE PROVIDED|PENDING|WILL PROVIDE|TBD|\W*)$')


def ascii_fold(s):
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


def basic(s):
    """Uppercase, ascii, & -> AND, punctuation -> space, collapse spaces."""
    if s is None or (isinstance(s, float)):
        return ''
    s = ascii_fold(str(s)).upper()
    s = s.replace('&', ' AND ').replace('+', ' AND ')
    s = re.sub(r"[’'`]", '', s)
    s = re.sub(r'[^A-Z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def org_key(s):
    """Canonical comparison key for an organization name."""
    b = basic(s)
    if not b:
        return ''
    b = re.sub(r'\b(DBA|D B A|AKA|FKA|F K A)\b.*$', '', b).strip() or b  # keep the legal name before a dba
    for rx, rep in _WORD_SUBS:
        b = rx.sub(rep, b)
    prev = None
    while prev != b:
        prev = b
        b = _SUFFIX_RE.sub(' ', b)
        b = re.sub(r'\s+', ' ', b).strip()
    b = re.sub(r'\bAND\b', ' ', b)
    b = re.sub(r'\s+', ' ', b).strip()
    return b


_NON_EMP_SEARCH = re.compile(r'\b(NOT EMPL\w*|NOT EMPLOYED|UNEMPLOYED|RETIRED|RETIREE|SELF ?EMPLOY\w*|SEL ?EMPLOY\w*|SELF|HOMEMAKER|HOUSEWIFE|NONE|N A|NA|NOT APPLICABLE|'
                             r'INFORMATION REQUESTED|INFO REQUESTED|REQUESTED|UNKNOWN|STUDENT|DISABLED)\b')


def is_non_employer(s):
    b = basic(s)
    if (not b) or b in NON_EMPLOYERS or bool(_NON_EMP_PATTERNS.match(b)):
        return True
    return len(b.split()) <= 4 and bool(_NON_EMP_SEARCH.search(b))


def person_key(first, last):
    f = basic(first).split(' ')
    f = f[0] if f and f[0] else ''
    l = basic(last)
    l = re.sub(r'\b(JR|SR|II|III|IV|MD|PHD|ESQ|DDS)\b', '', l).strip()
    return f'{l}|{f}'


def split_last_first(name):
    """'Reuben, James' -> ('JAMES', 'REUBEN'); 'James Reuben' -> ('JAMES','REUBEN')"""
    if not isinstance(name, str):
        return '', ''
    if ',' in name:
        last, first = name.split(',', 1)
    else:
        parts = name.strip().split()
        if len(parts) < 2:
            return '', basic(name)
        first, last = parts[0], parts[-1]
    return basic(first).split(' ')[0] if basic(first) else '', basic(last)


NICK = {
    'BILL': 'WILLIAM', 'WILL': 'WILLIAM', 'BILLY': 'WILLIAM', 'BOB': 'ROBERT', 'ROB': 'ROBERT', 'BOBBY': 'ROBERT',
    'JIM': 'JAMES', 'JIMMY': 'JAMES', 'JAMIE': 'JAMES', 'MIKE': 'MICHAEL', 'TOM': 'THOMAS', 'TONY': 'ANTHONY',
    'DAVE': 'DAVID', 'DAN': 'DANIEL', 'DANNY': 'DANIEL', 'JOE': 'JOSEPH', 'CHRIS': 'CHRISTOPHER', 'MATT': 'MATTHEW',
    'STEVE': 'STEVEN', 'STEPHEN': 'STEVEN', 'RICK': 'RICHARD', 'RICH': 'RICHARD', 'DICK': 'RICHARD', 'ED': 'EDWARD',
    'TED': 'EDWARD', 'LIZ': 'ELIZABETH', 'BETH': 'ELIZABETH', 'KATE': 'KATHERINE', 'KATHY': 'KATHERINE',
    'CATHERINE': 'KATHERINE', 'SUE': 'SUSAN', 'JEFF': 'JEFFREY', 'GREG': 'GREGORY', 'KEN': 'KENNETH', 'LARRY': 'LAWRENCE',
    'JON': 'JONATHAN', 'JOHNNY': 'JOHN', 'JACK': 'JOHN', 'PAT': 'PATRICK', 'PETE': 'PETER', 'SAM': 'SAMUEL',
    'ANDY': 'ANDREW', 'DREW': 'ANDREW', 'ALEX': 'ALEXANDER', 'BEN': 'BENJAMIN', 'NICK': 'NICHOLAS', 'TIM': 'TIMOTHY',
    'DOUG': 'DOUGLAS', 'RON': 'RONALD', 'DON': 'DONALD', 'GERRY': 'GERALD', 'JERRY': 'GERALD', 'FRANK': 'FRANCIS',
    'PAM': 'PAMELA', 'DEB': 'DEBORAH', 'DEBBIE': 'DEBORAH', 'JENNY': 'JENNIFER', 'JEN': 'JENNIFER', 'MEG': 'MARGARET',
    'PEGGY': 'MARGARET', 'MAGGIE': 'MARGARET', 'VICKY': 'VICTORIA', 'CINDY': 'CYNTHIA', 'SANDY': 'SANDRA',
    'NATE': 'NATHAN', 'ZACH': 'ZACHARY', 'PHIL': 'PHILIP', 'PHILLIP': 'PHILIP', 'FRED': 'FREDERICK', 'AL': 'ALBERT',
    'HANK': 'HENRY', 'HARRY': 'HENRY', 'CHUCK': 'CHARLES', 'CHARLIE': 'CHARLES', 'MARTY': 'MARTIN', 'LEN': 'LEONARD',
}


def canon_first(f):
    f = basic(f).split(' ')[0] if basic(f) else ''
    return NICK.get(f, f)


def zip5(z):
    if not isinstance(z, str):
        z = '' if z is None or (isinstance(z, float)) else str(z)
    m = re.match(r'(\d{5})', z.strip())
    return m.group(1) if m else ''
