"""Step 7: build the final recommendation rows with resolved status history.

Evidence used per source
  CSA: rec-level status items (field follow-ups, public-integrity updates, 'not implemented
       after two years' lists, older follow-up summaries); report-level 'report closed' rows
       (all recommendations in the report resolved as of the follow-up period end);
       absence inference: a recommendation issued >= 2 years before the as-of date of a
       'not implemented after two years' list, whose report is not mentioned in that list,
       was closed by that date (upper bound only).
  CGJ: department responses (Penal Code 933.05) and Controller tracking documents,
       one row per recommendation x responding department.
  BLA: responses in the report only; BLA publishes no follow-up -> status unknown.
Writes data/work/rows.json and data/work/report_dates.json
"""
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, DATA  # noqa
from maps import DEPT_CODE, TOPIC, AGREED, CGJ_AGREED, STATUS  # noqa

WORK = os.path.join(DATA, "work")
AS_OF = date(2026, 9, 26)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def pdate(s, default_day=None):
    """Parse many date formats -> (date, precision) or (None, None)."""
    if not s:
        return None, None
    s = str(s).strip()
    for fmt, prec in (("%Y-%m-%d", "day"), ("%m/%d/%y", "day"), ("%m/%d/%Y", "day"), ("%B %d, %Y", "day"),
                      ("%b %d, %Y", "day"), ("%B %Y", "month"), ("%b %Y", "month"), ("%Y-%m", "month")):
        try:
            d = datetime.strptime(s, fmt).date()
            if prec == "month":
                d = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            return d, prec
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), "day"
        except ValueError:
            pass
    m = re.search(rf"({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})", s)
    if m:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date(), "day"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        try:
            return date(y, int(m.group(1)), int(m.group(2))), "day"
        except ValueError:
            pass
    m = re.fullmatch(r"(19|20)\d{2}", s)
    if m:
        return date(int(s), 12, 31), "year"
    m = re.search(r"\b(19|20)\d{2}\b", s)
    if m:
        return date(int(m.group(0)), 12, 31), "year"
    return None, None


def nrec(r):
    if not r:
        return None
    r = str(r).lower()
    r = re.sub(r"\[.*?\]|\(for .*?\)|for f\d+.*$", "", r)
    r = re.sub(r"recommendation|rec\.?|no\.|number|#", "", r).strip().strip(".").strip()
    r = re.sub(r"^r\.?\s*", "", r)
    return re.sub(r"\s+", "", r) or None


def sid(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def priority_bucket(p):
    if not p:
        return None
    t = p.lower()
    if re.search(r"high|critical|significant|major|priority 1|\b1\b", t):
        return "high"
    if re.search(r"medium|moderate|priority 2|\b2\b", t):
        return "medium"
    if re.search(r"low|minor|priority 3|\b3\b", t):
        return "low"
    return None


def months_between(a, b):
    return round((b - a).days / 30.4375, 1)


def main():
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    recs = json.load(open(os.path.join(WORK, "recommendations.json")))
    reports = {r["doc_id"]: r for r in json.load(open(os.path.join(WORK, "reports.json")))}
    items = {x["status_uid"]: x for x in json.load(open(os.path.join(WORK, "status_items.json")))
             if x["status_doc_type"] != "cgj_status_legacy"}
    rls = {x["rl_uid"]: x for x in json.load(open(os.path.join(WORK, "report_level.json")))}
    lrep = json.load(open(os.path.join(WORK, "links_report.json")))
    lrec = json.load(open(os.path.join(WORK, "links_rec.json")))
    dmap = json.load(open(os.path.join(WORK, "dept_map.json")))

    ov = json.load(open(os.path.join(os.path.dirname(__file__), "dept_overrides.json")))

    def code(raw):
        if not raw:
            return None
        c = ov.get(raw) or dmap.get(raw, {}).get("canonical")
        c = re.sub(r"\s*\(.*$", "", c).strip() if c else None
        return DEPT_CODE.get(c, "UNK") if c else None

    # ---------- report dates
    tracker_dates = defaultdict(list)
    for uid, it in items.items():
        did = lrep.get(uid, {}).get("doc_id")
        if did and it.get("source_report_date"):
            d, p = pdate(it["source_report_date"])
            if d and p == "day":
                tracker_dates[did].append(d)
    rep_date = {}
    for did, d in inv.items():
        dt, basis = None, None
        if d.get("date"):
            dt, basis = pdate(d["date"])[0], "listing"
        if not dt and did in reports and reports[did].get("date"):
            dt, prec = pdate(reports[did]["date"])
            basis = "report_text" if dt else None
            if prec == "year":
                dt, basis = None, None
        if not dt and tracker_dates.get(did):
            dt, basis = sorted(tracker_dates[did])[len(tracker_dates[did]) // 2], "cited_in_followup"
        if not dt and d["extra"].get("cgj_term"):
            dt, basis = date(int(d["extra"]["cgj_term"][5:9]), 6, 30), "term_end_estimate"
        rep_date[did] = (dt.isoformat() if dt else None, basis)
    json.dump(rep_date, open(os.path.join(WORK, "report_dates.json"), "w"), indent=0)

    def clamp(d, p, doc_id):
        """Year-only dates are set to Dec 31; never let them run past the status document's
        own date (or the as-of date)."""
        if d and p == "year":
            dd = pdate(inv.get(doc_id, {}).get("date"))[0] or AS_OF
            return min(d, dd, AS_OF)
        return min(d, AS_OF) if d else d

    def response_date(it):
        """Date of a CGJ response document (from its listing title), else None."""
        t = it.get("status_doc_title") or ""
        d, p = pdate(t)
        if d and p == "day":
            return d
        m = re.search(r"_(\d{2})(\d{2})(\d{2})(?:_|\.pdf|[a-z_]*\.pdf)", inv[it["status_doc_id"]]["url"] or "")
        if m:
            try:
                return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None
        return None

    # ---------- events per rec_uid / per (rec_uid, dept) for CGJ
    ev_rec = defaultdict(list)          # rec_uid -> events (csa)
    cgj_groups = defaultdict(list)      # (rec_uid or synthetic key, dept code) -> items
    orphan_meta = {}
    for uid, it in items.items():
        lr = lrec.get(uid, {})
        did = lrep.get(uid, {}).get("doc_id")
        t = it["status_doc_type"]
        is_cgj = t in ("cgj_response", "cgj_status_tracker", "cgj_status_legacy")
        if is_cgj:
            if not did or inv.get(did, {}).get("doc_type") != "cgj_report":
                continue
            dc = code(it.get("department")) or code(it.get("respondent")) or "UNK"
            key = lr.get("rec_uid") or f"ITEM:{did}:{nrec(it.get('rec_id')) or sid(it.get('rec_text'))}"
            if not lr.get("rec_uid"):
                orphan_meta.setdefault(key, (did, it))
            cgj_groups[(key, dc)].append(it)
            for extra in lr.get("also_rec_uids", []):
                cgj_groups[(extra, dc)].append(it)
        else:
            if not lr.get("rec_uid"):
                continue
            d, p = pdate(it.get("status_date"))
            if not d:
                d, p = pdate(it.get("as_of_date")) if it.get("as_of_date") else pdate(it.get("status_doc_date"))
            if not d:
                d, p = pdate(it.get("status_doc_date"))
            d = clamp(d, p, it["status_doc_id"])
            ev = {"date": d.isoformat() if d else None, "precision": p, "status": STATUS.get(it["status"], "unknown"),
                  "raw": it.get("status_raw"), "doc": it["status_doc_id"], "page": it.get("page"),
                  "basis": t, "explanation": it.get("explanation"), "status_uid": uid}
            for ru in [lr["rec_uid"]] + lr.get("also_rec_uids", []):
                ev_rec[ru].append(ev)

    # report-level closure events (CSA)
    closed_rep = defaultdict(list)
    mentioned_in = defaultdict(set)     # status doc id -> report doc ids mentioned (items or rl)
    for uid, rl in rls.items():
        did = lrep.get(uid, {}).get("doc_id")
        if not did:
            continue
        mentioned_in[rl["status_doc_id"]].add(did)
        if rl["event"] == "report_closed":
            d, p = pdate(rl.get("as_of_date")) if rl.get("as_of_date") else (None, None)
            if not d:
                d, p = pdate(rl.get("status_doc_date"))
            closed_rep[did].append({"date": d.isoformat() if d else None, "precision": p, "status": "implemented",
                                    "raw": "Report closed by CSA follow-up (all recommendations resolved)",
                                    "doc": rl["status_doc_id"], "page": rl.get("page"), "basis": "csa_report_closed"})
    for uid, it in items.items():
        did = lrep.get(uid, {}).get("doc_id")
        if did:
            mentioned_in[it["status_doc_id"]].add(did)
    # recommendation-level detail in 'open > 2 years' lists: which recs of a report are listed
    listed = defaultdict(set)          # (status doc, report) -> rec_uids listed as open
    for uid, it in items.items():
        if it["status_doc_type"] == "csa_open_over_2yrs":
            lr_ = lrec.get(uid, {})
            did_ = lrep.get(uid, {}).get("doc_id")
            if did_ and lr_.get("rec_uid"):
                listed[(it["status_doc_id"], did_)].add(lr_["rec_uid"])
                for x in lr_.get("also_rec_uids", []):
                    listed[(it["status_doc_id"], did_)].add(x)
    over2 = []
    for did, d in inv.items():
        if d["doc_type"] == "csa_open_over_2yrs":
            asof = None
            m = re.search(r"as of (June 30|December 31),? (\d{4})|on June 30,? (\d{4})", d["title"])
            if m:
                y = int(m.group(2) or m.group(3))
                asof = date(y, 6, 30) if (m.group(1) or "June 30").startswith("June") else date(y, 12, 31)
            if asof:
                over2.append((asof, did))
    over2.sort()
    json.dump([(a.isoformat(), b) for a, b in over2], open(os.path.join(WORK, "over2_docs.json"), "w"))

    rows = []
    recs_by_doc = defaultdict(list)
    for r in recs:
        recs_by_doc[r["doc_id"]].append(r)

    def base_row(r, dept_code, src):
        did = r["doc_id"]
        dt = rep_date.get(did, (None, None))[0]
        topic = TOPIC.get(r.get("category") or "other", "other")
        text = (r.get("text") or "").strip()
        return {
            "id": "K-" + sid(r["rec_uid"], dept_code), "rec_uid": r["rec_uid"], "report": did, "source": src,
            "dept": dept_code, "date_issued": dt, "date_basis": rep_date.get(did, (None, None))[1],
            "topic": topic, "category": r.get("category"), "secondary_topic": TOPIC.get(r.get("secondary_category") or "", None),
            "priority": priority_bucket(r.get("priority")), "priority_raw": r.get("priority"),
            "rec_number": r.get("rec_id"),
            "text": text if len(text) <= 400 else text[:397].rsplit(" ", 1)[0] + "...",
            "text_full": text if len(text) > 400 else None,
            "finding": r.get("finding"), "page": r.get("page"), "response_page": r.get("response_page"),
            "target_date": r.get("target_date_iso") or None, "target_date_raw": r.get("target_date"),
            "conf": {"text": r.get("conf_text"), "department": r.get("conf_department"), "category": r.get("conf_category"),
                     "response": r.get("conf_response"), "target_date": r.get("conf_target_date")},
            "depts_all": r.get("departments_canon") or [],
        }

    def resolve(row, events, extra_note=None):
        """Pick status from events (latest wins; rec-level terminal beats report closure)."""
        evs = [e for e in events if e.get("date") and e.get("status") != "unknown"]
        evs.sort(key=lambda e: (e["date"], 0 if e["basis"] == "csa_report_closed" else 1))
        terminal_rec = [e for e in evs if e["basis"] != "csa_report_closed" and e["status"] in ("implemented", "closed_other", "not_implementing")]
        final = None
        if evs:
            final = evs[-1]
            if final["basis"] == "csa_report_closed" and terminal_rec:
                final = terminal_rec[-1]
        row["events"] = evs
        if final:
            row["status"] = final["status"]
            row["status_date"] = final["date"]
            row["status_raw"] = final.get("raw")
            row["status_basis"] = final["basis"]
            row["status_doc"] = final.get("doc")
            row["status_page"] = final.get("page")
            row["status_date_precision"] = final.get("precision")
        else:
            row.update({"status": "unknown", "status_date": None, "status_raw": None, "status_basis": "none",
                        "status_doc": None, "status_page": None, "status_date_precision": None})
        impl = [e for e in evs if e["status"] == "implemented"]
        row["months_to_close"] = None
        row["months_to_close_upper"] = None
        if row["status"] == "implemented" and impl and row["date_issued"]:
            first = impl[0]["date"]
            d0 = date.fromisoformat(row["date_issued"])
            m = months_between(d0, date.fromisoformat(first))
            row["months_to_close"] = max(0.0, m)
            row["implemented_date"] = first
            row["implemented_basis"] = impl[0]["basis"]
        row["last_followup"] = evs[-1]["date"] if evs else None
        if row.get("status_date") and row.get("date_issued") and row["status_date"] < row["date_issued"]:
            row["status_date_flag"] = "status date precedes issue date (year-only precision or source inconsistency)"

    # ---------- CSA and BLA rows
    for r in recs:
        if r["source"] == "cgj":
            continue
        src = "csa" if r["source"] == "controller" else "bla"
        dc = DEPT_CODE.get(r["dept_primary"], "UNK")
        row = base_row(r, dc, src)
        row["agreed"] = AGREED.get(r.get("response") or "not_stated", "none")
        row["response_raw"] = r.get("response_raw")
        row["response_text"] = r.get("response_raw")
        events = list(ev_rec.get(r["rec_uid"], []))
        if src == "csa":
            events += closed_rep.get(r["doc_id"], [])
        resolve(row, events)
        # absence inference (CSA only): upper bound on closure date
        # Only CSA audit reports are in scope of CSA's follow-up program (follow-up documents
        # never cite City Performance or Whistleblower reports; Public Integrity reviews have
        # their own status updates), so absence inference is limited to audits.
        in_followup_scope = (inv[r["doc_id"]]["doc_type"] in ("csa_audit", "csa_field_followup")
                             and not inv[r["doc_id"]]["title"].lower().startswith("public integrity"))
        row["in_csa_followup_scope"] = in_followup_scope if src == "csa" else None
        stale_open = row["status"] in ("open", "in_progress") and row.get("status_date")
        if src == "csa" and in_followup_scope and row["date_issued"] and (row["status"] == "unknown" or stale_open):
            d0 = date.fromisoformat(row["date_issued"])
            after = date.fromisoformat(row["status_date"]) if stale_open else date.min
            if d0 >= date(2010, 7, 1):
                for asof, odid in over2:
                    if d0 <= asof - timedelta(days=730) and asof >= date(2014, 6, 30) and asof > after:
                        if r["doc_id"] in mentioned_in.get(odid, set()):
                            lst = listed.get((odid, r["doc_id"]))
                            if not lst or r["rec_uid"] in lst:
                                continue  # report (or this rec) still listed as open -> check later lists
                        row["status"] = "implemented"
                        row["status_basis"] = "inferred_absent_from_open_over_2yrs_list"
                        row["status_date"] = asof.isoformat()
                        row["status_doc"] = odid
                        row["status_raw"] = ("Not listed among CSA recommendations open more than two years"
                                             + (" (earlier follow-up had recorded it as open)" if stale_open else ""))
                        row["status_date_precision"] = "upper_bound"
                        row["months_to_close"] = None
                        row["months_to_close_upper"] = months_between(d0, asof)
                        row["implemented_date"] = None
                        row["implemented_basis"] = "inferred_absence"
                        break
        rows.append(row)

    # ---------- CGJ rows
    covered = set()
    for (key, dc), its in cgj_groups.items():
        if key.startswith("ITEM:"):
            did, it0 = orphan_meta[key]
            pseudo = {"rec_uid": key, "doc_id": did, "rec_id": it0.get("rec_id"), "text": it0.get("rec_text") or "",
                      "category": None, "departments_canon": [], "finding": None, "page": None}
            row = base_row(pseudo, dc, "cgj")
            row["rec_from"] = "followup_document"
            row["text_page_doc"] = it0["status_doc_id"]
            row["page"] = it0.get("page")
        else:
            r = next((x for x in recs_by_doc[key.split("#")[0]] if x["rec_uid"] == key), None)
            if not r:
                continue
            row = base_row(r, dc, "cgj")
            row["rec_from"] = "report"
            covered.add(key)
        # original response: earliest response letter item, else tracker original column
        letters = sorted([i for i in its if i["status_doc_type"] == "cgj_response"], key=lambda i: str(response_date(i) or ""))
        trackers = [i for i in its if i["status_doc_type"] != "cgj_response"]
        orig = None
        for i in letters + trackers:
            if i.get("original_response") and i["original_response"] not in ("not_applicable",):
                orig = i
                break
        row["cgj_response"] = orig["original_response"] if orig else None
        row["agreed"] = CGJ_AGREED.get(row["cgj_response"] or "not_applicable", "none")
        row["response_raw"] = (orig or {}).get("original_response_raw")
        row["response_text"] = (orig or {}).get("explanation") or (orig or {}).get("original_response_raw")
        events = []
        for i in letters:
            d = response_date(i)
            prec = "day" if d else None
            if not d and row["date_issued"]:
                d = date.fromisoformat(row["date_issued"]) + timedelta(days=90)
                prec = "estimated_report_plus_90d"
            events.append({"date": d.isoformat() if d else None, "precision": prec,
                           "status": STATUS.get(i["status"], "unknown"), "raw": i.get("status_raw") or i.get("original_response_raw"),
                           "doc": i["status_doc_id"], "page": i.get("page"), "basis": "cgj_response",
                           "explanation": i.get("explanation")})
        for i in trackers:
            d, p = pdate(i.get("status_date"))
            if not d:
                d, p = pdate(i.get("as_of_date"))
            d = clamp(d, p, i["status_doc_id"])
            events.append({"date": d.isoformat() if d else None, "precision": p,
                           "status": STATUS.get(i["status"], "unknown"), "raw": i.get("status_raw"),
                           "doc": i["status_doc_id"], "page": i.get("page"), "basis": i["status_doc_type"],
                           "explanation": i.get("explanation")})
        # drop 'unknown' events so they don't override real statuses
        events = [e for e in events if e["status"] != "unknown"]
        resolve(row, events)
        row["respondent_raw"] = sorted({i.get("respondent") or i.get("department") or "" for i in its})[:5]
        rows.append(row)
    for r in recs:
        if r["source"] == "cgj" and r["rec_uid"] not in covered:
            dc = DEPT_CODE.get(r["dept_primary"], "UNK")
            row = base_row(r, dc, "cgj")
            row["rec_from"] = "report"
            row["agreed"] = "none"
            row["cgj_response"] = None
            row["response_raw"] = row["response_text"] = None
            resolve(row, [])
            row["respondent_raw"] = []
            rows.append(row)

    # dedupe ids (same rec + dept twice)
    seen, out = set(), []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append(r)
    json.dump(out, open(os.path.join(WORK, "rows.json"), "w"), indent=0)
    from collections import Counter
    print("rows", len(out))
    print(Counter((r["source"], r["status"]) for r in out).most_common())
    print(Counter(r["status_basis"] for r in out).most_common())


if __name__ == "__main__":
    main()
