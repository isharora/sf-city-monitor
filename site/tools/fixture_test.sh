#!/bin/zsh
# Robustness test: build a throwaway copy of the site against a fake "real" nonprofits export with one
# file missing (contracts) and one file broken (form990 rows without 'fy'), plus a network export
# whose meta lacks "sample": false. Then render and assert:
#   - np-growth, np-dependency, np-pay show "Analysis not available yet"; np-flows renders normally;
#   - the org profile blanks only its Contracts / Form 990 sections;
#   - network falls back to sample data (banner present);
#   - over http the loader reads the raw export JSON (fetch path) and the page still renders.
# Nothing in the real tree is modified. Usage: site/tools/fixture_test.sh
set -u
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
FX=/tmp/scm_fixture
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
rm -rf "$FX"; mkdir -p "$FX"
cp -R "$SRC/site" "$FX/site"; rm -rf "$FX/site/data"
ln -s "$SRC/design" "$FX/design"; ln -s "$SRC/performance" "$FX/performance"
mkdir -p "$FX/audits/data/site"
# nonprofits: sample files promoted to a "real" export, then damaged
mkdir -p "$FX/nonprofits/data/site"
cp -R "$SRC/design/prototype/sample-data/nonprofits/." "$FX/nonprofits/data/site/"
mkdir -p "$FX/nonprofits/data/site/commentary"; cp "$SRC"/design/prototype/sample-data/commentary/np-*.json "$SRC"/design/prototype/sample-data/commentary/story_np.json "$FX/nonprofits/data/site/commentary/"
python3 - "$FX" <<'EOF'
import json, os, sys
fx = sys.argv[1]; d = f"{fx}/nonprofits/data/site"
m = json.load(open(f"{d}/meta.json")); m["sample"] = False; json.dump(m, open(f"{d}/meta.json", "w"))
os.remove(f"{d}/contracts/contracts.json")
f = json.load(open(f"{d}/finances/form990.json"))
for r in f["rows"][:40]: r.pop("fy", None)
json.dump(f, open(f"{d}/finances/form990.json", "w"))
# split payments into per-year files, as the contract asks for production
p = json.load(open(f"{d}/payments/cells.json")); os.remove(f"{d}/payments/cells.json")
for fy in sorted({c["fy"] for c in p["cells"]}):
    json.dump(dict(p, cells=[c for c in p["cells"] if c["fy"] == fy]), open(f"{d}/payments/cells_{fy}.json", "w"))
# network: export present but not flagged
n = f"{fx}/network/data/site"; os.makedirs(n, exist_ok=True)
nm = json.load(open(f"{fx}/design/prototype/sample-data/network/meta.json")); nm.pop("sample"); json.dump(nm, open(f"{n}/meta.json", "w"))
EOF
python3 "$FX/site/tools/bundle.py" --quiet | sed -n '/== nonprofits/,/== performance/p;/Summary/p;/Unavailable/p'
fail=0
dom() { perl -e 'alarm 60; exec @ARGV' "$CHROME" --headless=new --disable-gpu --window-size=1440,1000 --virtual-time-budget=7000 --dump-dom "$1" 2>/dev/null; }
expect() { # url, pattern, should (1=present, 0=absent), label
  local out; out=$(dom "$1")
  if print -r -- "$out" | grep -q "$2"; then got=1; else got=0; fi
  if [[ $got == $3 ]]; then echo "  PASS $4"; else echo "  FAIL $4"; fail=1; fi
}
F="file://$FX/site/index.html"
expect "$F?view=np-growth" "Analysis not available yet" 1 "np-growth blanks (contracts missing)"
expect "$F?view=np-dependency" "fails the data contract" 1 "np-dependency blanks (form990 invalid)"
expect "$F?view=np-pay" "Analysis not available yet" 1 "np-pay blanks (form990 invalid)"
expect "$F?view=np-flows" "Analysis not available yet" 0 "np-flows still renders"
expect "$F?view=np-flows" "sample-banner" 0 "np-flows has no sample banner (module is real)"
expect "$F?view=np-flows" "payment records" 1 "np-flows registers counts from the per-year payment files"
expect "$F?view=org&id=org-001" "Contracts: not available yet" 1 "org profile blanks only its contracts section"
expect "$F?view=org&id=org-001" "Payments by fiscal year and department" 1 "org profile keeps city money"
expect "$F?view=nw-overview" "sample-banner" 1 "network falls back to sample (meta not flagged)"
expect "$F?view=au-overview" "sample-banner" 1 "audits falls back to sample (no export)"
# http: serve the fixture root, the loader reads raw exports for real modules
PORT=8765
(cd "$FX" && perl -e 'alarm 120; exec @ARGV' python3 -m http.server $PORT >/dev/null 2>&1) &
SRV=$!; sleep 1
expect "http://127.0.0.1:$PORT/site/index.html?view=np-flows" "read from the export" 1 "http: np-flows reads the raw export (fetch path)"
expect "http://127.0.0.1:$PORT/site/index.html?view=np-growth&data=1" "Analysis not available yet" 1 "http: np-growth still blanks"
kill $SRV 2>/dev/null
[[ $fail == 0 ]] && echo "fixture test: all passed" || echo "fixture test: FAILURES"
exit $fail
