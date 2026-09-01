"""Tests for sync POST /v2/batch/scrape with per-URL error isolation."""

import json
import urllib.error
import urllib.request


def _post(base: str, path: str, payload: dict):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


def test_batch_scrape_two_urls(server):
    base, _ = server
    status, body = _post(
        base,
        "/v2/batch/scrape",
        {
            "urls": ["https://example.com", "https://example.org"],
            "formats": ["markdown"],
        },
    )
    assert status == 200
    assert body["success"] is True
    assert body["status"] == "completed"
    assert body["completed"] == body["total"] == 2
    assert len(body["data"]) == 2
    for doc in body["data"]:
        assert doc["markdown"]
        assert doc["metadata"]["statusCode"] == 200


def test_batch_scrape_bad_url_isolated(server):
    base, _ = server
    status, body = _post(
        base,
        "/v2/batch/scrape",
        {
            "urls": ["https://example.com", "http://127.0.0.1:9/unreachable"],
            "formats": ["markdown"],
        },
    )
    assert status == 200
    assert body["success"] is True
    assert body["status"] == "completed"
    # per-item failure does not fail the batch
    assert body["data"][1]["success"] is False
    assert body["data"][1]["error"]
    assert body["data"][1]["metadata"]["sourceURL"] == "http://127.0.0.1:9/unreachable"
    # the good URL still scraped fine
    assert body["data"][0]["markdown"]
    assert body["completed"] == 1
    assert body["total"] == 2


def test_batch_scrape_too_many_urls(server):
    base, _ = server
    try:
        _post(base, "/v2/batch/scrape", {"urls": [f"https://example.com/?i={i}" for i in range(51)]})
    except urllib.error.HTTPError as excinfo:
        status_body = excinfo.code, json.loads(excinfo.read())
    assert status_body is not None
    status, body = status_body
    assert status == 400
    assert "too many urls (max 50)" in body["error"]


def test_batch_scrape_preserves_order(server):
    base, _ = server
    urls = ["https://example.com", "https://example.org"]
    status, body = _post(
        base,
        "/v2/batch/scrape",
        {"urls": urls, "formats": ["markdown"]},
    )
    assert status == 200
    got = [doc["metadata"]["sourceURL"].rstrip("/") for doc in body["data"]]
    assert got == [u.rstrip("/") for u in urls]
