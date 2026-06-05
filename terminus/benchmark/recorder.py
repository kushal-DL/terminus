"""Turn recorder — records per-turn snapshots and builds GameRecording."""

from __future__ import annotations

import time

from terminus.benchmark.schemas import (
    ActionResponse,
    BenchmarkGameState,
    GameRecording,
    TurnSnapshot,
)


class TurnRecorder:
    """Records benchmark game data turn-by-turn and builds final GameRecording."""

    def __init__(self, model_name: str, opponent_type: str, seed: int):
        self._model_name = model_name
        self._opponent_type = opponent_type
        self._seed = seed
        self._turns: list[TurnSnapshot] = []
        self._start_time = time.time()

    def record_turn(
        self,
        turn: int,
        state: BenchmarkGameState,
        raw_response: str,
        parsed_response: ActionResponse | None,
        valid: bool,
        error_message: str | None,
        latency_ms: float,
        tokens_used: int,
        retry_count: int,
    ) -> None:
        """Record a single turn snapshot."""
        self._turns.append(TurnSnapshot(
            turn=turn,
            state=state,
            raw_response=raw_response,
            parsed_response=parsed_response,
            valid=valid,
            error_message=error_message,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            retry_count=retry_count,
        ))

    def finalize(
        self,
        final_score: int,
        duration_seconds: float | None = None,
        dq_reason: str | None = None,
    ) -> GameRecording:
        """Build the complete GameRecording from all turn snapshots.

        Args:
            final_score: Final game score for the LLM player.
            duration_seconds: Total game duration. If None, computed from start time.
            dq_reason: If set, the player was disqualified with this reason.
        """
        if duration_seconds is None:
            duration_seconds = time.time() - self._start_time

        return GameRecording(
            model_name=self._model_name,
            opponent_type=self._opponent_type,
            seed=self._seed,
            turns=self._turns,
            final_score=final_score,
            duration_seconds=duration_seconds,
            dq_reason=dq_reason,
        )

    @property
    def turns(self) -> list[TurnSnapshot]:
        return self._turns

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def valid_count(self) -> int:
        return sum(1 for t in self._turns if t.valid)

    @property
    def invalid_count(self) -> int:
        return sum(1 for t in self._turns if not t.valid)

    @property
    def total_latency_ms(self) -> float:
        return sum(t.latency_ms for t in self._turns)

    @property
    def avg_latency_ms(self) -> float:
        if not self._turns:
            return 0.0
        return self.total_latency_ms / len(self._turns)

    @property
    def total_tokens(self) -> int:
        return sum(t.tokens_used for t in self._turns)
