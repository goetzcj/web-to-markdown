# Framework Adapter Examples

The core fetch logic lives in `scripts/fetch_as_markdown.py` with no framework dependencies.
Adding support for a new framework is always the same pattern: import the core functions
and wrap them in your framework's tool format.

## LangChain

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

## CrewAI

```python
from crewai.tools import BaseTool
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

class FetchPageAsMarkdownTool(BaseTool):
    name: str = "Fetch Page as Markdown"
    description: str = (
        "Fetch a webpage and return clean markdown. "
        "Handles JavaScript-rendered pages automatically via headless browser fallback."
    )

    def _run(self, url: str) -> str:
        return fetch_as_markdown(url)

class FetchApiSpecTool(BaseTool):
    name: str = "Fetch API Spec"
    description: str = (
        "Fetch API documentation or an OpenAPI/Swagger spec. "
        "Returns raw JSON/YAML if available, clean markdown otherwise."
    )

    def _run(self, url: str) -> str:
        return fetch_api_spec(url)
```

## OpenAI Agents SDK

```python
from agents import function_tool
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec

@function_tool
def fetch_page_as_markdown(url: str) -> str:
    """Fetch a webpage and return clean markdown. Handles JS-rendered pages automatically."""
    return fetch_as_markdown(url)

@function_tool
def fetch_api_spec_tool(url: str) -> str:
    """Fetch API docs or OpenAPI spec. Returns raw JSON/YAML if available, markdown otherwise."""
    return fetch_api_spec(url)
```

## Generic / Standalone

```python
# No framework needed — just import and call directly
from scripts.fetch_as_markdown import fetch_as_markdown

content = fetch_as_markdown("https://docs.example.com/api-reference")
print(content)
```
