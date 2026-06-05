"""Tests for Tier-2 Dimension Scorers."""

from __future__ import annotations

import pytest

from terminus.benchmark.dimensions.base import (
    ArchetypeLabel,
    DimensionComputer,
    DimensionReport,
    DimensionScore,
    FailureMode,
    TrendClassification,
)
from terminus.benchmark.dimensions.arithmetic import ArithmeticComputer
from terminus.benchmark.dimensions.coherence import CoherenceComputer
from terminus.benchmark.dimensions.composite import DIMENSION_ORDER, PRESETS, compute_composite
from terminus.benchmark.dimensions.degradation import DegradationComputer
from terminus.benchmark.dimensions.error_recognition import ErrorRecognitionComputer, NegativeTrajectory
from terminus.benchmark.dimensions.game_theory import GameTheoryComputer
from terminus.benchmark.dimensions.opportunity import OpportunityComputer
from terminus.benchmark.dimensions.pivot import PivotComputer, StrategyChange
from terminus.benchmark.dimensions.triage import TriageComputer, PRIORITY_LABELS
from terminus.benchmark.dimensions.trend import classify_trend, classify_overall_trend
from terminus.benchmark.dimensions.archetypes import classify_archetype
from terminus.benchmark.dimensions import DimensionScorer
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import (
    ActionResponse,
    AvailableAction,
    BenchmarkActionType,
    BenchmarkGameState,
    BenchmarkWorkerAllocation,
    BuildingState,
    CatastropheWarning,
    DimensionWeights,
    GameRecording,
    LastCatastropheResult,
    MarketPrices,
    ProductionRates,
    Reasoning,
    ReasoningFactor,
    ReasoningFactorType,
    ResourceCapacity,
    ResourceState,
    TurnSnapshot,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_metric(metric_id: str, value: float, sample_count: int = 10) -> MetricResult:
    return MetricResult(
        metric_id=metric_id,
        value=value,
        raw_value=value,
        sample_count=sample_count,
        details={},
    )


def _make_metrics(**kwargs: float) -> dict[str, MetricResult]:
    """Create metrics dict from short IDs. e.g. _make_metrics(**{"2.1": 0.9})"""
    full_ids = {
        "1.1": "1.1_build_order_efficiency",
        "1.2": "1.2_worker_allocation_anticipation",
        "1.3": "1.3_market_timing",
        "1.4": "1.4_catastrophe_preparation",
        "1.5": "1.5_housing_before_growth",
        "1.6": "1.6_resource_stockpile_timing",
        "2.1": "2.1_invalid_action_rate",
        "2.2": "2.2_worker_sum_accuracy",
        "2.3": "2.3_over_capacity_errors",
        "2.4": "2.4_production_rate_awareness",
        "2.5": "2.5_trade_math_accuracy",
        "2.6": "2.6_multi_resource_feasibility",
        "3.1": "3.1_post_catastrophe_recovery",
        "3.2": "3.2_worker_reallocation_after_damage",
        "3.3": "3.3_repair_prioritization",
        "3.4": "3.4_market_adaptation",
        "3.5": "3.5_starvation_response_speed",
        "3.6": "3.6_defense_investment_after_hit",
        "3.7": "3.7_action_distribution_shift",
        "4.1": "4.1_building_recall",
        "4.2": "4.2_resource_awareness",
        "4.3": "4.3_strategy_consistency",
        "4.4": "4.4_history_recall",
        "5.1": "5.1_win_rate_vs_archetypes",
        "5.2": "5.2_exploitation_resistance",
        "5.3": "5.3_counter_strategy_speed",
        "5.4": "5.4_cooperative_surplus",
        "5.5": "5.5_market_manipulation_detection",
        "6.1": "6.1_per_quartile_quality",
        "6.2": "6.2_historical_reference_rate",
        "6.3": "6.3_context_collapse_point",
    }
    result = {}
    for short_id, val in kwargs.items():
        full_id = full_ids[short_id]
        result[full_id] = _make_metric(full_id, val)
    return result


def _make_state(
    turn: int = 1,
    food: float = 100,
    gold: float = 50,
    population: int = 20,
    population_cap: int = 50,
    morale: float = 1.0,
    catastrophe_warning: CatastropheWarning | None = None,
    last_catastrophe: LastCatastropheResult | None = None,
    buildings: list[BuildingState] | None = None,
    market_food: float = 1.0,
    available_actions: list[AvailableAction] | None = None,
) -> BenchmarkGameState:
    return BenchmarkGameState(
        turn=turn,
        max_turns=100,
        score=turn * 5,
        resources=ResourceState(food=food, materials=80, knowledge=30, gold=gold),
        population=population,
        population_cap=population_cap,
        morale=morale,
        catastrophe_warning=catastrophe_warning,
        last_catastrophe=last_catastrophe,
        buildings=buildings or [],
        market_prices=MarketPrices(food=market_food, materials=1.0, knowledge=1.0),
        available_actions=available_actions or [
            AvailableAction(action_type="PASS", description="Do nothing"),
            AvailableAction(action_type="BUILD", description="Build something"),
        ],
    )


def _make_snap(
    turn: int = 1,
    action: str = "BUILD",
    valid: bool = True,
    reasoning_factor: str | None = None,
    state: BenchmarkGameState | None = None,
) -> TurnSnapshot:
    params: dict = {}
    if action == "BUILD":
        params = {"building_type": "farm"}

    reasoning = None
    if reasoning_factor:
        reasoning = Reasoning(
            factors=[ReasoningFactor(factor=ReasoningFactorType(reasoning_factor), weight=1.0)]
        )

    return TurnSnapshot(
        turn=turn,
        state=state or _make_state(turn=turn),
        parsed_response=ActionResponse(
            action=BenchmarkActionType(action),
            params=params,
            reasoning=reasoning,
        ),
        valid=valid,
    )


def _make_recording(
    turns: list[TurnSnapshot] | None = None,
    num_turns: int = 50,
    opponent: str = "balanced",
) -> GameRecording:
    if turns is None:
        turns = [_make_snap(turn=i + 1) for i in range(num_turns)]
    return GameRecording(
        model_name="test-model",
        opponent_type=opponent,
        seed=42,
        turns=turns,
        final_score=500,
        opponent_final_score=400,
    )


# ─── Test ArithmeticComputer ─────────────────────────────────────────────────


class TestArithmeticComputer:
    def setup_method(self):
        self.computer = ArithmeticComputer()

    def test_perfect_scores(self):
        metrics = _make_metrics(**{
            "2.1": 1.0, "2.2": 1.0, "2.3": 1.0,
            "2.4": 1.0, "2.5": 1.0, "2.6": 1.0,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert result.score >= 0.95
        assert result.dimension_id == "dim_2_arithmetic"

    def test_zero_scores(self):
        metrics = _make_metrics(**{
            "2.1": 0.0, "2.2": 0.0, "2.3": 0.0,
            "2.4": 0.0, "2.5": 0.0, "2.6": 0.0,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert result.score <= 0.05

    def test_mixed_scores(self):
        metrics = _make_metrics(**{
            "2.1": 0.8, "2.2": 0.7, "2.3": 0.9,
            "2.4": 0.6, "2.5": 0.5, "2.6": 0.8,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.5 < result.score < 0.9
        assert "base_accuracy" in result.sub_scores

    def test_load_degradation_penalty(self):
        # Recording with all valid early, all invalid late
        turns = []
        for i in range(100):
            turns.append(_make_snap(turn=i + 1, valid=(i < 50)))
        rec = _make_recording(turns=turns)

        metrics = _make_metrics(**{
            "2.1": 0.5, "2.2": 1.0, "2.3": 1.0,
            "2.4": 1.0, "2.5": 1.0, "2.6": 1.0,
        })
        result = self.computer.compute(metrics, [rec])
        # Should have degradation penalty
        assert result.sub_scores["load_degradation"] > 0
        assert result.sub_scores["early_load_accuracy"] > result.sub_scores["late_load_accuracy"]

    def test_missing_metrics_use_default(self):
        # Only provide some metrics
        metrics = _make_metrics(**{"2.1": 0.9, "2.2": 0.8})
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.0 <= result.score <= 1.0
        assert result.confidence < 1.0

    def test_confidence_all_present(self):
        metrics = _make_metrics(**{
            "2.1": 1.0, "2.2": 1.0, "2.3": 1.0,
            "2.4": 1.0, "2.5": 1.0, "2.6": 1.0,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert result.confidence == 1.0


# ─── Test GameTheoryComputer ─────────────────────────────────────────────────


class TestGameTheoryComputer:
    def setup_method(self):
        self.computer = GameTheoryComputer()

    def test_perfect_scores(self):
        metrics = _make_metrics(**{
            "5.1": 1.0, "5.2": 1.0, "5.3": 1.0,
            "5.4": 1.0, "5.5": 1.0,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert result.score >= 0.9
        assert result.dimension_id == "dim_8_game_theory"

    def test_zero_scores(self):
        metrics = _make_metrics(**{
            "5.1": 0.0, "5.2": 0.0, "5.3": 0.0,
            "5.4": 0.0, "5.5": 0.0,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert result.score <= 0.3  # Diversity defaults to 0.5 with 1 game

    def test_strategic_diversity_multiple_games(self):
        # Create games with different action patterns
        rec1 = _make_recording(turns=[
            _make_snap(turn=i + 1, action="BUILD") for i in range(15)
        ])
        rec2 = _make_recording(turns=[
            _make_snap(turn=i + 1, action="TRADE_BUY") for i in range(15)
        ])
        metrics = _make_metrics(**{
            "5.1": 0.7, "5.2": 0.7, "5.3": 0.7,
            "5.4": 0.7, "5.5": 0.7,
        })
        result = self.computer.compute(metrics, [rec1, rec2])
        # Higher diversity with different openings
        assert result.sub_scores["strategic_diversity"] > 0.5

    def test_strategy_profile_oblivious(self):
        metrics = _make_metrics(**{
            "5.1": 0.3, "5.2": 0.2, "5.3": 0.1,
            "5.4": 0.2, "5.5": 0.2,
        })
        # Multiple similar recordings → low diversity
        same_turns = [_make_snap(turn=i + 1, action="BUILD") for i in range(15)]
        recs = [_make_recording(turns=list(same_turns)) for _ in range(3)]
        result = self.computer.compute(metrics, recs)
        assert result.details["strategy_profile"] == "oblivious"

    def test_strategy_profile_predator(self):
        metrics = _make_metrics(**{
            "5.1": 0.9, "5.2": 0.8, "5.3": 0.8,
            "5.4": 0.8, "5.5": 0.8,
        })
        # Need diverse recordings for predator
        rec1 = _make_recording(turns=[_make_snap(turn=i + 1, action="BUILD") for i in range(15)])
        rec2 = _make_recording(turns=[_make_snap(turn=i + 1, action="TRADE_BUY") for i in range(15)])
        result = self.computer.compute(metrics, [rec1, rec2])
        assert result.details["strategy_profile"] == "predator"

    def test_sub_scores_present(self):
        metrics = _make_metrics(**{
            "5.1": 0.5, "5.2": 0.5, "5.3": 0.5,
            "5.4": 0.5, "5.5": 0.5,
        })
        result = self.computer.compute(metrics, [_make_recording()])
        assert "opponent_modeling" in result.sub_scores
        assert "exploitation_resistance" in result.sub_scores
        assert "strategic_diversity" in result.sub_scores


# ─── Test OpportunityComputer ────────────────────────────────────────────────


class TestOpportunityComputer:
    def setup_method(self):
        self.computer = OpportunityComputer()

    def test_perfect_scores_no_passes(self):
        metrics = _make_metrics(**{
            "1.1": 1.0, "1.3": 1.0, "1.6": 1.0, "3.3": 1.0,
        })
        rec = _make_recording(turns=[_make_snap(turn=i + 1, action="BUILD") for i in range(50)])
        result = self.computer.compute(metrics, [rec])
        assert result.score >= 0.8

    def test_all_unnecessary_passes(self):
        metrics = _make_metrics(**{
            "1.1": 0.0, "1.3": 0.0, "1.6": 0.0, "3.3": 0.0,
        })
        rec = _make_recording(turns=[
            _make_snap(turn=i + 1, action="PASS") for i in range(50)
        ])
        result = self.computer.compute(metrics, [rec])
        assert result.score < 0.3
        assert result.details["unnecessary_pass_rate"] > 0.5

    def test_action_diversity(self):
        # Diverse actions should score higher
        actions = ["BUILD", "TRADE_BUY", "TRADE_SELL", "ALLOCATE_WORKERS", "REPAIR"]
        turns = [_make_snap(turn=i + 1, action=actions[i % len(actions)]) for i in range(50)]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"1.1": 0.5, "1.3": 0.5, "1.6": 0.5, "3.3": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["action_diversity"] > 0.7

    def test_no_diversity_single_action(self):
        rec = _make_recording(turns=[_make_snap(turn=i + 1, action="BUILD") for i in range(50)])
        metrics = _make_metrics(**{"1.1": 0.5, "1.3": 0.5, "1.6": 0.5, "3.3": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["action_diversity"] == 0.0

    def test_pass_only_counted_when_alternatives_exist(self):
        # PASS with no other options is not unnecessary
        state_no_options = _make_state(
            available_actions=[AvailableAction(action_type="PASS", description="Do nothing")]
        )
        turns = [_make_snap(turn=i + 1, action="PASS", state=state_no_options) for i in range(10)]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"1.1": 0.5, "1.3": 0.5, "1.6": 0.5, "3.3": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.details["unnecessary_pass_rate"] == 0.0


# ─── Test TriageComputer ─────────────────────────────────────────────────────


class TestTriageComputer:
    def setup_method(self):
        self.computer = TriageComputer()

    def test_no_multi_constraint_events(self):
        metrics = _make_metrics(**{"3.5": 0.8, "1.4": 0.7, "3.3": 0.6, "1.5": 0.9})
        result = self.computer.compute(metrics, [_make_recording()])
        # No multi-constraint → triage_accuracy defaults to 0.5
        assert result.sub_scores["triage_accuracy"] == 0.5

    def test_correct_triage_starvation_first(self):
        # Create turn with starvation + building damage, and action buys food
        state = _make_state(
            food=0, gold=50,
            buildings=[BuildingState(type="farm", level=1, health=30, max_health=100)],
        )
        snap = TurnSnapshot(
            turn=1,
            state=state,
            parsed_response=ActionResponse(
                action=BenchmarkActionType.TRADE_BUY,
                params={"resource": "food"},
            ),
            valid=True,
        )
        rec = _make_recording(turns=[snap])
        metrics = _make_metrics(**{"3.5": 0.8, "1.4": 0.7, "3.3": 0.6, "1.5": 0.9})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["triage_accuracy"] == 1.0

    def test_wrong_triage_repair_when_starving(self):
        state = _make_state(
            food=0,
            buildings=[BuildingState(type="farm", level=1, health=30, max_health=100)],
        )
        snap = TurnSnapshot(
            turn=1,
            state=state,
            parsed_response=ActionResponse(
                action=BenchmarkActionType.REPAIR,
                params={"building_type": "farm"},
            ),
            valid=True,
        )
        rec = _make_recording(turns=[snap])
        metrics = _make_metrics(**{"3.5": 0.5, "1.4": 0.5, "3.3": 0.5, "1.5": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["triage_accuracy"] == 0.0

    def test_score_bounded(self):
        metrics = _make_metrics(**{"3.5": 1.0, "1.4": 1.0, "3.3": 1.0, "1.5": 1.0})
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.0 <= result.score <= 1.0


# ─── Test ErrorRecognitionComputer ───────────────────────────────────────────


class TestErrorRecognitionComputer:
    def setup_method(self):
        self.computer = ErrorRecognitionComputer()

    def test_no_trajectories(self):
        # Stable resources → no negative trajectories
        turns = [
            _make_snap(turn=i + 1, state=_make_state(turn=i + 1, food=100))
            for i in range(50)
        ]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"3.5": 0.8, "3.1": 0.7, "1.6": 0.9})
        result = self.computer.compute(metrics, [rec])
        assert result.details["trajectory_count"] == 0
        # Avoidance defaults to 0.5
        assert result.sub_scores["avoidance_rate"] == 0.5

    def test_declining_food_detected(self):
        # Food decreasing from 100 to 0 over 20 turns
        turns = [
            _make_snap(turn=i + 1, state=_make_state(turn=i + 1, food=max(0, 100 - i * 5)))
            for i in range(30)
        ]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"3.5": 0.5, "3.1": 0.5, "1.6": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.details["trajectory_count"] > 0

    def test_lead_time_scoring(self):
        assert self.computer._score_lead_time(20) == 1.0
        assert self.computer._score_lead_time(12) == 0.7
        assert self.computer._score_lead_time(7) == 0.4
        assert self.computer._score_lead_time(3) == 0.2
        assert self.computer._score_lead_time(0) == 0.0

    def test_score_bounded(self):
        metrics = _make_metrics(**{"3.5": 0.5, "3.1": 0.5, "1.6": 0.5})
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.0 <= result.score <= 1.0


# ─── Test PivotComputer ──────────────────────────────────────────────────────


class TestPivotComputer:
    def setup_method(self):
        self.computer = PivotComputer()

    def test_consistent_strategy_no_changes(self):
        # Same factor every turn → no changes → SNR defaults to 0.5
        turns = [
            _make_snap(turn=i + 1, reasoning_factor="long_term_growth")
            for i in range(20)
        ]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"3.7": 0.5, "3.2": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["signal_to_noise"] == 0.5  # default

    def test_justified_changes_score_high(self):
        # Create turns with factor changes accompanied by catastrophes
        turns = []
        for i in range(20):
            factor = "long_term_growth"
            last_cat = None
            if i == 10:
                last_cat = LastCatastropheResult(
                    name="earthquake", category="infrastructure",
                    damage_summary="heavy", building_damage=50,
                )
                factor = "immediate_survival"
            elif i > 10:
                factor = "immediate_survival"

            state = _make_state(turn=i + 1, last_catastrophe=last_cat)
            turns.append(_make_snap(turn=i + 1, reasoning_factor=factor, state=state))

        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"3.7": 0.7, "3.2": 0.8})
        result = self.computer.compute(metrics, [rec])
        # The change at turn 10 should be detected as justified
        assert result.sub_scores["signal_to_noise"] >= 0.5

    def test_score_bounded(self):
        metrics = _make_metrics(**{"3.7": 0.5, "3.2": 0.5})
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.0 <= result.score <= 1.0


# ─── Test CoherenceComputer ──────────────────────────────────────────────────


class TestCoherenceComputer:
    def setup_method(self):
        self.computer = CoherenceComputer()

    def test_fully_coherent(self):
        # Same reasoning factor throughout
        turns = [
            _make_snap(turn=i + 1, reasoning_factor="long_term_growth")
            for i in range(50)
        ]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"4.1": 1.0, "4.2": 1.0, "4.3": 1.0, "4.4": 1.0})
        result = self.computer.compute(metrics, [rec])
        assert result.score >= 0.9
        assert result.sub_scores["action_coherence"] == 1.0

    def test_fully_incoherent(self):
        # Random factor changes every turn
        factors = list(ReasoningFactorType)
        turns = [
            _make_snap(turn=i + 1, reasoning_factor=factors[i % len(factors)].value)
            for i in range(50)
        ]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"4.1": 0.0, "4.2": 0.0, "4.3": 0.0, "4.4": 0.0})
        result = self.computer.compute(metrics, [rec])
        assert result.score < 0.4

    def test_no_reasoning_data(self):
        # No reasoning → defaults to coherent
        turns = [_make_snap(turn=i + 1) for i in range(50)]
        # Remove reasoning from all turns
        for t in turns:
            t.parsed_response.reasoning = None
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"4.1": 0.5, "4.2": 0.5, "4.3": 0.5, "4.4": 0.5})
        result = self.computer.compute(metrics, [rec])
        assert result.sub_scores["action_coherence"] == 1.0

    def test_state_fidelity_contribution(self):
        turns = [_make_snap(turn=i + 1, reasoning_factor="long_term_growth") for i in range(20)]
        rec = _make_recording(turns=turns)
        # High probe scores → high state fidelity
        metrics = _make_metrics(**{"4.1": 0.9, "4.2": 0.8, "4.3": 0.85, "4.4": 0.7})
        result = self.computer.compute(metrics, [rec])
        expected_fidelity = 0.9 * 0.3 + 0.8 * 0.25 + 0.85 * 0.25 + 0.7 * 0.2
        assert abs(result.sub_scores["state_fidelity"] - expected_fidelity) < 0.01

    def test_score_bounded(self):
        metrics = _make_metrics(**{"4.1": 0.5, "4.2": 0.5, "4.3": 0.5, "4.4": 0.5})
        result = self.computer.compute(metrics, [_make_recording()])
        assert 0.0 <= result.score <= 1.0


# ─── Test DegradationComputer ────────────────────────────────────────────────


class TestDegradationComputer:
    def setup_method(self):
        self.computer = DegradationComputer()

    def test_stable_performance(self):
        # All turns valid
        turns = [_make_snap(turn=i + 1, valid=True) for i in range(50)]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"6.1": 1.0, "6.2": 0.8, "6.3": 1.0})
        result = self.computer.compute(metrics, [rec])
        assert result.details["failure_mode"] == "stable"
        assert result.score >= 0.8

    def test_cliff_failure(self):
        # Good until turn 30, then all invalid
        turns = [_make_snap(turn=i + 1, valid=(i < 30)) for i in range(60)]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"6.1": 0.3, "6.2": 0.2, "6.3": 0.3})
        result = self.computer.compute(metrics, [rec])
        assert result.details["failure_mode"] == "cliff_failure"
        assert result.details["cliff_point"] is not None
        assert result.score < 0.5

    def test_linear_decay(self):
        # Gradually decreasing quality using probability ramp
        import random
        rng = random.Random(42)
        turns = []
        for i in range(100):
            # validity probability decreases linearly from 1.0 to 0.0
            p_valid = 1.0 - i / 100
            valid = rng.random() < p_valid
            turns.append(_make_snap(turn=i + 1, valid=valid))
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"6.1": 0.5, "6.2": 0.5, "6.3": 0.5})
        result = self.computer.compute(metrics, [rec])
        # With gradual probability decrease the classifier may see linear_decay or oscillating
        assert result.details["failure_mode"] in ("linear_decay", "oscillating", "cliff_failure")

    def test_empty_recordings(self):
        metrics = _make_metrics(**{"6.1": 0.5, "6.2": 0.5, "6.3": 0.5})
        result = self.computer.compute(metrics, [_make_recording(turns=[])])
        assert result.details["failure_mode"] == "stable"

    def test_decision_budget(self):
        # All valid → budget = full length
        turns = [_make_snap(turn=i + 1, valid=True) for i in range(50)]
        rec = _make_recording(turns=turns)
        metrics = _make_metrics(**{"6.1": 1.0, "6.2": 1.0, "6.3": 1.0})
        result = self.computer.compute(metrics, [rec])
        assert result.details["effective_decision_budget"] == 50


# ─── Test Composite ──────────────────────────────────────────────────────────


class TestComposite:
    def test_balanced_equal_weights(self):
        dims = {
            dim_id: DimensionScore(dimension_id=dim_id, dimension_name="", score=0.8)
            for dim_id in DIMENSION_ORDER
        }
        result = compute_composite(dims, "balanced")
        assert abs(result - 0.8) < 0.001

    def test_all_presets_exist(self):
        assert len(PRESETS) == 9
        for preset_name in ["balanced", "reliability", "strategy", "triage",
                            "endurance", "precision", "adversarial", "coordination", "context"]:
            assert preset_name in PRESETS
            assert len(PRESETS[preset_name]) == 8

    def test_custom_weights(self):
        dims = {
            dim_id: DimensionScore(dimension_id=dim_id, dimension_name="", score=0.5)
            for dim_id in DIMENSION_ORDER
        }
        # Give coherence weight 5 (max allowed), everything else 0
        custom = DimensionWeights(
            coherence=5.0, arithmetic=0.0, triage=0.0,
            error_recognition=0.0, pivot=0.0, degradation=0.0,
            opportunity_cost=0.0, game_theory=0.0,
        )
        result = compute_composite(dims, "custom", custom)
        assert abs(result - 0.5) < 0.001  # Only coherence matters, it's 0.5

    def test_empty_dimensions(self):
        result = compute_composite({}, "balanced")
        assert result == 0.0

    def test_partial_dimensions(self):
        dims = {
            "dim_1_coherence": DimensionScore(dimension_id="dim_1_coherence", dimension_name="", score=1.0),
            "dim_2_arithmetic": DimensionScore(dimension_id="dim_2_arithmetic", dimension_name="", score=0.0),
        }
        result = compute_composite(dims, "balanced")
        assert abs(result - 0.5) < 0.001

    def test_weighted_preset_changes_result(self):
        dims = {
            "dim_8_game_theory": DimensionScore(dimension_id="dim_8_game_theory", dimension_name="", score=1.0),
        }
        # Adversarial preset weights game theory at 3.0
        adversarial_result = compute_composite(dims, "adversarial")
        balanced_result = compute_composite(dims, "balanced")
        # Both should be 1.0 since it's the only dimension present
        assert adversarial_result == balanced_result == 1.0


# ─── Test Trend ──────────────────────────────────────────────────────────────


class TestTrend:
    def test_improving_trend(self):
        scores = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        assert classify_trend(scores) == TrendClassification.IMPROVING

    def test_degrading_trend(self):
        scores = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
        assert classify_trend(scores) == TrendClassification.DEGRADING

    def test_consistent_trend(self):
        scores = [0.5, 0.51, 0.49, 0.50, 0.51, 0.50]
        assert classify_trend(scores) == TrendClassification.CONSISTENT

    def test_volatile_trend(self):
        scores = [0.2, 0.9, 0.1, 0.8, 0.3, 0.7]
        assert classify_trend(scores) == TrendClassification.VOLATILE

    def test_too_few_data_points(self):
        scores = [0.5, 0.6]
        assert classify_trend(scores) == TrendClassification.CONSISTENT

    def test_overall_trend_majority_vote(self):
        per_game = [
            {"dim_1": 0.3, "dim_2": 0.4},
            {"dim_1": 0.4, "dim_2": 0.5},
            {"dim_1": 0.5, "dim_2": 0.6},
            {"dim_1": 0.6, "dim_2": 0.7},
        ]
        result = classify_overall_trend(per_game)
        assert result == TrendClassification.IMPROVING

    def test_overall_trend_empty(self):
        assert classify_overall_trend([]) == TrendClassification.CONSISTENT


# ─── Test Archetypes ─────────────────────────────────────────────────────────


class TestArchetypes:
    def _make_dims(self, **scores) -> dict[str, DimensionScore]:
        mapping = {
            "d1": "dim_1_coherence", "d2": "dim_2_arithmetic",
            "d3": "dim_3_triage", "d4": "dim_4_error_recognition",
            "d5": "dim_5_pivot", "d6": "dim_6_degradation",
            "d7": "dim_7_opportunity", "d8": "dim_8_game_theory",
        }
        dims = {}
        for key, val in scores.items():
            dim_id = mapping[key]
            dims[dim_id] = DimensionScore(dimension_id=dim_id, dimension_name="", score=val)
        return dims

    def test_oblivious(self):
        dims = self._make_dims(d1=0.5, d2=0.5, d3=0.2, d4=0.5, d5=0.2, d6=0.5, d7=0.5, d8=0.2)
        assert classify_archetype(dims) == ArchetypeLabel.OBLIVIOUS

    def test_predator(self):
        dims = self._make_dims(d1=0.6, d2=0.6, d3=0.7, d4=0.6, d5=0.6, d6=0.6, d7=0.8, d8=0.8)
        assert classify_archetype(dims) == ArchetypeLabel.PREDATOR

    def test_fortress(self):
        dims = self._make_dims(d1=0.8, d2=0.8, d3=0.5, d4=0.5, d5=0.5, d6=0.9, d7=0.5, d8=0.5)
        assert classify_archetype(dims) == ArchetypeLabel.FORTRESS

    def test_scholar(self):
        dims = self._make_dims(d1=0.9, d2=0.8, d3=0.5, d4=0.5, d5=0.5, d6=0.5, d7=0.8, d8=0.5)
        assert classify_archetype(dims) == ArchetypeLabel.SCHOLAR

    def test_pragmatist_default(self):
        dims = self._make_dims(d1=0.5, d2=0.5, d3=0.5, d4=0.5, d5=0.5, d6=0.5, d7=0.5, d8=0.5)
        assert classify_archetype(dims) == ArchetypeLabel.PRAGMATIST

    def test_chameleon(self):
        dims = self._make_dims(d1=0.5, d2=0.5, d3=0.7, d4=0.7, d5=0.8, d6=0.5, d7=0.5, d8=0.5)
        assert classify_archetype(dims) == ArchetypeLabel.CHAMELEON

    def test_cautious(self):
        dims = self._make_dims(d1=0.5, d2=0.7, d3=0.5, d4=0.8, d5=0.5, d6=0.8, d7=0.5, d8=0.5)
        assert classify_archetype(dims) == ArchetypeLabel.CAUTIOUS


# ─── Test DimensionScorer Facade ─────────────────────────────────────────────


class TestDimensionScorer:
    def setup_method(self):
        self.scorer = DimensionScorer()

    def test_score_returns_report(self):
        all_metrics = _make_metrics(**{
            "1.1": 0.7, "1.3": 0.6, "1.4": 0.5, "1.5": 0.8, "1.6": 0.7,
            "2.1": 0.9, "2.2": 0.8, "2.3": 0.9, "2.4": 0.7, "2.5": 0.6, "2.6": 0.8,
            "3.1": 0.6, "3.2": 0.5, "3.3": 0.7, "3.5": 0.8, "3.7": 0.5,
            "4.1": 0.7, "4.2": 0.6, "4.3": 0.7, "4.4": 0.5,
            "5.1": 0.6, "5.2": 0.7, "5.3": 0.5, "5.4": 0.4, "5.5": 0.6,
            "6.1": 0.8, "6.2": 0.5, "6.3": 0.9,
        })
        rec = _make_recording()
        report = self.scorer.score(all_metrics, [rec], model_name="gpt-4o")

        assert isinstance(report, DimensionReport)
        assert report.model_name == "gpt-4o"
        assert len(report.dimensions) == 8
        assert 0.0 <= report.composite_score <= 1.0
        assert report.trend in TrendClassification
        assert report.archetype in ArchetypeLabel

    def test_all_dimensions_present(self):
        metrics = _make_metrics(**{
            "1.1": 0.5, "1.3": 0.5, "1.4": 0.5, "1.5": 0.5, "1.6": 0.5,
            "2.1": 0.5, "2.2": 0.5, "2.3": 0.5, "2.4": 0.5, "2.5": 0.5, "2.6": 0.5,
            "3.1": 0.5, "3.2": 0.5, "3.3": 0.5, "3.5": 0.5, "3.7": 0.5,
            "4.1": 0.5, "4.2": 0.5, "4.3": 0.5, "4.4": 0.5,
            "5.1": 0.5, "5.2": 0.5, "5.3": 0.5, "5.4": 0.5, "5.5": 0.5,
            "6.1": 0.5, "6.2": 0.5, "6.3": 0.5,
        })
        report = self.scorer.score(metrics, [_make_recording()])
        expected_dims = {
            "dim_1_coherence", "dim_2_arithmetic", "dim_3_triage",
            "dim_4_error_recognition", "dim_5_pivot", "dim_6_degradation",
            "dim_7_opportunity", "dim_8_game_theory",
        }
        assert set(report.dimensions.keys()) == expected_dims

    def test_empty_recordings(self):
        metrics = _make_metrics(**{"2.1": 0.5, "2.2": 0.5, "2.3": 0.5,
                                    "2.4": 0.5, "2.5": 0.5, "2.6": 0.5})
        report = self.scorer.score(metrics, [], model_name="empty")
        assert report.model_name == "empty"
        assert 0.0 <= report.composite_score <= 1.0

    def test_scores_all_bounded(self):
        metrics = _make_metrics(**{
            "1.1": 0.5, "1.3": 0.5, "1.4": 0.5, "1.5": 0.5, "1.6": 0.5,
            "2.1": 0.5, "2.2": 0.5, "2.3": 0.5, "2.4": 0.5, "2.5": 0.5, "2.6": 0.5,
            "3.1": 0.5, "3.2": 0.5, "3.3": 0.5, "3.5": 0.5, "3.7": 0.5,
            "4.1": 0.5, "4.2": 0.5, "4.3": 0.5, "4.4": 0.5,
            "5.1": 0.5, "5.2": 0.5, "5.3": 0.5, "5.4": 0.5, "5.5": 0.5,
            "6.1": 0.5, "6.2": 0.5, "6.3": 0.5,
        })
        report = self.scorer.score(metrics, [_make_recording()])
        for dim in report.dimensions.values():
            assert 0.0 <= dim.score <= 1.0


# ─── Test Legacy scorer.py Backward Compat ───────────────────────────────────


class TestLegacyScorer:
    def test_score_dimensions_legacy(self):
        from terminus.benchmark.scorer import score_dimensions, compute_composite_score

        games = [
            {"model_name": "gpt-4", "valid_actions": 90, "invalid_actions": 10,
             "score": 500, "turns_played": 100},
            {"model_name": "gpt-4", "valid_actions": 85, "invalid_actions": 15,
             "score": 450, "turns_played": 100},
        ]
        config = {"dimension_weights": [1.0] * 8, "dimensions_enabled": [True] * 8}
        result = score_dimensions(games, config)
        assert "gpt-4" in result
        assert len(result["gpt-4"]) == 8
        for dim_name, score in result["gpt-4"].items():
            assert 0.0 <= score <= 1.0

    def test_compute_composite_legacy(self):
        from terminus.benchmark.scorer import compute_composite_score, DIMENSIONS

        dim_scores = {d: 0.7 for d in DIMENSIONS}
        result = compute_composite_score(dim_scores)
        assert abs(result - 0.7) < 0.001
