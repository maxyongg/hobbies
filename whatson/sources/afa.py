"""Asian Film Archive (Oldham Theatre) — WordPress + "Event Manager for WooCommerce".

Events live at /event-calendar/<title-slug>-<year>/; repeat screenings add -1, -2, ...
Data path is unverified (sites were unreachable when this was written): tries the
plugin's post type over REST first, then links on the What's On pages.
"""

from __future__ import annotations

import re

from ..models import Item
from . import wordpress as wp
from .base import Source
from .html import get_pages, harvest_links, last_segment, slug_id

BASE = "https://asianfilmarchive.org"
LISTINGS = ["/whatson/", "/events-calendar/"]
EVENT_PATH = r"^/event-calendar/[^/]+/?$"
SOLD_OUT = re.compile(r"[\[(]sold out[\])]\s*", re.I)


def film_id(slug: str) -> str:
    """One film = one id: drop repeat-screening suffixes (hush-2016-2 -> hush-2016).

    Only 1-2 digit suffixes are dropped, so a trailing 4-digit year stays.
    """
    slug = slug_id(slug)
    return re.sub(r"(-\d{1,2})+$", "", slug) or slug


class AsianFilmArchive(Source):
    key = "afa"
    name = "Asian Film Archive"
    url = BASE + "/whatson/"

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_rest, self.from_listing_pages)

    def from_rest(self, http) -> list[Item]:
        rest_base = wp.find_rest_base(http, BASE, ["mep_events", "mep_event"]) or "mep_events"
        items: dict[str, Item] = {}
        for p in wp.latest_posts(http, BASE, rest_base):  # newest first
            if not p.get("slug") or not wp.title(p):
                continue
            fid = film_id(p["slug"])
            items.setdefault(fid, Item(
                source=self.key, id=fid, title=SOLD_OUT.sub("", wp.title(p)), url=p["link"],
                poster=wp.featured_image(p), tags=wp.term_names(p),
            ))
        return list(items.values())

    def from_listing_pages(self, http) -> list[Item]:
        items: dict[str, Item] = {}
        for page, html in get_pages(http, [BASE + p for p in LISTINGS]):
            for link in harvest_links(html, page, EVENT_PATH):
                if not link["title"]:
                    continue
                fid = film_id(last_segment(link["url"]))
                items.setdefault(fid, Item(source=self.key, id=fid, title=SOLD_OUT.sub("", link["title"]),
                                           url=link["url"], poster=link["poster"]))
        return list(items.values())
