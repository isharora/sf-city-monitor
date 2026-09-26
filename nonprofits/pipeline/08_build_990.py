"""Combine IRS e-file XML (parsed) and ProPublica extracts into an org-by-tax-year financial table.

Tax year convention: the IRS "tax period" is the month the fiscal year ENDS (e.g. 202406 = FY ending June
2024). We label each filing with `period_end` (YYYY-MM) and `fy_end_year`. When an org's fiscal year ends
June 30 it lines up with the city fiscal year exactly; otherwise the overlap is partial (documented).

Priority: e-file XML (has government grants line 1e, employees, officer detail); ProPublica fills years
without XML. For duplicate filings of the same period (amended returns), keep the latest submitted.

Outputs: data/interim/fin990.parquet (one row per EIN x period_end)
         data/interim/officers990.parquet (officer/key employee compensation rows)
         data/interim/schedule_i.parquet (grants paid to other organizations, Schedule I)
         data/interim/contractors990.parquet (Part VII-B top independent contractors)
"""
import glob, json, os
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

def main():
    rows, offs, grants, cons = [], [], [], []
    for f in glob.glob(os.path.join(BASE, "cache", "990", "*.json")):
        d = json.load(open(f))
        if not d.get("form") or not d.get("tax_period_end"):
            continue
        ein = (d.get("ein") or "").zfill(9)
        pe = d["tax_period_end"][:7]
        base = {k: v for k, v in d.items() if not isinstance(v, (list, dict))}
        base["ein"] = ein
        base["period_end"] = pe
        base["source"] = "irs_xml"
        rows.append(base)
        for o in d.get("officers", []):
            offs.append({"ein": ein, "period_end": pe, "object_id": d["object_id"], **o})
        for g in d.get("schedule_i_grants", []):
            g = dict(g); g["recipient_ein"] = (g.pop("ein", None) or "").zfill(9) if g.get("ein") else None
            grants.append({**g, "ein": ein, "period_end": pe, "object_id": d["object_id"]})
        for c in d.get("contractors", []):
            cons.append({"ein": ein, "period_end": pe, "object_id": d["object_id"], **c})
    x = pd.DataFrame(rows)
    if len(x):
        x = x.sort_values(["ein", "period_end", "amended", "return_ts"]).drop_duplicates(["ein", "period_end"], keep="last")
    # ProPublica
    pp = []
    for f in glob.glob(os.path.join(BASE, "cache", "propublica", "*.json")):
        d = json.load(open(f))
        if d.get("not_found"):
            continue
        org = d.get("organization", {})
        for fl in d.get("filings_with_data", []):
            tp = str(fl.get("tax_prd") or "")
            if len(tp) != 6:
                continue
            pp.append({"ein": str(fl.get("ein") or org.get("ein")).zfill(9), "period_end": f"{tp[:4]}-{tp[4:]}",
                       "form": {0: "990", 1: "990EZ", 2: "990PF"}.get(fl.get("formtype"), str(fl.get("formtype"))),
                       "total_revenue": fl.get("totrevenue"), "total_expenses": fl.get("totfuncexpns"),
                       "total_assets_eoy": fl.get("totassetsend"), "total_liabilities_eoy": fl.get("totliabend"),
                       "net_assets_eoy": fl.get("totnetassetend"), "officer_comp_partix": fl.get("compnsatncurrofcr"),
                       "program_service_revenue": fl.get("totprgmrevnue"), "contributions_grants": fl.get("totcntrbgfts"),
                       "salaries_etc": (fl.get("compnsatncurrofcr") or 0) + (fl.get("othrsalwages") or 0) if fl.get("othrsalwages") is not None else None,
                       "source": "propublica"})
    pp = pd.DataFrame(pp)
    if len(pp):
        pp = pp.drop_duplicates(["ein", "period_end"], keep="first")
        have = set(zip(x.ein, x.period_end)) if len(x) else set()
        pp_add = pp[[(e, p) not in have for e, p in zip(pp.ein, pp.period_end)]]
        fin = pd.concat([x, pp_add], ignore_index=True)
        # cross-check table: where both exist, compare total revenue
        if len(x):
            chk = x[["ein", "period_end", "total_revenue"]].merge(pp[["ein", "period_end", "total_revenue"]], on=["ein", "period_end"], suffixes=("_xml", "_pp"))
            chk.to_parquet(os.path.join(INT, "check_xml_vs_propublica.parquet"))
            ok = (abs(chk.total_revenue_xml - chk.total_revenue_pp) <= 1).mean()
            print("XML vs ProPublica total revenue agreement:", round(ok, 4), "on", len(chk))
    else:
        fin = x
    fin["fy_end_year"] = fin.period_end.str[:4].astype(int)
    fin["fy_end_month"] = fin.period_end.str[5:7].astype(int)
    fin = fin.sort_values(["ein", "period_end"])
    fin.to_parquet(os.path.join(INT, "fin990.parquet"))
    pd.DataFrame(offs).to_parquet(os.path.join(INT, "officers990.parquet"))
    pd.DataFrame(grants).to_parquet(os.path.join(INT, "schedule_i.parquet"))
    pd.DataFrame(cons).to_parquet(os.path.join(INT, "contractors990.parquet"))
    print("fin rows", len(fin), "EINs", fin.ein.nunique(), "xml rows", len(x), "officer rows", len(offs), "sched I", len(grants))

if __name__ == "__main__":
    main()
