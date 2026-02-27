"""
LLM Provider — Abstract base class for multi-LLM support.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[dict] | None = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
