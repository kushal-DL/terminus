"""WorkerSlider widget — compact allocation control with ◄/► adjustment."""

from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult
from textual.events import Key
from textual.timer import Timer


class WorkerSlider(Widget):
    """Compact worker allocation: role_icon ROLE [◄ 12 ►]"""

    DEFAULT_CSS = """
    WorkerSlider {
        height: 1;
        width: 1fr;
        min-width: 30;
    }
    WorkerSlider:focus {
        text-style: bold;
        color: #00ff41;
    }
    """

    DEBOUNCE_MS = 300

    can_focus = True

    value: reactive[int] = reactive(0)
    max_value: reactive[int] = reactive(0)
    role: reactive[str] = reactive("")
    _input_mode: reactive[bool] = reactive(False)
    _input_buffer: str = ""

    ROLE_ICONS = {
        "farming": "🌾",
        "mining": "⛏ ",
        "research": "🔬",
        "construction": "🔨",
        "defense": "🛡 ",
        "medicine": "💊",
    }

    class Changed(Message):
        """Posted when the slider value changes."""

        def __init__(self, slider: WorkerSlider, role: str, value: int) -> None:
            super().__init__()
            self.slider = slider
            self.role = role
            self.value = value

    def __init__(
        self,
        role: str = "",
        value: int = 0,
        max_value: int = 0,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.role = role
        self.value = value
        self.max_value = max_value
        self._debounce_timer: Timer | None = None

    def render(self) -> RenderResult:
        icon = self.ROLE_ICONS.get(self.role, "  ")
        role_display = self.role.capitalize()
        if self._input_mode:
            buf = self._input_buffer or "_"
            return f"  {icon} {role_display:14s} [ {buf:>3s}  ]  /{self.max_value}"
        return f"  {icon} {role_display:14s} [◄ {self.value:3d} ►]  /{self.max_value}"

    def on_key(self, event: Key) -> None:
        if self._input_mode:
            if event.key == "enter":
                self._commit_input()
                event.stop()
            elif event.key == "escape":
                self._input_mode = False
                self._input_buffer = ""
                self.refresh()
                event.stop()
            elif event.key == "backspace":
                self._input_buffer = self._input_buffer[:-1]
                self.refresh()
                event.stop()
            elif event.key.isdigit() and len(self._input_buffer) < 4:
                self._input_buffer += event.key
                self.refresh()
                event.stop()
            return

        if event.key in ("left", "minus"):
            self._decrement()
            event.stop()
        elif event.key in ("right", "plus"):
            self._increment()
            event.stop()
        elif event.key == "enter":
            self._input_mode = True
            self._input_buffer = ""
            self.refresh()
            event.stop()

    def _commit_input(self) -> None:
        """Apply typed numeric value and exit input mode."""
        self._input_mode = False
        if self._input_buffer:
            new_val = int(self._input_buffer)
            new_val = max(0, min(new_val, self.max_value))
            self._input_buffer = ""
            if new_val != self.value:
                self.value = new_val
                self._emit_debounced()
        self.refresh()

    def _emit_debounced(self) -> None:
        """Schedule a Changed message after DEBOUNCE_MS idle."""
        if self._debounce_timer is not None:
            self._debounce_timer.stop()
        self._debounce_timer = self.set_timer(
            self.DEBOUNCE_MS / 1000,
            self._fire_changed,
        )

    def _fire_changed(self) -> None:
        self._debounce_timer = None
        self.post_message(self.Changed(self, self.role, self.value))

    def _increment(self) -> None:
        if self.value < self.max_value:
            self.value += 1
            self._emit_debounced()
            self.refresh()

    def _decrement(self) -> None:
        if self.value > 0:
            self.value -= 1
            self._emit_debounced()
            self.refresh()

    def watch_value(self) -> None:
        self.refresh()

    def watch_max_value(self) -> None:
        self.refresh()
