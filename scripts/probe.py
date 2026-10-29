"""Print what each cinema site exposes, to pick (or re-pick) a scraping path.

Run where the sites are reachable (GitHub Actions, or locally):
    python scripts/probe.py [filmhouse|afa|shaw ...]
Shaw needs `pip install playwright && playwright install chromium`.
"""

import json
import re
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "whats-on-sg/0.1 (+https://github.com/maxyongg/hobbies; personal new-film alerts)"
S = requests.Session()
S.headers["User-Agent"] = UA


def get(url, **kw):
    try:
        r = S.get(url, timeout=30, **kw)
    except Exception as e:  # noqa: BLE001
        print(f"  GET {url} -> ERROR {e!r}")
        return None
    print(f"  GET {url} -> {r.status_code} {r.headers.get('content-type')} {len(r.content)}B")
    return r


def anchors(html, base, pattern=None):
    soup = BeautifulSoup(html, "lxml")
    seen = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if urlparse(href).netloc != urlparse(base).netloc:
            continue
        if pattern and not re.search(pattern, href):
            continue
        seen.setdefault(href, " ".join(a.get_text(" ", strip=True).split())[:80])
    return seen


def wp(base, guesses):
    r = get(base + "/wp-json/")
    if r is not None and r.ok:
        try:
            routes = r.json().get("routes", {})
            print("  routes of interest:")
            for k in routes:
                if re.search(r"film|movie|event|mep|show|session|jacro", k, re.I):
                    print("   ", k)
        except ValueError:
            print("  /wp-json/ not JSON")
    r = get(base + "/wp-json/wp/v2/types")
    if r is not None and r.ok:
        for k, v in r.json().items():
            print(f"    type {k!r} rest_base={v.get('rest_base')!r} name={v.get('name')!r}")
    for rb in guesses:
        r = get(f"{base}/wp-json/wp/v2/{rb}", params={"per_page": 20, "_embed": "wp:featuredmedia,wp:term"})
        if r is None or not r.ok:
            continue
        print("    X-WP-Total:", r.headers.get("X-WP-Total"), "pages:", r.headers.get("X-WP-TotalPages"))
        data = r.json()
        if data:
            first = data[0]
            print("    keys:", sorted(first.keys()))
            print("    first (trimmed):", json.dumps({k: first[k] for k in first if k not in ("content", "_links", "yoast_head", "_embedded")}, ensure_ascii=False)[:1500])
            emb = first.get("_embedded", {})
            for t in emb.get("wp:term", []) or []:
                print("    terms:", [(x.get("taxonomy"), x.get("name")) for x in t][:10])
            fm = emb.get("wp:featuredmedia") or []
            if fm:
                print("    featured:", fm[0].get("source_url"))
        for p in data:
            print(f"    - {p.get('date')} {p.get('slug')} | {p.get('title', {}).get('rendered')} | {p.get('link')}")


def filmhouse():
    base = "https://filmhouse.sg"
    print("== FILMHOUSE")
    wp(base, ["film", "films", "movie", "movies", "event", "events"])
    for path in ["/films", "/films/coming-soon/", "/seasons-events/ls/"]:
        r = get(base + path)
        if r is not None and r.ok:
            links = anchors(r.text, base)
            print(f"  anchors on {path}: {len(links)}")
            for h, t in links.items():
                print(f"    {h} | {t}")
            for m in sorted(set(re.findall(r"https?://[^\"' ]*(?:api|json|jacro|tapos)[^\"' ]*", r.text)))[:40]:
                print("    ref:", m)
            if path == "/films":
                soup = BeautifulSoup(r.text, "lxml")
                print("  /films sample HTML:")
                body = soup.find("main") or soup.body
                print(str(body)[:6000] if body else "")
    r = get(base + "/feed/")
    if r is not None and r.ok:
        print(r.text[:1500])


def afa():
    base = "https://asianfilmarchive.org"
    print("== AFA")
    wp(base, ["mep_events", "mep_event", "events"])
    r = get(base + "/wp-json/wp/v2/mep_cat", params={"per_page": 100})
    if r is not None and r.ok:
        print("   mep_cat:", [(c.get("id"), c.get("slug"), c.get("count")) for c in r.json()])
    for path in ["/whatson/", "/events-calendar/"]:
        r = get(base + path)
        if r is not None and r.ok:
            links = anchors(r.text, base)
            print(f"  anchors on {path}: {len(links)}")
            for h, t in links.items():
                print(f"    {h} | {t}")
    r = get(base + "/feed/", params={"post_type": "mep_events"})
    if r is not None and r.ok:
        print(r.text[:2500])


def shaw():
    base = "https://www.shaw.sg"
    print("== SHAW")
    r = get(base + "/movie")
    if r is not None:
        print("  scripts:", re.findall(r"<script[^>]+src=\"([^\"]+)\"", r.text)[:30])
        for m in sorted(set(re.findall(r"[\"'](/?[^\"' ]*(?:api|Api|API|json)[^\"' ]*)[\"']", r.text)))[:60]:
            print("    ref:", m)
        print(r.text[:3000])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed; skipping rendered probe")
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(user_agent=UA)
        seen = []

        def on_response(resp):
            ct = resp.headers.get("content-type", "")
            if resp.request.resource_type in ("xhr", "fetch") or "json" in ct:
                try:
                    body = resp.text()
                except Exception:  # noqa: BLE001
                    body = ""
                seen.append((resp.request.method, resp.url, resp.status, ct, body))

        page.on("response", on_response)
        page.goto(base + "/movie", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(5000)
        print(f"  XHR/JSON responses: {len(seen)}")
        for method, url, status, ct, body in seen:
            print(f"   {method} {url} -> {status} {ct} {len(body)}B")
            print("     ", body[:1500].replace("\n", " "))
        links = anchors(page.content(), base)
        print(f"  rendered anchors: {len(links)}")
        for h, t in links.items():
            print(f"    {h} | {t}")
        b.close()


if __name__ == "__main__":
    wanted = sys.argv[1:] or ["filmhouse", "afa", "shaw"]
    for name in wanted:
        globals()[name]()
