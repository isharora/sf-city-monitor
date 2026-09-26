"""Parse per-contractor final monitoring status from the appendices of the Controller's
Citywide Nonprofit Monitoring annual reports (FY22-FY25), and join standard-level unresolved
findings from the published datasets. Output: data/reviews/monitoring_data/monitoring_status.json"""
import re, json, csv, pathlib, collections, openpyxl
base = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews"
T = base / "text"; M = base / "monitoring_data"

def pages(name):
    t = (T / name).read_text(); parts = re.split(r"=== PAGE (\d+) ===", t)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]

STAT = {
 "FY22": r"Complete \(No Findings\)|Findings In Conformance|Findings Not in Conformance|Not Complete",
 "FY23": r"Complete \(No Findings\)|Findings In Conformance|Findings Not in Conformance|Not Complete",
 "FY24": r"No Findings|Findings Not in Conformance|Waiver|Incomplete|Not Complete",
 "FY25": r"No Findings|Findings Not in\s+Conformance|Waiver|Incomplete",
}
CFG = {  # file, first page of appendix table, last page, start marker regex
 "FY22": ("monitoring_FY22_annual_report.txt", r"Final Monitoring Results\s*\n"),
 "FY23": ("monitoring_FY23_annual_report.txt", r"Monitoring Final Monitoring Status\s*\n"),
 "FY24": ("monitoring_FY24_annual_report.txt", r"Final Status\s*\n"),
 "FY25": ("monitoring_FY25_annual_report.txt", r"Prior Year Final\s*\nStatus \(FY24\)\s*\n"),
}
END = {"FY22": None, "FY23": r"Appendix E", "FY24": r"APPENDIX C", "FY25": None}
PRIOR = r"(?:No Findings|Findings Not in\s+Conformance|Waiver|Incomplete|Not Monitored|Not Complete)"

def parse(fy):
    fname, start = CFG[fy]
    pg = pages(fname)
    # locate appendix start
    full = ""; pmap = []
    started = False
    for n, txt in pg:
        if not started:
            m = re.search(start, txt)
            if m and (fy != "FY24" or "CONTRACTORS BY TYPE OF MONITORING" in txt) and (fy != "FY22" or "Contractor's Name" in txt):
                started = True; txt = txt[m.end():]
            else:
                continue
        if END[fy] and re.search(END[fy], txt):
            txt = txt[:re.search(END[fy], txt).start()]
            pmap.append((len(full), n)); full += txt + "\n"; break
        txt = re.sub(r"^\s*\d+ \| Citywide Nonprofit Monitoring[^\n]*\n", "", txt)
        txt = re.sub(r"Appendix E: Contractors by Type of\s*\nMonitoring and Final Monitoring Results,\s*\nFY22\s*\n", "", txt)
        txt = re.sub(r"Contractor Name Type of\s*\nMonitoring\s*\nFY25 Final Status FY25 Fiscal\s*\nFindings\s*\nFY25 Compliance\s*\nFindings\s*\nPrior Year Final\s*\nStatus \(FY24\)\s*\n", "", txt)
        pmap.append((len(full), n)); full += txt + "\n"
    if fy == "FY25":
        pat = re.compile(r"\s*(?P<name>.+?)\s+(?P<type>Core|Expanded|Waiver)(?P<late>\s*\*)?\s+(?P<status>%s)\s+(?P<fis>\d+)\s+(?P<comp>\d+)\s+(?P<prior>%s)" % (STAT[fy], PRIOR), re.S)
    else:
        pat = re.compile(r"\s*(?P<name>.+?)\s+(?P<type>Core|Expanded|Waiver)(?P<late>\s*\*)?\s+(?P<status>%s)[ \t]*(?:\n|$)" % STAT[fy], re.S)
    out = []; pos = 0
    while True:
        m = pat.match(full, pos)
        if not m: break
        page = max(p for off, p in pmap if off <= m.start("name"))
        d = {k: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v for k, v in m.groupdict().items()}
        d["late"] = bool(m.group("late")); d["page"] = page
        d["raw"] = re.sub(r"\s+", " ", m.group(0)).strip()
        out.append(d); pos = m.end()
    rest = full[pos:pos + 300].strip()
    return out, rest

def norm(n):
    n = n.lower().replace("&", "and").replace("*", "")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\b(inc|the|dba|llc)\b", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return re.sub(r"(youth) homey$", r"\1", n)

def unresolved():
    """fy -> org(lower) -> list of (category, description) not yet in conformance on required standards"""
    res = collections.defaultdict(lambda: collections.defaultdict(list))
    wb = openpyxl.load_workbook(M / "fy22_dataset.xlsx", read_only=True)
    for r in list(wb["FY21-22 Dataset"].iter_rows(values_only=True))[1:]:
        if r[3] == "Not Yet in Conformance" and r[5] == "Standard": res["FY22"][norm(r[0])].append((r[4], r[6]))
    wb = openpyxl.load_workbook(M / "fy23_dataset.xlsx", read_only=True)
    for r in list(wb["FY22-23 Data Set "].iter_rows(values_only=True))[1:]:
        if r[0] and r[4] == "Not Yet In Conformance" and r[6] == "Standard": res["FY23"][norm(r[0])].append((r[5], r[7]))
    for fy, f in [("FY24", "3v2z-djjd.csv"), ("FY25", "7yeh-dyn4.csv")]:
        for r in csv.DictReader(open(M / f)):
            if r["Final Status"] == "Not Yet In Conformance" and r["Standard Type"] == "Standard":
                res[fy][norm(r["Contractor Name"])].append((r["Standard Category"], r["Standard Description"]))
    return res

if __name__ == "__main__":
    U = unresolved(); allrows = {}
    for fy in ["FY22", "FY23", "FY24", "FY25"]:
        rows, rest = parse(fy)
        c = collections.Counter(r["status"] for r in rows)
        un = U[fy]; matched = 0
        for r in rows:
            k = norm(r["name"])
            r["unresolved"] = un.get(k, [])
            if r["unresolved"]: matched += 1
        notin = sum(1 for r in rows if "Not in" in r["status"])
        missing = [k for k in un if k not in {norm(r["name"]) for r in rows}]
        print(fy, len(rows), dict(c), "| not-in-conf:", notin, "matched to dataset:", matched, "| dataset orgs unmatched:", missing[:10], "| leftover:", rest[:120].replace("\n", " "))
        allrows[fy] = rows
    json.dump(allrows, open(M / "monitoring_status.json", "w"), indent=1)
