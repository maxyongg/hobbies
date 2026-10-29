"""Print what each cinema site exposes, to pick (or re-pick) a scraping path.

Run where the sites are reachable (GitHub Actions, or locally):
    python scripts/probe.py filmhouse shaw afa afa_dates gv carnival discover
`discover` looks at candidate sites (CANDIDATES) for a new source. Rendered probes need
`pip install playwright && playwright install chromium`.
"""

import json
import re
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

UA = "cinema/0.1 (+https://github.com/maxyongg/hobbies; personal new-film alerts)"
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
    r = get(base + "/wp-json/wp/v2/mep_events",
            params={"per_page": 5, "_fields": "id,slug,link,title,date,class_list,yoast_head_json"})
    if r is not None:
        print("   ", " ".join(r.text[:600].split()))
    for path in ["/whatson/", "/events-calendar/"]:
        r = get(base + path)
        if r is not None:
            print(f"    event links on {path}:", len(anchors(r.text, base, r"/event-calendar/")))
            if not r.ok or "event-calendar" not in r.text:
                print("   ", " ".join(r.text[:600].split()))


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


CANDIDATES = {
    "gv": ["https://www.gv.com.sg/", "https://www.gv.com.sg/GVMovies"],
    "carnival": ["https://carnivalcinemas.sg/", "https://www.carnivalcinemas.sg/"],
    "sfs": ["https://www.singaporefilmsociety.com/", "https://singaporefilmsociety.com/"],
    "alliance": ["https://www.alliancefrancaise.org.sg/"],
    "objectifs": ["https://www.objectifs.com.sg/"],
    "sgiff": ["https://www.sgiff.com/"],
}
NOISE = re.compile(r"google|facebook|doubleclick|hotjar|clarity|tiktok|freshworks|gstatic|youtube|cookie|onetrust|sentry", re.I)


def discover():
    """First look at candidate cinema sites: platform, links, and JSON calls when rendered."""
    for key, urls in CANDIDATES.items():
        print(f"== DISCOVER {key}")
        for url in urls:
            r = get(url)
            if r is None or not r.ok:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            gen = soup.find("meta", attrs={"name": "generator"})
            print("  final:", r.url, "| title:", soup.title.string.strip() if soup.title and soup.title.string else None,
                  "| generator:", gen.get("content") if gen else None)
            origin = f"{urlparse(r.url).scheme}://{urlparse(r.url).netloc}"
            t = get(origin + "/wp-json/wp/v2/types")
            if t is not None and t.ok and "json" in t.headers.get("content-type", ""):
                print("  wp types:", [(k, v.get("rest_base")) for k, v in t.json().items()])
            links = anchors(r.text, r.url)
            print(f"  anchors: {len(links)}")
            for h, txt in list(links.items())[:120]:
                print(f"    {h} | {txt}")
            for m in sorted(set(re.findall(r"[\"'](/?[^\"' <>]*(?:api|Api|API|json|graphql)[^\"' <>]*)[\"']", r.text)))[:30]:
                print("    ref:", m[:200])
            break
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        for key in ("gv", "carnival", "sfs"):
            page = b.new_page(user_agent=UA)
            seen = []

            def on_response(resp, seen=seen):
                ct = resp.headers.get("content-type", "")
                if ("json" in ct or resp.request.resource_type in ("xhr", "fetch")) and not NOISE.search(resp.url):
                    try:
                        body = resp.text()
                    except Exception:  # noqa: BLE001
                        body = ""
                    seen.append((resp.request.method, resp.url, resp.status, body))

            page.on("response", on_response)
            url = CANDIDATES[key][-1] if key == "gv" else CANDIDATES[key][0]
            print(f"== RENDER {key} {url}")
            try:
                page.goto(url, wait_until="load", timeout=60000)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(3000)
            except Exception as e:  # noqa: BLE001
                print("  error:", type(e).__name__, e)
                continue
            print("  url:", page.url)
            for method, u, status, body in seen[:40]:
                print(f"   {method} {u[:200]} -> {status} {len(body)}B")
                print("     ", " ".join(body[:400].split()))
            links = anchors(page.content(), page.url)
            print(f"  rendered anchors: {len(links)}")
            for h, txt in list(links.items())[:150]:
                print(f"    {h} | {txt}")
            page.close()
        b.close()


def gv():
    base = "https://www.gv.com.sg"
    print("== GV API (plain requests)")
    get(base + "/GVMovies")  # same session: pick up any cookies a browser would have
    for name in ["nowshowing", "comingsoon", "advancesales"]:
        try:
            r = S.post(f"{base}/.gv-api/{name}", json={}, timeout=30, headers={
                "Accept": "application/json, text/plain, */*", "Origin": base, "Referer": base + "/GVMovies"})
        except Exception as e:  # noqa: BLE001
            print(f"  POST {name} -> ERROR {e!r}")
            continue
        print(f"  POST {name} -> {r.status_code} {r.headers.get('content-type')} {len(r.content)}B")
        print("   ", " ".join(r.text[:1200].split()))


def carnival():
    base = "https://carnivalcinemas.sg"
    print("== CARNIVAL")
    r = get(base + "/")
    if r is not None:
        print(r.text[:2100])
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(user_agent=UA)
        seen = []
        page.on("response", lambda resp: seen.append(resp) if (
            "json" in resp.headers.get("content-type", "") or resp.request.resource_type in ("xhr", "fetch"))
            and not NOISE.search(resp.url) else None)
        try:
            page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:  # noqa: BLE001
            print("  goto:", type(e).__name__)
        page.wait_for_timeout(15000)
        print("  url:", page.url)
        for resp in seen[:40]:
            try:
                body = resp.text()
            except Exception:  # noqa: BLE001
                body = ""
            print(f"   {resp.request.method} {resp.url[:200]} -> {resp.status} {len(body)}B")
            print("     ", " ".join(body[:700].split()))
        links = anchors(page.content(), page.url)
        print(f"  rendered anchors: {len(links)}")
        for h, txt in list(links.items())[:80]:
            print(f"    {h} | {txt}")
        print("  text:", " ".join(page.inner_text("body")[:1500].split()))
        b.close()


def afa_dates():
    base = "https://asianfilmarchive.org"
    print("== AFA DATES")
    r = get(base + "/wp-json/wp/v2/mep_events", params={"per_page": 3, "_fields": "id,slug,event_informations"})
    if r is None or not r.ok:
        return
    for ev in r.json():
        info = ev.get("event_informations") or {}
        print("  ", ev["slug"], "keys:", sorted(info)[:80])
        for k, v in info.items():
            if re.search(r"date|time|start|end", k, re.I):
                print(f"     {k} = {str(v)[:200]}")


if __name__ == "__main__":
    names = ["filmhouse", "shaw", "afa", "afa_dates", "gv", "carnival", "discover"]
    wanted = sys.argv[1:]
    if not wanted:
        # CI runs this with no arguments. While debugging a source on a branch, default `wanted` to its probe.
        print("usage: probe.py " + " | ".join(names) + "  (set a default list here while debugging)")
    for name in wanted:
        globals()[name]()
