"""Build screen — select and construct buildings."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, OptionList, Static
from textual.widgets.option_list import Option

from terminus.client.api import GameClient
from terminus.client.art import get_building_art
from terminus.data.loader import get_buildings

# Human-friendly effect labels: key → (label, format_string)
_EFFECT_LABELS: dict[str, tuple[str, str]] = {
    "food_production_bonus": ("Food production", "+{:.0%}"),
    "materials_production_bonus": ("Materials production", "+{:.0%}"),
    "knowledge_production_bonus": ("Knowledge production", "+{:.0%}"),
    "gold_production_bonus": ("Gold production", "+{:.0%}"),
    "trade_unlock": ("Trading", "Unlocked"),
    "trade_discount": ("Trade discount", "{:.0%}"),
    "plague_mitigation": ("Plague mitigation", "+{:.0%}"),
    "healing": ("Healing", "+{}/tick"),
    "defense_bonus": ("Defense", "+{:.0%}"),
    "capacity_multiplier": ("Storage capacity", "×{:.1f}"),
    "pop_cap": ("Population cap", "+{}"),
    "morale_bonus": ("Morale", "+{:.2f}"),
    "hint_level": ("Catastrophe intel", "Level {}"),
}


def _format_effects(effects: dict) -> str:
    """Format a building effects dict into a human-readable string."""
    parts: list[str] = []
    for key, val in effects.items():
        if key in _EFFECT_LABELS:
            label, fmt = _EFFECT_LABELS[key]
            if isinstance(val, bool):
                parts.append(f"{label}: {fmt}")
            else:
                parts.append(f"{label}: {fmt.format(val)}")
        else:
            parts.append(f"{key}: {val}")
    return " │ ".join(parts) if parts else "—"


class BuildScreen(Screen):
    """Screen for building new structures or upgrading existing ones."""

    BINDINGS = [("escape", "go_back", "Back")]

    _current_resources: dict = {}
    _colony_buildings: dict = {}

    def compose(self) -> ComposeResult:
        buildings = get_buildings()
        with Horizontal(id="build-layout"):
            with Vertical(id="build-container"):
                yield Static("═══ BUILD / UPGRADE ═══", classes="panel-title")
                yield OptionList(
                    *[Option(f"{b['name']} — {b['description']}", id=b['id']) for b in buildings],
                    id="building-list",
                )
                yield Label("", id="cost-preview")
                yield Label("", id="effect-preview")
                yield Button("🔨 Build", id="btn-build", variant="success")
                yield Button("⬆  Upgrade", id="btn-upgrade", variant="primary")
                yield Button("← Back [Esc]", id="btn-back")
                yield Label("", id="build-status")
            with Vertical(id="build-art-panel"):
                yield Static("", id="building-art")
        yield Footer()

    async def on_mount(self) -> None:
        """Fetch current resources and colony buildings."""
        client: GameClient = self.app._game_client  # type: ignore
        try:
            state = await client.get_state()
            colony = state.get("colony", {})
            self._current_resources = colony.get("resources", {})
            self._colony_buildings = {
                b.get("building_type", ""): b
                for b in colony.get("buildings", [])
                if b.get("building_type")
            }
        except Exception:
            self._current_resources = {}
            self._colony_buildings = {}
        self._update_option_colors()

    def _get_current_level(self, building_id: str) -> int:
        existing = self._colony_buildings.get(building_id)
        if not existing:
            return 0
        return existing.get("level", 0)

    def _is_under_construction(self, building_id: str) -> bool:
        existing = self._colony_buildings.get(building_id)
        return bool(existing and existing.get("under_construction"))

    def _can_afford(self, costs: dict) -> bool:
        for resource, amount in costs.items():
            if self._current_resources.get(resource, 0) < amount:
                return False
        return True

    def _update_option_colors(self) -> None:
        """Repaint OptionList items with level badges and affordability."""
        option_list = self.query_one("#building-list", OptionList)
        option_list.clear_options()
        for b in get_buildings():
            bid = b["id"]
            level = self._get_current_level(bid)
            max_level = b.get("max_level", 3)
            under_construction = self._is_under_construction(bid)

            if under_construction:
                badge = "🔨"
            elif level >= max_level:
                badge = "MAX"
            elif level > 0:
                badge = f"Lv.{level}"
            else:
                badge = "NEW"

            next_level = min(level + 1, max_level)
            if level < max_level and not under_construction:
                costs = b.get("costs", {}).get(str(next_level), {})
                prefix = "✓" if self._can_afford(costs) else "✗"
            else:
                prefix = " "

            option_list.add_option(
                Option(f"[{badge}] {prefix} {b['name']} — {b['description']}", id=bid)
            )

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        building_id = event.option.id
        b_data = next((b for b in get_buildings() if b["id"] == building_id), None)
        if not b_data:
            return

        level = self._get_current_level(building_id)
        max_level = b_data.get("max_level", 3)
        under_construction = self._is_under_construction(building_id)

        cost_label = self.query_one("#cost-preview", Label)
        effect_label = self.query_one("#effect-preview", Label)

        if under_construction:
            existing = self._colony_buildings[building_id]
            pct = 0
            prog = existing.get("construction_progress", 0)
            target = existing.get("construction_target", 1)
            if target > 0:
                pct = min(100, int(prog / target * 100))
            cost_label.update(f"🔨 Under construction — {pct}% complete")
            effects = b_data.get("effects", {}).get(str(level), {})
            effect_label.update(f"  Effect (Lv.{level}): {_format_effects(effects)}")
        elif level >= max_level:
            cost_label.update(f"Level {level} — MAX LEVEL")
            effects = b_data.get("effects", {}).get(str(level), {})
            effect_label.update(f"  Effect: {_format_effects(effects)}")
        else:
            next_level = level + 1
            costs = b_data["costs"].get(str(next_level), {})
            parts = []
            for k, v in costs.items():
                have = self._current_resources.get(k, 0)
                color = "green" if have >= v else "red"
                parts.append(f"[{color}]{k}: {v}[/]")
            cost_str = " | ".join(parts)
            ticks = b_data["build_time_ticks"].get(str(next_level), "?")
            action = "Build" if level == 0 else f"Upgrade to"
            cost_label.update(f"{action} Level {next_level}: {cost_str} | Build time: {ticks} ticks")

            effects = b_data.get("effects", {}).get(str(next_level), {})
            effect_label.update(f"  Effect: {_format_effects(effects)}")

        art = get_building_art(building_id)
        self.query_one("#building-art", Static).update(art)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
            return

        option_list = self.query_one("#building-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            self.query_one("#build-status", Label).update("⚠ Select a building first")
            return

        building_id = option_list.get_option_at_index(highlighted).id
        client: GameClient = self.app._game_client  # type: ignore
        status = self.query_one("#build-status", Label)

        try:
            if event.button.id == "btn-build":
                result = await client.submit_action("build", {"building_type": building_id})
                status.update(f"✓ {result.get('status', 'OK')}")
                self.app.notify_toast(f"✓ Started building {building_id}", "success")
            elif event.button.id == "btn-upgrade":
                result = await client.submit_action("upgrade", {"building_type": building_id})
                status.update(f"✓ {result.get('status', 'OK')}")
                self.app.notify_toast(f"✓ Upgrading {building_id}", "success")
            # Refresh state after action
            await self.on_mount()
        except Exception as e:
            status.update(f"✗ {e}")
            self.app.notify_toast(str(e), "error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
