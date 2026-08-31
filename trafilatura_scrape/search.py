"""Web search: Firecrawl-compatible /v2/search + /v1/search backed by SearXNG.
"""

from __future__ import annotations

import concurrent.futures
import os
from typing import Any, Dict, List, Optional, Sequence

import requests
from requests import RequestException

from trafilatura_scrape.scrape import extract

RESULTS_PER_PAGE = 20
MAX_INLINE_SCRAPES = 5
SCRAPE_WORKERS = 4
_FETCH_TIMEOUT = 30
_DEFAULT_LANG = "en"
_SUPPORTED_SOURCES = ("web", "news")


def _searxng_url() -> str:
    return (os.environ.get("SEARXNG_URL") or "").strip().rstrip("/")


def _searxng_params(
    query: str,
    categories: Optional[str],
    offset: int,
) -> Dict[str, Any]:
    """Build SearXNG query params for one backend call."""
    params: Dict[str, Any] = {
        "q": query,
        "format": "json",
        "language": os.environ.get("SCRAPE_LANG", _DEFAULT_LANG),
    }
    if categories:
        params["categories"] = categories
    pageno = (offset // RESULTS_PER_PAGE) + 1
    if pageno > 1:
        params["pageno"] = pageno
    return params


def _fetch(
    query: str,
    categories: Optional[str],
    offset: int,
) -> List[Dict[str, Any]]:
    """Call SearXNG once and return its raw ``results`` list."""
    url = _searxng_url() + "/search"
    params = _searxng_params(query, categories, offset)
    resp = requests.get(url, params=params, timeout=_FETCH_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("results", [])


def _map_result(r: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return {
        "url": r.get("url"),
        "title": r.get("title"),
        "description": r.get("content", "") or "",
        "position": idx + 1,
    }


def _map_news_result(r: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return {
        "url": r.get("url"),
        "title": r.get("title"),
        "snippet": r.get("content", "") or "",
        "date": r.get("publishedDate"),
        "position": idx + 1,
    }


def _scrape_one(url: str) -> Dict[str, Any]:
    try:
        return extract(url, formats=["markdown"])
    except RequestException as exc:
        return {"__error__": str(exc)}


def _inline_scrape(results: List[Dict[str, Any]], limit: int) -> None:
    """Add ``markdown``/``metadata`` to the top results, in place."""
    if not results:
        return
    count = min(
        len(results),
        MAX_INLINE_SCRAPES if limit > MAX_INLINE_SCRAPES else limit,
    )
    targets = results[:count]
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=SCRAPE_WORKERS,
    ) as pool:
        payloads = list(
            pool.map(lambda r: _scrape_one(r.get("url") or ""), targets)
        )
    for r, payload in zip(targets, payloads):
        if "__error__" in payload:
            r["warning"] = f"scrape failed: {payload['__error__']}"
        else:
            r["markdown"] = payload.get("markdown")
            r["metadata"] = payload.get("metadata")


def search(
    query: str,
    limit: int = 5,
    offset: int = 0,
    sources: Optional[Sequence[str]] = None,
    categories: Optional[str] = None,
    scrape_formats: Optional[Sequence[str]] = None,
    version: int = 2,
) -> Dict[str, Any]:
    """Run a web search via SearXNG and return a Firecrawl-shaped response."""
    if not query or not query.strip():
        return {"success": False, "error": "Missing 'query'"}

    srcs = [s.lower() for s in (sources or ["web"])]
    if not any(s in _SUPPORTED_SOURCES for s in srcs):
        return {
            "success": False,
            "error": f"Unsupported sources: {srcs}",
        }

    searxng = _searxng_url()
    if not searxng:
        return {
            "success": False,
            "error": "SEARXNG_URL not configured - search backend unavailable",
        }

    want_news = "news" in srcs
    want_web = "web" in srcs or not want_news

    data: Dict[str, Any] = {}

    if want_news:
        raw = _fetch(query, categories or "news", offset)
        news = [_map_news_result(r, i) for i, r in enumerate(raw)][:limit]
        data["news"] = news

    if want_web:
        if not want_news:
            raw = _fetch(query, categories, offset)
        else:
            raw = _fetch(query, None, offset)
        web = [_map_result(r, i) for i, r in enumerate(raw)][:limit]
        data["web"] = web

    if scrape_formats and "markdown" in list(scrape_formats):
        for key in ("web", "news"):
            if key in data:
                _inline_scrape(data[key], limit)

    if version == 1:
        merged: List[Dict[str, Any]] = []
        merged.extend(data.get("web", []))
        merged.extend(data.get("news", []))
        return {"success": True, "data": merged}

    return {"success": True, "data": data}
