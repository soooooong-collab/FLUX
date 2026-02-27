"""
Gemini LLM Provider — Google GenAI integration.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse, ToolDefinition

settings = get_settings()


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-2.5-pro"):
        from google import genai
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = model
        self.embedding_model = settings.EMBEDDING_MODEL

    async def generate(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        from google.genai import types

        # Convert messages to Gemini format (simple: last user message as prompt)
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"[{role}]: {content}")
        prompt = "\n\n".join(prompt_parts)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system:
            config.system_instruction = system

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return LLMResponse(
            text=response.text or "",
            model=self.model,
            input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) if hasattr(response, "usage_metadata") else 0,
            output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) if hasattr(response, "usage_metadata") else 0,
        )

    async def embed(self, text: str) -> list[float]:
        response = self.client.models.embed_content(
            model=self.embedding_model,
            contents=text,
        )
        return response.embeddings[0].values

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.models.embed_content(
            model=self.embedding_model,
            contents=texts,
        )
        return [emb.values for emb in response.embeddings]
