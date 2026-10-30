"""Upcoming screenings for the web app, from the sources that list them.

Written to data/showtimes.json on every run (published, not committed: screenings pass
every day, and items.json should only change when listings do):

    updated: when this run finished
    items:   "<source>:<id>" -> [{start: "2026-10-30T16:10" (Singapore time), url, venue?, note?}]

A source that fails a run has no times until its next good run; its cards still link out.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Item, now_sgt


def collect(items: list[Item], now: str) -> dict[str, list[dict]]:
    """Future screenings per item, earliest first, without duplicates."""
    out = {}
    for item in items:
        unique = {(s["start"], s["url"]): s for s in item.sessions if s["start"] >= now[:16]}
        if unique:
            out[f"{item.source}:{item.id}"] = sorted(unique.values(), key=lambda s: (s["start"], s["url"]))
    return out


def write(path: Path, by_item: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": now_sgt(), "items": dict(sorted(by_item.items()))}
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
