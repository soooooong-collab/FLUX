"""
Agent Tool — Method DB semantic search.
"""
from app.services.llm.base import ToolDefinition

METHOD_SEARCH_TOOL = ToolDefinition(
    name="search_methods",
    description=(
        "Search the Method DB (strategy frameworks/methodologies) by semantic similarity. "
        "Use this when you need to find relevant strategic frameworks for the current step. "
        "Returns top-k methods with name, category, core_principle, apply_when, avoid_when."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language query describing the strategic need or situation.",
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
