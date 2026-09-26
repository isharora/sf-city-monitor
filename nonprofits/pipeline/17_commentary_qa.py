"""Compute commentary facts (numbers computed from the exported site files) and run the contract QA checks.

Facts are computed here from data/site/*.json; the commentary itself is written by 18_commentary.py and checked by
verify_commentary.py. Writes data/site/qa_report.json,
data/site/commentary_facts.json and refreshes meta.files.
"""
import glob, json, os, statistics as st
from collections import Counter, defaultdict

SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "site")
RES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "interim", "results")
J = lambda p: json.load(open(os.path.join(SITE, p)))


def money(x):
    x = float(x)
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f} billion"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.0f} million"
    return f"${x:,.0f}"


def pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def main():
    meta = J("meta.json")
    idx = meta["deflator"]["index"]
    orgs = {o["id"]: o for o in J("orgs/index.json")["orgs"]}
    cells = [c for f in sorted(glob.glob(os.path.join(SITE, "payments", "cells_*.json"))) for c in json.load(open(f))["cells"]]
    tot = defaultdict(float); pay = defaultdict(float); dept_fy = defaultdict(float); org_fy = defaultdict(float)
    for c in cells:
        tot[c["fy"]] += c["amt"]; pay[(c["org"], c["fy"])] += c["amt"]; dept_fy[(c["dept"], c["fy"])] += c["amt"]
    F = {}
    F["fy_latest"] = 2025
    F["total_fy2025"] = tot[2025]; F["total_fy2016"] = tot[2016]; F["total_fy2007"] = tot[2007]
    F["total_fy2016_real2025"] = tot[2016] / idx["2016"]
    F["real_growth_fy2016_2025"] = tot[2025] / F["total_fy2016_real2025"] - 1
    F["nominal_multiple_fy2016_2025"] = tot[2025] / tot[2016]
    F["real_growth_fy2019_2025"] = tot[2025] / (tot[2019] / idx["2019"]) - 1
    by = defaultdict(float)
    for c in cells:
        if c["fy"] == 2025:
            by[c["org"]] += c["amt"]
    s = sorted(by.values(), reverse=True)
    F["orgs_fy2025"] = len(by); F["top10_share_fy2025"] = sum(s[:10]) / sum(s); F["top20_share_fy2025"] = sum(s[:20]) / sum(s)
    by16 = defaultdict(float)
    for c in cells:
        if c["fy"] == 2016:
            by16[c["org"]] += c["amt"]
    s16 = sorted(by16.values(), reverse=True); F["top20_share_fy2016"] = sum(s16[:20]) / sum(s16)
    d25 = sorted(((d, v) for (d, fy), v in dept_fy.items() if fy == 2025), key=lambda x: -x[1])
    F["top_depts_fy2025"] = [(d, v) for d, v in d25[:6]]
    F["top3_dept_share_fy2025"] = sum(v for _, v in d25[:3]) / tot[2025]
    F["hom_fy2019"] = dept_fy[("HOM", 2019)]; F["hom_fy2025"] = dept_fy[("HOM", 2025)]
    top10 = sorted(by.items(), key=lambda x: -x[1])[:10]
    F["top10_orgs_fy2025"] = [(orgs[o]["name"], v) for o, v in top10]
    # dependency (UI definition): city payments in fy / total_revenue of the 990 whose tax year ends in fy
    f24 = J("finances/form990_2024.json")["rows"]
    dep = [(r["org"], pay.get((r["org"], 2024), 0) / r["total_revenue"], pay.get((r["org"], 2024), 0), r) for r in f24 if r["total_revenue"] > 0]
    dep1 = [x for x in dep if x[2] >= 1e6]
    F["dep_fy"] = 2024; F["dep_n"] = len(dep1); F["dep_median"] = st.median(x[1] for x in dep1)
    F["dep_ge75_n"] = sum(x[1] >= 0.75 for x in dep1); F["dep_gt100_share"] = sum(x[1] > 1 for x in dep1) / len(dep1)
    F["large_dependent_n"] = sum(1 for x in dep if x[2] >= 5e6 and x[1] > 0.75)
    ex = [x[3]["exec_comp"] for x in dep1 if x[3]["exec_comp"]]
    F["pay_n"] = len(ex); F["pay_median"] = st.median(ex)
    rs = [x[3]["months_reserves"] for x in dep1 if x[3]["months_reserves"] is not None]
    F["res_n"] = len(rs); F["res_median"] = st.median(rs); F["res_lt1_n"] = sum(r < 1 for r in rs)
    F["res_neg_n"] = sum(r < 0 for r in rs)
    con = J("contracts/contracts.json")["contracts"]
    ratios = [c["agreed"] / c["original_agreed"] for c in con if c["original_agreed"]]
    F["con_n"] = len(con); F["con_amended_n"] = sum(1 for c in con if c["amendments"])
    F["con_median_ratio"] = st.median(ratios); F["con_doubled_n"] = sum(r >= 2 for r in ratios)
    am = [c["agreed"] / c["original_agreed"] for c in con if c["amendments"] and c["original_agreed"]]
    F["con_median_ratio_amended"] = st.median(am)
    F["con_emergency_share"] = sum(c["agreed"] for c in con if c["authority_class"] == "emergency_or_waiver") / sum(c["agreed"] for c in con)
    big = sorted(con, key=lambda c: -(c["agreed"] - (c["original_agreed"] or c["agreed"])))[:3]
    F["con_biggest"] = [(orgs[c["org"]]["name"], c["title"], c["original_agreed"], c["agreed"], c["first_snapshot"]) for c in big]
    fr = J("reviews/findings.json")["rows"]
    F["rev_n"] = len(fr); F["rev_orgs"] = len({r["org"] for r in fr})
    F["rev_none_share"] = sum(r["result"] == "none" for r in fr) / len(fr)
    F["rev_elev_orgs"] = len({r["org"] for r in fr if r["result"] in ("elevated", "redflag")})
    F["rev_by_fy"] = {str(k): v for k, v in Counter((r["fy"], r["result"]) for r in fr).items()}
    cov = json.load(open(os.path.join(RES, "coverage_precision.json")))
    F["coverage_any_signal"] = cov["B_any_signal_fy2007_2026"]["share_matched"]
    F["coverage_city_flag"] = cov["A_city_flag_fy2018_2026"]["share_matched"]
    F["precision_strict"] = cov["precision"]["raw_strict"]; F["precision_n"] = cov["precision"]["n_reviewed_accepted"]
    sm = json.load(open(os.path.join(RES, "summary.json")))
    F["comp_elasticity"] = sm["compensation"]["comp_elasticity"]; F["comp_n_fit"] = sm["compensation"]["n_orgs"]
    oc = json.load(open(os.path.join(SITE, "aggregates", "outcomes.json")))["ratios"]
    F["outcome_ratios"] = oc
    json.dump(F, open(os.path.join(SITE, "commentary_facts.json"), "w"), indent=1, default=str)

    # Commentary files are written by 18_commentary.py (which also uses data/redteam/redteam.json).

    # ---------------- QA
    qa = {}
    trends = {r["fiscal_year"]: r for r in J("aggregates/trends.json")["rows"]}
    qa["1_sum_cells_vs_processed"] = {str(fy): {"cells": tot[fy], "processed_nonprofit_all": trends[fy]["nonprofit_all"],
                                                "diff": tot[fy] - trends[fy]["nonprofit_all"],
                                                "city_flag_expenditure": trends[fy]["city_flag_expenditure"]} for fy in sorted(tot)}
    dims = meta["dimensions"]
    ids = {k: {v["id"] for v in dims[k]["values"]} for k in dims}
    bad = [c for c in cells if c["org"] not in orgs or c["dept"] not in ids["dept"]]
    bad_o = [o for o in orgs.values() if o["area"] not in ids["area"] or o["size_band"] not in ids["size_band"]]
    fr_bad = [r for r in fr if r["result"] not in ids["result"] or r["org"] not in orgs]
    qa["2_ids"] = {"bad_cells": len(bad), "bad_orgs": len(bad_o), "bad_findings": len(fr_bad)}
    ot = defaultdict(float); fmin = {}; fmax = {}
    for c in cells:
        ot[c["org"]] += c["amt"]; fmin[c["org"]] = min(fmin.get(c["org"], 9999), c["fy"]); fmax[c["org"]] = max(fmax.get(c["org"], 0), c["fy"])
    mism = [o for o in orgs.values() if abs(o["city_total"] - ot[o["id"]]) > len(cells) or o["first_fy"] != fmin[o["id"]] or o["last_fy"] != fmax[o["id"]]]
    qa["3_org_totals"] = {"mismatches": len(mism)}
    allf = [r for f in glob.glob(os.path.join(SITE, "finances", "form990_*.json")) for r in json.load(open(f))["rows"]]
    shares = [pay.get((r["org"], r["fy"]), 0) / r["total_revenue"] for r in allf if r["total_revenue"] and pay.get((r["org"], r["fy"]), 0) > 0]
    qa["4_form990"] = {"rows": len(allf), "revenue_nonpositive": sum(1 for r in allf if not r["total_revenue"] or r["total_revenue"] <= 0),
                       "share_org_years_city_share_gt_1": sum(s > 1 for s in shares) / len(shares)}
    qa["5_reviews"] = {"rows_missing_url": sum(1 for r in fr if not r["report"]["url"]),
                       "non_none_missing_page": sum(1 for r in fr if r["result"] != "none" and not r["report"]["page"]),
                       "urls": sorted({r["report"]["url"] for r in fr})}
    qa["7_network_id"] = "all null: no network/entities.json exists yet in any module"
    # files list
    files = {}
    for f in sorted(glob.glob(os.path.join(SITE, "**", "*.json"), recursive=True)):
        rel = os.path.relpath(f, SITE)
        if rel in ("meta.json",):
            continue
        files["nonprofits/" + rel] = {"bytes": os.path.getsize(f)}
    over = {k: v["bytes"] for k, v in files.items() if v["bytes"] > 400_000}
    qa["size_over_400kb"] = over
    meta["files"] = files
    json.dump(meta, open(os.path.join(SITE, "meta.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    meta["files"]["nonprofits/meta.json"] = {"bytes": os.path.getsize(os.path.join(SITE, "meta.json"))}
    json.dump(meta, open(os.path.join(SITE, "meta.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump(qa, open(os.path.join(SITE, "qa_report.json"), "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in qa.items() if k != "1_sum_cells_vs_processed"}, indent=1, default=float)[:3000])
    print(json.dumps(F, indent=1, default=str)[:3500])


if __name__ == "__main__":
    main()
