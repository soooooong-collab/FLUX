"""
Claude LLM Provider — Anthropic API integration.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse, ToolDefinition

settings = get_settings()


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = model

    async def generate(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]

        response = await self.client.messages.create(**kwargs)

        text_parts = []
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return LLMResponse(
            text="\n".join(text_parts),
            model=self.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            tool_calls=tool_calls if tool_calls else None,
        )

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Claude does not provide embeddings. Use Gemini or OpenAI.")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Claude does not provide embeddings. Use Gemini or OpenAI.")
