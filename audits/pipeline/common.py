"""Shared helpers: polite HTTP with disk cache, paths."""
import hashlib
import os
import time
import threading

import requests
import warnings
warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
PDFS = os.path.join(DATA, "pdfs")
TEXT = os.path.join(DATA, "text")
SITE = os.path.join(DATA, "site")
HTML_CACHE = os.path.join(DATA, "cache", "html")
for d in (RAW, PDFS, TEXT, SITE, HTML_CACHE):
    os.makedirs(d, exist_ok=True)

UA = "Mozilla/5.0 (compatible; SF-City-Monitor research bot; audit recommendations tracker)"
_session = requests.Session()
_session.headers.update({"User-Agent": UA})
_last = {}
_lock = threading.Lock()
MIN_INTERVAL = 1.0  # seconds between requests to the same host


def _host(url):
    return url.split("/")[2] if "//" in url else ""


def polite_wait(url):
    h = _host(url)
    with _lock:
        now = time.time()
        wait = _last.get(h, 0) + MIN_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        _last[h] = time.time()


def get(url, cache=True, timeout=90, binary=False, method="GET", data=None, retries=3):
    """Polite GET/POST with disk cache. Returns text (or bytes)."""
    key = hashlib.sha256((method + url + repr(sorted((data or {}).items()))).encode()).hexdigest()
    path = os.path.join(HTML_CACHE, key[:2], key)
    if cache and os.path.exists(path):
        with open(path, "rb") as f:
            b = f.read()
        return b if binary else b.decode("utf-8", errors="replace")
    last = None
    for i in range(retries):
        polite_wait(url)
        try:
            if method == "POST":
                r = _session.post(url, data=data, timeout=timeout)
            else:
                r = _session.get(url, timeout=timeout)
            if r.status_code == 200:
                b = r.content
                if cache:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(b)
                return b if binary else b.decode("utf-8", errors="replace")
            last = f"HTTP {r.status_code}"
            if r.status_code in (404, 403, 410):
                break
        except Exception as e:  # network errors
            last = repr(e)
        time.sleep(5 * (i + 1))
    raise IOError(f"GET failed {url}: {last}")


def session():
    return _session
