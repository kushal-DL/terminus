"""CountdownTimer widget — large time display with urgency color states."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult


class CountdownTimer(Widget):
    """Displays MM:SS countdown with urgency color transitions."""

    DEFAULT_CSS = """
    CountdownTimer {
        height: 1;
        width: auto;
        min-width: 12;
        text-style: bold;
    }
    CountdownTimer.timer-normal {
        color: #00ff41;
    }
    CountdownTimer.timer-warning {
        color: #ffb000;
    }
    CountdownTimer.timer-critical {
        color: #ff0040;
    }
    CountdownTimer.timer-final {
        color: #ff0040;
        text-style: bold reverse;
    }
    """

    seconds_remaining: reactive[int] = reactive(0)
    running: reactive[bool] = reactive(False)

    def __init__(
        self,
        seconds: int = 0,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.seconds_remaining = seconds
        self._timer_handle = None

    def on_mount(self) -> None:
        self._timer_handle = self.set_interval(1, self._tick)
        self._update_urgency()

    def start(self, seconds: int) -> None:
        """Start or restart the countdown from given seconds."""
        self.seconds_remaining = seconds
        self.running = True

    def stop(self) -> None:
        """Stop the countdown."""
        self.running = False

    def _tick(self) -> None:
        if self.running and self.seconds_remaining > 0:
            self.seconds_remaining -= 1
            if self.seconds_remaining <= 0:
                self.running = False

    def watch_seconds_remaining(self) -> None:
        self._update_urgency()
        self.refresh()

    def _update_urgency(self) -> None:
        """Toggle CSS classes based on time remaining."""
        self.remove_class("timer-normal", "timer-warning", "timer-critical", "timer-final")
        s = self.seconds_remaining
        if s > 60:
            self.add_class("timer-normal")
        elif s > 30:
            self.add_class("timer-warning")
        elif s > 10:
            self.add_class("timer-critical")
        else:
            self.add_class("timer-final")

    def render(self) -> RenderResult:
        s = self.seconds_remaining
        if s <= 0 and not self.running:
            return " --:-- "
        mins, secs = divmod(max(s, 0), 60)
        return f" {mins:02d}:{secs:02d} "
