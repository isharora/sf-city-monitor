"""Export dashboard data to data/site/ following design/DATA_CONTRACT_nonprofits.md.

Contract files: meta.json, orgs/index.json, payments/cells_<fy>.json, contracts/contracts.json,
finances/form990.json (+ form990_<fy>.json split, see CONTRACT_GAPS.md), reviews/findings.json,
commentary/np-*.json, commentary/story_np.json.
Additions (listed in meta.files and CONTRACT_GAPS.md): orgs/profiles/<org>.json (top 150 by city $),
aggregates/{trends,departments,areas,outcomes,findings_summary}.json, reviews/other_findings.json.
All dollars nominal. Runs QA checks from contract section 5 and writes data/site/qa_report.json.
"""
import datetime as dt, glob, hashlib, json, math, os, re, shutil
import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
INT = os.path.join(BASE, "interim")
RES = os.path.join(INT, "results")
SITE = os.path.join(BASE, "site")
AS_OF = "2026-09-21"  # data_loaded_at of the Vendor Payments / Supplier Contracts extracts
FY_MIN, FY_MAX = 2007, 2026  # FY2027 is partial (Jul-Sep 2026) and not exported
SRC_PAY, SRC_CON, SRC_990, SRC_MON = "n9pm-xkyq", "cqi5-hm2d", "irs-990", "csa-npm"

AREAS = [("homeless", "Homelessness and housing"), ("health", "Health and behavioral health"),
         ("human", "Human services and seniors"), ("youth", "Children, youth and families"),
         ("workforce", "Workforce and economic development"), ("arts", "Arts and culture"), ("other", "Other")]
SIZE_BANDS = [("lt1m", "< $1M a year"), ("1-5m", "$1M–5M"), ("5-25m", "$5M–25M"), ("25m+", "$25M+")]
RESULTS = [("none", "No findings, or findings resolved or waived"), ("findings", "Findings not yet resolved at final status"),
           ("corrective", "Corrective action, Tier 2 (FY2024 on)"), ("elevated", "Elevated concern (to FY2023) or Tier 3"), ("redflag", "Red flag")]
GROUP_MAP = {"Public Protection": "protection", "Public Works, Transportation & Commerce": "works",
             "Human Welfare & Neighborhood Development": "welfare", "Community Health": "health",
             "Culture & Recreation": "culture", "General Administration & Finance": "admin",
             "General City Responsibilities": "admin"}
DEPT_AREA = {"HOM": "homeless", "DPH": "health", "CHF": "youth", "DEC": "youth", "CFC": "youth", "ECN": "workforce",
             "ART": "arts", "AAM": "arts", "FAM": "arts", "WAR": "arts", "SCI": "arts", "LIB": "arts"}
NTEE_AREA = {"L": "homeless", "E": "health", "F": "health", "G": "health", "H": "health", "O": "youth", "B": "youth",
             "J": "workforce", "A": "arts", "P": "human"}
files_written = {}
GROUP_SENT = re.compile(r"^(The report says several|The report says one of the three|most common unresolved findings among|it does not say which)", re.I)


def clean_note(text, result):
    """Fairness: a monitoring note states only what the report says about THIS organization, never truncates a
    sentence (truncation used to cut off disclaimers), and replaces report statements about a group of
    organizations with a sentence saying the report does not attribute them."""
    if not text or result == "none":
        return None
    if result == "findings":
        m = re.search(r"\((Core|Expanded) monitoring\)", text)
        kind = f" ({m.group(1)} monitoring)" if m else ""
        return f"Some City fiscal and administrative standards were not yet met at final status{kind}. A finding does not by itself indicate misuse of funds."
    parts = [x.strip() for x in re.split(r"(?<=[.;])\s+", text) if x.strip()]
    keep, dropped = [], False
    for x in parts:
        if GROUP_SENT.search(x):
            dropped = True
            continue
        x = x.rstrip(";")
        keep.append(x[0].upper() + x[1:])
    note = " ".join(k if k.endswith(".") else k + "." for k in keep)
    note = note.replace("The Controller paused technical assistance with Providence Foundation", "The report notes the City paused technical assistance with this organization")
    if dropped:
        note += " The report lists issues common to organizations at this level without saying which applied to each one."
    return note


# News items: label what kind of statement each is, so allegations always read as allegations.
NEWS_LABEL = {"news allegation": "allegation reported in the news", "criminal charges": "criminal charge reported in the news (not a conviction)",
              "contract terminated": "official action reported in the news", "corrective action": "official action reported in the news",
              "no findings/cleared": "outcome reported in the news"}
# (org ein, finding-text prefix) -> override label or None to drop. Reviewed item by item (red team, fairness pass).
NEWS_OVERRIDES = {
    ("952557063", "KQED reported that prosecutors describe"): "context reported in the news (no allegation against this organization)",
    ("810622701", "Mission Local reported (Aug. 2026) that the DA charged two shelter employees"): None,  # charges against staff below executive level, not the organization
    ("942333038", "Mission Local reported (June 2026) that court data"): "dispute over performance measurement reported in the news",
    ("941694551", "Mission Local, citing the BLA report"): "news report citing a Budget and Legislative Analyst report",
    ("931204173", "Mission Local, citing the BLA report"): "news report citing a Budget and Legislative Analyst report",
    ("943112338", "KQED reported on the Controller's April 2024 audit"): "news report citing a Controller audit",
    ("941429538", "KQED reported (May 2026) that a Budget and Legislative Analyst audit"): "news report citing a Budget and Legislative Analyst audit",
    ("461329910", "Mission Local reported that the Controller found"): "news report citing a Controller review",
    ("931204173", "KQED reported (Aug. 2025) that Providence agreed"): "settlement reported in the news",
}


def news_label(ein, finding_type, text):
    for (e, pre), lab in NEWS_OVERRIDES.items():
        if ein == e and (text or "").startswith(pre):
            return lab, lab is None
    return NEWS_LABEL.get(finding_type, "news report"), False


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o is None or math.isnan(o) or math.isinf(o)) else float(o)
    if o is pd.NaT:
        return None
    return o


def w(path, obj):
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    s = json.dumps(clean(obj), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with open(full, "w") as f:
        f.write(s)
    files_written["nonprofits/" + path] = {"bytes": len(s.encode("utf-8"))}


def rint(x):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else int(round(x))


def r2(x, n=3):
    return None if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else round(float(x), n)


def exempt_status(ein, orgs_irs):
    """Plain statement of IRS exemption status; a past automatic revocation is always shown with what followed."""
    if ein not in orgs_irs.index:
        return None
    o = orgs_irs.loc[ein]
    rev, rein, in_bmf, ruling = o.revocation_date, o.reinstatement_date, bool(o.in_bmf), o.RULING
    if not isinstance(rev, str) or not rev:
        return {"listed_in_irs_master_file": in_bmf, "note": "Listed as tax-exempt in the IRS Business Master File." if in_bmf else None}
    if in_bmf or (isinstance(rein, str) and rein):
        extra = f" The IRS lists an exemption ruling dated {str(ruling)[:4]}-{str(ruling)[4:6]}." if isinstance(ruling, str) and len(ruling) >= 6 else ""
        return {"listed_in_irs_master_file": in_bmf, "past_automatic_revocation": rev, "reinstatement_date": rein if isinstance(rein, str) else None,
                "note": f"The IRS automatically revoked this organization's exemption on {rev} for not filing required returns for three consecutive years; it has since been restored and the organization is currently listed as tax-exempt.{extra} Automatic revocation for missed filings is common among small nonprofits and is often reversed."}
    return {"listed_in_irs_master_file": False, "past_automatic_revocation": rev, "reinstatement_date": None,
            "note": f"The IRS automatically revoked this organization's exemption on {rev} for not filing required returns for three consecutive years, and it is not in the current IRS Business Master File. Automatic revocation reflects missed filings; it is not a finding of misconduct."}


# Lead department per monitored contractor: the Controller's monitoring datasets for FY2021-22 and FY2022-23
# (data/reviews/monitoring_data/fy22_dataset.xlsx, fy23_dataset.xlsx, sheet "Contractor Summary", column
# "Lead Department"). The FY2019, FY2024 and FY2025 reports and datasets do not publish a lead department, so
# those rows keep lead_dept = null (the site shows them under all departments, labelled).
LEAD_FILES = {2022: "fy22_dataset.xlsx", 2023: "fy23_dataset.xlsx"}
LEAD_NAME_TO_CODE = {"department of children youth and their families": "CHF", "human services agency": "HSA",
                     "department of public health": "DPH", "mayor's office of housing and community development": "MYR",
                     "office of economic and workforce development": "ECN", "department of homelessness and supportive housing": "HOM",
                     "arts commission": "ART", "san francisco arts commission": "ART", "department on the status of women": "WOM",
                     "first 5": "CFC", "first 5 commission": "CFC", "department of early childhood": "DEC", "sheriff's department": "SHF",
                     "department of public works": "DPW", "adult probation department": "ADP"}
_SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|llc|the|dba .*)\b")


def _nm(s):
    s = re.sub(r"[’']s\b", "s", str(s).lower())
    s = _SUFFIX.sub(" ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def lead_departments():
    import openpyxl
    tables = {}
    for fy, fn in LEAD_FILES.items():
        path = os.path.join(BASE, "reviews", "monitoring_data", fn)
        if not os.path.exists(path):
            continue
        rows = list(openpyxl.load_workbook(path, read_only=True)["Contractor Summary"].iter_rows(values_only=True))
        h = next(i for i, r in enumerate(rows) if r and r[0] == "Contractor Name")
        col = list(rows[h]).index("Lead Department")
        t = {}
        for r in rows[h + 1:]:
            if r and r[0] and r[col]:
                code = LEAD_NAME_TO_CODE.get(str(r[col]).strip().lower())
                if code is None:
                    raise ValueError(f"unmapped lead department {r[col]!r} in {fn}")
                t[_nm(r[0])] = code
        tables[fy] = (t, f"Controller monitoring dataset FY{fy - 2001}-{fy - 2000} ({fn}), Contractor Summary > Lead Department")

    def lookup(fy, names):
        if fy not in tables:
            return None, None
        t, src = tables[fy]
        keys = [_nm(n) for n in names if n]
        for k in keys:  # exact normalized name or alias
            if k in t:
                return t[k], src
        for k in keys:  # unique prefix match either way (e.g. "Arriba Juntos" / "Arriba Juntos - IAI"), long names only
            if len(k) < 10:
                continue
            hits = [v for kk, v in t.items() if len(kk) >= 10 and (kk.startswith(k) or k.startswith(kk))]
            if len(hits) == 1:  # exactly one contractor in the table
                return hits[0], src + " (name matched by prefix)"
        return None, None
    return lookup


def main():
    if os.path.exists(SITE):
        shutil.rmtree(SITE)
    os.makedirs(SITE)
    p = pd.read_parquet(os.path.join(INT, "payments.parquet"))
    npay = pd.read_parquet(os.path.join(INT, "np_payments.parquet"))
    npay = npay[npay.fiscal_year.between(FY_MIN, FY_MAX)]
    vm = pd.read_parquet(os.path.join(INT, "vendor_map.parquet"))
    vm = vm[vm.org_class != "public_university"]
    names = pd.read_parquet(os.path.join(INT, "org_names.parquet"))
    orgs_irs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    al = pd.read_parquet(os.path.join(INT, "aligned.parquet"))
    cpi = pd.read_parquet(os.path.join(INT, "cpi.parquet")).set_index("fy")
    findings = pd.read_parquet(os.path.join(INT, "findings_linked.parquet"))
    reviews = {r["id"]: r for r in json.load(open(os.path.join(BASE, "reviews", "reviews.json")))}
    dg = pd.DataFrame(json.load(open(os.path.join(BASE, "raw", "dept_groups.json"))))
    dg["last_fy"] = dg.last_fy.astype(int)
    dg = dg.sort_values("last_fy").drop_duplicates("department_code", keep="last").set_index("department_code")

    oid = lambda ein: f"org-{ein}"
    # ---------------- cells
    cells = (npay.groupby(["fiscal_year", "department_code", "ein"])
             .agg(amt=("paid", "sum"), vouchers=("n_lines", "sum"),
                  contracts=("contract_number", lambda s: s[s != ""].nunique())).reset_index())
    cells = cells[cells.amt > 0.5]
    for fy, g in cells.groupby("fiscal_year"):
        w(f"payments/cells_{fy}.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY],
            "note": "One row per (fiscal year, department, organization); vouchers_paid in expenditure characters only; amt > 0 (net negative adjustments dropped). vouchers = count of voucher lines in the source. Nominal dollars; deflate with meta.deflator.",
            "cells": [{"fy": int(fy), "dept": r.department_code, "org": oid(r.ein), "amt": rint(r.amt), "vouchers": int(r.vouchers),
                       "contracts": int(r.contracts)} for r in g.itertuples()]})
    # ---------------- orgs
    org_tot = cells.groupby("ein").amt.sum()
    dept_tot = cells.groupby(["ein", "department_code"]).amt.sum().reset_index().sort_values("amt", ascending=False)
    top_dept = dept_tot.drop_duplicates("ein").set_index("ein").department_code
    yrs = cells.groupby("ein").fiscal_year.agg(["min", "max", "nunique"])
    conf = vm.groupby("ein").confidence.max()
    org_rows, area_of, size_of, extra_of = [], {}, {}, {}
    for ein, tot in org_tot.items():
        ntee = orgs_irs.NTEE_CD.get(ein) if ein in orgs_irs.index else None
        d0 = top_dept.get(ein)
        area = DEPT_AREA.get(d0)
        if area is None:
            area = NTEE_AREA.get((ntee or " ")[0], "other")
            if d0 == "HSA" and area in ("other", "health"):
                area = "human"
        avg = tot / yrs.loc[ein, "nunique"]
        sb = "lt1m" if avg < 1e6 else "1-5m" if avg < 5e6 else "5-25m" if avg < 25e6 else "25m+"
        area_of[ein], size_of[ein] = area, sb
        latest = cells[(cells.ein == ein) & (cells.fiscal_year == FY_MAX)].amt.sum()
        org_rows.append({"id": oid(ein), "name": names.city_vendor_name.get(ein) or names.display_name.get(ein),
                         "ein": f"{ein[:2]}-{ein[2:]}", "area": area, "size_band": sb,
                         "depts": dept_tot[dept_tot.ein == ein].department_code.tolist(), "city_total": rint(tot),
                         "city_fy_latest": rint(latest), "first_fy": int(yrs.loc[ein, "min"]), "last_fy": int(yrs.loc[ein, "max"]),
                         "match": {"method": "name", "confidence": r2(conf.get(ein), 2)}, "network_id": None})
        extra_of[ein] = {"irs_name": names.display_name.get(ein), "org_class": vm[vm.ein == ein].org_class.iloc[0]}
    org_rows.sort(key=lambda r: -r["city_total"])
    w("orgs/index.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY, SRC_990],
                          "note": "Organizations = city vendors matched to an IRS exempt-organization EIN (public universities excluded). name = the city's vendor name with the most dollars; irs_name = IRS name. match.method 'name' = name/location match adjudicated by Claude (see DATA_NOTES.md).",
                          "orgs": org_rows})
    org_ids = {r["id"] for r in org_rows}
    # ---------------- form 990
    off = pd.read_parquet(os.path.join(INT, "officers990.parquet"))
    off["total_comp"] = off.comp_org.fillna(0) + off.comp_related.fillna(0) + off.comp_other.fillna(0)
    ex = off[(off.officer | off.key_employee) & ~off.former.fillna(False).astype(bool)]
    topx = ex.sort_values("total_comp", ascending=False).drop_duplicates(["ein", "period_end"]).set_index(["ein", "period_end"])
    hpc = off[off.highest_comp.fillna(False).astype(bool)].groupby(["ein", "period_end"]).size()
    f9 = al[al.ein.isin(org_tot.index) & (al.total_revenue > 0) & al.form.isin(["990", "990EZ"])].copy()
    f9["fy"] = f9.fy_end_year + (f9.fy_end_month >= 7).astype(int)
    f9 = f9.sort_values(["ein", "fy", "period_end"]).drop_duplicates(["ein", "fy"], keep="last")
    f9rows = []
    for r in f9.itertuples():
        k = (r.ein, r.period_end)
        t = topx.loc[k] if k in topx.index else None
        f9rows.append({"org": oid(r.ein), "fy": int(r.fy), "period_end": r.period_end, "form": "990-EZ" if r.form == "990EZ" else "990",
                       "total_revenue": rint(r.total_revenue), "total_expenses": rint(r.total_expenses),
                       "gov_grants": rint(r.government_grants),
                       "program_share": r2(r.program_expenses / r.total_expenses) if r.program_expenses and r.total_expenses else None,
                       "net_assets": rint(r.net_assets_eoy), "unrestricted_net_assets": rint(r.unrestricted_na_eoy),
                       "months_reserves": r2(r.months_reserves_unrestricted, 1), "employees": rint(r.total_employees),
                       "exec_comp": rint(t.total_comp) if t is not None else None,
                       "exec_comp_from_org": rint(t.comp_org) if t is not None else None,
                       "exec_title": (t.title if t is not None else None), "exec_comp_rank": 1 if t is not None else None,
                       "highest_paid_count": int(hpc.get(k, 0)) if r.source == "irs_xml" else None,
                       "_grants_paid": rint(r.grants_paid), "_city_paid_aligned": rint(r.city_paid_aligned),
                       "_program_service_revenue": rint(r.program_service_revenue), "_source": r.source})
    f9df = pd.DataFrame(f9rows)
    paid_keys = set(zip(cells.ein.map(oid), cells.fiscal_year))
    f9df["_rel"] = [any((o, y + k) in paid_keys for k in (-1, 0, 1)) for o, y in zip(f9df.org, f9df.fy)]
    f9df = f9df[f9df._rel].drop(columns="_rel")
    slim = lambda g: [{k: v for k, v in rec.items() if not k.startswith("_") and k not in ("exec_comp_from_org", "period_end")} for rec in g.to_dict("records")]
    by_fy_files = []
    for fy, g in f9df.groupby("fy"):
        if fy < 2011:
            continue
        w(f"finances/form990_{fy}.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_990],
                                          "rows": slim(g)})
        by_fy_files.append(f"finances/form990_{fy}.json")
    latest_fy = int(f9df.fy.max()) if len(f9df) else None
    w("finances/form990.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_990],
        "note": "Rows for fy = FY2025 only, to respect the 400 KB file limit; all years are in finances/form990_<fy>.json (see files_by_fy). fy = the city fiscal year in which the tax year ends. exec_comp = highest-paid current officer/key employee total compensation (org + related orgs + other); exec_comp_from_org = from this org only. city_paid_aligned = city payments prorated to the org's 12-month tax year (approximate).",
        "files_by_fy": by_fy_files, "rows": slim(f9df[f9df.fy == FY_MAX - 1])})
    # ---------------- contracts
    npc = pd.read_csv(os.path.join(RES, "np_contracts.csv"), dtype={"Contract Number": str, "ein": str})
    npc = npc[npc.ein.isin(org_tot.index)]
    npc = npc[npc["amt_2026-09-21"] >= 250000]
    con = []
    # Department codes. Supplier Contracts gives "<CODE> <name>"; two values are not Controller codes:
    # "DT  GSA - Technology" (Department of Technology, Controller code TIS) and "Unmapped Departments"
    # (mostly First 5 / DEC family-support grants). Unmapped contracts take the department that made the
    # largest vendor payments on the same contract number; with no payments they are "UNK" (Unknown department).
    DEPT_ALIAS = {"DT": "TIS"}
    pay_dept = (npay[npay.contract_number.astype(str) != ""].groupby(["contract_number", "department_code"]).paid.sum()
                .reset_index().sort_values("paid", ascending=False).drop_duplicates("contract_number").set_index("contract_number").department_code.to_dict())
    def con_dept(rd):
        raw = str(rd.get("Department_Code") or str(rd["Department"])[:3]).strip()
        if str(rd["Department"]).startswith("Unmapped"):
            d = pay_dept.get(str(rd["Contract_Number"]))
            return (d, "vendor payments on this contract (Supplier Contracts lists 'Unmapped Departments')") if d else ("UNK", "Supplier Contracts lists 'Unmapped Departments' and no vendor payments name a department")
        if raw.lower() in ("", "nan", "none"):
            return "UNK", "Supplier Contracts gives no department"
        if raw in DEPT_ALIAS:
            return DEPT_ALIAS[raw], f"Supplier Contracts code '{raw}' is an alias of Controller code {DEPT_ALIAS[raw]}"
        return raw, None
    snapcols =[("2021-04-22", "amt_2021-04-22"), ("2022-12-06", "amt_2022-12-06"), ("2025-11-02", "amt_2025-11-02"), ("2026-09-21", "amt_2026-09-21")]
    for rd0 in npc.to_dict("records"):
        rd = {k.replace(" ", "_").replace("-", "_"): v for k, v in rd0.items()}
        obs = [(d, rd.get(c.replace("-", "_"))) for d, c in snapcols]
        obs = [(d, v) for d, v in obs if v is not None and not (isinstance(v, float) and math.isnan(v)) and v > 0]
        amend, prev = [], None
        for d, v in obs:
            if prev is not None and abs(v - prev) >= 1:
                amend.append({"date": d, "agreed_after": rint(v)})
            prev = v
        orig = obs[0][1] if obs else rd["amt_2026_09_21"]
        ctype = str(rd["Contract_Type"])
        typ = "grant" if "Grant" in ctype else "professional_services" if "Professional" in ctype else "other"
        cdept, cbasis = con_dept(rd)
        con.append({"id": rd["Contract_Number"], "org": oid(rd["ein"]), "dept": cdept, **({"dept_basis": cbasis} if cbasis else {}),
                    "title": rd["Contract_Title"], "start": str(rd["Term_Start_Date"]).replace("/", "-")[:10],
                    "end": str(rd["Term_End_Date"]).replace("/", "-")[:10], "type": typ,
                    "sole_source": rd["Sole_Source"] == "X", "authority_class": rd["authority_class"],
                    "original_agreed": rint(orig), "agreed": rint(rd["amt_2026_09_21"]), "consumed": rint(rd["paid_to_date"]),
                    "amendments": amend,
                    "first_snapshot": obs[0][0] if obs else None,
                    # term end as recorded at the first snapshot: most 'doubled' ceilings are longer terms (red team)
                    "term_end_first_snapshot": (str(rd.get(f"end_{obs[0][0]}".replace("-", "_"))).replace("/", "-")[:10]
                                                if obs and obs[0][0] != "2026-09-21" and isinstance(rd.get(f"end_{obs[0][0]}".replace("-", "_")), str)
                                                else (str(rd["Term_End_Date"]).replace("/", "-")[:10] if obs else None)),
                    "pre_snapshot": bool(obs and obs[0][0] > str(rd["Term_Start_Date"]).replace("/", "-")[:10])})
    con_all = con
    con = [c for c in con_all if c["agreed"] >= 4e6 and c["end"] >= "2019-07-01"]
    for i in range(0, len(con_all), 1000):
        w(f"contracts/all_{i // 1000 + 1}.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_CON],
          "note": "All prime contracts of matched nonprofits with awarded amount >= $250,000 (addition to the contract; same schema as contracts.json).",
          "contracts": con_all[i:i + 1000]})
    w("contracts/contracts.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_CON],
        "note": "dept = Controller department code; where Supplier Contracts lists 'Unmapped Departments' it is the department with the largest vendor payments on the contract, and 'DT' (Department of Technology) is mapped to TIS; dept_basis explains each such row, and UNK means unknown. Prime contracts with matched nonprofits, current awarded amount >= $4,000,000 and term ending on or after 2019-07-01 (to respect the 400 KB limit; all contracts >= $250,000 are in contracts/all_*.json). agreed_amt history comes from Supplier Contracts snapshots archived by the Internet Archive (2021-04-22, 2022-12-06, 2025-11-02) plus the 2026-09-21 extract; amendment dates are observation (snapshot) dates, not execution dates; pre_snapshot = true when the contract began before its first snapshot, so earlier amendments are not visible and original_agreed may already include amendments. consumed = payments made to date. sole_source = the Supplier Contracts flag (authority permits sole source). authority_class = our classification of the purchasing-authority text.",
        "contracts": con})
    # ---------------- reviews (monitoring)
    mon = findings[findings.review_id.str.startswith("ctrl-monitoring") & findings.ein.notna()].copy()
    mon["fy"] = mon.review_id.str.extract(r"fy(\d\d)").astype(int)[0] + 2000
    def sev(r):
        t = (r.finding or "")
        if re.search(r"placed on red flag", t, re.I):
            return "redflag"
        if re.search(r"[Dd]esignated (as )?Tier 3|Tier 3 under", t) or r.finding_type == "elevated concern":
            return "elevated"
        if r.finding_type == "corrective action":
            return "corrective"
        if r.finding_type == "fiscal monitoring finding":
            return "findings"
        if r.finding_type in ("no findings/cleared", "monitoring findings resolved"):
            return "none"
        return None
    mon["result"] = mon.apply(sev, axis=1)
    mon = mon[mon.result.notna()]
    rank = {k: i for i, (k, _) in enumerate(RESULTS)}
    lead_of = lead_departments()
    cats_all = set()
    frows = []
    for (ein, fy), g in mon.groupby(["ein", "fy"]):
        g = g.assign(rk=g.result.map(rank)).sort_values("rk", ascending=False)
        top = g.iloc[0]
        cats = []
        for t in g.finding:
            m = re.search(r"by category, per the published dataset: ([^.]*)\.", t or "")
            if m:
                cats += [re.sub(r"\s*\(\d+\)$", "", c).strip() for c in m.group(1).split(";")]
        cats = sorted(set(c for c in cats if c))
        cats_all.update(cats)
        rv = reviews.get(top.review_id, {})
        names = [top.org_name] + [a for x in g.org_name_aliases if x is not None for a in list(x)]
        ld = lead_of(int(fy), names)
        frows.append({"id": f"F-{ein}-{fy}", "org": oid(ein), "fy": int(fy), "lead_dept": ld[0], "lead_dept_source": ld[1], "type": "fiscal_compliance",
                      "result": top.result, "categories": cats,
                      "report": {"title": rv.get("title"), "url": top.url or rv.get("url"), "page": rint(top.page) if top.page == top.page and top.page is not None else None},
                      "note": clean_note(top.finding, top.result)})
    frows = [r for r in frows if r["org"] in org_ids]
    w("reviews/findings.json", {"sample": False, "as_of": "2026-06-30", "sources": [SRC_MON],
        "note": "One row per organization x monitoring fiscal year (most severe status that year). Source: Controller's Citywide Nonprofit Monitoring and Capacity Building Program annual reports FY2022-FY2025 (per-organization appendix tables) and FY2019 elevated-concern list. Monitoring checks fiscal and administrative standards; a finding is not evidence of misuse of funds. 'Monitoring incomplete' rows are omitted (not a result). lead_dept = the lead department named in the Controller's FY2021-22 and FY2022-23 monitoring datasets (Contractor Summary sheet; lead_dept_source says which); the FY2019, FY2024 and FY2025 reports do not publish one, so those rows have lead_dept = null.",
        "results": [{"id": a, "label": l} for a, l in RESULTS], "categories": sorted(cats_all), "rows": frows})
    other = findings[~findings.review_id.str.startswith("ctrl-monitoring")].copy()
    orows = []
    for r in other.itertuples():
        rv = reviews.get(r.review_id, {})
        if rv.get("type") == "news":
            label, drop = news_label(r.ein, r.finding_type, r.finding)
        else:
            label, drop = ("official finding" if rv.get("type") in ("controller_audit", "controller_public_integrity", "bla", "civil_grand_jury", "controller_monitoring") else "document"), False
        if drop:
            continue
        orows.append({"statement_type": label, "org": oid(r.ein) if isinstance(r.ein, str) and oid(r.ein) in org_ids else None, "org_name": r.org_name,
                      "review_id": r.review_id, "review_title": rv.get("title"), "publisher": rv.get("publisher"),
                      "review_type": rv.get("type"), "date": rv.get("date"), "finding_type": r.finding_type,
                      "finding": r.finding, "quote": r.quote, "page": rint(r.page) if r.page == r.page and r.page is not None else None,
                      "status": r.status, "url": r.url or rv.get("url")})
    w("reviews/other_findings.json", {"sample": False, "as_of": AS_OF, "sources": ["reviews"],
        "note": "Findings from Controller audits and Public Integrity reviews, Budget and Legislative Analyst, Civil Grand Jury, city policy documents and news investigations. statement_type says what kind of statement each row is: 'official finding' (a public report's finding, cited with page), or for news items 'allegation reported in the news', 'criminal charge reported in the news (not a conviction)', 'official action reported in the news', and so on. News items are reported claims, not findings of this dashboard. finding_type is the research coding. org = null when the organization is not among matched city vendors.",
        "rows": orows})
    # ---------------- aggregates
    t = pd.read_csv(os.path.join(RES, "trends.csv"))
    t = t[t.fiscal_year.between(FY_MIN, FY_MAX)]
    w("aggregates/trends.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY, "qkex-vh98"],
        "rows": t[["fiscal_year", "all_expenditure", "nonprofit_all", "nonprofit_core", "n_orgs_paid", "top10_share", "top20_share",
                   "top50_share", "hhi", "orgs_for_80pct", "city_flag_expenditure", "controller_dataset_excl_ucsf",
                   "nonprofit_share_of_expenditure"]].to_dict("records")})
    d = pd.read_csv(os.path.join(RES, "departments_by_year.csv"))
    d = d[d.fiscal_year.between(FY_MIN, FY_MAX)]
    w("aggregates/departments.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY],
        "note": "nonprofit_share_of_vendor_spend = nonprofit payments / all expenditure-class vendor payments by the department (not share of the department budget).",
        "rows": d.to_dict("records")})
    ar = npay.assign(area=npay.ein.map(area_of)).groupby(["area", "fiscal_year"]).paid.sum().reset_index()
    w("aggregates/areas.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY], "rows": ar.to_dict("records")})
    oc = pd.read_csv(os.path.join(RES, "outcomes_vs_spending.csv"))
    w("aggregates/outcomes.json", {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY, "6dpt-7w23", "kc49-udxn", "pit"],
        "note": "Descriptive only. nonprofit_paid = the department's payments to matched nonprofits; outcome measures cover all providers (including city staff) and are published by the Controller/HSH. FY2018-22 HSH placements are sums of monthly counts (not deduplicated).",
        "rows": oc.to_dict("records"), "ratios": pd.read_csv(os.path.join(RES, "outcomes_ratios.csv")).to_dict("records")})
    # ---------------- profiles (top 150)
    odY = npay.groupby(["ein", "fiscal_year", "department_code"]).paid.sum().reset_index()
    for r in org_rows[:150]:
        ein = r["ein"].replace("-", "")
        prof = {"sample": False, "as_of": AS_OF, "sources": [SRC_PAY, SRC_CON, SRC_990, SRC_MON, "reviews"], "org": r, **extra_of.get(ein, {}),
                "irs": {k: (orgs_irs.loc[ein, c] if ein in orgs_irs.index else None) for k, c in
                        [("name", "NAME"), ("city", "CITY"), ("state", "STATE"), ("ntee", "NTEE_CD"), ("subsection", "SUBSECTION"),
                         ("ruling", "RULING"), ("revocation_date", "revocation_date")]},
                "exempt_status": exempt_status(ein, orgs_irs),
                "vendor_names": sorted(vm[vm.ein == ein].vendor.tolist()),
                "payments_by_year_dept": [{"fy": int(x.fiscal_year), "dept": x.department_code, "amt": rint(x.paid)} for x in odY[odY.ein == ein].itertuples() if x.paid > 0.5],
                "form990": [x for x in f9rows if x["org"] == r["id"]],
                "contracts": [c for c in con_all if c["org"] == r["id"]][:60],
                "monitoring": [x for x in frows if x["org"] == r["id"]],
                "other_findings": [x for x in orows if x["org"] == r["id"]]}
        w(f"orgs/profiles/{r['id']}.json", prof)
    # ---------------- meta
    depts_used = sorted(cells.department_code.unique())
    dvals = []
    for dcode in depts_used:
        nm = dg.department.get(dcode, dcode) if dcode in dg.index else dcode
        nm = re.sub(r"^[A-Z]{2,4}\s+", "", str(nm)).strip()
        grp = GROUP_MAP.get(dg.organization_group.get(dcode), "admin") if dcode in dg.index else "admin"
        dvals.append({"id": dcode, "name": nm, "group": grp, "short": dcode})
    if any(c["dept"] == "UNK" for c in con):
        dvals.append({"id": "UNK", "name": "Unknown department", "group": "admin", "short": "Unknown"})
    idx = {str(int(fy)): r2(1 / row.deflator_to_fy2025, 4) for fy, row in cpi.iterrows() if FY_MIN <= fy <= FY_MAX}
    raw_rows_total = 8171891
    meta = {"sample": False, "module": "nonprofits", "as_of": AS_OF, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "version": "1.0",
            "fiscal_years": {"min": FY_MIN, "max": FY_MAX, "note": "City fiscal year, July–June; FY2025 = July 2024–June 2025. FY2027 (partial, Jul–Sep 2026) is not exported. Vendor Payments uses the FAMIS chart of accounts through FY2017 and PeopleSoft from FY2018; department reorganizations (HSH created FY2017, DEC in FY2023) move spending between codes."},
            "deflator": {"base_fy": 2025, "source": "BLS CPI-U San Francisco-Oakland-Hayward (CUURS49BSA0), mean of monthly/bimonthly values July–June; index[fy] = CPI_fy / CPI_FY2025", "index": idx},
            "dimensions": {"dept": {"label": "Department", "values": dvals},
                           "area": {"label": "Service area", "kind": "categorical", "values": [{"id": a, "label": l, "slot": i + 1} for i, (a, l) in enumerate(AREAS)]},
                           "size_band": {"label": "Size (average city $ a year)", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in SIZE_BANDS]},
                           "result": {"label": "Monitoring result", "kind": "ordinal", "values": [{"id": a, "label": l} for a, l in RESULTS]}},
            "counts": {"organizations": len(org_rows), "payment_rows": int(len(cells)), "contracts": len(con), "form_990_years": len(f9rows),
                       "monitoring_results": len(frows), "total_paid_all_years": rint(cells.amt.sum())},
            "small_n": 5,
            "sources": [
                {"id": SRC_PAY, "name": "Vendor Payments (Vouchers)", "publisher": "SF Controller via data.sf.gov", "rows": raw_rows_total,
                 "rows_used": int(npay.n_lines.sum()), "as_of": AS_OF, "url": "https://data.sf.gov/resource/n9pm-xkyq.json",
                 "note": "FY2007–FY2026, expenditure characters, vendors matched to IRS exempt-organization EINs (rows_used = voucher lines behind the exported cells)."},
                {"id": SRC_CON, "name": "Supplier Contracts", "publisher": "SF Controller via data.sf.gov", "rows": 49186,
                 "rows_used": len(con), "as_of": AS_OF, "url": "https://data.sf.gov/resource/cqi5-hm2d.json",
                 "note": "Prime contracts of matched nonprofits >= $250k; amount history from Internet Archive snapshots 2021-04-22, 2022-12-06, 2025-11-02."},
                {"id": SRC_990, "name": "IRS Form 990 e-file XML (TEOS releases 2017–2026) and ProPublica Nonprofit Explorer API", "publisher": "IRS / ProPublica",
                 "rows": int(len(al)), "rows_used": len(f9rows), "as_of": "2026-09-26", "url": "https://www.irs.gov/charities-non-profits/form-990-series-downloads",
                 "note": "Matched by EIN after name matching against the IRS Exempt Organizations Business Master File; XML preferred, ProPublica fills earlier years."},
                {"id": SRC_MON, "name": "Controller Citywide Nonprofit Monitoring and Capacity Building Program annual reports (FY2019, FY2022–FY2025)", "publisher": "SF Controller",
                 "rows": int(findings.review_id.str.startswith("ctrl-monitoring").sum()), "rows_used": len(frows), "as_of": "2026-06-30",
                 "url": "https://media.api.sf.gov/documents/FY25_Nonprofit_Monitoring_Program_Annual_Report_-_Final.pdf", "note": "Per-organization appendix tables; names matched to EINs."},
                {"id": "irs-bmf", "name": "IRS Exempt Organizations Business Master File + auto-revocation list", "publisher": "IRS",
                 "rows": 1964958, "rows_used": len(org_rows), "as_of": "2026-09-26", "url": "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf",
                 "note": "All regional files (eo1–eo4) plus eo_ca; used for name matching."},
                {"id": "qkex-vh98", "name": "Citywide Nonprofit Spending", "publisher": "SF Controller via data.sf.gov", "rows": 26929, "rows_used": 26929,
                 "as_of": "2025-10-02", "url": "https://data.sf.gov/resource/qkex-vh98.json", "note": "Used only as a benchmark for totals (FY2019–FY2025)."},
                {"id": "6dpt-7w23", "name": "San Francisco Citywide Performance Metrics", "publisher": "SF Controller via data.sf.gov", "rows": 10164, "rows_used": int(len(oc)),
                 "as_of": "2026-09-26", "url": "https://data.sf.gov/resource/6dpt-7w23.json", "note": "Outcome measures for aggregates/outcomes.json."},
                {"id": "kc49-udxn", "name": "Scorecard Measures", "publisher": "SF Controller via data.sf.gov", "rows": 25349, "rows_used": None,
                 "as_of": "2026-09-26", "url": "https://data.sf.gov/resource/kc49-udxn.json", "note": "Monthly HSH placements FY2018–FY2022 (summed)."},
                {"id": "pit", "name": "San Francisco Point-in-Time homeless counts", "publisher": "HSH / sf.gov", "rows": None, "rows_used": None,
                 "as_of": "2026-09-26", "url": "https://api.sf.gov/documents/31917/2024_San_Francisco_Point-in-Time_Count_Report_8_13_24.pdf", "note": "2024 PIT report (earlier counts via Controller scorecard dataset kc49-udxn; 2026 preliminary: https://www.sf.gov/2026-point-in-time-count-preliminary-results)."},
                {"id": "reviews", "name": "Audits, reviews and news investigations (compiled)", "publisher": "SF Controller, BLA, Civil Grand Jury, news outlets",
                 "rows": len(findings), "rows_used": len(orows), "as_of": "2026-09-26", "url": None, "note": "Each row carries its own source URL; see reviews/other_findings.json."},
            ],
            "files": {}}
    w("meta.json", meta)
    return org_rows, cells, f9df, con, frows


if __name__ == "__main__":
    main()
