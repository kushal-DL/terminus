"""Token counting utilities per LLM provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminus.benchmark.agent import Message

logger = logging.getLogger(__name__)

# Lazy-loaded tiktoken module
_tiktoken = None


def _get_tiktoken():
    """Lazy-load tiktoken to avoid import cost when not needed."""
    global _tiktoken
    if _tiktoken is None:
        try:
            import tiktoken
            _tiktoken = tiktoken
        except ImportError:
            logger.warning("tiktoken not installed — falling back to character estimation for OpenAI models")
            _tiktoken = False  # type: ignore[assignment]
    return _tiktoken


# ─── Encoding Selection ───────────────────────────────────────────────────────

# Model → tiktoken encoding name mapping
_MODEL_ENCODINGS: dict[str, str] = {
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "o1": "o200k_base",
    "o1-mini": "o200k_base",
    "o1-preview": "o200k_base",
    "o3": "o200k_base",
    "o3-mini": "o200k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


def get_encoding_for_model(model: str) -> str:
    """Get the tiktoken encoding name for a model."""
    # Exact match
    if model in _MODEL_ENCODINGS:
        return _MODEL_ENCODINGS[model]
    # Prefix match
    for prefix, encoding in _MODEL_ENCODINGS.items():
        if model.startswith(prefix):
            return encoding
    # Default for OpenAI models
    return "o200k_base"


# ─── Token Counting ──────────────────────────────────────────────────────────


def count_tokens(text: str, provider: str, model: str = "") -> int:
    """Count tokens for a text string.

    Args:
        text: The text to count tokens for.
        provider: The provider name ("openai", "anthropic", "google", "ollama").
        model: The model identifier (used for OpenAI encoding selection).

    Returns:
        Estimated token count.
    """
    if provider == "openai":
        return _count_tokens_tiktoken(text, model)
    else:
        # Character estimation for non-OpenAI providers
        return _estimate_tokens(text)


def count_messages_tokens(messages: "list[Message]", provider: str, model: str = "") -> int:
    """Count total tokens across a list of messages.

    Includes per-message overhead (~4 tokens for role/formatting per message in OpenAI).
    """
    total = 0
    for msg in messages:
        total += count_tokens(msg.content, provider, model)
        # Add per-message overhead (role tokens + formatting)
        total += 4
    # Add conversation overhead
    total += 3
    return total


# ─── Provider-specific implementations ────────────────────────────────────────


def _count_tokens_tiktoken(text: str, model: str) -> int:
    """Count tokens using tiktoken (OpenAI models)."""
    tk = _get_tiktoken()
    if not tk:
        return _estimate_tokens(text)

    encoding_name = get_encoding_for_model(model)
    try:
        encoding = tk.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        return _estimate_tokens(text)


def _estimate_tokens(text: str) -> int:
    """Estimate tokens using character count (÷4 for English text).

    This is a rough approximation suitable for Anthropic, Google, and local models
    where exact tokenization isn't available.
    """
    if not text:
        return 0
    # ~4 characters per token for English text is a reasonable approximation
    return max(1, len(text) // 4)
