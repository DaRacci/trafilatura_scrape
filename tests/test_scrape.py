"""Tests for trafilatura_scrape.scrape.extract()."""

from trafilatura_scrape.scrape import extract


class TestExtractMetadata:
    def test_extract_metadata_status_code(self):
        """extract() must include statusCode + contentType in metadata."""
        data = extract("https://example.com", fmt="markdown")
        md = data["metadata"]
        assert md["statusCode"] == 200
        assert md.get("contentType")
