"""Filmhouse (Golden Mile Tower) — WordPress + Elementor, ticketing by JACRO.

Data path is unverified (sites were unreachable when this was written): tries a
film-like WordPress post type over REST first, then links on the listing pages.
"""

from __future__ import annotations

from ..models import Item
from . import wordpress as wp
from .base import Source
from .html import get_pages, harvest_links, last_segment, slug_id

BASE = "https://filmhouse.sg"
LISTINGS = {"/films/": None, "/films/coming-soon/": "Coming soon"}
# /films/<slug>/ or /film/<slug>/, but not listing sub-pages.
FILM_PATH = r"^/(films?|movies?)/(?!(coming-soon|now-showing|page)/?$)[^/]+/?$"


class Filmhouse(Source):
    key = "filmhouse"
    name = "Filmhouse"
    url = BASE + "/films/"

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_rest, self.from_listing_pages)

    def from_rest(self, http) -> list[Item]:
        rest_base = wp.find_rest_base(http, BASE, ["film", "films", "movie", "movies"])
        if not rest_base:
            return []
        return [
            Item(
                source=self.key,
                id=slug_id(p["slug"]),
                title=wp.title(p),
                url=p["link"],
                poster=wp.featured_image(p),
                tags=wp.term_names(p),
            )
            for p in wp.latest_posts(http, BASE, rest_base)
            if p.get("slug") and wp.title(p)
        ]

    def from_listing_pages(self, http) -> list[Item]:
        items: dict[str, Item] = {}
        for page, html in get_pages(http, [BASE + p for p in LISTINGS]):
            tag = LISTINGS[page.removeprefix(BASE)]
            for link in harvest_links(html, page, FILM_PATH):
                fid = last_segment(link["url"])
                item = items.setdefault(fid, Item(source=self.key, id=fid, title=link["title"],
                                                  url=link["url"], poster=link["poster"]))
                if tag and tag not in item.tags:
                    item.tags.append(tag)
        return list(items.values())
