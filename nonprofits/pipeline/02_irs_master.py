"""Build a master list of IRS exempt organizations for matching.

Sources (downloaded by 00_download_irs.sh):
  - EO BMF regional files eo1-eo4.csv + eo_ca.csv (current exempt orgs)
  - Auto-revocation list data-download-revocation.txt (pipe-delimited, no header)
  - 990 e-file index files 2017-2026 (EIN + taxpayer name per return; captures names
    of orgs that filed electronically, including past names)
Output: data/interim/irs_orgs.parquet (one row per EIN, current BMF info)
        data/interim/irs_names.parquet (EIN, name variant, source) for candidate search
"""
import glob, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from lib_names import norm

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "irs")
INT = os.path.join(os.path.dirname(__file__), "..", "data", "interim")
os.makedirs(INT, exist_ok=True)

bmf = pd.concat([pd.read_csv(f, dtype=str) for f in
                 [os.path.join(RAW, x) for x in ["eo1.csv", "eo2.csv", "eo3.csv", "eo4.csv", "eo_ca.csv"]]])
bmf = bmf.drop_duplicates("EIN")
bmf["in_bmf"] = True
print("BMF orgs", len(bmf), "CA", (bmf.STATE == "CA").sum())

rev = pd.read_csv(os.path.join(RAW, "data-download-revocation.txt"), sep="|", header=None, dtype=str,
                  names=["EIN", "NAME", "DBA", "STREET", "CITY", "STATE", "ZIP", "COUNTRY", "SUBSECTION",
                         "REVOCATION_DATE", "POSTING_DATE", "REINSTATEMENT_DATE"], quoting=3)
rev = rev.apply(lambda c: c.str.strip())
rev = rev.dropna(subset=["EIN"]).drop_duplicates("EIN", keep="last")
print("revocations", len(rev), "CA", (rev.STATE == "CA").sum())

names = [bmf[["EIN", "NAME"]].assign(src="bmf"),
         bmf[bmf.SORT_NAME.notna()][["EIN", "SORT_NAME"]].rename(columns={"SORT_NAME": "NAME"}).assign(src="bmf_sort"),
         rev[["EIN", "NAME"]].assign(src="revoked"),
         rev[rev.DBA.notna()][["EIN", "DBA"]].rename(columns={"DBA": "NAME"}).assign(src="revoked_dba")]
efi = []
for f in sorted(glob.glob(os.path.join(RAW, "efile", "index_*.csv"))):
    d = pd.read_csv(f, dtype=str, usecols=["EIN", "TAX_PERIOD", "TAXPAYER_NAME", "RETURN_TYPE", "OBJECT_ID"],
                    on_bad_lines="skip")
    d["index_year"] = os.path.basename(f)[6:10]
    efi.append(d)
efi = pd.concat(efi)
efi["EIN"] = efi.EIN.str.zfill(9)
efi.to_parquet(os.path.join(INT, "efile_index_all.parquet"))
print("efile returns", len(efi))
names.append(efi[["EIN", "TAXPAYER_NAME"]].rename(columns={"TAXPAYER_NAME": "NAME"}).drop_duplicates().assign(src="efile"))
names = pd.concat(names).dropna(subset=["NAME"])
names["EIN"] = names.EIN.str.zfill(9)
names["norm"] = names.NAME.map(norm)
names = names[names.norm != ""].drop_duplicates(["EIN", "norm"])
names.to_parquet(os.path.join(INT, "irs_names.parquet"))
print("name variants", len(names))

# one row per EIN
last_efile = efi.groupby("EIN").agg(last_tax_period=("TAX_PERIOD", "max"), n_efile_returns=("OBJECT_ID", "count"),
                                     efile_name=("TAXPAYER_NAME", "last"))
orgs = bmf.set_index("EIN")
rev_i = rev.set_index("EIN")
all_eins = sorted(set(orgs.index) | set(rev_i.index) | set(last_efile.index))
o = pd.DataFrame(index=pd.Index(all_eins, name="EIN"))
for c in ["NAME", "ICO", "STREET", "CITY", "STATE", "ZIP", "SUBSECTION", "CLASSIFICATION", "RULING", "FOUNDATION",
          "STATUS", "TAX_PERIOD", "ASSET_AMT", "INCOME_AMT", "REVENUE_AMT", "NTEE_CD", "FILING_REQ_CD", "in_bmf"]:
    o[c] = orgs[c]
o["in_bmf"] = o.in_bmf.fillna(False).astype(bool)
for c in ["NAME", "STREET", "CITY", "STATE", "ZIP", "SUBSECTION"]:
    o[c] = o[c].fillna(rev_i[c])
o["revocation_date"] = rev_i.REVOCATION_DATE
o["reinstatement_date"] = rev_i.REINSTATEMENT_DATE
o = o.join(last_efile)
o["NAME"] = o.NAME.fillna(o.efile_name)
o.reset_index().to_parquet(os.path.join(INT, "irs_orgs.parquet"))
print("orgs", len(o))
