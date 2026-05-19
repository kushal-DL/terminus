"""Google Generative AI adapter (Gemini models)."""

from __future__ import annotations

import json
import logging

import httpx

from terminus.benchmark.agent import LLMAdapter, LLMError, Message
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkGameState,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class GoogleAdapter(LLMAdapter):
    """Adapter for Google Generative AI (Gemini) API."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        base = config.endpoint.rstrip("/") if config.endpoint else self.BASE_URL
        self._base_url = base
        self._generate_url = f"{base}/models/{config.model}:generateContent"
        self._count_url = f"{base}/models/{config.model}:countTokens"

    async def get_action(
        self,
        state: BenchmarkGameState,
        history: list[Message],
        available_actions: list[AvailableAction],
    ) -> tuple[ActionResponse, str]:
        from terminus.benchmark.prompt import build_system_prompt, build_turn_message
        from terminus.benchmark.response_parser import parse_action_response

        system_prompt = build_system_prompt()
        turn_message = build_turn_message(state, available_actions)

        contents = self._build_contents(history, turn_message)
        raw_text = await self._call_api(system_prompt, contents)
        parsed = parse_action_response(raw_text)
        return parsed, raw_text

    async def test_connection(self) -> bool:
        try:
            contents = [{"role": "user", "parts": [{"text": "Reply with just 'ok'."}]}]
            payload = {
                "contents": contents,
                "generationConfig": {"maxOutputTokens": 5, "temperature": 0},
            }
            params = {"key": self.api_key}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._generate_url, json=payload, params=params)
                return resp.status_code == 200
        except Exception:
            return False

    def get_token_count(self, messages: list[Message]) -> int:
        from terminus.benchmark.tokens import count_messages_tokens
        return count_messages_tokens(messages, "google", self.config.model)

    async def count_tokens_api(self, text: str) -> int:
        """Use Google's countTokens API for accurate counting."""
        payload = {"contents": [{"parts": [{"text": text}]}]}
        params = {"key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._count_url, json=payload, params=params)
                if resp.status_code == 200:
                    return resp.json().get("totalTokens", 0)
        except Exception:
            pass
        # Fallback to estimation
        return len(text) // 4

    def _build_contents(
        self,
        history: list[Message],
        turn_message: str,
    ) -> list[dict]:
        contents: list[dict] = []
        for m in history:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        contents.append({"role": "user", "parts": [{"text": turn_message}]})
        return contents

    async def _call_api(self, system_prompt: str, contents: list[dict]) -> str:
        payload: dict = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 500,
                "responseMimeType": "application/json",
            },
        }
        params = {"key": self.api_key}
        timeout = self.config.timeout_seconds

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(self._generate_url, json=payload, params=params)
        except httpx.TimeoutException:
            raise LLMError("timeout", f"Request timed out after {timeout}s")
        except httpx.ConnectError:
            raise LLMError("connection_error", f"Cannot connect to {self._generate_url}")

        if resp.status_code == 429:
            raise LLMError("rate_limit", "Rate limited", retry_after=5.0, status_code=429)
        elif resp.status_code >= 500:
            raise LLMError("api_error", resp.text[:200], status_code=resp.status_code)
        elif resp.status_code != 200:
            raise LLMError("api_error", f"HTTP {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        data = resp.json()

        # Check for safety blocks
        candidates = data.get("candidates", [])
        if not candidates:
            block_reason = data.get("promptFeedback", {}).get("blockReason", "")
            if block_reason:
                raise LLMError("refusal", f"Blocked by safety filter: {block_reason}")
            raise LLMError("parse_error", "No candidates in response")

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason", "")
        if finish_reason == "SAFETY":
            raise LLMError("refusal", "Response blocked by safety filter")

        try:
            content = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise LLMError("parse_error", f"Unexpected response structure: {json.dumps(data)[:200]}")

        if not content:
            raise LLMError("parse_error", "Empty response content")

        return content
