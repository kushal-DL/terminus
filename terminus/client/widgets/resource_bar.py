"""ResourceBar widget — horizontal fill bar with value/max display."""

from __future__ import annotations

from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.app import RenderResult


class ResourceBar(Widget):
    """A horizontal bar [████████░░░░] 120/500 with color gradient."""

    DEFAULT_CSS = """
    ResourceBar {
        height: 1;
        width: 1fr;
        min-width: 30;
    }
    """

    value: reactive[float] = reactive(0.0)
    max_value: reactive[float] = reactive(100.0)
    label: reactive[str] = reactive("")
    bar_color: reactive[str] = reactive("green")
    rate: reactive[float | None] = reactive(None)

    def __init__(
        self,
        label: str = "",
        value: float = 0.0,
        max_value: float = 100.0,
        bar_color: str = "green",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        self._flash_timer: Timer | None = None
        super().__init__(name=name, id=id, classes=classes)
        self.label = label
        self.value = value
        self.max_value = max_value
        self.bar_color = bar_color

    def render(self) -> RenderResult:
        width = self.size.width
        # Reserve space for label and value text
        label_part = f"  {self.label:12s} " if self.label else " "
        max_display = int(self.max_value)
        val_display = int(self.value)
        value_part = f" {val_display:>4}/{max_display:<4}"
        # Calculate bar width
        bar_width = width - len(label_part) - len(value_part) - 2  # 2 for brackets
        if bar_width < 4:
            bar_width = 4

        # Calculate fill
        ratio = min(self.value / self.max_value, 1.0) if self.max_value > 0 else 0.0
        filled = int(ratio * bar_width)
        empty = bar_width - filled

        bar = "█" * filled + "░" * empty
        rate_part = ""
        if self.rate is not None:
            sign = "+" if self.rate >= 0 else ""
            rate_part = f" {sign}{self.rate:.1f}/t"
        return f"{label_part}[{bar}]{value_part}{rate_part}"

    def watch_value(self) -> None:
        self._update_color_class()
        self.refresh()

    def watch_max_value(self) -> None:
        self._update_color_class()
        self.refresh()

    def _update_color_class(self) -> None:
        """Update CSS class based on fill percentage."""
        ratio = self.value / self.max_value if self.max_value > 0 else 0.0
        self.remove_class("bar-high", "bar-mid", "bar-low")
        if ratio > 0.5:
            self.add_class("bar-high")
        elif ratio > 0.25:
            self.add_class("bar-mid")
        else:
            self.add_class("bar-low")

        # Depletion flash: alternate red when <10%
        if ratio < 0.10 and self.max_value > 0 and self.value > 0:
            if self._flash_timer is None:
                self._flash_timer = self.set_interval(0.5, self._toggle_depleted)
        else:
            if self._flash_timer is not None:
                self._flash_timer.stop()
                self._flash_timer = None
                self.remove_class("resource-depleted")

    def _toggle_depleted(self) -> None:
        """Toggle the depletion warning class for flashing effect."""
        self.toggle_class("resource-depleted")
