"""Workers screen — reallocate worker distribution using slider widgets."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from terminus.client.api import GameClient
from terminus.client.widgets import WorkerSlider
from terminus.config import WORKER_ROLES


class WorkersScreen(Screen):
    """Screen for reallocating workers across roles."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        with Vertical(id="workers-container"):
            yield Static("═══ WORKER ALLOCATION ═══", classes="panel-title")
            yield Label("Use ◄/► to adjust. Total must equal population.", id="workers-help")
            yield Label("", id="pop-label")
            yield Label("", id="pool-label")

            for role in WORKER_ROLES:
                yield WorkerSlider(role=role, value=0, max_value=0, id=f"slider-{role}")

            yield Label("", id="total-label")
            yield Button("✓  Apply Allocation", id="btn-apply", variant="success")
            yield Button("← Back [Esc]", id="btn-back")
            yield Label("", id="workers-status")
        yield Footer()

    async def on_mount(self) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            state = await client.get_state()
            colony = state.get("colony", {})
            pop = int(colony.get("population", 0))
            workers = colony.get("workers", {})
            self.query_one("#pop-label", Label).update(f"  Total population: {pop}")
            for role in WORKER_ROLES:
                slider = self.query_one(f"#slider-{role}", WorkerSlider)
                slider.value = int(workers.get(role, 0))
                slider.max_value = pop
            self._update_pool()
        except Exception as e:
            self.query_one("#workers-status", Label).update(f"✗ Failed to load workers: {e}")

    def on_worker_slider_changed(self, event: WorkerSlider.Changed) -> None:
        """React to any slider change — update pool display."""
        self._update_pool()

    def _update_pool(self) -> None:
        """Recalculate and display remaining unallocated workers."""
        total = 0
        pop = 0
        for role in WORKER_ROLES:
            slider = self.query_one(f"#slider-{role}", WorkerSlider)
            total += slider.value
            pop = slider.max_value  # all sliders share max
        remaining = pop - total
        self.query_one("#pool-label", Label).update(f"  Unallocated: {remaining}")
        self.query_one("#total-label", Label).update(f"  Total allocated: {total} / {pop}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
            return

        if event.button.id == "btn-apply":
            allocation = {}
            for role in WORKER_ROLES:
                slider = self.query_one(f"#slider-{role}", WorkerSlider)
                allocation[role] = slider.value

            client: GameClient = self.app._game_client  # type: ignore
            status = self.query_one("#workers-status", Label)
            try:
                await client.submit_action("allocate_workers", {"allocation": allocation})
                status.update("✓ Workers reallocated!")
                self.app.notify_toast("✓ Workers reallocated!", "success")
                from terminus.audio import play_sound
                play_sound("worker_allocated")
                await asyncio.sleep(1)
                self.app.pop_screen()
            except Exception as e:
                status.update(f"✗ {e}")
                self.app.notify_toast(str(e), "error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
