#!/usr/bin/env python3
"""Fetch the SF Controller's Performance Program data (rerunnable).

Sources (all verified 2026-09-26):
  - data.sf.gov 6dpt-7w23  San Francisco Citywide Performance Metrics (current measure set,
    history back-filled FY2002..FY2028; targets + mid-year + full-year results)
  - data.sf.gov kc49-udxn  Scorecard Measures (monthly/annual actuals+targets, 86 scorecard measures)
  - data.sf.gov 5x94-tptc  Citywide Performance Measurement Annual Report FY13 (snapshot, 999 KPIs)
  - data.sf.gov 6h77-suve  Citywide Performance Measurement Annual Report FY14 (snapshot, 999 KPIs)
  - Annual performance report PDFs linked from https://www.sf.gov/san-francisco-performance-program
    (FY2006..FY2025). Dead sfcontroller.org links fall back to the Internet Archive (id_ raw capture).

Every network call is time-limited. Writes only to data/raw/perf_measures/.
"""
import json
import os
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw", "perf_measures")
PDF = os.path.join(OUT, "reports")
os.makedirs(PDF, exist_ok=True)

DATASETS = {
    "6dpt-7w23": "citywide_performance_metrics",
    "kc49-udxn": "scorecard_measures",
    "5x94-tptc": "annual_report_fy13",
    "6h77-suve": "annual_report_fy14",
}

# Links exactly as published on https://www.sf.gov/san-francisco-performance-program (fetched 2026-09-26)
REPORTS = {
    "FY2006_PerfMeas_All2006.pdf": "https://www.sfcontroller.org/ftp/uploadedfiles/controller/csa/performance/PerfMeas_All2006.pdf",
    "FY2007_PerfMeas_Dept061307.pdf": "https://www.sfcontroller.org/ftp/uploadedfiles/controller/csa/performance/PerfMeas_Dept061307.pdf",
    "FY2008_PM_0708Report.pdf": "https://www.sfcontroller.org/ftp/uploadedfiles/controller/reports/PM_0708Report.pdf",
    "FY2009_AnnualYearEndPM.pdf": "https://www.sfcontroller.org/ftp/uploadedfiles/controller/reports/AnnualPMReport%20.pdf",
    "FY2005_Performance_Report_narrative.pdf": "https://www.sfcontroller.org/ftp/uploadedfiles/controller/csa/full.pdf",
    "FY2010_AnnualYearEndPM.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/1427-AnnualYear-EndPerformanceMeasureFY09-10.pdf",
    "FY2011_AnnualYearEndPM.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/2708-Annual_Year_End_Performance_Measure_Report_FY2010.11.pdf",
    "FY2012_PM_Annual_Report.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/3669-PM%20Annual%20Report%20FY12%20FINAL%20v1%2001.pdf",
    "FY2013_City_Services_PM_Report.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/4957-City%20Services%20Performance%20Measure%20Report%20-%20FY%202013.pdf",
    "FY2014_Citywide_PM_Annual_Report.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/6040-Citywide%20Performance%20Measurement%20Program%20FY14%20Annual%20Report.pdf",
    "FY2015_Performance_Annual_Report.pdf": "https://sfcontroller.org/sites/default/files/FileCenter/Documents/6946-FY15%20Performance%20Annual%20Report%2011-20-15.pdf",
    "FY2016_Scorecards_Update_and_Measures.pdf": "https://sfcontroller.org/sites/default/files/Documents/Auditing/Performance%20Scorecards%20Update%20and%20FY16%20Measures%20Report%20final.pdf",
    "FY2017_Annual_Performance_Report.pdf": "https://sfcontroller.org/sites/default/files/Documents/Auditing/FY17%20Annual%20Performance%20Report%20_%20FINAL.pdf",
    "FY2018_Annual_Performance_Report.pdf": "https://sfcontroller.org/sites/default/files/Documents/Auditing/FY18%20Annual%20Performance%20Report%20FINAL.pdf",
    "FY2019_Annual_Performance_Report.pdf": "https://sfcontroller.org/sites/default/files/Documents/Auditing/FY19%20Annual%20Performance%20Report%202019-12-10.pdf",
    "FY2022_APR_with_Appendix.pdf": "https://www.sf.gov/sites/default/files/2022-12/FY22-APR%20Final%20Report%20w%20Appendix-12.5.22.pdf",
    "FY2023_APR.pdf": "https://www.sf.gov/sites/default/files/2023-12/FY23APRfinal.pdf",
    "FY2024_APR.pdf": "https://www.sf.gov/documents/48224/FY24_APR_FINAL_mBS1s7d.pdf",
    "FY2025_APR.pdf": "https://media.api.sf.gov/documents/FY25_APR_Final.pdf",
    # Mayor's proposed budget book (dept performance measures + FTE tables), linked from the same page
    "BudgetBook_FY27_FY28_Mayor_Proposed.pdf": "https://media.api.sf.gov/documents/Mayors_June_1st_Proposed_FY27_and_FY28_Budget_Budget_Book.pdf",
}

UA = "Mozilla/5.0 (SF City Monitor research)"


def curl(url, dest, secs=300):
    tmp = dest + ".tmp"
    cmd = ["perl", "-e", f"alarm {secs}; exec @ARGV", "curl", "-s", "-L", "-f", "-A", UA,
           "-o", tmp, url]
    r = subprocess.run(cmd)
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 0:
        os.replace(tmp, dest)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def is_pdf(path):
    with open(path, "rb") as f:
        return f.read(5) == b"%PDF-"


def wayback(url):
    q = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    tmp = os.path.join(OUT, ".wb.json")
    if not curl(q, tmp, 60):
        return None
    try:
        snap = json.load(open(tmp)).get("archived_snapshots", {}).get("closest")
    finally:
        os.remove(tmp)
    if snap and snap.get("available"):
        ts = snap["timestamp"]
        return f"https://web.archive.org/web/{ts}id_/{url}"
    return None


def main():
    log = []
    for dsid, name in DATASETS.items():
        ok = curl(f"https://data.sf.gov/api/views/{dsid}.json", os.path.join(OUT, f"meta_{dsid}.json"), 60)
        ok &= curl(f"https://data.sf.gov/api/views/{dsid}/rows.csv?accessType=DOWNLOAD",
                   os.path.join(OUT, f"{name}.csv"), 600)
        log.append({"source": dsid, "file": f"{name}.csv", "ok": bool(ok)})
        print(dsid, name, "ok" if ok else "FAIL")
    for fname, url in REPORTS.items():
        dest = os.path.join(PDF, fname)
        if os.path.exists(dest) and is_pdf(dest):
            log.append({"source": url, "file": fname, "ok": True, "via": "cached"})
            continue
        via = "direct"
        ok = curl(url, dest) and is_pdf(dest)
        if not ok:
            if os.path.exists(dest):
                os.remove(dest)
            wb = wayback(url)
            via = wb or "none"
            ok = bool(wb) and curl(wb, dest) and is_pdf(dest)
            if not ok and os.path.exists(dest):
                os.remove(dest)
        log.append({"source": url, "file": fname, "ok": bool(ok), "via": via})
        print(fname, "ok" if ok else "FAIL", via)
    json.dump(log, open(os.path.join(OUT, "fetch_log.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
