"""Pass 3: discovery for likely-nonprofit vendors with no accepted match.

Targets: universe vendors with total expenditure >= $250k where
  (a) pass 1/2 returned NONE but judged vendor_is_exempt_org yes/unsure, or
  (b) no candidate >= 85 existed but the city flags them nonprofit or they received City Grant Program /
      community-based-organization payments.
Step A (claude-sonnet-5): propose up to 5 likely IRS legal names (former names, full names for acronyms,
        legal names behind DBAs), or say it is not an exempt org.
Step B: search IRS name variants for those names (exact normalized key, then fuzzy within names sharing
        the rarest token), preferring CA/Bay Area.
Step C (claude-opus-5-5, effort high): adjudicate against the new candidate list.
Output: data/interim/matches_pass3.parquet and data/interim/matches_final.parquet
"""
import os, sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from rapidfuzz import fuzz, process
sys.path.insert(0, os.path.dirname(__file__))
from lib_llm import call_json, spent
from lib_names import norm
import importlib.util
_spec = importlib.util.spec_from_file_location("adj", os.path.join(os.path.dirname(__file__), "05_adjudicate.py"))
adj = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(adj)

INT = os.path.join(os.path.dirname(__file__), "..", "data", "interim")
BAY = {"SAN FRANCISCO", "OAKLAND", "BERKELEY", "DALY CITY", "SAN MATEO", "SOUTH SAN FRANCISCO", "EMERYVILLE",
       "RICHMOND", "SAN JOSE", "BRISBANE", "BURLINGAME", "REDWOOD CITY", "SAUSALITO", "SAN RAFAEL", "ALAMEDA",
       "SAN LEANDRO", "HAYWARD", "PALO ALTO", "MENLO PARK", "COLMA", "PACIFICA", "MILLBRAE", "SAN BRUNO"}

PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "likely_exempt_org": {"type": "string", "enum": ["yes", "no", "unsure"]},
        "vendor_type": {"type": "string", "enum": ["nonprofit_service_provider", "nonprofit_other", "government",
                                                   "university_or_hospital_system", "for_profit_company",
                                                   "affordable_housing_partnership_or_llc", "individual", "unknown"]},
        "candidate_legal_names": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
    "required": ["likely_exempt_org", "vendor_type", "candidate_legal_names", "rationale"],
    "additionalProperties": False,
}


def main():
    v = pd.read_parquet(os.path.join(INT, "vendors.parquet")).set_index("vendor", drop=False)
    m = pd.read_parquet(os.path.join(INT, "matches.parquet"))
    matched = set(m[m.matched_ein != "NONE"].vendor)
    a = set(m[(m.matched_ein == "NONE") & (m.vendor_is_exempt_org != "no")].vendor)
    b = set(v[(v.city_np_flag | (v.grant_paid > 0) | (v.cbo_paid > 0))].vendor) - set(m.vendor)
    targets = [x for x in (a | b) if x not in matched and v.loc[x].total_paid >= 2.5e5]
    print("discovery targets", len(targets))

    def propose(name):
        r = v.loc[name]
        p = (f"San Francisco city vendor name: {r.vendor}\nPaid FY{r.first_fy}-FY{r.last_fy}: ${r.total_paid:,.0f}\n"
             f"Departments: {r.top_departments}\nContract titles: {r.top_contract_titles}\nObjects: {r.top_objects}\n"
             f"City nonprofit flag: {r.city_np_flag}\n\nIf this payee is (or may be) a US tax-exempt organization, list up "
             "to 5 names under which it is likely registered with the IRS (full legal name, former names, the legal "
             "entity behind a DBA, spelled-out acronyms), most likely first. If it is clearly a for-profit company, "
             "government body, individual, or a limited partnership/LLC (e.g., an affordable-housing project entity), "
             "say so and return an empty list. Only list names you have real reason to believe.")
        out = call_json("discover_propose", p, PROPOSE_SCHEMA, model="claude-sonnet-5", effort="medium", max_tokens=4000)
        out["vendor"] = name
        return out

    with ThreadPoolExecutor(16) as ex:
        props = list(ex.map(propose, targets))
    props = pd.DataFrame(props)
    props.to_parquet(os.path.join(INT, "discover_proposals.parquet"))
    print("proposals with names", (props.candidate_legal_names.map(len) > 0).sum(), "spent", round(spent(), 2))

    names = pd.read_parquet(os.path.join(INT, "irs_names.parquet"))
    orgs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    key_to = names.assign(k=names.norm.str.replace(" ", "")).groupby("k").EIN.apply(lambda s: sorted(set(s))).to_dict()
    uniq = names.drop_duplicates("norm").norm.tolist()
    df = defaultdict(int); inv = defaultdict(list)
    for i, n in enumerate(uniq):
        for t in set(n.split()):
            df[t] += 1; inv[t].append(i)
    norm_to = names.groupby("norm").EIN.apply(lambda s: sorted(set(s))).to_dict()

    def search(nm):
        n = norm(nm)
        hits = {}
        for e in key_to.get(n.replace(" ", ""), []):
            hits[e] = 100
        toks = sorted([t for t in set(n.split()) if df.get(t)], key=lambda t: df[t])
        if toks:
            pool = inv[toks[0]] if df[toks[0]] < 30000 else list(set(inv[toks[0]]) & set(inv[toks[1]] if len(toks) > 1 else []))
            ch = [uniq[i] for i in pool]
            for cn, sc, _ in process.extract(n, ch, scorer=fuzz.token_sort_ratio, limit=30, score_cutoff=80):
                for e in norm_to.get(cn, [])[:50]:
                    hits[e] = max(hits.get(e, 0), sc)
        return hits

    rows = []
    for _, p in props.iterrows():
        if p.likely_exempt_org == "no" or not len(p.candidate_legal_names):
            continue
        hits = {}
        for nm in list(p.candidate_legal_names)[:5]:
            for e, sc in search(nm).items():
                hits[e] = max(hits.get(e, 0), sc)
        for e, sc in hits.items():
            if e not in orgs.index:
                continue
            o = orgs.loc[e]
            rows.append({"vendor": p.vendor, "ein": e, "score": sc, "irs_name": o.NAME, "irs_city": o.CITY,
                         "irs_state": o.STATE, "irs_street": o.STREET, "irs_zip": o.ZIP, "subsection": o.SUBSECTION,
                         "ntee": o.NTEE_CD, "revenue_amt": o.REVENUE_AMT, "in_bmf": bool(o.in_bmf),
                         "revocation_date": o.revocation_date, "last_tax_period": o.last_tax_period,
                         "bay_area": (o.CITY in BAY) if isinstance(o.CITY, str) else False})
    c3 = pd.DataFrame(rows)
    c3.to_parquet(os.path.join(INT, "candidates_pass3.parquet"))
    biz = adj.build_biz_index()
    groups = {k: adj.pick_cands(g) for k, g in c3.groupby("vendor")}
    print("pass3 adjudications", len(groups))
    jobs = [(adj.adjudicate, v.loc[k], g, biz, "claude-opus-5-5", "high", "match_pass3_opus") for k, g in groups.items()]
    p3 = pd.DataFrame(adj.run_parallel(jobs, workers=6))
    p3["pass"] = 3
    p3.to_parquet(os.path.join(INT, "matches_pass3.parquet"))
    # final: pass3 matches override NONE decisions
    newm = p3[p3.matched_ein != "NONE"]
    final = pd.concat([m[~m.vendor.isin(newm.vendor)], newm])
    # vendors with proposals but no match: record typing info
    final.to_parquet(os.path.join(INT, "matches_final.parquet"))
    print("final matches", (final.matched_ein != "NONE").sum(), "spent", round(spent(), 2))


if __name__ == "__main__":
    main()
