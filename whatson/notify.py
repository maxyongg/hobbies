"""Alert channels. v1: ntfy.sh push (https://docs.ntfy.sh/publish/)."""

from __future__ import annotations

import logging
import os

from .models import Item

log = logging.getLogger(__name__)

SUMMARY_OVER = 5  # more new items than this from one source -> one summary push


class Notifier:
    """Base: logs only. Used when no channel is configured."""

    configured = False

    def new_items(self, source_name: str, items: list[Item], site_url: str) -> None:
        for i in items:
            log.info("[no notifier] new at %s: %s %s", source_name, i.title, i.url)

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
                title=f"New at {source_name}",
                message=i.title + (f"\n{', '.join(i.tags)}" if i.tags else ""),
                click=i.url,
                attach=i.poster,
                tags=["clapper"],
            )

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
