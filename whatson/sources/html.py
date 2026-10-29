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
    When the links themselves carry no heading (e.g. a bare poster link), the card around
    them (the largest ancestor linking to no other film) is searched for one.
    """
    soup = BeautifulSoup(page_html, "lxml")
    base = urlparse(base_url)
    found: dict[str, dict] = {}

    def film_url(a) -> str | None:
        parsed = urlparse(urljoin(base_url, a["href"]).split("#")[0])
        if parsed.netloc != base.netloc or not re.search(path_pattern, parsed.path):
            return None
        return parsed._replace(scheme=base.scheme).geturl()

    for a in soup.find_all("a", href=True):
        url = film_url(a)
        if not url:
            continue
        entry = found.setdefault(url, {"url": url, "title": "", "score": 0, "poster": None, "anchor": a})
        consider(entry, a, base_url)

    for url, entry in found.items():
        if entry["score"] >= 4 and entry["poster"]:
            continue
        card = entry["anchor"]
        for parent in entry["anchor"].parents:
            if parent.name in ("body", "html", "[document]"):
                break
            if any(film_url(x) not in (None, url) for x in parent.find_all("a", href=True)):
                break
            card = parent
        if card is not entry["anchor"]:
            consider(entry, card, base_url, in_card=True)
    return [{k: e[k] for k in ("url", "title", "poster")} for e in found.values()]


def consider(entry: dict, node, base_url: str, in_card: bool = False) -> None:
    """Update entry's best title and first poster from a link or its card."""
    img = node.find("img")
    heading = node.find(re.compile(r"^h[1-6]$")) or node.find(class_=re.compile(r"title", re.I))
    candidates = [(4, heading.get_text(" ", strip=True) if heading else None)]
    if not in_card:  # Best first: a heading, then the link's attributes/text, then image alt.
        candidates += [(3, node.get("title")), (3, node.get("aria-label")), (2, node.get_text(" ", strip=True))]
    candidates.append((1, img.get("alt") if img is not None else None))
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


def title_from_slug(url: str) -> str:
    return unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").title()


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
