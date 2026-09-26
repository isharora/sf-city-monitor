"""Draw a stratified sample of status-item -> recommendation links for hand checking.
Writes data/validation/link_sample.json (verdicts are filled in by the analyst)."""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, RAW
W = os.path.join(DATA, "work")
random.seed(int(sys.argv[1]) if len(sys.argv) > 1 else 11)
inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
items = {x["status_uid"]: x for x in json.load(open(os.path.join(W, "status_items.json")))}
recs = {r["rec_uid"]: r for r in json.load(open(os.path.join(W, "recommendations.json")))}
lc = json.load(open(os.path.join(W, "links_rec.json")))
strata = {"rec_number+text": 18, "rec_number": 8, "text": 8, "claude_adjudicated": 12, "rec_number_paraphrase": 10, "rec_number_subparts": 8}
out = []
for m, n in strata.items():
    pool = [k for k, v in lc.items() if v["method"] == m and k in items]
    for k in random.sample(pool, min(n, len(pool))):
        v, it = lc[k], items[k]
        r = recs.get(v.get("rec_uid"))
        out.append({"status_uid": k, "method": m, "link_confidence": v.get("confidence"),
                    "item": {"doc": it["status_doc_id"], "doc_type": it["status_doc_type"], "cited_report": it.get("source_report_title"),
                             "cited_date": it.get("source_report_date"), "rec_id": it.get("rec_id"), "dept": it.get("department"),
                             "text": (it.get("rec_text") or "")[:400]},
                    "linked": None if not r else {"report": r["doc_id"], "report_title": inv[r["doc_id"]]["title"], "date": r["report_date"],
                                                  "rec_id": r["rec_id"], "dept": r["dept_primary"], "text": (r["text"] or "")[:400]},
                    "verdict": None, "note": None})
json.dump(out, open(os.path.join(DATA, "validation", sys.argv[2] if len(sys.argv) > 2 else "link_sample.json"), "w"), indent=1)
print(len(out))
