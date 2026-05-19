"""Abstract LLM adapter interface and supporting types."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkGameState,
    ModelConfig,
)


# ─── Message Type ─────────────────────────────────────────────────────────────


@dataclass
class Message:
    """A single message in the LLM conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


# ─── Errors ───────────────────────────────────────────────────────────────────


@dataclass
class LLMError(Exception):
    """Structured error from an LLM adapter."""

    error_type: Literal["timeout", "rate_limit", "api_error", "parse_error", "connection_error", "refusal"]
    details: str = ""
    retry_after: float | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        parts = [f"LLMError({self.error_type})"]
        if self.details:
            parts.append(self.details)
        if self.status_code:
            parts.append(f"status={self.status_code}")
        return ": ".join(parts)


# ─── Abstract Adapter ─────────────────────────────────────────────────────────


class LLMAdapter(ABC):
    """Abstract interface for LLM providers."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.name = config.name
        self._resolve_api_key()

    def _resolve_api_key(self) -> None:
        """Resolve API key from config or environment variable."""
        if self.config.api_key:
            self.api_key = self.config.api_key
        elif self.config.api_key_env:
            self.api_key = os.environ.get(self.config.api_key_env, "")
        else:
            self.api_key = ""

    @abstractmethod
    async def get_action(
        self,
        state: BenchmarkGameState,
        history: list[Message],
        available_actions: list[AvailableAction],
    ) -> tuple[ActionResponse, str]:
        """Query the LLM for an action.

        Returns:
            Tuple of (parsed ActionResponse, raw response text)
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connectivity to the LLM provider. Returns True if reachable."""
        ...

    @abstractmethod
    def get_token_count(self, messages: list[Message]) -> int:
        """Estimate token count for a list of messages."""
        ...

    def get_model_info(self) -> dict[str, Any]:
        """Return metadata about this adapter."""
        return {
            "name": self.config.name,
            "provider": self.config.provider,
            "model": self.config.model,
            "context_window": self.config.context_window,
        }


# ─── Adapter Factory ──────────────────────────────────────────────────────────


def create_adapter(config: ModelConfig) -> LLMAdapter:
    """Create the appropriate LLM adapter based on provider config."""
    if config.provider in ("openai", "ollama", "custom"):
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        return OpenAICompatAdapter(config)
    elif config.provider == "anthropic":
        from terminus.benchmark.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(config)
    elif config.provider == "google":
        from terminus.benchmark.adapters.google import GoogleAdapter
        return GoogleAdapter(config)
    else:
        raise ValueError(f"Unknown provider: {config.provider}")
