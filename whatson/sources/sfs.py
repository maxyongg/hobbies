"""Singapore Film Society — SFS Somerset (GV Cineleisure Hall 6) plus its Spotlight and
Showcase screenings at other halls.

Screenings are sold through Eventive. Its API needs the client header SFS's own page
sends, so instead of imitating that, load www.singaporefilmsociety.com in headless
Chromium and read the events list the page fetches. One item per film, not per session;
each event is one of its screenings (venue short_name, e.g. "GV Cineleisure").
Shown in the web app only (alerts = False).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..http import USER_AGENT
from ..models import Item, screening
from .base import Source, SourceError
from .html import clean

SITE = "https://www.singaporefilmsociety.com/"
EVENTS = "https://events.singaporefilmsociety.com"
NOW_DAYS = 7


def note(event_name: str, film_name: str) -> str | None:
    """What the event adds to the film: "SFS Spotlight: Roman Holiday (Members-Only)" -> "Members-Only"."""
    rest = event_name.split(":", 1)[-1].strip()
    if not rest.lower().startswith(film_name.lower()):
        return None
    return rest[len(film_name):].strip(" ()–-") or None


def venue(event: dict) -> str | None:
    v = event.get("venue") or {}
    return clean(v.get("short_name") or v.get("name") or event.get("location")) or None


def items_from_events(events: list[dict], now: datetime) -> list[Item]:
    items: dict[str, Item] = {}
    for ev in events:
        try:
            start = datetime.fromisoformat(ev["start_time"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            start = None
        showing = "now" if start and start <= now + timedelta(days=NOW_DAYS) else "soon"
        series = clean(ev.get("name")).split(":")[0] if ":" in (ev.get("name") or "") else None
        for film in ev.get("films") or []:
            fid, title = film.get("id"), clean(film.get("name"))
            if not fid or not title:
                continue
            item = items.get(fid)
            if item is None:
                item = items[fid] = Item(source="sfs", id=fid, title=title, url=f"{EVENTS}/films/{fid}",
                                         poster=film.get("poster_image") or None, showing=showing)
            elif showing == "now":
                item.showing = "now"
            if series and series not in item.tags:
                item.tags.append(series)
            if start:
                item.sessions.append(screening(start, item.url, venue(ev), note(clean(ev.get("name")), title)))
    return list(items.values())


class SingaporeFilmSociety(Source):
    key = "sfs"
    name = "Singapore Film Society"
    url = SITE
    alerts = False

    def fetch(self, http) -> list[Item]:
        return self.first_working(http, self.from_browser)

    def from_browser(self, http) -> list[Item]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise SourceError("playwright not installed (pip install playwright; playwright install chromium)") from e

        payloads = []

        def on_response(resp):
            if "api.eventive.org" in resp.url and "/events" in resp.url and resp.ok:
                try:
                    payloads.append(resp.json())
                except Exception:  # noqa: BLE001 - not JSON
                    pass

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                page.on("response", on_response)
                page.goto(SITE, wait_until="load", timeout=60_000)
                for _ in range(20):  # the schedule widget loads after the page
                    if payloads:
                        break
                    page.wait_for_timeout(500)
            finally:
                browser.close()
        events = [ev for payload in payloads for ev in payload.get("events", [])]
        return items_from_events(events, datetime.now(timezone.utc))
