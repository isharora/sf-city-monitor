"""Match coverage and precision.

Coverage (dollar-weighted, expenditure-class payments):
  A. Of payments to vendors the CITY flags as nonprofit (flag exists FY2018+), share matched to an IRS EIN,
     with the unmatched remainder broken down by the adjudicator's vendor_type.
  B. Of payments to vendors judged to be exempt organizations by ANY signal (matched, or Claude said
     vendor_is_exempt_org = yes, or discovery said likely_exempt_org = yes), share matched.
  C. Share of the Controller's own nonprofit-spending dataset (qkex-vh98, FY2019-25, excl. UCSF) whose
     supplier+FY dollars we capture (matched by contract number x FY where possible).
Precision: from data/validation/hand_review.csv (stratified sample), overall and stratum-weighted by the
number of accepted matches (and by dollars) in each stratum.
Output: data/interim/results/coverage_precision.json
"""
import json, os
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

def main():
    p = pd.read_parquet(os.path.join(INT, "payments.parquet"))
    e = p[p.spend_class == "expenditure"]
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet"))
    props = pd.read_parquet(os.path.join(INT, "discover_proposals.parquet"))
    vmap = pd.read_parquet(os.path.join(INT, "vendor_map.parquet"))
    matched = set(vmap[vmap.org_class != "public_university"].vendor)  # public universities excluded as government
    for vname in vmap[vmap.org_class == "public_university"].vendor:
        m.loc[m.vendor == vname, "vendor_type"] = "university_or_hospital_system"
    exempt_yes = set(m[m.vendor_is_exempt_org == "yes"].vendor) | set(props[props.likely_exempt_org == "yes"].vendor)
    vt = m.set_index("vendor").vendor_type.to_dict()
    vt.update({r.vendor: r.vendor_type for r in props.itertuples() if r.vendor not in vt})
    out = {}
    f = e[(e.non_profit_indicator == "X") & (e.fiscal_year.between(2018, 2026))]
    tot = f.paid.sum()
    fm = f[f.vendor.isin(matched)].paid.sum()
    un = f[~f.vendor.isin(matched)].copy()
    un["type"] = un.vendor.map(vt).fillna("not_adjudicated")
    brk = un.groupby("type").paid.sum().sort_values(ascending=False)
    topun = un.groupby("vendor").paid.sum().sort_values(ascending=False).head(15)
    out["A_city_flag_fy2018_2026"] = {"total": tot, "matched": fm, "share_matched": fm / tot,
                                      "unmatched_by_type": brk.to_dict(), "top_unmatched": topun.to_dict()}
    ex = e[e.fiscal_year.between(2007, 2026)]
    likely = matched | exempt_yes | set(e[e.non_profit_indicator == "X"].vendor) - {v for v, t in vt.items() if t in ("government", "for_profit_company", "affordable_housing_partnership_or_llc", "university_or_hospital_system", "individual")}
    lt = ex[ex.vendor.isin(likely)].paid.sum()
    lm = ex[ex.vendor.isin(matched)].paid.sum()
    out["B_any_signal_fy2007_2026"] = {"likely_nonprofit_total": lt, "matched": lm, "share_matched": lm / lt}
    # C: Controller dataset
    q = pd.read_csv(os.path.join(BASE, "raw", "city_np", "qkex-vh98.csv"), dtype=str)
    q["amt"] = q["Completed Payments"].astype(float)
    q = q[q.Nonprofit != "UCSF"]
    cn_m = set(e[e.vendor.isin(matched)].contract_number)
    q["captured"] = q["Contract Number"].isin(cn_m)
    out["C_controller_dataset_fy2019_2025"] = {"total": q.amt.sum(), "share_by_contract_captured": q[q.captured].amt.sum() / q.amt.sum()}
    # precision
    h = pd.read_csv(os.path.join(BASE, "validation", "hand_review.csv"))
    acc = h[h.stratum == "accepted"].copy()
    acc["tier"] = pd.cut(acc.total_paid, [-1e18, 1e6, 1e7, 1e18], labels=["lt1m", "1m_10m", "ge10m"], right=False)
    v = pd.read_parquet(os.path.join(INT, "vendors.parquet")).set_index("vendor")
    mm = m[m.matched_ein != "NONE"].join(v.total_paid, on="vendor")
    mm["tier"] = pd.cut(mm.total_paid, [-1e18, 1e6, 1e7, 1e18], labels=["lt1m", "1m_10m", "ge10m"], right=False)
    pop_n = mm.tier.value_counts(); pop_d = mm.groupby("tier").total_paid.sum()
    strict = acc.groupby("tier").verdict.apply(lambda s: (s == "correct").mean())
    lenient = acc.groupby("tier").verdict.apply(lambda s: (s != "incorrect").mean())
    out["precision"] = {
        "n_reviewed_accepted": int(len(acc)),
        "raw_strict": float((acc.verdict == "correct").mean()), "raw_lenient": float((acc.verdict != "incorrect").mean()),
        "by_tier_strict": strict.to_dict(),
        "weighted_by_match_count_strict": float((strict * pop_n).sum() / pop_n.sum()),
        "weighted_by_dollars_strict": float((strict * pop_d).sum() / pop_d.sum()),
        "population_matches_by_tier": pop_n.to_dict()}
    none = h[h.stratum != "accepted"]
    out["recall_check"] = {s: g.verdict.value_counts().to_dict() for s, g in none.groupby("stratum")}
    # agreement with city nonprofit flag among matched vendors paid FY2018+
    recent = e[e.fiscal_year >= 2018].groupby("vendor").agg(paid=("paid", "sum"), flag=("non_profit_indicator", lambda s: (s == "X").any()))
    rm = recent[recent.index.isin(matched)]
    out["matched_vendors_city_flagged_share_dollars"] = float(rm[rm.flag].paid.sum() / rm.paid.sum())
    json.dump(out, open(os.path.join(INT, "results", "coverage_precision.json"), "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:4000])

if __name__ == "__main__":
    main()
