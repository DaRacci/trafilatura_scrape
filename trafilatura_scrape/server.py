"""Compatibility shim — the server was split into modules.

``extract``/``_extract_title`` now live in
:mod:`trafilatura_scrape.scrape`; the HTTP layer (``_Handler``,
``create_app``, ``serve``) lives in :mod:`trafilatura_scrape.handler`.
This module re-exports both so existing imports keep working.
"""

from .scrape import extract, _extract_title  # noqa: F401
from .handler import _Handler, create_app, serve  # noqa: F401
