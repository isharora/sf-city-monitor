"""Step 12: commentary for the audits dashboard (DATA_CONTRACT_audits.md section 3; DESIGN.md section 4).

Rewritten by the red-team/commentary pass (redteam2). Every number, quote and dated fact in the
text is inserted through a placeholder so it is traced:

  {m:<metric>}  a number computed below from data/work/rows_final.json (+ clusters, reasons)
  {q:<quote>}   a verbatim quote, with the PDF document and page it comes from
  {x:<fact>}    a dated/external fact with the PDF page that supports it
  {k:<const>}   a definitional constant (statute section, score threshold)
  {slot}        a live-template slot filled by the site (no colon)

The trace goes to data/site/commentary/facts_au.json and data/redteam/commentary_trace.json.
pipeline/verify_commentary.py recomputes every metric independently from the published export
(data/site/) and checks every quote and fact against the PDF text; it must report zero untraced
or mismatched numbers.

Inputs: data/work/rows_final.json, data/work/reports_final.json, data/work/repeat_clusters.json,
data/redteam/reasons.json (pipeline/redteam2/reasons.py). Writes data/site/commentary/*.json.
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from statistics import median

sys.path.insert(0, os.path.dirname(__file__))
from common import DATA, SITE  # noqa

WORK = os.path.join(DATA, "work")
OUT = os.path.join(SITE, "commentary")
RT = os.path.join(DATA, "redteam")
os.makedirs(OUT, exist_ok=True)
os.makedirs(RT, exist_ok=True)
AUTHOR = "SF City Monitor analyst (numbers recomputed by pipeline/verify_commentary.py)"
SOURCES = ["audits/recs/recs_*.json", "audits/reports/reports.json", "audits/repeats/clusters.json", "audits/commentary/facts_au.json"]


# ------------------------------------------------------------------ formats (mirrored in verify_commentary.py)
def fmt_value(v, f):
    if f == "int":
        return f"{int(v):,}"
    if f == "pct":
        return f"{round(100 * v):d}%"
    if f == "pct1":
        return f"{100 * v:.1f}%"
    if f == "mo":
        return f"{round(v):d}"
    if f == "year":
        return str(int(v))
    raise ValueError(f)


# ------------------------------------------------------------------ quotes, facts, constants (checked against PDFs)
QUOTES = {
    "bos_formula": {"text": "supports the recommendation of the Civil Grand Jury, but does not have the operational authority to implement the recommendations",
                    "doc": "CGJS-2004-05", "page": 4},
    "csa_own_speed": {"text": "57 percent implemented within six months, 74 percent implemented within one year, and 86 percent implemented within two years",
                      "doc": "CON-2213", "page": 3},
    "csa_self_report": {"text": "departments report having implemented 96 percent of the 689 recommendations", "doc": "CON-1772", "page": 5},
    "csa_closed_mix": {"text": "two were no longer applicable, eight were fully implemented, and one was partially implemented", "doc": "CON-1454", "page": 2},
    # headline stories (verified word for word; data/redteam/stories_check.json)
    "awss_cover": {"text": "does not cover large parts of Supervisorial Districts 1, 4, 7 and 11, roughly one-third of the City\u2019s developed area",
                   "doc": "CGJ-2018-2019-a4a61434", "page": 44},
    "awss_capital": {"text": "Committing to entirely funding a single program out of context and without regard for the trade-offs of that commitment would "
                     "be out of step with the City\u2019s longstanding and highly regarded capital planning process", "doc": "CGJS-2018-19", "pages": [1, 2, 3]},
    "bla18_civ": {"text": "the immediate civilianization of at least 30 positions", "doc": "BLA-165267bf", "page": 9},
    "bla24_stopped": {"text": "stopped following the start of the COVID-19 pandemic and have not resumed", "doc": "BLA-48c11f71", "page": 109},
    "bla24_unable": {"text": "was unable to share details on any positions that have been civilianized since FY 2019-20", "doc": "BLA-48c11f71", "page": 109},
    "sfpd_noimpact": {"text": "hiring civilians has little-to-no impact on sworn overtime costs", "doc": "BLA-48c11f71", "page": 128},
    "mayor_ch6": {"text": "requires Chapter 6 departments to document, evaluate, and report the performance of all contractors", "doc": "CGJS-2014-15", "page": 1},
    "bla_db": {"text": "are not using the City\u2019s contractor performance and evaluation database, as required by section 6.26", "doc": "BLA-f9cb966a", "page": 10},
    "dph_improve": {"text": "many improvements are needed for DPH to monitor and manage City Option and SFHP more appropriately, effectively, and efficiently",
                    "doc": "CON-3045", "page": 3},
    "dph_resp": {"text": "is working with other city agencies and stakeholders to manage the City Option program, which has been implementing significant "
                 "policy and program changes", "doc": "CON-3533", "page": 2},
    "csa25_list": {"text": "as of June 30, 2025, 7 recommendations, addressed to two departments, were not implemented more than two years after issuance",
                   "doc": "CON-3533", "page": 2},
    "pi_closed": {"text": "Of the 91 recommendations made in 13 Public Integrity assessments and audits, 86 (95%) of the recommendations are closed",
                  "doc": "CON-3624", "page": 4},
    "pi_def": {"text": "the response provided by the departments described sufficient action to implement the recommendation or an acceptable alternative",
               "doc": "CON-3624", "page": 4},
    "pi_ig": {"text": "The new Inspector General may evaluate the closed and open recommendations for follow-up to confirm the department\u2019s reported "
              "implementation status", "doc": "CON-3624", "page": 4},
}
FACTS = {
    "csa_program_start": {"text": "July 2010", "doc": "CON-1772", "page": 10, "needle": r"July 1, 2010"},
    "csa_window_end": {"text": "June 2013", "doc": "CON-2213", "page": 3, "needle": r"June 30, 2013"},
    "cite_con2213": {"text": "CON-2213, p. 3", "doc": "CON-2213", "page": 3, "needle": r"57 percent implemented within six months"},
    "cite_con1772": {"text": "CON-1772, p. 5", "doc": "CON-1772", "page": 5, "needle": r"report having implemented 96 percent"},
    "cite_con1454": {"text": "CON-1454, p. 2", "doc": "CON-1454", "page": 2, "needle": r"no longer applicable"},
    "cite_cgjs0405": {"text": "CGJS-2004-05, p. 4", "doc": "CGJS-2004-05", "page": 4, "needle": r"operational authority"},
    "jury_0405": {"text": "2004-05", "doc": "CGJS-2004-05", "page": 4, "needle": r"2004-05"},
    "d_bla18": {"text": "2018", "doc": "BLA-165267bf", "date": "year"},
    "d_bla24": {"text": "December 2024", "doc": "BLA-48c11f71", "date": "month_year"},
    "d_bla24b": {"text": "December 2024", "doc": "BLA-f9cb966a", "date": "month_year"},
    "d_cgj19": {"text": "2019", "doc": "CGJ-2018-2019-a4a61434", "date": "year"},
    "d_con3045": {"text": "2022", "doc": "CON-3045", "date": "year"},
    "d_2016": {"text": "2016", "doc": "CGJS-2014-15", "page": 1, "needle": r"2016"},
    "d_pi2020": {"text": "2020", "doc": "CON-3624", "page": 3, "needle": r"Issued from 2020"},
    "c_bla18_p9": {"text": "BLA-165267bf, p. 9", "doc": "BLA-165267bf", "page": 9, "needle": r"civilianization of at least 30"},
    "c_bla24_p109": {"text": "BLA-48c11f71, p. 109", "doc": "BLA-48c11f71", "page": 109, "needle": r"have not resumed"},
    "c_p128": {"text": "p. 128", "doc": "BLA-48c11f71", "page": 128, "needle": r"little-to-no impact"},
    "c_cgjs1415_p1": {"text": "CGJS-2014-15, p. 1", "doc": "CGJS-2014-15", "page": 1, "needle": r"Chapter 6"},
    "c_blaf9_p10": {"text": "BLA-f9cb966a, p. 10", "doc": "BLA-f9cb966a", "page": 10, "needle": r"section 6\.26"},
    "c_cgj19_p44": {"text": "CGJ-2018-2019-a4a61434, p. 44", "doc": "CGJ-2018-2019-a4a61434", "page": 44, "needle": r"one-third"},
    "c_cgjs1819": {"text": "CGJS-2018-19, pp. 1-3", "doc": "CGJS-2018-19", "pages": [1, 2, 3], "needle": r"capital planning process"},
    "c_cgjs1819_p4": {"text": "p. 4", "doc": "CGJS-2018-19", "page": 4, "needle": r"EFWS|Emergency Firefighting Water"},
    "c_con3533_p2": {"text": "CON-3533, p. 2", "doc": "CON-3533", "page": 2, "needle": r"City Option"},
    "c_con3045_p3": {"text": "CON-3045, p. 3", "doc": "CON-3045", "page": 3, "needle": r"City Option"},
    "c_con3624_p4": {"text": "CON-3624, p. 4", "doc": "CON-3624", "page": 4, "needle": r"86 \(95%\)"},
}
CONSTS = {"ch6": "6", "pc_933_05": "933.05", "score_hi": "7", "score_min": "1", "score_max": "10"}


class W:
    """Fills placeholders and records a trace entry per inserted token."""

    def __init__(self, M, FMT, DEF):
        self.M, self.FMT, self.DEF, self.trace = M, FMT, DEF, []

    def __call__(self, view, field, s):
        def rep(mo):
            kind, key = mo.group(1), mo.group(2)
            if kind == "m":
                t = fmt_value(self.M[key], self.FMT[key])
                val = self.M[key]
            elif kind == "q":
                t, val = QUOTES[key]["text"], QUOTES[key]
            elif kind == "x":
                t, val = FACTS[key]["text"], FACTS[key]
            elif kind == "k":
                t, val = CONSTS[key], CONSTS[key]
            else:
                raise KeyError(kind)
            self.trace.append({"view": view, "field": field, "kind": kind, "id": key, "text": t,
                               "value": val if kind == "m" else None, "fmt": self.FMT.get(key) if kind == "m" else None,
                               "definition": self.DEF.get(key) if kind == "m" else None})
            return t
        return re.sub(r"\{([mqxk]):([a-z0-9_]+)\}", rep, s)


def main():
    rows = json.load(open(os.path.join(WORK, "rows_final.json")))
    reports = json.load(open(os.path.join(WORK, "reports_final.json")))
    clusters = json.load(open(os.path.join(WORK, "repeat_clusters.json")))
    reasons = json.load(open(os.path.join(RT, "reasons.json")))
    as_of = date(2026, 9, 26)
    M, FMT, DEF = {}, {}, {}

    def put(k, v, f, d):
        M[k], FMT[k], DEF[k] = v, f, d

    src = lambda s: [r for r in rows if r["source"] == s]
    known = lambda rs: [r for r in rs if r["status"] != "unknown"]
    impl = lambda rs: [r for r in rs if r["status"] == "implemented"]
    csa, cgj = src("csa"), src("cgj")
    csak, cgjk = known(csa), known(cgj)

    # corpus
    put("n_rows", len(rows), "int", "all recommendation rows")
    put("n_distinct", len({r["rec_uid"] for r in rows}), "int", "distinct recommendations (rec_uid)")
    put("n_reports", len(reports), "int", "reports with >=1 recommendation")
    put("year_max", max(int(r["date_issued"][:4]) for r in rows), "year", "latest year issued")
    put("bla_rows", len(src("bla")), "int", "BLA rows")
    put("unknown_share", sum(1 for r in rows if r["status"] == "unknown") / len(rows), "pct", "status unknown / all rows")
    put("impl_all_share", len(impl(rows)) / len(rows), "pct", "implemented / all rows (what the Implemented tile shows unfiltered)")
    # CSA
    put("csa_known", len(csak), "int", "CSA rows with a status")
    put("csa_impl", len(impl(csak)), "int", "CSA implemented")
    put("csa_rate", len(impl(csak)) / len(csak), "pct", "CSA implemented / CSA with status")
    agr = Counter(r["agreed"] for r in csa if r["agreed"] != "none")
    put("csa_agree_share", agr["agree"] / sum(agr.values()), "pct", "CSA agree / CSA with a recorded response")
    put("csa_dis_share", agr["disagree"] / sum(agr.values()), "pct", "CSA disagree / CSA with a recorded response")
    rl = [r for r in csak if r["status_basis"] not in ("csa_report_closed", "inferred_absent_from_open_over_2yrs_list")]
    put("csa_rl_share", sum(1 for r in impl(csak) if r["status_basis"] in ("csa_report_closed", "inferred_absent_from_open_over_2yrs_list")) / len(impl(csak)),
        "pct", "CSA implemented whose basis is report closure or absence inference / CSA implemented")
    put("csa_n_rl", len(rl), "int", "CSA with status from recommendation-level evidence")
    put("csa_rate_rl", len(impl(rl)) / len(rl), "pct", "implemented among CSA recommendation-level evidence")
    ver = [r for r in csak if r["status_basis"] in ("csa_field_followup", "pi_status_update")]
    put("csa_n_ver", len(ver), "int", "CSA with auditor-verified status")
    put("csa_rate_ver", len(impl(ver)) / len(ver), "pct", "implemented among auditor-verified CSA")
    put("ver_share_all", sum(1 for r in impl(rows) if r["status_basis"] in ("csa_field_followup", "pi_status_update")) / len(impl(rows)),
        "pct", "auditor-verified implemented / all implemented")
    put("csa_ni_n", sum(1 for r in csak if r["status"] == "not_implementing"), "int", "CSA not_implementing")
    put("csa_open_n", sum(1 for r in csak if r["status"] in ("open", "in_progress")), "int", "CSA open or in progress")
    put("cgj_bosmyr_share", sum(1 for r in cgj if r["dept"] in ("BOS", "MYR")) / len(cgj), "pct", "CGJ rows answered by BOS or MYR / CGJ rows")
    put("csa_bosmyr_share", sum(1 for r in csa if r["dept"] in ("BOS", "MYR")) / len(csa), "pct", "CSA rows for BOS or MYR / CSA rows")
    for s, key in (("csa", "csa_fin"), ("cgj", "cgj_fin")):
        x = known([r for r in src(s) if r["topic"] == "finance"])
        put(key + "_n", len(x), "int", f"{s} finance-topic rows with status")
        put(key + "_rate", len(impl(x)) / len(x), "pct", f"{s} finance-topic implemented / with status")
    # CGJ
    put("cgj_known", len(cgjk), "int", "CGJ rows with a status")
    put("cgj_impl", len(impl(cgjk)), "int", "CGJ implemented")
    put("cgj_rate", len(impl(cgjk)) / len(cgjk), "pct", "CGJ implemented / with status")
    ni = [r for r in cgjk if r["status"] == "not_implementing"]
    put("cgj_ni", len(ni), "int", "CGJ not_implementing")
    put("cgj_ni_bm", sum(1 for r in ni if r["dept"] in ("BOS", "MYR")), "int", "CGJ not_implementing by BOS or MYR")
    put("cgj_ni_bm_share", sum(1 for r in ni if r["dept"] in ("BOS", "MYR")) / len(ni), "pct", "share of CGJ not_implementing by BOS or MYR")
    put("ni_bos", sum(1 for r in ni if r["dept"] == "BOS"), "int", "CGJ not_implementing, BOS")
    put("ni_myr", sum(1 for r in ni if r["dept"] == "MYR"), "int", "CGJ not_implementing, MYR")
    put("cgj_ni_ex", sum(1 for r in ni if r["dept"] not in ("BOS", "MYR")), "int", "CGJ not_implementing excl. BOS, MYR")
    put("cgj_impl_ex", sum(1 for r in impl(cgjk) if r["dept"] not in ("BOS", "MYR")), "int", "CGJ implemented excl. BOS, MYR")
    g = {}
    for r in cgjk:
        g.setdefault(r["rec_uid"], []).append(r["status"])
    put("cgj_rec_any_rate", sum(1 for v in g.values() if "implemented" in v) / len(g), "pct", "CGJ distinct recs with any respondent implemented / distinct recs with status")
    # reasons (disagree responses, model-classified)
    items = reasons["items"]
    rs = lambda sel: [x for x in items if sel(x)]
    cg = rs(lambda x: x["source"] == "cgj")
    put("cgj_wn_n", len(cg), "int", "CGJ 'will not be implemented' responses classified")
    for key, cat in (("r_auth", "not_our_authority"), ("r_exist", "already_done_or_existing_process"), ("r_alt", "alternative_approach"),
                     ("r_legal", "legal_or_contract_constraint"), ("r_cost", "cost_or_resources"), ("r_merit", "policy_disagreement"), ("r_none", "no_reason_given")):
        put(key, sum(1 for x in cg if x["primary"] == cat) / len(cg), "pct", f"CGJ will-not responses with primary reason {cat}")
    bos = rs(lambda x: x["dept"] == "BOS")
    for key, cat in (("bos_auth", "not_our_authority"), ("bos_exist", "already_done_or_existing_process"), ("bos_alt", "alternative_approach"), ("bos_merit", "policy_disagreement")):
        put(key, sum(1 for x in bos if x["primary"] == cat) / len(bos), "pct", f"BOS disagree responses with primary reason {cat}")
    bm = rs(lambda x: x["dept"] in ("BOS", "MYR"))
    put("r_bm_other", sum(1 for x in bm if x["primary"] in ("not_our_authority", "already_done_or_existing_process", "alternative_approach")) / len(bm),
        "pct", "BOS+MYR disagree responses citing authority, existing process or another route")
    # agreement
    def arate(rs_, a):
        x = [r for r in rs_ if r["agreed"] == a and r["status"] != "unknown"]
        return x, (len(impl(x)) / len(x) if x else None)
    _, M_pa = arate(rows, "agree")
    dis_all, M_pd = arate(rows, "disagree")
    put("pool_agree", M_pa, "pct", "implemented among agreed with status (pooled)")
    put("pool_dis", M_pd, "pct", "implemented among disagreed with status (pooled)")
    put("dis_cgj_share", sum(1 for r in dis_all if r["source"] == "cgj") / len(dis_all), "pct", "CGJ share of disagreed rows with status")
    put("cgj_hbi", sum(1 for r in cgj if r.get("cgj_response") == "has_been_implemented"), "int", "CGJ 'has been implemented' first responses")
    cd, _ = arate(csa, "disagree")
    put("csa_dis_n", len(cd), "int", "CSA disagreed with status")
    put("csa_dis_impl", len(impl(cd)), "int", "CSA disagreed, implemented")
    wb = [r for r in cgj if r.get("cgj_response") == "will_be_implemented" and any(e["basis"] == "cgj_status_tracker" and e.get("date") for e in r.get("events", []))]
    fs = Counter(r["status"] for r in wb)
    put("wbi_n", len(wb), "int", "CGJ 'will be implemented' with a later tracker entry")
    put("wbi_impl", fs["implemented"], "int", "... implemented")
    put("wbi_rate", fs["implemented"] / len(wb), "pct", "... implemented share")
    put("wbi_prog", fs["in_progress"], "int", "... in progress")
    put("wbi_rev", fs["not_implementing"], "int", "... later not_implementing")
    put("wbi_rev_rate", fs["not_implementing"] / len(wb), "pct", "... later not_implementing share")
    put("bos_rev", sum(1 for r in wb if r["status"] == "not_implementing" and r["dept"] == "BOS"), "int", "... reversals by BOS")
    b = [r for r in rows if r["dept"] == "BOS" and r["agreed"] != "none"]
    put("bos_n", len(b), "int", "BOS rows with a recorded response")
    put("bos_dis", sum(1 for r in b if r["agreed"] == "disagree"), "int", "BOS disagree")
    put("bos_share", sum(1 for r in b if r["agreed"] == "disagree") / len(b), "pct", "BOS disagree share")
    put("bos_cgj", sum(1 for r in b if r["source"] == "cgj"), "int", "BOS responses to CGJ")
    # time
    mt = [r["months_to_close"] for r in rows if r.get("months_to_close") is not None]
    put("n_timed", len(mt), "int", "implemented with months_to_close")
    put("med_all", median(mt), "mo", "median months_to_close")
    ct = [r for r in csa if r.get("months_to_close") is not None]
    put("csa_timed", len(ct), "int", "CSA timed")
    put("csa_timed_rc", sum(1 for r in ct if r.get("implemented_basis") == "csa_report_closed"), "int", "CSA timed by report closure")
    put("med_csa", median(r["months_to_close"] for r in ct), "mo", "CSA median months_to_close")
    put("n_inferred", sum(1 for r in rows if r["status_basis"] == "inferred_absent_from_open_over_2yrs_list"), "int", "CSA implemented by absence inference")
    # repeats
    rp = [r for r in rows if r.get("repeat_of")]
    byid = {r["id"]: r for r in rows}
    put("rep_n", len(rp), "int", "rows with repeat_of")
    put("rep_share", len(rp) / len(rows), "pct1", "repeat rows / all rows")
    put("rep_clusters", len({r["repeat_cluster"] for r in rp}), "int", "distinct clusters among repeat rows")
    put("rep_pred_impl", sum(1 for r in rp if byid[r["repeat_of"]]["status"] == "implemented"), "int", "repeats whose predecessor is implemented")
    put("rep_cross", sum(1 for r in rp if byid[r["repeat_of"]]["source"] != r["source"]), "int", "repeats whose predecessor is from another body")
    val = json.load(open(os.path.join(SITE, "repeats", "clusters.json")))["validation"]
    put("val_judge", val["judge_confirms_pos"], "pct", "independent judge confirms sampled pairs")
    put("val_pairs", val["pairs_judged_pos"], "int", "pairs judged")

    def chain(dept, pat):
        c = [c for c in clusters if c["dept"] == dept and c.get("used_for_repeat_of") and re.search(pat, c["theme"], re.I)]
        c = max(c, key=lambda c: len({byid[i]["report"] for i in c["members"] if i in byid}))
        m = [byid[i] for i in c["members"] if i in byid]
        ys = [int(r["date_issued"][:4]) for r in m]
        return len({r["report"] for r in m}), max(ys) - min(ys)
    for key, dept, pat in (("ch_air", "AIR", r"certified financial report"), ("ch_mta", "MTA", r"reconcil.*monthly parker"),
                           ("ch_pol", "POL", r"civilian"), ("ch_dpw", "DPW", r"contractor performance evaluation used in contractor selection")):
        n, y = chain(dept, pat)
        put(key + "_reps", n, "int", f"reports in the {dept} cluster matching /{pat}/")
        put(key + "_yrs", y, "int", f"year span of that cluster")
    # open
    age = lambda r: (as_of - date.fromisoformat(r["date_issued"])).days / 365.25
    op = [r for r in rows if r["status"] in ("open", "in_progress")]
    o2 = [r for r in op if age(r) > 2]
    put("open_n", len(op), "int", "open or in progress")
    put("open2", len(o2), "int", "... issued > 2 years before as-of")
    put("open5", sum(1 for r in op if age(r) > 5), "int", "... > 5 years")
    put("open2_stale", sum(1 for r in o2 if r.get("last_followup") and (as_of - date.fromisoformat(r["last_followup"])).days > 730), "int", "... last follow-up > 2 years ago")
    put("open2_cgj", sum(1 for r in o2 if r["source"] == "cgj"), "int", "... from CGJ")
    fu = sorted(int(r["last_followup"][:4]) for r in o2 if r.get("last_followup"))
    put("open2_medfu", fu[len(fu) // 2], "year", "median year of last follow-up among open > 2 years (upper median)")
    put("cityopt_open", sum(1 for r in csa if r["report"] == "CON-3045" and r["status"] in ("open", "in_progress")), "int", "CON-3045 (City Option audit) rows open or in progress")
    put("open_hi", sum(1 for r in op if r["consequence"]["score"] >= 7), "int", "open with consequence score >= 7")
    # chart callouts
    y07 = [r for r in cgj if r["date_issued"][:4] == "2007"]
    put("cgj07", len(y07), "int", "CGJ rows issued 2007")
    put("cgj07_top", Counter(r["report"] for r in y07).most_common(1)[0][1], "int", "largest single CGJ report in 2007 (rows)")
    rep_title = {r["id"]: r["title"] for r in reports}
    put("pol08", sum(1 for r in csa if r["date_issued"][:4] == "2008" and rep_title.get(r["report"], "").startswith("Organizational Assessment of the San Francisco Police")),
        "int", "CSA rows issued 2008 from the two SFPD organizational assessment reports")
    y = lambda s, yy: [r for r in src(s) if r["date_issued"][:4] == yy]
    put("csa09_impl_all", len(impl(y("csa", "2009"))) / len(y("csa", "2009")), "pct", "CSA 2009 implemented / all rows")
    put("csa10_impl_all", len(impl(y("csa", "2010"))) / len(y("csa", "2010")), "pct", "CSA 2010 implemented / all rows")

    w = W(M, FMT, DEF)
    files = {}

    def com(view, headline, paragraphs, templates=(), caveats=(), annotations=()):
        obj = {"sample": False, "view": view, "author": AUTHOR,
               "headline": w(view, "headline", headline),
               "paragraphs": [w(view, f"paragraphs[{i}]", p) for i, p in enumerate(paragraphs)],
               "annotations": [{**a, "text": w(view, f"annotations[{i}]", a["text"])} for i, a in enumerate(annotations)],
               "templates": [{**t, "template": w(view, f"templates[{i}]", t["template"]), "fallback": w(view, f"templates[{i}].fallback", t["fallback"])}
                             for i, t in enumerate(templates)],
               "caveats": [{"severity": c[0], "text": w(view, f"caveats[{i}]", c[1])} for i, c in enumerate(caveats)],
               "sources": SOURCES}
        files[view] = obj

    TF = "Only {recs_fmt} recommendations match, too few for stable shares; widen the years or clear a filter."

    # ------------------------------------------------------------------ au-overview
    com("au-overview",
        "The Controller's auditors see {m:csa_rate} of their followed-up recommendations closed as implemented ({m:csa_impl} of {m:csa_known}); "
        "departments report implementing {m:cgj_rate} of Civil Grand Jury recommendations ({m:cgj_impl} of {m:cgj_known}), a gap that reflects "
        "what each body asks for as much as how departments respond.",
        ["Three bodies tell San Francisco departments what to fix, and they are not interchangeable. The Controller's City Services Auditor (CSA) "
         "writes narrow operational recommendations (financial controls, governance, payroll, IT); departments agree with {m:csa_agree_share} of them "
         "at publication, and CSA chases each one through its own follow-up program. The Civil Grand Jury, a volunteer panel with no enforcement power, "
         "often asks for new laws, budgets or reorganizations: {m:cgj_bosmyr_share} of Grand Jury rows are answered by the Board of Supervisors or the "
         "Mayor's Office, against {m:csa_bosmyr_share} of CSA rows. Even within one topic the asks differ in scale: financial-control recommendations "
         "show {m:csa_fin_rate} implemented for CSA (n = {m:csa_fin_n}) and {m:cgj_fin_rate} for the Grand Jury (n = {m:cgj_fin_n}).",
         "The CSA figure is solid as a record of what CSA closed and softer as proof of what changed. {m:csa_rl_share} of CSA's implemented statuses come "
         "from a whole report being closed, or from the report's absence on CSA's annual list of items open more than two years, rather than from a "
         "recommendation-by-recommendation check. Counting only recommendation-level evidence the rate is {m:csa_rate_rl} (n = {m:csa_n_rl}); where CSA "
         "auditors verified in the field or in Public Integrity updates it is {m:csa_rate_ver} (n = {m:csa_n_ver}). CSA itself words its totals carefully: "
         "\"{q:csa_self_report}\" ({x:cite_con1772}).",
         "Coverage is uneven, and it changes how the tiles read. {m:unknown_share} of rows have no follow-up status: all {m:bla_rows} Budget and "
         "Legislative Analyst recommendations (the BLA publishes no follow-up), Controller reports issued before CSA's follow-up program began in "
         "{x:csa_program_start} or outside it (City Performance, Whistleblower), and Grand Jury reports older than the Controller's tracking. The "
         "Implemented tile divides by every matched recommendation, including those never followed up, so unfiltered it reads {m:impl_all_share}; the "
         "rates in the finding use only recommendations with a recorded status."],
        templates=[{"id": "ov", "template": "{recs_fmt} recommendations from {reports_fmt} reports issued {years}. {impl_share} of all of them are recorded as "
                    "implemented (those never followed up count as not recorded); {open_fmt} were open or in progress at their last follow-up; median "
                    "{median_months} months from report to recorded implementation.", "requires": {"recs_min": 20}, "fallback": TF}],
        caveats=[("high", "Status is mostly self-reported. Only {m:ver_share_all} of implemented statuses rest on an auditor's own check (CSA field "
                  "follow-ups and Public Integrity updates); Grand Jury statuses are departments' own words, copied by the Controller."),
                 ("high", "The Controller and Grand Jury rates are not a like-for-like comparison. CSA asks are narrow and agreed at publication; Grand "
                  "Jury asks are often policy or budget choices for elected officials. Read the gap as a difference in leverage and scope, not as "
                  "departments ignoring auditors."),
                 ("medium", "The BLA publishes no follow-up, so all {m:bla_rows} BLA recommendations have no status; they are in the counts but never in a rate."),
                 ("medium", "Grand Jury recommendations are counted once per responding department ({m:n_rows} rows for {m:n_distinct} distinct "
                  "recommendations). Counted once per recommendation, with any respondent implementing it, the Grand Jury rate is {m:cgj_rec_any_rate}."),
                 ("low", "Reports from {m:year_max} run only to the as-of date, and recent years have had little time for follow-up.")],
        annotations=[{"chart": "au_issued", "x": 2007, "text": "{m:cgj07} Grand Jury rows; one disaster-readiness report has {m:cgj07_top}", "placement": "left"},
                     {"chart": "au_issued", "x": 2008, "text": "Two consultant assessments of SFPD for the Controller: {m:pol08} rows", "placement": "right"}])

    # ------------------------------------------------------------------ au-status
    com("au-status",
        "For the Civil Grand Jury, 'will not be implemented' ({m:cgj_ni}) outnumbers 'implemented' ({m:cgj_impl}), but the Board of Supervisors and "
        "the Mayor's Office give {m:cgj_ni_bm} of those refusals; for every other respondent together, implemented leads {m:cgj_impl_ex} to {m:cgj_ni_ex}.",
        ["A 'will not be implemented' answer is a decision, and usually a reasoned one. Across all {m:cgj_wn_n} Grand Jury 'will not' responses, "
         "{m:r_auth} say the recommendation is outside the respondent's authority or belongs to another body, {m:r_exist} that it is already done or "
         "covered by an existing process, {m:r_alt} propose a different approach, {m:r_legal} cite a legal or contractual constraint and {m:r_cost} "
         "cite cost; {m:r_merit} dispute the merits and {m:r_none} give no reason. The Board's standard wording makes the point: it "
         "\"{q:bos_formula}\" (Controller tracker for the {x:jury_0405} jury, {x:cite_cgjs0405}).",
         "Status by department mostly measures how often a department is audited, and by whom. Respondents that answer many Grand Jury reports (the "
         "Board, the Mayor's Office, the Controller as a respondent) carry most refusals, while in CSA audits only {m:csa_ni_n} recommendations are "
         "recorded as 'will not implement' and {m:csa_open_n} as open or in progress. The Controller tracks Grand Jury items only for a few years after "
         "each report, so an item frozen at 'in progress' may since have been finished.",
         "Emergency firefighting water shows what a reasoned refusal looks like. The {x:d_cgj19} Grand Jury found the high-pressure water system "
         "\"{q:awss_cover}\" ({x:c_cgj19_p44}) and asked for a financed plan to extend it. The Mayor, the Public Utilities Commission, the Fire "
         "Department and the City Administrator ultimately answered 'will not be implemented', arguing that \"{q:awss_capital}\" ({x:c_cgjs1819}). "
         "The Board of Supervisors reported the same recommendation implemented, through a planning study and a funding-options report ({x:c_cgjs1819_p4}). "
         "Whether that answer is prudent budgeting or avoidance is a policy judgment the data cannot settle."],
        templates=[{"id": "status", "template": "{recs_fmt} recommendations issued {years}, as shares of all of them: {impl_share} implemented, "
                    "{prog_share} in progress, {open_share} open, {notimpl_share} will not be implemented; the rest were closed another way or have no "
                    "follow-up status.", "requires": {"recs_min": 20}, "fallback": TF}],
        caveats=[("high", "Refusals are concentrated: the Board of Supervisors ({m:ni_bos}) and the Mayor's Office ({m:ni_myr}) account for "
                  "{m:cgj_ni_bm_share} of Grand Jury 'will not' statuses, and {m:r_bm_other} of their stated reasons say the matter belongs to another "
                  "official, is already covered, or will be handled another way."),
                 ("medium", "Reasons were classified by Claude Sonnet from the extracted summary of each printed response (one primary reason each, with a "
                  "stored confidence and rationale); treat the shares as approximate."),
                 ("medium", "CSA closes a report once every recommendation in it is resolved, and a closed report can include items found no longer "
                  "applicable (one closed follow-up: \"{q:csa_closed_mix}\", {x:cite_con1454}). Those are counted as implemented here."),
                 ("low", "Grand Jury tracker statuses are yearly; their dates are set to the end of the year.")],
        annotations=[{"chart": "au_impl", "x": 2010, "series": "csa", "text": "CSA follow-up records start with audits issued from {x:csa_program_start}", "placement": "right"},
                     {"chart": "au_impl", "x": 2024, "series": "cgj", "text": "Recent reports have had less time to be followed up", "placement": "left"}])

    # ------------------------------------------------------------------ au-time
    com("au-time",
        "Among implemented recommendations with a dated closure, half were recorded as implemented within {m:med_all} months of the report "
        "(n = {m:n_timed}), but for the Controller's audits that is mostly the date the whole report closed, so it overstates how long individual fixes took.",
        ["Time runs from the report date to the first follow-up that records the recommendation as implemented, so it is rounded up to the follow-up "
         "cadence: every six months for CSA, yearly for the Grand Jury tracker. For {m:csa_timed_rc} of the {m:csa_timed} timed CSA recommendations the "
         "date is when CSA closed the entire report, which happens only after the last recommendation in it is resolved. CSA's own "
         "recommendation-level counts are faster: for recommendations issued {x:csa_program_start} to {x:csa_window_end}, \"{q:csa_own_speed}\" "
         "({x:cite_con2213}).",
         "Medians describe only the recommendations that got done. The step curves also count the ones that never were, which is why Grand Jury cohorts "
         "flatten well below full implementation. {m:n_inferred} CSA recommendations are known to be implemented only because they dropped off CSA's "
         "two-year list; they have no month count, so they are missing from the bars and the histogram."],
        templates=[{"id": "time", "template": "{impl_fmt} recommendations issued {years} are recorded as implemented; among those with a dated closure, "
                    "median {median_months} months; a quarter took longer than {p75_months} months and a tenth longer than {p90_months}.", "requires": {"impl_min": 10},
                    "fallback": "Only {impl_fmt} implemented recommendations match, too few for percentiles; widen the years or clear a filter."}],
        caveats=[("high", "CSA times are upper bounds: most are whole-report closure dates, and CSA's own counts show most recommendations done well before "
                  "their report closes."),
                 ("medium", "The step curves count the {m:n_inferred} CSA recommendations closed by inference (no month count) as never implemented, so "
                  "CSA curves read low."),
                 ("medium", "Recommendations still open are not in the range bars (survivor bias); the step curves correct for this.")])

    # ------------------------------------------------------------------ au-agreement
    com("au-agreement",
        "Saying yes usually means doing it, but less than the pooled numbers suggest: Grand Jury respondents who promised 'will be implemented' were "
        "later recorded as implementing {m:wbi_rate} of the time ({m:wbi_impl} of {m:wbi_n}), while in the Controller's audits even recommendations "
        "departments disagreed with were mostly closed as implemented ({m:csa_dis_impl} of {m:csa_dis_n}).",
        ["Pooled across bodies, {m:pool_agree} of agreed and {m:pool_dis} of disagreed recommendations are recorded as implemented. Much of that contrast "
         "is built in. {m:dis_cgj_share} of disagreements with a known status are Grand Jury answers of 'will not be implemented', and for most of them "
         "the later status simply repeats the answer; on the agree side, {m:cgj_hbi} Grand Jury answers said 'has been implemented' at the outset. The "
         "cleaner test is the promise: of {m:wbi_n} 'will be implemented' answers with a later tracker entry, {m:wbi_impl} were recorded implemented, "
         "{m:wbi_prog} were still in progress and {m:wbi_rev} ({m:wbi_rev_rate}) were later changed to 'will not be implemented'.",
         "The Board of Supervisors disagreed or declined in {m:bos_dis} of {m:bos_n} recorded responses ({m:bos_share}), almost all ({m:bos_cgj}) to "
         "Grand Jury reports, and it accounts for {m:bos_rev} of the {m:wbi_rev} reversed promises. Read that as a legislature deciding what to "
         "legislate, fund or direct, not as a department ignoring auditors: among the Board's refusals, {m:bos_auth} say the matter belongs to another "
         "official or body, {m:bos_exist} that it is already covered, {m:bos_alt} that another route will be taken, and {m:bos_merit} dispute the merits.",
         "In the Controller's own audits disagreement is rare ({m:csa_dis_share} of recorded responses), and even then most were closed as implemented: the department's written response is printed with the report, and CSA keeps following up whatever the response."],
        templates=[{"id": "agree", "template": "{recs_fmt} recommendations issued {years}: {agree_share} agreed at publication, {partial_share} partially, "
                    "{disagree_share} disagreed, and the rest printed no response. {impl_agreed} of the agreed and {impl_disagreed} of the disagreed are "
                    "recorded as implemented (never followed up counts as not recorded).", "requires": {"recs_min": 20}, "fallback": TF}],
        caveats=[("high", "For the Grand Jury, response and outcome are not independent: 'will not be implemented' is both the answer and, usually, the "
                  "final status. Compare within one body, or use the 'will be implemented' promises."),
                 ("medium", "Grand Jury responses are mapped from Penal Code section {k:pc_933_05}: has been or will be implemented = agree, requires "
                  "further analysis = partial, will not be implemented = disagree."),
                 ("medium", "Many older Controller reports print no response table; those rows show 'no response recorded'.")])

    # ------------------------------------------------------------------ au-repeat
    com("au-repeat",
        "{m:rep_n} recommendations ({m:rep_share}) repeat an earlier recommendation to the same department on the same problem, in {m:rep_clusters} "
        "clusters; {m:rep_pred_impl} of them follow a predecessor recorded as implemented, so problems recur even after a recorded fix.",
        ["The longest chains are routine revenue controls audited again and again: Airport tenants' certified financial reports ({m:ch_air_reps} "
         "Controller reports over {m:ch_air_yrs} years) and SFMTA garage operators' reconciliation of monthly-parker cards ({m:ch_mta_reps} reports over "
         "{m:ch_mta_yrs} years). Two policy chains cross all three bodies: Police civilianization, raised in {m:ch_pol_reps} reports over "
         "{m:ch_pol_yrs} years, and contractor performance evaluation in Public Works construction, raised in {m:ch_dpw_reps} reports over "
         "{m:ch_dpw_yrs} years.",
         "A repeat means an oversight body raised the same problem again later. It does not by itself show that the earlier fix failed: sometimes the "
         "fix held and the problem returned with new staff or a new contractor, and {m:rep_cross} repeats come from a different body raising the issue "
         "on its own. Clusters were drawn by Claude Opus within each department, kept only when they span at least two reports in different years, and "
         "checked by an independent model ({m:val_judge} of {m:val_pairs} sampled pairs confirmed) and by hand.",
         "The two policy chains in detail. Police civilianization stalled rather than failed: in {x:d_bla18} the Budget and Legislative Analyst "
         "recommended \"{q:bla18_civ}\" ({x:c_bla18_p9}), which SFPD partially agreed to; in {x:d_bla24} it reported that SFPD's plans \"{q:bla24_stopped}\" "
         "and that SFPD \"{q:bla24_unable}\" ({x:c_bla24_p109}). SFPD's response was that \"{q:sfpd_noimpact}\" ({x:c_p128}). In city construction, the "
         "Mayor's Office reported a {x:d_2016} ordinance that \"{q:mayor_ch6}\" ({x:c_cgjs1415_p1}), yet in {x:d_bla24b} the BLA found the departments "
         "covered by Chapter {k:ch6} \"{q:bla_db}\" ({x:c_blaf9_p10})."],
        templates=[{"id": "repeat", "template": "{repeats_fmt} of {recs_fmt} recommendations issued {years} ({repeat_share}) repeat an earlier one to the "
                    "same department; the most common topic among them is {top_topic} ({top_topic_fmt}).", "requires": {"recs_min": 20}, "fallback": TF}],
        caveats=[("high", "Repeat coding is model-assisted judgment: an independent model confirmed {m:val_judge} of sampled pairs, so roughly one flagged "
                  "repeat in eight may be a related problem rather than the same one. The chains table links both reports so each can be checked."),
                 ("medium", "Same-type findings about different tenants or contractors (for example separate concession audits) are deliberately not "
                  "counted as repeats, which understates recurrence in revenue audits."),
                 ("medium", "Departments audited often (the Airport, SFMTA, the Port) have more chances to show repeats.")])

    # ------------------------------------------------------------------ au-open
    com("au-open",
        "{m:open_n} recommendations were last recorded as open or in progress; {m:open2} were issued more than two years ago, but for {m:open2_stale} "
        "of those the last follow-up is itself more than two years old, so 'open' often means 'no longer tracked' rather than 'known to be undone'.",
        ["Most old open items are Grand Jury recommendations ({m:open2_cgj} of the {m:open2}) whose tracking stopped; the typical last follow-up among "
         "them was in {m:open2_medfu}. {m:open5} of the open items are more than five years old.",
         "The consequence score ({k:score_min} to {k:score_max}) ranks items by auditor priority, dollars stated in the report, age while recorded open, "
         "whether the department declined, whether the item repeats an earlier recommendation, and whether it concerns public safety, health or ethics. "
         "{m:open_hi} open items score {k:score_hi} or higher. It is a reading aid built from a published rule, not an audit judgment.",
         "On the Controller's side the open list is short and specific. CSA reported that \"{q:csa25_list}\" ({x:c_con3533_p2}); {m:cityopt_open} of "
         "them come from its {x:d_con3045} audit of Public Health's oversight of the City Option health-spending program, which found \"{q:dph_improve}\" "
         "({x:c_con3045_p3}). Public Health's stated reason is that it \"{q:dph_resp}\". The Controller's final update on the Public Integrity reviews "
         "that began in {x:d_pi2020} reports: \"{q:pi_closed}\" ({x:c_con3624_p4}). Closed there means \"{q:pi_def}\", and the update adds that "
         "\"{q:pi_ig}\"."],
        templates=[{"id": "open", "template": "{open_fmt} recommendations issued {years} were open or in progress at their last recorded follow-up; "
                    "{high_fmt} of them score 7 or higher on the consequence rule.", "requires": {"open_min": 1},
                    "fallback": "No open or in-progress recommendations match; widen the years or clear a filter."}],
        caveats=[("high", "'Open' is the last recorded status. For {m:open2_stale} of the {m:open2} items open more than two years, no follow-up has been "
                  "published in more than two years; some were probably finished without a record."),
                 ("medium", "Dollar figures come from the reports, can overlap between recommendations and reports, and should never be added up."),
                 ("medium", "Grand Jury rows are per respondent, so one recommendation addressed to several officials can appear several times.")])

    com("au-reports", "Every report with at least one extracted recommendation, linked to its original PDF.",
        ["Each report page lists its recommendations in report order with the department's response, the latest recorded status, the page reference "
         "and the follow-up document that recorded it. Counts in the directory reflect your filters."])

    # ------------------------------------------------------------------ story
    story_steps = [
        ("au-overview", "Three watchdogs, different leverage", {},
         "The Controller's auditors, the Budget and Legislative Analyst and the Civil Grand Jury made {m:n_rows} recommendations in {m:n_reports} reports. "
         "CSA sees {m:csa_rate} of its followed-up recommendations closed; the Grand Jury sees {m:cgj_rate}. The difference is mostly in what they ask for."),
        ("au-status", "Who says no, and why", {"source": ["cgj"]},
         "Grand Jury 'will not' answers outnumber 'implemented', but {m:cgj_ni_bm} of the {m:cgj_ni} come from the Board and the Mayor's Office, and "
         "most refusals say the matter belongs elsewhere, is already covered, or will be handled another way."),
        ("au-agreement", "Promises mostly kept", {"source": ["cgj"]},
         "{m:wbi_rate} of 'will be implemented' answers were later recorded as implemented; {m:wbi_rev_rate} were changed to 'will not'."),
        ("au-agreement", "The Board of Supervisors", {"dept": ["BOS"]},
         "The Board declined {m:bos_share} of the recommendations it answered, nearly all from the Grand Jury. That is a legislature choosing what to "
         "legislate or fund; each report page carries its reasons."),
        ("au-time", "Why it looks slow", {"source": ["csa"]},
         "Median {m:med_csa} months for CSA, but most dates are whole-report closures. CSA's own count: most recommendations are done within a year."),
        ("au-repeat", "Problems that come back", {"dept": ["POL"]},
         "Police civilianization was recommended in {m:ch_pol_reps} reports from all three bodies over {m:ch_pol_yrs} years; in {x:d_bla24} the BLA "
         "reported the plans had stopped with the pandemic. A repeat is a signal to check, not proof that a fix failed."),
        ("au-open", "Open, or just untracked?", {},
         "{m:open2} items were open more than two years at their last follow-up; for {m:open2_stale} of them the follow-up itself is over two years old."),
    ]
    story = {"sample": False, "title": "Audit recommendations tracker",
             "steps": [{"view": v, "title": t, "text": w("story_au", f"steps[{i}]", s), "filters": f} for i, (v, t, f, s) in enumerate(story_steps)]}

    # ------------------------------------------------------------------ write
    for view, obj in files.items():
        json.dump(obj, open(os.path.join(OUT, f"{view}.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(story, open(os.path.join(OUT, "story_au.json"), "w"), indent=1, ensure_ascii=False)
    facts = {"sample": False, "as_of": as_of.isoformat(), "note": "Every number, quote and dated fact in the audits commentary, with its definition. "
             "Recomputed independently from data/site/ by pipeline/verify_commentary.py.",
             "metrics": {k: {"value": M[k], "fmt": FMT[k], "text": fmt_value(M[k], FMT[k]), "definition": DEF[k]} for k in M},
             "quotes": QUOTES, "facts": FACTS, "constants": CONSTS, "trace": w.trace}
    json.dump(facts, open(os.path.join(OUT, "facts_au.json"), "w"), indent=1, ensure_ascii=False, default=str)
    json.dump(facts, open(os.path.join(RT, "commentary_trace.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print("commentary written:", len(files) + 1, "files;", len(w.trace), "traced tokens;", len(M), "metrics")


if __name__ == "__main__":
    main()
