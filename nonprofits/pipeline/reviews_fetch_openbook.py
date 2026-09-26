"""Download Controller reports from OpenBook (openbook.sfgov.org/webreports/details3.aspx?id=N).
The page requires an ASP.NET postback on the 'Continue' button. Usage: python3 reviews_fetch_openbook.py ID:filename ..."""
import sys, re, html, subprocess, pathlib, urllib.parse
out = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews" / "pdfs"
def curl(args, timeout=90):
    return subprocess.run(["perl", "-e", f"alarm {timeout}; exec @ARGV", "curl", "-sL", "-A", "Mozilla/5.0"] + args, capture_output=True)
for spec in sys.argv[1:]:
    rid, name = spec.split(":")
    url = f"https://openbook.sfgov.org/webreports/details3.aspx?id={rid}"
    jar = f"/tmp/ob_{rid}.jar"
    page = curl(["-c", jar, url]).stdout.decode("utf-8", "ignore")
    fields = {}
    for n in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % n, page)
        if m: fields[n] = html.unescape(m.group(1))
    fields["ctl00$ContentPlaceHolder1$btnGo"] = "Continue"
    data = urllib.parse.urlencode(fields)
    dst = out / name
    r = curl(["-b", jar, "-o", str(dst), "-w", "%{http_code} %{content_type} %{url_effective}", "--data", data, url], 120)
    print(rid, name, r.stdout.decode())
