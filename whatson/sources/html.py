"""Helpers for pulling item links out of listing pages."""

from __future__ import annotations

import html as htmllib
import logging
import re
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Link texts that label buttons rather than films.
GENERIC = re.compile(
    r"^(buy|book|get)( tickets?| now)?$|^(more )?(info|details)$|^(watch )?trailer$|^read more$|^learn more$",
    re.I,
)


def clean(text: str | None) -> str:
    """Strip tags, unescape entities, collapse whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def harvest_links(page_html: str, base_url: str, path_pattern: str) -> list[dict]:
    """Find links whose path matches `path_pattern` and guess a title and poster for each.

    A film card often has several links to the same page (poster, title, "Buy tickets"),
    so results are grouped by URL, keeping the best-scoring title and the first image.
    """
    soup = BeautifulSoup(page_html, "lxml")
    host = urlparse(base_url).netloc
    found: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"]).split("#")[0]
        parsed = urlparse(url)
        if parsed.netloc != host or not re.search(path_pattern, parsed.path):
            continue
        entry = found.setdefault(url, {"url": url, "title": "", "score": 0, "poster": None})
        img = a.find("img")
        heading = a.find(re.compile(r"^h[1-6]$"))
        # Best first: a heading inside the link, then attributes/text, then image alt.
        candidates = [
            (4, heading.get_text(" ", strip=True) if heading else None),
            (3, a.get("title")),
            (3, a.get("aria-label")),
            (2, a.get_text(" ", strip=True)),
            (1, img.get("alt") if img is not None else None),
        ]
        if img is not None and not entry["poster"]:
            src = img.get("data-src") or img.get("src")
            if src and not src.startswith("data:"):
                entry["poster"] = urljoin(base_url, src)
        for score, text in candidates:
            text = clean(text)
            if not text or GENERIC.match(text) or len(text) > 150:
                continue  # button labels, or a whole card's text
            if (score, len(text)) > (entry["score"], len(entry["title"])):
                entry["title"], entry["score"] = text, score
    return [{k: e[k] for k in ("url", "title", "poster")} for e in found.values() if e["title"]]


def slug_id(slug: str) -> str:
    """Normalise a slug so REST slugs and URL path segments compare equal."""
    return unquote(slug).strip("/").lower()


def last_segment(url: str) -> str:
    return slug_id(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])


def get_pages(http, urls: list[str]) -> list[tuple[str, str]]:
    """Fetch listing pages, tolerating some failing; raise only if all of them do."""
    pages, errors = [], []
    for url in urls:
        try:
            pages.append((url, http.get_text(url)))
        except Exception as e:  # noqa: BLE001
            log.info("%s failed: %s", url, e)
            errors.append(f"{url}: {e}")
    if not pages:
        raise RuntimeError("; ".join(errors))
    return pages
