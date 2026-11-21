"""Alert channels. v1: ntfy.sh push (https://docs.ntfy.sh/publish/)."""

from __future__ import annotations

import logging
import os
from typing import NamedTuple

from .models import Item

log = logging.getLogger(__name__)

SUMMARY_OVER = 5  # more new items than this from one source -> one summary push


class Sale(NamedTuple):
    """A coming-soon film whose tickets just went on sale."""
    item: Item
    cinema: str  # source name
    when: str  # "First screening Sat 6 Dec, 7:30 pm", "Opens Thu 4 Dec", "Now showing" or ""


class Notifier:
    """Base: logs only. Used when no channel is configured."""

    configured = False

    def new_items(self, source_name: str, items: list[Item], site_url: str) -> None:
        for i in items:
            log.info("[no notifier] new at %s: %s %s", source_name, i.title, i.url)

    def on_sale(self, sales: list[Sale], site_url: str) -> None:
        for s in sales:
            log.info("[no notifier] tickets on sale at %s: %s %s", s.cinema, s.item.title, s.item.url)

    def problem(self, title: str, message: str, click: str | None = None) -> None:
        log.warning("[no notifier] %s: %s", title, message)


class Ntfy(Notifier):
    configured = True

    def __init__(self, http, topic: str, server: str = "https://ntfy.sh", token: str | None = None):
        self.http = http
        self.topic = topic
        self.server = server.rstrip("/")
        self.token = token

    def _send(self, **payload) -> None:
        payload = {k: v for k, v in payload.items() if v}
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        # JSON publishing keeps non-ASCII titles intact (headers can't carry them).
        r = self.http.post(self.server, json={"topic": self.topic, **payload}, headers=headers)
        r.raise_for_status()

    def new_items(self, source_name: str, items: list[Item], site_url: str) -> None:
        if len(items) > SUMMARY_OVER:
            lines = [f"• {i.title}" for i in items]
            self._send(
                title=f"{len(items)} new at {source_name}",
                message="\n".join(lines),
                click=site_url,
                tags=["clapper"],
            )
            return
        for i in items:
            self._send(
                title=f"New at {source_name}" + (" · tickets on sale" if i.on_sale and i.showing == "soon" else ""),
                message=i.title + (f"\n{', '.join(i.tags)}" if i.tags else ""),
                click=i.url,
                attach=i.poster,
                tags=["clapper"],
            )

    def on_sale(self, sales: list[Sale], site_url: str) -> None:
        """All of a run's films in one push; one film gets its poster and a link to its page."""
        if len(sales) == 1:
            s = sales[0]
            self._send(title=f"Tickets on sale at {s.cinema}", message="\n".join(filter(None, [s.item.title, s.when])),
                       click=s.item.url, attach=s.item.poster, tags=["tickets"])
            return
        lines = [f"• {s.item.title} ({s.cinema}" + (f", {s.when[0].lower()}{s.when[1:]})" if s.when else ")")
                 for s in sales]
        self._send(title=f"Tickets on sale for {len(sales)} films", message="\n".join(lines),
                   click=site_url, tags=["tickets"])

    def problem(self, title: str, message: str, click: str | None = None) -> None:
        self._send(title=title, message=message, click=click, tags=["warning"], priority=4)


def from_env(http) -> Notifier:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return Notifier()
    return Ntfy(
        http,
        topic,
        server=os.environ.get("NTFY_SERVER") or "https://ntfy.sh",
        token=os.environ.get("NTFY_TOKEN") or None,
    )
