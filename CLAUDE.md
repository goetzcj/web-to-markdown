# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code skill (`SKILL.md`) that gives agents a clean, framework-agnostic way to fetch webpages as markdown. The core logic is in `scripts/fetch_as_markdown.py`; framework-specific wrappers (Agno, LangChain, CrewAI, etc.) import from it.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # includes test deps
playwright install chromium                # one-time ~200MB; only needed for JS-heavy pages
```

## Running the script

```bash
# Basic fetch
python scripts/fetch_as_markdown.py https://docs.example.com/api

# Skip static fetch, go straight to headless browser (SPAs, Swagger UI)
python scripts/fetch_as_markdown.py https://app.example.com/swagger --playwright-first

# Return raw JSON/YAML if the server provides it
python scripts/fetch_as_markdown.py https://api.example.com/openapi.json --api-spec

# Save to file
python scripts/fetch_as_markdown.py https://docs.example.com --output docs.md
```

## Architecture

**Two-stage fetch strategy** in `fetch_as_markdown()`:
1. Static HTTP request (~1s) → readability strip → html2text → if ≥200 chars of text, return it
2. If thin/empty, fall back to Playwright headless Chromium (~5-8s) → same pipeline
3. If still thin after Playwright, return an `ERROR:` string

**Key design decisions:**
- Errors are returned as strings prefixed with `"ERROR:"`, never raised — agents don't need try/catch
- Images are stripped from markdown output (noise for agents)
- `_is_thin_content()` threshold is 200 chars after whitespace collapse
- `fetch_api_spec()` checks `Content-Type` first; returns raw JSON/YAML directly when the server sends it (agents can often parse OpenAPI specs natively)
- `playwright_first=True` skips the static fetch entirely — use for known SPAs or Swagger UI instances

**Adding a new framework adapter:** Import `fetch_as_markdown` and `fetch_api_spec` from `scripts.fetch_as_markdown` and wrap in your framework's tool format. See `references/framework-adapters.md` for LangChain, CrewAI, and OpenAI Agents SDK examples (~5–10 lines each).

## Tests

```bash
python -m pytest tests/ -v                  # full suite (no network, no browser — all mocked)
python -m pytest tests/test_fetch_as_markdown.py::TestFetchAsMarkdown -v   # one class
```

## Skill definition

`SKILL.md` uses frontmatter (`name`, `description`, `compatibility`) consumed by Claude Code's skill system. The `description` field controls when the skill is auto-triggered.
