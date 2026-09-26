"""Red team: re-derive key numbers with independent code paths and test robustness.

Independent re-derivations (do not use np_payments/org_year/aligned):
  R1. FY2025 nonprofit total: fresh server-side SoQL sums from data.sf.gov for the matched vendor names
      (expenditure characters), compared with the pipeline figure.
  R2. Top-20 share FY2025 and FY2016 recomputed from the raw per-FY aggregate CSVs with csv module only.
  R3. Dependency for the 25 largest recipients recomputed from ProPublica API JSON only (a different
      source than the IRS XML used in the pipeline), using city FY payments summed from raw CSVs.
  R4. Contract amendment growth for the 10 largest increases recomputed from the raw Wayback CSVs.
Robustness:
  S1. Totals if only matches with confidence >= 0.9 are kept; if pass-3 (discovery) matches are dropped.
  S2. Totals excluding the four childcare pass-through contracts the Controller excludes.
  S3. Dependency median restricted to orgs whose fiscal year ends in June (exact city-FY alignment).
  S4. Growth FY2019->FY2025 nominal vs real; excluding pandemic-era emergency-authority contracts.
Output: data/interim/results/redteam.json
"""
import csv, glob, json, os, subprocess, urllib.parse
from collections import defaultdict
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")
RAW = os.path.join(BASE, "raw")
EXP_CHARS = {"Non Personnel Services", "Non-Personnel Services", "City Grant Programs", "City Grant Program",
             "Other Support&Care Of Persons", "Other Support/Care of Persons", "Aid Assistance", "Aid Payments",
             "Materials & Supplies", "Capital Outlay", "Capitalized Expenditures", "Facilities Maintenance",
             "Programmatic Projects", "Overhead and Allocations"}
PASS_THROUGH = {"1000026979", "1000028798", "1000027035", "1000008034"}


def raw_vendor_year():
    """vendor -> fy -> paid (expenditure chars), vendor -> fy -> contract -> paid, straight from raw CSVs."""
    vy = defaultdict(lambda: defaultdict(float))
    vc = defaultdict(float)
    for f in sorted(glob.glob(os.path.join(RAW, "payments_agg_fy*.csv"))):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                if r["character"] in EXP_CHARS:
                    amt = float(r["paid"] or 0)
                    vy[r["vendor"].strip()][int(r["fiscal_year"])] += amt
                    vc[(r["vendor"].strip(), int(r["fiscal_year"]), r["contract_number"])] += amt
    return vy, vc


def soql_sum(vendors, fy):
    tot = 0.0
    chunk = []
    def run(ch):
        names = ",".join("'" + v.replace("'", "''") + "'" for v in ch)
        chars = ",".join("'" + c.replace("'", "''") + "'" for c in EXP_CHARS)
        q = f"SELECT sum(vouchers_paid) as s WHERE fiscal_year='{fy}' AND character in ({chars}) AND vendor in ({names})"
        url = "https://data.sf.gov/resource/n9pm-xkyq.json?" + urllib.parse.urlencode({"$query": q})
        r = subprocess.run(["perl", "-e", "alarm 300; exec @ARGV", "curl", "-s", "-f", url], capture_output=True)
        return float(json.loads(r.stdout)[0].get("s") or 0)
    for v in vendors:
        chunk.append(v)
        if len(chunk) == 60:
            tot += run(chunk); chunk = []
    if chunk:
        tot += run(chunk)
    return tot


def main():
    out = {}
    vm = pd.read_parquet(os.path.join(INT, "vendor_map.parquet"))
    vm = vm[vm.org_class != "public_university"]
    t = pd.read_csv(os.path.join(INT, "results", "trends.csv")).set_index("fiscal_year")
    v2e = dict(zip(vm.vendor, vm.ein))
    vy, vc = raw_vendor_year()
    # R1
    try:
        server = soql_sum(sorted(v2e), 2025)
        out["R1_fy2025_total_server"] = {"server": server, "pipeline": float(t.loc[2025, "nonprofit_all"]),
                                         "diff_pct": server / float(t.loc[2025, "nonprofit_all"]) - 1}
    except Exception as e:  # noqa
        out["R1_fy2025_total_server"] = {"error": str(e)}
    # R2
    for fy in (2016, 2025):
        by_ein = defaultdict(float)
        for v, e in v2e.items():
            by_ein[e] += vy.get(v, {}).get(fy, 0.0)
        vals = sorted((x for x in by_ein.values() if x > 0), reverse=True)
        out[f"R2_top20_share_{fy}"] = {"independent": sum(vals[:20]) / sum(vals), "pipeline": float(t.loc[fy, "top20_share"]),
                                       "total_independent": sum(vals)}
    # R3: dependency from ProPublica only for 25 largest FY2023 recipients (ProPublica coverage ends ~TY2023)
    by_ein_fy = defaultdict(lambda: defaultdict(float))
    for v, e in v2e.items():
        for fy, a in vy.get(v, {}).items():
            by_ein_fy[e][fy] += a
    top = sorted(by_ein_fy, key=lambda e: -by_ein_fy[e].get(2023, 0))[:25]
    rows = []
    for e in top:
        f = os.path.join(BASE, "cache", "propublica", f"{e}.json")
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        for fl in d.get("filings_with_data", []):
            tp = str(fl.get("tax_prd"))
            if tp.startswith("2023") and fl.get("totrevenue"):
                y, mth = int(tp[:4]), int(tp[4:])
                # prorate city FYs over the 12 months ending (y, mth)
                c = 0.0
                for k in range(12):
                    mo, yr = mth - k, y
                    while mo <= 0:
                        mo += 12; yr -= 1
                    c += by_ein_fy[e].get(yr + 1 if mo >= 7 else yr, 0) / 12
                rows.append({"ein": e, "tax_prd": tp, "revenue_pp": fl["totrevenue"], "city": c, "dep_pp": c / fl["totrevenue"]})
    r3 = pd.DataFrame(rows)
    al = pd.read_parquet(os.path.join(INT, "aligned.parquet"))
    al["tp"] = al.period_end.str.replace("-", "")
    r3 = r3.merge(al[["ein", "tp", "dependency"]], left_on=["ein", "tax_prd"], right_on=["ein", "tp"], how="left")
    out["R3_dependency_propublica_vs_pipeline"] = {"n": int(len(r3)), "median_pp": float(r3.dep_pp.median()),
                                                    "median_pipeline": float(r3.dependency.median()),
                                                    "max_abs_diff": float((r3.dep_pp - r3.dependency).abs().max())}
    # R4 contract growth from raw wayback
    def load(f):
        with open(f, newline="", encoding="utf-8", errors="ignore") as fh:
            return {r["Contract Number"]: float(r["Contract Awarded Amount"] or 0) for r in csv.DictReader(fh)
                    if r.get("Supplier Type") == "Prime Contractor"}
    a21 = load(os.path.join(RAW, "wayback", "supplier_contracts_20210422145443.csv"))
    a26 = load(os.path.join(RAW, "supplier_contracts.csv"))
    npc = pd.read_csv(os.path.join(INT, "results", "np_contracts.csv"), dtype={"Contract Number": str})
    chk = []
    for cn in npc[npc.earliest_snapshot == "2021-04-22"].assign(inc=lambda d: d["amt_2026-09-21"] - d.earliest_snapshot_amt).nlargest(10, "inc")["Contract Number"]:
        chk.append({"contract": cn, "amt_2021": a21.get(cn), "amt_2026": a26.get(cn),
                    "pipeline_growth": float(npc.set_index("Contract Number").loc[cn, "growth_since_earliest"]),
                    "independent_growth": a26.get(cn) / a21.get(cn) if a21.get(cn) else None})
    out["R4_contract_growth"] = chk
    # S1 match-confidence sensitivity
    np_ = pd.read_parquet(os.path.join(INT, "np_payments.parquet"))
    conf = dict(zip(vm.vendor, vm.confidence)); ps = dict(zip(vm.vendor, vm["pass"]))
    np_["conf"] = np_.vendor.map(conf); np_["pass"] = np_.vendor.map(ps)
    f25 = np_[np_.fiscal_year == 2025]
    out["S1_fy2025"] = {"all": float(f25.paid.sum()), "conf_ge_0_9": float(f25[f25.conf >= 0.9].paid.sum()),
                        "no_pass3": float(f25[f25["pass"] != 3].paid.sum())}
    # S2 pass-through exclusion
    out["S2_fy2025_excl_childcare_passthrough"] = float(f25[~f25.contract_number.isin(PASS_THROUGH)].paid.sum())
    fyt = np_.groupby("fiscal_year").paid.sum()
    fyt_x = np_[~np_.contract_number.isin(PASS_THROUGH)].groupby("fiscal_year").paid.sum()
    cpi = pd.read_parquet(os.path.join(INT, "cpi.parquet")).set_index("fy").deflator_to_fy2025
    out["S4_growth_fy2019_2025"] = {"nominal": float(fyt[2025] / fyt[2019] - 1),
                                    "real": float(fyt[2025] * cpi[2025] / (fyt[2019] * cpi[2019]) - 1),
                                    "real_excl_passthrough": float(fyt_x[2025] * cpi[2025] / (fyt_x[2019] * cpi[2019]) - 1),
                                    "real_fy2016_2025": float(fyt[2025] * cpi[2025] / (fyt[2016] * cpi[2016]) - 1)}
    # S3 dependency with June fiscal years only
    l = al[(al.total_revenue > 0)].sort_values("period_end").groupby("ein").tail(1)
    l = l[l.city_paid_aligned >= 1e6]
    out["S3_dependency_median"] = {"all": float(l.dependency.median()), "june_fye_only": float(l[l.fy_end_month == 6].dependency.median()),
                                   "n_june": int((l.fy_end_month == 6).sum()), "n_all": int(len(l)),
                                   "excluding_gt_1_05": float(l[l.dependency <= 1.05].dependency.median())}
    # S5 dependency / reserves vs monitoring status (FY2023-25), with permutation test (independent of site export)
    import numpy as np
    fr = json.load(open(os.path.join(BASE, "site", "reviews", "findings.json")))["rows"]
    alx = al.assign(fy=al.fy_end_year + (al.fy_end_month >= 7).astype(int)).sort_values("period_end").drop_duplicates(["ein", "fy"], keep="last").set_index(["ein", "fy"])
    recs = []
    for r in fr:
        e = r["org"].replace("org-", "")
        if r["fy"] in (2023, 2024, 2025) and (e, r["fy"]) in alx.index:
            a = alx.loc[(e, r["fy"])]
            if a.total_revenue > 0:
                city = by_ein_fy[e].get(r["fy"], 0)
                recs.append((city / a.total_revenue, a.months_reserves_unrestricted, r["result"] in ("corrective", "elevated", "redflag"), r["result"] != "none"))
    arr = pd.DataFrame(recs, columns=["dep", "res", "severe", "any"])
    rng = np.random.default_rng(1)
    def perm(flag, y, n=5000):
        obs = y[flag].mean() - y[~flag].mean()
        yv, fv = y.values, flag.values
        cnt = 0
        for _ in range(n):
            sh = rng.permutation(yv)
            cnt += (sh[fv].mean() - sh[~fv].mean()) >= obs
        return float(obs), (cnt + 1) / (n + 1)
    hi = arr.dep >= 0.75
    out["S5_dependency_vs_monitoring"] = {"n": int(len(arr)), "n_dep_ge75": int(hi.sum()),
        "severe_rate_dep_ge75": float(arr[hi].severe.mean()), "severe_rate_dep_lt75": float(arr[~hi].severe.mean()),
        "any_rate_dep_ge75": float(arr[hi]["any"].mean()), "any_rate_dep_lt75": float(arr[~hi]["any"].mean()),
        "perm_p_severe": perm(hi, arr.severe.astype(float))[1], "perm_p_any": perm(hi, arr["any"].astype(float))[1],
        "severe_events": int(arr.severe.sum())}
    lo = arr.res < 1
    out["S5_reserves_vs_monitoring"] = {"n_res_lt1": int(lo.sum()), "severe_rate_res_lt1": float(arr[lo].severe.mean()),
        "severe_rate_res_ge1": float(arr[~lo & arr.res.notna()].severe.mean()), "perm_p_severe": perm(lo, arr.severe.astype(float))[1]}
    json.dump(out, open(os.path.join(INT, "results", "redteam.json"), "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
