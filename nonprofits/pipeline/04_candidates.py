"""Generate IRS candidate matches for city vendors.

Vendor universe: vendors with >= $100k lifetime expenditure-class payments (FY2007-FY2027),
plus vendors with >= $25k that the city flags as nonprofit or that received City Grant Program /
community-based-organization payments.

For each vendor we search all IRS name variants (BMF, revocation list, e-file index names) with a
token inverted index (rarest tokens first), score with rapidfuzz, and keep the top candidates.
We also attach "address evidence": SF Registered Business Locations records whose ownership or
DBA name matches the vendor, compared with the IRS street address / ZIP.

Output: data/interim/vendors.parquet, data/interim/candidates.parquet
"""
import math, os, re, sys
from collections import defaultdict
import pandas as pd
from rapidfuzz import fuzz, process
sys.path.insert(0, os.path.dirname(__file__))
from lib_names import norm, split_dba

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

BAY = {"SAN FRANCISCO", "OAKLAND", "BERKELEY", "DALY CITY", "SAN MATEO", "SOUTH SAN FRANCISCO", "EMERYVILLE",
       "RICHMOND", "SAN JOSE", "BRISBANE", "BURLINGAME", "REDWOOD CITY", "SAUSALITO", "SAN RAFAEL", "ALAMEDA",
       "SAN LEANDRO", "HAYWARD", "PALO ALTO", "MENLO PARK", "COLMA", "PACIFICA", "MILLBRAE", "SAN BRUNO",
       "WALNUT CREEK", "CONCORD", "FREMONT", "NOVATO", "MILL VALLEY", "SAN CARLOS", "BELMONT", "FOSTER CITY"}


def build_vendors():
    p = pd.read_parquet(os.path.join(INT, "payments.parquet"))
    e = p[p.spend_class == "expenditure"]
    agg = e.groupby("vendor").agg(total_paid=("paid", "sum"), first_fy=("fiscal_year", "min"),
                                  last_fy=("fiscal_year", "max"))
    agg["service_paid"] = e[e.service_class == "contracted_services"].groupby("vendor").paid.sum()
    agg["grant_paid"] = e[e.char_group == "City Grant Program"].groupby("vendor").paid.sum()
    cbo = e.object.str.contains("Community Based|Comm Based|CBO|Homeless", case=False, na=False)
    agg["cbo_paid"] = e[cbo].groupby("vendor").paid.sum()
    agg["city_np_flag_paid"] = p[p.non_profit_indicator == "X"].groupby("vendor").paid.sum()
    agg = agg.fillna(0)
    agg["city_np_flag"] = agg.city_np_flag_paid.abs() > 0
    top_depts = (e.groupby(["vendor", "department"]).paid.sum().reset_index()
                 .sort_values("paid", ascending=False).groupby("vendor").head(3)
                 .groupby("vendor").department.apply(lambda s: "; ".join(s)))
    agg["top_departments"] = top_depts
    titles = (e[e.contract_title != ""].groupby(["vendor", "contract_title"]).paid.sum().reset_index()
              .sort_values("paid", ascending=False).groupby("vendor").head(4)
              .groupby("vendor").contract_title.apply(lambda s: "; ".join(s)))
    agg["top_contract_titles"] = titles
    objs = (e.groupby(["vendor", "object"]).paid.sum().reset_index().sort_values("paid", ascending=False)
            .groupby("vendor").head(3).groupby("vendor").object.apply(lambda s: "; ".join(s)))
    agg["top_objects"] = objs
    sel = (agg.total_paid >= 1e5) | ((agg.total_paid >= 2.5e4) & (agg.city_np_flag | (agg.grant_paid > 0) | (agg.cbo_paid > 0)))
    v = agg[sel].reset_index()
    v = v[v.vendor.str.strip() != ""]
    v["vendor_norm"] = v.vendor.map(norm)
    v.to_parquet(os.path.join(INT, "vendors.parquet"))
    print("vendors in universe", len(v), "share of expenditure $", v.total_paid.sum() / agg.total_paid.sum())
    return v


def main():
    v = build_vendors()
    names = pd.read_parquet(os.path.join(INT, "irs_names.parquet"))
    orgs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    # token document frequency over distinct normalized names
    uniq = names.drop_duplicates("norm")[["norm"]].reset_index(drop=True)
    df = defaultdict(int)
    inv = defaultdict(list)
    for i, n in enumerate(uniq.norm.values):
        toks = set(n.split())
        for t in toks:
            df[t] += 1
            inv[t].append(i)
    N = len(uniq)
    norm_to_eins = names.groupby("norm").EIN.apply(lambda s: sorted(set(s))).to_dict()
    print("unique IRS names", N)
    uniq_norm = list(uniq.norm.values)
    key_to_norms = defaultdict(list)
    for n in uniq_norm:
        key_to_norms[n.replace(" ", "")].append(n)

    rows = []
    import time; t0 = time.time()
    for vi, (_, r) in enumerate(v.iterrows()):
        if vi % 500 == 0:
            print(vi, round(time.time() - t0), flush=True)
        variants = {r.vendor_norm} | {norm(x) for x in split_dba(r.vendor)}
        variants = {x for x in variants if x}
        cand_idx = set()
        for vn in variants:
            toks = sorted(set(vn.split()), key=lambda t: df.get(t, 0) or 10**9)
            toks = [t for t in toks if df.get(t, 0) > 0]
            if not toks:
                continue
            if df[toks[0]] <= 20000 or len(toks) == 1:
                cand_idx.update(inv[toks[0]][:200000])
                if len(toks) > 1 and df[toks[1]] <= 20000:
                    cand_idx.update(inv[toks[1]])
            else:
                cand_idx.update(set(inv[toks[0]]) & set(inv[toks[1]]))
        cand_idx = list(cand_idx)
        choices = [uniq_norm[i] for i in cand_idx]
        best = {}
        for vn in variants:
            for scorer, w in ((fuzz.token_sort_ratio, 1.0), (fuzz.token_set_ratio, 0.95)):
                for cn, sc, _ in process.extract(vn, choices, scorer=scorer, limit=120, score_cutoff=70):
                    if w < 1:
                        # token_set_ratio rewards subsets; require the vendor's rarest token to be present
                        # and at least 2 shared tokens, otherwise generic names ("SAN FRANCISCO") match everything
                        vt = [t for t in vn.split() if df.get(t, 0) > 0]
                        ct = set(cn.split())
                        if min(len(vn), len(cn)) <= 8 or not vt:
                            continue
                        rare = min(vt, key=lambda t: df[t])
                        if rare not in ct or len(ct & set(vt)) < 2:
                            continue
                    best[cn] = max(best.get(cn, 0), sc * w)
            k = vn.replace(" ", "")
            for cn in key_to_norms.get(k, []):
                best[cn] = 100
        scored = [(sc, cn) for cn, sc in best.items()]
        scored.sort(reverse=True)
        pool = []
        for s, cn in scored[:30]:
            for ein in norm_to_eins.get(cn, [])[:300]:
                if ein not in orgs.index:
                    continue
                o = orgs.loc[ein]
                city = o.CITY if isinstance(o.CITY, str) else ""
                bay = city in BAY
                prio = s + 6 * bay + 3 * (o.STATE == "CA") + 1 * bool(o.in_bmf)
                pool.append((prio, s, ein, cn, o, bay))
        pool.sort(key=lambda x: -x[0])
        seen_e = set()
        for prio, s, ein, cn, o, bay in pool:
            if ein in seen_e:
                continue
            seen_e.add(ein)
            rows.append({"vendor": r.vendor, "ein": ein, "irs_name_matched": cn, "score": s,
                         "irs_name": o.NAME, "irs_city": o.CITY, "irs_state": o.STATE, "irs_street": o.STREET,
                         "irs_zip": o.ZIP, "subsection": o.SUBSECTION, "ntee": o.NTEE_CD,
                         "revenue_amt": o.REVENUE_AMT, "in_bmf": bool(o.in_bmf),
                         "revocation_date": o.revocation_date, "last_tax_period": o.last_tax_period,
                         "bay_area": bay})
            if len(seen_e) >= 25:
                break
    c = pd.DataFrame(rows).drop_duplicates(["vendor", "ein"])
    c.to_parquet(os.path.join(INT, "candidates.parquet"))
    print("candidate rows", len(c), "vendors with >=1 candidate", c.vendor.nunique())


if __name__ == "__main__":
    main()
