"""Dev Panel — Host-only in-game admin panel (F12)."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from terminus.client.api import GameClient


class DevPanelScreen(ModalScreen):
    """Modal admin panel — resource editing, catastrophe controls, state viewer."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("f12", "dismiss", "Close"),
    ]

    CSS = """
    DevPanelScreen {
        align: center middle;
    }

    #dev-panel {
        width: 80;
        height: 40;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #dev-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    .dev-section {
        margin-bottom: 1;
    }

    .dev-section-title {
        text-style: bold;
        color: $accent;
    }

    #resource-inputs {
        height: auto;
        margin: 0 1;
    }

    #resource-inputs Input {
        width: 12;
        margin-right: 1;
    }

    #player-selector {
        height: 6;
        margin-bottom: 1;
    }

    #state-viewer {
        height: 10;
        margin-top: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_task: asyncio.Task | None = None
        self._players: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="dev-panel"):
            yield Static("═══ DEV PANEL (Host Only) ═══", id="dev-title")

            # Player selector
            yield Static("─── Player ───", classes="dev-section-title")
            yield OptionList(id="player-selector")

            # Resource editor
            yield Static("─── Set Resources ───", classes="dev-section-title")
            with Horizontal(id="resource-inputs"):
                yield Input(placeholder="Food", id="input-food", type="number")
                yield Input(placeholder="Matrl", id="input-materials", type="number")
                yield Input(placeholder="Know", id="input-knowledge", type="number")
                yield Input(placeholder="Gold", id="input-gold", type="number")
                yield Input(placeholder="Pop", id="input-population", type="number")
                yield Input(placeholder="Morale", id="input-morale", type="number")
            yield Button("Set Resources", id="btn-set-resources", variant="warning")

            # Catastrophe controls
            yield Static("─── Catastrophe ───", classes="dev-section-title")
            with Horizontal(classes="dev-section"):
                yield Button("Trigger Now", id="btn-trigger-cat", variant="error")
                yield Button("0.5×", id="btn-speed-05", variant="default")
                yield Button("1×", id="btn-speed-1", variant="default")
                yield Button("2×", id="btn-speed-2", variant="default")
                yield Button("5×", id="btn-speed-5", variant="default")

            # Building controls
            yield Static("─── Buildings ───", classes="dev-section-title")
            yield Button("Complete All Buildings", id="btn-complete-bldg", variant="success")

            # State viewer
            yield Static("─── State ───", classes="dev-section-title")
            yield TextArea("Loading...", id="state-viewer", read_only=True)

            yield Label("", id="dev-status")
        yield Footer()

    async def on_mount(self) -> None:
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        try:
            while True:
                await self._refresh_state()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    async def _refresh_state(self) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            state = await client.admin_get_state()
            # Update player list
            players = state.get("players", [])
            if players != self._players:
                self._players = players
                selector = self.query_one("#player-selector", OptionList)
                selector.clear_options()
                for p in players:
                    selector.add_option(Option(f"{p['name']} ({p['player_id'][:8]}…)"))

            # Update state viewer
            import json
            viewer = self.query_one("#state-viewer", TextArea)
            # Show compact summary
            summary = {
                "turn": state.get("turn"),
                "phase": state.get("phase"),
                "dev_mode": state.get("dev_mode"),
                "players": [
                    {
                        "name": p["name"],
                        "food": p.get("resources", {}).get("food"),
                        "materials": p.get("resources", {}).get("materials"),
                        "knowledge": p.get("resources", {}).get("knowledge"),
                        "gold": p.get("resources", {}).get("gold"),
                        "population": p.get("resources", {}).get("population"),
                        "morale": p.get("resources", {}).get("morale"),
                    }
                    for p in players
                ],
            }
            viewer.load_text(json.dumps(summary, indent=2))
        except Exception as e:
            self._set_status(f"✗ Refresh failed: {e}")

    def _get_selected_player_id(self) -> str | None:
        """Get the player_id of the currently selected player."""
        selector = self.query_one("#player-selector", OptionList)
        idx = selector.highlighted
        if idx is not None and 0 <= idx < len(self._players):
            return self._players[idx]["player_id"]
        return None

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        btn_id = event.button.id

        if btn_id == "btn-set-resources":
            await self._set_resources(client)
        elif btn_id == "btn-trigger-cat":
            try:
                await client.admin_trigger_catastrophe()
                self._set_status("Catastrophe triggered!")
            except Exception as e:
                self._set_status(f"✗ {e}")
        elif btn_id == "btn-speed-05":
            await self._set_speed(client, 0.5)
        elif btn_id == "btn-speed-1":
            await self._set_speed(client, 1.0)
        elif btn_id == "btn-speed-2":
            await self._set_speed(client, 2.0)
        elif btn_id == "btn-speed-5":
            await self._set_speed(client, 5.0)
        elif btn_id == "btn-complete-bldg":
            player_id = self._get_selected_player_id()
            if not player_id:
                self._set_status("✗ Select a player first")
                return
            try:
                await client.admin_complete_building(player_id)
                self._set_status(f"Buildings completed for {player_id[:8]}…")
            except Exception as e:
                self._set_status(f"✗ {e}")

    async def _set_resources(self, client: GameClient) -> None:
        player_id = self._get_selected_player_id()
        if not player_id:
            self._set_status("✗ Select a player first")
            return

        resources = {}
        for field, key in [
            ("input-food", "food"),
            ("input-materials", "materials"),
            ("input-knowledge", "knowledge"),
            ("input-gold", "gold"),
            ("input-population", "population"),
            ("input-morale", "morale"),
        ]:
            val = self.query_one(f"#{field}", Input).value.strip()
            if val:
                try:
                    resources[key] = float(val) if key == "morale" else int(val)
                except ValueError:
                    pass

        if not resources:
            self._set_status("✗ Enter at least one resource value")
            return

        try:
            await client.admin_set_resources(player_id, **resources)
            self._set_status(f"Resources set for {player_id[:8]}…")
        except Exception as e:
            self._set_status(f"✗ {e}")

    async def _set_speed(self, client: GameClient, multiplier: float) -> None:
        try:
            await client.admin_set_catastrophe_speed(multiplier)
            self._set_status(f"Catastrophe speed: {multiplier}×")
        except Exception as e:
            self._set_status(f"✗ {e}")

    def _set_status(self, msg: str) -> None:
        try:
            self.query_one("#dev-status", Label).update(msg)
        except Exception:
            pass

    def on_unmount(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
