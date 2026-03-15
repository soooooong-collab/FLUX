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

        output_cap = max(max_tokens, 768)
        thinking_budget = max(32, min(128, output_cap // 4))

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=output_cap,
            thinking_config=types.ThinkingConfig(
                include_thoughts=False,
                thinking_budget=thinking_budget,
            ),
        )
        if system:
            config.system_instruction = system

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        text = self._extract_text(response)
        if not text:
            finish_reason = None
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                finish_reason = getattr(candidates[0], "finish_reason", None)
            text = f"[모델 응답이 비어 있어 핵심 결론만 유지합니다. reason={finish_reason}]"

        usage = getattr(response, "usage_metadata", None)
        input_tokens = 0
        output_tokens = 0
        if usage:
            input_tokens = (
                getattr(usage, "prompt_token_count", 0)
                or getattr(usage, "input_token_count", 0)
                or 0
            )
            output_tokens = (
                getattr(usage, "candidates_token_count", 0)
                or getattr(usage, "output_token_count", 0)
                or 0
            )

        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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

    @staticmethod
    def _extract_text(response) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        parts: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in (getattr(content, "parts", None) or []):
                part_text = getattr(part, "text", None)
                if isinstance(part_text, str) and part_text.strip():
                    parts.append(part_text.strip())

        return "\n".join(parts).strip()
