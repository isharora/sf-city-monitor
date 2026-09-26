"""Probe candidate datasets: name, row count, columns and field descriptions. Writes data/raw/probe.json"""
import json, subprocess, sys, urllib.parse
IDS = sys.argv[1:]
def get(url, t=60):
    out = subprocess.run(["perl","-e",f"alarm {t}; exec @ARGV","curl","-s",url],capture_output=True,text=True).stdout
    return json.loads(out)
res = {}
try: res = json.load(open('../data/raw/probe.json'))
except Exception: pass
for i in IDS:
    try:
        m = get(f"https://data.sf.gov/api/views/{i}.json")
        cnt = get(f"https://data.sf.gov/resource/{i}.json?$select=count(*)")
        cols = [(c['fieldName'], c.get('dataTypeName'), (c.get('description') or '')[:200]) for c in m.get('columns',[]) if not c['fieldName'].startswith(':')]
        res[i] = dict(name=m.get('name'), rows=cnt, desc=(m.get('description') or '')[:3000], cols=cols, updated=m.get('rowsUpdatedAt'))
        print(i, m.get('name'), cnt)
    except Exception as e:
        print(i, 'ERR', e)
json.dump(res, open('../data/raw/probe.json','w'), indent=1)
