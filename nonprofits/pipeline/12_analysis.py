"""Analysis: produces data/interim/results/*.csv|json used by ANALYSIS.md and the site export.

Definitions (see DATA_NOTES.md):
  city payments   = vouchers_paid in expenditure-class characters (excludes liability clearing,
                    benefit-trust, debt service, revenue refunds, pass-through assessments)
  nonprofit       = vendor matched to an IRS exempt-organization EIN (any 501(c) subsection)
  core nonprofits = matched orgs excluding large institutions (hospitals/universities by NTEE) and
                    non-501(c)(3) organizations
  real dollars    = FY2025 dollars using the SF-Oakland-Hayward CPI-U (BLS CUURS49BSA0) FY average
"""
import glob, json, os
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, os.path.dirname(__file__))
from lib_authority import classify
from lib_names import norm

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")
RES = os.path.join(INT, "results")
os.makedirs(RES, exist_ok=True)
FULL_YEARS = list(range(2007, 2027))  # FY2027 is partial (data through Sep 2026)


def save(df, name):
    df.to_csv(os.path.join(RES, name + ".csv"), index=False)


def load():
    d = {}
    d["p"] = pd.read_parquet(os.path.join(INT, "payments.parquet"))
    d["np"] = pd.read_parquet(os.path.join(INT, "np_payments.parquet"))
    d["vm"] = pd.read_parquet(os.path.join(INT, "vendor_map.parquet"))
    d["oy"] = pd.read_parquet(os.path.join(INT, "org_year.parquet"))
    d["al"] = pd.read_parquet(os.path.join(INT, "aligned.parquet"))
    d["cpi"] = pd.read_parquet(os.path.join(INT, "cpi.parquet")).set_index("fy").deflator_to_fy2025
    d["orgs"] = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    return d


def org_names(d):
    vm = d["vm"]
    top_vendor = (d["np"].groupby(["ein", "vendor"]).paid.sum().reset_index().sort_values("paid", ascending=False)
                  .drop_duplicates("ein").set_index("ein").vendor)
    names = vm.drop_duplicates("ein").set_index("ein")
    names["display_name"] = names.org_name.fillna(top_vendor)
    names["city_vendor_name"] = top_vendor
    return names


def trends(d):
    p, npay, cpi = d["p"], d["np"], d["cpi"]
    exp = p[p.spend_class == "expenditure"]
    t = pd.DataFrame({"all_expenditure": exp.groupby("fiscal_year").paid.sum(),
                      "all_contracted_services": exp[exp.service_class == "contracted_services"].groupby("fiscal_year").paid.sum(),
                      "nonprofit_all": npay.groupby("fiscal_year").paid.sum(),
                      "nonprofit_core": npay[npay.org_class == "501c3"].groupby("fiscal_year").paid.sum(),
                      "nonprofit_contracted_services": npay[npay.service_class == "contracted_services"].groupby("fiscal_year").paid.sum(),
                      "n_orgs_paid": npay[npay.paid > 0].groupby("fiscal_year").ein.nunique(),
                      "city_flag_all_characters": p[p.non_profit_indicator == "X"].groupby("fiscal_year").paid.sum(),
                      "city_flag_expenditure": exp[exp.non_profit_indicator == "X"].groupby("fiscal_year").paid.sum(),
                      }).fillna(0)
    # Controller's own nonprofit spending dataset (qkex-vh98) for comparison
    q = pd.read_csv(os.path.join(BASE, "raw", "city_np", "qkex-vh98.csv"), dtype=str)
    q["amt"] = q["Completed Payments"].astype(float)
    q["fy"] = q["Fiscal Year"].astype(int)
    t["controller_dataset_excl_ucsf"] = q[q.Nonprofit != "UCSF"].groupby("fy").amt.sum()
    t = t.reset_index().rename(columns={"index": "fiscal_year"})
    t["deflator_to_fy2025"] = t.fiscal_year.map(cpi)
    t["nonprofit_all_real2025"] = t.nonprofit_all * t.deflator_to_fy2025
    t["nonprofit_core_real2025"] = t.nonprofit_core * t.deflator_to_fy2025
    t["nonprofit_share_of_expenditure"] = t.nonprofit_all / t.all_expenditure
    t["partial_year"] = t.fiscal_year == 2027
    # concentration
    rows = []
    for fy, g in npay.groupby("fiscal_year"):
        s = g.groupby("ein").paid.sum().sort_values(ascending=False)
        s = s[s > 0]
        sh = s / s.sum()
        rows.append({"fiscal_year": fy, "top20_share": sh.head(20).sum(), "top10_share": sh.head(10).sum(),
                     "top50_share": sh.head(50).sum(), "hhi": float((sh ** 2).sum() * 10000),
                     "orgs_for_80pct": int((sh.cumsum() < 0.8).sum() + 1)})
    t = t.merge(pd.DataFrame(rows), on="fiscal_year", how="left")
    save(t, "trends")
    return t


def departments(d):
    npay, p = d["np"], d["p"]
    exp = p[p.spend_class == "expenditure"]
    a = npay.groupby(["department_code", "fiscal_year"]).paid.sum().rename("nonprofit_paid").reset_index()
    b = exp.groupby(["department_code", "fiscal_year"]).paid.sum().rename("dept_expenditure_to_vendors").reset_index()
    names = exp.groupby("department_code").department.agg(lambda s: s.value_counts().index[0])
    x = a.merge(b, on=["department_code", "fiscal_year"], how="left")
    x["department"] = x.department_code.map(names)
    x["nonprofit_share_of_vendor_spend"] = x.nonprofit_paid / x.dept_expenditure_to_vendors
    x["n_orgs"] = x.set_index(["department_code", "fiscal_year"]).index.map(
        npay[npay.paid > 0].groupby(["department_code", "fiscal_year"]).ein.nunique()).values
    save(x, "departments_by_year")
    ar = npay.groupby(["area", "fiscal_year"]).paid.sum().reset_index()
    save(ar, "areas_by_year")
    return x


def dependency(d, names):
    al, oy = d["al"].copy(), d["oy"]
    al = al[al.form.isin(["990", "990EZ"]) & (al.total_revenue > 0)]
    tot = oy.groupby("ein").city_paid.sum()
    al["city_total_all_years"] = al.ein.map(tot)
    al["display_name"] = al.ein.map(names.display_name)
    save(al.drop(columns=[c for c in al.columns if al[c].dtype == object and c not in
                          ("ein", "period_end", "form", "source", "display_name", "filer_name", "return_type")]),
         "filings_aligned")
    # latest filing per org with meaningful city money
    latest = al.sort_values("period_end").groupby("ein").tail(1)
    big = latest[latest.city_paid_aligned >= 1e6]
    summ = {"n_orgs_city_ge_1m_latest": int(len(big)),
            "median_dependency": float(big.dependency.median()),
            "share_dep_ge_50": float((big.dependency >= 0.5).mean()),
            "share_dep_ge_75": float((big.dependency >= 0.75).mean()),
            "share_dep_gt_105": float((big.dependency > 1.05).mean()),
            "latest_period_median": str(sorted(big.period_end)[len(big)//2] if len(big) else "")}
    # quick dependency growth: first year dependency < 25% and within <= 5 years >= 60%
    fast = []
    for ein, g in al[al.total_revenue >= 5e5].sort_values("period_end").groupby("ein"):
        g = g[g.dependency.notna()]
        if len(g) < 3:
            continue
        vals = list(zip(g.fy_end_year, g.dependency, g.total_revenue, g.city_paid_aligned))
        for i, (y0, d0, r0, c0) in enumerate(vals):
            if d0 < 0.25:
                for y1, d1, r1, c1 in vals[i + 1:]:
                    if y1 - y0 <= 5 and d1 >= 0.6 and d1 <= 1.05 and c1 >= 2e6:
                        fast.append({"ein": ein, "name": names.display_name.get(ein), "from_year": y0, "dep_from": d0,
                                     "rev_from": r0, "city_from": c0, "to_year": y1, "dep_to": d1, "rev_to": r1, "city_to": c1})
                        break
                else:
                    continue
                break
    fast = pd.DataFrame(fast)
    save(fast, "fast_dependency")
    summ["n_fast_dependency"] = int(len(fast))
    return summ, latest


def compensation(d, names):
    off = pd.read_parquet(os.path.join(INT, "officers990.parquet"))
    al = d["al"]
    off["total_comp"] = off.comp_org.fillna(0) + off.comp_related.fillna(0) + off.comp_other.fillna(0)
    ex = off[(off.officer | off.key_employee) & ~off.former.fillna(False)]
    top = ex.sort_values("total_comp", ascending=False).drop_duplicates(["ein", "period_end"])
    top = top.merge(al[["ein", "period_end", "total_expenses", "total_revenue", "total_employees", "city_paid_aligned", "dependency"]],
                    on=["ein", "period_end"], how="left")
    top["comp_pct_expenses"] = top.total_comp / top.total_expenses
    top["display_name"] = top.ein.map(names.display_name)
    top = top[top.total_comp > 0]
    # size-adjusted: log-log fit on latest filing per org
    latest = top.sort_values("period_end").groupby("ein").tail(1)
    latest = latest[(latest.total_expenses > 1e6)]
    X = np.log(latest.total_expenses); Y = np.log(latest.total_comp)
    b, a = np.polyfit(X, Y, 1)
    latest["expected_comp"] = np.exp(a + b * X)
    latest["comp_vs_expected"] = latest.total_comp / latest.expected_comp
    save(top[["ein", "display_name", "period_end", "title", "name", "total_comp", "comp_org", "comp_related", "comp_other",
              "total_expenses", "comp_pct_expenses", "city_paid_aligned", "dependency"]], "top_exec_comp_by_filing")
    save(latest[["ein", "display_name", "period_end", "title", "total_comp", "total_expenses", "expected_comp",
                 "comp_vs_expected", "dependency", "city_paid_aligned"]].sort_values("comp_vs_expected", ascending=False),
         "exec_comp_latest_size_adjusted")
    return {"comp_elasticity": float(b), "n_orgs": int(len(latest)),
            "median_top_comp_latest": float(latest.total_comp.median())}


def reserves(latest):
    r = latest[latest.city_paid_aligned >= 1e6]
    return {"median_months_unrestricted": float(r.months_reserves_unrestricted.median()),
            "share_unrestricted_negative": float((r.unrestricted_na_eoy < 0).mean()),
            "share_lt_1_month": float((r.months_reserves_unrestricted < 1).mean()),
            "share_ge_6_months": float((r.months_reserves_unrestricted >= 6).mean()),
            "n": int(r.months_reserves_unrestricted.notna().sum())}


def revoked_and_nonfilers(d, names):
    vm, oy, orgs = d["vm"], d["oy"], d["orgs"]
    fin = d["al"]
    last990 = fin.groupby("ein").fy_end_year.max()
    efi = pd.read_parquet(os.path.join(INT, "efile_index_all.parquet"))
    last_idx = efi.groupby("EIN").TAX_PERIOD.max()
    out = []
    for ein, g in oy.groupby("ein"):
        o = orgs.loc[ein] if ein in orgs.index else None
        rev = o.revocation_date if o is not None else None
        rein = o.reinstatement_date if o is not None else None
        paid_by_fy = g.set_index("fiscal_year").city_paid
        rec = {"ein": ein, "name": names.display_name.get(ein), "in_current_bmf": bool(o.in_bmf) if o is not None else False,
               "revocation_date": rev, "reinstatement_date": rein,
               "last_990_fy_end": last990.get(ein), "last_efile_period": last_idx.get(ein),
               "bmf_filing_req": o.FILING_REQ_CD if o is not None else None,
               "total_paid": g.city_paid.sum(), "last_paid_fy": int(g[g.city_paid > 0].fiscal_year.max()) if (g.city_paid > 0).any() else None}
        if isinstance(rev, str) and rev:
            ry = pd.to_datetime(rev, errors="coerce")
            if pd.notna(ry):
                rfy = ry.year + (1 if ry.month >= 7 else 0)
                ryi = pd.to_datetime(rein, errors="coerce") if isinstance(rein, str) and rein else pd.NaT
                end_fy = (ryi.year + (1 if ryi.month >= 7 else 0)) if pd.notna(ryi) else 9999
                rec["paid_while_revoked"] = float(paid_by_fy[(paid_by_fy.index > rfy) & (paid_by_fy.index < end_fy)].sum())
        rec["paid_fy2023_2026"] = float(paid_by_fy[(paid_by_fy.index >= 2023) & (paid_by_fy.index <= 2026)].sum())
        out.append(rec)
    r = pd.DataFrame(out)
    save(r, "org_status")
    # Paid after an IRS automatic revocation (corrected by the red team, see pipeline/redteam/rt_revocations.py):
    # only organizations still absent from the current BMF and not reinstated; only payments dated after the IRS
    # POSTED the revocation (voucher timestamps; FY2007-17 rows: fiscal years starting after posting); only
    # matches with confidence >= 0.9. The earlier definition (fiscal years after the revocation date, any
    # confidence) overstated the list (8 organizations, $1.87M, vs 5 and $1.62M).
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "redteam"))
    from rt_revocations import compute as revocation_check
    rc = revocation_check()
    rv = pd.DataFrame([{k: o.get(k) for k in ("ein", "irs_name", "subsection", "match_confidence", "paid_after_revocation_fy_pipeline_def",
                                               "paid_after_posting", "first_payment_after_posting", "last_payment_after_posting",
                                               "depts_after_posting", "last_990_on_file", "publishable", "exclusion_reason")}
                       for o in rc["orgs"] if o["status"] == "revoked_not_reinstated"])
    rv = rv.rename(columns={"paid_after_posting": "paid_while_revoked"}).sort_values("paid_while_revoked", ascending=False)
    save(rv, "paid_while_revoked")
    rv = rv[rv.publishable]
    lp = r.last_efile_period.fillna("0").astype(str).str[:4].astype(int)
    # must-file orgs (BMF filing requirement 01 = Form 990) with no e-filed return since 2021 but >= $1M paid FY2023-26
    nf = r[(r.paid_fy2023_2026 >= 1e6) & (lp < 2021) & (r.bmf_filing_req.astype(str).str.zfill(2) == "01")]
    # orgs whose BMF filing requirement is 990-N (02: gross receipts normally <= $50k) yet were paid >= $1M in a year
    maxyr = oy[oy.fiscal_year >= 2020].groupby("ein").city_paid.max()
    r["max_year_paid_fy2020plus"] = r.ein.map(maxyr)
    small = r[(r.bmf_filing_req.astype(str).str.zfill(2) == "02") & (r.max_year_paid_fy2020plus >= 1e6)]
    save(small.sort_values("max_year_paid_fy2020plus", ascending=False), "990n_filers_large_payments")
    save(nf.sort_values("paid_fy2023_2026", ascending=False), "stopped_filing")
    return {"n_paid_while_revoked": int(len(rv)), "amt_paid_while_revoked": float(rv.paid_while_revoked.sum()),
            "n_stopped_filing_ge_1m": int(len(nf)), "amt_stopped_filing": float(nf.paid_fy2023_2026.sum())}


def year_end(d):
    files = sorted(glob.glob(os.path.join(BASE, "raw", "payments_timing_fy*.csv")))
    vm = d["vm"]
    npv = set(vm.vendor)
    rows = []
    for f in files:
        t = pd.read_csv(f, dtype=str, keep_default_na=False)
        t["paid"] = pd.to_numeric(t.paid, errors="coerce").fillna(0)
        t["fy"] = t.fiscal_year.astype(int)
        dt = pd.to_datetime(t.data_as_of.str[:10], errors="coerce")
        t["month"] = dt.dt.month
        t["in_fy"] = (dt >= pd.to_datetime(t.fy.astype(str).radd("").map(lambda y: f"{int(y)-1}-07-01"))) & \
                     (dt <= pd.to_datetime(t.fy.map(lambda y: f"{y}-06-30")))
        t["np"] = t.vendor.isin(npv)
        g = t.groupby(["fy", "np", "department_code", "month", "in_fy"]).paid.sum().reset_index()
        rows.append(g)
    g = pd.concat(rows)
    save(g, "timing_month")
    s = g[g.in_fy].groupby(["fy", "np", "month"]).paid.sum().unstack("month").fillna(0)
    share = s.div(s.sum(axis=1), axis=0)
    out = share[[6, 7]].rename(columns={6: "june_share", 7: "july_share"}).reset_index()
    out["np"] = out.np.map({True: "nonprofit", False: "other_vendors"})
    save(out, "june_july_share")
    return out


def contracts(d, names):
    vm = d["vm"]
    snaps = {"2021-04-22": "wayback/supplier_contracts_20210422145443.csv", "2022-12-06": "wayback/supplier_contracts_20221206220239.csv",
             "2025-11-02": "wayback/supplier_contracts_20251102051641.csv", "2026-09-21": "supplier_contracts.csv"}
    S = {}
    for k, f in snaps.items():
        c = pd.read_csv(os.path.join(BASE, "raw", f), dtype=str)
        c["amt"] = pd.to_numeric(c["Contract Awarded Amount"], errors="coerce")
        S[k] = c
    cur = S["2026-09-21"]
    prime = cur[cur["Supplier Type"] == "Prime Contractor"].drop_duplicates("Contract Number").copy()
    vm = vm[vm.org_class != "public_university"]
    v2e = vm.set_index("vendor").ein.to_dict()
    # supplier names in contracts differ slightly from voucher vendor names; map by exact then normalized
    n2e = {}
    for k, v in v2e.items():
        n2e.setdefault(norm(k), set()).add(v)
    n2e = {k: next(iter(v)) for k, v in n2e.items() if len(v) == 1}
    def to_ein(n):
        return v2e.get(n) or n2e.get(norm(n))
    prime["ein"] = prime["Supplier Name"].map(to_ein)
    prime["authority_class"] = prime["Purchasing Authority"].map(classify)
    prime["start"] = pd.to_datetime(prime["Term Start Date"], errors="coerce")
    prime["end"] = pd.to_datetime(prime["Term End Date"], errors="coerce")
    prime["duration_years"] = (prime.end - prime.start).dt.days / 365.25
    prime["paid_to_date"] = pd.to_numeric(prime["Payments Made"], errors="coerce")
    for k in ["2021-04-22", "2022-12-06", "2025-11-02"]:
        s = S[k][S[k]["Supplier Type"] == "Prime Contractor"].drop_duplicates("Contract Number").set_index("Contract Number")
        prime[f"amt_{k}"] = prime["Contract Number"].map(s.amt)
        prime[f"end_{k}"] = prime["Contract Number"].map(s["Term End Date"])
    prime["amt_2026-09-21"] = prime.amt
    npc = prime[prime.ein.notna()].copy()
    npc["display_name"] = npc.ein.map(names.display_name)
    first = npc[["amt_2021-04-22", "amt_2022-12-06", "amt_2025-11-02"]].bfill(axis=1).iloc[:, 0]
    firstk = npc[["amt_2021-04-22", "amt_2022-12-06", "amt_2025-11-02"]].notna().idxmax(axis=1).str[4:]
    npc["earliest_snapshot_amt"] = first
    npc["earliest_snapshot"] = np.where(first.notna(), firstk, None)
    npc["growth_since_earliest"] = npc.amt / first
    # payments by FY per contract from vouchers
    pay = d["np"][d["np"].contract_number != ""].groupby(["contract_number", "fiscal_year"]).paid.sum().reset_index()
    save(pay, "contract_payments_by_fy")
    keep = ["Contract Number", "Contract Title", "Department", "Supplier Name", "ein", "display_name", "Contract Type",
            "Purchasing Authority", "authority_class", "Sole Source", "Term Start Date", "Term End Date", "duration_years",
            "amt_2021-04-22", "amt_2022-12-06", "amt_2025-11-02", "amt_2026-09-21", "end_2021-04-22", "end_2022-12-06",
            "end_2025-11-02", "earliest_snapshot", "earliest_snapshot_amt", "growth_since_earliest", "paid_to_date"]
    save(npc[keep].sort_values("amt_2026-09-21", ascending=False), "np_contracts")
    # authority mix by start year (dollar-weighted awarded amount)
    npc["start_fy"] = npc.start.dt.year + (npc.start.dt.month >= 7).astype(int)
    mix = npc.groupby(["start_fy", "authority_class"]).amt.sum().unstack().fillna(0)
    mix = mix.div(mix.sum(axis=1), axis=0).reset_index()
    save(mix, "authority_mix_by_start_fy")
    # subcontractors under nonprofit primes
    sub = cur[(cur["Supplier Type"] != "Prime Contractor") & cur["Contract Number"].isin(set(npc["Contract Number"]))]
    save(sub, "subcontractors_on_np_contracts")
    return npc


def subgrants(d, names):
    """Schedule I grants from matched nonprofits to other organizations; flag recipients that are also city vendors."""
    si = pd.read_parquet(os.path.join(INT, "schedule_i.parquet"))
    if not len(si):
        return {}
    vm = d["vm"]
    city_eins = set(vm.ein)
    si["recipient_is_city_vendor"] = si.recipient_ein.isin(city_eins)
    si["grantor_name"] = si.ein.map(names.display_name)
    si["recipient_city_name"] = si.recipient_ein.map(names.display_name)
    si = si.merge(d["al"][["ein", "period_end", "city_paid_aligned", "total_revenue", "government_grants"]],
                  on=["ein", "period_end"], how="left")
    save(si, "schedule_i_grants")
    agg = si.groupby(["ein", "grantor_name", "period_end"]).agg(
        grants_total=("cash", "sum"), n_grants=("cash", "size"),
        to_city_vendors=("cash", lambda s: s[si.loc[s.index, "recipient_is_city_vendor"]].sum()),
        city_paid_aligned=("city_paid_aligned", "first"), total_revenue=("total_revenue", "first")).reset_index()
    agg["grants_share_of_revenue"] = agg.grants_total / agg.total_revenue
    save(agg, "schedule_i_by_grantor")
    return {"n_grantors": int(agg.ein.nunique()), "n_grant_rows": int(len(si))}


def main():
    d = load()
    names = org_names(d)
    names.to_parquet(os.path.join(INT, "org_names.parquet"))
    res = {}
    t = trends(d)
    departments(d)
    dep, latest = dependency(d, names)
    res["dependency"] = dep
    res["compensation"] = compensation(d, names)
    res["reserves"] = reserves(latest)
    res["status"] = revoked_and_nonfilers(d, names)
    year_end(d)
    contracts(d, names)
    res["subgrants"] = subgrants(d, names)
    json.dump(res, open(os.path.join(RES, "summary.json"), "w"), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
