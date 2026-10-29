"""Shaw Theatres — a Next.js site; /movie is filled from a JSON endpoint.

Primary path: the same JSON the page calls (internal/get_now_showing_movies).
Fallback: render /movie in headless Chromium (Playwright), click each tab, and read
movie-detail links from the DOM.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..http import USER_AGENT
from ..models import Item
from .base import Source, SourceError
from .html import clean, harvest_links, slug_id

BASE = "https://shaw.sg"
API = BASE + "/internal/get_now_showing_movies"
FLAGS = {"isAdvanceSales": "Advance sales", "isSneakPreview": "Sneak preview",
         "isExclusive": "Exclusive", "isLimited": "Limited release"}
TABS = ["New Now Showing", "Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon"]
MOVIE_PATH = r"^/movie-details/\d+"


def movie_id(url: str) -> str:
    """Prefer a numeric path segment (stable if the title slug is edited), else the path."""
    segments = [s for s in urlparse(url).path.split("/") if s]
    for s in segments[1:]:
        if s.isdigit():
            return s
    return slug_id("/".join(segments[1:]))


class Shaw(Source):
    key = "shaw"
    name = "Shaw Theatres"
    url = BASE + "/movie"

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_api, self.from_browser)

    def from_api(self, http) -> list[Item]:
        items = []
        for m in http.get_json(API, headers={"Referer": self.url}):
            title = clean(m.get("primaryTitle"))
            code, release_id = str(m.get("code") or ""), m.get("movieReleaseId")
            mid = code if code.isdigit() else str(release_id or "") or slug_id(code)
            if not title or not mid:
                continue
            items.append(Item(
                source=self.key, id=mid, title=title,
                url=f"{BASE}/movie-details/{mid}" if mid.isdigit() else self.url,
                poster=m.get("posterUrl") or None,
                release_date=(m.get("releaseDate") or "")[:10] or None,
                tags=[label for flag, label in FLAGS.items() if m.get(flag)],
            ))
        return items

    def items_from_html(self, page_html: str, found: dict[str, Item], tag: str | None = None) -> None:
        for link in harvest_links(page_html, self.url, MOVIE_PATH):
            if not link["title"]:
                continue
            mid = movie_id(link["url"])
            item = found.setdefault(mid, Item(source=self.key, id=mid, title=link["title"],
                                              url=link["url"], poster=link["poster"]))
            if tag and tag not in item.tags:
                item.tags.append(tag)

    def from_browser(self, http) -> list[Item]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise SourceError("playwright not installed (pip install playwright; playwright install chromium)") from e

        found: dict[str, Item] = {}
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                # Posters aren't needed to read the DOM; skip heavy assets.
                page.route("**/*", lambda route: route.abort()
                           if route.request.resource_type in ("image", "media", "font") else route.continue_())
                page.goto(self.url, wait_until="load", timeout=60_000)
                settle(page)
                self.items_from_html(page.content(), found)
                for tab in TABS:
                    try:
                        page.get_by_text(tab, exact=True).first.click(timeout=5_000)
                    except Exception:  # noqa: BLE001 - tab not on the page
                        continue
                    settle(page)
                    self.items_from_html(page.content(), found, tag=tab)
            finally:
                browser.close()
        return list(found.values())


def settle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
    except Exception:  # noqa: BLE001 - analytics can keep the network busy
        pass
    page.wait_for_timeout(1_500)


