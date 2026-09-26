"""Fetch Form 990 data for matched EINs.

1. ProPublica Nonprofit Explorer API (organizations/<EIN>.json): IRS SOI extract financials by tax
   year (1 request/sec, cached in data/cache/propublica/).
2. IRS 990 e-file XML (TEOS releases 2017-2026): locate each EIN's returns in the index files,
   map OBJECT_ID -> zip file (index XML_BATCH_ID for 2024+, central-directory listing for older
   zips), extract only those members over HTTP Range requests, parse with lib_990.
   Parsed returns cached as data/cache/990/<OBJECT_ID>.json.

Usage: python3 07_fetch_990.py [propublica|xml|all]
"""
import glob, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests
sys.path.insert(0, os.path.dirname(__file__))
from lib_remotezip import open_remote_zip, read_member
from lib_990 import parse_990

BASE = os.path.join(os.path.dirname(__file__), "..", "data")
INT = os.path.join(BASE, "interim")
RAW = os.path.join(BASE, "raw", "irs", "efile")
PPC = os.path.join(BASE, "cache", "propublica")
X990 = os.path.join(BASE, "cache", "990")
for d in (PPC, X990):
    os.makedirs(d, exist_ok=True)


def target_eins():
    m = pd.read_parquet(os.path.join(INT, "matches_final.parquet")) if os.path.exists(os.path.join(INT, "matches_final.parquet")) \
        else pd.read_parquet(os.path.join(INT, "matches.parquet"))
    eins = set(m[m.matched_ein != "NONE"].matched_ein)
    ov = os.path.join(BASE, "manual", "match_overrides.csv")
    if os.path.exists(ov):
        eins |= {e for e in pd.read_csv(ov, dtype=str).ein if e != "NONE"}
    return sorted(eins)


def fetch_propublica(eins):
    s = requests.Session()
    s.headers["User-Agent"] = "sf-city-monitor research (nonprofit spending analysis)"
    for i, ein in enumerate(eins):
        path = os.path.join(PPC, f"{ein}.json")
        if os.path.exists(path):
            continue
        for attempt in range(4):
            try:
                r = s.get(f"https://projects.propublica.org/nonprofits/api/v2/organizations/{int(ein)}.json", timeout=60)
                if r.status_code == 404:
                    json.dump({"not_found": True}, open(path, "w"))
                    break
                if r.status_code == 429:
                    time.sleep(30 * (attempt + 1))
                    continue
                r.raise_for_status()
                json.dump(r.json(), open(path, "w"))
                break
            except Exception as e:  # noqa
                time.sleep(5 * (attempt + 1))
        time.sleep(1.0)
        if i % 100 == 0:
            print("propublica", i, len(eins), flush=True)


def zip_urls():
    return [u.strip() for u in open(os.path.join(RAW, "zip_list.txt")) if u.strip()]


def zip_member_map(years):
    """OBJECT_ID -> (zip_url, member_name) for zips of given index years (cached)."""
    out = {}
    for u in zip_urls():
        y = u.split("/")[-2]
        if y not in years:
            continue
        cache = os.path.join(RAW, "listing_" + os.path.basename(u) + ".txt")
        if not os.path.exists(cache):
            try:
                z = open_remote_zip(u)
                names = z.namelist()
            except Exception as e:  # noqa
                print("listing failed", u, e)
                continue
            with open(cache, "w") as f:
                f.write("\n".join(names))
            print("listed", u, len(names), flush=True)
        for n in open(cache).read().split("\n"):
            b = os.path.basename(n)
            if b.endswith(".xml"):
                out[b.split("_")[0]] = (u, n)
    return out


def fetch_xml(eins):
    idx = []
    for f in sorted(glob.glob(os.path.join(RAW, "index_*.csv"))):
        d = pd.read_csv(f, dtype=str, on_bad_lines="skip")
        d["index_year"] = os.path.basename(f)[6:10]
        d["EIN"] = d.EIN.str.zfill(9)
        d = d[d.EIN.isin(set(eins)) & d.RETURN_TYPE.isin(["990", "990EZ"])]
        idx.append(d)
    idx = pd.concat(idx)
    idx = idx.drop_duplicates("OBJECT_ID")
    print("returns to fetch", len(idx), "for", idx.EIN.nunique(), "EINs")
    todo = idx[~idx.OBJECT_ID.map(lambda o: os.path.exists(os.path.join(X990, f"{o}.json")))]
    member = zip_member_map(set(todo.index_year))
    jobs = {}
    missing = 0
    for _, r in todo.iterrows():
        loc = member.get(r.OBJECT_ID)
        if loc is None:
            missing += 1
            continue
        jobs.setdefault(loc[0], []).append((r.OBJECT_ID, loc[1], r.EIN))
    print("to extract", sum(len(v) for v in jobs.values()), "in", len(jobs), "zips; not located", missing)

    def work(url):
        items = jobs[url]
        z = open_remote_zip(url)
        n_ok = 0
        for oid, name, ein in items:
            try:
                data = read_member(z, name)
                parsed = parse_990(data)
                parsed["object_id"] = oid
                parsed["zip"] = os.path.basename(url)
                json.dump(parsed, open(os.path.join(X990, f"{oid}.json"), "w"))
                n_ok += 1
            except Exception as e:  # noqa
                print("fail", oid, e, flush=True)
        print("done zip", os.path.basename(url), n_ok, "/", len(items), flush=True)

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(work, list(jobs)))
    idx.to_parquet(os.path.join(INT, "efile_returns_matched.parquet"))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    eins = target_eins()
    print("EINs", len(eins))
    if what in ("propublica", "all"):
        fetch_propublica(eins)
    if what in ("xml", "all"):
        fetch_xml(eins)
