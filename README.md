# web-to-markdown

![CI](https://github.com/goetzcj/web-to-markdown/actions/workflows/ci.yml/badge.svg)

An agent skill that fetches any webpage and returns clean, content-focused markdown — handling JavaScript-rendered pages automatically so your agent never has to.

Raw HTML is a terrible format for agents. It's bloated with nav menus, cookie banners, sidebars, and scripts that have nothing to do with the actual content. And on modern sites, a plain HTTP request often returns an empty JavaScript shell — the agent sees nothing useful and either hallucinates or gives up.

This skill solves both problems. It uses a two-stage fetch (fast static request first, headless browser fallback if content is thin), then strips boilerplate using the same algorithm as Firefox Reader Mode before converting to markdown. The result is **60–80% fewer tokens** than raw HTML, with only the content that matters.

## Install

Requires Python 3.10+.

```bash
pip install requests readability-lxml html2text playwright
playwright install chromium   # ~200MB one-time download; only needed for JS-heavy pages
```

`playwright` is optional — if a JS-rendered page is encountered without it installed, the error message tells you exactly what to run.

## Quick start

```python
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

# Fetch any page — static first, headless browser fallback if needed
markdown = fetch_as_markdown("https://docs.example.com/api")

# Known JS-heavy target (SPA, Swagger UI, React docs) — skip straight to browser
markdown = fetch_as_markdown("https://app.example.com/swagger", playwright_first=True)

# API docs — returns raw JSON/YAML if the server provides it, markdown otherwise
spec = fetch_api_spec("https://api.example.com/openapi.json")
```

Errors come back as strings prefixed with `"ERROR:"` rather than raised exceptions, so your agent can handle them inline without try/catch.

## CLI

```bash
python scripts/fetch_as_markdown.py https://docs.example.com/getting-started
python scripts/fetch_as_markdown.py https://app.example.com/swagger --playwright-first
python scripts/fetch_as_markdown.py https://api.example.com/openapi.json --api-spec
python scripts/fetch_as_markdown.py https://docs.example.com --output docs.md
```

## Framework support

The core (`scripts/fetch_as_markdown.py`) has no framework dependencies. Wrap it in 5–10 lines for any framework:

### Agno

```python
from scripts.agno_toolkit import WebToMarkdownTools

agent = Agent(tools=[WebToMarkdownTools()])

# For JS-heavy targets:
agent = Agent(tools=[WebToMarkdownTools(playwright_first=True)])
```

Registers two tools: `fetch_page_as_markdown` and `fetch_api_spec_tool`.

### LangChain

```python
from langchain.tools import tool
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

@tool
def fetch_page_as_markdown(url: str) -> str:
    """Fetch a webpage and return clean markdown. Handles JS-rendered pages automatically."""
    return fetch_as_markdown(url)

@tool
def fetch_api_spec_tool(url: str) -> str:
    """Fetch API docs or OpenAPI spec. Returns raw JSON/YAML if available, markdown otherwise."""
    return fetch_api_spec(url)
```

### CrewAI

```python
from crewai.tools import BaseTool
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

class FetchPageAsMarkdownTool(BaseTool):
    name: str = "Fetch Page as Markdown"
    description: str = "Fetch a webpage and return clean markdown. Handles JS-rendered pages automatically."

    def _run(self, url: str) -> str:
        return fetch_as_markdown(url)
```

### OpenAI Agents SDK

```python
from agents import function_tool
from scripts.fetch_as_markdown import fetch_as_markdown

@function_tool
def fetch_page_as_markdown(url: str) -> str:
    """Fetch a webpage and return clean markdown. Handles JS-rendered pages automatically."""
    return fetch_as_markdown(url)
```

See [`references/framework-adapters.md`](references/framework-adapters.md) for all examples in one place.

## How it works

```
fetch_as_markdown(url)
  │
  ├─ Static fetch (fast, ~1s)
  │    └─ readability → html2text → clean markdown
  │         ├─ ≥200 chars of real text? → return it
  │         └─ Thin/empty?              → fall through ↓
  │
  └─ Playwright fetch (headless Chromium, ~5–8s)
       └─ readability → html2text → clean markdown
            ├─ Enough content? → return it
            └─ Still empty?    → ERROR: login wall or bot block
```

"Thin content" means less than 200 characters after whitespace normalization. This catches JS-gated shells without falsely flagging legitimately short pages.

`fetch_api_spec` checks the response `Content-Type` header before converting — if the server returns `application/json` or YAML, it passes the raw spec straight through so agents that can parse OpenAPI natively don't have to deal with a markdown representation of it.

## Claude Code skill

This repo ships as a Claude Code skill (`SKILL.md`). If you're using Claude Code, add it to your project and Claude will automatically fetch and convert pages whenever an agent needs to read web content.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | Static HTTP fetching |
| `readability-lxml` | Boilerplate stripping (Firefox Reader Mode algorithm) |
| `html2text` | HTML → markdown conversion |
| `playwright` | Headless browser fallback for JS-rendered pages |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, how to run the test suite, and how to add a new framework adapter.

## License

MIT
