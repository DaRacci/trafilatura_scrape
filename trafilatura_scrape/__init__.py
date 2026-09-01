"""trafilatura-scrape: Firecrawl-compatible web scrape server.

Speaks the Firecrawl REST API so agents can use it
as a web extraction backend via FIRECRAWL_API_URL.
Backed by trafilatura for HTML->Markdown extraction.
"""

from trafilatura_scrape.handler import create_app, serve

__all__ = ["create_app", "serve"]
__version__ = "1.0.0"
