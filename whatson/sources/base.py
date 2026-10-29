from __future__ import annotations

import logging

from ..models import Item

log = logging.getLogger(__name__)


class SourceError(Exception):
    pass


class Source:
    key: str  # short, stable; used in item keys and data files
    name: str  # shown in alerts and the web app
    url: str  # human-facing listing page

    def fetch(self, http) -> list[Item]:
        """Return everything currently listed. Raise or return [] on failure."""
        raise NotImplementedError

    def first_working(self, http, *strategies) -> list[Item]:
        """Try strategies in order (cheapest first); return the first non-empty result."""
        errors = []
        for strategy in strategies:
            try:
                items = strategy(http)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{strategy.__name__}: {type(e).__name__}: {e}")
                log.info("%s.%s failed: %s", self.key, strategy.__name__, e)
                continue
            if items:
                log.info("%s: %d items via %s", self.key, len(items), strategy.__name__)
                return items
            errors.append(f"{strategy.__name__}: 0 items")
        raise SourceError("; ".join(errors))
