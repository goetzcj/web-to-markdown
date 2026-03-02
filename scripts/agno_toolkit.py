"""
agno_toolkit.py
===============
Agno-specific wrapper for the web-to-markdown skill.

Usage:
    from scripts.agno_toolkit import WebToMarkdownTools

    agent = Agent(tools=[WebToMarkdownTools()])

    # For known JS-heavy targets (SPAs, Swagger UI):
    agent = Agent(tools=[WebToMarkdownTools(playwright_first=True)])
"""

from agno.tools import Toolkit
from agno.utils.log import logger
from scripts.fetch_as_markdown import fetch_as_markdown, fetch_api_spec


class WebToMarkdownTools(Toolkit):
    """
    Agno Toolkit: fetch any webpage and return clean markdown.
    Handles JS-rendered pages transparently via headless browser fallback.
    """

    def __init__(self, playwright_first: bool = False):
        """
        Args:
            playwright_first: Always use headless browser instead of trying
                              a static fetch first. Slower (~5-8s vs ~1s) but
                              reliable for SPAs and Swagger UI instances.
        """
        super().__init__(name="web_to_markdown")
        self.playwright_first = playwright_first
        self.register(self.fetch_page_as_markdown)
        self.register(self.fetch_api_spec_tool)

    def fetch_page_as_markdown(self, url: str) -> str:
        """
        Fetch a webpage and return its content as clean markdown.

        Automatically handles JavaScript-rendered pages — if a fast static
        fetch returns insufficient content, a headless browser is used as
        a fallback. The agent never needs to manage this distinction.

        Args:
            url: Full URL of the page to fetch (must include https://)

        Returns:
            Clean markdown of the page content, or an error message.
        """
        logger.info(f"[web-to-markdown] fetch_page_as_markdown: {url}")
        return fetch_as_markdown(url, playwright_first=self.playwright_first)

    def fetch_api_spec_tool(self, url: str) -> str:
        """
        Fetch API documentation or an OpenAPI/Swagger spec.

        Returns raw JSON/YAML if the server provides it directly (useful for
        OpenAPI specs that agents can parse natively). Otherwise returns clean
        markdown of the docs page.

        Args:
            url: URL of the API docs page or raw spec file

        Returns:
            Raw spec (JSON/YAML) or clean markdown of the docs page.
        """
        logger.info(f"[web-to-markdown] fetch_api_spec: {url}")
        return fetch_api_spec(url)
