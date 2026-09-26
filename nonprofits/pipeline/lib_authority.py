"""Classify Supplier Contracts 'Purchasing Authority' text into procurement categories.

Categories (hand-built from the 94 distinct authority strings; see DATA_NOTES.md):
  competitive          - text says bid / competitive solicitation / term contract awarded by bid
  sole_source_or_not_bid - sole source, 'not bid', 'no bid', 'no other source', sole-source waiver
  emergency_or_waiver  - emergency procurement, or legislation that waived competitive rules
                         (e.g., 2023 ordinance 'Core Initiatives Addressing Homelessness...' and
                         'Behavioral Health and Residential Care Contracts by DPH', 'Streamline contracting for homeless shelters')
  government           - agreements with other public entities / UC
  grant_unspecified    - 'Authorized by grant - not purchasing authority' (does not say whether competed)
  extension            - short-term contract/grant extensions
  other_unclear        - legacy / non-purchasing / rent / unspecified
The Supplier Contracts 'Sole Source' flag is kept separately; per the data dictionary it indicates whether
the purchasing authority *permits* sole-source purchases, not that the award was sole-sourced.
"""
import re

def classify(a):
    if not isinstance(a, str) or not a.strip():
        return "other_unclear"
    s = a.upper()
    if "EXTENSION" in s:
        return "extension"
    if "SOLICITATION WAIVED BY ORDINANCE" in s:
        return "emergency_or_waiver"
    if re.search(r"EMERGENCY", s) or s.startswith("CORE INITIATIVES ADDRESSING HOMELESSNESS") or \
       "BEHAVIORAL HEALTH AND RESIDENTIAL CARE CONTRACTS" in s or "STREAMLINE CONTRACTING FOR HOMELESS" in s:
        return "emergency_or_waiver"
    if re.search(r"GOVERNMENT ENTITY|PUBLIC AGENC|OTHER PUBLIC ENTIT|UCSF MASTER|UNIV HEALTHSYSTEMS|GOVERNMENT", s):
        # the UHC consortium purchases are group purchasing, treat as government/cooperative
        return "government"
    if re.search(r"SOLE SOURCE|NOT BID|NO BID|NO OTHER SOURCE|NOT BEEN COMPETITIVELY BID|INFEASIBLE|NO VALID OFFERS", s):
        return "sole_source_or_not_bid"
    if re.search(r"COMPETITIVE|DOCUMENT BID|- BID|PROFSERV-BID|\bBID\b|TERM CONTRACT", s):
        return "competitive"
    if "AUTHORIZED BY GRANT" in s:
        return "grant_unspecified"
    return "other_unclear"
