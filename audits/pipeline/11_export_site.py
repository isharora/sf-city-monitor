"""Step 11: prepare final rows and export dashboard data per design/DATA_CONTRACT_audits.md.

  python3 11_export_site.py prepare   # rows_final.json / reports_final.json (dollars, repeats, consequence)
  python3 11_export_site.py export    # data/site/* (+ QA report data/site/_qa.json)
  python3 11_export_site.py headcheck # HEAD every report URL (contract QA 5), polite
"""
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, RAW, SITE, session, polite_wait  # noqa
from maps import (DEPT_INFO, TOPIC_LABELS, STATUS_LABELS, STATUS_MAPPING, CONSEQUENCE_RULE,  # noqa
                  consequence)

WORK = os.path.join(DATA, "work")
AS_OF = date(2026, 9, 26)
SRC = {"controller": "csa", "bla": "bla", "cgj": "cgj"}


def clean_title(t):
    t = re.sub(r"\s*-\s*Full [Rr]eport This report details.*$", "", t)
    t = re.sub(r"\s*This report details the Jury.*$", "", t)
    return t.strip()


def prepare():
    rows = json.load(open(os.path.join(WORK, "rows.json")))
    reps = {r["doc_id"]: r for r in json.load(open(os.path.join(WORK, "reports.json")))}
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
    dollars = json.load(open(os.path.join(WORK, "dollars.json"))) if os.path.exists(os.path.join(WORK, "dollars.json")) else {}
    dver = json.load(open(os.path.join(WORK, "dollar_findings_verified_by_report.json")))
    rep_of = json.load(open(os.path.join(WORK, "repeat_of.json"))) if os.path.exists(os.path.join(WORK, "repeat_of.json")) else {}
    rdates = json.load(open(os.path.join(WORK, "report_dates.json")))
    dol_rec = {}
    for v in dollars.values():
        dol_rec.update(v["recs"])
    for r in rows:
        d = dol_rec.get(r["rec_uid"])
        r["dollars_at_stake"] = d["dollars"] if d else None
        r["dollars_kind"] = d["kind"] if d else None
        r["dollars_page"] = d["page"] if d else None
        ro = rep_of.get(r["id"])
        r["repeat_of"] = ro["repeat_of"] if ro else None
        r["repeat_confidence"] = ro["confidence"] if ro else None
        r["repeat_cluster"] = ro["cluster_id"] if ro else None
        r["repeat_theme"] = ro["theme"] if ro else None
        sc, parts = consequence(r, AS_OF)
        why = None
        if sc >= 7 or r["repeat_of"]:
            why = "; ".join(parts).capitalize() + "." if parts else None
        r["consequence"] = {"score": sc, "why": why}
    # reports with at least one row
    by_rep = defaultdict(list)
    for r in rows:
        by_rep[r["report"]].append(r)
    out_reps = []
    for did, rs in by_rep.items():
        d = inv[did]
        rp = reps.get(did, {})
        ev_dates = sorted({e["date"] for r in rs for e in r.get("events", []) if e.get("date")})
        topic = Counter(r["topic"] for r in rs).most_common(1)[0][0]
        depts = list(dict.fromkeys([r["dept"] for r in rs]))
        out_reps.append({
            "id": did, "source": SRC[d["source"]], "title": clean_title(d["title"]), "date": rdates.get(did, [None])[0],
            "date_basis": rdates.get(did, [None, None])[1], "depts": depts, "topic": topic, "url": d["url"],
            "listing_url": d["listing_url"], "pages": dl.get(did, {}).get("n_pages"), "n_recs": len(rs),
            "n_recommendations_distinct": len({r["rec_uid"] for r in rs}),
            "stated_rec_count": rp.get("stated_rec_count"), "summary": rp.get("summary"),
            "followups": ev_dates, "openbook_id": str(d["extra"].get("openbook_id")) if d["extra"].get("openbook_id") else None,
            "cgj_term": d["extra"].get("cgj_term"), "doc_type": d["doc_type"], "report_kind": rp.get("report_kind"),
            "scanned": dl.get(did, {}).get("status") == "ok_low_text" or bool(dl.get(did, {}).get("partial_scan")),
            "dollar_findings": dver.get(did, []),
            "dollar_independent": dollars.get(did, {}).get("independent"),
        })
    json.dump(rows, open(os.path.join(WORK, "rows_final.json"), "w"), indent=0)
    json.dump(out_reps, open(os.path.join(WORK, "reports_final.json"), "w"), indent=0)
    print("rows", len(rows), "reports", len(out_reps), "repeats", sum(1 for r in rows if r["repeat_of"]),
          "with dollars", sum(1 for r in rows if r["dollars_at_stake"]))


def w(path, obj):
    p = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    return os.path.getsize(p)


REC_FIELDS = ["id", "report", "source", "dept", "date_issued", "topic", "priority", "text", "text_full", "agreed",
              "response_text", "status", "status_date", "months_to_close", "last_followup", "repeat_of",
              "repeat_confidence", "dollars_at_stake", "consequence",
              # extensions (documented in CONTRACT_GAPS.md / DATA_NOTES.md)
              "rec_number", "page", "page_check", "response_page", "finding", "category", "secondary_topic",
              "priority_raw", "response_raw", "cgj_response", "target_date", "status_raw", "status_basis",
              "status_doc", "status_page", "status_date_precision", "months_to_close_upper", "implemented_date",
              "date_basis", "depts_all", "dollars_kind", "dollars_page", "repeat_theme", "repeat_cluster", "conf",
              "in_csa_followup_scope", "history"]


def export():
    rows = json.load(open(os.path.join(WORK, "rows_final.json")))
    reports = json.load(open(os.path.join(WORK, "reports_final.json")))
    inv = json.load(open(os.path.join(RAW, "inventory.json")))
    recs_src = {r["rec_uid"]: r for r in json.load(open(os.path.join(WORK, "recommendations.json")))}
    for f in os.listdir(SITE) if os.path.isdir(SITE) else []:
        pass
    files = {}
    # rows -> contract shape
    out_rows = []
    for r in rows:
        r = dict(r)
        r["page_check"] = recs_src.get(r["rec_uid"], {}).get("page_check")
        r["history"] = [{"date": e["date"], "status": e["status"], "raw": e.get("raw"), "doc": e.get("doc"),
                         "page": e.get("page"), "basis": e["basis"]} for e in r.get("events", [])]
        out_rows.append({k: r.get(k) for k in REC_FIELDS})
    by_year = defaultdict(list)
    for r in out_rows:
        by_year[(r["date_issued"] or "0000")[:4]].append(r)
    for y, rs in sorted(by_year.items()):
        files[f"recs/recs_{y}.json"] = w(f"recs/recs_{y}.json", {
            "sample": False, "as_of": AS_OF.isoformat(), "sources": ["csa-reports", "bla-reports", "cgj-reports", "cgj-status"],
            "note": f"One row per recommendation issued in {y} (Civil Grand Jury: one row per recommendation x responding department).",
            "rows": rs})
    rep_out = [{k: rp.get(k) for k in ("id", "source", "title", "date", "depts", "topic", "url", "pages", "n_recs", "summary",
                                         "followups", "openbook_id", "n_recommendations_distinct", "stated_rec_count",
                                         "listing_url", "date_basis", "cgj_term", "doc_type", "report_kind", "scanned",
                                         "dollar_findings", "dollar_independent")} for rp in reports]
    files["reports/reports.json"] = w("reports/reports.json", {"sample": False, "as_of": AS_OF.isoformat(),
                                                               "sources": ["csa-reports", "bla-reports", "cgj-reports"], "reports": rep_out})
    # extras
    A = json.load(open(os.path.join(DATA, "analysis", "analysis.json")))
    prof = defaultdict(lambda: {"n": 0, "status": Counter(), "agreed": Counter(), "by_source": Counter(), "topics": Counter(),
                                "months": [], "repeats": 0, "open_over_2y": 0, "open_over_5y": 0, "reports": set()})
    for r in rows:
        p = prof[r["dept"]]
        p["n"] += 1
        p["status"][r["status"]] += 1
        p["agreed"][r["agreed"]] += 1
        p["by_source"][r["source"]] += 1
        p["topics"][r["topic"]] += 1
        p["reports"].add(r["report"])
        if r.get("months_to_close") is not None:
            p["months"].append(r["months_to_close"])
        if r.get("repeat_of"):
            p["repeats"] += 1
        if r["status"] in ("open", "in_progress") and r.get("date_issued"):
            age = (AS_OF - date.fromisoformat(r["date_issued"])).days / 365.25
            p["open_over_2y"] += age > 2
            p["open_over_5y"] += age > 5
    profiles = []
    for d, p in sorted(prof.items(), key=lambda x: -x[1]["n"]):
        m = sorted(p["months"])
        known = p["n"] - p["status"]["unknown"]
        top_open = sorted([r for r in rows if r["dept"] == d and r["status"] in ("open", "in_progress", "unknown", "not_implementing")],
                          key=lambda r: (-r["consequence"]["score"], r["date_issued"] or ""))[:10]
        profiles.append({"dept": d, "name": DEPT_INFO.get(d, (d,))[0], "recommendations": p["n"], "reports": len(p["reports"]),
                         "by_source": dict(p["by_source"]), "status": dict(p["status"]), "agreed": dict(p["agreed"]),
                         "impl_share_known": round(p["status"]["implemented"] / known, 3) if known >= 5 else None,
                         "median_months_to_close": m[len(m) // 2] if len(m) >= 5 else None, "n_timed": len(m),
                         "repeats": p["repeats"], "open_over_2y": p["open_over_2y"], "open_over_5y": p["open_over_5y"],
                         "top_topics": dict(p["topics"].most_common(5)), "top_open_by_consequence": [r["id"] for r in top_open],
                         "small_n": p["n"] < 5})
    files["depts/profiles.json"] = w("depts/profiles.json", {"sample": False, "as_of": AS_OF.isoformat(), "profiles": profiles})
    agg_keys = ["corpus", "corpus_by_year", "reports_with_recs_by_source", "reports_with_recs_by_source_year", "rows_by_source",
                "rows_by_source_year", "status_by_source", "status_basis_by_source", "agreed_by_source", "rates_by_source",
                "rates_by_topic", "time_to_implement", "time_by_topic", "open_recorded", "disagreement_by_dept_top",
                "disagreement_by_source", "agreed_vs_status", "cgj_will_implement", "cgj_response_mix",
                "dollars_by_source_kind", "dollars_by_source_year", "dollars_top_reports", "repeats", "consequence_hist_open",
                "sensitivity", "redteam"]
    files["aggregates/summary.json"] = w("aggregates/summary.json", {"sample": False, "as_of": AS_OF.isoformat(),
                                                                     **{k: A.get(k) for k in agg_keys}})
    clusters = json.load(open(os.path.join(WORK, "repeat_clusters.json"))) if os.path.exists(os.path.join(WORK, "repeat_clusters.json")) else []
    rv = json.load(open(os.path.join(DATA, "qc", "repeat_validation.json")))["summary"] if os.path.exists(os.path.join(DATA, "qc", "repeat_validation.json")) else None
    files["repeats/clusters.json"] = w("repeats/clusters.json", {"sample": False, "as_of": AS_OF.isoformat(), "validation": rv,
                                                                 "clusters": clusters})
    # commentary written by 12_commentary.py into data/site/commentary/
    for f in sorted(os.listdir(os.path.join(SITE, "commentary"))) if os.path.isdir(os.path.join(SITE, "commentary")) else []:
        files[f"commentary/{f}"] = os.path.getsize(os.path.join(SITE, "commentary", f))
    # meta
    used_depts = sorted({r["dept"] for r in rows} | {d for rp in reports for d in rp["depts"]})
    years = sorted(int(r["date_issued"][:4]) for r in rows if r.get("date_issued"))
    src_rows = Counter(rp["source"] for rp in reports)
    corpus_n = Counter()
    for d in inv:
        corpus_n[d["source"]] += 1
    head = json.load(open(os.path.join(DATA, "qc", "url_headcheck.json"))) if os.path.exists(os.path.join(DATA, "qc", "url_headcheck.json")) else {}
    meta = {
        "sample": False, "module": "audits", "as_of": AS_OF.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "version": "1.0",
        "years": {"min": years[0], "max": years[-1],
                  "note": "Calendar year the report was issued. Coverage is uneven: CSA follow-up status exists mainly for audits issued from July 2010; Controller CGJ tracking from jury term 2003-04; BLA has no follow-up."},
        "dimensions": {
            "source": {"label": "Who recommended", "kind": "categorical", "values": [
                {"id": "csa", "label": "Controller's City Services Auditor", "short": "CSA", "slot": 1},
                {"id": "bla", "label": "Budget and Legislative Analyst", "short": "BLA", "slot": 2},
                {"id": "cgj", "label": "Civil Grand Jury", "short": "CGJ", "slot": 3}]},
            "dept": {"label": "Department", "values": [{"id": d, "name": DEPT_INFO.get(d, (d, "other", d))[0],
                                                        "group": DEPT_INFO.get(d, (d, "other", d))[1],
                                                        "short": DEPT_INFO.get(d, (d, "other", d))[2]} for d in used_depts]},
            "topic": {"label": "Topic", "values": [{"id": a, "label": l} for a, l in TOPIC_LABELS]},
            "status": {"label": "Implementation status", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in STATUS_LABELS]},
            "agreed": {"label": "Department response", "kind": "polarity", "values": [
                {"id": "agree", "label": "Agreed"}, {"id": "partial", "label": "Partially agreed"},
                {"id": "disagree", "label": "Disagreed"}, {"id": "none", "label": "No response recorded"}]},
            "priority": {"label": "Auditor priority", "values": [{"id": a, "label": a.title()} for a in ("high", "medium", "low")]},
        },
        "status_mapping": STATUS_MAPPING,
        "consequence_rule": CONSEQUENCE_RULE,
        "counts": {"reports": len(reports), "recommendations": len(rows),
                   "recommendations_distinct": len({r["rec_uid"] for r in rows})},
        "small_n": 5,
        "sources": [
            {"id": "csa-reports", "name": "Controller's Office reports (CSA audits, assessments, Public Integrity reviews, City Performance, Whistleblower) and CSA recommendation follow-up reports",
             "publisher": "SF Controller, City Services Auditor", "rows": corpus_n["controller"], "rows_used": src_rows["csa"],
             "as_of": "2026-09-16", "url": "https://openbook.sfgov.org/webreports/search.aspx",
             "note": "rows = Controller documents inventoried (incl. follow-ups and reports without recommendations); rows_used = reports with at least one extracted recommendation. Extracted 2026-09-26 with Claude Sonnet 5; follow-up status from semiannual follow-up and 'not implemented after two years' reports."},
            {"id": "bla-reports", "name": "Budget and Legislative Analyst performance and management audits",
             "publisher": "SF Board of Supervisors, Budget and Legislative Analyst", "rows": corpus_n["bla"], "rows_used": src_rows["bla"],
             "as_of": "2026-08-03", "url": "https://sfbos.archive.sf.gov/budget-legislative-analyst-reports",
             "note": "rows = all BLA documents listed 2010-2026; only performance/management audits are extracted. BLA publishes no recommendation follow-up, so status is unknown."},
            {"id": "cgj-reports", "name": "Civil Grand Jury reports and required responses (Penal Code 933.05)",
             "publisher": "San Francisco Civil Grand Jury", "rows": sum(1 for d in inv if d["source"] == "cgj"), "rows_used": src_rows["cgj"],
             "as_of": "2026-09-14", "url": "https://civilgrandjury.archive.sf.gov/previousreport.html",
             "note": "Reports 1995-96 to 2025-26 and responses where posted (mostly from 2014-15). rows counts reports, responses, press releases and appendices."},
            {"id": "cgj-status", "name": "Controller's tracking of Civil Grand Jury recommendation status (Admin. Code 2.10)",
             "publisher": "SF Controller", "rows": sum(1 for d in inv if d["source"] == "cgj_status"),
             "rows_used": sum(1 for d in inv if d["source"] == "cgj_status" and d["doc_type"] == "cgj_status_tracker"),
             "as_of": "2025-12-23", "url": "https://www.sf.gov/information--status-civil-grand-jury-recommendations/",
             "note": "Status self-reported by departments, copied verbatim by the Controller; covers jury terms 2003-04 to 2024-25."},
        ],
        "url_check": {"checked": head.get("checked"), "ok": head.get("ok"), "failed": head.get("failed_ids", [])[:50], "when": head.get("when")},
        "files": {},
    }
    meta["files"] = {k: v for k, v in sorted(files.items())}
    meta["files"]["meta.json"] = None
    w("meta.json", meta)
    meta["files"]["meta.json"] = os.path.getsize(os.path.join(SITE, "meta.json"))
    w("meta.json", meta)
    qa(out_rows, rep_out, meta)


def qa(rows, reports, meta):
    dims = meta["dimensions"]
    ids = {k: {v["id"] for v in dims[k]["values"]} for k in dims}
    rep_ids = {r["id"] for r in reports}
    res = {}
    cnt = Counter(r["report"] for r in rows)
    res["1_report_ids_exist"] = all(r["report"] in rep_ids for r in rows)
    res["1_n_recs_match"] = all(cnt[rp["id"]] == rp["n_recs"] for rp in reports)
    bad = [r["id"] for r in rows if r["source"] not in ids["source"] or r["dept"] not in ids["dept"] or r["topic"] not in ids["topic"]
           or r["status"] not in ids["status"] or r["agreed"] not in ids["agreed"] or (r["priority"] is not None and r["priority"] not in ids["priority"])]
    res["2_dimension_ids_ok"] = not bad
    res["2_bad_rows"] = bad[:20]
    v3 = [r["id"] for r in rows if (r["months_to_close"] is not None) != (r["status"] == "implemented")]
    res["3_months_iff_implemented_violations"] = len(v3)
    res["3_violations_explained_by_inferred_or_undated_implemented"] = sum(1 for r in rows if r["id"] in set(v3) and r["status"] == "implemented" and r["months_to_close"] is None)
    res["3_status_date_before_issue"] = sum(1 for r in rows if r["status_date"] and r["date_issued"] and r["status_date"] < r["date_issued"])
    byid = {r["id"]: r for r in rows}
    rep_bad = [r["id"] for r in rows if r["repeat_of"] and (r["repeat_of"] not in byid or byid[r["repeat_of"]]["date_issued"] >= r["date_issued"]
                                                           or byid[r["repeat_of"]]["dept"] != r["dept"])]
    res["4_repeat_of_valid"] = not rep_bad
    res["4_bad"] = rep_bad[:20]
    res["5_url_check"] = meta.get("url_check")
    from maps import consequence as cf
    res["6_consequence_recomputes"] = all(cf(r, AS_OF)[0] == r["consequence"]["score"] for r in rows)
    res["6b_why_present_when_required"] = all(r["consequence"]["why"] for r in rows if r["consequence"]["score"] >= 7 or r["repeat_of"])
    res["text_len_ok"] = all(len(r["text"] or "") <= 400 for r in rows)
    json.dump(res, open(os.path.join(SITE, "_qa.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


def headcheck():
    reports = json.load(open(os.path.join(WORK, "reports_final.json")))
    s = session()
    ok, failed = 0, []
    for rp in reports:
        u = rp["url"]
        polite_wait(u)
        code = None
        try:
            r = s.head(u, allow_redirects=True, timeout=60)
            code = r.status_code
            if code in (403, 405, 400):
                polite_wait(u)
                r = s.get(u, stream=True, timeout=60)
                code = r.status_code
                r.close()
        except Exception as e:
            code = repr(e)[:80]
        if code == 200:
            ok += 1
        else:
            failed.append({"id": rp["id"], "url": u, "code": code})
    out = {"checked": len(reports), "ok": ok, "failed_ids": [f["id"] for f in failed], "failed": failed,
           "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    os.makedirs(os.path.join(DATA, "qc"), exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "qc", "url_headcheck.json"), "w"), indent=1)
    print(ok, "of", len(reports), "OK; failed", len(failed))


if __name__ == "__main__":
    {"prepare": prepare, "export": export, "headcheck": headcheck}[sys.argv[1]]()
