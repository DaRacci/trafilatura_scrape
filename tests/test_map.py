"""Tests for trafilatura_scrape.map.map_site() and POST /v2/map.

All network I/O is mocked: ``requests.get`` is monkeypatched in the
``trafilatura_scrape.map`` namespace with fixtures returning objects
shaped like responses (``.status_code``, ``.text``, ``.raise_for_status()``).
"""

import json

import pytest
import requests
import urllib.error
import urllib.request

from trafilatura_scrape import map as map_mod
from trafilatura_scrape.map import map_site

# --- Fixtures ---

ROBOTS_TXT = (
    "User-agent: *\n"
    "Disallow: /private\n"
    "Sitemap: https://example.com/sitemap.xml\n"
)

SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    "  <url><loc>https://example.com/</loc></url>\n"
    "  <url><loc>https://example.com/about</loc></url>\n"
    "  <url><loc>https://example.com/blog/post-1</loc></url>\n"
    "</urlset>\n"
)

# 1 new link (/contact) + 1 duplicate of a sitemap entry (/blog/post-1)
PAGE_HTML = (
    "<html><head><title>Example</title></head><body>"
    '<a href="/blog/post-1">Blog</a>'
    '<a href="/contact">Contact</a>'
    '<a href="mailto:hi@example.com">mail</a>'
    '<a href="#top">top</a>'
    "</body></html>"
)


class FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def make_get(routes):
    """Build a fake requests.get(url, **kw) from {url: (status, text)}."""

    def fake_get(url, **kw):
        if url in routes:
            status, text = routes[url]
            return FakeResp(status, text)
        return FakeResp(404, "")

    return fake_get


STANDARD_ROUTES = {
    "https://example.com/robots.txt": (200, ROBOTS_TXT),
    "https://example.com/sitemap.xml": (200, SITEMAP_XML),
    "https://example.com": (200, PAGE_HTML),
}


@pytest.fixture
def patch_standard(monkeypatch):
    monkeypatch.setattr(
        map_mod.requests, "get", make_get(STANDARD_ROUTES)
    )


# --- map_site() unit tests ---


class TestMapSite:
    def test_map_merges_sitemap_and_links(self, patch_standard):
        out = map_site("https://example.com")
        assert out["success"] is True
        urls = [link["url"] for link in out["links"]]
        # 3 sitemap entries + 1 new page link (the duplicate is dropped)
        assert len(urls) == 4
        assert len(set(urls)) == 4
        for u in urls:
            assert u.startswith("https://example.com")
        assert "https://example.com/contact" in urls
        assert "https://example.com/blog/post-1" in urls

    def test_map_respects_limit(self, patch_standard):
        out = map_site("https://example.com", limit=2)
        assert out["success"] is True
        assert len(out["links"]) == 2

    def test_map_search_filter(self, patch_standard):
        out = map_site("https://example.com", search="blog")
        assert out["success"] is True
        urls = [link["url"] for link in out["links"]]
        assert urls == ["https://example.com/blog/post-1"]

    def test_map_search_filter_case_insensitive(self, patch_standard):
        out = map_site("https://example.com", search="BLOG")
        urls = [link["url"] for link in out["links"]]
        assert urls == ["https://example.com/blog/post-1"]

    def test_map_include_subdomains(self, monkeypatch):
        routes = {
            # no sitemap anywhere
            "https://example.com/robots.txt": (404, ""),
            "https://example.com/sitemap.xml": (404, ""),
            "https://example.com": (
                200,
                '<a href="/home">home</a>'
                '<a href="https://docs.example.com/x">docs</a>',
            ),
        }
        monkeypatch.setattr(map_mod.requests, "get", make_get(routes))

        default = map_site("https://example.com")
        assert [link["url"] for link in default["links"]] == [
            "https://example.com/home"
        ]

        sub = map_site("https://example.com", include_subdomains=True)
        assert [link["url"] for link in sub["links"]] == [
            "https://example.com/home",
            "https://docs.example.com/x",
        ]

    def test_map_no_sitemap_falls_back_to_page_links(self, monkeypatch):
        routes = {
            "https://example.com/robots.txt": (404, ""),
            "https://example.com/sitemap.xml": (404, ""),
            "https://example.com": (
                200,
                '<a href="/a">a</a><a href="/b">b</a>',
            ),
        }
        monkeypatch.setattr(map_mod.requests, "get", make_get(routes))
        out = map_site("https://example.com")
        assert out["success"] is True
        assert [link["url"] for link in out["links"]] == [
            "https://example.com/a",
            "https://example.com/b",
        ]

    def test_map_total_failure(self, monkeypatch):
        routes = {
            "https://example.com/robots.txt": (404, ""),
            "https://example.com/sitemap.xml": (404, ""),
            "https://example.com": (500, ""),
        }
        monkeypatch.setattr(map_mod.requests, "get", make_get(routes))
        out = map_site("https://example.com")
        assert out["success"] is False
        assert "error" in out

    def test_map_sitemap_index_recurse(self, monkeypatch):
        index_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>\n"
            "</sitemapindex>\n"
        )
        child_xml = (
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "  <url><loc>https://example.com/p1</loc></url>\n"
            "</urlset>\n"
        )
        routes = {
            "https://example.com/robots.txt": (200, ROBOTS_TXT),
            "https://example.com/sitemap.xml": (200, index_xml),
            "https://example.com/sitemap-pages.xml": (200, child_xml),
            "https://example.com": (200, PAGE_HTML),
        }
        monkeypatch.setattr(map_mod.requests, "get", make_get(routes))
        out = map_site("https://example.com")
        urls = [link["url"] for link in out["links"]]
        assert "https://example.com/p1" in urls
        # index child (p1) + page links (blog/post-1, contact)
        assert len(urls) == 3


# --- Route tests: POST /v2/map ---


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class TestMapRoute:
    def test_v2_map_route(self, server, monkeypatch):
        base, _ = server
        monkeypatch.setattr(
            map_mod.requests, "get", make_get(STANDARD_ROUTES)
        )
        status, body = _post(base, "/v2/map", {"url": "https://example.com"})
        assert status == 200
        assert body["success"] is True
        assert len(body["links"]) == 4
        assert all("url" in link for link in body["links"])

    def test_v2_map_missing_url(self, server):
        base, _ = server
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _post(base, "/v2/map", {})
        assert excinfo.value.code == 400
        assert json.loads(excinfo.value.read())["success"] is False

    def test_v2_map_upstream_failure_is_502(self, server, monkeypatch):
        base, _ = server
        routes = {
            "https://example.com/robots.txt": (404, ""),
            "https://example.com/sitemap.xml": (404, ""),
            "https://example.com": (500, ""),
        }
        monkeypatch.setattr(map_mod.requests, "get", make_get(routes))
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _post(base, "/v2/map", {"url": "https://example.com"})
        assert excinfo.value.code == 502
        assert json.loads(excinfo.value.read())["success"] is False
