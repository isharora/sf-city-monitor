"""Core analytical tables.

Inputs: payments.parquet, vendors.parquet, matches_final.parquet, irs_orgs.parquet, fin990.parquet
Outputs (data/interim/):
  vendor_map.parquet      vendor -> ein, org name, org class
  np_payments.parquet     expenditure-class payment rows for matched nonprofits (+ein)
  org_year.parquet        ein x city FY: city payments (expenditure), contracted services, # depts
  org_dept_year.parquet   ein x dept x FY
  aligned.parquet         990 filing rows with city payments aligned to the org's fiscal year
  cpi.parquet             FY deflator (SF-Oakland-Hayward CPI-U, FY average, FY2025 = 1)
"""
import os, re
import numpy as np
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

AREA_BY_DEPT = {
    "HOM": "Homelessness & supportive housing", "DPH": "Health & behavioral health",
    "HSA": "Human services (HSA)", "DSS": "Human services (HSA)",
    "DEC": "Early childhood", "CFC": "Early childhood", "CHF": "Children, youth & families",
    "MYR": "Housing & community development (Mayor/MOHCD)", "ECN": "Workforce & economic development",
    "ADP": "Justice & public safety", "JUV": "Justice & public safety", "SHF": "Justice & public safety",
    "DAT": "Justice & public safety", "PDR": "Justice & public safety", "POL": "Justice & public safety",
    "CRT": "Justice & public safety", "DEM": "Justice & public safety",
    "ART": "Arts & culture", "AAM": "Arts & culture", "FAM": "Arts & culture", "WAR": "Arts & culture",
    "SCI": "Arts & culture", "LIB": "Arts & culture",
    "HRC": "Community & equity grants", "WOM": "Community & equity grants",
    "REC": "Parks, environment & public works", "ENV": "Parks, environment & public works",
    "DPW": "Parks, environment & public works", "PUC": "Parks, environment & public works",
    "WTR": "Parks, environment & public works", "PRT": "Parks, environment & public works",
    "MTA": "Transportation", "AIR": "Airport",
}


def cpi_table():
    rows = []
    with open(os.path.join(BASE, "raw", "cu_summaries.txt")) as f:
        for line in f:
            p = line.split("\t")
            if p[0].strip() == "CUURS49BSA0" and p[2].startswith("M") and p[2] != "M13":
                try:
                    rows.append((int(p[1]), int(p[2][1:]), float(p[3])))
                except ValueError:
                    pass
    c = pd.DataFrame(rows, columns=["year", "month", "cpi"])
    c["fy"] = np.where(c.month >= 7, c.year + 1, c.year)
    fy = c.groupby("fy").cpi.mean().reset_index()
    base = fy.loc[fy.fy == 2025, "cpi"].iloc[0]
    fy["deflator_to_fy2025"] = base / fy.cpi
    fy.to_parquet(os.path.join(INT, "cpi.parquet"))
    return fy


def org_class(row):
    ntee = row.get("NTEE_CD") or ""
    sub = str(row.get("SUBSECTION") or "")
    if isinstance(ntee, str) and (ntee.startswith("E2") or ntee.startswith("B4") or ntee.startswith("B5")):
        return "large_institution"  # hospitals, universities
    if sub not in ("03", "3", ""):
        return f"501c{int(sub) if sub.isdigit() else sub}"
    return "501c3"


def main():
    cpi_table()
    p = pd.read_parquet(os.path.join(INT, "payments.parquet"))
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet"))
    orgs = pd.read_parquet(os.path.join(INT, "irs_orgs.parquet")).set_index("EIN")
    ov = os.path.join(BASE, "manual", "match_overrides.csv")
    if os.path.exists(ov):  # hand-reviewed resolutions (Opus second opinion disagreements, validation errors)
        o_ = pd.read_csv(ov, dtype=str)
        for r in o_.itertuples():
            m.loc[m.vendor == r.vendor, ["matched_ein", "rationale", "model"]] = [r.ein, "override: " + r.note, "manual"]
    mm = m[m.matched_ein != "NONE"][["vendor", "matched_ein", "confidence", "vendor_type", "pass", "model", "rationale"]]
    mm = mm.rename(columns={"matched_ein": "ein"})
    o = orgs.reindex(mm.ein)
    mm["org_name"] = o.NAME.values
    mm["irs_city"] = o.CITY.values
    mm["irs_state"] = o.STATE.values
    mm["ntee"] = o.NTEE_CD.values
    mm["subsection"] = o.SUBSECTION.values
    mm["ruling"] = o.RULING.values
    mm["revocation_date"] = o.revocation_date.values
    mm["reinstatement_date"] = o.reinstatement_date.values
    mm["in_bmf"] = o.in_bmf.values
    mm["org_class"] = [org_class({"NTEE_CD": n, "SUBSECTION": s}) for n, s in zip(mm.ntee, mm.subsection)]
    # Public universities (UC campuses/Regents) are government instrumentalities, not nonprofits; the
    # Controller also excludes UCSF from its nonprofit reporting. Keep them in the map, flagged, and drop
    # them from np_payments.
    pub = mm.org_name.str.contains(r"UNIVERSITY OF CALIFORNIA|REGENTS OF THE UNIVERSITY", case=False, na=False)
    mm.loc[pub, "org_class"] = "public_university"
    mm.to_parquet(os.path.join(INT, "vendor_map.parquet"))

    e = p[p.spend_class == "expenditure"].merge(mm[mm.org_class != "public_university"][["vendor", "ein", "org_class"]], on="vendor", how="inner")
    e["area"] = e.department_code.map(AREA_BY_DEPT).fillna("Other departments")
    e.to_parquet(os.path.join(INT, "np_payments.parquet"))
    oy = e.groupby(["ein", "fiscal_year"]).agg(city_paid=("paid", "sum"), n_depts=("department_code", "nunique")).reset_index()
    oy["contracted_services"] = oy.set_index(["ein", "fiscal_year"]).index.map(
        e[e.service_class == "contracted_services"].groupby(["ein", "fiscal_year"]).paid.sum()).fillna(0).values
    oy.to_parquet(os.path.join(INT, "org_year.parquet"))
    e.groupby(["ein", "department_code", "department", "fiscal_year"]).paid.sum().reset_index().to_parquet(
        os.path.join(INT, "org_dept_year.parquet"))

    # --- align city payments to each 990 filing period ---
    fin = pd.read_parquet(os.path.join(INT, "fin990.parquet"))
    fin = fin[fin.ein.isin(set(mm.ein))].copy()
    oyi = oy.set_index(["ein", "fiscal_year"]).city_paid
    def aligned(ein, y, mth):
        # org FY = 12 months ending (y, mth). City FY F covers Jul(F-1)..Jun(F).
        tot, months = 0.0, 0
        for k in range(12):
            mo = mth - k; yr = y
            while mo <= 0:
                mo += 12; yr -= 1
            cfy = yr + 1 if mo >= 7 else yr
            tot += oyi.get((ein, cfy), 0.0) / 12.0
        return tot
    fin["city_paid_aligned"] = [aligned(e_, y, mth) for e_, y, mth in zip(fin.ein, fin.fy_end_year, fin.fy_end_month)]
    fin["city_fy_exact"] = fin.fy_end_month == 6
    fin["dependency"] = fin.city_paid_aligned / fin.total_revenue.where(fin.total_revenue > 0)
    fin["gov_grant_share"] = fin.government_grants / fin.total_revenue.where(fin.total_revenue > 0)
    fin["months_reserves_unrestricted"] = fin.unrestricted_na_eoy / (fin.total_expenses / 12).where(fin.total_expenses > 0)
    fin["months_reserves_netassets"] = fin.net_assets_eoy / (fin.total_expenses / 12).where(fin.total_expenses > 0)
    fin["months_cash"] = (fin.cash_eoy.fillna(0) + fin.savings_eoy.fillna(0)) / (fin.total_expenses / 12).where(fin.total_expenses > 0)
    fin.to_parquet(os.path.join(INT, "aligned.parquet"))
    print("vendor map", len(mm), "EINs", mm.ein.nunique(), "np payment rows", len(e), "aligned filings", len(fin))


if __name__ == "__main__":
    main()
