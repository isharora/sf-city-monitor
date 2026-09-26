"""Step 10b: red team. Adds `redteam` and `sensitivity` to data/analysis/analysis.json.

1. Independent re-derivation of key rates directly from the raw extraction files
   (data/extract/status/*.json), without the linking/row-building code path.
2. Sensitivity of implementation rates to status-mapping choices.
3. How much of 'implemented' is auditor-verified vs department self-reported.
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, RAW  # noqa

WORK = os.path.join(DATA, "work")
AS_OF = date(2026, 9, 26)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def rate(rows, impl=lambda r: r["status"] == "implemented", known=lambda r: r["status"] != "unknown"):
    k = [r for r in rows if known(r)]
    return {"n_known": len(k), "implemented": sum(1 for r in k if impl(r)),
            "rate": round(sum(1 for r in k if impl(r)) / len(k), 3) if k else None}


def main():
    A = json.load(open(os.path.join(DATA, "analysis", "analysis.json")))
    rows = json.load(open(os.path.join(WORK, "rows_final.json")))
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    RT = {}

    # ---- 1a. CGJ original responses straight from response letters + trackers (dedup by report/rec/dept)
    seen = {}
    for f in os.listdir(os.path.join(DATA, "extract", "status")):
        if not f.endswith(".json"):
            continue
        r = json.load(open(os.path.join(DATA, "extract", "status", f)))
        did = r["doc_id"]
        if inv[did]["doc_type"] not in ("cgj_response", "cgj_status_tracker"):
            continue
        for it in r["data"]["items"]:
            k = (norm(it.get("source_report_title"))[:40], norm(it.get("rec_id")), norm(it.get("department") or it.get("respondent"))[:25])
            o = it.get("original_response")
            if o and o not in ("not_applicable",):
                seen.setdefault(k, o)
    raw_mix = Counter(seen.values())
    tot = sum(raw_mix.values())
    RT["cgj_original_response_raw_rederived"] = {"n": tot, "shares": {k: round(v / tot, 3) for k, v in raw_mix.items()}}
    rows_cgj = [r for r in rows if r["source"] == "cgj" and r.get("cgj_response")]
    mix = Counter(r["cgj_response"] for r in rows_cgj)
    RT["cgj_original_response_rows"] = {"n": len(rows_cgj), "shares": {k: round(v / len(rows_cgj), 3) for k, v in mix.items()}}

    # ---- 1b. CGJ latest status straight from trackers (dedup)
    latest = {}
    for f in os.listdir(os.path.join(DATA, "extract", "status")):
        if not f.startswith("CGJS-"):
            continue
        r = json.load(open(os.path.join(DATA, "extract", "status", f)))
        for it in r["data"]["items"]:
            k = (f, norm(it.get("source_report_title"))[:40], norm(it.get("rec_id")), norm(it.get("department"))[:25])
            latest[k] = it["status"]
    lm = Counter(latest.values())
    tl = sum(v for k, v in lm.items() if k != "unknown")
    RT["cgj_tracker_latest_status_raw_rederived"] = {"n": sum(lm.values()), "counts": dict(lm),
                                                     "implemented_share_known": round(lm["implemented"] / tl, 3) if tl else None}
    rt = [r for r in rows if r["source"] == "cgj" and r["status_basis"] == "cgj_status_tracker"]
    RT["cgj_tracker_latest_status_rows"] = {"n": len(rt), "counts": dict(Counter(r["status"] for r in rt)), **rate(rt)}

    # ---- 1c. CSA: compare with CSA's own published totals
    csa_claims = []
    for f in os.listdir(os.path.join(DATA, "extract", "status")):
        did = f[:-5]
        if f.endswith(".json") and inv.get(did, {}).get("doc_type") == "csa_open_over_2yrs":
            r = json.load(open(os.path.join(DATA, "extract", "status", f)))
            csa_claims.append({"doc": did, "as_of": r["data"]["doc"].get("as_of_date"), "claim": r["data"]["doc"].get("summary_counts")})
    RT["csa_published_claims"] = sorted(csa_claims, key=lambda x: x["as_of"] or "")
    win = [r for r in rows if r["source"] == "csa" and r.get("in_csa_followup_scope") and r["date_issued"] and "2010-07-01" <= r["date_issued"] <= "2025-06-30"]
    RT["csa_ours_same_window"] = {"window": "issued 2010-07-01..2025-06-30, CSA audits in follow-up scope", "n": len(win),
                                  "status": dict(Counter(r["status"] for r in win)), **rate(win)}

    # ---- 2. sensitivity
    S = {}
    def by_src(fn_impl=None, fn_known=None, subset=None):
        out = {}
        for s in ("csa", "bla", "cgj", "all"):
            rs = [r for r in rows if (s == "all" or r["source"] == s) and (subset is None or subset(r))]
            kw = {}
            if fn_impl:
                kw["impl"] = fn_impl
            if fn_known:
                kw["known"] = fn_known
            out[s] = rate(rs, **kw)
        return out
    S["baseline_implemented_over_known"] = by_src()
    S["implemented_over_all_rows"] = by_src(fn_known=lambda r: True)
    S["in_progress_counts_as_implemented"] = by_src(fn_impl=lambda r: r["status"] in ("implemented", "in_progress"))
    S["csa_report_closed_not_counted_as_implemented"] = by_src(
        fn_impl=lambda r: r["status"] == "implemented" and r["status_basis"] != "csa_report_closed",
        fn_known=lambda r: r["status"] != "unknown" and r["status_basis"] != "csa_report_closed")
    S["no_absence_inference"] = by_src(fn_known=lambda r: r["status"] != "unknown" and r["status_basis"] != "inferred_absent_from_open_over_2yrs_list")
    S["closed_other_excluded_from_denominator"] = by_src(fn_known=lambda r: r["status"] not in ("unknown", "closed_other"))
    S["tracker_star_star_resolved_as_unknown"] = by_src(fn_known=lambda r: r["status"] != "unknown" and "[then **]" not in (r.get("status_raw") or ""))
    S["only_auditor_verified_evidence"] = by_src(fn_known=lambda r: r["status"] != "unknown" and r["status_basis"] in ("csa_field_followup", "pi_status_update"))
    S["issued_2011_2022_only"] = by_src(subset=lambda r: r["date_issued"] and "2011" <= r["date_issued"][:4] <= "2022")
    # CGJ at recommendation level (any respondent implemented) vs rec x respondent
    g = defaultdict(list)
    for r in rows:
        if r["source"] == "cgj" and r["status"] != "unknown":
            g[r.get("rec_number"), r["report"]].append(r["status"])
    anyimpl = sum(1 for v in g.values() if "implemented" in v)
    S["cgj_rec_level_any_respondent_implemented"] = {"n_recs": len(g), "implemented_any": anyimpl, "rate": round(anyimpl / len(g), 3) if g else None}
    S["cgj_excluding_mayor_and_board_rows"] = by_src(subset=lambda r: r["source"] == "cgj" and r["dept"] not in ("MYR", "BOS"))
    # agreed mapping: CGJ 'requires further analysis' as disagree
    cg = [r for r in rows if r["source"] == "cgj" and r.get("cgj_response")]
    alt = Counter("disagree" if r["cgj_response"] in ("will_not_be_implemented", "requires_further_analysis") else r["agreed"] for r in cg)
    S["cgj_agreed_if_further_analysis_counted_as_disagree"] = {k: round(v / len(cg), 3) for k, v in alt.items()} if cg else None
    S["cgj_agreed_baseline"] = {k: round(v / len(cg), 3) for k, v in Counter(r["agreed"] for r in cg).items()} if cg else None

    # ---- 3. verified vs self-reported
    basis = Counter(r["status_basis"] for r in rows if r["status"] == "implemented")
    verified = {"csa_field_followup", "pi_status_update"}
    csa_self = {"csa_report_closed", "csa_followup_summary", "inferred_absent_from_open_over_2yrs_list", "csa_open_over_2yrs"}
    RT["implemented_by_evidence"] = dict(basis)
    n_impl = sum(basis.values())
    RT["implemented_evidence_shares"] = {
        "auditor_field_verified": round(sum(v for k, v in basis.items() if k in verified) / n_impl, 3) if n_impl else None,
        "csa_followup_based_on_department_reports": round(sum(v for k, v in basis.items() if k in csa_self) / n_impl, 3) if n_impl else None,
        "cgj_department_self_report": round(sum(v for k, v in basis.items() if k in ("cgj_status_tracker", "cgj_response")) / n_impl, 3) if n_impl else None}

    A["redteam"] = RT
    A["sensitivity"] = S
    json.dump(A, open(os.path.join(DATA, "analysis", "analysis.json"), "w"), indent=1, default=str)
    print(json.dumps({"redteam": RT, "sensitivity": S}, indent=1, default=str)[:8000])


if __name__ == "__main__":
    main()
