"""Colony management screen — the main gameplay screen."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from terminus.client.api import GameClient
from terminus.client.widgets import ResourceBar, CountdownTimer, BuildingCard


class ColonyScreen(Screen):
    """Main gameplay screen — resource management, building, workers."""

    BINDINGS = [
        ("b", "open_build", "Build"),
        ("w", "open_workers", "Workers"),
        ("m", "open_market", "Market"),
        ("l", "open_leaderboard", "Scores"),
        ("f12", "open_dev_panel", "Dev Panel"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._refresh_task: asyncio.Task | None = None
        self._prev_building_states: dict[str, bool] = {}  # track construction→complete

    def compose(self) -> ComposeResult:
        with Vertical(id="colony-screen"):
            # Top bar: phase + catastrophe timer
            with Horizontal(id="top-bar"):
                yield Label("Phase: PLAYING", id="phase-label")
                yield CountdownTimer(seconds=0, id="catastrophe-timer")
                yield Label("Catastrophes left: --", id="catastrophe-label")
            with Horizontal(id="info-bar"):
                yield Label("📍 --", id="location-label")
                yield Label("⚙ --", id="spec-label")
                yield Label("⭐ Score: --", id="score-label")
            yield Label("", id="watchtower-hint")

            # Resources panel
            with Vertical(id="resources-panel"):
                yield Static("═══ RESOURCES ═══", classes="panel-title")
                yield ResourceBar(label="Population", value=0, max_value=50, id="bar-population")
                yield ResourceBar(label="Food", value=0, max_value=500, bar_color="green", id="bar-food", classes="resource-food")
                yield ResourceBar(label="Materials", value=0, max_value=500, bar_color="amber", id="bar-materials", classes="resource-materials")
                yield ResourceBar(label="Knowledge", value=0, max_value=200, bar_color="cyan", id="bar-knowledge", classes="resource-knowledge")
                yield ResourceBar(label="Gold", value=0, max_value=300, bar_color="gold", id="bar-gold", classes="resource-gold")
                yield Label("  😊 Morale: 1.00", id="res-morale")

            # Workers panel
            with Vertical(id="workers-panel"):
                yield Static("═══ WORKERS ═══", classes="panel-title")
                yield Label("🌾 Farming: --  ⛏ Mining: --  🔬 Research: --", id="wk-line1")
                yield Label("🔨 Construction: --  🛡 Defense: --  💊 Medicine: --", id="wk-line2")

            # Buildings panel
            with Vertical(id="buildings-panel"):
                yield Static("═══ BUILDINGS ═══", classes="panel-title")
                yield Label("No buildings yet. Press [b] to build.", id="buildings-empty")
                with ScrollableContainer(id="buildings-grid"):
                    pass  # BuildingCard widgets added dynamically

            # Action buttons
            with Horizontal(id="action-bar"):
                yield Button("Build [b]", id="btn-build", variant="success")
                yield Button("Workers [w]", id="btn-workers", variant="primary")
                yield Button("Market [m]", id="btn-market", variant="warning")
                yield Button("Scores [l]", id="btn-scores")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def on_ws_event(self, event: str, data: dict) -> None:
        """Handle WS events forwarded from the app-level dispatcher."""

        if event == "catastrophe_warning":
            seconds = data.get("seconds_until", 0)
            timer = self.query_one("#catastrophe-timer", CountdownTimer)
            timer.start(int(seconds))
            from terminus.audio import play_sound
            play_sound("catastrophe_warning")
            hint = data.get("hint_text")
            if hint:
                self.app.notify_toast(f"⚠ {hint}", "warning")  # type: ignore
            else:
                self.app.notify_toast(f"⚠ Catastrophe incoming in {int(seconds)}s!", "warning")  # type: ignore
        elif event == "catastrophe_started":
            from terminus.client.screens.catastrophe import CatastropheScreen
            from terminus.audio import play_sound
            play_sound("catastrophe_hit")
            self.app.push_screen(CatastropheScreen(data))
        elif event == "catastrophe_results":
            # Forward results to the active catastrophe screen if present
            from terminus.client.screens.catastrophe import CatastropheScreen
            for screen in reversed(self.app.screen_stack):
                if isinstance(screen, CatastropheScreen):
                    screen.receive_results(data)
                    break
        elif event == "market_update":
            # Cache latest market data for when user opens MarketScreen
            self.app._cached_market = data  # type: ignore
        elif event == "state_sync":
            # Full state resync after reconnect — force refresh
            await self._refresh_state()

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
            state = await client.get_state()
            colony = state.get("colony")
            if not colony:
                return

            # Update app status bar (non-critical — don't block resource updates)
            try:
                phase = state.get("phase", "playing")
                num_players = state.get("player_count", 0)
                bar = self.app.status_bar  # type: ignore
                if bar:
                    bar.update_connection(True)
                    bar.update_phase(phase)
                    if num_players:
                        bar.update_players(num_players)
            except Exception:
                pass

            # Location, specialization, score
            location = colony.get("location", "")
            spec = colony.get("specialization", "")
            score = colony.get("score", state.get("score"))
            if location:
                self.query_one("#location-label", Label).update(f"📍 {location.title()}")
            if spec:
                self.query_one("#spec-label", Label).update(f"⚙ {spec.title()}")
            if score is not None:
                self.query_one("#score-label", Label).update(f"⭐ Score: {score:.0f}")

            res = colony.get("resources", {})
            cap = colony.get("capacity", {})
            pop = colony.get("population", 0)
            max_pop = colony.get("max_population", 50)
            morale = colony.get("morale", 1.0)
            workers = colony.get("workers", {})
            buildings = colony.get("buildings", [])

            # Update resource bars
            bar_pop = self.query_one("#bar-population", ResourceBar)
            bar_pop.value = pop
            bar_pop.max_value = max_pop

            bar_food = self.query_one("#bar-food", ResourceBar)
            bar_food.value = res.get("food", 0)
            bar_food.max_value = cap.get("food", 500)

            bar_mat = self.query_one("#bar-materials", ResourceBar)
            bar_mat.value = res.get("materials", 0)
            bar_mat.max_value = cap.get("materials", 500)

            bar_know = self.query_one("#bar-knowledge", ResourceBar)
            bar_know.value = res.get("knowledge", 0)
            bar_know.max_value = cap.get("knowledge", 200)

            bar_gold = self.query_one("#bar-gold", ResourceBar)
            bar_gold.value = res.get("gold", 0)
            bar_gold.max_value = cap.get("gold", 300)

            # Production rates
            rates = state.get("production_rates")
            if rates:
                bar_food.rate = rates.get("food")
                bar_mat.rate = rates.get("materials")
                bar_know.rate = rates.get("knowledge")
                bar_gold.rate = rates.get("gold")

            # Morale with color hint
            morale_str = f"  😊 Morale: {morale:.2f}"
            if morale >= 1.2:
                morale_str += " ▲"
            elif morale <= 0.8:
                morale_str += " ▼"
            self.query_one("#res-morale", Label).update(morale_str)

            # Workers summary (compact two-line display)
            self.query_one("#wk-line1", Label).update(
                f"🌾 Farming: {workers.get('farming', 0):>3}  "
                f"⛏ Mining: {workers.get('mining', 0):>3}  "
                f"🔬 Research: {workers.get('research', 0):>3}"
            )
            self.query_one("#wk-line2", Label).update(
                f"🔨 Construction: {workers.get('construction', 0):>3}  "
                f"🛡 Defense: {workers.get('defense', 0):>3}  "
                f"💊 Medicine: {workers.get('medicine', 0):>3}"
            )

            # Update buildings with BuildingCard widgets
            grid = self.query_one("#buildings-grid", ScrollableContainer)
            empty_label = self.query_one("#buildings-empty", Label)
            if buildings:
                visible = [b for b in buildings if b.get("level", 0) > 0 or b.get("under_construction", False)]
                if visible:
                    empty_label.display = False
                    # Get existing cards by building_type
                    existing = {c.building_type: c for c in grid.query(BuildingCard)}
                    seen = set()
                    for b in visible:
                        btype = b.get("building_type", "?")
                        seen.add(btype)
                        is_building = b.get("under_construction", False)
                        was_building = self._prev_building_states.get(btype, False)

                        # Calculate construction pct and ETA
                        construction_pct = 0
                        eta_text = ""
                        if is_building:
                            progress = b.get("construction_progress", 0)
                            target = b.get("construction_target", 1)
                            construction_pct = min(100, int(progress / max(target, 0.01) * 100))
                            remaining = max(0, target - progress)
                            cw = workers.get("construction", 1)
                            if cw > 0:
                                eta_s = int(remaining * max(pop, 1) / max(cw, 1))
                                eta_text = f"~{eta_s}s" if eta_s > 0 else ""
                            else:
                                eta_text = "(paused)"

                        if btype in existing:
                            card = existing[btype]
                            card.level = b.get("level", 0)
                            card.health = b.get("health", 100)
                            card.under_construction = is_building
                            card.construction_pct = construction_pct
                            card.eta_text = eta_text
                        else:
                            card = BuildingCard(
                                building_type=btype,
                                level=b.get("level", 0),
                                health=b.get("health", 100),
                                under_construction=is_building,
                                construction_pct=construction_pct,
                                eta_text=eta_text,
                                id=f"bcard-{btype}",
                            )
                            grid.mount(card)

                        # Detect completion → toast + flash
                        if was_building and not is_building and b.get("level", 0) > 0:
                            self.app.notify_toast(
                                f"✓ {btype.title()} construction complete!", "success"
                            )  # type: ignore
                            from terminus.audio import play_sound
                            play_sound("build_complete")
                            card.flash_complete()
                        self._prev_building_states[btype] = is_building

                    # Remove cards for buildings no longer present
                    for btype, card in existing.items():
                        if btype not in seen:
                            card.remove()
                else:
                    empty_label.display = True
            else:
                empty_label.display = True

            # Update catastrophe timer from state (if not already counting from WS event)
            timer = self.query_one("#catastrophe-timer", CountdownTimer)
            next_cat = state.get("next_catastrophe_in")
            if next_cat is not None and not timer.running:
                timer.start(int(next_cat))

            remaining = state.get("catastrophes_remaining", 0)
            self.query_one("#catastrophe-label", Label).update(f"Catastrophes left: {remaining}")

            # Watchtower hint
            hint = state.get("watchtower_hint")
            hint_label = self.query_one("#watchtower-hint", Label)
            if hint:
                hint_label.update(f"  🔭 {hint}")
            else:
                hint_label.update("")

        except Exception as exc:
            import logging; logging.getLogger("terminus.client").error("_refresh_state error: %s", exc, exc_info=True)
            self.app.notify_toast(f"Refresh error: {exc}", "error")  # type: ignore

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-build":
            self.action_open_build()
        elif event.button.id == "btn-workers":
            self.action_open_workers()
        elif event.button.id == "btn-market":
            self.action_open_market()
        elif event.button.id == "btn-scores":
            self.action_open_leaderboard()

    def action_open_build(self) -> None:
        from terminus.client.screens.build import BuildScreen
        self.app.push_screen(BuildScreen())

    def action_open_workers(self) -> None:
        from terminus.client.screens.workers import WorkersScreen
        self.app.push_screen(WorkersScreen())

    def action_open_market(self) -> None:
        from terminus.client.screens.market import MarketScreen
        self.app.push_screen(MarketScreen())

    def action_open_leaderboard(self) -> None:
        from terminus.client.screens.leaderboard import LeaderboardScreen
        self.app.push_screen(LeaderboardScreen([]))

    def action_open_dev_panel(self) -> None:
        import os
        dev_enabled = getattr(self.app, "_dev_mode_enabled", False) or os.environ.get("TERMINUS_DEV_MODE") == "1"
        if not dev_enabled:
            return
        from terminus.client.screens.dev_panel import DevPanelScreen
        self.app.push_screen(DevPanelScreen())

    def on_unmount(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
