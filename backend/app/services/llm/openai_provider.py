"""
OpenAI LLM Provider — GPT integration.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse, ToolDefinition

settings = get_settings()


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o"):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model

    async def generate(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        formatted.extend(messages)

        kwargs: dict = {
            "model": self.model,
            "messages": formatted,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = None
        if choice.message.tool_calls:
            import json
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                }
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            text=choice.message.content or "",
            model=self.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            tool_calls=tool_calls,
        )

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [d.embedding for d in response.data]
