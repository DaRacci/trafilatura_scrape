"""Unit tests for the SearXNG-backed search module (v2/v1)."""

import json
import os
import urllib.error
import urllib.request

import pytest

from trafilatura_scrape import search as search_mod
from trafilatura_scrape.search import search

FIXTURE = {
    "query": "firecrawl",
    "results": [
        {
            "url": "https://github.com/mendableai/firecrawl",
            "title": "firecrawl: Turn websites into LLM-ready markdown",
            "content": "Firecrawl is an API service that takes a URL, crawls it, and returns markdown.",
            "engine": "duckduckgo",
            "engines": ["duckduckgo"],
            "score": 12.5,
            "positions": [1],
            "category": "general",
            "publishedDate": None,
        },
        {
            "url": "https://www.firecrawl.dev/",
            "title": "Firecrawl: The Web Data API for LLMs",
            "content": "Extract structured data from any website for your AI apps.",
            "engine": "google",
            "engines": ["google"],
            "score": 9.1,
            "positions": [2],
            "category": "general",
            "publishedDate": "2026-08-14T00:00:00",
        },
        {
            "url": "https://example.com/blog/firecrawl-v2",
            "title": "Firecrawl v2 announcement",
            "content": "Version 2 adds search and structured output.",
            "engine": "bing",
            "engines": ["bing"],
            "score": 4.2,
            "positions": [3],
            "category": "news",
            "publishedDate": "2026-07-01T10:00:00+00:00",
        },
    ],
    "answers": [],
    "corrections": [],
    "infoboxes": [],
    "suggestions": [],
    "unresponsive_engines": [],
}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _fake_get_factory(calls):
    def fake_get(url, params=None, timeout=None, **kwargs):
        calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(FIXTURE)

    return fake_get


@pytest.fixture
def capture(monkeypatch):
    calls = []
    monkeypatch.setattr(search_mod.requests, "get", _fake_get_factory(calls))
    monkeypatch.setenv("SEARXNG_URL", "https://searx.example.test")
    return calls


def test_v2_web_results_shape(capture):
    out = search("firecrawl", limit=5)
    assert out["success"] is True
    web = out["data"]["web"]
    assert isinstance(web, list)
    assert len(web) <= 5
    for r in web:
        assert set(("url", "title", "description", "position")) <= set(r)
    assert web[0]["url"] == "https://github.com/mendableai/firecrawl"
    assert web[0]["position"] == 1


def test_v2_news_source(capture):
    out = search("firecrawl", limit=5, sources=["news"])
    news = out["data"]["news"]
    assert len(news) == 3
    assert set(("url", "title", "snippet", "date", "position")) <= set(news[0])
    assert news[0]["date"] is None
    assert news[2]["date"] == "2026-07-01T10:00:00+00:00"
    assert capture[0]["params"]["categories"] == "news"
    assert capture[0]["params"]["format"] == "json"


def test_v1_array_shape(capture):
    out = search("firecrawl", limit=5, version=1)
    assert out["success"] is True
    assert isinstance(out["data"], list)
    assert len(out["data"]) == 3
    for r in out["data"]:
        assert set(("url", "title", "description")) <= set(r)


def test_missing_searxng_url(monkeypatch):
    monkeypatch.delenv("SEARXNG_URL", raising=False)
    out = search("firecrawl")
    assert out["success"] is False
    assert "SEARXNG_URL" in out["error"]


def test_scrape_options_inlines_markdown(capture, monkeypatch):
    monkeypatch.setattr(
        search_mod, "extract",
        lambda url, formats=None: {"markdown": "# M", "metadata": {"url": url}},
    )
    out = search("firecrawl", limit=5, scrape_formats=["markdown"])
    assert out["success"] is True
    for r in out["data"]["web"]:
        assert r["markdown"] == "# M"
        assert r["metadata"]["url"] == r["url"]


def test_offset_maps_to_pageno(capture):
    search("firecrawl", limit=5, offset=20)
    assert capture[0]["params"]["pageno"] == 2
    assert capture[0]["params"]["q"] == "firecrawl"


def test_limit_trims(capture):
    out = search("firecrawl", limit=2)
    assert len(out["data"]["web"]) == 2
    assert [r["position"] for r in out["data"]["web"]] == [1, 2]


def test_default_language_param(capture):
    search("firecrawl", limit=5)
    assert capture[0]["params"]["language"] == "en"


def test_both_sources_makes_two_calls(capture):
    out = search("firecrawl", limit=5, sources=["web", "news"])
    assert out["success"] is True
    assert "web" in out["data"] and "news" in out["data"]
    assert len(capture) == 2
    cats = sorted(c["params"].get("categories", "") for c in capture)
    assert cats == ["", "news"]


# --- Route tests (server-level, mocked SearXNG) ---


def test_v2_search_route(server, monkeypatch):
    monkeypatch.setattr(search_mod.requests, "get", _fake_get_factory([]))
    monkeypatch.setenv("SEARXNG_URL", "https://searx.example.test")

    from tests.test_routes import _post

    base, _ = server
    status, body = _post(base, "/v2/search", {"query": "firecrawl", "limit": 3})
    assert status == 200
    assert body["success"] is True
    assert isinstance(body["data"]["web"], list)
    assert len(body["data"]["web"]) <= 3


def test_v1_search_route_bare_array(server, monkeypatch):
    monkeypatch.setattr(search_mod.requests, "get", _fake_get_factory([]))
    monkeypatch.setenv("SEARXNG_URL", "https://searx.example.test")

    from tests.test_routes import _post

    base, _ = server
    status, body = _post(base, "/v1/search", {"query": "firecrawl", "limit": 3})
    assert status == 200
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_v2_search_get_convenience(server, monkeypatch):
    monkeypatch.setattr(search_mod.requests, "get", _fake_get_factory([]))
    monkeypatch.setenv("SEARXNG_URL", "https://searx.example.test")

    base, _ = server
    with urllib.request.urlopen(f"{base}/v2/search?q=firecrawl") as resp:
        body = json.loads(resp.read())
    assert body["success"] is True
    assert isinstance(body["data"]["web"], list)


def test_v2_search_route_unconfigured(server, monkeypatch):
    from tests.test_routes import _post

    monkeypatch.delenv("SEARXNG_URL", raising=False)
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(base, "/v2/search", {"query": "firecrawl"})
    assert excinfo.value.code == 503
    body = json.loads(excinfo.value.read())
    assert "SEARXNG_URL" in body["error"]


@pytest.mark.skipif(
    not os.environ.get("SEARXNG_URL"),
    reason="SEARXNG_URL not set, live network test skipped",
)
def test_live_searxng():
    out = search("firecrawl", limit=3)
    assert out["success"] is True
    assert out["data"]["web"]
