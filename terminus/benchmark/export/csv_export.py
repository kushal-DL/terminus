"""CSV export — tabular output for spreadsheet analysis."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminus.benchmark.results import BenchmarkResult

_DIM_IDS = [
    "dim_1_coherence",
    "dim_2_arithmetic",
    "dim_3_triage",
    "dim_4_error_recognition",
    "dim_5_pivot",
    "dim_6_degradation",
    "dim_7_opportunity",
    "dim_8_game_theory",
]

_DIM_HEADERS = [
    "d1_coherence", "d2_arithmetic", "d3_triage", "d4_error_recog",
    "d5_pivot", "d6_degradation", "d7_opportunity", "d8_game_theory",
]


def export_csv(
    result: "BenchmarkResult",
    output_path: Path,
    *,
    mode: str = "summary",
) -> Path:
    """Write a CSV export of the benchmark result.

    Args:
        result: Full benchmark result.
        output_path: Destination path.
        mode: "summary" (1 row per model) or "detailed" (1 row per game).

    Returns:
        Absolute path to the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "detailed":
        _write_detailed(result, output_path)
    else:
        _write_summary(result, output_path)

    return output_path.resolve()


def _write_summary(result: "BenchmarkResult", path: Path) -> None:
    headers = [
        "rank", "model", "composite", "archetype", "trend",
        "avg_score", "max_score", "min_score", "score_std",
        "games_played", "valid_rate", "dq_count", "total_tokens",
        "avg_duration_s",
    ] + _DIM_HEADERS

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for r in result.rankings:
            name = r["name"]
            mr = result.models.get(name)
            if not mr:
                continue
            dr = mr.dimension_report
            row = {
                "rank": r["rank"],
                "model": name,
                "composite": round(dr.composite_score, 4),
                "archetype": dr.archetype.value if dr.archetype else "pragmatist",
                "trend": dr.trend.value if dr.trend else "consistent",
                "avg_score": round(mr.avg_score, 1),
                "max_score": mr.max_score,
                "min_score": mr.min_score,
                "score_std": round(mr.score_std, 2),
                "games_played": mr.games_played,
                "valid_rate": round(mr.valid_rate, 4),
                "dq_count": mr.dq_count,
                "total_tokens": mr.total_tokens,
                "avg_duration_s": round(mr.avg_duration_seconds, 1),
            }
            for dim_id, header in zip(_DIM_IDS, _DIM_HEADERS):
                ds = dr.dimensions.get(dim_id)
                row[header] = round(ds.score, 4) if ds else ""
            writer.writerow(row)


def _write_detailed(result: "BenchmarkResult", path: Path) -> None:
    headers = [
        "model", "game_idx", "score", "valid_rate",
    ] + _DIM_HEADERS + ["composite", "dq"]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for model_name, mr in result.models.items():
            for game_idx, (score, per_game_dims) in enumerate(
                zip(mr.scores, mr.per_game_dimensions or [{}] * len(mr.scores))
            ):
                row: dict = {
                    "model": model_name,
                    "game_idx": game_idx + 1,
                    "score": score,
                    "valid_rate": "",
                    "composite": "",
                    "dq": "N",
                }
                for dim_id, header in zip(_DIM_IDS, _DIM_HEADERS):
                    row[header] = round(per_game_dims.get(dim_id, 0.0), 4)
                writer.writerow(row)
