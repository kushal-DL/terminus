"""Balance report — formats simulation results and checks constraints."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.balance.simulator import BatchResults

from tools.balance.constraints import ALL_CONSTRAINTS


def print_report(results: "BatchResults", file=None) -> None:
    """Print a human-readable balance report to stdout."""
    out = file or sys.stdout
    w = out.write

    w("\n")
    w("=" * 70 + "\n")
    w("  TERMINUS BALANCE REPORT\n")
    w("=" * 70 + "\n")

    # ── Overview ─────────────────────────────────────────────────────────
    n_games = len(results.games)
    w(f"\n  Preset: {results.preset}  |  Games: {n_games}  |  Players: {results.total_players}\n")

    if results.game_durations:
        avg_dur = sum(results.game_durations) / len(results.game_durations)
        min_dur = min(results.game_durations)
        max_dur = max(results.game_durations)
        w(f"  Duration: avg {avg_dur / 60:.1f} min  |  min {min_dur / 60:.1f}  |  max {max_dur / 60:.1f}\n")

    if results.total_players > 0:
        surv_rate = results.survivors / results.total_players
        w(f"  Survival rate: {surv_rate:.1%} ({results.survivors}/{results.total_players})\n")

    # ── Score Distribution ───────────────────────────────────────────────
    w("\n" + "-" * 70 + "\n")
    w("  SCORE DISTRIBUTION\n")
    w("-" * 70 + "\n")

    scores = results.all_final_scores
    if scores:
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        std = variance ** 0.5
        scores_sorted = sorted(scores)
        p25 = scores_sorted[len(scores_sorted) // 4]
        p50 = scores_sorted[len(scores_sorted) // 2]
        p75 = scores_sorted[3 * len(scores_sorted) // 4]
        w(f"  Mean: {mean:.0f}  |  Std: {std:.0f}  |  CV: {std / mean:.3f}\n" if mean else "  No scores\n")
        w(f"  Min: {min(scores):.0f}  |  P25: {p25:.0f}  |  P50: {p50:.0f}  |  P75: {p75:.0f}  |  Max: {max(scores):.0f}\n")

    # ── Win Rates by Combo ───────────────────────────────────────────────
    w("\n" + "-" * 70 + "\n")
    w("  WIN RATES BY COMBO\n")
    w("-" * 70 + "\n")

    combo_wins = results.wins_by_combo()
    if combo_wins:
        w(f"  {'Combo':<40s} {'Win%':>6s}  {'Avg Score':>9s}\n")
        w(f"  {'─' * 40} {'─' * 6}  {'─' * 9}\n")
        for combo in sorted(combo_wins.keys()):
            rate = combo_wins[combo]
            avg_score = 0.0
            if combo in results.combo_scores and results.combo_scores[combo]:
                avg_score = sum(results.combo_scores[combo]) / len(results.combo_scores[combo])
            w(f"  {combo:<40s} {rate:5.1%}  {avg_score:9.0f}\n")

    # ── Starvation & Build Timing ────────────────────────────────────────
    w("\n" + "-" * 70 + "\n")
    w("  ECONOMY TIMING\n")
    w("-" * 70 + "\n")

    if results.first_starvation_ticks:
        avg_starve = sum(results.first_starvation_ticks) / len(results.first_starvation_ticks)
        earliest = min(results.first_starvation_ticks)
        w(f"  First starvation: avg tick {avg_starve:.0f}  |  earliest tick {earliest}\n")
        early = sum(1 for t in results.first_starvation_ticks if t < 60)
        w(f"  Starved before tick 60: {early}/{len(results.first_starvation_ticks)}\n")
    else:
        w("  No starvation events recorded\n")

    if results.first_build_ticks:
        avg_build = sum(results.first_build_ticks) / len(results.first_build_ticks)
        latest = max(results.first_build_ticks)
        w(f"  First build: avg tick {avg_build:.0f}  |  latest tick {latest}\n")
        late = sum(1 for t in results.first_build_ticks if t > 30)
        w(f"  Built after tick 30: {late}/{len(results.first_build_ticks)}\n")
    else:
        w("  No build events recorded\n")

    w(f"  Never built: {results.never_built_count}\n")

    # ── Constraint Checks ────────────────────────────────────────────────
    w("\n" + "-" * 70 + "\n")
    w("  CONSTRAINT CHECKS\n")
    w("-" * 70 + "\n")

    all_passed = True
    for constraint in ALL_CONSTRAINTS:
        passed, detail = constraint.check(results)
        status = "✓ PASS" if passed else "✗ FAIL"
        if not passed:
            all_passed = False
        w(f"  [{status}] {constraint.name}: {detail}\n")

    w("\n" + "=" * 70 + "\n")
    if all_passed:
        w("  OVERALL: ✓ ALL CONSTRAINTS PASSED\n")
    else:
        w("  OVERALL: ✗ SOME CONSTRAINTS FAILED\n")
    w("=" * 70 + "\n\n")


def generate_json_report(results: "BatchResults") -> dict:
    """Generate a JSON-serializable report for further analysis."""
    scores = results.all_final_scores
    mean = sum(scores) / len(scores) if scores else 0
    std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5 if scores else 0

    constraint_results = []
    for c in ALL_CONSTRAINTS:
        passed, detail = c.check(results)
        constraint_results.append({
            "name": c.name,
            "passed": passed,
            "detail": detail,
        })

    return {
        "preset": results.preset,
        "n_games": len(results.games),
        "total_players": results.total_players,
        "survivors": results.survivors,
        "survival_rate": results.survivors / max(results.total_players, 1),
        "score_mean": mean,
        "score_std": std,
        "score_cv": std / mean if mean else 0,
        "avg_duration_seconds": sum(results.game_durations) / len(results.game_durations) if results.game_durations else 0,
        "combo_win_rates": results.wins_by_combo(),
        "constraints": constraint_results,
        "all_passed": all(c["passed"] for c in constraint_results),
    }
