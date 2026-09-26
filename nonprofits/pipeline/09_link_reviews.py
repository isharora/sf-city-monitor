"""Link accountability findings (data/reviews/org_findings.json) to matched EINs.

For every distinct organization name (plus aliases) in the findings we look for matching names among
(a) city vendor names matched to an EIN and (b) IRS names of matched EINs. Exact normalized-name hits are
accepted. Otherwise the top fuzzy candidates go to claude-sonnet-5 for a decision (with rationale and
confidence). Unlinked findings are kept (ein = null) so nothing is dropped.
Output: data/interim/findings_linked.parquet
"""
import json, os, sys
import pandas as pd
from rapidfuzz import fuzz, process
sys.path.insert(0, os.path.dirname(__file__))
from lib_names import norm
from lib_llm import call_json

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

SCHEMA = {"type": "object", "properties": {
    "ein": {"type": "string", "description": "EIN of the same organization, or NONE"},
    "confidence": {"type": "number"}, "rationale": {"type": "string"}},
    "required": ["ein", "confidence", "rationale"], "additionalProperties": False}


def main():
    f = pd.DataFrame(json.load(open(os.path.join(BASE, "reviews", "org_findings.json"))))
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet"))
    m = m[m.matched_ein != "NONE"]
    orgs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    names = pd.read_parquet(os.path.join(INT, "irs_names.parquet"))
    eins = set(m.matched_ein)
    ref = pd.concat([m[["vendor", "matched_ein"]].rename(columns={"vendor": "name", "matched_ein": "ein"}),
                     names[names.EIN.isin(eins)][["NAME", "EIN"]].rename(columns={"NAME": "name", "EIN": "ein"})])
    ref["n"] = ref.name.map(norm)
    ref = ref[ref.n != ""].drop_duplicates(["n", "ein"])
    n2e = ref.groupby("n").ein.apply(lambda s: sorted(set(s))).to_dict()
    choices = list(n2e)
    uniq = {}
    for _, r in f.iterrows():
        allnames = [r.org_name] + list(r.org_name_aliases or [])
        uniq.setdefault(r.org_name, set()).update(allnames)
    link = {}
    for on, als in uniq.items():
        hit = None
        for a in als:
            e = n2e.get(norm(a))
            if e and len(e) == 1:
                hit = (e[0], 1.0, "exact normalized name match")
                break
        if hit is None:
            cands = {}
            for a in als:
                for scorer, cut in ((fuzz.token_sort_ratio, 70), (fuzz.WRatio, 80)):
                    for cn, sc, _ in process.extract(norm(a), choices, scorer=scorer, limit=6, score_cutoff=cut):
                        for e in n2e[cn]:
                            cands[e] = max(cands.get(e, 0), sc)
            if cands:
                lines = [f"Organization named in a San Francisco government review or news story: {on}",
                         f"Aliases given: {', '.join(sorted(als - {on})) or 'none'}", "Candidate IRS organizations:"]
                for e, sc in sorted(cands.items(), key=lambda x: -x[1])[:8]:
                    o = orgs.loc[e] if e in orgs.index else None
                    vn = "; ".join(m[m.matched_ein == e].vendor.head(3))
                    lines.append(f"- EIN {e}: {o.NAME if o is not None else ''} ({o.CITY if o is not None else ''}); city vendor names: {vn}")
                lines.append("Is one of these the same organization? Answer NONE unless clearly the same entity.")
                r = call_json("link_reviews", "\n".join(lines), SCHEMA, model="claude-sonnet-5", effort="medium", max_tokens=3000)
                e = r["ein"].replace("-", "").strip()
                if e in cands:
                    hit = (e, r["confidence"], r["rationale"])
        link[on] = hit
    ov = os.path.join(BASE, "manual", "review_link_overrides.csv")
    if os.path.exists(ov):
        for _, r in pd.read_csv(ov, dtype=str).iterrows():
            link[r.org_name] = (r.ein, 1.0, "manual override: " + r.note)
    f["ein"] = f.org_name.map(lambda x: link[x][0] if link.get(x) else None)
    f["link_confidence"] = f.org_name.map(lambda x: link[x][1] if link.get(x) else None)
    f["link_rationale"] = f.org_name.map(lambda x: link[x][2] if link.get(x) else None)
    f["org_name_aliases"] = f.org_name_aliases.map(lambda x: list(x or []))
    f.to_parquet(os.path.join(INT, "findings_linked.parquet"))
    print("findings", len(f), "linked", f.ein.notna().sum(), "orgs linked", f[f.ein.notna()].ein.nunique(),
          "unlinked names", sorted(set(f[f.ein.isna()].org_name))[:60])


if __name__ == "__main__":
    main()
