"""Step 1: build the report inventory from all sources.

Outputs data/raw/inventory.json : list of documents with
  doc_id, source, doc_type, title, date, url, listing_url, extra
Sources:
  controller  - OpenBook webreports (AU, CP, Whistleblower categories)
  cgj         - Civil Grand Jury reports + department responses (archive + sf.gov)
  cgj_status  - Controller's CGJ recommendation status tracking documents
  bla         - Budget & Legislative Analyst reports (archive + sf.gov)
"""
import base64
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urljoin, unquote

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from common import get, RAW, session, polite_wait  # noqa

OB = "https://openbook.sfgov.org/webreports/search.aspx"


def ob_list(cat):
    html = get(OB, cache=False)
    s = BeautifulSoup(html, "html.parser")
    data = {i["name"]: i.get("value", "") for i in s.find_all("input") if i.get("name")}
    data.update({
        "ctl00$ContentPlaceHolder1$TextBox1": "",
        "ctl00$ContentPlaceHolder1$DropDownList2": cat,
        "ctl00$ContentPlaceHolder1$DropDownList1": "1986",
        "ctl00$ContentPlaceHolder1$DropDownList3": str(datetime.now().year),
    })
    polite_wait(OB)
    t = session().post(OB, data=data, timeout=240).text
    sp = BeautifulSoup(t, "html.parser")
    out = []
    for tr in sp.find_all("tr"):
        if tr.find("tr"):
            continue
        a = tr.find("a", href=True)
        txt = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if a and txt and re.match(r"\d+/\d+/\d{4}$", txt[0]):
            out.append({"date": datetime.strptime(txt[0], "%m/%d/%Y").strftime("%Y-%m-%d"),
                        "title": re.sub(r"\s+", " ", a.get_text(" ", strip=True)),
                        "href": urljoin(OB, a["href"])})
    return out


def clean_ob_url(u):
    """ViewState strings end with ASP.NET markers ('dd', etc.) - trim them."""
    if not u:
        return u
    m = re.match(r"(.*?ShowDocument\.aspx\?documentid=\d+)", u, re.I)
    if m:
        return m.group(1)
    m = re.match(r"(.*?\.(?:pdf|docx?|xlsx?))", u, re.I)
    return m.group(1) if m else u


def ob_pdf_url(details_url):
    html = get(details_url)
    m = re.search(r'id="__VIEWSTATE" value="([^"]+)"', html)
    if not m:
        return None
    try:
        raw = base64.b64decode(m.group(1) + "==")
    except Exception:
        return None
    # ViewState strings are length-prefixed (7-bit varint); use the prefix to
    # read the exact string, which may contain spaces.
    urls = []
    for m2 in re.finditer(rb"https?://", raw):
        st = m2.start()
        ln = raw[st - 1] if st >= 1 else 0
        if st >= 2 and raw[st - 1] < 0x80 and raw[st - 2] >= 0x80:
            ln = (raw[st - 2] & 0x7F) | (raw[st - 1] << 7)
        cand = raw[st:st + ln] if ln > 10 else re.match(rb"https?://[\x20-\x7e]+", raw[st:]).group(0)
        urls.append(cand)
    for u in urls:
        u = u.decode("utf-8", errors="replace").strip().replace(" ", "%20")
        # viewstate strings are length-prefixed; cut trailing garbage after known ext
        mm = re.match(r"(https?://.+?\.(?:pdf|PDF|docx?|xlsx?|htm|html|aspx\?[^\s]*))", u)
        if mm:
            return mm.group(1)
    return urls[0].decode("latin-1") if urls else None


# Controller items listed only under "All" (no category) that are CSA assessments/reviews
# (curated after reviewing the 1,420 uncategorized titles; most are economic reports,
# budget documents, policies and tax letters, which are out of scope).
EXTRA_OB_IDS = {3133, 3028, 2519, 1875, 1363, 1273, 1121, 947, 749, 608, 450}


def controller():
    docs = []
    seen = {}
    for cat in ["AU", "CP", "Whistleblower", "All"]:
        rows = ob_list(cat)
        if cat == "All":
            rows = [r for r in rows if int(re.search(r"id=(\d+)", r["href"]).group(1)) in EXTRA_OB_IDS]
        print("openbook", cat, len(rows), flush=True)
        for r in rows:
            rid = re.search(r"id=(\d+)", r["href"]).group(1)
            if rid in seen:
                seen[rid]["extra"]["categories"].append(cat)
                continue
            d = {"doc_id": f"CON-{rid}", "source": "controller", "doc_type": None,
                 "title": r["title"], "date": r["date"], "url": None,
                 "listing_url": r["href"], "extra": {"categories": [cat], "openbook_id": int(rid)}}
            seen[rid] = d
            docs.append(d)
    for i, d in enumerate(docs):
        try:
            d["url"] = clean_ob_url(ob_pdf_url(d["listing_url"]))
        except Exception as e:
            d["extra"]["error"] = repr(e)
        if i % 100 == 0:
            print("  details", i, len(docs), flush=True)
    return docs


def cgj_status():
    url = "https://www.sf.gov/information--status-civil-grand-jury-recommendations/"
    s = BeautifulSoup(get(url), "html.parser")
    docs = []
    for a in (s.find("main") or s).find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        h = urljoin(url, a["href"])
        m = re.match(r"(?:20)?(\d{2})-(\d{2}) (Status of the )?Civil Grand Jury Recommendations", t)
        if m and h.lower().endswith(".pdf"):
            term = f"20{m.group(1)}-{m.group(2)}"
            yr = re.search(r"(20\d\d)\.pdf", unquote(h))
            docs.append({"doc_id": f"CGJS-{term}", "source": "cgj_status",
                         "doc_type": "cgj_status_tracker", "title": t + " (Controller tracking document)",
                         "date": None, "url": h, "listing_url": url,
                         "extra": {"cgj_term": term, "status_as_of_year": yr.group(1) if yr else None}})
        elif "Cover" in t and h.lower().endswith(".pdf"):
            docs.append({"doc_id": "CGJS-cover-2025", "source": "cgj_status", "doc_type": "cgj_status_cover",
                         "title": t, "date": "2025-12-23", "url": h, "listing_url": url, "extra": {}})
    return docs


def uid(url):
    import hashlib
    return hashlib.sha1(url.encode()).hexdigest()[:8]


def classify_cgj_link(text, href):
    t = (text + " " + unquote(href)).lower()
    if re.search(r"press[ _-]?release|press_rel|\bpress\b", t):
        return "press_release"
    if "respon" in t:
        return "cgj_response"
    # judge appendices by link text only (a report file may be named "..._with_Appendices.pdf")
    if re.search(r"^(grand jury )?appendi|^exhibit|errat", text.lower().strip()):
        return "cgj_appendix"
    if re.search(r"controller's audit|civil_grand_jury_rec", t):
        return "cgj_status_legacy"
    return "cgj_report"


def cgj():
    base = "https://civilgrandjury.archive.sf.gov/"
    docs = []
    terms = [f"{y}_{y+1}" for y in range(1995, 2022)]
    for term in terms:
        url = base + term + ".html"
        try:
            html = get(url)
        except Exception as e:
            print("cgj fail", term, e)
            continue
        s = BeautifulSoup(html, "html.parser")
        current_report = None
        for a in s.find_all("a", href=True):
            h = a["href"]
            if h.endswith(".html") or "sfgov.org/index" in h or h.startswith("#") or "cse.google" in h \
                    or "index.asp" in h or h.rstrip("/") in ("http://www.sfgov.org", "https://civilgrandjury.sfgov.org"):
                continue
            if not re.search(r"\.(pdf|doc|docx|htm)$", h, re.I):
                continue
            text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            kind = classify_cgj_link(text, h)
            full = urljoin(url, h)
            if kind == "cgj_report":
                current_report = full
            docs.append({"doc_id": None, "source": "cgj", "doc_type": kind, "title": text,
                         "date": None, "url": full, "listing_url": url,
                         "extra": {"cgj_term": term.replace("_", "-"), "parent_report_url": current_report if kind != "cgj_report" else None}})
    # sf.gov pages for recent terms
    home = BeautifulSoup(get("https://www.sf.gov/departments--civil-grand-jury"), "html.parser")
    pages = sorted({urljoin("https://www.sf.gov/", a["href"]) for a in home.find_all("a", href=True)
                    if "civil-grand-jury-reports-20" in a["href"]})
    # older terms also have sf.gov pages (found via api.sf.gov/api/v2/pages/?search=)
    pages = sorted(set(pages) | {"https://www.sf.gov/resource--2024--civil-grand-jury-reports-2020-2021/",
                                 "https://www.sf.gov/resource--2024--civil-grand-jury-reports-2021-2022/"})
    for p in pages:
        m = re.search(r"reports-(\d{4})-(\d{4})", p)
        term = f"{m.group(1)}-{m.group(2)}"
        s = BeautifulSoup(get(p), "html.parser")
        current_report = None
        for a in (s.find("main") or s).find_all("a", href=True):
            h = urljoin(p, a["href"])
            if not re.search(r"/documents/", h):
                continue
            text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            kind = classify_cgj_link(text.split(" This report")[0] if "Full Report" in text else text, h)
            if "full report" in text.lower():
                kind = "cgj_report"
            if kind == "cgj_report":
                current_report = h
            docs.append({"doc_id": None, "source": "cgj", "doc_type": kind, "title": text,
                         "date": None, "url": h, "listing_url": p,
                         "extra": {"cgj_term": term, "parent_report_url": current_report if kind != "cgj_report" else None}})
    # dedupe by URL, then by normalized title within a term (some archive
    # pages list the same report twice under two filenames)
    def norm(t):
        t = re.sub(r"\s*[-(]?\s*(revised|final)\)?", "", t.lower())
        t = re.sub(rf"[-,]?\s*({MONTHS})\.?\s*\d{{0,2}},?\s*\d{{4}}.*$", "", t, flags=re.I)
        t = re.sub(r"\s+report$", "", t)
        return re.sub(r"[^a-z0-9]+", " ", t).strip()
    out, seen, seen_t = [], set(), set()
    for d in docs:
        if d["url"] in seen:
            continue
        seen.add(d["url"])
        if d["doc_type"] == "cgj_report":
            k = (d["extra"]["cgj_term"], norm(d["title"]))
            if k in seen_t:
                d["extra"]["duplicate_of_title"] = True
                continue
            seen_t.add(k)
        out.append(d)
    for i, d in enumerate(out):
        d["doc_id"] = f"CGJ-{d['extra']['cgj_term']}-{uid(d['url'])}"
    return out


MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"


def parse_date(t):
    m = re.search(rf"({MONTHS})\.? ?(\d{{1,2}})? ?,? ?(\d{{4}})", t)
    if not m:
        return None
    mon = m.group(1)[:3]
    day = int(m.group(2) or 1)
    try:
        return datetime.strptime(f"{mon} {day} {m.group(3)}", "%b %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def bla():
    docs = []
    for url, base in [("https://sfbos.archive.sf.gov/budget-legislative-analyst-reports", "https://sfbos.archive.sf.gov/"),
                      ("https://www.sf.gov/budget-and-legislative-analyst-bla", "https://api.sf.gov/")]:
        s = BeautifulSoup(get(url), "html.parser")
        for a in s.find_all("a", href=True):
            h = a["href"]
            t = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            if not (".pdf" in h.lower() or "/documents/" in h):
                continue
            if re.search(r"roster|meeting information guide|speaker card|election schedule|committee assignment|minutes|rules of order", t, re.I):
                continue
            full = urljoin(base, h)
            docs.append({"doc_id": None, "source": "bla", "doc_type": None, "title": t,
                         "date": parse_date(t), "url": full, "listing_url": url, "extra": {}})
    out, seen = [], set()
    for d in docs:
        if d["url"] in seen:
            continue
        seen.add(d["url"])
        out.append(d)
    for i, d in enumerate(out):
        tl = d["title"].lower()
        d["doc_type"] = "bla_performance_audit" if re.search(r"audit", tl) else "bla_other"
        d["doc_id"] = f"BLA-{uid(d['url'])}"
    return out


def classify_controller(d):
    t = d["title"].lower()
    if re.search(r"follow-?up on recommendation implementation|summary of (the )?implementation status|summary of recommendation implementation|recommendation implementation status", t):
        return "csa_followup_summary"
    if "not implemented after more than two years" in t:
        return "csa_open_over_2yrs"
    if re.search(r"public integrity .*(update|status)", t):
        return "pi_status_update"
    if re.search(r"field follow-?up|results of (the )?follow-?up|follow-?up (review|of)", t):
        return "csa_field_followup"
    if re.search(r"status of the implementation of the recommendations of the san francisco civil grand jur|status of the implementation of the sf civil grand", t):
        return "cgj_status_legacy"
    if "Whistleblower" in d["extra"]["categories"] and len(d["extra"]["categories"]) == 1:
        return "whistleblower"
    if "CP" in d["extra"]["categories"] and "AU" not in d["extra"]["categories"]:
        return "city_performance"
    return "csa_audit"


if __name__ == "__main__":
    out_path = os.path.join(RAW, "inventory.json")
    inv = []
    parts = sys.argv[1:] or ["cgj_status", "cgj", "bla", "controller"]
    old = []
    if os.path.exists(out_path):
        old = json.load(open(out_path))
        old = [d for d in old if d["source"] not in parts]
    for p in parts:
        docs = globals()[p]()
        if p == "controller":
            for d in docs:
                d["doc_type"] = classify_controller(d)
        print(p, len(docs), flush=True)
        inv.extend(docs)
    inv = old + inv
    json.dump(inv, open(out_path, "w"), indent=1)
    print("total", len(inv))
