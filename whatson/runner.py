"""The core loop: fetch each source -> diff against the store -> alert -> save."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from . import showtimes as times
from .models import Item, now_sgt
from .notify import Notifier, Sale
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
        dry_run: bool = False, showtimes_path: Path | None = None, enrich=None) -> dict:
    """`enrich(store)` runs after every source is merged and before alerts (ratings: runtimes)."""
    now = now_sgt()
    status = {"checked": now, "sources": {}}
    showtimes: dict[str, list[dict]] = {}
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
        if found := times.collect(items, now):
            showtimes.update(found)
            sessions = [s for ss in found.values() for s in ss]
            log.info("%s: %d upcoming screenings for %d films, %s to %s", src.key, len(sessions), len(found),
                     min(s["start"] for s in sessions), max(s["start"] for s in sessions))

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
            posters = sum(1 for i in items if i.poster)
            on_sale = sum(1 for i in items if i.showing == "soon" and i.on_sale)
            log.info("%s: %d listed (%d now, %d soon of which %d on sale, %d with posters), %d new",
                     src.key, len(items), showing["now"], showing["soon"], on_sale, posters, len(new))
        for i in new:
            log.info("  + %s | %s | %s", i.id, i.title, i.url)

    if enrich:
        enrich(store)
    if not dry_run:
        send_pending(store, notifier, names)
        send_sales(store, notifier, names, showtimes)
        store.save()
        if status_path:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(json.dumps(status, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if showtimes_path:
            times.write(showtimes_path, showtimes)
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


def send_sales(store, notifier: Notifier, names: dict[str, str], showtimes: dict[str, list[dict]]) -> None:
    """One push per run for coming-soon films whose tickets went on sale; retried if the send fails."""
    items = sorted(store.pending_sales(), key=lambda i: (i.title.lower(), i.source))
    if not items:
        return
    sales = [Sale(i, names.get(i.source, i.source), when(i, showtimes.get(f"{i.source}:{i.id}"))) for i in items]
    for s in sales:
        log.info("tickets on sale: %s | %s | %s", s.cinema, s.item.title, s.when)
    try:
        notifier.on_sale(sales, site_url())
    except Exception:  # noqa: BLE001
        log.exception("tickets-on-sale alert failed; will retry next run")
        return
    for i in items:
        i.sale_alert = "sent"


def when(item: Item, sessions: list[dict] | None) -> str:
    """"First screening Sat 6 Dec, 7:30 pm" / "Opens Thu 4 Dec" / "Now showing", when known."""
    if item.showing == "now":
        return "Now showing"
    if sessions:
        d = datetime.strptime(sessions[0]["start"], "%Y-%m-%dT%H:%M")
        return f"First screening {d:%a} {d.day} {d:%b}, {d.hour % 12 or 12}:{d:%M} {'am' if d.hour < 12 else 'pm'}"
    if item.release_date:
        try:
            d = datetime.strptime(item.release_date[:10], "%Y-%m-%d")
        except ValueError:
            return ""
        return f"Opens {d:%a} {d.day} {d:%b}"
    return ""


def dedupe(items: list[Item]) -> list[Item]:
    seen = {}
    for i in items:
        seen.setdefault(i.key, i)
    return list(seen.values())
