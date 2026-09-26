"""Step 6: quality control - compare Sonnet extraction with an independent Opus
re-extraction of a random sample of reports (and status documents).

Usage:
  python3 06_qc_compare.py sample   # choose sample, write data/qc/sample_*.json
  (then run 03_extract.py reports --model opus --ids <sample>; status likewise)
  python3 06_qc_compare.py compare  # write data/qc/qc_results.json
"""
import json
import os
import random
import re
import sys
from collections import Counter

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, DATA  # noqa

EX = os.path.join(DATA, "extract")
QC = os.path.join(DATA, "qc")
os.makedirs(QC, exist_ok=True)


def nrec(r):
    r = str(r or "").lower()
    r = re.sub(r"recommendation|rec\.?|no\.|#|\s+", "", r).strip(".")
    return re.sub(r"^r\.?", "", r)


def load(mode, model_suffix, doc_id):
    p = os.path.join(EX, mode + model_suffix, doc_id + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def sample():
    random.seed(20260926)
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    rep = []
    for f in os.listdir(os.path.join(EX, "reports")):
        if not f.endswith(".json"):
            continue
        r = json.load(open(os.path.join(EX, "reports", f)))
        if r.get("skipped"):
            continue
        rep.append((inv[r["doc_id"]]["source"], r["doc_id"], len(r["data"]["recommendations"])))
    # stratify: 20 controller, 12 cgj, 8 bla; include some zero-rec docs among controller
    out = []
    for src, n in (("controller", 22), ("cgj", 12), ("bla", 8)):
        pool = [x for x in rep if x[0] == src]
        out += random.sample(pool, min(n, len(pool)))
    ids = [x[1] for x in out]
    st = [f[:-5] for f in os.listdir(os.path.join(EX, "status")) if f.endswith(".json")]
    st_s = random.sample(st, min(15, len(st)))
    json.dump({"reports": ids, "status": st_s}, open(os.path.join(QC, "sample.json"), "w"), indent=1)
    print(",".join(ids))
    print(",".join(st_s))


def match(a, b):
    """Greedy match of recommendation lists a (sonnet) to b (opus)."""
    pairs, used = [], set()
    scored = []
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            s = fuzz.token_set_ratio((x["text"] or "").lower(), (y["text"] or "").lower())
            if nrec(x["rec_id"]) == nrec(y["rec_id"]):
                s += 15
            scored.append((s, i, j))
    usedi = set()
    for s, i, j in sorted(scored, reverse=True):
        if s < 70 or i in usedi or j in used:
            continue
        usedi.add(i)
        used.add(j)
        pairs.append((i, j, s))
    return pairs


def _vp():
    import importlib.util
    spec = importlib.util.spec_from_file_location("norm", os.path.join(os.path.dirname(__file__), "04_normalize.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.verify_page


def compare():
    global VP
    VP = _vp()
    s = json.load(open(os.path.join(QC, "sample.json")))
    res = {"per_report": [], "fields": Counter(), "fields_n": Counter()}
    tot_a = tot_b = tot_m = 0
    for doc_id in s["reports"]:
        a, b = load("reports", "", doc_id), load("reports", "_opus", doc_id)
        if not a or not b:
            continue
        ra, rb = a["data"]["recommendations"], b["data"]["recommendations"]
        pairs = match(ra, rb)
        tot_a += len(ra)
        tot_b += len(rb)
        tot_m += len(pairs)
        stated = (b["data"].get("report") or {}).get("stated_recommendation_count")
        res["per_report"].append({"doc_id": doc_id, "sonnet": len(ra), "opus": len(rb), "matched": len(pairs),
                                  "stated": stated})
        for i, j, _ in pairs:
            x, y = ra[i], rb[j]
            for f in ("category", "response", "target_date_iso", "page"):
                res["fields_n"][f] += 1
                if (x.get(f) or None) == (y.get(f) or None):
                    res["fields"][f] += 1
            # category agreement allowing primary==secondary swap
            res["fields_n"]["category_lenient"] += 1
            if x["category"] in (y["category"], y.get("secondary_category")) or y["category"] == x.get("secondary_category"):
                res["fields"]["category_lenient"] += 1
            res["fields_n"]["department_first"] += 1
            da = (x["departments"] or [""])[0].lower()
            db = (y["departments"] or [""])[0].lower()
            if fuzz.token_set_ratio(da, db) >= 80:
                res["fields"]["department_first"] += 1
            res["fields_n"]["page_verified_exact"] += 1
            pa = VP(doc_id, x["text"], x.get("page"))[0]
            pb = VP(doc_id, y["text"], y.get("page"))[0]
            if pa == pb:
                res["fields"]["page_verified_exact"] += 1
            res["fields_n"]["page_pm1"] += 1
            if x.get("page") and y.get("page") and abs(x["page"] - y["page"]) <= 1:
                res["fields"]["page_pm1"] += 1
        # dollar findings: compare sets of amounts
    res["rec_recall_vs_opus"] = tot_m / tot_b if tot_b else None
    res["rec_precision_vs_opus"] = tot_m / tot_a if tot_a else None
    res["totals"] = {"sonnet": tot_a, "opus": tot_b, "matched": tot_m}
    res["field_agreement"] = {f: res["fields"][f] / res["fields_n"][f] for f in res["fields_n"]}
    res["report_count_exact"] = sum(1 for r in res["per_report"] if r["sonnet"] == r["opus"]) / max(1, len(res["per_report"]))
    wst = [r for r in res["per_report"] if r["stated"]]
    res["stated_count_match_sonnet"] = sum(1 for r in wst if r["sonnet"] == r["stated"]) / max(1, len(wst))
    res["stated_count_match_opus"] = sum(1 for r in wst if r["opus"] == r["stated"]) / max(1, len(wst))
    res["n_with_stated"] = len(wst)
    # status docs
    st = {"n_items_sonnet": 0, "n_items_opus": 0, "matched": 0, "status_agree": 0, "orig_agree": 0}
    for doc_id in s["status"]:
        a, b = load("status", "", doc_id), load("status", "_opus", doc_id)
        if not a or not b:
            continue
        ia, ib = a["data"]["items"], b["data"]["items"]
        st["n_items_sonnet"] += len(ia)
        st["n_items_opus"] += len(ib)
        used = set()
        for x in ia:
            best, bj = 0, None
            for j, y in enumerate(ib):
                if j in used:
                    continue
                sc = fuzz.token_set_ratio(f"{x.get('source_report_title')} {x.get('rec_id')} {x.get('department')}",
                                          f"{y.get('source_report_title')} {y.get('rec_id')} {y.get('department')}")
                if nrec(x.get("rec_id")) == nrec(y.get("rec_id")):
                    sc += 10
                if sc > best:
                    best, bj = sc, j
            if bj is not None and best >= 85:
                used.add(bj)
                st["matched"] += 1
                y = ib[bj]
                st["status_agree"] += x["status"] == y["status"]
                st["orig_agree"] += x["original_response"] == y["original_response"]
    st["status_agreement"] = st["status_agree"] / max(1, st["matched"])
    st["original_response_agreement"] = st["orig_agree"] / max(1, st["matched"])
    st["item_recall_vs_opus"] = st["matched"] / max(1, st["n_items_opus"])
    res["status"] = st
    res.pop("fields")
    res.pop("fields_n")
    json.dump(res, open(os.path.join(QC, "qc_results.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "per_report"}, indent=1))


if __name__ == "__main__":
    {"sample": sample, "compare": compare}[sys.argv[1]]()
