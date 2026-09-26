"""Red team, finding G: organizations paid after an IRS automatic revocation of tax-exempt status.

Independent of 12_analysis.revoked_and_nonfilers(): re-parses the raw IRS files and re-fetches voucher-level
payments from data.sf.gov for every candidate, then checks each organization individually.

For every matched EIN (vendor_map, public universities excluded) that appears in the raw IRS auto-revocation
list (data/raw/irs/data-download-revocation.txt; columns EIN|name|DBA|street|city|state|zip|country|
subsection|revocation date|posting date|reinstatement date) this script records:
  * every revocation entry (an EIN can be revoked, reinstated and revoked again);
  * whether the EIN is in the current IRS Business Master File (eo1-4.csv, eo_ca.csv): reinstated
    organizations reappear there, and reinstatement can be retroactive;
  * payments by the pipeline's definition (city fiscal years after the fiscal year of the revocation date);
  * payments after the IRS *posted* the revocation (the date the public, and the city, could first see it):
    PeopleSoft-era vouchers (FY2018+) by the voucher's source-system timestamp (data_as_of); FAMIS-era
    (FY2007-17) rows carry a 2017 conversion timestamp, so only fiscal years that began after the posting
    date are counted (conservative);
  * the match: vendor name, adjudicator confidence and rationale (a low-confidence or alias-only match
    is excluded from any published count).
Output: data/redteam/parts/revocations.json
"""
import csv, glob, json, os, subprocess, urllib.parse
from collections import defaultdict
from datetime import date, datetime

import pandas as pd

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
RAW = os.path.join(BASE, "raw")
OUT = os.path.join(BASE, "redteam")
CACHE = os.path.join(OUT, "cache")
os.makedirs(os.path.join(OUT, "parts"), exist_ok=True)
os.makedirs(CACHE, exist_ok=True)
EXP_CHARS = {"Non Personnel Services", "Non-Personnel Services", "City Grant Programs", "City Grant Program",
             "Other Support&Care Of Persons", "Other Support/Care of Persons", "Aid Assistance", "Aid Payments",
             "Materials & Supplies", "Capital Outlay", "Capitalized Expenditures", "Facilities Maintenance",
             "Programmatic Projects", "Overhead and Allocations"}
MIN_CONFIDENCE = 0.9   # below this, a name match is not strong enough to name an organization
LAST_FULL_FY = 2026


def d(s):
    return datetime.strptime(s.strip(), "%d-%b-%Y").date() if s and s.strip() else None


def fy_of(dt):
    return dt.year + (1 if dt.month >= 7 else 0)


def fetch_vouchers(vendor):
    key = "".join(c if c.isalnum() else "_" for c in vendor)[:80]
    path = os.path.join(CACHE, f"vouchers_{key}.json")
    if os.path.exists(path):
        return json.load(open(path))
    q = ("SELECT fiscal_year, department_code, character, object, contract_number, contract_title, voucher, "
         f"vouchers_paid, data_as_of WHERE vendor='{vendor.replace(chr(39), chr(39) * 2)}' AND vouchers_paid != 0 LIMIT 50000")
    url = "https://data.sf.gov/resource/n9pm-xkyq.json?" + urllib.parse.urlencode({"$query": q})
    r = subprocess.run(["perl", "-e", "alarm 180; exec @ARGV", "curl", "-s", "-f", url], capture_output=True)
    rows = json.loads(r.stdout)
    json.dump(rows, open(path, "w"))
    return rows


def compute():
    vm = pd.read_parquet(os.path.join(BASE, "interim", "vendor_map.parquet"))
    vm = vm[vm.org_class != "public_university"]
    eins = set(vm.ein)
    rev = defaultdict(list)
    with open(os.path.join(RAW, "irs", "data-download-revocation.txt"), encoding="latin-1") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|")
            if len(p) >= 11 and p[0] in eins:
                rev[p[0]].append({"name": p[1].strip(), "dba": p[2].strip(), "city": p[4].strip(), "subsection": p[8],
                                  "revocation_date": str(d(p[9])), "posting_date": str(d(p[10])),
                                  "reinstatement_date": str(d(p[11])) if len(p) > 11 and p[11].strip() else None})
    in_bmf = set()
    for f in glob.glob(os.path.join(RAW, "irs", "eo*.csv")):
        with open(f, newline="", encoding="latin-1") as fh:
            for r in csv.reader(fh):
                if r and r[0] in rev:
                    in_bmf.add(r[0])
    # annual expenditure-class payments from the raw per-FY aggregates (independent of np_payments)
    v2e = dict(zip(vm.vendor, vm.ein))
    by_fy = defaultdict(lambda: defaultdict(float))
    for f in sorted(glob.glob(os.path.join(RAW, "payments_agg_fy*.csv"))):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                e = v2e.get(r["vendor"].strip())
                if e in rev and r["character"] in EXP_CHARS:
                    by_fy[e][int(r["fiscal_year"])] += float(r["paid"] or 0)
    out = []
    for ein, entries in sorted(rev.items()):
        entries = sorted(entries, key=lambda x: x["revocation_date"])
        last = entries[-1]
        rdate, pdate = date.fromisoformat(last["revocation_date"]), date.fromisoformat(last["posting_date"])
        rein = last["reinstatement_date"]
        pay = by_fy.get(ein, {})
        rfy = fy_of(rdate)
        pipeline_def = sum(v for fy, v in pay.items() if fy > rfy and (rein is None))
        if pipeline_def <= 0 and not any(fy > rfy for fy in pay):
            continue
        vend = vm[vm.ein == ein]
        rec = {"ein": ein, "irs_name": last["name"], "irs_dba": last["dba"], "subsection": last["subsection"],
               "revocations": entries, "in_current_bmf": ein in in_bmf,
               "vendors": vend.vendor.tolist(), "match_confidence": float(vend.confidence.max()),
               "match_pass": int(vend["pass"].min()), "match_rationale": vend.rationale.iloc[0][:400],
               "paid_by_fy": {str(k): round(v, 2) for k, v in sorted(pay.items())},
               "paid_after_revocation_fy_pipeline_def": round(pipeline_def, 2)}
        if rein is not None or ein in in_bmf:
            rec["status"] = "reinstated_or_in_bmf"
            out.append(rec)
            continue
        # voucher-level check
        after_post, after_post_full, before_post_after_rev, lines = 0.0, 0.0, 0.0, []
        for v in rec["vendors"]:
            for r in fetch_vouchers(v):
                if r.get("character") not in EXP_CHARS:
                    continue
                fy = int(r["fiscal_year"]); amt = float(r["vouchers_paid"])
                ts = date.fromisoformat(r["data_as_of"][:10])
                if fy >= 2018:
                    after = ts > pdate
                    between = rdate < ts <= pdate
                else:
                    after = date(fy - 1, 7, 1) > pdate
                    between = False
                if after:
                    after_post += amt
                    if fy <= LAST_FULL_FY:
                        after_post_full += amt
                    lines.append({"fy": fy, "date": r["data_as_of"][:10] if fy >= 2018 else None, "dept": r.get("department_code"),
                                  "contract_title": r.get("contract_title"), "amt": amt})
                elif between:
                    before_post_after_rev += amt
        rec.update({"status": "revoked_not_reinstated",
                    "paid_after_posting": round(after_post, 2), "paid_after_posting_fy_le_2026": round(after_post_full, 2),
                    "paid_between_revocation_and_posting": round(before_post_after_rev, 2),
                    "first_payment_after_posting": (lambda l: (l["date"] or f"FY{l['fy']}") if l else None)(min(lines, key=lambda l: (l["fy"], l["date"] or ""), default=None)),
                    "last_payment_after_posting": (lambda l: (l["date"] or f"FY{l['fy']}") if l else None)(max(lines, key=lambda l: (l["fy"], l["date"] or ""), default=None)),
                    "fiscal_years_after_posting": sorted({l["fy"] for l in lines}),
                    "depts_after_posting": sorted({l["dept"] for l in lines if l["dept"]}),
                    "contract_titles_after_posting": sorted({l["contract_title"] for l in lines if l["contract_title"]})[:6],
                    "n_voucher_lines_after_posting": len(lines),
                    "last_990_on_file": None})
        pp = os.path.join(BASE, "cache", "propublica", f"{ein}.json")
        if os.path.exists(pp):
            j = json.load(open(pp))
            prds = [str(x.get("tax_prd")) for x in j.get("filings_with_data", [])]
            rec["last_990_on_file"] = max(prds) if prds else None
        rec["publishable"] = bool(rec["match_confidence"] >= MIN_CONFIDENCE and rec["paid_after_posting"] > 0)
        rec["exclusion_reason"] = (None if rec["publishable"] else
                                   (f"match confidence {rec['match_confidence']:.2f}, below the 0.9 needed to name an organization" if rec["match_confidence"] < MIN_CONFIDENCE
                                    else "no payment dated after the IRS posted the revocation"))
        out.append(rec)
    pub = [r for r in out if r.get("publishable")]
    summary = {"candidates_revoked_with_later_fy_payments": len(out),
               "pipeline_def_count_not_in_bmf": sum(1 for r in out if r["status"] == "revoked_not_reinstated" and r["paid_after_revocation_fy_pipeline_def"] > 0),
               "pipeline_def_amount_not_in_bmf": round(sum(r["paid_after_revocation_fy_pipeline_def"] for r in out if r["status"] == "revoked_not_reinstated"), 2),
               "publishable_count": len(pub),
               "publishable_amount_after_posting": round(sum(r["paid_after_posting"] for r in pub), 2),
               "publishable_amount_after_posting_fy_le_2026": round(sum(r["paid_after_posting_fy_le_2026"] for r in pub), 2),
               "largest_share": (max(r["paid_after_posting"] for r in pub) / sum(r["paid_after_posting"] for r in pub)) if pub else None}
    res = {"summary": summary, "orgs": out}
    json.dump(res, open(os.path.join(OUT, "parts", "revocations.json"), "w"), indent=1)
    return res


def main():
    res = compute()
    out = res["orgs"]
    print(json.dumps(res["summary"], indent=1))
    for r in out:
        print(r["ein"], r["irs_name"], r["status"], r["match_confidence"], r["paid_after_revocation_fy_pipeline_def"],
              r.get("paid_after_posting"), r.get("first_payment_after_posting"), r.get("last_payment_after_posting"), r.get("exclusion_reason"))


if __name__ == "__main__":
    main()
