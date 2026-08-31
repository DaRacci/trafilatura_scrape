"""Content extraction: fetch a URL,
then convert its HTML with trafilatura.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse, urljoin

import requests
import trafilatura
from pypdf.errors import PyPdfError

from trafilatura_scrape.parse import parse_pdf

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

SUPPORTED_FORMATS = ("markdown", "html", "rawHtml", "links", "images", "summary")

_FORMAT_KEY_ORDER = ("warning",) + SUPPORTED_FORMATS

_DEFAULT_FORMAT = "markdown"
_FETCH_TIMEOUT = 30
_SUMMARY_CHARS = 200
_DEFAULT_WORKERS = 4

_A_HREF_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*[\"']([^\"'#]+)[\"']", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"'#]+)[\"']", re.IGNORECASE)
_SKIP_HREF_RE = re.compile(r"^(?:javascript:|mailto:|tel:|data:)", re.IGNORECASE)


def _extract_title(html: str) -> str:
    """Pull the <title> tag from raw HTML."""
    m = re.search(
        r'<title[^>]*>\s*(.*?)\s*</title>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _normalize_formats(
    formats: Optional[Union[List[Any], str]],
    fmt: Optional[str] = None,
) -> List[Any]:
    """Normalize the formats argument to a plain list.

    Accepts None, a single string (legacy),
    or a mixed list of strings and objects.
    The legacy fmt kwarg maps to [fmt]
    when formats is not given.
    """
    if formats is None:
        return [fmt] if fmt else [_DEFAULT_FORMAT]
    if isinstance(formats, str):
        return [formats]
    return list(formats)


def _collect_urls(
    raw_html: str,
    base_url: str,
    kind: str,
) -> List[str]:
    """Extract absolute, deduplicated URLs from raw HTML.

    kind is "links" (<a href>) or "images" (<img src>).
    Skips javascript:/mailto: style schemes,
    pure # fragments and same-page anchors.
    Dedupe preserves first-seen order.
    """
    regex = _A_HREF_RE if kind == "links" else _IMG_SRC_RE
    seen: set = set()
    out: List[str] = []
    for href in regex.findall(raw_html):
        href = href.strip()
        if not href:
            continue
        if kind == "links":
            if href.startswith("#"):
                continue
            if _SKIP_HREF_RE.match(href):
                continue
        absolute = urljoin(base_url, href)
        parsed_scheme = absolute.split(":", 1)[0].lower()
        if parsed_scheme not in ("http", "https"):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
    return out


def _make_summary(markdown: str) -> str:
    """Extractive summary: first ~200 chars, truncated at a word boundary."""
    text = " ".join(markdown.split())
    if not text:
        return ""
    if len(text) <= _SUMMARY_CHARS:
        return text
    cut = text[:_SUMMARY_CHARS]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip(" .,;:-") + "..."


def extract(
    url: str,
    formats: Optional[Union[List[Any], str]] = None,
    fmt: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch *url* and extract content with trafilatura.

    Returns the Firecrawl ``data`` sub-shape:
    one key per requested format, then ``metadata`` last.
    Unsupported formats are reported in a top-level ``warning``.
    """
    resp = requests.get(
        url,
        headers=_HEADERS,
        timeout=_FETCH_TIMEOUT,
        allow_redirects=True,
    )
    resp.raise_for_status()

    final_url = resp.url
    raw_html = resp.text
    title = _extract_title(raw_html)
    content_type = resp.headers.get("Content-Type", "")

    pdf_path = urlparse(final_url).path.lower()
    if content_type.startswith("application/pdf") or pdf_path.endswith(".pdf"):
        parsed = parse_pdf(resp.content, final_url)
        return {
            "markdown": parsed["markdown"],
            "metadata": {
                "title": parsed["metadata"]["title"],
                "sourceURL": final_url,
                "statusCode": resp.status_code,
                "contentType": content_type,
                "numPages": parsed["metadata"]["numPages"],
            },
        }

    wanted = _normalize_formats(formats, fmt)
    strings = [f for f in wanted if isinstance(f, str)]
    objects = [f for f in wanted if not isinstance(f, str)]

    unsupported: List[str] = []
    for obj in objects:
        name = obj.get("type") if isinstance(obj, dict) else str(obj)
        if name:
            unsupported.append(name)
    for name in strings:
        if name not in SUPPORTED_FORMATS:
            unsupported.append(name)

    warning = ""
    if unsupported:
        warning = (
            "Formats not supported by this backend: "
            + ", ".join(unsupported)
        )

    computed: Dict[str, Any] = {}
    for name in dict.fromkeys(strings):
        if name not in SUPPORTED_FORMATS:
            continue
        if name == "markdown":
            computed[name] = trafilatura.extract(
                raw_html,
                output_format="markdown",
                include_comments=False,
                include_tables=True,
                include_images=False,
                include_links=True,
            ) or ""
        elif name == "html":
            computed[name] = trafilatura.extract(
                raw_html,
                output_format="html",
                include_comments=False,
                include_tables=True,
            ) or ""
        elif name == "rawHtml":
            computed[name] = raw_html
        elif name == "links":
            computed[name] = _collect_urls(raw_html, final_url, "links")
        elif name == "images":
            computed[name] = _collect_urls(raw_html, final_url, "images")
        elif name == "summary":
            if "markdown" not in computed:
                computed["markdown"] = trafilatura.extract(
                    raw_html,
                    output_format="markdown",
                    include_comments=False,
                    include_tables=True,
                    include_images=False,
                    include_links=True,
                ) or ""
            computed[name] = _make_summary(computed["markdown"])

    metadata = {
        "title": title,
        "sourceURL": final_url,
        "statusCode": resp.status_code,
        "contentType": content_type,
    }

    status = resp.status_code
    if status not in range(200, 300) and status != 304:
        metadata["error"] = f"HTTP {status}"

    data: Dict[str, Any] = {}
    if warning:
        data["warning"] = warning
    for key in _FORMAT_KEY_ORDER:
        if key == "warning":
            continue
        if key in computed:
            data[key] = computed[key]
    data["metadata"] = metadata
    return data


def _safe_extract(
    url: str,
    formats: Optional[Union[List[Any], str]],
) -> Dict[str, Any]:
    """Extract one URL, converting failure into a Firecrawl error doc."""
    try:
        return {"success": True, **extract(url, formats=formats)}
    except (requests.RequestException, PyPdfError) as exc:
        return {
            "success": False,
            "error": str(exc),
            "metadata": {"sourceURL": url},
        }


def batch_extract(
    urls: List[str],
    formats: Optional[Union[List[Any], str]] = None,
    max_workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Extract *urls* in parallel, preserving request order.

    Each URL is scraped independently:
    a failure for one URL yields an error item
    instead of failing the whole batch.
    Worker count comes from *max_workers*
    or SCRAPE_MAX_WORKERS, capped at the number of URLs.
    """
    workers = max_workers or int(
        os.environ.get("SCRAPE_MAX_WORKERS", str(_DEFAULT_WORKERS))
    )
    workers = min(max(1, workers), max(1, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(lambda u: _safe_extract(u, formats), urls))
