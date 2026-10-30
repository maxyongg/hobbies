"""Filmhouse (Golden Mile Tower) — WordPress + Elementor; listings rendered by the JACRO plugin.

No film post type over REST. The listing pages link each film as /film/<id>/<slug>
(id is JACRO's, stable); the link is a bare poster, so the title comes from the card.
Each card (div.jacro-event) also lists its screenings: a div.heading per day
("Friday 30th October"), then a.film_book_button links (span.time "4:10 pm"), or
a.soldfilm_book_button without a link when sold out; div.movietag holds span.tag
labels ("4K", "LastChance", "Live Q&A").
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import SGT, Item, screening
from .base import Source
from .html import clean, get_pages, harvest_links, title_from_slug

BASE = "https://filmhouse.sg"
LISTINGS = {"/films/": None, "/films/coming-soon/": "Coming soon"}
FILM_PATH = r"^/film/(\d+)/"
DAY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*(?:,?\s+(\d{4}))?", re.I)  # "Friday 30th October"
TIME = re.compile(r"(\d{1,2})[:.](\d{2})\s*([ap])?\.?m?\b", re.I)  # "4:10 pm"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def today() -> date:
    return datetime.now(SGT).date()


def parse_day(text: str, ref: date) -> date | None:
    """A day heading without a year: the date nearest after `ref` (allowing a few days back)."""
    words = text.lower()
    if "today" in words:
        return ref
    if "tomorrow" in words:
        return ref + timedelta(days=1)
    m = DAY.search(text)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    day, month = int(m.group(1)), MONTHS.index(m.group(2).lower()) + 1
    years = [int(m.group(3))] if m.group(3) else [ref.year, ref.year + 1]
    for year in years:
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if m.group(3) or d >= ref - timedelta(days=7):
            return d
    return None


def parse_time(text: str) -> tuple[int, int] | None:
    m = TIME.search(text or "")
    if not m:
        return None
    hour, minute, half = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if half == "p" and hour < 12:
        hour += 12
    elif half == "a" and hour == 12:
        hour = 0
    return (hour, minute) if hour < 24 and minute < 60 else None


def labels(slot) -> list[str]:
    """Tags on a screening: "LastChance" -> "Last Chance"."""
    tag = slot.find(class_="movietag")
    if tag is None:
        return []
    texts = [clean(t.get_text(" ")) for t in tag.find_all(class_="tag")] or [clean(tag.get_text(" "))]
    return [re.sub(r"([a-z])([A-Z])", r"\1 \2", t) for t in texts if t]


def sessions_from_html(page_html: str, page_url: str, ref: date) -> dict[str, list[dict]]:
    """Film id -> screenings listed on its card. Sold-out ones link to the film's page."""
    soup = BeautifulSoup(page_html, "lxml")
    found: dict[str, list[dict]] = {}
    for card in soup.select("div.jacro-event"):
        link = card.find("a", href=re.compile(r"/film/\d+/"))
        if link is None:
            continue
        fid = re.search(r"/film/(\d+)/", link["href"]).group(1)
        film_url = re.sub(r"^http:", "https:", urljoin(page_url, link["href"]))
        day = None
        for node in card.find_all(["div", "a"]):  # document order: a day heading, then that day's Book links
            classes = node.get("class") or []
            if "heading" in classes:
                day = parse_day(node.get_text(" ", strip=True), ref)
            elif day and any(c.endswith("book_button") for c in classes):
                when = parse_time(node.find(class_="time").get_text() if node.find(class_="time") else "")
                if not when:
                    continue
                sold = any(c.startswith("sold") for c in classes) or not node.get("href")
                note = (["Sold out"] if sold else []) + labels(node.find_parent("li") or node)
                found.setdefault(fid, []).append(screening(
                    datetime(day.year, day.month, day.day, *when),
                    film_url if sold else urljoin(page_url, node["href"]), note=" · ".join(note)))
    return found


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
            for fid, sessions in sessions_from_html(html, page, today()).items():
                if fid in items:
                    items[fid].sessions += sessions
        for item in items.values():
            item.showing = "soon" if "Coming soon" in item.tags else "now"
        return list(items.values())
