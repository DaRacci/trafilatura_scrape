"""Firecrawl-compatible HTTP server backed by trafilatura.

Speaks the Firecrawl ``/v1/scrape`` REST API so Hermes's native
``web_extract`` tool dispatches to it via ``FIRECRAWL_API_URL``.
Zero Docker, zero config nightmare — just this package + trafilatura.
"""

from __future__ import annotations

import json
import logging
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests

from trafilatura_scrape.scrape import batch_extract, extract
from trafilatura_scrape.map import map_site
from trafilatura_scrape import search as search_mod
from trafilatura_scrape.search import search as _search

log = logging.getLogger("trafilatura-scrape")

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
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/health":
            self._json({"status": "ok", "service": "trafilatura-scrape"})
            return
        if path in ("/v1/search", "/v2/search"):
            version = 1 if path.startswith("/v1") else 2
            params = parse_qs(parsed.query)
            q = (params.get("q") or [""])[0].strip()
            if not q:
                self._err("Missing 'q' query parameter", status=400)
                return
            body: Dict[str, Any] = {}
            if params.get("limit"):
                body["limit"] = params["limit"][0]
            if params.get("offset"):
                body["offset"] = params["offset"][0]
            self._do_search(q, version=version, body=body)
            return
        self._err(
            "Not found. Use POST /v2/scrape, POST /v2/search or GET /health",
            status=404,
        )

    def _do_search(
        self, query: str, version: int, body: Optional[Dict[str, Any]] = None
    ) -> None:
        """Run a search and emit the response (shared by GET and POST).

        Honors the Firecrawl v2 search request fields ``limit``,
        ``offset``, ``sources`` and ``scrapeOptions.formats`` when given.
        """
        body = body or {}
        try:
            limit = int(body.get("limit") or 5)
            offset = int(body.get("offset") or 0)
        except (TypeError, ValueError):
            self._err("'limit' and 'offset' must be integers", status=400)
            return
        sources = body.get("sources") or None
        scrape_opts = body.get("scrapeOptions") or {}
        formats = scrape_opts.get("formats")

        out = _search(
            query,
            limit=limit,
            offset=offset,
            sources=sources,
            scrape_formats=formats,
            version=version,
        )
        if not out.get("success"):
            self._err(out.get("error", "search failed"), status=503)
        else:
            self._json(out)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path in ("/v1/search", "/v2/search"):
            version = 1 if path.startswith("/v1") else 2

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

            query = (body.get("query") or "").strip()
            if not query:
                self._err("Missing 'query' field", status=400)
                return

            log.info("searching: %r  (v%d)", query, version)
            self._do_search(query, version=version, body=body)
            return

        if path == "/v2/batch/scrape":
            self._do_batch_scrape()
            return

        if path == "/v2/map":
            self._do_map()
            return

        if path not in ("/v1/scrape", "/v2/scrape"):
            self._err(
                "Not found. Use POST /v2/scrape, POST /v2/map or POST /v2/search",
                status=404,
            )
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

        # Firecrawl v2 formats: list of strings and/or object formats.
        formats: List[Any] = body.get("formats", ["markdown"])

        log.info("scraping: %s  (formats=%s)", url, formats)
        try:
            data = extract(url, formats=formats)
            self._json({"success": True, "data": data})
        except requests.Timeout:
            self._err("Request timed out after 30s", status=504)
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response else 502
            self._err(f"Upstream HTTP {code}", status=502)
        except Exception as exc:
            log.exception("scrape failed for %s", url)
            self._err(str(exc), status=500)


    def _do_map(self) -> None:
        """Firecrawl v2 map: sitemap + page links for one site."""
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

        try:
            limit = int(body.get("limit") or 100)
        except (TypeError, ValueError):
            self._err("'limit' must be an integer", status=400)
            return

        include_subdomains = bool(body.get("includeSubdomains") or False)
        search = body.get("search") or None

        log.info("mapping: %s (limit=%d)", url, limit)
        out = map_site(
            url,
            limit=limit,
            include_subdomains=include_subdomains,
            search=search,
        )
        if not out.get("success"):
            self._err(out.get("error", "map failed"), status=502)
        else:
            self._json(out)

    def _do_batch_scrape(self) -> None:
        """Sync batch scrape: parallel extraction, per-URL error isolation."""
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

        urls = body.get("urls")
        if (
            not isinstance(urls, list)
            or not urls
            or not all(isinstance(u, str) and u.strip() for u in urls)
        ):
            self._err("'urls' must be a non-empty list of strings", status=400)
            return
        if len(urls) > 50:
            self._err("too many urls (max 50)", status=400)
            return

        formats: List[Any] = body.get("formats", ["markdown"])

        log.info("batch scraping %d urls (formats=%s)", len(urls), formats)
        data = batch_extract(urls, formats=formats)
        completed = sum(1 for d in data if d.get("success"))
        self._json(
            {
                "success": True,
                "status": "completed",
                "completed": completed,
                "total": len(urls),
                "data": data,
            }
        )

# ── Public API ────────────────────────────────────────────────────────


def create_app() -> ThreadingHTTPServer:
    """Create the HTTP server (not yet listening).

    Call ``server.serve_forever()`` to start.
    """
    host = os.environ.get("SCRAPE_HOST", "127.0.0.1")
    port = int(os.environ.get("SCRAPE_PORT", "8766"))
    server = ThreadingHTTPServer((host, port), _Handler)
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
