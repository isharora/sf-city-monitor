"""Verify every number, quote and dated fact in the audits commentary.

Independent of 12_commentary.py: metrics are recomputed here from the PUBLISHED export
(data/site/recs/recs_*.json, reports/reports.json, repeats/clusters.json, meta.json) with separate
code and a separately declared format, then compared token by token with the text. Quotes are
checked word for word against the per-page PDF text (data/text/<doc>.json); dated facts against
the page text or the document date in the inventory.

A token passes only if (1) it is registered in the trace for that exact field, in order, (2) its
metric id exists in THIS file's registry, and (3) the value recomputed here, formatted with THIS
file's format, equals the text. Any digit left in a text field after masking traced tokens and
template slots is an untraced number. Straight double-quoted passages must be registered quotes.

Usage: python3 pipeline/verify_commentary.py   (exit 1 on any failure)
Writes data/redteam/verify_commentary.json
"""
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(DATA, "site")
COM = os.path.join(SITE, "commentary")
DESIGN = os.path.join(os.path.dirname(ROOT), "design", "DESIGN.md")

# ------------------------------------------------------------------ data (published export only)
ROWS = []
for f in sorted(glob.glob(os.path.join(SITE, "recs", "recs_*.json"))):
    ROWS += json.load(open(f))["rows"]
META = json.load(open(os.path.join(SITE, "meta.json")))
REPORTS = json.load(open(os.path.join(SITE, "reports", "reports.json")))["reports"]
CLUSTERS = json.load(open(os.path.join(SITE, "repeats", "clusters.json")))
REASONS = json.load(open(os.path.join(DATA, "redteam", "reasons.json")))["items"]
INV = {d["doc_id"]: d for d in json.load(open(os.path.join(DATA, "raw", "inventory.json")))}
REPDATE = {r["id"]: r["date"] for r in REPORTS}
AS_OF = date.fromisoformat(META["as_of"])
BY_ID = {r["id"]: r for r in ROWS}


def frac(a, b):
    return a / b


def S(src):
    return [r for r in ROWS if r["source"] == src]


def has_status(r):
    return r["status"] != "unknown"


def is_impl(r):
    return r["status"] == "implemented"


def cnt(it):
    return sum(1 for _ in it)


def yrs_old(r):
    return (AS_OF - date.fromisoformat(r["date_issued"])).days / 365.25


def first_impl_basis(r):
    ev = sorted((h for h in r.get("history") or [] if h.get("status") == "implemented" and h.get("date")), key=lambda h: h["date"])
    return ev[0]["basis"] if ev else None


def reason_rows(pred):
    """Join model reasons to published rows (dept/source from the row, not the reasons file)."""
    out = []
    for x in REASONS:
        r = BY_ID.get(x["id"])
        if r and r["agreed"] == "disagree" and pred(r):
            out.append((r, x["primary"]))
    return out


def rshare(pred, cats):
    rr = reason_rows(pred)
    return frac(cnt(1 for _, p in rr if p in cats), len(rr))


def chain(dept, pat):
    cands = [c for c in CLUSTERS["clusters"] if c["dept"] == dept and c.get("used_for_repeat_of") and re.search(pat, c["theme"], re.I)]
    best = None
    for c in cands:
        m = [BY_ID[i] for i in c["members"] if i in BY_ID]
        k = (len({r["report"] for r in m}), m)
        if best is None or k[0] > best[0]:
            best = k
    n, m = best
    ys = [int(r["date_issued"][:4]) for r in m]
    return n, max(ys) - min(ys)


def agreed_rate(rows, a):
    x = [r for r in rows if r["agreed"] == a and has_status(r)]
    return frac(cnt(r for r in x if is_impl(r)), len(x))


def wbi_rows():
    return [r for r in S("cgj") if r.get("cgj_response") == "will_be_implemented"
            and any(h.get("basis") == "cgj_status_tracker" and h.get("date") for h in r.get("history") or [])]


def open_rows():
    return [r for r in ROWS if r["status"] in ("open", "in_progress")]


def open2():
    return [r for r in open_rows() if yrs_old(r) > 2]


def fin(src):
    return [r for r in S(src) if r["topic"] == "finance" and has_status(r)]


RL = ("csa_report_closed", "inferred_absent_from_open_over_2yrs_list")
VER = ("csa_field_followup", "pi_status_update")
BM = ("BOS", "MYR")
NI = lambda r: r["status"] == "not_implementing"

# metric id -> (function, format). Formats declared here independently of the generator.
REG = {
    "n_rows": (lambda: len(ROWS), "int"),
    "n_distinct": (lambda: META["counts"]["recommendations_distinct"], "int"),
    "n_reports": (lambda: len(REPORTS), "int"),
    "year_max": (lambda: max(int(r["date_issued"][:4]) for r in ROWS), "year"),
    "bla_rows": (lambda: len(S("bla")), "int"),
    "unknown_share": (lambda: frac(cnt(r for r in ROWS if not has_status(r)), len(ROWS)), "pct"),
    "impl_all_share": (lambda: frac(cnt(r for r in ROWS if is_impl(r)), len(ROWS)), "pct"),
    "csa_known": (lambda: cnt(r for r in S("csa") if has_status(r)), "int"),
    "csa_impl": (lambda: cnt(r for r in S("csa") if is_impl(r)), "int"),
    "csa_rate": (lambda: frac(cnt(r for r in S("csa") if is_impl(r)), cnt(r for r in S("csa") if has_status(r))), "pct"),
    "csa_agree_share": (lambda: frac(cnt(r for r in S("csa") if r["agreed"] == "agree"), cnt(r for r in S("csa") if r["agreed"] in ("agree", "partial", "disagree"))), "pct"),
    "csa_dis_share": (lambda: frac(cnt(r for r in S("csa") if r["agreed"] == "disagree"), cnt(r for r in S("csa") if r["agreed"] in ("agree", "partial", "disagree"))), "pct"),
    "csa_rl_share": (lambda: frac(cnt(r for r in S("csa") if is_impl(r) and r["status_basis"] in RL), cnt(r for r in S("csa") if is_impl(r))), "pct"),
    "csa_n_rl": (lambda: cnt(r for r in S("csa") if has_status(r) and r["status_basis"] not in RL), "int"),
    "csa_rate_rl": (lambda: frac(cnt(r for r in S("csa") if is_impl(r) and r["status_basis"] not in RL), cnt(r for r in S("csa") if has_status(r) and r["status_basis"] not in RL)), "pct"),
    "csa_n_ver": (lambda: cnt(r for r in S("csa") if has_status(r) and r["status_basis"] in VER), "int"),
    "csa_rate_ver": (lambda: frac(cnt(r for r in S("csa") if is_impl(r) and r["status_basis"] in VER), cnt(r for r in S("csa") if has_status(r) and r["status_basis"] in VER)), "pct"),
    "ver_share_all": (lambda: frac(cnt(r for r in ROWS if is_impl(r) and r["status_basis"] in VER), cnt(r for r in ROWS if is_impl(r))), "pct"),
    "csa_ni_n": (lambda: cnt(r for r in S("csa") if NI(r)), "int"),
    "csa_open_n": (lambda: cnt(r for r in S("csa") if r["status"] in ("open", "in_progress")), "int"),
    "cgj_bosmyr_share": (lambda: frac(cnt(r for r in S("cgj") if r["dept"] in BM), len(S("cgj"))), "pct"),
    "csa_bosmyr_share": (lambda: frac(cnt(r for r in S("csa") if r["dept"] in BM), len(S("csa"))), "pct"),
    "csa_fin_n": (lambda: len(fin("csa")), "int"),
    "csa_fin_rate": (lambda: frac(cnt(r for r in fin("csa") if is_impl(r)), len(fin("csa"))), "pct"),
    "cgj_fin_n": (lambda: len(fin("cgj")), "int"),
    "cgj_fin_rate": (lambda: frac(cnt(r for r in fin("cgj") if is_impl(r)), len(fin("cgj"))), "pct"),
    "cgj_known": (lambda: cnt(r for r in S("cgj") if has_status(r)), "int"),
    "cgj_impl": (lambda: cnt(r for r in S("cgj") if is_impl(r)), "int"),
    "cgj_rate": (lambda: frac(cnt(r for r in S("cgj") if is_impl(r)), cnt(r for r in S("cgj") if has_status(r))), "pct"),
    "cgj_ni": (lambda: cnt(r for r in S("cgj") if NI(r)), "int"),
    "cgj_ni_bm": (lambda: cnt(r for r in S("cgj") if NI(r) and r["dept"] in BM), "int"),
    "cgj_ni_bm_share": (lambda: frac(cnt(r for r in S("cgj") if NI(r) and r["dept"] in BM), cnt(r for r in S("cgj") if NI(r))), "pct"),
    "ni_bos": (lambda: cnt(r for r in S("cgj") if NI(r) and r["dept"] == "BOS"), "int"),
    "ni_myr": (lambda: cnt(r for r in S("cgj") if NI(r) and r["dept"] == "MYR"), "int"),
    "cgj_ni_ex": (lambda: cnt(r for r in S("cgj") if NI(r) and r["dept"] not in BM), "int"),
    "cgj_impl_ex": (lambda: cnt(r for r in S("cgj") if is_impl(r) and r["dept"] not in BM), "int"),
    "cgj_rec_any_rate": (None, "pct"),  # set below
    "cgj_wn_n": (lambda: len(reason_rows(lambda r: r["source"] == "cgj")), "int"),
    "r_auth": (lambda: rshare(lambda r: r["source"] == "cgj", {"not_our_authority"}), "pct"),
    "r_exist": (lambda: rshare(lambda r: r["source"] == "cgj", {"already_done_or_existing_process"}), "pct"),
    "r_alt": (lambda: rshare(lambda r: r["source"] == "cgj", {"alternative_approach"}), "pct"),
    "r_legal": (lambda: rshare(lambda r: r["source"] == "cgj", {"legal_or_contract_constraint"}), "pct"),
    "r_cost": (lambda: rshare(lambda r: r["source"] == "cgj", {"cost_or_resources"}), "pct"),
    "r_merit": (lambda: rshare(lambda r: r["source"] == "cgj", {"policy_disagreement"}), "pct"),
    "r_none": (lambda: rshare(lambda r: r["source"] == "cgj", {"no_reason_given"}), "pct"),
    "bos_auth": (lambda: rshare(lambda r: r["dept"] == "BOS", {"not_our_authority"}), "pct"),
    "bos_exist": (lambda: rshare(lambda r: r["dept"] == "BOS", {"already_done_or_existing_process"}), "pct"),
    "bos_alt": (lambda: rshare(lambda r: r["dept"] == "BOS", {"alternative_approach"}), "pct"),
    "bos_merit": (lambda: rshare(lambda r: r["dept"] == "BOS", {"policy_disagreement"}), "pct"),
    "r_bm_other": (lambda: rshare(lambda r: r["dept"] in BM, {"not_our_authority", "already_done_or_existing_process", "alternative_approach"}), "pct"),
    "pool_agree": (lambda: agreed_rate(ROWS, "agree"), "pct"),
    "pool_dis": (lambda: agreed_rate(ROWS, "disagree"), "pct"),
    "dis_cgj_share": (lambda: frac(cnt(r for r in ROWS if r["agreed"] == "disagree" and has_status(r) and r["source"] == "cgj"),
                                   cnt(r for r in ROWS if r["agreed"] == "disagree" and has_status(r))), "pct"),
    "cgj_hbi": (lambda: cnt(r for r in S("cgj") if r.get("cgj_response") == "has_been_implemented"), "int"),
    "csa_dis_n": (lambda: cnt(r for r in S("csa") if r["agreed"] == "disagree" and has_status(r)), "int"),
    "csa_dis_impl": (lambda: cnt(r for r in S("csa") if r["agreed"] == "disagree" and is_impl(r)), "int"),
    "wbi_n": (lambda: len(wbi_rows()), "int"),
    "wbi_impl": (lambda: cnt(r for r in wbi_rows() if is_impl(r)), "int"),
    "wbi_rate": (lambda: frac(cnt(r for r in wbi_rows() if is_impl(r)), len(wbi_rows())), "pct"),
    "wbi_prog": (lambda: cnt(r for r in wbi_rows() if r["status"] == "in_progress"), "int"),
    "wbi_rev": (lambda: cnt(r for r in wbi_rows() if NI(r)), "int"),
    "wbi_rev_rate": (lambda: frac(cnt(r for r in wbi_rows() if NI(r)), len(wbi_rows())), "pct"),
    "bos_rev": (lambda: cnt(r for r in wbi_rows() if NI(r) and r["dept"] == "BOS"), "int"),
    "bos_n": (lambda: cnt(r for r in ROWS if r["dept"] == "BOS" and r["agreed"] != "none"), "int"),
    "bos_dis": (lambda: cnt(r for r in ROWS if r["dept"] == "BOS" and r["agreed"] == "disagree"), "int"),
    "bos_share": (lambda: frac(cnt(r for r in ROWS if r["dept"] == "BOS" and r["agreed"] == "disagree"), cnt(r for r in ROWS if r["dept"] == "BOS" and r["agreed"] != "none")), "pct"),
    "bos_cgj": (lambda: cnt(r for r in ROWS if r["dept"] == "BOS" and r["agreed"] != "none" and r["source"] == "cgj"), "int"),
    "n_timed": (lambda: cnt(r for r in ROWS if r.get("months_to_close") is not None), "int"),
    "med_all": (lambda: _median([r["months_to_close"] for r in ROWS if r.get("months_to_close") is not None]), "mo"),
    "csa_timed": (lambda: cnt(r for r in S("csa") if r.get("months_to_close") is not None), "int"),
    "csa_timed_rc": (lambda: cnt(r for r in S("csa") if r.get("months_to_close") is not None and first_impl_basis(r) == "csa_report_closed"), "int"),
    "med_csa": (lambda: _median([r["months_to_close"] for r in S("csa") if r.get("months_to_close") is not None]), "mo"),
    "n_inferred": (lambda: cnt(r for r in ROWS if r["status_basis"] == "inferred_absent_from_open_over_2yrs_list"), "int"),
    "rep_n": (lambda: cnt(r for r in ROWS if r.get("repeat_of")), "int"),
    "rep_share": (lambda: frac(cnt(r for r in ROWS if r.get("repeat_of")), len(ROWS)), "pct1"),
    "rep_clusters": (lambda: len({r["repeat_cluster"] for r in ROWS if r.get("repeat_of")}), "int"),
    "rep_pred_impl": (lambda: cnt(r for r in ROWS if r.get("repeat_of") and is_impl(BY_ID[r["repeat_of"]])), "int"),
    "rep_cross": (lambda: cnt(r for r in ROWS if r.get("repeat_of") and BY_ID[r["repeat_of"]]["source"] != r["source"]), "int"),
    "val_judge": (lambda: CLUSTERS["validation"]["judge_confirms_pos"], "pct"),
    "val_pairs": (lambda: CLUSTERS["validation"]["pairs_judged_pos"], "int"),
    "ch_air_reps": (lambda: chain("AIR", r"certified financial report")[0], "int"),
    "ch_air_yrs": (lambda: chain("AIR", r"certified financial report")[1], "int"),
    "ch_mta_reps": (lambda: chain("MTA", r"monthly parker access cards")[0], "int"),
    "ch_mta_yrs": (lambda: chain("MTA", r"monthly parker access cards")[1], "int"),
    "ch_pol_reps": (lambda: chain("POL", r"civiliani")[0], "int"),
    "ch_pol_yrs": (lambda: chain("POL", r"civiliani")[1], "int"),
    "ch_dpw_reps": (lambda: chain("DPW", r"performance evaluation used in contractor selection")[0], "int"),
    "ch_dpw_yrs": (lambda: chain("DPW", r"performance evaluation used in contractor selection")[1], "int"),
    "open_n": (lambda: len(open_rows()), "int"),
    "open2": (lambda: len(open2()), "int"),
    "open5": (lambda: cnt(r for r in open_rows() if yrs_old(r) > 5), "int"),
    "open2_stale": (lambda: cnt(r for r in open2() if r.get("last_followup") and (AS_OF - date.fromisoformat(r["last_followup"])).days > 730), "int"),
    "open2_cgj": (lambda: cnt(r for r in open2() if r["source"] == "cgj"), "int"),
    "open2_medfu": (lambda: sorted(int(r["last_followup"][:4]) for r in open2() if r.get("last_followup"))[len([r for r in open2() if r.get("last_followup")]) // 2], "year"),
    "open_hi": (lambda: cnt(r for r in open_rows() if r["consequence"]["score"] >= 7), "int"),
    "cityopt_open": (lambda: cnt(r for r in S("csa") if r["report"] == "CON-3045" and r["status"] in ("open", "in_progress")), "int"),
    "cgj07": (lambda: cnt(r for r in S("cgj") if r["date_issued"].startswith("2007")), "int"),
    "cgj07_top": (lambda: Counter(r["report"] for r in S("cgj") if r["date_issued"].startswith("2007")).most_common(1)[0][1], "int"),
    "pol08": (lambda: cnt(r for r in S("csa") if r["date_issued"].startswith("2008") and r["report"] in
                          {p["id"] for p in REPORTS if re.search(r"organizational assessment of the san francisco police", p["title"], re.I)}), "int"),
    "csa09_impl_all": (lambda: frac(cnt(r for r in S("csa") if r["date_issued"].startswith("2009") and is_impl(r)), cnt(r for r in S("csa") if r["date_issued"].startswith("2009"))), "pct"),
    "csa10_impl_all": (lambda: frac(cnt(r for r in S("csa") if r["date_issued"].startswith("2010") and is_impl(r)), cnt(r for r in S("csa") if r["date_issued"].startswith("2010"))), "pct"),
}


def _median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def _cgj_rec_any():
    g = {}
    for r in S("cgj"):
        if has_status(r):
            g.setdefault((r["report"], r.get("rec_number"), r["text"]), []).append(r["status"])
    return frac(cnt(v for v in g.values() if "implemented" in v), len(g))


REG["cgj_rec_any_rate"] = (_cgj_rec_any, "pct")


def fmt(v, f):
    if f == "int":
        return "{:,}".format(int(v))
    if f == "pct":
        return "{}%".format(int(round(v * 100)))
    if f == "pct1":
        return "{:.1f}%".format(v * 100)
    if f in ("mo",):
        return str(int(round(v)))
    if f == "year":
        return str(int(v))
    raise ValueError(f)


# ------------------------------------------------------------------ PDF text checks
def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-").replace("­", "")
    return re.sub(r"\s+", " ", s).strip()


_TXT = {}


def page_text(doc, pages):
    if doc not in _TXT:
        _TXT[doc] = json.load(open(os.path.join(DATA, "text", doc + ".json")))["pages"]
    t = _TXT[doc]
    return " ".join(norm(t[p - 1]) for p in pages if 1 <= p <= len(t))


def pages_of(e):
    return e.get("pages") or [e["page"]]


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def doc_date(doc):
    d = REPDATE.get(doc) or (INV.get(doc) or {}).get("date")
    return date.fromisoformat(d) if d else None


def check_fact(e):
    if "date" in e:
        d = doc_date(e["doc"])
        if not d:
            return False, "no document date"
        want = str(d.year) if e["date"] == "year" else f"{MONTHS[d.month - 1]} {d.year}"
        return want == e["text"], f"document date {d.isoformat()} -> {want}"
    t = page_text(e["doc"], pages_of(e))
    ok = re.search(e["needle"], t) is not None or re.search(e["needle"], re.sub(r"(\w)- (\w)", r"\1-\2", t)) is not None
    return ok, f"needle /{e['needle']}/ on {e['doc']} p.{pages_of(e)}"


def check_quote(e):
    txt = page_text(e["doc"], pages_of(e))
    q = norm(e["text"])
    if q in txt:
        return True, "verbatim"
    # allow a PDF line-break hyphen split ("capi- tal") only
    if q in re.sub(r"(\w)- (\w)", r"\1\2", txt) or q in re.sub(r"(\w)- (\w)", r"\1-\2", txt):
        return True, "verbatim after rejoining a line-break hyphen"
    return False, f"not found on {e['doc']} p.{pages_of(e)}"


def check_const(cid, val):
    if cid == "pc_933_05":
        return val == "933.05", "California Penal Code section 933.05 (response categories)"
    if cid in ("score_min", "score_max"):
        return re.search(r"clamped to 1-10", META["consequence_rule"]) is not None and val in ("1", "10"), "meta.consequence_rule 'clamped to 1-10'"
    if cid == "score_hi":
        return val == "7" and os.path.exists(DESIGN) and "7+" in open(DESIGN).read(), "DESIGN.md au-open '7+' highlight"
    if cid == "ch6":
        return val == "6" and "Chapter 6" in page_text("CGJS-2014-15", [1]), "Administrative Code Chapter 6 (CGJS-2014-15 p.1)"
    return False, "unknown constant"


# ------------------------------------------------------------------ main
SLOTS = {"common": {"__small", "years", "recs", "recs_fmt", "reports_fmt", "impl", "impl_fmt", "impl_share", "open", "open_fmt", "median_months"},
         "au-status": {"prog_share", "open_share", "notimpl_share"}, "au-time": {"p75_months", "p90_months"},
         "au-agreement": {"agree_share", "partial_share", "disagree_share", "impl_agreed", "impl_disagreed"},
         "au-repeat": {"repeats_fmt", "repeat_share", "top_topic", "top_topic_fmt"}, "au-open": {"high_fmt", "dollars"}}


def fields(obj, view):
    if view == "story_au":
        for i, s in enumerate(obj["steps"]):
            yield f"steps[{i}]", s["text"], False
        return
    yield "headline", obj.get("headline") or "", False
    for i, p in enumerate(obj.get("paragraphs") or []):
        yield f"paragraphs[{i}]", p, False
    for i, a in enumerate(obj.get("annotations") or []):
        yield f"annotations[{i}]", a["text"], False
    for i, t in enumerate(obj.get("templates") or []):
        yield f"templates[{i}]", t["template"], True
        yield f"templates[{i}].fallback", t.get("fallback") or "", True
    for i, c in enumerate(obj.get("caveats") or []):
        yield f"caveats[{i}]", c["text"], False


def main():
    facts = json.load(open(os.path.join(COM, "facts_au.json")))
    trace = facts["trace"]
    tr = {}
    for e in trace:
        tr.setdefault((e["view"], e["field"]), []).append(e)
    res = {"checked_tokens": 0, "ok": 0, "failures": [], "untraced": [], "unregistered_quotes": [], "by_kind": Counter(), "notes": []}
    views = sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(COM, "au-*.json"))) + ["story_au"]
    for view in views:
        obj = json.load(open(os.path.join(COM, view + ".json")))
        for a in obj.get("annotations") or []:
            if len(a["text"]) > 90:
                res["failures"].append({"view": view, "field": "annotation", "problem": "over 90 characters", "text": a["text"]})
        for field, text, is_tpl in fields(obj, view):
            masked, pos = text, 0
            for e in tr.get((view, field), []):
                i = masked.find(e["text"], pos)
                res["checked_tokens"] += 1
                res["by_kind"][e["kind"]] += 1
                if i < 0:
                    res["failures"].append({"view": view, "field": field, "id": e["id"], "problem": "traced text not found in field", "text": e["text"]})
                    continue
                masked = masked[:i] + "█" * len(e["text"]) + masked[i + len(e["text"]):]
                pos = i + len(e["text"])
                if e["kind"] == "m":
                    if e["id"] not in REG:
                        ok, why = False, "metric not in verifier registry"
                    else:
                        fn, f = REG[e["id"]]
                        v = fn()
                        ok, why = fmt(v, f) == e["text"], f"recomputed {v!r} -> {fmt(v, f)}"
                elif e["kind"] == "q":
                    ok, why = check_quote(facts["quotes"][e["id"]])
                elif e["kind"] == "x":
                    ok, why = check_fact(facts["facts"][e["id"]])
                else:
                    ok, why = check_const(e["id"], e["text"])
                if ok:
                    res["ok"] += 1
                else:
                    res["failures"].append({"view": view, "field": field, "id": e["id"], "kind": e["kind"], "text": e["text"], "problem": why})
            if is_tpl:
                for s in re.findall(r"\{(\w+)\}", masked):
                    if s not in SLOTS["common"] | SLOTS.get(view, set()):
                        res["failures"].append({"view": view, "field": field, "problem": f"template slot '{s}' is not set by the view"})
                masked = re.sub(r"\{\w+\}", "", masked)
                # the template's literal '7' (score threshold) is a constant of the published rule
                if view == "au-open":
                    masked = masked.replace("score 7 or higher", "score █ or higher")
            for m in re.finditer(r"[$]?\d[\d,.]*%?", masked):
                res["untraced"].append({"view": view, "field": field, "token": m.group(0), "context": masked[max(0, m.start() - 40): m.end() + 40]})
            for m in re.finditer(r'"([^"]+)"', masked):
                if set(m.group(1)) - {"█", " "}:
                    res["unregistered_quotes"].append({"view": view, "field": field, "quote": m.group(1)})
    res["by_kind"] = dict(res["by_kind"])
    res["summary"] = {"tokens": res["checked_tokens"], "verified": res["ok"], "failures": len(res["failures"]),
                      "untraced_numbers": len(res["untraced"]), "unregistered_quotes": len(res["unregistered_quotes"])}
    os.makedirs(os.path.join(DATA, "redteam"), exist_ok=True)
    json.dump(res, open(os.path.join(DATA, "redteam", "verify_commentary.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res["summary"]))
    for f in res["failures"][:40]:
        print("FAIL", f)
    for u in res["untraced"][:40]:
        print("UNTRACED", u)
    for u in res["unregistered_quotes"][:20]:
        print("QUOTE?", u)
    sys.exit(1 if res["failures"] or res["untraced"] or res["unregistered_quotes"] else 0)


if __name__ == "__main__":
    main()
