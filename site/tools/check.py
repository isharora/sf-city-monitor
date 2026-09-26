#!/usr/bin/env python3
"""Render every view of the site in light and dark with headless Chrome, capture console errors,
write screenshots to /tmp/scm_site/, and run the in-page self-test (?selftest=1).

  site/tools/check.sh                 # everything (bundle, screenshots, console, self-test)
  site/tools/check.sh --no-shots      # console + self-test only
  site/tools/check.sh --only np-      # states whose name starts with np-
Exit status 1 if any console error, render error or self-test failure.
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys
import html

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
OUT = "/tmp/scm_site"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE = ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1440,1000", "--no-first-run", "--no-default-browser-check"]
NOISE = re.compile(r"gpu|dbus|fontconfig|sandbox|ssl_client|registration|updater|trust|CVDisplayLink|task_policy|Fontations|DEPRECATED_ENDPOINT", re.I)

VIEWS = ["home", "search", "methods",
         "np-overview", "np-flows", "np-dependency", "np-pay", "np-growth", "np-reviews", "np-orgs",
         "pf-overview", "pf-spending", "pf-staffing", "pf-outcomes", "pf-cost", "pf-integrity", "pf-gaps", "pf-depts",
         "au-overview", "au-status", "au-time", "au-agreement", "au-repeat", "au-open", "au-reports",
         "nw-overview", "nw-graph", "nw-ban", "nw-behested", "nw-lobby", "nw-concentration", "nw-loop", "nw-entities"]


def chunk_rows(logical, key):
    """Read rows of a bundled logical file straight from its chunk scripts (for picking entity ids)."""
    man = json.load(open(os.path.join(SITE, "data", "manifest.json")))
    mod = logical.split("/")[0]
    mods = list(man["modules"].values()) + [{"module": "site", "files": man["site"]}]
    for m in mods:
        if m["module"] == mod:
            e = m["files"].get(logical)
            if not e or e["status"] != "ok":
                return []
            rows, enc = [], None
            for c in e["chunks"]:
                txt = open(os.path.join(SITE, c), encoding="utf-8").read()
                body = txt[txt.index(",", txt.index(",", txt.index(",") + 1) + 1) + 1: txt.rindex(");")]
                v = json.loads(body).get(key)
                if isinstance(v, dict) and v.get("__enc") == "cols":
                    enc = v
                if isinstance(v, dict):
                    rows.extend(v.get("rows", []))
                elif isinstance(v, list):
                    rows.extend(v)
            if enc:
                out = []
                for r in rows:
                    o = {}
                    for c2, x in zip(enc["cols"], r):
                        if x is None and c2 in enc.get("sparse", []):
                            continue
                        o[c2] = enc["dicts"][c2][x] if c2 in enc.get("dicts", {}) and x is not None else x
                    out.append(o)
                rows = out
            return rows
    return []


def states():
    out = [(v, f"view={v}" + ("&q=health" if v == "search" else "")) for v in VIEWS]
    orgs = chunk_rows("nonprofits/orgs/index.json", "orgs")
    if orgs:
        out.append(("org", "view=org&id=" + max(orgs, key=lambda o: o.get("city_total") or 0)["id"]))
    ents = chunk_rows("network/entities.json", "entities")
    con = next((e for e in ents if e.get("type") == "contractor"), None)
    off = next((e for e in ents if e.get("type") == "official"), None)
    if con:
        out.append(("org-contractor", "view=org&id=" + con["id"]))
    if off:
        out.append(("official", "view=official&id=" + off["id"]))
    site = chunk_rows("site/site.json", "departments")
    dept = next((d for d in site if d["id"] in ("DPH", "POL")), site[0] if site else None)
    if dept:
        out.append(("dept", "view=dept&id=" + dept["id"]))
    reps = chunk_rows("audits/reports/reports.json", "reports")
    if reps:
        out.append(("report", "view=report&id=" + reps[0]["id"]))
    out += [("story-np", "view=np-overview&mode=story&step=1"), ("story-pf", "view=pf-overview&mode=story&step=0"),
            ("data-panel", "view=np-flows&data=1"), ("graph-focus", "view=nw-graph&v.focus=" + (con["id"] if con else "")),
            ("filtered-np", "view=np-flows&dept=HSH&area=homeless&real=0"), ("unknown-org", "view=org&id=org-does-not-exist"),
            ("empty-filters", "view=au-status&years=2014-2014&topic=it&source=bla")]
    return out


def run_chrome(args, timeout=120):
    try:
        p = subprocess.run([CHROME] + args, capture_output=True, text=True, timeout=timeout)
        return p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT"


def console_lines(stderr):
    out = []
    for line in stderr.splitlines():
        if "CONSOLE" in line or "Uncaught" in line or line == "TIMEOUT":
            if NOISE.search(line):
                continue
            m = re.search(r'"(.*)", source: (\S+) \((\d+)\)', line)
            msg = f"{m.group(1)} ({os.path.basename(m.group(2))}:{m.group(3)})" if m else line.strip()
            level = "info" if ("[data]" in line or "INFO:CONSOLE" in line and not re.search(r"Error|Uncaught|failed|\[filters\]", line)) else "error"
            out.append((level, msg))
    return out


def shoot(name, query, theme, shots):
    url = f"file://{SITE}/index.html?{query}&theme={theme}"
    args = BASE + ["--virtual-time-budget=7000", "--enable-logging=stderr", "--v=0"]
    if shots:
        args.append(f"--screenshot={OUT}/{name}-{theme}.png")
    else:
        args.append("--dump-dom")
    _, err = run_chrome(args + [url])
    return name, theme, console_lines(err)


def selftest():
    url = f"file://{SITE}/index.html?selftest=1"
    dom, err = run_chrome(BASE + ["--virtual-time-budget=600000", "--enable-logging=stderr", "--v=0", "--dump-dom", url], timeout=600)
    m = re.search(r'<pre id="selftest-json"[^>]*>(.*?)</pre>', dom, re.S)
    if not m:
        return None, console_lines(err)
    return json.loads(html.unescape(m.group(1))), console_lines(err)


def main(argv):
    shots = "--no-shots" not in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else ""
    os.makedirs(OUT, exist_ok=True)
    if "--no-bundle" not in argv:
        r = subprocess.run([sys.executable, os.path.join(HERE, "bundle.py"), "--quiet"], capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)
    todo = [(n, q, t) for n, q in states() if n.startswith(only) for t in ("light", "dark")]
    problems = 0
    print(f"rendering {len(todo)} states ({'screenshots' if shots else 'console only'}) …")
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for name, theme, lines in ex.map(lambda a: shoot(*a, shots), todo):
            errs = [m for lvl, m in lines if lvl == "error"]
            if errs:
                problems += len(errs)
                print(f"  CONSOLE {name}-{theme}:")
                for m in errs[:6]:
                    print(f"      {m[:300]}")
    print(f"console: {'clean' if not problems else str(problems) + ' error line(s)'} across {len(todo)} renders" + (f"; screenshots in {OUT}/" if shots else ""))
    if "--no-selftest" not in argv and not only:
        res, lines = selftest()
        errs = [m for lvl, m in lines if lvl == "error"]
        if res is None:
            print("selftest: did not finish (no #selftest-json in the DOM)")
            for m in errs[:10]:
                print("   ", m[:300])
            problems += 1
        else:
            print(f"selftest: {res['pass']} passed, {res['fail']} failed")
            for r in res["results"]:
                if not r["pass"]:
                    print(f"   FAIL [{r['group']}] {r['name']}: {r['detail'][:300]}")
            problems += res["fail"]
            with open(os.path.join(OUT, "selftest.json"), "w") as fh:
                json.dump(res, fh, indent=1)
            print(f"selftest details: {OUT}/selftest.json")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
