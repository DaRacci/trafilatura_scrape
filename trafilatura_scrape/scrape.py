"""Content extraction: fetch a URL and convert HTML with trafilatura.

This module holds the pure scraping logic (headers, title parsing,
``extract``) with no HTTP layer — the Firecrawl-compatible server
lives in :mod:`trafilatura_scrape.handler`.
"""

from __future__ import annotations

import re
from typing import Any, Dict

import requests
import trafilatura

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
