"""Build data/reviews/partials/group_b.json (Controller audits/assessments 2023-2026: HRC purchasing,
Arriba Juntos, support organizations, Opportunities for All/JCYC, AAACC, charity-registry memo,
Chapter 12G political-activity memo, nonprofit public reporting). Quotes are verified against
extracted PDF text (data/reviews/text) and the page number is computed from the text markers."""
import json, re, pathlib, sys
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
urls = {}
for line in (base / "pdf_sources.tsv").read_text().splitlines()[1:]:
    f, _, u = line.split("\t"); urls[f.replace(".pdf", "")] = u
ACC = "2026-09-26"
def norm(s): return re.sub(r"\s+", " ", s.replace(" ", " ")).strip()
pages_cache = {}
def pages(stem):
    if stem not in pages_cache:
        t = (base / "text" / f"{stem}.txt").read_text()
        parts = re.split(r"=== PAGE (\d+) ===", t)
        pages_cache[stem] = {int(parts[i]): norm(parts[i + 1]) for i in range(1, len(parts), 2)}
    return pages_cache[stem]

R = {}  # review_id -> (stem, review dict)
def review(rid, stem, title, date, typ, summary):
    R[rid] = stem
    reviews.append(dict(id=rid, title=title, publisher="San Francisco Office of the Controller, City Services Auditor",
                        date=date, url=urls[stem], type=typ, summary=summary, accessed_date=ACC))
reviews, findings = [], []
def F(org, rid, ftype, finding, quote, status=None, aliases=None, ein=None):
    findings.append(dict(org_name=org, org_name_aliases=aliases or [], ein=ein, review_id=rid, finding_type=ftype,
                         finding=finding, quote=quote, page=None, status=status, url=urls[R[rid]]))

# ---------------- HRC purchasing audit (2025) ----------------
rid = "ctrl-2025-hrc-purchasing"
review(rid, "ctrl_audit_hrc_purchasing_2025",
       "The Human Rights Commission Violated the City's Purchasing Rules, Circumventing Controls and Policies",
       "2025-09-16", "controller_audit",
       "Joint Controller/City Attorney audit and investigation of $6.3 million in Human Rights Commission (HRC) noncontract payments, July 2020 to September 2024. "
       "It found that HRC, under its former executive director, made millions of dollars in ineligible and improper payments, including $2,447,660 in ineligible or likely ineligible Prop Q purchases and $3.1 million in improper direct-voucher single payments. "
       "The findings are mainly about the department's own purchasing failures; several nonprofits appear as recipients of those payments. HRC's new leadership had begun putting recommendations in place.")
F("Collective Impact", rid, "conflict of interest",
  "The audit reports that HRC's former executive director did not disclose payments she received from Collective Impact or her personal relationship with its executive director, while HRC kept funding the nonprofit (2019-2024). "
  "In March 2025 the City Attorney suspended Collective Impact from city contracts and grants and moved to debar it for up to five years. The City Attorney alleges that it spent city funds on gifts to the director and submitted improper reimbursement claims. These are allegations in a debarment proceeding, not final findings. "
  "The Controller said a separate audit of Collective Impact's grants from HRC and three other departments would follow.",
  "As alleged in the Counts and Allegations, Collective Impact spent city funds on gifts to Davis, aided and abetted her in violating various conflict-of-interest laws, and submitted improper claims for reimbursement.",
  status="Suspended from city contracting by City Attorney order (March 20, 2025); debarment hearing began August 18, 2025 (per report). Outcome not stated in this report.")
F("Collective Impact", rid, "contract terminated",
  "The report states that the City Attorney's Office filed an order on March 20, 2025 suspending Collective Impact from city contracting and moving to debar the organization for up to five years.",
  "suspending Collective Impact from city contracting and moving to debar the organization for up to five years.",
  status="Suspension (not a final debarment) as of the report date")
F("Total Women Empowerment Inc.", rid, "questioned costs",
  "On September 19, 2023, HRC paid $8,000 toward the nonprofit's \"Queen's Weekend Retreat\" after the nonprofit emailed the HRC director asking for funds. The audit calls this an ineligible use of HRC's Prop Q purchasing authority and faults HRC's process. It makes no finding of wrongdoing by the nonprofit.",
  "On September 19, 2023, HRC paid $8,000 to Total Women Empowerment Inc. to fund its “Queen’s Weekend Retreat,”",
  status="Department (HRC) finding; no nonprofit response reported")
F("Renaissance Parents of Success", rid, "questioned costs",
  "On October 11, 2022, HRC paid $9,995 to Renaissance Parents of Success for a community event for seniors hosted by a different nonprofit (The Village Project). The audit cites this as an example of HRC using Prop Q for program-related payments that are not allowed. The finding is about HRC's purchasing practice.",
  "On October 11, 2022, HRC paid $9,995 to Renaissance Parents of Success for a community event for seniors hosted by The Village Project.",
  status="Department (HRC) finding")
F("The Good Rural", rid, "questioned costs",
  "On February 25, 2022, HRC paid a $9,500 advance to The Good Rural, which had an HRC grant at the time. The audit says departments may pay advances only if the grant agreement explicitly allows them, and that Prop Q should not be used for grant payments. The finding is about HRC's process.",
  "On February 25, 2022, HRC paid a $9,500 advance to The Good Rural, a nonprofit that had a grant with HRC at the time.",
  status="Department (HRC) finding")

# ---------------- Arriba Juntos (2026) ----------------
rid = "ctrl-2026-arriba-juntos"
review(rid, "ctrl_audit_arriba_juntos_2026",
       "Arriba Juntos Generally Complied With Its Grant Agreements With the San Francisco Human Services Agency, Although It Did Not Always Meet Job Enrollment and Placement Goals",
       "2026-04-16", "controller_audit",
       "Audit (done by consultant Sjoberg Evashenk) of 12 Human Services Agency workforce grants to Arriba Juntos, FY2021-22 through FY2023-24. "
       "It found that the nonprofit had the required fiscal controls, was financially healthy, and generally complied, underbilling the City by $282,634. Timesheets and cost allocation need improvement, and it missed enrollment and job-placement targets. "
       "Human Services concurred with all 7 recommendations.")
F("Arriba Juntos", rid, "no findings/cleared",
  "The audit found that Arriba Juntos had the required fiscal controls, generally complied with its Human Services grant requirements, and was financially healthy. Grant costs were generally allowable and supported, and it billed the City $282,634 less than allowed.",
  "Grant salaries, operating expenses, and indirect costs were generally allowable and accurately supported, although Arriba Juntos underbilled $282,634 to the City.",
  status="Generally compliant; 7 recommendations, all concurred by Human Services (open as of report)", aliases=["AJ", "Arriba Juntos - IAI"])
F("Arriba Juntos", rid, "fiscal monitoring finding",
  "The audit found that timesheets (128 tested) did not record time by individual grant, and some costs were allocated in ways that did not match the nonprofit's own allocation method, causing both underbilling and overbilling of particular grants. It also found that the organization met program completion goals but not enrollment or job-placement goals. The auditors note that enrollment depends partly on actions by the City.",
  "The 128 Arriba Juntos timesheets we tested lack sufficient data to fully support allocations among grants.",
  status="Human Services concurred; implementation targeted by June-December 2026", aliases=["AJ"])

# ---------------- Support ("friends of") organizations (2026) ----------------
rid = "ctrl-2026-support-orgs"
review(rid, "ctrl_audit_support_orgs_2026",
       "Support Organizations Must Better Comply With City Agreements to Improve Public Trust and Accountability",
       "2026-06-09", "controller_audit",
       "Audit of two city \"friends of\" support organizations: San Francisco Parks Alliance (Recreation and Park) and Friends of San Francisco Animal Care & Control. It checked their compliance with the MOUs required by Executive Directive 20-02 (2020). "
       "Parks Alliance lacked sufficient documentation for $848,670 (50%) of $1.7 million in sampled payments, most of it from the India Basin Park Project fund. Both groups missed some public-disclosure requirements, and neither had written conflict-of-interest procedures, although no conflicts were found. "
       "Parks Alliance ceased operations in June 2025; a separate joint City Attorney/Controller public integrity assessment of it is ongoing.")
F("San Francisco Parks Alliance", rid, "questioned costs",
  "The audit found that Parks Alliance did not keep sufficient documentation for 35 sampled payments totaling $848,670 (50% of $1,700,038 sampled). That included $838,507 (58% of the sample) from the India Basin Park Project fund, $4,116 from Annual Support, and $6,047 from the Japanese Tea Garden fund. Some invoices lacked detail or approvals, or were missing. "
  "The auditors say poor documentation exposes the organization to potential waste and fraud; they do not find that fraud occurred.",
  "Rec and Park did not ensure that Parks Alliance maintained sufficient documentation to support $848,670 (50%) of $1,700,038 of payments sampled.",
  status="Parks Alliance ceased operations June 3, 2025; separate City Attorney/Controller public integrity assessment ongoing (report expected FY2026-27)",
  aliases=["Parks Alliance", "SF Parks Alliance"])
F("San Francisco Parks Alliance", rid, "compliance finding",
  "Parks Alliance missed some MOU public-disclosure requirements, such as posting Form 990s and 2023 donation reports. As of October 2024 it had not completed its 2023 audited financial report. It lacked written procedures for complying with the MOU's conflict-of-interest rules, but auditors found no conflict-of-interest violations.",
  "Support organizations lacked written processes to ensure compliance with their MOU’s conflict-of-interest requirements, although no conflicts were found.",
  status="Organization defunct", aliases=["Parks Alliance"])
F("Friends of San Francisco Animal Care & Control", rid, "compliance finding",
  "All tested payments were allowed by the MOU. The department (Animal Care and Control) did not always follow its own procedures for documenting spending requests and approvals. For example, 13 transactions totaling $10,890 were missing required request forms. "
  "Friends of SFACC did not post some required financial reports and had no written conflict-of-interest procedures, but auditors found no conflict-of-interest violations. It uploaded the missing disclosures after being notified.",
  "Animal Care and Control did not consistently follow its own procedures for documenting spending requests and approvals, although all tested payments were allowed by the MOU.",
  status="Missing disclosures uploaded after notification; recommendations to departments open", aliases=["Friends of SFACC", "Friends of Animal Care & Control"])
F("Collective Impact", rid, "compliance finding",
  "The audit notes that Collective Impact acted as fiscal sponsor for the Public Defender-linked MAGIC (formerly Mo'MAGIC) program. As of November 2025, the Public Defender had never had a City Attorney- and Controller-approved MOU with Collective Impact, as Executive Directive 20-02 requires. This is a finding about the department's compliance.",
  "But as of November 2025, the Public Defender had never had an MOU with Collective Impact approved by the City Attorney and Controller, as required by Executive Directive 20-02.",
  status="Noted in Exhibit 1 footnote; not an audited organization")

# ---------------- Opportunities for All / JCYC (2026) ----------------
rid = "ctrl-2026-opportunities-for-all-jcyc"
review(rid, "ctrl_audit_opportunities_for_all_2026",
       "The Fragmented Structure of the City's Opportunities for All Program Between JCYC, HRC, and DCYF Led to Deficient Fiscal and Programmatic Activities and Inadequate Oversight of the Grant Agreement",
       "2026-08-26", "controller_audit",
       "Audit (done by consultant Sjoberg Evashenk) of the Opportunities for All youth workforce grant between the City and the Japanese Community Youth Council (JCYC), FY2019-20 through FY2023-24. More than $13 million had been invested as of November 2023. "
       "It found that a confused structure among DCYF, HRC, and JCYC led to weak JCYC fiscal controls: $5.6 million in stipends were paid without verifying eligibility or work performed, and 14 of 20 sampled expenses could not be shown to be appropriate. It also found inadequate oversight by both departments, and that HRC exaggerated participant counts. "
       "JCYC's response says many practices were directed by HRC; the auditors acknowledge HRC's role but hold JCYC responsible as the employer of record.")
F("Japanese Community Youth Council", rid, "questioned costs",
  "As employer of record, JCYC paid $5.6 million in stipends to Opportunities for All participants in 2020-2022 without verifying work eligibility, confirming work was performed, or documenting how amounts were set. "
  "It could not show that 14 of 20 sampled program operating expenses were appropriate, and it invoiced costs up to six months late. The auditors also found that HRC directed the use of stipends. JCYC says the decisions were HRC directives.",
  "In total, JCYC paid $5.6 million in stipend payments to OFA participants without verifying they were eligible to work, without ensuring they had performed the work or completed assignments, and without documenting how the amount paid to each was determined.",
  status="27 recommendations to DCYF and HRC; JCYC disputed responsibility for HRC-directed practices (Appendix C/D)", aliases=["JCYC"])
F("Japanese Community Youth Council", rid, "fiscal monitoring finding",
  "The auditors respond that the confused governance structure is recognized, but JCYC as grantee was still responsible for proper budgets and timely invoices. It lacked the required cost allocation plan to support the indirect rates it charged. The report notes that the City's own fiscal monitoring had not flagged issues with JCYC, which the auditors call an insufficient process.",
  "While HRC may have directed JCYC on the use of stipends including how much to pay participants, JCYC still had responsibilities as the employer of record to review proof of work from participants before making payments.",
  status="Auditor's comments on contractor response", aliases=["JCYC"])

# ---------------- AAACC (2026) ----------------
rid = "ctrl-2026-aaacc"
review(rid, "ctrl_aaacc_2026",
       "Clearer Expectations and Communication Are Key to a Stronger Partnership With the African American Art and Culture Complex",
       "2026-08-31", "controller_audit",
       "Audit of San Francisco Arts Commission grants to the African American Art and Culture Complex (AAACC), including Dream Keeper Initiative regranting duties. "
       "It found management gaps at AAACC: no board treasurer from 2022 to 2024, reliance on consultants, and late or erroneous grant reports. It also found Arts Commission shortcomings: unclear reporting requirements, errors in grant agreements, and giving AAACC new regranting duties without assessing its capacity. "
       "The 12 recommendations are to the Arts Commission.")
F("African American Art and Culture Complex", rid, "compliance finding",
  "The audit found that AAACC had management gaps that led to errors in its grant reporting. It had no board treasurer for at least three years and relied mainly on consultants for fiscal work until January 2024. It submitted 5 of 9 sampled final grant reports late. "
  "The audit also found that the Arts Commission's unclear requirements, grant-agreement errors, and payment delays contributed, and that the Commission gave AAACC Dream Keeper regranting duties without assessing its capacity.",
  "Despite receiving increasing levels of funding and assuming expanded fiscal responsibilities, AAACC did not have a board treasurer for at least three years,",
  status="12 recommendations to the Arts Commission; AAACC response attached (Appendix B)", aliases=["AAACC"])

# ---------------- Charity registry memo (2024) ----------------
rid = "ctrl-2024-charity-registry-31"
review(rid, "ctrl_charity_registry_31_2023",
       "31 City Nonprofit Suppliers Were Not in Good Standing per the State Charitable Trusts Registry as of August 16, 2023",
       "2024-06-12", "controller_monitoring",
       "One-time Controller assessment required by the February 2023 city policy that nonprofit suppliers be in good standing with the California Attorney General's charity registry. "
       "Of 682 city suppliers on the registry with city activity from July 1 to September 6, 2023, 31 were listed as delinquent or revoked (none suspended); 12 had fixed their status by March 26, 2024. "
       "Delinquent usually means required annual filings or fees were late. It is an administrative status, not a finding that funds were misused, and many listed suppliers are national membership or training organizations with small payments.")
reg = [
 ("Bay Area Gators", "Delinquent", "Current", "CHF", "1. Bay Area Gators Delinquent Current CHF - - $200,000 The contract is on hold until supplier cures its status.", []),
 ("Chapin Hall at The Univ. of Chicago", "Delinquent", "Current", "HSA", "After the department was notified that the supplier must register, the supplier became compliant (in September 2023).", ["Chapin Hall"]),
 ("Community Tech Network", "Delinquent", "Current", "HSA, MYR", "The supplier remedied its status in September 2023, and contract modification was certified in October 2023. In February 2024 the supplier again had a delinquent status.", []),
 ("County Behavioral Health Directors Assoc", "Delinquent", "Current – Awaiting Reporting", "DPH", "4. County Behavioral Health Directors Assoc Delinquent Current – Awaiting Reporting DPH $152,277", []),
 ("Cross Cultural Family Center", "Delinquent", "Current – Awaiting Reporting", "CHF", "5. Cross Cultural Family Center Delinquent Current – Awaiting Reporting CHF $86,968 $498,942 $100,821", []),
 ("Deltares USA", "Delinquent", "Delinquent", "PUC", "The prime contractor has not authorized the subcontractor to perform any work", []),
 ("Indochinese Housing", "Delinquent", "Delinquent", "CHF", "7. Indochinese Housing Delinquent Delinquent CHF $83,553 $427,428 $483,267 The department receives regular updates while the supplier is working to cure its status.", []),
 ("International Accreditation Service, Inc", "Revoked", "Revoked", "PUC", "8. International Accreditation Service, Inc Revoked Revoked PUC - $5,500", []),
 ("Lavender Youth Recreation & Info Ctr", "Delinquent", "Current – Awaiting Reporting", "CHF, DPH, HSH, HRC, MYR, PUC, WOM", "9. Lavender Youth Recreation & Info Ctr Delinquent Current – Awaiting Reporting CHF $230,614", ["LYRIC", "Lavender Youth Recreation and Information Center"]),
 ("Nichi Bei Foundation", "Delinquent", "Current – Awaiting Reporting", "ADM", "10. Nichi Bei Foundation Delinquent Current – Awaiting Reporting ADM - $10,000", []),
 ("Race To Zero Waste", "Delinquent", "Delinquent", "ENV, REC", "The department instructed the supplier to stop work until its status is resolved.", []),
 ("SF Community Clinic Consortium", "Delinquent", "Current – Awaiting Reporting", "DPH", "The supplier received an extension to file its annual IRS Form 990, which registry requires, thus delaying the update of its registration status.", ["San Francisco Community Clinic Consortium"]),
 ("San Francisco Estuary Institute", "Delinquent", "Current – Awaiting Reporting", "ADM, REC", "13. San Francisco Estuary Institute Delinquent Current – Awaiting Reporting ADM - $22,000 $428,000", []),
 ("Worker Rights Consortium", "Delinquent", "Current – Awaiting Reporting", "ADM", "The supplier is no longer delinquent. CSA verified that its status was changed to current in December 2023.", []),
 ("Sojourn to the Past", "Delinquent", "Current – Awaiting Reporting", "DAT, POL", "On February 1, 2024, CSA confirmed the supplier had status of current.", []),
 ("Civic", "Delinquent", "Delinquent", "DPW", "16. Civic Delinquent Delinquent DPW $432,684 - - The department no longer works with the supplier.", []),
 ("Compasspoint Nonprofit Services", "Delinquent", "Delinquent", "HSH", "The contract was an incorrect entry, which the department subsequently cancelled in the City’s financial and procurement system.", ["CompassPoint"]),
 ("Grattan After School Program", "Delinquent", "Current – Awaiting Reporting", "CHF", "18. Grattan After School Program Delinquent Current – Awaiting Reporting CHF $3,553 - $55,994 The supplier no longer has an active contract with the department.", []),
 ("Mercy Midtown Inc", "Delinquent", "Suspended", "MYR", "Mercy Midtown Inc was created by Mercy Housing solely for their work on the Midtown Apartments and has not worked with the department since 2019.", []),
 ("SF Mental Health Educational Funds", "Delinquent", "Delinquent", "DPH", "CSA verified that as of May 2024 the contract was cancelled.", []),
 ("Americans for the Arts", "Delinquent", "Suspended", "ART", "21. Americans for the Arts Delinquent Suspended ART $1,000", []),
 ("California Resource Recovery Association", "Delinquent", "Delinquent", "ENV", "22. California Resource Recovery Association Delinquent Delinquent ENV $60", []),
 ("International Public Mgmnt Assoc for HR", "Revoked", "Revoked", "PUC", "23. International Public Mgmnt Assoc for HR Revoked Revoked PUC $1,000", []),
 ("JSTOR", "Delinquent", "Suspended", "LIB", "According to the Public Library (Library), the supplier is part of the 501(c)(3) Ithaka Harbors, Inc.", ["Ithaka Harbors, Inc."]),
 ("KPOO -- FM Radio", "Delinquent", "Suspended", "PUC", "25. KPOO -- FM Radio Delinquent Suspended PUC $342", ["KPOO"]),
 ("Mosquito & Vector Control Assoc of Calif", "Delinquent", "Delinquent", "DPH", "26. Mosquito & Vector Control Assoc of Calif Delinquent Delinquent DPH $2,600", []),
 ("National Alliance for Youth Sports Inc", "Revoked", "Revoked", "REC", "27. National Alliance for Youth Sports Inc Revoked Revoked REC - $1,000", []),
 ("National Safety Council", "Revoked", "Revoked", "AIR, MTA, REC", "28. National Safety Council Revoked Revoked AIR - $3,994", []),
 ("OCLC, INC", "Delinquent", "Suspended", "LIB", "City pays supplier for software licensing fees for Library, so is not providing charitable donations or grants.", ["OCLC"]),
 ("C5 Children's School", "Delinquent", "Delinquent", "ADM, DPH", "According to the Department of Public Health, solicitation was cancelled and no contract was issued.", []),
 ("OCT Water Quality Academy", "Delinquent", "Delinquent", "REC", "31. OCT Water Quality Academy Delinquent Delinquent REC - - $6,000", []),
]
for name, s1, s2, depts, q, al in reg:
    F(name, rid, "charity registry noncompliance",
      f"On August 16, 2023, the California Attorney General's charity registry listed this city supplier as '{s1}' (city client department codes: {depts}). By March 26, 2024 its status was '{s2}'. "
      "A delinquent or revoked status means the organization was out of compliance with state registration or reporting rules. It is not a finding that city funds were misused. See the memo's Exhibit 1 for payments and department comments.",
      q, status=f"Registry status on 3/26/2024: {s2}", aliases=al)

# ---------------- Chapter 12G political activity memo (2024) ----------------
rid = "ctrl-2024-12g-political-activity"
review(rid, "ctrl_12g_political_2024",
       "All 20 Selected Recipients of City Funds—10 in FY 2019-20 and 10 in FY 2020-21—Complied With the SF Administrative Code, Chapter 12G, by Not Using the Funds for Political Activity",
       "2024-07-24", "controller_monitoring",
       "Required annual Controller assessment (done by consultant Sjoberg Evashenk) of whether selected recipients of city funds used them for political campaign activity, which Administrative Code Chapter 12G prohibits. "
       "Twenty entities (19 nonprofits and 1 for-profit) were chosen partly because their names or addresses matched campaign contribution data. All 20 were found to have complied, and none used city funds for political activity.")
pol = [("Circus Center", "$50,173", "FY2019-20"), ("First Voice", "$132,590", "FY2019-20"), ("Flyaway Productions", "$90,150", "FY2019-20"),
       ("Homeless Prenatal Program", "$6,976,944", "FY2019-20"), ("Intersection for the Arts", "$1,648,664", "FY2019-20"),
       ("Jewish Family and Children’s Services", "$447,525", "FY2019-20"), ("Livable City", "$657,980", "FY2019-20"),
       ("Lower Polk Community Benefit District", "$1,219,955", "FY2019-20"), ("Rafiki Coalition for the Health & Wellness", "$1,628,063", "FY2019-20"),
       ("TODCO", "$590,481", "FY2019-20"), ("Centro Latino de San Francisco", "$1,316,522", "FY2020-21"),
       ("Children’s Council of San Francisco", "$86,421,717", "FY2020-21"), ("Homey", "$558,012", "FY2020-21"),
       ("Instituto Familiar De La Raza", "$11,987,652", "FY2020-21"), ("Larkin Street Youth Services", "$20,344,946", "FY2020-21"),
       ("Mission Neighborhood Centers", "$14,296,630", "FY2020-21"), ("Mujeres Unidas Y Activas", "$647,807", "FY2020-21"),
       ("Renaissance Entrepreneurship", "$553,142", "FY2020-21"), ("Wah Mei School", "$151,924", "FY2020-21")]
alias = {"Homey": ["Homies Organizing the Mission to Empower Youth", "HOMEY"], "Jewish Family and Children’s Services": ["Jewish Family and Children's Services"],
         "Children’s Council of San Francisco": ["Children's Council of San Francisco"], "Renaissance Entrepreneurship": ["Renaissance Entrepreneurship Center"],
         "Rafiki Coalition for the Health & Wellness": ["Rafiki Coalition for Health and Wellness"]}
for name, amt, fy in pol:
    F(name, rid, "no findings/cleared",
      f"Selected for the Chapter 12G political-activity assessment for {fy} (city funds received: {amt}). The assessment found that it complied, meaning it did not use city funds for political campaign activity.",
      "They did not use city funds to participate in, support, or attempt to influence a political campaign for any candidate or ballot measure.",
      status="Complied", aliases=alias.get(name, []))

# ---------------- Nonprofit public reporting (2024) ----------------
review("ctrl-2024-nonprofit-public-reporting", "ctrl_nonprofit_public_reporting", "Assessment of Public Reporting on Nonprofit Contracting",
       "2024-12-09", "city_policy",
       "Memo required by Ordinance 055-24 reviewing what information the city publishes about nonprofit contracting. In FY2023-24 the city contracted with more than 700 nonprofits and spent over $1.5 billion. "
       "It found that big-spending departments publish several kinds of reports but often do not separate out nonprofit work, and that central tools exist but are hard to use. It recommends better search, data, and dashboards. It has no findings about specific organizations.")

# ---------------- verify quotes, set pages ----------------
bad = 0
for f in findings:
    q = norm(f["quote"]); stem = R[f["review_id"]]
    if len(q.split()) > 40: print("TOO LONG", f["org_name"], len(q.split())); bad += 1
    hits = [p for p, t in sorted(pages(stem).items()) if q in t]
    if not hits: print("NOT FOUND", f["org_name"], "|", q[:90]); bad += 1
    else: f["page"] = hits[0]
out = base / "partials" / "group_b.json"
out.write_text(json.dumps({"reviews": reviews, "org_findings": findings}, ensure_ascii=False, indent=1))
print(len(reviews), "reviews;", len(findings), "findings;", bad, "problems")
