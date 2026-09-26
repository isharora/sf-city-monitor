"""Group D: Budget and Legislative Analyst (BLA) + Civil Grand Jury (CGJ) review documents and org findings.
Writes data/reviews/partials/group_d.json. Every quote is verified against the extracted PDF text
(data/reviews/text/<pdf>.txt, per-page) with whitespace/ligature-insensitive matching; the script fails on mismatch.
Page numbers are 1-based PDF page indexes (not printed page numbers)."""
import json, re, pathlib, sys
BASE = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
ACC = "2026-09-26"

def norm(s):
    s = s.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s)

def pages(txt):
    t = (BASE / "text" / txt).read_text()
    parts = re.split(r"=== PAGE (\d+) ===", t)
    return {int(parts[i]): norm(parts[i + 1]) for i in range(1, len(parts), 2)}

BLA = "https://sfbos.archive.sf.gov/sites/default/files/"
REVIEWS = [
 dict(id="bla_2020_hsh_performance_audit", title="Performance Audit of the Department of Homelessness & Supportive Housing",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2020-08-06",
      url=BLA + "BLA_Performance_Audit_Homelessness_Supportive_Housing_08062020.pdf", type="bla", pdf="bla_hsh_performance_audit_2020",
      summary="Performance audit of HSH requested by the Board of Supervisors. It found HSH did not sufficiently monitor its nonprofit provider contracts to ensure service goals were met, had no documented program-monitoring policies, and projected $26.5 million in FY 2019-20 contract underspending. The report does not name individual providers; HSH agreed with all recommendations."),
 dict(id="bla_2023_street_teams_audit", title="Performance Audit of San Francisco Street Teams",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2023-11-07",
      url=BLA + "110723%20Performance%20Audit%20of%20San%20Francisco%20Street%20Teams.pdf", type="bla", pdf="bla_street_teams_2023",
      summary="Performance audit of the City's 11 street teams (SCRT, SORT, SFHOT, etc.), which rely on nine contracts with six organizations. It found departments, especially DPH, were not adequately overseeing contractors: some had no formal monitoring reports after two and a half years, one corrective action plan was dropped without follow-up, and one provider worked more than 18 months without an executed contract. Named providers include Heluna Health, HealthRight 360, RAMS, Felton Institute, Harm Reduction Therapy Center and Urban Alchemy."),
 dict(id="bla_2024_psh_performance_audit", title="Performance Audit of Permanent Supportive Housing Funds Administered by the Department of Homelessness and Supportive Housing",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2024-05-03",
      url=BLA + "050324_PA_of_Permanent_Supportive_Housing_Funds_Admin_by_DH_SH.pdf", type="bla", pdf="bla_psh_performance_audit_2024",
      summary="Performance audit of HSH's permanent supportive housing (PSH) funds, which flow mostly through about 130 nonprofit contracts worth nearly $280 million in FY 2023. It found PSH vacancies averaged 10.2 percent against a 7 percent goal, about $73 million (40 percent) of FY 2021-22 PSH grant budgets went unspent, performance metrics were not consistently used in contracts, and HSH lacked a standard corrective-action procedure. Providers are not named; HSH agreed or partially agreed with 15 of 17 recommendations."),
 dict(id="bla_2025_contract_oversight", title="General Fund Vacancies, Contract Oversight, & Functions (Policy Analysis Report to Supervisor Chan)",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2025-01-13",
      url=BLA + "Policy_Analysis.GF_Vacancies.Contract_Oversight.Dept_Restructures.Final_.01.13.25.pdf", type="bla", pdf="bla_gf_vacancies_contract_oversight_2025",
      summary="Policy analysis that, among other things, reviewed 81 DPH, HSH and HSA contracts with community-based organizations (over $400 million in FY 2022-23 spending). It reports that about 30 percent of nonprofits in the Controller's FY 2023-24 monitoring pool had not come into conformance, describes Baker Places program closures after financial insolvency, and describes the City's move to debar Providence Foundation over allegations of falsified invoices. Twelve reviewed organizations were not in conformance in FY 2023-24, but most are not named."),
 dict(id="bla_2020_sheriff_cbo_contracts", title="Review of Sheriff Department Community-Based Programs and Contracts",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2020-12-14",
      url=BLA + "BLA_Policy_Report_Sheriff_%20Contracts_121420.pdf", type="bla", pdf="bla_sheriff_cbo_contracts_2020",
      summary="Policy analysis of the Sheriff's $12.1 million (FY 2020-21) in community-based program contracts, including $5.8 million for pretrial services by the nonprofit SF Pretrial Diversion Project. It raises policy questions about pretrial electronic monitoring and coordination of reentry services with Adult Probation; it makes no findings of provider noncompliance."),
 dict(id="bla_2022_oewd_community_grants", title="Performance Audit of Small Business Programs and Community Grants Managed by the Office of Economic and Workforce Development and the Office of Small Business",
      publisher="San Francisco Board of Supervisors, Budget and Legislative Analyst", date="2022-06-14",
      url=BLA + "061422%20PA%20of%20OEWD%20%26%20the%20Office%20of%20Small%20Business.pdf", type="bla", pdf="bla_oewd_community_grants_2022",
      summary="Performance audit of OEWD's community grants and small business programs. It found chronic delays in grant procurement that leave grantees unable to be paid on time, and a lack of documented guidance and training for monitoring grant agreements. Findings are directed at the department, not individual grantees."),
 dict(id="cgj_2022_hsh_progress_report", title="A Progress Report about the San Francisco Department of Homelessness and Supportive Housing",
      publisher="San Francisco Civil Grand Jury (2021-2022)", date="2022-06-30",
      url="https://civilgrandjury.archive.sf.gov/2021_2022/2022%20CGJ%20Report_A%20Progress%20Report%20about%20the%20San%20Francisco%20Department%20of%20Homelessness%20and%20Supportive%20Housing.pdf",
      type="civil_grand_jury", pdf="cgj_hsh_progress_report_2022",
      summary="Follow-up to the 2020 BLA audit of HSH. The Jury found HSH had strengthened its administrative infrastructure and resolved severe staffing shortages, but major issues remained in data management, communications, and department oversight. It does not make findings about individual nonprofits."),
 dict(id="cgj_2023_performance_bullseye", title="Hitting the Performance Bullseye: Contracting for Better Outcomes in Homelessness Services",
      publisher="San Francisco Civil Grand Jury (2022-2023)", date="2023-06-28",
      url="https://media.api.sf.gov/documents/2023_CGJ_Report_Hitting_the_Performance_Bullseye_-_Contracting_for_Better_Outc_h8lGNXC.pdf",
      type="civil_grand_jury", pdf="cgj_performance_bullseye_2023",
      summary="Investigation of HSH contracting with community-based organizations (over 300 active agreements, more than $2 billion in original value as of May 2023). The Jury found results-based outcome measures were inconsistently used in contracts and that on-site program monitoring was limited (17 confirmed on-site audits among 49 contractors in FY22). An appendix reproduces a FY 2021-22 monitoring status table for HSH contractors; HSH responded that the table appears to reflect the citywide joint fiscal monitoring process rather than HSH program monitoring."),
 dict(id="cgj_2023_performance_bullseye_responses", title="Hitting the Performance Bullseye - Consolidated Response (Office of the Mayor, City Administrator, HSH, Controller)",
      publisher="City and County of San Francisco (responses to the Civil Grand Jury)", date="2023-08-25",
      url="https://media.api.sf.gov/documents/Homelessness_Report_Response_MYR_082523.pdf", type="civil_grand_jury", pdf="cgj_performance_bullseye_2023_responses",
      summary="City responses to the 2023 Civil Grand Jury homelessness contracting report. The City agreed that contracts had been inconsistent on outcome measures and said standardized metrics would be phased in as agreements are reprocured or amended, while disagreeing in part with the monitoring finding and wholly with the scorecard finding. HSH said the report's contractor status table appears to reflect joint fiscal monitoring, not HSH program monitoring."),
 dict(id="cgj_2025_capacity_to_serve", title="Capacity To Serve: Setting Social Services Nonprofits Up for Success",
      publisher="San Francisco Civil Grand Jury (2024-2025)", date="2025-06-03",
      url="https://media.api.sf.gov/documents/2025_CGJ_Report_Capacity_To_Serve_Setting_Social_Services_Nonprofits_Up_for_Su_kqii3f0.pdf",
      type="civil_grand_jury", pdf="cgj_capacity_to_serve_2025",
      summary="Investigation of how the City awards and monitors more than $1 billion a year in social services grants to nonprofits. The Jury found the City does not proactively build nonprofit capacity, procurement is slow and complex, and monitoring 'doesn't lead to timely corrective action.' Appendix A details three examples drawn from public records and news: Baker Places, Providence Foundation and HomeRise."),
 dict(id="cgj_2025_capacity_to_serve_responses", title="Capacity To Serve - Consolidated Responses (Office of the Mayor, City Administrator, Controller)",
      publisher="City and County of San Francisco (responses to the Civil Grand Jury)", date="2025-08-04",
      url="https://media.api.sf.gov/documents/Capacity_To_Serve_Report_Response_MYR_080425_Consolidated.pdf", type="civil_grand_jury", pdf="cgj_capacity_to_serve_2025_responses",
      summary="Consolidated City responses to the 2025 Civil Grand Jury report on social services nonprofits, covering findings on capacity building, procurement delays, staff tooling, and monitoring follow-through."),
 dict(id="cgj_2026_at_scale_at_risk", title="At Scale, At Risk: Upgrading Data and Oversight to Improve Homelessness Services",
      publisher="San Francisco Civil Grand Jury (2025-2026)", date="2026-06-23",
      url="https://media.api.sf.gov/documents/2026_CGJ_Rpt_At_Scale_At_Risk_-_Upgrading_Data_and_Oversight_to_Improve_Homele_woZ0ksh.pdf",
      type="civil_grand_jury", pdf="cgj_at_scale_at_risk_2026",
      summary="Investigation of oversight of HSH, which administers nearly $500 million a year in nonprofit contracts. The Jury found critical incident reports are not analyzed in aggregate, contract metrics omit client safety, and the Homelessness Oversight Commission underuses its authority. Two case studies, which the Jury says are 'rather than findings of fault', examine a death at HomeRise's Jazzie Collins Apartments and Urban Alchemy's 711 Post Street shelter."),
 dict(id="cgj_2026_at_scale_at_risk_responses", title="At Scale, At Risk - Consolidated Responses (Office of the Mayor and HSH)",
      publisher="City and County of San Francisco (responses to the Civil Grand Jury)", date="2026-08-24",
      url="https://media.api.sf.gov/documents/At_Scale_At_Risk_Report_Responses_MYR_082426_kEG3pjC.pdf", type="civil_grand_jury", pdf="cgj_at_scale_at_risk_2026_responses",
      summary="Responses from the Mayor's Office and HSH to the 2026 Civil Grand Jury homelessness oversight report. The City partially disagreed that HSH has not used critical incident reports effectively, said some recommendations were already implemented or would be (outlier benchmarking, data triggers), and declined others, including returning contract renewals to the Homelessness Oversight Commission's consent calendar."),
]

def F(org, aliases, rid, ftype, finding, quote, page, status=None, ein=None):
    return dict(org_name=org, org_name_aliases=aliases, ein=ein, review_id=rid, finding_type=ftype,
                finding=finding, quote=quote, page=page, status=status)

S = "bla_2023_street_teams_audit"; C = "bla_2025_contract_oversight"; B = "cgj_2023_performance_bullseye"
K = "cgj_2025_capacity_to_serve"; A = "cgj_2026_at_scale_at_risk"
FIND = [
 F("Heluna Health", ["Heluna"], S, "contract performance finding",
   "HSH's Homeless Outreach Team (SFHOT) contractor met or exceeded its contracted units of service in FY 2021-22 but did not meet the contract requirement to keep staffing above 90 percent. Between January 2021 and March 2023 it met the 90 percent level in 6 of 9 quarters, hiring 34 FTEs while losing 44.",
   "met or exceeded its contracted units of service for FY 2021 -22 but did not meet its contractual requirement to maintain staffing levels above 90 percent", 90,
   "HSH's response (Oct 2023) said staffing is the primary agenda of biweekly meetings with Heluna Health, that staffing was 86% in June 2023, and that it requested written short- and long-term hiring plans by November 1, 2023."),
 F("HealthRight 360", ["HealthRIGHT 360", "HR360"], S, "oversight gap (city department)",
   "DPH had not conducted any formal performance evaluation of HealthRight 360's Street Crisis Response Team contract (not-to-exceed $8,009,837, begun November 2020) as of April 2023. After a March 2023 reconfiguration changed their role, all 14 HealthRight 360 clinicians quit; DPH staff said the organization relinquished the contract in 2023 due to an inability to hire. The finding is about DPH's oversight, not misconduct by the provider.",
   "as of April 2023 all 14 of the HealthRight 360 clinicians quit rather than switch to post -crisis outreach", 88,
   "The BLA says DPH later provided unsigned preliminary FY 2021-22 monitoring reports, which the auditors could not review in time."),
 F("Richmond Area Multi-Services", ["RAMS", "Richmond Area Multi-Services Inc"], S, "oversight gap (city department)",
   "DPH amended RAMS's SCRT peer counselor contract on December 1, 2022, adding 18 months and raising the not-to-exceed amount by over $4.7 million (88 percent), from $5,313,977 to $9,999,998, without a formal performance evaluation. The BLA notes the new amount is $2 under the $10 million level that would require Board of Supervisors approval. The audit reports this as unusual and a DPH oversight gap; it does not allege wrongdoing by RAMS.",
   "from $5,313,977 to $9,999,998 (just $2 under the City Charter requirement that would subject the agreement to Board of Supervisors approval for agreements over $10 million)", 88, None),
 F("Felton Institute", ["Felton"], S, "corrective action",
   "In May 2021, DPH put the Felton Institute on a corrective Plan of Action for not supplying data on its two annual performance goals under the Felton Engagement Specialist Team contract in FY 2019-20. The next year's monitoring report did not document progress, and the underperformance persisted in FY 2020-21, but DPH did not enforce the plan.",
   "DPH put the Felton Institute on a corrective Plan of Action in May 2021 to address lack of performance under the Felton Engagement Specialist Team (FEST) contract", 92,
   "Felton was unsuccessful in a spring 2023 competitive bid; RAMS assumed the street engagement work as of August 1, 2023."),
 F("Harm Reduction Therapy Center", ["HRTC"], S, "contract compliance (city department)",
   "HRTC performed limited work for DPH's Post Overdose Engagement Team from June 2021, without payment and without a signed, executed contract, for over 18 months. The contract for FY 2021-22 and FY 2022-23 was not fully executed until March 6, 2023. The BLA frames this as a significant risk to the City and a DPH contract-management failure.",
   "was performing work for DPH's Post Overdose Engagement Team (POET) without a signed, executed contract in place for such work for over 18 months", 93, "Contract fully executed March 6, 2023."),
 F("Baker Places, Inc.", ["Baker Places", "PRC and Baker Places", "Positive Resource Center", "PRC"], C, "financial insolvency / program closures",
   "Because of Baker Places' financial insolvency, two of its programs closed and two were transferred to another provider, even though the programs were performing well (for example, Jo Ruffin met more than 97 percent of performance objectives). The Citywide Nonprofit Monitoring Program put Baker Places on 'red flag' status in FY 2021-22 and revised it to 'elevated concern' in FY 2022-23.",
   "two programs operated by Baker Places closed and two other programs were transferred due to Baker Places' financial insolvency", 16, "Status revised from red flag (FY 2021-22) to elevated concern (FY 2022-23)."),
 F("Providence Foundation of San Francisco", ["Providence Foundation"], C, "suspension/debarment proceeding (allegation)",
   "As of May 2024, the City moved to debar Providence Foundation from new City contracts over allegations that it falsified invoices. HSH transferred one program to another provider. The $58 million Oasis Hotel shelter contract (58 units) runs to June 2032, and the Board of Supervisors put six months of its FY 2024-25 budget on reserve at the BLA's recommendation.",
   "the City moved to debar Providence Foundation from seeking new City contracts over allegations that the community-based organization falsified invoices", 16,
   "Allegation in a debarment proceeding, not a final adjudication as of this report. Board reserve pending an HSH report on the organization's audited financials, controls, and board oversight."),
 F("Providence Foundation of San Francisco", ["Providence Foundation"], C, "fiscal monitoring finding",
   "Fiscal monitoring found Providence Foundation out of conformance with City fiscal standards in FY 2021-22 and FY 2022-23, including board oversight, invoicing and budgeting practices. Invoice testing found insufficient supporting documentation and expenses not 'reasonably associated with the program budget.' HSH issued its first corrective action letter to Providence for the Oasis Hotel in FY 2022-23, although routine program monitoring that year had no findings.",
   "Providence Foundation was out of conformance with fiscal standards in FY 2021-22 and FY 2022-23, including board of directors' oversight, invoicing practices, and budgeting practices", 16, None),
]
for org, al in [("Hunters Point Family", []), ("Jewish Family Services", ["Jewish Family and Children's Services"]),
                ("Native American Health Center", []), ("PRC", ["Positive Resource Center", "PRC and Baker Places"]), ("Sequoia Living", [])]:
    FIND.append(F(org, al, C, "fiscal monitoring finding",
      f"The BLA added a contract with {org} to its review sample because, according to the Controller's FY 2022-23 Citywide Nonprofit Monitoring report, the organization was not in conformance with fiscal policies. The BLA gives no more detail on the specific findings.",
      "for which the Citywide Nonprofit Monitoring Program report in FY 2022-23 found that the contractor was not in conformance", 26, None))
FIND += [
 F("Urban Alchemy", ["UA"], B, "contract design observation",
   "The Jury cited HSH's March 21, 2022 grant agreement with Urban Alchemy as a contract where the 'outcome objective' was an activity (completing client data in a City database) rather than a result. This is a critique of how HSH drafted the contract, not a finding about Urban Alchemy's performance.",
   "the contract's outcome objective identified a singular activity to be performed—submitting data into a City database, RTZ—instead of a result to be achieved", 23, None),
 F("Tenderloin Housing Clinic, Inc.", ["Tenderloin Housing Clinic", "THC"], B, "no findings/cleared",
   "The Jury cited Tenderloin Housing Clinic's October 1, 2020 HSH grant agreement as a positive example that correctly separates service objectives (activities) from outcome objectives (results such as housing retention).",
   "A grant agreement with the Tenderloin Housing Clinic Inc., dated October 1, 2020 , correctly identifies service objectives that are activities and outcome objectives that are results.", 22, None),
]
STATUS_NOTE = ("HSH responded (Aug 2023) that this table 'appears to reference the findings of the citywide joint fiscal monitoring process, which HSH participates in but does not lead.' "
               "The report does not define 'Elevated'; compare the Controller's FY22 annual report, which named only Bayview Hunters Point Foundation and HomeRise as elevated concern and PRC/Baker Places and UCHS as red flag.")
for org, al, q, p in [("Bayview Hunters Point Foundation", ["Bayview Hunters Point Foundation for Community Improvement", "BVHPF"], "Bayview Hunters Point Foundation SV Elevated SV", 33),
                      ("Conard House", ["Conard House Inc"], "Conard House SV Elevated SV", 33),
                      ("HomeRise", ["Community Housing Partnership"], "HomeRise SA Elevated SV", 34),
                      ("Lavender Youth Recreation and Information Center", ["LYRIC"], "Lavender Youth Recreation and Information Center SA Elevated SV", 34),
                      ("Providence Foundation of San Francisco", ["Providence Foundation"], "PROVIDENCE FOUNDATION OF SAN FRANCISCO SA Elevated SA", 34),
                      ("St. James Infirmary", ["Saint James Infirmary"], "St. James Infirmary SV Elevated SA", 34)]:
    FIND.append(F(org, al, B, "elevated status (monitoring table)",
      f"In the report's appendix table of FY 2021-22 monitoring status for HSH contractors, {org} is listed with status 'Elevated'.", q, p, STATUS_NOTE))
for org, al, q, p in [("Glide Community Housing", [], "GLIDE COMMUNITY HOUSING SV Completed - findings resolved", 33),
                      ("Mission Housing Development Corp", ["MHDC", "Mission Housing Development Corporation"], "MISSION HOUSING DEVELOPMENT CORP (MHDC) SV Completed - findings resolved", 34),
                      ("Salvation Army", ["The Salvation Army"], "Salvation Army SV Completed - findings resolved", 34),
                      ("Sequoia Living", [], "SEQUOIA LIVING SV Completed - findings resolved", 34),
                      ("Urban Alchemy", ["UA"], "Urban Alchemy SV Completed - findings resolved", 34),
                      ("WeHOPE", ["WeHope"], "WeHOPE SA Completed - findings resolved", 34)]:
    FIND.append(F(org, al, B, "monitoring findings resolved",
      f"In the report's appendix table of FY 2021-22 monitoring status for HSH contractors, {org} is listed as 'Completed - findings resolved', meaning findings were identified and then resolved.", q, p,
      "HSH says the table appears to reflect citywide joint fiscal monitoring, not HSH program monitoring."))
FIND += [
 F("Baker Places, Inc.", ["Baker Places", "PRC and Baker Places", "Positive Resource Center"], K, "financial distress / repayment agreement",
   "Citing a 2024 Baker Places letter, the Jury reports losses in 14 of the 18 years from 2005 to 2022 (averaging $482,000 a year). The losses led to City cash advances and a $7.67 million debt to the City as of April 2024. Under an April 2024 repayment agreement, Baker transferred a residential care facility to the City for $3 million in credit and will repay the remaining $4.7 million over 23 years at 1.12% interest. Monitoring found payroll documentation, cash management and separation-of-duties deficiencies in 2020-2022.",
   "These losses led to cash advances by the city, resulting in a $7.67 million debt to the city accumulating as of April 2024.", 48,
   "Repayment agreement reached April 2024; per the Jury, Baker was on 'Elevated Concern' status as of 2024 and could continue doing business with the City."),
 F("Providence Foundation of San Francisco", ["Providence Foundation"], K, "allegation (City Attorney debarment proceeding)",
   "Providence received almost $100 million from 2015 to 2024 for shelters and case management. The City Attorney alleged that in 2022 it invoiced and was paid $105,000 for painting and deadbolt removal at the Oasis Motel shelter that was not performed, and more broadly that it submitted fraudulent invoices of more than $100,000. In May 2024 the City Attorney started debarment and suspended Providence from new City contracts and grants. The charging document also cites 2023 HSH corrective action letters about nepotism, overspending budgets and missing occupancy goals.",
   "the City Attorney alleged that Providence submitted fraudulent invoices of more than $100,000", 50,
   "These are allegations in a pending debarment proceeding (suspension pending resolution) as described by the Jury; not an adjudicated finding in this source."),
 F("HomeRise", ["Community Housing Partnership", "Community Housing Partnership d/b/a HomeRise"], K, "audit findings (as summarized)",
   "Summarizing the Controller's April 2024 audit, the Jury reports that HomeRise improperly transferred $2 million from a restricted account without approval, borrowed $2.5 million from a property operating account to cover corporate payroll, and paid more than $200,000 in unplanned, unbudgeted staff bonuses. The Jury says the City did not redirect grant funds because HomeRise owns essential housing (it operates nearly one-third of City-funded units for formerly homeless people).",
   "Improperly transferred $ 2 million from a restricted account without approval and borrowed another $2.5 million from a property's operating account to help cover corporate payrolls", 51,
   "HomeRise hired a new executive in spring 2023 who committed to new fiscal protocols; the Jury found City officials were providing significant informal management support."),
 F("HomeRise", ["Community Housing Partnership"], A, "corrective action",
   "After the reported death of resident Eric McCain at HomeRise's Jazzie Collins Apartments (reportedly undiscovered for about 10-12 days in November 2025), HSH issued a February 6, 2026 corrective action letter. It cited HomeRise's failure to follow HSH's Resident Emergency Safety Check policy from November 5 to 14, 2025, and required a wellness-check overhaul, staff training and a technology plan. The Jury presents this as a case study, 'rather than findings of fault.'",
   "to address HomeRise's failure to follow the required HSH Resident Emergency Safety Check Policy and Procedures for the Jazzie Collins Permanent Supportive Housing (PSH) program", 31,
   "The Jury notes the letter did not call for a review of other HomeRise sites."),
 F("HomeRise", ["Community Housing Partnership"], A, "corrective action tier history",
   "According to the Jury, HomeRise was on the Controller's corrective action list at Tier 2/'Elevated Concern' after FY 2021-22 and FY 2022-23 monitoring. It was escalated after the 2024 Controller audit (the Jury cites HSH materials calling this 'Red Flag'). It was later lowered to Tier 2 in the Controller's FY 2024-25 list.",
   "It was subsequently lowered to Tier 2, with a notation \"lowered from Tier 3 in 2024\" as reflected in the Controllers FY24-25 Corrective Action list.", 30, "Tier 2 as of the FY 2024-25 annual report."),
 F("Urban Alchemy", ["UA"], A, "corrective action",
   "The Jury states that by 2025 Urban Alchemy was designated Tier 2 on the Controller's corrective action list over exceeding budget, employee time-tracking, and prior invoicing issues. HSH's August 2025 packet for a six-month, $4 million extension of the 711 Post Street shelter listed two unresolved citywide fiscal-monitoring findings (exempt staff not tracking time; about 20 days of operating cash against a 30-day standard) and a June 26, 2025 corrective action letter for overspending at 711 Post.",
   "By 2025, UA was designated as \"Tier 2\" on the Controller's Office Nonprofit Monitoring Corrective Action list due to serious concerns about exceeding budget, employee time- tracking, and prior issues with invoicing.", 33,
   "Discrepancy to note: the Controller's FY25 annual report Tier 2 list (Figure 24, p.30) does not include Urban Alchemy, and the Jury says the September 2025 BLA review called the Tier 2 designation 'pending.' Treat Tier 2 status as reported by the Jury, not confirmed by the Controller list we checked."),
 F("Urban Alchemy", ["UA"], A, "program performance (met objectives) / contract exit",
   "HSH's FY 2024-25 performance monitoring found Urban Alchemy met all service and outcome objectives at 711 Post Street except guest attendance at community meetings, with 96 percent occupancy and 763 adults served. The Board of Supervisors approved the amendment (total about $27.6 million) in September 2025. The Jury argues these reviews did not measure resident safety or neighborhood conditions. After a February 12, 2026 Board committee hearing, Urban Alchemy chose to exit the contract.",
   "HSH's FY2024-25 performance monitoring found that Urban Alchemy \"met all service and outcome objectives\" except guest attendance at community meetings", 35,
   "Urban Alchemy elected to exit the 711 Post contract after the February 2026 hearing (per the Jury, citing Mission Local)."),
]

pdf_of = {r["id"]: r["pdf"] for r in REVIEWS}
url_of = {r["id"]: r["url"] for r in REVIEWS}
cache = {}
bad = 0
for f in FIND:
    pdf = pdf_of[f["review_id"]]
    pg = cache.setdefault(pdf, pages(pdf + ".txt"))
    q = norm(f["quote"])
    hits = [p for p, t in pg.items() if q in t]
    if f["page"] not in hits:
        # allow quote spanning page break
        span = [p for p in pg if q in pg[p] + pg.get(p + 1, "")]
        if f["page"] not in span:
            print("QUOTE FAIL", f["org_name"], f["review_id"], f["page"], hits, span); bad += 1
    if len(f["quote"].split()) > 40:
        print("QUOTE TOO LONG", f["org_name"], len(f["quote"].split())); bad += 1
    f["url"] = url_of[f["review_id"]]
if bad:
    sys.exit(1)
out = {"reviews": [{k: v for k, v in r.items() if k != "pdf"} | {"accessed_date": ACC} for r in REVIEWS], "org_findings": FIND}
(BASE / "partials").mkdir(exist_ok=True)
(BASE / "partials" / "group_d.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(len(out["reviews"]), "reviews;", len(FIND), "findings; all quotes verified")
