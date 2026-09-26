"""Step 2: download PDFs (polite, cached) and extract per-page text.

Reads data/raw/inventory.json; writes
  data/pdfs/<doc_id>.pdf
  data/text/<doc_id>.json   {"pages": [...], "n_pages": N, "chars": C}
  data/raw/downloads.json   per-doc status, sha256, bytes, pages, text chars
Press releases are skipped. Rate limit: 1 request/second/host (common.py).
"""
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import fitz  # pymupdf

sys.path.insert(0, os.path.dirname(__file__))
from common import get, RAW, PDFS, TEXT  # noqa

SKIP_TYPES = {"press_release"}


def fetch(d):
    rec = {"doc_id": d["doc_id"], "url": d.get("url")}
    if not d.get("url"):
        rec["status"] = "no_url"
        return rec
    path = os.path.join(PDFS, d["doc_id"] + ".pdf")
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            b = open(path, "rb").read()
        else:
            b = get(d["url"], binary=True, timeout=180, cache=False)
            with open(path, "wb") as f:
                f.write(b)
    except Exception as e:
        rec["status"] = "download_error"
        rec["error"] = str(e)[:300]
        return rec
    rec["bytes"] = len(b)
    rec["sha256"] = hashlib.sha256(b).hexdigest()
    if not b[:5].startswith(b"%PDF"):
        rec["status"] = "not_pdf"
        rec["head"] = b[:80].decode("latin-1")
        return rec
    tpath = os.path.join(TEXT, d["doc_id"] + ".json")
    try:
        if not os.path.exists(tpath):
            doc = fitz.open(stream=b, filetype="pdf")
            pages = [p.get_text("text") for p in doc]
            json.dump({"pages": pages, "n_pages": len(pages),
                       "chars": sum(len(p) for p in pages)}, open(tpath, "w"))
        t = json.load(open(tpath))
        rec["n_pages"] = t["n_pages"]
        rec["chars"] = t["chars"]
        rec["chars_per_page"] = t["chars"] / max(1, t["n_pages"])
        rec["status"] = "ok" if rec["chars_per_page"] > 200 else "ok_low_text"
        # partially scanned: text PDF with image-only pages (e.g. scanned response letters)
        empty = sum(1 for p in t["pages"] if len(p.strip()) < 80)
        rec["empty_pages"] = empty
        rec["partial_scan"] = bool(t["n_pages"] >= 3 and empty >= 2 and empty / t["n_pages"] >= 0.15)
    except Exception as e:
        rec["status"] = "pdf_parse_error"
        rec["error"] = str(e)[:300]
    return rec


if __name__ == "__main__":
    inv = json.load(open(os.path.join(RAW, "inventory.json")))
    todo = [d for d in inv if d["doc_type"] not in SKIP_TYPES]
    only = sys.argv[1:]
    if only:
        todo = [d for d in todo if d["source"] in only]
    out_path = os.path.join(RAW, "downloads.json")
    prev = {r["doc_id"]: r for r in json.load(open(out_path))} if os.path.exists(out_path) else {}
    results = dict(prev)
    # parallel across hosts; common.get enforces 1 req/s per host
    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, rec in enumerate(ex.map(fetch, todo)):
            results[rec["doc_id"]] = rec
            if i % 50 == 0:
                print(i, len(todo), rec["doc_id"], rec["status"], flush=True)
                json.dump(list(results.values()), open(out_path, "w"))
    json.dump(list(results.values()), open(out_path, "w"), indent=0)
    from collections import Counter
    print(Counter(r["status"] for r in results.values()))
