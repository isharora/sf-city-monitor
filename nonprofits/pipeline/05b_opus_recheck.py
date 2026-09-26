"""Second opinion: re-adjudicate every accepted Sonnet (pass-1) match with claude-opus-5-5 (effort high),
using the same candidate list. Disagreements are written for hand review; resolutions go in
data/manual/match_overrides.csv (vendor, ein or NONE, note), which 10_core.py applies.
Output: data/interim/opus_recheck.parquet, data/validation/opus_disagreements.csv
"""
import os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
_spec = importlib.util.spec_from_file_location("adj", os.path.join(os.path.dirname(__file__), "05_adjudicate.py"))
adj = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(adj)

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")

def main():
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet"))
    v = pd.read_parquet(os.path.join(INT, "vendors.parquet")).set_index("vendor", drop=False)
    c = pd.read_parquet(os.path.join(INT, "candidates.parquet"))
    c = c[c.score >= 85]
    todo = m[(m.matched_ein != "NONE") & (m["pass"] == 1)]
    groups = {k: adj.pick_cands(g) for k, g in c[c.vendor.isin(set(todo.vendor))].groupby("vendor")}
    biz = adj.build_biz_index()
    jobs = [(adj.adjudicate, v.loc[k], groups[k], biz, "claude-opus-5-5", "high", "match_recheck_opus") for k in todo.vendor if k in groups]
    print("rechecking", len(jobs))
    r = pd.DataFrame(adj.run_parallel(jobs, workers=12))
    r.to_parquet(os.path.join(INT, "opus_recheck.parquet"))
    x = todo[["vendor", "matched_ein", "confidence", "rationale"]].merge(
        r[["vendor", "matched_ein", "confidence", "rationale"]], on="vendor", suffixes=("_sonnet", "_opus"))
    dis = x[x.matched_ein_sonnet != x.matched_ein_opus].join(v[["total_paid"]], on="vendor")
    dis.sort_values("total_paid", ascending=False).to_csv(os.path.join(BASE, "validation", "opus_disagreements.csv"), index=False)
    print("agreement", round(1 - len(dis) / len(x), 4), "disagreements", len(dis), "$", round(dis.total_paid.sum() / 1e6, 1), "M")

if __name__ == "__main__":
    main()
