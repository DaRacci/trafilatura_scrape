"""Tests for PDF parsing: parse_pdf, PDF auto-detection in scrape, /v2/parse."""

import io
import os

import pytest
import requests as _requests

from trafilatura_scrape.parse import parse_pdf

needs_network = pytest.mark.skipif(
    os.environ.get("TEST_LIVE") != "1", reason="live network test"
)


def _make_pdf(*texts: str) -> bytes:
    """Build a minimal in-memory PDF with one blank page per entry."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in texts:
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class _FakeResp:
    def __init__(self, content: bytes, url: str, content_type: str, status: int = 200):
        self.content = content
        self.text = ""
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self) -> None:
        return None


# ── parse_pdf ─────────────────────────────────────────────────────────


def test_parse_pdf_blank_page() -> None:
    pdf = _make_pdf("")
    out = parse_pdf(pdf, "https://x/file.pdf")
    assert out["metadata"]["numPages"] == 1
    assert out["markdown"] == ""
    assert out["metadata"]["title"] == "https://x/file.pdf"


# ── scrape.extract PDF auto-detection ─────────────────────────────────


def test_extract_pdf_content_type(monkeypatch) -> None:
    pdf = _make_pdf("")
    monkeypatch.setattr(
        "trafilatura_scrape.scrape.requests.get",
        lambda *a, **kw: _FakeResp(pdf, "https://x/file.pdf", "application/pdf"),
    )
    from trafilatura_scrape.scrape import extract

    data = extract("https://x/file.pdf", formats=["markdown"])
    assert data["metadata"]["numPages"] == 1
    assert data["markdown"] == ""
    assert "html" not in data
    assert data["metadata"]["contentType"] == "application/pdf"
    assert data["metadata"]["sourceURL"] == "https://x/file.pdf"


def test_extract_pdf_suffix_detection(monkeypatch) -> None:
    pdf = _make_pdf("")
    monkeypatch.setattr(
        "trafilatura_scrape.scrape.requests.get",
        lambda *a, **kw: _FakeResp(
            pdf, "https://x/file.pdf", "application/octet-stream"
        ),
    )
    from trafilatura_scrape.scrape import extract

    data = extract("https://x/file.pdf?download=1", formats=["markdown"])
    assert data["metadata"]["numPages"] == 1
    assert data["markdown"] == ""
    assert "html" not in data


# ── /v2/parse route ───────────────────────────────────────────────────


def test_parse_route_missing_url(server) -> None:
    base, _httpd = server
    resp = _requests.post(f"{base}/v2/parse", json={})
    assert resp.status_code == 400
    assert resp.json()["success"] is False


@needs_network
def test_parse_route_live(server) -> None:
    base, _httpd = server
    # w3.org's dummy.pdf now sits behind a Cloudflare bot challenge for
    # spoofed-browser UAs (Cf-Mitigated: challenge, 403), so this uses an
    # equivalent public dummy PDF that serves application/pdf unchallenged.
    resp = _requests.post(
        f"{base}/v2/parse",
        json={"url": "https://www.orimi.com/pdf-test.pdf"},
        timeout=60,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "PDF Test File" in body["data"]["markdown"]
    assert body["data"]["metadata"]["numPages"] == 1
