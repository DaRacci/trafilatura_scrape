"""Parse documents (PDFs) into markdown via pypdf. Text layer only — no OCR."""

from __future__ import annotations

import io
from typing import Any, Dict

from pypdf import PdfReader


def parse_pdf(data: bytes, source: str) -> Dict[str, Any]:
    """Extract the text layer of *data* (PDF bytes) into markdown.

    Returns ``{"markdown": str, "metadata": {"numPages": int, "title": source}}``.
    Pages whose text extraction raises are skipped; a PDF with no
    extractable text yields ``markdown == ""``.
    """
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — skip unparseable pages
            continue
        if text.strip():
            parts.append(text)
    return {
        "markdown": "\n\n".join(parts),
        "metadata": {
            "numPages": len(reader.pages),
            "title": source,
        },
    }
