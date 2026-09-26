"""Verify that every number in the nonprofits commentary traces to the exported data or to redteam.json.

How it works
  1. 18_commentary.py pulls every number it prints from a registry of named values (site:*, facts:*, meta:*,
     rt:* for redteam.json, const:* for definitional thresholds) and writes data/redteam/commentary_trace.json:
     printed token -> the keys whose value produced it.
  2. This script extracts every numeric token from every commentary text field (headline, paragraphs,
     annotations, templates and fallbacks, caveats, story titles and texts). For each token it takes the
     writer's declared keys and RE-RESOLVES each key itself: site:* values are recomputed here, independently,
     from data/site/*.json; facts:/meta:/rt: keys are read from data/site/commentary_facts.json, meta.json and
     data/redteam/redteam.json; const:* are the thresholds listed below with their source. The token passes
     only if a declared key's re-resolved value rounds to the printed token (money, percent, count, decimal,
     'N times'). A token with no declared key passes only if it is a fiscal or calendar year inside the data's
     range (meta.fiscal_years).
Writes data/redteam/verify_report.json (every token with the key and value it traced to); exits 1 if any token is
untraced.
"""
import glob, json, os, re, statistics as st, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "data", "site")
RED = os.path.join(HERE, "..", "data", "redteam")
J = lambda p: json.load(open(os.path.join(SITE, p)))

CONSTANTS = {  # definitional thresholds written literally in the text, with their source
    "top_n": (20, "top-20 definition (np-flows 'Top 20 organizations' card; design spec 5.2)"),
    "dependency_threshold": (0.75, "high-dependency threshold (np-dependency view: share > 75%)"),
    "full_share": (1.0, "a city share of 100% of total revenue"),
    "recipient_threshold": (1e6, "$1 million recipient threshold (dependency population)"),
    "large_dependent_threshold": (5e6, "$5 million 'large and dependent' threshold (np-dependency view)"),
}
NAMED = [r"Tier [23]", r"HealthRIGHT 360", r"Form 990(?:-EZ)?", r"Part VII", r"Medi-Cal"]
TOKEN = re.compile(r"(?P<money>\$\d[\d,]*(?:\.\d+)?(?:\s(?:billion|million))?)|(?P<fy>\bFY\d{4}\b)|(?P<pct>\d+(?:\.\d+)?%)|"
                   r"(?P<times>\d+(?:\.\d+)?\s(?:times|×))|(?P<num>\d[\d,]*(?:\.\d+)?)")


def site_values():
    """Independent recomputation of every 'site:' key from the exported files."""
    V = {}
    meta = J("meta.json"); idx = meta["deflator"]["index"]
    cells = [c for f in sorted(glob.glob(os.path.join(SITE, "payments", "cells_*.json"))) for c in json.load(open(f))["cells"]]
    tot = defaultdict(float); dept = defaultdict(float); byo = defaultdict(lambda: defaultdict(float)); pay = defaultdict(float)
    for c in cells:
        tot[c["fy"]] += c["amt"]; dept[(c["dept"], c["fy"])] += c["amt"]; byo[c["fy"]][c["org"]] += c["amt"]; pay[(c["org"], c["fy"])] += c["amt"]
    V["total_fy2016"] = tot[2016]; V["total_fy2016_real2025"] = tot[2016] / idx["2016"]
    V["top_org_fy2025"] = max(byo[2025].values())
    d = sorted((v for (k, fy), v in dept.items() if fy == 2025), reverse=True)
    V["top3_dept_share_fy2025"] = sum(d[:3]) / tot[2025]
    for code, fy in (("HOM", 2025), ("DPH", 2025), ("DEC", 2025), ("HOM", 2019)):
        V[f"{code}_fy{fy}"] = dept[(code, fy)]
    tr = {r["fiscal_year"]: r for r in J("aggregates/trends.json")["rows"]}
    V["orgs_paid_fy2016"] = tr[2016]["n_orgs_paid"]; V["orgs_paid_fy2025"] = tr[2025]["n_orgs_paid"]
    ds = {r["department_code"]: r["nonprofit_share_of_vendor_spend"] for r in J("aggregates/departments.json")["rows"] if r["fiscal_year"] == 2025}
    for k in ("HOM", "DEC", "CHF", "DPH"):
        V[f"dshare_{k}_2025"] = ds[k]
    ov = {(r["measure"], r["fiscal_year"]): r["value"] for r in J("aggregates/outcomes.json")["rows"]}
    V["beds_change_2023_2025"] = ov[("shelter_beds", 2025)] / ov[("shelter_beds", 2023)] - 1
    V["pit_unsheltered_change_2019_2026"] = ov[("pit_unsheltered", 2026)] / ov[("pit_unsheltered", 2019)] - 1
    V["pit_total_2019"] = ov[("pit_total", 2019)]; V["pit_total_2026"] = ov[("pit_total", 2026)]
    facts = J("commentary_facts.json")
    V["pay_elasticity_doubling"] = 2 ** facts["comp_elasticity"] - 1
    big = [r for r in J("finances/form990_2024.json")["rows"] if r["total_revenue"] > 0 and pay[(r["org"], 2024)] >= 1e6]
    ex = [r["exec_comp"] for r in big if r["exec_comp"]]; rs = [r["months_reserves"] for r in big if r["months_reserves"] is not None]
    V.update({"fy2024_ge1m_median_pay": st.median(ex), "fy2024_ge1m_with_pay": len(ex), "fy2024_ge1m_median_reserves": st.median(rs),
              "fy2024_ge1m_with_reserves": len(rs), "fy2024_ge1m_reserves_lt1": sum(x < 1 for x in rs), "fy2024_ge1m_reserves_negative": sum(x < 0 for x in rs)})
    fr = J("reviews/findings.json")["rows"]
    per = [sum(1 for r in fr if r["fy"] == y) for y in (2022, 2023, 2024, 2025)]
    V.update({"monitoring_org_years": len(fr), "monitoring_share_none": sum(r["result"] == "none" for r in fr) / len(fr),
              "orgs_ever_severe": len({r["org"] for r in fr if r["result"] in ("corrective", "elevated", "redflag")}),
              "orgs_ever_elevated_redflag": len({r["org"] for r in fr if r["result"] in ("elevated", "redflag")}),
              "monitoring_min_per_year_2022_2025": min(per), "monitoring_max_per_year_2022_2025": max(per)})
    con = J("contracts/contracts.json")["contracts"]
    V["contracts_emergency_share"] = sum(c["agreed"] for c in con if c["authority_class"] == "emergency_or_waiver") / sum(c["agreed"] for c in con)
    return V


def resolve(key, V, rt, facts, meta):
    kind, _, rest = key.partition(":")
    if kind == "site":
        return V.get(rest), "recomputed here from data/site"
    if kind == "facts":
        return facts.get(rest), "data/site/commentary_facts.json"
    if kind == "meta":
        return meta.get(rest), "data/site/meta.json"
    if kind == "const":
        v, src = CONSTANTS[rest]
        return v, "definition: " + src
    if kind == "rt":
        fid, _, path = rest.partition(".")
        f = next((x for x in rt["findings"] if x["id"] == fid), None)
        if f is None:
            return None, None
        if path.startswith("cite."):
            return f["cite"].get(path[5:]), f"redteam.json {fid}.cite"
        if path == "checks.first_observed_later":
            return next(c["result"][1] for c in f["checks"] if c["check"].startswith("First observed in April 2021")), f"redteam.json {fid}.checks"
        if path == "checks.confidence_median":
            return next(c["result"][0] for c in f["checks"] if c["check"].startswith("Classification confidence")), f"redteam.json {fid}.checks"
    return None, None


def value_matches(tok, kind, v):
    if v is None or isinstance(v, bool):
        return False
    v = float(v)
    if kind == "money":
        m = re.match(r"\$([\d,]+(?:\.(\d+))?)(?:\s(billion|million))?", tok)
        num = float(m.group(1).replace(",", "")); dec = len(m.group(2) or ""); unit = {"billion": 1e9, "million": 1e6, None: 1}[m.group(3)]
        tol = (0.5 * 10 ** -dec) * unit if unit > 1 else (500 if num >= 1e4 and num % 1000 == 0 else 0.5)
        return abs(v - num * unit) <= tol + 1e-6
    if kind == "pct":
        num = float(tok[:-1]); dec = len(tok[:-1].split(".")[1]) if "." in tok else 0
        return abs(abs(v) * 100 - num) <= 0.5 * 10 ** -dec + 1e-9
    if kind == "times":
        return abs(v - float(tok.split()[0])) <= 0.5
    if kind == "fy":
        return v == float(tok[2:])
    num = float(tok.replace(",", "")); dec = len(tok.split(".")[1]) if "." in tok else 0
    return abs(v - num) <= (0.5 * 10 ** -dec + 1e-9 if dec else (0.5 if v != int(v) else 1e-9))


def texts(obj):
    out = []
    if "steps" in obj:
        for i, s in enumerate(obj["steps"]):
            out += [(f"steps[{i}].title", s["title"]), (f"steps[{i}].text", s["text"])]
        return out
    out.append(("headline", obj.get("headline") or ""))
    out += [(f"paragraphs[{i}]", p) for i, p in enumerate(obj.get("paragraphs", []))]
    out += [(f"annotations[{i}].text", a["text"]) for i, a in enumerate(obj.get("annotations", []))]
    for i, t in enumerate(obj.get("templates", [])):
        out += [(f"templates[{i}].template", t["template"]), (f"templates[{i}].fallback", t.get("fallback") or "")]
    out += [(f"caveats[{i}]", c["text"]) for i, c in enumerate(obj.get("caveats", []))]
    return out


def main():
    meta = J("meta.json"); facts = J("commentary_facts.json"); rt = json.load(open(os.path.join(RED, "redteam.json")))
    trace = json.load(open(os.path.join(RED, "commentary_trace.json")))
    V = site_values()
    ymin, ymax = meta["fiscal_years"]["min"], meta["fiscal_years"]["max"]
    report, untraced = [], 0
    for f in sorted(glob.glob(os.path.join(SITE, "commentary", "*.json"))):
        obj = json.load(open(f))
        for field, text in texts(obj):
            t = re.sub(r"\{\w+\}", " ", text)
            for nm in NAMED:
                t = re.sub(nm, " ", t)
            for m in TOKEN.finditer(t):
                kind, tok = m.lastgroup, m.group(0).rstrip(",.")
                look = tok.split()[0] if kind == "times" else tok[2:] if kind == "fy" else tok
                ok = None
                for key in trace.get(look, []):
                    v, src = resolve(key, V, rt, facts, meta)
                    if value_matches(tok, kind, v):
                        ok = f"{key} = {v:g} ({src})"
                        break
                if ok is None and kind in ("fy", "num") and re.fullmatch(r"(FY)?\d{4}", tok) and ymin <= int(tok[-4:]) <= ymax:
                    ok = f"year within the data range FY{ymin}-FY{ymax} (meta.fiscal_years)"
                report.append({"file": os.path.basename(f), "field": field, "token": tok, "kind": kind, "traced_to": ok})
                untraced += ok is None
    cnt = lambda p: sum(1 for r in report if r["traced_to"] and r["traced_to"].startswith(p))
    summary = {"tokens": len(report), "untraced": untraced, "redteam": cnt("rt:"), "site_data": cnt(("site:", "facts:", "meta:")),
               "definitions": cnt("const:"), "years": cnt("year within")}
    json.dump({"summary": summary, "tokens": report}, open(os.path.join(RED, "verify_report.json"), "w"), indent=1)
    for r in report:
        if r["traced_to"] is None:
            print("UNTRACED", r["file"], r["field"], r["token"])
    print(json.dumps(summary))
    sys.exit(1 if untraced else 0)


if __name__ == "__main__":
    main()
