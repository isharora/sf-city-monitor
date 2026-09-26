"""Step 9: repeat findings - cluster recommendations to the same department that
address the same underlying problem across different reports and years.

  python3 09_repeats.py cluster    # Opus clusters per department (blocks by topic if large)
  python3 09_repeats.py validate   # independent pair judge (Sonnet) on repeat pairs + near-miss non-pairs;
                                   # writes a hand-check sheet data/validation/repeat_pairs_handcheck.json
Writes data/work/repeat_clusters.json, data/work/repeat_of.json, data/qc/repeat_validation.json
"""
import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA  # noqa
import llm  # noqa

WORK = os.path.join(DATA, "work")
QC = os.path.join(DATA, "qc")
VAL = os.path.join(DATA, "validation")
os.makedirs(QC, exist_ok=True)
os.makedirs(VAL, exist_ok=True)

BLOCKS = [("finance", "revenue"), ("contracts", "grants"), ("hr",), ("it", "performance"),
          ("governance", "ethics", "compliance", "planning", "other"), ("service", "safety"), ("facilities",)]
MAX_PER_CALL = 420
MIN_CONF = 0.6

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["clusters"],
          "properties": {"clusters": {"type": "array", "items": {
              "type": "object", "additionalProperties": False,
              "required": ["theme", "members", "confidence", "rationale"],
              "properties": {"theme": {"type": "string", "description": "short plain-language name of the recurring problem"},
                             "members": {"type": "array", "items": {"type": "integer"}},
                             "confidence": {"type": "number"},
                             "rationale": {"type": "string"}}}}}}

SYSTEM = """You are an experienced government auditor looking for REPEAT FINDINGS: problems that oversight bodies (the Controller's auditors, the Budget and Legislative Analyst, the Civil Grand Jury) flagged for the same San Francisco department more than once, in different reports issued at different times.

You get a numbered list of recommendations made to ONE department: [n] year | source | report-id | recommendation (and the problem it addresses).
Return clusters of recommendations that ask the department to fix substantially the SAME underlying problem - the same process, program, control or system - so that a later recommendation shows the earlier fix did not happen or did not stick. Rules:
- A cluster must contain recommendations from at least TWO different report-ids with different years. Never cluster recommendations that all come from one report.
- Same broad topic is NOT enough (e.g. two unrelated contract-monitoring issues in different programs are not a repeat; "improve oversight" of two different contractors is not a repeat unless the underlying process failure is the same).
- Do include recurring issues phrased differently (e.g. overtime controls in 2012 and 2019; unreconciled cash receipts at the same division in 2008 and 2016; the same IT access-control weakness; the same unmet performance reporting requirement).
- Each recommendation can be in at most one cluster. Leave out everything that does not repeat.
- confidence 0-1 that the cluster is a genuine repeat; one-sentence rationale."""


def load_rows():
    rows = json.load(open(os.path.join(WORK, "rows.json")))
    return [r for r in rows if r.get("date_issued") and r["dept"] not in ("UNK", "NONCITY", "CITYWIDE")]


def fmt(i, r):
    t = (r.get("text_full") or r["text"] or "")[:260]
    f = (r.get("finding") or "")[:140]
    return f"[{i}] {r['date_issued'][:4]} | {r['source']} | {r['report']} | {t}" + (f" | problem: {f}" if f else "")


def cluster():
    rows = load_rows()
    by_dept = defaultdict(list)
    for r in rows:
        by_dept[r["dept"]].append(r)
    jobs = []
    for dept, rs in by_dept.items():
        if len({r["report"] for r in rs}) < 2:
            continue
        rs = sorted(rs, key=lambda r: (r["date_issued"], r["report"], r["id"]))
        if len(rs) <= MAX_PER_CALL:
            jobs.append((dept, "all", rs))
        else:
            for b in BLOCKS:
                sub = [r for r in rs if r["topic"] in b]
                for k in range(0, len(sub), MAX_PER_CALL):
                    part = sub[k:k + MAX_PER_CALL]
                    if len({r["report"] for r in part}) >= 2:
                        jobs.append((dept, "+".join(b) + f":{k}", part))
    print("cluster jobs", len(jobs), flush=True)

    def run(job):
        dept, blk, rs = job
        content = f"Department: {dept}\nBlock: {blk}\n\n" + "\n".join(fmt(i, r) for i, r in enumerate(rs))
        data, _ = llm.call_json("repeat_cluster", llm.OPUS, SYSTEM, content, SCHEMA, effort="high",
                                max_tokens=64000, cache_tag=f"rep:{dept}:{blk}")
        out = []
        for c in data["clusters"]:
            mem = [rs[i] for i in c["members"] if 0 <= i < len(rs)]
            if len({m["report"] for m in mem}) < 2 or len({m["date_issued"][:4] for m in mem}) < 2:
                continue
            out.append({"dept": dept, "block": blk, "theme": c["theme"], "confidence": c["confidence"],
                        "rationale": c["rationale"], "members": [m["id"] for m in mem]})
        return out

    clusters = []
    with ThreadPoolExecutor(6) as ex:
        for o in ex.map(run, jobs):
            clusters += o
    for i, c in enumerate(clusters):
        c["cluster_id"] = f"C-{i:04d}"
    byid = {r["id"]: r for r in rows}
    repeat_of = {}
    # Validation (independent pair judge) confirmed ~80% of pairs from clusters with
    # confidence >= 0.6 but only ~59% below it, so repeat_of uses clusters >= MIN_CONF.
    for c in clusters:
        c["used_for_repeat_of"] = c["confidence"] >= MIN_CONF
    for c in [c for c in clusters if c["used_for_repeat_of"]]:
        mem = sorted(c["members"], key=lambda k: (byid[k]["date_issued"], byid[k]["report"]))
        for j, k in enumerate(mem):
            prev = [m for m in mem[:j] if byid[m]["report"] != byid[k]["report"] and byid[m]["date_issued"] < byid[k]["date_issued"]]
            if prev:
                repeat_of[k] = {"repeat_of": prev[-1], "cluster_id": c["cluster_id"], "confidence": c["confidence"],
                                "theme": c["theme"]}
    json.dump(clusters, open(os.path.join(WORK, "repeat_clusters.json"), "w"), indent=0)
    json.dump(repeat_of, open(os.path.join(WORK, "repeat_of.json"), "w"), indent=0)
    print("clusters", len(clusters), "repeat rows", len(repeat_of))


PAIR_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["same_problem", "confidence", "rationale"],
               "properties": {"same_problem": {"type": "boolean"}, "confidence": {"type": "number"},
                              "rationale": {"type": "string"}}}
PAIR_SYS = """Two recommendations were made to the same San Francisco department in different reports. Decide whether the LATER one asks the department to fix substantially the same underlying problem (same process, program, control or system) as the EARLIER one - i.e. a repeat finding - rather than merely a similar topic. Answer true/false with confidence 0-1 and a one-sentence rationale."""


def judge(a, b, tag):
    content = (f"Department: {a['dept']}\nEARLIER ({a['date_issued']}, {a['source']}, report {a['report']}):\n{a.get('text_full') or a['text']}\nProblem: {a.get('finding')}\n\n"
               f"LATER ({b['date_issued']}, {b['source']}, report {b['report']}):\n{b.get('text_full') or b['text']}\nProblem: {b.get('finding')}")
    d, _ = llm.call_json("repeat_pair_judge", llm.SONNET, PAIR_SYS, content, PAIR_SCHEMA, effort="medium",
                         max_tokens=8000, cache_tag=tag)
    return d


def validate():
    random.seed(7)
    rows = load_rows()
    byid = {r["id"]: r for r in rows}
    rep = json.load(open(os.path.join(WORK, "repeat_of.json")))
    pos = random.sample(sorted(rep.items()), min(150, len(rep)))
    # near-miss negatives: same dept, different reports/years, high text similarity, not linked
    linked = {(k, v["repeat_of"]) for k, v in rep.items()}
    cl_of = {}
    for c in json.load(open(os.path.join(WORK, "repeat_clusters.json"))):
        for m in c["members"]:
            cl_of[m] = c["cluster_id"]
    by_dept = defaultdict(list)
    for r in rows:
        by_dept[r["dept"]].append(r)
    cands = []
    for dept, rs in by_dept.items():
        rs = sorted(rs, key=lambda r: r["date_issued"])
        sample = rs if len(rs) < 300 else random.sample(rs, 300)
        for i, a in enumerate(sample):
            for b in sample[i + 1:]:
                if a["report"] == b["report"] or a["date_issued"][:4] == b["date_issued"][:4]:
                    continue
                if cl_of.get(a["id"]) and cl_of.get(a["id"]) == cl_of.get(b["id"]):
                    continue
                s = fuzz.token_set_ratio(a["text"].lower(), b["text"].lower())
                if s >= 70:
                    e, l = (a, b) if a["date_issued"] <= b["date_issued"] else (b, a)
                    cands.append((s, e["id"], l["id"]))
    cands.sort(reverse=True)
    neg = random.sample(cands[:600], min(100, len(cands[:600])))

    def jp(x):
        kind, a, b = x
        d = judge(byid[a], byid[b], f"pair:{a}:{b}")
        return kind, a, b, d

    jobs = [("pos", v["repeat_of"], k) for k, v in pos if v["repeat_of"] in byid and k in byid] + [("neg", a, b) for _, a, b in neg]
    res = []
    with ThreadPoolExecutor(8) as ex:
        for kind, a, b, d in ex.map(jp, jobs):
            res.append({"kind": kind, "earlier": a, "later": b, **d})
    pos_r = [r for r in res if r["kind"] == "pos"]
    neg_r = [r for r in res if r["kind"] == "neg"]
    summary = {"pairs_judged_pos": len(pos_r), "judge_confirms_pos": sum(r["same_problem"] for r in pos_r) / max(1, len(pos_r)),
               "pairs_judged_neg": len(neg_r), "judge_says_repeat_among_near_miss_negatives": sum(r["same_problem"] for r in neg_r) / max(1, len(neg_r))}
    json.dump({"summary": summary, "pairs": res}, open(os.path.join(QC, "repeat_validation.json"), "w"), indent=0)
    # hand-check sheet: 40 positive pairs
    sheet = []
    for r in pos_r[:40]:
        a, b = byid[r["earlier"]], byid[r["later"]]
        sheet.append({"earlier": a["id"], "later": b["id"], "dept": a["dept"], "theme": rep[b["id"]]["theme"],
                      "earlier_text": f"{a['date_issued']} {a['report']}: {a.get('text_full') or a['text']}",
                      "later_text": f"{b['date_issued']} {b['report']}: {b.get('text_full') or b['text']}",
                      "judge": r["same_problem"], "analyst_verdict": None, "analyst_note": None})
    # reuse analyst verdicts from earlier rounds for identical pairs
    prior = {}
    for f in ("repeat_pairs_handcheck_round1.json", "repeat_pairs_handcheck.json"):
        fp = os.path.join(VAL, f)
        if os.path.exists(fp):
            for x in json.load(open(fp)):
                if x.get("analyst_verdict") is not None:
                    prior[(x["earlier"], x["later"])] = (x["analyst_verdict"], x.get("analyst_note"))
    for x in sheet:
        if (x["earlier"], x["later"]) in prior:
            x["analyst_verdict"], x["analyst_note"] = prior[(x["earlier"], x["later"])]
    p = os.path.join(VAL, "repeat_pairs_handcheck_final.json")
    if not os.path.exists(p):
        json.dump(sheet, open(p, "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    {"cluster": cluster, "validate": validate}[sys.argv[1]]()
