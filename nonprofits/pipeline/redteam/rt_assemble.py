"""Red team: assemble data/redteam/redteam.json (one record per headline finding).

Per finding: claim, original number(s), re-derived number(s), checks run (with results), verdict
(robust | fragile | corrected), what changed, and the numbers the commentary may cite ("cite").
Inputs: data/redteam/parts/{findings,revocations,contracts_llm}.json, data/interim/results/redteam.json
(the pipeline's earlier server-side re-check), data/llm_usage.jsonl (red-team spend).
"""
import json, os, statistics as st
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "..", "..", "data")
P = os.path.join(BASE, "redteam", "parts")
J = lambda f: json.load(open(os.path.join(P, f)))


def mean(xs):
    xs = [x for x in xs if x]
    return sum(xs) / len(xs) if xs else None


def main():
    F = J("findings.json"); RV = J("revocations.json"); CL = J("contracts_llm.json")
    old = json.load(open(os.path.join(BASE, "interim", "results", "redteam.json")))
    f1, f2, f3, f3b, f4, f5, f6 = (F["F1_total_and_growth"], F["F2_top20"], F["F3_dependency"], F["F3_dependency_fy2025"],
                                   F["F4_dependency_corrective"], F["F5_contracts"], F["F6_hsh_outcomes"])
    out = []
    # ---- 1 total
    out.append({"id": "total_fy2025", "claim": "The city paid $1.88 billion to 964 nonprofits in FY2025.",
        "original": {"total": 1880034944, "orgs": 964},
        "rederived": {"total": round(f1["raw_total_fy2025"]), "orgs": f1["orgs_fy2025_with_positive_cell"]},
        "checks": [
            {"check": "Recomputed from the raw per-FY payment aggregates with the csv module (not the pipeline tables)", "result": round(f1["raw_total_fy2025"])},
            {"check": "Server-side SoQL sum on data.sf.gov for the matched vendor names (pipeline red team R1)", "result": round(old["R1_fy2025_total_server"]["server"])},
            {"check": "Organizations with net-positive FY2025 payments", "result": f1["orgs_fy2025_net_positive"]},
            {"check": "Only matches with confidence >= 0.9 and no discovery-pass matches (growth FY2016-25, real)", "result": round(f1["real_growth_2016_2025_conf_ge_0_9_no_discovery"], 4)},
            {"check": "Controller's own Citywide Nonprofit Spending dataset (qkex-vh98), FY2025, excluding UCSF; narrower definition", "result": round(f1["controller_dataset_fy2025"])},
            {"check": "Payments to pass-through and fiscal-sponsor organizations in FY2025 (childcare-subsidy administrators, a loan fund, fiscal sponsors)", "result": round(f1["passthrough_orgs_fy2025"])},
            {"check": "Loans issued by the city to matched nonprofits in FY2025 (counted as payments)", "result": round(f1["loans_fy2025"])}],
        "verdict": "robust",
        "what_changed": "Nothing in the number. Commentary now says that about $277 million of FY2025 went to organizations that mostly pass money on (childcare subsidies, a loan fund, fiscal sponsors) and that the Controller's narrower dataset reports $1.63 billion.",
        "cite": {"total_fy2025": f1["raw_total_fy2025"], "orgs_fy2025": f1["orgs_fy2025_with_positive_cell"],
                 "passthrough_orgs_fy2025": f1["passthrough_orgs_fy2025"], "total_fy2025_excl_passthrough_orgs": f1["total_fy2025_excl_passthrough_orgs"],
                 "controller_dataset_fy2025": f1["controller_dataset_fy2025"], "loans_fy2025": f1["loans_fy2025"],
                 "passthrough_contracts_fy2025": f1["passthrough_contracts_fy2025"]}})
    # ---- 2 real growth
    b = f1["base_year_sensitivity_real_growth_to_2025"]
    out.append({"id": "real_growth_fy2016_2025", "claim": "Nonprofit payments rose 132% after inflation from FY2016 to FY2025.",
        "original": {"real_growth": 1.3221314341819}, "rederived": {"real_growth": f1["real_growth_2016_2025"]["sf_cpi"]},
        "checks": [
            {"check": "SF-Oakland-Hayward CPI-U recomputed from the raw BLS file (FY averages)", "result": round(f1["real_growth_2016_2025"]["sf_cpi"], 4)},
            {"check": "U.S. city-average CPI-U instead", "result": round(f1["real_growth_2016_2025"]["us_cpi"], 4)},
            {"check": "U.S. CPI-U services instead (nonprofit costs are mostly wages)", "result": round(f1["real_growth_2016_2025"]["us_services_cpi"], 4)},
            {"check": "Excluding pass-through and fiscal-sponsor organizations in both years", "result": round(f1["real_growth_2016_2025_excl_passthrough_orgs"], 4)},
            {"check": "Also excluding city loans", "result": round(f1["real_growth_2016_2025_excl_passthrough_and_loans"], 4)},
            {"check": "Adjusting both years for the matched share of City Grant Program dollars (FY2016 86.8%, FY2025 92.8%)", "result": round(f1["real_growth_2016_2025_coverage_adjusted"], 4)},
            {"check": "Base-year sensitivity (real growth to FY2025 from FY2015 / 2016 / 2017 / 2018 / 2019)", "result": {k: round(v, 4) for k, v in b.items()}},
            {"check": "Benchmark: nominal growth FY2019-FY2025, this dashboard vs the Controller's dataset", "result": {"dashboard": round(f1["this_dashboard_nominal_growth_2019_2025"], 4), "controller": round(f1["controller_dataset_nominal_growth_2019_2025"], 4)}},
            {"check": "Chart-of-accounts change (FAMIS to PeopleSoft, FY2018): non-expenditure characters among matched vendors are health-benefit trust payments, excluded consistently", "result": "no effect on the expenditure definition"}],
        "verdict": "robust",
        "what_changed": "The claim 'more than doubled after inflation' survives every deflator and exclusion tested from the FY2016 base (+113% to +134%), but the exact figure depends on the base year (+96% from FY2017, +144% from FY2015). Commentary gives +132% with that range and the +113% pass-through-excluded figure.",
        "cite": {"total_fy2016": f1["raw_total_fy2016"], "real_growth_sf_cpi": f1["real_growth_2016_2025"]["sf_cpi"],
                 "real_growth_us_cpi": f1["real_growth_2016_2025"]["us_cpi"], "real_growth_services_cpi": f1["real_growth_2016_2025"]["us_services_cpi"],
                 "real_growth_excl_passthrough": f1["real_growth_2016_2025_excl_passthrough_orgs"],
                 "real_growth_from_fy2015": b["2015"], "real_growth_from_fy2017": b["2017"], "real_growth_from_fy2019": b["2019"],
                 "nominal_growth_2019_2025": f1["this_dashboard_nominal_growth_2019_2025"],
                 "controller_nominal_growth_2019_2025": f1["controller_dataset_nominal_growth_2019_2025"],
                 "coverage_grant_2016": f1["grant_character_matched_share"]["2016"], "coverage_grant_2025": f1["grant_character_matched_share"]["2025"]}})
    # ---- 3 top 20
    ser = [v for k, v in f2["series"].items() if int(k) >= 2008]
    out.append({"id": "top20_share", "claim": "The 20 largest recipients received 45% of FY2025 nonprofit dollars.",
        "original": {"fy2025": 0.44658371360569776, "fy2016": 0.45105601448898197}, "rederived": {"fy2025": f2["fy2025_by_ein"], "fy2016": f2["fy2016_by_ein"]},
        "checks": [{"check": "Recomputed by EIN from raw CSVs", "result": round(f2["fy2025_by_ein"], 4)},
                   {"check": "By city vendor name instead of EIN", "result": round(f2["fy2025_by_vendor_name"], 4)},
                   {"check": "Excluding pass-through and fiscal-sponsor organizations (FY2025 / FY2016)", "result": [round(f2["fy2025_excl_passthrough_orgs"], 4), round(f2["fy2016_excl_passthrough_orgs"], 4)]},
                   {"check": "Range FY2008-FY2026", "result": [round(min(ser), 4), round(max(ser), 4)]},
                   {"check": "Pass-through organizations among the FY2025 top 20", "result": f2["fy2025_top20_passthrough_members"]}],
        "verdict": "robust",
        "what_changed": f"None. Commentary adds that {len(f2['fy2025_top20_passthrough_members'])} of the top 20 mostly pass money on and that the share has stayed between {100 * min(ser):.0f}% and {100 * max(ser):.0f}% since FY2008.",
        "cite": {"top20_fy2025": f2["fy2025_by_ein"], "top20_fy2016": f2["fy2016_by_ein"], "top20_fy2025_excl_passthrough": f2["fy2025_excl_passthrough_orgs"],
                 "top20_min_2008_2026": min(ser), "top20_max_2008_2026": max(ser), "top10_fy2025": f2["fy2025_top10"],
                 "top20_passthrough_count": len(f2["fy2025_top20_passthrough_members"])}})
    # ---- 4 dependency
    u = f3["ui_definition_fy2024"]
    out.append({"id": "dependency", "claim": "Among organizations paid at least $1 million in FY2024, the median got 45% of its revenue from the city; 41 got more than 75%.",
        "original": {"n": 199, "median": 0.4486960428642654, "n_gt_75": 41}, "rederived": {"n": u["n"], "median": u["median"], "n_gt_75": u["n_gt_75"]},
        "checks": [{"check": f"Variant: {k}", "result": {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}}
                   for k, v in f3.items() if isinstance(v, dict) and "median" in v] +
                  [{"check": "Coverage: organizations paid >= $1M in FY2024 that have a FY2024 Form 990", "result": f3["coverage"]},
                   {"check": "FY2025 (the dashboard's default year) variants", "result": {k: v for k, v in f3b.items()}}],
        "verdict": "robust",
        "what_changed": "None in FY2024 (median 43%-48% and 37-44 organizations above 75% across alignment, pass-through and year variants). The dashboard's default year is FY2025, where the median is similar (46%) but 13 organizations exceed 100%, a sign the latest filings and payments are not yet aligned; commentary keeps FY2024 as the anchor and says why. Commentary also explains that the live sentence covers all ~920 organizations with a 990 (median 7%), not only large recipients.",
        "cite": {"dep_n_2024": u["n"], "dep_median_2024": u["median"], "dep_gt75_2024": u["n_gt_75"], "dep_gt100_share_2024": u["share_gt_100"],
                 "dep_median_prorated_2024": f3["prorated_to_tax_year"]["median"], "dep_gt75_prorated_2024": f3["prorated_to_tax_year"]["n_gt_75"],
                 "dep_median_june_2024": f3["june_fye_only"]["median"], "dep_median_2023": f3["fy2023_instead"]["median"], "dep_gt75_2023": f3["fy2023_instead"]["n_gt_75"],
                 "dep_gt75_excl_over100_2024": f3["excluding_ratios_over_100"]["n_gt_75"], "dep_non_june_share_2024": f3["non_june_share"],
                 "dep_coverage_2024": f3["coverage"]["share_with_990"],
                 "dep_n_2025": f3b["ui_definition"]["n"], "dep_median_2025": f3b["ui_definition"]["median"], "dep_gt75_2025": f3b["ui_definition"]["n_gt_75"],
                 "dep_gt100_n_2025": round(f3b["ui_definition"]["share_gt_100"] * f3b["ui_definition"]["n"]),
                 "dep_all_n_2025": f3b["all_orgs_with_990_any_payment"]["n"], "dep_all_median_2025": f3b["all_orgs_with_990_any_payment"]["median"],
                 "large_dependent_2025": f3b["large_and_dependent_ge_5m"]}})
    # ---- 5 dependency and corrective action
    ol = f4["org_level"]
    out.append({"id": "dependency_corrective_action", "claim": "Organization-years more than 75% dependent on the city were about four times as likely to be on corrective action, Tier 3 or red flag (13% vs 3%).",
        "original": {"rate_hi": 0.1322314049586777, "rate_lo": 0.032188841201716736}, "rederived": {"rate_hi": f4["rate_hi"], "rate_lo": f4["rate_lo"], "ratio": f4["ratio"]},
        "checks": [
            {"check": "Counts (FY2023-25 org-years with a matching 990)", "result": {"n": f4["n_org_years"], "hi": f4["n_hi"], "severe_hi": f4["severe_hi"], "severe_lo": f4["severe_lo"]}},
            {"check": "Organization-level permutation (labels shuffled by organization)", "result": round(f4["cluster_perm_p"], 4)},
            {"check": "Mantel-Haenszel risk ratio stratified by size band / service area / fiscal year", "result": [round(f4["by_size_band"]["mh_risk_ratio"], 2), round(f4["by_area"]["mh_risk_ratio"], 2), round(f4["by_fy"]["mh_risk_ratio"], 2)]},
            {"check": "Logistic regression with log revenue, service area and year; cluster-robust by organization (odds ratio, 95% CI)", "result": [round(f4["logit_adjusted"]["odds_ratio_hi"], 2)] + [round(x, 2) for x in f4["logit_adjusted"]["ci95"]]},
            {"check": "Same, also controlling for under one month of reserves", "result": [round(f4["logit_adjusted_plus_reserves"]["odds_ratio_hi"], 2)] + [round(x, 2) for x in f4["logit_adjusted_plus_reserves"]["ci95"]]},
            {"check": "Dependency prorated to the organization's tax year", "result": f4["variant_prorated_dependency"]},
            {"check": "Excluding pass-through and fiscal-sponsor organizations", "result": f4["variant_excl_passthrough_orgs"]},
            {"check": "June fiscal-year-end organizations only (exact alignment)", "result": f4["variant_june_fye_only"]},
            {"check": "Organization level (each counted once; Fisher exact one-sided p)", "result": ol},
            {"check": "Threshold sensitivity (50/60/75/90%)", "result": f4["threshold_sensitivity"]},
            {"check": "First monitored year per organization only (the tier policy began in FY2024, so few events)", "result": f4["first_year_per_org"]},
            {"check": "Median revenue of high vs other org-years (size confounding)", "result": [f4["median_revenue_hi"], f4["median_revenue_lo"]]}],
        "verdict": "robust",
        "what_changed": "The association holds after size, service area, year, alignment and pass-through checks and when each organization is counted once (13 of 44 vs 9 of 199). It rests on {sev} severe org-years at {sevo} organizations, many of them repeat designations, and is not evidence that dependency causes problems. Commentary states it as an association with those limits and the competing explanations.".format(sev=f4["severe_hi"] + f4["severe_lo"], sevo=f4["distinct_severe_orgs"]),
        "cite": {"assoc_n": f4["n_org_years"], "assoc_orgs": f4["n_orgs"], "assoc_hi_n": f4["n_hi"], "assoc_sev_hi": f4["severe_hi"], "assoc_sev_lo": f4["severe_lo"],
                 "assoc_lo_n": f4["n_org_years"] - f4["n_hi"], "assoc_rate_hi": f4["rate_hi"], "assoc_rate_lo": f4["rate_lo"], "assoc_ratio": f4["ratio"],
                 "assoc_or_adj": f4["logit_adjusted"]["odds_ratio_hi"], "assoc_or_adj_lo": f4["logit_adjusted"]["ci95"][0], "assoc_or_adj_hi": f4["logit_adjusted"]["ci95"][1],
                 "assoc_org_hi_n": ol["n_orgs_hi"], "assoc_org_hi_sev": ol["severe_orgs_hi"], "assoc_org_lo_n": ol["n_orgs_lo"], "assoc_org_lo_sev": ol["severe_orgs_lo"],
                 "assoc_org_rate_hi": ol["rate_hi"], "assoc_org_rate_lo": ol["rate_lo"],
                 "assoc_severe_events": f4["severe_hi"] + f4["severe_lo"], "assoc_severe_orgs": f4["distinct_severe_orgs"],
                 "res_lt1_share_hi": f4["reserves_lt1_hi_share"], "res_lt1_share_lo": f4["reserves_lt1_lo_share"],
                 "res_lt1_severe_rate": f4["reserves_lt1_severe"]["rate_lt1"], "res_ge1_severe_rate": f4["reserves_lt1_severe"]["rate_ge1"]}})
    # ---- 6 contracts
    drv = Counter(c["primary_driver"] for c in CL)
    ex = f5["examples"]
    def ann(cid, a, b_):
        p = ex[cid]["paid_by_fy"]
        return mean([p.get(str(y)) for y in a]), mean([p.get(str(y)) for y in b_])
    h_before, h_after = ann("1000010457", (2020, 2021, 2022), (2025, 2026))
    t_before, t_after = ex["1000017241"]["paid_by_fy"]["2021"], ex["1000017241"]["paid_by_fy"]["2025"]
    llm_c = {c["id"]: c for c in CL}
    out.append({"id": "contracts_doubled", "claim": "216 of 974 large nonprofit contracts at least doubled from their first observed amount (e.g., HealthRIGHT 360 and Tenderloin Housing Clinic).",
        "original": {"n": 974, "doubled": 216}, "rederived": {"n": f5["n_contracts_independent"], "doubled": f5["n_doubled_independent"], "agree_with_site": f5["doubled_agree"]},
        "checks": [
            {"check": "Recomputed from the four raw Supplier Contracts snapshots", "result": [f5["n_contracts_independent"], f5["n_doubled_independent"]]},
            {"check": "Term end moved out by 6+ months since first observation", "result": f5["n_term_extended_6m"]},
            {"check": "Amount per year of term at least doubled", "result": f5["n_annualized_ratio_ge_2"]},
            {"check": "Amount per year of term up less than 1.5x", "result": f5["n_annualized_ratio_lt_1_5"]},
            {"check": "Actual annual payments up 1.5x or more (of those with payment history)", "result": [f5["n_run_rate_ge_1_5"], f5["n_run_rate_known"]]},
            {"check": "First observed in April 2021 (the rest were first seen in Dec 2022 or Nov 2025, so earlier amendments are invisible)", "result": [f5["n_first_seen_2021"], f5["n_first_seen_later"]]},
            {"check": "Claude (claude-opus-5-5, effort high) classification of the growth driver from title, scope field, term history, per-year ratio and payments", "result": dict(drv)},
            {"check": "Title or scope text explicitly shows new scope or sites", "result": dict(Counter(c["text_shows_new_scope_or_sites"] for c in CL))},
            {"check": "Classification confidence (median; count below 0.6)", "result": [st.median(c["confidence"] for c in CL), sum(c["confidence"] < 0.6 for c in CL)]},
            {"check": "HealthRIGHT 360, DPH 'MH&SA res & OP' (1000010457)", "result": {**ex["1000010457"], "llm": {k: llm_c["1000010457"][k] for k in ("primary_driver", "secondary_driver", "confidence", "rationale")}}},
            {"check": "Tenderloin Housing Clinic, HSH 'Master Lease Hotels-CNC & NCNC' (1000017241)", "result": {**ex["1000017241"], "llm": {k: llm_c["1000017241"][k] for k in ("primary_driver", "secondary_driver", "confidence", "rationale")}}}],
        "verdict": "corrected",
        "what_changed": "The count is exact, but 'doubled' mostly means 'longer': 211 of the 216 had their end date pushed out, only 35 doubled per year of term, and Claude classed 162 as mainly extensions, 44 as larger annual levels, 8 as funding for years already in the term and 2 as rate or volume. The short title fields almost never show whether scope changed. Commentary and the growth headline now say this; both examples also grew in yearly payments, about 1.9x in nominal dollars for each.",
        "cite": {"con_n": f5["n_contracts_independent"], "con_doubled": f5["n_doubled_independent"], "con_term_extended": f5["n_term_extended_6m"],
                 "con_annual_doubled": f5["n_annualized_ratio_ge_2"], "con_llm_extension": drv.get("extension", 0), "con_llm_expansion": drv.get("expansion", 0),
                 "con_llm_funding_increment": drv.get("funding_increment", 0), "con_llm_rate_volume": drv.get("rate_or_volume", 0),
                 "con_text_cannot_tell": sum(c["text_shows_new_scope_or_sites"] == "cannot_tell" for c in CL),
                 "con_run_rate_up": f5["n_run_rate_ge_1_5"], "con_run_rate_known": f5["n_run_rate_known"],
                 "hr360_orig": ex["1000010457"]["orig"], "hr360_now": ex["1000010457"]["now"], "hr360_orig_end_year": int(ex["1000010457"]["orig_end"][:4]),
                 "hr360_end_year": int(ex["1000010457"]["end"][:4]), "hr360_per_year_ratio": ex["1000010457"]["annualized_ratio"],
                 "hr360_paid_fy2020_22_avg": h_before, "hr360_paid_fy2025_26_avg": h_after, "hr360_paid_ratio": h_after / h_before,
                 "thc_orig": ex["1000017241"]["orig"], "thc_now": ex["1000017241"]["now"], "thc_orig_end_year": int(ex["1000017241"]["orig_end"][:4]),
                 "thc_end_year": int(ex["1000017241"]["end"][:4]), "thc_per_year_ratio": ex["1000017241"]["annualized_ratio"],
                 "thc_paid_fy2021": t_before, "thc_paid_fy2025": t_after, "thc_paid_ratio": t_after / t_before}})
    # ---- 7 HSH vs outcomes
    out.append({"id": "hsh_spending_vs_placements", "claim": "HSH's real nonprofit spending rose 221% while households housed rose 62%.",
        "original": {"real_spend": 2.2238679324957746, "placed": 0.6228194247996228, "years": "FY2018-FY2026"},
        "rederived": {"real_spend": f6["pipeline_pair_2018_2026"]["real_spend"], "placed": f6["pipeline_pair_2018_2026"]["placed"]},
        "checks": [
            {"check": "Same endpoints recomputed from raw payments (HOM) and outcomes.csv", "result": f6["pipeline_pair_2018_2026"]},
            {"check": "Placement series: FY2018-22 are sums of monthly scorecard counts; FY2023+ are the annual performance measure (a different series); FY2026 is the June year-to-date figure", "result": f6["placed_basis"]},
            {"check": "FY2019-FY2025 (complete years, avoids HSH's start-up year)", "result": f6["pair_2019_2025"]},
            {"check": "FY2023-FY2025, one consistent placement series", "result": f6["pair_2023_2025_same_series"]},
            {"check": "FY2023-FY2026, one consistent placement series", "result": f6["pair_2023_2026_same_series"]},
            {"check": "Adding HSA payments to homelessness-area organizations (reorganization check)", "result": f6["pair_2018_2026_incl_hsa_homeless_orgs"]},
            {"check": "Base year FY2018 was HSH's first full year; homelessness contracts were still moving from HSA", "result": f6["hsa_payments_to_homeless_area_orgs"]}],
        "verdict": "fragile",
        "what_changed": "The +222% and +62% reproduce (the '221%' in the brief is a rounding slip), but they compare a start-up year with a spliced placement series. Spending outgrew placements in every window tested, yet the gap ranges from +136% vs +80% (FY2019-25) to +22% vs -13% (FY2023-25, one consistent series). Spending also bought shelter, outreach and prevention that placements do not measure. Commentary now leads with the consistent-series comparison and gives the range; no causal claim.",
        "cite": {"hsh_real_2018_2026": f6["pipeline_pair_2018_2026"]["real_spend"], "hsh_placed_2018_2026": f6["pipeline_pair_2018_2026"]["placed"],
                 "hsh_real_2019_2025": f6["pair_2019_2025"]["real_spend"], "hsh_placed_2019_2025": f6["pair_2019_2025"]["placed"],
                 "hsh_real_2023_2025": f6["pair_2023_2025_same_series"]["real_spend"], "hsh_placed_2023_2025": f6["pair_2023_2025_same_series"]["placed"],
                 "hsh_real_2023_2026": f6["pair_2023_2026_same_series"]["real_spend"], "hsh_placed_2023_2026": f6["pair_2023_2026_same_series"]["placed"],
                 "hom_fy2019": f6["hom_nominal"]["2019"], "hom_fy2025": f6["hom_nominal"]["2025"],
                 "placed_2023": f6["placed"]["2023"], "placed_2025": f6["placed"]["2025"]}})
    # ---- 8 revocations
    s = RV["summary"]; pub = [o for o in RV["orgs"] if o.get("publishable")]
    excl = [o for o in RV["orgs"] if o["status"] == "revoked_not_reinstated" and not o.get("publishable")]
    top = max(pub, key=lambda o: o["paid_after_posting"])
    out.append({"id": "paid_after_irs_revocation", "claim": "8 organizations were paid $1.87 million after the IRS revoked their tax exemption.",
        "original": {"orgs": 8, "amount": 1865221.44}, "rederived": {"orgs": s["publishable_count"], "amount": s["publishable_amount_after_posting"]},
        "checks": [
            {"check": "Raw IRS auto-revocation list re-parsed (all entries per EIN, with posting and reinstatement dates) and the current Business Master File searched by EIN and by name", "result": {"candidates_with_later_payments": s["candidates_revoked_with_later_fy_payments"], "not_reinstated_pipeline_definition": s["pipeline_def_count_not_in_bmf"], "amount_pipeline_definition": s["pipeline_def_amount_not_in_bmf"]}},
            {"check": "Voucher-level payments re-fetched from data.sf.gov; only payments dated after the IRS posted the revocation count (FY2007-17 rows: only fiscal years starting after posting)", "result": {"orgs": s["publishable_count"], "amount": s["publishable_amount_after_posting"]}},
            {"check": "Match confidence >= 0.9 required to name an organization", "result": "applied"},
            {"check": "Per-organization results", "result": [{k: o.get(k) for k in ("ein", "irs_name", "subsection", "match_confidence", "revocations", "paid_after_revocation_fy_pipeline_def", "paid_after_posting", "paid_between_revocation_and_posting", "first_payment_after_posting", "last_payment_after_posting", "fiscal_years_after_posting", "depts_after_posting", "last_990_on_file", "publishable", "exclusion_reason")} for o in RV["orgs"] if o["status"] == "revoked_not_reinstated"]}],
        "verdict": "corrected",
        "what_changed": f"Corrected to {s['publishable_count']} organizations and ${s['publishable_amount_after_posting']:,.0f}. Dropped: a vendor matched to a revoked EIN only through a DBA alias (confidence 0.55) whose last payment came before the IRS posted the revocation; an organization matched at 0.85 whose revocation was posted in August 2025, recent enough that reinstatement may be pending; and one whose only later payments predate the posting. One organization accounts for {100 * s['largest_share']:.0f}% of the corrected amount. Automatic revocation is for missed filings, is often reversed retroactively, and is not a finding of misconduct; commentary reports the pattern in aggregate with that context and does not name the organizations.",
        "cite": {"rev_orgs": s["publishable_count"], "rev_amount": s["publishable_amount_after_posting"], "rev_largest_share": s["largest_share"],
                 "rev_largest_amount": top["paid_after_posting"], "rev_largest_first_fy": min(top["fiscal_years_after_posting"]),
                 "rev_largest_last_fy": max(top["fiscal_years_after_posting"]), "rev_pipeline_orgs": s["pipeline_def_count_not_in_bmf"],
                 "rev_pipeline_amount": s["pipeline_def_amount_not_in_bmf"], "rev_excluded": len(excl)}})
    spend = 0.0
    for line in open(os.path.join(BASE, "llm_usage.jsonl")):
        j = json.loads(line)
        if j["task"].startswith(("redteam", "commentary")):
            spend += j["cost_usd"]
    res = {"generated_by": "pipeline/redteam/rt_assemble.py", "as_of": "2026-09-26",
           "method": "Independent re-derivation from raw inputs (payments CSVs, Supplier Contracts snapshots, IRS files, voucher API) plus robustness tests; see pipeline/redteam/*.py.",
           "verdicts": dict(Counter(f["verdict"] for f in out)), "findings": out,
           "fairness_changes": [
               "Monitoring notes: no longer truncated mid-sentence (truncation had cut off 'it does not say which applied to each nonprofit'); report statements about a group of organizations are replaced by a sentence saying the report does not attribute them.",
               "Organization profiles: a past IRS automatic revocation is now shown with its outcome (restored and currently listed, or not), plus what automatic revocation means.",
               "News items in reviews/other_findings.json carry a statement_type (allegation, criminal charge not a conviction, official action, settlement, context); a news item about criminal charges against two shelter staff members (not the organization, and below executive level) was removed; an item naming a fiscal sponsor only as the payment channel is labelled 'no allegation against this organization'.",
               "Revocation finding reported in aggregate only, with posting-date and match-confidence rules, and the context that revocation reflects missed filings."],
           "llm_spend_usd": round(spend, 2)}
    json.dump(res, open(os.path.join(BASE, "redteam", "redteam.json"), "w"), indent=1, default=float)
    print(json.dumps({"verdicts": res["verdicts"], "llm_spend_usd": res["llm_spend_usd"]}))


if __name__ == "__main__":
    main()
