"""The core loop: fetch each source -> diff against the store -> alert -> save."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from .models import Item, now_sgt
from .notify import Notifier
from .sources import Source, SourceError

log = logging.getLogger(__name__)

BROKEN_AFTER = 2  # consecutive failed/empty fetches before alerting that a source broke


def site_url() -> str:
    if url := os.environ.get("SITE_URL"):
        return url
    owner, _, repo = os.environ.get("GITHUB_REPOSITORY", "maxyongg/hobbies").partition("/")
    return f"https://{owner}.github.io/{repo}/"


def run_url() -> str | None:
    env = os.environ
    if "GITHUB_RUN_ID" in env:
        return f"{env['GITHUB_SERVER_URL']}/{env['GITHUB_REPOSITORY']}/actions/runs/{env['GITHUB_RUN_ID']}"
    return None


def run(sources: list[Source], store, notifier: Notifier, http, status_path: Path | None = None,
        dry_run: bool = False) -> dict:
    now = now_sgt()
    status = {"checked": now, "sources": {}}
    names = {s.key: s.name for s in sources}

    for src in sources:
        health = store.health(src.key)
        try:
            items = dedupe(src.fetch(http))
            error = None if items else "returned 0 items"
        except SourceError as e:
            items, error = [], str(e)
        except Exception as e:  # noqa: BLE001 - one broken source must not stop the others
            log.exception("%s failed", src.key)
            items, error = [], f"{type(e).__name__}: {e}"
        status["sources"][src.key] = {"name": src.name, "url": src.url, "alerts": src.alerts,
                                      "ok": not error, "count": len(items), "error": error}

        if error:
            health["consecutive_failures"] += 1
            health["last_error"] = error
            log.warning("%s: %s (failure %d)", src.key, error, health["consecutive_failures"])
            if health["consecutive_failures"] == BROKEN_AFTER and not dry_run:
                notifier.problem(f"cinema: {src.name} scraper may be broken",
                                 f"{error} on {BROKEN_AFTER} runs in a row.", run_url())
            continue

        if health["consecutive_failures"]:
            log.info("%s recovered after %d failures", src.key, health["consecutive_failures"])
        health["consecutive_failures"] = 0
        health["last_error"] = None

        seed = not store.has_source(src.key)
        new = store.merge(src.key, items, now, alert="seed" if seed else "pending" if src.alerts else "quiet")
        if seed:
            log.info("%s: seeded %d items (no alerts on first run)", src.key, len(new))
        else:
            showing = {s: sum(1 for i in items if (i.showing or "now") == s) for s in ("now", "soon")}
            log.info("%s: %d listed (%d now, %d soon), %d new", src.key, len(items), showing["now"], showing["soon"], len(new))
        for i in new:
            log.info("  + %s | %s | %s", i.id, i.title, i.url)

    if not dry_run:
        send_pending(store, notifier, names)
        store.save()
        if status_path:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return status


def send_pending(store, notifier: Notifier, names: dict[str, str]) -> None:
    """Alert on every pending item. Items stay pending if the send fails, so the next run retries."""
    by_source: dict[str, list[Item]] = {}
    for item in store.pending():
        by_source.setdefault(item.source, []).append(item)
    for source, items in by_source.items():
        try:
            notifier.new_items(names.get(source, source), items, site_url())
        except Exception:  # noqa: BLE001
            log.exception("alerting for %s failed; will retry next run", source)
            continue
        for i in items:
            i.alert = "sent"


def dedupe(items: list[Item]) -> list[Item]:
    seen = {}
    for i in items:
        seen.setdefault(i.key, i)
    return list(seen.values())
