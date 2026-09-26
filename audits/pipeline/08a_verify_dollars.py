"""Step 8a: verify dollar-quantified findings against the cited page.

Extraction sometimes records a total cost, total budget or total unmet need as a
'cost overrun' or 'savings'. Claude re-reads each finding with its cited page and keeps
only amounts that are themselves money lost, at risk, owed, recoverable, savable or
overrun (the difference), correcting the amount when the page states the difference.
Writes data/work/dollars_verified.json: {doc_id: [{index, valid, amount_usd, kind, rationale, confidence}]}
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA  # noqa
import llm  # noqa
from extract_schemas import DOLLAR_KINDS  # noqa

WORK = os.path.join(DATA, "work")

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["findings"],
          "properties": {"findings": {"type": "array", "items": {
              "type": "object", "additionalProperties": False,
              "required": ["index", "valid", "amount_usd", "kind", "rationale", "confidence"],
              "properties": {"index": {"type": "integer"}, "valid": {"type": "boolean"},
                             "amount_usd": {"type": "number", "description": "corrected amount (the difference / amount at stake); 0 if not valid"},
                             "kind": {"type": "string", "enum": DOLLAR_KINDS},
                             "rationale": {"type": "string"}, "confidence": {"type": "number"}}}}}}

SYSTEM = """You check dollar amounts that were extracted as 'findings' from a San Francisco oversight report.
A VALID dollar finding is an amount the report itself presents as money lost, overpaid, owed to the City, uncollected, questioned (unsupported or unallowable costs), potentially saved or recoverable, or a cost overrun (the amount ABOVE the original budget).
NOT valid: total project costs or budgets, total contract values, total revenues or spending, total unfunded needs or capital plans, pension liabilities or projected contributions as a whole, figures quoted only as background, and amounts the report attributes to a different earlier report without making its own finding.
If a total is given together with the original amount (e.g. 'budget rose from $38M to $51M'), the valid amount is the difference ($13M) - put it in amount_usd.
Use the page text to decide. Be strict: when in doubt, mark valid=false. Give a one-sentence rationale and confidence 0-1. Return one entry per finding index."""


def main():
    reports = json.load(open(os.path.join(WORK, "reports.json")))
    jobs = [r for r in reports if any(f["kind"] != "other" for f in r.get("dollar_findings") or [])]
    print("reports to verify", len(jobs))

    def page_text(doc_id, p):
        pth = os.path.join(DATA, "text", doc_id + ".json")
        if not p or not os.path.exists(pth):
            return ""
        pages = json.load(open(pth))["pages"]
        return pages[p - 1][:5000] if 1 <= p <= len(pages) else ""

    def run(rp):
        f = rp["dollar_findings"]
        idx = [i for i, x in enumerate(f) if x["kind"] != "other"]
        pages = sorted({f[i]["page"] for i in idx if f[i].get("page")})
        ctx = "\n\n".join(f"[[PAGE {p}]]\n{page_text(rp['doc_id'], p)}" for p in pages[:12])
        content = (f"Report: {rp['title']} ({rp['source']}, {rp.get('date')})\n\nFINDINGS TO CHECK:\n" +
                   "\n".join(f"[{i}] ${f[i]['amount_usd']:,.0f} ({f[i]['kind']}): {f[i]['description']} (page {f[i]['page']})" for i in idx) +
                   ("\n\nCITED PAGE TEXT:\n" + ctx if ctx.strip() else "\n\n(No page text available: the PDF is a scan. Judge from the descriptions.)"))
        data, _ = llm.call_json("dollars_verify", llm.SONNET, SYSTEM, content, SCHEMA, effort="medium",
                                max_tokens=16000, cache_tag="dverify:" + rp["doc_id"])
        return rp["doc_id"], [x for x in data["findings"] if x["index"] in idx]

    out = {}
    with ThreadPoolExecutor(8) as ex:
        for did, v in ex.map(run, jobs):
            out[did] = v
    json.dump(out, open(os.path.join(WORK, "dollars_verified.json"), "w"), indent=0)
    n = sum(len(v) for v in out.values())
    ok = sum(1 for v in out.values() for x in v if x["valid"])
    print("findings checked", n, "valid", ok)


if __name__ == "__main__":
    main()
