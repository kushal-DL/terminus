# Epic 3: Server API & Networking

> **Priority**: P0 (REST+WS), P1 (Cloudflared)  
> **Status**: 11 ✅ Done, 16 🔨 Scaffolded, 1 ⬜ TODO (28 total)  
> **Owner**: Core team  
> **Sprint**: 1 (basic), 2-4 (hardening)

---

## Epic Description

The server exposes game functionality via a REST API for request/response operations and WebSocket for real-time event streaming. Authentication uses opaque tokens issued at join time. The server optionally exposes itself to the internet via cloudflared tunnel for public multiplayer.

**Architecture**:
- **FastAPI** application with uvicorn ASGI server
- Single game instance per server process (no multi-game routing)
- REST for actions (create, join, ready, start, setup, action, market, leaderboard)
- WebSocket for real-time events (phase changes, catastrophes, state updates)
- Auth: `x-token` header with player's UUID token (issued at join)

---

## Feature 3.1 — REST API

### Overview
The REST API handles all discrete player operations — joining, readying, submitting actions. Each endpoint validates auth, checks game phase, and delegates to the engine.

---

### Story 3.1.1 — POST /game/create

**As a** host player  
**I want** to create a new game session  
**So that** other players can join my game

**Status**: ✅ Done  
**Notes**: Name validation (regex), host field in response

**Acceptance Criteria**:
- [ ] Request body: `{player_name: str, settings?: GameSettings}`
- [ ] Creates new GameEngine instance with given settings (or defaults)
- [ ] Adds host as first player with `is_host=True`
- [ ] Returns: `{game_id: str, player_id: str, token: str, host: true}`
- [ ] Game enters LOBBY phase
- [ ] Token must be stored by client for all subsequent requests
- [ ] Player name validated: 1-20 chars, alphanumeric + spaces, no offensive content (basic)

---

### Story 3.1.2 — POST /game/join

**As a** player  
**I want** to join an existing game  
**So that** I can play with other people

**Status**: ✅ Done  
**Notes**: Duplicate name check (case-insensitive), 409 on conflict

**Acceptance Criteria**:
- [ ] Request body: `{player_name: str}`
- [ ] Validates: game exists, game in LOBBY phase (or late_join enabled), not at max capacity
- [ ] Adds player with `is_host=False`
- [ ] Returns: `{game_id: str, player_id: str, token: str, host: false}`
- [ ] Broadcasts `player_joined` WebSocket event to all connected clients
- [ ] Player name must be unique (case-insensitive) — returns 409 if duplicate
- [ ] Returns 404 if no game exists, 403 if game not accepting joins

---

### Story 3.1.3 — GET /game/state

**As a** player  
**I want** to poll the current game state filtered to my perspective  
**So that** my client can display up-to-date information

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Requires auth (x-token header)
- [ ] Returns full state for requesting player's colony
- [ ] Does NOT expose other players' detailed colony state (only: name, score, population, connected status)
- [ ] Includes: current phase, elapsed ticks, own colony (resources, buildings, workers, etc.), next catastrophe timing, catastrophes remaining, market prices
- [ ] Returns 401 if token invalid
- [ ] Response is JSON-serializable `GameState` (filtered)

---

### Story 3.1.4 — POST /game/ready

**As a** player  
**I want** to toggle my ready status in the lobby  
**So that** the host knows when everyone is prepared to start

**Status**: ✅ Done  
**Notes**: Phase guard: LOBBY only

**Acceptance Criteria**:
- [ ] Requires auth
- [ ] Only valid in LOBBY phase (returns 400 otherwise)
- [ ] Toggles player's `ready` field (True ↔ False)
- [ ] Broadcasts `player_ready_changed` event via WebSocket
- [ ] Returns: `{ready: bool}` (new state)

---

### Story 3.1.5 — POST /game/start

**As a** host  
**I want** to start the game when players are ready  
**So that** the game begins when the group is prepared

**Status**: ✅ Done  
**Notes**: 403 for non-host, requires ≥1 ready, includes setup_duration_seconds

**Acceptance Criteria**:
- [ ] Requires auth + host verification
- [ ] Only valid in LOBBY phase
- [ ] Requires at least 1 player ready (host counts if ready)
- [ ] Transitions game to SETUP phase
- [ ] Broadcasts `game_phase_changed` event with phase="setup" and `setup_duration_seconds=90`
- [ ] Returns: `{phase: "setup", setup_duration_seconds: 90}`
- [ ] Non-host calling this: returns 403 "Only host can start the game"
- [ ] No players ready: returns 400 "At least one player must be ready"

---

### Story 3.1.6 — POST /game/setup

**As a** player  
**I want** to submit my location and specialization choices  
**So that** my colony is configured for the game

**Status**: ✅ Done  
**Notes**: Resubmit guard, returns {status, location, specialization}

**Acceptance Criteria**:
- [ ] Requires auth
- [ ] Only valid in SETUP phase (returns 400 otherwise)
- [ ] Request body: `{location: str, specialization: str}`
- [ ] Validates location is valid enum value (coast/mountain/plains/forest/desert)
- [ ] Validates specialization is valid enum value (military/trade/science/agriculture)
- [ ] Player can only submit once (second submission returns 400 "Already submitted")
- [ ] Returns: `{status: "confirmed", location: str, specialization: str}`
- [ ] When all players have submitted: engine initiates transition to PLAYING

---

### Story 3.1.7 — POST /game/action

**As a** player  
**I want** to submit game actions (build, trade, allocate workers, etc.)  
**So that** I can manage my settlement during gameplay

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Requires auth
- [ ] Only valid in PLAYING phase (returns 400 "Actions not allowed in {phase} phase")
- [ ] Request body: `{action_type: str, params: dict}`
- [ ] Supported action types: `build`, `upgrade`, `allocate_workers`, `trade_buy`, `trade_sell`, `demolish`, `repair`
- [ ] Each action type validated per its specific rules (see Epic 2)
- [ ] On success: returns `{status: str, ...action-specific results}`
- [ ] On failure: returns 400 with error message (insufficient resources, invalid building, etc.)
- [ ] Action is applied to engine state immediately (no queuing)

---

### Story 3.1.8 — GET /game/market

**As a** player  
**I want** to see current market prices and available stock  
**So that** I can make informed trading decisions

**Status**: ✅ Done  
**Notes**: Phase check (PLAYING/CATASTROPHE), player-specific sell_prices with trade discount

**Acceptance Criteria**:
- [ ] Requires auth
- [ ] Returns: `{prices: {food: float, materials: float, knowledge: float}, stock: {food: int, materials: int, knowledge: int}, sell_prices: {...}}`
- [ ] Sell prices calculated as `buy_price × (1 - spread)` with player-specific discounts applied
- [ ] Stock reflects remaining available units this round
- [ ] Available in PLAYING and CATASTROPHE phases

---

### Story 3.1.9 — GET /game/leaderboard

**As a** player  
**I want** to see current rankings  
**So that** I know my competitive position

**Status**: ✅ Done  
**Notes**: Adds rank + is_you fields per entry

**Acceptance Criteria**:
- [ ] Requires auth
- [ ] Returns: `{rankings: [{rank: int, player_name: str, score: float, population: int, is_you: bool}]}`
- [ ] During PLAYING: live scores (updated each tick)
- [ ] During SCORING/FINISHED: final scores with achievements
- [ ] `is_you` flag helps client highlight the requesting player's row
- [ ] Available in all phases (lobby shows empty, setup shows zeros)

---

### Story 3.1.10 — Auth Middleware

**As a** developer  
**I want** consistent auth validation across all protected endpoints  
**So that** auth logic isn't duplicated and security is uniform

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] All endpoints except `/game/create`, `/game/join`, `/health` require `x-token` header
- [ ] Token validated against player list: must match exactly one player's token
- [ ] Invalid/missing token: returns 401 `{"detail": "Invalid or missing authentication token"}`
- [ ] Authenticated player is resolved and passed to endpoint handler
- [ ] Disconnected players' tokens remain valid for reconnection window (60s)

---

### Story 3.1.11 — Rate Limiting

**As a** developer  
**I want** per-player rate limiting to prevent spam  
**So that** one client can't overwhelm the server with rapid-fire requests

**Status**: ✅ Done  
**Notes**: Per-endpoint: 10/sec on /action, 5/sec on GET routes

**Acceptance Criteria**:
- [ ] Maximum 10 actions per second per player (on `/game/action` endpoint)
- [ ] Maximum 5 requests per second on other endpoints per player
- [ ] Exceeded rate: returns 429 `{"detail": "Rate limit exceeded. Max 10 actions/second."}`
- [ ] Rate limit tracked in-memory (dict of player_id → timestamps)
- [ ] Does not affect WebSocket events (those are server-push, not client-requested)
- [ ] State polling (`/game/state`) has separate, more generous limit (10/sec)

---

## Feature 3.2 — WebSocket Events

### Overview
Real-time server→client event stream for game events that players need immediately — catastrophe warnings, phase changes, state updates. The client maintains a persistent WebSocket connection after joining.

---

### Story 3.2.1 — WebSocket Connection

**As a** player  
**I want** a persistent real-time connection to the game server  
**So that** I receive events instantly without polling

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Endpoint: `WS /game/ws?token={player_token}`
- [ ] Token validated on connection (same as REST auth)
- [ ] Invalid token: connection rejected with 4001 close code
- [ ] On connect: player marked as `connected=True`
- [ ] On disconnect: player marked as `connected=False`, broadcast `player_left` event
- [ ] Connection added to broadcast list for all subsequent events
- [ ] Multiple connections from same token: newest wins, old one closed
- [ ] Event format: `{"event": "event_name", "data": {...}}`

---

### Story 3.2.2 — player_joined Event

**Status**: ✅ Done  
**Notes**: Payload: player_name + player_count per spec

**Acceptance Criteria**:
- [ ] Broadcast when: new player joins via POST /game/join
- [ ] Payload: `{"event": "player_joined", "data": {"player_name": str, "player_count": int}}`
- [ ] Sent to all connected WebSocket clients
- [ ] Not sent to the joining player (they already know they joined)

---

### Story 3.2.3 — player_left Event

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Broadcast when: player's WebSocket disconnects
- [ ] Payload: `{"event": "player_left", "data": {"player_name": str, "player_count": int}}`
- [ ] Player is marked disconnected but NOT removed (can reconnect)
- [ ] Sent to all remaining connected clients

---

### Story 3.2.4 — game_phase_changed Event

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Broadcast when: game transitions between phases
- [ ] Payload: `{"event": "game_phase_changed", "data": {"phase": str, "phase_data": dict}}`
- [ ] Phase data varies:
  - SETUP: `{setup_duration_seconds: 90}`
  - PLAYING: `{tick_interval: 2.0, next_catastrophe_tick: int}`
  - CATASTROPHE: `{catastrophe_name: str, catastrophe_id: str}`
  - SCORING: `{}`
  - FINISHED: `{}`
- [ ] Sent to all connected clients

---

### Story 3.2.5 — catastrophe_warning Event

**Status**: ✅ Done  
**Notes**: Per-player via _emit_to_player; watchtower hints: L1=category, L2=type, L3=severity+hint_text

**Acceptance Criteria**:
- [ ] Sent: 30 seconds before catastrophe triggers
- [ ] Payload: `{"event": "catastrophe_warning", "data": {"seconds_until": 30, "hint": str|null}}`
- [ ] `hint` field: null if player has no Watchtower, otherwise category/type/timing per Watchtower level
- [ ] Sent individually per player (different hints based on their Watchtower)
- [ ] Triggers client-side warning display and timer acceleration

---

### Story 3.2.6 — catastrophe_started Event

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Broadcast when: catastrophe phase begins
- [ ] Payload: `{"event": "catastrophe_started", "data": {"name": str, "description": str, "flavor_text": str, "category": str}}`
- [ ] Clients switch to catastrophe display screen
- [ ] Flavor text may be location-specific (per Story 2.5.7)

---

### Story 3.2.7 — catastrophe_results Event

**Status**: ✅ Done  
**Notes**: Individualized per-player via _emit_to_player; includes avg_population_lost, avg_food_lost

**Acceptance Criteria**:
- [ ] Sent individually per player (each gets their own results)
- [ ] Payload: `{"event": "catastrophe_results", "data": {"population_lost": int, "resources_lost": dict, "buildings_damaged": list, "mitigation_details": list, "average_pop_lost": float}}`
- [ ] Sent after damage calculation completes (~2-3s after catastrophe_started)
- [ ] Client displays progressive damage reveal animation

---

### Story 3.2.8 — state_update Event (Tick Broadcast)

**Status**: ✅ Done  
**Notes**: Sends per-player colony state + market_prices via _emit_to_player

**Acceptance Criteria**:
- [ ] Sent: every server tick (2 seconds) during PLAYING phase
- [ ] Payload: `{"event": "state_update", "data": {"tick": int, "colony": {resources, population, morale, buildings, workers}, "next_catastrophe_in": float}}`
- [ ] Contains only the requesting player's colony state (not other players')
- [ ] Sent individually per player (each gets their own colony data)
- [ ] Client uses this to update display without polling
- [ ] Includes delta indicators: `resource_deltas: {food: +2.3, materials: +1.1, ...}`

---

### Story 3.2.9 — game_over Event

**Status**: 🔨 Scaffolded  
**Gap**: Missing achievements/stats structure in game_over payload

**Acceptance Criteria**:
- [ ] Broadcast when: game enters FINISHED phase
- [ ] Payload: `{"event": "game_over", "data": {"rankings": [...], "achievements": {...}, "stats": {...}}}`
- [ ] Rankings include all players with final scores
- [ ] Client switches to final leaderboard screen
- [ ] Connection remains open for viewing results

---

### Story 3.2.10 — market_update Event

**Status**: 🔨 Scaffolded  
**Notes**: Server sends prices+stock; client handles+caches; still missing price_changes delta

**Acceptance Criteria**:
- [ ] Broadcast when: market prices change (after catastrophe, new round)
- [ ] Payload: `{"event": "market_update", "data": {"prices": {...}, "stock": {...}, "price_changes": {...}}}`
- [ ] `price_changes` shows delta from previous prices: `{food: +0.3, materials: -0.1, ...}`
- [ ] Client updates market display without needing to poll

---

### Story 3.2.11 — Reconnection Handling

**Status**: ✅ Done  
**Notes**: 60s tolerance + full state_sync event on WS reconnect

**Acceptance Criteria**:
- [ ] If player disconnects and reconnects within 60 seconds:
  - Token still valid
  - Colony state preserved (no reset)
  - Full state sync sent on reconnection (complete colony + game state)
  - Player marked `connected=True` again
  - Other players see `player_reconnected` event
- [ ] If player disconnects for >60 seconds:
  - Colony continues producing/consuming (auto-pilot)
  - No actions taken on their behalf
  - Can still reconnect (indefinitely) — 60s is just the "grace" window
- [ ] On reconnection: client receives all missed events? Or just current state? → Just current state (simpler)

---

### Story 3.2.12 — Connection Heartbeat

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Server sends ping every 15 seconds
- [ ] Client must respond with pong within 5 seconds
- [ ] 3 consecutive missed pongs → connection considered dead → disconnect event fired
- [ ] Prevents ghost connections consuming resources
- [ ] Heartbeat interval configurable in config

---

## Feature 3.3 — Cloudflared Integration

### Overview
Enables public internet multiplayer without port forwarding. The host can optionally start a Cloudflare Tunnel that gives a public HTTPS URL for remote players to connect to.

---

### Story 3.3.1 — Detect Cloudflared Binary

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] On `--public` flag or "Create Public Game" TUI option: check if `cloudflared` is on PATH
- [ ] Uses `shutil.which("cloudflared")` for cross-platform detection
- [ ] If not found: print install instructions, fall back to localhost-only
- [ ] If found: proceed with tunnel start

---

### Story 3.3.2 — Start Quick Tunnel

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Start command: `cloudflared tunnel --url http://localhost:{port}`
- [ ] Subprocess launched in background (non-blocking)
- [ ] Parse public URL from cloudflared stdout (regex: `https://.*\.trycloudflare\.com`)
- [ ] URL available within ~5 seconds of launch
- [ ] Store URL for display in TUI lobby screen
- [ ] Store process handle for cleanup

---

### Story 3.3.3 — Display Public URL

**Status**: 🔨 Scaffolded  
**Gap**: URL printed to stdout only, not shown in TUI lobby

**Acceptance Criteria**:
- [ ] Public URL displayed prominently in lobby screen
- [ ] Format: `Share this URL: https://random-words.trycloudflare.com`
- [ ] In TUI: shown in bordered "SHARE" box at top of lobby
- [ ] In server-only mode: printed to stdout
- [ ] Players joining use this URL as the server address

---

### Story 3.3.4 — Graceful Tunnel Shutdown

**Status**: ✅ Done

**Implementation Notes**:
- `_tunnel_proc` module-level variable stores `Popen` reference in `__main__.py`
- `_cleanup_tunnel()` function: `terminate()` → `wait(5)` → `kill()` fallback
- Registered via `atexit.register()` for normal exit
- Signal handlers for `SIGINT` and `SIGTERM` (Windows: `SIGBREAK`) call cleanup then `sys.exit()`
- Daemon thread still used for tunnel lifecycle, but process reference is accessible for cleanup

**Acceptance Criteria**:
- [ ] On game end (FINISHED phase): kill cloudflared process
- [ ] On server shutdown (Ctrl+C): kill cloudflared process
- [ ] On TUI exit: kill cloudflared process
- [ ] Use `process.terminate()` then `process.wait(timeout=5)` then `process.kill()` if needed
- [ ] No orphaned cloudflared processes left running
- [ ] Handle case where process already died

---

### Story 3.3.5 — Tunnel Failure Handling

**Status**: ⬜ TODO (basic error message only)

**Acceptance Criteria**:
- [ ] If cloudflared process exits unexpectedly: log error, notify host
- [ ] If cloudflared fails to produce URL within 15 seconds: timeout, show error
- [ ] If network is unavailable: clear message "No internet connection — game available on LAN only"
- [ ] Game continues to work on localhost regardless of tunnel state
- [ ] Retry option: host can attempt tunnel restart from TUI
