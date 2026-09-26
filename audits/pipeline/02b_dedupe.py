"""Step 2b: find duplicate documents (same report listed twice, e.g. on the CGJ archive
and on sf.gov, or twice on one archive page under two file names).

Rules
- identical file bytes (sha256) -> duplicates
- Civil Grand Jury reports in the same jury term whose cleaned titles match >= 95 (token set)
- analyst-confirmed pairs in MANUAL (different titles/files for the same report)
Canonical copy: prefer the sf.gov listing (its responses are linked to it), else the
first doc_id. Writes data/raw/duplicates.json {dup_doc_id: canonical_doc_id}.
"""
import json
import os
import re
import sys
from collections import defaultdict

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW  # noqa

MANUAL = [  # (dup, canonical) confirmed by reading both PDFs' title pages
    ("CGJ-2013-2014-8aadd185", "CGJ-2013-2014-f0c8c650"),  # The Port of San Francisco (two file names)
]
NOT_DUP = {frozenset(("CGJ-1995-1996-52783143", "CGJ-1995-1996-abcb3deb")),   # DPW vs DPH
           frozenset(("CGJ-1996-1997-4a4fd328", "CGJ-1996-1997-c6115b2c"))}   # hiring vs jail


def clean(t):
    t = re.sub(r"(?i)\s*-\s*full report.*$|this report details.*$", "", t)
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"(?i)[-,]\s*(January|February|March|April|May|June|July|August|September|October|November|December)\b.*$", "", t)
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def main():
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
    parent = {}

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    def find(a):
        while parent.get(a, a) != a:
            a = parent[a]
        return a

    by_sha = defaultdict(list)
    for i, r in dl.items():
        if r.get("sha256") and i in inv:
            by_sha[r["sha256"]].append(i)
    for v in by_sha.values():
        # identical bytes -> duplicate, but only within the same document type (a file listed
        # once as a report and once as a response matrix is a listing error, handled by title)
        for x in v[1:]:
            same = [y for y in v if y != x and inv[y]["doc_type"] == inv[x]["doc_type"]]
            if same:
                union(x, same[0])
    by_term = defaultdict(list)
    for d in inv.values():
        if d["doc_type"] == "cgj_report":
            by_term[d["extra"]["cgj_term"]].append(d)
    for L in by_term.values():
        for i in range(len(L)):
            for j in range(i + 1, len(L)):
                a, b = L[i], L[j]
                if frozenset((a["doc_id"], b["doc_id"])) in NOT_DUP:
                    continue
                if fuzz.token_set_ratio(clean(a["title"]), clean(b["title"])) >= 95:
                    union(a["doc_id"], b["doc_id"])
    for a, b in MANUAL:
        union(a, b)
    groups = defaultdict(list)
    for i in inv:
        groups[find(i)].append(i)
    out = {}
    for g in groups.values():
        if len(g) < 2:
            continue
        # a report and a response can share bytes only if mislabeled: keep types apart
        types = {inv[i]["doc_type"] for i in g}
        pref = sorted(g, key=lambda i: (0 if "www.sf.gov" in inv[i]["listing_url"] else 1,
                                        0 if inv[i]["doc_type"] == "cgj_report" else 1, i))
        canon = pref[0]
        for i in g:
            if i != canon:
                out[i] = canon
        print(len(g), sorted(types), [(i, inv[i]["title"][:40]) for i in pref])
    json.dump(out, open(os.path.join(RAW, "duplicates.json"), "w"), indent=1)
    print("duplicates:", len(out))


if __name__ == "__main__":
    main()
