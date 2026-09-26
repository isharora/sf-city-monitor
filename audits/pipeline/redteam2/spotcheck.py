"""Red team 2, part C: extraction spot-check at the source.

Draws 25 random recommendations (fixed seed; stratified 10 CSA / 10 CGJ / 5 BLA,
spread across years) and, for each, pulls the cited PDF pages: the recommendation
page (+/-1), the response page, and the status-evidence page. A second reader
(Claude Opus 5.5, high effort) compares the exported fields against those pages;
scanned pages are sent as rendered page images. The analyst then reviews every
item (verdicts in data/redteam/spotcheck_analyst.json, merged here if present).

Writes data/redteam/spotcheck.json
"""
import base64
import glob
import json
import os
import random
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import OPUS, call_json  # noqa

DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
OUT = os.path.join(DATA, "redteam")
SEED = 20260926


def pages_text(doc, pages):
    t = json.load(open(os.path.join(DATA, "text", doc + ".json")))["pages"]
    out = []
    for p in pages:
        if p and 1 <= p <= len(t):
            out.append((p, t[p - 1] if isinstance(t, list) else t[str(p)]))
    return out


def page_image(doc, p):
    pdf = fitz.open(os.path.join(DATA, "pdfs", doc + ".pdf"))
    pix = pdf[p - 1].get_pixmap(dpi=110)
    return base64.b64encode(pix.tobytes("png")).decode()


def sample(rows):
    rng = random.Random(SEED)
    picks = []
    for s, k in (("csa", 10), ("cgj", 10), ("bla", 5)):
        pool = [r for r in rows if r["source"] == s]
        # spread across years: bucket by year, round-robin
        by_y = {}
        for r in pool:
            by_y.setdefault(r["date_issued"][:4], []).append(r)
        years = sorted(by_y)
        rng.shuffle(years)
        i = 0
        while sum(1 for p in picks if p["source"] == s) < k:
            y = years[i % len(years)]
            cand = rng.choice(by_y[y])
            if cand["id"] not in {p["id"] for p in picks}:
                picks.append(cand)
            i += 1
    return picks


SYSTEM = ("You are an independent fact-checker verifying data extracted from San Francisco audit and Civil Grand Jury PDFs. "
          "You receive the exported record and the text (or images) of the cited PDF pages. For each field decide: "
          "'match' (the page supports it), 'minor' (supported but paraphrased/shortened, wrong page by one, or small detail off), "
          "'mismatch' (the page contradicts it), or 'not_on_pages' (the cited pages do not contain the evidence). "
          "Department = the responding department code (codes: POL police, FIR fire, DPH public health, MYR mayor, BOS board of "
          "supervisors, CON controller, ADM city administrator, MTA transportation, PUC utilities, DBI building inspection, "
          "HSA human services, HOM homelessness, REC rec and park, AIR airport, PRT port, DPW public works, ETH ethics, etc.). "
          "Response = the department's response category at publication (agree / partial / disagree / none) as printed. "
          "Status = the latest follow-up status and whether the cited status page supports it (for 'report closed' evidence, "
          "the report must appear in a list of closed reports; for 'inferred_absent...' the page is a list of open items and the "
          "report should NOT appear on it). Quote the decisive words briefly.")
FIELD = {"type": "object", "additionalProperties": False, "required": ["verdict", "evidence"],
         "properties": {"verdict": {"type": "string", "enum": ["match", "minor", "mismatch", "not_on_pages"]}, "evidence": {"type": "string"}}}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["text", "dept", "response", "status", "overall", "confidence", "rationale"],
          "properties": {"text": FIELD, "dept": FIELD, "response": FIELD, "status": FIELD,
                         "overall": {"type": "string", "enum": ["correct", "minor_issues", "error"]},
                         "confidence": {"type": "number"}, "rationale": {"type": "string"}}}


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "site", "recs", "recs_*.json"))):
        rows += json.load(open(f))["rows"]
    picks = sample(rows)
    def one(r):
        rec = {k: r.get(k) for k in ("id", "report", "source", "dept", "depts_all", "date_issued", "rec_number", "text", "agreed",
                                     "response_raw", "response_text", "cgj_response", "status", "status_raw", "status_basis",
                                     "status_doc", "status_page", "page", "response_page")}
        blocks = [{"type": "text", "text": "EXPORTED RECORD:\n" + json.dumps(rec, indent=1)}]
        cites = [(r["report"], sorted({p for p in (r["page"] - 1, r["page"], r["page"] + 1, r.get("response_page")) if p}))]
        if r.get("status_doc") and r.get("status_page"):
            cites.append((r["status_doc"], [r["status_page"]]))
        for doc, pgs in cites:
            for p, txt in pages_text(doc, pgs):
                if len(txt.strip()) < 150:
                    blocks.append({"type": "text", "text": f"--- {doc} page {p} (scanned; image follows)"})
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": page_image(doc, p)}})
                else:
                    blocks.append({"type": "text", "text": f"--- {doc} page {p} ---\n{txt[:9000]}"})
        data, meta = call_json("redteam2_spotcheck", OPUS, SYSTEM, blocks, SCHEMA, effort="high", max_tokens=24000, cache_tag="rt2s1")
        print(r["id"], r["source"], r["date_issued"][:4], data["overall"], "|", data["rationale"][:160], flush=True)
        return ({"id": r["id"], "report": r["report"], "source": r["source"], "year": r["date_issued"][:4], "dept": r["dept"],
                        "page": r["page"], "status": r["status"], "status_basis": r["status_basis"], "status_doc": r.get("status_doc"),
                        "status_page": r.get("status_page"), "check": data})
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(one, picks))
    an_path = os.path.join(OUT, "spotcheck_analyst.json")
    analyst = json.load(open(an_path)) if os.path.exists(an_path) else {}
    for x in results:
        x["analyst"] = analyst.get(x["id"])
    summ = {f: {} for f in ("text", "dept", "response", "status", "overall")}
    for x in results:
        for f in ("text", "dept", "response", "status"):
            v = x["check"][f]["verdict"]
            summ[f][v] = summ[f].get(v, 0) + 1
        summ["overall"][x["check"]["overall"]] = summ["overall"].get(x["check"]["overall"], 0) + 1
    json.dump({"seed": SEED, "n": len(results), "summary_second_reader": summ, "items": results},
              open(os.path.join(OUT, "spotcheck.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
