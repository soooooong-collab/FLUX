"""
LLM Router — Step별 최적 모델 라우팅 + 임베딩 프로바이더.

Available API keys에 따라 자동 폴백:
  Claude 키 있음 → Claude 사용 (기본)
  Claude 키 없음 + Gemini 있음 → Gemini 폴백
  둘 다 없으면 → 에러
"""
from __future__ import annotations

import logging
from functools import lru_cache

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
}

# Default fallback
DEFAULT_PROVIDER = "claude"
DEFAULT_MODEL = "claude-sonnet-4-20250514"

# Gemini fallback model for generation tasks
GEMINI_FALLBACK_MODEL = "gemini-2.5-pro"


def _has_key(provider: str) -> bool:
    """Check if the API key for a provider is configured."""
    if provider == "claude":
        return bool(settings.ANTHROPIC_API_KEY)
    elif provider == "gemini":
        return bool(settings.GEMINI_API_KEY)
    elif provider == "openai":
        return bool(settings.OPENAI_API_KEY)
    return False


def _resolve_provider(provider_name: str, model: str) -> tuple[str, str]:
    """Resolve to an available provider, with automatic fallback."""
    if _has_key(provider_name):
        return provider_name, model

    # Fallback chain: claude → gemini → openai
    fallbacks = [
        ("gemini", GEMINI_FALLBACK_MODEL),
        ("claude", DEFAULT_MODEL),
        ("openai", "gpt-4o"),
    ]
    for fb_provider, fb_model in fallbacks:
        if fb_provider != provider_name and _has_key(fb_provider):
            logger.warning(
                f"LLM fallback: {provider_name} → {fb_provider} "
                f"(API key for {provider_name} not configured)"
            )
            return fb_provider, fb_model

    raise RuntimeError(
        f"No LLM API key available. Set ANTHROPIC_API_KEY or GEMINI_API_KEY in .env"
    )


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
    Automatically falls back to available providers if preferred one lacks API key.
    """
    provider_name, model = STEP_MODEL_MAP.get(step_key, (DEFAULT_PROVIDER, DEFAULT_MODEL))
    resolved_provider, resolved_model = _resolve_provider(provider_name, model)
    return _build_provider(resolved_provider, resolved_model)


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
