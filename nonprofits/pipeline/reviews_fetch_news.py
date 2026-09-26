"""Fetch news articles, extract title/date/paragraph text into data/reviews/news_cache/<key>.txt.
Usage: python3 reviews_fetch_news.py key=URL ...   (skips keys already cached)"""
import sys, re, html, subprocess, pathlib, json
cache = pathlib.Path(__file__).resolve().parents[1] / "data" / "reviews" / "news_cache"
cache.mkdir(parents=True, exist_ok=True)
def get(url):
    r = subprocess.run(["perl", "-e", "alarm 60; exec @ARGV", "curl", "-sL", "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", url], capture_output=True)
    return r.stdout.decode("utf-8", "ignore")
def meta(s, prop):
    m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), s) or \
        re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % re.escape(prop), s)
    return html.unescape(m.group(1)) if m else ""
for spec in sys.argv[1:]:
    key, url = spec.split("=", 1)
    dst = cache / f"{key}.txt"
    if dst.exists() and dst.stat().st_size > 500:
        print("cached", key); continue
    s = get(url)
    title = meta(s, "og:title") or (re.search(r"<title>(.*?)</title>", s, re.S) or [None, ""])[1]
    date = meta(s, "article:published_time") or meta(s, "datePublished")
    if not date:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', s); date = m.group(1) if m else ""
    author = meta(s, "author")
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", s, flags=re.S)
    paras = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    paras = [re.sub(r"\s+", " ", p) for p in paras if len(p) > 40]
    dst.write_text(f"URL: {url}\nTITLE: {html.unescape(title).strip()}\nDATE: {date}\nAUTHOR: {author}\n\n" + "\n\n".join(paras))
    print(key, len(paras), "paras |", date[:10], "|", html.unescape(title)[:90])
