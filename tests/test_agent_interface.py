"""Tests for Phase 1 — LLM Agent Interface (schemas, adapters, parser, prompt, tokens)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkConfig,
    BenchmarkGameState,
    BuildingState,
    DimensionWeights,
    GameRecording,
    GameTheoryDepth,
    MarketPrices,
    ModelConfig,
    OpponentInfo,
    OpponentType,
    ProductionRates,
    Reasoning,
    ReasoningFactor,
    ReasoningFactorType,
    ResourceCapacity,
    ResourceState,
    BenchmarkWorkerAllocation,
    TradeOfferInfo,
    TurnSnapshot,
    WeightPreset,
)
from terminus.benchmark.agent import LLMAdapter, LLMError, Message, create_adapter
from terminus.benchmark.prompt import (
    build_history_window,
    build_retry_prompt,
    build_system_prompt,
    build_turn_message,
    format_history_entry,
)
from terminus.benchmark.response_parser import (
    coerce_response,
    extract_json,
    parse_action_response,
    validate_action_feasibility,
)
from terminus.benchmark.tokens import (
    count_messages_tokens,
    count_tokens,
    get_encoding_for_model,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelConfig:
    def test_valid_openai_config(self) -> None:
        config = ModelConfig(
            name="GPT-4o",
            provider="openai",
            endpoint="https://api.openai.com/v1/chat/completions",
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
        )
        assert config.name == "GPT-4o"
        assert config.context_window == 128000

    def test_ollama_no_auth_required(self) -> None:
        config = ModelConfig(
            name="Llama",
            provider="ollama",
            endpoint="http://localhost:11434/v1",
            model="llama3.1",
        )
        assert config.api_key is None

    def test_openai_requires_auth(self) -> None:
        with pytest.raises(ValueError, match="api_key or api_key_env"):
            ModelConfig(
                name="GPT",
                provider="openai",
                endpoint="https://api.openai.com/v1",
                model="gpt-4o",
            )

    def test_timeout_bounds(self) -> None:
        with pytest.raises(ValueError):
            ModelConfig(
                name="Test",
                provider="ollama",
                endpoint="http://localhost:11434",
                model="test",
                timeout_seconds=2.0,  # Below minimum of 5
            )


class TestBenchmarkConfig:
    def test_valid_config(self) -> None:
        config = BenchmarkConfig(
            models=[
                ModelConfig(
                    name="GPT-4o",
                    provider="openai",
                    endpoint="https://api.openai.com/v1",
                    model="gpt-4o",
                    api_key_env="OPENAI_API_KEY",
                )
            ],
        )
        assert config.games_per_matchup == 10
        assert config.max_turns == 100
        assert config.speed_multiplier == 5
        assert config.weight_preset == WeightPreset.BALANCED

    def test_requires_at_least_one_model(self) -> None:
        with pytest.raises(ValueError):
            BenchmarkConfig(models=[])


class TestBenchmarkGameState:
    def test_default_state(self) -> None:
        state = BenchmarkGameState()
        assert state.turn == 1
        assert state.resources.food == 0
        assert state.workers.farming == 0
        assert state.buildings == []

    def test_full_state(self) -> None:
        state = BenchmarkGameState(
            turn=15,
            max_turns=100,
            score=285,
            rank=1,
            total_players=3,
            location="plains",
            specialization="agriculture",
            population=28,
            population_cap=50,
            morale=1.05,
            resources=ResourceState(food=142, materials=67, knowledge=18, gold=35),
            capacity=ResourceCapacity(food=500, materials=500, knowledge=200, gold=300),
            production=ProductionRates(food=4.8, materials=2.1, knowledge=0.9, gold=1.6),
            food_consumption=2.8,
            workers=BenchmarkWorkerAllocation(farming=10, mining=6, research=3, construction=5, defense=2, medicine=2),
            buildings=[BuildingState(type="farm", level=1, health=100, max_health=100)],
            market_prices=MarketPrices(food=1.8, materials=3.4, knowledge=5.2),
            opponents=[OpponentInfo(name="Bot", score=240, population=24, building_count=2)],
            incoming_trade_offers=[
                TradeOfferInfo(
                    offer_id="abc123",
                    from_player="Bot",
                    to_player="LLM",
                    offer_resources={"food": 20},
                    request_resources={"gold": 10},
                    ticks_remaining=15,
                )
            ],
        )
        assert state.turn == 15
        assert len(state.incoming_trade_offers) == 1


class TestActionResponse:
    def test_build_action(self) -> None:
        resp = ActionResponse(
            action=BenchmarkActionType.BUILD,
            params={"building_type": "farm"},
        )
        assert resp.action == BenchmarkActionType.BUILD
        assert resp.params["building_type"] == "farm"

    def test_pass_action(self) -> None:
        resp = ActionResponse(action=BenchmarkActionType.PASS, params={})
        assert resp.action == BenchmarkActionType.PASS

    def test_with_reasoning(self) -> None:
        resp = ActionResponse(
            action=BenchmarkActionType.BUILD,
            params={"building_type": "farm"},
            reasoning=Reasoning(
                factors=[
                    ReasoningFactor(factor=ReasoningFactorType.RESOURCE_BOTTLENECK, weight=0.6),
                    ReasoningFactor(factor=ReasoningFactorType.LONG_TERM_GROWTH, weight=0.4),
                ]
            ),
        )
        assert resp.reasoning is not None
        assert len(resp.reasoning.factors) == 2

    def test_reasoning_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to"):
            Reasoning(
                factors=[
                    ReasoningFactor(factor=ReasoningFactorType.RESOURCE_BOTTLENECK, weight=0.1),
                    ReasoningFactor(factor=ReasoningFactorType.LONG_TERM_GROWTH, weight=0.1),
                ]
            )


class TestRecordingModels:
    def test_turn_snapshot(self) -> None:
        snap = TurnSnapshot(turn=1, state=BenchmarkGameState())
        assert snap.valid is True
        assert snap.retry_count == 0

    def test_game_recording(self) -> None:
        rec = GameRecording(model_name="GPT-4o", opponent_type="random")
        assert rec.final_score == 0
        assert rec.turns == []


# ═══════════════════════════════════════════════════════════════════════════════
# Response Parser Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractJson:
    def test_clean_json(self) -> None:
        text = '{"action": "BUILD", "params": {"building_type": "farm"}}'
        result = extract_json(text)
        assert result is not None
        assert result["action"] == "BUILD"

    def test_markdown_fences(self) -> None:
        text = '```json\n{"action": "BUILD", "params": {"building_type": "farm"}}\n```'
        result = extract_json(text)
        assert result is not None
        assert result["action"] == "BUILD"

    def test_natural_language_prefix(self) -> None:
        text = 'Sure! Here is my action:\n{"action": "PASS", "params": {}}\nHope that helps!'
        result = extract_json(text)
        assert result is not None
        assert result["action"] == "PASS"

    def test_trailing_comma(self) -> None:
        text = '{"action": "BUILD", "params": {"building_type": "farm",},}'
        result = extract_json(text)
        assert result is not None
        assert result["action"] == "BUILD"

    def test_single_quotes_only(self) -> None:
        text = "{'action': 'BUILD', 'params': {'building_type': 'farm'}}"
        result = extract_json(text)
        assert result is not None
        assert result["action"] == "BUILD"

    def test_no_json_returns_none(self) -> None:
        text = "I cannot help with that request."
        assert extract_json(text) is None

    def test_empty_string(self) -> None:
        assert extract_json("") is None

    def test_nested_json(self) -> None:
        text = '{"action": "ALLOCATE_WORKERS", "params": {"allocation": {"farming": 10, "mining": 5, "research": 3, "construction": 2, "defense": 0, "medicine": 0}}, "reasoning": {"factors": [{"factor": "resource_bottleneck", "weight": 1.0}]}}'
        result = extract_json(text)
        assert result is not None
        assert result["params"]["allocation"]["farming"] == 10


class TestCoerceResponse:
    def test_valid_response(self) -> None:
        data = {
            "action": "BUILD",
            "params": {"building_type": "farm"},
            "reasoning": {"factors": [{"factor": "long_term_growth", "weight": 1.0}]},
        }
        resp = coerce_response(data)
        assert resp.action == BenchmarkActionType.BUILD
        assert resp.reasoning is not None

    def test_lowercase_action(self) -> None:
        data = {"action": "build", "params": {"building_type": "mine"}}
        resp = coerce_response(data)
        assert resp.action == BenchmarkActionType.BUILD

    def test_missing_reasoning_is_none(self) -> None:
        data = {"action": "PASS", "params": {}}
        resp = coerce_response(data)
        assert resp.reasoning is None

    def test_action_type_key(self) -> None:
        """Handle responses using 'action_type' instead of 'action'."""
        data = {"action_type": "TRADE_BUY", "params": {"resource": "food", "quantity": 10}}
        resp = coerce_response(data)
        assert resp.action == BenchmarkActionType.TRADE_BUY

    def test_payload_key(self) -> None:
        """Handle responses using 'payload' instead of 'params'."""
        data = {"action": "BUILD", "payload": {"building_type": "wall"}}
        resp = coerce_response(data)
        assert resp.params["building_type"] == "wall"

    def test_unknown_action_defaults_to_pass(self) -> None:
        data = {"action": "EXPLODE", "params": {}}
        resp = coerce_response(data)
        assert resp.action == BenchmarkActionType.PASS

    def test_reasoning_string_ignored(self) -> None:
        data = {"action": "PASS", "params": {}, "reasoning": "I chose pass because..."}
        resp = coerce_response(data)
        assert resp.reasoning is None

    def test_reasoning_weights_normalized(self) -> None:
        data = {
            "action": "BUILD",
            "params": {"building_type": "farm"},
            "reasoning": {
                "factors": [
                    {"factor": "resource_bottleneck", "weight": 3.0},
                    {"factor": "long_term_growth", "weight": 7.0},
                ]
            },
        }
        resp = coerce_response(data)
        assert resp.reasoning is not None
        total = sum(f.weight for f in resp.reasoning.factors)
        assert 0.9 <= total <= 1.1


class TestParseActionResponse:
    def test_full_pipeline(self) -> None:
        raw = '```json\n{"action": "BUILD", "params": {"building_type": "hospital"}, "reasoning": {"factors": [{"factor": "immediate_survival", "weight": 1.0}]}}\n```'
        resp = parse_action_response(raw)
        assert resp.action == BenchmarkActionType.BUILD
        assert resp.params["building_type"] == "hospital"

    def test_raises_on_unparseable(self) -> None:
        with pytest.raises(ValueError, match="Could not extract"):
            parse_action_response("This is not JSON at all.")


class TestValidateActionFeasibility:
    def test_valid_pass(self) -> None:
        resp = ActionResponse(action=BenchmarkActionType.PASS, params={})
        state = BenchmarkGameState()
        errors = validate_action_feasibility(resp, state)
        assert errors == []

    def test_worker_allocation_wrong_sum(self) -> None:
        resp = ActionResponse(
            action=BenchmarkActionType.ALLOCATE_WORKERS,
            params={"allocation": {"farming": 5, "mining": 5, "research": 5, "construction": 0, "defense": 0, "medicine": 0}},
        )
        state = BenchmarkGameState(population=20)
        errors = validate_action_feasibility(resp, state)
        assert any("sums to 15" in e for e in errors)

    def test_trade_sell_insufficient_resources(self) -> None:
        resp = ActionResponse(
            action=BenchmarkActionType.TRADE_SELL,
            params={"resource": "food", "quantity": 100},
        )
        state = BenchmarkGameState(resources=ResourceState(food=50))
        errors = validate_action_feasibility(resp, state)
        assert any("Insufficient" in e for e in errors)

    def test_trade_offer_missing_target(self) -> None:
        resp = ActionResponse(
            action=BenchmarkActionType.TRADE_OFFER,
            params={"offer_resources": {"food": 10}},
        )
        state = BenchmarkGameState()
        errors = validate_action_feasibility(resp, state)
        assert any("to_player_id" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Builder Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptBuilder:
    def test_system_prompt_contains_rules(self) -> None:
        prompt = build_system_prompt()
        assert "GAME RULES" in prompt
        assert "RESPONSE FORMAT" in prompt
        assert "ACTION TYPES" in prompt
        assert "TRADE_OFFER" in prompt

    def test_system_prompt_max_turns_param(self) -> None:
        prompt = build_system_prompt(max_turns=50)
        assert "50 turns" in prompt

    def test_turn_message_basic(self) -> None:
        state = BenchmarkGameState(
            turn=10,
            max_turns=100,
            score=150,
            rank=2,
            total_players=3,
            location="coast",
            specialization="trade",
            population=25,
            population_cap=50,
            morale=1.1,
            resources=ResourceState(food=100, materials=50, knowledge=20, gold=30),
            production=ProductionRates(food=3.0, materials=1.5, knowledge=0.5, gold=1.0),
            food_consumption=2.5,
            workers=BenchmarkWorkerAllocation(farming=8, mining=5, research=3, construction=5, defense=2, medicine=2),
        )
        actions = [AvailableAction(action_type="BUILD", description="Build Farm", cost="30M, 10G")]
        msg = build_turn_message(state, actions)
        assert "Turn 10/100" in msg
        assert "Score: 150" in msg
        assert "coast" in msg
        assert "trade" in msg
        assert "Food: 100/500" in msg
        assert "BUILD: Build Farm" in msg
        assert "30M, 10G" in msg

    def test_turn_message_with_trade_offers(self) -> None:
        state = BenchmarkGameState(
            incoming_trade_offers=[
                TradeOfferInfo(
                    offer_id="abc12345",
                    from_player="Bot",
                    to_player="LLM",
                    offer_resources={"food": 20},
                    request_resources={"gold": 10},
                    ticks_remaining=15,
                )
            ],
        )
        msg = build_turn_message(state, [])
        assert "INCOMING TRADE OFFERS" in msg
        assert "Bot offers" in msg
        assert "20 food" in msg
        assert "10 gold" in msg

    def test_turn_message_with_catastrophe_warning(self) -> None:
        from terminus.benchmark.schemas import CatastropheWarning

        state = BenchmarkGameState(
            catastrophe_warning=CatastropheWarning(
                category="population",
                type="plague",
                ticks_until=12,
                estimated_severity=2,
            )
        )
        msg = build_turn_message(state, [])
        assert "CATASTROPHE WARNING" in msg
        assert "plague" in msg
        assert "12 ticks" in msg

    def test_history_window(self) -> None:
        entries = [f"Turn {i}: Action: PASS | Result: No action" for i in range(1, 21)]
        window = build_history_window(entries, max_tokens=500)
        assert "RECENT HISTORY" in window
        # Should truncate to fit within budget
        assert len(window) < 2000

    def test_history_window_empty(self) -> None:
        assert build_history_window([]) == ""

    def test_format_history_entry(self) -> None:
        entry = format_history_entry(5, "BUILD", {"building_type": "farm"}, "Success")
        assert "Turn 5" in entry
        assert "BUILD" in entry
        assert "farm" in entry

    def test_retry_prompt(self) -> None:
        prompt = build_retry_prompt("Invalid JSON: trailing comma", 2, 3)
        assert "attempt 2/3" in prompt
        assert "trailing comma" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# Token Counting Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTokenCounting:
    def test_estimate_tokens_basic(self) -> None:
        # ~4 chars per token
        text = "Hello world, this is a test."  # 28 chars → ~7 tokens
        count = count_tokens(text, "anthropic")
        assert 5 <= count <= 10

    def test_empty_text(self) -> None:
        assert count_tokens("", "anthropic") == 0

    def test_openai_encoding_selection(self) -> None:
        assert get_encoding_for_model("gpt-4o") == "o200k_base"
        assert get_encoding_for_model("gpt-4") == "cl100k_base"
        assert get_encoding_for_model("gpt-4o-mini") == "o200k_base"
        assert get_encoding_for_model("unknown-model") == "o200k_base"

    def test_count_messages_tokens(self) -> None:
        messages = [
            Message(role="system", content="You are a game player."),
            Message(role="user", content="Turn 1. Choose an action."),
        ]
        count = count_messages_tokens(messages, "anthropic")
        # Should be > 0 and include overhead
        assert count > 10

    def test_openai_token_count(self) -> None:
        # This will use tiktoken if available, else fallback
        text = "Build a farm to increase food production."
        count = count_tokens(text, "openai", "gpt-4o")
        assert count > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Adapter Tests (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdapterFactory:
    def test_create_openai_adapter(self) -> None:
        config = ModelConfig(
            name="GPT-4o",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-test",
        )
        adapter = create_adapter(config)
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        assert isinstance(adapter, OpenAICompatAdapter)

    def test_create_anthropic_adapter(self) -> None:
        config = ModelConfig(
            name="Claude",
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
        )
        adapter = create_adapter(config)
        from terminus.benchmark.adapters.anthropic import AnthropicAdapter
        assert isinstance(adapter, AnthropicAdapter)

    def test_create_google_adapter(self) -> None:
        config = ModelConfig(
            name="Gemini",
            provider="google",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-1.5-pro",
            api_key="test-key",
        )
        adapter = create_adapter(config)
        from terminus.benchmark.adapters.google import GoogleAdapter
        assert isinstance(adapter, GoogleAdapter)

    def test_create_ollama_adapter(self) -> None:
        config = ModelConfig(
            name="Llama",
            provider="ollama",
            endpoint="http://localhost:11434/v1",
            model="llama3.1",
        )
        adapter = create_adapter(config)
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        assert isinstance(adapter, OpenAICompatAdapter)

    def test_unknown_provider_raises(self) -> None:
        config = ModelConfig(
            name="Unknown",
            provider="ollama",  # Use valid for construction
            endpoint="http://localhost",
            model="test",
        )
        config.provider = "imaginary"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unknown provider"):
            create_adapter(config)


class TestLLMError:
    def test_str_representation(self) -> None:
        err = LLMError("timeout", "30s elapsed")
        assert "timeout" in str(err)
        assert "30s elapsed" in str(err)

    def test_with_status_code(self) -> None:
        err = LLMError("api_error", "Server error", status_code=500)
        assert "500" in str(err)


class TestOpenAIAdapter:
    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        config = ModelConfig(
            name="GPT",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-test",
        )
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        adapter = OpenAICompatAdapter(config)

        mock_response = httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self) -> None:
        config = ModelConfig(
            name="GPT",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-test",
        )
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        adapter = OpenAICompatAdapter(config)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
            result = await adapter.test_connection()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_action_success(self) -> None:
        config = ModelConfig(
            name="GPT",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-test",
        )
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        adapter = OpenAICompatAdapter(config)

        llm_response = json.dumps({
            "action": "BUILD",
            "params": {"building_type": "farm"},
            "reasoning": {"factors": [{"factor": "long_term_growth", "weight": 1.0}]},
        })
        mock_response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": llm_response}, "finish_reason": "stop"}]},
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            state = BenchmarkGameState(turn=5, population=20)
            actions = [AvailableAction(action_type="BUILD", description="Build Farm")]
            resp, raw = await adapter.get_action(state, [], actions)
            assert resp.action == BenchmarkActionType.BUILD
            assert resp.params["building_type"] == "farm"

    @pytest.mark.asyncio
    async def test_rate_limit_raises(self) -> None:
        config = ModelConfig(
            name="GPT",
            provider="openai",
            endpoint="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="sk-test",
        )
        from terminus.benchmark.adapters.openai_compat import OpenAICompatAdapter
        adapter = OpenAICompatAdapter(config)

        mock_response = httpx.Response(429, headers={"Retry-After": "10"}, text="Rate limited")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError) as exc_info:
                await adapter._call_api([{"role": "user", "content": "test"}])
            assert exc_info.value.error_type == "rate_limit"
            assert exc_info.value.retry_after == 10.0


class TestAnthropicAdapter:
    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        config = ModelConfig(
            name="Claude",
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
        )
        from terminus.benchmark.adapters.anthropic import AnthropicAdapter
        adapter = AnthropicAdapter(config)

        mock_response = httpx.Response(200, json={"content": [{"text": "ok"}]})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_overloaded_raises_api_error(self) -> None:
        config = ModelConfig(
            name="Claude",
            provider="anthropic",
            endpoint="https://api.anthropic.com",
            model="claude-sonnet-4-20250514",
            api_key="sk-ant-test",
        )
        from terminus.benchmark.adapters.anthropic import AnthropicAdapter
        adapter = AnthropicAdapter(config)

        mock_response = httpx.Response(529, text="Overloaded")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError) as exc_info:
                await adapter._call_api("system", [{"role": "user", "content": "test"}])
            assert exc_info.value.error_type == "api_error"
            assert exc_info.value.status_code == 529


class TestGoogleAdapter:
    @pytest.mark.asyncio
    async def test_test_connection_success(self) -> None:
        config = ModelConfig(
            name="Gemini",
            provider="google",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-1.5-pro",
            api_key="test-key",
        )
        from terminus.benchmark.adapters.google import GoogleAdapter
        adapter = GoogleAdapter(config)

        mock_response = httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            result = await adapter.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_safety_block_raises_refusal(self) -> None:
        config = ModelConfig(
            name="Gemini",
            provider="google",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-1.5-pro",
            api_key="test-key",
        )
        from terminus.benchmark.adapters.google import GoogleAdapter
        adapter = GoogleAdapter(config)

        mock_response = httpx.Response(
            200,
            json={"candidates": [{"finishReason": "SAFETY", "content": {"parts": [{"text": ""}]}}]},
        )
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMError) as exc_info:
                await adapter._call_api("system", [{"role": "user", "parts": [{"text": "test"}]}])
            assert exc_info.value.error_type == "refusal"

    @pytest.mark.asyncio
    async def test_count_tokens_api(self) -> None:
        config = ModelConfig(
            name="Gemini",
            provider="google",
            endpoint="https://generativelanguage.googleapis.com/v1beta",
            model="gemini-1.5-pro",
            api_key="test-key",
        )
        from terminus.benchmark.adapters.google import GoogleAdapter
        adapter = GoogleAdapter(config)

        mock_response = httpx.Response(200, json={"totalTokens": 42})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            count = await adapter.count_tokens_api("Hello world")
            assert count == 42
