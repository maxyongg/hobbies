"""Filmhouse (Golden Mile Tower) — WordPress + Elementor; listings rendered by the JACRO plugin.

No film post type over REST. The listing pages link each film as /film/<id>/<slug>
(id is JACRO's, stable); the link is a bare poster, so the title comes from the card.
"""

from __future__ import annotations

import re

from ..models import Item
from .base import Source
from .html import get_pages, harvest_links, title_from_slug

BASE = "https://filmhouse.sg"
LISTINGS = {"/films/": None, "/films/coming-soon/": "Coming soon"}
FILM_PATH = r"^/film/(\d+)/"


class Filmhouse(Source):
    key = "filmhouse"
    name = "Filmhouse"
    url = BASE + "/films/"

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_listing_pages)

    def from_listing_pages(self, http) -> list[Item]:
        items: dict[str, Item] = {}
        for page, html in get_pages(http, [BASE + p for p in LISTINGS]):
            tag = LISTINGS[page.removeprefix(BASE)]
            for link in harvest_links(html, page, FILM_PATH):
                fid = re.search(FILM_PATH, link["url"].removeprefix(BASE)).group(1)
                item = items.setdefault(fid, Item(source=self.key, id=fid, url=link["url"], poster=link["poster"],
                                                  title=link["title"] or title_from_slug(link["url"])))
                if tag and tag not in item.tags:
                    item.tags.append(tag)
        for item in items.values():
            item.showing = "soon" if "Coming soon" in item.tags else "now"
        return list(items.values())
