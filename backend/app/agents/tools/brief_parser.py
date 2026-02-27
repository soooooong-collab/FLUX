"""
Agent Tool — Brief PDF parser.
"""
from pathlib import Path

from app.services.llm.base import ToolDefinition

BRIEF_PARSE_TOOL = ToolDefinition(
    name="parse_brief_pdf",
    description="Parse an uploaded client brief PDF and extract structured information.",
    input_schema={
        "type": "object",
        "properties": {
            "pdf_path": {
                "type": "string",
                "description": "Path to the uploaded PDF file.",
            },
        },
        "required": ["pdf_path"],
    },
)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
    return "\n\n".join(text_parts)
