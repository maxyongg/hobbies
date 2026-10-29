"""Print what a URL returns, from somewhere that can reach it (GitHub Actions).

Claude cloud sessions can't reach the cinema sites, so this is how a session
sees live responses: list URLs in scripts/probe-urls.txt (or pass them as
args / the workflow_dispatch input), push, and read the `probe` job log.

Line format in probe-urls.txt:  [deep] <url>     (# comments allowed)
`deep` also fetches the page's scripts and greps them for API-looking URLs.
Stdlib only, so the workflow needs no install step.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

UA = "hobbies/0.1 (+https://github.com/maxyongg/hobbies; personal new-film alerts)"
MAX_LINKS = 250
API_RE = re.compile(r"""["'`]((?:https?:)?//[^"'`\s]*?(?:api|graphql|json)[^"'`\s]*|/[^"'`\s]*?(?:api|graphql)/[^"'`\s]*)["'`]""", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.geturl(), dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, url, dict(e.headers), e.read()


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.scripts, self.title, self._a, self._in_title = [], [], "", None, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a = [a["href"], ""]
        elif tag == "img" and self._a is not None and not self._a[1].strip():
            self._a[1] = "[img] " + (a.get("alt") or "")
        elif tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append(tuple(self._a))
            self._a = None
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._a is not None:
            self._a[1] += data
        if self._in_title:
            self.title += data


def show_json(data):
    if isinstance(data, dict) and "routes" in data:
        print("namespaces:", data.get("namespaces"))
        for route in data["routes"]:
            if not re.match(r"^/wp/v2/(posts|pages|media|users|comments|tags|categories|settings|themes|plugins|block|templates|template-parts|global-styles|navigation|menu|sidebars|widget|font|pattern|search|statuses|taxonomies|types|wp_)", route) and "(?P" not in route:
                print("  route:", route)
        return
    if isinstance(data, dict) and all(isinstance(v, dict) and "rest_base" in v for v in data.values()):
        for slug, t in data.items():
            print(f"  type {slug!r}: name={t.get('name')!r} rest_base={t.get('rest_base')!r}")
        return
    if isinstance(data, list):
        print(f"list of {len(data)}")
        if data and isinstance(data[0], dict):
            print("first item keys:", sorted(data[0]))
            print(json.dumps(data[0], indent=1, ensure_ascii=False)[:4000])
            for item in data:
                title = item.get("title")
                title = title.get("rendered") if isinstance(title, dict) else title
                print("  -", item.get("id"), item.get("slug"), item.get("date"), item.get("link"), repr(title)[:80])
        return
    print(json.dumps(data, indent=1, ensure_ascii=False)[:6000])


def show_html(url, body, deep):
    text = body.decode("utf-8", "replace")
    p = LinkParser()
    p.feed(text)
    host = urlparse(url).netloc
    print("title:", p.title.strip())
    seen = set()
    for href, label in p.links:
        full = urljoin(url, href)
        if urlparse(full).netloc != host or full in seen:
            continue
        seen.add(full)
        if len(seen) <= MAX_LINKS:
            print(f"  link: {urlparse(full).path}{'?' + urlparse(full).query if urlparse(full).query else ''}  | {' '.join(label.split())[:70]}")
    print(f"same-host links: {len(seen)}")
    for s in p.scripts:
        print("  script:", s)
    for m in sorted(set(API_RE.findall(text)))[:80]:
        print("  api-ish in html:", m)
    for m in sorted(set(re.findall(r'<(?:div|section|article|li)[^>]+class="([^"]*(?:film|movie|event|card|poster)[^"]*)"', text, re.I)))[:40]:
        print("  class:", m)
    if deep:
        for s in p.scripts:
            surl = urljoin(url, s)
            try:
                status, _, _, js = fetch(surl)
            except Exception as e:  # noqa: BLE001 - diagnostic tool
                print("  !! script fetch failed", surl, e)
                continue
            hits = sorted(set(API_RE.findall(js.decode("utf-8", "replace"))))
            print(f"  [{status}] {surl} ({len(js)} bytes) api-ish: {len(hits)}")
            for h in hits[:60]:
                print("     ", h)


def probe(url, deep=False):
    print("=" * 100)
    print("URL:", url, "(deep)" if deep else "")
    try:
        status, final, headers, body = fetch(url)
    except Exception as e:  # noqa: BLE001 - diagnostic tool
        print("!! fetch failed:", type(e).__name__, e)
        return
    ctype = headers.get("Content-Type", "")
    print(f"status={status} final={final} type={ctype} bytes={len(body)} server={headers.get('Server')}")
    if "json" in ctype:
        try:
            return show_json(json.loads(body))
        except ValueError:
            pass
    if "html" in ctype:
        return show_html(final, body, deep)
    print(body[:6000].decode("utf-8", "replace"))


def main(argv):
    if argv:
        lines = argv
    else:
        lines = Path(__file__).with_name("probe-urls.txt").read_text().splitlines()
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        probe(parts[-1], deep=parts[0] == "deep")


if __name__ == "__main__":
    main(sys.argv[1:])
