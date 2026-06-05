"""Base types and abstract classes for Tier-2 dimension scorers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import GameRecording


class FailureMode(str, Enum):
    STABLE = "stable"
    IMPROVING = "improving"
    LINEAR_DECAY = "linear_decay"
    CLIFF_FAILURE = "cliff_failure"
    OSCILLATING = "oscillating"


class TrendClassification(str, Enum):
    IMPROVING = "improving"
    CONSISTENT = "consistent"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


class ArchetypeLabel(str, Enum):
    PREDATOR = "predator"
    FORTRESS = "fortress"
    DIPLOMAT = "diplomat"
    CHAMELEON = "chameleon"
    SCHOLAR = "scholar"
    PRAGMATIST = "pragmatist"
    CAUTIOUS = "cautious"
    OBLIVIOUS = "oblivious"


@dataclass
class DimensionScore:
    """Score for a single cognitive dimension."""

    dimension_id: str
    dimension_name: str
    score: float
    sub_scores: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    contributing_metrics: list[str] = field(default_factory=list)


@dataclass
class DimensionReport:
    """Complete Tier-2 report for a model."""

    model_name: str
    dimensions: dict[str, DimensionScore]
    composite_score: float
    trend: TrendClassification
    archetype: ArchetypeLabel
    weight_preset: str
    details: dict[str, Any] = field(default_factory=dict)


class DimensionComputer(ABC):
    """Abstract base for computing a single dimension score."""

    dimension_id: str
    dimension_name: str
    required_metrics: list[str]

    @abstractmethod
    def compute(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
    ) -> DimensionScore:
        """Compute dimension score from Tier-1 metrics and raw recordings."""
        ...

    def _get_metric_value(self, metrics: dict[str, MetricResult], metric_id: str) -> float:
        """Safely extract metric value, defaulting to 0.5 if missing."""
        if metric_id in metrics:
            return metrics[metric_id].value
        return 0.5

    def _compute_confidence(self, metrics: dict[str, MetricResult]) -> float:
        """Confidence based on how many required metrics have sufficient samples."""
        if not self.required_metrics:
            return 1.0
        available = sum(
            1 for mid in self.required_metrics
            if mid in metrics and metrics[mid].sample_count > 0
        )
        return available / len(self.required_metrics)
