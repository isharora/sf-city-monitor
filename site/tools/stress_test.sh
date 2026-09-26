#!/bin/zsh
# Scale test: a throwaway copy of the site with the sample data inflated (network flows x40 split by year,
# nonprofit orgs/cells x10, audit recommendations x6) promoted to "real" exports, then the full self-test.
# Checks that every filter still applies and nothing errors at production-like row counts.
set -u
SRC="$(cd "$(dirname "$0")/../.." && pwd)"; FX=/tmp/scm_stress
rm -rf "$FX"; mkdir -p "$FX"; cp -R "$SRC/site" "$FX/site"; rm -rf "$FX/site/data"
ln -s "$SRC/design" "$FX/design"; ln -s "$SRC/performance" "$FX/performance"
python3 - "$FX" <<'PY'
import json, os, shutil, sys
FX = sys.argv[1]; S = f"{FX}/design/prototype/sample-data"
sfx = lambda k: "" if k == 0 else f"-{k}"
def promote(mod, fn):
    d = f"{FX}/{mod}/data/site"; shutil.copytree(f"{S}/{mod}", d); os.makedirs(f"{d}/commentary", exist_ok=True)
    pre = {"nonprofits": "np-", "network": "nw-", "audits": "au-"}[mod]; st = {"nonprofits": "story_np", "network": "story_nw", "audits": "story_au"}[mod]
    for f in os.listdir(f"{S}/commentary"):
        if f.startswith(pre) or f == st + ".json": shutil.copy(f"{S}/commentary/{f}", f"{d}/commentary/{f}")
    m = json.load(open(f"{d}/meta.json")); m["sample"] = False; json.dump(m, open(f"{d}/meta.json", "w")); fn(d)
def nw(d):
    fl = json.load(open(f"{d}/flows.json")); out = [dict(f, id=f"{f['id']}{sfx(k)}") for k in range(40) for f in fl["flows"]]
    os.remove(f"{d}/flows.json"); os.makedirs(f"{d}/flows")
    for y in sorted({f["date"][:4] for f in out}): json.dump(dict(fl, flows=[f for f in out if f["date"][:4] == y]), open(f"{d}/flows/flows_{y}.json", "w"))
    print("network flows", len(out))
def np_(d):
    o = json.load(open(f"{d}/orgs/index.json")); c = json.load(open(f"{d}/payments/cells.json"))
    o["orgs"] = [dict(x, id=f"{x['id']}{sfx(k)}", name=x["name"] + (f" {k}" if k else ""), network_id=x["network_id"] if k == 0 else None) for k in range(10) for x in o["orgs"]]
    c["cells"] = [dict(x, org=f"{x['org']}{sfx(k)}") for k in range(10) for x in c["cells"]]
    json.dump(o, open(f"{d}/orgs/index.json", "w")); json.dump(c, open(f"{d}/payments/cells.json", "w")); print("orgs", len(o["orgs"]), "cells", len(c["cells"]))
def au(d):
    r = json.load(open(f"{d}/recs/recs.json"))
    r["rows"] = [dict(x, id=f"{x['id']}{sfx(k)}", repeat_of=(f"{x['repeat_of']}{sfx(k)}" if x.get("repeat_of") else None)) for k in range(6) for x in r["rows"]]
    json.dump(r, open(f"{d}/recs/recs.json", "w")); print("recs", len(r["rows"]))
promote("network", nw); promote("nonprofits", np_); promote("audits", au)
PY
python3 "$FX/site/tools/bundle.py" --quiet | tail -1
START=$(date +%s)
python3 - "$FX" <<'PY'
import sys; sys.path.insert(0, sys.argv[1] + "/site/tools")
import check; check.SITE = sys.argv[1] + "/site"
res, lines = check.selftest()
if not res: print("selftest did not finish", lines[:5]); sys.exit(1)
print(f"stress selftest: {res['pass']} passed, {res['fail']} failed")
for r in res["results"]:
    if not r["pass"]: print("  FAIL", r["group"], r["name"], r["detail"][:200])
sys.exit(1 if res["fail"] else 0)
PY
rc=$?; echo "wall time $(( $(date +%s) - START ))s"; exit $rc
