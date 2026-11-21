"""Seen-store: every item ever seen, plus per-source health, in one JSON file.

The file is committed by the scheduled workflow and published as the web app's data,
so it holds nothing that changes on every run (run timestamps go to status.json).
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Item

MUTABLE_FIELDS = ("title", "url", "poster", "release_date", "tags", "type", "showing")


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.items: dict[tuple[str, str], Item] = {}
        self.sources: dict[str, dict] = {}
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.sources = data.get("sources", {})
            for d in data.get("items", []):
                item = Item.from_dict(d)
                self.items[item.key] = item

    def has_source(self, source: str) -> bool:
        return any(k[0] == source for k in self.items)

    def merge(self, source: str, fetched: list[Item], now: str, alert: str = "pending") -> list[Item]:
        """Record a successful fetch; new items get `alert`. Returns the items not seen before."""
        new = []
        fetched_keys = set()
        for item in fetched:
            fetched_keys.add(item.key)
            old = self.items.get(item.key)
            if old is None:
                item.first_seen = now
                item.listed = True
                item.alert = alert
                item.sale_alert = "skip" if item.on_sale else None
                self.items[item.key] = item
                new.append(item)
            else:
                was_soon = old.showing == "soon"
                for f in MUTABLE_FIELDS:
                    value = getattr(item, f)
                    if value:
                        setattr(old, f, value)
                old.listed = True
                self.update_sale(old, item.on_sale, was_soon, alert)
        for key, item in self.items.items():
            if key[0] == source and key not in fetched_keys:
                item.listed = False
        return new

    @staticmethod
    def update_sale(old: Item, on_sale: bool | None, was_soon: bool, alert: str) -> None:
        """Mark a coming-soon film for a "tickets on sale" alert the first time its tickets go on sale.

        Only a change we saw counts: not on sale (False) on the last run, on sale now. Unknown before
        (None, e.g. the first run after this was added) is recorded without an alert.
        """
        if on_sale is None:
            return
        if on_sale and not old.on_sale and old.sale_alert is None:
            old.sale_alert = "pending" if old.on_sale is False and was_soon and alert == "pending" else "skip"
        old.on_sale = on_sale

    def pending(self) -> list[Item]:
        return [i for i in self.items.values() if i.alert == "pending"]

    def pending_sales(self) -> list[Item]:
        return [i for i in self.items.values() if i.sale_alert == "pending"]

    def health(self, source: str) -> dict:
        return self.sources.setdefault(source, {"consecutive_failures": 0, "last_error": None})

    def to_dict(self) -> dict:
        items = sorted(self.items.values(), key=lambda i: (i.source, i.id))
        items.sort(key=lambda i: i.first_seen or "", reverse=True)
        return {
            "sources": dict(sorted(self.sources.items())),
            "items": [i.to_dict() for i in items],
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=1) + "\n"
        self.path.write_text(text, encoding="utf-8")
