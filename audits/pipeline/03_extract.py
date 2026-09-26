"""Step 3: Claude extraction.

Modes:
  reports  - extract recommendations from original reports (CSA audits, PI reviews,
             City Performance, BLA performance audits, CGJ reports)
  status   - extract status updates from follow-up reports, CGJ trackers and CGJ responses

Usage: python3 03_extract.py reports|status [--model sonnet|opus] [--ids a,b] [--limit N] [--workers N]
Outputs data/extract/<mode>[_<model>]/<doc_id>.json
"""
import argparse
import base64
import json
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, PDFS, TEXT, DATA  # noqa
import llm  # noqa
from extract_schemas import REPORT_SCHEMA, REPORT_SYSTEM, STATUS_SCHEMA, STATUS_SYSTEM  # noqa

EXTRACT = os.path.join(DATA, "extract")

REPORT_TYPES = {"csa_audit", "city_performance", "whistleblower", "bla_performance_audit", "cgj_report"}
STATUS_TYPES = {"csa_followup_summary", "csa_open_over_2yrs", "csa_field_followup",
                "pi_status_update", "cgj_status_tracker", "cgj_response", "cgj_status_legacy"}
# Field follow-ups and PI updates can also contain NEW recommendations; they are
# run in both modes.
BOTH_TYPES = {"csa_field_followup", "pi_status_update"}

MAX_TEXT_CHARS = 700_000       # ~175k tokens; above this we split
PAGES_PER_STATUS_CHUNK = 4     # dense tracker tables -> bounded output


URL_TITLE = {}


def load_inventory():
    inv = json.load(open(os.path.join(RAW, "inventory.json")))
    for d in inv:
        URL_TITLE[d["url"]] = d["title"]
    dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
    for d in inv:
        d["dl"] = dl.get(d["doc_id"], {})
    return inv


def page_text(doc_id):
    p = os.path.join(TEXT, doc_id + ".json")
    return json.load(open(p))["pages"] if os.path.exists(p) else None


def header(d, extra=""):
    h = (f"Document ID: {d['doc_id']}\nIssuing body: {d['source']}\nListed title: {d['title']}\n"
         f"Listed date: {d.get('date')}\n")
    ex = d.get("extra", {})
    if ex.get("cgj_term"):
        h += f"Civil Grand Jury term: {ex['cgj_term']}\n"
    if ex.get("parent_report_url") and URL_TITLE.get(ex["parent_report_url"]):
        h += f"Listed under Civil Grand Jury report: {URL_TITLE[ex['parent_report_url']]}\n"
    return h + extra


def text_block(pages, start=0, end=None):
    end = len(pages) if end is None else end
    parts = []
    for i in range(start, end):
        t = re.sub(r"[ \t]+", " ", pages[i])
        t = re.sub(r"\n{3,}", "\n\n", t)
        parts.append(f"[[PAGE {i+1}]]\n{t.strip()}")
    return "\n\n".join(parts)


def pdf_block(doc_id):
    b = open(os.path.join(PDFS, doc_id + ".pdf"), "rb").read()
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.b64encode(b).decode()}}


def pdf_subset_block(doc_id, start, end):
    import fitz
    src = fitz.open(os.path.join(PDFS, doc_id + ".pdf"))
    out = fitz.open()
    out.insert_pdf(src, from_page=start, to_page=end - 1)
    b = out.tobytes()
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                           "data": base64.b64encode(b).decode()}}


# Tabular status documents: send as native PDF so Claude sees the table layout.
PDF_MODE_TYPES = {"cgj_status_tracker", "cgj_status_legacy", "csa_followup_summary", "csa_open_over_2yrs"}


def is_low_text(d):
    return (d["dl"].get("status") == "ok_low_text" or d["doc_type"] in PDF_MODE_TYPES
            or bool(d["dl"].get("partial_scan")))


def run_call(task, model, system, schema, content, effort, tag):
    return llm.call_json(task, model, system, content, schema, effort=effort,
                         max_tokens=64000, cache_tag=tag)


def segments(d, pages, per_chunk=None):
    """Yield (start, end) page ranges."""
    n = len(pages) if pages else d["dl"].get("n_pages", 1)
    if per_chunk:
        for s in range(0, n, per_chunk):
            yield s, min(n, s + per_chunk)
        return
    if pages is None or is_low_text(d):
        step = 90 if n > 95 else n   # PDF input: keep requests modest
        for s in range(0, n, step):
            yield s, min(n, s + step)
        return
    total = sum(len(p) for p in pages)
    if total <= MAX_TEXT_CHARS:
        yield 0, n
        return
    k = total // MAX_TEXT_CHARS + 1
    step = n // k + 1
    for s in range(0, n, step):
        yield s, min(n, s + step)


def build_content(d, pages, s, e, note=""):
    n = len(pages) if pages else d["dl"].get("n_pages")
    rng = f"This input covers PDF pages {s+1}-{e} of {n}." if (s, e) != (0, n) else f"Full document, {n} pages."
    if pages is None or is_low_text(d):
        blk = pdf_block(d["doc_id"]) if (s, e) == (0, n) else pdf_subset_block(d["doc_id"], s, e)
        rng += (" Read the PDF visually (it may be a scan or a table). For every page field, give the "
                "page number WITHIN THIS PDF (its first page = 1); the pipeline converts it.")
        return [blk, {"type": "text", "text": header(d, rng + "\n" + note)}]
    return [{"type": "text", "text": header(d, rng + "\n" + note) + "\n\n" + text_block(pages, s, e)}]


def extract_one(d, mode, model, effort, outdir, force=False):
    out_path = os.path.join(outdir, d["doc_id"] + ".json")
    if os.path.exists(out_path) and not force:
        return json.load(open(out_path))
    pages = page_text(d["doc_id"])
    if mode == "reports":
        system, schema = REPORT_SYSTEM, REPORT_SCHEMA
        # cheap triage: text PDFs with no mention of recommendations -> no LLM call
        if pages is not None and not is_low_text(d):
            full = " ".join(pages)
            if not re.search(r"recommend", full, re.I):
                res = {"doc_id": d["doc_id"], "skipped": "no_recommend_keyword",
                       "data": {"report": None, "recommendations": []}, "calls": []}
                json.dump(res, open(out_path, "w"))
                return res
        segs = list(segments(d, pages))
    else:
        system, schema = STATUS_SYSTEM, STATUS_SCHEMA
        per = PAGES_PER_STATUS_CHUNK if d["doc_type"] in ("cgj_status_tracker", "csa_followup_summary", "csa_open_over_2yrs", "cgj_status_legacy") else None
        if per:
            per = 4
        segs = list(segments(d, pages, per))
    calls, merged = [], None
    pdf_mode = pages is None or is_low_text(d)
    for (s, e) in segs:
        note = ""
        if mode == "reports" and len(segs) > 1:
            note = ("This is one part of a longer report. Extract the recommendations that appear in "
                    "these pages; report-level fields should reflect what these pages show.")
        content = build_content(d, pages, s, e, note)
        try:
            data, meta = run_call(f"extract_{mode}", model, system, schema, content, effort,
                                  f"{mode}:{d['doc_id']}:{s}-{e}")
        except RuntimeError as ex:
            if "max_tokens" in str(ex) and e - s > 1:
                # split in half and retry
                mid = (s + e) // 2
                sub = []
                for (a, b) in [(s, mid), (mid, e)]:
                    c2 = build_content(d, pages, a, b, note + " (sub-part)")
                    dd, mm = run_call(f"extract_{mode}", model, system, schema, c2, effort,
                                      f"{mode}:{d['doc_id']}:{a}-{b}")
                    sub.append((dd, mm, a, b))
                for dd, mm, a, b in sub:
                    calls.append({"pages": [a + 1, b], **{k: mm.get(k) for k in ("cached", "cost_usd", "key")}})
                    if pdf_mode:
                        dd = offset_pages(dd, mode, a)
                    merged = merge(merged, dd, mode)
                continue
            raise
        calls.append({"pages": [s + 1, e], **{k: meta.get(k) for k in ("cached", "cost_usd", "key")}})
        if pdf_mode:
            data = offset_pages(data, mode, s)
        merged = merge(merged, data, mode)
    res = {"doc_id": d["doc_id"], "model": model, "mode": mode, "data": merged, "calls": calls,
           "segments": len(segs)}
    json.dump(res, open(out_path, "w"))
    return res


def offset_pages(data, mode, off):
    """Convert excerpt-relative pages (PDF input) to full-document pages."""
    if not off:
        return data
    if mode == "reports":
        for x in data["recommendations"]:
            for k in ("page", "response_page"):
                if isinstance(x.get(k), int):
                    x[k] += off
        if data.get("report"):
            for f in data["report"].get("dollar_findings", []):
                if isinstance(f.get("page"), int):
                    f["page"] += off
    else:
        for x in data["items"] + data.get("report_level", []):
            if isinstance(x.get("page"), int):
                x["page"] += off
    return data


def merge(acc, new, mode):
    if acc is None:
        return new
    if mode == "reports":
        r0, r1 = acc["report"], new["report"]
        if r0 and r1:
            r0["has_recommendations"] = r0["has_recommendations"] or r1["has_recommendations"]
            for k in ("departments",):
                r0[k] = list(dict.fromkeys(r0[k] + r1[k]))
            r0["dollar_findings"] += r1["dollar_findings"]
            if r0.get("stated_recommendation_count") is None:
                r0["stated_recommendation_count"] = r1.get("stated_recommendation_count")
            if not r0.get("overall_response"):
                r0["overall_response"] = r1.get("overall_response")
        seen = {(x["rec_id"], x["text"][:60]) for x in acc["recommendations"]}
        for x in new["recommendations"]:
            if (x["rec_id"], x["text"][:60]) not in seen:
                acc["recommendations"].append(x)
        return acc
    else:
        acc["items"] += new["items"]
        acc["report_level"] = acc.get("report_level", []) + new.get("report_level", [])
        if not acc["doc"].get("summary_counts"):
            acc["doc"]["summary_counts"] = new["doc"].get("summary_counts")
        return acc


def select(inv, mode):
    out = []
    for d in inv:
        if d["dl"].get("status") not in ("ok", "ok_low_text"):
            continue
        t = d["doc_type"]
        if mode == "reports" and (t in REPORT_TYPES or t in BOTH_TYPES):
            out.append(d)
        elif mode == "status" and t in STATUS_TYPES:
            out.append(d)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["reports", "status"])
    ap.add_argument("--model", default="sonnet", choices=["sonnet", "opus"])
    ap.add_argument("--effort", default=None)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--types", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--reverse", action="store_true", help="process in reverse order (run a 2nd worker pool)")
    a = ap.parse_args()
    model = llm.SONNET if a.model == "sonnet" else llm.OPUS
    effort = a.effort or ("medium" if a.model == "sonnet" else "high")
    outdir = os.path.join(EXTRACT, a.mode + ("" if a.model == "sonnet" else "_opus"))
    os.makedirs(outdir, exist_ok=True)
    inv = load_inventory()
    todo = select(inv, a.mode)
    if a.ids:
        ids = set(a.ids.split(","))
        todo = [d for d in inv if d["doc_id"] in ids]
    if a.types:
        ts = set(a.types.split(","))
        todo = [d for d in todo if d["doc_type"] in ts]
    if a.limit:
        todo = todo[: a.limit]
    if a.reverse:
        todo = todo[::-1]
    print(f"{len(todo)} docs, model={model}, effort={effort}, spent so far ${llm.spent():.2f}", flush=True)
    done = errs = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(extract_one, d, a.mode, model, effort, outdir, a.force): d for d in todo}
        for f in as_completed(futs):
            d = futs[f]
            try:
                r = f.result()
                done += 1
                n = len(r["data"]["recommendations"]) if a.mode == "reports" else len(r["data"]["items"])
                if done % 10 == 0 or a.limit:
                    print(f"[{done}/{len(todo)}] {d['doc_id']} n={n} spent=${llm.spent():.2f}", flush=True)
            except llm.BudgetExceeded as e:
                print("BUDGET STOP", e, flush=True)
                ex.shutdown(cancel_futures=True)
                break
            except Exception as e:
                errs += 1
                with open(os.path.join(outdir, "_errors.log"), "a") as fh:
                    fh.write(f"{d['doc_id']}\t{repr(e)[:500]}\n{traceback.format_exc()[-1500:]}\n")
                print("ERR", d["doc_id"], repr(e)[:200], flush=True)
    print(f"done={done} errors={errs} spent=${llm.spent():.2f}")
