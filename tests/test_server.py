"""Smoke tests for trafilatura-scrape."""

import os
import urllib.error
from http.server import HTTPServer
from threading import Thread
from urllib.request import urlopen

import pytest

from trafilatura_scrape import __version__, create_app
from trafilatura_scrape.server import _extract_title


class TestVersion:
    def test_version(self):
        assert __version__ == "1.0.0"


class TestExtractTitle:
    def test_simple_title(self):
        html = "<html><head><title>Hello World</title></head><body></body></html>"
        assert _extract_title(html) == "Hello World"

    def test_title_with_extra_attrs(self):
        html = '<html><head><title lang="en">Hello</title></head></html>'
        assert _extract_title(html) == "Hello"

    def test_no_title(self):
        html = "<html><head></head><body></body></html>"
        assert _extract_title(html) == ""

    def test_multiline_title(self):
        html = "<html><head><title>\n  Hello\n  World\n</title></head></html>"
        result = _extract_title(html)
        assert "Hello" in result
        assert "World" in result


class TestCreateApp:
    def test_create_app_defaults(self):
        """create_app() returns a bound HTTPServer (on a free port)."""
        os.environ["SCRAPE_PORT"] = "0"
        server = create_app()
        assert isinstance(server, HTTPServer)
        server.server_close()
        del os.environ["SCRAPE_PORT"]

    def test_create_app_env_overrides(self):
        os.environ["SCRAPE_HOST"] = "0.0.0.0"
        os.environ["SCRAPE_PORT"] = "9999"
        server = create_app()
        server.server_close()
        del os.environ["SCRAPE_HOST"]
        del os.environ["SCRAPE_PORT"]


class TestServerEndToEnd:
    """Starts a real server on a random port and hits endpoints."""

    @pytest.fixture
    def server(self):
        from trafilatura_scrape.server import _Handler as Handler

        real_server = HTTPServer(("127.0.0.1", 0), Handler)
        t = Thread(target=real_server.serve_forever, daemon=True)
        t.start()
        addr = f"http://127.0.0.1:{real_server.server_address[1]}"
        yield addr, real_server
        real_server.shutdown()

    def test_health_endpoint(self, server):
        addr, _ = server
        resp = urlopen(f"{addr}/health")
        import json

        data = json.loads(resp.read())
        assert data["status"] == "ok"
        assert data["service"] == "trafilatura-scrape"

    def test_404_on_get(self, server):
        addr, _ = server
        try:
            urlopen(f"{addr}/nonexistent")
            pytest.fail("expected HTTP 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
