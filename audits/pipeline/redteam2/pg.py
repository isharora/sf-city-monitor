"""Print PDF page text: python3 pg.py DOC PAGE [grep]"""
import json, os, sys, re
T = os.path.join(os.path.dirname(__file__), "..", "..", "data", "text")
d, p = sys.argv[1], int(sys.argv[2])
t = json.load(open(os.path.join(T, d + ".json")))["pages"]
s = t[p - 1] if isinstance(t, list) else t[str(p)]
if len(sys.argv) > 3:
    for m in re.finditer(sys.argv[3], s, re.I):
        print("...", s[max(0, m.start() - 700): m.end() + 700].replace("\n", " "), "...\n")
else:
    print(s)
