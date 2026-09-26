"""Combine per-FY aggregated payment files into one table with harmonized categories.

Output: data/interim/payments.parquet
Adds:
  char_group: harmonized character name across the FAMIS (FY2007-17) and PeopleSoft (FY2018+) charts
  spend_class: 'expenditure' (money spent on goods/services/grants) vs 'balance_sheet_or_other'
               (liability clearing, benefit trust payments, debt service, revenue refunds, etc.)
  service_class: 'contracted_services' for Non-Personnel Services, City Grant Program,
               Other Support/Care of Persons, Aid Assistance/Payments (the characters under which
               community-based-organization contracts and grants are booked)
"""
import glob, os
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
INT = os.path.join(os.path.dirname(__file__), "..", "data", "interim")

CHAR_MAP = {
    "Non Personnel Services": "Non-Personnel Services", "Non-Personnel Services": "Non-Personnel Services",
    "City Grant Programs": "City Grant Program", "City Grant Program": "City Grant Program",
    "Other Support&Care Of Persons": "Other Support/Care of Persons",
    "Other Support/Care of Persons": "Other Support/Care of Persons",
    "Aid Assistance": "Aid Assistance", "Aid Payments": "Aid Payments",
    "Materials & Supplies": "Materials & Supplies", "Capital Outlay": "Capital Outlay",
    "Capitalized Expenditures": "Capital Outlay", "Facilities Maintenance": "Facilities Maintenance",
    "Programmatic Projects": "Programmatic Projects", "Overhead and Allocations": "Overhead and Allocations",
}
SERVICE_CHARS = {"Non-Personnel Services", "City Grant Program", "Other Support/Care of Persons",
                 "Aid Assistance", "Aid Payments"}
EXPENDITURE_CHARS = SERVICE_CHARS | {"Materials & Supplies", "Capital Outlay", "Facilities Maintenance",
                                     "Programmatic Projects", "Overhead and Allocations"}

def main():
    parts = []
    for f in sorted(glob.glob(os.path.join(RAW, "payments_agg_fy*.csv"))):
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        parts.append(d)
    p = pd.concat(parts, ignore_index=True)
    for c in ["paid", "pending", "n_lines"]:
        p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
    p["fiscal_year"] = p.fiscal_year.astype(int)
    p["char_group"] = p.character.map(CHAR_MAP).fillna(p.character)
    p["spend_class"] = p.char_group.map(lambda c: "expenditure" if c in EXPENDITURE_CHARS else "balance_sheet_or_other")
    p["service_class"] = p.char_group.map(lambda c: "contracted_services" if c in SERVICE_CHARS else "other")
    p["vendor"] = p.vendor.str.strip()
    p.to_parquet(os.path.join(INT, "payments.parquet"))
    print(len(p), "rows; FY", p.fiscal_year.min(), p.fiscal_year.max())
    print(p.groupby(["fiscal_year", "spend_class"]).paid.sum().unstack().div(1e9).round(2))

if __name__ == "__main__":
    main()
