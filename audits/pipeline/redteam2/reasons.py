"""Red team 2, part B (fairness): why do departments say no?

Classifies every 'disagree' response (CGJ 'will not be implemented', CSA/BLA
'do not concur / disagree') by the reason the department's printed response
gives, using Claude Sonnet 5 on the extracted response text. Each judgment
stores a rationale and a confidence (RULES.md). Cached; logged to
data/llm_usage.jsonl under task 'redteam2_reasons'.

Writes data/redteam/reasons.json
"""
import glob
import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from llm import SONNET, call_json  # noqa

DATA = os.path.normpath(os.path.join(HERE, "..", "..", "data"))
OUT = os.path.join(DATA, "redteam")

REASONS = {
    "not_our_authority": "Respondent says it lacks authority or jurisdiction, or the recommendation should go to another body",
    "already_done_or_existing_process": "Says it is already done, already covered by an existing policy, law or process, or duplicative",
    "cost_or_resources": "Cites cost, budget, staffing or funding constraints",
    "legal_or_contract_constraint": "Cites a legal, Charter, labor-agreement, state/federal-law or contractual constraint",
    "policy_disagreement": "Disagrees on the merits (not warranted, would not help, different policy judgment, disputes the finding)",
    "alternative_approach": "Will pursue a different approach or partial measure instead",
    "no_reason_given": "Gives no reason (bare 'disagree'/'will not be implemented' or a cross-reference only)",
}
SYSTEM = ("You classify why a San Francisco city department or official declined an audit or Civil Grand Jury "
          "recommendation, based only on the summary of its printed response. Choose the single best primary reason "
          "and optionally a secondary one. Categories: " + json.dumps(REASONS) +
          ". Be literal: do not infer motives the response does not state. Give a one-sentence rationale and a 0-1 confidence.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {"items": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["id", "primary", "secondary", "rationale", "confidence"],
    "properties": {"id": {"type": "string"}, "primary": {"type": "string", "enum": list(REASONS)},
                   "secondary": {"type": "string", "enum": list(REASONS) + ["none"]},
                   "rationale": {"type": "string"}, "confidence": {"type": "number"}}}}}}


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, "site", "recs", "recs_*.json"))):
        rows += json.load(open(f))["rows"]
    d = [r for r in rows if r["agreed"] == "disagree"]
    batches = [d[i:i + 40] for i in range(0, len(d), 40)]

    def run(b):
        content = "Classify each response.\n\n" + "\n".join(
            json.dumps({"id": r["id"], "respondent": r["dept"], "recommendation": r["text"][:300], "response": r["response_text"]}) for r in b)
        data, _ = call_json("redteam2_reasons", SONNET, SYSTEM, content, SCHEMA, effort="low", max_tokens=16000, cache_tag="rt2r1")
        return data["items"]

    with ThreadPoolExecutor(6) as ex:
        res = [x for items in ex.map(run, batches) for x in items]
    by_id = {x["id"]: x for x in res}
    out = []
    for r in d:
        x = by_id.get(r["id"])
        if x:
            out.append({**x, "dept": r["dept"], "source": r["source"]})
    summ = {}
    for key, sel in (("all", lambda x: True), ("cgj", lambda x: x["source"] == "cgj"), ("csa", lambda x: x["source"] == "csa"),
                     ("bla", lambda x: x["source"] == "bla"), ("BOS", lambda x: x["dept"] == "BOS"), ("MYR", lambda x: x["dept"] == "MYR"),
                     ("CON", lambda x: x["dept"] == "CON")):
        xs = [x for x in out if sel(x)]
        c = Counter(x["primary"] for x in xs)
        summ[key] = {"n": len(xs), "counts": dict(c.most_common()), "shares": {k: round(v / len(xs), 3) for k, v in c.most_common()} if xs else {}}
    cost_auth_legal_existing = {"not_our_authority", "already_done_or_existing_process", "cost_or_resources", "legal_or_contract_constraint"}
    for k in summ:
        xs = [x for x in out if (k == "all" or x["source"] == k or x["dept"] == k)]
        summ[k]["share_authority_existing_cost_legal"] = round(sum(1 for x in xs if x["primary"] in cost_auth_legal_existing) / len(xs), 3) if xs else None
    json.dump({"n_disagree_rows": len(d), "n_classified": len(out), "reasons": REASONS, "summary": summ, "items": out},
              open(os.path.join(OUT, "reasons.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
