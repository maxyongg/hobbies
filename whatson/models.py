"""Item: the one shape every source normalises to."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8))  # Singapore has no DST


def now_sgt() -> str:
    return datetime.now(SGT).isoformat(timespec="seconds")


@dataclass
class Item:
    source: str
    id: str  # stable per source, e.g. URL slug
    title: str
    url: str
    type: str = "film"
    poster: str | None = None
    release_date: str | None = None
    tags: list[str] = field(default_factory=list)
    showing: str | None = None  # "now" | "soon" (None: source can't tell; treated as now)
    # Upcoming screenings, from sources that list them (see screening()). They go to
    # showtimes.json, not the store, so items.json doesn't change as screenings pass.
    sessions: list[dict] = field(default_factory=list)
    # Set by the store, not by sources:
    first_seen: str | None = None
    listed: bool = True  # present in the latest successful fetch
    alert: str = "pending"  # "seed" (first run) | "quiet" (source doesn't alert) | "pending" | "sent"

    @property
    def key(self) -> tuple[str, str]:
        return (self.source, self.id)

    def to_dict(self) -> dict:
        d = asdict(self)
        del d["sessions"]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Item:
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})


def screening(start: datetime, url: str, venue: str | None = None, note: str | None = None) -> dict:
    """One screening for showtimes.json. `start` is Singapore time (naive, or any tz-aware)."""
    if start.tzinfo:
        start = start.astimezone(SGT)
    d = {"start": start.strftime("%Y-%m-%dT%H:%M"), "url": url, "venue": venue or None, "note": note or None}
    return {k: v for k, v in d.items() if v}
