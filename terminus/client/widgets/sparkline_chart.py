"""SparklineChart widget — inline ASCII sparkline for price/score history."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult


SPARK_CHARS = "▁▂▃▄▅▆▇█"


class SparklineChart(Widget):
    """Renders a compact sparkline from a list of numeric values.

    Uses Unicode block characters with trend-based coloring:
    green if trending up, red if trending down, dim otherwise.
    """

    DEFAULT_CSS = """
    SparklineChart {
        height: 1;
        width: 1fr;
        min-width: 12;
    }
    """

    data: reactive[list[float]] = reactive(list, always_update=True)
    label: reactive[str] = reactive("")

    def __init__(
        self,
        label: str = "",
        data: list[float] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.label = label
        if data:
            self.data = list(data)

    def render(self) -> RenderResult:
        width = self.size.width
        label_part = f"  {self.label:8s} " if self.label else " "
        available = width - len(label_part) - 1
        if available < 2:
            return label_part

        values = self.data
        if not values:
            return f"{label_part}{'─' * available}"

        # Take last N points that fit
        points = values[-available:]

        # Normalize to 0-7 range for spark chars
        lo = min(points)
        hi = max(points)
        spread = hi - lo if hi > lo else 1.0

        spark = ""
        for v in points:
            idx = int((v - lo) / spread * 7)
            idx = max(0, min(7, idx))
            spark += SPARK_CHARS[idx]

        # Determine trend color
        if len(points) >= 2:
            if points[-1] > points[0]:
                color = "green"
            elif points[-1] < points[0]:
                color = "red"
            else:
                color = "white"
        else:
            color = "white"

        text = Text()
        text.append(label_part)
        text.append(spark, style=color)
        return text

    def watch_data(self) -> None:
        self.refresh()
