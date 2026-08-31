"""Tests for trafilatura_scrape.scrape.extract()."""

from trafilatura_scrape.scrape import extract


RICH_PAGE = "http://httpbin.org/html"


class TestExtractMetadata:
    def test_extract_metadata_status_code(self):
        """extract() must include statusCode + contentType in metadata."""
        data = extract("https://example.com", fmt="markdown")
        md = data["metadata"]
        assert md["statusCode"] == 200
        assert md.get("contentType")


class TestFormatKeys:
    def test_links_format(self):
        data = extract("https://example.com", fmt="links")
        links = data["links"]
        assert isinstance(links, list)
        assert len(links) > 0
        for link in links:
            assert link.startswith(("http://", "https://"))

    def test_images_format(self):
        data = extract(RICH_PAGE, formats=["images", "markdown"])
        images = data["images"]
        assert isinstance(images, list)
        for img in images:
            assert img.startswith(("http://", "https://"))

    def test_rawhtml_format(self):
        data = extract("https://example.com", formats=["rawHtml", "markdown"])
        raw = data["rawHtml"]
        assert raw.startswith("<")
        assert len(raw) > len(data["markdown"])

    def test_summary_format(self):
        data = extract("https://example.com", formats=["summary"])
        summary = data["summary"]
        assert isinstance(summary, str)
        assert summary
        assert len(summary) <= 220

    def test_mixed_formats_only_requested_keys(self):
        data = extract("https://example.com", formats=["markdown", "links"])
        assert set(data.keys()) == {"markdown", "links", "metadata"}
        assert "html" not in data

    def test_object_format_warns(self):
        data = extract(
            "https://example.com",
            formats=["markdown", {"type": "json", "prompt": "x"}],
        )
        assert "markdown" in data
        assert "metadata" in data
        assert "warning" in data
        assert "json" in data["warning"]

    def test_default_formats_markdown(self):
        data = extract("https://example.com")
        assert set(data.keys()) == {"markdown", "metadata"}

    def test_single_string_formats_backward_compat(self):
        data = extract("https://example.com", formats="html")
        assert set(data.keys()) == {"html", "metadata"}
