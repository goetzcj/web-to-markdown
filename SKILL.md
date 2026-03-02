---
name: web-to-markdown
description: Use this skill whenever an agent needs to read a webpage, fetch API documentation, load example code from a URL, or access an OpenAPI/Swagger spec. Trigger this skill immediately if an agent reports a page is "JavaScript heavy", returns empty content, or gives up and searches for alternatives — that's exactly the problem this skill solves. Also use when pointing any agent at documentation sites, GitHub READMEs, blog posts, or technical references where raw HTML would waste tokens. Produces clean agent-readable markdown with 60-80% fewer tokens than raw HTML by stripping navigation, ads, scripts, and boilerplate using the same algorithm as Firefox Reader Mode.
compatibility: pip install requests readability-lxml html2text playwright && playwright install chromium
---

# Web-to-Markdown Skill

## What this skill does and why

Agents struggle with two related web fetching problems. First, many modern sites render their content with JavaScript — a plain HTTP request returns an empty shell, so the agent sees nothing useful and gives up. Second, even when content *is* returned, raw HTML is bloated with navigation menus, cookie banners, sidebars, and scripts that have nothing to do with the actual content. Both problems waste tokens and degrade agent performance.

This skill solves both by using a two-stage fetch: fast static request first, automatic headless browser fallback if the content is thin. A readability pass (Firefox Reader Mode algorithm) then strips boilerplate before markdown conversion. The agent always gets clean, content-focused markdown — it never has to manage the fallback logic itself.

## Scripts

All scripts are in `scripts/`. Use them by importing or running from CLI.

### `scripts/fetch_as_markdown.py` — the core tool

This is the main script. It has no framework dependencies and can be used standalone, imported into any agent framework, or called from the command line.

```python
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

# General page — tries static fetch, falls back to Playwright automatically
markdown = fetch_as_markdown("https://docs.example.com/api")

# Known JS-heavy site (SPA, Swagger UI, React docs) — skip straight to Playwright
markdown = fetch_as_markdown("https://app.example.com/swagger", playwright_first=True)

# API spec — returns raw JSON/YAML if available, clean markdown otherwise
spec = fetch_api_spec("https://api.example.com/openapi.json")
```

**CLI:**
```bash
python scripts/fetch_as_markdown.py https://docs.example.com/getting-started
python scripts/fetch_as_markdown.py https://app.example.com/swagger --playwright-first
python scripts/fetch_as_markdown.py https://api.example.com/openapi.json --api-spec
python scripts/fetch_as_markdown.py https://docs.example.com --output docs.md
```

**Return value:** Clean markdown string, or a string starting with `ERROR:` describing what went wrong. Errors are returned rather than raised so agents can handle them gracefully without try/catch.

### `scripts/agno_toolkit.py` — Agno wrapper

```python
from scripts.agno_toolkit import WebToMarkdownTools

agent = Agent(tools=[WebToMarkdownTools()])

# For targets you know are JS-heavy (SPAs, Swagger UI instances):
agent = Agent(tools=[WebToMarkdownTools(playwright_first=True)])
```

Registers two tools: `fetch_page_as_markdown` and `fetch_api_spec_tool`.

## How the fetch strategy works

```
fetch_as_markdown(url)
  │
  ├─ Static fetch (fast, ~1s)
  │    └─ readability → html2text → clean markdown
  │         ├─ Enough content? → return it
  │         └─ Thin/empty? → fall through ↓
  │
  └─ Playwright fetch (headless Chromium, ~5-8s)
       └─ readability → html2text → clean markdown
            ├─ Enough content? → return it
            └─ Still empty? → ERROR: login wall or hard bot block
```

"Thin content" means less than 200 characters of real text after whitespace normalization. This threshold catches JS-gated shells without falsely flagging legitimately short pages.

## Other agent frameworks

If you're using a framework other than Agno, see `references/framework-adapters.md` for LangChain and CrewAI wrapper examples. The pattern is always the same: import `fetch_as_markdown` from the core script and wrap it in your framework's tool format — usually 5-10 lines.

## Dependencies

```bash
pip install requests readability-lxml html2text playwright
playwright install chromium  # ~200MB one-time download
```

`playwright` is only needed for JS-heavy page support. The skill degrades gracefully without it — if a JS-rendered page is encountered and Playwright isn't installed, the error message explains exactly what to install.
