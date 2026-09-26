"""One-off utility: after switching CGJ/BLA doc_ids to URL hashes, rename
already-downloaded PDFs/text files and download records so nothing is refetched.
Uses data/raw/old_ids_url.json (old doc_id -> url) and the current inventory."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, PDFS, TEXT  # noqa

old = json.load(open(os.path.join(RAW, "old_ids_url.json")))
inv = json.load(open(os.path.join(RAW, "inventory.json")))
new_by_url = {d["url"]: d["doc_id"] for d in inv}
dl_path = os.path.join(RAW, "downloads.json")
dl = json.load(open(dl_path))
moved = 0
id_map = {}
for oid, url in old.items():
    nid = new_by_url.get(url)
    if not nid or nid == oid:
        continue
    id_map[oid] = nid
    for folder, ext in ((PDFS, ".pdf"), (TEXT, ".json")):
        a, b = os.path.join(folder, oid + ext), os.path.join(folder, nid + ext)
        if os.path.exists(a) and not os.path.exists(b):
            os.rename(a, b)
            moved += 1
for r in dl:
    if r["doc_id"] in id_map:
        r["doc_id"] = id_map[r["doc_id"]]
# drop download records whose doc no longer exists in the inventory
ids = {d["doc_id"] for d in inv}
dl = [r for r in dl if r["doc_id"] in ids]
json.dump(dl, open(dl_path, "w"), indent=0)
print("mapped", len(id_map), "files moved", moved, "download records", len(dl))
