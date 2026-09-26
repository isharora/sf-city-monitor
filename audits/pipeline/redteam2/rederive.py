"""Red team 2, part A: independent re-derivation of the headline findings.

Reads ONLY the published site export (data/site/recs/recs_*.json, reports.json,
repeats/clusters.json) -- not rows_final.json, not analysis.json -- and recomputes
every headline number with its own code, then runs robustness checks that the
data agent's 10b_redteam.py did not (circularity of agreement vs status,
within-source comparisons, respondent role for the Board of Supervisors,
evidence type behind 'reversals', staleness of 'open').

Writes data/redteam/rederive.json (merged into redteam2.json by build_redteam2.py).
"""
import glob
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
SITE = os.path.join(DATA, "site")
OUT = os.path.join(DATA, "redteam")
os.makedirs(OUT, exist_ok=True)


def load_recs():
    rows = []
    for f in sorted(glob.glob(os.path.join(SITE, "recs", "recs_*.json"))):
        rows += json.load(open(f))["rows"]
    return rows


def share(a, b):
    return round(a / b, 4) if b else None


def main():
    rows = load_recs()
    meta = json.load(open(os.path.join(SITE, "meta.json")))
    as_of = date.fromisoformat(meta["as_of"])
    R = {"as_of": meta["as_of"], "n_rows": len(rows)}
    src = lambda s: [r for r in rows if r["source"] == s]
    known = lambda rs: [r for r in rs if r["status"] != "unknown"]
    nimpl = lambda rs: sum(1 for r in rs if r["status"] == "implemented")

    # ---------------- F1 CSA 96% implemented
    csa, csak = src("csa"), known(src("csa"))
    basis = Counter(r["status_basis"] for r in csak)
    rec_level = [r for r in csak if r["status_basis"] not in ("csa_report_closed", "inferred_absent_from_open_over_2yrs_list")]
    verified = [r for r in csak if r["status_basis"] in ("csa_field_followup", "pi_status_update")]
    audits_scope = [r for r in csak if r.get("in_csa_followup_scope")]
    R["F1_csa_implemented"] = {
        "claim": "CSA 96% implemented (of recommendations with a follow-up status)",
        "n_known": len(csak), "implemented": nimpl(csak), "rate": share(nimpl(csak), len(csak)),
        "n_all": len(csa), "rate_all_rows": share(nimpl(csak), len(csa)),
        "known_by_basis": dict(basis),
        "rate_rec_level_evidence_only": {"n": len(rec_level), "rate": share(nimpl(rec_level), len(rec_level))},
        "rate_auditor_verified_only": {"n": len(verified), "rate": share(nimpl(verified), len(verified))},
        "share_of_implemented_from_report_level_closure_or_inference": share(
            sum(1 for r in csak if r["status"] == "implemented" and r["status_basis"] in ("csa_report_closed", "inferred_absent_from_open_over_2yrs_list")), nimpl(csak)),
        "unknown_by_scope": dict(Counter(("in_scope" if r.get("in_csa_followup_scope") else "out_of_scope") + ("|pre2010" if r["date_issued"][:4] < "2010" else "|2010on") for r in csa if r["status"] == "unknown").most_common()),
        "in_scope_known_rate": share(nimpl(audits_scope), len(audits_scope)),
    }

    # ---------------- F2 CGJ 43%; will-not outnumbers implemented
    cgj, cgjk = src("cgj"), known(src("cgj"))
    st = Counter(r["status"] for r in cgjk)
    notimpl = [r for r in cgjk if r["status"] == "not_implementing"]
    # distinct recommendation level: implemented if any respondent implemented
    g = defaultdict(list)
    for r in cgjk:
        g[(r["report"], r.get("rec_number"), r["text"][:80])].append(r["status"])
    anyimpl = sum(1 for v in g.values() if "implemented" in v)
    allnot = sum(1 for v in g.values() if all(x == "not_implementing" for x in v))
    no_bos_myr = [r for r in cgjk if r["dept"] not in ("BOS", "MYR")]
    only_orig = [r for r in cgjk if r["status_basis"] == "cgj_response"]
    R["F2_cgj"] = {
        "claim": "CGJ 43% implemented; 'will not be implemented' outnumbers 'implemented'",
        "n_known": len(cgjk), "status": dict(st), "rate": share(st["implemented"], len(cgjk)),
        "will_not_minus_implemented": st["not_implementing"] - st["implemented"],
        "not_implementing_status_basis": dict(Counter(r["status_basis"] for r in notimpl)),
        "not_implementing_whose_status_is_just_the_original_response": sum(1 for r in notimpl if len(r["history"]) <= 1 or all(h["status"] == "not_implementing" for h in r["history"])),
        "not_implementing_by_dept_top": dict(Counter(r["dept"] for r in notimpl).most_common(8)),
        "distinct_rec_level": {"n": len(g), "any_respondent_implemented": anyimpl, "rate": share(anyimpl, len(g)),
                               "all_respondents_will_not": allnot, "all_will_not_share": share(allnot, len(g))},
        "excluding_BOS_and_MYR_rows": {"n": len(no_bos_myr), "rate": share(nimpl(no_bos_myr), len(no_bos_myr)),
                                       "not_implementing": sum(1 for r in no_bos_myr if r["status"] == "not_implementing"),
                                       "implemented": nimpl(no_bos_myr)},
        "status_only_from_original_response": {"n": len(only_orig), "status": dict(Counter(r["status"] for r in only_orig))},
        "tracker_era_2003_on": None,
    }
    t03 = [r for r in cgjk if r["date_issued"] >= "2003-07-01"]
    R["F2_cgj"]["tracker_era_2003_on"] = {"n": len(t03), "rate": share(nimpl(t03), len(t03)),
                                          "not_implementing": sum(1 for r in t03 if r["status"] == "not_implementing")}

    # ---------------- F3 agreement predicts action (92% vs 6%)
    def agree_tab(rs):
        out = {}
        for a in ("agree", "partial", "disagree"):
            x = [r for r in rs if r["agreed"] == a and r["status"] != "unknown"]
            out[a] = {"n": len(x), "implemented": nimpl(x), "rate": share(nimpl(x), len(x))}
        return out
    pooled = agree_tab(rows)
    by_s = {s: agree_tab(src(s)) for s in ("csa", "cgj")}
    # remove circular CGJ cases: 'has been implemented' responses are implemented by construction,
    # and 'will not be implemented' responses are 'not_implementing' unless a later follow-up changed it.
    cg_nc = [r for r in cgj if r.get("cgj_response") in ("will_be_implemented", "will_not_be_implemented", "requires_further_analysis")
             and r["status"] != "unknown" and any(h["basis"] == "cgj_status_tracker" for h in r["history"])]
    nc = {}
    for resp in ("will_be_implemented", "requires_further_analysis", "will_not_be_implemented"):
        x = [r for r in cg_nc if r["cgj_response"] == resp]
        nc[resp] = {"n": len(x), "implemented": nimpl(x), "rate": share(nimpl(x), len(x))}
    has_been = [r for r in cgjk if r.get("cgj_response") == "has_been_implemented"]
    R["F3_agreement"] = {
        "claim": "92% of agreed vs 6% of disagreed recommendations implemented (pooled CSA+CGJ, known status)",
        "pooled": pooled, "by_source": by_s,
        "cgj_has_been_implemented_rows_in_agree": {"n": len(has_been), "implemented": nimpl(has_been)},
        "share_of_pooled_agree_implemented_that_are_cgj_has_been_implemented": share(nimpl(has_been), pooled["agree"]["implemented"]),
        "cgj_noncircular_by_response_with_tracker_followup": nc,
        "agree_rows_by_source_share": {s: share(sum(1 for r in src(s) if r["agreed"] == "agree" and r["status"] != "unknown"), pooled["agree"]["n"]) for s in ("csa", "cgj")},
        "disagree_rows_by_source_share": {s: share(sum(1 for r in src(s) if r["agreed"] == "disagree" and r["status"] != "unknown"), pooled["disagree"]["n"]) for s in ("csa", "cgj")},
    }

    # ---------------- F4 Board of Supervisors disagrees 57%
    bos = [r for r in rows if r["dept"] == "BOS" and r["agreed"] != "none"]
    bc = Counter(r["agreed"] for r in bos)
    bos_d = [r for r in bos if r["agreed"] == "disagree"]
    addressed = lambda r: bool(re.search(r"board of supervisors|\bBOS\b|supervisors should|the board should|legislat|ordinance", r["text"], re.I))
    R["F4_bos"] = {
        "claim": "Board of Supervisors disagreed 57% of the time",
        "n_responses": len(bos), "agreed": dict(bc), "disagree_share": share(bc["disagree"], len(bos)),
        "by_source": dict(Counter(r["source"] for r in bos)),
        "disagree_rows_text_names_board_or_legislation": sum(1 for r in bos_d if addressed(r)),
        "disagree_rows_text_does_not_name_board": sum(1 for r in bos_d if not addressed(r)),
        "disagree_share_when_text_names_board": share(sum(1 for r in bos if r["agreed"] == "disagree" and addressed(r)), sum(1 for r in bos if addressed(r))),
        "disagree_share_when_text_does_not_name_board": share(sum(1 for r in bos if r["agreed"] == "disagree" and not addressed(r)), sum(1 for r in bos if not addressed(r))),
        "by_era": {e: {"n": len(x), "disagree_share": share(sum(1 for r in x if r["agreed"] == "disagree"), len(x))}
                   for e, x in (("before_2014", [r for r in bos if r["date_issued"] < "2014"]), ("2014_on", [r for r in bos if r["date_issued"] >= "2014"]))},
        "n_distinct_reports": len({r["report"] for r in bos}),
        "top_reports_by_disagree": Counter(r["report"] for r in bos_d).most_common(8),
    }
    # all depts with >=15 responses for the fairness table
    dd = defaultdict(Counter)
    for r in rows:
        if r["agreed"] != "none":
            dd[r["dept"]][r["agreed"]] += 1
    R["disagree_by_dept_min15"] = sorted([{"dept": d, "n": sum(c.values()), "disagree": c["disagree"], "share": share(c["disagree"], sum(c.values())),
                                           "cgj_share_of_responses": share(sum(1 for r in rows if r["dept"] == d and r["agreed"] != "none" and r["source"] == "cgj"), sum(c.values()))}
                                          for d, c in dd.items() if sum(c.values()) >= 15], key=lambda x: -x["share"])[:15]

    # ---------------- F5 'will be implemented' -> 67% implemented, 18% reversed
    wb = [r for r in cgj if r.get("cgj_response") == "will_be_implemented"]
    later = [r for r in wb if any(h["basis"] == "cgj_status_tracker" and h.get("date") for h in r["history"])]
    fs = Counter(r["status"] for r in later)
    rev = [r for r in later if r["status"] == "not_implementing"]
    R["F5_will_be_implemented"] = {
        "claim": "'will be implemented' -> 67% implemented, 18% reversed to will-not",
        "n": len(wb), "n_with_tracker_entry": len(later), "final_status": dict(fs),
        "implemented_rate": share(fs["implemented"], len(later)), "reversed_rate": share(fs["not_implementing"], len(later)),
        "reversed_by_dept": dict(Counter(r["dept"] for r in rev).most_common(10)),
        "reversed_with_then_starstar": sum(1 for r in rev if "[then **]" in (r.get("status_raw") or "")),
        "reversed_ids": [r["id"] for r in rev],
        "excluding_BOS": {"n": sum(1 for r in later if r["dept"] != "BOS"),
                          "implemented_rate": share(sum(1 for r in later if r["dept"] != "BOS" and r["status"] == "implemented"), sum(1 for r in later if r["dept"] != "BOS")),
                          "reversed_rate": share(sum(1 for r in later if r["dept"] != "BOS" and r["status"] == "not_implementing"), sum(1 for r in later if r["dept"] != "BOS"))},
    }

    # ---------------- F6 open over 2 / 5 years
    def age(r):
        return (as_of - date.fromisoformat(r["date_issued"])).days / 365.25
    op = [r for r in rows if r["status"] in ("open", "in_progress")]
    o2 = [r for r in op if age(r) > 2]
    o5 = [r for r in op if age(r) > 5]
    stale = lambda r: r.get("last_followup") and (as_of - date.fromisoformat(r["last_followup"])).days > 730
    R["F6_open"] = {
        "claim": "223 open or in progress more than 2 years, 175 more than 5 years (latest recorded status)",
        "open_or_in_progress": len(op), "over_2y": len(o2), "over_5y": len(o5),
        "over_2y_by_source": dict(Counter(r["source"] for r in o2)), "over_5y_by_source": dict(Counter(r["source"] for r in o5)),
        "over_2y_last_followup_more_than_2y_ago": sum(1 for r in o2 if stale(r)),
        "over_2y_median_last_followup_year": sorted((r.get("last_followup") or "")[:4] for r in o2)[len(o2) // 2] if o2 else None,
        "over_2y_by_dept": dict(Counter(r["dept"] for r in o2).most_common(10)),
        "over_2y_status": dict(Counter(r["status"] for r in o2)),
        "csa_over_2y_reports": dict(Counter(r["report"] for r in o2 if r["source"] == "csa").most_common(10)),
        "alt_definition_calendar_2y_by_dateissued_lt_2024_09_26": sum(1 for r in op if r["date_issued"] < "2024-09-26"),
    }

    # ---------------- F7 repeats
    rp = [r for r in rows if r.get("repeat_of")]
    clusters = json.load(open(os.path.join(SITE, "repeats", "clusters.json")))
    used = [c for c in clusters["clusters"] if c.get("used_for_repeat_of")]
    ids_by = {r["id"]: r for r in rows}
    # every repeat_of target must be earlier, same dept
    bad = [r["id"] for r in rp if r["repeat_of"] not in ids_by or ids_by[r["repeat_of"]]["dept"] != r["dept"] or ids_by[r["repeat_of"]]["date_issued"] > r["date_issued"]]
    clus_of_repeats = {r.get("repeat_cluster") for r in rp}
    R["F7_repeats"] = {
        "claim": "1,137 repeats in 434 clusters",
        "repeat_rows": len(rp), "share": share(len(rp), len(rows)),
        "distinct_clusters_among_repeat_rows": len(clus_of_repeats - {None}),
        "clusters_in_file": len(clusters["clusters"]), "clusters_used_for_repeat_of": len(used),
        "bad_links": bad[:20], "n_bad": len(bad),
        "by_source": dict(Counter(r["source"] for r in rp)),
        "cross_source_repeats": sum(1 for r in rp if ids_by.get(r["repeat_of"], {}).get("source") != r["source"]),
        "predecessor_status": dict(Counter(ids_by[r["repeat_of"]]["status"] for r in rp if r["repeat_of"] in ids_by)),
        "confidence_lt_0_8": sum(1 for r in rp if (r.get("repeat_confidence") or 0) < 0.8),
        "validation": clusters.get("validation"),
    }

    # ---------------- evidence: self-reported vs verified
    imp = [r for r in rows if r["status"] == "implemented"]
    eb = Counter(r["status_basis"] for r in imp)
    R["evidence"] = {"implemented": len(imp), "by_basis": dict(eb),
                     "auditor_verified_share": share(eb["csa_field_followup"] + eb["pi_status_update"], len(imp))}

    # ---------------- CSA vs CGJ framing: what kind of asks
    topic_mix = {s: dict(Counter(r["topic"] for r in src(s)).most_common(6)) for s in ("csa", "cgj")}
    R["framing_csa_vs_cgj"] = {
        "topic_mix_top6": topic_mix,
        "cgj_rows_to_BOS_or_MYR_share": share(sum(1 for r in cgj if r["dept"] in ("BOS", "MYR")), len(cgj)),
        "csa_rows_to_BOS_or_MYR_share": share(sum(1 for r in csa if r["dept"] in ("BOS", "MYR")), len(csa)),
        "same_topic_compare": {t: {s: {"n": len(known([r for r in src(s) if r["topic"] == t])),
                                        "rate": share(nimpl(known([r for r in src(s) if r["topic"] == t])), len(known([r for r in src(s) if r["topic"] == t])))}
                                    for s in ("csa", "cgj")} for t in ("finance", "contracts", "it", "hr", "governance", "safety", "performance")},
    }
    json.dump(R, open(os.path.join(OUT, "rederive.json"), "w"), indent=1, default=str)
    print(json.dumps(R, indent=1, default=str)[:12000])


if __name__ == "__main__":
    main()
