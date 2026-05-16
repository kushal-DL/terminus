"""Setup screen — Location and Specialization selection."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, OptionList, Static
from textual.widgets.option_list import Option

from terminus.client.api import GameClient
from terminus.client.art import get_location_art, get_specialization_art
from terminus.data.loader import get_locations, get_specializations


class SetupScreen(Screen):
    """Player picks location and specialization."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_location: str | None = None
        self._selected_spec: str | None = None
        self._countdown_task: asyncio.Task | None = None
        self._seconds_left = 90

    def compose(self) -> ComposeResult:
        locations = get_locations()
        specs = get_specializations()

        with Vertical(id="setup-container"):
            yield Static("╔══════════════════════════════════════╗", classes="panel-title")
            yield Static("║    CHOOSE YOUR SETTLEMENT SETUP        ║", classes="panel-title")
            yield Static("╚══════════════════════════════════════╝", classes="panel-title")
            yield Label("", id="countdown-label")

            with Horizontal():
                with Vertical(id="setup-left"):
                    yield Label("⛰  LOCATION:", classes="panel-title")
                    yield OptionList(
                        *[Option(f"{loc['name']} — {loc['description']}", id=loc['id']) for loc in locations],
                        id="location-list",
                    )

                with Vertical(id="setup-center"):
                    yield Label("⚙  SPECIALIZATION:", classes="panel-title")
                    yield OptionList(
                        *[Option(f"{s['name']} — {s['description']}", id=s['id']) for s in specs],
                        id="spec-list",
                    )

                with Vertical(id="setup-right"):
                    yield Label("🎨  PREVIEW:", classes="panel-title")
                    yield Static("", id="art-preview")

            yield Label("", id="preview-label")
            yield Button("✓  Confirm Selection", id="btn-confirm", variant="success")
            yield Label("", id="setup-status")
        yield Footer()

    def on_mount(self) -> None:
        self._countdown_task = asyncio.create_task(self._countdown())

    async def _countdown(self) -> None:
        try:
            while self._seconds_left > 0:
                self.query_one("#countdown-label", Label).update(
                    f"⏱  Time remaining: {self._seconds_left}s"
                )
                await asyncio.sleep(1)
                self._seconds_left -= 1
            # Auto-submit if time runs out
            await self._submit_selection()
        except asyncio.CancelledError:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        option_list = event.option_list
        if option_list.id == "location-list":
            self._selected_location = event.option.id
            art = get_location_art(event.option.id)
            self.query_one("#art-preview", Static).update(art)
        elif option_list.id == "spec-list":
            self._selected_spec = event.option.id
            art = get_specialization_art(event.option.id)
            self.query_one("#art-preview", Static).update(art)
        self._update_preview()

    def _update_preview(self) -> None:
        parts = []
        if self._selected_location:
            loc = next((l for l in get_locations() if l["id"] == self._selected_location), None)
            if loc:
                mods = loc["production_modifiers"]
                parts.append(f"Location: {loc['name']} | Food ×{mods['food']} | Materials ×{mods['materials']} | Knowledge ×{mods['knowledge']} | Gold ×{mods['gold']}")
        if self._selected_spec:
            spec = next((s for s in get_specializations() if s["id"] == self._selected_spec), None)
            if spec:
                parts.append(f"Spec: {spec['name']} | {spec['description']}")
        self.query_one("#preview-label", Label).update("\n".join(parts) if parts else "")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-confirm":
            await self._submit_selection()

    async def _submit_selection(self) -> None:
        if self._countdown_task:
            self._countdown_task.cancel()

        # Default selections if none made
        location = self._selected_location or "plains"
        spec = self._selected_spec or "agriculture"

        client: GameClient = self.app._game_client  # type: ignore
        status = self.query_one("#setup-status", Label)

        try:
            await client.submit_setup(location, spec)
            status.update("✓ Selection confirmed! Waiting for other players...")

            # Poll for game to start
            for _ in range(100):
                await asyncio.sleep(1)
                state = await client.get_state()
                if state.get("phase") == "playing":
                    from terminus.client.screens.colony import ColonyScreen
                    self.app.push_screen(ColonyScreen())
                    return
        except Exception as e:
            status.update(f"✗ Error: {e}")

    def on_unmount(self) -> None:
        if self._countdown_task:
            self._countdown_task.cancel()
