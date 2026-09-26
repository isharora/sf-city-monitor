"""Build data/reviews/partials/group_f.json: Controller nonprofit monitoring program reports, policies,
corrective-action designations (hand-transcribed from report text, quotes verified), and per-contractor
annual fiscal/compliance monitoring results (parsed by reviews_parse_monitoring.py)."""
import json, re, pathlib, collections
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
ACC = "2026-09-26"
SRC = {l.split("\t")[0]: l.split("\t")[2].strip() for l in (base / "pdf_sources.tsv").read_text().splitlines()[1:]}
U = {"FY19": SRC["monitoring_FY19_annual_report.pdf"], "FY22": SRC["monitoring_FY22_annual_report.pdf"], "FY23": SRC["monitoring_FY23_annual_report.pdf"],
     "FY24": SRC["monitoring_FY24_annual_report.pdf"], "FY25": SRC["monitoring_FY25_annual_report.pdf"]}
RID = {fy: f"ctrl-monitoring-{fy.lower()}-annual-report" for fy in U}
FYL = {"FY19": "FY2018-19", "FY22": "FY2021-22", "FY23": "FY2022-23", "FY24": "FY2023-24", "FY25": "FY2024-25"}
DATA = {"FY22": "https://sf.gov/file/citywide-nonprofit-monitoring-and-capacity-building-program-fy21-22-dataset",
        "FY23": "https://www.sf.gov/file/citywide-nonprofit-monitoring-and-capacity-building-program-fy23-dataset",
        "FY24": "https://data.sf.gov/d/3v2z-djjd", "FY25": "https://data.sf.gov/d/7yeh-dyn4"}

reviews = [
 dict(id=RID["FY19"], title="Citywide Nonprofit Monitoring and Capacity Building Program FY19 Annual Report", publisher="San Francisco Office of the Controller", date="2019", url=U["FY19"], type="controller_monitoring",
      summary="FY2018-19 results of the Controller's joint fiscal and compliance monitoring of city-funded nonprofits, the last full cycle before the COVID-19 pause (no FY20-FY21 annual reports were found). It names two nonprofits placed on elevated concern and lists contractors with no findings (Appendix B) and with repeat findings FY18-FY19 (Appendix D). A companion FY18-19 dataset is listed on the Controller's report site (OpenBook id 2760)."),
 dict(id=RID["FY22"], title="Citywide Nonprofit Monitoring and Capacity Building Program FY22 Annual Report", publisher="San Francisco Office of the Controller", date="2022-12", url=U["FY22"], type="controller_monitoring",
      summary="Annual report of the Controller's joint fiscal and compliance monitoring of city-funded nonprofits for FY2021-22, the first full cycle after the COVID pause. Of 192 contractors in the pool, 155 had no findings (including 39 waivers), 12 resolved initial findings, 9 had unresolved findings at final status and 16 were not completed. It names two nonprofits placed on elevated concern and two on red flag status. Per-contractor results are in Appendix E and a companion dataset (" + DATA["FY22"] + ")."),
 dict(id=RID["FY23"], title="Citywide Nonprofit Monitoring and Capacity Building Program FY23 Annual Report", publisher="San Francisco Office of the Controller", date="2023-12", url=U["FY23"], type="controller_monitoring",
      summary="FY2022-23 results of the Controller's joint fiscal and compliance monitoring of about 197 city-funded nonprofits. Appendix D lists each contractor's final status; 46 had findings not yet in conformance at final status. The report names four nonprofits on elevated concern and reports no new red flag designations. Standard-level data: " + DATA["FY23"] + "."),
 dict(id=RID["FY24"], title="Citywide Nonprofit Monitoring and Capacity Building Program FY24 Annual Report", publisher="San Francisco Office of the Controller", date="2024-12", url=U["FY24"], type="controller_monitoring",
      summary="FY2023-24 results for 211 contractors in the fiscal monitoring pool (12 waivers). Appendix B lists 60 contractors with findings not in conformance at final status (the narrative says 61). It names eight nonprofits designated Tier 2 and three designated Tier 3 under the Citywide Corrective Action Policy. Standard-level data: " + DATA["FY24"] + "."),
 dict(id=RID["FY25"], title="Citywide Nonprofit Monitoring and Capacity Building Program FY25 Annual Report", publisher="San Francisco Office of the Controller", date="2025-12", url=U["FY25"], type="controller_monitoring",
      summary="FY2024-25 results for 206 contractors in the fiscal monitoring pool: 129 no findings, 20 waivers, 49 with findings not in conformance, and 8 where City monitors did not finish on time. Appendix A gives fiscal and compliance finding counts per contractor. It names 14 nonprofits designated Tier 2 and 2 designated Tier 3. Standard-level data: " + DATA["FY25"] + "."),
 dict(id="policy-2025-corrective-action", title="Citywide Nonprofit Corrective Action Policy (Version: November 2025)", publisher="San Francisco Office of the Controller", date="2025-11-12", url=SRC["corrective_action_policy.pdf"], type="city_policy",
      summary="Current citywide policy for escalating and responding to serious fiscal or programmatic problems at city-funded nonprofits, revised after 2024 Board of Supervisors legislation. It sets three tiers: Tier 1 (voluntary technical assistance, not public), Tier 2 (serious concerns, mandatory technical assistance, publicly reported) and Tier 3 (severe concerns, may be considered in funding decisions, publicly reported; de-funding is the ultimate sanction). The Controller currently publishes Tier 2 and 3 designations in the Fiscal Monitoring Program annual report."),
 dict(id="policy-2014-corrective-action", title="City and County of San Francisco Nonprofit Contractor Corrective Action Policy (2014 version)", publisher="San Francisco Office of the Controller", date="2014", url=SRC["corrective_action_policy_2024.pdf"], type="city_policy",
      summary="Earlier version of the corrective action policy that defined 'elevated concern' and 'red flag' status for nonprofit contractors. It was used for the FY22 and FY23 designations. sf.gov labels this link '2024 Corrective Action Policy' but the file is the 2014 policy signed under Controller Ben Rosenfield."),
 dict(id="policy-2024-contract-monitoring", title="Nonprofit Contract Monitoring Policy", publisher="San Francisco Office of the Controller", date="2024-12-09", url=SRC["contract_monitoring_policy_2024.pdf"], type="city_policy",
      summary="Policy issued in December 2024 setting citywide requirements for how departments monitor nonprofit contract performance (programmatic monitoring), following Ordinance 55-24. It complements the fiscal monitoring program and the corrective action policy. It contains no organization-level findings."),
]

# Corrective action designations, transcribed from report text. quote verified against page text below.
D = []
def des(org, aliases, fy, page, ftype, finding, quote, status):
    D.append(dict(org_name=org, org_name_aliases=aliases, ein=None, review_id=RID[fy], finding_type=ftype, finding=finding, quote=quote, page=page, status=status, url=U[fy]))
q22ec = "Based on FY22 monitoring activities and events that identified potential fiscal management and organizational concerns, the Controller's Office and City departments placed the following contractors on elevated concern status"
des("Bayview Hunters Point Foundation for Community Improvement", ["Bayview Hunters Point Foundation", "BVHPF"], "FY22", 16, "elevated concern",
    "The Controller's Office and City departments placed the organization on elevated concern status based on FY22 monitoring activities and events that identified potential fiscal management and organizational concerns. Elevated concern meant developing an action plan with the City and receiving technical assistance.", q22ec,
    "Retained on elevated concern in FY23; escalated to Tier 3 in FY24; sustained on Tier 3 in FY25 (see later reports).")
des("HomeRise", ["Community Housing Partnership", "HomeRise (formerly Community Housing Partnership)"], "FY22", 16, "elevated concern",
    "Placed on elevated concern status based on FY22 monitoring activities and events that identified potential fiscal management and organizational concerns.", q22ec,
    "Retained on elevated concern in FY23; designated Tier 3 in FY24; lowered to Tier 2 in FY25.")
q22rf = "Based on FY22 monitoring activities and external audits, the Controller's Office and City departments placed the following contractors on red flag status"
des("PRC and Baker Places, Inc.", ["PRC", "Positive Resource Center", "Baker Places", "PRC/Baker Places"], "FY22", 16, "corrective action",
    "Placed on red flag status (for agencies at imminent risk of being unable to perform services per their contract) based on FY22 monitoring activities and external audits. PRC and Baker Places were merging and were monitored together.", q22rf,
    "FY23 report: the red flag contractor that stayed in business developed a sustainability plan, 'notably improved its financial indicators,' and had red flag status removed; it was moved to elevated concern. By comparing FY23 and FY24 lists, PRC/Baker Places appears to be the FY23 elevated-concern nonprofit whose designation was removed in FY24 (the FY24 report does not name it).")
des("United Council of Human Services", ["UCHS"], "FY22", 16, "corrective action",
    "Placed on red flag status (imminent risk of being unable to perform services per contract) based on FY22 monitoring activities and external audits.", q22rf,
    "FY23 report states that one of the two FY22 red flag contractors 'is no longer doing business with the City due to noncompliance and delinquent nonprofit status with the California Office of Attorney General'; since the other (PRC/Baker Places) moved to elevated concern, this appears to be UCHS (the report does not name it).")
q23 = "The Controller's Office also added the following contractors on Elevated Concern due to monitoring results, issues identified by funding departments, and the need for enhanced coordination by City departments to support these contractors"
des("African American Art and Culture Complex", ["AAACC"], "FY23", 17, "elevated concern",
    "Added to elevated concern in FY23 due to monitoring results, issues identified by funding departments, and the need for enhanced coordination. Figure 14 lists its unresolved findings in audited financial statements, board oversight, public access and subcontracts.", q23,
    "Designated Tier 2 in FY24; not on the FY25 Tier 2/3 lists; receiving Controller coaching ('In-progress') in FY25.")
des("PRC and Baker Places, Inc.", ["PRC", "Positive Resource Center", "Baker Places"], "FY23", 17, "elevated concern",
    "Moved from red flag to elevated concern in FY23 after improving its financial indicators; most common unresolved findings among FY23 elevated-concern nonprofits were late audited financial statements.", q23,
    "Controller coaching for PRC/Baker Places listed as 'Complete' in FY24; not on FY24 or FY25 tier lists.")
q23r = "Based on FY23 monitoring results and activities, the Controller's Office retained the following contractors on elevated concern status"
des("Bayview Hunters Point Foundation for Community Improvement", ["Bayview Hunters Point Foundation", "BVHPF"], "FY23", 17, "elevated concern",
    "Retained on elevated concern in FY23. Figure 14 shows unresolved findings on audited financial statements.", q23r, "Designated Tier 3 in FY24.")
des("HomeRise", ["Community Housing Partnership"], "FY23", 17, "elevated concern",
    "Retained on elevated concern in FY23. Figure 14 shows an unresolved invoice finding.", q23r, "Designated Tier 3 in FY24.")
q24t2 = "Based on FY24 monitoring findings and contract management issues identified by funding departments, the Controller's Office designated the 8 nonprofits below as Tier 2."
t2_24 = [("African American Art and Culture Complex", ["AAACC"]), ("Centers for Equity and Success (dba Success Centers)", ["Success Centers", "Centers for Equity and Success, Inc.", "Success Center SF"]),
         ("Friendship House Association of American Indians", ["Friendship House"]), ("Homies Organizing the Mission to Empower Youth (HOMEY)", ["HOMEY"]),
         ("Lavender Youth Recreation and Information Center (LYRIC)", ["LYRIC"]), ("Livable City", []), ("Renaissance Parents of Success", []),
         ("Samoan Community Development Center, Inc.", ["Samoan Community Development Center"])]
nxt = {"Livable City": "Sustained on Tier 2 in FY25.", "Lavender Youth Recreation and Information Center (LYRIC)": "Sustained on Tier 2 in FY25.",
       "Samoan Community Development Center, Inc.": "Sustained on Tier 2 in FY25.", "Homies Organizing the Mission to Empower Youth (HOMEY)": "Escalated to Tier 3 (FY25 report).",
       "African American Art and Culture Complex": "Not listed in FY25 Tier 2 or Tier 3 designations.", "Centers for Equity and Success (dba Success Centers)": "Not listed in FY25 Tier 2 or Tier 3 designations; receiving coaching in FY25.",
       "Friendship House Association of American Indians": "Not listed in FY25 Tier 2 or Tier 3 designations; completed coaching in FY25.", "Renaissance Parents of Success": "Not listed in FY25 Tier 2 or Tier 3 designations; completed coaching in FY25."}
for o, a in t2_24:
    des(o, a, "FY24", 17, "corrective action",
        "Designated Tier 2 under the Citywide Corrective Action Policy (formerly 'elevated concern') based on FY24 monitoring findings and contract management issues identified by funding departments. The report says several Tier 2 nonprofits were missing audited financial statements, while others had wider concerns with budget and cost allocation, invoicing, and payroll tax payments; it does not say which applied to each nonprofit.",
        q24t2, nxt[o])
q24t3 = "The Controller's Office designated three nonprofits to Tier 3 due to serious financial concerns that have not been adequately addressed, and in one case, due to a suspension order by the City Attorney's Office."
des("Bayview Hunters Point Foundation for Community Improvement", ["Bayview Hunters Point Foundation", "BVHPF"], "FY24", 18, "corrective action",
    "Designated Tier 3 (serious risk to public funds and client services) due to serious financial concerns not adequately addressed.", q24t3, "Sustained on Tier 3 in FY25.")
des("HomeRise", ["Community Housing Partnership"], "FY24", 18, "corrective action",
    "Designated Tier 3 due to serious financial concerns not adequately addressed.", q24t3, "Lowered to Tier 2 in FY25.")
des("Providence Foundation", ["Providence Foundation of San Francisco"], "FY24", 18, "corrective action",
    "Designated Tier 3. The report says one of the three Tier 3 designations was due to a suspension order by the City Attorney's Office; the Controller paused technical assistance with Providence Foundation 'while investigation into debarment proceedings occurred' (Figure 14 note).", q24t3,
    "Not listed in FY25 tier designations; its FY25 monitoring status was findings not in conformance (see FY25 appendix entry).")
q25t2 = "Based on FY25 monitoring findings and contract management issues identified by funding departments, the Controller's Office designated the 14 nonprofits below to Tier 2."
t2_25 = [("AsianWeek Foundation", [], "Newly designated"), ("Bernal Heights Neighborhood Center", [], "Newly designated"), ("Conard House", ["Conard House Inc"], "Newly designated"),
         ("HomeRise", ["Community Housing Partnership"], "Lowered from Tier 3 in FY24"), ("Kultivate Labs", [], "Newly designated"), ("Livable City", [], "Sustained on Tier 2 from FY24"),
         ("Lavender Youth Recreation and Information Center (LYRIC)", ["LYRIC"], "Sustained on Tier 2 from FY24"), ("Mid-Market Foundation", ["Mid Market Foundation"], "Newly designated"),
         ("Mission Action", [], "Newly designated"), ("Reality House West", [], "Newly designated"), ("Samoan Community Development Center, Inc.", ["Samoan Community Development Center"], "Sustained on Tier 2 from FY24"),
         ("San Francisco Pre-Trial Diversion Program", ["SF Pretrial Diversion Project"], "Newly designated"), ("San Francisco Public Health Foundation", [], "Newly designated"), ("Young Community Developers", ["YCD"], "Newly designated")]
for o, a, note in t2_25:
    des(o, a, "FY25", 29, "corrective action",
        f"Designated Tier 2 under the Citywide Corrective Action Policy ({note}, per Figure 24). The report says several FY25 Tier 2 nonprofits were missing a current audited financial statement, while others had wider concerns with invoicing and payroll practices, subcontractor monitoring, or a material weakness or going-concern note in the audit; it does not say which applied to each nonprofit.",
        q25t2, f"Figure 24 note: {note}. Status after FY25 not yet published.")
q25t3 = "The Controller's Office designated two nonprofits to Tier 3 due to severe financial concerns that were not adequately addressed in FY25."
des("Bayview Hunters Point Foundation for Community Improvement", ["Bayview Hunters Point Foundation", "BVHPF"], "FY25", 30, "corrective action",
    "Designated Tier 3 due to severe financial concerns not adequately addressed in FY25 (Figure 25 note: 'Sustained on Tier 3 from FY23').", q25t3, "Completed Controller coaching in FY25. Status after FY25 not yet published.")
des("Homies Organizing the Mission to Empower Youth - HOMEY", ["HOMEY", "Homies Organizing the Mission to Empower Youth"], "FY25", 30, "corrective action",
    "Designated Tier 3 due to severe financial concerns not adequately addressed in FY25 (Figure 25 note: 'Escalated to Tier 3 from Tier 2 in FY24').", q25t3, "Coaching in progress in FY25. Status after FY25 not yet published.")

q19 = "Based on FY19 monitoring results, the Controller's Office and City departments placed the following contractors on elevated concern status."
des("African American Arts and Cultural Complex", ["African American Art and Culture Complex", "AAACC"], "FY19", 18, "elevated concern",
    "Placed on elevated concern status based on FY19 monitoring results; elevated concern meant mandatory technical assistance and an action plan. Appendix D lists repeat FY18-FY19 findings on audited financial statements, fiscal policies and internal controls, invoice documentation and payroll timesheets.", q19,
    "Again placed on elevated concern in FY23 and Tier 2 in FY24 (see later reports).")
des("Westside Community Services", [], "FY19", 18, "elevated concern",
    "Placed on elevated concern status based on FY19 monitoring results; elevated concern meant mandatory technical assistance and an action plan.", q19,
    "No findings (or a waiver) at final status in FY22-FY25 monitoring per later appendices (see those entries); completed Controller coaching in FY24.")

# per-contractor monitoring results
S = json.load(open(base / "monitoring_data" / "monitoring_status.json"))
def nm(n): return re.sub(r"[^a-z0-9]", "", n.lower().replace("*", ""))
nextfy = {"FY22": "FY23", "FY23": "FY24", "FY24": "FY25"}
idx = {fy: {nm(r["name"]): r for r in S[fy]} for fy in S}
MON = []
for fy, rows in S.items():
    for r in rows:
        st = r["status"]; name = r["name"].replace("*", "").strip()
        cats = collections.Counter(c for c, _ in r["unresolved"])
        catstr = "; ".join(f"{c} ({n})" for c, n in cats.most_common())
        typ = r["type"]
        if "Not in" in st:
            ftype = "fiscal monitoring finding"
            counts = f" ({r['fis']} fiscal and {r['comp']} compliance findings)" if fy == "FY25" else ""
            f = (f"In the Controller's {FYL[fy]} citywide fiscal and compliance monitoring ({typ} monitoring), the nonprofit still had findings not in conformance with City standards at final status{counts}. "
                 f"Unresolved required standards by category, per the published dataset: {catstr or 'not listed'}. The monitoring checks compliance with City fiscal and administrative standards (e.g., audits, budgets, cost allocation, board oversight); a finding does not by itself indicate misuse of funds.")
        elif st in ("Complete (No Findings)", "No Findings"):
            ftype = "no findings/cleared"; f = f"In the Controller's {FYL[fy]} citywide fiscal and compliance monitoring ({typ} monitoring), the nonprofit had no findings at final status."
        elif st == "Findings In Conformance":
            ftype = "no findings/cleared"; f = f"In the Controller's {FYL[fy]} citywide fiscal and compliance monitoring ({typ} monitoring), the nonprofit had initial findings that it brought into conformance by final status."
        elif st == "Waiver":
            ftype = "no findings/cleared"; f = f"In {FYL[fy]}, the nonprofit received a waiver from fiscal and compliance monitoring (the program grants waivers for strong prior performance)."
        else:
            ftype = "monitoring incomplete"
            f = (f"In {FYL[fy]}, the monitoring of this nonprofit was not completed by City monitors by the program deadline, so no final result was reported. This is not a finding against the nonprofit." if fy == "FY25"
                 else f"In {FYL[fy]}, the report lists this nonprofit's monitoring as 'Not Complete'; the report excludes incomplete monitorings from results and does not state a finding against the nonprofit.")
        if r["late"]: f += " (Asterisk in the report: City monitors completed this monitoring after the due date.)" if fy == "FY25" else ""
        status = None
        if name.startswith("St. James Infirmary") and fy == "FY23":
            status = "Report footnote: St. James Infirmary informed the City it planned to close all programs and transfer services; it was not required to bring findings into conformance."
        if fy in nextfy:
            n2 = idx[nextfy[fy]].get(nm(r["name"]))
            nxtst = f"{nextfy[fy]} final status: {n2['status']}" if n2 else f"Not listed in the {nextfy[fy]} monitoring pool"
            status = (status + " " if status else "") + nxtst + "."
        if fy == "FY25" and "Not in" in st:
            status = f"Prior year (FY24) status per report: {r['prior']}. FY26 results not yet published."
        if fy in ("FY24", "FY25") and ftype == "no findings/cleared" and st == "No Findings":
            pass
        MON.append(dict(org_name=name, org_name_aliases=[], ein=None, review_id=RID[fy], finding_type=ftype, finding=f, quote=r["raw"].replace("*", "").strip() if len(r["raw"].split()) <= 40 else " ".join(r["raw"].split()[:40]), page=r["page"], status=status, url=U[fy]))

# verify quotes
def norm(s): return re.sub(r"[^a-z0-9]", "", s.lower().replace("’", "'"))
T = {fy: {int(a): b for a, b in zip(*[iter(re.split(r"=== PAGE (\d+) ===", (base / "text" / f"monitoring_{fy}_annual_report.txt").read_text())[1:])] * 2)} for fy in U}
rid2fy = {v: k for k, v in RID.items()}
bad = 0
for e in D + MON:
    pg = T[rid2fy[e["review_id"]]]
    txt = pg.get(e["page"], "") + pg.get(e["page"] + 1, "")
    if norm(e["quote"]) not in norm(txt): bad += 1; print("QUOTE FAIL", e["org_name"], e["review_id"], e["quote"][:80])
json.dump({"reviews": reviews, "org_findings": D + MON}, open(base / "partials" / "group_f.json", "w"), indent=1, ensure_ascii=False)
print("reviews", len(reviews), "designations", len(D), "monitoring rows", len(MON), "quote failures", bad)
print(collections.Counter(e["finding_type"] for e in MON))
