import json,re
T='/Users/ishita/sf-city-monitor/nonprofits/data/reviews/text/'
U={}
for line in open('/Users/ishita/sf-city-monitor/nonprofits/data/reviews/pdf_sources.tsv').read().splitlines()[1:]:
    f,i,u=line.split('\t'); U[f.replace('.pdf','')]=u
def R(id,file,title,date,typ,summary):
    return dict(id=id,title=title,publisher="San Francisco Office of the Controller",date=date,url=U[file],type=typ,summary=summary,accessed_date="2026-09-26",_file=file)
PI="controller_public_integrity"
reviews=[
R("ctrl-pi-2020-06-public-works-contracting","pi_public_works_contracting_2020","Public Integrity Review: Preliminary Assessment of San Francisco Public Works Contracting","2020-06-29",PI,
 "First Controller public integrity assessment after federal charges against former Public Works Director Mohammed Nuru. It found Public Works awarded 366 contracts worth $1.4 billion (July 2017-March 2020), including 15 homelessness-related contracts worth $25 million through permitted exceptions without adequate safeguards. It recommended citywide changes such as requiring competitive solicitation of grants to nonprofits and closing gaps in gift rules. It makes no findings about specific nonprofits."),
R("ctrl-pi-2020-09-gifts-non-city-orgs","pi_gifts_non_city_orgs_2020","Public Integrity Review: Preliminary Assessment - Gifts to Departments Through Non-City Organizations Lack Transparency and Create \"Pay-to-Play\" Risk","2020-09-24",PI,
 "Reviews 'Friends of' and other non-City organizations that raise money for City departments, focusing on the Public Works subaccounts held by the San Francisco Parks Alliance. It found the subaccounts operated like a City account without City oversight, that seven City contractors or permit holders donated $966,247 to them (July 2015-January 2020), and that this creates a perceived 'pay-to-play' risk; it also found spending records lacked detail. It is a preliminary assessment of risk and controls, not a finding that the Parks Alliance itself broke the law; the Parks Alliance stated it did not know its fiscal agency was being misused and did not profit. It made 10 recommendations, including MOUs for non-City organizations and behested-payment reforms."),
R("ctrl-pi-2021-12-sfpuc-social-impact","pi_sfpuc_social_impact_2021","Public Integrity Audit: Significant Changes Are Needed to the Design, Monitoring, and Control of the San Francisco Public Utilities Commission's Social Impact Partnership Program","2021-12-09",PI,
 "Audit (by Sjoberg Evashenk Consulting for the Controller) of the SFPUC program under which contractors pledge money, volunteer hours, or in-kind services to nonprofits and schools. Since 2011 contractors committed nearly $22 million, but roughly two-thirds of commitments were unfulfilled, some contractors cut commitments after award, and records and controls were weak. Findings concern SFPUC and its contractors, not the nonprofit beneficiaries; no nonprofit is named with a finding."),
R("ctrl-pi-2023-12-sfpuc-sip-followup","pi_sfpuc_sip_followup_2023","Field Follow-up of the 2021 Public Integrity Audit: SFPUC's Social Impact Partnership Program","2023-12-07",PI,
 "Follow-up memo finding SFPUC implemented and closed all seven recommendations from the 2021 audit. SFPUC adopted program rules (Ordinance 261-22 and Resolution 23-0075), added liquidated-damages language, and published a public dashboard of contractor commitments and nonprofit beneficiaries."),
R("ctrl-pi-2023-10-community-challenge-grants","pi_community_challenge_grants_2023","Public Integrity Review: The Community Challenge Grant Program's 2023 Solicitation Process Was Deeply Flawed and Needs to Be Redone Properly","2023-10-17",PI,
 "Controller and City Attorney review of the City Administrator's Community Challenge Grant program, which funds community groups and nonprofits for neighborhood improvements. It found the 2023 grant scoring could not be relied on: the former program director misrepresented the scoring panel, one panelist had an undisclosed conflict tied to Rudolph Dwayne Jones, and the top-scoring application, fiscally sponsored by a now-suspended Jones-affiliated entity, included a forged Housing Authority support letter. It recommended re-evaluating all 2023 applications."),
R("ctrl-pi-2021-08-status-12month","pi_status_12month_2021","Public Integrity Reviews 12-Month Update: Implementation Status of Recommendations From Assessments to Date","2021-08-04",PI,
 "First status update on the Controller's public integrity recommendations after the Nuru charges. It summarizes criminal charges against 11 City employees and contractors and reports progress on recommendations, including those on gifts through non-City ('Friends of') organizations."),
R("ctrl-pi-2022-12-status-24month","pi_status_24month_2022","Public Integrity Reviews 2022 Update: Implementation Status of Recommendations From Assessments to Date","2022-12-21",PI,
 "Status update reporting that the Controller had issued nine public integrity reports with 64 recommendations, 38 (59 percent) implemented or partially implemented. For the non-City organizations report, 8 of 10 recommendations were implemented, 1 in progress, and 1 would not be implemented."),
R("ctrl-pi-2024-08-status","pi_status_2024","Public Integrity Reviews 2024 Update: Implementation Status of Recommendations","2024-08-01",PI,
 "Status update covering 79 recommendations. It reports that the Mayor's Executive Directive 20-02 (September 2020) requires departments to sign MOUs with non-City organizations that raise money for them, that behested-payment law was expanded and later amended to bar most officials from soliciting behested payments from their department's contractors, and that five entities affiliated with Rudolph Dwayne Jones, including the nonprofit Southeast Consortium for Equitable Partnerships, were suspended in September 2023."),
R("ctrl-pi-2026-09-status-final","pi_assessment_2026_status","Public Integrity Reviews 2026 Update: Implementation Status of Recommendations","2026-09-16",PI,
 "Final status update for the 13-report public integrity series. Of 91 recommendations, 86 (95 percent) were closed. All 10 recommendations in the non-City organizations report were closed (9 implemented, 1 partially), all 3 Community Challenge Grant recommendations were implemented, and 1 of 12 recommendations from the 2025 Rudolph Dwayne Jones assessment was still open as of July 31, 2026."),
R("ctrl-audit-2022-08-cbo-performance","controller_cbo_performance_audit_2022","The City Should More Effectively Evaluate the Impact of Services Provided by Community-Based Organizations (Citywide Nonprofit Performance Audit)","2022-08-30","controller_audit",
 "Citywide audit of how departments measure the impact of community-based organizations. The City spent nearly $680 million in FY 2017-18 on 703 CBOs. The audit reviewed 30 sample agreements and recommended standardizing performance measures and monitoring. It does not report compliance findings against individual nonprofits."),
R("ctrl-2025-03-shelter-assessment","ctrl_shelter_assessment_2025","Assessment of the San Francisco Shelter System","2025-03-10","controller_audit",
 "Controller City Performance assessment of HSH emergency shelter and crisis intervention programs. It found shelter capacity grew after 2021, clients generally saw safety as adequate, over half of exits have no recorded destination, and HSH and nonprofit providers partner effectively but shelters are under-resourced. The report states it is not an audit and does not evaluate individual providers."),
]
F=[]
def add(org,al,rid,ft,finding,quote,page,status,ein=None):
    F.append(dict(org_name=org,org_name_aliases=al,ein=ein,review_id=rid,finding_type=ft,finding=finding,quote=quote,page=page,status=status,url=None))
G="ctrl-pi-2020-09-gifts-non-city-orgs"
add("San Francisco Parks Alliance",["the Parks Alliance","SF Parks Alliance"],G,"lack of controls / transparency (preliminary finding)",
 "The Public Works subaccounts held at the Parks Alliance worked like a City account (Public Works staff directed and approved invoices) but sat outside City procurement and financial controls. From July 1, 2015 to January 17, 2020 they took in $990,830 and spent $980,738, mostly on employee events, volunteer programs and merchandise. The Controller says this created an opportunity for unethical steering of purchases; the finding is about the arrangement and Public Works' oversight.",
 "The Public Works subaccounts at the Parks Alliance operate like a city account in that invoices were directed and approved by Public Works employees and tracked by both Public Works and the Parks Alliance",15,
 "Parks Alliance response in report: it did not know its fiscal agency was being used unscrupulously by City officials, did not profit, and had sought an MOU with Public Works in 2019. Related recommendations were closed by 2026 (Executive Directive 20-02 requires MOUs).")
add("San Francisco Parks Alliance",["the Parks Alliance","SF Parks Alliance"],G,"pay-to-play risk (preliminary finding)",
 "Seven City contractors or building-permit holders donated $966,247 to the Public Works subaccounts at the Parks Alliance during July 2015-January 2020 (total donations $992,830). Those donors were paid $572 million by Public Works and received 218 building permits in the same period. The Controller says such donations 'can create' a pay-to-play relationship; it does not find that the Parks Alliance sought influence.",
 "Public Works paid eight contractors a total of $572 million through contract purchase orders or other voucher payments, and the Department of Building Inspection issued 218 building permits to seven entities",27,
 "Report is a preliminary assessment; recommendations on behested payments and MOUs later implemented (see 2024 and 2026 status updates).")
add("San Francisco Parks Alliance",["the Parks Alliance","SF Parks Alliance"],G,"behested payments (context; no filing was required)",
 "Because appointed department heads did not have to file behested-payment forms at the time, no filings were required. The report says that if the payments had been behested by Mr. Nuru under the rules as later proposed, the Parks Alliance would have had to file recipient forms for $199,500 (2016), $197,000 (2017), $258,714 (2018) and $285,200 (2019). This is a hypothetical in the report, not a violation.",
 "If all payments were behested payments by Mr. Nuru, the Parks Alliance would have had to file Form SFEC- 3630 in the following calendar years for the payments it received",36,
 "Behested-payment law later expanded (interested-party definition effective January 23, 2022; solicitation ban from contractors effective November 6, 2022) per 2024 status update.")
add("San Francisco Parks Alliance",["the Parks Alliance","SF Parks Alliance"],G,"context: city funding and donor disclosure",
 "The report's table lists the Parks Alliance as a 'Friends of' organization for Public Works and Recreation and Park that publicly reports donors (including some anonymous donors), with $11.9 million in City funding received July 1, 2015-June 30, 2020. The report notes that City funding may not be tied to its Friends-of role. Its Recreation and Park relationship had project MOUs and gift reporting, unlike the Public Works subaccounts.",
 "San Francisco Parks Alliance Public Works Yes2 Support department projects and programs, including community events, recreation programs, and staff appreciation programs $11.9 million",11,None)
add("SF Clean City Coalition",["San Francisco Clean City Coalition"],G,"donor to non-City account (context)",
 "SF Clean City Coalition donated $721,250 to the Public Works subaccounts at the Parks Alliance. Per the City Attorney, it received $150,000 from Recology in each of 2015, 2017 and 2018 for Public Works programs, and in 2019 received $180,000 from Recology and then paid $171,000 to the Parks Alliance. It also received $3.29 million in Public Works payments in the period. The report lists it as a donor; it does not state a finding of wrongdoing by the Coalition.",
 "SF Clean City Coalition received $150,000 from Recology in each of three years—2015, 2017, and 2018—for Public Works’ Giant Sweep program, Clean Team program, staff enrichment, and community events.",28,None)
add("Community Youth Center of San Francisco",["Community Youth Center"],G,"no findings/cleared",
 "Community Youth Center received $29,450 from the Public Works subaccounts at the Parks Alliance, mostly for sponsoring community events at its site. The Controller said these payments appear reasonable.",
 "Payments were mostly for sponsoring community events and activities at this organization’s site, which appears reasonable.",40,None)
add("Lefty O'Doul's Foundation",["Lefty O’Doul’s Foundation","Lefty O'Doul's Ballpark Buffet & Lefty O'Doul's Foundation"],G,"questionable procurement (preliminary finding)",
 "Lefty O'Doul's Ballpark Buffet and Lefty O'Doul's Foundation (combined) were paid $25,327 from the subaccounts for catering, musical performances and staff appreciation. The Controller said a City-approved contractor would most likely have been more appropriate. The report notes the criminal complaint alleged the principals had personal and business relationships with Mr. Nuru; the report does not itself make a finding against the Foundation.",
 "Payments were for catering and musical performances for events and for staff appreciation. It most likely would have been more appropriate for a city-approved contractor to cater these events.",40,None)
add("San Francisco Public Health Foundation",["SF Public Health Foundation"],G,"donor disclosure gap (context)",
 "Listed as a 'Friends of' organization for the Department of Public Health that did not publicly report donors, with $9.7 million in City funding received July 2015-June 2020. The report says City funding may not be directly tied to its Friends-of role. The report's general finding is that non-City organizations that don't disclose donors prevent detection of donor financial interests; it makes no specific finding of misuse by this organization.",
 "San Francisco Public Health Foundation Public Health No Support administrative and support services for various programs $9.7 million",10,None)
add("Friends of the Urban Forest",[],G,"context: city funding and donor disclosure",
 "Listed as a 'Friends of' organization associated with SFPUC that publicly reports donors (including some anonymous donors), with $7.6 million in City funding received July 2015-June 2020. The report says City funding may not be directly tied to its Friends-of role. No specific finding against the organization.",
 "Friends of the Urban Forest SFPUC Yes2 Support programs that plant and care for the City’s ideal urban forest $7.6 million",10,None)
add("Friends of the San Francisco Public Library",["Friends of the SF Public Library"],G,"no findings/cleared (cited as good practice)",
 "Cited as a model: it has an MOU with the Public Library with an audit clause, the Library obtains Board approval to accept its gifts, and the Library discloses gifts over $100 and donors with active contracts.",
 "the Public Library has a memorandum of understanding with the Friends of the San Francisco Public Library that defines the organization’s roles and allowable practices, contains an audit clause",17,None)
C="ctrl-pi-2023-10-community-challenge-grants"
add("Southeast Consortium for Equitable Partnerships",["The Southeast Consortium for Equitable Partnerships"],C,"falsified document in application; suspended entity",
 "The top-scoring 2023 Community Challenge Grant application had this Jones-affiliated organization as fiscal sponsor, and one of its five support letters, supposedly from the SF Housing Authority, appears to have been forged (the Housing Authority confirmed it never provided it). The organization was among entities suspended in September 2023. The report says it is unclear what role Jones had in preparing the application.",
 "The top-scoring application had as its fiscal sponsor Southeast Consortium for Equitable Partnerships, which is now a suspended entity.",10,
 "Controller recommended re-evaluating all 2023 applications; all 3 recommendations were implemented per the 2026 status update.")
add("Southeast Consortium for Equitable Partnerships",["The Southeast Consortium for Equitable Partnerships"],"ctrl-pi-2024-08-status","suspension",
 "On September 7, 2023 the City Attorney and City Administrator issued suspension orders against five entities that Rudolph Dwayne Jones owns, controls or manages, including The Southeast Consortium for Equitable Partnerships.",
 "The City Attorney and the City Administrator issued suspension orders against five affiliated entities that Mr. Jones owns, controls, or manages: RDJ Enterprises, LLC, RDJ-Project Complete, LLC, The Southeast Consortium for Equitable Partnerships",11,
 "2026 status update says all but one previously suspended contractor are again eligible to bid; it does not say which one remains, in the portion reviewed.")
rmap={r['id']:r for r in reviews}
def norm(s): return re.sub(r'\s+',' ',s).strip()
bad=0
for f in F:
    r=rmap[f['review_id']]; f['url']=r['url']
    t=open(T+r['_file']+'.txt').read(); parts=re.split(r'=== PAGE (\d+) ===',t)
    d={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
    ok=norm(f['quote']) in norm(d.get(f['page'],''))
    nw=len(f['quote'].split())
    if not ok or nw>40: bad+=1; print("FAIL",ok,nw,f['org_name'],f['quote'][:60])
for r in reviews: r.pop('_file')
json.dump({"reviews":reviews,"org_findings":F},open('/Users/ishita/sf-city-monitor/nonprofits/data/reviews/partials/group_c.json','w'),indent=1,ensure_ascii=False)
print(len(reviews),len(F),"bad",bad)
