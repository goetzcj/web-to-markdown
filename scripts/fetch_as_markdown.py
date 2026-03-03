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

# Silence noisy dependency warnings when pip resolves a compatible-but-not-whitelisted combo.
try:
    import warnings
    from requests.exceptions import RequestsDependencyWarning

    warnings.filterwarnings("ignore", category=RequestsDependencyWarning)
except Exception:
    pass

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

try:
    import lxml.html  # type: ignore
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False


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
    """Extract the primary content using readability when available."""
    if READABILITY_AVAILABLE:
        try:
            return Document(html).summary(html_partial=True)
        except Exception:
            pass
    return html


def _maybe_fix_mojibake(text: str) -> str:
    """Fix common UTF-8/latin-1 mojibake artifacts (â€™, Â, etc.).

    This is a pragmatic heuristic: only attempt the fix when the telltale sequences
    appear, and fall back silently if it doesn't work.
    """

    if "â" not in text and "Â" not in text:
        return text

    try:
        fixed = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return text

    # Only accept the fix if it actually removes the common sequences.
    if fixed.count("â") + fixed.count("Â") < text.count("â") + text.count("Â"):
        return fixed

    return text


def _candidate_html_blocks(html: str) -> list[str]:
    """Return a list of candidate HTML blocks to convert to markdown.

    Readability is great, but on some modern marketing sites it can latch onto a
    single section instead of the full main content. We generate a few candidates
    and later pick the best markdown output.
    """

    candidates: list[str] = []

    # 1) Readability (best when it works).
    candidates.append(_extract_main_content(html))

    if LXML_AVAILABLE:
        try:
            doc = lxml.html.fromstring(html)

            # 2) <main>
            mains = doc.xpath("//main")
            for node in mains[:2]:
                candidates.append(lxml.html.tostring(node, encoding="unicode", method="html"))

            # 3) <article>
            articles = doc.xpath("//article")
            for node in articles[:2]:
                candidates.append(lxml.html.tostring(node, encoding="unicode", method="html"))

            # 4) body (last resort)
            bodies = doc.xpath("//body")
            for node in bodies[:1]:
                candidates.append(lxml.html.tostring(node, encoding="unicode", method="html"))
        except Exception:
            pass

    # Always include full HTML as final fallback.
    candidates.append(html)

    # De-dupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in candidates:
        key = item.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


def _best_markdown_from_html(html: str) -> str:
    """Convert HTML to markdown using the best candidate extraction strategy.

    We score candidates to prefer real article text over navigation/link farms.
    """

    best = ""
    best_score = float("-inf")

    for idx, candidate in enumerate(_candidate_html_blocks(html)):
        md = _clean_markdown(_html_to_markdown(candidate))

        # Estimate "visible" text (strip URLs from markdown links).
        visible = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
        visible = re.sub(r"https?://\S+", "", visible)
        visible = re.sub(r"\s+", " ", visible).strip()

        link_count = md.count("](")
        pipe_count = md.count("|")

        # Base score: visible text length.
        score = float(len(visible))
        # Penalize link-heavy / table-like nav.
        score -= link_count * 30.0
        score -= pipe_count * 2.0

        # Slightly prefer earlier candidates (readability/main/article) when close.
        score -= idx * 5.0

        if score > best_score:
            best = md
            best_score = score

    return best


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
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; WebToMarkdown/1.0)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            timeout=timeout,
        )
        r.raise_for_status()

        # Normalize encoding to reduce mojibake.
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding

        return _maybe_fix_mojibake(r.text)
    except Exception:
        return None


def _playwright_fetch(url: str, wait_ms: int = 3000) -> str | None:
    """Headless Chromium fetch for JS-rendered pages."""
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
            return _maybe_fix_mojibake(html)
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
            md = _best_markdown_from_html(html)
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

    md = _best_markdown_from_html(html)

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
