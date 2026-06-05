"""Speed controller — manages time compression for benchmark games."""

from __future__ import annotations

from typing import Any


class SpeedController:
    """Manages time compression for benchmark games.

    Divides catastrophe scheduled_time values by the multiplier so games
    complete faster while maintaining relative spacing.
    """

    def __init__(self, multiplier: int = 5):
        if multiplier < 1:
            raise ValueError("Speed multiplier must be >= 1")
        self._multiplier = multiplier

    @property
    def multiplier(self) -> int:
        return self._multiplier

    def adjust_catastrophe_schedule(self, schedule: list[Any]) -> None:
        """Divide all scheduled_time values by multiplier (in-place).

        Args:
            schedule: List of CatastropheEvent objects with `scheduled_time` attribute.
        """
        for event in schedule:
            event.scheduled_time = event.scheduled_time / self._multiplier

    def get_effective_turn(self, actual_turn: int) -> int:
        """Map actual turn number to effective game-time turn.

        With higher multiplier, each actual turn represents more game-time.
        """
        return actual_turn * self._multiplier
