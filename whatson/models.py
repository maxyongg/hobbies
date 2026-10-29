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
    # Set by the store, not by sources:
    first_seen: str | None = None
    listed: bool = True  # present in the latest successful fetch
    alert: str = "pending"  # "seed" (first run) | "quiet" (source doesn't alert) | "pending" | "sent"

    @property
    def key(self) -> tuple[str, str]:
        return (self.source, self.id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Item:
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in d.items() if k in known})
