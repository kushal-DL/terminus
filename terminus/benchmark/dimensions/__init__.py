"""Tier-2 Dimension Scorers — compute cognitive dimension scores from Tier-1 metrics."""

from __future__ import annotations

from terminus.benchmark.dimensions.base import (
    ArchetypeLabel,
    DimensionComputer,
    DimensionReport,
    DimensionScore,
    FailureMode,
    TrendClassification,
)
from terminus.benchmark.dimensions.archetypes import classify_archetype
from terminus.benchmark.dimensions.arithmetic import ArithmeticComputer
from terminus.benchmark.dimensions.coherence import CoherenceComputer
from terminus.benchmark.dimensions.composite import PRESETS, compute_composite
from terminus.benchmark.dimensions.degradation import DegradationComputer
from terminus.benchmark.dimensions.error_recognition import ErrorRecognitionComputer
from terminus.benchmark.dimensions.game_theory import GameTheoryComputer
from terminus.benchmark.dimensions.opportunity import OpportunityComputer
from terminus.benchmark.dimensions.pivot import PivotComputer
from terminus.benchmark.dimensions.triage import TriageComputer
from terminus.benchmark.dimensions.trend import classify_trend, classify_overall_trend
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import BenchmarkConfig, GameRecording


class DimensionScorer:
    """Tier-2 scoring facade: Tier-1 metrics -> cognitive dimension scores."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self._config = config
        self._computers: list[DimensionComputer] = [
            CoherenceComputer(),
            ArithmeticComputer(),
            TriageComputer(),
            ErrorRecognitionComputer(),
            PivotComputer(),
            DegradationComputer(),
            OpportunityComputer(),
            GameTheoryComputer(),
        ]

    def score(
        self,
        metrics: dict[str, MetricResult],
        recordings: list[GameRecording],
        model_name: str = "",
    ) -> DimensionReport:
        """Compute all 8 dimension scores + composite + trend + archetype."""
        # 1. Compute each dimension
        dimensions: dict[str, DimensionScore] = {}
        for computer in self._computers:
            dim_score = computer.compute(metrics, recordings)
            dimensions[dim_score.dimension_id] = dim_score

        # 2. Compute composite
        preset = self._config.weight_preset.value if self._config else "balanced"
        custom_w = self._config.custom_weights if self._config else None
        composite = compute_composite(dimensions, preset, custom_w)

        # 3. Compute per-game dimension scores for trend analysis
        per_game_dims = self._compute_per_game_dimensions(recordings)
        overall_trend = classify_overall_trend(per_game_dims)

        # 4. Classify archetype
        archetype = classify_archetype(dimensions)

        return DimensionReport(
            model_name=model_name,
            dimensions=dimensions,
            composite_score=composite,
            trend=overall_trend,
            archetype=archetype,
            weight_preset=preset,
            details={
                "per_game_dimensions": per_game_dims,
                "dimension_count": len(dimensions),
            },
        )

    def _compute_per_game_dimensions(
        self,
        recordings: list[GameRecording],
    ) -> list[dict[str, float]]:
        """Compute dimension scores per individual game for trend analysis."""
        from terminus.benchmark.metrics import MetricsEngine

        engine = MetricsEngine(self._config)
        per_game: list[dict[str, float]] = []
        for rec in recordings:
            game_metrics = engine.compute_game_metrics(rec)
            dims: dict[str, float] = {}
            for computer in self._computers:
                dim_score = computer.compute(game_metrics, [rec])
                dims[dim_score.dimension_id] = dim_score.score
            per_game.append(dims)
        return per_game
