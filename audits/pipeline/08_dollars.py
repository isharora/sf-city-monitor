"""Step 8: tie report-stated dollar findings to the recommendations that address them.

For each report with extracted dollar findings, Claude sees the findings and the
recommendations and returns (a) which findings are non-overlapping (to avoid double
counting totals and their parts) and (b) for each recommendation, the findings it
addresses. dollars_at_stake = largest linked non-'other' finding (never summed across
findings, to avoid double counting). Writes data/work/dollars.json
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA  # noqa
import llm  # noqa

WORK = os.path.join(DATA, "work")

SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["independent_findings", "links"],
          "properties": {
              "independent_findings": {"type": "array", "items": {"type": "integer"},
                                       "description": "indices of findings whose amounts can be summed without double counting (drop subtotals/parts already inside a listed total, and duplicates)"},
              "links": {"type": "array", "items": {
                  "type": "object", "additionalProperties": False,
                  "required": ["rec_index", "finding_indices", "confidence"],
                  "properties": {"rec_index": {"type": "integer"},
                                 "finding_indices": {"type": "array", "items": {"type": "integer"}},
                                 "confidence": {"type": "number"}}}}}}

SYSTEM = """You connect dollar-quantified findings in a San Francisco audit report to the recommendations that address them.
For each recommendation, list the findings whose money the recommendation directly addresses (e.g. a recommendation to recover overpayments addresses the overpayment finding; a recommendation to fix a control that caused a questioned cost addresses that cost). Leave finding_indices empty if the recommendation does not address any dollar finding. Be conservative: only link when the report makes the connection reasonably clear.
Also return independent_findings: the subset of findings that can be added together without double counting (exclude a part when its total is also listed, and exclude duplicates)."""


def main():
    reports = json.load(open(os.path.join(WORK, "reports.json")))
    # use only verified findings (08a_verify_dollars.py), with corrected amounts
    ver = json.load(open(os.path.join(WORK, "dollars_verified.json")))
    for rp in reports:
        v = {x["index"]: x for x in ver.get(rp["doc_id"], [])}
        fs = []
        for i, f in enumerate(rp.get("dollar_findings") or []):
            x = v.get(i)
            if x and x["valid"] and x["amount_usd"] > 0:
                fs.append(dict(f, amount_usd=x["amount_usd"], kind=x["kind"], original_amount=f["amount_usd"],
                               verify_rationale=x["rationale"], verify_confidence=x["confidence"], orig_index=i))
        rp["dollar_findings"] = fs
    json.dump({rp["doc_id"]: rp["dollar_findings"] for rp in reports if rp["dollar_findings"]},
              open(os.path.join(WORK, "dollar_findings_verified_by_report.json"), "w"), indent=0)
    recs = json.load(open(os.path.join(WORK, "recommendations.json")))
    by_doc = {}
    for r in recs:
        by_doc.setdefault(r["doc_id"], []).append(r)
    jobs = [rp for rp in reports if rp.get("dollar_findings") and by_doc.get(rp["doc_id"])]
    print("reports with dollar findings and recs:", len(jobs))

    def run(rp):
        f = rp["dollar_findings"]
        rr = by_doc[rp["doc_id"]]
        content = (f"Report: {rp['title']}\n\nDOLLAR FINDINGS:\n" +
                   "\n".join(f"[{i}] ${x['amount_usd']:,.0f} ({x['kind']}): {x['description']} (p.{x['page']})" for i, x in enumerate(f)) +
                   "\n\nRECOMMENDATIONS:\n" +
                   "\n".join(f"[{i}] #{r['rec_id']}: {(r['text'] or '')[:350]} | problem: {r.get('finding') or ''}" for i, r in enumerate(rr)))
        data, _ = llm.call_json("dollars_link", llm.SONNET, SYSTEM, content, SCHEMA, effort="low",
                                max_tokens=16000, cache_tag="dollars:" + rp["doc_id"])
        out = {"doc_id": rp["doc_id"], "independent": data["independent_findings"], "recs": {}}
        for l in data["links"]:
            i = l["rec_index"]
            if not (0 <= i < len(rr)):
                continue
            idx = [k for k in l["finding_indices"] if 0 <= k < len(f) and f[k]["kind"] != "other"]
            if idx:
                best = max(idx, key=lambda k: f[k]["amount_usd"])
                out["recs"][rr[i]["rec_uid"]] = {"dollars": int(round(f[best]["amount_usd"])), "kind": f[best]["kind"],
                                                 "finding": f[best]["description"], "page": f[best]["page"],
                                                 "confidence": l["confidence"], "n_findings": len(idx)}
        return out

    res = {}
    with ThreadPoolExecutor(8) as ex:
        for o in ex.map(run, jobs):
            res[o["doc_id"]] = o
    json.dump(res, open(os.path.join(WORK, "dollars.json"), "w"), indent=0)
    print("recs with dollars:", sum(len(v["recs"]) for v in res.values()))


if __name__ == "__main__":
    main()
