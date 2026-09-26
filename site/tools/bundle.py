#!/usr/bin/env python3
"""Build the site's data bundles from the modules' exports (or the design sample data).

  python3 site/tools/bundle.py            # rebundle, print the readiness report
  python3 site/tools/bundle.py --strict   # exit 1 if a module that ships real data has an invalid file
  python3 site/tools/bundle.py --quiet    # summary only

For each module (nonprofits, performance, audits, network):
  * Looks for a real export in <module>/data/site/ (also accepts <module>/data/site/<module>/).
  * Uses it only if meta.json exists, validates, and says "sample": false. Otherwise the module
    falls back to design/prototype/sample-data/<module>/ (and its commentary), and every view of
    that dashboard shows a "sample data" banner. Real and sample data are never mixed in a module.
  * Normalizes the few documented shape variants (see normalize()), validates every file against
    tools/contracts.py (the machine-readable DATA_CONTRACT), and reports missing files/fields.
  * Writes site/data/<module>/<file>.<part>.js chunks (<= ~380 KB each, split by year where the
    rows carry one) and site/data/manifest.js, which the loader reads. A missing or invalid file is
    recorded as such; the site blanks only the views that need it ("analysis not available yet").
Works from file:// because chunks are plain <script> files.
"""
import fnmatch
import datetime as _dt
import glob
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
ROOT = os.path.dirname(SITE)
SAMPLE = os.path.join(ROOT, "design", "prototype", "sample-data")
OUT = os.path.join(SITE, "data")
CONTENT = os.path.join(SITE, "content")
sys.path.insert(0, HERE)
import contracts as C  # noqa: E402

CHUNK_LIMIT = 380_000
FILE_LIMIT = 400_000
MODULES = ["nonprofits", "performance", "audits", "network"]
DASH = {"nonprofits": "np", "performance": "pf", "audits": "au", "network": "nw"}
YEAR_FIELDS = ("fy", "first_fy", "last_fy", "dropped_fy", "base_fy")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
STREET_RE = re.compile(r"\b\d{1,5}\s+(?:[A-Z0-9][\w'.-]*\s+){1,4}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Way|Ln|Lane|Ct|Court|Pl|Place|Ter|Terrace)\b\.?")
ORGLIKE_RE = re.compile(r"\b(Foundation|LLC|L\.L\.C|Inc|Corp|Corporation|Company|Co|Association|Assn|Center|Centre|Church|Partners|Partnership|Group|Trust|Fund|School|Hospital|Clinic|Associates|Holdings|Properties|Owner|Ventures|LP|L\.P|Services|Housing|Project|Council|Society|Club|Hotel|Restaurant|Bar|Cafe)\b", re.I)
ZIP_RE = re.compile(r"(?<![\w-])9[0-6]\d{3}(?:-\d{4})?(?![\w-])")
PER_TYPE_ENTITY = ("official", "committee", "department", "contractor", "nonprofit", "lobbyist", "individuals", "donor_org")
PER_TYPE_FLOW = ("contribution", "behested", "lobby_contact", "lobby_payment", "contract", "payment")


# ------------------------------------------------------------------ normalization (mirrored in js/normalize.js)
def _int_year(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def normalize(module, rel, obj, notes):
    """Accept the documented variants so one shape reaches the UI. Every change is noted."""
    if not isinstance(obj, dict):
        return obj
    if rel == "meta.json":
        files = obj.get("files")
        if isinstance(files, dict):
            pre = module + "/"
            if any(k.startswith(pre) for k in files):
                obj["files"] = {(k[len(pre):] if k.startswith(pre) else k): v for k, v in files.items()}
        d = obj.get("deflator")
        if isinstance(d, dict) and "index" not in d and isinstance(d.get("multiplier_to_base"), dict):
            d["index"] = {k: round(1.0 / v, 6) for k, v in d["multiplier_to_base"].items() if v}
            notes.append("deflator.index derived from multiplier_to_base (index = 1 / multiplier)")
        if isinstance(d, dict):
            d["base_fy"] = _int_year(d.get("base_fy"))
    for key, arr in list(obj.items()):
        if not isinstance(arr, list):
            continue
        changed_years = 0
        for r in arr:
            if not isinstance(r, dict):
                continue
            for f in YEAR_FIELDS:
                if f in r and isinstance(r[f], float) and r[f].is_integer():
                    r[f] = int(r[f]); changed_years += 1
        if changed_years:
            notes.append(f"{key}: {changed_years} integral float years converted to int")
    if module == "performance" and rel == "measures/values.json":
        n = 0
        for r in obj.get("rows", []):
            if isinstance(r.get("met"), (int, float)) and not isinstance(r.get("met"), bool):
                r["met"] = bool(r["met"]); n += 1
        if n:
            notes.append(f"rows.met: {n} numeric 0/1 values converted to booleans")
    if module == "performance" and rel == "measures/measures.json":
        n = 0
        for m in obj.get("measures", []):
            dv = m.get("direction")
            if isinstance(dv, str) and dv.endswith("_better"):
                m["direction"] = dv[:-7]; n += 1
        if n:
            notes.append(f"measures.direction: {n} '*_better' values shortened")
    if module == "network" and rel == "entities.json":
        n = 0
        for e in obj.get("entities", []):
            for t in PER_TYPE_ENTITY:
                sub = e.get(t)
                if isinstance(sub, dict):
                    for k, v in sub.items():
                        e.setdefault(k, v)
                    if t != "official" or e.get("type") == "official":
                        pass
                    n += 1
        if n:
            notes.append(f"entities: {n} per-type sub-objects flattened")
    if module == "network" and rel == "flows.json":
        n = 0
        for f in obj.get("flows", []):
            sub = f.get(f.get("type"))
            if isinstance(sub, dict):
                for k, v in sub.items():
                    f.setdefault(k, v)
                n += 1
        if n:
            notes.append(f"flows: {n} per-type sub-objects flattened")
    if module == "network" and rel == "analyses/loop.json":
        for r in obj.get("rows", []):
            if "city_paid" not in r:
                for k in list(r):
                    m = re.match(r"^city_paid_fy(\d{4})$", k)
                    if m:
                        r["city_paid"] = r[k]; r["city_paid_fy"] = int(m.group(1))
    return obj


# ------------------------------------------------------------------ validation
class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, msg): self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)


def _type_ok(v, t):
    if t == "any":
        return True
    if t == "str":
        return isinstance(v, str)
    if t == "int":  # integral floats (12.0) are accepted; JSON has one number type
        return (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    if t == "num":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))
    if t == "bool":
        return isinstance(v, bool)
    if t == "list":
        return isinstance(v, list)
    if t == "dict":
        return isinstance(v, dict)
    if t == "date":
        return isinstance(v, str) and bool(DATE_RE.match(v))
    return True


def check_fields(obj, fields, where, rep, agg=None):
    """agg: dict collecting (field, problem) -> [count, example] for row arrays."""
    for f, t in fields.items():
        optional_key = t.startswith("~")
        t = t.lstrip("~")
        nullable = t.endswith("?")
        t = t.rstrip("?")
        if f not in obj:
            if optional_key:
                continue
            _note(agg, rep, (f, "missing"), where, f"missing field '{f}'")
            continue
        v = obj[f]
        if v is None:
            if not nullable:
                _note(agg, rep, (f, "null"), where, f"'{f}' is null (not allowed)")
            continue
        if not _type_ok(v, t):
            _note(agg, rep, (f, "type:" + t), where, f"'{f}' should be {t}, got {type(v).__name__} {json.dumps(v)[:60]}")


def _note(agg, rep, key, where, msg):
    if agg is None:
        rep.err(f"{where}: {msg}")
        return
    if key not in agg:
        agg[key] = [0, f"{where}: {msg}"]
    agg[key][0] += 1


def flush(agg, rep, total, label, level="err"):
    for (f, prob), (n, ex) in agg.items():
        msg = f"{label}: {n} of {total} rows — {ex}" if n > 1 else ex
        (rep.err if level == "err" else rep.warn)(msg)


def dim_ids(meta, dim):
    try:
        return {str(v.get("id")) for v in meta["dimensions"][dim]["values"]}
    except (KeyError, TypeError, AttributeError):
        return None


NAN_STRINGS = {"nan", "NaN", "NAN", "None", "none", "null", "NULL", "NaT", ""}


def repair_nan_strings(obj, spec, notes):
    """'nan'/'None'/'' strings in nullable non-text fields (a pandas export artifact the contract forbids)
    become null, so a handful of rows cannot blank a whole view. Counted in the report as a warning."""
    fixed = 0
    for key, fields in spec.get("arrays", {}).items():
        arr = obj.get(key)
        if not isinstance(arr, list):
            continue
        targets = [f for f, t in fields.items() if t.rstrip("?").lstrip("~") in ("date", "num", "int", "bool") and t.endswith("?")]
        for r in arr:
            if not isinstance(r, dict):
                continue
            for f in targets:
                if isinstance(r.get(f), str) and r[f].strip() in NAN_STRINGS:
                    r[f] = None
                    fixed += 1
    if fixed:
        notes.append(f"REPAIRED {fixed} 'nan'-like strings in nullable fields to null (the contract asks for null; fix in the exporter)")
    return fixed


def validate(module, rel, obj, spec, meta, loaded, real):
    rep = Report()
    if not isinstance(obj, dict):
        rep.err("top level is not a JSON object")
        return rep, 0
    check_fields(obj, dict(C.COMMON_KEYS, **spec.get("keys", {})), rel, rep)
    for k, sub in spec.get("nested", {}).items():
        if isinstance(obj.get(k), dict):
            check_fields(obj[k], sub, f"{rel} › {k}", rep)
    if real and obj.get("sample") is True and rel != "meta.json":
        rep.warn('file says "sample": true inside a real export')
    if rel == "meta.json":
        for dim in spec.get("dims", []):
            d = (obj.get("dimensions") or {}).get(dim)
            if not isinstance(d, dict):
                rep.err(f"dimensions.{dim} missing")
                continue
            check_fields(d, C.DIM_SHAPE, f"dimensions.{dim}", rep)
            for i, v in enumerate(d.get("values") or []):
                if not isinstance(v, dict) or "id" not in v:
                    rep.err(f"dimensions.{dim}.values[{i}] has no id"); break
        if module == "network":
            for i, r in enumerate(obj.get("rules") or []):
                miss = [k for k in ("id", "short", "cite", "text") if not (isinstance(r, dict) and r.get(k))]
                if miss:
                    rep.err(f"rules[{i}] lacks {', '.join(miss)} (a review tag must sit beside a cited rule)")
            ids = {r.get("id") for r in obj.get("rules") or [] if isinstance(r, dict)}
            for need in ("ban", "behested", "lobby", "limits"):
                if need not in ids:
                    rep.warn(f"rules has no '{need}' rule; the matching rule box will be omitted")
            ab = (obj.get("dimensions") or {}).get("amount_bands")
            if not isinstance(ab, list) or not ab:
                rep.err("dimensions.amount_bands missing (the Minimum amount filter needs it)")
        if not obj.get("files"):
            rep.warn("meta.files missing; file sizes are taken from disk")
    rows_total = 0
    for key, fields in spec.get("arrays", {}).items():
        arr = obj.get(key)
        if not isinstance(arr, list):
            rep.err(f"'{key}' array missing")
            continue
        rows_total += len(arr)
        agg, bad_rows = {}, []
        for i, r in enumerate(arr):
            if not isinstance(r, dict):
                _note(agg, rep, ("row", "notobj"), f"{key}[{i}]", "row is not an object")
                bad_rows.append(i)
                continue
            before = sum(v[0] for v in agg.values())
            check_fields(r, fields, f"{key}[{i}]", rep, agg)
            if sum(v[0] for v in agg.values()) > before:
                bad_rows.append(i)
        # A few malformed rows (<= 1% of the array) are dropped with a warning instead of blanking every view
        # that needs the file; more than that means the export is broken and the file is not used.
        if bad_rows and len(bad_rows) <= max(1, len(arr) // 100):
            drop = set(bad_rows)
            msgs = [ex for (_, _), (_, ex) in agg.items()]
            obj[key] = [r for i, r in enumerate(arr) if i not in drop]
            rows_total -= len(drop)
            rep.warn(f"{key}: dropped {len(drop)} of {len(arr)} malformed rows (e.g. {msgs[0]})")
        else:
            flush(agg, rep, len(arr), key)
    # enums and references
    for path, rule in spec.get("enums", {}).items():
        key, field = path.split(".")
        arr = obj.get(key)
        if not isinstance(arr, list):
            continue
        strict = rule.endswith("!")
        rule = rule.rstrip("!")
        allowed, what = None, rule
        if rule.startswith("dim:"):
            src = obj if rel == "meta.json" else meta
            allowed = dim_ids(src, rule[4:]) if src else None
            if rule[4:] == "result" and allowed is None and isinstance(obj.get("results"), list):
                allowed = {r.get("id") for r in obj["results"]}
            if rule[4:] == "result" and isinstance(obj.get("results"), list):
                allowed = {r.get("id") for r in obj["results"]}
            what = f"meta.dimensions.{rule[4:]}"
        elif rule.startswith("ref:"):
            tfile, tpath = rule[4:].split("#")
            tkey, tfield = tpath.split(".")
            target = obj if tfile == rel else loaded.get(tfile)
            if isinstance(target, dict) and isinstance(target.get(tkey), list):
                allowed = {str(t.get(tfield)) for t in target[tkey] if isinstance(t, dict)}
            what = tfile
        else:
            allowed = set(rule.split("|"))
        if allowed is None:
            continue
        bad, ex = 0, None
        for r in arr:
            if not isinstance(r, dict) or r.get(field) is None:
                continue
            vals = r[field] if isinstance(r[field], list) else [r[field]]
            for v in vals:
                if str(v) not in allowed:
                    bad += 1
                    ex = ex or v
        if bad:
            msg = f"{key}.{field}: {bad} values not in {what} (e.g. {json.dumps(ex)})"
            (rep.err if strict else rep.warn)(msg)
    if spec.get("unique"):
        key, field = spec["unique"].split(".")
        vals = [r.get(field) for r in obj.get(key, []) if isinstance(r, dict)]
        if len(vals) != len(set(vals)):
            rep.err(f"{key}.{field} has {len(vals) - len(set(vals))} duplicate ids")
    for rule in spec.get("row_rules", []):
        ROW_RULES[rule](obj, rep, real)
    return rep, rows_total


def rr_review_cites_report(obj, rep, real):
    no_url = no_title = no_page = 0
    for r in obj.get("rows", []):
        rp = r.get("report") if isinstance(r, dict) else None
        if not isinstance(rp, dict) or not rp.get("title"):
            no_title += 1
            continue
        if not rp.get("url"):
            no_url += 1
        if r.get("result") != "none" and rp.get("page") is None:
            no_page += 1
    if no_title:
        rep.err(f"rows: {no_title} monitoring results do not cite a report title")
    if no_url and real:
        rep.warn(f"rows: {no_url} results have no report url (required in production)")
    if no_page:
        rep.warn(f"rows: {no_page} results with findings have no page number")


def rr_months_iff_implemented(obj, rep, real):
    bad = sum(1 for r in obj.get("rows", []) if isinstance(r, dict) and ((r.get("months_to_close") is not None) != (r.get("status") == "implemented")))
    if bad:
        rep.warn(f"rows: {bad} recommendations break 'months_to_close iff implemented'")


def rr_consequence_score(obj, rep, real):
    bad = nowhy = 0
    for r in obj.get("rows", []):
        c = r.get("consequence") if isinstance(r, dict) else None
        s = c.get("score") if isinstance(c, dict) else None
        if not isinstance(s, (int, float)) or isinstance(s, bool) or not (1 <= s <= 10):
            bad += 1
            continue
        if (s >= 7 or r.get("repeat_of")) and not c.get("why"):
            nowhy += 1
    if bad:
        rep.err(f"rows: {bad} recommendations lack consequence.score in 1..10")
    if nowhy:
        rep.warn(f"rows: {nowhy} recommendations with score >= 7 or a repeat lack consequence.why")


def rr_rules_cited(obj, rep, real):
    pass  # handled in validate() for meta


def _strings(o, key=None):
    """Yield (key, string) for every string value, skipping id-like keys."""
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "id" or k.endswith("_id") or k in ("from", "to", "ref", "url", "date"):
                continue
            yield from _strings(v, k)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v, key)
    elif isinstance(o, str):
        yield key, o


def rr_no_addresses(obj, rep, real):
    street = zipc = 0
    ex_s = ex_z = None
    for key in ("entities", "flows"):
        for r in obj.get(key, []):
            if not isinstance(r, dict):
                continue
            for k, s in _strings(r):
                if STREET_RE.search(s) and not (k == "name" and r.get("type") not in ("individuals",)) and not ORGLIKE_RE.search(s):
                    street += 1; ex_s = ex_s or f"{r.get('id')}.{k} = {s[:60]!r}"
                if ZIP_RE.search(s):
                    zipc += 1; ex_z = ex_z or f"{r.get('id')}.{k} = {s[:60]!r}"
    if street:
        rep.err(f"{street} strings look like street addresses (never allowed; e.g. {ex_s})")
    if zipc:
        rep.warn(f"{zipc} strings contain a ZIP-like number (check for addresses; e.g. {ex_z})")


def rr_review_has_reason(obj, rep, real):
    bad = 0
    for r in obj.get("records", []):
        if isinstance(r, dict) and r.get("review") == "appears_to_warrant_review" and not (r.get("why") and r.get("inside_window") and r.get("covered_official")):
            bad += 1
    if bad:
        rep.warn(f"records: {bad} 'appears_to_warrant_review' rows lack a reason or the window/covered-official conditions; the UI shows them as a pattern only")


ROW_RULES = {"review_cites_report": rr_review_cites_report, "months_iff_implemented": rr_months_iff_implemented, "consequence_score": rr_consequence_score,
             "rules_cited": rr_rules_cited, "no_addresses": rr_no_addresses, "review_has_reason": rr_review_has_reason}


def validate_commentary(view, obj, real):
    rep = Report()
    if not isinstance(obj, dict):
        rep.err("not a JSON object")
        return rep
    if view.startswith("story_"):
        check_fields(obj, C.STORY_SPEC, view, rep)
        for i, s in enumerate(obj.get("steps") or []):
            if not isinstance(s, dict) or not s.get("view") or not s.get("title"):
                rep.err(f"steps[{i}] needs view and title")
        return rep
    check_fields(obj, C.COMMENTARY, view, rep)
    for i, t in enumerate(obj.get("templates") or []):
        if not isinstance(t, dict) or not t.get("id") or not isinstance(t.get("template"), str):
            rep.err(f"templates[{i}] needs id and template")
        elif t.get("requires") and not t.get("fallback"):
            rep.warn(f"templates[{i}] ({t['id']}) has requires but no fallback sentence")
    ids = {t.get("id") for t in obj.get("templates") or [] if isinstance(t, dict)}
    for need in C.TEMPLATE_IDS.get(view, []):
        if need not in ids:
            rep.warn(f"no template '{need}' (the view fills its slots; no live sentence will show)")
    for i, c in enumerate(obj.get("caveats") or []):
        if not isinstance(c, dict) or not c.get("text"):
            rep.err(f"caveats[{i}] needs text")
        elif c.get("severity") not in ("high", "medium", "low"):
            rep.warn(f"caveats[{i}] severity {c.get('severity')!r} not high/medium/low")
    for i, a in enumerate(obj.get("annotations") or []):
        if not isinstance(a, dict) or not a.get("chart") or "x" not in a or not a.get("text"):
            rep.err(f"annotations[{i}] needs chart, x, text")
        elif len(a["text"]) > 90:
            rep.warn(f"annotations[{i}] text over 90 characters")
        if isinstance(a, dict) and a.get("chart") and a["chart"] not in C.CHART_IDS.get(view, []):
            rep.warn(f"annotations[{i}] chart '{a['chart']}' is not drawn on {view} (drawn: {', '.join(C.CHART_IDS.get(view, [])) or 'none'})")
    text = " ".join([obj.get("headline") or ""] + [p for p in obj.get("paragraphs") or [] if isinstance(p, str)])
    low = text.lower()
    for w in C.FAIRNESS_WORDS:
        for m in re.finditer(re.escape(w), low):
            ctxs = low[max(0, m.start() - 40):m.start()]
            if not re.search(r"\b(not|no|never|without|nor)\b", ctxs):
                rep.warn(f"fairness lint: '{w}' appears without a negation nearby; check the wording")
                break
    if real and obj.get("sample"):
        rep.warn('commentary says "sample": true inside a real export')
    return rep


# ------------------------------------------------------------------ discovery and loading
def find_real_root(module):
    base = os.path.join(ROOT, module, "data", "site")
    for cand in (base, os.path.join(base, module)):
        if os.path.isfile(os.path.join(cand, "meta.json")):
            return cand, (cand != base)
    has_any = os.path.isdir(base) and any(f.endswith(".json") for _, _, fs in os.walk(base) for f in fs)
    return (None, has_any)


def physical_files(root, rel, spec):
    """The base file (if present) followed by every split part (if any)."""
    p = os.path.join(root, rel)
    out = [p] if os.path.isfile(p) else []
    if spec.get("split"):
        out += [x for x in sorted(glob.glob(os.path.join(root, spec["split"]))) if x != p]
    return out


def read_json(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    return json.loads(raw.decode("utf-8")), len(raw)


def load_logical(root, rel, spec, notes=None):
    """Returns (obj|None, bytes, paths, error). Merges the base file and split parts; de-duplicates rows on spec['key']."""
    paths = physical_files(root, rel, spec)
    if not paths:
        return None, 0, [], "missing"
    total, merged = 0, None
    for p in paths:
        try:
            o, n = read_json(p)
        except (ValueError, UnicodeDecodeError) as e:
            return None, 0, paths, f"not valid JSON: {os.path.relpath(p, ROOT)}: {e}"
        total += n
        if merged is None:
            merged = o
        else:
            for k, v in (o.items() if isinstance(o, dict) else []):
                if isinstance(v, list) and isinstance(merged.get(k), list):
                    merged[k].extend(v)
                elif k not in merged:
                    merged[k] = v
    if len(paths) > 1 and spec.get("key") and isinstance(merged, dict):
        for k, v in merged.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and all(f in v[0] for f in spec["key"]):
                seen, out = set(), []
                for r in v:
                    key = tuple(json.dumps(r.get(f)) for f in spec["key"]) if isinstance(r, dict) else None
                    if key in seen:
                        continue
                    seen.add(key); out.append(r)
                if notes is not None:
                    notes.append(f"merged {len(paths)} files ({os.path.basename(paths[0])} + {len(paths) - 1} parts); {len(v) - len(out)} duplicate rows dropped on ({', '.join(spec['key'])})")
                merged[k] = out
    return merged, total, paths, None


# ------------------------------------------------------------------ chunk writing
def year_of(r):
    if not isinstance(r, dict):
        return None
    for f in ("fy", "date_issued", "date", "month"):
        v = r.get(f)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and len(v) >= 4 and v[:4].isdigit():
            return int(v[:4])
    return None


def split_rows(rows, limit):
    """Split into consecutive groups <= limit bytes, keeping a year together where rows carry one."""
    sizes = [len(json.dumps(r, separators=(",", ":"), ensure_ascii=False)) + 1 for r in rows]
    years = [year_of(r) for r in rows]
    if all(y is not None for y in years) and rows:
        order = sorted(range(len(rows)), key=lambda i: years[i])
        groups, cur, cur_n, cur_y = [], [], 0, None
        for i in order:
            if cur and cur_n + sizes[i] > limit and years[i] != cur_y:
                groups.append(cur); cur, cur_n = [], 0
            elif cur and cur_n + sizes[i] > limit * 1.6:
                groups.append(cur); cur, cur_n = [], 0
            cur.append(rows[i]); cur_n += sizes[i]; cur_y = years[i]
        if cur:
            groups.append(cur)
        return groups
    groups, cur, cur_n = [], [], 0
    for r, s in zip(rows, sizes):
        if cur and cur_n + s > limit:
            groups.append(cur); cur, cur_n = [], 0
        cur.append(r); cur_n += s
    if cur:
        groups.append(cur)
    return groups


def encode_array(rows):
    """Columnar encoding for large arrays of objects: {"__enc": "cols", cols, rows: [[...]], dicts, sparse}.
    Low-cardinality string columns are dictionary-encoded. js/data.js decodes it back to objects."""
    cols, seen = [], set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k); cols.append(k)
    sparse = [c for c in cols if any(c not in r for r in rows)]
    dicts = {}
    for c in cols:
        vals = [r.get(c) for r in rows]
        strs = [v for v in vals if v is not None]
        if strs and all(isinstance(v, str) for v in strs):
            distinct = sorted(set(strs))
            if len(distinct) <= max(64, len(rows) // 5) and sum(len(v) for v in strs) / len(strs) > 6:
                dicts[c] = distinct
    index = {c: {v: i for i, v in enumerate(d)} for c, d in dicts.items()}
    out = []
    for r in rows:
        row = []
        for c in cols:
            v = r.get(c)
            row.append(index[c][v] if c in index and v is not None else v)
        out.append(row)
    return {"__enc": "cols", "cols": cols, "dicts": dicts, "sparse": sparse, "rows": out}


def _size(o):
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False))


def write_chunks(logical, obj):
    """logical e.g. 'nonprofits/payments/cells.json'. Returns (chunk paths relative to site/, split key, total chunk bytes)."""
    base = os.path.join(OUT, logical[:-5] if logical.endswith(".json") else logical)
    os.makedirs(os.path.dirname(base), exist_ok=True)
    obj = dict(obj)
    for k, v in list(obj.items()):
        if isinstance(v, list) and len(v) >= 400 and all(isinstance(r, dict) for r in v):
            enc = encode_array(v)
            if _size(enc) < 0.85 * _size(v):
                obj[k] = enc
    parts, key = [obj], None
    if _size(obj) > CHUNK_LIMIT:
        cands = [(k, v) for k, v in obj.items() if isinstance(v, list) or (isinstance(v, dict) and v.get("__enc") == "cols")]
        if cands:
            key, big = max(cands, key=lambda kv: _size(kv[1]))
            rows = big["rows"] if isinstance(big, dict) else big
            head_bytes = _size(obj) - _size(rows)
            groups = split_rows(rows, max(60_000, CHUNK_LIMIT - head_bytes)) if not isinstance(big, dict) else split_plain(rows, max(60_000, CHUNK_LIMIT - head_bytes))
            head = {k: v for k, v in obj.items() if k != key}
            first = dict(big, rows=groups[0]) if isinstance(big, dict) else groups[0]
            parts = [dict(head, **{key: first})] + [{key: ({"rows": g} if isinstance(big, dict) else g)} for g in groups[1:]]
    out, total = [], 0
    for i, p in enumerate(parts):
        path = f"{base}.{i}.js"
        body = json.dumps(p, separators=(",", ":"), ensure_ascii=False).replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        text = f"SFCM_DATA_PART({json.dumps(logical)},{i},{len(parts)},{body});\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        total += len(text.encode("utf-8"))
        out.append(os.path.relpath(path, SITE))
    return out, key, total


def split_plain(rows, limit):
    groups, cur, n = [], [], 0
    for r in rows:
        s = _size(r) + 1
        if cur and n + s > limit:
            groups.append(cur); cur, n = [], 0
        cur.append(r); n += s
    if cur:
        groups.append(cur)
    return groups


# ------------------------------------------------------------------ main
def rel_to_site(p):
    return os.path.relpath(p, SITE).replace(os.sep, "/")


def bundle_module(module, report_lines, quiet):
    dash = DASH[module]
    spec_all = C.SPEC[module]
    real_root, nested = find_real_root(module)
    decision, reason = "sample", None
    real_meta_rep = None
    if real_root:
        notes = []
        try:
            meta, _ = read_json(os.path.join(real_root, "meta.json"))
            meta = normalize(module, "meta.json", meta, notes)
            real_meta_rep, _n = validate(module, "meta.json", meta, spec_all["meta.json"], meta, {}, True)
            if meta.get("sample") is not False:
                reason = 'meta.json does not say "sample": false' + (' (key absent)' if "sample" not in meta else f' (sample = {meta.get("sample")!r})')
            elif real_meta_rep.errors:
                reason = "meta.json fails the contract: " + "; ".join(real_meta_rep.errors[:3])
            else:
                decision = "real"
        except (ValueError, OSError) as e:
            reason = f"meta.json unreadable: {e}"
    else:
        reason = f"no meta.json in {module}/data/site/" + (" (other JSON files exist there, not in the contract layout)" if nested else "")
    root = real_root if decision == "real" else os.path.join(SAMPLE, module)
    comm_root = os.path.join(real_root, "commentary") if decision == "real" else os.path.join(SAMPLE, "commentary")
    mod = {"module": module, "dash": dash, "source": decision, "reason": reason, "root": rel_to_site(root),
           "nested_layout": bool(nested and decision == "real"), "files": {}, "commentary": {}}
    loaded = {}
    order = ["meta.json"] + [k for k in spec_all if k != "meta.json"]
    # load referenced files first (orgs, measures, reports, entities) so refs can be checked
    for rel in order:
        spec = spec_all[rel]
        merge_notes = []
        obj, nbytes, paths, err = load_logical(root, rel, spec, merge_notes)
        logical = f"{module}/{rel}"
        entry = {"status": "missing", "bytes": nbytes, "raw": [rel_to_site(p) for p in paths] if decision == "real" else [],
                 "sample": decision == "sample", "optional": bool(spec.get("optional")), "errors": [], "warnings": [], "notes": [], "rows": 0}
        if err and err != "missing":
            entry.update(status="invalid", errors=[err])
        elif obj is not None:
            notes = list(merge_notes)
            obj = normalize(module, rel, obj, notes)
            repaired = repair_nan_strings(obj, spec, notes)
            rep, rows = validate(module, rel, obj, spec, loaded.get("meta.json"), loaded, decision == "real")
            entry.update(rows=rows, errors=rep.errors, warnings=rep.warnings + [n for n in notes if n.startswith("REPAIRED")], notes=[n for n in notes if not n.startswith("REPAIRED")], repaired=bool(repaired))
            big = [p for p in paths if os.path.getsize(p) > FILE_LIMIT]
            if big and decision == "real":
                entry["warnings"].append(f"{len(big)} file(s) over the contract's 400 KB (largest {max(os.path.getsize(p) for p in big)/1e3:.0f} KB: {os.path.basename(max(big, key=os.path.getsize))})" + (f"; the contract suggests per-year files ({spec['split']})" if spec.get("split") and len(paths) == 1 else "") + "; bundled in chunks")
            if rep.errors:
                entry["status"] = "invalid"
            else:
                entry["status"] = "ok"
                loaded[rel] = obj
                slim = obj
                if spec.get("bundle_drop"):
                    slim = dict(obj)
                    for k, fields in spec["bundle_drop"].items():
                        if isinstance(obj.get(k), list):
                            slim[k] = [{f: v for f, v in r.items() if f not in fields} for r in obj[k]]
                    entry["notes"].append("bundle omits unused fields: " + ", ".join(sorted({f for fs in spec["bundle_drop"].values() for f in fs})))
                entry["chunks"], entry["split_key"], entry["chunk_bytes"] = write_chunks(logical, slim)
        mod["files"][logical] = entry
    # commentary
    for view in C.VIEWS[module] + [C.STORY[module]]:
        p = os.path.join(comm_root, view + ".json")
        logical = f"{module}/commentary/{view}.json"
        entry = {"status": "missing", "bytes": 0, "raw": [], "sample": decision == "sample", "errors": [], "warnings": []}
        if os.path.isfile(p):
            try:
                obj, n = read_json(p)
                rep = validate_commentary(view, obj, decision == "real")
                entry.update(bytes=n, errors=rep.errors, warnings=rep.warnings, raw=[rel_to_site(p)] if decision == "real" else [])
                if rep.errors:
                    entry["status"] = "invalid"
                else:
                    entry["status"] = "ok"
                    if decision == "sample" and isinstance(obj, dict):
                        obj.setdefault("sample", True)
                    entry["chunks"], _, entry["chunk_bytes"] = write_chunks(logical, obj)
            except ValueError as e:
                entry.update(status="invalid", errors=[f"not valid JSON: {e}"])
        mod["commentary"][logical] = entry
    meta = loaded.get("meta.json") or {}
    mod["as_of"] = meta.get("as_of")
    mod["_meta"] = meta
    mod["sample_meta"] = meta.get("sample")
    # --- report
    L = report_lines
    L.append("")
    L.append(f"== {module} ({dash}): using {decision.upper()} data" + (f" — {reason}" if reason else ""))
    if decision == "sample" and real_root:
        L.append(f"   real export found at {os.path.relpath(real_root, ROOT)}{' (nested layout)' if nested else ''}; previewing it against the contract:")
        prev = preview_real(module, real_root)
        L.extend("   " + x for x in prev)
    if decision == "real":
        ex = extra_files(module, real_root)
        if ex:
            L.append(f"   not in the contract, not loaded: {len(ex)} files ({', '.join(ex[:5])}{' …' if len(ex) > 5 else ''})")
    for logical, e in list(mod["files"].items()) + list(mod["commentary"].items()):
        if quiet and e["status"] == "ok" and not e["errors"]:
            continue
        flag = {"ok": "OK     ", "invalid": "INVALID", "missing": "MISSING"}[e["status"]]
        if e["status"] == "missing" and e.get("optional"):
            flag = "absent "
        extra = (f"{e['rows']:>8,} rows" if e.get('rows') else " " * 13) + f" {e['bytes']/1e3:>7.0f} KB" + (f" → {e['chunk_bytes']/1e3:.0f} KB bundled" if e.get('chunk_bytes') and e['chunk_bytes'] < 0.8 * e['bytes'] else "") if e["status"] != "missing" else ""
        L.append(f"   {flag} {logical:<48} {extra}")
        for x in e["errors"][:6]:
            L.append(f"            error: {x}")
        if len(e["errors"]) > 6:
            L.append(f"            … {len(e['errors']) - 6} more errors")
        if not quiet:
            for x in e["warnings"][:4]:
                L.append(f"            warn:  {x}")
            for x in e.get("notes", [])[:3]:
                L.append(f"            note:  {x}")
    return mod


def preview_real(module, root):
    out, loaded = [], {}
    meta = None
    for rel, spec in C.SPEC[module].items():
        obj, nbytes, paths, err = load_logical(root, rel, spec)
        if err:
            if not spec.get("optional"):
                out.append(f"  {'MISSING' if err == 'missing' else 'INVALID'} {rel}" + ("" if err == "missing" else f": {err}"))
            continue
        notes = []
        obj = normalize(module, rel, obj, notes)
        repair_nan_strings(obj, spec, notes)
        if rel == "meta.json":
            meta = obj
        rep, rows = validate(module, rel, obj, spec, meta, loaded, True)
        loaded[rel] = obj
        status = "INVALID" if rep.errors else "ok     "
        out.append(f"  {status} {rel:<34} {rows:>8,} rows {nbytes/1e3:>7.0f} KB")
        for x in rep.errors[:4]:
            out.append(f"           error: {x}")
        if len(rep.errors) > 4:
            out.append(f"           … {len(rep.errors) - 4} more errors")
    comm = os.path.join(root, "commentary")
    have = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(comm, "*.json")))
    want = C.VIEWS[module] + [C.STORY[module]]
    missing = [v for v in want if v not in have]
    out.append(f"  commentary: {len(want) - len(missing)} of {len(want)} view files present" + (f"; missing {', '.join(missing[:4])}{'…' if len(missing) > 4 else ''}" if missing else ""))
    extra = extra_files(module, root)
    if extra:
        out.append(f"  not in the contract (ignored): {', '.join(extra[:6])}{' …' if len(extra) > 6 else ''}")
    return out


def extra_files(module, root):
    """JSON files in an export that no contract entry reads (reported, never loaded)."""
    extra = []
    for dirpath, _, fs in os.walk(root):
        for f in fs:
            rp = os.path.relpath(os.path.join(dirpath, f), root)
            if f.endswith(".json") and not any(rp == k or (C.SPEC[module][k].get("split") and fnmatch.fnmatch(rp, C.SPEC[module][k]["split"])) for k in C.SPEC[module]) and not rp.startswith("commentary"):
                extra.append(rp)
    return sorted(extra)


def build_site_json(mods, loaded_meta):
    depts, seen = [], {}
    order = ["performance", "nonprofits", "audits"]
    for m in order:
        meta = loaded_meta.get(m) or {}
        for v in ((meta.get("dimensions") or {}).get("dept") or {}).get("values") or []:
            if not isinstance(v, dict) or not v.get("id"):
                continue
            if v["id"] in seen:
                d = seen[v["id"]]
                if mods[m]["source"] == "real":
                    d["sample"] = False
                for k in ("name", "group", "short"):
                    if not d.get(k) and v.get(k):
                        d[k] = v[k]
                continue
            d = {"id": v["id"], "name": v.get("name") or v.get("label") or v["id"], "group": v.get("group"), "short": v.get("short") or v["id"], "from": m,
                 "sample": mods[m]["source"] == "sample"}
            seen[v["id"]] = d
            depts.append(d)
    groups = ((loaded_meta.get("performance") or {}).get("dimensions") or {}).get("group", {}).get("values") or []
    return {"generated_at": _dt.datetime.now().isoformat(timespec="seconds"), "sample": any(mods[m]["source"] == "sample" for m in mods),
            "modules": {m: {"as_of": mods[m]["as_of"], "source": mods[m]["source"]} for m in mods}, "departments": depts, "groups": groups}


def main(argv):
    quiet = "--quiet" in argv
    strict = "--strict" in argv
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    lines = [f"SF City Monitor bundle — {_dt.datetime.now().isoformat(timespec='seconds')}", f"root: {ROOT}"]
    mods, metas = {}, {}
    for m in MODULES:
        mods[m] = bundle_module(m, lines, quiet)
        metas[m] = mods[m].pop("_meta")
    site = build_site_json(mods, metas)
    site_files = {}
    chunks, _, _cb = write_chunks("site/site.json", site)
    site_files["site/site.json"] = {"status": "ok", "bytes": len(json.dumps(site)), "chunks": chunks, "sample": False, "errors": [], "warnings": [], "raw": []}
    for p in sorted(glob.glob(os.path.join(CONTENT, "commentary", "*.json"))):
        view = os.path.basename(p)[:-5]
        obj, n = read_json(p)
        rep = validate_commentary(view, obj, True)
        logical = f"site/commentary/{view}.json"
        e = {"status": "invalid" if rep.errors else "ok", "bytes": n, "sample": False, "errors": rep.errors, "warnings": rep.warnings, "raw": [rel_to_site(p)]}
        if not rep.errors:
            e["chunks"], _, e["chunk_bytes"] = write_chunks(logical, obj)
        site_files[logical] = e
    manifest = {"generated_at": site["generated_at"], "tool": "site/tools/bundle.py", "chunk_limit": CHUNK_LIMIT,
                "modules": {DASH[m]: mods[m] for m in MODULES}, "site": site_files}
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(OUT, "manifest.js"), "w", encoding="utf-8") as fh:
        fh.write("window.SFCM_MANIFEST = " + json.dumps(manifest, separators=(",", ":"), ensure_ascii=False) + ";\n")
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    nchunks = sum(1 for dp, _, fs in os.walk(OUT) for f in fs if f.endswith(".js")) - 1
    lines.append("")
    lines.append("Summary: " + ", ".join(f"{m} {mods[m]['source']}" for m in MODULES) + f"; {nchunks} chunks, {total/1e6:.2f} MB in site/data/")
    bad = [(m, k) for m in MODULES for k, e in mods[m]["files"].items() if e["status"] != "ok" and not e.get("optional")]
    if bad:
        lines.append("Unavailable files (their views show 'analysis not available yet'): " + ", ".join(k for _, k in bad))
    print("\n".join(lines))
    if strict and any(mods[m]["source"] == "real" for m, _ in bad):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
