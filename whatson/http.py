"""Polite HTTP: one session, descriptive User-Agent, timeouts, light retries."""

from __future__ import annotations

import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "cinema/0.1 (+https://github.com/maxyongg/hobbies; personal new-film alerts)"
TIMEOUT = 30
MIN_INTERVAL = 1.0  # seconds between requests to the same host


class Http:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        retry = Retry(total=2, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))
        self._last: dict[str, float] = {}

    def get(self, url: str, **kw) -> requests.Response:
        host = urlparse(url).netloc
        wait = self._last.get(host, 0) + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            return self.session.get(url, timeout=TIMEOUT, **kw)
        finally:
            self._last[host] = time.monotonic()

    def get_text(self, url: str, **kw) -> str:
        r = self.get(url, **kw)
        r.raise_for_status()
        return r.text

    def get_json(self, url: str, **kw):
        r = self.get(url, **kw)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            # Usually a bot-protection or error page served with 200; say what it was.
            snippet = " ".join(r.text[:200].split())
            raise ValueError(f"expected JSON from {r.url}, got {r.headers.get('content-type')}: {snippet!r}") from None

    def post(self, url: str, **kw) -> requests.Response:
        return self.session.post(url, timeout=TIMEOUT, **kw)
