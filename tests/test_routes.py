"""Route tests: POST /v2/scrape plus /v1/scrape aliasing."""

import json
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from trafilatura_scrape.handler import _Handler


@pytest.fixture
def server():
    """Start the handler in-process on an ephemeral port; yield base URL."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield base, httpd
    httpd.shutdown()


def _post(base: str, path: str, payload: dict):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def test_v2_scrape_route(server):
    base, _ = server
    status, body = _post(
        base, "/v2/scrape", {"url": "https://example.com", "formats": ["markdown"]}
    )
    assert status == 200
    assert body["success"] is True
    assert body["data"]["markdown"]
    assert body["data"]["metadata"]["statusCode"] == 200


def test_v1_scrape_route_still_works(server):
    base, _ = server
    status, body = _post(
        base, "/v1/scrape", {"url": "https://example.com", "formats": ["markdown"]}
    )
    assert status == 200
    assert body["success"] is True
    assert body["data"]["markdown"]


def test_v2_scrape_bad_url(server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _post(base, "/v2/scrape", {"url": ""})
    assert excinfo.value.code == 400
    body = json.loads(excinfo.value.read())
    assert body["success"] is False
