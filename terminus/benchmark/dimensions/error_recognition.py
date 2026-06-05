"""Dimension 4: Compounding Error Recognition.

Measures the model's ability to detect negative resource trajectories
and correct them BEFORE the crisis point.
"""

from __future__ import annotations

from dataclasses import dataclass

from terminus.benchmark.dimensions.base import DimensionComputer, DimensionScore
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.metrics.utils import linear_regression_slope
from terminus.benchmark.schemas import GameRecording


@dataclass
class NegativeTrajectory:
    """A detected negative resource trajectory."""

    resource: str
    start_turn: int
    crisis_turn: int | None  # when resource hit 0
    correction_turn: int | None  # when LLM acted to correct
    corrected: bool

    @property
    def correction_lead_time(self) -> int:
        """Turns between correction and projected/actual crisis."""
        if self.correction_turn is None:
            return 0
        target = self.crisis_turn if self.crisis_turn else self.start_turn + 20
        return max(0, target - self.correction_turn)


class ErrorRecognitionComputer(DimensionComputer):
    """Computes Dimension 4: Compounding Error Recognition."""

    dimension_id = "dim_4_error_recognition"
    dimension_name = "Compounding Error Recognition"
    required_metrics = [
        "3.5_starvation_response_speed",
        "3.1_post_catastrophe_recovery",
        "1.6_resource_stockpile_timing",
    ]

    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        # 1. Trajectory analysis from recordings
        trajectories = self._detect_negative_trajectories(recordings)

        # Lead time scoring
        lead_times = [t.correction_lead_time for t in trajectories if t.corrected]
        avg_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0
        lead_time_score = self._score_lead_time(avg_lead_time)

        # Crisis avoidance rate
        if trajectories:
            avoidance_rate = sum(1 for t in trajectories if t.corrected) / len(trajectories)
        else:
            avoidance_rate = 0.5

        # Component metrics
        starvation_speed = self._get_metric_value(metrics, "3.5_starvation_response_speed")
        recovery_speed = self._get_metric_value(metrics, "3.1_post_catastrophe_recovery")
        stockpile = self._get_metric_value(metrics, "1.6_resource_stockpile_timing")

        score = (
            lead_time_score * 0.35
            + avoidance_rate * 0.25
            + starvation_speed * 0.15
            + recovery_speed * 0.15
            + stockpile * 0.10
        )
        score = max(0.0, min(1.0, score))

        return DimensionScore(
            dimension_id=self.dimension_id,
            dimension_name=self.dimension_name,
            score=score,
            sub_scores={
                "lead_time_score": lead_time_score,
                "avoidance_rate": avoidance_rate,
                "starvation_speed": starvation_speed,
                "recovery_speed": recovery_speed,
                "stockpile_timing": stockpile,
            },
            details={
                "avg_lead_time_turns": avg_lead_time,
                "trajectory_count": len(trajectories),
                "corrected_count": sum(1 for t in trajectories if t.corrected),
            },
            confidence=self._compute_confidence(metrics),
            contributing_metrics=list(self.required_metrics),
        )

    def _detect_negative_trajectories(
        self, recordings: list[GameRecording]
    ) -> list[NegativeTrajectory]:
        """Detect turns where resource trajectories go negative toward crisis."""
        trajectories: list[NegativeTrajectory] = []
        window = 10

        for rec in recordings:
            for resource in ("food", "materials", "knowledge", "gold"):
                values = [
                    getattr(snap.state.resources, resource, 0.0)
                    for snap in rec.turns
                ]
                if len(values) < window:
                    continue

                i = window
                while i < len(values):
                    segment = values[i - window: i]
                    slope = linear_regression_slope(
                        list(range(window)), segment
                    )

                    # Negative slope AND projected to hit 0 within 20 turns
                    current_val = values[i - 1]
                    if slope < -0.1 and current_val > 0:
                        turns_to_zero = current_val / abs(slope)
                        if turns_to_zero <= 20:
                            start_turn = i - 1
                            # Find crisis point (resource hits 0)
                            crisis_turn = None
                            for j in range(i, len(values)):
                                if values[j] <= 0:
                                    crisis_turn = j
                                    break

                            # Find correction (slope reversal)
                            correction_turn = None
                            for j in range(i, min(i + 20, len(values) - window)):
                                future_seg = values[j: j + min(window, len(values) - j)]
                                if len(future_seg) >= 3:
                                    future_slope = linear_regression_slope(
                                        list(range(len(future_seg))), future_seg
                                    )
                                    if future_slope > 0:
                                        correction_turn = j
                                        break

                            corrected = correction_turn is not None and (
                                crisis_turn is None or correction_turn < crisis_turn
                            )

                            trajectories.append(NegativeTrajectory(
                                resource=resource,
                                start_turn=start_turn,
                                crisis_turn=crisis_turn,
                                correction_turn=correction_turn,
                                corrected=corrected,
                            ))
                            # Skip ahead to avoid duplicate detection
                            i += window
                            continue
                    i += 1

        return trajectories

    def _score_lead_time(self, avg_lead_time: float) -> float:
        """Score based on average detection lead time."""
        if avg_lead_time > 15:
            return 1.0
        if avg_lead_time > 10:
            return 0.7
        if avg_lead_time > 5:
            return 0.4
        if avg_lead_time > 1:
            return 0.2
        return 0.0
