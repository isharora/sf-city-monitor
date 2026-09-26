#!/usr/bin/env python3
"""SF City Monitor - synthetic sample data for the design prototype.

Writes sample-data/<module>/... following design/DATA_CONTRACT_<module>.md, plus
sample-data/bundle.js (every file in one script) so the prototype works from file://.
EVERYTHING HERE IS SYNTHETIC. Organization, official and lobbyist names are invented.
Real department names are used only so the layout reads realistically; no number
describes a real department. Every file carries "sample": true.
"""
import json, math, os, random, re
from collections import defaultdict

random.seed(20260926)
HERE = os.path.dirname(os.path.abspath(__file__))
AS_OF = "2026-09-20"
GENERATED = "2026-09-26T09:00:00-07:00"
OUT = {}  # path -> object

def w(path, obj):
    OUT[path] = obj

def r2(x): return round(x, 2)
def r1(x): return round(x, 1)
def r3(x): return round(x, 3)
def lognorm(mu, sigma): return math.exp(random.gauss(mu, sigma))
def clamp(x, a, b): return max(a, min(b, x))
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')

# ---------------------------------------------------------------- shared reference
# CPI-U, San Francisco-Oakland-Hayward (BLS CUURS49BSA0), annual averages by fiscal year (July-June).
# Synthetic-but-plausible index, FY2025 = 1.000. Production: compute from BLS series.
DEFLATOR = {"base_fy": 2025, "source": "BLS CPI-U SF-Oakland-Hayward (CUURS49BSA0), FY average; SAMPLE VALUES",
            "index": {}}
_lvl = 0.735
_rates = {2016: 0.030, 2017: 0.031, 2018: 0.037, 2019: 0.032, 2020: 0.018, 2021: 0.022, 2022: 0.052, 2023: 0.040, 2024: 0.028, 2025: 0.026, 2026: 0.027}
for fy in range(2016, 2027):
    _lvl *= 1 + _rates[fy]
    DEFLATOR["index"][str(fy)] = _lvl
_base = DEFLATOR["index"]["2025"]
DEFLATOR["index"] = {k: r3(v / _base) for k, v in DEFLATOR["index"].items()}

POPULATION = {"source": "CA Dept of Finance E-1 estimates (SAMPLE VALUES)", "by_fy": {str(fy): v for fy, v in
    zip(range(2016, 2027), [864000, 870000, 875000, 878000, 870000, 842000, 815000, 809000, 812000, 818000, 823000])}}

DEPTS = [  # id, name, org group id, short
    ("DPH", "Public Health", "health", "DPH"), ("HSH", "Homelessness and Supportive Housing", "welfare", "HSH"),
    ("HSA", "Human Services Agency", "welfare", "HSA"), ("MOHCD", "Mayor's Office of Housing and Community Development", "welfare", "MOHCD"),
    ("DCYF", "Children, Youth and Their Families", "welfare", "DCYF"), ("DPW", "Public Works", "works", "Public Works"),
    ("MTA", "Municipal Transportation Agency", "works", "SFMTA"), ("SFPD", "Police", "protection", "Police"),
    ("SFFD", "Fire", "protection", "Fire"), ("SHF", "Sheriff", "protection", "Sheriff"), ("REC", "Recreation and Parks", "culture", "Rec & Park"),
    ("LIB", "Public Library", "culture", "Library"), ("DEM", "Emergency Management", "protection", "DEM"),
    ("DBI", "Building Inspection", "works", "DBI"), ("PLN", "Planning", "works", "Planning"), ("ENV", "Environment", "works", "Environment"),
    ("OEWD", "Economic and Workforce Development", "admin", "OEWD"), ("ART", "Arts Commission", "culture", "Arts"),
    ("TIS", "Technology", "admin", "DT"), ("ADM", "City Administrator", "admin", "City Admin"),
]
GROUPS = [("protection", "Public Protection"), ("works", "Public Works, Transportation and Commerce"), ("welfare", "Human Welfare and Neighborhood Development"),
          ("health", "Community Health"), ("culture", "Culture and Recreation"), ("admin", "General Administration and Finance")]
DEPT_BY_ID = {d[0]: d for d in DEPTS}
DEPT_LIST = [{"id": d[0], "name": d[1], "group": d[2], "short": d[3]} for d in DEPTS]

# ================================================================ NONPROFITS
NP_FY = list(range(2016, 2026))
AREAS = [("homeless", "Homelessness and housing"), ("health", "Health and behavioral health"), ("human", "Human services and seniors"),
         ("youth", "Children, youth and families"), ("workforce", "Workforce and economic development"), ("arts", "Arts and culture"), ("other", "Other")]
SIZE_BANDS = [("lt1m", "< $1M a year"), ("1-5m", "$1M–5M"), ("5-25m", "$5M–25M"), ("25m+", "$25M+")]
NP_DEPTS = ["DPH", "HSH", "HSA", "MOHCD", "DCYF", "OEWD", "ART", "REC", "LIB", "ADM", "SHF", "DEM"]
AREA_DEPTS = {"homeless": ["HSH", "MOHCD", "DPH"], "health": ["DPH", "HSA"], "human": ["HSA", "DPH", "ADM"], "youth": ["DCYF", "HSA", "REC"],
              "workforce": ["OEWD", "HSA", "SHF"], "arts": ["ART", "LIB", "REC"], "other": ["ADM", "DEM", "OEWD"]}
W1 = ["Bayview", "Mission", "Tenderloin", "Sunset", "Richmond", "Excelsior", "Western Addition", "Chinatown", "Potrero", "Visitacion Valley", "Haight", "SoMa", "Bernal", "Ingleside", "Golden Gate", "Pacific", "Dolores", "Presidio", "Ocean Beach", "Twin Peaks", "Glen Park", "Portola", "Castro", "Noe", "Balboa"]
W2 = {"homeless": ["Housing Partners", "Shelter Network", "Supportive Housing Collaborative", "Housing Alliance", "Navigation Services"],
      "health": ["Community Clinic", "Health Center", "Wellness Collaborative", "Behavioral Health Services", "Recovery Alliance"],
      "human": ["Family Services", "Senior Center", "Community Services", "Neighborhood Resource Center", "Legal Aid Society"],
      "youth": ["Youth Collaborative", "Children's Center", "Youth Development Fund", "After-School Alliance", "Family Resource Center"],
      "workforce": ["Workforce Institute", "Job Training Partners", "Economic Development Corporation", "Small Business Network", "Reentry Works"],
      "arts": ["Arts Collective", "Cultural Center", "Theater Project", "Music Alliance", "Community Arts Studio"],
      "other": ["Community Foundation", "Civic Trust", "Neighborhood Association", "Emergency Volunteers", "Service Corps"]}
orgs = []
names = set()
for i in range(220):
    area = random.choices([a[0] for a in AREAS], weights=[24, 22, 18, 16, 8, 8, 4])[0]
    while True:
        nm = f"{random.choice(W1)} {random.choice(W2[area])}"
        if nm not in names: names.add(nm); break
    base = lognorm(13.6, 1.35)  # annual city $ around FY2020
    base = clamp(base, 60_000, 120_000_000)
    depts = random.sample(AREA_DEPTS[area], k=min(len(AREA_DEPTS[area]), random.choices([1, 2, 3], weights=[55, 33, 12])[0]))
    growth = random.gauss(0.07, 0.09)
    dep = clamp(random.betavariate(2.2, 1.6), 0.03, 0.99)  # city share of revenue
    if base > 20e6: dep = clamp(dep + 0.15, 0.1, 0.99)
    orgs.append({"id": f"org-{i+1:03d}", "name": nm, "ein": f"94-{random.randint(1000000, 9999999)}", "area": area, "depts": depts,
                 "_base": base, "_growth": growth, "_dep": dep, "_start": random.choice(NP_FY[:6]) if random.random() < 0.35 else 2016,
                 "_end": 2025 if random.random() < 0.9 else random.choice(NP_FY[5:])})

pay_cells = []  # {fy, dept, org, amt, vouchers, contracts}
org_year_total = defaultdict(float)
for o in orgs:
    weights = [random.random() + 0.3 for _ in o["depts"]]
    for fy in NP_FY:
        if fy < o["_start"] or fy > o["_end"]: continue
        yr_amt = o["_base"] * (1 + o["_growth"]) ** (fy - 2020) * lognorm(0, 0.18)
        if fy in (2021, 2022) and o["area"] in ("homeless", "health"): yr_amt *= 1.25  # pandemic-era surge
        for d, wt in zip(o["depts"], weights):
            amt = yr_amt * wt / sum(weights)
            pay_cells.append({"fy": fy, "dept": d, "org": o["id"], "amt": round(amt), "vouchers": max(1, int(amt / random.uniform(20_000, 90_000))), "contracts": random.choice([1, 1, 1, 2, 2, 3])})
            org_year_total[(o["id"], fy)] += amt
for o in orgs:
    tot = sum(v for (oid, fy), v in org_year_total.items() if oid == o["id"])
    yrs = [fy for (oid, fy) in org_year_total if oid == o["id"]]
    avg = tot / max(1, len(yrs))
    o["size_band"] = "lt1m" if avg < 1e6 else "1-5m" if avg < 5e6 else "5-25m" if avg < 25e6 else "25m+"
    o["city_total"] = round(tot); o["first_fy"] = min(yrs); o["last_fy"] = max(yrs)
    o["city_fy_latest"] = round(org_year_total.get((o["id"], 2025), 0))

fin = []  # IRS 990 (synthetic)
for o in orgs:
    for fy in NP_FY:
        city = org_year_total.get((o["id"], fy))
        if not city or random.random() < 0.08: continue  # 990 missing some years
        rev = city / o["_dep"] * lognorm(0, 0.12)
        exp = rev * lognorm(-0.01, 0.07)
        net = max(-0.3 * exp, random.gauss(0.35, 0.45) * exp)
        unrestricted = net * clamp(random.gauss(0.6, 0.25), 0.05, 1.0)
        exec_comp = clamp(95_000 + 0.011 * exp ** 0.92 * lognorm(0, 0.22), 60_000, 620_000)
        if random.random() < 0.05: exec_comp *= 1.5
        fin.append({"org": o["id"], "fy": fy, "form": random.choice(["990", "990", "990", "990-EZ"]) if exp < 500_000 else "990",
                    "total_revenue": round(rev), "total_expenses": round(exp), "gov_grants": round(min(rev, city * lognorm(0.08, 0.15))),
                    "program_share": r3(clamp(random.gauss(0.82, 0.06), 0.5, 0.97)), "net_assets": round(net), "unrestricted_net_assets": round(unrestricted),
                    "months_reserves": r1(clamp(unrestricted / (exp / 12), -3, 36)), "employees": max(2, int(exp / random.uniform(85_000, 140_000))),
                    "exec_comp": round(exec_comp), "exec_title": random.choice(["Executive Director", "Executive Director", "CEO", "President & CEO"]),
                    "exec_comp_rank": 1, "highest_paid_count": random.choice([0, 0, 1, 2, 3, 5])})

contracts = []
cid = 0
for o in orgs:
    for d in o["depts"]:
        n = random.choice([1, 1, 2, 2, 3])
        for _ in range(n):
            cid += 1
            start_fy = random.choice(range(max(2014, o["_start"] - 1), 2025))
            term = random.choice([1, 2, 3, 3, 4, 5])
            orig = o["_base"] * term / len(o["depts"]) * lognorm(0, 0.35)
            amend = []
            cur = orig
            for k in range(random.choices([0, 1, 2, 3, 4, 6], weights=[35, 25, 18, 10, 8, 4])[0]):
                cur *= lognorm(0.22, 0.2)
                amend.append({"date": f"{min(2026, start_fy + k + 1)}-{random.randint(1, 12):02d}-15", "agreed_after": round(cur)})
            contracts.append({"id": f"C-{cid:05d}", "org": o["id"], "dept": d, "title": f"{random.choice(['Grant agreement', 'Professional services', 'Grant agreement', 'Master agreement'])}: {random.choice(['case management', 'shelter operations', 'behavioral health services', 'youth programming', 'workforce training', 'legal services', 'arts programming', 'food security', 'permanent supportive housing operations', 'community outreach'])}",
                              "start": f"{start_fy - 1}-07-01", "end": f"{start_fy - 1 + term}-06-30", "type": random.choice(["grant", "grant", "grant", "professional_services"]),
                              "sole_source": random.random() < 0.12, "original_agreed": round(orig), "agreed": round(cur), "consumed": round(cur * clamp(random.gauss(0.72, 0.2), 0.05, 1.0)), "amendments": amend})

findings = []
RESULTS = [("none", "No findings"), ("findings", "Findings, resolved"), ("corrective", "Corrective action plan"), ("elevated", "Elevated concern"), ("redflag", "Red flag")]
CATS = ["Fiscal: late or missing audit", "Fiscal: deficit or low reserves", "Fiscal: cost allocation", "Compliance: board governance", "Compliance: subcontractor monitoring", "Program: invoicing accuracy", "Program: performance reporting", "Compliance: personnel policies"]
fid = 0
for o in orgs:
    for fy in NP_FY[2:]:
        if (o["id"], fy) not in org_year_total: continue
        if org_year_total[(o["id"], fy)] < 150_000 and random.random() < 0.6: continue  # small grantees not monitored
        if random.random() < 0.55: continue
        fid += 1
        res = random.choices([r[0] for r in RESULTS], weights=[56, 22, 13, 7, 2])[0]
        if fy >= 2023: res = random.choices([r[0] for r in RESULTS], weights=[50, 22, 15, 10, 3])[0]
        cats = [] if res == "none" else random.sample(CATS, k=1 if res == "findings" else random.choice([1, 2, 3]))
        findings.append({"id": f"F-{fid:04d}", "org": o["id"], "fy": fy, "lead_dept": random.choice(o["depts"]), "type": "fiscal_compliance", "result": res, "categories": cats,
                         "report": {"title": f"Nonprofit Monitoring and Capacity Building Program: FY{fy} Annual Report", "url": None, "page": None if res == "none" else random.randint(8, 40)},
                         "note": None if res in ("none", "findings") else random.choice(["Corrective action plan in place; follow-up review scheduled.", "Organization on payment hold pending audited financials.", "Deficit in two consecutive years; city working with the organization on a plan."])})

NP_SOURCES = [
    {"id": "n9pm-xkyq", "name": "Vendor Payments (Vouchers)", "publisher": "SF Controller via data.sf.gov", "rows": 4_218_663, "rows_used": 612_402, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/n9pm-xkyq.json", "note": "Rows with non_profit_indicator = Y; joined to Supplier Contracts by contract_number."},
    {"id": "cqi5-hm2d", "name": "Supplier Contracts", "publisher": "SF Controller via data.sf.gov", "rows": 22_917, "rows_used": 3_884, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/cqi5-hm2d.json", "note": "non_profit = Y; agreed_amt history reconstructed from data_as_of snapshots."},
    {"id": "irs-990", "name": "IRS Form 990 e-file extracts (ProPublica Nonprofit Explorer API)", "publisher": "IRS / ProPublica", "rows": 2_140, "rows_used": 1_902, "as_of": "2026-08-31", "url": "https://projects.propublica.org/nonprofits/api", "note": "Matched on EIN where available, else name; match confidence stored per org."},
    {"id": "csa-npm", "name": "Controller CSA Nonprofit Monitoring and Capacity Building annual reports", "publisher": "SF Controller, City Services Auditor", "rows": 8, "rows_used": 8, "as_of": "2026-06-30", "url": "https://www.sf.gov/nonprofit-monitoring-and-capacity-building-program", "note": "PDF tables extracted; organization names matched to the vendor list."},
]
np_meta = {"sample": True, "module": "nonprofits", "as_of": AS_OF, "generated_at": GENERATED, "version": "0.3-sample",
           "fiscal_years": {"min": 2016, "max": 2025, "note": "City fiscal year, July–June; FY2025 = July 2024–June 2025"},
           "deflator": DEFLATOR, "dimensions": {
               "dept": {"label": "Department", "values": [{"id": d, **{k: v for k, v in next(x for x in DEPT_LIST if x["id"] == d).items() if k != "id"}} for d in NP_DEPTS]},
               "area": {"label": "Service area", "kind": "categorical", "values": [{"id": a, "label": l, "slot": i + 1} for i, (a, l) in enumerate(AREAS)]},
               "size_band": {"label": "Size (average city $ a year)", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in SIZE_BANDS]},
               "result": {"label": "Monitoring result", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in RESULTS]}},
           "counts": {"organizations": len(orgs), "payment_rows": len(pay_cells), "contracts": len(contracts), "form_990_years": len(fin), "monitoring_results": len(findings), "total_paid_all_years": round(sum(c["amt"] for c in pay_cells))},
           "small_n": 5, "sources": NP_SOURCES, "files": {}}
w("nonprofits/meta.json", np_meta)
w("nonprofits/orgs/index.json", {"sample": True, "as_of": AS_OF, "sources": ["n9pm-xkyq", "cqi5-hm2d", "irs-990"], "orgs": [
    {"id": o["id"], "name": o["name"], "ein": o["ein"], "area": o["area"], "size_band": o["size_band"], "depts": o["depts"], "city_total": o["city_total"], "city_fy_latest": o["city_fy_latest"],
     "first_fy": o["first_fy"], "last_fy": o["last_fy"], "match": {"method": random.choice(["ein", "ein", "ein", "name"]), "confidence": r2(random.uniform(0.86, 1.0))},
     "network_id": None} for o in orgs]})
w("nonprofits/payments/cells.json", {"sample": True, "as_of": AS_OF, "sources": ["n9pm-xkyq"], "note": "One row per (fiscal year, department, organization). Nominal dollars; deflate with meta.deflator. Production splits by fiscal year: payments/cells_<fy>.json.", "cells": pay_cells})
w("nonprofits/contracts/contracts.json", {"sample": True, "as_of": AS_OF, "sources": ["cqi5-hm2d"], "contracts": contracts})
w("nonprofits/finances/form990.json", {"sample": True, "as_of": "2026-08-31", "sources": ["irs-990"], "note": "One row per organization-year. fy is the IRS tax year ending in that fiscal year; city payments are city FY, so the city-share ratio is approximate (see DATA_NOTES).", "rows": fin})
w("nonprofits/reviews/findings.json", {"sample": True, "as_of": "2026-06-30", "sources": ["csa-npm"], "results": [{"id": a, "label": l} for a, l in RESULTS], "categories": CATS, "rows": findings})

# ================================================================ PERFORMANCE
PF_FY = list(range(2016, 2026))
CHARS = [("salaries", "Salaries"), ("fringe", "Fringe benefits"), ("overtime", "Overtime"), ("nonpersonnel", "Non-personnel services"), ("aid", "Aid, grants and city grant programs"), ("capital", "Capital and equipment"), ("other", "Debt, transfers and other")]
DEPT_BUDGET_2020 = {"DPH": 2_450e6, "HSH": 360e6, "HSA": 1_050e6, "MOHCD": 300e6, "DCYF": 260e6, "DPW": 380e6, "MTA": 1_250e6, "SFPD": 690e6, "SFFD": 420e6, "SHF": 260e6, "REC": 230e6, "LIB": 165e6, "DEM": 110e6, "DBI": 85e6, "PLN": 60e6, "ENV": 25e6, "OEWD": 95e6, "ART": 35e6, "TIS": 130e6, "ADM": 480e6}
CHAR_MIX = {"protection": [0.52, 0.22, 0.09, 0.12, 0.01, 0.02, 0.02], "works": [0.36, 0.16, 0.05, 0.28, 0.02, 0.10, 0.03], "welfare": [0.14, 0.06, 0.005, 0.15, 0.62, 0.005, 0.02],
            "health": [0.36, 0.16, 0.02, 0.28, 0.14, 0.02, 0.02], "culture": [0.45, 0.20, 0.02, 0.22, 0.03, 0.06, 0.02], "admin": [0.32, 0.14, 0.01, 0.40, 0.05, 0.05, 0.03]}
DEPT_BIAS = {d: random.gauss(0, 0.03) for d in DEPT_BUDGET_2020}  # systematic under/over-spend
DEPT_BIAS["HSH"] = -0.07; DEPT_BIAS["SFPD"] = 0.045; DEPT_BIAS["SFFD"] = 0.05; DEPT_BIAS["DBI"] = -0.06
spend_cells = []
for d in DEPT_BUDGET_2020:
    grp = DEPT_BY_ID[d][2]
    g = {"HSH": 0.14, "DPH": 0.06, "MTA": 0.045, "SFPD": 0.05, "DBI": 0.02, "PLN": 0.02, "OEWD": 0.07}.get(d, 0.05)
    for fy in PF_FY + [2026]:
        tot = DEPT_BUDGET_2020[d] * (1 + g) ** (fy - 2020) * lognorm(0, 0.03)
        if fy == 2021 and d in ("MTA", "REC", "LIB", "ART"): tot *= 0.9
        for (c, _), share in zip(CHARS, CHAR_MIX[grp]):
            budget = tot * share * lognorm(0, 0.05)
            for fund in ("gf", "other"):
                fshare = {"protection": 0.85, "works": 0.25, "welfare": 0.55, "health": 0.45, "culture": 0.4, "admin": 0.6}[grp]
                b = budget * (fshare if fund == "gf" else 1 - fshare)
                if b < 1: continue
                bias = DEPT_BIAS[d] + (0.35 if c == "overtime" and grp == "protection" else 0.15 if c == "overtime" else -0.02 if c == "aid" else 0)
                actual = None if fy == 2026 else round(b * (1 + bias + random.gauss(0, 0.05)))
                spend_cells.append({"fy": fy, "dept": d, "fund": fund, "char": c, "budget": round(b), "revised": round(b * lognorm(0.01, 0.03)), "actual": actual})
staff = []
HC_2020 = {"DPH": 7400, "HSH": 200, "HSA": 2300, "MOHCD": 130, "DCYF": 80, "DPW": 1700, "MTA": 6300, "SFPD": 2900, "SFFD": 1800, "SHF": 1000, "REC": 1000, "LIB": 900, "DEM": 300, "DBI": 300, "PLN": 250, "ENV": 130, "OEWD": 130, "ART": 50, "TIS": 300, "ADM": 900}
for d in HC_2020:
    grp = DEPT_BY_ID[d][2]
    for fy in PF_FY:
        hc = HC_2020[d] * (1 + {"HSH": 0.12, "DPH": 0.02}.get(d, 0.008)) ** (fy - 2020) * lognorm(0, 0.02)
        sal = sum(c["actual"] or 0 for c in spend_cells if c["dept"] == d and c["fy"] == fy and c["char"] == "salaries")
        ot = sum(c["actual"] or 0 for c in spend_cells if c["dept"] == d and c["fy"] == fy and c["char"] == "overtime")
        fam = {"protection": ["Police services", "Fire services", "Sheriff deputies"], "works": ["Transit operators", "Street maintenance", "Engineering"], "health": ["Nursing", "Behavioral health", "Hospital support"]}.get(grp, ["Administration", "Program staff", "Facilities"])
        staff.append({"fy": fy, "dept": d, "headcount": round(hc), "fte": round(hc * random.uniform(0.86, 0.95), 1), "salaries": sal, "overtime": ot,
                      "ot_share": r3(ot / (sal + ot)) if sal + ot else None, "employees_ot_over_100k": int(hc * (0.06 if grp == "protection" else 0.008) * lognorm(0, 0.3)),
                      "top_ot_job_families": [{"family": f, "overtime": round(ot * s)} for f, s in zip(fam, [0.55, 0.3, 0.15])]})
MEASURE_TPL = {
    "DPH": [("Patients seen at community clinics", "patients", "higher", "output"), ("Behavioral health clients housed within 90 days", "%", "higher", "outcome"), ("ED median wait time", "minutes", "lower", "outcome"), ("Cost per primary care visit", "$", "lower", "efficiency")],
    "HSH": [("Exits from shelter to permanent housing", "%", "higher", "outcome"), ("Shelter bed occupancy", "%", "higher", "output"), ("Returns to homelessness within 12 months", "%", "lower", "outcome"), ("Placements into permanent supportive housing", "households", "higher", "output")],
    "HSA": [("CalFresh applications processed within 30 days", "%", "higher", "outcome"), ("IHSS clients served", "clients", "higher", "output"), ("Child welfare: reunifications within 12 months", "%", "higher", "outcome")],
    "MOHCD": [("Affordable units completed", "units", "higher", "output"), ("Eviction prevention: households assisted", "households", "higher", "output")],
    "DCYF": [("Youth served in funded programs", "youth", "higher", "output"), ("Grantees meeting performance targets", "%", "higher", "outcome")],
    "DPW": [("Street cleaning requests closed within 48 hours", "%", "higher", "outcome"), ("Pothole repairs within 72 hours", "%", "higher", "outcome"), ("Street pavement condition index", "PCI", "higher", "outcome"), ("Cost per lane-mile resurfaced", "$", "lower", "efficiency")],
    "MTA": [("Muni on-time performance", "%", "higher", "outcome"), ("Service hours delivered vs scheduled", "%", "higher", "output"), ("Collisions per 100,000 miles", "per 100k mi", "lower", "outcome"), ("Cost per revenue hour", "$", "lower", "efficiency")],
    "SFPD": [("Priority A response time", "minutes", "lower", "outcome"), ("Violent crime clearance rate", "%", "higher", "outcome"), ("Officers completing crisis-intervention training", "%", "higher", "output")],
    "SFFD": [("Advanced life support on scene within 10 minutes", "%", "higher", "outcome"), ("Fire suppression on scene within 5 minutes", "%", "higher", "outcome")],
    "SHF": [("In-custody assaults per 100 inmates", "per 100", "lower", "outcome"), ("Inmates in programming", "%", "higher", "output")],
    "REC": [("Park maintenance score", "score", "higher", "outcome"), ("Recreation program enrollment", "enrollments", "higher", "output"), ("Scholarship share of enrollment", "%", "higher", "outcome")],
    "LIB": [("Library visits", "visits", "higher", "output"), ("Circulation per capita", "items", "higher", "output"), ("Program attendance", "attendees", "higher", "output")],
    "DEM": [("911 calls answered within 10 seconds", "%", "higher", "outcome"), ("311 cases closed within service level", "%", "higher", "outcome")],
    "DBI": [("Permits issued within target review time", "%", "higher", "outcome"), ("Complaint inspections within 72 hours", "%", "higher", "outcome")],
    "PLN": [("Planning applications decided within target", "%", "higher", "outcome"), ("Housing units entitled", "units", "higher", "output")],
    "ENV": [("Landfill diversion rate", "%", "higher", "outcome"), ("Municipal buildings on renewable power", "%", "higher", "outcome")],
    "OEWD": [("Job placements", "placements", "higher", "output"), ("Placements retained 12 months", "%", "higher", "outcome"), ("Cost per placement", "$", "lower", "efficiency")],
    "ART": [("Grants awarded to small organizations", "%", "higher", "output"), ("Public art projects completed", "projects", "higher", "output")],
    "TIS": [("Network uptime", "%", "higher", "outcome"), ("Help desk tickets resolved within SLA", "%", "higher", "outcome")],
    "ADM": [("Contracts certified within 30 days", "%", "higher", "outcome"), ("Fleet vehicles meeting emissions standard", "%", "higher", "outcome")],
}
GENERIC = [("Customer satisfaction survey score", "score", "higher", "outcome"), ("Invoices paid within 30 days", "%", "higher", "output"), ("Staff vacancy rate", "%", "lower", "outcome"), ("Complaints resolved within 30 days", "%", "higher", "outcome"), ("Contracts certified on time", "%", "higher", "output"), ("Training hours completed per employee", "hours", "higher", "output")]
measures, mvalues = [], []
mid = 0
for d, tpls in MEASURE_TPL.items():
    tpls = list(tpls) + random.sample(GENERIC, random.choice([3, 4, 5]))
    for name, unit, direction, mtype in tpls:
        mid += 1
        m = {"id": f"M-{mid:03d}", "dept": d, "name": name, "unit": unit, "direction": direction, "type": mtype, "first_fy": 2016, "last_fy": 2025, "dropped_fy": None, "replaced_by": None}
        if random.random() < 0.14: m["dropped_fy"] = random.choice([2019, 2020, 2022, 2023, 2024]); m["last_fy"] = m["dropped_fy"] - 1
        if random.random() < 0.08: m["first_fy"] = random.choice([2018, 2020, 2021])
        measures.append(m)
        if unit == "%": lvl = random.uniform(45, 92)
        elif unit == "minutes": lvl = random.uniform(6, 40)
        elif unit == "$": lvl = random.uniform(150, 9000)
        elif unit in ("PCI", "score"): lvl = random.uniform(60, 85)
        elif unit == "per 100k mi": lvl = random.uniform(4, 9)
        elif unit == "per 100": lvl = random.uniform(2, 8)
        else: lvl = lognorm(9, 1.3)
        target = lvl * (1.06 if direction == "higher" else 0.92)
        actual = lvl
        cost_link = mtype == "efficiency" or random.random() < 0.3
        prog_cost = lognorm(16.5, 0.7)
        for fy in range(m["first_fy"], m["last_fy"] + 1):
            drift = random.gauss(0.01, 0.05)
            actual *= 1 + drift
            if fy == 2021 and unit in ("visits", "enrollments", "attendees", "patients"): actual *= 0.45
            if fy == 2022 and unit in ("visits", "enrollments", "attendees", "patients"): actual *= 1.7
            prev_target = target
            lowered = False
            # targets sometimes chase actuals: if missed last year, lower target (make easier)
            if random.random() < 0.25 and fy > m["first_fy"]:
                target = target * (0.94 if direction == "higher" else 1.07)
                lowered = True
            elif random.random() < 0.3:
                target *= 1.02 if direction == "higher" else 0.98
            met = (actual >= target) if direction == "higher" else (actual <= target)
            if unit == "%": actual = clamp(actual, 5, 100); target = clamp(target, 5, 100)
            row = {"measure": m["id"], "fy": fy, "target": r1(target), "actual": r1(actual), "met": bool(met), "target_change": "easier" if lowered else ("harder" if target != prev_target and fy > m["first_fy"] else "same"), "source_doc": f"FY{fy} Performance Scorecards / Budget Book"}
            if fy == 2025 and random.random() < 0.1: row["actual"] = None; row["met"] = None
            if cost_link:
                prog_cost *= 1 + random.gauss(0.045, 0.06)
                row["program_cost"] = round(prog_cost)
                units = actual if unit not in ("%", "minutes", "PCI", "score", "per 100k mi", "per 100") else None
                row["cost_per_unit"] = round(prog_cost / units) if units else None
            mvalues.append(row)
PF_SOURCES = [
    {"id": "xdgd-c79v", "name": "Budget", "publisher": "SF Controller via data.sf.gov", "rows": 1_088_512, "rows_used": 402_190, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/xdgd-c79v.json", "note": "Original and revised budget by department, character and fund; spending side only."},
    {"id": "bpnb-jwfb", "name": "Spending and Revenue", "publisher": "SF Controller via data.sf.gov", "rows": 2_336_104, "rows_used": 918_330, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/bpnb-jwfb.json", "note": "Actual spending, revenue_or_spending = Spending."},
    {"id": "88g8-5mnd", "name": "Employee Compensation", "publisher": "SF Controller via data.sf.gov", "rows": 1_243_990, "rows_used": 1_243_990, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/88g8-5mnd.json", "note": "Fiscal-year rows; headcount = distinct employee_identifier per department-year; overtime summed."},
    {"id": "perf-scorecards", "name": "Performance measures (Controller Performance Scorecards + Mayor's Budget Book measure tables)", "publisher": "SF Controller / Mayor's Office", "rows": 3_120, "rows_used": len(mvalues), "as_of": "2026-07-31", "url": "https://sfgov.org/scorecards/", "note": "Budget Book PDF tables extracted; measure identity tracked by name across years; dropped measures flagged when a name disappears without a stated replacement."},
    {"id": "dof-e1", "name": "Population estimates (CA Dept of Finance E-1)", "publisher": "CA DOF", "rows": 11, "rows_used": 11, "as_of": "2026-05-01", "url": "https://dof.ca.gov/forecasting/demographics/estimates/", "note": "Per-resident figures use the January estimate of the fiscal year."},
    {"id": "bls-cpi", "name": "CPI-U San Francisco-Oakland-Hayward", "publisher": "BLS", "rows": 132, "rows_used": 11, "as_of": "2026-08-15", "url": "https://data.bls.gov/timeseries/CUURS49BSA0", "note": "Deflator; fiscal-year average; base FY2025."},
]
pf_meta = {"sample": True, "module": "performance", "as_of": AS_OF, "generated_at": GENERATED, "version": "0.3-sample",
           "fiscal_years": {"min": 2016, "max": 2025, "budget_max": 2026}, "deflator": DEFLATOR, "population": POPULATION,
           "dimensions": {"dept": {"label": "Department", "values": DEPT_LIST}, "group": {"label": "Department group", "values": [{"id": a, "label": l} for a, l in GROUPS]},
                          "char": {"label": "Spending category", "kind": "categorical", "values": [{"id": a, "label": l, "slot": i + 1} for i, (a, l) in enumerate(CHARS)]},
                          "fund": {"label": "Fund", "values": [{"id": "gf", "label": "General Fund"}, {"id": "other", "label": "Other funds"}]}},
           "counts": {"departments": len(DEPT_BUDGET_2020), "spending_rows": len(spend_cells), "staffing_rows": len(staff), "measures": len(measures), "measure_values": len(mvalues)},
           "small_n": 3, "sources": PF_SOURCES, "files": {}}
w("performance/meta.json", pf_meta)
w("performance/spending/cells.json", {"sample": True, "as_of": AS_OF, "sources": ["xdgd-c79v", "bpnb-jwfb"], "note": "Nominal dollars. One row per (fy, dept, fund, char). actual is null for the current budget year.", "cells": spend_cells})
w("performance/staffing/cells.json", {"sample": True, "as_of": AS_OF, "sources": ["88g8-5mnd"], "cells": staff})
w("performance/measures/measures.json", {"sample": True, "as_of": "2026-07-31", "sources": ["perf-scorecards"], "measures": measures})
w("performance/measures/values.json", {"sample": True, "as_of": "2026-07-31", "sources": ["perf-scorecards", "bpnb-jwfb"], "note": "program_cost and cost_per_unit are present only where a program-level cost could be tied to the measure (see DATA_NOTES for the mapping).", "rows": mvalues})

# ================================================================ AUDITS
AU_SOURCES_DIM = [("csa", "Controller's City Services Auditor", "CSA"), ("bla", "Budget and Legislative Analyst", "BLA"), ("cgj", "Civil Grand Jury", "CGJ")]
TOPICS = [("contracts", "Contracting and procurement"), ("it", "IT and data"), ("hr", "Staffing and overtime"), ("finance", "Financial controls"), ("safety", "Public safety"), ("housing", "Housing and homelessness"), ("facilities", "Facilities and capital"), ("service", "Service delivery"), ("governance", "Governance and oversight")]
STATUSES = [("implemented", "Implemented"), ("in_progress", "In progress"), ("open", "Open, not started"), ("not_implementing", "Department will not implement"), ("closed_other", "Closed without implementation (superseded / no longer applicable)")]
AGREE = [("agree", "Agreed"), ("partial", "Partially agreed"), ("disagree", "Disagreed"), ("none", "No response recorded")]
reports, recs = [], []
rid = 0; kid = 0
TITLES = {"csa": ["Audit of {d}'s Contract Monitoring", "{d}: Overtime Controls Audit", "Follow-up Audit: {d} Cash Handling", "Performance Audit of {d} Grant Administration", "Audit of {d} Information Technology Controls", "{d}: Fleet and Facilities Management Audit"],
          "bla": ["Performance Audit of {d}", "Policy Analysis: {d} Spending Trends", "Management Audit of {d}", "Analysis of {d} Contracting Practices"],
          "cgj": ["{d}: Are We Getting What We Pay For?", "The {d} Backlog", "Oversight at {d}: A Civil Grand Jury Report", "{d} and the Public Trust"]}
dept_pool = list(DEPT_BUDGET_2020)
topic_repeat = defaultdict(list)  # (dept, topic) -> rec ids
for yr in range(2014, 2026):
    for src, _, _ in AU_SOURCES_DIM:
        n_rep = {"csa": random.choice([6, 7, 8, 9]), "bla": random.choice([2, 3, 3, 4]), "cgj": random.choice([3, 4, 5])}[src]
        for _ in range(n_rep):
            rid += 1
            d = random.choice(dept_pool)
            topic = random.choice([t[0] for t in TOPICS])
            date = f"{yr}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            n_recs = {"csa": random.randint(4, 18), "bla": random.randint(5, 20), "cgj": random.randint(6, 14)}[src]
            rep = {"id": f"R-{rid:04d}", "source": src, "title": random.choice(TITLES[src]).format(d=DEPT_BY_ID[d][1]), "date": date, "depts": [d] + ([random.choice(dept_pool)] if random.random() < 0.2 else []),
                   "topic": topic, "url": None, "pages": random.randint(18, 96), "n_recs": n_recs, "summary": f"Sample summary: the report reviewed {DEPT_BY_ID[d][1]}'s {dict(TOPICS)[topic].lower()} and made {n_recs} recommendations.",
                   "followups": [f"{yr + k}-{random.randint(1, 12):02d}-01" for k in range(1, random.choice([1, 2, 3, 4])) if yr + k <= 2026]}
            reports.append(rep)
            for k in range(n_recs):
                kid += 1
                agree = random.choices([a[0] for a in AGREE], weights={"csa": [82, 12, 4, 2], "bla": [60, 25, 10, 5], "cgj": [45, 30, 20, 5]}[src])[0]
                pri = random.choices(["high", "medium", "low"], weights=[25, 50, 25])[0]
                mu = {"csa": 2.5, "bla": 2.9, "cgj": 3.0}[src] + (0.5 if agree == "partial" else 1.0 if agree == "disagree" else 0)
                months = lognorm(mu, 0.6)
                age = (2026 - yr) * 12 + 9 - int(date[5:7])
                if agree == "disagree" and random.random() < 0.6: status = "not_implementing"; months_to = None
                elif months <= age and random.random() < 0.9: status = "implemented"; months_to = r1(months)
                elif random.random() < 0.08: status = "closed_other"; months_to = None
                elif random.random() < 0.55: status = "in_progress"; months_to = None
                else: status = "open"; months_to = None
                if yr >= 2024 and status == "implemented" and random.random() < 0.4: status = "in_progress"; months_to = None
                dollars = round(lognorm(13.2, 1.4)) if random.random() < 0.28 else None
                cons = clamp(round(({"high": 6, "medium": 4, "low": 2}[pri] + (2 if dollars and dollars > 5e6 else 1 if dollars else 0) + (1 if age > 36 else 0) + random.choice([0, 0, 1])), 1), 1, 10)
                rec = {"id": f"K-{kid:05d}", "report": rep["id"], "source": src, "dept": rep["depts"][0] if random.random() < 0.9 else rep["depts"][-1], "date_issued": date, "topic": topic, "priority": pri,
                       "text": f"Sample recommendation {k + 1}: the department should {random.choice(['document and enforce', 'establish a written procedure for', 'assign a single owner for', 'report quarterly to its commission on', 'reconcile monthly', 'complete a staffing analysis of', 'implement system controls over'])} {random.choice(['contract monitoring', 'overtime approval', 'grant closeout', 'access to financial systems', 'inventory counts', 'performance reporting', 'complaint follow-up'])}.",
                       "agreed": agree, "response_text": None if agree == "none" else "Sample response text.", "status": status, "status_date": f"{min(2026, yr + random.randint(0, 4))}-{random.randint(1, 12):02d}-01", "months_to_close": months_to,
                       "last_followup": rep["followups"][-1] if rep["followups"] else None, "repeat_of": None, "dollars_at_stake": dollars, "consequence": {"score": cons, "why": None}}
                prev = topic_repeat[(rec["dept"], topic)]
                if prev and random.random() < 0.3:
                    rec["repeat_of"] = random.choice(prev)
                    rec["consequence"]["why"] = "Repeats an earlier recommendation on the same theme at the same department."
                elif cons >= 7:
                    rec["consequence"]["why"] = random.choice(["High priority with dollars at stake and more than three years open.", "Auditor rated high priority; department partially agreed; still open.", "Controls over public funds; open past the last follow-up."])
                topic_repeat[(rec["dept"], topic)].append(rec["id"])
                recs.append(rec)
AU_SOURCES = [
    {"id": "csa-reports", "name": "Controller CSA audit reports and recommendation follow-up reports", "publisher": "SF Controller, City Services Auditor", "rows": 312, "rows_used": len([r for r in reports if r["source"] == "csa"]), "as_of": "2026-08-31", "url": "https://www.sf.gov/audits", "note": "PDFs; recommendations and status tables extracted; semi-annual follow-up status matched by recommendation number."},
    {"id": "bla-reports", "name": "Budget and Legislative Analyst performance audits and policy analyses", "publisher": "SF Board of Supervisors BLA", "rows": 96, "rows_used": len([r for r in reports if r["source"] == "bla"]), "as_of": "2026-08-31", "url": "https://sfbos.org/budget-legislative-analyst-reports", "note": "Recommendations and department responses extracted from report text; implementation status from BLA follow-up hearings where held."},
    {"id": "cgj-reports", "name": "Civil Grand Jury reports and required responses", "publisher": "SF Superior Court Civil Grand Jury", "rows": 88, "rows_used": len([r for r in reports if r["source"] == "cgj"]), "as_of": "2026-08-31", "url": "https://civilgrandjury.sfgov.org/", "note": "Penal Code 933 responses (agree / disagree / will implement / requires further analysis / will not implement) mapped to the shared status scale."},
]
au_meta = {"sample": True, "module": "audits", "as_of": AS_OF, "generated_at": GENERATED, "version": "0.3-sample", "years": {"min": 2014, "max": 2025, "note": "Calendar year the report was issued"},
           "dimensions": {"source": {"label": "Who recommended", "kind": "categorical", "values": [{"id": a, "label": l, "short": s, "slot": i + 1} for i, (a, l, s) in enumerate(AU_SOURCES_DIM)]},
                          "dept": {"label": "Department", "values": DEPT_LIST}, "topic": {"label": "Topic", "values": [{"id": a, "label": l} for a, l in TOPICS]},
                          "status": {"label": "Implementation status", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in STATUSES]},
                          "agreed": {"label": "Department response", "kind": "polarity", "values": [{"id": a, "label": l} for a, l in AGREE]},
                          "priority": {"label": "Auditor priority", "values": [{"id": a, "label": a.title()} for a in ["high", "medium", "low"]]}},
           "status_mapping": {"cgj": {"agree": "Agrees with finding", "partial": "Partially disagrees", "disagree": "Wholly disagrees", "implemented": "Has been implemented", "in_progress": "Will be implemented in the future", "open": "Requires further analysis", "not_implementing": "Will not be implemented"}},
           "counts": {"reports": len(reports), "recommendations": len(recs)}, "small_n": 5, "sources": AU_SOURCES, "files": {}}
w("audits/meta.json", au_meta)
w("audits/reports/reports.json", {"sample": True, "as_of": "2026-08-31", "sources": ["csa-reports", "bla-reports", "cgj-reports"], "reports": reports})
w("audits/recs/recs.json", {"sample": True, "as_of": "2026-08-31", "sources": ["csa-reports", "bla-reports", "cgj-reports"], "note": "One row per recommendation. Production splits by year issued: recs/recs_<year>.json.", "rows": recs})

# ================================================================ NETWORK
ETYPES = [("committee", "Candidate or officeholder committee", 7), ("contractor", "City contractor (for-profit)", 2), ("nonprofit", "Nonprofit with city funding", 1), ("lobbyist", "Registered lobbyist firm", 3), ("donor_org", "Other organization or PAC", 4), ("individuals", "Individuals (aggregated)", 0), ("department", "City department", 0), ("official", "Elected or appointed official", 7)]
FLOWS = [("contribution", "Campaign contribution", "Form 460 Schedule A", "Contributions"), ("behested", "Behested payment", "SFEC-3.610 / FPPC 803", "Behested"), ("lobby_contact", "Lobbying contact", "Lobbyist monthly disclosure", "Lobby contacts"), ("lobby_payment", "Payment to lobbyist", "Lobbyist monthly disclosure", "Lobby payments"), ("contract", "Contract approval", "SFEC-126(f)4 / Supplier Contracts", "Contracts"), ("payment", "City payment", "Vendor Payments", "City payments")]
FIRST = ["A.", "B.", "C.", "D.", "E.", "J.", "K.", "L.", "M.", "R.", "S.", "T."]
LAST = ["Rivera", "Chen", "Okafor", "Nguyen", "Goldberg", "Alvarez", "Park", "Washington", "Santos", "Lindqvist", "Haddad", "Moreno", "Tanaka", "Osei", "Brennan", "Kaur"]
ents, flows = [], []
def ent(id_, type_, name, **kw):
    e = {"id": id_, "type": type_, "name": name, **kw}; ents.append(e); return e
officials = []
OFFICES = [("Mayor", 1), ("City Attorney", 1), ("District Attorney", 1), ("Supervisor, District {n}", 11), ("Treasurer", 1), ("Assessor-Recorder", 1), ("Sheriff", 1)]
n = 0
for office, cnt in OFFICES:
    for k in range(cnt):
        n += 1
        nm = f"{random.choice(FIRST)} {random.choice(LAST)}"
        off = office.format(n=k + 1)
        o = ent(f"off-{n:02d}", "official", nm, office=off, term=[random.choice([2019, 2021, 2023]), 2027], sample_note="Fictional officeholder")
        officials.append(o)
        ent(f"cmte-{n:02d}", "committee", f"{nm} for {off.split(',')[0]} 2024", official=o["id"], fppc_id=f"14{random.randint(10000, 99999)}")
        if random.random() < 0.4: ent(f"cmte-{n:02d}b", "committee", f"Re-elect {nm} 2022", official=o["id"], fppc_id=f"13{random.randint(10000, 99999)}")
for d in ["DPH", "HSH", "MTA", "DPW", "MOHCD", "OEWD", "PLN", "DBI", "REC", "TIS", "ADM", "SFPD", "HSA", "DCYF", "ART"]:
    ent(f"dept-{d}", "department", DEPT_BY_ID[d][1], code=d)
CONTR = ["Golden Gate Civil Constructors", "Bay Rail Systems", "Pacific Paving Co.", "Sunset Engineering Group", "Presidio Technology Partners", "Marina Facilities Services", "Twin Peaks Environmental", "Embarcadero Consulting", "Mission Creek Builders", "Ocean View Security", "Hilltop Medical Supply", "Fog City Data Systems", "Bayshore Transit Services", "Portola Architecture", "Lakeside Waste Solutions", "Coastal Electric", "Cathedral Hill Health Staffing", "Balboa Fleet Services", "Dogpatch Design Build", "Alamo Square Software"]
contractors = [ent(f"con-{i+1:02d}", "contractor", nm, principals_disclosed=random.randint(2, 9), sector=random.choice(["construction", "IT", "professional services", "facilities", "transit", "health"])) for i, nm in enumerate(CONTR)]
nonprofits_nw = []
for o in random.sample(orgs, 40):
    e = ent(f"np-{o['id']}", "nonprofit", o["name"], nonprofit_org=o["id"])
    o["network_id"] = e["id"]; nonprofits_nw.append(e)
OUT["nonprofits/orgs/index.json"]["orgs"] = [dict(x, network_id=next((o.get("network_id") for o in orgs if o["id"] == x["id"]), None)) for x in OUT["nonprofits/orgs/index.json"]["orgs"]]
LOBBY = ["Civic Strategies LLC", "Bay Area Public Affairs", "Kearny Street Advocacy", "Van Ness Government Relations", "Market Street Partners", "Polk Street Consulting", "Union Square Advisors", "Harbor Advocacy Group", "Ferry Building Strategies", "Clement Street Counsel", "Divisadero Public Policy", "Judah Advocacy"]
lobbyists = [ent(f"lob-{i+1:02d}", "lobbyist", nm, lobbyist_type="contact", registered_since=random.choice([2015, 2017, 2019, 2021])) for i, nm in enumerate(LOBBY)]
DONOR = ["Building Trades Council PAC", "Tenants Rights Coalition PAC", "Realtors Association PAC", "Firefighters Local PAC", "Nurses Association PAC", "Tech Forward Committee", "Small Business Alliance PAC", "Housing Now Action Fund", "Police Officers Association PAC", "Hospitality Industry PAC", "Transit Riders Fund", "Neighborhood Preservation Committee"]
donor_orgs = [ent(f"pac-{i+1:02d}", "donor_org", nm) for i, nm in enumerate(DONOR)]
# individuals: aggregated nodes only (never named)
agg_all = ent("ind-all", "individuals", "Individual donors not affiliated with a listed entity (aggregate)", count=18_420)
agg_by_contractor = {}
for c in contractors:
    if random.random() < 0.75:
        agg_by_contractor[c["id"]] = ent(f"ind-{c['id']}", "individuals", f"Individuals affiliated with {c['name']} (aggregate)", affiliated_with=c["id"], count=random.randint(3, 40), basis="employer/occupation field on Form 460 matches the contractor; principals per SFEC-126(f)4")
committees = [e for e in ents if e["type"] == "committee"]
depts_nw = [e for e in ents if e["type"] == "department"]
def rdate(y0=2019, y1=2026):
    y = random.randint(y0, y1); m = random.randint(1, 12 if y < 2026 else 9); return f"{y}-{m:02d}-{random.randint(1, 28):02d}"
fid = 0
def flow(frm, to, type_, date, amount, **kw):
    global fid; fid += 1
    f = {"id": f"fl-{fid:05d}", "from": frm, "to": to, "type": type_, "date": date, "amount": amount, "count": kw.pop("count", 1), **kw}
    flows.append(f); return f
# contracts + payments (contractor -> dept, dept -> contractor)
ban_rows = []
for c in contractors:
    for _ in range(random.randint(1, 4)):
        d = random.choice(depts_nw)
        approval = rdate(2019, 2025)
        amt = round(lognorm(15.2, 1.1))
        if amt < 100_000: amt = 100_000 + amt
        cf = flow(d["id"], c["id"], "contract", approval, amt, ref={"form": "SFEC-126(f)4", "id": f"126f4-{random.randint(100000, 999999)}", "url": None}, approving_body=random.choice(["Board of Supervisors", "Department head", "Commission"]))
        y, m, dd = map(int, approval.split("-"))
        # ban window: from proposal submission (approx. 6 months before approval in this sample) to 12 months after approval (§1.126 as amended 2020)
        ban_start = f"{y if m > 6 else y - 1}-{(m - 6 - 1) % 12 + 1:02d}-{dd:02d}"
        ban_end = f"{y + 1}-{m:02d}-{dd:02d}"
        for k in range(random.randint(2, 8)):
            flow(c["id"], d["id"], "payment", rdate(y, min(2026, y + 2)), round(amt * random.uniform(0.05, 0.3)), count=random.randint(1, 6), ref={"form": "Vendor Payments", "id": None})
        ban_rows.append({"contract": cf["id"], "contractor": c["id"], "dept": d["id"], "approval_date": approval, "amount": amt, "window": [ban_start, ban_end], "approving_body": cf["approving_body"], "contributions": []})
# contributions: individuals aggregate / contractors' individuals / PACs -> committees
for cm in committees:
    flow(agg_all["id"], cm["id"], "contribution", f"{random.choice([2022, 2023, 2024])}-12-31", round(lognorm(12.5, 0.6)), count=random.randint(200, 2400), aggregated=True, period="cycle total")
    for p in random.sample(donor_orgs, random.randint(4, 10)):
        for _ in range(random.randint(1, 4)):
            flow(p["id"], cm["id"], "contribution", rdate(2021, 2025), random.choice([500, 500, 1000, 2500, 5000, 10000, 25000]), ref={"form": "Form 460 Sch. A", "id": None})
    for npx in random.sample(nonprofits_nw, random.randint(0, 3)):
        flow(npx["id"], cm["id"], "contribution", rdate(2021, 2025), random.choice([500, 1000, 2500]), ref={"form": "Form 460 Sch. A", "id": None}, note="Nonprofit-sponsored committee or affiliated PAC; see filing")
from datetime import date as _date
def _d(s_): y, m, dd = map(int, s_.split("-")); return _date(y, m, dd)
ban_records = []
for c in contractors:
    agg = agg_by_contractor.get(c["id"])
    if not agg: continue
    my_contracts = [br for br in ban_rows if br["contractor"] == c["id"]]
    for cm in random.sample(committees, random.randint(1, 5)):
        for _ in range(random.randint(1, 4)):
            dt = rdate(2019, 2025)
            amt = random.choice([100, 250, 500, 500, 500, 250])
            n_ind = random.randint(1, 6)
            fl = flow(agg["id"], cm["id"], "contribution", dt, amt * n_ind, count=n_ind, aggregated=True, ref={"form": "Form 460 Sch. A", "id": None})
            # one record per contribution: nearest contract approval, inside ANY window of this contractor?
            nearest = min(my_contracts, key=lambda br: abs((_d(dt) - _d(br["approval_date"])).days))
            inside_any = [br for br in my_contracts if br["window"][0] <= dt <= br["window"][1]]
            covered = bool(inside_any) and random.random() < 0.7  # sample rule: committee's official approves this contract
            rec = {"flow": fl["id"], "contractor": c["id"], "committee": cm["id"], "date": dt, "amount": fl["amount"], "count": n_ind,
                   "nearest_contract": nearest["contract"], "days_from_approval": (_d(dt) - _d(nearest["approval_date"])).days,
                   "inside_window": bool(inside_any), "window_contract": inside_any[0]["contract"] if inside_any else None, "covered_official": covered,
                   "review": "appears_to_warrant_review" if covered else ("inside_window_not_covered" if inside_any else "outside_window"),
                   "why": ("Contribution dated inside the §1.126 window of contract " + inside_any[0]["contract"] + " and the committee belongs to an official who approves that contract, per the SFEC-126(f)4 filing. Attribution of the donors to the contractor rests on the employer field; the Ethics Commission may have reviewed this and the contribution may have been returned.") if covered else None}
            ban_records.append(rec)
            if covered: fl["flags"] = {"in_ban_window": True, "ban_contract": inside_any[0]["contract"]}
for br in ban_rows:
    br["contributions"] = [r["flow"] for r in ban_records if r["window_contract"] == br["contract"]]
# expected share by chance: union coverage of each contractor's windows over 2019-01-01..2025-12-31, weighted by that contractor's contribution count
def _coverage(cid):
    ivs = sorted((_d(br["window"][0]), _d(br["window"][1])) for br in ban_rows if br["contractor"] == cid)
    lo, hi = _date(2019, 1, 1), _date(2025, 12, 31); days = 0; cur = None
    for a, b in ivs:
        a, b = max(a, lo), min(b, hi)
        if b < a: continue
        if cur and a <= cur[1]: cur = (cur[0], max(cur[1], b))
        else:
            if cur: days += (cur[1] - cur[0]).days
            cur = (a, b)
    if cur: days += (cur[1] - cur[0]).days
    return days / (hi - lo).days
# behested payments: payor (contractor / nonprofit / PAC / individuals agg) -> payee (nonprofit / department) at behest of official
behested = []
for _ in range(140):
    off = random.choice(officials)
    payor = random.choice(contractors + donor_orgs + nonprofits_nw[:10] + [agg_all])
    payee = random.choice(nonprofits_nw + depts_nw[:6])
    amt = round(lognorm(10.3, 1.0) / 100) * 100
    dt = rdate(2019, 2026)
    fl = flow(payor["id"], payee["id"], "behested", dt, amt, behest_of=off["id"], purpose=random.choice(["Community event", "Homelessness services", "Public health outreach", "Youth programs", "Disaster relief", "Arts festival", "Small business recovery"]), ref={"form": "SFEC-3.610(b)", "id": None})
    interested = payor["type"] == "contractor" or (payor["type"] == "nonprofit" and random.random() < 0.3)
    behested.append({"flow": fl["id"], "official": off["id"], "payor": payor["id"], "payee": payee["id"], "date": dt, "amount": amt, "purpose": fl["purpose"], "payor_interested_party": interested, "filed_within_30_days": random.random() < 0.85})
# lobbying: client (contractor / nonprofit / PAC) -> lobbyist (payment); lobbyist -> dept/official (contact)
lobby_contacts = []
LTOPICS = ["Contract award", "Land use / entitlement", "Budget appropriation", "Permit / inspection", "Legislation", "Grant funding", "Transit policy", "Housing policy"]
for lob in lobbyists:
    clients = random.sample(contractors + nonprofits_nw[:15] + donor_orgs, random.randint(2, 7))
    for cl in clients:
        for q in range(random.randint(2, 10)):
            dt = rdate(2019, 2026)
            flow(cl["id"], lob["id"], "lobby_payment", dt, round(lognorm(9.5, 0.7) / 100) * 100, count=1, ref={"form": "Lobbyist monthly disclosure", "id": None})
        for _ in range(random.randint(2, 12)):
            tgt = random.choice(depts_nw + officials)
            dt = rdate(2019, 2026)
            topic = random.choice(LTOPICS)
            cnt = random.randint(1, 9)
            fl = flow(lob["id"], tgt["id"], "lobby_contact", dt, None, count=cnt, client=cl["id"], topic=topic, ref={"form": "Lobbyist monthly disclosure", "id": None})
            lobby_contacts.append({"flow": fl["id"], "lobbyist": lob["id"], "client": cl["id"], "target": tgt["id"], "month": dt[:7], "topic": topic, "contacts": cnt})
# nonprofit loop rows
loop_rows = []
for e in nonprofits_nw:
    o = next(x for x in orgs if x["id"] == e["nonprofit_org"])
    beh_recv = sum(b["amount"] for b in behested if b["payee"] == e["id"])
    beh_made = sum(b["amount"] for b in behested if b["payor"] == e["id"])
    lob = sum(f["amount"] for f in flows if f["type"] == "lobby_payment" and f["from"] == e["id"])
    contacts = sum(f["count"] for f in flows if f["type"] == "lobby_contact" and f.get("client") == e["id"])
    if beh_recv or beh_made or lob:
        loop_rows.append({"entity": e["id"], "org": o["id"], "city_paid_fy2025": o["city_fy_latest"], "behested_received": beh_recv, "behested_made": beh_made, "lobby_payments": lob, "lobby_contacts": contacts,
                          "depts_funding": o["depts"], "depts_lobbied": sorted({f["to"].replace("dept-", "") for f in flows if f["type"] == "lobby_contact" and f.get("client") == e["id"] and f["to"].startswith("dept-")})})
# concentration
conc = []
for cm in committees:
    fl = [f for f in flows if f["type"] == "contribution" and f["to"] == cm["id"]]
    tot = sum(f["amount"] for f in fl)
    by_type = defaultdict(float)
    for f in fl:
        src = next(e for e in ents if e["id"] == f["from"])
        by_type["individuals" if src["type"] == "individuals" and not src.get("affiliated_with") else "contractor_affiliated" if src["type"] == "individuals" else src["type"]] += f["amount"]
    named = sorted([f["amount"] for f in fl if not f.get("aggregated")], reverse=True)
    conc.append({"committee": cm["id"], "official": cm["official"], "total": tot, "n_contributions": sum(f["count"] for f in fl), "by_source_type": {k: round(v) for k, v in by_type.items()},
                 "top10_share_named": r3(sum(named[:10]) / sum(named)) if named else None, "n_named_sources": len(named), "cycle": "2024"})
# graph layout hints: clusters (community ids) precomputed
clusters = {}
for e in ents:
    if e["type"] in ("official", "committee"): clusters[e["id"]] = "officials"
    elif e["type"] == "department": clusters[e["id"]] = "city"
    elif e["type"] in ("lobbyist",): clusters[e["id"]] = "lobbying"
    elif e["type"] == "nonprofit": clusters[e["id"]] = "nonprofits"
    else: clusters[e["id"]] = "contractors_and_donors"
for e in ents: e["cluster"] = clusters[e["id"]]
# base rates for the ban analysis
n_contr_flows = len(ban_records)
n_inside = sum(1 for r in ban_records if r["inside_window"])
n_covered = sum(1 for r in ban_records if r["covered_official"])
_w = defaultdict(int)
for r in ban_records: _w[r["contractor"]] += 1
cov = sum(_coverage(cid) * k for cid, k in _w.items()) / max(1, sum(_w.values()))
NW_RULES = [
    {"id": "ban", "short": "Contractor contribution ban", "cite": "S.F. Campaign and Governmental Conduct Code §1.126", "text": "A party to a City contract worth $100,000 or more (and its board members, principal officers, 10%+ owners, subcontractors and committees it controls) may not contribute to a City elective officer who must approve the contract, or to that officer's candidate or controlled committees, from the submission of a proposal until 12 months after the contract is approved (6 months before January 2020). Departments file form SFEC-126(f)4 within 30 days of approval.", "verify": "Data agent: confirm thresholds, window length by date, and which approving bodies are covered, against the current code text and the Ethics Commission's regulations."},
    {"id": "behested", "short": "Behested payment disclosure and restrictions", "cite": "S.F. C&GC Code §3.610–3.630; Cal. Gov. Code §82004.5 and §84224", "text": "City officers must disclose payments of $1,000 or more made at their request (behested) to a third party, on form SFEC-3.610(b) within 30 days of the threshold being met. Since 2022, officers and employees may not solicit behested payments from interested parties (contractors, permit applicants, lobbyists) in matters before them, with exceptions.", "verify": "Data agent: confirm effective dates and the interested-party definition in the 2022 ordinance and its amendments."},
    {"id": "lobby", "short": "Lobbyist registration, disclosure and contribution limits", "cite": "S.F. C&GC Code Article II, Chapter 1 (§2.100 et seq.), esp. §2.110 and §2.115", "text": "Contact lobbyists register with the Ethics Commission and file monthly reports of contacts with City officers (who, for which client, on what matter) and payments received. Lobbyists may not make contributions to officers they have contacted on behalf of a client, or give gifts to them.", "verify": "Data agent: confirm the current thresholds for registration and the exact scope of §2.115 prohibitions."},
    {"id": "limits", "short": "Contribution limits", "cite": "S.F. C&GC Code §1.114", "text": "Contributions to a candidate for City elective office are limited to $500 per person per election. Contributions from corporations are prohibited (§1.114(b)).", "verify": "Data agent: confirm the limit amount for each election cycle in the data."},
]
NW_SOURCES = [
    {"id": "sfec-460", "name": "Campaign finance transactions (Form 460 Schedules A, C, E; Form 497)", "publisher": "SF Ethics Commission via data.sf.gov", "rows": 1_284_411, "rows_used": 212_804, "as_of": "2026-09-15", "url": "https://data.sf.gov/", "note": "Filtered to committees for City elective offices; individuals aggregated by employer match; addresses dropped at ingest."},
    {"id": "sfec-126f", "name": "SFEC-126(f)4 contract notifications (contractor contribution ban)", "publisher": "SF Ethics Commission via data.sf.gov", "rows": 6_902, "rows_used": 6_902, "as_of": "2026-09-15", "url": "https://data.sf.gov/", "note": "One filing per approved contract ≥ $100k; disclosed principals used only to attribute aggregate individual contributions."},
    {"id": "sfec-3610", "name": "Behested payment disclosures (SFEC-3.610(b))", "publisher": "SF Ethics Commission via data.sf.gov", "rows": 3_118, "rows_used": 3_118, "as_of": "2026-09-15", "url": "https://data.sf.gov/", "note": "Payor, payee, official, amount, date, purpose."},
    {"id": "sfec-lobby", "name": "Lobbyist registrations, contacts and payments", "publisher": "SF Ethics Commission via data.sf.gov", "rows": 148_220, "rows_used": 148_220, "as_of": "2026-09-15", "url": "https://data.sf.gov/", "note": "Contacts aggregated to (lobbyist, client, target, month, topic)."},
    {"id": "cqi5-hm2d", "name": "Supplier Contracts", "publisher": "SF Controller via data.sf.gov", "rows": 22_917, "rows_used": 9_410, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/cqi5-hm2d.json", "note": "Contract approval dates and amounts for entities in the network."},
    {"id": "n9pm-xkyq", "name": "Vendor Payments (Vouchers)", "publisher": "SF Controller via data.sf.gov", "rows": 4_218_663, "rows_used": 1_102_338, "as_of": "2026-09-19", "url": "https://data.sf.gov/resource/n9pm-xkyq.json", "note": "Payments to entities in the network, aggregated by month."},
]
nw_meta = {"sample": True, "module": "network", "as_of": "2026-09-15", "generated_at": GENERATED, "version": "0.3-sample", "years": {"min": 2019, "max": 2026, "note": "Calendar years; transaction dates"},
           "dimensions": {"etype": {"label": "Entity type", "kind": "categorical", "values": [{"id": a, "label": l, "slot": s} for a, l, s in ETYPES]},
                          "flow": {"label": "Flow type", "values": [{"id": a, "label": l, "form": f, "short": sh} for a, l, f, sh in FLOWS]},
                          "amount_bands": [{"id": 0, "label": "Any amount"}, {"id": 1000, "label": "≥ $1,000"}, {"id": 10000, "label": "≥ $10,000"}, {"id": 100000, "label": "≥ $100,000"}]},
           "rules": NW_RULES, "fairness": {"individuals": "Private individuals appear only in aggregates (never named; addresses dropped at ingest). Named nodes are organizations, officials in their public roles, registered lobbyists, and contractors with their disclosed principals counted, not named.", "timing": "A donation near a contract or approval is a pattern worth checking, not proof of improper influence.", "review": "'Appears to warrant review' is shown only when a transaction appears to fall inside a cited legal rule; the Ethics Commission may already have reviewed it and contributions may have been returned."},
           "counts": {"entities": len(ents), "flows": len(flows), "contracts_with_126f": len(ban_rows), "behested_payments": len(behested), "lobby_contact_rows": len(lobby_contacts), "individuals_aggregated": agg_all["count"] + sum(e["count"] for e in agg_by_contractor.values())},
           "small_n": 5, "sources": NW_SOURCES, "files": {}}
w("network/meta.json", nw_meta)
w("network/entities.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-460", "sfec-126f", "sfec-3610", "sfec-lobby", "cqi5-hm2d"], "entities": ents})
w("network/flows.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-460", "sfec-126f", "sfec-3610", "sfec-lobby", "cqi5-hm2d", "n9pm-xkyq"], "note": "One row per (from, to, type, date) after aggregating individuals. Production splits by year: flows/flows_<year>.json.", "flows": flows})
w("network/analyses/ban_window.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-126f", "sfec-460"], "rule": "ban", "base_rates": {"contributions_by_contractor_affiliated": n_contr_flows, "inside_any_window": n_inside, "inside_window_covered_official": n_covered, "expected_share_if_unrelated": r3(cov), "expected_note": "For each contractor, the share of days between 2019-01-01 and 2025-12-31 covered by the union of its ban windows, weighted by that contractor's number of contribution records. If timing were unrelated to contracts, about this share of contributions would land inside a window by chance."}, "contracts": ban_rows, "records": ban_records})
w("network/analyses/behested.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-3610"], "rule": "behested", "rows": behested})
w("network/analyses/lobbying.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-lobby"], "rule": "lobby", "topics": LTOPICS, "rows": lobby_contacts})
w("network/analyses/concentration.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-460"], "rule": "limits", "rows": conc})
w("network/analyses/loop.json", {"sample": True, "as_of": "2026-09-15", "sources": ["sfec-3610", "sfec-lobby", "n9pm-xkyq"], "note": "Nonprofits that receive city money and also appear as behested payors or payees, or as lobbying clients. Appearing here is not improper: nonprofits may lawfully lobby and receive behested payments; the loop is shown so readers can check the pattern.", "rows": loop_rows})

# ================================================================ helpers for commentary numbers
def money(x):
    a = abs(x)
    if a >= 1e9: return f"${x/1e9:.1f} billion"
    if a >= 1e6: return f"${x/1e6:.0f} million" if a >= 10e6 else f"${x/1e6:.1f} million"
    if a >= 1e3: return f"${x/1e3:.0f}k"
    return f"${x:.0f}"
def pct(x, d=0): return f"{x*100:.{d}f}%"
tot25 = sum(c["amt"] for c in pay_cells if c["fy"] == 2025); tot16 = sum(c["amt"] for c in pay_cells if c["fy"] == 2016)
real16 = tot16 / DEFLATOR["index"]["2016"]
n_orgs25 = len({c["org"] for c in pay_cells if c["fy"] == 2025})
top10 = sorted(((sum(v for (oid, fy), v in org_year_total.items() if oid == o["id"] and fy == 2025), o) for o in orgs), key=lambda t: -t[0])[:10]
top10_share = sum(t[0] for t in top10) / tot25
dep_hi = [f for f in fin if f["fy"] == 2024 and org_year_total.get((f["org"], 2024), 0) / f["total_revenue"] > 0.75]
fin24 = [f for f in fin if f["fy"] == 2024]
res_low = [f for f in fin24 if f["months_reserves"] < 1]
elev = [f for f in findings if f["result"] in ("elevated", "redflag")]
elev_orgs = len({f["org"] for f in elev})
n_amend = len([c for c in contracts if c["amendments"]])
big_growth = [c for c in contracts if c["amendments"] and c["agreed"] / c["original_agreed"] >= 2]
# performance
def real_total(fy, dept=None):
    return sum((c["actual"] or 0) for c in spend_cells if c["fy"] == fy and (dept is None or c["dept"] == dept)) / DEFLATOR["index"][str(fy)]
gt = real_total(2025) / real_total(2016) - 1
pop_ch = POPULATION["by_fy"]["2025"] / POPULATION["by_fy"]["2016"] - 1
per_res_ch = (real_total(2025) / POPULATION["by_fy"]["2025"]) / (real_total(2016) / POPULATION["by_fy"]["2016"]) - 1
vals25 = [v for v in mvalues if v["fy"] == 2025 and v["met"] is not None]
met_share = sum(1 for v in vals25 if v["met"]) / len(vals25)
n_dropped = len([m for m in measures if m["dropped_fy"]])
n_lowered = len([v for v in mvalues if v["target_change"] == "easier"])
n_lowered_missed = len([v for v in mvalues if v["target_change"] == "easier" and any(p["measure"] == v["measure"] and p["fy"] == v["fy"] - 1 and p["met"] is False for p in mvalues)])
ot_tot = sum(s["overtime"] for s in staff if s["fy"] == 2025); ot_prot = sum(s["overtime"] for s in staff if s["fy"] == 2025 and DEPT_BY_ID[s["dept"]][2] == "protection")
gap_rows = [(d, sum((c["actual"] or 0) for c in spend_cells if c["fy"] == 2025 and c["dept"] == d) / sum(c["budget"] for c in spend_cells if c["fy"] == 2025 and c["dept"] == d) - 1) for d in DEPT_BUDGET_2020]
over = max(gap_rows, key=lambda t: t[1]); under = min(gap_rows, key=lambda t: t[1])
# audits
impl = [r for r in recs if r["status"] == "implemented"]
impl_share = len(impl) / len(recs)
med_months = sorted(r["months_to_close"] for r in impl)[len(impl) // 2]
open_recs = [r for r in recs if r["status"] in ("open", "in_progress")]
old_open = [r for r in open_recs if r["date_issued"] < "2023-01-01"]
disagree = [r for r in recs if r["agreed"] == "disagree"]
cgj_agree = sum(1 for r in recs if r["source"] == "cgj" and r["agreed"] == "agree") / sum(1 for r in recs if r["source"] == "cgj")
csa_agree = sum(1 for r in recs if r["source"] == "csa" and r["agreed"] == "agree") / sum(1 for r in recs if r["source"] == "csa")
repeats = [r for r in recs if r["repeat_of"]]
# network
beh_tot = sum(b["amount"] for b in behested); beh_int = sum(b["amount"] for b in behested if b["payor_interested_party"])
top_lob_client = max(set(f["from"] for f in flows if f["type"] == "lobby_payment"), key=lambda cid: sum(f["amount"] for f in flows if f["type"] == "lobby_payment" and f["from"] == cid))
top_lob_name = next(e["name"] for e in ents if e["id"] == top_lob_client)
share_named = [c["top10_share_named"] for c in conc if c["top10_share_named"]]
med_top10 = sorted(share_named)[len(share_named) // 2]

# ================================================================ COMMENTARY
def com(view, headline, paragraphs, templates=None, caveats=None, annotations=None, sources=None):
    w(f"commentary/{view}.json", {"sample": True, "view": view, "author": "Sample commentary (synthetic data)", "headline": headline, "paragraphs": paragraphs,
                                  "annotations": annotations or [], "templates": templates or [], "caveats": caveats or [], "sources": sources or []})
TF = "Too few records match to summarize; widen the years or clear a filter."
# --- nonprofits
com("np-overview", f"The city paid {money(tot25)} to {n_orgs25} nonprofits in FY2025; the ten largest received {pct(top10_share)} of it.",
    [f"Payments to nonprofits grew from {money(tot16)} in FY2016 ({money(real16)} in FY2025 dollars) to {money(tot25)} in FY2025, driven mostly by homelessness and health contracts. Growth in real terms is smaller than the nominal figures suggest; every chart on this dashboard can be switched between the two.",
     f"Concentration is the headline: a small number of large organizations receive most of the money, and several of them get more than three quarters of their total revenue from the city. That is a dependency worth understanding, not a finding of wrongdoing: the city deliberately contracts out large services, and the organizations that run them are large by design.",
     f"The Controller's monitoring program reviewed most large grantees each year. {elev_orgs} organizations were rated 'elevated concern' or 'red flag' at least once; the reviews view links each to the report."],
    templates=[{"id": "total", "template": "For your filters: {orgs_fmt} organizations were paid {total} across {rows_fmt} department-year payment records ({years}).", "requires": {"rows_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "The nonprofit flag in Vendor Payments is set by the supplier record and is missing or wrong for some organizations; the pipeline adds IRS 990 matches, but coverage is not complete."},
             {"severity": "medium", "text": "Payments are cash paid in a fiscal year, not services delivered; a late invoice moves money between years."},
             {"severity": "low", "text": "Real dollars use the SF-area CPI-U, which understates cost growth in health care and housing services."}],
    sources=["nonprofits/payments/cells.json", "nonprofits/orgs/index.json", "nonprofits/reviews/findings.json"])
com("np-flows", "Three departments account for most nonprofit spending, and the mix by service area has shifted toward homelessness since FY2020.",
    ["Public Health, Homelessness and Supportive Housing, and the Human Services Agency contract out large parts of their service delivery. A department's share here says how much of its work is done by nonprofits, not whether that is good or bad.",
     "The trend chart is in real dollars by default. Pandemic-era federal money shows as a bump in FY2021–22 for health and homelessness; the question for FY2024–25 is how much of that spending has become permanent."],
    templates=[{"id": "flows", "template": "{total} paid to {orgs_fmt} organizations across {depts_fmt} departments, {years}. Largest department: {top_dept} ({top_dept_share} of the total).", "requires": {"rows_min": 5}, "fallback": TF}],
    annotations=[{"chart": "np_trend", "x": 2021, "text": "Pandemic-era federal funds flow through city contracts", "placement": "top"}],
    caveats=[{"severity": "medium", "text": "Service area is assigned per organization (from IRS NTEE code and city program), so a multi-service organization's money is not split."}],
    sources=["nonprofits/payments/cells.json"])
com("np-dependency", f"{len(dep_hi)} organizations with a 2024 Form 990 received more than 75% of their revenue from the city.",
    ["City share is city payments divided by the organization's total revenue on its Form 990. It answers: if city funding stopped, what would be left? A high share is normal for organizations built to run city programs, and it also means the city carries their operational risk.",
     "The scatter puts city dollars on a log axis against the city share. The top-right is the group to watch: large and dependent. The reviews view shows whether those organizations have had monitoring findings."],
    templates=[{"id": "dep", "template": "Among {orgs_fmt} organizations with a Form 990 in {fy}, the median city share is {median_share}; {hi_fmt} organizations are above 75%.", "requires": {"orgs_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Form 990 tax years and city fiscal years are not aligned; a share above 100% usually means a timing mismatch or an unmatched affiliate, not fraud."},
             {"severity": "medium", "text": "Fiscal sponsors and organizations with large pass-through grants have inflated or deflated shares."}],
    sources=["nonprofits/finances/form990.json", "nonprofits/payments/cells.json"])
com("np-pay", f"Executive pay tracks organization size; {len(res_low)} of {len(fin24)} organizations reported less than one month of unrestricted reserves in 2024.",
    ["Top executive compensation rises with organization size, as it does across the sector. The chart shows each organization against the median for its size band, so 'high' means high for a peer of that size. High pay is unusual, not improper, and boards set it; the point of showing it is that the city funds most of these budgets.",
     "Reserves matter more for accountability: an organization with under a month of reserves that depends on the city for most of its revenue is one late payment away from missing payroll. The Controller's monitoring program flags exactly this."],
    templates=[{"id": "pay", "template": "In {fy}, across {orgs_fmt} organizations, the median top-executive compensation is {median_pay}; {n_low_fmt} organizations have under one month of reserves.", "requires": {"orgs_min": 5}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "Reported compensation is total compensation (base, bonus, deferred, benefits) for the highest-paid officer; it can include one-time payouts."},
             {"severity": "medium", "text": "Unrestricted net assets are a proxy for reserves; organizations with property holdings look richer than their cash position."}],
    sources=["nonprofits/finances/form990.json"])
com("np-growth", f"{len(big_growth)} of {n_amend} amended contracts at least doubled from their original agreed amount.",
    ["Contract growth is measured as the final agreed amount over the original. Amendments are normal (terms extend, services are added), so a doubling is a signal to read the contract, not a finding. The histogram shows how common each level of growth is, and the table names the largest.",
     "Sole-source contracts are marked; they are permitted under the Administrative Code but deserve a closer look when they also grow fast."],
    templates=[{"id": "growth", "template": "Of {contracts_fmt} contracts starting {years}, {amended_fmt} were amended; the median final-to-original ratio among amended contracts is {median_ratio}×, and {doubled_fmt} at least doubled.", "requires": {"contracts_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Original agreed amounts are reconstructed from the earliest snapshot of the Supplier Contracts dataset the pipeline captured; contracts that started before the first snapshot show their first observed amount, which understates growth."}],
    sources=["nonprofits/contracts/contracts.json"])
com("np-reviews", f"Most monitored organizations had no findings; {elev_orgs} were rated 'elevated concern' or worse at least once.",
    ["The Controller's Nonprofit Monitoring and Capacity Building Program runs joint fiscal and compliance monitoring for organizations funded by several departments. Results are on a five-step scale from 'no findings' to 'red flag'. Every row here cites the annual report and page.",
     "Findings cluster in fiscal controls (late audits, deficits, cost allocation). A finding is a review result, not a judgment of the organization's mission or program quality."],
    templates=[{"id": "reviews", "template": "{reviews_fmt} monitoring results for {orgs_fmt} organizations, {years}: {none_share} had no findings, {elev_fmt} were elevated concern or red flag.", "requires": {"reviews_min": 5}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "Only organizations in the joint monitoring pool are reviewed (roughly those with multiple city funders); single-funder grantees are monitored by their department and are not here."}],
    sources=["nonprofits/reviews/findings.json"])
com("np-orgs", "Every organization in the payments data, with its city money, service area and links to its finances, reviews and network connections.", ["Search or sort; open an organization to see its profile."], sources=["nonprofits/orgs/index.json"])
# --- performance
com("pf-overview", f"Real spending rose {pct(gt)} since FY2016 while population fell {pct(abs(pop_ch))}: {pct(per_res_ch)} more per resident, and {pct(met_share)} of measures met their FY2025 target.",
    [f"In FY2025 dollars, city departments spent {pct(gt)} more than in FY2016. Population fell, so spending per resident rose faster. Both numbers are real, and neither says whether the money bought better outcomes; that is the job of the measures views.",
     f"Departments met {pct(met_share)} of the measures they reported in FY2025. That number is only as honest as the measures: {n_dropped} measures were dropped over the decade and targets were made easier {n_lowered} times, {n_lowered_missed} of them the year after a miss. The integrity view lists each.",
     f"Overtime was {money(ot_tot)} in FY2025, {pct(ot_prot / ot_tot)} of it in public-safety departments where minimum staffing rules drive it."],
    templates=[{"id": "ov", "template": "For your filters: {depts_fmt} departments spent {total} ({dollars}) in FY{fy}; {met_share} of {measures_fmt} reported measures met their target.", "requires": {"measures_min": 3}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Actuals include pass-through and one-time federal funds; the FY2021–22 spike is mostly not local money."},
             {"severity": "medium", "text": "Performance measures are self-reported by departments; the Controller audits only a sample."}],
    sources=["performance/spending/cells.json", "performance/measures/values.json", "performance/staffing/cells.json"])
com("pf-spending", "Spending per resident rose in real terms in almost every department; the largest increases were in homelessness and health.",
    ["The lines show real and nominal dollars for the selected departments; the difference between them is inflation. Per-resident spending divides by the January population estimate of each fiscal year, so the 2020–22 population drop pushes it up.",
     "The category breakdown separates salaries, benefits, overtime, non-personnel, aid and capital. Human-welfare departments are mostly 'aid and grants', which is the money that flows to the nonprofits in the first dashboard."],
    templates=[{"id": "sp", "template": "{depts_fmt} departments, FY{fy0}–FY{fy1}: spending changed {change_real} in real terms and {change_nominal} in nominal terms; per resident it changed {change_per_res} (real).", "requires": {"depts_min": 1}, "fallback": TF}],
    annotations=[{"chart": "pf_trend", "x": 2022, "text": "One-time federal relief peaks", "placement": "top"}],
    caveats=[{"severity": "medium", "text": "Department reorganizations (HSH created FY2017 from DPH and HSA programs) create artificial jumps; the pipeline restates prior years where it can."}],
    sources=["performance/spending/cells.json"])
com("pf-staffing", f"Overtime was {money(ot_tot)} in FY2025; public-safety departments account for {pct(ot_prot / ot_tot)} of it.",
    ["Headcount is distinct employees paid in the year, which overstates full-time equivalents for departments with seasonal staff (Rec and Park, Library). Overtime share is overtime divided by base plus overtime pay.",
     "High overtime is not automatically waste: minimum staffing rules and vacancies both drive it. The chart pairs overtime share with vacancy-driven headcount changes so readers can see which is at work."],
    templates=[{"id": "st", "template": "FY{fy}, {depts_fmt} departments: {headcount_fmt} employees, overtime {ot_total} ({ot_share} of base plus overtime); {ot100k_fmt} employees earned more than $100,000 in overtime.", "requires": {"depts_min": 1}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "Employees who worked in two departments in a year are counted in both."}],
    sources=["performance/staffing/cells.json"])
com("pf-outcomes", f"Departments met {pct(met_share)} of their FY2025 targets; the share varies from under half to nearly all by department.",
    ["Each cell is the share of a department's reported measures that met their target in a year. Grey cells mean fewer than three measures were reported. A high share can mean strong performance or easy targets; the integrity view separates the two.",
     "Output measures (things done) are met more often than outcome measures (results for residents)."],
    templates=[{"id": "oc", "template": "FY{fy}, {depts_fmt} departments: {met_fmt} of {measures_fmt} reported measures met their target ({met_share}); outcome measures {met_share_outcome}, output measures {met_share_output}.", "requires": {"measures_min": 3}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "A measure's definition can change without its name changing; the pipeline flags value jumps above 50% but cannot catch every redefinition."}],
    sources=["performance/measures/values.json", "performance/measures/measures.json"])
com("pf-cost", "Where a program cost can be tied to a measure, unit costs rose faster than inflation in most service areas.",
    ["Cost per outcome divides a program's actual spending by the number of units its measure counts (placements, visits, repairs). It works only for count measures with a clearly linked program budget; percentages and rates are excluded, and the mapping is listed in the data notes.",
     "Rising unit cost can mean lower productivity, harder cases, or a deliberate shift to more intensive services; the view shows the trend and leaves the interpretation to the reader, with the department's own explanation where one exists."],
    templates=[{"id": "cost", "template": "{measures_fmt} measures with a linked cost, {depts_fmt} departments: median change in real cost per unit FY{fy0}–FY{fy1} is {median_change}.", "requires": {"measures_min": 2}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Program-to-measure links are the analyst's judgment; a different mapping gives different unit costs. Each link's rationale is in DATA_NOTES."}],
    sources=["performance/measures/values.json"])
com("pf-integrity", f"{n_dropped} measures were dropped and targets were made easier {n_lowered} times, {n_lowered_missed} of them right after a miss.",
    ["Measures disappear for good reasons (a program ends, a better measure replaces it) and for convenient ones. The list shows each dropped measure, its last value and whether it was being met. A target that becomes easier the year after a miss is the clearest signal of target-chasing; it is not misconduct, but it changes what the 'met' share means.",
     "Read with the outcomes view: a department with a high met share and many lowered targets is different from one with a high met share and stable targets."],
    templates=[{"id": "int", "template": "{depts_fmt} departments, FY{fy0}–FY{fy1}: {dropped_fmt} measures dropped ({dropped_missed_fmt} were being missed when dropped); targets made easier {lowered_fmt} times, {lowered_after_miss_fmt} the year after a miss.", "requires": {"measures_min": 3}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "A renamed measure looks like a drop plus an addition; the pipeline matches names with a similarity threshold and lists uncertain matches."}],
    sources=["performance/measures/measures.json", "performance/measures/values.json"])
com("pf-gaps", f"In FY2025, {DEPT_BY_ID[over[0]][1]} spent {pct(over[1], 1)} more than its original budget and {DEPT_BY_ID[under[0]][1]} {pct(abs(under[1]), 1)} less.",
    ["Budget versus actual compares the original adopted budget with year-end actuals. Overspending in public safety is usually overtime; underspending in housing and homelessness usually means projects and hiring lagged the appropriation. Both are stories about capacity, not necessarily about control.",
     "The dumbbell shows each department's original budget and actual; the heat grid shows the pattern over years so a one-off can be told from a habit."],
    templates=[{"id": "gap", "template": "FY{fy}, {depts_fmt} departments: actual spending was {gap_total} versus the original budget ({gap_pct}); {over_fmt} departments overspent by more than 5%, {under_fmt} underspent by more than 5%.", "requires": {"depts_min": 1}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "Supplemental appropriations during the year are in the revised budget; the gap to the revised budget is shown in the table."}],
    sources=["performance/spending/cells.json"])
com("pf-depts", "Every department with its spending, staffing, measures and links to its audits and nonprofit contracts.", ["Open a department for its scorecard."], sources=["performance/meta.json"])
# --- audits
com("au-overview", f"{pct(impl_share)} of {len(recs):,} recommendations since 2014 were implemented; the median took {med_months:.0f} months, and {len(old_open)} recommendations issued before 2023 are still open.",
    [f"Three bodies recommend changes to city departments: the Controller's auditors (with formal follow-up), the Budget and Legislative Analyst (for the Board of Supervisors) and the Civil Grand Jury (whose recommendations require a response under Penal Code 933 but have no enforcement). Implementation rates differ accordingly, and the source filter applies everywhere on this dashboard.",
     f"Departments agreed with {pct(csa_agree)} of Controller recommendations and {pct(cgj_agree)} of Civil Grand Jury recommendations. Disagreement is legitimate; {len(disagree)} recommendations were formally disagreed with, and their reasons are on the report pages.",
     f"{len(repeats)} recommendations repeat an earlier one on the same theme at the same department. Repeats are the strongest sign that a fix did not stick."],
    templates=[{"id": "ov", "template": "For your filters: {recs_fmt} recommendations from {reports_fmt} reports, {years}; {impl_share} implemented, {open_fmt} open or in progress, median {median_months} months to implement.", "requires": {"recs_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "'Implemented' is the department's own report for BLA and Civil Grand Jury recommendations; only the Controller's auditors verify implementation."},
             {"severity": "medium", "text": "Status is as of the last follow-up; a recommendation with no follow-up since 2022 may have been implemented without anyone recording it."}],
    sources=["audits/recs/recs.json", "audits/reports/reports.json"])
com("au-status", "Controller recommendations are implemented most often; Civil Grand Jury recommendations are most often left open.",
    ["Status uses one five-step scale for all three sources, mapped from each body's own vocabulary (the mapping is in the methods). 'Closed without implementation' covers superseded and no-longer-applicable items and is shown in grey because it is neither success nor failure.",
     "The department chart is sorted by open share; a department with many open recommendations may simply have been audited more."],
    templates=[{"id": "status", "template": "{recs_fmt} recommendations, {years}: {impl_share} implemented, {prog_share} in progress, {open_share} open, {notimpl_share} will not be implemented.", "requires": {"recs_min": 5}, "fallback": TF}],
    sources=["audits/recs/recs.json"])
com("au-time", f"Half of implemented recommendations took under {med_months:.0f} months; one in ten took more than four years.",
    ["Time to implement is measured from the report date to the follow-up that first recorded 'implemented', so it is rounded up to the follow-up cadence (about six months for the Controller). The step curves show, for recommendations issued in each year, the share implemented within N months; recent years are cut off where they cannot yet be observed.",
     "High-priority recommendations are not implemented faster on average."],
    templates=[{"id": "time", "template": "{impl_fmt} implemented recommendations, {years}: median {median_months} months, 75th percentile {p75_months}, 90th percentile {p90_months}.", "requires": {"impl_min": 5}, "fallback": TF}],
    caveats=[{"severity": "medium", "text": "Recommendations still open are excluded from the medians (survivor bias); the step curves correct for this."}],
    sources=["audits/recs/recs.json"])
com("au-agreement", "Departments agree with most recommendations, and agreement predicts implementation: disagreed recommendations are rarely implemented.",
    ["Agreement is the department's formal response at publication. The grid crosses response with eventual status. The bottom-left cell (agreed, never implemented) is the accountability gap; the top-right (disagreed, implemented anyway) is rare and usually follows a Board hearing.",
     "Disagreeing is legitimate and sometimes right; the report page shows each department's reasons."],
    templates=[{"id": "agree", "template": "{recs_fmt} recommendations, {years}: departments agreed with {agree_share}, partially agreed with {partial_share}, disagreed with {disagree_share}. Among agreed recommendations {impl_agreed} were implemented; among disagreed, {impl_disagreed}.", "requires": {"recs_min": 5}, "fallback": TF}],
    sources=["audits/recs/recs.json"])
com("au-repeat", f"{len(repeats)} recommendations repeat an earlier recommendation on the same theme at the same department.",
    ["A repeat is a later recommendation coded to the same topic at the same department, confirmed by an analyst reading both. Repeats show where a fix was reported as implemented and the problem came back, or was never fixed. Contracting and overtime controls repeat most.",
     "The chains table links each repeat to its predecessor so a reader can check the coding."],
    templates=[{"id": "repeat", "template": "{repeats_fmt} of {recs_fmt} recommendations ({repeat_share}) repeat an earlier one; the most repeated theme is {top_topic} ({top_topic_fmt})."}],
    caveats=[{"severity": "high", "text": "Repeat coding is a judgment (model-assisted, analyst-confirmed, confidence stored per pair); different coders would draw the line differently."}],
    sources=["audits/recs/recs.json"])
com("au-open", "The most consequential open recommendations combine high auditor priority, money at stake and years without action.",
    ["The consequence score (1–10) is the analyst's ranking from priority, dollars at stake, age and whether the recommendation repeats an earlier one; the rule is published in the methods and each score carries its reason. It is a reading aid, not an audit judgment.",
     "Open does not mean ignored: many are in progress. The list links to each report so a reader can check the department's latest response."],
    templates=[{"id": "open", "template": "{open_fmt} open or in-progress recommendations, {years}; {high_fmt} scored 7 or more; {dollars} in identified dollars at stake.", "requires": {"open_min": 3}, "fallback": TF}],
    sources=["audits/recs/recs.json"])
com("au-reports", "Every report, with its recommendations and their status.", ["Open a report for its page."], sources=["audits/reports/reports.json"])
# --- network
com("nw-overview", f"Contractor-affiliated individuals made {n_contr_flows} aggregated contribution records since 2019; {n_covered} fall inside a ban window for a covered official, against about {pct(cov)} expected by chance.",
    ["This dashboard connects four public disclosure systems: campaign contributions (Form 460), behested payments (SFEC-3.610), lobbying (registrations and monthly contact reports) and contracts (SFEC-126(f)4 notifications, Supplier Contracts, Vendor Payments). Every link is a disclosed transaction with a date and, usually, an amount.",
     "Two design rules matter more than any chart. Private individuals never appear by name: their contributions are aggregated by the organization they are affiliated with. And timing is never proof: a contribution near a contract is a pattern worth checking, and the dashboard shows the base rate, the rule and the reason wherever it says something 'appears to warrant review'.",
     f"Behested payments totalled {money(beh_tot)}, {pct(beh_int / beh_tot)} from payors who were interested parties. The largest lobbying client by payments was {top_lob_name}."],
    templates=[{"id": "ov", "template": "For your filters: {flows_fmt} flows totalling {total} between {entities_fmt} entities, {years}.", "requires": {"flows_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Affiliation of individual donors to contractors uses the employer and occupation fields on Form 460, which are self-reported and inconsistent; the match rate and rules are in DATA_NOTES."},
             {"severity": "high", "text": "The Ethics Commission may already have reviewed any transaction flagged here, and contributions may have been returned; the data does not record that."}],
    sources=["network/flows.json", "network/analyses/ban_window.json", "network/analyses/behested.json"])
com("nw-graph", "Most money flows in a few thick channels: contractors to departments, PACs to committees, clients to lobbyists to departments.",
    ["Nodes are entities; edges are flows summed over the selected years and types, with thickness by amount (contacts by count). The graph prunes to the strongest edges by default and lets you search for an entity to see its neighborhood; it never shows every edge at once.",
     "Colour is entity type, never judgment. Individuals appear only as grey aggregate nodes."],
    templates=[{"id": "graph", "template": "Showing {nodes_fmt} entities and {edges_fmt} flows ({total}); {hidden_fmt} weaker flows hidden by the current pruning. Search or click a node to expand its neighborhood.", "requires": {"edges_min": 1}, "fallback": "No flows match; widen the years, lower the minimum amount or add a flow type."}],
    sources=["network/flows.json", "network/entities.json"])
com("nw-ban", f"{n_covered} of {n_contr_flows} contractor-affiliated contribution records fall inside a ban window for a covered official; about {pct(cov)} would by chance.",
    ["The contractor contribution ban (§1.126) prohibits contributions from a contractor's principals to officials who approve its contract, from proposal to 12 months after approval. The strip chart places every contractor-affiliated contribution by its days from the nearest contract approval; the shaded band is the window.",
     f"Base rate first: contracts and their windows cover a large share of the calendar for active contractors, so some contributions will fall inside windows by coincidence. Here the observed share ({pct(n_inside / n_contr_flows)} inside any window) should be read against the {pct(cov)} expected. Rows tagged 'appears to warrant review' are inside a window and to a covered official; the tag cites the rule and says why, and it is not an assertion that a violation occurred: principals may have been misattributed, contributions may have been returned, and the Ethics Commission may have reviewed the case."],
    templates=[{"id": "ban", "template": "{records_fmt} contractor-affiliated contribution records for {contracts_fmt} contracts, {years}: {inside_fmt} inside a window ({inside_share}, vs {expected_share} expected by chance); {covered_fmt} to a covered official (appears to warrant review).", "requires": {"records_min": 5}, "fallback": TF}],
    caveats=[{"severity": "high", "text": "Which officials 'approve' a contract depends on the approving body and the contract; the pipeline uses the SFEC-126(f)4 filing's list where available and a rule otherwise (Board of Supervisors for contracts above the Charter threshold, otherwise the department head's appointing officer)."},
             {"severity": "high", "text": "Windows before January 2020 were 6 months after approval, not 12; the pipeline applies the rule in force on the contribution date."}],
    sources=["network/analyses/ban_window.json"])
com("nw-behested", f"Behested payments totalled {money(beh_tot)} since 2019; {pct(beh_int / beh_tot)} came from payors who were interested parties at the time.",
    ["A behested payment is money an official asks a third party to give to a cause, disclosed by the official. They fund real services (shelters, festivals, relief) and they are also the channel that the 2022 ordinance restricted because of the Public Works scandal. The chart shows totals by official, by payor type and over time.",
     "'Interested party' here is computed: the payor had a contract, permit or lobbying matter before the official's department within 12 months. It is a flag to check, not a finding."],
    templates=[{"id": "beh", "template": "{payments_fmt} behested payments totalling {total}, {years}, at the behest of {officials_fmt} officials; {interested_share} of the dollars from interested parties; {late_fmt} filed more than 30 days after the threshold.", "requires": {"payments_min": 3}, "fallback": TF}],
    sources=["network/analyses/behested.json"])
com("nw-lobby", f"Lobbying contacts concentrate on a handful of departments and topics; {top_lob_name} paid lobbyists the most.",
    ["Contact lobbyists report every contact with a city officer, for which client and on what matter. The heat grid crosses clients with departments; the topic chart shows what the contacts were about. Lobbying is lawful and disclosed, which is exactly why it can be shown here.",
     "Payments from clients to lobbyists are the amount side; contacts have no dollar value, so the amount filter does not appear on this view."],
    templates=[{"id": "lob", "template": "{contacts_fmt} reported contacts by {lobbyists_fmt} lobbyist firms for {clients_fmt} clients, {years}; most-contacted target: {top_target} ({top_target_fmt} contacts); lobbyist payments {payments_total}.", "requires": {"contacts_min": 5}, "fallback": TF}],
    sources=["network/analyses/lobbying.json"])
com("nw-concentration", f"For the median committee, the ten largest named contributors account for {pct(med_top10)} of named-source dollars.",
    ["Concentration asks how dependent a committee is on a few sources. Individuals are aggregated, so the top-10 share counts organizations and PACs only, and the stacked bar shows how much of each committee's total came from individuals, PACs, contractor-affiliated individuals and other organizations.",
     "With a $500 limit per person, high concentration comes from PACs and independent expenditures, which the limit does not cover."],
    templates=[{"id": "conc", "template": "{committees_fmt} committees, {years}: individuals gave {ind_share} of dollars, PACs and organizations {org_share}, contractor-affiliated individuals {contr_share}.", "requires": {"committees_min": 2}, "fallback": TF}],
    sources=["network/analyses/concentration.json"])
com("nw-loop", f"{len(loop_rows)} nonprofits with city funding also appear as behested payees or payors, or as lobbying clients.",
    ["The loop: the city funds a nonprofit; an official asks a donor to give to the same nonprofit; the nonprofit hires a lobbyist to work the department that funds it. Each step is lawful and disclosed. The table lists nonprofits where at least two steps are present, so readers can check the pattern with the rules beside it.",
     "Appearing here is not improper. It is shown because behested payments to city-funded nonprofits were the mechanism in recent enforcement cases, and because the pattern is otherwise invisible across four datasets."],
    templates=[{"id": "loop", "template": "{orgs_fmt} nonprofits in the loop, {years}: {city_total} in FY2025 city payments, {beh_total} in behested payments received, {lob_total} paid to lobbyists.", "requires": {"orgs_min": 1}, "fallback": TF}],
    sources=["network/analyses/loop.json"])
com("nw-entities", "Every named entity in the network, with its type and totals.", ["Open an entity for its profile."], sources=["network/entities.json"])
# entity pages + home + search + methods commentary (light)
com("home", "Four dashboards, one visual system, every number traceable to a public dataset.", [], sources=[])
com("org", "Organization profile.", [], templates=[{"id": "org", "template": "{name} received {city_total} from {depts_fmt} departments over FY{fy0}–FY{fy1}; {city_share_sentence}"}])
com("dept", "Department scorecard.", [])
com("report", "Report page.", [])
com("official", "Official profile.", [])
com("methods", "How the numbers were made, ranked caveats, and every file.", [])
com("search", "Search results.", [])

# ---- stories (per dashboard)
w("commentary/story_np.json", {"title": "Follow the nonprofit money", "steps": [
    {"view": "np-overview", "title": "Start with the total", "text": f"The city paid {money(tot25)} to nonprofits in FY2025. This dashboard follows that money to the organizations and back to their finances."},
    {"view": "np-flows", "title": "Three departments do most of it", "text": "Public Health, HSH and HSA contract out large services. Watch the shift toward homelessness after FY2020.", "filters": {"years": [2019, 2025]}},
    {"view": "np-flows", "title": "Zoom to homelessness", "text": "Filtering to one service area shows how concentrated it is in a few organizations.", "filters": {"years": [2019, 2025], "area": ["homeless"]}},
    {"view": "np-dependency", "title": "Who depends on the city", "text": "Large and dependent organizations carry the city's operational risk. Top-right is the group to watch.", "filters": {"area": ["homeless"]}},
    {"view": "np-pay", "title": "Pay and reserves", "text": "Pay tracks size. Reserves are the accountability issue: many organizations have under a month.", "filters": {}},
    {"view": "np-growth", "title": "Contracts that doubled", "text": "Amendments are normal; a doubling is a reason to read the contract.", "filters": {}},
    {"view": "np-reviews", "title": "What the Controller found", "text": "Most reviews find nothing. The organizations rated elevated concern are listed with the report page.", "filters": {}},
]})
w("commentary/story_pf.json", {"title": "Budget vs outcomes", "steps": [
    {"view": "pf-overview", "title": "More money, fewer residents", "text": f"Real spending rose {pct(gt)} since FY2016 while population fell; per resident it rose {pct(per_res_ch)}."},
    {"view": "pf-spending", "title": "Where it went", "text": "Homelessness and health grew fastest in real terms.", "filters": {"dept": ["HSH", "DPH", "HSA"]}},
    {"view": "pf-staffing", "title": "Overtime", "text": f"{money(ot_tot)} in FY2025, mostly public safety, where minimum staffing rules and vacancies drive it.", "filters": {"group": ["protection"]}},
    {"view": "pf-outcomes", "title": "Did it work?", "text": f"Departments met {pct(met_share)} of FY2025 targets. Outcome measures are met less often than outputs.", "filters": {}},
    {"view": "pf-integrity", "title": "Are the targets honest?", "text": f"{n_dropped} measures dropped, {n_lowered} targets made easier. The met share is only as good as the measures.", "filters": {}},
    {"view": "pf-gaps", "title": "Budget vs actual", "text": "Public safety overspends (overtime); housing underspends (projects lag). Both are capacity stories.", "filters": {}},
]})
w("commentary/story_au.json", {"title": "Audit recommendations tracker", "steps": [
    {"view": "au-overview", "title": "Three recommenders", "text": "The Controller's auditors, the BLA and the Civil Grand Jury. Their leverage differs, and so do their implementation rates."},
    {"view": "au-status", "title": "Who implements", "text": "Controller recommendations are implemented most; Civil Grand Jury ones least.", "filters": {}},
    {"view": "au-time", "title": "How long", "text": f"Median {med_months:.0f} months for the ones that were implemented. The curves include the ones that were not.", "filters": {}},
    {"view": "au-agreement", "title": "Agreement predicts action", "text": "Disagreed recommendations are rarely implemented. Disagreeing is legitimate; the report page has the reasons.", "filters": {}},
    {"view": "au-repeat", "title": "Repeat findings", "text": f"{len(repeats)} recommendations repeat earlier ones. Repeats mean the fix did not stick.", "filters": {}},
    {"view": "au-open", "title": "What is still open and matters", "text": "Ranked by a published consequence score, each with its reason and a link to the report.", "filters": {}},
]})
w("commentary/story_nw.json", {"title": "Money network", "steps": [
    {"view": "nw-overview", "title": "Four disclosure systems, one map", "text": "Contributions, behested payments, lobbying and contracts. Individuals are aggregated; timing is never proof."},
    {"view": "nw-graph", "title": "The shape of the network", "text": "Thick channels, not a hairball: contractors to departments, PACs to committees, clients to lobbyists.", "filters": {"amt": 10000}},
    {"view": "nw-ban", "title": "The ban window, with a base rate", "text": f"{pct(cov)} of contributions would fall in a window by chance; {n_covered} records to covered officials appear to warrant review.", "filters": {}},
    {"view": "nw-behested", "title": "Behested payments", "text": f"{money(beh_tot)} since 2019. Interested-party payors are flagged to check, not to accuse.", "filters": {}},
    {"view": "nw-lobby", "title": "Who lobbies whom", "text": "Contacts by client and department; topics show what they were about.", "filters": {}},
    {"view": "nw-concentration", "title": "Concentration", "text": f"For the median committee the top ten named sources give {pct(med_top10)} of named dollars.", "filters": {}},
    {"view": "nw-loop", "title": "The nonprofit loop", "text": f"{len(loop_rows)} city-funded nonprofits also receive behested payments or hire lobbyists. Lawful, disclosed, and worth seeing in one place.", "filters": {}},
]})

# ---- site meta (cross-module)
w("site.json", {"sample": True, "generated_at": GENERATED, "modules": {"nonprofits": {"as_of": AS_OF}, "performance": {"as_of": AS_OF}, "audits": {"as_of": "2026-08-31"}, "network": {"as_of": "2026-09-15"}},
                "departments": DEPT_LIST, "groups": [{"id": a, "label": l} for a, l in GROUPS]})

# ---- write files, sizes, bundle
for path, obj in list(OUT.items()):
    full = os.path.join(HERE, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as fh: json.dump(obj, fh, separators=(",", ":"), ensure_ascii=False)
for mod in ("nonprofits", "performance", "audits", "network"):
    files = {p: {"bytes": os.path.getsize(os.path.join(HERE, p))} for p in OUT if p.startswith(mod + "/")}
    OUT[f"{mod}/meta.json"]["files"] = files
    with open(os.path.join(HERE, f"{mod}/meta.json"), "w") as fh: json.dump(OUT[f"{mod}/meta.json"], fh, separators=(",", ":"), ensure_ascii=False)
with open(os.path.join(HERE, "bundle.js"), "w") as fh:
    fh.write("window.SFCM_SAMPLE_BUNDLE = " + json.dumps(OUT, separators=(",", ":"), ensure_ascii=False) + ";\n")
total = sum(os.path.getsize(os.path.join(HERE, p)) for p in OUT)
print(f"wrote {len(OUT)} files, {total/1e6:.2f} MB; bundle {os.path.getsize(os.path.join(HERE, 'bundle.js'))/1e6:.2f} MB")
print("orgs", len(orgs), "pay cells", len(pay_cells), "contracts", len(contracts), "990", len(fin), "findings", len(findings))
print("spend", len(spend_cells), "measures", len(measures), "values", len(mvalues), "reports", len(reports), "recs", len(recs), "ents", len(ents), "flows", len(flows))
print("ban: records", n_contr_flows, "inside", n_inside, "covered", n_covered, "expected", cov)
