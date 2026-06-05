"""Benchmark event types — emitted by the orchestrator, consumed by the TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnCompleted:
    """Emitted after every turn (one tick processed for all players)."""

    game_index: int  # 0-based index in total game list
    turn: int  # 1-based turn within this game
    max_turns: int
    model_name: str  # Which model's turn just completed
    model_index: int  # Index in config["models"]
    action_type: str  # e.g. "BUILD", "ALLOCATE_WORKERS", "PASS"
    action_valid: bool
    rejection_reason: str | None = None
    # Snapshot of the model's colony state after this turn
    colony_state: dict[str, Any] = field(default_factory=dict)
    # Current score
    score: float = 0.0
    # Opponent score (for side-by-side comparison in live viewer)
    opponent_score: float = 0.0
    # Top reasoning factor from LLM response (e.g. "long_term_growth:0.60")
    reasoning_summary: str = ""
    # Short summary of any trade activity this turn (e.g. "offered 20 food for 10 gold")
    trade_summary: str = ""


@dataclass
class GameCompleted:
    """Emitted when a single game finishes (all turns played or game ended early)."""

    game_index: int
    model_name: str
    model_index: int
    opponent_strategy: str
    final_score: float
    turns_played: int
    valid_actions: int
    invalid_actions: int
    scores: list[dict[str, Any]] = field(default_factory=list)  # Full score breakdown


@dataclass
class BenchmarkCompleted:
    """Emitted when the entire benchmark run is done."""

    total_games: int
    total_turns: int
    elapsed_seconds: float
    results: dict[str, Any] = field(default_factory=dict)  # Full results payload
    report_path: str | None = None


@dataclass
class ErrorOccurred:
    """Emitted on non-fatal errors (LLM timeout, parse failure, etc.)."""

    game_index: int
    turn: int
    model_name: str
    error_type: str  # "timeout", "parse_error", "api_error", "engine_error"
    message: str
    recoverable: bool = True


@dataclass
class GameStarted:
    """Emitted when a new game begins."""

    game_index: int
    model_name: str
    model_index: int
    opponent_strategy: str
    seed: int


@dataclass
class CatastropheTriggered:
    """Emitted when a catastrophe fires during a game."""

    game_index: int
    turn: int
    model_name: str
    catastrophe_name: str
    catastrophe_id: str
    severity: int


# Union type for all events the TUI can receive
BenchmarkEvent = (
    TurnCompleted
    | GameCompleted
    | BenchmarkCompleted
    | ErrorOccurred
    | GameStarted
    | CatastropheTriggered
)
