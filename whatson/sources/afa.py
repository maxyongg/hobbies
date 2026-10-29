"""Asian Film Archive (Oldham Theatre) — WordPress + "Event Manager for WooCommerce".

Events live at /event-calendar/<title-slug>-<year>/; repeat screenings add -1, -2, ...
Reads the plugin's post type (mep_events) over WP REST, asking only for the fields
needed; falls back to event links on the What's On / Events Calendar pages.
Screenings that have ended are left out; ones within NOW_DAYS count as "now".
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..models import SGT, Item
from . import wordpress as wp
from .base import Source
from .html import get_pages, harvest_links, last_segment, slug_id

BASE = "https://asianfilmarchive.org"
LISTINGS = ["/whatson/", "/events-calendar/"]
EVENT_PATH = r"^/event-calendar/[^/]+/?$"
SOLD_OUT = re.compile(r"[\[(]sold out[\])]\s*", re.I)
NOW_DAYS = 7


def now() -> datetime:
    return datetime.now(SGT).replace(tzinfo=None)  # the plugin's datetimes are naive SGT


def screening_times(post: dict) -> tuple[datetime | None, datetime | None]:
    """(next start, end) from the plugin's meta, e.g. event_start_datetime = ["2026-10-31 11:00:00"]."""
    info = post.get("event_informations") or {}

    def meta(*keys):
        for key in keys:
            value = info.get(key)
            value = value[0] if isinstance(value, list) and value else value
            if value:
                try:
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
        return None

    return (meta("event_upcoming_datetime", "event_start_datetime"),
            meta("event_expire_datetime", "event_end_datetime"))


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
        items: dict[str, Item] = {}
        posts = wp.latest_posts(http, BASE, "mep_events", per_page=50,
                                fields="id,slug,link,title,date,class_list,yoast_head_json,event_informations")
        current = now()
        for p in posts:  # newest first
            if not p.get("slug") or not wp.title(p):
                continue
            start, end = screening_times(p)
            if end and end < current:
                continue  # already screened
            showing = None if not start else "now" if start <= current + timedelta(days=NOW_DAYS) else "soon"
            fid = film_id(p["slug"])
            item = items.setdefault(fid, Item(
                source=self.key, id=fid, title=SOLD_OUT.sub("", wp.title(p)), url=p["link"],
                poster=wp.featured_image(p), tags=wp.class_terms(p, ("mep_cat-", "tag-")), showing=showing,
            ))
            if showing == "now":  # any repeat screening this week makes the film "now"
                item.showing = "now"
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
