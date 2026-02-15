"""
Web Tools

Provides web search and fetch capabilities using free services.
- Web search via DuckDuckGo (no API key required)
- Web fetch via requests + BeautifulSoup
"""

import re
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

from .base import BaseTool, ToolResult, ToolParam, ToolCategory, register_tool

# Lazy imports to handle missing dependencies gracefully
REQUESTS_AVAILABLE = False
BS4_AVAILABLE = False
DDGS_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    pass

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    pass

try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    pass


def html_to_markdown(soup) -> str:
    """Convert HTML soup to readable markdown-ish text."""
    # Remove script and style elements
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        element.decompose()

    # Get text
    text = soup.get_text(separator='\n', strip=True)

    # Clean up whitespace
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            lines.append(line)

    return '\n\n'.join(lines)


@register_tool
class WebFetchTool(BaseTool):
    """
    Fetch and parse a web page.

    Returns the page content as readable text.
    Uses requests + BeautifulSoup (free, no API key).
    """

    name = "web_fetch"
    description = "Fetch a web page and return its content as text"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="url",
            type="string",
            description="URL to fetch",
            required=True,
        ),
        ToolParam(
            name="selector",
            type="string",
            description="CSS selector to filter content (optional)",
            required=False,
            default=None,
        ),
        ToolParam(
            name="max_length",
            type="int",
            description="Maximum content length to return",
            required=False,
            default=10000,
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Fetch the web page."""
        url = params["url"]
        selector = params.get("selector")
        max_length = params.get("max_length", 10000)

        if not REQUESTS_AVAILABLE:
            return ToolResult.fail(
                "requests package not installed. Run: pip install requests"
            )

        if not BS4_AVAILABLE:
            return ToolResult.fail(
                "beautifulsoup4 package not installed. Run: pip install beautifulsoup4"
            )

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = "https://" + url
            elif parsed.scheme not in ('http', 'https'):
                return ToolResult.fail(f"Invalid URL scheme: {parsed.scheme}")
        except Exception as e:
            return ToolResult.fail(f"Invalid URL: {str(e)}")

        # Fetch page
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            return ToolResult.fail("Request timed out")
        except requests.exceptions.RequestException as e:
            return ToolResult.fail(f"Request failed: {str(e)}")

        # Parse HTML
        try:
            soup = BeautifulSoup(response.text, 'lxml')
        except Exception:
            # Fallback to html.parser
            soup = BeautifulSoup(response.text, 'html.parser')

        # Apply selector if provided
        if selector:
            elements = soup.select(selector)
            if not elements:
                return ToolResult.fail(f"No elements found matching selector: {selector}")
            # Create new soup from selected elements
            from bs4 import BeautifulSoup as BS
            combined = BS("", 'html.parser')
            for el in elements:
                combined.append(el)
            soup = combined

        # Convert to text
        content = html_to_markdown(soup)

        # Truncate if needed
        truncated = False
        if len(content) > max_length:
            content = content[:max_length]
            truncated = True

        # Get title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        return ToolResult.ok(
            data={
                "url": url,
                "title": title,
                "content": content,
                "length": len(content),
                "truncated": truncated,
            },
            summary=f"Fetched {url} ({len(content)} chars)" +
                    (" [truncated]" if truncated else ""),
        )


@register_tool
class WebSearchTool(BaseTool):
    """
    Search the web using DuckDuckGo.

    Returns search results with titles, URLs, and snippets.
    Free, no API key required.
    """

    name = "web_search"
    description = "Search the web using DuckDuckGo (free, no API key)"
    category = ToolCategory.READ_ONLY

    parameters = [
        ToolParam(
            name="query",
            type="string",
            description="Search query",
            required=True,
        ),
        ToolParam(
            name="max_results",
            type="int",
            description="Maximum number of results",
            required=False,
            default=10,
        ),
        ToolParam(
            name="region",
            type="string",
            description="Region for results (e.g., 'us-en', 'uk-en')",
            required=False,
            default="wt-wt",  # No region
        ),
    ]

    def execute(self, **params) -> ToolResult:
        """Search the web."""
        query = params["query"]
        max_results = params.get("max_results", 10)
        region = params.get("region", "wt-wt")

        if not DDGS_AVAILABLE:
            return ToolResult.fail(
                "duckduckgo-search package not installed. Run: pip install duckduckgo-search"
            )

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region=region,
                ))

            # Format results
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })

            return ToolResult.ok(
                data={
                    "query": query,
                    "results": formatted,
                    "count": len(formatted),
                },
                summary=f"Found {len(formatted)} results for '{query}'",
            )

        except Exception as e:
            return ToolResult.fail(f"Search failed: {str(e)}")


# Convenience functions
def web_fetch(url: str, selector: Optional[str] = None) -> ToolResult:
    """Fetch a web page."""
    tool = WebFetchTool()
    return tool(url=url, selector=selector)


def web_search(query: str, max_results: int = 10) -> ToolResult:
    """Search the web."""
    tool = WebSearchTool()
    return tool(query=query, max_results=max_results)
