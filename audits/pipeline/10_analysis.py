"""Step 10: analysis. Reads data/work/rows_final.json (rows + dollars + repeats +
consequence, produced by 11_export_site.py's prepare step) and writes
data/analysis/analysis.json and CSV tables used in ANALYSIS.md.

Definitions
- known status: status != unknown
- implementation rate (primary) = implemented / known-status rows
- implementation rate (strict)  = implemented / all rows
- 'still open' = latest recorded status open or in_progress, age measured from
  date issued to the as-of date (2026-09-26); 'not recorded implemented' adds unknown.
- time to implement: months_to_close (report date -> first follow-up recording
  implemented); Kaplan-Meier with open/in-progress rows censored at their last follow-up.
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from statistics import median

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, RAW  # noqa

WORK = os.path.join(DATA, "work")
OUT = os.path.join(DATA, "analysis")
os.makedirs(OUT, exist_ok=True)
AS_OF = date(2026, 9, 26)
KNOWN = lambda r: r["status"] != "unknown"


def q(vals, p):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return round(v[f] + (v[c] - v[f]) * (k - f), 1)


def age_years(r):
    return (AS_OF - date.fromisoformat(r["date_issued"])).days / 365.25 if r.get("date_issued") else None


def km(rows):
    """Kaplan-Meier estimate of time to implementation (months)."""
    pts = []
    for r in rows:
        if r["status"] == "implemented" and r.get("months_to_close") is not None:
            pts.append((r["months_to_close"], 1))
        elif r["status"] in ("open", "in_progress") and r.get("date_issued") and r.get("last_followup"):
            t = (date.fromisoformat(r["last_followup"]) - date.fromisoformat(r["date_issued"])).days / 30.4375
            pts.append((max(0.0, t), 0))
        elif r["status"] in ("not_implementing", "closed_other") and r.get("date_issued") and r.get("status_date"):
            # competing outcome: treated as never implemented -> censor at +inf (kept in risk set)
            pts.append((1e9, 0))
    pts.sort()
    n = len(pts)
    s, curve, at_risk = 1.0, [], n
    i = 0
    while i < len(pts):
        t = pts[i][0]
        d = sum(1 for x in pts if x[0] == t and x[1] == 1)
        c = sum(1 for x in pts if x[0] == t)
        if d:
            s *= (1 - d / at_risk)
            curve.append((round(t, 1), round(1 - s, 4)))
        at_risk -= c
        i += c
    def share_by(m):
        v = [y for x, y in curve if x <= m]
        return v[-1] if v else 0.0
    med = next((x for x, y in curve if y >= 0.5), None)
    return {"n": n, "events": sum(p[1] for p in pts), "median_months": med,
            "impl_by_12m": share_by(12), "impl_by_24m": share_by(24), "impl_by_60m": share_by(60)}


def rate_table(rows, key, min_n=1):
    g = defaultdict(list)
    for r in rows:
        k = key(r)
        if k is not None:
            g[k].append(r)
    out = []
    for k, rs in g.items():
        kn = [r for r in rs if KNOWN(r)]
        st = Counter(r["status"] for r in rs)
        mt = [r["months_to_close"] for r in rs if r.get("months_to_close") is not None]
        out.append({"group": k, "n": len(rs), "n_known": len(kn),
                    "implemented": st["implemented"], "in_progress": st["in_progress"], "open": st["open"],
                    "not_implementing": st["not_implementing"], "closed_other": st["closed_other"], "unknown": st["unknown"],
                    "impl_rate_known": round(st["implemented"] / len(kn), 3) if len(kn) >= min_n else None,
                    "impl_rate_all": round(st["implemented"] / len(rs), 3) if len(rs) >= min_n else None,
                    "median_months": q(mt, 0.5) if len(mt) >= 5 else None, "n_timed": len(mt)})
    return sorted(out, key=lambda x: -x["n"])


def write_csv(name, rows):
    if not rows:
        return
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    rows = json.load(open(os.path.join(WORK, "rows_final.json")))
    reports = json.load(open(os.path.join(WORK, "reports_final.json")))
    inv = json.load(open(os.path.join(RAW, "inventory.json")))
    dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
    A = {"as_of": AS_OF.isoformat()}

    # ---- corpus
    corpus = Counter()
    corpus_year = defaultdict(Counter)
    for d in inv:
        ok = dl.get(d["doc_id"], {}).get("status") in ("ok", "ok_low_text")
        k = (d["source"], d["doc_type"])
        corpus[k] += 1
        y = (d.get("date") or "")[:4] or (d["extra"].get("cgj_term") or "")[:4] or "unknown"
        corpus_year[d["source"]][y] += 1
    A["corpus"] = {f"{a}|{b}": n for (a, b), n in sorted(corpus.items())}
    A["corpus_by_year"] = {s: dict(sorted(c.items())) for s, c in corpus_year.items()}
    A["downloads"] = dict(Counter(r["status"] for r in dl.values()))
    A["reports_with_recs_by_source"] = dict(Counter(r["source"] for r in reports if r["n_recs"] > 0))
    A["reports_with_recs_by_source_year"] = {s: dict(sorted(Counter(r["date"][:4] for r in reports if r["n_recs"] > 0 and r["source"] == s and r.get("date")).items())) for s in ("csa", "bla", "cgj")}

    # ---- recommendations
    A["rows"] = len(rows)
    A["rows_by_source"] = dict(Counter(r["source"] for r in rows))
    A["rows_by_source_year"] = {s: dict(sorted(Counter(r["date_issued"][:4] for r in rows if r["source"] == s and r.get("date_issued")).items())) for s in ("csa", "bla", "cgj")}
    A["status_by_source"] = {s: dict(Counter(r["status"] for r in rows if r["source"] == s)) for s in ("csa", "bla", "cgj")}
    A["status_basis_by_source"] = {s: dict(Counter(r["status_basis"] for r in rows if r["source"] == s)) for s in ("csa", "bla", "cgj")}
    A["agreed_by_source"] = {s: dict(Counter(r["agreed"] for r in rows if r["source"] == s)) for s in ("csa", "bla", "cgj")}

    by_source = rate_table(rows, lambda r: r["source"])
    by_dept = rate_table(rows, lambda r: r["dept"], min_n=20)
    by_topic = rate_table(rows, lambda r: r["topic"])
    by_year = rate_table(rows, lambda r: (r["source"], r["date_issued"][:4]) if r.get("date_issued") else None)
    by_src_dept = rate_table(rows, lambda r: (r["source"], r["dept"]), min_n=15)
    write_csv("rates_by_source.csv", by_source)
    write_csv("rates_by_dept.csv", by_dept)
    write_csv("rates_by_topic.csv", by_topic)
    write_csv("rates_by_source_year.csv", [{**x, "group": "|".join(x["group"])} for x in by_year])
    write_csv("rates_by_source_dept.csv", [{**x, "group": "|".join(x["group"])} for x in by_src_dept])
    A["rates_by_source"] = by_source
    A["rates_by_topic"] = by_topic

    # ---- time to implement
    t = {}
    for s in ("csa", "bla", "cgj", "all"):
        rs = rows if s == "all" else [r for r in rows if r["source"] == s]
        mt = [r["months_to_close"] for r in rs if r.get("months_to_close") is not None]
        t[s] = {"n_timed": len(mt), "median": q(mt, 0.5), "p75": q(mt, 0.75), "p90": q(mt, 0.9), "km": km(rs),
                "basis": dict(Counter(r.get("implemented_basis") for r in rs if r.get("months_to_close") is not None))}
    A["time_to_implement"] = t
    A["time_by_topic"] = {tp: {"n": len(v), "median": q(v, 0.5)} for tp, v in
                          ((tp, [r["months_to_close"] for r in rows if r["topic"] == tp and r.get("months_to_close") is not None]) for tp in sorted({r["topic"] for r in rows})) if len(v) >= 10}

    # ---- open after 2 / 5 years
    op = [r for r in rows if r["status"] in ("open", "in_progress") and r.get("date_issued")]
    A["open_recorded"] = {
        "open_or_in_progress": len(op),
        "over_2y": sum(1 for r in op if age_years(r) > 2), "over_5y": sum(1 for r in op if age_years(r) > 5),
        "over_2y_by_source": dict(Counter(r["source"] for r in op if age_years(r) > 2)),
        "over_5y_by_source": dict(Counter(r["source"] for r in op if age_years(r) > 5)),
        "over_2y_by_dept": dict(Counter(r["dept"] for r in op if age_years(r) > 2).most_common(15)),
        "over_5y_by_dept": dict(Counter(r["dept"] for r in op if age_years(r) > 5).most_common(15)),
        "stale_followup_over_2y": sum(1 for r in op if age_years(r) > 2 and r.get("last_followup") and (AS_OF - date.fromisoformat(r["last_followup"])).days > 730),
    }

    # ---- disagreement
    resp = [r for r in rows if r["agreed"] != "none"]
    dis = rate = []
    ddept = defaultdict(Counter)
    for r in resp:
        ddept[r["dept"]][r["agreed"]] += 1
    dis = [{"dept": d, "n_responses": sum(c.values()), "disagree": c["disagree"], "partial": c["partial"],
            "agree": c["agree"], "disagree_share": round(c["disagree"] / sum(c.values()), 3),
            "disagree_or_partial_share": round((c["disagree"] + c["partial"]) / sum(c.values()), 3)}
           for d, c in ddept.items() if sum(c.values()) >= 15]
    dis.sort(key=lambda x: -x["disagree_share"])
    write_csv("disagreement_by_dept.csv", dis)
    A["disagreement_by_dept_top"] = dis[:15]
    A["disagreement_by_source"] = {s: dict(Counter(r["agreed"] for r in resp if r["source"] == s)) for s in ("csa", "bla", "cgj")}
    # agreement vs implementation
    av = defaultdict(Counter)
    for r in rows:
        if KNOWN(r) and r["agreed"] != "none":
            av[r["agreed"]][r["status"]] += 1
    A["agreed_vs_status"] = {k: dict(v) for k, v in av.items()}

    # ---- CGJ: said 'will be implemented' - were they?
    cg = [r for r in rows if r["source"] == "cgj" and r.get("cgj_response") == "will_be_implemented"]
    followed = [r for r in cg if any(e["basis"] != "cgj_response" and e.get("date") for e in r.get("events", []))]
    A["cgj_will_implement"] = {
        "n": len(cg), "n_with_later_followup": len(followed),
        "final_status_followed": dict(Counter(r["status"] for r in followed)),
        "final_status_all": dict(Counter(r["status"] for r in cg)),
        "by_dept_followed": {d: dict(c) for d, c in
                             ((d, Counter(r["status"] for r in followed if r["dept"] == d)) for d in {r["dept"] for r in followed}) if sum(c.values()) >= 10},
    }
    A["cgj_response_mix"] = dict(Counter(r.get("cgj_response") for r in rows if r["source"] == "cgj"))

    # ---- dollars
    dsum = defaultdict(float)
    dsum_kind = defaultdict(float)
    top_d = []
    for rp in reports:
        ind = rp.get("dollar_independent")
        f = rp.get("dollar_findings") or []
        use = [f[i] for i in ind if 0 <= i < len(f)] if ind is not None else f
        use = [x for x in use if x["kind"] != "other"]
        tot = sum(x["amount_usd"] for x in use)
        if tot:
            dsum[(rp["source"], (rp.get("date") or "")[:4])] += tot
            for x in use:
                dsum_kind[(rp["source"], x["kind"])] += x["amount_usd"]
            top_d.append({"report": rp["id"], "title": rp["title"], "source": rp["source"], "date": rp.get("date"),
                          "total": round(tot), "n_findings": len(use), "url": rp["url"]})
    top_d.sort(key=lambda x: -x["total"])
    A["dollars_by_source_kind"] = {f"{a}|{b}": round(v) for (a, b), v in sorted(dsum_kind.items())}
    A["dollars_by_source_year"] = {f"{a}|{b}": round(v) for (a, b), v in sorted(dsum.items())}
    A["dollars_top_reports"] = top_d[:25]
    A["reports_with_dollar_findings"] = len(top_d)
    write_csv("dollar_findings_top_reports.csv", top_d)

    # ---- repeats
    rp_rows = [r for r in rows if r.get("repeat_of")]
    A["repeats"] = {"n": len(rp_rows), "share": round(len(rp_rows) / len(rows), 4),
                    "by_dept": dict(Counter(r["dept"] for r in rp_rows).most_common(15)),
                    "by_topic": dict(Counter(r["topic"] for r in rp_rows).most_common()),
                    "by_source": dict(Counter(r["source"] for r in rp_rows))}
    dept_n = Counter(r["dept"] for r in rows)
    A["repeats"]["share_by_dept"] = {d: round(n / dept_n[d], 3) for d, n in Counter(r["dept"] for r in rp_rows).items() if dept_n[d] >= 40}

    # ---- consequence
    opn = [r for r in rows if r["status"] in ("open", "in_progress", "unknown", "not_implementing")]
    A["consequence_hist_open"] = dict(sorted(Counter(r["consequence"]["score"] for r in opn).items()))
    json.dump(A, open(os.path.join(OUT, "analysis.json"), "w"), indent=1, default=str)
    print(json.dumps({k: A[k] for k in ("rows", "rows_by_source", "status_by_source", "time_to_implement", "open_recorded", "cgj_will_implement", "repeats")}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
