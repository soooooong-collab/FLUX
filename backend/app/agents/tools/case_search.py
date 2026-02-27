"""
Agent Tool — Case DB semantic search.
"""
from app.services.llm.base import ToolDefinition

CASE_SEARCH_TOOL = ToolDefinition(
    name="search_cases",
    description=(
        "Search the Case DB (real advertising campaign case studies) by semantic similarity. "
        "Use this to find relevant campaign references for evidence and inspiration. "
        "Returns top-k cases with brand, campaign_title, problem, insight, solution, outcomes."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query describing the campaign situation or strategy.",
            },
            "industry": {
                "type": "string",
                "description": "Optional: filter by industry (e.g., '식음료', 'IT/테크').",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default: 3).",
                "default": 3,
            },
        },
        "required": ["query"],
    },
)
