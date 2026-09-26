"""Red team: independent re-derivation and robustness tests of every headline finding.

Independence: the payment side is rebuilt from the raw per-fiscal-year aggregates
(data/raw/payments_agg_fy*.csv) with the csv module; contracts from the raw Supplier Contracts snapshots;
990s from the exported site files and, for alignment tests, the pipeline's aligned table; monitoring results
from the exported findings file (whose severe rows were checked by hand against the report text); outcomes
from data/outcomes/outcomes.csv. The only shared input is the vendor -> EIN match table (vendor_map), whose
precision is tested separately (hand review) and whose sensitivity is tested here.

Writes data/redteam/parts/findings.json (numbers only; verdicts are assembled in rt_assemble.py).
"""
import csv, glob, json, math, os, re, statistics as st, sys
from collections import Counter, defaultdict
from datetime import date

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from lib_names import norm  # noqa: E402

BASE = os.path.join(HERE, "..", "..", "data")
RAW = os.path.join(BASE, "raw")
SITE = os.path.join(BASE, "site")
OUT = os.path.join(BASE, "redteam", "parts")
os.makedirs(OUT, exist_ok=True)

EXP_CHARS = {"Non Personnel Services", "Non-Personnel Services", "City Grant Programs", "City Grant Program",
             "Other Support&Care Of Persons", "Other Support/Care of Persons", "Aid Assistance", "Aid Payments",
             "Materials & Supplies", "Capital Outlay", "Capitalized Expenditures", "Facilities Maintenance",
             "Programmatic Projects", "Overhead and Allocations"}
GRANT_CHARS = {"City Grant Programs", "City Grant Program"}
# Organizations whose city payments are largely passed on to others: childcare-subsidy administrators,
# a loan fund, and fiscal sponsors / fiscal intermediaries (they hold contracts for many projects).
PASS_THROUGH_ORGS = {
    "942221305": "Children's Council of San Francisco (childcare subsidies)",
    "942387002": "Wu Yee Children's Services (childcare subsidies)",
    "010716217": "SF Housing Accelerator Fund (loan fund)",
    "943213100": "Tides Center (fiscal sponsor)",
    "942168838": "San Francisco Study Center (fiscal sponsor)",
    "943255070": "Community Initiatives (fiscal sponsor)",
    "941593216": "Intersection for the Arts (fiscal sponsor)",
    "943355076": "Independent Arts & Media (fiscal sponsor)",
    "942889684": "Earth Island Institute (fiscal sponsor)",
    "943117093": "San Francisco Public Health Foundation (fiscal intermediary)",
    "952557063": "Public Health Foundation Enterprises / Heluna Health (fiscal intermediary)",
}
PASS_THROUGH_CONTRACTS = {"1000026979", "1000028798", "1000027035", "1000008034"}  # Controller's childcare exclusions


def fy_of(d):
    return d.year + (1 if d.month >= 7 else 0)


# ------------------------------------------------------------------ raw payments
def load_raw(v2e):
    """-> dict ein -> fy -> paid; plus detail rows (ein, fy, dept, char, object, contract, paid)."""
    by = defaultdict(lambda: defaultdict(float))
    cells = defaultdict(float)
    detail = []
    for f in sorted(glob.glob(os.path.join(RAW, "payments_agg_fy*.csv"))):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                e = v2e.get(r["vendor"].strip())
                if e is None:
                    continue
                amt = float(r["paid"] or 0)
                fy = int(r["fiscal_year"])
                if r["character"] in EXP_CHARS:
                    by[e][fy] += amt
                    cells[(fy, r["department_code"], e)] += amt
                detail.append((e, fy, r["department_code"], r["character"], r["object"], r["contract_number"], amt))
    return by, cells, pd.DataFrame(detail, columns=["ein", "fy", "dept", "character", "object", "contract", "paid"])


def cpi_series(series_id):
    rows = []
    with open(os.path.join(RAW, "cu_summaries.txt")) as fh:
        for line in fh:
            p = line.split("\t")
            if p[0].strip() == series_id and p[2].startswith("M") and p[2] != "M13":
                try:
                    rows.append((int(p[1]), int(p[2][1:]), float(p[3])))
                except ValueError:
                    pass
    acc = defaultdict(list)
    for y, m, v in rows:
        acc[y + 1 if m >= 7 else y].append(v)
    return {fy: sum(v) / len(v) for fy, v in acc.items()}


def main():
    np.seterr(all="ignore")
    R = {}
    vm = pd.read_parquet(os.path.join(BASE, "interim", "vendor_map.parquet"))
    vm = vm[vm.org_class != "public_university"]
    v2e = dict(zip(vm.vendor, vm.ein))
    conf = vm.groupby("ein").confidence.max().to_dict()
    passno = vm.groupby("ein")["pass"].min().to_dict()
    by, cells, det = load_raw(v2e)
    site_cells = [c for f in sorted(glob.glob(os.path.join(SITE, "payments", "cells_*.json"))) for c in json.load(open(f))["cells"]]
    meta = json.load(open(os.path.join(SITE, "meta.json")))
    idx = {int(k): v for k, v in meta["deflator"]["index"].items()}

    # ============ F1 total, organizations, real growth
    tot = lambda fy, keep=lambda e: True: sum(v.get(fy, 0) for e, v in by.items() if keep(e))
    pos_cells = defaultdict(set)
    for (fy, d, e), a in cells.items():
        if a > 0.5:
            pos_cells[fy].add(e)
    site_tot = defaultdict(float)
    for c in site_cells:
        site_tot[c["fy"]] += c["amt"]
    F1 = {"raw_total_fy2025": tot(2025), "raw_total_fy2016": tot(2016),
          "site_total_fy2025": site_tot[2025], "site_total_fy2016": site_tot[2016],
          "orgs_fy2025_with_positive_cell": len(pos_cells[2025]),
          "orgs_fy2025_net_positive": sum(1 for e, v in by.items() if v.get(2025, 0) > 0.5)}
    # the site total drops net-negative (fy, dept, org) cells; quantify
    F1["dropped_negative_cells_fy2025"] = sum(a for (fy, d, e), a in cells.items() if fy == 2025 and a <= 0.5)
    sf = cpi_series("CUURS49BSA0"); us = cpi_series("CUUR0000SA0"); svc = cpi_series("CUUR0000SAS")
    F1["sf_cpi_recomputed_index_2016"] = sf[2016] / sf[2025]
    F1["site_index_2016"] = idx[2016]
    g = lambda a, b, d: (tot(b) / tot(a)) * (d[a] / d[b]) - 1
    F1["real_growth_2016_2025"] = {"sf_cpi": g(2016, 2025, sf), "us_cpi": g(2016, 2025, us), "us_services_cpi": g(2016, 2025, svc) if 2016 in svc else None,
                                   "nominal": tot(2025) / tot(2016) - 1}
    keep_np = lambda e: e not in PASS_THROUGH_ORGS
    F1["real_growth_2016_2025_excl_passthrough_orgs"] = (tot(2025, keep_np) / tot(2016, keep_np)) * (sf[2016] / sf[2025]) - 1
    F1["total_fy2025_excl_passthrough_orgs"] = tot(2025, keep_np)
    F1["passthrough_orgs_fy2025"] = tot(2025) - tot(2025, keep_np)
    loans = det[(det.character.isin(EXP_CHARS)) & det.object.str.contains("Loan", case=False, na=False)].groupby("fy").paid.sum()
    F1["loans_fy2025"] = float(loans.get(2025, 0)); F1["loans_fy2016"] = float(loans.get(2016, 0))
    F1["real_growth_2016_2025_excl_passthrough_and_loans"] = ((tot(2025, keep_np) - float(det[(det.fy == 2025) & det.character.isin(EXP_CHARS) & det.object.str.contains("Loan", case=False, na=False) & det.ein.map(keep_np)].paid.sum()))
                                                              / (tot(2016, keep_np) - float(det[(det.fy == 2016) & det.character.isin(EXP_CHARS) & det.object.str.contains("Loan", case=False, na=False) & det.ein.map(keep_np)].paid.sum()))) * (sf[2016] / sf[2025]) - 1
    F1["passthrough_contracts_fy2025"] = float(det[(det.fy == 2025) & det.contract.isin(PASS_THROUGH_CONTRACTS) & det.character.isin(EXP_CHARS)].paid.sum())
    hi = lambda e: conf.get(e, 0) >= 0.9 and passno.get(e, 9) != 3
    F1["real_growth_2016_2025_conf_ge_0_9_no_discovery"] = (tot(2025, hi) / tot(2016, hi)) * (sf[2016] / sf[2025]) - 1
    F1["base_year_sensitivity_real_growth_to_2025"] = {str(b): (tot(2025) / tot(b)) * (sf[b] / sf[2025]) - 1 for b in (2015, 2016, 2017, 2018, 2019)}
    # coverage drift: matched share of City Grant Program dollars (a character used almost only for community grants)
    allp = defaultdict(float); mp = defaultdict(float)
    for f in sorted(glob.glob(os.path.join(RAW, "payments_agg_fy*.csv"))):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                if r["character"] in GRANT_CHARS:
                    fy = int(r["fiscal_year"]); a = float(r["paid"] or 0)
                    allp[fy] += a
                    if r["vendor"].strip() in v2e:
                        mp[fy] += a
    cov = {fy: mp[fy] / allp[fy] for fy in allp if allp[fy]}
    F1["grant_character_matched_share"] = {str(k): round(v, 4) for k, v in sorted(cov.items())}
    F1["real_growth_2016_2025_coverage_adjusted"] = ((tot(2025) / cov[2025]) / (tot(2016) / cov[2016])) * (sf[2016] / sf[2025]) - 1
    # non-expenditure characters among matched vendors (definition drift across the FY2018 chart-of-accounts change)
    ne = det[~det.character.isin(EXP_CHARS)].groupby("fy").paid.sum()
    F1["non_expenditure_share"] = {str(fy): float(ne.get(fy, 0) / (ne.get(fy, 0) + tot(fy))) for fy in (2016, 2017, 2018, 2019, 2025)}
    q = pd.read_csv(os.path.join(RAW, "city_np", "qkex-vh98.csv"), dtype=str)
    q["amt"] = q["Completed Payments"].astype(float); q["fy"] = q["Fiscal Year"].astype(int)
    qs = q[q.Nonprofit != "UCSF"].groupby("fy").amt.sum()
    F1["controller_dataset_nominal_growth_2019_2025"] = float(qs[2025] / qs[2019] - 1)
    F1["this_dashboard_nominal_growth_2019_2025"] = tot(2025) / tot(2019) - 1
    F1["controller_dataset_fy2025"] = float(qs[2025])
    R["F1_total_and_growth"] = F1

    # ============ F2 top-20 share
    def top_share(fy, n=20, keep=lambda e: True):
        s = sorted((v.get(fy, 0) for e, v in by.items() if keep(e) and v.get(fy, 0) > 0), reverse=True)
        return sum(s[:n]) / sum(s)
    vend_fy = defaultdict(float)
    for f in [os.path.join(RAW, "payments_agg_fy2025.csv")]:
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                if r["vendor"].strip() in v2e and r["character"] in EXP_CHARS:
                    vend_fy[r["vendor"].strip()] += float(r["paid"] or 0)
    sv = sorted((x for x in vend_fy.values() if x > 0), reverse=True)
    top20 = sorted(((v.get(2025, 0), e) for e, v in by.items()), reverse=True)[:20]
    R["F2_top20"] = {"fy2025_by_ein": top_share(2025), "fy2016_by_ein": top_share(2016),
                     "fy2025_by_vendor_name": sum(sv[:20]) / sum(sv),
                     "fy2025_excl_passthrough_orgs": top_share(2025, keep=keep_np),
                     "fy2016_excl_passthrough_orgs": top_share(2016, keep=keep_np),
                     "fy2025_top10": top_share(2025, 10),
                     "fy2025_top20_passthrough_members": [PASS_THROUGH_ORGS[e] for _, e in top20 if e in PASS_THROUGH_ORGS],
                     "series": {str(fy): top_share(fy) for fy in range(2007, 2027)}}

    # ============ F3 dependency (UI definition and variants)
    f24 = json.load(open(os.path.join(SITE, "finances", "form990_2024.json")))["rows"]
    pay = lambda org, fy: by.get(org.replace("org-", ""), {}).get(fy, 0.0)
    base = [(r["org"], pay(r["org"], 2024) / r["total_revenue"], pay(r["org"], 2024), r) for r in f24 if r["total_revenue"] > 0]
    big = [x for x in base if x[2] >= 1e6]
    al = pd.read_parquet(os.path.join(BASE, "interim", "aligned.parquet"))
    al = al[al.form.isin(["990", "990EZ"]) & (al.total_revenue > 0)].copy()
    al["fy"] = al.fy_end_year + (al.fy_end_month >= 7).astype(int)
    al = al.sort_values("period_end").drop_duplicates(["ein", "fy"], keep="last").set_index(["ein", "fy"])
    def variant(rows):
        vals = [x[1] for x in rows]
        return {"n": len(vals), "median": st.median(vals) if vals else None, "n_ge_75": sum(v >= 0.75 for v in vals),
                "n_gt_75": sum(v > 0.75 for v in vals), "share_gt_100": (sum(v > 1 for v in vals) / len(vals)) if vals else None}
    pro = []
    fye = {}
    for o, dep, c, r in big:
        e = o.replace("org-", "")
        if (e, 2024) in al.index:
            a = al.loc[(e, 2024)]
            pro.append((o, a.city_paid_aligned / a.total_revenue, c, r)); fye[o] = int(a.fy_end_month)
    paid24 = {e for e, v in by.items() if v.get(2024, 0) >= 1e6}
    have = {x[0].replace("org-", "") for x in base}
    f23 = json.load(open(os.path.join(SITE, "finances", "form990_2023.json")))["rows"]
    big23 = [(r["org"], pay(r["org"], 2023) / r["total_revenue"], pay(r["org"], 2023), r) for r in f23 if r["total_revenue"] > 0 and pay(r["org"], 2023) >= 1e6]
    f25 = json.load(open(os.path.join(SITE, "finances", "form990_2025.json")))["rows"]
    big25 = [(r["org"], pay(r["org"], 2025) / r["total_revenue"], pay(r["org"], 2025), r) for r in f25 if r["total_revenue"] > 0 and pay(r["org"], 2025) >= 1e6]
    all25 = [(r["org"], pay(r["org"], 2025) / r["total_revenue"], pay(r["org"], 2025), r) for r in f25 if r["total_revenue"] > 0 and pay(r["org"], 2025) > 0]
    pro25, fye25 = [], {}
    for o, dep, c, r in big25:
        e = o.replace("org-", "")
        if (e, 2025) in al.index:
            a = al.loc[(e, 2025)]
            pro25.append((o, a.city_paid_aligned / a.total_revenue, c, r)); fye25[o] = int(a.fy_end_month)
    paid25 = {e for e, v in by.items() if v.get(2025, 0) >= 1e6}
    have25 = {x[0].replace("org-", "") for x in all25}
    R["F3_dependency_fy2025"] = {
        "ui_definition": variant(big25), "all_orgs_with_990_any_payment": variant(all25),
        "prorated_to_tax_year": variant(pro25), "june_fye_only": variant([x for x in big25 if fye25.get(x[0]) == 6]),
        "excluding_ratios_over_100": variant([x for x in big25 if x[1] <= 1]),
        "excluding_passthrough_orgs": variant([x for x in big25 if x[0].replace("org-", "") not in PASS_THROUGH_ORGS]),
        "coverage": {"orgs_paid_ge_1m": len(paid25), "with_990": len(paid25 & have25), "share_with_990": len(paid25 & have25) / len(paid25)},
        "non_june_share": sum(1 for x in big25 if fye25.get(x[0]) not in (6, None)) / len(big25),
        "large_and_dependent_ge_5m": sum(1 for x in big25 if x[2] >= 5e6 and x[1] > 0.75),
    }
    R["F3_dependency"] = {
        "ui_definition_fy2024": variant(big),
        "prorated_to_tax_year": variant(pro),
        "june_fye_only": variant([x for x in big if fye.get(x[0]) == 6]),
        "excluding_ratios_over_100": variant([x for x in big if x[1] <= 1]),
        "excluding_passthrough_orgs": variant([x for x in big if x[0].replace("org-", "") not in PASS_THROUGH_ORGS]),
        "fy2023_instead": variant(big23),
        "coverage": {"orgs_paid_ge_1m_fy2024": len(paid24), "with_fy2024_990": len(paid24 & have),
                     "share_with_990": len(paid24 & have) / len(paid24),
                     "dollars_share_with_990": sum(by[e][2024] for e in paid24 & have) / sum(by[e][2024] for e in paid24)},
        "non_june_share": sum(1 for x in big if fye.get(x[0]) not in (6, None)) / len(big),
    }
    # ============ F4 dependency and corrective action
    fr = json.load(open(os.path.join(SITE, "reviews", "findings.json")))["rows"]
    orgs = {o["id"]: o for o in json.load(open(os.path.join(SITE, "orgs", "index.json")))["orgs"]}
    f990 = {}
    for fy in (2023, 2024, 2025):
        for r in json.load(open(os.path.join(SITE, "finances", f"form990_{fy}.json")))["rows"]:
            f990[(r["org"], fy)] = r
    fye_all = {("org-" + e, fy): int(r_.fy_end_month) for (e, fy), r_ in al.iterrows()}
    recs = []
    for r in fr:
        k = (r["org"], r["fy"])
        if r["fy"] in (2023, 2024, 2025) and k in f990 and f990[k]["total_revenue"] > 0:
            c = pay(r["org"], r["fy"])
            recs.append({"org": r["org"], "fy": r["fy"], "dep": c / f990[k]["total_revenue"], "city": c,
                         "rev": f990[k]["total_revenue"], "area": orgs[r["org"]]["area"], "size": orgs[r["org"]]["size_band"],
                         "severe": r["result"] in ("corrective", "elevated", "redflag"), "any": r["result"] != "none",
                         "res": f990[k].get("months_reserves")})
    A = pd.DataFrame(recs)
    A["hi"] = A.dep >= 0.75
    F4 = {"n_org_years": int(len(A)), "n_orgs": int(A.org.nunique()), "n_hi": int(A.hi.sum()),
          "severe_hi": int(A[A.hi].severe.sum()), "severe_lo": int(A[~A.hi].severe.sum()),
          "rate_hi": float(A[A.hi].severe.mean()), "rate_lo": float(A[~A.hi].severe.mean()),
          "any_rate_hi": float(A[A.hi]["any"].mean()), "any_rate_lo": float(A[~A.hi]["any"].mean())}
    F4["ratio"] = F4["rate_hi"] / F4["rate_lo"]
    F4["distinct_severe_orgs"] = int(A[A.severe].org.nunique())
    F4["distinct_severe_orgs_hi"] = int(A[A.hi & A.severe].org.nunique()); F4["distinct_severe_orgs_lo"] = int(A[~A.hi & A.severe].org.nunique())
    rng = np.random.default_rng(7)
    # org-level (cluster) permutation: shuffle each org's high/low label as a block
    org_hi = A.groupby("org").hi.mean()
    obs = F4["rate_hi"] - F4["rate_lo"]
    orgs_l = org_hi.index.to_numpy(); probs = org_hi.to_numpy()
    cnt = 0; N = 5000
    sev = A.severe.to_numpy(); orgcol = A.org.to_numpy()
    pos = {o: i for i, o in enumerate(orgs_l)}
    oi = np.array([pos[o] for o in orgcol])
    hi_rows = A.hi.to_numpy()
    for _ in range(N):
        perm = rng.permutation(len(orgs_l))
        # give org j the row labels of org perm[j] only when the row counts align; approximate with org-level label
        lab = (probs[perm] >= 0.5)[oi]
        if lab.sum() == 0 or (~lab).sum() == 0:
            continue
        d = sev[lab].mean() - sev[~lab].mean()
        cnt += d >= obs
    F4["cluster_perm_p"] = (cnt + 1) / (N + 1)
    # stratified by size band (Mantel-Haenszel risk ratio) and by area
    def mh(strat):
        num = den = 0.0
        rows = []
        for s, g in A.groupby(strat):
            a = g[g.hi].severe.sum(); n1 = g.hi.sum(); c = g[~g.hi].severe.sum(); n0 = (~g.hi).sum(); n = len(g)
            rows.append({"stratum": s, "n_hi": int(n1), "sev_hi": int(a), "n_lo": int(n0), "sev_lo": int(c)})
            if n1 and n0:
                num += a * n0 / n; den += c * n1 / n
        return {"mh_risk_ratio": (num / den) if den else None, "strata": rows}
    F4["by_size_band"] = mh("size"); F4["by_area"] = mh("area"); F4["by_fy"] = mh("fy")
    # logistic regression, cluster-robust SE by organization (numpy IRLS). Size is controlled with log revenue
    # (log city dollars is not added: with log revenue it would reconstruct dependency itself).
    def logit(cols):
        X = pd.DataFrame({"const": 1.0, "hi": A.hi.astype(float)})
        if "log_rev" in cols:
            X["log_rev"] = np.log10(A.rev.clip(lower=1e4))
        if "area" in cols:
            for a_ in sorted(A.area.unique())[1:]:
                X[f"area_{a_}"] = (A.area == a_).astype(float)
        if "fy" in cols:
            for fy in (2024, 2025):
                X[f"fy{fy}"] = (A.fy == fy).astype(float)
        if "res" in cols:
            X["res_lt1"] = (A.res.fillna(99) < 1).astype(float)
        y = A.severe.astype(float).to_numpy(); Xm = X.to_numpy()
        b = np.zeros(Xm.shape[1])
        for _ in range(100):
            p = 1 / (1 + np.exp(-Xm @ b)); W = p * (1 - p) + 1e-9
            step = np.linalg.solve(Xm.T @ (Xm * W[:, None]) + np.eye(len(b)) * 1e-6, Xm.T @ (y - p)); b += step
            if np.abs(step).max() < 1e-8:
                break
        p = 1 / (1 + np.exp(-Xm @ b)); Hinv = np.linalg.inv(Xm.T @ (Xm * (p * (1 - p))[:, None]) + np.eye(len(b)) * 1e-6)
        meat = np.zeros_like(Hinv)
        for o, g in A.groupby("org").groups.items():
            ii = [A.index.get_loc(i) for i in g]
            s_ = Xm[ii].T @ (y[ii] - p[ii]); meat += np.outer(s_, s_)
        V = Hinv @ meat @ Hinv
        j = 1
        return {"covariates": list(X.columns), "odds_ratio_hi": float(math.exp(b[j])),
                "ci95": [float(math.exp(b[j] - 1.96 * math.sqrt(V[j, j]))), float(math.exp(b[j] + 1.96 * math.sqrt(V[j, j])))]}
    F4["logit_unadjusted"] = logit([])
    F4["logit_adjusted"] = logit(["log_rev", "area", "fy"])
    F4["logit_adjusted_plus_reserves"] = logit(["log_rev", "area", "fy", "res"])
    # alignment and pass-through variants
    def rates(df, col="dep"):
        h = df[col] >= 0.75
        return {"n": int(len(df)), "n_hi": int(h.sum()), "rate_hi": float(df[h].severe.mean()), "rate_lo": float(df[~h].severe.mean()),
                "ratio": float(df[h].severe.mean() / df[~h].severe.mean())}
    A["dep_pro"] = [al.loc[(o.replace("org-", ""), fy)].city_paid_aligned / al.loc[(o.replace("org-", ""), fy)].total_revenue
                    if (o.replace("org-", ""), fy) in al.index else np.nan for o, fy in zip(A.org, A.fy)]
    F4["variant_prorated_dependency"] = rates(A[A.dep_pro.notna()], "dep_pro")
    F4["variant_excl_passthrough_orgs"] = rates(A[~A.org.str.replace("org-", "").isin(PASS_THROUGH_ORGS)])
    F4["variant_june_fye_only"] = rates(A[[fye_all.get((o, fy)) == 6 for o, fy in zip(A.org, A.fy)]])
    # organization-level version (each organization counted once): high = median dependency over its
    # monitored years >= 75%; outcome = ever corrective / Tier 3 / red flag in FY2023-25. Fisher exact test.
    og = A.groupby("org").agg(dep=("dep", "median"), severe=("severe", "max"))
    a_ = int((og.dep >= 0.75)[og.severe].sum()); b_ = int((og.dep >= 0.75).sum()) - a_
    c_ = int((og.dep < 0.75)[og.severe].sum()); d_ = int((og.dep < 0.75).sum()) - c_
    def fisher_greater(a, b, c, d):
        n1, n2, k, n = a + b, c + d, a + c, a + b + c + d
        tot = math.comb(n, k)
        return sum(math.comb(n1, x) * math.comb(n2, k - x) for x in range(a, min(n1, k) + 1)) / tot
    F4["org_level"] = {"n_orgs_hi": a_ + b_, "severe_orgs_hi": a_, "n_orgs_lo": c_ + d_, "severe_orgs_lo": c_,
                       "rate_hi": a_ / (a_ + b_), "rate_lo": c_ / (c_ + d_), "ratio": (a_ / (a_ + b_)) / (c_ / (c_ + d_)),
                       "fisher_p_one_sided": fisher_greater(a_, b_, c_, d_)}
    lo_res = A.res.notna() & (A.res < 1)
    F4["reserves_lt1_severe"] = {"n_lt1": int(lo_res.sum()), "rate_lt1": float(A[lo_res].severe.mean()),
                                 "rate_ge1": float(A[A.res.notna() & ~lo_res].severe.mean())}
    # size comparison: are high-dependency org-years smaller?
    F4["median_revenue_hi"] = float(A[A.hi].rev.median()); F4["median_revenue_lo"] = float(A[~A.hi].rev.median())
    F4["reserves_lt1_hi_share"] = float((A[A.hi].res < 1).mean()); F4["reserves_lt1_lo_share"] = float((A[~A.hi].res < 1).mean())
    # alternative thresholds
    F4["threshold_sensitivity"] = {str(t): {"rate_hi": float(A[A.dep >= t].severe.mean()), "rate_lo": float(A[A.dep < t].severe.mean()),
                                            "n_hi": int((A.dep >= t).sum())} for t in (0.5, 0.6, 0.75, 0.9)}
    # only first observation per org (removes repeated measures)
    first = A.sort_values("fy").drop_duplicates("org")
    F4["first_year_per_org"] = {"n": int(len(first)), "rate_hi": float(first[first.hi].severe.mean()), "rate_lo": float(first[~first.hi].severe.mean()),
                                "sev_hi": int(first[first.hi].severe.sum()), "sev_lo": int(first[~first.hi].severe.sum())}
    R["F4_dependency_corrective"] = F4

    # ============ F5 contracts that at least doubled (raw snapshots)
    snaps = [("2021-04-22", "wayback/supplier_contracts_20210422145443.csv"), ("2022-12-06", "wayback/supplier_contracts_20221206220239.csv"),
             ("2025-11-02", "wayback/supplier_contracts_20251102051641.csv"), ("2026-09-21", "supplier_contracts.csv")]
    S = {}
    for k, f in snaps:
        m = {}
        with open(os.path.join(RAW, f), newline="", encoding="utf-8", errors="ignore") as fh:
            for r in csv.DictReader(fh):
                if r.get("Supplier Type") == "Prime Contractor" and r["Contract Number"] not in m:
                    m[r["Contract Number"]] = r
        S[k] = m
    n2e = defaultdict(set)
    for v, e in v2e.items():
        n2e[norm(v)].add(e)
    to_e = lambda n: v2e.get(n) or (next(iter(n2e[norm(n)])) if len(n2e.get(norm(n), ())) == 1 else None)
    org_eins = {o.replace("org-", "") for o in orgs}
    con = []
    for cn, r in S["2026-09-21"].items():
        e = to_e(r["Supplier Name"])
        if e is None or e not in org_eins:
            continue
        amt = float(r["Contract Awarded Amount"] or 0)
        end = r["Term End Date"].replace("/", "-")[:10]
        if amt < 4e6 or end < "2019-07-01":
            continue
        obs = [(k, float(S[k][cn]["Contract Awarded Amount"] or 0), S[k][cn]["Term End Date"].replace("/", "-")[:10], S[k][cn]["Term Start Date"].replace("/", "-")[:10])
               for k, _ in snaps if cn in S[k] and float(S[k][cn]["Contract Awarded Amount"] or 0) > 0]
        if not obs:
            continue
        con.append({"id": cn, "ein": e, "title": r["Contract Title"], "scope": r.get("Scope of Work"), "dept": r["Department Code"],
                    "type": r["Contract Type"], "authority": r["Purchasing Authority"], "start": r["Term Start Date"].replace("/", "-")[:10],
                    "end": end, "orig": obs[0][1], "orig_snap": obs[0][0], "orig_end": obs[0][2], "orig_start": obs[0][3], "now": amt,
                    "history": [{"snapshot": k, "amt": a, "end": en} for k, a, en, _ in obs]})
    doubled = [c for c in con if c["now"] / c["orig"] >= 2]
    site_con = json.load(open(os.path.join(SITE, "contracts", "contracts.json")))["contracts"]
    site_doubled = {c["id"] for c in site_con if c["original_agreed"] and c["agreed"] / c["original_agreed"] >= 2}
    # contract payments by fiscal year (raw)
    cpay = det[det.character.isin(EXP_CHARS)].groupby(["contract", "fy"]).paid.sum()
    for c in doubled:
        oe, ne_ = c["orig_end"], c["end"]
        c["term_extended_days"] = (date.fromisoformat(ne_) - date.fromisoformat(oe)).days if oe and ne_ else None
        s0 = date.fromisoformat(c["start"]) if c["start"] else None
        yrs0 = max((date.fromisoformat(oe) - s0).days / 365.25, 0.25) if oe and s0 else None
        yrs1 = max((date.fromisoformat(ne_) - s0).days / 365.25, 0.25) if ne_ and s0 else None
        c["annualized_ratio"] = (c["now"] / yrs1) / (c["orig"] / yrs0) if yrs0 and yrs1 else None
        pays = cpay[c["id"]] if c["id"] in cpay.index.get_level_values(0) else pd.Series(dtype=float)
        c["paid_by_fy"] = {str(int(k)): round(float(v)) for k, v in pays.items() if 2016 <= k <= 2027}
        snap_fy = fy_of(date.fromisoformat(c["orig_snap"]))
        pre = [v for k, v in pays.items() if snap_fy - 2 <= k <= snap_fy - 1 and v > 0]
        post = [v for k, v in pays.items() if 2024 <= k <= 2026 and v > 0]
        c["run_rate_ratio"] = (st.mean(post) / st.mean(pre)) if pre and post else None
    F5 = {"n_contracts_independent": len(con), "n_doubled_independent": len(doubled), "n_contracts_site": len(site_con),
          "n_doubled_site": len(site_doubled), "doubled_agree": len(site_doubled & {c["id"] for c in doubled}),
          "n_first_seen_2021": sum(c["orig_snap"] == "2021-04-22" for c in doubled),
          "n_first_seen_later": sum(c["orig_snap"] != "2021-04-22" for c in doubled),
          "n_started_after_first_snapshot_of_panel": sum(c["start"] > "2021-04-22" for c in doubled),
          "n_term_extended_6m": sum((c["term_extended_days"] or 0) >= 182 for c in doubled),
          "n_term_unchanged": sum(abs(c["term_extended_days"] or 0) < 60 for c in doubled),
          "n_annualized_ratio_ge_2": sum((c["annualized_ratio"] or 0) >= 2 for c in doubled),
          "n_annualized_ratio_lt_1_5": sum((c["annualized_ratio"] or 9) < 1.5 for c in doubled),
          "n_run_rate_known": sum(c["run_rate_ratio"] is not None for c in doubled),
          "n_run_rate_ge_1_5": sum((c["run_rate_ratio"] or 0) >= 1.5 for c in doubled),
          "median_ratio_all": st.median(c["now"] / c["orig"] for c in con)}
    # a stricter panel: contracts already observed in April 2021 that started before it
    panel = [c for c in con if c["orig_snap"] == "2021-04-22"]
    F5["panel_2021"] = {"n": len(panel), "doubled": sum(c["now"] / c["orig"] >= 2 for c in panel),
                        "doubled_same_term": sum(c["now"] / c["orig"] >= 2 and abs((date.fromisoformat(c["end"]) - date.fromisoformat(c["orig_end"])).days) < 60 for c in panel)}
    ex = {}
    for cid in ("1000010457", "1000017241"):
        c = next((x for x in doubled if x["id"] == cid), None)
        if c:
            ex[cid] = {k: c[k] for k in ("title", "ein", "dept", "start", "end", "orig", "orig_snap", "orig_end", "now", "history",
                                         "term_extended_days", "annualized_ratio", "run_rate_ratio", "paid_by_fy", "authority")}
    F5["examples"] = ex
    R["F5_contracts"] = F5
    json.dump(doubled, open(os.path.join(OUT, "doubled_contracts.json"), "w"), indent=1)

    # ============ F6 HSH spending vs households placed
    o = pd.read_csv(os.path.join(BASE, "outcomes", "outcomes.csv"))
    def ms(mid):
        s = o[o.measure_id == mid].drop_duplicates("fiscal_year").set_index("fiscal_year")
        return s.value, s.value_basis
    parts_old = ["SCM-HOM-ecf75eac", "SCM-HOM-25057c1f", "SCM-HOM-50792742"]
    parts_new = ["CPM-HOM-0490c63a", "CPM-HOM-70c2574e", "CPM-HOM-effe2874"]
    placed = {}
    basis = {}
    for grp in (parts_old, parts_new):
        for mid in grp:
            v, bs = ms(mid)
            for fy, x in v.items():
                placed[int(fy)] = placed.get(int(fy), 0) + x; basis[int(fy)] = bs[fy]
    hom = defaultdict(float); hsa_homeless = defaultdict(float)
    for (fy, d, e), a in cells.items():
        if d == "HOM":
            hom[fy] += a
    real = lambda fy: hom[fy] * sf[2025] / sf[fy] if fy in sf else None
    # FY2026 CPI: SF CPI may be incomplete; use the site's index
    real26 = hom[2026] / idx[2026]
    rr = lambda a, b: ((real26 if b == 2026 else real(b)) / real(a) - 1)
    F6 = {"placed": {str(k): placed[k] for k in sorted(placed)}, "placed_basis": {str(k): basis[k] for k in sorted(basis)},
          "hom_nominal": {str(k): hom[k] for k in range(2017, 2027)},
          "pipeline_pair_2018_2026": {"real_spend": rr(2018, 2026), "placed": placed[2026] / placed[2018] - 1},
          "pair_2019_2025": {"real_spend": rr(2019, 2025), "placed": placed[2025] / placed[2019] - 1},
          "pair_2018_2025": {"real_spend": rr(2018, 2025), "placed": placed[2025] / placed[2018] - 1},
          "pair_2023_2025_same_series": {"real_spend": rr(2023, 2025), "placed": placed[2025] / placed[2023] - 1},
          "pair_2023_2026_same_series": {"real_spend": rr(2023, 2026), "placed": placed[2026] / placed[2023] - 1},
          "hsa_homeless_contracts_note": "HSH (HOM) began in FY2017; some homelessness contracts were still paid by HSA in FY2017-18."}
    # reorganization check: HSA payments to organizations whose area is homelessness, FY2017-2019
    homeless_orgs = {o_.replace("org-", "") for o_, v in orgs.items() if v["area"] == "homeless"}
    for (fy, d, e), a in cells.items():
        if d in ("HSA", "DSS") and e in homeless_orgs:
            hsa_homeless[fy] += a
    F6["hsa_payments_to_homeless_area_orgs"] = {str(k): hsa_homeless[k] for k in range(2016, 2027)}
    F6["pair_2018_2026_incl_hsa_homeless_orgs"] = {"real_spend": ((hom[2026] + hsa_homeless[2026]) / idx[2026]) / ((hom[2018] + hsa_homeless[2018]) * sf[2025] / sf[2018]) - 1}
    R["F6_hsh_outcomes"] = F6
    json.dump(R, open(os.path.join(OUT, "findings.json"), "w"), indent=1, default=float)
    print(json.dumps(R, indent=1, default=float)[:12000])


if __name__ == "__main__":
    main()
