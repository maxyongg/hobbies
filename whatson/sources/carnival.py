"""Carnival Cinemas (Golden Mile Tower) — Indian-language films.

The site (AngularJS) reads plain JSON from service.carnivalcinemas.sg; it sends
location=Mumbai itself, so we do too. Shown in the web app only (alerts = False).
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote

from ..models import SGT, Item
from .base import Source
from .html import clean

SITE = "https://carnivalcinemas.sg"
API = "https://service.carnivalcinemas.sg/api/QuickSearch"
LISTS = ["GetNowPlayingMovies", "GetCommingSoonMovies"]  # sic
POSTERS = SITE + "/upload/movie"  # + imageURL, e.g. CC00002369.JPG
LEADING_LANGUAGE = re.compile(r"^\(([^)]+)\)\s*(.+)$")


def carnival_title(raw: str | None) -> str:
    title = clean(raw)
    if m := LEADING_LANGUAGE.match(title):  # "(TAMIL) Ramayana" -> "Ramayana (TAMIL)"
        title = f"{m.group(2)} ({m.group(1)})"
    return re.sub(r"(\S)\(", r"\1 (", title)  # "The Execution(M18)" -> "The Execution (M18)"


class Carnival(Source):
    key = "carnival"
    name = "Carnival Cinemas"
    url = SITE + "/"
    alerts = False

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_api)

    def from_api(self, http) -> list[Item]:
        items: dict[str, Item] = {}
        today = datetime.now(SGT).date().isoformat()
        for endpoint in LISTS:
            data = http.get_json(f"{API}/{endpoint}", params={"location": "Mumbai"})
            for m in data.get("responseMovies") or []:
                name = clean(m.get("name"))
                if not name:
                    continue
                mid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")  # codes aren't unique ("111")
                opening = (m.get("openingDate") or "")[:10] or None
                bookable = endpoint == "GetNowPlayingMovies"
                items.setdefault(mid, Item(
                    source=self.key, id=mid, title=carnival_title(name), release_date=opening,
                    url=f"{SITE}/{quote(name, safe='()')}/{quote(name, safe='()')}" if bookable else self.url,
                    poster=f"{POSTERS}/{m['imageURL']}" if POSTERS and m.get("imageURL") else None,
                    showing="now" if bookable and (not opening or opening <= today) else "soon",
                ))
        return list(items.values())
