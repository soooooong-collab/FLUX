"""
LLM Router — Step별 최적 모델 라우팅 + 임베딩 프로바이더.

Available API keys에 따라 자동 폴백:
  Claude 키 있음 → Claude 사용 (기본)
  Claude 키 없음 + Gemini 있음 → Gemini 폴백
  둘 다 없으면 → 에러
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)
settings = get_settings()

# Step별 모델 매핑 — 필요에 따라 변경 가능
STEP_MODEL_MAP: dict[str, tuple[str, str]] = {
    # step_key: (provider, model)
    "orchestrator":  ("claude", "claude-sonnet-4-20250514"),
    "s1_goal":       ("claude", "claude-sonnet-4-20250514"),
    "s2_market":     ("gemini", "gemini-2.5-pro"),  # 웹검색 강점
    "s3_target":     ("claude", "claude-sonnet-4-20250514"),
    "s4_competition":("claude", "claude-sonnet-4-20250514"),
    "s5_definition": ("claude", "claude-sonnet-4-20250514"),
    "s6_strategy":   ("claude", "claude-sonnet-4-20250514"),
    "s7_promise":    ("claude", "claude-sonnet-4-20250514"),
    "s8_creative":   ("claude", "claude-sonnet-4-20250514"),
    "slides":        ("claude", "claude-sonnet-4-20250514"),
    "meeting_slides": ("claude", "claude-sonnet-4-20250514"),
}

# Default fallback
DEFAULT_PROVIDER = "claude"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Gemini fallback model for generation tasks
GEMINI_FALLBACK_MODEL = "gemini-2.5-pro"


class FailoverLLMProvider(LLMProvider):
    """Try multiple providers in order until one succeeds."""

    def __init__(self, providers: list[LLMProvider]):
        self.providers = providers

    async def generate(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return await provider.generate(
                    messages=messages,
                    system=system,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "LLM generation failed on %s(%s): %s",
                    provider.__class__.__name__,
                    getattr(provider, "model", "unknown"),
                    str(e),
                )
                continue
        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}") from last_error

    async def embed(self, text: str) -> list[float]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return await provider.embed(text)
            except NotImplementedError:
                continue
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        raise RuntimeError("No embedding-capable provider available in failover chain.")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return await provider.embed_batch(texts)
            except NotImplementedError:
                continue
            except Exception as e:
                last_error = e
                continue
        if last_error:
            raise last_error
        raise RuntimeError("No embedding-capable provider available in failover chain.")


def _has_key(provider: str) -> bool:
    """Check if the API key for a provider is configured."""
    if provider == "claude":
        return bool(settings.ANTHROPIC_API_KEY)
    elif provider == "gemini":
        return bool(settings.GEMINI_API_KEY)
    elif provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    return False


def _provider_chain(provider_name: str, model: str) -> list[tuple[str, str]]:
    """Build ordered provider chain (preferred first, then fallbacks)."""
    chain: list[tuple[str, str]] = []
    if _has_key(provider_name):
        chain.append((provider_name, model))
    else:
        logger.warning("LLM key missing for preferred provider: %s", provider_name)

    fallbacks = [
        ("gemini", GEMINI_FALLBACK_MODEL),
        ("claude", DEFAULT_MODEL),
        ("openai", "gpt-4o"),
    ]
    for fb_provider, fb_model in fallbacks:
        if _has_key(fb_provider) and all(p != fb_provider for p, _ in chain):
            chain.append((fb_provider, fb_model))

    return chain


def _build_provider(provider_name: str, model: str) -> LLMProvider:
    if provider_name == "claude":
        from app.services.llm.claude import ClaudeProvider
        return ClaudeProvider(model=model)
    elif provider_name == "gemini":
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider(model=model)
    elif provider_name == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model)
    raise ValueError(f"Unknown LLM provider: {provider_name}")


def get_llm_for_step(step_key: str) -> LLMProvider:
    """Return the best LLM provider for a given pipeline step.
    Automatically falls back to available providers on key-missing or runtime failure.
    """
    provider_name, model = STEP_MODEL_MAP.get(step_key, (DEFAULT_PROVIDER, DEFAULT_MODEL))
    chain = _provider_chain(provider_name, model)
    if not chain:
        raise RuntimeError("No LLM API key available. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env")

    providers = [_build_provider(provider, model_name) for provider, model_name in chain]
    if len(providers) == 1:
        return providers[0]
    return FailoverLLMProvider(providers)


def get_embedding_provider() -> LLMProvider:
    """Return the embedding provider (Gemini by default)."""
    provider = settings.EMBEDDING_PROVIDER
    if provider == "gemini" and _has_key("gemini"):
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider()
    elif provider == "openai" and _has_key("openai"):
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    # Fallback
    if _has_key("gemini"):
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider()
    raise ValueError(f"No embedding provider available. Set GEMINI_API_KEY.")
