"""Merge data/reviews/partials/group_*.json into data/reviews/reviews.json and org_findings.json.
Validates schema, review_id references, and re-verifies verbatim quotes against extracted PDF text
(data/reviews/text) or cached news text (data/reviews/news_cache)."""
import json, re, pathlib, glob, collections
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
RK = ["id", "title", "publisher", "date", "url", "type", "summary", "accessed_date"]
FK = ["org_name", "org_name_aliases", "ein", "review_id", "finding_type", "finding", "quote", "page", "status", "url"]
TYPES = {"controller_audit", "controller_public_integrity", "controller_monitoring", "bla", "civil_grand_jury", "news", "city_policy"}
reviews, findings = {}, []
for f in sorted(glob.glob(str(base / "partials" / "group_*.json"))):
    d = json.load(open(f))
    for r in d.get("reviews", []):
        r = {k: r.get(k) for k in RK}
        assert r["type"] in TYPES, (f, r["id"], r["type"])
        if r["id"] in reviews: print("dup review id", r["id"], f); continue
        reviews[r["id"]] = r
    for e in d.get("org_findings", []):
        findings.append({k: e.get(k) for k in FK})
# url -> text file
src = {}
for l in (base / "pdf_sources.tsv").read_text().splitlines()[1:]:
    p = l.split("\t")
    if len(p) >= 3:
        u = p[2].strip(); src[u] = base / "text" / (p[0].replace(".pdf", ".txt"))
        src[u.replace("https://sfbos.org/", "https://sfbos.archive.sf.gov/")] = src[u]  # sfbos.org now redirects to the archive host
import unicodedata
def norm(s): return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", s or "").lower())
def pages(p):
    parts = re.split(r"=== PAGE (\d+) ===", p.read_text()); return {int(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}
cache = {}
news_txt = {pathlib.Path(p).name: pathlib.Path(p).read_text(errors="ignore") for p in glob.glob(str(base / "news_cache" / "*.txt"))}
bad, orphan = [], []
for e in findings:
    if e["review_id"] not in reviews: orphan.append(e); continue
    q = norm(e["quote"])
    if not q: bad.append((e, "no quote")); continue
    tf = src.get(e["url"])
    if tf and tf.exists():
        pg = cache.setdefault(tf, pages(tf))
        hay = "".join(pg.values()) if not e["page"] else "".join(pg.get(i, "") for i in (e["page"] - 1, e["page"], e["page"] + 1))
        if q not in norm(hay): bad.append((e, "not in pdf page"))
    elif reviews[e["review_id"]]["type"] == "news":
        if not any(q in norm(t) for t in news_txt.values()): bad.append((e, "not in news cache"))
    else:
        bad.append((e, "no source text to verify"))
    if len((e["quote"] or "").split()) > 40: bad.append((e, "quote >40 words"))
print("reviews", len(reviews), "findings", len(findings), "orphans", len(orphan), "unverified", len(bad))
for e, why in bad[:40]: print(" ", why, "|", e["review_id"], "|", e["org_name"], "|", (e["quote"] or "")[:70])
json.dump(list(reviews.values()), open(base / "reviews.json", "w"), indent=1, ensure_ascii=False)
json.dump([e for e in findings if e["review_id"] in reviews], open(base / "org_findings.json", "w"), indent=1, ensure_ascii=False)
print(collections.Counter(r["type"] for r in reviews.values()))
print(collections.Counter(e["finding_type"] for e in findings).most_common())
