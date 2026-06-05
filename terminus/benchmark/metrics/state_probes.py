"""State probe metrics (4.1–4.4) — off-clock LLM knowledge probes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from terminus.benchmark.metrics.base import MetricCollector, MetricResult
from terminus.benchmark.metrics.utils import clamp
from terminus.benchmark.schemas import BenchmarkGameState, GameRecording


@dataclass
class ProbeResult:
    """Result of a single state probe."""

    probe_type: str  # "building_recall", "resource_awareness", "strategy_consistency", "history_recall"
    turn: int
    prompt: str
    raw_response: str = ""
    ground_truth: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


# ─── Probe Prompts ────────────────────────────────────────────────────────────

PROBE_PROMPTS = {
    "building_recall": (
        "Without looking at the game state, list all your current buildings "
        "with their types, levels, and approximate health percentages. "
        "Format: building_type (level X, ~Y% health)"
    ),
    "resource_awareness": (
        "Without looking at the game state, estimate your current resource levels. "
        "Format: food=X, materials=Y, knowledge=Z, gold=W"
    ),
    "strategy_consistency": (
        "In one sentence, what is your current strategy and primary goal for this game?"
    ),
    "history_recall": (
        "List the major events that have happened so far in this game "
        "(catastrophes, significant trades, major milestones). Be specific about turns."
    ),
}


class StateProbeCollector(MetricCollector):
    """Computes metrics 4.1–4.4 from pre-recorded probe results.

    Probes are injected by the orchestrator at configured turns and stored
    in the GameRecording. This collector evaluates stored probe responses
    against ground truth.
    """

    def __init__(self, probe_turns: list[int] | None = None):
        self._probe_turns = probe_turns or [10, 25, 50, 75, 100]

    def compute(self, recording: GameRecording) -> list[MetricResult]:
        # Get probe results from recording (stored as extra field)
        probes = getattr(recording, "probes", [])
        if not probes:
            # No probes were run — return neutral scores
            return [
                MetricResult(metric_id="4.1_building_recall", value=0.5, raw_value=0.0, sample_count=0),
                MetricResult(metric_id="4.2_resource_awareness", value=0.5, raw_value=0.0, sample_count=0),
                MetricResult(metric_id="4.3_strategy_consistency", value=0.5, raw_value=0.0, sample_count=0),
                MetricResult(metric_id="4.4_history_recall", value=0.5, raw_value=0.0, sample_count=0),
            ]

        return [
            self._building_recall(probes),
            self._resource_awareness(probes),
            self._strategy_consistency(probes),
            self._history_recall(probes),
        ]

    # ─── 4.1 Building Inventory Recall ───────────────────────────────────

    def _building_recall(self, probes: list[ProbeResult]) -> MetricResult:
        """Score accuracy of building list recall."""
        relevant = [p for p in probes if p.probe_type == "building_recall"]
        if not relevant:
            return MetricResult(metric_id="4.1_building_recall", value=0.5, raw_value=0.0, sample_count=0)

        scores = [p.score for p in relevant]
        avg = sum(scores) / len(scores)

        return MetricResult(
            metric_id="4.1_building_recall",
            value=clamp(avg),
            raw_value=avg,
            sample_count=len(relevant),
            details={"per_turn_scores": {p.turn: p.score for p in relevant}},
        )

    # ─── 4.2 Resource Awareness Accuracy ─────────────────────────────────

    def _resource_awareness(self, probes: list[ProbeResult]) -> MetricResult:
        """Score accuracy of resource level estimates."""
        relevant = [p for p in probes if p.probe_type == "resource_awareness"]
        if not relevant:
            return MetricResult(metric_id="4.2_resource_awareness", value=0.5, raw_value=0.0, sample_count=0)

        scores = [p.score for p in relevant]
        avg = sum(scores) / len(scores)

        return MetricResult(
            metric_id="4.2_resource_awareness",
            value=clamp(avg),
            raw_value=avg,
            sample_count=len(relevant),
            details={"per_turn_scores": {p.turn: p.score for p in relevant}},
        )

    # ─── 4.3 Strategy Consistency Check ──────────────────────────────────

    def _strategy_consistency(self, probes: list[ProbeResult]) -> MetricResult:
        """Score consistency between stated strategy and actions."""
        relevant = [p for p in probes if p.probe_type == "strategy_consistency"]
        if not relevant:
            return MetricResult(metric_id="4.3_strategy_consistency", value=0.5, raw_value=0.0, sample_count=0)

        scores = [p.score for p in relevant]
        avg = sum(scores) / len(scores)

        return MetricResult(
            metric_id="4.3_strategy_consistency",
            value=clamp(avg),
            raw_value=avg,
            sample_count=len(relevant),
            details={"per_turn_scores": {p.turn: p.score for p in relevant}},
        )

    # ─── 4.4 History Event Recall ────────────────────────────────────────

    def _history_recall(self, probes: list[ProbeResult]) -> MetricResult:
        """Score accuracy of historical event recall."""
        relevant = [p for p in probes if p.probe_type == "history_recall"]
        if not relevant:
            return MetricResult(metric_id="4.4_history_recall", value=0.5, raw_value=0.0, sample_count=0)

        scores = [p.score for p in relevant]
        avg = sum(scores) / len(scores)

        return MetricResult(
            metric_id="4.4_history_recall",
            value=clamp(avg),
            raw_value=avg,
            sample_count=len(relevant),
            details={"per_turn_scores": {p.turn: p.score for p in relevant}},
        )


# ─── Probe Evaluation Helpers ─────────────────────────────────────────────────


def evaluate_building_recall(response: str, state: BenchmarkGameState) -> ProbeResult:
    """Evaluate LLM's building recall against ground truth state."""
    ground_truth = {
        b.type: {"level": b.level, "health_pct": int(b.health / b.max_health * 100) if b.max_health > 0 else 100}
        for b in state.buildings
    }

    # Parse response — look for building type mentions
    response_lower = response.lower()
    recalled: set[str] = set()
    for btype in ground_truth:
        if btype.lower() in response_lower:
            recalled.add(btype)

    # F1 score
    actual_set = set(ground_truth.keys())
    if not actual_set:
        score = 1.0 if not recalled else 0.5
    else:
        tp = len(recalled & actual_set)
        fp = len(recalled - actual_set)
        fn = len(actual_set - recalled)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall_rate = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        score = 2 * precision * recall_rate / (precision + recall_rate) if (precision + recall_rate) > 0 else 0.0

    return ProbeResult(
        probe_type="building_recall",
        turn=state.turn,
        prompt=PROBE_PROMPTS["building_recall"],
        raw_response=response,
        ground_truth=ground_truth,
        score=score,
        details={"recalled": list(recalled), "actual": list(actual_set), "precision": precision if actual_set else 1.0, "recall": recall_rate if actual_set else 1.0},
    )


def evaluate_resource_awareness(response: str, state: BenchmarkGameState) -> ProbeResult:
    """Evaluate LLM's resource estimates against actual values."""
    ground_truth = {
        "food": state.resources.food,
        "materials": state.resources.materials,
        "knowledge": state.resources.knowledge,
        "gold": state.resources.gold,
    }

    # Parse response for numbers
    import re
    errors: dict[str, float] = {}
    total_error = 0.0
    parsed_count = 0

    for resource, actual in ground_truth.items():
        # Look for patterns like "food=123" or "food: 123" or "food ~123"
        pattern = rf"{resource}\s*[=:~≈]\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, response.lower())
        if match:
            estimated = float(match.group(1))
            if actual > 0:
                error = abs(estimated - actual) / actual
            else:
                error = 0.0 if estimated == 0 else 1.0
            errors[resource] = error
            total_error += error
            parsed_count += 1

    if parsed_count == 0:
        score = 0.0
    else:
        avg_error = total_error / parsed_count
        # ±15% tolerance: error <= 0.15 → full score
        score = clamp(1.0 - max(0, avg_error - 0.15) / 0.85)

    return ProbeResult(
        probe_type="resource_awareness",
        turn=state.turn,
        prompt=PROBE_PROMPTS["resource_awareness"],
        raw_response=response,
        ground_truth=ground_truth,
        score=score,
        details={"errors": errors, "parsed_count": parsed_count},
    )


def evaluate_history_recall(
    response: str,
    state: BenchmarkGameState,
    actual_events: list[dict[str, Any]],
) -> ProbeResult:
    """Evaluate LLM's recall of game events."""
    ground_truth = {"events": actual_events}
    response_lower = response.lower()

    correct = 0
    for event in actual_events:
        event_name = event.get("name", "").lower()
        if event_name and event_name in response_lower:
            correct += 1

    total = len(actual_events)
    if total == 0:
        score = 1.0
    else:
        score = correct / total

    return ProbeResult(
        probe_type="history_recall",
        turn=state.turn,
        prompt=PROBE_PROMPTS["history_recall"],
        raw_response=response,
        ground_truth=ground_truth,
        score=clamp(score),
        details={"correct": correct, "total_events": total},
    )
