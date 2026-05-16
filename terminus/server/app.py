"""FastAPI server — REST API and WebSocket endpoints."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from terminus.server.engine import GameEngine
from terminus.config import SETUP_PHASE_SECONDS
from terminus.server.models import (
    ActionType,
    BuildAction,
    UpgradeAction,
    AllocateWorkersAction,
    TradeBuyAction,
    TradeSellAction,
    DemolishAction,
    RepairAction,
    CreateGameRequest,
    CreateGameResponse,
    GameActionRequest,
    GamePhase,
    GameSettings,
    JoinGameRequest,
    JoinGameResponse,
    Player,
    SetupRequest,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Terminus Game Server", version="0.1.0")

MAX_BODY_BYTES = 64 * 1024  # 64KB payload limit


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject HTTP requests with bodies larger than MAX_BODY_BYTES."""

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413, content={"detail": "Payload too large"}
            )
        return await call_next(request)


app.add_middleware(PayloadSizeLimitMiddleware)

# Global game engine (single game per server instance)
_engine: GameEngine | None = None
# Connected WebSocket clients: player_id → WebSocket
_ws_clients: dict[str, WebSocket] = {}
# Token → player_id lookup
_token_map: dict[str, str] = {}
# Disconnect timestamps: player_id → time.time() of disconnect
_disconnect_times: dict[str, float] = {}
# Rate limiting: player_id → list of action timestamps
_action_timestamps: dict[str, list[float]] = {}

HEARTBEAT_INTERVAL = 15  # seconds
HEARTBEAT_TIMEOUT = 30  # close if no pong in this time
DISCONNECT_TOLERANCE = 60  # keep player state for 60s after disconnect
RATE_LIMIT_WINDOW = 1.0  # 1 second window
RATE_LIMIT_MAX_ACTIONS = 10  # max actions per window (for /game/action)
RATE_LIMIT_MAX_DEFAULT = 5  # max requests per window (for other endpoints)

import re
_VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9 _-]{1,20}$')
_UUID4_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$', re.I)

_ACTION_VALIDATORS: dict[ActionType, type] = {
    ActionType.BUILD: BuildAction,
    ActionType.UPGRADE: UpgradeAction,
    ActionType.ALLOCATE_WORKERS: AllocateWorkersAction,
    ActionType.TRADE_BUY: TradeBuyAction,
    ActionType.TRADE_SELL: TradeSellAction,
    ActionType.DEMOLISH: DemolishAction,
    ActionType.REPAIR: RepairAction,
}


def get_engine() -> GameEngine:
    global _engine
    if _engine is None:
        _engine = GameEngine()
        _engine.set_broadcast(_broadcast_event, _broadcast_to_player)
        # Persistence is initialized asynchronously in startup_event
    return _engine


async def _init_persistence(engine: GameEngine) -> None:
    """Initialize persistence layer for the engine."""
    from terminus.server.persistence import StatePersistence
    persist = StatePersistence(engine.state.game_id)
    await persist.init_db()
    engine._persist = persist


async def _broadcast_event(event: str, data: dict[str, Any]) -> None:
    """Broadcast a WebSocket event to all connected clients."""
    message = {"event": event, "data": data}
    disconnected = []
    for player_id, ws in _ws_clients.items():
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(player_id)
    for pid in disconnected:
        _ws_clients.pop(pid, None)


async def _broadcast_to_player(player_id: str, event: str, data: dict[str, Any]) -> None:
    """Send a WebSocket event to a specific player."""
    ws = _ws_clients.get(player_id)
    if ws:
        try:
            await ws.send_json({"event": event, "data": data})
        except Exception:
            _ws_clients.pop(player_id, None)


def _auth_player(token: str | None) -> str:
    """Validate auth token, return player_id."""
    if not token:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
    token = token.strip()
    if not _UUID4_RE.match(token):
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
    if token not in _token_map:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")
    return _token_map[token]


def _check_rate_limit(player_id: str, max_per_window: int = RATE_LIMIT_MAX_ACTIONS) -> None:
    """Reject if player exceeds rate limit."""
    now = time.time()
    timestamps = _action_timestamps.setdefault(player_id, [])
    # Prune old timestamps outside window
    cutoff = now - RATE_LIMIT_WINDOW
    _action_timestamps[player_id] = [t for t in timestamps if t > cutoff]
    if len(_action_timestamps[player_id]) >= max_per_window:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _action_timestamps[player_id].append(now)


def _validate_name(name: str) -> str:
    """Validate and sanitize a player name."""
    name = name.strip()[:20]
    if not name:
        raise HTTPException(400, "Player name required")
    if not _VALID_NAME_RE.match(name):
        raise HTTPException(400, "Player name must be 1-20 alphanumeric characters, spaces, hyphens, or underscores")
    return name


# ─── REST Endpoints ──────────────────────────────────────────────────────────


@app.post("/game/create", response_model=CreateGameResponse)
async def create_game(req: CreateGameRequest):
    global _engine
    name = _validate_name(req.player_name)

    _engine = GameEngine(settings=req.settings)
    _engine.set_broadcast(_broadcast_event, _broadcast_to_player)
    await _init_persistence(_engine)

    player = Player(name=name, is_host=True)
    _engine.add_player(player)
    _token_map[player.token] = player.player_id

    return CreateGameResponse(
        game_id=_engine.state.game_id,
        player_id=player.player_id,
        token=player.token,
        host=True,
    )


@app.post("/game/join", response_model=JoinGameResponse)
async def join_game(req: JoinGameRequest):
    engine = get_engine()
    name = _validate_name(req.player_name)

    player = Player(name=name)
    try:
        engine.add_player(player)
    except ValueError as e:
        raise HTTPException(409, str(e))

    _token_map[player.token] = player.player_id
    await _broadcast_event("player_joined", {
        "player_name": player.name,
        "player_count": len(engine.state.players),
    })

    return JoinGameResponse(
        game_id=engine.state.game_id,
        player_id=player.player_id,
        token=player.token,
    )


@app.get("/game/state")
async def get_state(x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    _check_rate_limit(player_id, RATE_LIMIT_MAX_DEFAULT)
    engine = get_engine()
    return engine.get_player_state(player_id)


@app.post("/game/ready")
async def toggle_ready(x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    engine = get_engine()
    if engine.state.phase != GamePhase.LOBBY:
        raise HTTPException(400, "Can only toggle ready in lobby phase")
    player = engine.state.players.get(player_id)
    if not player:
        raise HTTPException(404, "Player not found")
    engine.set_ready(player_id, not player.ready)
    await _broadcast_event("player_ready", {"player_id": player_id, "ready": player.ready})
    return {"ready": player.ready}


@app.post("/game/start")
async def start_game(x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    engine = get_engine()
    player = engine.state.players.get(player_id)
    if not player or not player.is_host:
        raise HTTPException(403, "Only the host can start the game")
    # Require at least one player is ready
    if not any(p.ready for p in engine.state.players.values()):
        raise HTTPException(400, "At least one player must be ready")
    try:
        await engine.start_game(player_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "game_started", "phase": "setup", "setup_duration_seconds": SETUP_PHASE_SECONDS}


@app.post("/game/setup")
async def submit_setup(req: SetupRequest, x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    engine = get_engine()
    # Guard against resubmission
    player = engine.state.players.get(player_id)
    if player and player.colony is not None:
        raise HTTPException(400, "Setup already submitted")
    try:
        await engine.submit_setup(player_id, req.location, req.specialization)
        await engine.check_setup_complete()
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"status": "confirmed", "location": req.location.value, "specialization": req.specialization.value}


@app.post("/game/action")
async def submit_action(req: GameActionRequest, x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    _check_rate_limit(player_id, RATE_LIMIT_MAX_ACTIONS)
    # Validate payload against action-specific Pydantic model
    validator = _ACTION_VALIDATORS.get(req.action_type)
    if validator:
        try:
            validated = validator(**req.payload)
            payload = validated.model_dump(exclude={"action_type"})
        except Exception as e:
            raise HTTPException(400, f"Invalid payload for {req.action_type.value}: {e}")
    else:
        payload = req.payload
    engine = get_engine()
    try:
        result = await engine.handle_action(player_id, req.action_type, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@app.get("/game/market")
async def get_market(x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    _check_rate_limit(player_id, RATE_LIMIT_MAX_DEFAULT)
    engine = get_engine()
    if engine.state.phase not in (GamePhase.PLAYING, GamePhase.CATASTROPHE):
        raise HTTPException(400, "Market only available during gameplay")
    market = engine.state.market.model_dump()
    # Add player-specific sell prices (with trade spec discount)
    player = engine.state.players.get(player_id)
    if player and player.colony:
        from terminus.config import MARKET_SELL_SPREAD, TRADE_SPEC_BUY_DISCOUNT
        sell_prices = {}
        for resource, price in engine.state.market.prices.items():
            sell_price = price * MARKET_SELL_SPREAD
            if player.colony.specialization and player.colony.specialization.value == "trade":
                sell_price *= (1 / TRADE_SPEC_BUY_DISCOUNT)  # Better sell rate for traders
            sell_prices[resource] = round(sell_price, 2)
        market["sell_prices"] = sell_prices
    return market


@app.get("/game/leaderboard")
async def get_leaderboard(x_token: str | None = Header(None)):
    player_id = _auth_player(x_token)
    _check_rate_limit(player_id, RATE_LIMIT_MAX_DEFAULT)
    engine = get_engine()
    scores = engine._calculate_scores()
    # Add rank and is_you fields
    for i, entry in enumerate(scores):
        entry["rank"] = i + 1
        entry["is_you"] = entry["player_id"] == player_id
    return scores


@app.get("/game/action-log")
async def get_action_log(x_token: str | None = Header(None)):
    """Return the full action log for the current game."""
    _auth_player(x_token)
    engine = get_engine()
    if engine._persist:
        return await engine._persist.get_action_log()
    return []


@app.post("/game/settings")
async def update_settings(settings: dict, x_token: str | None = Header(None)):
    """Host-only: update game settings before game starts."""
    player_id = _auth_player(x_token)
    engine = get_engine()
    player = engine.state.players.get(player_id)
    if not player or not player.is_host:
        raise HTTPException(403, "Only the host can change settings")
    if engine.state.phase != GamePhase.LOBBY:
        raise HTTPException(400, "Settings can only be changed in lobby")

    allowed = {"preset", "num_catastrophes", "catastrophe_interval_seconds", "max_players"}
    # Type + range validation
    _settings_validators = {
        "preset": (str, lambda v: v in ("quick", "standard", "marathon")),
        "num_catastrophes": (int, lambda v: 1 <= v <= 20),
        "catastrophe_interval_seconds": (int, lambda v: 30 <= v <= 3600),
        "max_players": (int, lambda v: 2 <= v <= 250),
    }
    for key, val in settings.items():
        if key not in allowed:
            continue
        validator = _settings_validators.get(key)
        if validator:
            expected_type, range_check = validator
            if not isinstance(val, expected_type):
                raise HTTPException(422, f"Invalid type for {key}: expected {expected_type.__name__}")
            if not range_check(val):
                raise HTTPException(422, f"Value out of range for {key}")
        if hasattr(engine.state.settings, key):
            setattr(engine.state.settings, key, val)
    return {"status": "updated", "settings": engine.state.settings.model_dump()}


@app.get("/game/lobby")
async def get_lobby():
    """Public endpoint — no auth needed. Shows player list for joining."""
    engine = get_engine()
    players = [
        {"name": p.name, "ready": p.ready, "is_host": p.is_host, "player_id": p.player_id}
        for p in engine.state.players.values()
    ]
    return {
        "game_id": engine.state.game_id,
        "phase": engine.state.phase.value,
        "players": players,
        "player_count": len(players),
        "max_players": engine.state.settings.max_players,
        "settings": engine.state.settings.model_dump(),
    }


@app.post("/game/leave")
async def leave_game(x_token: str | None = Header(None)):
    """Authenticated: leave the game. In lobby: fully removed. In game: soft-disconnect."""
    player_id = _auth_player(x_token)
    engine = get_engine()
    result = engine.remove_player(player_id)
    if result is None:
        raise HTTPException(404, "Player not found")
    # Clean up WS client and token
    _ws_clients.pop(player_id, None)
    _disconnect_times.pop(player_id, None)
    # Remove token mapping
    token_to_remove = None
    for tok, pid in _token_map.items():
        if pid == player_id:
            token_to_remove = tok
            break
    if token_to_remove:
        _token_map.pop(token_to_remove, None)
    # Broadcast player_left
    await _broadcast_event("player_left", result)
    return {"status": "left", **result}


# ─── WebSocket ───────────────────────────────────────────────────────────────


@app.websocket("/game/ws")
async def websocket_endpoint(ws: WebSocket, token: str | None = None):
    if not token or token not in _token_map:
        await ws.close(code=4001, reason="Unauthorized")
        return

    player_id = _token_map[token]
    await ws.accept()
    _ws_clients[player_id] = ws

    engine = get_engine()
    player = engine.state.players.get(player_id)
    if player:
        player.connected = True

    # Clear disconnect timer if reconnecting
    was_reconnect = player_id in _disconnect_times
    _disconnect_times.pop(player_id, None)

    logger.info(f"WebSocket connected: {player_id}")

    # Send full state snapshot on reconnect so client isn't stale
    if was_reconnect and engine and player_id:
        try:
            state = engine.get_player_state(player_id)
            await ws.send_json({"event": "state_sync", "data": state})
        except Exception:
            pass

    # Track last pong time for heartbeat
    last_pong = time.time()

    async def _heartbeat_loop():
        """Send pings every HEARTBEAT_INTERVAL, close if no pong received."""
        nonlocal last_pong
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                await ws.send_json({"event": "ping", "data": {}})
                # Check if client responded to previous ping
                if time.time() - last_pong > HEARTBEAT_TIMEOUT:
                    logger.warning(f"Heartbeat timeout for {player_id}")
                    await ws.close(code=4002, reason="Heartbeat timeout")
                    return
            except Exception:
                return

    heartbeat_task = asyncio.create_task(_heartbeat_loop())

    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_BODY_BYTES:
                await ws.send_json({"event": "error", "data": {"detail": "Message too large"}})
                continue
            import json as _json
            data = _json.loads(raw)
            msg_type = data.get("type") or data.get("event", "")
            if msg_type == "ping":
                await ws.send_json({"event": "pong", "data": {}})
            elif msg_type == "pong":
                last_pong = time.time()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {player_id}")
    except Exception as e:
        logger.error(f"WebSocket error for {player_id}: {e}")
    finally:
        heartbeat_task.cancel()
        _ws_clients.pop(player_id, None)
        if player:
            player.connected = False
        # Start disconnect tolerance — don't remove player immediately
        _disconnect_times[player_id] = time.time()
        engine = get_engine() if _engine else None
        player_count = len(engine.state.players) if engine else 0
        await _broadcast_event("player_left", {
            "player_id": player_id,
            "name": player.name if player else "",
            "player_count": player_count,
        })


async def _cleanup_stale_players() -> None:
    """Periodically remove players disconnected longer than DISCONNECT_TOLERANCE."""
    while True:
        await asyncio.sleep(15)
        now = time.time()
        expired = [
            pid for pid, dc_time in _disconnect_times.items()
            if now - dc_time > DISCONNECT_TOLERANCE
        ]
        for pid in expired:
            _disconnect_times.pop(pid, None)
            _action_timestamps.pop(pid, None)
            engine = get_engine() if _engine else None
            if engine:
                player = engine.state.players.get(pid)
                if player and not player.connected:
                    logger.info(f"Removing stale player: {pid} ({player.name})")
                    engine.remove_player(pid)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(_cleanup_stale_players())


@app.on_event("shutdown")
async def shutdown_event():
    """Broadcast server_shutdown to all connected WS clients, then stop engine."""
    logger.info("Server shutting down — notifying clients")
    for player_id, ws in list(_ws_clients.items()):
        try:
            await ws.send_json({"event": "server_shutdown", "data": {"reason": "Server shutting down"}})
            await ws.close(code=1001, reason="Server shutdown")
        except Exception:
            pass
    _ws_clients.clear()
    if _engine:
        try:
            await _engine.stop()
        except Exception:
            logger.warning("Error stopping engine", exc_info=True)


# ─── Health Check ────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "game_active": _engine is not None}


# ─── Admin / Dev Mode Endpoints ──────────────────────────────────────────────

import os

_DEV_MODE = os.environ.get("TERMINUS_DEV_MODE", "").lower() in ("1", "true", "yes")


def _require_dev_mode(token: str | None = None):
    """Check dev mode access: env var OR host-enabled dev_mode with host token."""
    if _DEV_MODE:
        return
    # Check if game has dev_mode enabled by host
    engine = get_engine()
    if engine.state.dev_mode and token:
        token = token.strip()
        player_id = _token_map.get(token)
        if player_id:
            player = engine.state.players.get(player_id)
            if player and player.is_host:
                return
    raise HTTPException(403, "Dev mode not enabled")


@app.post("/game/dev-mode")
async def toggle_dev_mode(request: Request):
    """Host-only: enable/disable dev mode for this game."""
    token = request.headers.get("x-token")
    player_id = _auth_player(token)
    engine = get_engine()
    player = engine.state.players.get(player_id)
    if not player or not player.is_host:
        raise HTTPException(403, "Only the host can toggle dev mode")
    engine.state.dev_mode = not engine.state.dev_mode
    return {"status": "ok", "dev_mode": engine.state.dev_mode}


@app.get("/admin/state")
async def admin_get_state(request: Request):
    """Full game state dump — all players, all colonies."""
    _require_dev_mode(request.headers.get("x-token"))
    engine = get_engine()
    players = {}
    for pid, player in engine.state.players.items():
        colony_data = player.colony.model_dump() if player.colony else None
        rates = engine.get_production_rates(player.colony) if player.colony else None
        players[pid] = {
            "name": player.name,
            "connected": player.connected,
            "is_host": player.is_host,
            "colony": colony_data,
            "production_rates": rates,
        }
    schedule_info = []
    for event in engine.state.catastrophe_schedule:
        schedule_info.append({
            "catastrophe_id": event.catastrophe_id,
            "scheduled_time": event.scheduled_time,
            "resolved": event.resolved,
        })
    return {
        "game_id": engine.state.game_id,
        "phase": engine.state.phase.value,
        "elapsed_ticks": engine.state.elapsed_ticks,
        "game_start_time": engine.state.game_start_time,
        "players": players,
        "catastrophe_schedule": schedule_info,
        "current_catastrophe_index": engine.state.current_catastrophe_index,
        "market": engine.state.market.model_dump(),
    }


@app.post("/admin/set-resources")
async def admin_set_resources(request: Request, data: dict):
    """Set resources for a specific player. Body: {player_id, food, materials, knowledge, gold}"""
    _require_dev_mode(request.headers.get("x-token"))
    engine = get_engine()
    player_id = data.get("player_id")
    if not player_id:
        # Use first player if not specified
        player_id = next(iter(engine.state.players), None)
    player = engine.state.players.get(player_id)
    if not player or not player.colony:
        raise HTTPException(404, "Player/colony not found")
    colony = player.colony
    if "food" in data:
        colony.resources.food = float(data["food"])
    if "materials" in data:
        colony.resources.materials = float(data["materials"])
    if "knowledge" in data:
        colony.resources.knowledge = float(data["knowledge"])
    if "gold" in data:
        colony.resources.gold = float(data["gold"])
    if "population" in data:
        colony.population = int(data["population"])
    if "morale" in data:
        colony.morale = float(data["morale"])
    return {"status": "ok", "resources": colony.resources.model_dump()}


@app.post("/admin/set-catastrophe-speed")
async def admin_set_catastrophe_speed(request: Request, data: dict):
    """Adjust catastrophe timing. Body: {multiplier: float} — 0.5 = faster, 2.0 = slower."""
    _require_dev_mode(request.headers.get("x-token"))
    engine = get_engine()
    multiplier = float(data.get("multiplier", 1.0))
    if multiplier <= 0:
        raise HTTPException(400, "Multiplier must be positive")
    # Scale remaining scheduled catastrophes
    now_elapsed = time.time() - (engine.state.game_start_time or time.time())
    for i, event in enumerate(engine.state.catastrophe_schedule):
        if not event.resolved and i >= engine.state.current_catastrophe_index:
            remaining = event.scheduled_time - now_elapsed
            event.scheduled_time = now_elapsed + remaining * multiplier
    return {"status": "ok", "multiplier": multiplier}


@app.post("/admin/trigger-catastrophe")
async def admin_trigger_catastrophe(request: Request):
    """Force the next catastrophe to happen immediately."""
    _require_dev_mode(request.headers.get("x-token"))
    engine = get_engine()
    idx = engine.state.current_catastrophe_index
    if idx >= len(engine.state.catastrophe_schedule):
        raise HTTPException(400, "No more catastrophes scheduled")
    # Set the next catastrophe to happen now
    elapsed = time.time() - (engine.state.game_start_time or time.time())
    engine.state.catastrophe_schedule[idx].scheduled_time = elapsed - 1
    return {"status": "ok", "triggered_index": idx}


@app.post("/admin/complete-building")
async def admin_complete_building(request: Request, data: dict):
    """Instantly complete all buildings under construction. Body: {player_id?}"""
    _require_dev_mode(request.headers.get("x-token"))
    engine = get_engine()
    player_id = data.get("player_id") or next(iter(engine.state.players), None)
    player = engine.state.players.get(player_id)
    if not player or not player.colony:
        raise HTTPException(404, "Player/colony not found")
    completed = []
    for building in player.colony.buildings:
        if building.under_construction:
            building.under_construction = False
            building.construction_progress = building.construction_target
            building.health = building.max_health
            player.colony.buildings_built += 1
            completed.append(building.building_type)
    engine._update_colony_capacity(player.colony)
    return {"status": "ok", "completed": completed}
