"""The page loads style.css and app.js with ?v=<content hash>, so browsers never pair a new
index.html with a cached old script (which left the page stuck on "Loading…")."""

import hashlib
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


def asset_version(name: str) -> str:
    return hashlib.sha256((SITE / name).read_bytes()).hexdigest()[:10]


def test_index_references_current_asset_versions():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for name in ("style.css", "app.js"):
        want = f"{name}?v={asset_version(name)}"
        found = re.findall(rf'{re.escape(name)}\?v=[0-9a-f]+', html)
        assert found == [want], f"{name} changed: set its reference in site/index.html to {want!r}"
