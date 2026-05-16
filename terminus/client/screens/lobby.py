"""Lobby screens — Create Game and Join Game flows."""

from __future__ import annotations

import asyncio
import socket
import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static

from terminus.client.api import GameClient
from terminus.config import DEFAULT_HOST, DEFAULT_PORT


def _get_local_ip() -> str:
    """Get the local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class CreateGameScreen(Screen):
    """Screen to create a new game as host."""

    def compose(self) -> ComposeResult:
        with Vertical(id="create-container"):
            yield Static("╔══════════════════════════╗", classes="panel-title")
            yield Static("║    CREATE NEW GAME       ║", classes="panel-title")
            yield Static("╚══════════════════════════╝", classes="panel-title")
            yield Label("Your Name:")
            yield Input(placeholder="Enter your name...", id="input-name", max_length=20)
            yield Label("")
            yield Button("▶  Start Server & Create Game", id="btn-start", variant="success")
            yield Button("← Back", id="btn-back", variant="default")
            yield Label("", id="status-label")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-start":
            name_input = self.query_one("#input-name", Input)
            name = name_input.value.strip()
            if not name:
                self.query_one("#status-label", Label).update("⚠ Please enter your name")
                return
            await self._create_game(name)

    async def _create_game(self, name: str) -> None:
        status = self.query_one("#status-label", Label)
        status.update("Starting server...")

        # Start the FastAPI server in a background thread
        self._start_server()
        await asyncio.sleep(1)  # Give server time to start

        # Connect as client
        server_url = f"http://127.0.0.1:{DEFAULT_PORT}"
        client = GameClient(server_url)

        try:
            data = await client.create_game(name)
            local_ip = _get_local_ip()
            share_url = f"http://{local_ip}:{DEFAULT_PORT}"
            # Check if tunnel URL is available
            try:
                from terminus.__main__ import _tunnel_url
                if _tunnel_url:
                    share_url = _tunnel_url
            except ImportError:
                pass
            status.update(f"✓ Game created! Share URL: {share_url}")

            # Store client on app for other screens to use
            self.app._game_client = client  # type: ignore
            self.app._share_url = share_url  # type: ignore
            self.app.register_game_client()  # type: ignore

            # Connect WebSocket
            await client.connect_ws()

            # Push to lobby wait screen
            from terminus.client.screens.lobby import LobbyWaitScreen
            self.app.push_screen(LobbyWaitScreen(is_host=True))
        except Exception as e:
            status.update(f"✗ Error: {e}")

    def _start_server(self) -> None:
        """Start uvicorn server in a background thread."""
        import uvicorn
        from terminus.server.app import app

        # Check if port is already in use
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", DEFAULT_PORT)) == 0:
                raise RuntimeError(
                    f"Port {DEFAULT_PORT} is already in use. "
                    "Another server may be running."
                )

        config = uvicorn.Config(app, host=DEFAULT_HOST, port=DEFAULT_PORT, log_level="warning")
        server = uvicorn.Server(config)

        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()


class JoinGameScreen(Screen):
    """Screen to join an existing game."""

    def compose(self) -> ComposeResult:
        with Vertical(id="join-container"):
            yield Static("╔══════════════════════════╗", classes="panel-title")
            yield Static("║      JOIN A GAME         ║", classes="panel-title")
            yield Static("╚══════════════════════════╝", classes="panel-title")
            yield Label("Server URL:")
            yield Input(placeholder="http://192.168.1.50:8080", id="input-url")
            yield Label("Your Name:")
            yield Input(placeholder="Enter your name...", id="input-name", max_length=20)
            yield Label("")
            yield Button("▶  Connect & Join", id="btn-join", variant="primary")
            yield Button("← Back", id="btn-back", variant="default")
            yield Label("", id="status-label")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-join":
            url_input = self.query_one("#input-url", Input)
            name_input = self.query_one("#input-name", Input)
            url = url_input.value.strip()
            name = name_input.value.strip()

            if not url:
                self.query_one("#status-label", Label).update("⚠ Please enter server URL")
                return
            if not name:
                self.query_one("#status-label", Label).update("⚠ Please enter your name")
                return

            await self._join_game(url, name)

    async def _join_game(self, url: str, name: str) -> None:
        status = self.query_one("#status-label", Label)
        status.update("Connecting...")

        client = GameClient(url)
        try:
            data = await client.join_game(name)
            status.update(f"✓ Joined game!")

            self.app._game_client = client  # type: ignore
            self.app.register_game_client()  # type: ignore
            await client.connect_ws()

            from terminus.client.screens.lobby import LobbyWaitScreen
            self.app.push_screen(LobbyWaitScreen(is_host=False))
        except Exception as e:
            status.update(f"✗ Connection failed: {e}")


class LobbyWaitScreen(Screen):
    """Lobby screen — shows players and waits for game start."""

    def __init__(self, is_host: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.is_host = is_host
        self._refresh_task: asyncio.Task | None = None
        self._my_ready: bool = False

    def compose(self) -> ComposeResult:
        with Vertical(id="lobby-container"):
            yield Static("╔══════════════════════════╗", classes="panel-title")
            yield Static("║        GAME LOBBY        ║", classes="panel-title")
            yield Static("╚══════════════════════════╝", classes="panel-title")

            # Prominent share URL box
            yield Static("╔══════════════════════════════════════════════╗", id="url-box-top")
            yield Label("║  Share this URL to invite players:           ║", id="url-box-label")
            yield Label("║  (loading...)                                ║", id="share-url-label")
            yield Static("╚══════════════════════════════════════════════╝", id="url-box-bot")

            # Game settings panel
            yield Label("")
            yield Static("─── Game Settings ───", classes="panel-title")
            yield Label("  Preset: standard", id="setting-preset")
            yield Label("  Catastrophes: 5", id="setting-catastrophes")
            yield Label("  Max Players: 250", id="setting-max-players")
            if self.is_host:
                with Horizontal(id="settings-controls"):
                    yield Button("Fewer Cats", id="btn-less-cats", variant="default")
                    yield Button("More Cats", id="btn-more-cats", variant="default")

            yield Label("")
            yield Static("─── Players ───", classes="panel-title")
            yield ListView(id="player-list")
            yield Label("", id="player-count")
            with Horizontal():
                yield Button("✓ Ready", id="btn-ready", variant="success")
                if self.is_host:
                    yield Button("▶ Start Game", id="btn-start-game", variant="warning")
            yield Label("", id="lobby-status")
        yield Footer()

    def on_mount(self) -> None:
        if hasattr(self.app, "_share_url"):
            url = self.app._share_url  # type: ignore
            self.query_one("#share-url-label", Label).update(f"║  {url:42s} ║")
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        try:
            while True:
                await self._refresh_lobby()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass

    async def _refresh_lobby(self) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            lobby = await client.get_lobby()
            player_list = self.query_one("#player-list", ListView)
            player_list.clear()
            for p in lobby.get("players", []):
                ready_icon = "✓" if p["ready"] else "○"
                host_badge = " [HOST]" if p["is_host"] else ""
                player_list.append(ListItem(Label(f"  {ready_icon} {p['name']}{host_badge}")))
                # Sync our own ready state from server
                if p.get("player_id") == client.player_id:
                    if p["ready"] != self._my_ready:
                        self._my_ready = p["ready"]
                        self._update_ready_button()
            count = lobby.get("player_count", 0)
            max_p = lobby.get("max_players", 250)
            self.query_one("#player-count", Label).update(f"  {count} / {max_p} players")

            # Update settings display
            settings = lobby.get("settings", {})
            self.query_one("#setting-preset", Label).update(
                f"  Preset: {settings.get('preset', 'standard')}"
            )
            self.query_one("#setting-catastrophes", Label).update(
                f"  Catastrophes: {settings.get('num_catastrophes', 5)}"
            )
            self.query_one("#setting-max-players", Label).update(
                f"  Max Players: {settings.get('max_players', 250)}"
            )

            # If game has moved to setup phase, transition
            if lobby.get("phase") == "setup":
                if self._refresh_task:
                    self._refresh_task.cancel()
                from terminus.client.screens.setup import SetupScreen
                self.app.push_screen(SetupScreen())
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        if event.button.id == "btn-ready":
            try:
                result = await client.toggle_ready()
                self._my_ready = result.get("ready", not self._my_ready)
            except Exception:
                self._my_ready = not self._my_ready
            self._update_ready_button()
        elif event.button.id == "btn-start-game":
            try:
                await client.start_game()
            except Exception as e:
                self.query_one("#lobby-status", Label).update(f"✗ {e}")
        elif event.button.id in ("btn-less-cats", "btn-more-cats"):
            await self._adjust_catastrophes(event.button.id)

    async def _adjust_catastrophes(self, button_id: str) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            lobby = await client.get_lobby()
            current = lobby.get("settings", {}).get("num_catastrophes", 5)
            if button_id == "btn-less-cats":
                new_val = max(1, current - 1)
            else:
                new_val = min(10, current + 1)
            resp = await client._http.post(
                "/game/settings",
                json={"num_catastrophes": new_val},
                headers=client._headers,
            )
            resp.raise_for_status()
        except Exception as e:
            self.query_one("#lobby-status", Label).update(f"✗ {e}")

    def _update_ready_button(self) -> None:
        """Update ready button label and variant to match current state."""
        try:
            btn = self.query_one("#btn-ready", Button)
            if self._my_ready:
                btn.label = "✗ Not Ready"
                btn.variant = "default"
            else:
                btn.label = "✓ Ready"
                btn.variant = "success"
        except Exception:
            pass

    def on_unmount(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
