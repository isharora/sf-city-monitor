"""Step 4: build normalized tables from extractions.

- data/work/reports.json          one record per report (inventory + extracted report facts)
- data/work/recommendations.json  one record per recommendation from original reports
- data/work/status_items.json     one record per status item (rec-level)
- data/work/report_level.json     report-level status rows (CSA closure tables etc.)
- data/work/dept_map.json         raw department string -> canonical department (Claude, cached)
"""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from common import RAW, DATA  # noqa
import llm  # noqa

EXTRACT = os.path.join(DATA, "extract")
WORK = os.path.join(DATA, "work")
os.makedirs(WORK, exist_ok=True)

CANONICAL_HINT = """Airport (San Francisco International Airport); Arts Commission; Asian Art Museum; Assessor-Recorder; Board of Appeals; Board of Supervisors; Building Inspection (Department of Building Inspection); Child Support Services; Children, Youth and Their Families (DCYF); City Administrator (incl. Office of Contract Administration, Real Estate Division, Fleet, Risk Management, Convention Facilities, Medical Examiner when stated as part of it); City Attorney; City Planning (Planning Department); Civil Service Commission; Controller; County Transportation Authority; Disability and Aging Services (formerly Aging and Adult Services); District Attorney; Early Childhood (Department of Early Childhood / First 5 / Office of Early Care and Education); Economic and Workforce Development (OEWD); Elections; Emergency Management; Environment; Ethics Commission; Film Commission; Fine Arts Museums; Fire Department; Health Service System; Homelessness and Supportive Housing; Human Resources; Human Rights Commission; Human Services Agency; Juvenile Probation; Law Library; Library (Public Library); Mayor's Office (incl. Mayor's Budget Office); Mayor's Office of Housing and Community Development; Municipal Transportation Agency (SFMTA, incl. Muni, Parking and Traffic, Taxi Commission); Office of Community Investment and Infrastructure (former Redevelopment Agency); Police Accountability (Department of Police Accountability / Office of Citizen Complaints); Police Department; Police Commission; Port; Public Defender; Public Health (incl. Zuckerberg SF General, Laguna Honda Hospital, Behavioral Health); Public Utilities Commission (SFPUC, incl. Hetch Hetchy, Water, Power, Wastewater, CleanPowerSF); Public Works; Recreation and Park; Rent Board; Retirement System (SFERS); Sheriff; Sheriff's Department of Accountability (Sheriff Inspector General); Status of Women; Superior Court; Technology (Department of Technology); Treasure Island Development Authority; Treasurer and Tax Collector; War Memorial; Youth Commission; Adult Probation; Animal Care and Control; Entertainment Commission; Small Business; Retirement Board; Citywide (all departments / multiple departments generally); School District (SFUSD, not a City department); Community College District; Other non-City entity; Unknown"""

DEPT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["mappings"],
    "properties": {"mappings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["raw", "canonical", "confidence"],
        "properties": {"raw": {"type": "string"}, "canonical": {"type": "string"},
                       "confidence": {"type": "number"}}}}}}

DEPT_SYSTEM = f"""You standardize names of San Francisco City and County departments and bodies.
Map each raw name to ONE canonical short name from this list (use the name before any parenthesis exactly):
{CANONICAL_HINT}
Rules: commissions map to their department (e.g. "Airport Commission" -> Airport, "Health Commission" -> Public Health, "Library Commission" -> Library, "Public Works Commission" -> Public Works), except Police Commission, Ethics Commission, Civil Service Commission, Arts Commission, Entertainment Commission, Youth Commission, Film Commission, Human Rights Commission which are their own. Department heads/officials map to their department (e.g. "Chief of Police" -> Police Department, "Director of Elections" -> Elections, "the Mayor" -> Mayor's Office, "Controller" -> Controller). Divisions map to their parent department. Private contractors, nonprofits, lessees and concessionaires audited on the City's behalf map to "Other non-City entity". If a raw string names several departments, map to the first/primary one. Give a confidence 0-1. Return every raw string exactly as given."""


def canon_depts(raws):
    path = os.path.join(WORK, "dept_map.json")
    m = json.load(open(path)) if os.path.exists(path) else {}
    todo = sorted({r for r in raws if r and r not in m})
    for i in range(0, len(todo), 150):
        chunk = todo[i:i + 150]
        data, meta = llm.call_json("dept_normalize", llm.SONNET, DEPT_SYSTEM,
                                   "Raw names:\n" + "\n".join(chunk), DEPT_SCHEMA,
                                   effort="low", max_tokens=32000)
        got = {x["raw"]: x for x in data["mappings"]}
        for r in chunk:
            x = got.get(r)
            m[r] = {"canonical": x["canonical"], "confidence": x["confidence"]} if x else {"canonical": "Unknown", "confidence": 0.0}
        json.dump(m, open(path, "w"), indent=0)
    return m


_page_cache = {}


def _pages_norm(doc_id):
    if doc_id not in _page_cache:
        pth = os.path.join(DATA, "text", doc_id + ".json")
        if os.path.exists(pth):
            t = json.load(open(pth))
            _page_cache[doc_id] = [re.sub(r"[^a-z0-9]+", " ", p.lower()) for p in t["pages"]] if t["chars"] / max(1, t["n_pages"]) > 200 else None
        else:
            _page_cache[doc_id] = None
    return _page_cache[doc_id]


def verify_page(doc_id, text, page):
    """Check that `text` appears on `page` of the PDF text; else find the nearest page where it
    does. Returns (page, check) with check in verified|corrected|unverified|no_text."""
    from rapidfuzz import fuzz
    pages = _pages_norm(doc_id)
    if not pages or not text:
        return page, "no_text"
    t = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    words = t.split()
    if len(words) < 4:
        return page, "unverified"
    snip = " ".join(words[:14])
    seed = " ".join(words[:5])
    def hit(i):
        pg = pages[i]
        return snip in pg or (seed in pg and fuzz.partial_ratio(snip, pg) >= 88)
    if page and 1 <= page <= len(pages) and hit(page - 1):
        return page, "verified"
    found = [i + 1 for i in range(len(pages)) if seed in pages[i] and hit(i)]
    if not found:
        # seed may break across lines/pages: try fuzzy on neighbours of claimed page
        cand = range(max(0, (page or 1) - 3), min(len(pages), (page or 1) + 2))
        found = [i + 1 for i in cand if fuzz.partial_ratio(snip, pages[i]) >= 90]
    if not found:
        return page, "unverified"
    best = min(found, key=lambda p: abs(p - (page or 0)))
    return best, "corrected"


def nz(v):
    return None if v in ("", None) else v


def load_dir(sub):
    d = os.path.join(EXTRACT, sub)
    out = {}
    if not os.path.isdir(d):
        return out
    for f in os.listdir(d):
        if f.endswith(".json"):
            out[f[:-5]] = json.load(open(os.path.join(d, f)))
    return out


def main():
    inv = {d["doc_id"]: d for d in json.load(open(os.path.join(RAW, "inventory.json")))}
    dl = {r["doc_id"]: r for r in json.load(open(os.path.join(RAW, "downloads.json")))}
    rep_ex = load_dir("reports")
    st_ex = load_dir("status")
    dups = json.load(open(os.path.join(RAW, "duplicates.json"))) if os.path.exists(os.path.join(RAW, "duplicates.json")) else {}
    rep_ex = {k: v for k, v in rep_ex.items() if k not in dups}
    st_ex = {k: v for k, v in st_ex.items() if k not in dups}
    print("skipped duplicate docs:", len(dups))

    reports, recs = [], []
    for doc_id, r in rep_ex.items():
        d = inv.get(doc_id)
        if not d:
            continue
        rep = (r.get("data") or {}).get("report") or {}
        reports.append({
            "doc_id": doc_id, "source": d["source"], "doc_type": d["doc_type"], "title": d["title"],
            "date": d.get("date") or rep.get("report_date"), "url": d["url"], "listing_url": d["listing_url"],
            "cgj_term": d["extra"].get("cgj_term"), "n_pages": dl.get(doc_id, {}).get("n_pages"),
            "scanned": dl.get(doc_id, {}).get("status") == "ok_low_text",
            "skipped": r.get("skipped"), "report_kind": rep.get("report_kind"),
            "has_recommendations": rep.get("has_recommendations", False),
            "departments_raw": rep.get("departments", []), "summary": rep.get("summary"),
            "stated_rec_count": rep.get("stated_recommendation_count"),
            "overall_response": rep.get("overall_response"),
            "dollar_findings": rep.get("dollar_findings", []), "notes": rep.get("notes"),
            "n_recs": len(r["data"]["recommendations"]), "model": r.get("model"),
            "cost_usd": sum((c.get("cost_usd") or 0) for c in r.get("calls", [])),
        })
        for i, x in enumerate(r["data"]["recommendations"]):
            pg, pchk = verify_page(doc_id, x.get("text"), x.get("page"))
            x = dict(x, page=pg)
            recs.append({"page_check": pchk, "page_claimed": r["data"]["recommendations"][i].get("page"),
                "rec_uid": f"{doc_id}#{i:03d}", "doc_id": doc_id, "source": d["source"],
                "doc_type": d["doc_type"], "report_title": d["title"],
                "report_date": d.get("date") or rep.get("report_date"),
                "cgj_term": d["extra"].get("cgj_term"), "url": d["url"],
                **{k: x.get(k) for k in ("rec_id", "text", "finding", "departments", "category",
                                         "secondary_category", "priority", "response", "response_raw",
                                         "target_date", "target_date_iso", "page", "response_page",
                                         "conf_text", "conf_department", "conf_category",
                                         "conf_response", "conf_target_date")},
            })

    items, rl = [], []
    for doc_id, r in st_ex.items():
        d = inv.get(doc_id)
        if not d:
            continue
        doc = r["data"]["doc"]
        for i, x in enumerate(r["data"]["items"]):
            # responses to Grand Jury FINDINGS (F1, F.C.2, "Finding 3") are not recommendation statuses
            if re.match(r"(?i)^\s*(f[\s.\-:_]*[\dIVX]|finding)", x.get("rec_id") or ""):
                continue
            pg, pchk = verify_page(doc_id, x.get("rec_text") or x.get("explanation"), x.get("page"))
            x = dict(x, page=pg)
            items.append({"page_check": pchk,"status_uid": f"{doc_id}#{i:04d}", "status_doc_id": doc_id,
                          "status_doc_type": d["doc_type"], "status_doc_title": d["title"],
                          "status_doc_date": d.get("date"), "status_doc_url": d["url"],
                          "as_of_date": doc.get("as_of_date"), "cgj_term": d["extra"].get("cgj_term"),
                          "parent_report_url": d["extra"].get("parent_report_url"),
                          **{k: nz(v) for k, v in x.items()}})
        for i, x in enumerate(r["data"].get("report_level", [])):
            rl.append({"rl_uid": f"{doc_id}#RL{i:03d}", "status_doc_id": doc_id,
                       "status_doc_type": d["doc_type"], "status_doc_date": d.get("date"),
                       "as_of_date": doc.get("as_of_date"), **x})

    raws = set()
    for x in recs:
        raws.update(x["departments"] or [])
    for x in reports:
        raws.update(x["departments_raw"] or [])
    for x in items:
        raws.update([x.get("department"), x.get("respondent")])
    for x in rl:
        raws.add(x.get("department"))
    dm = canon_depts({r for r in raws if r})

    ov = json.load(open(os.path.join(os.path.dirname(__file__), "dept_overrides.json")))

    def canon(v):
        if not v:
            return None
        if v in ov:
            return ov[v]
        c = dm.get(v, {}).get("canonical")
        return re.sub(r"\s*\(.*$", "", c).strip() if c else None

    for x in recs:
        c = [canon(v) for v in (x["departments"] or [])]
        x["departments_canon"] = list(dict.fromkeys([v for v in c if v]))
        x["dept_primary"] = x["departments_canon"][0] if x["departments_canon"] else "Unknown"
    for x in reports:
        x["departments_canon"] = list(dict.fromkeys([canon(v) for v in x["departments_raw"] if canon(v)]))
    for x in items:
        x["dept_canon"] = canon(x.get("department")) or canon(x.get("respondent"))
    for x in rl:
        x["dept_canon"] = canon(x.get("department"))

    for name, obj in (("reports", reports), ("recommendations", recs),
                      ("status_items", items), ("report_level", rl)):
        json.dump(obj, open(os.path.join(WORK, name + ".json"), "w"), indent=0)
        print(name, len(obj))
    print(Counter(x["source"] for x in recs))


if __name__ == "__main__":
    main()
