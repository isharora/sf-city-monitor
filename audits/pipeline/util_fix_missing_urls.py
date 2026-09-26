"""Find replacement URLs for Controller PDFs whose old sf.gov/sites/default/files
links 404, using the sf.gov Wagtail documents API (exact title match only)."""
import json, os, re, sys
from urllib.parse import quote
sys.path.insert(0, os.path.dirname(__file__))
from common import get, RAW

inv_path = os.path.join(RAW, "inventory.json")
inv = json.load(open(inv_path))
dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower().replace("’", "'")).strip()
fixed = 0
for d in inv:
    r = dl.get(d["doc_id"], {})
    if r.get("status") != "download_error" or "sf.gov/sites/default/files" not in (d["url"] or ""):
        continue
    words = " ".join(re.sub(r"[^A-Za-z0-9 ]", " ", d["title"]).split()[:6])
    res = json.loads(get("https://api.sf.gov/api/v2/documents/?search=" + quote(words)))
    hits = [x for x in res.get("items", []) if norm(x["title"]) == norm(d["title"])]
    if hits:
        d["extra"]["original_url"] = d["url"]
        d["url"] = hits[0]["meta"]["download_url"]
        fixed += 1
        print("fixed", d["doc_id"], d["url"])
    else:
        print("no exact match", d["doc_id"], d["title"][:60], [x["title"][:50] for x in res.get("items", [])][:3])
json.dump(inv, open(inv_path, "w"), indent=1)
print("fixed", fixed)
