"""Adjudicate vendor -> IRS EIN matches with Claude.

Pass 1 (claude-sonnet-5, effort medium): every universe vendor that has at least one IRS
candidate scoring >= 85. Claude sees the vendor's payment profile (departments, contract titles,
objects, city nonprofit flag, years), SF business-registration addresses for that name, and up
to 10 IRS candidates (name, city/state/street/ZIP, subsection, NTEE, revenue, revocation).
Pass 2 (claude-opus-5-5, effort high): re-adjudicate pass-1 decisions with confidence < 0.8
on vendors paid >= $1M, plus any pass-1 match paid >= $20M (high-stakes check).
Pass 3 (discovery): large vendors that look like nonprofits (city flag or grant/CBO payments,
>= $500k) with no accepted match: Claude proposes likely legal names (former names, DBAs); we
search IRS names for those and adjudicate again.

Output: data/interim/matches.parquet (vendor, ein, decision, confidence, rationale, pass, model)
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from lib_llm import call_json, spent
from lib_names import norm

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

SCHEMA = {
    "type": "object",
    "properties": {
        "matched_ein": {"type": "string", "description": "EIN of the matching candidate, or 'NONE'"},
        "vendor_is_exempt_org": {"type": "string", "enum": ["yes", "no", "unsure"],
                                 "description": "Whether the vendor appears to be a tax-exempt nonprofit organization, regardless of match"},
        "vendor_type": {"type": "string", "enum": ["nonprofit_service_provider", "nonprofit_other", "government",
                                                   "university_or_hospital_system", "for_profit_company",
                                                   "individual", "unknown"]},
        "confidence": {"type": "number", "description": "0-1 confidence in the matched_ein decision"},
        "rationale": {"type": "string"},
    },
    "required": ["matched_ein", "vendor_is_exempt_org", "vendor_type", "confidence", "rationale"],
    "additionalProperties": False,
}

SYSTEM = ("You match San Francisco city government vendors (payees) to IRS tax-exempt organization records. "
          "City vendor names are often abbreviated, truncated, or use a DBA. Decide whether one candidate is the "
          "same legal entity that the city paid. Use: name equivalence (abbreviations, former names, DBAs), "
          "location (an SF-based service provider should match an SF/Bay Area EIN, not a same-name chapter "
          "elsewhere), what the city paid for (departments, contract titles) versus the candidate's NTEE/activity, "
          "and scale (revenue should be plausible for the payment size). Beware of parent vs. chapter vs. "
          "foundation/supporting-org confusion (e.g., 'X Foundation' is a different EIN from 'X'): pick the "
          "operating entity that most plausibly received the payments. If the vendor is a for-profit company, a "
          "government entity, or none of the candidates is the same entity, answer NONE. Be precise: a wrong "
          "match is worse than no match.")


def fmt_money(x):
    try:
        return f"${float(x):,.0f}"
    except Exception:
        return "n/a"


def build_biz_index():
    b = pd.read_csv(os.path.join(BASE, "raw", "sf_business_locations.csv"), dtype=str,
                    usecols=["Ownership Name", "DBA Name", "Street Address", "City", "State", "Source Zipcode",
                             "Location End Date", "Self-Reported NAICS Code"])
    idx = {}
    for col in ["Ownership Name", "DBA Name"]:
        for n, grp in b.groupby(b[col].map(norm)):
            if not n:
                continue
            idx.setdefault(n, [])
            for _, r in grp.head(4).iterrows():
                idx[n].append(f"{r['Street Address']}, {r['City']} {r['Source Zipcode']} (NAICS {r['Self-Reported NAICS Code']}; ended {r['Location End Date'] if isinstance(r['Location End Date'], str) else 'active'})")
    return idx


def prompt_for(v, cands, biz):
    lines = [f"CITY VENDOR: {v.vendor}",
             f"Total city payments FY{v.first_fy}-FY{v.last_fy}: {fmt_money(v.total_paid)} "
             f"(contracted services {fmt_money(v.service_paid)}, City Grant Program {fmt_money(v.grant_paid)})",
             f"City financial system nonprofit flag: {'yes' if v.city_np_flag else 'no'} (flag only exists FY2018+, known to be imperfect)",
             f"Top departments: {v.top_departments}",
             f"Top contract titles: {v.top_contract_titles}",
             f"Top expense objects: {v.top_objects}"]
    addrs = biz.get(v.vendor_norm, [])[:4]
    if addrs:
        lines.append("SF business registrations under this name: " + " | ".join(addrs))
    lines.append("\nIRS CANDIDATES:")
    for _, c in cands.iterrows():
        rev = f"; IRS revocation date {c.revocation_date}" if isinstance(c.revocation_date, str) and c.revocation_date else ""
        lines.append(f"- EIN {c.ein}: {c.irs_name} | {c.irs_street}, {c.irs_city}, {c.irs_state} {c.irs_zip} | "
                     f"501(c)({c.subsection}) NTEE {c.ntee} | BMF revenue {fmt_money(c.revenue_amt)} | "
                     f"in current BMF: {c.in_bmf}{rev} | last e-filed period {c.last_tax_period} | name score {c.score:.0f}")
    lines.append("\nWhich candidate EIN, if any, is this vendor? Return JSON.")
    return "\n".join(lines)


def adjudicate(v, cands, biz, model, effort, task):
    p = prompt_for(v, cands, biz)
    r = call_json(task, p, SCHEMA, model=model, system=SYSTEM, effort=effort, max_tokens=6000)
    r["matched_ein"] = r["matched_ein"].replace("-", "").strip()
    if r["matched_ein"] != "NONE" and r["matched_ein"] not in set(cands.ein):
        r["rationale"] = "[EIN not among candidates -> rejected] " + r["rationale"]
        r["matched_ein"] = "NONE"
    return {"vendor": v.vendor, **r, "model": model, "prompt_chars": len(p)}


def pick_cands(c, n=10):
    c = c.copy()
    c["prio"] = c.score + c.bay_area * 3 + (c.irs_state == "CA") * 2 + c.in_bmf * 1
    return c.sort_values("prio", ascending=False).head(n)


def run_parallel(jobs, workers=20):
    out = []
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(*j) for j in jobs]
        for i, f in enumerate(futs):
            try:
                out.append(f.result())
            except Exception as e:  # noqa
                print("ERR", e)
            if i % 250 == 0:
                print(i, "done; spent $", round(spent(), 2), flush=True)
    return out


def main():
    v = pd.read_parquet(os.path.join(INT, "vendors.parquet")).set_index("vendor", drop=False)
    c = pd.read_parquet(os.path.join(INT, "candidates.parquet"))
    biz = build_biz_index()
    c = c[c.score >= 85]
    groups = {k: pick_cands(g) for k, g in c.groupby("vendor")}
    print("pass1 vendors", len(groups))
    jobs = [(adjudicate, v.loc[k], g, biz, "claude-sonnet-5", "medium", "match_pass1") for k, g in groups.items() if k in v.index]
    p1 = pd.DataFrame(run_parallel(jobs))
    p1["pass"] = 1
    p1.to_parquet(os.path.join(INT, "matches_pass1.parquet"))

    # pass 2: Opus re-check of uncertain / high-stakes
    p1v = p1.merge(v[["total_paid"]], left_on="vendor", right_index=True)
    sel = p1v[((p1v.confidence < 0.8) & (p1v.total_paid >= 1e6)) | ((p1v.matched_ein != "NONE") & (p1v.total_paid >= 2e7))]
    print("pass2 vendors", len(sel))
    jobs = [(adjudicate, v.loc[k], groups[k], biz, "claude-opus-5-5", "high", "match_pass2_opus") for k in sel.vendor]
    p2 = pd.DataFrame(run_parallel(jobs, workers=6))
    p2["pass"] = 2
    p2.to_parquet(os.path.join(INT, "matches_pass2.parquet"))
    final = pd.concat([p1[~p1.vendor.isin(p2.vendor)], p2])
    final.to_parquet(os.path.join(INT, "matches.parquet"))
    print(final.matched_ein.ne("NONE").sum(), "matches; spent $", round(spent(), 2))


if __name__ == "__main__":
    main()
