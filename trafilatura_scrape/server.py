"""Tiny Firecrawl-compatible scrape server backed by trafilatura.

Speaks the Firecrawl ``/v1/scrape`` REST API so Hermes's native
``web_extract`` tool dispatches to it via ``FIRECRAWL_API_URL``.
Zero Docker, zero config nightmare — just this package + trafilatura.
"""

from __future__ import annotations

import json
import logging
import os
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
import trafilatura

log = logging.getLogger("trafilatura-scrape")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.5",
}


def _extract_title(html: str) -> str:
    """Pull the <title> tag from raw HTML."""
    m = re.search(
        r'<title[^>]*>\s*(.*?)\s*</title>', html, re.IGNORECASE | re.DOTALL
    )
    return m.group(1).strip() if m else ""


def extract(url: str, fmt: str = "markdown") -> Dict[str, Any]:
    """Fetch *url* and extract content with trafilatura.

    Returns the Firecrawl ``data`` sub-shape so the Hermes provider's
    ``_extract_scrape_payload`` normalizer picks it up as::

        {"markdown": …, "html": …, "metadata": {…}}
    """
    resp = requests.get(
        url, headers=_HEADERS, timeout=30, allow_redirects=True,
    )
    resp.raise_for_status()

    final_url = resp.url
    raw_html = resp.text
    title = _extract_title(raw_html)

    markdown = trafilatura.extract(
        raw_html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=True,
    ) or ""

    html = trafilatura.extract(
        raw_html,
        output_format="html",
        include_comments=False,
        include_tables=True,
    ) or ""

    return {
        "markdown": markdown,
        "html": html,
        "metadata": {
            "title": title,
            "sourceURL": final_url,
        },
    }


# ── HTTP Handler ──────────────────────────────────────────────────────


class _Handler(BaseHTTPRequestHandler):
    """HTTP 1.0 handler for /v1/scrape."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — base class API
        log.info("%s - %s", self.client_address[0], format % args)

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg: str, status: int = 500) -> None:
        self._json({"success": False, "error": msg}, status=status)

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path == "/health":
            self._json({"status": "ok", "service": "trafilatura-scrape"})
        else:
            self._err(
                "Not found. Use POST /v1/scrape or GET /health",
                status=404,
            )

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path != "/v1/scrape":
            self._err("Not found. Use POST /v1/scrape", status=404)
            return

        # Read body
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            self._err("Empty request body", status=400)
            return

        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            self._err(f"Invalid JSON: {exc}", status=400)
            return

        url = (body.get("url") or "").strip()
        if not url:
            self._err("Missing 'url' field", status=400)
            return

        # Firecrawl sends formats=["markdown"] or ["markdown", "html"]
        formats: List[str] = body.get("formats", ["markdown"])
        fmt = "markdown" if "markdown" in formats else "html"

        log.info("scraping: %s  (format=%s)", url, fmt)
        try:
            data = extract(url, fmt=fmt)
            self._json({"success": True, "data": data})
        except requests.Timeout:
            self._err("Request timed out after 30s", status=504)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response else 502
            self._err(f"Upstream HTTP {code}", status=502)
        except Exception as exc:
            log.exception("scrape failed for %s", url)
            self._err(str(exc), status=500)


# ── Public API ────────────────────────────────────────────────────────


def create_app() -> HTTPServer:
    """Create the HTTP server (not yet listening).

    Call ``server.serve_forever()`` to start.
    """
    host = os.environ.get("SCRAPE_HOST", "127.0.0.1")
    port = int(os.environ.get("SCRAPE_PORT", "8766"))
    server = HTTPServer((host, port), _Handler)
    log.info("listening on http://%s:%d", host, port)
    return server


def serve() -> None:
    """Start the server and block forever."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s %(message)s",
    )
    server = create_app()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        server.server_close()
