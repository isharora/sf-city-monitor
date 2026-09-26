"""Write the dashboard commentary (headline, analyst paragraphs, callouts, live templates, caveats, story).

Every number is computed here from the exported site files (data/site/) or taken from the red-team results
(data/redteam/redteam.json, "cite" blocks), so reruns reproduce the text. verify_commentary.py checks
independently that each number in the output traces to those files.
Writes data/site/commentary/np-*.json and story_np.json, then refreshes meta.files sizes.
"""
import glob, json, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "data", "site")
RT = os.path.join(HERE, "..", "data", "redteam", "redteam.json")
J = lambda p: json.load(open(os.path.join(SITE, p)))
AUTHOR = "Nonprofits module analysis; red-teamed (see data/redteam/redteam.json). Numbers computed by pipeline/18_commentary.py"


REG = {}     # key -> value (every number the commentary may use)
TRACE = defaultdict(set)   # token -> keys whose value produced it


def keys_for(x):
    ks = [k for k, v in REG.items() if isinstance(v, (int, float)) and not isinstance(v, bool) and float(v) == float(x)]
    if not ks:
        raise KeyError(f"number {x!r} is not registered; add it to S (site) or cite it from redteam.json")
    return ks


def rec(tok, x):
    TRACE[tok].update(keys_for(x))
    return tok


def n(x, d=0):
    tok = f"{float(x):,.{d}f}" if d else f"{round(float(x)):,}"
    return rec(tok, x)


def yr(x):
    return rec(str(int(x)), x)


def money(x, d=None):
    return rec(_money(x, d), x)


def _money(x, d=None):
    x = float(x)
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f} billion"
    if abs(x) >= 1e6:
        dd = d if d is not None else (1 if abs(x) < 1e7 else 0)
        return f"${x / 1e6:.{dd}f} million"
    if abs(x) >= 1e4:
        return f"${round(x, -3):,.0f}"
    return f"${x:,.0f}"


def display(name):
    t = name.title()
    for a, b in (("'S ", "'s "), (" Of ", " of "), (" And ", " and "), (" The ", " the ")):
        t = t.replace(a, b)
    return t


def pct(x, d=0):
    return rec(f"{100 * abs(x):.{d}f}%", x)


def main():
    rt = {f["id"]: f["cite"] for f in json.load(open(RT))["findings"]}
    T, G, T20, D, A, C, H, R = (rt["total_fy2025"], rt["real_growth_fy2016_2025"], rt["top20_share"], rt["dependency"],
                                rt["dependency_corrective_action"], rt["contracts_doubled"], rt["hsh_spending_vs_placements"],
                                rt["paid_after_irs_revocation"])
    meta = J("meta.json"); idx = meta["deflator"]["index"]
    orgs = {o["id"]: o for o in J("orgs/index.json")["orgs"]}
    cells = [c for f in sorted(glob.glob(os.path.join(SITE, "payments", "cells_*.json"))) for c in json.load(open(f))["cells"]]
    tot = defaultdict(float); dept = defaultdict(float); org25 = defaultdict(float); pay = defaultdict(float)
    for c in cells:
        tot[c["fy"]] += c["amt"]; dept[(c["dept"], c["fy"])] += c["amt"]; pay[(c["org"], c["fy"])] += c["amt"]
        if c["fy"] == 2025:
            org25[c["org"]] += c["amt"]
    top_org, top_amt = max(org25.items(), key=lambda x: x[1])
    d25 = sorted(((d, v) for (d, fy), v in dept.items() if fy == 2025), key=lambda x: -x[1])
    top3 = sum(v for _, v in d25[:3]) / tot[2025]
    trends = {r["fiscal_year"]: r for r in J("aggregates/trends.json")["rows"]}
    dshare = {r["department_code"]: r["nonprofit_share_of_vendor_spend"] for r in J("aggregates/departments.json")["rows"] if r["fiscal_year"] == 2025}
    oc = J("aggregates/outcomes.json")["rows"]
    ov = lambda m, fy: next(r["value"] for r in oc if r["measure"] == m and r["fiscal_year"] == fy)
    beds23, beds25 = ov("shelter_beds", 2023), ov("shelter_beds", 2025)
    pitu19, pitu26, pitt19, pitt26 = ov("pit_unsheltered", 2019), ov("pit_unsheltered", 2026), ov("pit_total", 2019), ov("pit_total", 2026)
    facts = J("commentary_facts.json")
    f24 = J("finances/form990_2024.json")["rows"]
    big24 = [r for r in f24 if r["total_revenue"] > 0 and pay[(r["org"], 2024)] >= 1e6]
    ex = [r["exec_comp"] for r in big24 if r["exec_comp"]]
    rs = [r["months_reserves"] for r in big24 if r["months_reserves"] is not None]
    pay_med, res_med, res_lt1, res_neg = st.median(ex), st.median(rs), sum(r < 1 for r in rs), sum(r < 0 for r in rs)
    fr = J("reviews/findings.json")["rows"]
    none_share = sum(r["result"] == "none" for r in fr) / len(fr)
    sev_orgs = len({r["org"] for r in fr if r["result"] in ("corrective", "elevated", "redflag")})
    elev_orgs = len({r["org"] for r in fr if r["result"] in ("elevated", "redflag")})
    per_year = [sum(1 for r in fr if r["fy"] == y) for y in (2022, 2023, 2024, 2025)]
    con = J("contracts/contracts.json")["contracts"]
    emerg = sum(c["agreed"] for c in con if c["authority_class"] == "emergency_or_waiver") / sum(c["agreed"] for c in con)
    rtf = {f["id"]: f for f in json.load(open(RT))["findings"]}
    chk = {c["check"][:40]: c["result"] for c in rtf["contracts_doubled"]["checks"]}
    first_later = next(v for k, v in chk.items() if k.startswith("First observed in April 2021"))[1]
    conf_med = next(v for k, v in chk.items() if k.startswith("Classification confidence"))[0]
    elasticity = facts["comp_elasticity"]
    t16real = tot[2016] / idx["2016"]
    S = {"total_fy2016": tot[2016], "total_fy2016_real2025": t16real, "top_org_fy2025": top_amt, "top3_dept_share_fy2025": top3,
         "HOM_fy2025": dept[("HOM", 2025)], "DPH_fy2025": dept[("DPH", 2025)], "DEC_fy2025": dept[("DEC", 2025)], "HOM_fy2019": dept[("HOM", 2019)],
         "orgs_paid_fy2016": trends[2016]["n_orgs_paid"], "orgs_paid_fy2025": trends[2025]["n_orgs_paid"],
         "dshare_HOM_2025": dshare["HOM"], "dshare_DEC_2025": dshare["DEC"], "dshare_CHF_2025": dshare["CHF"], "dshare_DPH_2025": dshare["DPH"],
         "beds_change_2023_2025": beds25 / beds23 - 1, "pit_unsheltered_change_2019_2026": pitu26 / pitu19 - 1, "pit_total_2019": pitt19, "pit_total_2026": pitt26,
         "pay_elasticity_doubling": 2 ** elasticity - 1, "fy2024_ge1m_median_pay": pay_med, "fy2024_ge1m_with_pay": len(ex),
         "fy2024_ge1m_median_reserves": res_med, "fy2024_ge1m_with_reserves": len(rs), "fy2024_ge1m_reserves_lt1": res_lt1, "fy2024_ge1m_reserves_negative": res_neg,
         "monitoring_org_years": len(fr), "monitoring_share_none": none_share, "orgs_ever_severe": sev_orgs, "orgs_ever_elevated_redflag": elev_orgs,
         "monitoring_min_per_year_2022_2025": min(per_year), "monitoring_max_per_year_2022_2025": max(per_year), "contracts_emergency_share": emerg}
    REG.update({f"site:{k}": v for k, v in S.items()})
    for fid, cite in rt.items():
        REG.update({f"rt:{fid}.cite.{k}": v for k, v in cite.items()})
    REG["rt:contracts_doubled.checks.first_observed_later"] = first_later
    REG["rt:contracts_doubled.checks.confidence_median"] = conf_med
    REG.update({f"facts:{k}": v for k, v in facts.items() if isinstance(v, (int, float))})
    REG["meta:small_n"] = meta["small_n"]
    # definitional constants written literally in the text (thresholds used by the views and the pipeline)
    for tok, key in (("20", "const:top_n"), ("75%", "const:dependency_threshold"), ("100%", "const:full_share"),
                     ("$1 million", "const:recipient_threshold"), ("$5 million", "const:large_dependent_threshold")):
        TRACE[tok].add(key)

    def com(view, headline, paragraphs, templates, caveats, sources, annotations=None):
        obj = {"sample": False, "view": view, "author": AUTHOR, "headline": headline, "paragraphs": paragraphs,
               "annotations": annotations or [], "templates": templates, "caveats": caveats, "sources": sources}
        for a in obj["annotations"]:
            assert len(a["text"]) <= 90, a["text"]
        os.makedirs(os.path.join(SITE, "commentary"), exist_ok=True)
        json.dump(obj, open(os.path.join(SITE, "commentary", f"{view}.json"), "w"), ensure_ascii=False, indent=1)

    SMALL = "Fewer than " + n(meta["small_n"]) + " {what} match these filters, too few to summarize without singling out individual organizations; widen the years or clear a filter."
    # ------------------------------------------------------------------ overview
    com("np-overview",
        f"San Francisco paid {money(T['total_fy2025'])} to {n(T['orgs_fy2025'])} nonprofits in FY2025, more than double its FY2016 spending after inflation; 20 organizations received {pct(T20['top20_fy2025'])} of the money.",
        [f"The city runs much of its safety net through nonprofits it pays under contract: shelters and supportive housing, behavioral health treatment, childcare subsidies, youth programs, legal aid. Payments rose from {money(tot[2016])} in FY2016 ({money(t16real)} in FY2025 dollars) to {money(T['total_fy2025'])} in FY2025, a real increase of {pct(G['real_growth_sf_cpi'])}. Most of the growth came after FY2019, as voter-approved taxes for homelessness and early care came online and pandemic-era shelter and food programs were added, and spending did not fall back afterward.",
         f"Two things are less obvious. First, some of the largest recipients are conduits: {display(orgs[top_org]['name'])} ({money(top_amt)} in FY2025) mostly passes childcare subsidies on to providers and families, and fiscal sponsors hold city grants on behalf of many small projects. Organizations like these received {money(T['passthrough_orgs_fy2025'])} in FY2025; leaving them out of both years, real growth since FY2016 is {pct(G['real_growth_excl_passthrough'])}, still more than double. Second, concentration has not changed with scale. The top 20 received {pct(T20['top20_fy2016'])} in FY2016 and {pct(T20['top20_fy2025'])} in FY2025, the share has stayed between {pct(T20['top20_min_2008_2026'])} and {pct(T20['top20_max_2008_2026'])} since FY2008, and the number of organizations paid grew only from {n(trends[2016]['n_orgs_paid'])} to {n(trends[2025]['n_orgs_paid'])}. The city added money mainly by growing the providers it already had.",
         f"What counts as a nonprofit matters, and reasonable definitions differ. This dashboard counts any city vendor matched to an IRS tax-exempt record; the Controller's own nonprofit dataset uses a narrower definition and reports {money(T['controller_dataset_fy2025'])} for FY2025. The two agree on the trend ({pct(G['nominal_growth_2019_2025'])} and {pct(G['controller_nominal_growth_2019_2025'])} nominal growth from FY2019 to FY2025). The implication is one of scale and reliance: a few hundred organizations now deliver {money(T['total_fy2025'])} a year of public services, while the Controller's joint fiscal monitoring reviews {n(min(per_year))} to {n(max(per_year))} of them a year."],
        [{"id": "total", "template": "{orgs_fmt} organizations received {total} ({dollars}) across {rows_fmt} department-by-year payment records in {years}.",
          "requires": {"orgs_min": 1}, "fallback": "No payments match these filters; widen the years or clear a filter."}],
        [{"severity": "high", "text": f"Pass-through money inflates totals and growth. {money(T['passthrough_orgs_fy2025'])} of FY2025 went to childcare-subsidy administrators, a housing loan fund and fiscal sponsors; the Controller excludes four childcare pass-through contracts ({money(T['passthrough_contracts_fy2025'])} in FY2025) from its own totals. Without these organizations, real growth since FY2016 is {pct(G['real_growth_excl_passthrough'])} rather than {pct(G['real_growth_sf_cpi'])}."},
         {"severity": "medium", "text": f"The growth figure depends on the starting year more than on the deflator. Measured from FY2017, real growth to FY2025 is {pct(G['real_growth_from_fy2017'])}; from FY2015 it is {pct(G['real_growth_from_fy2015'])}. The U.S. CPI gives {pct(G['real_growth_us_cpi'])} and the services-only CPI {pct(G['real_growth_services_cpi'])}, against {pct(G['real_growth_sf_cpi'])} with the SF-area CPI used here."},
         {"severity": "medium", "text": f"Nonprofit status comes from matching city vendor names to IRS records. {n(facts['precision_n'])} hand-checked matches were {pct(facts['precision_strict'], 1)} correct, and the matched share of city grant-program dollars rose from {pct(G['coverage_grant_2016'])} in FY2016 to {pct(G['coverage_grant_2025'])} in FY2025, so older years may be slightly undercounted, which would overstate growth a little."},
         {"severity": "low", "text": "Totals are cash paid in each fiscal year, not contract budgets or obligations. FY2026 is shown, but late invoices for it are still being paid."}],
        ["nonprofits/payments/cells_2016.json", "nonprofits/payments/cells_2025.json", "nonprofits/aggregates/trends.json", "redteam.json#total_fy2025", "redteam.json#real_growth_fy2016_2025", "redteam.json#top20_share"],
        [{"chart": "np_trend", "x": 2019, "text": "Growth speeds up after FY2019", "placement": "top"},
         {"chart": "np_trend", "x": 2023, "text": "Childcare moves to the new Dept. of Early Childhood", "placement": "bottom"}])
    # ------------------------------------------------------------------ flows
    hom19, hom25 = dept[("HOM", 2019)], dept[("HOM", 2025)]
    com("np-flows",
        f"Three departments paid {pct(top3)} of FY2025 nonprofit dollars: Homelessness and Supportive Housing ({money(dept[('HOM', 2025)])}), Public Health ({money(dept[('DPH', 2025)])}) and Early Childhood ({money(dept[('DEC', 2025)])}).",
        [f"Homelessness and Supportive Housing (HSH, code HOM) is the biggest single story: its payments to nonprofits rose from {money(hom19)} in FY2019 to {money(hom25)} in FY2025 (nominal dollars). Part of any department-level change is bookkeeping. HSH was created in FY2017 from programs previously run by the Human Services Agency and Public Health, and the Department of Early Childhood took over the Human Services Agency's childcare contracts in FY2023, so compare service areas rather than department codes across those breaks.",
         f"Did more money buy more housing placements? Over the years in which HSH reports one consistent measure, FY2023 to FY2025, its real payments to nonprofits rose {pct(H['hsh_real_2023_2025'])} while households moved into supportive housing, rapid rehousing or a problem-solving resolution fell {pct(H['hsh_placed_2023_2025'])} ({n(H['placed_2023'])} to {n(H['placed_2025'])}). Longer comparisons show a gap in the same direction whose size depends on the years chosen (FY2019 to FY2025: {pct(H['hsh_real_2019_2025'])} against {pct(H['hsh_placed_2019_2025'])}, across a change in how placements were counted). Placements are not the whole product: the same budget paid for shelter (beds up {pct(beds25 / beds23 - 1)} from FY2023 to FY2025), outreach and prevention, and the unsheltered count fell {pct(pitu26 / pitu19 - 1)} between the 2019 and 2026 (preliminary) point-in-time counts while the total barely moved ({n(pitt19)} to {n(pitt26)}).",
         f"A department's nonprofit share of its vendor spending shows how much of its service delivery it buys rather than provides. In FY2025 it was {pct(dshare['HOM'])} for HSH, {pct(dshare['DEC'])} for Early Childhood and {pct(dshare['CHF'])} for Children, Youth and Their Families, but {pct(dshare['DPH'])} for Public Health, which also buys hospital, pharmacy and university services and employs its own clinicians. Contracting out is a design choice, so a high share is not a problem in itself; it does make the city's results depend on its providers' capacity."],
        [{"id": "flows", "template": "In {years}, {depts_fmt} departments paid these {orgs_fmt} organizations; the largest payer, {top_dept}, accounted for {top_dept_share} of the dollars ({dollars}).",
          "requires": {"orgs_min": 1}, "fallback": "No payments match these filters; widen the years or clear a filter."}],
        [{"severity": "high", "text": f"Spending-versus-outcome comparisons are descriptive, and outcome measures include work done by city staff. HSH placements for FY2018 to FY2022 come from monthly scorecard counts and those from FY2023 on from the annual performance measure. A widely cited comparison, FY2018 to FY2026 ({pct(H['hsh_real_2018_2026'])} spending against {pct(H['hsh_placed_2018_2026'])} placements), starts in HSH's first full year and splices the two series, which overstates the gap."},
         {"severity": "medium", "text": "Department codes changed with reorganizations (HSH in FY2017, Early Childhood in FY2023), and the city's chart of accounts changed in FY2018. Service areas are the better unit across those breaks."},
         {"severity": "low", "text": "Service area is assigned once per organization from its main funding department and IRS activity code, so multi-service organizations appear under one area."}],
        ["nonprofits/payments/cells_2019.json", "nonprofits/payments/cells_2025.json", "nonprofits/aggregates/departments.json", "nonprofits/aggregates/outcomes.json", "redteam.json#hsh_spending_vs_placements"],
        [{"chart": "np_trend", "x": 2023, "text": "Early Childhood takes over childcare contracts from Human Services", "placement": "top"}])
    # ------------------------------------------------------------------ dependency
    com("np-dependency",
        f"Among the {n(D['dep_n_2024'])} organizations paid at least $1 million in FY2024, the median got {pct(D['dep_median_2024'])} of its revenue from the city, and {n(D['dep_gt75_2024'])} got more than three-quarters.",
        [f"For most of the {n(D['dep_all_n_2025'])} organizations with a Form 990 that the city paid in FY2025, the city is a minor funder: their median city share is {pct(D['dep_all_median_2025'])}. Large recipients are different. Many were built to deliver city programs, so among those paid $1 million or more the median is near half, and {n(facts['large_dependent_n'])} were both paid at least $5 million and more than 75% dependent in FY2024.",
         f"Dependency cuts both ways. An organization that gets most of its money from one payer has little cushion when invoices are paid late or a contract is cut, and the city has few alternatives when a large, single-purpose provider falters. The monitoring data show the pattern: in FY2023 to FY2025, organization-years more than 75% dependent were placed on corrective action (Tier 2), Tier 3 or red flag {pct(A['assoc_rate_hi'])} of the time ({n(A['assoc_sev_hi'])} of {n(A['assoc_hi_n'])}), against {pct(A['assoc_rate_lo'])} for the rest ({n(A['assoc_sev_lo'])} of {n(A['assoc_lo_n'])}). Counting each organization once gives {n(A['assoc_org_hi_sev'])} of {n(A['assoc_org_hi_n'])} against {n(A['assoc_org_lo_sev'])} of {n(A['assoc_org_lo_n'])}, and the gap holds after accounting for size, service area and year.",
         f"The association is clear in these data but small in absolute numbers ({n(A['assoc_severe_events'])} designations at {n(A['assoc_severe_orgs'])} organizations, many repeated from year to year), and it does not show which way causation runs. Organizations with a single funder may lack the finance staff and audits that other funders pay for; organizations already in trouble lose private donors, which raises their city share; and highly dependent organization-years more often had under one month of reserves ({pct(A['res_lt1_share_hi'])} against {pct(A['res_lt1_share_lo'])}). Ratios above 100% ({pct(D['dep_gt100_share_2024'])} of large recipients in FY2024) usually reflect timing or pass-through funds, not missing money."],
        [{"id": "dep", "template": "In {fy}, among {orgs_fmt} organizations with a Form 990 under these filters, the median got {median_share} of its revenue from the city and {hi_fmt} got more than 75%. Small grantees pull this median down; the finding above covers only organizations paid $1 million or more.",
          "requires": {"orgs_min": 5}, "fallback": SMALL.format(what="organizations with a Form 990")}],
        [{"severity": "high", "text": f"Tax years and city fiscal years do not line up for about a quarter of large recipients ({pct(D['dep_non_june_share_2024'])} in FY2024 end their year in a month other than June). Prorating payments to each organization's tax year leaves the FY2024 median at {pct(D['dep_median_prorated_2024'])} and the count above 75% at {n(D['dep_gt75_prorated_2024'])}; June-year-end organizations alone have a median of {pct(D['dep_median_june_2024'])}."},
         {"severity": "medium", "text": f"FY2025 is this page's default year. Its median for large recipients is similar ({pct(D['dep_median_2025'])}), but {n(D['dep_gt100_n_2025'])} organizations show ratios above 100%, a sign that the latest filings and payments are not yet aligned, so the finding uses FY2024. FY2023 gives {pct(D['dep_median_2023'])} and {n(D['dep_gt75_2023'])} above 75%."},
         {"severity": "medium", "text": f"The link between dependency and corrective action is an association across {n(A['assoc_n'])} organization-years, not a finding about any organization, and the corrective-action tiers only began in FY2024."},
         {"severity": "low", "text": "City money that passes through state or federal programs (for example Medi-Cal behavioral health) counts as city payments here; organizations may book it as program-service revenue."}],
        ["nonprofits/finances/form990_2024.json", "nonprofits/payments/cells_2024.json", "nonprofits/reviews/findings.json", "redteam.json#dependency", "redteam.json#dependency_corrective_action"])
    # ------------------------------------------------------------------ pay
    com("np-pay",
        f"Among organizations paid at least $1 million by the city in FY2024, the median top executive earned {money(pay_med)} ({n(len(ex))} organizations reporting pay) and the median organization held {n(res_med, 1)} months of unrestricted reserves; {n(res_lt1)} of {n(len(rs))} had less than one month.",
        [f"Executive pay rises with organization size, but less than proportionally: across {n(facts['comp_n_fit'])} organizations' latest filings, doubling expenses goes with about {pct(2 ** elasticity - 1)} higher top pay. Part VII of the Form 990 also counts pay from related organizations, so the executive of a small affiliate of a large system can look highly paid. Pay well above peers of the same size is a fair question for a board, not evidence of impropriety.",
         f"Reserves are the more consequential number for the city. {n(res_lt1)} of {n(len(rs))} large recipients had less than one month of unrestricted net assets, {n(res_neg)} of them below zero. Most city grants pay in arrears once invoices are approved, so an organization with thin reserves has to borrow or delay bills when payments slip. In the monitoring data, organization-years with under a month of reserves were placed on corrective action or worse {pct(A['res_lt1_severe_rate'])} of the time, against {pct(A['res_ge1_severe_rate'])} for the rest.",
         "Unrestricted net assets include buildings and equipment, so property-owning organizations, housing providers especially, look better cushioned than their cash suggests, while money restricted by donors does not count at all. Treat the measure as a screen for fragility, not a verdict."],
        [{"id": "pay", "template": "In {fy}, across {orgs_fmt} organizations with a Form 990 under these filters, the median top-executive pay was {median_pay} ({dollars}) and {n_low_fmt} reported under one month of reserves.",
          "requires": {"orgs_min": 5}, "fallback": SMALL.format(what="organizations with a Form 990")}],
        [{"severity": "medium", "text": "High compensation is unusual, not improper. Boards set pay, and the Form 990 is the public record; only the title is shown here, not the name."},
         {"severity": "medium", "text": "Months of reserves overstate cash for property-owning organizations and ignore restricted funds."},
         {"severity": "low", "text": "The finding uses FY2024 because filings for FY2025, this page's default year, are still arriving for some organizations."}],
        ["nonprofits/finances/form990_2024.json", "nonprofits/payments/cells_2024.json", "nonprofits/commentary_facts.json", "redteam.json#dependency_corrective_action"])
    # ------------------------------------------------------------------ growth
    com("np-growth",
        f"{n(C['con_doubled'])} of {n(C['con_n'])} large nonprofit contracts at least doubled their ceiling between the 2021 and 2026 snapshots, mostly by running longer: {n(C['con_term_extended'])} had their end date pushed out, and only {n(C['con_annual_doubled'])} doubled per year of term.",
        [f"A contract's ceiling, its not-to-exceed amount, is raised by amendment, and the city routinely extends multi-year service contracts rather than rebidding them, adding both years and the money to pay for them. To see what the doublings were, each of the {n(C['con_doubled'])} was classified with Claude from its term history, amount per year of term and actual payments: {n(C['con_llm_extension'])} were mainly extensions, {n(C['con_llm_expansion'])} raised the annual level (more services, sites or clients), {n(C['con_llm_funding_increment'])} funded years already inside the term and {n(C['con_llm_rate_volume'])} reflected rates or volume. Contract titles are too short to show new scope ({n(C['con_text_cannot_tell'])} of {n(C['con_doubled'])} could not be read either way), so the classification rests on dates and payments.",
         f"The two largest dollar increases show both forces (amounts in nominal dollars, as written in the contracts). HealthRIGHT 360's Public Health behavioral health contract went from {money(C['hr360_orig'])} with a term ending in {yr(C['hr360_orig_end_year'])} to {money(C['hr360_now'])} ending in {yr(C['hr360_end_year'])}; most of that is six more years, but yearly payments also rose from about {money(C['hr360_paid_fy2020_22_avg'])} (FY2020 to FY2022 average) to {money(C['hr360_paid_fy2025_26_avg'])} (FY2025 to FY2026). Tenderloin Housing Clinic's master-lease hotels agreement with HSH went from {money(C['thc_orig'])}, ending in {yr(C['thc_orig_end_year'])}, to {money(C['thc_now'])}, ending in {yr(C['thc_end_year'])}, as yearly payments rose from {money(C['thc_paid_fy2021'])} in FY2021 to {money(C['thc_paid_fy2025'])} in FY2025.",
         f"Extensions buy continuity for clients and staff and avoid the cost of rebidding, but they also mean large, growing agreements are rarely re-competed: {pct(emerg)} of these contracts' value was awarded under emergency authority or ordinances that waived competitive solicitation. The sharper oversight question is not whether contracts grew but whether the {n(C['con_llm_expansion'])} whose annual level rose got the scrutiny of a new award."],
        [{"id": "growth", "template": "Of {contracts_fmt} contracts that started in {years} under these filters, {amended_fmt} changed value between snapshots; the median amended contract ended at {median_ratio} times its first observed amount, and {doubled_fmt} at least doubled. Across all contracts, most doublings added years rather than raising the annual level.",
          "requires": {"contracts_min": 5}, "fallback": SMALL.format(what="contracts")}],
        [{"severity": "high", "text": f"Amendment history comes from four snapshots (April 2021, December 2022, November 2025 and September 2026). Amendments before a contract's first snapshot are invisible, and {n(first_later)} of the doubled contracts were first observed after April 2021, so growth is understated for older contracts and the first observed amount may already include amendments."},
         {"severity": "medium", "text": f"The growth-driver classification is Claude's reading of term dates, amount per year and payments (median confidence {n(conf_med, 2)}); it cannot see contract documents, so 'expansion' means the annual level rose, not that new programs were confirmed."},
         {"severity": "medium", "text": "The Supplier Contracts 'sole source' flag marks authorities that permit sole-source awards, and some Public Health contracts carry a legacy purchasing-authority code from the 2017 system conversion, so the competitive split is approximate."},
         {"severity": "low", "text": "Amendment dates are the snapshot dates on which a change was first observed, not execution dates."}],
        ["nonprofits/contracts/contracts.json", "redteam.json#contracts_doubled"])
    # ------------------------------------------------------------------ reviews
    com("np-reviews",
        f"{pct(none_share)} of {n(len(fr))} organization-years in the Controller's fiscal monitoring ended with no unresolved findings; {n(sev_orgs)} organizations were placed on corrective action, Tier 3 or red flag at least once, {n(elev_orgs)} of them to elevated concern, Tier 3 or red flag.",
        ["Each year the Controller and funding departments check a pool of nonprofits funded by several departments against City fiscal and administrative standards: audited financial statements, budgets, cost allocation, board oversight, invoicing and payroll. A finding means a standard was not yet met at final status; it is not a finding that money was misused. Since FY2024 the Citywide Corrective Action Policy sorts organizations with serious or unresolved problems into tiers. The Controller names Tier 2 and Tier 3 organizations but does not say which issue led to each Tier 2 designation, so neither does this dashboard.",
         f"Corrective action concentrates among the organizations that depend most on the city (see City dependency): in FY2023 to FY2025, {pct(A['assoc_org_rate_hi'])} of organizations more than 75% dependent were designated at least once, against {pct(A['assoc_org_rate_lo'])} of the rest. That is a guide to where monitoring and technical assistance matter most, not a judgment of any organization.",
         f"A separate check against IRS records found {n(R['rev_orgs'])} organizations whose federal tax exemption had been automatically revoked for not filing returns, and never restored, that received {money(R['rev_amount'])} in city payments dated after the IRS published the revocation; {pct(R['rev_largest_share'])} of it went to one youth-services grantee between FY{yr(R['rev_largest_first_fy'])} and FY{yr(R['rev_largest_last_fy'])}. Automatic revocation reflects missed filings, is common among small nonprofits and is often reversed retroactively, and whether a city grant requires federal exemption depends on the program. An earlier count of {n(R['rev_pipeline_orgs'])} organizations dropped {n(R['rev_excluded'])} after checking payment dates against the IRS posting date and the quality of the name match."],
        [{"id": "reviews", "template": "{reviews_fmt} monitoring results for {orgs_fmt} organizations match these filters; {none_share} ended with no unresolved findings and {elev_fmt} were elevated concern, Tier 3 or red flag.",
          "requires": {"reviews_min": 5}, "fallback": SMALL.format(what="monitoring results")}],
        [{"severity": "medium", "text": f"Only organizations in the joint monitoring pool are reviewed ({n(min(per_year))} to {n(max(per_year))} matched organizations a year in FY2022 to FY2025), so absence from this view is not a clean bill of health. FY2020 and FY2021 results were not published."},
         {"severity": "medium", "text": "The scale changed in FY2024. The new policy describes Tier 2 as the former 'elevated concern' status, but this dashboard's scale keeps pre-FY2024 elevated concern on the same step as Tier 3, so designations before FY2024 can look more severe than their FY2024 equivalents."},
         {"severity": "medium", "text": "Tier designations reflect Controller and department judgment and can rest on contract-management issues raised by funders as well as on monitoring findings."},
         {"severity": "low", "text": "Organization names in the reports were matched to IRS records; a handful could not be matched and are omitted."}],
        ["nonprofits/reviews/findings.json", "redteam.json#dependency_corrective_action", "redteam.json#paid_after_irs_revocation"])
    com("np-orgs", "Every organization in the payments data, with its city money, service area and links to its finances, contracts and monitoring results.",
        ["Search or sort, then open an organization to see its profile. Match confidence is the adjudicator's confidence that the city vendor and the IRS record are the same legal entity; profiles also state the organization's IRS exemption status, including any past automatic revocation and whether it was restored."], [],
        [{"severity": "low", "text": "An organization's city vendor name can differ from its IRS name (trade names, renamings); both are searchable in profiles."}],
        ["nonprofits/orgs/index.json"])
    # ------------------------------------------------------------------ story
    story = {"sample": False, "title": "Follow the nonprofit money", "steps": [
        {"view": "np-overview", "title": "Start with the total", "text": f"The city paid {money(T['total_fy2025'])} to {n(T['orgs_fy2025'])} nonprofits in FY2025, {pct(G['real_growth_sf_cpi'])} more than in FY2016 after inflation. About {money(T['passthrough_orgs_fy2025'])} of it went to organizations that mostly pass money on."},
        {"view": "np-flows", "title": "Where the growth went", "text": f"Homelessness, Public Health and Early Childhood paid {pct(top3)} of FY2025 dollars; HSH alone went from {money(hom19)} in FY2019 to {money(hom25)}.", "filters": {"years": [2019, 2025]}},
        {"view": "np-flows", "title": "Zoom to homelessness", "text": "A few large providers carry most of the homelessness work. HSH spending grew faster than housing placements in every period checked, but by how much depends heavily on the years compared.", "filters": {"years": [2019, 2025], "area": ["homeless"]}},
        {"view": "np-dependency", "title": "How dependent are they?", "text": f"Among large recipients the median gets {pct(D['dep_median_2024'])} of its revenue from the city, and {n(D['dep_gt75_2024'])} get more than three-quarters.", "filters": {"years": [2016, 2024]}},
        {"view": "np-reviews", "title": "Dependency and corrective action", "text": f"Organization-years more than 75% dependent were placed on corrective action or worse about {n(A['assoc_ratio'], 0)} times as often as the rest. It is an association across {n(A['assoc_n'])} organization-years, not a verdict on anyone."},
        {"view": "np-growth", "title": "Contracts that grow", "text": f"{n(C['con_doubled'])} contract ceilings at least doubled, but {n(C['con_llm_extension'])} of those mainly added years; {n(C['con_llm_expansion'])} raised the annual level."},
        {"view": "np-pay", "title": "Thin cushions", "text": f"{n(res_lt1)} of {n(len(rs))} large recipients had under one month of unrestricted reserves in FY2024.", "filters": {"years": [2016, 2024]}},
    ]}
    json.dump(story, open(os.path.join(SITE, "commentary", "story_np.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({k: sorted(v) for k, v in TRACE.items()}, open(os.path.join(HERE, "..", "data", "redteam", "commentary_trace.json"), "w"), indent=1)
    # refresh meta.files (commentary sizes changed)
    files = {}
    for f in sorted(glob.glob(os.path.join(SITE, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(f, SITE)
        if rel != "meta.json":
            files["nonprofits/" + rel] = {"bytes": os.path.getsize(f)}
    meta["files"] = files
    json.dump(meta, open(os.path.join(SITE, "meta.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    meta["files"]["nonprofits/meta.json"] = {"bytes": os.path.getsize(os.path.join(SITE, "meta.json"))}
    json.dump(meta, open(os.path.join(SITE, "meta.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    print("commentary written")


if __name__ == "__main__":
    main()
