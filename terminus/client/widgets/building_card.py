"""BuildingCard widget — bordered card with mini ASCII art, level pips, health bar."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widget import Widget
from textual.app import RenderResult

from terminus.client.art import get_building_art


class BuildingCard(Widget):
    """Compact building card: art, name, level pips, health bar, status badge."""

    DEFAULT_CSS = """
    BuildingCard {
        height: auto;
        min-height: 7;
        width: 1fr;
        min-width: 20;
        border: round #444444;
        padding: 0 1;
    }
    BuildingCard.under-construction {
        border: round #ffb000;
    }
    BuildingCard.damaged {
        border: round #ff0040;
    }
    """

    building_type: reactive[str] = reactive("")
    level: reactive[int] = reactive(0)
    max_level: reactive[int] = reactive(3)
    health: reactive[float] = reactive(100.0)
    max_health: reactive[float] = reactive(100.0)
    under_construction: reactive[bool] = reactive(False)
    construction_pct: reactive[int] = reactive(0)
    eta_text: reactive[str] = reactive("")

    def __init__(
        self,
        building_type: str = "",
        level: int = 0,
        health: float = 100.0,
        max_health: float = 100.0,
        under_construction: bool = False,
        construction_pct: int = 0,
        eta_text: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.building_type = building_type
        self.level = level
        self.health = health
        self.max_health = max_health
        self.under_construction = under_construction
        self.construction_pct = construction_pct
        self.eta_text = eta_text

    def render(self) -> RenderResult:
        name = self.building_type.title() if self.building_type else "?"
        # Level pips ●●○
        pips = "●" * self.level + "○" * (self.max_level - self.level)

        # Status badge
        if self.under_construction:
            filled = self.construction_pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            status = f"🔨 [{bar}] {self.construction_pct}%"
            if self.eta_text:
                status += f" {self.eta_text}"
        else:
            hp_pct = self.health / max(self.max_health, 1) * 100
            hp_filled = int(hp_pct / 20)
            hp_bar = "█" * hp_filled + "░" * (5 - hp_filled)
            if hp_pct >= 80:
                badge = "✓"
            elif hp_pct >= 40:
                badge = "⚠"
            else:
                badge = "✗"
            status = f"{badge} [{hp_bar}] {hp_pct:.0f}%"

        # Mini ASCII art (first 3 lines only to keep card compact)
        art_lines = get_building_art(self.building_type).split("\n")[:3]
        art_section = "\n".join(art_lines) if art_lines else ""

        return f"{art_section}\n{name} Lv.{self.level} [{pips}]\n{status}"

    def watch_under_construction(self, value: bool) -> None:
        self.remove_class("under-construction", "damaged")
        if value:
            self.add_class("under-construction")
        elif self.health < self.max_health * 0.5:
            self.add_class("damaged")
        self.refresh()

    def watch_health(self, value: float) -> None:
        self.remove_class("damaged")
        if not self.under_construction and value < self.max_health * 0.5:
            self.add_class("damaged")
        self.refresh()

    def watch_level(self) -> None:
        self.refresh()

    def watch_construction_pct(self) -> None:
        self.refresh()

    def flash_complete(self) -> None:
        """Flash green border for 2s to celebrate construction completion."""
        self.add_class("build-complete-flash")
        self.set_timer(2.0, self._remove_flash)

    def _remove_flash(self) -> None:
        self.remove_class("build-complete-flash")
