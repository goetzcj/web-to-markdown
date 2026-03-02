#!/usr/bin/env python3
"""
fetch_as_markdown.py
====================
Fetch any URL and return clean markdown. Framework-agnostic.
Can be imported as a module or called from the CLI.

Usage (import):
    from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

Usage (CLI):
    python scripts/fetch_as_markdown.py <url> [--playwright-first] [--api-spec] [--output file.md]

Dependencies:
    pip install requests readability-lxml html2text playwright
    playwright install chromium
"""

import re
import sys
import argparse
import requests
import html2text

try:
    from readability import Document
    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# ── Internal helpers ────────────────────────────────────────────────────────────

def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown. Images are skipped — they're noise for agents."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 0        # no line wrapping
    converter.skip_internal_links = True
    converter.single_line_break = True
    return converter.handle(html).strip()


def _extract_main_content(html: str) -> str:
    """
    Strip nav, ads, sidebars, and footers using the readability algorithm.
    This is the same approach Firefox Reader Mode uses, which means it's
    battle-tested across millions of real-world pages. Falls back to full
    HTML if readability isn't installed.
    """
    if READABILITY_AVAILABLE:
        try:
            return Document(html).summary(html_partial=True)
        except Exception:
            pass
    return html


def _is_thin_content(markdown: str, threshold: int = 200) -> bool:
    """
    Detect JS-gated shells and empty responses.
    Less than 200 chars of real text after whitespace collapse means
    the page didn't actually render any content worth returning.
    """
    return len(re.sub(r'\s+', ' ', markdown).strip()) < threshold


def _clean_markdown(markdown: str) -> str:
    """Post-process to remove common noise patterns from converted markdown."""
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)       # collapse excessive blank lines
    markdown = re.sub(r'^\W{3,}$', '', markdown, flags=re.MULTILINE)  # decorative dividers
    return markdown.strip()


def _static_fetch(url: str, timeout: int = 15) -> str | None:
    """Fast HTTP fetch. Sends a browser-like User-Agent to avoid basic bot blocks."""
    try:
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; WebToMarkdown/1.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        return None


def _playwright_fetch(url: str, wait_ms: int = 3000) -> str | None:
    """
    Headless Chromium fetch. Used when static fetch returns thin content.
    The wait_ms gives JS frameworks time to finish rendering after load.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_ms)
            html = page.content()
            browser.close()
            return html
    except Exception:
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_as_markdown(url: str, playwright_first: bool = False) -> str:
    """
    Fetch a URL and return clean markdown.

    Args:
        url:              Full URL including scheme (https://...)
        playwright_first: Skip static fetch; go straight to headless browser.
                          Use for known JS-heavy targets (SPAs, Swagger UI, etc.)

    Returns:
        Clean markdown string, or an error message prefixed with "ERROR:"
    """
    html = None

    if not playwright_first:
        html = _static_fetch(url)
        if html:
            md = _clean_markdown(_html_to_markdown(_extract_main_content(html)))
            if not _is_thin_content(md):
                return md
            # Thin content detected — fall through to Playwright
            html = None

    html = _playwright_fetch(url)

    if not html:
        if not PLAYWRIGHT_AVAILABLE:
            return (
                "ERROR: Page appears JavaScript-rendered but Playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
        return f"ERROR: Could not fetch {url}. The page may require authentication or block automated access."

    md = _clean_markdown(_html_to_markdown(_extract_main_content(html)))

    if _is_thin_content(md):
        # Readability may have over-stripped structured content (e.g. Swagger UI,
        # API docs, SPAs). Fall back to raw HTML→markdown before declaring failure.
        md = _clean_markdown(_html_to_markdown(html))

    if _is_thin_content(md):
        return (
            f"ERROR: Fetched {url} but content appears to be behind a login wall "
            "or requires user interaction that cannot be automated."
        )

    return md


def fetch_api_spec(url: str) -> str:
    """
    Fetch API documentation or an OpenAPI/Swagger spec.

    Checks the Content-Type header first — if the server returns raw JSON or YAML,
    that's returned directly since agents can often work with OpenAPI specs natively
    without needing markdown conversion. Falls back to fetch_as_markdown otherwise.

    Args:
        url: URL of the API docs page or raw spec file

    Returns:
        Raw spec (JSON/YAML) or clean markdown of the docs page
    """
    try:
        r = requests.get(url, headers={
            "Accept": "application/json,application/yaml,text/yaml,text/html",
            "User-Agent": "Mozilla/5.0 (compatible; WebToMarkdown/1.0)",
        }, timeout=15)
        ct = r.headers.get("content-type", "")
        if any(t in ct for t in ["application/json", "yaml", "text/plain"]):
            return r.text
    except Exception:
        pass

    return fetch_as_markdown(url)


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch a URL and return clean markdown.")
    parser.add_argument("url", help="URL to fetch (include https://)")
    parser.add_argument("--playwright-first", action="store_true",
                        help="Skip static fetch; use headless browser immediately")
    parser.add_argument("--api-spec", action="store_true",
                        help="Treat as API docs — return raw JSON/YAML if available")
    parser.add_argument("--output", "-o", metavar="FILE",
                        help="Write output to file instead of stdout")
    args = parser.parse_args()

    result = fetch_api_spec(args.url) if args.api_spec else fetch_as_markdown(
        args.url, playwright_first=args.playwright_first
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Written to {args.output}")
    else:
        print(result)
