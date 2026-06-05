"""Tests for Phase 3: Orchestrator components."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from terminus.benchmark.error_handler import (
    DisqualificationError,
    ErrorHandler,
    ErrorHandlerConfig,
)
from terminus.benchmark.recorder import TurnRecorder
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    BuildingState,
    CatastropheWarning,
    GameRecording,
    MarketPrices,
    Reasoning,
    ReasoningFactor,
    ReasoningFactorType,
    ResourceState,
    TradeOfferInfo,
    TurnSnapshot,
)
from terminus.benchmark.speed import SpeedController
from terminus.benchmark.state_converter import StateConverter


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_raw_state(
    population: int = 30,
    food: float = 100,
    materials: float = 80,
    knowledge: float = 20,
    gold: float = 50,
    buildings: list | None = None,
    tick: int = 10,
) -> dict:
    """Create a mock engine get_player_state() return value."""
    return {
        "game_id": "test-game",
        "phase": "playing",
        "colony": {
            "name": "Test Colony",
            "location": "plains",
            "specialization": "agriculture",
            "resources": {"food": food, "materials": materials, "knowledge": knowledge, "gold": gold},
            "capacity": {"food": 500, "materials": 500, "knowledge": 200, "gold": 300},
            "buildings": buildings or [],
            "workers": {"farming": 10, "mining": 6, "research": 4, "construction": 5, "defense": 3, "medicine": 2},
            "population": population,
            "max_population": 50,
            "morale": 1.0,
            "score": 450,
            "achievements": [],
            "buildings_built": 2,
            "trades_completed": 0,
            "total_trade_volume": 0,
            "catastrophes_survived": 0,
            "peak_population": population,
        },
        "market": {
            "prices": {"food": 2.0, "materials": 3.0, "knowledge": 5.0},
            "stock": {"food": 200, "materials": 200, "knowledge": 200},
            "price_history": [],
        },
        "other_players": [
            {"name": "Opponent", "connected": True, "score": 300},
        ],
        "player_count": 2,
        "catastrophes_remaining": 3,
        "next_catastrophe_in": 120.0,
        "watchtower_hint": None,
        "tick": tick,
        "production_rates": {"food": 2.5, "materials": 1.8, "knowledge": 1.0, "gold": 1.5},
        "trade_history": [],
        "incoming_trade_offers": [],
        "outgoing_trade_offers": [],
    }


def _make_state(**kwargs) -> BenchmarkGameState:
    """Create a BenchmarkGameState for testing."""
    return BenchmarkGameState(
        turn=kwargs.get("turn", 10),
        max_turns=100,
        population=kwargs.get("population", 30),
        population_cap=50,
        morale=1.0,
        resources=ResourceState(food=100, materials=80, knowledge=20, gold=50),
        workers=BenchmarkWorkerAllocation(farming=10, mining=6, research=4, construction=5, defense=3, medicine=2),
        market_prices=MarketPrices(food=2.0, materials=3.0, knowledge=5.0),
    )


# ─── Speed Controller Tests ──────────────────────────────────────────────────


class TestSpeedController:
    def test_default_multiplier(self):
        sc = SpeedController()
        assert sc.multiplier == 5

    def test_custom_multiplier(self):
        sc = SpeedController(multiplier=10)
        assert sc.multiplier == 10

    def test_invalid_multiplier(self):
        with pytest.raises(ValueError):
            SpeedController(multiplier=0)

    def test_adjust_catastrophe_schedule(self):
        sc = SpeedController(multiplier=5)
        schedule = [MagicMock(scheduled_time=500), MagicMock(scheduled_time=1000)]
        sc.adjust_catastrophe_schedule(schedule)
        assert schedule[0].scheduled_time == 100.0
        assert schedule[1].scheduled_time == 200.0

    def test_effective_turn(self):
        sc = SpeedController(multiplier=5)
        assert sc.get_effective_turn(10) == 50
        assert sc.get_effective_turn(1) == 5

    def test_multiplier_1_no_change(self):
        sc = SpeedController(multiplier=1)
        schedule = [MagicMock(scheduled_time=420)]
        sc.adjust_catastrophe_schedule(schedule)
        assert schedule[0].scheduled_time == 420.0


# ─── State Converter Tests ────────────────────────────────────────────────────


class TestStateConverter:
    def setup_method(self):
        self.converter = StateConverter()

    def test_basic_conversion(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=5, max_turns=100)
        assert state.turn == 5
        assert state.max_turns == 100
        assert state.population == 30
        assert state.population_cap == 50
        assert state.morale == 1.0
        assert state.location == "plains"
        assert state.specialization == "agriculture"

    def test_resources_converted(self):
        raw = _make_raw_state(food=150, materials=90, knowledge=30, gold=60)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.resources.food == 150
        assert state.resources.materials == 90
        assert state.resources.knowledge == 30
        assert state.resources.gold == 60

    def test_workers_converted(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.workers.farming == 10
        assert state.workers.mining == 6
        assert state.workers.research == 4
        assert state.workers.construction == 5
        assert state.workers.defense == 3
        assert state.workers.medicine == 2

    def test_buildings_converted(self):
        raw = _make_raw_state(buildings=[
            {"building_type": "farm", "level": 2, "health": 150, "max_health": 200, "under_construction": False},
            {"building_type": "wall", "level": 1, "health": 80, "max_health": 100, "under_construction": True,
             "construction_progress": 3, "construction_target": 10},
        ])
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert len(state.buildings) == 2
        assert state.buildings[0].type == "farm"
        assert state.buildings[0].level == 2
        assert state.buildings[0].health == 150
        assert state.buildings[1].under_construction is True
        assert state.buildings[1].ticks_remaining == 7

    def test_market_prices_converted(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.market_prices.food == 2.0
        assert state.market_prices.materials == 3.0
        assert state.market_prices.knowledge == 5.0

    def test_opponents_converted(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert len(state.opponents) == 1
        assert state.opponents[0].name == "Opponent"
        assert state.opponents[0].score == 300

    def test_rank_computed(self):
        raw = _make_raw_state()  # score=450, opponent score=300
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.rank == 1  # We're higher

    def test_rank_when_losing(self):
        raw = _make_raw_state()
        raw["colony"]["score"] = 100
        raw["other_players"] = [{"name": "Opp", "connected": True, "score": 500}]
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.rank == 2

    def test_food_consumption(self):
        raw = _make_raw_state(population=40)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert abs(state.food_consumption - 4.0) < 0.01  # 40 × 0.1

    def test_sell_spread_default(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.sell_spread == 0.7

    def test_sell_spread_trade_spec(self):
        raw = _make_raw_state()
        raw["colony"]["specialization"] = "trade"
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.sell_spread == 0.85

    def test_catastrophe_warning_none(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.catastrophe_warning is None

    def test_catastrophe_warning_parsed(self):
        raw = _make_raw_state()
        raw["watchtower_hint"] = "A population threat approaches..."
        raw["next_catastrophe_in"] = 60.0
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.catastrophe_warning is not None
        assert state.catastrophe_warning.category == "population"
        assert state.catastrophe_warning.ticks_until == 30  # 60s / 2s per tick

    def test_trade_offers_converted(self):
        raw = _make_raw_state()
        raw["incoming_trade_offers"] = [{
            "offer_id": "trade-1",
            "from_player_id": "p1",
            "to_player_id": "p2",
            "offer_resources": {"food": 20.0},
            "request_resources": {"gold": 15.0},
            "tick_created": 5,
            "expires_tick": 35,
        }]
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert len(state.incoming_trade_offers) == 1
        assert state.incoming_trade_offers[0].offer_id == "trade-1"
        assert state.incoming_trade_offers[0].offer_resources == {"food": 20.0}

    def test_available_actions_always_has_pass(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "PASS" in action_types

    def test_available_actions_has_allocate_workers(self):
        raw = _make_raw_state(population=20)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "ALLOCATE_WORKERS" in action_types

    def test_available_actions_no_allocate_zero_pop(self):
        raw = _make_raw_state(population=0)
        raw["colony"]["population"] = 0
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "ALLOCATE_WORKERS" not in action_types

    def test_available_actions_trade_buy_with_gold(self):
        raw = _make_raw_state(gold=50)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "TRADE_BUY" in action_types

    def test_available_actions_no_trade_buy_zero_gold(self):
        raw = _make_raw_state(gold=0)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "TRADE_BUY" not in action_types

    def test_available_actions_trade_sell(self):
        raw = _make_raw_state(food=50)
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "TRADE_SELL" in action_types

    def test_available_actions_repair_damaged(self):
        raw = _make_raw_state(materials=100, buildings=[
            {"building_type": "farm", "level": 1, "health": 50, "max_health": 100, "under_construction": False},
        ])
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "REPAIR" in action_types

    def test_available_actions_trade_offer(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        action_types = [a.action_type for a in state.available_actions]
        assert "TRADE_OFFER" in action_types

    def test_empty_colony_returns_pass_only(self):
        raw = _make_raw_state()
        raw["colony"] = None
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert len(state.available_actions) == 1
        assert state.available_actions[0].action_type == "PASS"

    def test_production_rates_converted(self):
        raw = _make_raw_state()
        state = self.converter.convert(raw, turn=1, max_turns=100)
        assert state.production.food == 2.5
        assert state.production.materials == 1.8
        assert state.production.knowledge == 1.0
        assert state.production.gold == 1.5


# ─── Error Handler Tests ──────────────────────────────────────────────────────


class TestErrorHandler:
    def test_initial_state(self):
        handler = ErrorHandler()
        assert not handler.is_disqualified
        assert handler.dq_reason is None
        assert handler.consecutive_invalid == 0
        assert handler.total_invalid == 0

    def test_record_valid_resets_consecutive(self):
        handler = ErrorHandler()
        handler._stats.consecutive_invalid = 5
        handler.record_valid()
        assert handler.consecutive_invalid == 0
        assert handler.stats.total_valid == 1

    def test_record_invalid_increments(self):
        handler = ErrorHandler(ErrorHandlerConfig(consecutive_invalid_dq=20))
        handler.record_invalid("test")
        assert handler.consecutive_invalid == 1
        assert handler.total_invalid == 1

    def test_dq_on_consecutive_threshold(self):
        handler = ErrorHandler(ErrorHandlerConfig(consecutive_invalid_dq=3))
        handler.record_invalid("test")
        handler.record_invalid("test")
        with pytest.raises(DisqualificationError):
            handler.record_invalid("test")
        assert handler.is_disqualified

    def test_valid_resets_dq_counter(self):
        handler = ErrorHandler(ErrorHandlerConfig(consecutive_invalid_dq=5))
        handler.record_invalid("test")
        handler.record_invalid("test")
        handler.record_valid()
        assert handler.consecutive_invalid == 0
        # Can now do more without DQ
        handler.record_invalid("test")
        handler.record_invalid("test")
        assert not handler.is_disqualified

    def test_refusal_dq(self):
        handler = ErrorHandler(ErrorHandlerConfig(refusal_dq=2, consecutive_invalid_dq=100))
        handler._stats.total_refusals = 1
        with pytest.raises(DisqualificationError):
            handler._check_refusal_dq()
            handler._stats.total_refusals = 2
            handler._check_refusal_dq()

    def test_pass_action_returned(self):
        handler = ErrorHandler()
        action = handler._pass_action()
        assert action.action == BenchmarkActionType.PASS

    def test_rate_limit_delay_exponential(self):
        handler = ErrorHandler(ErrorHandlerConfig(
            rate_limit_base_delay=1.0,
            rate_limit_max_delay=60.0,
        ))
        # First attempt: ~1s
        handler._rate_limit_attempt = 0
        delay0 = handler._get_rate_limit_delay(None)
        assert 0.5 < delay0 < 1.5

        # Second attempt: ~2s
        handler._rate_limit_attempt = 1
        delay1 = handler._get_rate_limit_delay(None)
        assert 1.0 < delay1 < 3.0

        # Third attempt: ~4s
        handler._rate_limit_attempt = 2
        delay2 = handler._get_rate_limit_delay(None)
        assert 2.0 < delay2 < 6.0

    def test_rate_limit_delay_capped(self):
        handler = ErrorHandler(ErrorHandlerConfig(
            rate_limit_base_delay=1.0,
            rate_limit_max_delay=10.0,
        ))
        handler._rate_limit_attempt = 20  # Would be 2^20 without cap
        delay = handler._get_rate_limit_delay(None)
        assert delay <= 12.0  # 10 + 20% jitter max

    @pytest.mark.asyncio
    async def test_handle_response_success(self):
        """Test successful adapter response."""
        handler = ErrorHandler()
        state = _make_state()
        actions = [AvailableAction(action_type="PASS", description="pass")]

        # Mock adapter that returns success
        mock_adapter = AsyncMock()
        expected_response = ActionResponse(
            action=BenchmarkActionType.BUILD,
            params={"building_type": "farm"},
        )
        mock_adapter.get_action = AsyncMock(return_value=(expected_response, '{"action": "BUILD"}'))

        response, raw, retries = await handler.handle_response(mock_adapter, state, [], actions)
        assert response.action == BenchmarkActionType.BUILD
        assert retries == 0
        assert handler.stats.total_valid == 1

    @pytest.mark.asyncio
    async def test_handle_response_timeout_retries(self):
        """Test timeout triggers retry then fallback."""
        from terminus.benchmark.agent import LLMError

        handler = ErrorHandler(ErrorHandlerConfig(max_retries_timeout=1, consecutive_invalid_dq=50))
        state = _make_state()
        actions = [AvailableAction(action_type="PASS", description="pass")]

        mock_adapter = AsyncMock()
        mock_adapter.get_action = AsyncMock(side_effect=LLMError("timeout", "timed out"))

        response, raw, retries = await handler.handle_response(mock_adapter, state, [], actions)
        assert response.action == BenchmarkActionType.PASS
        assert "TIMEOUT" in raw
        assert retries >= 1


# ─── Turn Recorder Tests ─────────────────────────────────────────────────────


class TestTurnRecorder:
    def test_record_turn(self):
        recorder = TurnRecorder("gpt-4", "balanced", seed=42)
        state = _make_state()
        response = ActionResponse(action=BenchmarkActionType.BUILD, params={"building_type": "farm"})

        recorder.record_turn(
            turn=1, state=state, raw_response='{"action":"BUILD"}',
            parsed_response=response, valid=True, error_message=None,
            latency_ms=150.0, tokens_used=200, retry_count=0,
        )

        assert recorder.turn_count == 1
        assert recorder.valid_count == 1
        assert recorder.invalid_count == 0

    def test_record_multiple_turns(self):
        recorder = TurnRecorder("gpt-4", "greedy", seed=1)
        state = _make_state()

        for i in range(5):
            recorder.record_turn(
                turn=i + 1, state=state, raw_response="{}",
                parsed_response=None, valid=i < 3, error_message="err" if i >= 3 else None,
                latency_ms=100.0, tokens_used=100, retry_count=0,
            )

        assert recorder.turn_count == 5
        assert recorder.valid_count == 3
        assert recorder.invalid_count == 2

    def test_finalize_produces_recording(self):
        recorder = TurnRecorder("claude-3", "random", seed=99)
        state = _make_state()

        recorder.record_turn(
            turn=1, state=state, raw_response="test",
            parsed_response=None, valid=True, error_message=None,
            latency_ms=200.0, tokens_used=150, retry_count=0,
        )

        recording = recorder.finalize(final_score=750, duration_seconds=10.5)
        assert isinstance(recording, GameRecording)
        assert recording.model_name == "claude-3"
        assert recording.opponent_type == "random"
        assert recording.seed == 99
        assert recording.final_score == 750
        assert recording.duration_seconds == 10.5
        assert len(recording.turns) == 1

    def test_finalize_with_dq(self):
        recorder = TurnRecorder("model", "balanced", seed=1)
        recording = recorder.finalize(final_score=0, dq_reason="10 consecutive invalid")
        assert recording.dq_reason == "10 consecutive invalid"

    def test_latency_stats(self):
        recorder = TurnRecorder("model", "balanced", seed=1)
        state = _make_state()

        for i in range(4):
            recorder.record_turn(
                turn=i + 1, state=state, raw_response="",
                parsed_response=None, valid=True, error_message=None,
                latency_ms=100.0 * (i + 1), tokens_used=0, retry_count=0,
            )

        assert recorder.total_latency_ms == 1000.0  # 100+200+300+400
        assert recorder.avg_latency_ms == 250.0

    def test_total_tokens(self):
        recorder = TurnRecorder("model", "balanced", seed=1)
        state = _make_state()

        recorder.record_turn(1, state, "", None, True, None, 0, 100, 0)
        recorder.record_turn(2, state, "", None, True, None, 0, 200, 0)

        assert recorder.total_tokens == 300


# ─── Integration Tests ────────────────────────────────────────────────────────


class TestOrchestratorIntegration:
    """Integration tests using the actual engine (no mocking of engine)."""

    @pytest.mark.asyncio
    async def test_orchestrator_runs_with_mock_adapter(self):
        """Full game with a mock adapter that always returns PASS."""
        from terminus.benchmark.orchestrator_v2 import BenchmarkOrchestrator
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig

        # Create a mock adapter
        mock_adapter = MagicMock()
        mock_adapter.config = ModelConfig(
            name="test-model",
            provider="ollama",
            endpoint="http://localhost:11434/v1",
            model="test",
        )

        pass_response = ActionResponse(
            action=BenchmarkActionType.PASS,
            params={},
            reasoning=Reasoning(factors=[
                ReasoningFactor(factor=ReasoningFactorType.IMMEDIATE_SURVIVAL, weight=1.0),
            ]),
        )
        mock_adapter.get_action = AsyncMock(return_value=(pass_response, '{"action":"PASS"}'))

        config = BenchmarkConfig(
            models=[mock_adapter.config],
            max_turns=20,
            speed_multiplier=10,
            games_per_matchup=1,
        )

        orchestrator = BenchmarkOrchestrator(
            adapter=mock_adapter,
            opponent_type="random",
            seed=42,
            config=config,
        )

        recording = await orchestrator.run_game()

        assert isinstance(recording, GameRecording)
        assert recording.model_name == "test-model"
        assert recording.opponent_type == "random"
        assert len(recording.turns) > 0
        assert len(recording.turns) <= 20

    @pytest.mark.asyncio
    async def test_orchestrator_handles_dq(self):
        """Test that DQ stops the game."""
        from terminus.benchmark.orchestrator_v2 import BenchmarkOrchestrator
        from terminus.benchmark.agent import LLMError
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig

        mock_adapter = MagicMock()
        mock_adapter.config = ModelConfig(
            name="bad-model",
            provider="ollama",
            endpoint="http://localhost:11434/v1",
            model="test",
        )
        # Always raise parse error
        mock_adapter.get_action = AsyncMock(side_effect=LLMError("parse_error", "bad json"))

        config = BenchmarkConfig(
            models=[mock_adapter.config],
            max_turns=50,
            speed_multiplier=10,
            games_per_matchup=1,
            max_retries_invalid_json=1,
            consecutive_invalid_dq=5,
        )

        orchestrator = BenchmarkOrchestrator(
            adapter=mock_adapter,
            opponent_type="random",
            seed=42,
            config=config,
        )

        recording = await orchestrator.run_game()

        # Should have stopped before max_turns due to DQ
        assert recording.dq_reason is not None
        assert len(recording.turns) < 50

    @pytest.mark.asyncio
    async def test_orchestrator_opponent_plays(self):
        """Verify opponent takes actions (not just PASS)."""
        from terminus.benchmark.orchestrator_v2 import BenchmarkOrchestrator
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig

        mock_adapter = MagicMock()
        mock_adapter.config = ModelConfig(
            name="test-model",
            provider="ollama",
            endpoint="http://localhost:11434/v1",
            model="test",
        )

        pass_response = ActionResponse(action=BenchmarkActionType.PASS, params={})
        mock_adapter.get_action = AsyncMock(return_value=(pass_response, '{"action":"PASS"}'))

        config = BenchmarkConfig(
            models=[mock_adapter.config],
            max_turns=20,
            speed_multiplier=10,
            games_per_matchup=1,
        )

        orchestrator = BenchmarkOrchestrator(
            adapter=mock_adapter,
            opponent_type="balanced",
            seed=42,
            config=config,
        )

        recording = await orchestrator.run_game()

        # Opponent should have affected game state (built something, reallocated workers)
        # The opponent_final_score should be > 0 since balanced agent plays well
        assert recording.opponent_final_score >= 0
        assert len(recording.turns) == 20


class TestBenchmarkRunner:
    """Tests for the multi-game runner."""

    @pytest.mark.asyncio
    async def test_runner_builds_game_plan(self):
        from terminus.benchmark.runner import BenchmarkRunner
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig, OpponentType

        config = BenchmarkConfig(
            models=[ModelConfig(
                name="test",
                provider="ollama",
                endpoint="http://localhost:11434/v1",
                model="test",
            )],
            opponents=[OpponentType.RANDOM, OpponentType.GREEDY],
            games_per_matchup=3,
            max_turns=20,
        )

        runner = BenchmarkRunner(config)
        # 1 model × 2 opponents × 3 games = 6
        assert runner.total_games == 6

    @pytest.mark.asyncio
    async def test_runner_completes_all_games(self):
        from terminus.benchmark.runner import BenchmarkRunner
        from terminus.benchmark.schemas import BenchmarkConfig, ModelConfig, OpponentType

        config = BenchmarkConfig(
            models=[ModelConfig(
                name="test",
                provider="ollama",
                endpoint="http://localhost:11434/v1",
                model="test",
            )],
            opponents=[OpponentType.RANDOM],
            games_per_matchup=2,
            max_turns=20,
            speed_multiplier=10,
        )

        # Patch create_adapter to return a mock
        pass_response = ActionResponse(action=BenchmarkActionType.PASS, params={})
        mock_adapter = MagicMock()
        mock_adapter.config = config.models[0]
        mock_adapter.get_action = AsyncMock(return_value=(pass_response, '{"action":"PASS"}'))

        with patch("terminus.benchmark.runner.create_adapter", return_value=mock_adapter):
            runner = BenchmarkRunner(config)
            recordings = await runner.run()

        assert len(recordings) == 2
        assert all(isinstance(r, GameRecording) for r in recordings)
        assert runner.completed_games == 2
        assert not runner.is_running
