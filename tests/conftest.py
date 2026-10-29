"""Shared fakes. Fixture HTML/JSON in these tests is hand-written, not captured from the sites."""

from __future__ import annotations

import json

import pytest


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status_code = status
        self.text = body if isinstance(body, str) else json.dumps(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.body if not isinstance(self.body, str) else json.loads(self.body)


class FakeHttp:
    """Maps URL (without query string) -> body. Unknown URLs 404. Records posts."""

    def __init__(self, routes=None):
        self.routes = routes or {}
        self.posts = []
        self.fail_posts = False

    def get(self, url, **kw):
        if url in self.routes:
            return FakeResponse(self.routes[url])
        return FakeResponse("not found", 404)

    def get_text(self, url, **kw):
        r = self.get(url)
        r.raise_for_status()
        return r.text

    def get_json(self, url, **kw):
        r = self.get(url)
        r.raise_for_status()
        return r.json()

    def post(self, url, **kw):
        if self.fail_posts:
            raise RuntimeError("ntfy down")
        self.posts.append((url, kw))
        return FakeResponse("ok")


@pytest.fixture
def http():
    return FakeHttp()
