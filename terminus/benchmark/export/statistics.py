"""Statistical analysis — confidence intervals and pairwise comparisons."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminus.benchmark.results import BenchmarkResult

try:
    from scipy import stats as _scipy_stats  # type: ignore[import-untyped]
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class DimensionCI:
    """Bootstrap 95% confidence interval for one dimension score."""

    dimension_id: str
    mean: float
    ci_lower: float
    ci_upper: float
    n_games: int


@dataclass
class PairwiseComparison:
    """Statistical comparison between two models on composite score."""

    model_a: str
    model_b: str
    mean_diff: float        # model_a composite − model_b composite
    p_value: float | None   # None if scipy unavailable
    significant: bool       # p < 0.05 when available; abs(mean_diff) > 0.05 otherwise


@dataclass
class StatisticalReport:
    """Complete statistical analysis for a benchmark run."""

    confidence_intervals: dict[str, list[DimensionCI]]  # model → per-dim CIs
    pairwise_comparisons: list[PairwiseComparison]
    has_scipy: bool = HAS_SCIPY
    notes: list[str] = field(default_factory=list)


def compute_statistics(result: "BenchmarkResult") -> StatisticalReport:
    """Compute CIs and pairwise comparisons for a BenchmarkResult."""
    cis: dict[str, list[DimensionCI]] = {}
    comparisons: list[PairwiseComparison] = []
    notes: list[str] = []

    if not HAS_SCIPY:
        notes.append(
            "scipy not installed — using bootstrap CIs; p-values unavailable. "
            "Install scipy for significance tests: pip install scipy"
        )

    # ── Per-model confidence intervals ────────────────────────────────────────
    for model_name, mr in result.models.items():
        model_cis: list[DimensionCI] = []
        per_game = mr.per_game_dimensions  # list[dict[dim_id → score]]

        for dim_id, ds in mr.dimension_report.dimensions.items():
            game_scores = [g.get(dim_id, ds.score) for g in per_game]
            if not game_scores:
                game_scores = [ds.score]

            mean = sum(game_scores) / len(game_scores)
            lower, upper = _bootstrap_ci(game_scores)

            model_cis.append(DimensionCI(
                dimension_id=dim_id,
                mean=mean,
                ci_lower=lower,
                ci_upper=upper,
                n_games=len(game_scores),
            ))

        cis[model_name] = model_cis

    # ── Pairwise comparisons ──────────────────────────────────────────────────
    model_names = list(result.models.keys())
    for i in range(len(model_names)):
        for j in range(i + 1, len(model_names)):
            a_name = model_names[i]
            b_name = model_names[j]
            mr_a = result.models[a_name]
            mr_b = result.models[b_name]

            composite_a = mr_a.dimension_report.composite_score
            composite_b = mr_b.dimension_report.composite_score
            mean_diff = composite_a - composite_b

            p_value: float | None = None
            significant = abs(mean_diff) > 0.05  # heuristic fallback

            if HAS_SCIPY and len(mr_a.scores) > 1 and len(mr_b.scores) > 1:
                try:
                    stat, p = _scipy_stats.mannwhitneyu(
                        mr_a.scores, mr_b.scores, alternative="two-sided"
                    )
                    p_value = float(p)
                    significant = p_value < 0.05
                except Exception:
                    pass

            comparisons.append(PairwiseComparison(
                model_a=a_name,
                model_b=b_name,
                mean_diff=mean_diff,
                p_value=p_value,
                significant=significant,
            ))

    return StatisticalReport(
        confidence_intervals=cis,
        pairwise_comparisons=comparisons,
        has_scipy=HAS_SCIPY,
        notes=notes,
    )


def format_statistics_md(stats: StatisticalReport) -> str:
    """Render a StatisticalReport as a markdown section."""
    lines: list[str] = ["## Statistical Analysis", ""]

    if stats.notes:
        for note in stats.notes:
            lines.append(f"> ⚠️ {note}")
        lines.append("")

    # CI table per model
    for model_name, cis in stats.confidence_intervals.items():
        lines.append(f"### {model_name} — 95% Confidence Intervals")
        lines.append("")
        lines.append("| Dimension | Mean | 95% CI | N |")
        lines.append("|-----------|------|--------|---|")
        for ci in sorted(cis, key=lambda x: x.dimension_id):
            lines.append(
                f"| {ci.dimension_id} | {ci.mean:.3f} "
                f"| [{ci.ci_lower:.3f}, {ci.ci_upper:.3f}] | {ci.n_games} |"
            )
        lines.append("")

    # Pairwise comparisons
    if stats.pairwise_comparisons:
        lines.append("### Pairwise Comparisons (composite score)")
        lines.append("")
        lines.append("| Model A | Model B | Diff | p-value | Significant |")
        lines.append("|---------|---------|------|---------|-------------|")
        for pc in stats.pairwise_comparisons:
            p_str = f"{pc.p_value:.4f}" if pc.p_value is not None else "N/A"
            sig = "Yes ✓" if pc.significant else "No"
            lines.append(
                f"| {pc.model_a} | {pc.model_b} | {pc.mean_diff:+.3f} | {p_str} | {sig} |"
            )
        lines.append("")

    return "\n".join(lines)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _bootstrap_ci(
    values: list[float],
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute a bootstrap confidence interval. Pure Python, no scipy required."""
    if len(values) <= 1:
        v = values[0] if values else 0.0
        return v, v

    rng = random.Random(42)  # deterministic
    boot_means: list[float] = []
    n = len(values)

    for _ in range(n_bootstrap):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)

    boot_means.sort()
    alpha = (1.0 - confidence) / 2
    lo_idx = int(alpha * n_bootstrap)
    hi_idx = int((1 - alpha) * n_bootstrap)
    return boot_means[lo_idx], boot_means[min(hi_idx, n_bootstrap - 1)]
