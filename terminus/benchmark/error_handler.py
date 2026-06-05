"""Error handler — retry logic, DQ tracking, and response validation."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any

from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    Reasoning,
    ReasoningFactor,
    ReasoningFactorType,
)


class DisqualificationError(Exception):
    """Raised when a player is disqualified."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class ErrorHandlerConfig:
    """Configuration for error handling thresholds."""

    max_retries_json: int = 3
    max_retries_schema: int = 2
    max_retries_timeout: int = 1
    consecutive_invalid_dq: int = 10
    refusal_dq: int = 5
    rate_limit_base_delay: float = 1.0
    rate_limit_max_delay: float = 60.0


@dataclass
class ErrorStats:
    """Tracks error statistics for a game."""

    total_valid: int = 0
    total_invalid: int = 0
    total_refusals: int = 0
    total_timeouts: int = 0
    total_rate_limits: int = 0
    consecutive_invalid: int = 0
    dq_reason: str | None = None


class ErrorHandler:
    """Handles LLM response errors with retry, coercion, and DQ logic."""

    def __init__(self, config: ErrorHandlerConfig | None = None):
        self._config = config or ErrorHandlerConfig()
        self._stats = ErrorStats()
        self._rate_limit_attempt = 0

    @property
    def stats(self) -> ErrorStats:
        return self._stats

    @property
    def is_disqualified(self) -> bool:
        return self._stats.dq_reason is not None

    @property
    def dq_reason(self) -> str | None:
        return self._stats.dq_reason

    @property
    def consecutive_invalid(self) -> int:
        return self._stats.consecutive_invalid

    @property
    def total_invalid(self) -> int:
        return self._stats.total_invalid

    @property
    def total_refusals(self) -> int:
        return self._stats.total_refusals

    async def handle_response(
        self,
        adapter: Any,
        state: BenchmarkGameState,
        history: list[Any],
        available_actions: list[AvailableAction],
    ) -> tuple[ActionResponse, str, int]:
        """Get valid action from LLM with full error handling pipeline.

        Returns:
            (parsed_response, raw_text, retry_count)

        Raises:
            DisqualificationError: If DQ threshold reached.
        """
        from terminus.benchmark.agent import LLMError
        from terminus.benchmark.prompt import build_retry_prompt
        from terminus.benchmark.response_parser import parse_action_response

        retry_count = 0
        last_error = ""

        for attempt in range(self._config.max_retries_json + 1):
            try:
                # Call the adapter
                response, raw_text = await adapter.get_action(state, history, available_actions)

                # Success — reset consecutive invalid counter
                self.record_valid()
                self._rate_limit_attempt = 0
                return response, raw_text, retry_count

            except LLMError as e:
                if e.error_type == "timeout":
                    self._stats.total_timeouts += 1
                    if attempt < self._config.max_retries_timeout:
                        retry_count += 1
                        last_error = f"Timeout: {e}"
                        continue
                    # Max timeout retries exhausted
                    self._record_invalid_and_check_dq("timeout")
                    return self._pass_action(), f"TIMEOUT: {e}", retry_count

                elif e.error_type == "rate_limit":
                    self._stats.total_rate_limits += 1
                    delay = self._get_rate_limit_delay(e)
                    await asyncio.sleep(delay)
                    self._rate_limit_attempt += 1
                    retry_count += 1
                    continue

                elif e.error_type == "refusal":
                    self._stats.total_refusals += 1
                    self._check_refusal_dq()
                    self._record_invalid_and_check_dq("refusal")
                    return self._pass_action(), f"REFUSAL: {e}", retry_count

                elif e.error_type == "parse_error":
                    # Try to salvage the raw text
                    raw_text = str(e)
                    try:
                        response = parse_action_response(raw_text)
                        self.record_valid()
                        return response, raw_text, retry_count
                    except Exception:
                        pass

                    # Send retry prompt
                    retry_count += 1
                    last_error = str(e)
                    if attempt < self._config.max_retries_json:
                        # Add retry prompt to history for next attempt
                        retry_msg = build_retry_prompt(last_error, attempt + 1, self._config.max_retries_json)
                        history = list(history) + [_make_retry_message(retry_msg)]
                        continue

                    # All retries exhausted
                    self._record_invalid_and_check_dq("parse_error")
                    return self._pass_action(), f"PARSE_ERROR: {last_error}", retry_count

                else:
                    # Generic API error
                    retry_count += 1
                    last_error = str(e)
                    if attempt < self._config.max_retries_json:
                        continue
                    self._record_invalid_and_check_dq("api_error")
                    return self._pass_action(), f"API_ERROR: {last_error}", retry_count

            except Exception as e:
                retry_count += 1
                last_error = str(e)
                if attempt < self._config.max_retries_json:
                    continue
                self._record_invalid_and_check_dq("unknown_error")
                return self._pass_action(), f"ERROR: {last_error}", retry_count

        # Should not reach here, but safety fallback
        self._record_invalid_and_check_dq("max_retries_exhausted")
        return self._pass_action(), f"MAX_RETRIES: {last_error}", retry_count

    def record_valid(self) -> None:
        """Record a valid action — resets consecutive invalid counter."""
        self._stats.total_valid += 1
        self._stats.consecutive_invalid = 0

    def record_invalid(self, error_type: str) -> None:
        """Record an invalid action (e.g., engine rejection after parsing)."""
        self._record_invalid_and_check_dq(error_type)

    def _record_invalid_and_check_dq(self, error_type: str) -> None:
        """Record invalid and check if DQ threshold reached."""
        self._stats.total_invalid += 1
        self._stats.consecutive_invalid += 1

        if self._stats.consecutive_invalid >= self._config.consecutive_invalid_dq:
            self._stats.dq_reason = (
                f"Disqualified: {self._stats.consecutive_invalid} consecutive invalid actions "
                f"(threshold: {self._config.consecutive_invalid_dq})"
            )
            raise DisqualificationError(self._stats.dq_reason)

    def _check_refusal_dq(self) -> None:
        """Check if refusal DQ threshold reached."""
        if self._stats.total_refusals >= self._config.refusal_dq:
            self._stats.dq_reason = (
                f"Disqualified: {self._stats.total_refusals} refusals "
                f"(threshold: {self._config.refusal_dq})"
            )
            raise DisqualificationError(self._stats.dq_reason)

    def _get_rate_limit_delay(self, error: Any) -> float:
        """Calculate exponential backoff delay for rate limiting."""
        base = self._config.rate_limit_base_delay
        delay = base * (2 ** self._rate_limit_attempt)
        delay = min(delay, self._config.rate_limit_max_delay)
        # Add jitter ±20%
        jitter = delay * 0.2 * (2 * random.random() - 1)
        return max(0.1, delay + jitter)

    def _pass_action(self) -> ActionResponse:
        """Create a fallback PASS action."""
        return ActionResponse(
            action=BenchmarkActionType.PASS,
            params={},
            reasoning=Reasoning(factors=[
                ReasoningFactor(factor=ReasoningFactorType.IMMEDIATE_SURVIVAL, weight=1.0),
            ]),
        )


def _make_retry_message(content: str) -> Any:
    """Create a message object for retry prompts."""
    from terminus.benchmark.agent import Message
    return Message(role="user", content=content)
