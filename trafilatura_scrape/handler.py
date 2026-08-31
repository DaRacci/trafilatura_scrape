"""Firecrawl-compatible HTTP server backed by trafilatura.
"""

from __future__ import annotations

import json
import logging
import os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from trafilatura_scrape.handler import _Handler

import requests

from trafilatura_scrape.scrape import _HEADERS, batch_extract, extract
from trafilatura_scrape.parse import parse_pdf
from trafilatura_scrape.map import map_site
from trafilatura_scrape.search import search

log = logging.getLogger("trafilatura-scrape")

_DEFAULT_FORMAT = "markdown"
_FETCH_TIMEOUT = 30
_MAP_DEFAULT_LIMIT = 100
_BATCH_MAX_URLS = 50
_SEARCH_DEFAULT_LIMIT = 5


def _read_json_body(handler: "_Handler") -> Optional[Dict[str, Any]]:
    """Read the request body as JSON.

    Returns None and emits the error response
    when the body is empty or not valid JSON.
    """
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        handler._err("Empty request body", status=400)
        return None
    try:
        return json.loads(handler.rfile.read(length))
    except json.JSONDecodeError as exc:
        handler._err(f"Invalid JSON: {exc}", status=400)
        return None


def _error(exc: Exception) -> Tuple[int, str]:
    """Map an upstream fetch failure to a (status, message) pair."""
    if isinstance(exc, requests.Timeout):
        return 504, f"Request timed out after {_FETCH_TIMEOUT}s"
    if isinstance(exc, requests.HTTPError):
        code = exc.response.status_code if exc.response else 502
        return 502, f"Upstream HTTP {code}"
    return 500, str(exc)


class _Handler(BaseHTTPRequestHandler):
    """HTTP 1.0 handler for /v1/scrape."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base class API
        log.info("%s - %s", self.client_address[0], format % args)

    def _json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg: str, status: int = 500) -> None:
        self._json({"success": False, "error": msg}, status=status)

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
        self._err("Not found", status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path in ("/v1/scrape", "/v2/scrape"):
            self._do_scrape()
            return
        if path == "/v2/batch/scrape":
            self._do_batch_scrape()
            return
        if path == "/v2/parse":
            self._do_parse()
            return
        if path == "/v2/map":
            self._do_map()
            return
        if path in ("/v1/search", "/v2/search"):
            version = 1 if path.startswith("/v1") else 2
            self._do_post_search(version=version)
            return
        self._err("Not found", status=404)

    def _do_scrape(self) -> None:
        """Handle POST /v{1,2}/scrape."""
        body = _read_json_body(self)
        if body is None:
            return
        url = (body.get("url") or "").strip()
        if not url:
            self._err("Missing 'url' field", status=400)
            return

        formats: List[Any] = body.get(
            "formats",
            [_DEFAULT_FORMAT],
        )

        log.info("scraping: %s (formats=%s)", url, formats)
        try:
            data = extract(url, formats=formats)
            self._json({"success": True, "data": data})
        except Exception as exc:
            log.exception("scrape failed for %s", url)
            status, msg = _error(exc)
            self._err(msg, status=status)

    def _do_post_search(self, version: int) -> None:
        """Handle POST /v{1,2}/search."""
        body = _read_json_body(self)
        if body is None:
            return
        query = (body.get("query") or "").strip()
        if not query:
            self._err("Missing 'query' field", status=400)
            return

        log.info("searching: %r (v%d)", query, version)
        self._do_search(query, version=version, body=body)

    def _do_search(
        self,
        query: str,
        version: int,
        body: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Run a search and emit the response (shared by GET and POST)."""
        body = body or {}
        try:
            limit = int(body.get("limit") or _SEARCH_DEFAULT_LIMIT)
            offset = int(body.get("offset") or 0)
        except (TypeError, ValueError):
            self._err("'limit' and 'offset' must be integers", status=400)
            return
        sources = body.get("sources") or None
        scrape_opts = body.get("scrapeOptions") or {}
        formats = scrape_opts.get("formats")

        out = search(
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

    def _do_parse(self) -> None:
        """Handle POST /v2/parse."""
        body = _read_json_body(self)
        if body is None:
            return
        url = (body.get("url") or "").strip()
        if not url:
            self._err("Missing 'url' field", status=400)
            return

        log.info("parsing: %s", url)
        try:
            resp = requests.get(
                url,
                headers=_HEADERS,
                timeout=_FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            final_url = resp.url
            parsed = parse_pdf(resp.content, final_url)
            self._json(
                {
                    "success": True,
                    "data": {
                        "markdown": parsed["markdown"],
                        "metadata": {
                            "title": parsed["metadata"]["title"],
                            "numPages": parsed["metadata"]["numPages"],
                            "sourceURL": final_url,
                            "statusCode": resp.status_code,
                            "contentType": resp.headers.get(
                                "Content-Type",
                                "",
                            ),
                        },
                    },
                }
            )
        except Exception as exc:
            log.exception("parse failed for %s", url)
            status, msg = _error(exc)
            self._err(msg, status=status)

    def _do_map(self) -> None:
        """Handle POST /v2/map."""
        body = _read_json_body(self)
        if body is None:
            return
        url = (body.get("url") or "").strip()
        if not url:
            self._err("Missing 'url' field", status=400)
            return

        try:
            limit = int(body.get("limit") or _MAP_DEFAULT_LIMIT)
        except (TypeError, ValueError):
            self._err("'limit' must be an integer", status=400)
            return

        include_subdomains = bool(body.get("includeSubdomains") or False)
        search_filter = body.get("search") or None

        log.info("mapping: %s (limit=%d)", url, limit)
        out = map_site(
            url,
            limit=limit,
            include_subdomains=include_subdomains,
            search=search_filter,
        )
        if not out.get("success"):
            self._err(out.get("error", "map failed"), status=502)
        else:
            self._json(out)

    def _do_batch_scrape(self) -> None:
        """Handle POST /v2/batch/scrape."""
        body = _read_json_body(self)
        if body is None:
            return
        urls = body.get("urls")
        if (
            not isinstance(urls, list)
            or not urls
            or not all(isinstance(u, str) and u.strip() for u in urls)
        ):
            self._err("'urls' must be a non-empty list of strings", status=400)
            return
        if len(urls) > _BATCH_MAX_URLS:
            self._err(
                f"too many urls (max {_BATCH_MAX_URLS})",
                status=400,
            )
            return

        formats: List[Any] = body.get(
            "formats",
            [_DEFAULT_FORMAT],
        )

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
