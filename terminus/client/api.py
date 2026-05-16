"""HTTP + WebSocket client for connecting to the game server."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger(__name__)

EventHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class GameClient:
    """Async client that communicates with the Terminus game server."""

    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.token: str | None = None
        self.player_id: str | None = None
        self.game_id: str | None = None
        self._http = httpx.AsyncClient(base_url=self.server_url, timeout=10.0)
        self._ws_task: asyncio.Task | None = None
        self._event_handler: EventHandler | None = None
        self._ws = None

    def set_event_handler(self, handler: EventHandler) -> None:
        self._event_handler = handler

    @property
    def _headers(self) -> dict[str, str]:
        if self.token:
            return {"x-token": self.token}
        return {}

    # ─── API Calls ───────────────────────────────────────────────────────

    async def create_game(self, player_name: str, settings: dict | None = None) -> dict:
        payload: dict[str, Any] = {"player_name": player_name}
        if settings:
            payload["settings"] = settings
        resp = await self._http.post("/game/create", json=payload)
        resp.raise_for_status()
        data = resp.json()
        self.token = data["token"]
        self.player_id = data["player_id"]
        self.game_id = data["game_id"]
        return data

    async def join_game(self, player_name: str) -> dict:
        resp = await self._http.post("/game/join", json={"player_name": player_name})
        resp.raise_for_status()
        data = resp.json()
        self.token = data["token"]
        self.player_id = data["player_id"]
        self.game_id = data["game_id"]
        return data

    async def get_lobby(self) -> dict:
        resp = await self._http.get("/game/lobby")
        resp.raise_for_status()
        return resp.json()

    async def toggle_ready(self) -> dict:
        resp = await self._http.post("/game/ready", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def start_game(self) -> dict:
        resp = await self._http.post("/game/start", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def submit_setup(self, location: str, specialization: str) -> dict:
        resp = await self._http.post(
            "/game/setup",
            json={"location": location, "specialization": specialization},
            headers=self._headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_state(self) -> dict:
        resp = await self._http.get("/game/state", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def submit_action(self, action_type: str, payload: dict) -> dict:
        resp = await self._http.post(
            "/game/action",
            json={"action_type": action_type, "payload": payload},
            headers=self._headers,
        )
        if resp.status_code == 400:
            try:
                detail = resp.json().get("detail", "Action failed")
            except Exception:
                detail = "Action failed"
            raise ValueError(detail)
        resp.raise_for_status()
        return resp.json()

    async def get_market(self) -> dict:
        resp = await self._http.get("/game/market", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def get_leaderboard(self) -> list:
        resp = await self._http.get("/game/leaderboard", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    # ─── Dev Mode / Admin ────────────────────────────────────────────────

    async def toggle_dev_mode(self) -> dict:
        """Host-only: toggle dev mode on/off."""
        resp = await self._http.post("/game/dev-mode", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def admin_get_state(self) -> dict:
        resp = await self._http.get("/admin/state", headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def admin_set_resources(self, player_id: str, **resources) -> dict:
        data = {"player_id": player_id, **resources}
        resp = await self._http.post("/admin/set-resources", json=data, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def admin_set_catastrophe_speed(self, multiplier: float) -> dict:
        resp = await self._http.post("/admin/set-catastrophe-speed", json={"multiplier": multiplier}, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def admin_trigger_catastrophe(self) -> dict:
        resp = await self._http.post("/admin/trigger-catastrophe", json={}, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    async def admin_complete_building(self, player_id: str) -> dict:
        resp = await self._http.post("/admin/complete-building", json={"player_id": player_id}, headers=self._headers)
        resp.raise_for_status()
        return resp.json()

    # ─── WebSocket Connection ────────────────────────────────────────────

    async def connect_ws(self) -> None:
        """Start WebSocket connection in background."""
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def _ws_loop(self) -> None:
        import json
        import websockets

        ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/game/ws?token={self.token}"

        max_retries = 3
        retry_count = 0
        backoff_base = 2  # seconds

        while retry_count <= max_retries:
            try:
                if retry_count > 0:
                    # Emit reconnecting event
                    if self._event_handler:
                        await self._event_handler("reconnecting", {"attempt": retry_count})
                    delay = backoff_base ** retry_count
                    logger.info(f"Reconnecting in {delay}s (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(delay)

                async with websockets.connect(ws_url) as ws:
                    self._ws = ws
                    # Successful connection — reset retry counter
                    if retry_count > 0:
                        if self._event_handler:
                            await self._event_handler("reconnected", {})
                    retry_count = 0

                    async for message in ws:
                        data = json.loads(message)
                        event = data.get("event", "")
                        event_data = data.get("data", {})

                        # Respond to server heartbeat pings
                        if event == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
                            continue

                        if self._event_handler:
                            try:
                                await self._event_handler(event, event_data)
                            except Exception as handler_err:
                                logger.warning(f"Event handler error for {event}: {handler_err}")

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self._ws = None
                retry_count += 1
                if retry_count > max_retries:
                    if self._event_handler:
                        await self._event_handler("connection_lost", {"error": str(e)})
                    return

    async def disconnect(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        await self._http.aclose()
