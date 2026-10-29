"""Shaw Theatres — movie list is rendered by JavaScript.

Data path is unverified (sites were unreachable when this was written). Tries the
static HTML first, then renders /movie in headless Chromium (Playwright), clicking
each tab, and reads movie-detail links from the DOM. Once the JSON endpoint the page
calls is known (scripts/probe.py prints it), replace from_browser with a direct call.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..http import USER_AGENT
from ..models import Item
from .base import Source, SourceError
from .html import harvest_links, slug_id


BASE = "https://www.shaw.sg"
TABS = ["New Now Showing", "Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon"]
# /movie/<x>, /movies/<x>, /movie-detail(s)/<x>, but not tab pages.
MOVIE_PATH = (r"^/movies?(-details?)?/"
              r"(?!(now-showing|new-now-showing|coming-soon|advance-sales|ending-soon|top-movies)/?$)[^/]+")


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
        return self.first_working(http, self.from_static_html, self.from_browser)

    def items_from_html(self, page_html: str, found: dict[str, Item], tag: str | None = None) -> None:
        for link in harvest_links(page_html, self.url, MOVIE_PATH):
            mid = movie_id(link["url"])
            item = found.setdefault(mid, Item(source=self.key, id=mid, title=link["title"],
                                              url=link["url"], poster=link["poster"]))
            if tag and tag not in item.tags:
                item.tags.append(tag)

    def from_static_html(self, http) -> list[Item]:
        found: dict[str, Item] = {}
        self.items_from_html(http.get_text(self.url), found)
        return list(found.values())

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


