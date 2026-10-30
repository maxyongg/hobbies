"""Film ratings (IMDb, Letterboxd) for the web app's cards.

Films are matched to TMDb by title, which gives each one's IMDb ID.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


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

    def check(self) -> str:
        """Returns a description of the key, or raises TmdbError if TMDb rejects it."""
        self.get("/authentication")
        return self.kind


def check(http) -> bool:
    tmdb = Tmdb.from_env(http)
    if tmdb is None:
        log.warning("ratings: TMDB_API_KEY not set")
        return False
    try:
        kind = tmdb.check()
        sample = tmdb.get("/search/movie", query="Before Sunrise")["results"][:1]
    except Exception as e:  # noqa: BLE001
        log.warning("ratings: TMDb key rejected or unreachable: %s", e)
        return False
    found = ", ".join(f"{m['title']} ({m.get('release_date', '')[:4]})" for m in sample)
    log.info("ratings: TMDb accepted the %s (%d characters); test search found: %s", kind, len(tmdb.key), found)
    return True
