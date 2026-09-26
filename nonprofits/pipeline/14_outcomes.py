"""Descriptive comparison of departments' nonprofit spending with published outcome measures.

Pairs (department code -> measures), nominal and real (FY2025 $, SF CPI-U):
  HOM: households placed = PSH move-ins + Rapid Rehousing move-ins + Problem Solving resolutions
       (FY2018-22: sums of HSH monthly scorecard counts, not deduplicated; FY2023+: official annual),
       people exiting homelessness to permanent housing (FY2023+), shelter beds, PIT counts
  CHF (DCYF): children and youth served by DCYF grants (FY2019+)
  DPH: unique mental-health and substance-use clients in SFHN/BHS (FY2020+)
  HSA: home-delivered meals to older people (FY2013+)
  ECN: job placement rate (FY2013+)
Output: data/interim/results/outcomes_vs_spending.csv, outcomes_ratios.csv
No causal claim: spending covers many services beyond each measure; see ANALYSIS.md.
"""
import os
import pandas as pd

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")
RES = os.path.join(INT, "results")

def main():
    o = pd.read_csv(os.path.join(BASE, "outcomes", "outcomes.csv"))
    o = o[o.period_type.fillna("fiscal_year").str.startswith("fiscal") | o.measure_id.str.startswith("PIT")]
    npay = pd.read_parquet(os.path.join(INT, "np_payments.parquet"))
    cpi = pd.read_parquet(os.path.join(INT, "cpi.parquet")).set_index("fy").deflator_to_fy2025
    spend = npay.groupby(["department_code", "fiscal_year"]).paid.sum().unstack(0)
    def m(mid):
        s = o[o.measure_id == mid].drop_duplicates("fiscal_year").set_index("fiscal_year").value
        return s
    rows = []
    placed = pd.concat([m("SCM-HOM-ecf75eac").add(m("SCM-HOM-25057c1f"), fill_value=0).add(m("SCM-HOM-50792742"), fill_value=0),
                        m("CPM-HOM-0490c63a").add(m("CPM-HOM-70c2574e"), fill_value=0).add(m("CPM-HOM-effe2874"), fill_value=0)])
    placed = placed[~placed.index.duplicated(keep="last")]
    series = {
        ("HOM", "households_placed_psh_rrh_ps"): placed,
        ("HOM", "people_exiting_to_permanent_housing"): m("CPM-HOM-511f3451"),
        ("HOM", "shelter_beds"): m("CPM-HOM-bc3a6b7c"),
        ("HOM", "pit_total"): m("PIT-TOTAL"),
        ("HOM", "pit_unsheltered"): m("PIT-UNSHELTERED"),
        ("CHF", "children_youth_served"): m("CPM-CHF-9112ab93"),
        ("DPH", "unique_mental_health_clients"): m("CPM-DPH-3cc2f17c"),
        ("DPH", "unique_substance_use_clients"): m("CPM-DPH-0178fabb"),
        ("HSA", "home_delivered_meals_older_adults"): m("CPM-HSA-eb29a833"),
        ("ECN", "job_placement_rate"): m("CPM-ECN-7cd9e171"),
    }
    for (dept, name), s in series.items():
        for fy, val in s.items():
            fy = int(fy)
            sp = spend[dept].get(fy) if dept in spend else None
            rows.append({"department_code": dept, "measure": name, "fiscal_year": fy, "value": val,
                         "nonprofit_paid": sp, "nonprofit_paid_real2025": sp * cpi.get(fy) if sp is not None and fy in cpi else None,
                         "derived_sum_not_deduplicated": bool(name == "households_placed_psh_rrh_ps" and fy <= 2022)})
    d = pd.DataFrame(rows).sort_values(["department_code", "measure", "fiscal_year"])
    d["real_dollars_per_unit"] = d.nonprofit_paid_real2025 / d.value
    d.to_csv(os.path.join(RES, "outcomes_vs_spending.csv"), index=False)
    # growth comparisons over overlapping spans.
    # Red-team correction: the households-placed series is spliced (FY2018-22 = sums of monthly scorecard counts,
    # FY2023+ = the annual performance measure), and FY2018 was HSH's first full year while homelessness contracts
    # were still moving from HSA. So the first-to-last comparison is kept but flagged, and consistent windows are added.
    out = []
    def add(dept, name, g, a_fy, b_fy, consistent, note):
        g = g.set_index("fiscal_year")
        if a_fy in g.index and b_fy in g.index:
            a, b = g.loc[a_fy], g.loc[b_fy]
            out.append({"department_code": dept, "measure": name, "fy_from": int(a_fy), "fy_to": int(b_fy),
                        "real_spend_change": b.nonprofit_paid_real2025 / a.nonprofit_paid_real2025 - 1,
                        "measure_change": b.value / a.value - 1, "consistent_series": consistent, "note": note})
    for (dept, name), g in d.dropna(subset=["nonprofit_paid_real2025", "value"]).groupby(["department_code", "measure"]):
        g = g.sort_values("fiscal_year")
        if dept == "HOM":
            g = g[g.fiscal_year >= 2018]  # HSH's first full fiscal year; earlier homelessness contracts sat in HSA
        if name.endswith("_rate"):
            continue  # a rate is not a volume; no spend-per-unit comparison
        if len(g) < 2:
            continue
        if name == "households_placed_psh_rrh_ps":
            add(dept, name, g, 2023, 2025, True, "one consistent series (annual performance measure); preferred comparison")
            add(dept, name, g, 2023, 2026, True, "one consistent series; FY2026 is the June year-to-date figure")
            add(dept, name, g, 2019, 2025, False, "spliced series (FY2019 from monthly scorecard sums)")
            add(dept, name, g, 2018, 2026, False, "spliced series and HSH start-up base year; do not use alone")
            continue
        a, b = g.iloc[0], g.iloc[-1]
        out.append({"department_code": dept, "measure": name, "fy_from": int(a.fiscal_year), "fy_to": int(b.fiscal_year),
                    "real_spend_change": b.nonprofit_paid_real2025 / a.nonprofit_paid_real2025 - 1,
                    "measure_change": b.value / a.value - 1, "consistent_series": True, "note": None})
    pd.DataFrame(out).to_csv(os.path.join(RES, "outcomes_ratios.csv"), index=False)
    print(pd.DataFrame(out).round(3).to_string())

if __name__ == "__main__":
    main()
