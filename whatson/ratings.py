"""Film ratings (IMDb, Letterboxd) for the web app's cards and the widget.

Each film is matched once to TMDb by title (which gives its IMDb ID). IMDb ratings come
from IMDb's daily ratings file, Letterboxd's from the film's page (letterboxd.com/tmdb/<id>/
redirects there). Ratings refresh once a day. Everything goes to data/ratings.json:

    items:   "<source>:<id>" -> TMDb id, for the web app and widget
    films:   TMDb id -> {title, year, imdb_id, imdb, letterboxd, letterboxd_url}
    matches: cleaned title -> {tmdb, checked}; tmdb is null when nothing matched

Wrong or missing matches are fixed by hand in data/rating-overrides.json.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import re
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from .models import now_sgt

log = logging.getLogger(__name__)

IMDB_RATINGS = "https://datasets.imdbws.com/title.ratings.tsv.gz"
LETTERBOXD = "https://letterboxd.com/tmdb/{}/"
MIN_VOTES = 100  # fewer IMDb votes than this: too early to show a rating
RETRY_UNMATCHED = timedelta(days=7)
CHAINS = {"gv", "shaw", "carnival"}  # first-run cinemas: prefer recent releases

# Listings that are not films, so have no rating.
NOT_FILMS = re.compile(r"live viewing|world tour|\bin cinemas\b|\bconcert\b|\bmarathon\b|\bprogramme\b", re.I)
PREFIXES = [
    re.compile(r"^.*?\bfans'? screening\s*[:–-]\s*", re.I),  # Halloween Fans' Screening: Clayface
    re.compile(r"^(sgiff|singapore international film festival)\s*\d{4}\s*[–-]\s*", re.I),
    re.compile(r"^.*?\bpresents?\s+(?=\S)", re.I),  # The Glory Hoes present The Rocky Horror...
    re.compile(r"^(marvel studios'?|disney and pixar'?s|disney pixar'?s|disney'?s|dc studios'?|dreamworks'?)\s+", re.I),
]
SUFFIXES = re.compile(r"(\s*[–-]\s*|\s+)(imax\b.*|\d+(st|nd|rd|th) anniversary.*|(premiere|special) screening|encore)$",
                      re.I)  # GODZILLA MINUS ZERO - IMAX Premiere Screening, Casino Royale - 20th Anniversary
BRACKETS = re.compile(r"\s*[\[(]([^\])]*)[\])]")
YEAR = re.compile(r"\b(19\d\d|20\d\d)\b")
CJK_CHARS = "\u3000-\u303f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uff00-\uffef"
CJK = re.compile(f"[{CJK_CHARS}]+")
CJK_TAIL = re.compile(f"^(.*?[a-z0-9!?.)'])\\s*([{CJK_CHARS}].*)$", re.I)  # GV: "Go For Broke 2 重生 2"
# Bracketed notes that are not an alternative title: (4K Restoration), (Mand), [M18], (IV)
NOTE = re.compile(r"restor|remaster|\b4k\b|imax|atmos|\biv\b|\beng|mand|canto|tamil|hindi|telugu|malay|"
                  r"\bjap|korean|encore|\bdub|\bsub|\d+d\b|\b(g|pg|pg13|nc16|m18|r21)\b|anniversary", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[’']", "", s).replace("&", " and ")
    return re.sub(r"[^\w]+", " ", s).strip()


def clean(title: str) -> tuple[list[str], int | None]:
    """Search queries for a listing title, best first, and a release year if the title gives one."""
    year, alts = None, []
    for inner in BRACKETS.findall(title):
        if years := YEAR.findall(inner):
            year = int(years[-1])
        alt = YEAR.sub("", inner).strip(" ,")
        if " " in alt and not NOTE.search(alt):
            alts.append(alt)  # AFA: "Darah-ku (My Blood, 1963)"
    t = BRACKETS.sub("", title).replace("’", "'")
    for p in PREFIXES:
        t = p.sub("", t)
    t = SUFFIXES.sub("", t)
    if m := CJK_TAIL.match(t):
        latin, cjk = m.groups()
    else:
        latin, cjk = CJK.sub(" ", t), " ".join(CJK.findall(t))
    latin = re.sub(r"\s+", " ", latin).strip(" :–-!")
    queries = [latin] if len(norm(latin)) >= 3 else []
    if cjk:
        queries.append(cjk)  # GV: "V 空枪 (Mand)"
    queries += alts
    return [q for q in queries if q], year  # none: too short to search for ("V [M]")


def title_matches(query: str, candidate: str) -> bool:
    a, b = norm(query), norm(candidate)
    if a == b:
        return True
    if re.findall(r"\d+", a) != re.findall(r"\d+", b):
        return False  # Jailer 2 is not Jailer
    return SequenceMatcher(None, a, b).ratio() >= 0.85


class TmdbError(Exception):
    pass


class Tmdb:
    API = "https://api.themoviedb.org/3"

    def __init__(self, http, key: str):
        self.http = http
        self.key = key

    @classmethod
    def from_env(cls, http) -> Tmdb | None:
        key = os.environ.get("TMDB_API_KEY", "").strip()
        return cls(http, key) if key else None

    @property
    def kind(self) -> str:
        # TMDb issues a short v3 "API Key" and a long v4 "Read Access Token" (a JWT); both work.
        return "read access token" if self.key.startswith("eyJ") else "API key"

    def get(self, path: str, **params) -> dict:
        headers = {"Accept": "application/json"}
        if self.kind == "API key":
            params["api_key"] = self.key
        else:
            headers["Authorization"] = f"Bearer {self.key}"
        try:
            r = self.http.get(f"{self.API}{path}", params=params, headers=headers)
        except Exception as e:  # noqa: BLE001
            raise TmdbError(f"TMDb {path}: {type(e).__name__}") from None  # message would show the key
        if r.status_code != 200:
            # Never echo the URL: it carries the key.
            try:
                message = r.json().get("status_message", "")
            except ValueError:
                message = r.text[:100]
            raise TmdbError(f"TMDb {path}: HTTP {r.status_code} {message}".strip())
        return r.json()

    def search(self, queries: list[str], year: int | None, chain: bool, today: date) -> dict | None:
        """The best TMDb result for any of the queries, or None if no title is close enough."""
        for q in queries:
            results = self.get("/search/movie", query=q, include_adult="false").get("results", [])
            found = [m for m in results[:10]
                     if title_matches(q, m.get("title", "")) or title_matches(q, m.get("original_title", ""))]
            if year:
                found = [m for m in found if abs(release_year(m) - year) <= 1]
            if found:
                return max(found, key=lambda m: rank(m, q, chain, today))
        return None

    def movie(self, tmdb_id: int) -> dict:
        return self.get(f"/movie/{tmdb_id}")

    def find_imdb(self, imdb_id: str) -> int | None:
        hits = self.get(f"/find/{imdb_id}", external_source="imdb_id").get("movie_results", [])
        return hits[0]["id"] if hits else None


def release_year(m: dict) -> int:
    return int((m.get("release_date") or "0")[:4] or 0)


def rank(m: dict, query: str, chain: bool, today: date) -> tuple:
    exact = norm(query) in (norm(m.get("title", "")), norm(m.get("original_title", "")))
    y = release_year(m)
    recent = not y or y >= today.year - 1  # unreleased films often have no date yet
    return (exact, recent if chain else True, m.get("popularity", 0))


def letterboxd(http, tmdb_id: int) -> tuple[float | None, str | None]:
    """(average rating out of 5, film page URL). Raises PermissionError if Letterboxd blocks us."""
    r = http.get(LETTERBOXD.format(tmdb_id))
    if r.status_code == 404:
        return None, None
    if r.status_code in (403, 429) or "Just a moment" in r.text[:2000]:
        raise PermissionError(f"Letterboxd answered HTTP {r.status_code}")
    r.raise_for_status()
    url = r.url if "/film/" in r.url else None
    m = re.search(r'name="twitter:data2" content="([\d.]+) out of 5"', r.text) \
        or re.search(r'"ratingValue":\s*([\d.]+)', r.text)
    return (round(float(m.group(1)), 1) if m else None), url


def imdb_ratings(http, wanted: set[str]) -> dict[str, tuple[float, int]]:
    """IMDb ID -> (rating, votes) for the wanted IDs, from IMDb's daily ratings file."""
    r = http.get(IMDB_RATINGS)
    r.raise_for_status()
    out = {}
    for line in gzip.decompress(r.content).decode("utf-8").splitlines():
        tconst, _, rest = line.partition("\t")
        if tconst in wanted:
            rating, votes = rest.split("\t")
            out[tconst] = (float(rating), int(votes))
    return out


def load_overrides(path: Path) -> dict[str, str | None]:
    """Hand-made fixes: listing title -> IMDb or TMDb ID/URL, or null for "no rating"."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key_for(k): v for k, v in data.items() if not k.startswith("_")}


def key_for(title: str) -> str:
    queries, _ = clean(title)
    return norm(queries[0] if queries else BRACKETS.sub("", title))


class Ratings:
    def __init__(self, path: Path, overrides: Path | None = None):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.updated: str | None = data.get("updated")
        self.films: dict[str, dict] = data.get("films", {})
        self.matches: dict[str, dict] = data.get("matches", {})
        self.items: dict[str, str] = data.get("items", {})
        self.overrides = load_overrides(overrides or self.path.with_name("rating-overrides.json"))

    def update(self, store_items, http, tmdb: Tmdb, today: date | None = None) -> None:
        today = today or date.fromisoformat(now_sgt()[:10])
        groups: dict[str, list] = {}
        for item in store_items:
            if item.type == "film" and item.listed:  # delisted films keep their last match
                groups.setdefault(key_for(item.title), []).append(item)

        new_films, errors = set(), 0
        for key, items in groups.items():
            try:
                tmdb_id = self.match(key, items, tmdb, today)
                if tmdb_id is not None and str(tmdb_id) not in self.films:
                    self.films[str(tmdb_id)] = self.describe(tmdb, tmdb_id)
                    new_films.add(str(tmdb_id))
            except TmdbError as e:
                log.warning("ratings: %s: %s", items[0].title, e)
                errors += 1
                if errors == 3:
                    log.warning("ratings: TMDb keeps failing; no more matching this run")
                    break
                continue
            for item in items:
                ref = f"{item.source}:{item.id}"
                if tmdb_id is None:
                    self.items.pop(ref, None)
                else:
                    self.items[ref] = str(tmdb_id)

        listed = {self.items[f"{i.source}:{i.id}"] for i in store_items
                  if i.listed and f"{i.source}:{i.id}" in self.items}
        stale = self.updated != today.isoformat()
        self.refresh(http, listed if stale else new_films & listed)
        if stale:
            self.updated = today.isoformat()
        referenced = set(self.items.values())
        self.films = {k: v for k, v in self.films.items() if k in referenced}

    def match(self, key: str, items, tmdb: Tmdb, today: date) -> int | None:
        if key in self.overrides:
            return self.resolve_override(key, tmdb)
        known = self.matches.get(key)
        if known and (known["tmdb"] is not None
                      or date.fromisoformat(known["checked"]) > today - RETRY_UNMATCHED):
            return known["tmdb"]
        title = items[0].title
        found = None
        queries, year = clean(title)
        if queries and not NOT_FILMS.search(title):
            chain = any(i.source in CHAINS for i in items)
            found = tmdb.search(queries, year, chain, today)
        if found:
            log.info("ratings: %s -> %s (%s) tmdb %s", title, found.get("title"), release_year(found), found["id"])
        else:
            log.info("ratings: %s -> no match", title)
        self.matches[key] = {"tmdb": found["id"] if found else None, "checked": today.isoformat()}
        return found["id"] if found else None

    def resolve_override(self, key: str, tmdb: Tmdb) -> int | None:
        value = self.overrides[key]
        if not value:
            return None
        if m := re.search(r"themoviedb\.org/movie/(\d+)|^(\d+)$", value):
            return int(m.group(1) or m.group(2))
        if m := re.search(r"tt\d+", value):
            known = self.matches.get(key, {})
            if known.get("override") == m.group(0):
                return known["tmdb"]
            tmdb_id = tmdb.find_imdb(m.group(0))
            self.matches[key] = {"tmdb": tmdb_id, "checked": now_sgt()[:10], "override": m.group(0)}
            return tmdb_id
        log.warning("ratings: override for %r is not an IMDb/TMDb ID or URL: %r", key, value)
        return None

    @staticmethod
    def describe(tmdb: Tmdb, tmdb_id: int) -> dict:
        m = tmdb.movie(tmdb_id)
        return {"title": m.get("title"), "year": release_year(m) or None, "imdb_id": m.get("imdb_id") or None,
                "imdb": None, "letterboxd": None, "letterboxd_url": None}

    def refresh(self, http, ids: set[str]) -> None:
        ids = sorted(i for i in ids if i in self.films)
        if not ids:
            return
        films = [self.films[i] for i in ids]
        wanted = {f["imdb_id"] for f in films if f.get("imdb_id")}
        try:
            imdb = imdb_ratings(http, wanted) if wanted else {}
        except Exception as e:  # noqa: BLE001
            log.warning("ratings: IMDb ratings file failed: %s", e)
            imdb = None
        if imdb is not None:
            for f in films:
                rating, votes = imdb.get(f.get("imdb_id"), (None, 0))
                f["imdb"] = rating if votes >= MIN_VOTES else None
        for tmdb_id, f in zip(ids, films):
            try:
                f["letterboxd"], url = letterboxd(http, int(tmdb_id))
                f["letterboxd_url"] = url or f.get("letterboxd_url")
            except PermissionError as e:
                log.warning("ratings: %s; keeping last Letterboxd ratings", e)
                break
            except Exception as e:  # noqa: BLE001
                log.warning("ratings: Letterboxd %s failed: %s", tmdb_id, e)
        rated = sum(1 for f in films if f["imdb"] or f["letterboxd"])
        log.info("ratings: refreshed %d films (%d with IMDb, %d with Letterboxd, %d with neither)",
                 len(films), sum(1 for f in films if f["imdb"]), sum(1 for f in films if f["letterboxd"]),
                 len(films) - rated)

    def to_dict(self) -> dict:
        return {
            "updated": self.updated,
            "items": dict(sorted(self.items.items())),
            "films": dict(sorted(self.films.items(), key=lambda kv: int(kv[0]))),
            "matches": dict(sorted(self.matches.items())),
        }

    def save(self) -> None:
        text = json.dumps(self.to_dict(), ensure_ascii=False, indent=1) + "\n"
        self.path.write_text(text, encoding="utf-8")


def update(store, http, path: Path, dry_run: bool = False) -> None:
    """Match new films and refresh ratings. Never raises: ratings must not break the run."""
    tmdb = Tmdb.from_env(http)
    if tmdb is None:
        log.warning("ratings: TMDB_API_KEY not set; ratings not updated")
        return
    try:
        ratings = Ratings(path)
        ratings.update(list(store.items.values()), http, tmdb)
        matched = sum(1 for m in ratings.matches.values() if m["tmdb"] is not None)
        log.info("ratings: %d of %d titles matched", matched, len(ratings.matches))
        if not dry_run:
            ratings.save()
    except Exception:  # noqa: BLE001
        log.exception("ratings: update failed")
