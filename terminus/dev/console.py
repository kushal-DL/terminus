"""Dev Console — Textual TUI for administrating a running Terminus game."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual.reactive import reactive


# ─── API Client ──────────────────────────────────────────────────────────────


class AdminClient:
    """Simple HTTP client for admin endpoints."""

    def __init__(self, server_url: str) -> None:
        self.server_url = server_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self.server_url, timeout=5.0)

    async def get_state(self) -> dict[str, Any]:
        resp = await self._http.get("/admin/state")
        resp.raise_for_status()
        return resp.json()

    async def set_resources(self, data: dict) -> dict:
        resp = await self._http.post("/admin/set-resources", json=data)
        resp.raise_for_status()
        return resp.json()

    async def set_catastrophe_speed(self, multiplier: float) -> dict:
        resp = await self._http.post("/admin/set-catastrophe-speed", json={"multiplier": multiplier})
        resp.raise_for_status()
        return resp.json()

    async def trigger_catastrophe(self) -> dict:
        resp = await self._http.post("/admin/trigger-catastrophe")
        resp.raise_for_status()
        return resp.json()

    async def complete_building(self, player_id: str | None = None) -> dict:
        resp = await self._http.post("/admin/complete-building", json={"player_id": player_id or ""})
        resp.raise_for_status()
        return resp.json()

    async def health(self) -> dict:
        resp = await self._http.get("/health")
        resp.raise_for_status()
        return resp.json()


# ─── Player Card Widget ─────────────────────────────────────────────────────


class PlayerCard(Static):
    """Display panel for a single player's colony state."""

    DEFAULT_CSS = """
    PlayerCard {
        border: round #00ff41 30%;
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, player_id: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.player_id = player_id
        self.player_name = name

    def compose(self) -> ComposeResult:
        yield Label(f"═══ {self.player_name} ═══", classes="panel-title")
        yield Label("", id=f"p-{self.player_id}-resources")
        yield Label("", id=f"p-{self.player_id}-workers")
        yield Label("", id=f"p-{self.player_id}-buildings")
        yield Label("", id=f"p-{self.player_id}-rates")
        with Horizontal():
            yield Input(placeholder="food", id=f"p-{self.player_id}-food", type="number")
            yield Input(placeholder="materials", id=f"p-{self.player_id}-mat", type="number")
            yield Input(placeholder="knowledge", id=f"p-{self.player_id}-know", type="number")
            yield Input(placeholder="gold", id=f"p-{self.player_id}-gold", type="number")
        yield Button("✓ Set Resources", id=f"btn-set-{self.player_id}", variant="success")
        yield Button("⚡ Complete Buildings", id=f"btn-complete-{self.player_id}", variant="primary")

    def update_state(self, colony: dict | None, rates: dict | None) -> None:
        if not colony:
            return
        res = colony.get("resources", {})
        workers = colony.get("workers", {})
        buildings = colony.get("buildings", [])
        pop = colony.get("population", 0)
        morale = colony.get("morale", 1.0)

        res_text = (
            f"  Pop: {pop}  Morale: {morale:.2f}\n"
            f"  Food: {int(res.get('food', 0))}  "
            f"Mat: {int(res.get('materials', 0))}  "
            f"Know: {int(res.get('knowledge', 0))}  "
            f"Gold: {int(res.get('gold', 0))}"
        )

        wk_text = (
            f"  🌾{workers.get('farming', 0)} "
            f"⛏{workers.get('mining', 0)} "
            f"🔬{workers.get('research', 0)} "
            f"🔨{workers.get('construction', 0)} "
            f"🛡{workers.get('defense', 0)} "
            f"💊{workers.get('medicine', 0)}"
        )

        bld_parts = []
        for b in buildings:
            if b.get("level", 0) > 0 or b.get("under_construction"):
                name = b.get("building_type", "?")
                lvl = b.get("level", 0)
                status = "🔨" if b.get("under_construction") else f"Lv.{lvl}"
                bld_parts.append(f"{name}({status})")
        bld_text = "  " + ", ".join(bld_parts) if bld_parts else "  No buildings"

        rate_text = "  Rates: —"
        if rates:
            rate_text = (
                f"  Rates: food {rates.get('food', 0):+.2f}/t  "
                f"mat {rates.get('materials', 0):+.2f}/t  "
                f"know {rates.get('knowledge', 0):+.2f}/t  "
                f"gold {rates.get('gold', 0):+.2f}/t"
            )

        try:
            self.query_one(f"#p-{self.player_id}-resources", Label).update(res_text)
            self.query_one(f"#p-{self.player_id}-workers", Label).update(wk_text)
            self.query_one(f"#p-{self.player_id}-buildings", Label).update(bld_text)
            self.query_one(f"#p-{self.player_id}-rates", Label).update(rate_text)
        except Exception:
            pass


# ─── Main Dev Console App ───────────────────────────────────────────────────


class DevConsoleApp(App):
    """Terminus Dev Console — admin TUI for debugging and testing."""

    TITLE = "TERMINUS DEV CONSOLE"
    SUB_TITLE = "Admin Tools"

    CSS = """
    Screen {
        background: #1a1a2e;
    }
    #console-header {
        dock: top;
        height: 3;
        background: #0d0d1a;
        color: #ff0040;
        text-style: bold;
        padding: 1;
        text-align: center;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: #0d0d1a;
        color: #00ff41;
        padding: 0 1;
    }
    #game-info {
        height: 3;
        border: round #00d4ff 30%;
        padding: 0 1;
        margin-bottom: 1;
    }
    #catastrophe-controls {
        border: round #ff0040 30%;
        padding: 0 1;
        height: auto;
        margin-bottom: 1;
    }
    #player-area {
        height: 1fr;
    }
    .panel-title {
        text-style: bold;
        color: #00d4ff;
    }
    Label {
        color: #00ff41;
    }
    Input {
        background: #0d0d1a;
        color: #00ff41;
        border: tall #00ff41 30%;
        width: 1fr;
        margin-right: 1;
    }
    Input:focus {
        border: tall #00ff41;
    }
    Button {
        background: #0d0d1a;
        color: #00ff41;
        border: tall #00ff41 30%;
        margin: 0 1;
    }
    Button:hover {
        background: #00ff41 10%;
    }
    Button.-error {
        color: #ff0040;
        border: tall #ff0040 50%;
    }
    Button.-warning {
        color: #ffb000;
        border: tall #ffb000 50%;
    }
    PlayerCard Input {
        height: 1;
        min-width: 8;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("t", "trigger_cat", "Trigger Catastrophe"),
    ]

    def __init__(self, server_url: str = "http://127.0.0.1:8080", **kwargs):
        super().__init__(**kwargs)
        self._server_url = server_url
        self._client = AdminClient(server_url)
        self._refresh_task: asyncio.Task | None = None
        self._player_cards: dict[str, PlayerCard] = {}

    def compose(self) -> ComposeResult:
        yield Static("⚙  TERMINUS DEV CONSOLE  ⚙", id="console-header")
        with Vertical():
            yield Label("", id="game-info")
            with Horizontal(id="catastrophe-controls"):
                yield Label("═══ CATASTROPHE CONTROL ═══", classes="panel-title")
                yield Button("⚡ Trigger Now", id="btn-trigger-cat", variant="error")
                yield Button("0.5× Faster", id="btn-cat-fast", variant="warning")
                yield Button("1× Normal", id="btn-cat-normal")
                yield Button("2× Slower", id="btn-cat-slow", variant="warning")
                yield Button("5× Very Slow", id="btn-cat-veryslow", variant="warning")
            with ScrollableContainer(id="player-area"):
                pass  # Player cards added dynamically
        yield Label("", id="status-bar")
        yield Footer()

    async def on_mount(self) -> None:
        self._refresh_task = asyncio.create_task(self._auto_refresh())

    async def _auto_refresh(self) -> None:
        """Poll server state every 2 seconds."""
        while True:
            await self._do_refresh()
            await asyncio.sleep(2)

    async def _do_refresh(self) -> None:
        """Fetch full state and update UI."""
        status = self.query_one("#status-bar", Label)
        try:
            state = await self._client.get_state()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                status.update("✗ Dev mode not enabled. Start server with TERMINUS_DEV_MODE=1")
            else:
                status.update(f"✗ HTTP {e.response.status_code}")
            return
        except Exception as e:
            status.update(f"✗ Connection failed: {e}")
            return

        # Game info
        phase = state.get("phase", "?")
        ticks = state.get("elapsed_ticks", 0)
        player_count = len(state.get("players", {}))
        cat_idx = state.get("current_catastrophe_index", 0)
        cat_total = len(state.get("catastrophe_schedule", []))

        # Next catastrophe ETA
        cat_eta = "—"
        schedule = state.get("catastrophe_schedule", [])
        start_time = state.get("game_start_time")
        if schedule and start_time and cat_idx < len(schedule):
            import time
            elapsed = time.time() - start_time
            next_time = schedule[cat_idx].get("scheduled_time", 0)
            remaining = max(0, next_time - elapsed)
            cat_eta = f"{int(remaining)}s"

        info = (
            f"  Phase: {phase.upper()}  │  Tick: {ticks}  │  "
            f"Players: {player_count}  │  "
            f"Catastrophes: {cat_idx}/{cat_total}  │  Next in: {cat_eta}"
        )
        self.query_one("#game-info", Label).update(info)
        status.update(f"● Connected to {self._server_url}  │  Last refresh: tick {ticks}")

        # Update player cards
        players = state.get("players", {})
        area = self.query_one("#player-area", ScrollableContainer)

        for pid, pdata in players.items():
            if pid not in self._player_cards:
                card = PlayerCard(pid, pdata.get("name", "?"), id=f"card-{pid}")
                self._player_cards[pid] = card
                area.mount(card)
            self._player_cards[pid].update_state(
                pdata.get("colony"), pdata.get("production_rates")
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        status = self.query_one("#status-bar", Label)

        try:
            if btn_id == "btn-trigger-cat":
                result = await self._client.trigger_catastrophe()
                status.update(f"✓ Catastrophe triggered (index {result.get('triggered_index')})")
            elif btn_id == "btn-cat-fast":
                await self._client.set_catastrophe_speed(0.5)
                status.update("✓ Catastrophe speed: 0.5× (faster)")
            elif btn_id == "btn-cat-normal":
                await self._client.set_catastrophe_speed(1.0)
                status.update("✓ Catastrophe speed: 1× (normal)")
            elif btn_id == "btn-cat-slow":
                await self._client.set_catastrophe_speed(2.0)
                status.update("✓ Catastrophe speed: 2× (slower)")
            elif btn_id == "btn-cat-veryslow":
                await self._client.set_catastrophe_speed(5.0)
                status.update("✓ Catastrophe speed: 5× (very slow)")
            elif btn_id and btn_id.startswith("btn-set-"):
                player_id = btn_id[len("btn-set-"):]
                await self._set_player_resources(player_id)
            elif btn_id and btn_id.startswith("btn-complete-"):
                player_id = btn_id[len("btn-complete-"):]
                result = await self._client.complete_building(player_id)
                completed = result.get("completed", [])
                if completed:
                    status.update(f"✓ Completed: {', '.join(completed)}")
                else:
                    status.update("No buildings under construction")
        except Exception as e:
            status.update(f"✗ {e}")

        await self._do_refresh()

    async def _set_player_resources(self, player_id: str) -> None:
        """Read input fields and send set-resources request."""
        data: dict[str, Any] = {"player_id": player_id}
        for field, key in [("food", "food"), ("mat", "materials"), ("know", "knowledge"), ("gold", "gold")]:
            try:
                inp = self.query_one(f"#p-{player_id}-{field}", Input)
                if inp.value.strip():
                    data[key] = float(inp.value.strip())
                    inp.value = ""
            except Exception:
                pass
        if len(data) > 1:  # More than just player_id
            result = await self._client.set_resources(data)
            self.query_one("#status-bar", Label).update(f"✓ Resources set for {player_id[:8]}...")
        else:
            self.query_one("#status-bar", Label).update("⚠ Enter at least one resource value")

    def action_refresh(self) -> None:
        asyncio.create_task(self._do_refresh())

    def action_trigger_cat(self) -> None:
        asyncio.create_task(self._trigger_catastrophe())

    async def _trigger_catastrophe(self) -> None:
        try:
            result = await self._client.trigger_catastrophe()
            self.query_one("#status-bar", Label).update(
                f"✓ Catastrophe triggered (index {result.get('triggered_index')})"
            )
        except Exception as e:
            self.query_one("#status-bar", Label).update(f"✗ {e}")
