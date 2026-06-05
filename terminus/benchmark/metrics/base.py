"""Base types for the metrics engine — ABC and result dataclass."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from terminus.benchmark.schemas import GameRecording


@dataclass
class MetricResult:
    """Result of a single metric computation."""

    metric_id: str
    value: float  # normalized [0.0, 1.0]
    raw_value: float  # pre-normalization
    sample_count: int = 0  # data points used
    details: dict[str, Any] = field(default_factory=dict)


class MetricCollector(ABC):
    """Base class for single-game metric collectors."""

    @abstractmethod
    def compute(self, recording: GameRecording) -> list[MetricResult]:
        """Compute all metrics in this category from a single game recording."""
        ...


class CrossGameCollector(ABC):
    """Base class for metrics requiring multiple game recordings."""

    @abstractmethod
    def compute(self, recordings: list[GameRecording]) -> list[MetricResult]:
        """Compute metrics that require multiple game recordings."""
        ...
