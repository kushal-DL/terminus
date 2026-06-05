"""Tests for Phase 4C: Tier-1 Metric Collectors."""

from __future__ import annotations

import pytest

from terminus.benchmark.metrics import MetricsEngine
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.context_pressure import ContextPressureCollector
from terminus.benchmark.metrics.flexibility import FlexibilityCollector
from terminus.benchmark.metrics.numerical import NumericalCollector
from terminus.benchmark.metrics.opponent_aware import OpponentAwareCollector
from terminus.benchmark.metrics.planning import PlanningCollector
from terminus.benchmark.metrics.state_probes import (
    ProbeResult,
    StateProbeCollector,
    evaluate_building_recall,
    evaluate_resource_awareness,
)
from terminus.benchmark.metrics.utils import (
    action_distribution,
    clamp,
    detect_change_point,
    jensen_shannon_divergence,
    kendall_tau,
    linear_regression_slope,
    normalize_score,
    rolling_average,
)
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    BuildingState,
    CatastropheWarning,
    GameRecording,
    LastCatastropheResult,
    MarketPrices,
    OpponentInfo,
    ProductionRates,
    ResourceCapacity,
    ResourceState,
    TurnSnapshot,
)


# ─── Test Helpers ─────────────────────────────────────────────────────────────


def _state(
    turn: int = 1,
    food: float = 100,
    materials: float = 80,
    knowledge: float = 20,
    gold: float = 50,
    population: int = 30,
    pop_cap: int = 50,
    score: int = 200,
    buildings: list[BuildingState] | None = None,
    catastrophe_warning: CatastropheWarning | None = None,
    last_catastrophe: LastCatastropheResult | None = None,
    market_food: float = 2.0,
    market_materials: float = 3.0,
    market_knowledge: float = 5.0,
    available_actions: list[AvailableAction] | None = None,
    opponents: list[OpponentInfo] | None = None,
    production: ProductionRates | None = None,
) -> BenchmarkGameState:
    return BenchmarkGameState(
        turn=turn,
        max_turns=100,
        score=score,
        rank=1,
        total_players=2,
        population=population,
        population_cap=pop_cap,
        morale=1.0,
        resources=ResourceState(food=food, materials=materials, knowledge=knowledge, gold=gold),
        capacity=ResourceCapacity(food=500, materials=500, knowledge=200, gold=300),
        production=production or ProductionRates(food=2.5, materials=1.8, knowledge=1.0, gold=1.5),
        food_consumption=population * 0.1,
        workers=BenchmarkWorkerAllocation(farming=10, mining=6, research=4, construction=5, defense=3, medicine=2),
        buildings=buildings or [],
        market_prices=MarketPrices(food=market_food, materials=market_materials, knowledge=market_knowledge),
        sell_spread=0.7,
        catastrophe_warning=catastrophe_warning,
        last_catastrophe=last_catastrophe,
        available_actions=available_actions or [AvailableAction(action_type="PASS", description="pass")],
        opponents=opponents or [OpponentInfo(name="Opp", score=150)],
    )


def _snap(
    turn: int = 1,
    action: BenchmarkActionType = BenchmarkActionType.PASS,
    params: dict | None = None,
    valid: bool = True,
    tokens: int = 100,
    latency: float = 50.0,
    **state_kwargs,
) -> TurnSnapshot:
    s = _state(turn=turn, **state_kwargs)
    response = ActionResponse(action=action, params=params or {})
    return TurnSnapshot(
        turn=turn,
        state=s,
        raw_response="{}",
        parsed_response=response,
        valid=valid,
        latency_ms=latency,
        tokens_used=tokens,
    )


def _recording(turns: list[TurnSnapshot], **kwargs) -> GameRecording:
    return GameRecording(
        model_name=kwargs.get("model_name", "test-model"),
        opponent_type=kwargs.get("opponent_type", "balanced"),
        seed=kwargs.get("seed", 42),
        turns=turns,
        final_score=kwargs.get("final_score", 500),
        opponent_final_score=kwargs.get("opponent_final_score", 300),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UTILS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestUtils:
    def test_rolling_average_basic(self):
        result = rolling_average([1, 2, 3, 4, 5], 3)
        assert len(result) == 5
        assert result[0] == 1.0
        assert result[1] == 1.5
        assert abs(result[2] - 2.0) < 0.01
        assert abs(result[3] - 3.0) < 0.01
        assert abs(result[4] - 4.0) < 0.01

    def test_rolling_average_empty(self):
        assert rolling_average([], 3) == []

    def test_kendall_tau_same_order(self):
        assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_kendall_tau_reversed(self):
        assert kendall_tau(["c", "b", "a"], ["a", "b", "c"]) == -1.0

    def test_kendall_tau_partial(self):
        tau = kendall_tau(["a", "c", "b"], ["a", "b", "c"])
        assert -1.0 <= tau <= 1.0
        assert abs(tau - (1 / 3)) < 0.01

    def test_kendall_tau_single(self):
        assert kendall_tau(["a"], ["a"]) == 1.0

    def test_jensen_shannon_identical(self):
        p = {"a": 0.5, "b": 0.5}
        assert jensen_shannon_divergence(p, p) < 0.01

    def test_jensen_shannon_different(self):
        p = {"a": 1.0, "b": 0.0}
        q = {"a": 0.0, "b": 1.0}
        js = jensen_shannon_divergence(p, q)
        assert js > 0.5

    def test_jensen_shannon_empty(self):
        assert jensen_shannon_divergence({}, {}) == 0.0

    def test_normalize_score(self):
        assert normalize_score(5, 0, 10) == 0.5
        assert normalize_score(0, 0, 10) == 0.0
        assert normalize_score(10, 0, 10) == 1.0
        assert normalize_score(15, 0, 10) == 1.0  # clamped

    def test_clamp(self):
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0

    def test_detect_change_point_none(self):
        series = [1.0] * 20
        assert detect_change_point(series, 0.8) is None

    def test_detect_change_point_found(self):
        series = [1.0] * 10 + [0.3] * 10
        result = detect_change_point(series, 0.8)
        assert result is not None
        assert 5 <= result <= 15

    def test_linear_regression_slope_positive(self):
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]
        assert abs(linear_regression_slope(x, y) - 2.0) < 0.01

    def test_linear_regression_slope_zero(self):
        x = [1, 2, 3]
        y = [5, 5, 5]
        assert linear_regression_slope(x, y) == 0.0

    def test_action_distribution(self):
        turns = [
            _snap(1, BenchmarkActionType.BUILD),
            _snap(2, BenchmarkActionType.BUILD),
            _snap(3, BenchmarkActionType.PASS),
            _snap(4, BenchmarkActionType.TRADE_BUY),
        ]
        dist = action_distribution(turns)
        assert abs(dist["BUILD"] - 0.5) < 0.01
        assert abs(dist["PASS"] - 0.25) < 0.01
        assert abs(dist["TRADE_BUY"] - 0.25) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# NUMERICAL METRICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestNumericalMetrics:
    def setup_method(self):
        self.collector = NumericalCollector()

    def test_all_valid(self):
        turns = [_snap(i, valid=True) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        rate = next(r for r in results if r.metric_id == "2.1_invalid_action_rate")
        assert rate.value == 1.0

    def test_all_invalid(self):
        turns = [_snap(i, valid=False) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        rate = next(r for r in results if r.metric_id == "2.1_invalid_action_rate")
        assert rate.value == 0.0

    def test_half_invalid(self):
        turns = [_snap(i, valid=(i <= 10)) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        rate = next(r for r in results if r.metric_id == "2.1_invalid_action_rate")
        assert abs(rate.value - 0.5) < 0.01

    def test_worker_sum_correct(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.ALLOCATE_WORKERS,
            params={"allocation": {"farming": 10, "mining": 6, "research": 4, "construction": 5, "defense": 3, "medicine": 2}},
            population=30,
        ) for i in range(1, 6)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.2_worker_sum_accuracy")
        assert metric.value == 1.0

    def test_worker_sum_incorrect(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.ALLOCATE_WORKERS,
            params={"allocation": {"farming": 15, "mining": 10, "research": 5, "construction": 5, "defense": 3, "medicine": 2}},
            population=30,  # sum=40 != 30
        ) for i in range(1, 6)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.2_worker_sum_accuracy")
        assert metric.value == 0.0

    def test_no_allocations_returns_perfect(self):
        turns = [_snap(i) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.2_worker_sum_accuracy")
        assert metric.value == 1.0

    def test_over_capacity_detected(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.TRADE_BUY,
            params={"resource": "food", "quantity": 500},
            food=400,  # 400 + 500 > 500 capacity
        ) for i in range(1, 4)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.3_over_capacity_errors")
        assert metric.value == 0.0

    def test_no_over_capacity(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.TRADE_BUY,
            params={"resource": "food", "quantity": 10},
            food=50,  # 50 + 10 < 500 capacity
        ) for i in range(1, 4)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.3_over_capacity_errors")
        assert metric.value == 1.0

    def test_trade_math_sufficient_gold(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.TRADE_BUY,
            params={"resource": "food", "quantity": 5},
            gold=100,  # price=2, cost=10 <= 100 ✓
            market_food=2.0,
        ) for i in range(1, 4)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.5_trade_math_accuracy")
        assert metric.value == 1.0

    def test_trade_math_insufficient_gold(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.TRADE_BUY,
            params={"resource": "food", "quantity": 100},
            gold=5,  # price=2, cost=200 > 5 ✗
            market_food=2.0,
        ) for i in range(1, 4)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.5_trade_math_accuracy")
        assert metric.value == 0.0

    def test_production_rate_all_valid_builds(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.BUILD,
            params={"building_type": "farm"},
            valid=True,
        ) for i in range(1, 6)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.4_production_rate_awareness")
        assert metric.value == 1.0

    def test_production_rate_invalid_builds(self):
        turns = [_snap(
            i,
            action=BenchmarkActionType.BUILD,
            params={"building_type": "farm"},
            valid=False,
        ) for i in range(1, 6)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "2.4_production_rate_awareness")
        assert metric.value == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PLANNING METRICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanningMetrics:
    def setup_method(self):
        self.collector = PlanningCollector()

    def test_correct_build_order(self):
        """Farm before housing = correct prerequisite."""
        turns = [
            _snap(1, BenchmarkActionType.BUILD, {"building_type": "farm"}),
            _snap(2, BenchmarkActionType.BUILD, {"building_type": "housing"}),
        ]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.1_build_order_efficiency")
        assert metric.value == 1.0

    def test_incorrect_build_order(self):
        """Housing before farm = violated prerequisite."""
        turns = [
            _snap(1, BenchmarkActionType.BUILD, {"building_type": "housing"}),
            _snap(2, BenchmarkActionType.BUILD, {"building_type": "farm"}),
        ]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.1_build_order_efficiency")
        assert metric.value == 0.0

    def test_no_builds(self):
        turns = [_snap(i) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.1_build_order_efficiency")
        assert metric.value == 0.5  # Neutral

    def test_housing_before_growth_no_cap(self):
        """Never hitting pop cap = perfect score."""
        turns = [_snap(i, population=20, pop_cap=50) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.5_housing_before_growth")
        assert metric.value == 1.0

    def test_housing_before_growth_always_capped(self):
        """Always at pop cap = worst score."""
        turns = [_snap(i, population=50, pop_cap=50) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.5_housing_before_growth")
        assert metric.value == 0.0

    def test_resource_stockpile_no_unnecessary_passes(self):
        """No PASS when actions available = good."""
        turns = [_snap(i, action=BenchmarkActionType.BUILD, params={"building_type": "farm"}) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.6_resource_stockpile_timing")
        assert metric.value == 1.0

    def test_resource_stockpile_all_unnecessary_passes(self):
        """PASS when non-PASS actions available = bad."""
        available = [
            AvailableAction(action_type="BUILD", description="build farm"),
            AvailableAction(action_type="PASS", description="pass"),
        ]
        turns = [_snap(i, action=BenchmarkActionType.PASS, available_actions=available) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.6_resource_stockpile_timing")
        assert metric.value < 0.5

    def test_market_timing_no_trades(self):
        turns = [_snap(i) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "1.3_market_timing")
        assert metric.value == 0.5  # Neutral


# ═══════════════════════════════════════════════════════════════════════════════
# FLEXIBILITY METRICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlexibilityMetrics:
    def setup_method(self):
        self.collector = FlexibilityCollector()

    def test_no_starvation_perfect(self):
        turns = [_snap(i, food=100) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.5_starvation_response_speed")
        assert metric.value == 1.0

    def test_starvation_long_duration(self):
        """10 turns of starvation = 0 score."""
        turns = [_snap(i, food=0.0) for i in range(1, 11)]
        turns += [_snap(i, food=50) for i in range(11, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.5_starvation_response_speed")
        assert metric.value == 0.0

    def test_starvation_fast_recovery(self):
        """2 turns of starvation then recovery = good score."""
        turns = [_snap(1, food=0.0), _snap(2, food=0.0)]
        turns += [_snap(i, food=50) for i in range(3, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.5_starvation_response_speed")
        assert metric.value == 0.8

    def test_no_catastrophe_neutral(self):
        turns = [_snap(i) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        recovery = next(r for r in results if r.metric_id == "3.1_post_catastrophe_recovery")
        assert recovery.value == 0.5

    def test_action_distribution_shift_no_turns(self):
        rec = _recording([])
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.7_action_distribution_shift")
        assert metric.value == 0.5

    def test_repair_prioritization_no_repairs(self):
        turns = [_snap(i) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.3_repair_prioritization")
        assert metric.value == 0.5

    def test_defense_investment_no_catastrophe(self):
        turns = [_snap(i) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "3.6_defense_investment_after_hit")
        assert metric.value == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT PRESSURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextPressureMetrics:
    def setup_method(self):
        self.collector = ContextPressureCollector()

    def test_stable_quality(self):
        """Consistent quality across all quartiles = 1.0."""
        turns = [_snap(i, valid=True, score=i * 10) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "6.1_per_quartile_quality")
        assert metric.value >= 0.8

    def test_degrading_quality(self):
        """Valid in Q1, invalid in Q4 = low score."""
        turns = []
        for i in range(1, 21):
            valid = i <= 10  # First half valid, second half invalid
            turns.append(_snap(i, valid=valid, score=100 if valid else 50))
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "6.1_per_quartile_quality")
        assert metric.value < 0.8

    def test_no_collapse(self):
        """All valid = no collapse = 1.0."""
        turns = [_snap(i, valid=True) for i in range(1, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "6.3_context_collapse_point")
        assert metric.value == 1.0

    def test_early_collapse(self):
        """Invalid from turn 3 onward = early collapse."""
        turns = [_snap(1, valid=True), _snap(2, valid=True)]
        turns += [_snap(i, valid=False) for i in range(3, 21)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        metric = next(r for r in results if r.metric_id == "6.3_context_collapse_point")
        assert metric.value < 0.5

    def test_too_few_turns_neutral(self):
        turns = [_snap(1), _snap(2)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        quartile = next(r for r in results if r.metric_id == "6.1_per_quartile_quality")
        assert quartile.value == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# OPPONENT-AWARE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestOpponentAwareMetrics:
    def setup_method(self):
        self.collector = OpponentAwareCollector()

    def test_all_wins(self):
        recs = [
            _recording([], final_score=500, opponent_final_score=200, opponent_type="random"),
            _recording([], final_score=500, opponent_final_score=200, opponent_type="balanced"),
        ]
        results = self.collector.compute(recs)
        metric = next(r for r in results if r.metric_id == "5.1_win_rate_vs_archetypes")
        assert metric.value == 1.0

    def test_all_losses(self):
        recs = [
            _recording([], final_score=100, opponent_final_score=500, opponent_type="random"),
            _recording([], final_score=100, opponent_final_score=500, opponent_type="balanced"),
        ]
        results = self.collector.compute(recs)
        metric = next(r for r in results if r.metric_id == "5.1_win_rate_vs_archetypes")
        assert metric.value == 0.0

    def test_exploitation_resistance_equal(self):
        recs = [
            _recording([], final_score=400, opponent_final_score=200, opponent_type="adversarial"),
            _recording([], final_score=400, opponent_final_score=200, opponent_type="balanced"),
        ]
        results = self.collector.compute(recs)
        metric = next(r for r in results if r.metric_id == "5.2_exploitation_resistance")
        assert metric.value == 1.0

    def test_exploitation_resistance_weak(self):
        recs = [
            _recording([], final_score=100, opponent_final_score=200, opponent_type="adversarial"),
            _recording([], final_score=400, opponent_final_score=200, opponent_type="balanced"),
        ]
        results = self.collector.compute(recs)
        metric = next(r for r in results if r.metric_id == "5.2_exploitation_resistance")
        assert metric.value == 0.25  # 100/400

    def test_no_recordings(self):
        results = self.collector.compute([])
        assert all(r.value == 0.5 for r in results)

    def test_cooperative_surplus_no_trades(self):
        turns = [_snap(i) for i in range(1, 11)]
        recs = [_recording(turns)]
        results = self.collector.compute(recs)
        metric = next(r for r in results if r.metric_id == "5.4_cooperative_surplus")
        assert metric.value == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# STATE PROBES TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateProbeMetrics:
    def setup_method(self):
        self.collector = StateProbeCollector()

    def test_no_probes_neutral(self):
        turns = [_snap(i) for i in range(1, 11)]
        rec = _recording(turns)
        results = self.collector.compute(rec)
        assert all(r.value == 0.5 for r in results)
        assert len(results) == 4

    def test_evaluate_building_recall_perfect(self):
        state = _state(buildings=[
            BuildingState(type="farm", level=2, health=180, max_health=200),
            BuildingState(type="wall", level=1, health=100, max_health=100),
        ])
        response = "I have a farm (level 2, ~90% health) and a wall (level 1, 100% health)"
        result = evaluate_building_recall(response, state)
        assert result.score == 1.0

    def test_evaluate_building_recall_partial(self):
        state = _state(buildings=[
            BuildingState(type="farm", level=2, health=200, max_health=200),
            BuildingState(type="wall", level=1, health=100, max_health=100),
            BuildingState(type="library", level=1, health=100, max_health=100),
        ])
        response = "I have a farm and a wall"
        result = evaluate_building_recall(response, state)
        # Recalled 2/3 buildings
        assert 0.5 < result.score < 1.0

    def test_evaluate_resource_awareness_exact(self):
        state = _state(food=100, materials=80, knowledge=20, gold=50)
        response = "food=100, materials=80, knowledge=20, gold=50"
        result = evaluate_resource_awareness(response, state)
        assert result.score == 1.0

    def test_evaluate_resource_awareness_within_tolerance(self):
        state = _state(food=100, materials=80, knowledge=20, gold=50)
        response = "food=110, materials=85, knowledge=22, gold=48"
        result = evaluate_resource_awareness(response, state)
        assert result.score > 0.8  # Within 15% tolerance

    def test_evaluate_resource_awareness_way_off(self):
        state = _state(food=100, materials=80, knowledge=20, gold=50)
        response = "food=500, materials=10, knowledge=200, gold=5"
        result = evaluate_resource_awareness(response, state)
        assert result.score < 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS ENGINE FACADE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMetricsEngine:
    def test_compute_game_metrics(self):
        engine = MetricsEngine()
        turns = [_snap(i) for i in range(1, 21)]
        rec = _recording(turns)
        results = engine.compute_game_metrics(rec)
        # Should have all per-game metrics
        assert "2.1_invalid_action_rate" in results
        assert "1.1_build_order_efficiency" in results
        assert "3.1_post_catastrophe_recovery" in results
        assert "6.1_per_quartile_quality" in results
        assert "4.1_building_recall" in results

    def test_compute_cross_game_metrics(self):
        engine = MetricsEngine()
        recs = [
            _recording([], final_score=500, opponent_final_score=200, opponent_type="random"),
            _recording([], final_score=400, opponent_final_score=300, opponent_type="balanced"),
        ]
        results = engine.compute_cross_game_metrics(recs)
        assert "5.1_win_rate_vs_archetypes" in results

    def test_compute_all(self):
        engine = MetricsEngine()
        turns = [_snap(i) for i in range(1, 21)]
        recs = [_recording(turns, opponent_type="random")]
        results = engine.compute_all(recs)
        # Should have both per-game and cross-game
        assert "2.1_invalid_action_rate" in results
        assert "5.1_win_rate_vs_archetypes" in results

    def test_get_metric_ids(self):
        engine = MetricsEngine()
        ids = engine.get_metric_ids()
        assert len(ids) == 31
        assert "1.1_build_order_efficiency" in ids
        assert "6.3_context_collapse_point" in ids

    def test_all_metrics_normalized(self):
        """All metric values should be in [0, 1]."""
        engine = MetricsEngine()
        turns = [_snap(i, valid=True) for i in range(1, 21)]
        rec = _recording(turns)
        results = engine.compute_game_metrics(rec)
        for mid, result in results.items():
            assert 0.0 <= result.value <= 1.0, f"{mid} value {result.value} out of range"
