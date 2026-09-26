"""Group A: Controller audits of UCHS, HomeRise, Rudolph Dwayne Jones entities / Urban Ed Academy,
Mexican Museum, SF SAFE, Ocean Avenue Association. Writes data/reviews/partials/group_a.json and verifies quotes."""
import json, re, pathlib, csv
base = pathlib.Path(__file__).resolve().parents[2] / "data" / "reviews"
urls = {r["file"]: r["url"] for r in csv.DictReader(open(base / "pdf_sources.tsv"), delimiter="\t")}
A = "2026-09-26"
R = [
 dict(id="ctrl-2022-uchs-audit", file="ctrl_audit_uchs_2022.pdf",
  title="The City Must Determine Whether United Council of Human Services Should Continue Providing Services to San Francisco Residents Despite Continuing Noncompliance With City Agreements",
  date="2022-11-17", type="controller_audit",
  summary="Controller's City Services Auditor audit, requested by the Department of Homelessness and Supportive Housing (HSH), of six grants totaling $36.4 million to Bayview Hunters Point Foundation as fiscal sponsor for United Council of Human Services (UCHS). It found UCHS did not comply with tenant eligibility, expenditure, and recordkeeping requirements, collected tenant rent it was not authorized to collect, and that HSH's program monitoring was deficient. It made 14 recommendations, including that HSH consider terminating the grants with UCHS."),
 dict(id="ctrl-2024-uchs-followup", file="ctrl_followup_uchs_2024.pdf",
  title="Field Follow-up of the 2022 Audit of the United Council of Human Services' Compliance With City Agreements",
  date="2024-04-16", type="controller_audit",
  summary="Controller follow-up memo on the 2022 UCHS audit. It reports that 9 of 14 recommendations were implemented and 5 became inapplicable because HSH removed UCHS as a subcontractor after UCHS was listed as suspended in the state charity registry; programs moved to Felton Institute by June 30, 2023. UCHS returned the remaining tenant rent with a $35,000 check in November 2022."),
 dict(id="ctrl-2024-homerise-audit", file="ctrl_audit_homerise_2024.pdf",
  title="HSH/MOHCD: Community Housing Partnership, d/b/a HomeRise, Mismanaged Financial Activities and Misused City Funds Related to City Agreements for Its Properties and Supportive Housing Efforts",
  date="2024-04-02", type="controller_audit",
  summary="Performance audit (conducted for the Controller by Sjoberg Evashenk Consulting) of HomeRise's city agreements with HSH and MOHCD, covering 2019-2022. It found gross fiscal noncompliance, unallowable or questionable spending, improper transfers of restricted property funds, weak financial controls, and insufficient board and executive oversight, while noting HomeRise appeared to have an adequate programmatic framework. HomeRise said it has since remedied many issues; the auditors did not verify those changes."),
 dict(id="ctrl-2025-pi-rdj-entities", file="pi_rudolph_dwayne_jones_2025.pdf",
  title="Public Integrity Assessment - Status of City Contracts and Grants With Rudolph Dwayne Jones and Related Entities After Criminal Charges and Suspension",
  date="2025-03-11", type="controller_public_integrity",
  summary="Controller public integrity assessment itemizing $15.2 million the City paid from July 2016 to December 2024 to entities related to Rudolph Dwayne Jones, who was criminally charged in 2023 (he has pleaded not guilty), and confirming contracts with the five suspended entities were terminated or expired. It also reviewed grants to Urban Ed Academy (founded by Jones, not suspended) and found irregularities in HRC and OEWD award and oversight processes, including a gift to the former HRC director and awards to UEA despite low scores. UEA has new leadership and cooperated."),
 dict(id="ctrl-2024-mexican-museum-audit", file="ctrl_audit_mexican_museum_2024.pdf",
  title="OCII and RED: The Mexican Museum Has Not Demonstrated That It Can Meet the City's Contractual Obligations, and OCII Has Not Effectively Enforced the Museum's Grant Agreement",
  date="2024-03-21", type="controller_audit",
  summary="Controller audit of The Mexican Museum's $10.6 million grant from the Office of Community Investment and Infrastructure (of which $4 million was disbursed) and related lease for 706 Mission Street. It found the Museum had about 2 percent of the funds needed to build out its space, did not meet several lease requirements, and submitted ineligible and questionable costs that OCII approved. The Museum disputed the report's scope and fairness; the auditors stood by their findings."),
 dict(id="ctrl-2024-sfsafe-assessment", file="ctrl_audit_sfpd_sfsafe_2024.pdf",
  title="The San Francisco Police Department Did Not Adequately Review Expenses and Subsequently Approved Ineligible or Unsupported Expenses Incurred Under Its Grant Agreement With SF SAFE",
  date="2024-01-18", type="controller_audit",
  summary="Controller assessment (a nonaudit service, done with the City Attorney) of invoices under the Police Department's $5.3 million grant to the nonprofit SF SAFE. In a sample of $910,000 from July 2022 to March 2023 it found at least $79,655 in ineligible or excessive expenses, and that the Police Department lacked documentation for 72 percent of reimbursements. The Police Department concurred and said it would recover the ineligible payments."),
 dict(id="ctrl-2023-ocean-ave-assn-audit", file="ctrl_audit_ocean_ave_assn_2023.pdf",
  title="Ocean Avenue Association Generally Complies With Some Provisions of the Management Agreement but the Board of Directors Does Not Effectively Govern the Organization or Community Benefit District",
  date="2023-06-29", type="controller_audit",
  summary="Audit (by Sjoberg Evashenk Consulting for the Controller) of the Ocean Avenue Association, the nonprofit that manages the Ocean Avenue Community Benefit District under an agreement administered by OEWD. It found the association complies with key agreement provisions but its board does not govern effectively, some agreement provisions were not fully met, and city grants were not always properly administered. The association concurred and had hired a new executive director."),
]
def F(org, aliases, rid, ftype, finding, quote, page, status=None):
    return dict(org_name=org, org_name_aliases=aliases, ein=None, review_id=rid, finding_type=ftype,
                finding=finding, quote=quote, page=page, status=status)
UCHS = ("United Council of Human Services", ["UCHS"])
BVHPF = ("Bayview Hunters Point Foundation", ["BVHPF", "Bayview Hunters Point Foundation for Community Improvement"])
HR = ("Community Housing Partnership, d/b/a HomeRise", ["HomeRise", "Community Housing Partnership"])
UEA = ("Urban Ed Academy, Inc.", ["Urban Ed Academy", "UEA"])
MM = ("The Mexican Museum", ["Mexican Museum"])
SAFE = ("San Francisco SAFE", ["SF SAFE", "SFSAFE"])
OAA = ("Ocean Avenue Association", ["OAA", "Ocean Avenue Community Benefit District"])
uchs_status = "HSH moved all UCHS programs to Felton Institute by June 30, 2023 and removed UCHS as a subcontractor (Controller follow-up, April 2024). UCHS's written response is attached to the report as an image and could not be text-extracted."
O = [
 F(*UCHS, "ctrl-2022-uchs-audit", "eligibility/recordkeeping noncompliance",
   "In a sample of 29 tenants in HSH-funded Hope House programs, 24 (83%) were not properly prioritized through the city's Coordinated Entry process or lacked required eligibility documents, and 19 (66%) had incomes calculated incorrectly at entry.",
   "Of 29 sample tenants, 24 (83 percent) were not appropriately prioritized through HOM’s Coordinated Entry process or did not have the required eligibility documentation.", 5, uchs_status),
 F(*UCHS, "ctrl-2022-uchs-audit", "eligibility/recordkeeping noncompliance",
   "Three UCHS employees were enrolled as tenants in the Hope House Consolidated program without going through Coordinated Entry, with incomplete documentation.",
   "Three UCHS employees were enrolled into the Hope House Consolidated program without going through the Coordinated Entry process and provided incomplete supporting documentation.", 5,
   "HSH later adopted a policy (effective March 1, 2024) on enrolling provider employees in HSH-funded services (Controller follow-up, April 2024)."),
 F(*UCHS, "ctrl-2022-uchs-audit", "unauthorized rent collection",
   "From March through August 2022 UCHS collected at least $108,861 in tenant rent although the grants assigned rent collection to the fiscal sponsor; after HSH directed it to turn the money over, UCHS remitted $78,200 and still owed at least $30,661 as of September 20, 2022. UCHS told auditors it kept the rent in a dedicated account and did not spend it.",
   "From March through August 2022, UCHS collected at least $108,861 in tenant rent, contrary to HOM’s grant agreements, which task BVHPF with collecting rent.", 21,
   "Resolved: in November 2022 UCHS sent a $35,000 cashier's check to Felton Institute, returning the remaining rent (Controller follow-up, April 2024)."),
 F(*UCHS, "ctrl-2022-uchs-audit", "questioned costs",
   "UCHS did not consistently support its expenditures: 4 of 21 sampled American Express charges ($8,464 of $27,946) lacked documentation, and UCHS overbilled the fiscal sponsor $227,663 for Drop-In Center staffing in May-June 2022 because staffing exceeded the budget.",
   "UCHS overbilled BVHPF for staffing expenditures at the Drop-In Center by $227,663 for May and June 2022.", 25, uchs_status),
 F(*UCHS, "ctrl-2022-uchs-audit", "performance shortfall",
   "In August 2022 file reviews, Hope House Consolidated had 70 of 99 rooms occupied (71%) and Hope House for Veterans 12 of 33 (36%), far below the required 90% average. The audit attributes this both to UCHS circumventing required processes and to HSH not adequately monitoring the programs.",
   "Hope House for Veterans had only 12 (36 percent) of 33 rooms occupied.", 31, uchs_status),
 F(*BVHPF, "ctrl-2022-uchs-audit", "fiscal sponsor oversight weakness",
   "As UCHS's fiscal sponsor (from February 2022), BVHPF paid UCHS's monthly American Express balance before reviewing supporting documents, which the audit calls not a best practice. The audit also records BVHPF's statements that UCHS denied it full access to key records and excluded it from rent collection; the main findings concern UCHS, not BVHPF.",
   "it pays the total monthly balance of UCHS’s American Express account before reviewing the supporting documentation for the expenditures on the monthly statement, which is not a best practice.", 24,
   "Felton Institute replaced BVHPF as sole fiscal sponsor in October 2022 (Controller follow-up, April 2024)."),
 F(*UCHS, "ctrl-2024-uchs-followup", "charity registry noncompliance",
   "In February 2023 the Controller notified HSH that UCHS was listed as 'suspended' in the California Attorney General's Registry of Charities and Fundraisers; city policy requires charities doing business with the City to be in compliance.",
   "notified HSH that UCHS had a status of “suspended” in the California Attorney General’s Registry of Charities and Fundraisers", 2, None),
 F(*UCHS, "ctrl-2024-uchs-followup", "contract terminated",
   "In April 2023 HSH told UCHS and Felton Institute to move all HSH-funded programs to Felton by June 30, 2023 and removed UCHS as a subcontractor, which the Controller says effectively ended UCHS's city funding.",
   "In April 2023 HSH notified UCHS and Felton Institute that they must transition all programs funded by HSH to Felton Institute by June 30, 2023, and that UCHS would be subsequently removed as a subcontractor.", 2,
   "Closed: all 14 audit recommendations closed (9 implemented, 5 no longer applicable)."),
 F("Felton Institute", [], "ctrl-2024-uchs-followup", "context (successor provider)",
   "Felton Institute became the sole fiscal sponsor in October 2022 and took over the former UCHS programs. The follow-up found that Felton's grant agreements include the eligibility and recordkeeping requirements, and that Felton adopted the credit card controls recommended for UCHS. Felton was not itself audited.",
   "the latter has implemented changes to its credit card policy, as the Controller recommended for UCHS.", 6, None),
 F(*HR, "ctrl-2024-homerise-audit", "misuse of funds / fiscal noncompliance",
   "The audit found gross fiscal noncompliance, wasteful practices, and spending of city funds on unallowed or questionable costs, with key financial controls missing. The City had provided almost $110 million in loans, $90 million in operating subsidies, and over $40 million in grants during the audit period.",
   "the audit found gross fiscal noncompliance, wasteful practices that misuse taxpayer funds, and spending of city funds on unallowed or questionable costs", 3,
   "HomeRise acknowledged the concerns and said it had fixed many of them after new leadership arrived (CEO June 2023, CFO May 2023); auditors did not verify the fixes. HSH and MOHCD concurred with the recommendations; HSH said it would require repayment of unallowable costs whose eligibility can't be documented."),
 F(*HR, "ctrl-2024-homerise-audit", "improper transfer of restricted funds",
   "HomeRise transferred $2 million from a restricted account without approval and borrowed $2.5 million from a property's operating account to help cover corporate payroll; $2.1 million was still unpaid as of August 23, 2023.",
   "HomeRise improperly transferred $2 million from a restricted account without approval and borrowed another $2.5 million from a property’s operating account to help cover corporate payroll charges.", 10,
   "As of August 23, 2023, $2.1 million remained unpaid (per audit)."),
 F(*HR, "ctrl-2024-homerise-audit", "questioned costs",
   "Records for eight properties showed operating costs that were improperly charged or questionable, including more than $100,000 in temporary rental charges, $96,000 for tenant program salaries, and $12,500 for a social event. HomeRise also adjusted $1 million of property expenses without sufficient explanation.",
   "Records of eight properties show instances of operational costs that were improperly charged to the property or questionable", 10, None),
 F(*HR, "ctrl-2024-homerise-audit", "questioned costs",
   "All nine types of grant expenses reviewed (nearly $24,000) included unallowable, imprudent, or questionable spending, such as fundraising, staff bonuses, and staff lunches and gifts. Because records were in poor condition, auditors could not determine the full amount of inappropriate charges.",
   "All nine types of expenses we reviewed, totaling nearly $24,000, revealed instances of unallowable, imprudent, or questionable spending that did not meet the intent of the City’s grant agreement.", 11, None),
 F(*HR, "ctrl-2024-homerise-audit", "financial management finding",
   "HomeRise paid more than $200,000 in unplanned, unbudgeted staff bonuses while it had cash flow problems, and lost about $6.3 million to vacancies over the four-year audit period (average vacancy 14.6% in January 2023).",
   "HomeRise gave staff bonuses of more than $200,000 that were unplanned and unbudgeted, worsening cash flow problems.", 10, None),
 F(*HR, "ctrl-2024-homerise-audit", "internal control weakness",
   "As of January 2023 HomeRise had 118 active credit cards, 40 with limits of $10,000 or more; about 15% required no purchase approval, and 18% more let users approve their own purchases.",
   "As of January 2023, HomeRise had 118 active credit cards in use, of which more than one-third, or 40, had credit limits of $10,000 or higher", 12, None),
 F(*HR, "ctrl-2024-homerise-audit", "governance finding",
   "Past executive leadership and the board did not provide sufficient oversight; between 2019 and early 2023 the CEO position turned over three times and the CFO five times.",
   "Between 2019 and early 2023, HomeRise’s chief executive officer and chief financial officer turned over three and five times, respectively.", 14, None),
 F(*HR, "ctrl-2024-homerise-audit", "elevated concern",
   "On December 12, 2022 the Controller placed HomeRise on 'elevated concern' status because of risk of instability; it remained there in FY 2023-24. MOHCD had issued a notice of default on one property on June 2, 2022.",
   "on December 12, 2022, the Office of the City Controller placed HomeRise on “elevated concern status” due to risk of instability.", 7, None),
 F(*HR, "ctrl-2024-homerise-audit", "no findings/cleared (programmatic, limited review)",
   "In a high-level review, auditors found HomeRise appeared to have a sufficient programmatic framework to deliver contracted services; HSH had monitored its program performance.",
   "HomeRise appeared to have a sufficient programmatic framework to provide contracted program services to its intended recipients.", 11, None),
 F("RDJ Enterprises, LLC", ["RDJ"], "ctrl-2025-pi-rdj-entities", "suspension / contract terminated",
   "A for-profit company related to Rudolph Dwayne Jones. It received $1,001,635 as a city prime contractor (July 2016-December 2024) and was a subcontractor on Port and SFPUC contracts. It was suspended in September 2023 after Jones was criminally charged, and departments ended their contracts with it. Criminal charges are allegations; Jones has pleaded not guilty.",
   "In September 2023 SFPUC stated in a memo that it took action to terminate all contracts with RDJ as a prime contractor or subcontractor.", 17, "Suspended; all city contracts expired or terminated as of report date."),
 F("Southeast Consortium for Equitable Partnerships", ["SECEP"], "ctrl-2025-pi-rdj-entities", "suspension / contract terminated",
   "A Jones-related entity that received $811,374 from the City Administrator as a prime recipient, plus $293,908 in SFPUC Social Impact Partnership payments from contractors (summed from the report's table). It was suspended in September 2023, and its 2023 Community Challenge Grant proposal was removed from consideration. The criminal complaint alleges city funds were steered to it; these are allegations, and the defendants have pleaded not guilty.",
   "The City Administrator determined that Southeast Consortium for Equitable Partnerships’ proposal was no longer eligible to receive funding for the Community Challenge Grant program’s 2023 solicitation cycle", 17, "Suspended."),
 F("RDJ-Project Complete, LLC", [], "ctrl-2025-pi-rdj-entities", "suspension",
   "A Jones-related entity suspended from city funding in September 2023. The criminal complaint (an allegation; the defendants pleaded not guilty) alleges city funds were steered to it.",
   "RDJ-Project Complete, LLC - suspended", 5, "Suspended."),
 F("20ROC Holdings, LLC", ["20ROC Holdings"], "ctrl-2025-pi-rdj-entities", "suspension",
   "A Jones-related entity suspended in September 2023. It leased space to Urban Ed Academy starting May 1, 2023, at $3,600 per month (per the report).",
   "20ROC Holdings, LLC - suspended", 5, "Suspended."),
 F("Urban Equity, LLC", [], "ctrl-2025-pi-rdj-entities", "suspension",
   "A Jones-related entity suspended from city funding in September 2023.", "Urban Equity, LLC - suspended", 5, "Suspended."),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "context (not suspended)",
   "A nonprofit founded by Jones in 2012. It was not suspended and can still bid on city work. It received $2,941,983 as a city prime recipient and $297,489 in SFPUC Social Impact Partnership payments (summed from the report's table). All its city grants have expired or been terminated.",
   "UEA has new leadership and is fully cooperating with the assessment.", 6, "All city grants to UEA expired or terminated as of January 2025; UEA not suspended."),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "conflict of interest",
   "UEA commissioned and gave then-HRC Director Sheryl Davis a $5,500 portrait of herself less than a month before HRC signed a $270,000 grant with UEA. The Controller says this appears to violate city ethics rules and creates at least the appearance of undue influence, and that the gift was not disclosed on her Form 700.",
   "UEA commissioned and gave former HRC Director Sheryl Davis a $5,500 portrait of herself just before she approved a $270,000 grant to UEA.", 23, None),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "conflict of interest",
   "UEA's then-executive director sat on the Dream Keeper Initiative's Community Accountability Committee, which oversees DKI grants, from October 2023 to January 2024 while UEA held DKI-funded grants. HRC had reopened the application period so he could apply.",
   "While executive director of UEA, Seriguchi was on DKI’s Community Accountability Committee and UEA received DKI funding.", 24, None),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "irregular award (department process)",
   "HRC gave UEA a $270,000 grant from a prequalified pool even though UEA ranked 19th of 20. The finding is about HRC not following competitive award rules; the report also says UEA and HRC officials communicated during the RFQ's no-contact period.",
   "Of the 7 organizations that were awarded grants, 3 were ranked 18th, 19th, and 20th.", 30, None),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "questioned costs",
   "HRC reimbursed UEA at least $26,675 in questionable or ineligible expenses, including $19,834 lacking justification and gift cards bought without a Controller-approved gift card policy.",
   "HRC reimbursed UEA for at least $26,675 in questionable or ineligible expenses.", 33, None),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "irregular award (department process)",
   "OEWD awarded UEA a Dream Keeper Initiative 'Industries of Opportunity' grant even though its proposal ranked 7th of 8 and was not recommended by the scoring panel. OEWD later raised the grant from $350,000 to $1,192,500, including a $755,000 increase in February 2024 just after UEA was at 43% of its placement target. OEWD had no documented explanation for the award.",
   "OEWD awarded UEA a grant although its proposal received the second lowest score (ranked seventh of eight) and was not recommended for funding by the scoring panel.", 40,
   "OEWD terminated the grant effective June 30/July 1, 2024 citing budget reductions; $337,405 paid through December 2024."),
 F(*UEA, "ctrl-2025-pi-rdj-entities", "risk identified (double billing)",
   "UEA's grants from several departments had overlapping scopes of work and did not fully disclose its other city funding. The Controller says this created a risk of paying twice for the same services, but it did not find that double billing occurred.",
   "This timing suggests the potential for duplicate payments that may have gone unnoticed without our assessment and inquiry into these grants to UEA.", 52, None),
 F("Young Community Developers", ["YCD"], "ctrl-2025-pi-rdj-entities", "unusual arrangement (department practice)",
   "HRC paid stipends to Dream Keeper Initiative Community Accountability Committee members through an amendment to its grant with YCD, which received a 12.5% administrative fee (budgeted at $10,500). The Controller found HRC had no legal authority to pay the stipends and that routing them through a grantee lacked transparency. The finding concerns HRC's practice, not misconduct by YCD.",
   "YCD receives a 12.5 percent (budgeted at $10,500) fee for administering checks that HRC could and should have issued directly through the City’s financial and procurement system.", 26, None),
 F(*MM, "ctrl-2024-mexican-museum-audit", "questioned costs",
   "The Museum submitted, and OCII approved, $43,616 in ineligible costs (including $21,250 in duplicate expenses), $930,247 in questionable costs (including $534,187 in salaries and benefits and $177,072 in accounting fees without enough support), and $562,579 in operating costs.",
   "The Museum submitted $43,616 of ineligible costs, $930,247 of questionable costs, and $562,579 of operational costs, all of which OCII approved.", 8,
   "The Museum disputed the audit, saying it overreached its scope and was not fair and balanced; auditors disagreed and stood by the findings. Auditors recommended OCII seek reimbursement of ineligible costs."),
 F(*MM, "ctrl-2024-mexican-museum-audit", "financial capacity finding",
   "The Museum projected it needed $49.8 million in capital funds (beyond the city grant) to finish its space at 706 Mission Street but had about $835,000 in cash (2%) and could not document other fundraising.",
   "estimated that it had only approximately $835,000 (2 percent of the amount needed) in available cash", 5,
   "The Museum said it had raised at least $30 million in matching funds; auditors said it did not provide documents supporting the amounts."),
 F(*MM, "ctrl-2024-mexican-museum-audit", "contract noncompliance",
   "The Museum did not substantially complete interior improvements by September 2022 as the lease required (work had not begun), did not meet reporting and insurance requirements, and had not paid nearly $80,000 in common area dues.",
   "The Museum has not fulfilled reporting and insurance requirements in the lease and facilities agreement and has not paid nearly $80,000 in common area and maintenance dues.", 8, None),
 F(*MM, "ctrl-2024-mexican-museum-audit", "prior audit finding (historical)",
   "The report cites a September 2014 California Department of Finance interim audit that found none of an $800,000 state grant's disbursed funds were supported or eligible, and recommended the Museum return $123,662.",
   "The Museum has a history of poorly administering grants received from other sources.", 17, None),
 F(*SAFE, "ctrl-2024-sfsafe-assessment", "questioned costs",
   "In a sample of $910,000 reimbursed from July 2022 to March 2023, at least $79,655 (9%) went to ineligible or excessive expenses, including $36,041 in luxury gift boxes, $14,525 for a Lake Tahoe symposium trip, recurring parking, and ride-hailing. The Controller said the total for the whole grant term is likely significantly higher.",
   "we found at least $79,655 (9 percent) was spent on ineligible and/or excessive expenses, including those for luxury gift boxes, a Lake Tahoe symposium trip, recurring parking fees/permits, and ride-hailing services.", 1,
   "The Police Department concurred and said it would recover the ineligible payments through SF SAFE's current agreement. It also noted SF SAFE's FY22-23 ledger showed $1.58M in eligible expenses against $1.17M in grant authority. SF SAFE's legal counsel submitted a response (image, not text-extracted)."),
 F(*SAFE, "ctrl-2024-sfsafe-assessment", "documentation gap (department oversight)",
   "Until SF SAFE provided more documents for this review, the Police Department had no documentation for $3,822,228 (72%) of the $5,332,791 reimbursed from July 2018 to March 2023, and it had not monitored the grant since 2019. This is mainly a finding about the Police Department's oversight.",
   "the Police Department did not have documentation to support $3,822,228 (72 percent) of the $5,332,791 spent by and reimbursed to SF SAFE from July 2018 through March 2023.", 3, None),
 F(*OAA, "ctrl-2023-ocean-ave-assn-audit", "governance finding",
   "The association's board did not govern effectively: there were weak controls, unclear roles, no basic policies, Brown Act compliance gaps, and conflict-of-interest obligations not fully addressed.",
   "OAA Board of Directors Does Not Effectively Govern the Organization or District", 7,
   "OEWD concurred with the recommendations; OAA hired a new, experienced executive director and board training consultant."),
 F(*OAA, "ctrl-2023-ocean-ave-assn-audit", "partial compliance",
   "The association complied with key provisions of its management agreement (delivering district services, good standing, at least 1% non-assessment revenue) but not with provisions on annual and midyear reports, budget allocations, showing assessment funds were spent only on eligible costs, and accounting records.",
   "OAA complies with key provisions of its management agreement, including those regarding administering district services, maintaining its corporate and nonprofit status in good standing", 7, None),
 F(*OAA, "ctrl-2023-ocean-ave-assn-audit", "grant administration finding",
   "Of six city grants ($349,250 awarded, $200,006 received), the three reviewed showed missing deliverables documentation, payments to consultants without enough support, and staff costs that could not be justified.",
   "OAA also paid some consultants without sufficient support for services and could not justify some expenses associated with staff", 7, None),
]
rid2file = {r["id"]: r["file"] for r in R}
for o in O:
    o["url"] = urls[rid2file[o["review_id"]]]
reviews = []
for r in R:
    reviews.append(dict(id=r["id"], title=r["title"], publisher="San Francisco Office of the Controller, City Services Auditor",
                        date=r["date"], url=urls[r["file"]], type=r["type"], summary=r["summary"], accessed_date=A))
# verify quotes
def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("ﬃ", "ffi")
    s = re.sub(r"-\s*\n\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()
bad = 0
for o in O:
    f = rid2file[o["review_id"]].replace(".pdf", ".txt")
    t = open(base / "text" / f).read(); parts = re.split(r"=== PAGE (\d+) ===", t)
    d = {int(parts[i]): parts[i+1] for i in range(1, len(parts), 2)}
    if len(o["quote"].split()) > 40: print("TOO LONG", o["quote"][:60]); bad += 1
    if norm(o["quote"]) not in norm(d.get(o["page"], "")):
        hits = [p for p, s in d.items() if norm(o["quote"]) in norm(s)]
        print("QUOTE FAIL", o["org_name"], o["page"], hits, o["quote"][:70]); bad += 1
(base / "partials").mkdir(exist_ok=True)
json.dump({"reviews": reviews, "org_findings": O}, open(base / "partials" / "group_a.json", "w"), indent=1, ensure_ascii=False)
print(len(reviews), "reviews", len(O), "findings", bad, "problems")
