"""Site mapping: sitemap + page links, Firecrawl ``/v2/map`` style.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from trafilatura_scrape.scrape import _A_HREF_RE, _SKIP_HREF_RE

_HEADERS = {
    "User-Agent": "trafilatura-scrape (map) +https://codeberg.org/Racci/trafilatura_scrape",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_FETCH_TIMEOUT = 20
_MAX_INDEX_CHILDREN = 5


def _localname(tag: str) -> str:
    """Strip any XML namespace from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _fetch_text(url: str) -> str:
    """GET *url* and return its body, or "" on any failure."""
    try:
        resp = requests.get(
            url,
            headers=_HEADERS,
            timeout=_FETCH_TIMEOUT,
        )
        if resp.status_code != 200:
            return ""
        return resp.text
    except requests.RequestException:
        return ""


def _loc_texts(root: ET.Element, child_tag: str) -> List[str]:
    """Collect ``<loc>`` texts under *child_tag* elements of *root*."""
    out: List[str] = []
    for elem in root:
        if _localname(elem.tag) != child_tag:
            continue
        for sub in elem:
            if _localname(sub.tag) == "loc" and sub.text and sub.text.strip():
                out.append(sub.text.strip())
    return out


def _collect_sitemap(
    sitemap_url: str,
    add: Callable[[str], None],
    depth: int = 0,
) -> None:
    """Parse one sitemap, adding ``<loc>`` URLs via *add*.

    Handles ``<urlset>`` (``<url><loc>``) and, one level deep,
    ``<sitemapindex>`` (recursing into at most
    :data:`_MAX_INDEX_CHILDREN` child sitemaps).
    """
    xml_text = _fetch_text(sitemap_url)
    if not xml_text:
        return
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return
    kind = _localname(root.tag)
    if kind == "urlset":
        for loc in _loc_texts(root, "url"):
            add(loc)
    elif kind == "sitemapindex" and depth < 1:
        for child_url in _loc_texts(root, "sitemap")[:_MAX_INDEX_CHILDREN]:
            _collect_sitemap(child_url, add, depth=depth + 1)


def _collect_page_links(
    page_url: str,
    html: str,
    add: Callable[[str], None],
) -> None:
    """Extract same-page ``<a href>`` links from *html* and hand to *add*."""
    for href in _A_HREF_RE.findall(html):
        href = href.strip()
        if not href or href.startswith("#"):
            continue
        if _SKIP_HREF_RE.match(href):
            continue
        absolute = urljoin(page_url, href)
        scheme = absolute.split(":", 1)[0].lower()
        if scheme not in ("http", "https"):
            continue
        add(absolute)


def map_site(
    url: str,
    limit: int = 100,
    include_subdomains: bool = False,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Map a site: sitemap entries + page links, deduped and capped.

    Returns ``{"success": True, "links": [{"url": ...}, ...]}`` with links
    deduped in first-seen order, filtered to the origin (plus subdomains
    when *include_subdomains*), optionally filtered by a case-insensitive
    *search* substring on the URL, and capped at *limit*.
    Titles are omitted.
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    base_host = (parsed.hostname or "").lower()

    links: List[str] = []
    seen: set = set()

    def add(raw: str) -> None:
        if not raw or raw in seen:
            return
        seen.add(raw)
        links.append(raw)

    sitemap_urls: List[str] = []
    robots_txt = _fetch_text(origin + "/robots.txt")
    for line in robots_txt.splitlines():
        line = line.strip()
        if line.lower().startswith("sitemap:"):
            candidate = line.split(":", 1)[1].strip()
            if candidate:
                sitemap_urls.append(candidate)
    if not sitemap_urls:
        sitemap_urls = [origin + "/sitemap.xml"]
    for sm_url in sitemap_urls:
        _collect_sitemap(sm_url, add)

    page_html = _fetch_text(url)
    if page_html:
        _collect_page_links(url, page_html, add)

    if not links and not page_html:
        return {
            "success": False,
            "error": f"could not fetch page or sitemap for {url}",
        }

    def allowed(link: str) -> bool:
        host = (urlparse(link).hostname or "").lower()
        if host == base_host:
            return True
        return bool(include_subdomains and host.endswith("." + base_host))

    links = [lnk for lnk in links if allowed(lnk)]

    if search:
        needle = search.lower()
        links = [lnk for lnk in links if needle in lnk.lower()]

    links = links[: max(0, int(limit))]

    return {"success": True, "links": [{"url": lnk} for lnk in links]}
