#!/usr/bin/env python3
"""Fetch context series: CPI deflators (BLS) and San Francisco population.

Outputs (performance/data/raw/context/):
  bls_raw_<series>.csv   every BLS observation (year, period, value, footnote)
  cpi_fy.csv             fiscal-year average index (FY = July..June, labeled by ending year)
  population*.csv        see fetch_population()

Every network call goes through curl wrapped in `perl -e 'alarm N'` (RULES.md).
Rerunnable: raw responses are cached in context/cache/; delete to refresh.
"""
import json, os, subprocess, sys, time
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CTX = os.path.join(HERE, "..", "data", "raw", "context")
CACHE = os.path.join(CTX, "cache")
os.makedirs(CACHE, exist_ok=True)


def fetch(url, dest, timeout=90, refresh=False, post_json=None):
    """Download url to dest with a hard timeout. Returns path or None."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0 and not refresh:
        return dest
    tmp = dest + ".tmp"
    extra = []
    if post_json is not None:
        extra = ["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(post_json)]
    r = subprocess.run(["perl", "-e", f"alarm {timeout}; exec @ARGV", "curl", "-s", "-f", "-L",
                        "-A", "Mozilla/5.0 (research; sf-city-monitor)", "-o", tmp] + extra + [url])
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, dest)
        return dest
    if os.path.exists(tmp):
        os.remove(tmp)
    print(f"FAIL {url} rc={r.returncode}", file=sys.stderr)
    return None


# ---------------------------------------------------------------- CPI
SERIES = {"bay": "CUURS49BSA0",   # CPI-U, San Francisco-Oakland-Hayward, all items, NSA, 1982-84=100
          "us": "CUUR0000SA0"}    # CPI-U, U.S. city average, all items, NSA, 1982-84=100


def fetch_bls(series, start=1996, end=2026):
    """BLS API v1 (no key): POST JSON, <=10 years per request. (GET query params are ignored.)"""
    rows = []
    y = start
    while y <= end:
        y2 = min(y + 9, end)
        dest = os.path.join(CACHE, f"bls_{series}_{y}_{y2}.json")
        p = fetch("https://api.bls.gov/publicAPI/v1/timeseries/data/", dest, refresh=(y2 >= end - 1),
                  post_json={"seriesid": [series], "startyear": str(y), "endyear": str(y2)})
        if p:
            d = json.load(open(p))
            if d.get("status") != "REQUEST_SUCCEEDED":
                print("BLS error", series, y, d.get("message"), file=sys.stderr)
                os.remove(p)
            else:
                for s in d["Results"]["series"]:
                    for o in s["data"]:
                        fn = "; ".join(f.get("text", "") for f in o.get("footnotes", []) if f)
                        rows.append(dict(series=series, year=int(o["year"]), period=o["period"],
                                         value=o["value"], footnote=fn))
        time.sleep(1.0)
        y = y2 + 1
    df = pd.DataFrame(rows).drop_duplicates(["series", "year", "period"]).sort_values(["year", "period"])
    df.to_csv(os.path.join(CTX, f"bls_raw_{series}.csv"), index=False)
    return df


BLS_UA = "sf-city-monitor research (contact: research@example.org)"  # BLS blocks default agents


def load_bls_flatfile():
    """Primary CPI source: BLS LABSTAT flat file cu.data.2.Summaries (contains all-items
    indexes for U.S. city average and metro areas). Falls back to cached API responses."""
    dest = os.path.join(CACHE, "cu.data.2.Summaries")
    if not os.path.exists(dest):
        tmp = dest + ".tmp"
        r = subprocess.run(["perl", "-e", "alarm 180; exec @ARGV", "curl", "-s", "-f", "-L", "-A", BLS_UA,
                            "-o", tmp, "https://download.bls.gov/pub/time.series/cu/cu.data.2.Summaries"])
        if r.returncode != 0:
            raise SystemExit("could not download BLS flat file")
        os.replace(tmp, dest)
    df = pd.read_csv(dest, sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip()
    df = df.rename(columns={"series_id": "series", "footnote_codes": "footnote"})
    df["year"] = df.year.astype(int)
    out = {}
    for label, sid in SERIES.items():
        d = df[df.series == sid][["series", "year", "period", "value", "footnote"]].copy()
        d.to_csv(os.path.join(CTX, f"bls_raw_{sid}.csv"), index=False)
        out[label] = d
    return out


def monthly(df):
    m = df[df.period.str.match(r"M(0[1-9]|1[0-2])$")].copy()
    m["value"] = pd.to_numeric(m["value"], errors="coerce")
    m["month"] = m.period.str[1:].astype(int)
    m["date"] = pd.to_datetime(dict(year=m.year, month=m.month, day=1))
    return m.sort_values("date")


def fy_average(df, label, expected_months):
    """FY (Jul y-1 .. Jun y, labeled y) average of the index.
    Missing observations INSIDE the published schedule (e.g. Oct 2025, not collected during the
    2025 federal funding lapse) are filled by log-linear interpolation between neighbors and flagged."""
    m = monthly(df)
    m = m[m.month.isin(expected_months)].set_index("date")
    m["interpolated"] = m.value.isna()
    lv = m.value.apply(lambda v: None if pd.isna(v) else __import__("math").log(v)).astype(float)
    lv = lv.interpolate(method="time", limit_area="inside")
    m["value_filled"] = lv.apply(lambda v: None if pd.isna(v) else __import__("math").exp(v))
    m["fy"] = m.year + (m.month >= 7).astype(int)
    m = m.dropna(subset=["value_filled"])
    g = m.groupby("fy").agg(**{f"{label}_cpi_fyavg": ("value_filled", "mean"),
                               f"{label}_n_obs": ("value_filled", "size"),
                               f"{label}_n_interpolated": ("interpolated", "sum")})
    g[f"{label}_complete"] = g[f"{label}_n_obs"] == len(expected_months)
    return g


def build_cpi():
    raw = load_bls_flatfile()
    # Bay Area: bimonthly (even months) since 1998; monthly 1987-1997. Use even months throughout
    # so every FY average uses the same six-point schedule (Aug, Oct, Dec, Feb, Apr, Jun).
    bay = fy_average(raw["bay"], "bay", [2, 4, 6, 8, 10, 12])
    us = fy_average(raw["us"], "us", list(range(1, 13)))
    out = bay.join(us, how="outer")
    out = out[(out.index >= 1998)]
    notes = []
    for fy, r in out.iterrows():
        n = []
        if r.get("bay_n_interpolated", 0) > 0:
            n.append(f"bay: {int(r.bay_n_interpolated)} obs interpolated (Oct 2025 not collected, 2025 funding lapse)")
        if r.get("us_n_interpolated", 0) > 0:
            n.append(f"us: {int(r.us_n_interpolated)} obs interpolated")
        if not r.bay_complete:
            n.append(f"bay PARTIAL FY: {int(r.bay_n_obs)} of 6 obs - do not use for deflation")
        if not r.us_complete:
            n.append(f"us PARTIAL FY: {int(r.us_n_obs)} of 12 obs - do not use for deflation")
        notes.append("; ".join(n))
    out["method_notes"] = notes
    # Rebase: multiplier to convert nominal FY dollars into latest-complete-FY dollars
    base = int(out[out.bay_complete & out.us_complete].index.max())
    out["bay_to_base_multiplier"] = out.loc[base, "bay_cpi_fyavg"] / out.bay_cpi_fyavg
    out["us_to_base_multiplier"] = out.loc[base, "us_cpi_fyavg"] / out.us_cpi_fyavg
    out["base_fy"] = base
    out.index.name = "fy"
    out.round(4).to_csv(os.path.join(CTX, "cpi_fy.csv"))
    print(out.round(3).to_string())
    return out


# ---------------------------------------------------------------- POPULATION
def read_xlsx_sheet(path, sheet_index):
    """Minimal .xlsx reader (openpyxl not installed): returns list of rows (lists of str)."""
    import zipfile, re
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    # map sheet order -> file via workbook rels
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rmap = {r.get("Id"): r.get("Target") for r in rels}
    sheets = wb.find("m:sheets", ns)
    sh = list(sheets)[sheet_index]
    rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    target = rmap[rid].lstrip("/")
    target = target if target.startswith("xl/") else "xl/" + target
    root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter("{%s}row" % ns["m"]):
        vals = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r"); col = re.match(r"[A-Z]+", ref).group()
            ci = 0
            for ch in col:
                ci = ci * 26 + (ord(ch) - 64)
            t = c.get("t"); v = c.find("m:v", ns)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
            else:
                val = v.text if v is not None else ""
            vals[ci - 1] = val
        if vals:
            rows.append([vals.get(k, "") for k in range(max(vals) + 1)])
    return rows


DOF_BASE = "https://dof.ca.gov/media/docs/forecasting/Demographics/estimates/"
DOF_FILES = {
    "E-4_90-00": "e-4-revised-historical-city-county-and-state-population-estimates-1991-2000-with-1990-and-2000-census-counts/E-4_90-00_Rpt.xlsx",
    "E-4_00-10": "estimates-e4-2000-2010/E4_2000-2010_Report_Final_EOC_000.xlsx",
    "E-4_10-20": "e-4-population-estimates-for-cities-counties-and-the-state-2011-2020-with-2010-and-2020-census-benchmark/E-4_2010-2020-Internet-Version.xlsx",
    "E-4_21-26": "e-4-population-estimates-for-cities-counties-and-the-state-2021-2026-with-2020-census-benchmark/E-4_2026_InternetVersion.xlsx",
}

CENSUS_BASE = "https://www2.census.gov/programs-surveys/popest/"
CENSUS_FILES = {
    # file -> (url, description)
    "99c8_06.txt": (CENSUS_BASE + "tables/1990-2000/counties/totals/99c8_06.txt",
                    "CO-99-8 postcensal July 1 1990-1999 (NOT revised to Census 2000)"),
    "co-est00int-tot.csv": (CENSUS_BASE + "datasets/2000-2010/intercensal/county/co-est00int-tot.csv",
                            "Intercensal July 1 2000-2009"),
    "cc-est2020int-alldata-06.csv": (CENSUS_BASE + "datasets/2010-2020/intercensal/county/asrh/cc-est2020int-alldata-06.csv",
                                     "Intercensal July 1 2010-2019 (YEAR=2..11)"),
    "co-est2025-alldata.csv": (CENSUS_BASE + "datasets/2020-2025/counties/totals/co-est2025-alldata.csv",
                               "Vintage 2025 postcensal July 1 2020-2025"),
}


def excel_date(v):
    try:
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(v)))).date()
    except Exception:
        return pd.to_datetime(v).date()


def build_population(fetch_fn=None, ctx=None, cache=None):
    fetch_fn = fetch_fn or fetch
    recs = []
    # ---- DOF E-4 (January 1 estimates; census counts on April 1 of census years)
    for key, rel in DOF_FILES.items():
        dest = os.path.join(CACHE, "dof_" + os.path.basename(rel))
        fetch_fn(DOF_BASE + rel, dest, timeout=120)
        idx = 0 if key == "E-4_90-00" else 1
        rows = read_xlsx_sheet(dest, idx)
        hdr = next(r for r in rows if r and str(r[0]).strip().upper() in ("COUNTY", "STATE/COUNTY"))
        sf = next(r for r in rows if r and str(r[0]).strip() == "San Francisco")
        for h, v in zip(hdr[1:], sf[1:]):
            if not str(h).strip() or not str(v).strip() or str(h).startswith("Column"):
                continue
            d = excel_date(h)
            recs.append(dict(source="CA DOF " + key, reference_date=str(d), year=d.year,
                             population=int(float(v)),
                             kind="census count" if d.month == 4 else "Jan 1 estimate",
                             url=DOF_BASE + rel))
    # ---- Census PEP (July 1)
    for f, (url, desc) in CENSUS_FILES.items():
        dest = os.path.join(CACHE, f)
        fetch_fn(url, dest, timeout=180)
        if f == "99c8_06.txt":
            line = next(l for l in open(dest, encoding="latin1") if l.startswith("1  06075"))
            nums = [int(x.replace(",", "")) for x in line.split()[2:13]]
            for k, yr in enumerate(range(1999, 1989, -1)):
                recs.append(dict(source="Census " + desc, reference_date=f"{yr}-07-01", year=yr,
                                 population=nums[k], kind="Jul 1 estimate", url=url))
        elif f == "cc-est2020int-alldata-06.csv":
            d = pd.read_csv(dest, encoding="latin1")
            r = d[(d.COUNTY == 75) & (d.AGEGRP == 0)]
            for _, x in r.iterrows():
                if 2 <= x.YEAR <= 11:
                    yr = 2010 + int(x.YEAR) - 2
                    recs.append(dict(source="Census " + desc, reference_date=f"{yr}-07-01", year=yr,
                                     population=int(x.TOT_POP), kind="Jul 1 estimate", url=url))
        else:
            d = pd.read_csv(dest, encoding="latin1", dtype={"STATE": str, "COUNTY": str})
            r = d[(d.STATE.str.zfill(2) == "06") & (d.COUNTY.str.zfill(3) == "075")].iloc[0]
            for c in r.index:
                if c.startswith("POPESTIMATE") and c[11:].isdigit():
                    yr = int(c[11:])
                    if f == "co-est00int-tot.csv" and yr >= 2010:
                        continue  # 2010 taken from 2010-2020 intercensal
                    recs.append(dict(source="Census " + desc, reference_date=f"{yr}-07-01", year=yr,
                                     population=int(r[c]), kind="Jul 1 estimate", url=url))
    pop = pd.DataFrame(recs).drop_duplicates(["source", "reference_date"])
    pop = pop.sort_values(["reference_date", "source"])
    pop.to_csv(os.path.join(CTX, "population.csv"), index=False)

    # ---- fiscal-year series. PRIMARY = DOF Jan 1 of the FY's ending year (the FY midpoint).
    dof = pop[(pop.source.str.startswith("CA DOF")) & (pop.kind == "Jan 1 estimate")]
    dof = dof.drop_duplicates("year", keep="last").set_index("year").population
    cen = pop[pop.source.str.startswith("Census")].drop_duplicates("year", keep="last").set_index("year").population
    fys = range(1999, 2029)
    rows = []
    for fy in fys:
        c0, c1 = cen.get(fy - 1), cen.get(fy)
        rows.append(dict(fy=fy,
                         pop_dof_jan1=dof.get(fy),
                         pop_census_mid=(c0 + c1) / 2 if c0 is not None and c1 is not None else None,
                         pop_census_jul1_start=c0))
    fy = pd.DataFrame(rows)
    fy["population_primary"] = fy.pop_dof_jan1
    fy["primary_note"] = "CA DOF E-4 Jan 1 of FY ending year (FY midpoint)"
    last = fy.dropna(subset=["pop_dof_jan1"]).fy.max()
    m = fy.fy > last
    fy.loc[m, "population_primary"] = fy.loc[fy.fy == last, "pop_dof_jan1"].iloc[0]
    fy.loc[m, "primary_note"] = f"NO ESTIMATE YET: held flat at DOF Jan 1 {last}"
    fy.to_csv(os.path.join(CTX, "population_fy.csv"), index=False)
    print(fy.to_string())
    return fy


# ---------------------------------------------------------------- POSITIONS / VACANCY PROXY
FTE_DATASETS = {"budget_fte": "4zfx-f2ts",   # Budget - FTE (Annual Salary Ordinance), FY2010+
                "spending_fte": "43jt-u7yn"}  # Spending - FTE (actual paid FTE), FY2003+
# Department-code consolidations observed at the FY2019 ASO/financial-system break (verified by
# matching FTE magnitudes: DSS 2,368 (FY18) -> HSA 2,398 (FY19); WTR 654 + CWP 491 + HHP 279 + PUC 779
# (FY18) -> PUC 2,542 (FY19); ECD 297 -> DEM 309).
CODE_CROSSWALK = {"DSS": "HSA", "WTR": "PUC", "CWP": "PUC", "HHP": "PUC", "ECD": "DEM"}


def _norm_cols(df):
    df.columns = [c.lower().replace(" ", "_").replace("-", "_") for c in df.columns]
    return df


def build_fte():
    for name, dsid in FTE_DATASETS.items():
        fetch(f"https://data.sf.gov/api/views/{dsid}/rows.csv?accessType=DOWNLOAD",
              os.path.join(CTX, name + ".csv"), timeout=900)
        fetch(f"https://data.sf.gov/api/views/{dsid}.json", os.path.join(CTX, f"meta_{dsid}.json"))
    b = _norm_cols(pd.read_csv(os.path.join(CTX, "budget_fte.csv"), dtype=str))
    b["budget"] = pd.to_numeric(b.budget.str.replace(",", ""), errors="coerce")
    a = _norm_cols(pd.read_csv(os.path.join(CTX, "spending_fte.csv"), dtype=str))
    a["actual"] = pd.to_numeric(a.actual.str.replace(",", ""), errors="coerce")
    for d in (b, a):
        d["fy"] = d.fiscal_year.astype(int)
        d["dept_code"] = d.department_code.map(lambda c: CODE_CROSSWALK.get(c, c))
    # latest name for each unified code
    names = pd.concat([a[["fy", "dept_code", "department"]], b[["fy", "dept_code", "department"]]])
    names = names.sort_values("fy").drop_duplicates("dept_code", keep="last").set_index("dept_code").department

    bg = b[b.budget > 0].groupby(["fy", "dept_code"]).budget.sum().rename("budget_fte_gross")
    bn = b[b.budget < 0].groupby(["fy", "dept_code"]).budget.sum().rename("budget_attrition_adj")
    ba = b[b.job.fillna("").str.contains("Attrition", case=False)].groupby(["fy", "dept_code"]).budget.sum().rename("budget_attrition_only")
    ac = a.groupby(["fy", "dept_code"]).actual.sum().rename("actual_fte")
    t = pd.concat([bg, bn, ba, ac], axis=1).reset_index()
    t[["budget_attrition_adj", "budget_attrition_only"]] = t[["budget_attrition_adj", "budget_attrition_only"]].fillna(0)
    t["budget_fte_net"] = t.budget_fte_gross + t.budget_attrition_adj
    t["department"] = t.dept_code.map(names)
    # FY2019-FY2024 the ASO extract carries no negative attrition lines -> net == gross (not comparable)
    t["budget_regime"] = t.fy.map(lambda y: "gross_only_no_attrition_lines" if 2019 <= y <= 2024
                                  else ("gross_and_attrition" if 2010 <= y <= 2028 else "no_budget_fte"))
    t["vacancy_gross"] = t.budget_fte_gross - t.actual_fte
    t["vacancy_rate_gross"] = t.vacancy_gross / t.budget_fte_gross
    t.loc[t.budget_regime == "gross_only_no_attrition_lines", "budget_fte_net"] = None
    t["vacancy_net"] = t.budget_fte_net - t.actual_fte
    t["vacancy_rate_net"] = t.vacancy_net / t.budget_fte_net
    t["actual_partial_year"] = t.fy >= 2027
    t = t[["fy", "dept_code", "department", "budget_regime", "budget_fte_gross", "budget_attrition_adj",
           "budget_attrition_only", "budget_fte_net", "actual_fte", "vacancy_gross", "vacancy_rate_gross",
           "vacancy_net", "vacancy_rate_net", "actual_partial_year"]].sort_values(["dept_code", "fy"])
    t.round(3).to_csv(os.path.join(CTX, "fte_by_dept_fy.csv"), index=False)
    c = t.groupby("fy")[["budget_fte_gross", "budget_attrition_adj", "budget_fte_net", "actual_fte"]].sum(min_count=1)
    c.loc[(c.index >= 2019) & (c.index <= 2024), "budget_fte_net"] = None
    c["vacancy_gross"] = c.budget_fte_gross - c.actual_fte
    c["vacancy_rate_gross"] = c.vacancy_gross / c.budget_fte_gross
    c["vacancy_net"] = c.budget_fte_net - c.actual_fte
    c.round(1).to_csv(os.path.join(CTX, "fte_citywide_fy.csv"))
    pd.DataFrame([dict(old_code=k, unified_code=v) for k, v in CODE_CROSSWALK.items()]).to_csv(
        os.path.join(CTX, "fte_dept_code_crosswalk.csv"), index=False)
    print(c.round(3).to_string())
    return t


if __name__ == "__main__":
    what = sys.argv[1:] or ["cpi", "pop", "fte"]
    if "cpi" in what:
        build_cpi()
    if "pop" in what:
        build_population()
    if "fte" in what:
        build_fte()
