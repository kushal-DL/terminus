"""Shared utility functions for metrics computation."""

from __future__ import annotations

import math
from typing import Any

from terminus.benchmark.schemas import (
    BenchmarkActionType,
    GameRecording,
    TurnSnapshot,
)


def rolling_average(values: list[float], window: int) -> list[float]:
    """Compute rolling average with given window size.

    Returns list of same length; first (window-1) entries use available data.
    """
    if not values:
        return []
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def kendall_tau(actual: list[Any], expected: list[Any]) -> float:
    """Compute Kendall tau rank correlation between two orderings.

    Both lists must contain the same elements.
    Returns value in [-1.0, 1.0]. +1 = same order, -1 = reversed.
    """
    if len(actual) <= 1:
        return 1.0

    # Build rank mapping from expected order
    rank_map = {item: i for i, item in enumerate(expected)}

    # Map actual to ranks
    try:
        actual_ranks = [rank_map[item] for item in actual]
    except KeyError:
        # Items don't match — return 0.0 (no correlation)
        return 0.0

    n = len(actual_ranks)
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if actual_ranks[i] < actual_ranks[j]:
                concordant += 1
            elif actual_ranks[i] > actual_ranks[j]:
                discordant += 1

    total_pairs = n * (n - 1) / 2
    if total_pairs == 0:
        return 1.0
    return (concordant - discordant) / total_pairs


def jensen_shannon_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Compute Jensen-Shannon divergence between two distributions.

    Distributions are dicts mapping category → probability (should sum to ~1).
    Returns value in [0.0, 1.0].
    """
    # Get all keys
    all_keys = set(p.keys()) | set(q.keys())
    if not all_keys:
        return 0.0

    # Normalize distributions
    p_sum = sum(p.values()) or 1.0
    q_sum = sum(q.values()) or 1.0
    p_norm = {k: p.get(k, 0) / p_sum for k in all_keys}
    q_norm = {k: q.get(k, 0) / q_sum for k in all_keys}

    # Compute midpoint
    m = {k: (p_norm[k] + q_norm[k]) / 2 for k in all_keys}

    # KL divergences
    kl_pm = _kl_divergence(p_norm, m)
    kl_qm = _kl_divergence(q_norm, m)

    return (kl_pm + kl_qm) / 2


def _kl_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """KL(P || Q) with smoothing to avoid log(0)."""
    eps = 1e-10
    total = 0.0
    for k in p:
        pk = max(p[k], eps)
        qk = max(q[k], eps)
        total += pk * math.log2(pk / qk)
    return max(0.0, total)


def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """Linearly normalize value from [min_val, max_val] to [0.0, 1.0]."""
    if max_val <= min_val:
        return 0.5
    clamped = max(min_val, min(max_val, value))
    return (clamped - min_val) / (max_val - min_val)


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp value to [lo, hi]."""
    return max(lo, min(hi, value))


def detect_change_point(series: list[float], threshold: float) -> int | None:
    """Find first index where rolling average drops below threshold × overall mean.

    Returns None if no drop detected.
    """
    if len(series) < 5:
        return None

    overall_mean = sum(series) / len(series)
    if overall_mean == 0:
        return None

    target = threshold * overall_mean
    window = 5
    rolling = rolling_average(series, window)

    for i in range(window, len(rolling)):
        if rolling[i] < target:
            return i
    return None


def linear_regression_slope(x: list[float], y: list[float]) -> float:
    """Compute slope of simple linear regression.

    Returns 0.0 if insufficient data.
    """
    n = len(x)
    if n < 2 or len(y) < 2:
        return 0.0

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    denominator = sum((xi - x_mean) ** 2 for xi in x)

    if abs(denominator) < 1e-10:
        return 0.0
    return numerator / denominator


def action_distribution(turns: list[TurnSnapshot]) -> dict[str, float]:
    """Compute normalized action type distribution from turn snapshots.

    Returns dict mapping action_type → proportion [0, 1].
    """
    counts: dict[str, int] = {}
    total = 0
    for t in turns:
        if t.parsed_response:
            action = t.parsed_response.action.value
        else:
            action = "PASS"
        counts[action] = counts.get(action, 0) + 1
        total += 1

    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def find_catastrophe_turns(recording: GameRecording) -> list[int]:
    """Find turns where a new catastrophe result first appears."""
    catastrophe_turns = []
    prev_cat = None
    for snap in recording.turns:
        current_cat = snap.state.last_catastrophe
        if current_cat and (prev_cat is None or current_cat.name != prev_cat.name):
            catastrophe_turns.append(snap.turn)
        prev_cat = current_cat
    return catastrophe_turns


def find_starvation_turns(recording: GameRecording) -> list[int]:
    """Find turns where food == 0."""
    return [
        snap.turn
        for snap in recording.turns
        if snap.state.resources.food <= 0
    ]


def resource_at_turn(recording: GameRecording, turn: int, resource: str) -> float:
    """Get a resource value at a specific turn."""
    for snap in recording.turns:
        if snap.turn == turn:
            return getattr(snap.state.resources, resource, 0.0)
    return 0.0


def get_action_at_turn(recording: GameRecording, turn: int) -> str:
    """Get the action type string at a given turn."""
    for snap in recording.turns:
        if snap.turn == turn:
            if snap.parsed_response:
                return snap.parsed_response.action.value
            return "PASS"
    return "PASS"


def get_params_at_turn(recording: GameRecording, turn: int) -> dict:
    """Get action params at a given turn."""
    for snap in recording.turns:
        if snap.turn == turn:
            if snap.parsed_response:
                return snap.parsed_response.params
            return {}
    return {}


def production_total_at_turn(recording: GameRecording, turn: int) -> float:
    """Get total production rate at a turn."""
    for snap in recording.turns:
        if snap.turn == turn:
            p = snap.state.production
            return p.food + p.materials + p.knowledge + p.gold
    return 0.0
