"""Markdown export — GFM summary with archetype emoji."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminus.benchmark.results import BenchmarkResult

_ARCHETYPE_EMOJI = {
    "predator": "🦅",
    "fortress": "🏰",
    "diplomat": "🤝",
    "chameleon": "🦎",
    "scholar": "🎓",
    "pragmatist": "⚖️",
    "cautious": "🛡️",
    "oblivious": "😶",
}

_TREND_ARROW = {
    "improving": "↑",
    "consistent": "→",
    "degrading": "↓",
    "volatile": "↕",
}

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

_DIM_SHORT = [
    "Coherence", "Arithmetic", "Triage", "Err.Recog",
    "Pivot", "Degrade", "OpCost", "GameThry",
]


def export_markdown(
    result: "BenchmarkResult",
    output_path: Path,
) -> Path:
    """Write a GFM markdown summary of the benchmark result.

    Returns:
        Absolute path to the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []

    # Header
    elapsed = result.elapsed_seconds
    elapsed_str = f"{elapsed / 60:.1f} min" if elapsed < 3600 else f"{elapsed / 3600:.1f} hr"
    lines += [
        "# LLM Benchmark Results",
        "",
        f"**Run:** {result.timestamp} | **Duration:** {elapsed_str} | **Games:** {result.total_games}",
        "",
    ]

    # Rankings table
    lines += ["## Rankings", ""]
    lines.append("| # | Model | Composite | Archetype | Trend | Games | Valid% |")
    lines.append("|---|-------|-----------|-----------|-------|-------|--------|")
    for r in result.rankings:
        name = r.get("name", "?")
        composite = r.get("composite_score", 0.0)
        archetype_key = r.get("archetype", "pragmatist")
        archetype = _ARCHETYPE_EMOJI.get(archetype_key, "⚖️") + " " + archetype_key.title()
        trend_key = r.get("trend", "consistent")
        trend = _TREND_ARROW.get(trend_key, "→") + " " + trend_key.title()
        games = r.get("games_played", "—")
        valid_pct = f"{r.get('valid_rate', 0) * 100:.0f}%" if r.get("valid_rate") is not None else "—"
        lines.append(
            f"| {r.get('rank', '?')} | **{name}** | {composite:.3f} | {archetype} | {trend} | {games} | {valid_pct} |"
        )
    lines.append("")

    # Dimension scores table
    lines += ["## Dimension Scores", ""]
    dim_header = "| Dimension | " + " | ".join(
        f"**{r.get('name', '?')}**" for r in result.rankings
    ) + " |"
    lines.append(dim_header)
    lines.append("|-----------|" + "---|" * len(result.rankings))

    for dim_id, dim_short in zip(_DIM_IDS, _DIM_SHORT):
        cells = []
        for r in result.rankings:
            mr = result.models.get(r.get("name", ""))
            if mr:
                ds = mr.dimension_report.dimensions.get(dim_id)
                val = f"{ds.score:.3f}" if ds else "—"
            else:
                val = "—"
            cells.append(val)
        lines.append(f"| {dim_short} | " + " | ".join(cells) + " |")
    lines.append("")

    # Per-model breakdown
    lines += ["## Model Details", ""]
    for r in result.rankings:
        name = r.get("name", "?")
        mr = result.models.get(name)
        if not mr:
            continue
        dr = mr.dimension_report
        archetype_key = dr.archetype.value if dr.archetype else "pragmatist"
        lines += [
            f"### {name}",
            "",
            f"- **Composite score:** {dr.composite_score:.3f}",
            f"- **Archetype:** {_ARCHETYPE_EMOJI.get(archetype_key, '')} {archetype_key.title()}",
            f"- **Trend:** {_TREND_ARROW.get(dr.trend.value if dr.trend else 'consistent', '→')} {dr.trend.value.title() if dr.trend else 'Consistent'}",
            f"- **Avg game score:** {mr.avg_score:.0f} (range {mr.min_score}–{mr.max_score})",
            f"- **Valid action rate:** {mr.valid_rate * 100:.1f}%",
            f"- **Games played:** {mr.games_played}",
            f"- **DQ count:** {mr.dq_count}",
            "",
        ]

    # Config summary
    cfg = result.config_dict
    lines += [
        "## Configuration",
        "",
        f"- Weight preset: {cfg.get('weight_preset', 'balanced')}",
        f"- Games per matchup: {cfg.get('num_games', cfg.get('games_per_matchup', '?'))}",
        f"- Max turns: {cfg.get('max_turns', '?')}",
        f"- Speed multiplier: {cfg.get('speed_multiplier', '?')}×",
        "",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path.resolve()
