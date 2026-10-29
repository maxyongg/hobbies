"""CLI.

    python -m whatson run [--dry-run] [--source KEY ...]
    python -m whatson sources
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import notify, runner
from .http import Http
from .sources import SOURCES
from .store import Store

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="whatson")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch all sources, record new items, alert")
    r.add_argument("--dry-run", action="store_true", help="fetch and report; write nothing, alert nobody")
    r.add_argument("--source", action="append", choices=[s.key for s in SOURCES], help="limit to these sources")
    r.add_argument("--data", type=Path, default=ROOT / "data" / "items.json")
    r.add_argument("--status", type=Path, default=ROOT / "data" / "status.json")
    sub.add_parser("sources", help="list sources")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "sources":
        for s in SOURCES:
            print(f"{s.key:10} {s.name:22} {s.url}")
        return 0

    http = Http()
    sources = [s for s in SOURCES if not args.source or s.key in args.source]
    notifier = notify.from_env(http)
    if not notifier.configured:
        logging.warning("NTFY_TOPIC not set: new items are logged, not pushed")
    status = runner.run(sources, Store(args.data), notifier, http,
                        status_path=args.status, dry_run=args.dry_run)
    # Non-zero only if every source failed, so one flaky site doesn't fail the workflow.
    return 0 if any(s["ok"] for s in status["sources"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
