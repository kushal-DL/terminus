"""OpenAI-compatible LLM adapter (covers GPT-4o, Ollama, vLLM, LM Studio, etc.)."""

from __future__ import annotations

import json
import logging
import time

import httpx

from terminus.benchmark.agent import LLMAdapter, LLMError, Message
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkGameState,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class OpenAICompatAdapter(LLMAdapter):
    """Adapter for OpenAI-compatible chat completion APIs."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        self._endpoint = config.endpoint.rstrip("/")
        if not self._endpoint.endswith("/chat/completions"):
            self._endpoint += "/chat/completions"

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

        messages = self._build_messages(system_prompt, history, turn_message)

        raw_text = await self._call_api(messages)
        parsed = parse_action_response(raw_text)
        return parsed, raw_text

    async def test_connection(self) -> bool:
        try:
            messages = [{"role": "user", "content": "Reply with just the word 'ok'."}]
            payload = {
                "model": self.config.model,
                "messages": messages,
                "max_tokens": 5,
                "temperature": 0,
            }
            headers = self._build_headers()
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False

    def get_token_count(self, messages: list[Message]) -> int:
        from terminus.benchmark.tokens import count_messages_tokens
        return count_messages_tokens(messages, "openai", self.config.model)

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_messages(
        self,
        system_prompt: str,
        history: list[Message],
        turn_message: str,
    ) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        # Skip any system message already in history — we prepend a fresh one above
        for m in history:
            if m.role == "system":
                continue
            msgs.append({"role": m.role, "content": m.content})
        msgs.append({"role": "user", "content": turn_message})
        return msgs

    async def _call_api(self, messages: list[dict[str, str]]) -> str:
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": 1024 if self.config.extra_body else 800,
            "temperature": 0.3,
        }
        # Use JSON mode for models that support it
        if self.config.provider == "openai":
            payload["response_format"] = {"type": "json_object"}

        # Merge any extra fields (e.g. reasoning_budget, enable_thinking for Nemotron)
        if self.config.extra_body:
            payload.update(self.config.extra_body)

        # Streaming required when extra_body requests thinking mode
        needs_stream = bool(self.config.extra_body)
        if needs_stream:
            payload["stream"] = True

        headers = self._build_headers()
        timeout = self.config.timeout_seconds

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if needs_stream:
                    return await self._call_streaming(client, payload, headers)
                resp = await client.post(self._endpoint, json=payload, headers=headers)
        except httpx.TimeoutException:
            raise LLMError("timeout", f"Request timed out after {timeout}s")
        except httpx.ConnectError:
            raise LLMError("connection_error", f"Cannot connect to {self._endpoint}")

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", "5"))
            raise LLMError("rate_limit", "Rate limited", retry_after=retry_after, status_code=429)
        elif resp.status_code >= 500:
            raise LLMError("api_error", resp.text[:200], status_code=resp.status_code)
        elif resp.status_code != 200:
            raise LLMError("api_error", f"HTTP {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise LLMError("parse_error", f"Unexpected response structure: {json.dumps(data)[:200]}")

        if not content:
            raise LLMError("parse_error", "Empty response content")

        finish_reason = data["choices"][0].get("finish_reason", "")
        if finish_reason == "content_filter":
            raise LLMError("refusal", "Response blocked by content filter")

        return content

    async def _call_streaming(
        self,
        client: "httpx.AsyncClient",
        payload: dict,
        headers: dict,
    ) -> str:
        """Consume a streaming SSE response and return the final content."""
        import json as _json

        content_parts: list[str] = []
        try:
            async with client.stream("POST", self._endpoint, json=payload, headers=headers) as resp:
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "5"))
                    raise LLMError("rate_limit", "Rate limited", retry_after=retry_after, status_code=429)
                elif resp.status_code >= 500:
                    body = await resp.aread()
                    raise LLMError("api_error", body.decode()[:200], status_code=resp.status_code)
                elif resp.status_code != 200:
                    body = await resp.aread()
                    raise LLMError("api_error", f"HTTP {resp.status_code}: {body.decode()[:200]}", status_code=resp.status_code)

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        # Collect the actual response content (not the internal reasoning)
                        piece = delta.get("content") or ""
                        if piece:
                            content_parts.append(piece)
                    except (_json.JSONDecodeError, IndexError):
                        continue
        except httpx.TimeoutException:
            raise LLMError("timeout", f"Streaming request timed out after {self.config.timeout_seconds}s")
        except httpx.ConnectError:
            raise LLMError("connection_error", f"Cannot connect to {self._endpoint}")

        content = "".join(content_parts).strip()
        if not content:
            raise LLMError("parse_error", "Streaming response produced no content")
        return content
