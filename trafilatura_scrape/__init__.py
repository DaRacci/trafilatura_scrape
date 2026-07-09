"""trafilatura-scrape: Firecrawl-compatible web scrape server.

A tiny HTTP server that speaks the Firecrawl /v1/scrape REST API
so Hermes's native web_extract tool can route through it via the
FIRECRAWL_API_URL env var. Backed by trafilatura for HTML→Markdown
extraction — no Docker, no databases, no config nightmare.
"""

from trafilatura_scrape.server import create_app, serve

__all__ = ["create_app", "serve"]
__version__ = "1.0.0"
