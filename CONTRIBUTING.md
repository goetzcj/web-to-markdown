# Contributing

## Setup

Requires Python 3.10+.

```bash
git clone https://github.com/goetzcj/web-to-markdown.git
cd web-to-markdown
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
playwright install chromium   # optional; only needed to manually test JS-heavy pages
```

## Running tests

```bash
# All tests (no network calls, no browser — everything is mocked)
python -m pytest tests/ -v

# Single test
python -m pytest tests/test_fetch_as_markdown.py::TestFetchAsMarkdown::test_falls_back_to_playwright_when_static_is_thin -v
```

## Adding a framework adapter

The core logic lives entirely in `scripts/fetch_as_markdown.py` with no framework dependencies. Adding support for a new framework is always the same pattern:

1. Create `scripts/<framework>_toolkit.py`
2. Import `fetch_as_markdown` and/or `fetch_api_spec` from `scripts.fetch_as_markdown`
3. Wrap them in your framework's tool format — typically 5–10 lines
4. Add an example to `references/framework-adapters.md`

See `scripts/agno_toolkit.py` as a reference implementation.

## Submitting a pull request

- Keep changes focused — one fix or feature per PR
- If you're adding a framework adapter, include a usage example in `references/framework-adapters.md`
- All tests must pass (`python -m pytest tests/ -v`)
