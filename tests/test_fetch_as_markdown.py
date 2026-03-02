"""
Tests for scripts/fetch_as_markdown.py

Playwright and requests are mocked throughout — no network calls or browser
launches happen during the test suite.
"""

import pytest
from unittest.mock import patch, MagicMock

from scripts.fetch_as_markdown import (
    fetch_as_markdown,
    fetch_api_spec,
    _is_thin_content,
    _clean_markdown,
    _html_to_markdown,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

# Realistic HTML structure that readability can extract content from
_HTML = """
<html><head><title>Test Page</title></head>
<body>
  <nav><a href="/">Home</a> | <a href="/about">About</a></nav>
  <article>
    <h1>{title}</h1>
    <p>{body}</p>
  </article>
  <footer>© 2026 Example Corp</footer>
</body></html>
"""

RICH_CONTENT = "This is a detailed article about Python agent frameworks. " * 8  # well over 200 chars
THIN_CONTENT  = "Hi."

def rich_html(title="Article", body=RICH_CONTENT):
    return _HTML.format(title=title, body=body)

def thin_html():
    return _HTML.format(title="Page", body=THIN_CONTENT)


# ── _is_thin_content ──────────────────────────────────────────────────────────

class TestIsThinContent:
    def test_empty_string_is_thin(self):
        assert _is_thin_content("") is True

    def test_short_string_is_thin(self):
        assert _is_thin_content("Hello world") is True

    def test_whitespace_only_is_thin(self):
        assert _is_thin_content("   \n\n   \t   ") is True

    def test_threshold_boundary(self):
        # Exactly 200 chars is NOT thin (threshold is < 200)
        assert _is_thin_content("a" * 200) is False

    def test_sufficient_content_is_not_thin(self):
        assert _is_thin_content(RICH_CONTENT) is False

    def test_collapses_whitespace_before_measuring(self):
        # 500 spaces collapse to 1 — still thin
        assert _is_thin_content(" " * 500) is True


# ── _clean_markdown ───────────────────────────────────────────────────────────

class TestCleanMarkdown:
    def test_collapses_excessive_blank_lines(self):
        result = _clean_markdown("paragraph one\n\n\n\n\nparagraph two")
        assert "\n\n\n" not in result
        assert "paragraph one" in result
        assert "paragraph two" in result

    def test_preserves_single_blank_lines(self):
        result = _clean_markdown("line one\n\nline two")
        assert result == "line one\n\nline two"

    def test_strips_leading_and_trailing_whitespace(self):
        result = _clean_markdown("\n\ncontent\n\n")
        assert result == "content"


# ── _html_to_markdown ─────────────────────────────────────────────────────────

class TestHtmlToMarkdown:
    def test_converts_headings(self):
        result = _html_to_markdown("<h1>Title Here</h1>")
        assert "Title Here" in result

    def test_preserves_links(self):
        result = _html_to_markdown('<a href="https://example.com">click here</a>')
        assert "https://example.com" in result
        assert "click here" in result

    def test_ignores_images(self):
        result = _html_to_markdown('<img src="photo.jpg" alt="A photo">')
        assert "photo.jpg" not in result

    def test_converts_paragraphs(self):
        result = _html_to_markdown("<p>Hello world</p>")
        assert "Hello world" in result

    def test_no_line_wrapping(self):
        long_line = "word " * 50
        result = _html_to_markdown(f"<p>{long_line}</p>")
        # Without wrapping every line should be at most one paragraph
        assert "\n" not in result.strip()


# ── fetch_as_markdown ─────────────────────────────────────────────────────────

class TestFetchAsMarkdown:
    def test_returns_markdown_on_successful_static_fetch(self):
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=rich_html()):
            result = fetch_as_markdown("https://example.com")
        assert not result.startswith("ERROR:")
        assert len(result) > 50

    def test_does_not_call_playwright_when_static_fetch_succeeds(self):
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=rich_html()):
            with patch("scripts.fetch_as_markdown._playwright_fetch") as mock_pw:
                fetch_as_markdown("https://example.com")
        mock_pw.assert_not_called()

    def test_falls_back_to_playwright_when_static_is_thin(self):
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=thin_html()):
            with patch("scripts.fetch_as_markdown._playwright_fetch", return_value=rich_html()) as mock_pw:
                result = fetch_as_markdown("https://example.com")
        mock_pw.assert_called_once()
        assert not result.startswith("ERROR:")

    def test_playwright_first_skips_static_fetch(self):
        with patch("scripts.fetch_as_markdown._static_fetch") as mock_static:
            with patch("scripts.fetch_as_markdown._playwright_fetch", return_value=rich_html()):
                result = fetch_as_markdown("https://example.com", playwright_first=True)
        mock_static.assert_not_called()
        assert not result.startswith("ERROR:")

    def test_returns_error_when_both_fetches_fail(self):
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=None):
            with patch("scripts.fetch_as_markdown._playwright_fetch", return_value=None):
                with patch("scripts.fetch_as_markdown.PLAYWRIGHT_AVAILABLE", True):
                    result = fetch_as_markdown("https://example.com")
        assert result.startswith("ERROR:")

    def test_returns_install_hint_when_playwright_not_installed(self):
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=thin_html()):
            with patch("scripts.fetch_as_markdown._playwright_fetch", return_value=None):
                with patch("scripts.fetch_as_markdown.PLAYWRIGHT_AVAILABLE", False):
                    result = fetch_as_markdown("https://example.com")
        assert result.startswith("ERROR:")
        assert "playwright install" in result.lower()

    def test_errors_are_returned_not_raised(self):
        """The contract: errors come back as strings, never as exceptions."""
        with patch("scripts.fetch_as_markdown._static_fetch", return_value=None):
            with patch("scripts.fetch_as_markdown._playwright_fetch", return_value=None):
                with patch("scripts.fetch_as_markdown.PLAYWRIGHT_AVAILABLE", True):
                    result = fetch_as_markdown("https://example.com")
        assert isinstance(result, str)


# ── fetch_api_spec ────────────────────────────────────────────────────────────

class TestFetchApiSpec:
    def _mock_response(self, content_type: str, text: str) -> MagicMock:
        r = MagicMock()
        r.headers = {"content-type": content_type}
        r.text = text
        return r

    def test_returns_raw_json_for_json_content_type(self):
        payload = '{"openapi": "3.0.0", "info": {"title": "Test API"}}'
        with patch("requests.get", return_value=self._mock_response("application/json", payload)):
            result = fetch_api_spec("https://api.example.com/openapi.json")
        assert result == payload

    def test_returns_raw_yaml_for_yaml_content_type(self):
        payload = "openapi: '3.0.0'\ninfo:\n  title: Test API"
        with patch("requests.get", return_value=self._mock_response("application/yaml", payload)):
            result = fetch_api_spec("https://api.example.com/openapi.yaml")
        assert result == payload

    def test_falls_back_to_fetch_as_markdown_for_html(self):
        with patch("requests.get", return_value=self._mock_response("text/html", "<html></html>")):
            with patch("scripts.fetch_as_markdown._static_fetch", return_value=rich_html()):
                result = fetch_api_spec("https://docs.example.com/api")
        assert not result.startswith("ERROR:")

    def test_falls_back_to_fetch_as_markdown_on_request_error(self):
        with patch("requests.get", side_effect=Exception("connection refused")):
            with patch("scripts.fetch_as_markdown._static_fetch", return_value=rich_html()):
                result = fetch_api_spec("https://api.example.com/spec")
        assert not result.startswith("ERROR:")
