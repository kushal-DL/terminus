"""Benchmark Result aggregator — runs the MetricsEngine + DimensionScorer pipeline
on completed game recordings and produces a single structured result object.
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from terminus.benchmark.dimensions import DimensionScorer
from terminus.benchmark.dimensions.base import DimensionReport
from terminus.benchmark.metrics import MetricsEngine
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import BenchmarkConfig, GameRecording


# ─── Per-model result ─────────────────────────────────────────────────────────


@dataclass
class ModelResult:
    """Complete results for a single model across all its games."""

    model_name: str
    games_played: int

    # Game-level stats
    avg_score: float
    max_score: int
    min_score: int
    score_std: float
    total_valid_actions: int
    total_invalid_actions: int
    valid_rate: float
    dq_count: int
    avg_duration_seconds: float
    total_tokens: int

    # Scoring pipeline outputs
    metrics: dict[str, MetricResult]
    dimension_report: DimensionReport
    per_game_dimensions: list[dict[str, float]]

    # Convenience: per-game scores in order (for trend display)
    scores: list[float]


# ─── Top-level result ─────────────────────────────────────────────────────────


@dataclass
class BenchmarkResult:
    """Complete aggregated results for the entire benchmark run."""

    run_id: str
    timestamp: str
    elapsed_seconds: float
    total_games: int
    total_turns: int

    # Per-model
    models: dict[str, ModelResult]  # model_name → ModelResult

    # Sorted rankings (by composite_score desc)
    rankings: list[dict[str, Any]]

    # Legacy-compatible summary dict (for report.py and BenchmarkCompleted event)
    summary: dict[str, Any]

    # Config used (stored as plain dict for serialization)
    config_dict: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_recordings(
        cls,
        recordings: list[GameRecording],
        config: BenchmarkConfig,
        elapsed_seconds: float,
        config_dict: dict[str, Any] | None = None,
    ) -> "BenchmarkResult":
        """Run the full scoring pipeline and return a populated BenchmarkResult.

        This is the single entry point — call it once after all games complete.
        """
        if not recordings:
            return cls._empty(elapsed_seconds, config, config_dict or {})

        # Group recordings by model
        by_model: dict[str, list[GameRecording]] = {}
        for rec in recordings:
            by_model.setdefault(rec.model_name, []).append(rec)

        metrics_engine = MetricsEngine(config)
        scorer = DimensionScorer(config)

        # Compute reference score = best average score across all models (for participation)
        reference_score: float = max(
            (sum(r.final_score for r in recs) / len(recs))
            for recs in by_model.values()
        ) if by_model else None  # type: ignore[assignment]

        model_results: dict[str, ModelResult] = {}

        for model_name, recs in by_model.items():
            # Tier-1 metrics (averaged across all games for this model)
            metrics = metrics_engine.compute_all(recs)

            # Tier-2 dimension scores — pass reference_score for participation (Option B)
            dim_report = scorer.score(
                metrics, recs,
                model_name=model_name,
                reference_score=reference_score,
            )

            # Game-level stats
            scores = [r.final_score for r in recs]
            valid_counts = [len(r.turns) - r.invalid_action_count for r in recs]
            invalid_counts = [r.invalid_action_count for r in recs]
            total_valid = sum(valid_counts)
            total_invalid = sum(invalid_counts)
            total_actions = total_valid + total_invalid
            durations = [r.duration_seconds for r in recs]
            tokens = [r.total_tokens for r in recs]

            per_game_dims: list[dict[str, float]] = dim_report.details.get(
                "per_game_dimensions", []
            )

            model_results[model_name] = ModelResult(
                model_name=model_name,
                games_played=len(recs),
                avg_score=sum(scores) / len(scores) if scores else 0.0,
                max_score=int(max(scores)) if scores else 0,
                min_score=int(min(scores)) if scores else 0,
                score_std=statistics.stdev(scores) if len(scores) > 1 else 0.0,
                total_valid_actions=total_valid,
                total_invalid_actions=total_invalid,
                valid_rate=total_valid / total_actions if total_actions > 0 else 0.0,
                dq_count=sum(1 for r in recs if r.dq_reason),
                avg_duration_seconds=sum(durations) / len(durations) if durations else 0.0,
                total_tokens=sum(tokens),
                metrics=metrics,
                dimension_report=dim_report,
                per_game_dimensions=per_game_dims,
                scores=scores,
            )

        rankings = _build_rankings(model_results)
        summary = _build_summary(model_results, rankings, recordings, elapsed_seconds)
        total_turns = sum(len(r.turns) for r in recordings)

        return cls(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            elapsed_seconds=elapsed_seconds,
            total_games=len(recordings),
            total_turns=total_turns,
            models=model_results,
            rankings=rankings,
            summary=summary,
            config_dict=config_dict or {},
        )

    @classmethod
    def _empty(
        cls,
        elapsed_seconds: float,
        config: BenchmarkConfig,
        config_dict: dict[str, Any],
    ) -> "BenchmarkResult":
        return cls(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            elapsed_seconds=elapsed_seconds,
            total_games=0,
            total_turns=0,
            models={},
            rankings=[],
            summary={"rankings": [], "model_stats": {}, "total_games": 0, "elapsed_seconds": elapsed_seconds},
            config_dict=config_dict,
        )


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_rankings(model_results: dict[str, ModelResult]) -> list[dict[str, Any]]:
    """Sort models by composite dimension score, return ranking dicts."""
    rows = []
    for name, mr in model_results.items():
        dr = mr.dimension_report
        rows.append({
            "name": name,
            "composite_score": dr.composite_score,
            "archetype": dr.archetype.value if dr.archetype else "pragmatist",
            "trend": dr.trend.value if dr.trend else "consistent",
            # Game stats
            "score": mr.avg_score,
            "max_score": mr.max_score,
            "min_score": mr.min_score,
            "consistency": mr.score_std,
            "games_played": mr.games_played,
            "valid_rate": mr.valid_rate,
            "dq_count": mr.dq_count,
            "avg_duration_seconds": mr.avg_duration_seconds,
            "total_tokens": mr.total_tokens,
            # Dimension scores (flat, for easy display)
            "dimensions": {
                dim_id: ds.score
                for dim_id, ds in dr.dimensions.items()
            },
        })

    rows.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    return rows


def _build_summary(
    model_results: dict[str, ModelResult],
    rankings: list[dict[str, Any]],
    recordings: list[GameRecording],
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build the legacy-compatible summary dict consumed by report.py and the TUI."""
    # model_stats in the format report.py already understands
    model_stats: dict[str, Any] = {}
    for name, mr in model_results.items():
        model_stats[name] = {
            "games_played": mr.games_played,
            "scores": mr.scores,
            "avg_score": mr.avg_score,
            "max_score": mr.max_score,
            "min_score": mr.min_score,
            "total_valid": mr.total_valid_actions,
            "total_invalid": mr.total_invalid_actions,
            "total_tokens": mr.total_tokens,
            "total_duration": mr.avg_duration_seconds * mr.games_played,
            "dq_count": mr.dq_count,
        }

    # Dimension scores keyed by display name for report.py
    dimensions: dict[str, dict[str, float]] = {}
    _DIM_ID_TO_DISPLAY = {
        "dim_1_coherence": "Multi-Decision Coherence",
        "dim_2_arithmetic": "Applied Arithmetic Under Load",
        "dim_3_triage": "Priority Triage",
        "dim_4_error_recognition": "Compounding Error Recognition",
        "dim_5_pivot": "Justified Pivot",
        "dim_6_degradation": "Graceful Degradation",
        "dim_7_opportunity": "Opportunity Cost Awareness",
        "dim_8_game_theory": "Game-Theoretic Sophistication",
    }
    for name, mr in model_results.items():
        dim_scores: dict[str, float] = {}
        for dim_id, ds in mr.dimension_report.dimensions.items():
            display = _DIM_ID_TO_DISPLAY.get(dim_id, dim_id)
            dim_scores[display] = ds.score
        dimensions[name] = dim_scores

    # game_results list (for legacy score_dimensions fallback)
    game_results = []
    for rec in recordings:
        game_results.append({
            "model_name": rec.model_name,
            "score": rec.final_score,
            "turns_played": len(rec.turns),
            "valid_actions": len(rec.turns) - rec.invalid_action_count,
            "invalid_actions": rec.invalid_action_count,
        })

    # models_detail — per-model Tier-1 metrics for report drill-down
    models_detail: dict[str, Any] = {}
    for name, mr in model_results.items():
        models_detail[name] = {
            "metrics": {
                mid: {"value": m.value, "sample_count": m.sample_count}
                for mid, m in mr.metrics.items()
            },
        }

    return {
        "rankings": rankings,
        "model_stats": model_stats,
        "dimensions": dimensions,
        "models_detail": models_detail,
        "game_results": game_results,
        "total_games": len(recordings),
        "elapsed_seconds": elapsed_seconds,
    }


def write_report(
    result: BenchmarkResult,
    output_dir: str = "./benchmark-results",
) -> str:
    """Write the HTML report for a BenchmarkResult. Returns the report path."""
    from terminus.benchmark.report import generate_report

    dir_path = Path(output_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M")
    report_path = str(dir_path / f"{ts}_report.html")
    return generate_report(result.summary, result.config_dict, report_path)
