"""JSON export — full-fidelity structured output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from terminus.benchmark.results import BenchmarkResult


def export_json(
    result: "BenchmarkResult",
    output_path: Path,
    *,
    compact: bool = False,
) -> Path:
    """Write a JSON export of the benchmark result.

    Args:
        result: Full benchmark result.
        output_path: Destination path.
        compact: If True, omit per-turn state data from recordings (~10× smaller).

    Returns:
        Absolute path to the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "meta": {
            "run_id": result.run_id,
            "timestamp": result.timestamp,
            "elapsed_seconds": result.elapsed_seconds,
            "total_games": result.total_games,
            "total_turns": result.total_turns,
        },
        "config": result.config_dict,
        "rankings": result.rankings,
        "models": {},
    }

    for model_name, mr in result.models.items():
        dr = mr.dimension_report
        model_entry: dict[str, Any] = {
            "game_stats": {
                "games_played": mr.games_played,
                "avg_score": mr.avg_score,
                "max_score": mr.max_score,
                "min_score": mr.min_score,
                "score_std": mr.score_std,
                "valid_rate": mr.valid_rate,
                "dq_count": mr.dq_count,
                "avg_duration_seconds": mr.avg_duration_seconds,
                "total_tokens": mr.total_tokens,
            },
            "dimension_report": {
                "composite_score": dr.composite_score,
                "archetype": dr.archetype.value if dr.archetype else "pragmatist",
                "trend": dr.trend.value if dr.trend else "consistent",
                "weight_preset": dr.weight_preset,
                "dimensions": {
                    dim_id: {
                        "score": ds.score,
                        "dimension_name": ds.dimension_name,
                        "sub_scores": ds.sub_scores,
                        "confidence": ds.confidence,
                    }
                    for dim_id, ds in dr.dimensions.items()
                },
            },
            "metrics": {
                mid: {
                    "value": m.value,
                    "raw_value": m.raw_value,
                    "sample_count": m.sample_count,
                }
                for mid, m in mr.metrics.items()
            },
            "per_game_dimensions": mr.per_game_dimensions,
            "scores_per_game": mr.scores,
        }

        if not compact:
            # Include full turn-by-turn recording data
            recordings_data = []
            # We don't store recordings on ModelResult, but game_results in summary has basic data
            model_entry["scores_per_game"] = mr.scores

        data["models"][model_name] = model_entry

    indent = None if compact else 2
    output_path.write_text(
        json.dumps(data, indent=indent, ensure_ascii=False),
        encoding="utf-8",
    )
    return output_path.resolve()
