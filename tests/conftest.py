"""Shared pytest fixtures for the trafilatura-scrape test suite."""

from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from trafilatura_scrape.handler import _Handler


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, httpd
    httpd.shutdown()
