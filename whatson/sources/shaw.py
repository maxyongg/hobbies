"""Shaw Theatres — a Next.js site; /movie is filled by JavaScript.

The page loads each tab from shaw.sg/internal/get_{now_showing,advance_sale,top,
coming_soon}_movies, but those return 404 to plain requests (verified 2026-10-29),
so render /movie in headless Chromium (Playwright), click each tab, and read the
/movie-details/<id> cards from the DOM (title from the card's <h3>).
"""

from __future__ import annotations

import base64
import re
from urllib.parse import urlparse

from ..http import USER_AGENT
from ..models import Item
from .base import Source, SourceError
from .html import harvest_links, slug_id

BASE = "https://shaw.sg"
TABS = ["Now Showing", "Ending Soon", "Advance Sales", "Top Movies", "Coming Soon"]
SOON_TABS = {"Advance Sales", "Coming Soon"}
MOVIE_PATH = r"^/movie-details/\d+"
# Posters come through Shaw's gumlet image proxy, which answers 403 to pages on other sites;
# the Azure CDN behind it serves the same image to anyone.
GUMLET = re.compile(r"^https://[^/]+\.gumlet\.io/fetch/(https?://[^?]+)")
PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


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
        return self.first_working(http, self.from_browser)

    def items_from_html(self, page_html: str, found: dict[str, Item], tag: str | None = None) -> None:
        for link in harvest_links(page_html, self.url, MOVIE_PATH):
            if not link["title"]:
                continue
            mid = movie_id(link["url"])
            poster = link["poster"]
            if poster and (m := GUMLET.match(poster)):
                poster = m.group(1)
            item = found.setdefault(mid, Item(source=self.key, id=mid, title=link["title"],
                                              url=link["url"], poster=poster))
            if tag and tag not in item.tags:
                item.tags.append(tag)
            if tag:  # a film on any now-showing tab is "now", even if also in Advance Sales
                item.showing = "now" if tag not in SOON_TABS or item.showing == "now" else "soon"

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
                # Posters aren't needed to read the DOM, but a failed image makes Shaw swap in its
                # "no image" placeholder, so answer image requests with a 1x1 PNG instead.
                page.route("**/*", lambda route: route.fulfill(status=200, content_type="image/png", body=PIXEL)
                           if route.request.resource_type == "image" else route.abort()
                           if route.request.resource_type in ("media", "font") else route.continue_())
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


