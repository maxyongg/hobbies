"""Golden Village — the biggest chain. The site (AngularJS) loads its lists by POSTing to
/.gv-api/{nowshowing,advancesales,comingsoon}, which answer plain requests with JSON.
Shown in the web app only (alerts = False): mainstream titles mostly overlap with Shaw.
"""

from __future__ import annotations

import re

from ..models import Item
from .base import Source, SourceError
from .html import clean

BASE = "https://www.gv.com.sg"
LISTS = {"nowshowing": "now", "advancesales": "soon", "comingsoon": "soon"}
LEADING_LANGUAGE = re.compile(r"^\(([^)]+)\)\s*(.+)$")  # "(Hindi) Ramayana" -> "Ramayana (Hindi)"


def gv_title(raw: str | None) -> str:
    title = clean(raw).rstrip("* ").strip()
    if m := LEADING_LANGUAGE.match(title):
        title = f"{m.group(2)} ({m.group(1)})"
    if title.isupper():  # "LOOK BACK" -> "Look Back"
        title = " ".join(w.capitalize() for w in title.split())
    return title


def detail_url(movie: dict) -> str:
    code = movie.get("filmCd")
    if movie.get("specialEvent"):
        return f"{BASE}/GVEventDetails#/event/{code}"
    if movie.get("type") == "Group":
        return f"{BASE}/GVGroupSynopsis#/group/{code}"
    return f"{BASE}/GVMovieDetails#/movie/{code}"


class GoldenVillage(Source):
    key = "gv"
    name = "Golden Village"
    url = BASE + "/GVMovies"
    alerts = False

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_api)

    def from_api(self, http) -> list[Item]:
        items: dict[str, Item] = {}
        for endpoint, showing in LISTS.items():
            data = http.post_json(f"{BASE}/.gv-api/{endpoint}", json={}, headers={
                "Accept": "application/json", "Origin": BASE, "Referer": self.url})
            if not data.get("success"):
                raise SourceError(f"{endpoint}: {data.get('errorMessage')}")
            for m in data.get("data") or []:
                code, title = str(m.get("filmCd") or ""), gv_title(m.get("filmTitle"))
                if not code or not title:
                    continue
                if code in items:  # listed twice (e.g. now showing and advance sales): now wins
                    if showing == "now":
                        items[code].showing = "now"
                    continue
                rating = m.get("rating") if "advised" not in (m.get("rating") or "").lower() else None
                items[code] = Item(source=self.key, id=code, title=title, url=detail_url(m),
                                   poster=m.get("imageLink") or None, showing=showing,
                                   tags=[t for t in (m.get("language"), rating) if t])
        return list(items.values())
