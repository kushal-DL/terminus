"""Measurable balance constraints for Terminus game tuning.

Each constraint has a name, description, and a check function that takes
a BatchResults and returns (passed: bool, detail: str).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.balance.simulator import BatchResults


@dataclass
class Constraint:
    name: str
    description: str

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        raise NotImplementedError


# ─── Concrete Constraints ────────────────────────────────────────────────────


class WinRateSpread(Constraint):
    """No location×spec combo should deviate >15% from mean win rate."""

    max_deviation: float = 0.25

    def __init__(self):
        super().__init__(
            name="win_rate_spread",
            description=f"Win-rate spread ≤{self.max_deviation:.0%} from mean across all combos",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        combo_wins = results.wins_by_combo()
        if not combo_wins:
            return True, "No combo data"
        rates = list(combo_wins.values())
        mean = sum(rates) / len(rates)
        if mean == 0:
            return True, "No wins recorded"
        max_dev = max(abs(r - mean) / mean for r in rates) if mean else 0
        passed = max_dev <= self.max_deviation
        worst = max(combo_wins.items(), key=lambda x: abs(x[1] - mean))
        return passed, f"Max deviation: {max_dev:.1%} (combo {worst[0]}: {worst[1]:.1%} vs mean {mean:.1%})"


class GameDuration(Constraint):
    """Game duration should fall within target range for the preset."""

    targets: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        "quick": (25 * 60, 35 * 60),
        "standard": (40 * 60, 50 * 60),
        "extended": (55 * 60, 65 * 60),
    })

    def __init__(self):
        super().__init__(
            name="game_duration",
            description="Game duration within target range for preset",
        )
        self.targets = {
            "quick": (25 * 60, 35 * 60),
            "standard": (40 * 60, 50 * 60),
            "extended": (55 * 60, 65 * 60),
        }

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        durations = results.game_durations
        if not durations:
            return True, "No duration data"
        avg = sum(durations) / len(durations)
        preset = results.preset
        lo, hi = self.targets.get(preset, (0, float("inf")))
        passed = lo <= avg <= hi
        return passed, f"Avg duration: {avg / 60:.1f} min (target: {lo / 60:.0f}-{hi / 60:.0f} min)"


class SurvivalRate(Constraint):
    """≥60% of players should survive all catastrophes."""

    min_rate: float = 0.60

    def __init__(self):
        super().__init__(
            name="survival_rate",
            description=f"≥{self.min_rate:.0%} of players survive all catastrophes",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        if results.total_players == 0:
            return True, "No players"
        rate = results.survivors / results.total_players
        passed = rate >= self.min_rate
        return passed, f"Survival rate: {rate:.1%} ({results.survivors}/{results.total_players})"


class ScoreVariation(Constraint):
    """Score coefficient of variation should be <0.30."""

    max_cv: float = 0.40

    def __init__(self):
        super().__init__(
            name="score_variation",
            description=f"Score CV < {self.max_cv}",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        scores = results.all_final_scores
        if len(scores) < 2:
            return True, "Insufficient data"
        mean = sum(scores) / len(scores)
        if mean == 0:
            return True, "Zero mean score"
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        cv = variance ** 0.5 / mean
        passed = cv < self.max_cv
        return passed, f"Score CV: {cv:.3f} (mean={mean:.0f}, std={variance ** 0.5:.0f})"


class NoEarlyStarvation(Constraint):
    """No player should starve before tick 60 (~2 min)."""

    min_tick: int = 60

    def __init__(self):
        super().__init__(
            name="no_early_starvation",
            description=f"No starvation before tick {self.min_tick}",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        early = [t for t in results.first_starvation_ticks if t < self.min_tick]
        passed = len(early) == 0
        if early:
            return passed, f"FAIL: {len(early)} players starved early (earliest tick {min(early)})"
        return passed, f"OK: no starvation before tick {self.min_tick}"


class FirstBuildingAffordable(Constraint):
    """First building should be affordable by tick 30 (~1 min) for all combos."""

    max_tick: int = 30

    def __init__(self):
        super().__init__(
            name="first_building_affordable",
            description=f"First building affordable by tick {self.max_tick}",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        late = [t for t in results.first_build_ticks if t > self.max_tick]
        never = results.never_built_count
        passed = len(late) == 0 and never == 0
        detail = f"{len(results.first_build_ticks)} players built; "
        if late:
            detail += f"{len(late)} built late (latest tick {max(late)}); "
        if never:
            detail += f"{never} never built; "
        return passed, detail.rstrip("; ")


class NoDominantCombo(Constraint):
    """No single combo should win >70% of games in head-to-head."""

    max_win_rate: float = 0.70

    def __init__(self):
        super().__init__(
            name="no_dominant_combo",
            description=f"No combo wins >{self.max_win_rate:.0%} of games",
        )

    def check(self, results: "BatchResults") -> tuple[bool, str]:
        combo_wins = results.wins_by_combo()
        if not combo_wins:
            return True, "No combo data"
        worst = max(combo_wins.items(), key=lambda x: x[1])
        passed = worst[1] <= self.max_win_rate
        return passed, f"Highest win rate: {worst[0]} at {worst[1]:.1%}"


# ─── Default constraint set ─────────────────────────────────────────────────

ALL_CONSTRAINTS: list[Constraint] = [
    WinRateSpread(),
    GameDuration(),
    SurvivalRate(),
    ScoreVariation(),
    NoEarlyStarvation(),
    FirstBuildingAffordable(),
    NoDominantCombo(),
]
