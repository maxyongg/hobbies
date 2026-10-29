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


def card_html(html, base, pattern, n=3, limit=2500):
    """Print the smallest ancestor of each of the first n matching links that holds only that link."""
    soup = BeautifulSoup(html, "lxml")
    shown = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if not re.search(pattern, urlparse(href).path) or href in shown:
            continue
        shown.add(href)
        node = a
        for parent in a.parents:
            hrefs = {urljoin(base, x["href"]) for x in parent.find_all("a", href=True)
                     if re.search(pattern, urlparse(urljoin(base, x["href"])).path)}
            if len(hrefs) > 1:
                break
            node = parent
        print(f"  --- card for {href}:")
        print(str(node)[:limit])
        if len(shown) >= n:
            break


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
    r = get(base + "/films")
    if r is not None and r.ok:
        card_html(r.text, base, r"^/film/\d+/")
        for m in sorted(set(re.findall(r"admin-ajax[^\"' ]*|ajax_?url[^,]{0,120}|wp-json/[a-z0-9_-]+/v\d[^\"' ]*", r.text)))[:20]:
            print("    ref:", m)
        first = re.search(r"https?://filmhouse\.sg/film/\d+/[^\"'# ]+", r.text)
        if first:
            d = get(first.group(0).replace("http://", "https://"))
            if d is not None and d.ok:
                soup = BeautifulSoup(d.text, "lxml")
                print("  title:", soup.title.string if soup.title else None)
                for prop in ("og:title", "og:image", "og:description"):
                    tag = soup.find("meta", property=prop)
                    print(f"  {prop}:", tag.get("content") if tag else None)
                print("  h1/h2:", [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])][:8])
                for js in soup.find_all("script", type="application/ld+json")[:3]:
                    print("  ld+json:", (js.string or "")[:1500])
    r = get(base + "/films/coming-soon/")
    if r is not None and r.ok:
        card_html(r.text, base, r"^/film/\d+/", n=1)


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
    base = "https://shaw.sg"
    print("== SHAW")
    r = get(base + "/internal/get_now_showing_movies", headers={"Referer": base + "/movie"})
    if r is not None and r.ok:
        movies = r.json()
        keys = sorted({k for m in movies for k in m})
        print(f"  {len(movies)} movies; keys: {keys}")
        for m in [m for m in movies if m.get("movieReleaseId")][:3]:
            print("   full:", json.dumps({k: v for k, v in m.items() if k != "synopsisShort"}, ensure_ascii=False))
        for m in movies:
            flags = [k for k, v in m.items() if k.startswith("is") and v]
            print(f"   - {m.get('movieReleaseId')} | {m.get('code')} | {m.get('primaryTitle')} | {m.get('releaseDate')} | {flags}")
    for name in ["get_coming_soon_movies", "get_advance_sales_movies", "get_ending_soon_movies",
                 "get_top_movies", "get_all_movies", "get_movies"]:
        r = get(f"{base}/internal/{name}", headers={"Referer": base + "/movie"})
        if r is not None and r.ok and "json" in r.headers.get("content-type", ""):
            data = r.json()
            print(f"    {name}: {len(data) if isinstance(data, list) else type(data).__name__}", str(data)[:300])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed; skipping rendered probe")
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(user_agent=UA)
        calls = []
        page.on("request", lambda req: "/internal/" in req.url and calls.append(req.url))
        page.goto(base + "/movie", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(3000)
        print("  internal calls on load:", calls)
        card_html(page.content(), base, r"^/movie-details/\d+", n=3, limit=3000)
        for tab in ["Now Showing", "New Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon"]:
            before = len(calls)
            try:
                page.get_by_text(tab, exact=True).first.click(timeout=5000)
                page.wait_for_timeout(3000)
            except Exception as e:  # noqa: BLE001
                print(f"  tab {tab!r}: {type(e).__name__}")
                continue
            ids = sorted(set(re.findall(r"/movie-details/(\d+)", page.content())))
            print(f"  tab {tab!r}: url={page.url} new internal calls={calls[before:]} movie ids={len(ids)}")
            if tab == "Coming Soon":
                card_html(page.content(), base, r"^/movie-details/\d+", n=2, limit=3000)
        b.close()


if __name__ == "__main__":
    wanted = sys.argv[1:] or ["filmhouse", "shaw"]
    for name in wanted:
        globals()[name]()
