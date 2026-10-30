"""Shared fakes. Fixture HTML/JSON in these tests is hand-written, not captured from the sites."""

from __future__ import annotations

import json

import pytest


class FakeResponse:
    def __init__(self, body, status=200, url=None):
        self.body = body
        self.status_code = status
        self.url = url
        self.content = body if isinstance(body, bytes) else None
        self.text = body if isinstance(body, str) else "" if isinstance(body, bytes) else json.dumps(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.body if not isinstance(self.body, str) else json.loads(self.body)


class FakeHttp:
    """Maps URL (without query string) -> body, FakeResponse, or a function of the request's
    params returning either. Unknown URLs 404. Records gets and posts."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.gets = []
        self.posts = []
        self.fail_posts = False

    def get(self, url, **kw):
        self.gets.append(url)
        if url not in self.routes:
            return FakeResponse("not found", 404, url)
        route = self.routes[url]
        if callable(route):
            route = route(kw.get("params") or {})
        return route if isinstance(route, FakeResponse) else FakeResponse(route, url=url)

    def get_text(self, url, **kw):
        r = self.get(url)
        r.raise_for_status()
        return r.text

    def get_json(self, url, **kw):
        r = self.get(url)
        r.raise_for_status()
        return r.json()

    def post_json(self, url, **kw):
        return self.get_json(url)

    def post(self, url, **kw):
        if self.fail_posts:
            raise RuntimeError("ntfy down")
        self.posts.append((url, kw))
        return FakeResponse("ok")


@pytest.fixture
def http():
    return FakeHttp()
