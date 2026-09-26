"""Step 5: link status updates to original reports and recommendations.

A) status item / report-level row -> report (doc_id)
   CGJ responses: parent report from the listing page (exact); else fuzzy title within term.
   CGJ trackers: fuzzy title among CGJ reports of the same term (+/- 1 term).
   CSA: fuzzy title among Controller reports + date proximity.
   Ambiguous -> Claude adjudication (top candidates).
B) status item -> recommendation within the linked report
   normalized rec number match, checked by text similarity when text is available;
   otherwise fuzzy text; ambiguous -> Claude adjudication.
Writes data/work/links_report.json, data/work/links_rec.json
"""
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, DATA  # noqa
import llm  # noqa

WORK = os.path.join(DATA, "work")

STOP = set("the of and a an to in for on its with by at from city san francisco sf department dept".split())


def ntitle(t):
    t = (t or "").lower().replace("’", "'")
    t = re.sub(r"\s*-\s*full report.*$", "", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(w for w in t.split() if w not in STOP)


def parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
    if m:
        y = int(m.group(3))
        y = y + 2000 if y < 100 else y
        try:
            return datetime(y, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    m = re.search(r"(19|20)\d{2}", s)
    return datetime(int(m.group(0)), 7, 1) if m else None


def nrec(r):
    if not r:
        return None
    r = str(r).lower()
    r = re.sub(r"\[.*?\]|\(for .*?\)|for f\d+.*$", "", r)
    r = re.sub(r"recommendation|rec\.?|no\.|number|#", "", r)
    r = r.strip().strip(".").strip()
    r = re.sub(r"^r\.?\s*", "", r)
    r = re.sub(r"\s+", "", r)
    return r or None


def term_shift(term, k):
    a = int(term[:4]) + k
    return f"{a}-{a+1}"


ADJ_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["choice", "confidence", "rationale"],
              "properties": {"choice": {"type": "integer", "description": "index of the matching candidate, or -1 if none match"},
                             "confidence": {"type": "number"},
                             "rationale": {"type": "string"}}}

ADJ_REPORT_SYS = """You match a reference to an original San Francisco oversight report (as cited in a later follow-up or response document) to the correct report in a catalog. Titles in follow-up documents are often shortened, paraphrased or missing a department prefix; dates may be approximate. Choose the candidate that is the same report, or -1 if none is. Give a confidence 0-1 and a one-sentence rationale."""

ADJ_REC_SYS = """You match a recommendation as cited in a later status/response document to the same recommendation in the original report. Numbering may differ in format (e.g. 'R2.3' vs '2.3', 'Recommendation 4' vs '4'), text may be abbreviated. Choose the candidate that is the SAME recommendation (same action for the same department), or -1 if none is. Give a confidence 0-1 and a one-sentence rationale."""


def adjudicate(kind, query, cands, tag):
    lines = [f"[{i}] {c}" for i, c in enumerate(cands)]
    content = f"REFERENCE:\n{query}\n\nCANDIDATES:\n" + "\n".join(lines)
    sysp = ADJ_REPORT_SYS if kind == "report" else ADJ_REC_SYS
    data, _ = llm.call_json(f"link_adjudicate_{kind}", llm.SONNET, sysp, content, ADJ_SCHEMA,
                            effort="low", max_tokens=8000, cache_tag=tag)
    return data


def main():
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    dups = json.load(open(os.path.join(RAW, "duplicates.json"))) if os.path.exists(os.path.join(RAW, "duplicates.json")) else {}
    url2id = {d["url"]: dups.get(d["doc_id"], d["doc_id"]) for d in inv.values()}
    inv_all = inv
    inv = {k: v for k, v in inv.items() if k not in dups}
    recs = json.load(open(os.path.join(WORK, "recommendations.json")))
    items = json.load(open(os.path.join(WORK, "status_items.json")))
    # Legacy Controller CGJ status reports (2006-2008) cover the same jury terms as the
    # per-term tracking documents (CGJS-2003-04 ...) and often omit report titles: excluded.
    items = [x for x in items if x["status_doc_type"] != "cgj_status_legacy"]
    rls = json.load(open(os.path.join(WORK, "report_level.json")))

    rec_by_doc = defaultdict(list)
    for r in recs:
        rec_by_doc[r["doc_id"]].append(r)

    ORIG_TYPES_CON = {"csa_audit", "city_performance", "whistleblower", "csa_field_followup", "pi_status_update"}
    con_reports = [d for d in inv.values() if d["source"] == "controller" and d["doc_type"] in ORIG_TYPES_CON]
    cgj_reports = defaultdict(list)
    for d in inv.values():
        if d["doc_type"] == "cgj_report":
            cgj_reports[d["extra"]["cgj_term"]].append(d)
    bla_reports = [d for d in inv.values() if d["doc_type"] == "bla_performance_audit"]

    def cands_for(obj, is_cgj):
        if is_cgj:
            term = obj.get("cgj_term")
            if term and len(term) == 7:  # "2023-24" from trackers
                term = f"{term[:4]}-{int(term[:2] + term[5:])}"
            terms = set()
            if term:
                terms |= {term_shift(term, k) for k in (0, -1, 1)}
            od = parse_date(obj.get("source_report_date"))
            if od:  # cited report date -> jury term(s) ending/starting that year
                y = od.year
                terms |= {f"{y-1}-{y}", f"{y}-{y+1}"}
            if not terms:
                return [d for v in cgj_reports.values() for d in v]
            pool = []
            for t in sorted(terms):
                pool += cgj_reports.get(t, [])
            return pool
        return con_reports + bla_reports

    def score(obj, d):
        a, b = ntitle(obj.get("source_report_title")), ntitle(d["title"])
        s = max(fuzz.token_set_ratio(a, b), fuzz.token_sort_ratio(a, b) * 0.95)
        od, dd = parse_date(obj.get("source_report_date")), parse_date(d.get("date"))
        bonus = 0
        if od and dd:
            gap = abs((od - dd).days)
            bonus = 12 if gap <= 3 else 6 if gap <= 45 else 0 if gap <= 400 else -15
        return s + bonus

    report_links = {}
    adj_jobs = []

    def link_report(obj, key, is_cgj):
        if obj.get("parent_report_url") and url2id.get(obj["parent_report_url"]):
            pid = url2id[obj["parent_report_url"]]
            # listing parent is reliable unless the item clearly names another report
            if not obj.get("source_report_title") or fuzz.token_set_ratio(ntitle(obj["source_report_title"]), ntitle(inv[pid]["title"])) >= 50:
                report_links[key] = {"doc_id": pid, "method": "listing_parent", "score": 100, "confidence": 0.98}
                return
        if not obj.get("source_report_title"):
            report_links[key] = {"doc_id": None, "method": "no_title", "score": 0, "confidence": 0}
            return
        pool = cands_for(obj, is_cgj)
        scored = sorted(((score(obj, d), d["doc_id"]) for d in pool), reverse=True)[:6]
        if not scored:
            report_links[key] = {"doc_id": None, "method": "no_candidates", "score": 0, "confidence": 0}
            return
        top, second = scored[0][0], (scored[1][0] if len(scored) > 1 else 0)
        if top >= 92 and top - second >= 8:
            report_links[key] = {"doc_id": scored[0][1], "method": "fuzzy_title", "score": round(top, 1), "confidence": 0.95}
        elif top < 45:
            report_links[key] = {"doc_id": None, "method": "no_match", "score": round(top, 1), "confidence": 0.7}
        else:
            adj_jobs.append((key, obj, [c[1] for c in scored]))

    # dedupe report references: many items share the same title/date
    ref_groups = {}
    for it in items:
        is_cgj = it["status_doc_type"] in ("cgj_response", "cgj_status_tracker", "cgj_status_legacy")
        k = (it["status_doc_type"] in ("cgj_response",) and it.get("parent_report_url"), is_cgj,
             it.get("cgj_term"), ntitle(it.get("source_report_title")), str(it.get("source_report_date")))
        ref_groups.setdefault(k, []).append(it["status_uid"])
        it["_refkey"] = k
    for rl in rls:
        k = (None, False, None, ntitle(rl.get("source_report_title")), str(rl.get("source_report_date")))
        ref_groups.setdefault(k, []).append(rl["rl_uid"])
        rl["_refkey"] = k
    rep_obj = {}
    for it in items + rls:
        rep_obj.setdefault(it["_refkey"], it)
    for k, obj in rep_obj.items():
        link_report(obj, k, k[1])
    print("report refs", len(rep_obj), "to adjudicate", len(adj_jobs), flush=True)

    def run_adj(job):
        key, obj, cids = job
        q = f"Title: {obj.get('source_report_title')}\nDate: {obj.get('source_report_date')}\nDepartment: {obj.get('department') or obj.get('dept_canon')}\nCited in: {obj.get('status_doc_title', obj.get('status_doc_id'))}"
        cands = [f"{inv[c]['title']} | date {inv[c].get('date') or inv[c]['extra'].get('cgj_term')} | {inv[c]['source']}" for c in cids]
        res = adjudicate("report", q, cands, "rep:" + json.dumps(key, default=str))
        ch = res["choice"]
        return key, {"doc_id": cids[ch] if 0 <= ch < len(cids) else None, "method": "claude_adjudicated",
                     "score": None, "confidence": res["confidence"], "rationale": res["rationale"]}

    with ThreadPoolExecutor(8) as ex:
        for key, v in ex.map(run_adj, adj_jobs):
            report_links[key] = v

    out_rep = {}
    for it in items:
        out_rep[it["status_uid"]] = report_links[it["_refkey"]]
    for rl in rls:
        out_rep[rl["rl_uid"]] = report_links[rl["_refkey"]]
    json.dump(out_rep, open(os.path.join(WORK, "links_report.json"), "w"), indent=0)

    # ---- B) recommendation-level
    rec_links = {}
    rec_jobs = []
    for it in items:
        rl = out_rep[it["status_uid"]]
        did = rl.get("doc_id")
        if not did:
            rec_links[it["status_uid"]] = {"rec_uid": None, "doc_id": None, "method": "no_report", "confidence": 0}
            continue
        cands = rec_by_doc.get(did, [])
        if not cands:
            rec_links[it["status_uid"]] = {"rec_uid": None, "doc_id": did, "method": "report_has_no_extracted_recs", "confidence": 0}
            continue
        nid = nrec(it.get("rec_id"))
        txt = it.get("rec_text") or ""
        same = [r for r in cands if nid and nrec(r["rec_id"]) == nid]
        sims = sorted(((fuzz.token_set_ratio(txt.lower(), (r["text"] or "").lower()) if txt else 0, r["rec_uid"]) for r in cands), reverse=True)
        sub = []
        if nid and not same:
            # follow-up cites "1" while the report was extracted as sub-parts 1a, 1b, ...
            sub = [r for r in cands if nrec(r["rec_id"]) and nrec(r["rec_id"]).startswith(nid)
                   and len(nrec(r["rec_id"])) > len(nid) and nrec(r["rec_id"])[len(nid)] in "abcdefghij.(-_"]
        if len(same) == 1:
            r = same[0]
            if not txt:
                rec_links[it["status_uid"]] = {"rec_uid": r["rec_uid"], "doc_id": did, "method": "rec_number", "confidence": 0.85}
                continue
            s = fuzz.token_set_ratio(txt.lower(), (r["text"] or "").lower())
            if s >= 60:
                rec_links[it["status_uid"]] = {"rec_uid": r["rec_uid"], "doc_id": did, "method": "rec_number+text", "score": s, "confidence": 0.97}
                continue
            # Follow-up summaries often paraphrase: keep the number unless another
            # recommendation in the report matches the text far better.
            other = [x for x in sims if x[1] != r["rec_uid"]]
            if not (other and other[0][0] >= 85 and other[0][0] >= s + 25):
                rec_links[it["status_uid"]] = {"rec_uid": r["rec_uid"], "doc_id": did, "method": "rec_number_paraphrase", "score": s, "confidence": 0.8}
                continue
        elif sub and len(sub) <= 8:
            sub = sorted(sub, key=lambda r: r["rec_id"])
            rec_links[it["status_uid"]] = {"rec_uid": sub[0]["rec_uid"], "also_rec_uids": [r["rec_uid"] for r in sub[1:]],
                                           "doc_id": did, "method": "rec_number_subparts", "confidence": 0.85}
            continue
        elif txt and sims and sims[0][0] >= 85 and (len(sims) == 1 or sims[0][0] - sims[1][0] >= 10):
            rec_links[it["status_uid"]] = {"rec_uid": sims[0][1], "doc_id": did, "method": "text", "score": sims[0][0], "confidence": 0.9}
            continue
        if not txt and not same:
            rec_links[it["status_uid"]] = {"rec_uid": None, "doc_id": did, "method": "no_number_no_text", "confidence": 0}
            continue
        # candidates for adjudication: same-number ones first, then best text matches
        ordered = [r["rec_uid"] for r in same] + [u for _, u in sims if u not in {r["rec_uid"] for r in same}]
        rec_jobs.append((it, did, ordered[:10]))
    print("rec items", len(items), "to adjudicate", len(rec_jobs), flush=True)
    by_uid = {r["rec_uid"]: r for r in recs}

    def run_rec(job):
        it, did, uids = job
        q = (f"Report: {inv[did]['title']}\nRecommendation number: {it.get('rec_id')}\nDepartment: {it.get('department')}\n"
             f"Text: {it.get('rec_text') or '(not given)'}")
        cands = [f"#{by_uid[u]['rec_id']} ({', '.join(by_uid[u]['departments'] or [])}): {(by_uid[u]['text'] or '')[:500]}" for u in uids]
        res = adjudicate("rec", q, cands, "rec:" + it["status_uid"])
        ch = res["choice"]
        return it["status_uid"], {"rec_uid": uids[ch] if 0 <= ch < len(uids) else None, "doc_id": did,
                                  "method": "claude_adjudicated", "confidence": res["confidence"],
                                  "rationale": res["rationale"]}

    with ThreadPoolExecutor(8) as ex:
        for k, v in ex.map(run_rec, rec_jobs):
            rec_links[k] = v
    json.dump(rec_links, open(os.path.join(WORK, "links_rec.json"), "w"), indent=0)
    from collections import Counter
    print("report link methods", Counter(v["method"] for v in out_rep.values()))
    print("rec link methods", Counter(v["method"] for v in rec_links.values()))
    print("rec linked", sum(1 for v in rec_links.values() if v.get("rec_uid")), "of", len(rec_links))


if __name__ == "__main__":
    main()
