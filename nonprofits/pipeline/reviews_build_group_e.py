"""Build data/reviews/partials/group_e.json (news investigations) and verify every quote
against the cached article text in data/reviews/news_cache/ (normalized substring check)."""
import json, re, pathlib, unicodedata, sys
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
cache = base / "news_cache"
ACC = "2026-09-26"

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()

def meta(key):
    t = (cache / f"{key}.txt").read_text()
    m = dict(re.findall(r"^(URL|TITLE|DATE): (.*)$", t, re.M))
    return m, t

R = []   # reviews
F = []   # findings
def review(key, rid, publisher, summary, title=None):
    m, _ = meta(key)
    ttl = title or re.sub(r"\s*[|-]\s*(KQED|48 hills)\s*$", "", m["TITLE"]).strip()
    R.append(dict(id=rid, title=ttl, publisher=publisher, date=m["DATE"][:10], url=m["URL"], type="news",
                  summary=summary, accessed_date=ACC, _key=key))
def finding(rid, org, aliases, ftype, text, quote, status=None, ein=None):
    rv = next(r for r in R if r["id"] == rid)
    F.append(dict(org_name=org, org_name_aliases=aliases, ein=ein, review_id=rid, finding_type=ftype,
                  finding=text, quote=quote, page=None, status=status, url=rv["url"], _key=rv["_key"]))

# ---------------- United Council of Human Services ----------------
review("kq-2026-ceo-enriched", "news-2026-kqed-uchs-charges", "KQED",
  "KQED reported that the former longtime CEO of United Council of Human Services (UCHS), a Bayview homelessness nonprofit, was charged with nine felonies over alleged misappropriation and theft of public funds. The article ties the criminal investigation to a 2022 Controller audit of UCHS and a City Attorney referral. The charges are allegations; no conviction is reported.")
finding("news-2026-kqed-uchs-charges", "United Council of Human Services", ["UCHS"], "criminal charges",
  "KQED reported (Feb. 2026) that UCHS's former CEO of two decades faces nine felony charges; prosecutors allege she misappropriated $1.2 million and stole $91,000 in public funds, and that $1.4 million withdrawn from UCHS accounts remains unaccounted for. These are charges against the former executive, not findings of guilt. No response from the defendant is quoted in the article.",
  "The former head of a San Francisco homelessness organization appeared in court on Tuesday after being accused of misappropriating $1.2 million and stealing $91,000 in public funds",
  status="Charges pending as of article date; arraignment set for March 9, 2026 (per article).")
finding("news-2026-kqed-uchs-charges", "Heluna Health", ["UCHS fiscal sponsor"], "news allegation",
  "KQED reported that prosecutors describe an 'unusual' compensation method for UCHS's former CEO that ran through UCHS's fiscal sponsor, Heluna Health. The article does not allege wrongdoing by Heluna Health itself; it is named only as the fiscal sponsor through which part of the pay flowed.",
  "She was paid more than $467,000 through an “unusual” compensation method involving the nonprofit’s fiscal sponsor, Heluna Health",
  status="Context only; no allegation against Heluna Health stated.")

# ---------------- Providence Foundation ----------------
review("kq-2024-providence-nepotism", "news-2024-kqed-providence-debarment", "KQED",
  "KQED reported that the City Attorney suspended Providence Foundation of San Francisco, an HSH-funded homeless services provider, from new city funding and began debarment proceedings after an investigation found about $105,000 in falsified maintenance invoices and nepotism-related contract violations. The foundation's attorney called the allegations baseless at the time.")
finding("news-2024-kqed-providence-debarment", "Providence Foundation of San Francisco", ["Providence Foundation"], "news allegation",
  "KQED reported (May 2024) that a City Attorney investigation found Providence falsified about $105,000 in invoices for shelter maintenance work at the Oasis Hotel that was never done, and violated its contracts despite warnings over nepotism. The City Attorney suspended the group from new contracts and started debarment proceedings. Providence's attorney called the allegations \"unfounded and baseless\" and said it would take remedial action where appropriate.",
  "A San Francisco homeless services provider accused of falsifying $105,000 in invoices is cut off from future city funding, the city attorney’s office said",
  status="Suspended from new city funding; debarment proceedings started (May 2024). See 2025 settlement.")
review("kq-2024-providence-stripped", "news-2024-kqed-providence-contract", "KQED",
  "KQED reported that HSH would not renew Providence Foundation's roughly $600,000 contract to manage a storage facility for unhoused people after the fraud allegations, while its other HSH contracts continued under review. The foundation had denied the allegations.")
finding("news-2024-kqed-providence-contract", "Providence Foundation of San Francisco", ["Providence Foundation"], "contract terminated",
  "KQED reported (May 30, 2024) that HSH confirmed Providence would no longer manage a storage facility for unhoused people, a nearly $600,000 contract ending June 30, 2024 that would not be renewed; Providence continued to run five other HSH programs while the city weighed their future.",
  "Providence Foundation of San Francisco will no longer manage a storage facility for unhoused people — a nearly $600,000 contract",
  status="Contract not renewed after June 30, 2024; interim executive director working with HSH (per article).")
review("kq-2025-homeless-nonprofit-1m-fraud", "news-2025-kqed-providence-settlement", "KQED",
  "KQED reported that the City Attorney reached a $1 million settlement with Providence Foundation of San Francisco, in which the nonprofit admitted wrongdoing, removed employees involved, and reimbursed the city for fraudulent invoices. The City Attorney and the nonprofit's interim leader both described the settlement as a turnaround.")
finding("news-2025-kqed-providence-settlement", "Providence Foundation of San Francisco", ["Providence Foundation"], "news allegation",
  "KQED reported (Aug. 2025) that Providence agreed to a $1 million settlement with the City Attorney, admitted wrongdoing, removed employees who took part in the misconduct, reimbursed the city for fraudulent invoices, and paid workers denied holiday pay. The City Attorney called it an example of an organization turning itself around; the interim executive director cited 'sweeping reforms'.",
  "Under the agreement, Providence Foundation of San Francisco admitted wrongdoing, removed employees who participated in the misconduct, reimbursed the city for fraudulent invoices",
  status="Resolved by $1 million settlement (Aug. 2025); new board and interim leadership (per article).")

# ---------------- HomeRise ----------------
review("kq-2024-homerise-audit", "news-2024-kqed-homerise-audit", "KQED",
  "KQED covered the April 2024 Controller audit of HomeRise, which operates about 1,500 supportive housing units. The audit found wasteful spending and mismanagement; HomeRise called many findings factually incorrect or misleading. The Controller recommended stronger oversight rather than cutting off funding.")
finding("news-2024-kqed-homerise-audit", "HomeRise", ["Community Housing Partnership"], "news allegation",
  "KQED reported on the Controller's April 2024 audit, which called HomeRise 'careless and irresponsible' with taxpayer money, citing $12,500 on a social event and $200,000 in bonuses. HomeRise said the audit 'presents a false picture'. The Controller urged stronger oversight rather than ending funding, and new senior leadership had begun addressing issues (per article).",
  "The report details mismanagement and wasteful spending by the nonprofit, HomeRise, including $12,500 spent on a social event and $200,000 in bonuses",
  status="HomeRise disputed many findings; new leadership in place; Controller recommended strengthened oversight (per article).")

# ---------------- SF SAFE ----------------
review("ml-2024-02-sfsafe-rent", "news-2024-missionlocal-sfsafe-rent", "Mission Local",
  "Mission Local reported that SF SAFE, an SFPD-affiliated nonprofit, allegedly owed $445,306 in back rent, and that SFPD had ended its contract with the group after a January 2024 Controller audit found $79,655 in grant funds spent on unauthorized expenses. The former director did not respond to requests for comment.")
finding("news-2024-missionlocal-sfsafe-rent", "SF SAFE", ["San Francisco SAFE", "Safety Awareness for Everyone"], "contract terminated",
  "Mission Local reported (Feb. 2024) that the police department broke its contract with SF SAFE after a January Controller audit showed the nonprofit spent $79,655 in grant funds on unauthorized expenses (such as a staff trip to Lake Tahoe, limo service, and luxury gifts). A landlord notice claimed $445,306 in unpaid rent (the landlord declined to comment).",
  "Yesterday, the police department announced that it broke its contract with SF SAFE after a series of revelations over the past two months.",
  status="Organization dissolved in 2024 (per later reporting).")
review("ml-2024-02-sfsafe-workers", "news-2024-missionlocal-sfsafe-workers", "Mission Local",
  "Mission Local reported that former SF SAFE workers planned to file a complaint with the city's Office of Labor Standards Enforcement over unpaid wages and benefits after the nonprofit closed in January 2024. Workers described months of irregular pay.")
finding("news-2024-missionlocal-sfsafe-workers", "SF SAFE", ["San Francisco SAFE"], "news allegation",
  "Mission Local reported (Feb. 2024) that former SF SAFE employees alleged unpaid wages and missing benefits and planned a labor complaint; the nonprofit fired its executive director and closed on Jan. 24, 2024, and the DA announced a criminal investigation of the former director.",
  "at least half a dozen former SF SAFE workers will go to City Hall for an appointment with the Office of Labor Standards Enforcement to file a complaint about unpaid wages and benefits",
  status="Organization closed Jan. 24, 2024.")
review("ml-2024-07-sfsafe-worthy-charged", "news-2024-missionlocal-sfsafe-charges", "Mission Local",
  "Mission Local reported that SF SAFE's former executive director was arrested and charged with 34 felonies, including misappropriation of public money and submitting fraudulent invoices to a city department. The charges followed a Controller audit and a board discovery that bank accounts were nearly empty. These are criminal allegations.")
finding("news-2024-missionlocal-sfsafe-charges", "SF SAFE", ["San Francisco SAFE"], "criminal charges",
  "Mission Local reported (July 2024) that SF SAFE's former head was charged with 34 felony counts, accused of illegally misusing more than $700,000, including misappropriation of public money and fraudulent invoices to a city department. These are charges, not convictions.",
  "Worthy is accused of illegally misusing more than $700,000 during her tenure with SF SAFE.",
  status="Charges pending as of article date.")

# ---------------- Collective Impact / HRC / Dream Keeper ----------------
review("48h-2024-09-collective-impact-salary", "news-2024-48hills-collective-impact", "48 Hills",
  "48 Hills reported, from IRS filings, that Collective Impact's executive director's salary rose from $119,000 to $148,000 after the Human Rights Commission began sending the group $1.5 million in grants, while the HRC director who approved the grants shared a home with him. The article notes such raises are not unusual for a growing nonprofit.")
finding("news-2024-48hills-collective-impact", "Collective Impact", [], "news allegation",
  "48 Hills reported that Collective Impact's revenue grew from about $2.8 million to more than $7.4 million after it became a Dream Keeper grantee, and its director's salary rose nearly 25 percent, from $119,000 to $148,000. The article says such a raise is not unusual and 'by no means out of line'. The concern it raises is the undisclosed shared household with the HRC director who signed the grants.",
  "It’s not unusual for an executive director to get a salary bump as a group expands",
  status="See later City Attorney debarment case and 2026 criminal charges.")
review("ml-2024-09-hrc-controller", "news-2024-missionlocal-hrc-controller", "Mission Local",
  "Mission Local reported that the Controller took over accounting operations at the Human Rights Commission after its director resigned amid reports about spending and about $1.5 million directed to Collective Impact, whose director shared her home. The Controller and City Attorney were investigating HRC and the Dream Keeper Initiative.")
finding("news-2024-missionlocal-hrc-controller", "Collective Impact", [], "news allegation",
  "Mission Local reported (Sept. 2024), citing the SF Standard, that the HRC director had directed about $1.5 million to Collective Impact, whose director lived at the same address and co-owned a car with her.",
  "the San Francisco Standard noted that Davis had directed some $1.5 million in funding to the nonprofit Collective Impact",
  status="City investigation opened; see later reporting.")
review("kq-2025-hrc-nonprofit-shutdown", "news-2025-kqed-collective-impact-debarment", "KQED",
  "KQED reported on the City Attorney's effort to debar Collective Impact for five years, alleging it misappropriated public funds to give gifts to the former HRC director and her son, and billed a Martha's Vineyard trip to an OEWD grant. Collective Impact's attorneys said the city could not meet the willful-misconduct standard and that debarment would force closure.")
finding("news-2025-kqed-collective-impact-debarment", "Collective Impact", [], "news allegation",
  "KQED reported (Aug. 2025) that the City Attorney alleged Collective Impact paid more than $19,000 in graduate tuition for the HRC director's son and $18,400 toward her personal work, and falsely billed conference travel to an OEWD Educational Pathways grant. It sought a five-year debarment. The nonprofit said it could not be shown to have engaged in willful misconduct and would have to shut down without city funds.",
  "Collective Impact is accused of paying more than $19,000 in graduate school tuition for Davis’ son, $18,400 to support her personal work",
  status="Suspended from city funding since Oct. 2024; debarment hearing pending (per article).")
review("kq-2025-embroiled-green-light", "news-2025-kqed-collective-impact-ruling", "KQED",
  "KQED reported that an administrative hearing officer found no preponderance of evidence of willful misconduct by Collective Impact and lifted its suspension from city funding. The City Attorney said it would appeal.")
finding("news-2025-kqed-collective-impact-ruling", "Collective Impact", [], "no findings/cleared",
  "KQED reported (Oct. 2025) that the hearing officer did not find the preponderance of evidence needed to prove willful misconduct and lifted Collective Impact's suspension. The City Attorney called the result 'absurd' and planned to appeal. The nonprofit's board called the accusations speculative.",
  "The administrative ruling on Wednesday by Officer Andrea McGary did not find the “preponderance of evidence” required to prove willful misconduct by Collective Impact",
  status="Suspension lifted Oct. 8, 2025; City Attorney appeal planned (per article).")
review("ml-2025-10-nonprofit-reprieve", "news-2025-missionlocal-collective-impact-reprieve", "Mission Local",
  "Mission Local reported on the same ruling restoring Collective Impact's eligibility for city funds, including the City Attorney's objections to how the hearing officer reached her decision. Collective Impact said the ruling showed the accusations were unsupported, and its director announced he was stepping down.")
finding("news-2025-missionlocal-collective-impact-reprieve", "Collective Impact", [], "no findings/cleared",
  "Mission Local reported (Oct. 2025) that the hearing officer restored Collective Impact's ability to receive city contracts, while the City Attorney called the process irregular and planned to appeal. Collective Impact said the decision showed the accusations were 'speculative and unsupported by the evidence'.",
  "We are deeply gratified by today’s decision, which acknowledges that the accusations against Collective Impact were speculative and unsupported by the evidence",
  status="Eligibility restored pending City Attorney appeal; executive director stepped down (per article).")
review("ml-2026-03-davis-spingola-arrested", "news-2026-missionlocal-davis-spingola-charges", "Mission Local",
  "Mission Local reported that the former HRC director and Collective Impact's former executive director were arrested and charged; she faces 17 felonies and two misdemeanors, and he faces four felony counts of aiding and abetting. The DA stressed the charges are allegations to be proven in court; both have denied intentional wrongdoing.")
finding("news-2026-missionlocal-davis-spingola-charges", "Collective Impact", [], "criminal charges",
  "Mission Local reported (March 2026) that Collective Impact's former executive director was charged with four felony counts of aiding and abetting the former HRC director, whose charges reflect about $350,000 in allegedly misappropriated Prop Q and Dream Keeper funds. The DA said the charges 'will ultimately be proven or disproven in court'. Both denied intentional wrongdoing.",
  "Spingola is facing four felony counts of aiding and abetting Davis.",
  status="Criminal case pending as of article date.")

# ---------------- Urban Ed Academy (Jones-founded) ----------------
review("ml-2025-03-bidding", "news-2025-missionlocal-urban-ed-academy", "Mission Local",
  "Mission Local covered a March 2025 Controller/City Attorney report finding that HRC and OEWD manipulated or disregarded competitive rules in grants to Urban Ed Academy, a nonprofit founded by Dwayne Jones. The article says Urban Ed Academy had new leadership and was cooperating.")
finding("news-2025-missionlocal-urban-ed-academy", "Urban Ed Academy", ["Urban Ed Academy, Inc."], "news allegation",
  "Mission Local reported that the Controller found HRC and OEWD disregarded competitive rules to award grants to Urban Ed Academy despite lower scores, and OEWD raised its grant 173 percent (from $473,000 to $1,192,500) despite below-standard performance. The report also said the nonprofit gave the HRC director a $5,500 portrait before a contract of up to $270,000. Per the article, Urban Ed Academy has new leadership and is fully cooperating with the assessment.",
  "Despite the nonprofit falling below performance standards, the office increased its grant amount 173 percent, from $473,000 to $1,192,500.",
  status="New leadership; cooperating with the assessment (per article). The article also says city grants 'with the organization' ended by Jan. 2025, but the sentence is ambiguous about which nonprofit it means.")

# ---------------- Community Challenge Grant / Jones entities ----------------
review("ml-2023-08-rdj-charges", "news-2023-missionlocal-rdj-charges", "Mission Local",
  "Mission Local reported that the DA charged the director of the city's Community Challenge Grant Program and consultant Rudolph Dwayne Jones with corruption, alleging she steered 23 contracts worth over $1.4 million to Jones-controlled entities between 2016 and 2020. Both later pleaded not guilty.")
finding("news-2023-missionlocal-rdj-charges", "Rudolph Dwayne Jones-controlled entities (incl. RDJ Enterprises)", ["RDJ Enterprises"], "criminal charges",
  "Mission Local reported (Aug. 2023) that the DA alleged the Community Challenge Grant director directed some 23 contracts worth over $1.4 million to Jones-controlled entities between 2016 and 2020, in which she had a financial stake. Jones was charged with misappropriation, bribery, and aiding a conflict of interest. These are charges; RDJ Enterprises is a consulting firm, and not every Jones-related entity is a nonprofit.",
  "Henriquez allegedly directed some 23 contracts to Jones-controlled entities, in which she had a financial stake, between 2016 and 2020.",
  status="Both defendants pleaded not guilty (per Mission Local, Oct. 2023).")
review("ml-2023-10-ccg-scores", "news-2023-missionlocal-ccg-scores", "Mission Local",
  "Mission Local covered the Controller's October 2023 finding that the 2023 Community Challenge Grant solicitation (about $3 million to 28 organizations) was deeply flawed and must be redone. Findings included possibly fabricated panel scores and a conflicted panelist tied to a Jones entity.")
finding("news-2023-missionlocal-ccg-scores", "Rudolph Dwayne Jones-controlled entities (incl. RDJ Enterprises)", ["RDJ Enterprises"], "news allegation",
  "Mission Local reported that the Controller found one of two actual scoring panelists worked for a Jones-controlled entity, and documented a forged Housing Authority support letter in an application for a Jones-controlled entity.",
  "in one instance, a forged letter of support from the Housing Authority in an application for a Jones-controlled entity",
  status="Controller recommended redoing the 2023 solicitation.")

# ---------------- SF Parks Alliance ----------------
review("kq-2025-parks-audit-call", "news-2025-kqed-parks-alliance-freeze", "KQED",
  "KQED reported that the mayor paused city grants to the San Francisco Parks Alliance and the City Attorney and Controller opened a public integrity review. This followed reports that the nonprofit had admitted misspending at least $3.8 million in restricted funds and a DA criminal investigation.")
finding("news-2025-kqed-parks-alliance-freeze", "San Francisco Parks Alliance", ["SF Parks Alliance", "Parks Alliance"], "news allegation",
  "KQED reported (May 2025) that the mayor directed departments to pause outstanding grants and make no new agreements with the Parks Alliance, and that the City Attorney and Controller announced a public integrity review. The nonprofit had recently admitted misspending at least $3.8 million.",
  "Mayor Daniel Lurie directed city departments to pause any outstanding grants and not enter into any new agreements with the San Francisco Parks Alliance",
  status="City funding paused May 2025; organization later dissolved.")
review("kq-2025-parks-alliance-shut", "news-2025-kqed-parks-alliance-shutdown", "KQED",
  "KQED reported that the Parks Alliance board voted to begin shutting down after leaders admitted misspending at least $3.8 million in restricted funds to cover operating costs. It was fiscal sponsor to about 80 community groups, and some of their staff received layoff notices.")
finding("news-2025-kqed-parks-alliance-shutdown", "San Francisco Parks Alliance", ["SF Parks Alliance"], "news allegation",
  "KQED reported (June 2025) that the Parks Alliance moved to shut down after its leaders admitted misspending at least $3.8 million in restricted funds to cover operating costs. The city had launched civil and criminal investigations and suspended its funding. About 80 fiscally sponsored community groups were affected.",
  "its leaders recently admitted to misspending at least $3.8 million in restricted funds to cover its operating costs",
  status="Board voted to shut down (late May 2025).")
review("ml-2025-07-parks-alliance-hearing", "news-2025-missionlocal-parks-alliance-hearing", "Mission Local",
  "Mission Local covered a Board of Supervisors oversight hearing where subpoenaed former Parks Alliance leaders testified. The former CEO and treasurer said they did not know about years of money mismanagement until mid-2024. A balance sheet showed about $5.4 million owed to community groups.")
finding("news-2025-missionlocal-parks-alliance-hearing", "San Francisco Parks Alliance", ["SF Parks Alliance"], "news allegation",
  "Mission Local reported (July 2025) that the Parks Alliance is being investigated for misspending at least $3.8 million earmarked for specific park projects, and that a balance sheet shown at the hearing indicated it owed community groups $5.4 million ('at least that', per its last CEO). Former leaders said they were unaware of the mismanagement until May or June 2024. The Port said it came up almost $2 million short on a joint project.",
  "Walton handed Ogilvie a balance sheet that indicated that the Park Alliance currently owes San Francisco community groups $5.4 million.",
  status="Organization dissolved; DA and City Attorney inquiries reported.")

# ---------------- SF Zoological Society ----------------
review("kq-2026-zoo-audit", "news-2026-kqed-zoo-audit-loan", "KQED",
  "KQED reported that the San Francisco Zoological Society, the nonprofit that manages the city-owned zoo, sought an $8.5 million city loan days after a Budget and Legislative Analyst audit found it spent nearly $12 million in unapproved funding on capital projects. The zoo's new CEO cited falling attendance and rising costs.")
finding("news-2026-kqed-zoo-audit-loan", "San Francisco Zoological Society", ["San Francisco Zoo", "SF Zoo"], "news allegation",
  "KQED reported (May 2026) that a Budget and Legislative Analyst audit found the zoo spent nearly $12 million in unapproved funding on capital improvement projects. The zoo's new CEO said attendance had fallen since the pandemic while operating costs rose by about $3 million.",
  "A recent city audit found the zoo spent nearly $12 million in unapproved funding on capital improvement projects.",
  status="New CEO since Feb. 2026; loan proposed.")
review("kq-2026-zoo-bailout", "news-2026-kqed-zoo-loan-approved", "KQED",
  "KQED reported that supervisors approved an $8.5 million loan to the San Francisco Zoological Society, with conditions including a five-year strategic plan, at least 10% expense cuts, and quarterly reporting.")
finding("news-2026-kqed-zoo-loan-approved", "San Francisco Zoological Society", ["San Francisco Zoo"], "corrective action",
  "KQED reported (May 19, 2026) that supervisors approved an $8.5 million loan, and zoo officials agreed to conditions: a five-year strategic plan, cutting expenses by at least 10%, and quarterly reports on attendance and other metrics.",
  "zoo officials agreed to a series of conditions, including developing a five-year strategic plan, cutting expenses by at least 10% and producing quarterly reports",
  status="Loan approved with conditions (May 2026).")

# ---------------- SF Pretrial Diversion Project ----------------
review("ml-2026-06-pretrial-challenge", "news-2026-missionlocal-pretrial-court-data", "Mission Local",
  "Mission Local reported that San Francisco Superior Court data questioned the claimed success of the SF Pretrial Diversion Project, as the court moved to shift pretrial services to its Adult Probation Department. The nonprofit's CEO said the difference reflects methodology, not results.")
finding("news-2026-missionlocal-pretrial-court-data", "San Francisco Pretrial Diversion Project", ["SF Pretrial"], "news allegation",
  "Mission Local reported (June 2026) that court data found about 70 percent of SF Pretrial clients in 2025 were not re-arrested, versus the sheriff's figure that 94 percent picked up no new charge. The court called earlier comparisons 'misleading'. SF Pretrial's CEO said the difference reflects methodology (arrests vs. charges), not a discrepancy in results. This is a dispute over performance measurement, not an allegation of misconduct.",
  "The court’s findings reflect a difference in methodology rather than a discrepancy in results, SF Pretrial CEO David Mauroff argued.",
  status="Court planned to end partnership; budget decision pending (per article).")
review("ml-2026-09-pretrial-closing", "news-2026-missionlocal-pretrial-closing", "Mission Local",
  "Mission Local reported that the SF Pretrial Diversion Project is winding down and will close Nov. 13, 2026, after the city and courts decided to end its contract. Services are moving to a new Adult Probation division that will not be ready until January 2027.")
finding("news-2026-missionlocal-pretrial-closing", "San Francisco Pretrial Diversion Project", ["SF Pretrial"], "contract terminated",
  "Mission Local reported (Sept. 2026) that the city and courts decided to cut SF Pretrial's annual contract by fiscal year-end, moving services to a new Adult Probation division ($12.7 million a year). The nonprofit stopped taking new clients in its two main programs in August and will close Nov. 13, 2026. The article frames this as a policy decision, not a finding of misconduct.",
  "started winding down this summer after the city and courts decided to cut the organization’s annual contract by the end of the fiscal year",
  status="Closing Nov. 13, 2026 (per article).")

# ---------------- Five Keys ----------------
review("ml-2026-08-shelter-employees-charged", "news-2026-missionlocal-five-keys-shelter-staff", "Mission Local",
  "Mission Local reported that two employees of a Bayview navigation center run by Five Keys were charged as accessories after allegedly helping a man suspected of shooting a police officer. The charges concern the individual employees, not the organization; Five Keys' CEO said he hoped the allegations were not true.")
finding("news-2026-missionlocal-five-keys-shelter-staff", "Five Keys Schools and Programs", ["Five Keys", "Five Keys Charter School and Programs"], "news allegation",
  "Mission Local reported (Aug. 2026) that the DA charged two shelter employees at a Five Keys-run navigation center with accessory after the fact and obstruction. The charges are against individual staff, not the nonprofit. Five Keys' CEO called the allegations 'deeply troubling' and 'incredibly surprising', and relayed staff accounts that they tried to placate an armed intruder and evacuate clients.",
  "“I hope they’re not true,” said Steve Good, the CEO of Five Keys, the nonprofit that runs the shelter, of the allegations last week.",
  status="Charges against individual employees pending; no allegation against the organization reported.")

# ---------------- Baker Places / Providence via BLA coverage ----------------
review("ml-2025-01-monitoring-third", "news-2025-missionlocal-bla-nonprofit-compliance", "Mission Local",
  "Mission Local covered a January 2025 Budget and Legislative Analyst report finding that 61 of 199 nonprofits in the city's fiscal monitoring program did not conform with city standards, most often because of late or incomplete audited financial statements. The article notes non-compliance does not mean nonprofits are failing to deliver services.")
finding("news-2025-missionlocal-bla-nonprofit-compliance", "Baker Places", ["PRC and Baker Places, Inc.", "Positive Resource Center"], "news allegation",
  "Mission Local, citing the BLA report, said two Baker Places residential treatment programs (Jo Ruffin and Grove Street House) had delivered services successfully but closed in 2021 because of the operator's 'financial insolvency'. Baker Places later moved from 'red flag' status to 'elevated concern' status.",
  "The Jo Ruffin residential treatment program and the Grove Street House crisis residential treatment center had successfully provided service, but were closed due to the “financial insolvency” of their operator, Baker Places, in 2021.",
  status="Moved from red flag to elevated concern status (per report as cited).")
finding("news-2025-missionlocal-bla-nonprofit-compliance", "Providence Foundation of San Francisco", ["Providence Foundation"], "news allegation",
  "Mission Local, citing the BLA report, said Providence Foundation was debarred from seeking new contracts in May 2024 over allegations of falsified invoices. (Other reporting describes a May 2024 suspension plus debarment proceedings, later resolved by a 2025 settlement.)",
  "the homeless nonprofit Providence Foundation, in May 2024, was debarred from seeking new contracts over allegations of falsified invoices",
  status="See 2025 settlement.")

# ---------------- context-only reviews (no org findings) ----------------
review("kq-2024-breed-scrutiny-grantees", "news-2024-kqed-breed-grantee-directive", "KQED",
  "KQED reported on Mayor Breed's September 2024 directive tightening oversight of city grantees. It requires grant-making staff to follow the Controller's standards for nonprofit agreements (performance measures, fiscal monitoring, record retention) and calls for conflict-of-interest guidelines for grant selection panels.")
review("kq-2025-nonprofit-reporting-rules", "news-2025-kqed-nonprofit-reporting-rollback", "KQED",
  "KQED reported that supervisors voted to ease the 2023 public reporting requirements for city-funded nonprofits, citing risks of harassment of staff at LGBTQIA+ and domestic violence organizations. An ethics expert worried the change could make financial mismanagement harder to spot.")

# ---------------- verify ----------------
bad = []
for f in F:
    _, txt = meta(f["_key"])
    if len(f["quote"].split()) > 40: bad.append(("too long", f["org_name"], f["review_id"]))
    if norm(f["quote"]) not in norm(txt): bad.append(("quote not found", f["org_name"], f["review_id"], f["quote"][:60]))
if bad:
    for b in bad: print("FAIL", b)
    sys.exit(1)
for x in R + F: x.pop("_key")
out = base / "partials"; out.mkdir(exist_ok=True)
(out / "group_e.json").write_text(json.dumps({"reviews": R, "org_findings": F}, indent=2, ensure_ascii=False))
print(len(R), "reviews,", len(F), "findings; all quotes verified")
