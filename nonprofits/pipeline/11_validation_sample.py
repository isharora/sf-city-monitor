"""Draw a stratified validation sample of match decisions for hand review.

Sample (seed 20260926):
  - 45 accepted matches from vendors paid >= $10M, 45 from $1M-$10M, 30 from < $1M (precision)
  - 30 'NONE' decisions for vendors the city flags as nonprofit or that received grants (recall check)
  - 20 random 'NONE' decisions (recall check on the remainder)
Evidence columns: vendor payment profile, IRS record, and (where available) the 990 filer name/address/
mission from the e-file XML, so each row can be judged independently of the model's rationale.
Output: data/validation/sample_to_review.csv  (reviewer fills verdict + note in
        data/validation/hand_review.csv, keyed on vendor)
"""
import glob, json, os
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")
OUT = os.path.join(BASE, "validation")
os.makedirs(OUT, exist_ok=True)

def main():
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet"))
    v = pd.read_parquet(os.path.join(INT, "vendors.parquet")).set_index("vendor")
    orgs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    m = m.join(v[["total_paid", "city_np_flag", "grant_paid", "top_departments", "top_contract_titles"]], on="vendor")
    acc = m[m.matched_ein != "NONE"]
    s = pd.concat([acc[acc.total_paid >= 1e7].sample(45, random_state=20260926),
                   acc[(acc.total_paid >= 1e6) & (acc.total_paid < 1e7)].sample(45, random_state=20260926),
                   acc[acc.total_paid < 1e6].sample(30, random_state=20260926)]).assign(stratum="accepted")
    none = m[m.matched_ein == "NONE"]
    n1 = none[none.city_np_flag | (none.grant_paid > 0)]
    s2 = pd.concat([n1.sample(min(30, len(n1)), random_state=1).assign(stratum="none_flagged_or_grant"),
                    none.drop(n1.index, errors="ignore").sample(20, random_state=2).assign(stratum="none_random")])
    s = pd.concat([s, s2])
    # 990 filer evidence
    fil = {}
    for f in glob.glob(os.path.join(BASE, "cache", "990", "*.json")):
        d = json.load(open(f))
        e = (d.get("ein") or "").zfill(9)
        if e and (e not in fil or d.get("tax_period_end", "") > fil[e].get("tax_period_end", "")):
            fil[e] = {"tax_period_end": d.get("tax_period_end"), "filer": f"{d.get('filer_name')} | {d.get('filer_street')}, {d.get('filer_city')} {d.get('filer_state')}",
                      "mission": (d.get("mission") or "")[:200], "revenue": d.get("total_revenue")}
    rows = []
    for _, r in s.iterrows():
        e = r.matched_ein
        o = orgs.loc[e] if e in orgs.index else None
        rows.append({"stratum": r.stratum, "vendor": r.vendor, "total_paid": round(r.total_paid), "city_np_flag": r.city_np_flag,
                     "departments": r.top_departments, "contract_titles": r.top_contract_titles,
                     "matched_ein": e, "irs_name": o.NAME if o is not None else "", "irs_addr": f"{o.STREET}, {o.CITY} {o.STATE}" if o is not None else "",
                     "ntee": o.NTEE_CD if o is not None else "", "filer_990": fil.get(e, {}).get("filer", ""),
                     "mission_990": fil.get(e, {}).get("mission", ""), "rev_990": fil.get(e, {}).get("revenue", ""),
                     "model": r.model, "pass": r["pass"], "confidence": r.confidence, "vendor_type": r.vendor_type,
                     "rationale": r.rationale})
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "sample_to_review.csv"), index=False)
    print(len(rows), "rows written")

if __name__ == "__main__":
    main()
