"""
Agent Tool — Web search via Serper API.
"""
import httpx

from app.core.config import get_settings
from app.services.llm.base import ToolDefinition

WEB_SEARCH_TOOL = ToolDefinition(
    name="web_search",
    description=(
        "Search the web for current market trends, competitor analysis, consumer insights, "
        "and industry news. Use this for real-time information not available in the internal DB."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query in natural language (Korean or English).",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results (default: 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    },
)


async def execute_web_search(query: str, num_results: int = 5) -> list[dict]:
    """Execute web search via Serper API."""
    settings = get_settings()
    if not settings.SERPER_API_KEY:
        return [{"error": "SERPER_API_KEY not configured"}]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "num": num_results, "gl": "kr", "hl": "ko"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    for item in data.get("organic", [])[:num_results]:
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
        })
    return results
