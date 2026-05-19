# Terminus — Product Backlog

> **Product**: Terminus — Multiplayer CLI Survival Strategy Game  
> **Stack**: Python 3.14 | Textual (TUI) | FastAPI + WebSocket | SQLite | Cloudflared  
> **Target**: 40-60 min games, up to 250 players, `pip install .` + `python -m terminus`  
> **Last Updated**: 2026-05-16

---

## Status Legend

| Icon | Status | Meaning |
|------|--------|---------|
| ✅ | **DONE** | Implemented, tested, working |
| 🔨 | **SCAFFOLDED** | Code exists, functional but needs polish/edge-cases/testing |
| 🚧 | **IN PROGRESS** | Currently being worked on |
| ⬜ | **TODO** | Not started |
| 🚫 | **BLOCKED** | Waiting on something else |
| 💤 | **DEFERRED** | Pushed to future sprint/version |

---

## Progress Summary

| Epic | Name | Items | Done | Scaffolded | TODO |
|------|------|-------|------|------------|------|
| 1 | Foundation & Infrastructure | 16 | 16 | 0 | 0 |
| 2 | Game Engine | 48 | **48** | 0 | 0 |
| 3 | Server API & Networking | 28 | **28** | 0 | 0 |
| 4 | TUI Client (Screens) | 52 | **52** | 0 | 0 |
| 5 | Game Balance | 12 | **12** | 0 | 0 |
| 6 | Persistence & Reliability | 9 | **9** | 0 | 0 |
| 7 | Visual Identity & Retro Overhaul | 77 | 69 | 0 | 8 |
| 8 | Testing & Quality | 14 | **14** | 0 | 0 |
| 9 | Packaging & Distribution | 9 | **9** | 0 | 0 |
| 10 | Stretch Goals | 10 | 0 | 0 | 10 |
| 11 | Developer Tools | 18 | **18** | 0 | 0 |
| 12 | LLM Benchmark Suite | 42 | 0 | 0 | 42 |
| | **TOTAL** | **335** | **275** | **0** | **60** |

---

## Epic 1: Project Foundation & Infrastructure

### 1.1 — Project Scaffolding [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 1.1.1 | `pyproject.toml` — metadata, dependencies, console script, hatch build config | Working, installs via `uv` |
| ✅ | 1.1.2 | Package directory structure with all `__init__.py` files | `colony/server/`, `client/screens/`, `client/widgets/`, `data/` |
| ✅ | 1.1.3 | `colony/__main__.py` — CLI args: `--host`, `--port`, `--public`, `--server-only`, `--verbose` | Runs TUI or server-only mode |
| ✅ | 1.1.4 | `colony/config.py` — all game constants (resources, timing, balance, market, scoring) | ~150 lines of tunable numbers |
| ✅ | 1.1.5 | Basic logging with `--verbose` flag | Using stdlib logging |

### 1.2 — Data Definitions [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 1.2.1 | `catastrophes.json` — 20 catastrophes with full definitions | Categories, severity, vulnerability matrix, mitigation |
| ✅ | 1.2.2 | `buildings.json` — 10 buildings with costs, build times, effects per level | 3 levels each, balanced costs |
| ✅ | 1.2.3 | `locations.json` — 5 locations with modifiers, starting resources, flavor text | Coast/Mountain/Plains/Forest/Desert |
| ✅ | 1.2.4 | `specializations.json` — 4 specs with bonuses | Military/Trade/Science/Agriculture |
| ✅ | 1.2.5 | `colony/data/loader.py` — JSON loader with field validation + caching | Lazy-loaded, validates required fields |

### 1.3 — Rename Refactor: Colony → Terminus [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 1.3.1 | Rename package directory `colony/` → `terminus/` | All subfolders preserved: `server/`, `client/`, `data/` |
| ✅ | 1.3.2 | Update all Python imports across every `.py` file (`from colony.` → `from terminus.`) | ~30+ files affected |
| ✅ | 1.3.3 | Update `pyproject.toml` — project name, console script (`terminus`), hatch build targets | `[project.scripts] terminus = "terminus.__main__:main"` |
| ✅ | 1.3.4 | Update `test_engine.py` imports | `from terminus.server.engine import GameEngine` etc. |
| ✅ | 1.3.5 | Update `README.md` — all Colony references → Terminus, install/run commands | `python -m terminus`, pip install instructions |
| ✅ | 1.3.6 | Update display text in all screens — class names, CLI description, labels | `ColonyApp` → `TerminusApp`, "COLONY SETUP" → "SETTLEMENT SETUP" etc. |

---

## Epic 2: Game Engine (Server-Side Core Logic)

### 2.1 — Data Models [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.1.1 | `GameState` — game_id, phase enum, players, catastrophe schedule, settings, elapsed ticks | Pydantic BaseModel |
| ✅ | 2.1.2 | `Player` — player_id, name, token, connected, ready, is_host, colony | UUID generation, auth token |
| ✅ | 2.1.3 | `Colony` — name, location, specialization, resources, buildings, workers, population, morale, score | Full colony state |
| ✅ | 2.1.4 | `Resources` — food, materials, knowledge, gold (float, ge=0) | Non-negative validated |
| ✅ | 2.1.5 | `Building` — building_type, level, health, under_construction, progress, target | Construction state tracked |
| ✅ | 2.1.6 | `CatastropheEvent` — catastrophe_id, scheduled_time, resolved, results dict | Per-player results |
| ✅ | 2.1.7 | `MarketState` — prices, stock, price_history | Tracks all market data |
| ✅ | 2.1.8 | `GameSettings` — preset, max_players, num_catastrophes, interval, allow_late_join | Preset system (quick/standard/extended) |
| ✅ | 2.1.9 | Action models — Build, Upgrade, AllocateWorkers, TradeBuy, TradeSell, Demolish, Repair | All action types defined |

### 2.2 — Game State Machine [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.2.1 | State machine: LOBBY→SETUP→PLAYING→CATASTROPHE→PLAYING→...→SCORING→FINISHED | Tested: valid + invalid transitions |
| ✅ | 2.2.2 | LOBBY phase: join, ready, host-start, leave | Name uniqueness (case-insensitive); remove_player: LOBBY=full delete+host reassign, PLAYING+=soft-disconnect; POST /game/leave endpoint |
| ✅ | 2.2.3 | SETUP phase: location+spec selection, 90s timeout, auto-assign defaults | Tested: enum validation, auto-assign, colony init |
| ✅ | 2.2.4 | PLAYING phase: accept actions, production ticks, catastrophe timer | Tested: tick loop, action validation, phase check |
| ✅ | 2.2.5 | CATASTROPHE phase: freeze actions, calc damage, broadcast results, resume | Tested: damage, mitigation, worker realloc |
| ✅ | 2.2.6 | SCORING phase: calculate scores, rank players | Tested: weighted formula, achievements, ranking |
| ✅ | 2.2.7 | Async tick loop (2s interval): production, timers, broadcasts | Drift-compensated via time.monotonic(), tested |

### 2.3 — Resource System [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.3.1 | Production calculator: base × location × spec × worker_ratio × morale × building_bonus | Spec modifiers applied; tested: agriculture/science/military bonuses verified |
| ✅ | 2.3.2 | Food consumption + starvation (pop dies at 0 food) | Tested: starvation kills pop + morale penalty |
| ✅ | 2.3.3 | Morale system: surplus bonus, starvation penalty, death penalty | Tested: clamped 0.5–1.5 |
| ✅ | 2.3.4 | Resource capacity: base + warehouse bonus | Tested: capacity caps via `_update_colony_capacity` |
| ✅ | 2.3.5 | Worker allocation: 6 roles, must sum to population | Tested: validation on action |
| ✅ | 2.3.6 | Population growth: when food > threshold + housing capacity | Working in tick loop |

### 2.4 — Building System [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.4.1 | Build action: deduct cost, start timer, track construction | Tested: cost deduction, insufficient resources |
| ✅ | 2.4.2 | Construction progress: per tick based on construction workers | Tested: completion after ticks |
| ✅ | 2.4.3 | Building effects: production bonuses via `_get_building_bonus` | Working per level from buildings.json |
| ✅ | 2.4.4 | Upgrades: level 1→2→3, escalating costs | Tested: level costs from JSON |
| ✅ | 2.4.5 | Building destruction: health → 0 removes effects | Tested: level→0 in catastrophe damage |
| ✅ | 2.4.6 | Repair action: materials → restore health | Working: REPAIR_COST_PER_HEALTH × damage |
| ✅ | 2.4.7 | Demolish: recover 50% resources | Tested: DEMOLISH_REFUND_RATIO applied |

### 2.5 — Catastrophe System [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.5.1 | Selection algorithm: category diversity + severity progression | Tested: 6 tests in test_catastrophe_selection.py |
| ✅ | 2.5.2 | Scheduling: even intervals ± 60s jitter | Tested: schedule generated on game start |
| ✅ | 2.5.3 | Damage calc: base × (1 - mitigation) × location_vulnerability | Tested: defense mitigation verified |
| ✅ | 2.5.4 | Damage application: pop loss, resource loss, building damage | Tested: workers auto-reallocated proportionally |
| ✅ | 2.5.5 | Results generation: per-player breakdown with avg comparison | Tested: avg_score, avg_population, delta_vs_avg |
| ✅ | 2.5.6 | Watchtower hints: category/type/timing by level | Wired: colony.py reads watchtower_hint from state |
| ✅ | 2.5.7 | Location-specific flavor text variations | `location_flavor` dict on all 16 catastrophes; engine sends per-player flavor based on colony location |

### 2.6 — NPC Market System [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.6.1 | Base price + ±20% fluctuation per round | Tested: MARKET_PRICE_VOLATILITY in _refresh_market |
| ✅ | 2.6.2 | Supply/demand: catastrophe-driven price shifts | Tested: PRICE_SHOCK per category in _end_catastrophe |
| ✅ | 2.6.3 | Buy action: gold → resource, trade spec discount | Tested: TRADE_SPEC_BUY_DISCOUNT verified |
| ✅ | 2.6.4 | Sell action: resource → gold with spread | Tested: MARKET_SELL_SPREAD applied |
| ✅ | 2.6.5 | Market stock limits: finite per round | Tested: stock decremented, insufficient stock error |
| ✅ | 2.6.6 | Trade history tracking | TradeRecord per buy/sell with tick/player/amount |

### 2.7 — Scoring & Leaderboard [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 2.7.1 | Final score: weighted sum formula | Tested: SCORE_WEIGHTS, formula correctness |
| ✅ | 2.7.2 | Achievement detection (8-10 achievements) | 8 achievements, _check_achievements() + _check_catastrophe_achievements() |
| ✅ | 2.7.3 | Achievement bonus points | bonus_points from JSON added in _calculate_scores() |
| ✅ | 2.7.4 | Leaderboard ranking: sort by score | Tested: descending order verified |
| ✅ | 2.7.5 | Per-round scoring snapshots | `state.score_history` populated after each catastrophe with round number + full scores |
| ✅ | 2.7.6 | Game statistics (buildings, trades, catastrophes, peak pop) | Colony tracks: buildings_built, trades_completed, total_trade_volume, catastrophes_survived, peak_population |

---

## Epic 3: Server API & Networking

### 3.1 — REST API [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 3.1.1 | `POST /game/create` | Name validation (regex), host field in response |
| ✅ | 3.1.2 | `POST /game/join` | Duplicate name check (case-insensitive), 409 on conflict |
| ✅ | 3.1.3 | `GET /game/state` — filtered per player | Auth + filtered state, hides other colonies |
| ✅ | 3.1.4 | `POST /game/ready` — toggle | Phase guard: LOBBY only |
| ✅ | 3.1.5 | `POST /game/start` — host only | 403 for non-host, requires ≥1 ready, includes setup_duration_seconds |
| ✅ | 3.1.6 | `POST /game/setup` — location + spec | Resubmit guard, returns {status, location, specialization} |
| ✅ | 3.1.7 | `POST /game/action` — build/allocate/trade/demolish/repair | All 7 action types, phase check, rate limited |
| ✅ | 3.1.8 | `GET /game/market` | Phase check (PLAYING/CATASTROPHE), player-specific sell_prices with trade discount |
| ✅ | 3.1.9 | `GET /game/leaderboard` | Adds rank + is_you fields per entry |
| ✅ | 3.1.10 | Auth middleware: x-token header validation | 401 on missing/invalid, reconnection window preserved |
| ✅ | 3.1.11 | Rate limiting: 10 actions/sec/player | Per-endpoint: 10/sec on /action, 5/sec on GET routes |

### 3.2 — WebSocket Events [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 3.2.1 | `WS /game/ws` — persistent connection with token auth | Token validated, 4001 close on invalid |
| ✅ | 3.2.2 | `player_joined` broadcast | Payload: player_name + player_count per spec |
| ✅ | 3.2.3 | `player_left` broadcast | Payload: player_id, name, player_count; lobby=full remove+new_host; playing=soft disconnect |
| ✅ | 3.2.4 | `game_phase_changed` broadcast | Emitted on SETUP, PLAYING, post-catastrophe |
| ✅ | 3.2.5 | `catastrophe_warning` (30s before) | Per-player via _emit_to_player; watchtower hints: L1=category, L2=type, L3=severity+hint_text |
| ✅ | 3.2.6 | `catastrophe_started` | Emitted with id, name, description, category |
| ✅ | 3.2.7 | `catastrophe_results` | Individualized per-player via _emit_to_player; includes avg_population_lost, avg_food_lost |
| ✅ | 3.2.8 | `state_update` (every tick) | Sends per-player colony state + market_prices via _emit_to_player |
| ✅ | 3.2.9 | `game_over` with scores + stats | Includes achievements, buildings_built, trades_completed, total_trade_volume, catastrophes_survived, peak_population |
| ✅ | 3.2.10 | `market_update` on price change | Sends prices, stock, + `price_changes` (% delta vs previous round); client handles+caches |
| ✅ | 3.2.11 | Reconnection handling (restore state within 60s) | 60s tolerance + full state_sync event on WS reconnect |
| ✅ | 3.2.12 | Heartbeat: ping/pong every 15s | Server pings 15s, timeout 30s, client pong |

### 3.3 — Cloudflared Integration [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 3.3.1 | Detect `cloudflared` on PATH | shutil.which detection, prints install instructions |
| ✅ | 3.3.2 | Start tunnel on `--public` flag | Background subprocess, parses .trycloudflare.com URL |
| ✅ | 3.3.3 | Display URL to host | Prints to stdout + TUI lobby uses tunnel URL (via `_tunnel_url` module var) when available |
| ✅ | 3.3.4 | Graceful tunnel stop on shutdown | atexit + signal handlers, terminate/wait/kill |
| ✅ | 3.3.5 | Handle tunnel start failure gracefully | try/except in TUI + server-only modes; prints "Tunnel unavailable — using LAN only" |

---

## Epic 4: TUI Client (Screens & Logic)

### 4.1 — Application Shell [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.1.1 | Textual App subclass with screen management | TerminusApp, `q` quits globally |
| ✅ | 4.1.2 | Screen navigation: push/pop with data passing | Push/pop, data via constructors, Escape back |
| ✅ | 4.1.3 | Global status bar (connection, phase, timer) | StatusBar widget, updates from WS + state refresh |
| ✅ | 4.1.4 | Notification toast system | ToastRack, 4 categories, 3s auto-dismiss, max 3 |
| ✅ | 4.1.5 | Error handling: connection loss UI, retry | App-level WS dispatcher; ConnectionLost modal with auto-retry on mount, exponential backoff (1→2→4→8→16s, cap 30s), attempt counter, button disable during retry, manual retry after 5 failures |
| ✅ | 4.1.6 | Load external `.tcss` theme file | theme.tcss (350+ lines), CSS_PATH set, no inline CSS |

### 4.2 — Main Menu Screen [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.2.1 | ASCII art title "TERMINUS" — single-width chars only, max 60 cols | Single-width FIGlet, ~50 cols, centered |
| ✅ | 4.2.2 | Menu: Create / Join / How to Play / Quit | Styled buttons, focus highlight, keyboard nav |
| ✅ | 4.2.3 | Create Game flow: name → start server → lobby | Name input, uvicorn in thread, POST /game/create |
| ✅ | 4.2.4 | Join Game flow: URL + name → connect → lobby | URL + name inputs, POST /game/join, error display |
| ✅ | 4.2.5 | How to Play screen: rules, resources, buildings | Full Markdown help with all sections |

### 4.3 — Lobby Screen [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.3.1 | Player list with ready indicators | ListView, ✓/○ ready + [HOST] badge, 2s poll |
| ✅ | 4.3.2 | Display share URL | Box-drawing bordered panel, shows local IP:port |
| ✅ | 4.3.3 | Ready toggle button | Toggles label (✓ Ready / ✗ Not Ready) + variant; syncs state from server on poll |
| ✅ | 4.3.4 | Start Game button (host only) | Conditionally rendered, sends POST /game/start |
| ✅ | 4.3.5 | Game settings display/adjust | Shows preset, catastrophe count, max players; host can adjust catastrophe count |
| ✅ | 4.3.6 | Player count: "X / 250" | Updates on each poll |

### 4.4 — Setup Screen [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.4.1 | Location selection: 5 options with descriptions | OptionList + art preview, production modifiers |
| ✅ | 4.4.2 | Specialization selection: 4 options | OptionList + art preview on highlight |
| ✅ | 4.4.3 | Countdown timer (90s) | Auto-submits on timeout, color urgency |
| ✅ | 4.4.4 | Confirm button | POST /game/setup, auto-navigates on phase change |
| ✅ | 4.4.5 | Preview panel: starting resources for combo | Live preview of production modifiers for selection |

### 4.5 — Colony Management Screen [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.5.1 | Resource display: 4 resources with current/max | ResourceBar widgets, color-coded, 2s refresh |
| ✅ | 4.5.2 | Worker allocation (view only — edit via Workers screen) | Summary on colony screen, `w` opens editor |
| ✅ | 4.5.3 | Buildings panel: type, level, health, status | Name, Lv.X, health bar, ✓/🔨 status, construction % |
| ✅ | 4.5.4 | Build menu (separate screen via `b` key) | OptionList + cost/time preview + art panel |
| ✅ | 4.5.5 | Colony stats: population, morale | Pop, morale, score, location label, specialization label all displayed |
| ✅ | 4.5.6 | Catastrophe countdown timer | CountdownTimer widget, MM:SS, CSS urgency colors |
| ✅ | 4.5.7 | Watchtower hint display | 🔭 + hint text from server state |
| ✅ | 4.5.8 | Quick action keybindings: b/w/m/l | BINDINGS in Footer, all working |
| ✅ | 4.5.9 | Construction progress bar + ETA | Progress bar + ~Xs ETA text + completion toast notification |

### 4.6 — Market Screen [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.6.1 | Price table with stock remaining | Trend arrows (▲▼─), stock counts, WS updates |
| ✅ | 4.6.2 | Buy interface: select resource + quantity | Select → quantity → Buy, success/error messages |
| ✅ | 4.6.3 | Sell interface | Same pattern as buy, end-to-end |
| ✅ | 4.6.4 | Trade history panel | DataTable: Tick/Action/Resource/Qty/Price/Total, last 10 |
| ✅ | 4.6.5 | ASCII price sparkline chart | SparklineChart widget ×4 resources, Unicode blocks, trend coloring |

### 4.7 — Catastrophe Event Screen [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.7.1 | Dramatic announcement: name + flavor text | Full-screen overlay with category ASCII art |
| ✅ | 4.7.2 | Damage animation (progressive reveal) | Staggered reveal (pop→food→mat→bld offset 3 steps each) + Enter/Space skip-to-end |
| ✅ | 4.7.3 | Survival summary | Before→after format ("Population: 50→45 (lost 5)") + avg comparison from results |
| ✅ | 4.7.4 | Mitigation display ("Hospital saved X pop") | Shows mitigated_by buildings with icons |
| ✅ | 4.7.5 | Continue button / auto-advance | Continue + Enter/Escape bindings |
| ✅ | 4.7.6 | Quick leaderboard (top 5 + your rank) | Top 5 + current player rank with ◄ marker |

### 4.8 — Leaderboard Screen [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.8.1 | Ranked DataTable: rank, name, score, pop, morale | DataTable with [1st]/[2nd]/[3rd] decorations |
| ✅ | 4.8.2 | Achievement badges | Achievements column with icons from get_achievement_by_id() |
| ✅ | 4.8.3 | Game statistics summary | Stats panel below leaderboard when is_game_over=True: buildings built, trades completed, trade volume, catastrophes survived, peak population |
| ✅ | 4.8.4 | Back / Return to Menu button | Back + Play Again + Return to Menu buttons; game-over buttons via is_game_over flag |
| ✅ | 4.8.5 | Highlight current player's row | ► name ◄ markers + summary label |

### 4.9 — Action Error Handling & Feedback [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 4.9.1 | Extract server error detail from 400 responses | `api.py` — parse `detail` field instead of raw HTTP error string |
| ✅ | 4.9.2 | Toast notifications for build/upgrade errors | Shows "Insufficient materials (need 50)" instead of "400 Bad Request" |
| ✅ | 4.9.3 | Toast notifications for trade errors | Market buy/sell: insufficient gold, insufficient stock, etc. |
| ✅ | 4.9.4 | Toast notifications for worker allocation errors | Allocation mismatch, negative values, etc. |
| ✅ | 4.9.5 | Success toasts for completed actions | Build started, upgrade started, trade completed, workers reallocated |

---

## Epic 5: Game Balance & Data Tuning [P1]

### 5.1 — Balance Framework

| Status | ID | Task |
|--------|-----|------|
| ✅ | 5.1.1 | Define measurable balance constraints (win rates per combo) |
| ✅ | 5.1.2 | Simulation runner: headless 100-game batch with heuristic AI |
| ✅ | 5.1.3 | Tune production rates (comfortable by round 2, strategic by round 3) |
| ✅ | 5.1.4 | Tune catastrophe damage (progressive 1.5× scaling) |
| ✅ | 5.1.5 | Tune building costs (first affordable in 2 min, max requires multiple rounds) |
| ✅ | 5.1.6 | Tune game timing (target 45 min for standard) |
| ✅ | 5.1.7 | Difficulty presets: Quick (30 min) / Standard (45 min) / Extended (60 min) |

### 5.2 — Catastrophe Balance

| Status | ID | Task |
|--------|-----|------|
| ✅ | 5.2.1 | Verify category distribution (5 per category) |
| ✅ | 5.2.2 | Verify severity tiers ensure progressive difficulty |
| ✅ | 5.2.3 | Validate location vulnerability matrix (3-4 vulnerabilities each) |
| ✅ | 5.2.4 | Validate mitigation mapping (every catastrophe has ≥1 counter) |
| ✅ | 5.2.5 | Test selection algorithm with all 20 location×spec combos |

---

## Epic 6: Persistence & Reliability [P1]

### 6.1 — Game State Persistence

| Status | ID | Task |
|--------|-----|------|
| ✅ | 6.1.1 | SQLite storage: serialize game state every 10s |
| ✅ | 6.1.2 | Server restart recovery: detect + offer resume |
| ✅ | 6.1.3 | Disconnect tolerance: colony persists 5 min without player |
| ✅ | 6.1.4 | Game history: full action log for replays |

### 6.2 — Error Handling & Resilience

| Status | ID | Task |
|--------|-----|------|
| ✅ | 6.2.1 | Server: graceful handling of malformed requests (fuzz-safe) |
| ✅ | 6.2.2 | Client: disconnection UI with auto-retry + backoff |
| ✅ | 6.2.3 | Load: 250 WebSocket connections < 2GB RAM |
| ✅ | 6.2.4 | Graceful shutdown: Ctrl+C saves state, notifies clients |
| ✅ | 6.2.5 | Input validation: reject oversized/invalid payloads |

---

## Epic 7: Visual Identity & Retro Overhaul [P0]

> **Goal**: Transform the game from plain-text labels into a visually rich retro terminal experience.  
> **Constraint**: All art uses **single-width ASCII characters only** — no `██` or East Asian fullwidth chars.  
> **Allowed chars**: Letters, digits, `/`, `\`, `|`, `_`, `=`, `-`, `#`, `*`, `.`, `~`, `^`, `(`, `)`, `{`, `}`, `[`, `]`, `<`, `>`, `@`, `+`, box-drawing (`─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬`)  
> **Target width**: All art ≤ 60 columns (safe for 80-col terminals with Textual panel margins)

### 7.1 — ASCII Art Assets: Title [P0]

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.1.1 | Design "TERMINUS" title art — single-width ASCII, max 60 cols, 6-8 lines tall | 7-line art + `_build_framed_art()` in main_menu.py |
| ✅ | 7.1.2 | Decorative border frame around title | Full ╔═╗ ║ ║ ╚═╝ box-drawing frame |
| ✅ | 7.1.3 | Subtitle tagline: "The Last Stand Begins Here" or similar | Centered with ═══ dividers and amber color |
| ✅ | 7.1.4 | Title screen reveal animation — typing/fade-in effect on mount | `_reveal_tick()` + `set_interval()` progressive line reveal, ~1.5s |

### 7.2 — ASCII Art Assets: Locations [P0]

> 5 artworks, each ~10-12 lines × 30-35 cols. Displayed in setup screen art panel when location is highlighted.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.2.1 | **Coast** — waves, lighthouse, harbor, ships | 11 lines × ~30 cols in art.py, used in setup |
| ✅ | 7.2.2 | **Mountain** — peaks, snow caps, cliff face, mining cave | 10 lines × ~30 cols in art.py |
| ✅ | 7.2.3 | **Plains** — open fields, windmill, wheat stalks, road | 10 lines × ~35 cols in art.py |
| ✅ | 7.2.4 | **Forest** — dense trees, wildlife, mushrooms, canopy | 10 lines × ~30 cols in art.py |
| ✅ | 7.2.5 | **Desert** — sand dunes, cactus, scorching sun, oasis | 10 lines × ~30 cols in art.py |

### 7.3 — ASCII Art Assets: Specializations [P0]

> 4 artworks, each ~6-8 lines × 20-25 cols. Displayed alongside spec selection in setup screen.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.3.1 | **Military** — crossed swords, shield, fortress tower | 8 lines × ~20 cols in art.py, used in setup |
| ✅ | 7.3.2 | **Trade** — balance scales, coin stacks, caravan wagon | 8 lines × ~20 cols in art.py |
| ✅ | 7.3.3 | **Science** — telescope, flask/beaker, gears, book | 8 lines × ~20 cols in art.py |
| ✅ | 7.3.4 | **Agriculture** — wheat sheaf, plow, barn, sun | 9 lines × ~20 cols in art.py |

### 7.4 — ASCII Art Assets: Buildings [P1]

> 10 mini-artworks, each 4-5 lines × 15-20 cols. Used in BuildingCard widget and build selection screen.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.4.1 | **Farm** — barn with silo, fenced area, crops | 4 lines × ~16 cols, keyed to "farm" |
| ✅ | 7.4.2 | **Mine** — cave entrance, pickaxe, minecart, tracks | 4 lines × ~16 cols, keyed to "mine" |
| ✅ | 7.4.3 | **Library** — building with books, open book on stand | 4 lines × ~14 cols, keyed to "lab" |
| ✅ | 7.4.4 | **Hospital** — cross symbol, building with + sign | 5 lines × ~11 cols, keyed to "hospital" |
| ✅ | 7.4.5 | **Barracks** — fort with flag, crossed weapons | 5 lines × ~14 cols, keyed to "housing" |
| ✅ | 7.4.6 | **Warehouse** — large crate/building, stacked boxes | 4 lines × ~15 cols, keyed to "warehouse" |
| ✅ | 7.4.7 | **Market** — stall with awning, goods, coins | 4 lines × ~16 cols, keyed to "market" |
| ✅ | 7.4.8 | **Watchtower** — tall narrow tower, beacon flame | 5 lines × ~10 cols, keyed to "watchtower" |
| ✅ | 7.4.9 | **Wall** — fortification segments, gate | 4 lines × ~16 cols, keyed to "wall" |
| ✅ | 7.4.10 | **Workshop** — anvil, hammer, workbench, sparks | 4 lines × ~14 cols, keyed to "school" |

### 7.5 — ASCII Art Assets: Catastrophes [P1]

> 6 category artworks, each ~8-10 lines × 35-40 cols. Displayed on catastrophe event screen.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.5.1 | **Plague/Disease** — skull, sick figures, spreading dots | 10 lines × ~30 cols in CATASTROPHE_ART |
| ✅ | 7.5.2 | **Drought/Famine** — cracked earth, dead crops, empty well | 11 lines × ~30 cols, get_catastrophe_art() |
| ✅ | 7.5.3 | **Earthquake** — collapsing structures, ground split, rubble | 10 lines × ~30 cols in art.py |
| ✅ | 7.5.4 | **Fire/Inferno** — flames, burning buildings, smoke | 10 lines × ~25 cols in art.py |
| ✅ | 7.5.5 | **Storm/Flood** — lightning bolt, waves, wind | 10 lines × ~25 cols in art.py |
| ✅ | 7.5.6 | **Raid/Invasion** — attacking figures, broken gate, arrows | 10 lines × ~30 cols in art.py |

### 7.6 — Theme & Color System [P0]

> External `.tcss` file with full retro terminal aesthetic.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.6.1 | Create `terminus/client/theme.tcss` — external Textual CSS file | 350+ lines, CSS_PATH set, no inline CSS |
| ✅ | 7.6.2 | Color palette definition — dark bg `#1a1a2e`, green primary `#00ff41`, amber `#ffb000`, red `#ff0040`, cyan `#00d4ff` | All 6 colors defined and used |
| ✅ | 7.6.3 | Panel styling — all panels use box-drawing borders, consistent padding, section headers with `═══` dividers | .panel class with border+padding |
| ✅ | 7.6.4 | Button styling — retro bordered buttons `[ Action ]`, color-coded by function | success/primary/error/warning variants, hover states |
| ✅ | 7.6.5 | Typography hierarchy — title (bold+color), subtitle (muted), body, label (dim), value (bright) | .panel-title bold+cyan, .subtitle amber, consistent |
| ✅ | 7.6.6 | Responsive layout rules — minimum 80×24, scales to 120×40+, flexible panel widths | min-width, 1fr units throughout |
| ✅ | 7.6.7 | Status-specific colors — resources: food=green, materials=amber, knowledge=cyan, gold=yellow; health: high=green, mid=yellow, low=red | Color semantics consistent |

### 7.7 — Custom Widgets [P0]

> Reusable Textual Widget subclasses in `terminus/client/widgets/`.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.7.1 | `ResourceBar` widget — horizontal fill bar `[████████░░░░] 120/500` | Color gradient, reactive, width-adaptive |
| ✅ | 7.7.2 | `BuildingCard` widget — bordered card with mini ASCII art, level pips `●●○`, health bar, status badge | Art, level pips, health bar, construction %, CSS state classes |
| ✅ | 7.7.3 | `WorkerSlider` widget — compact allocation control `[◄ 12 ►]` | Enter-for-direct-input + 300ms debounce, focus styling |
| ✅ | 7.7.4 | `CountdownTimer` widget — large block-number display `03:42` with urgency states | MM:SS, 4 CSS urgency states, reactive |
| ✅ | 7.7.5 | `NotificationToast` widget — bordered popup message with auto-dismiss | 3s auto-dismiss, queue max 3, 4 categories with icons |
| ✅ | 7.7.6 | `AsciiArtPanel` widget — reusable container that renders pre-defined ASCII art with border | Bordered container with optional title, reactive art_text |
| ✅ | 7.7.7 | `SparklineChart` widget — inline ASCII sparkline for price/score history | Unicode blocks, trend coloring, reactive data |

### 7.8 — Screen Visual Integration [P1]

> Wire art assets and widgets into existing screens.

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.8.1 | Main Menu — new TERMINUS title art, border frame, animated reveal, themed buttons | Title + frame + `_reveal_tick()` reveal animation |
| ✅ | 7.8.2 | Setup Screen — location art panel (shows artwork for highlighted location), spec art panel | 3-column layout, art updates on highlight |
| ✅ | 7.8.3 | Colony Screen — replace plain Labels with `ResourceBar` widgets, `BuildingCard` grid, `CountdownTimer` | BuildingCard grid + ResourceBar + CountdownTimer wired |
| ✅ | 7.8.4 | Build Screen — show building mini-art in selection list, color-code affordability | ✓/✗ prefix + green/red per-resource coloring |
| ✅ | 7.8.5 | Workers Screen — use `WorkerSlider` widgets for each role | WorkerSlider for all 6 roles, pool display |
| ✅ | 7.8.6 | Catastrophe Screen — show category ASCII art, progressive damage number reveal | Category art + _animate_damage() count-up + mitigation |
| ✅ | 7.8.7 | Market Screen — `SparklineChart` for price history, styled buy/sell panels with borders | SparklineChart ×4, trend arrows, auto-refresh |
| ✅ | 7.8.8 | Leaderboard Screen — styled DataTable with rank decorations, current player row highlight | [1st]/[2nd]/[3rd], ► name ◄ highlight, delta vs avg |
| ✅ | 7.8.9 | Lobby Screen — show server URL in a prominent bordered "share" box, player list with ASCII decorations | Bordered URL box, ✓/○ ready, [HOST] badge |

### 7.9 — Animations & Effects [P2]

| Status | ID | Task | Details |
|--------|-----|------|---------|
| ✅ | 7.9.1 | Title reveal — characters appear progressively (left→right per line, top→down) | Implemented as 7.1.4: `_reveal_tick()` in main_menu.py |
| ✅ | 7.9.2 | Catastrophe damage reveal — numbers count up from 0 to final value over 5s | `_animate_damage()` in catastrophe.py: staggered offsets [0,3,6,9], 15 steps |
| ✅ | 7.9.3 | Timer urgency transitions — color shift + pulse rate changes at thresholds | `_update_urgency()` toggles 4 CSS classes: normal/warning/critical/final |
| ✅ | 7.9.4 | Construction completion flash — brief highlight/border flash when building finishes | `flash_complete()` on BuildingCard: green double-border for 2s |
| ✅ | 7.9.5 | Resource depletion warning — resource bar flashes when at <10% capacity | `_toggle_depleted()` alternates `resource-depleted` CSS class every 500ms |
| ✅ | 7.9.6 | Screen transition — brief border highlight on screen push/pop | `screen-transition` CSS class on push, removed after 300ms |

### 7.10 — Quality of Life [P2]

| Status | ID | Task |
|--------|-----|------|
| ⬜ | 7.10.1 | Game speed settings: Fast / Normal / Relaxed |
| ⬜ | 7.10.2 | Pause functionality (host only) |
| ⬜ | 7.10.3 | Late join: average resources of current players |
| ⬜ | 7.10.4 | Spectator mode: read-only view |
| ⬜ | 7.10.5 | Game chat (text messages between players) |
| ⬜ | 7.10.6 | Settlement naming with validation |
| ⬜ | 7.10.7 | Advisor hints for new players |

### 7.11 — Audio & Sound Effects [P2]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 7.11.1 | Audio synthesis engine — pure Python WAV generation | `terminus/audio/synth.py` — square, sine, sawtooth, triangle, noise waveforms |
| ✅ | 7.11.2 | Audio playback abstraction — cross-platform backend detection | simpleaudio > winsound > aplay/afplay > silent fallback |
| ✅ | 7.11.3 | Sound event definitions — 10 retro 8-bit effects | build_started, build_complete, catastrophe_warning, catastrophe_hit, trade_complete, worker_allocated, turn_tick, game_start, game_over, ui_navigate |
| ✅ | 7.11.4 | Audio public API — play_sound(), toggle(), set_volume() | Settings persisted to ~/.terminus/audio.json |
| ✅ | 7.11.5 | Audio toggle keybinding — Ctrl+S to enable/disable | Shows toast notification on toggle |
| ✅ | 7.11.6 | Integrate sounds into build screen | play_sound on build/upgrade actions |
| ✅ | 7.11.7 | Integrate sounds into market screen | play_sound on buy/sell trades |
| ✅ | 7.11.8 | Integrate sounds into colony screen | catastrophe_warning, catastrophe_hit, build_complete |
| ✅ | 7.11.9 | Integrate sounds into lobby/worker screens | game_start on phase transition, worker_allocated on realloc |
| ✅ | 7.11.10 | Optional simpleaudio dependency | `pip install terminus-game[audio]`; winsound fallback on Windows |
| ✅ | 7.11.11 | Audio unit tests — 30 tests | WAV format, duration, waveforms, caching, public API |
| ⬜ | 7.11.12 | Background music — looping chiptune per game phase | Stretch: lobby/playing/catastrophe themes |

---

## Epic 8: Testing & Quality [P1]

### 8.1 — Unit Tests

| Status | ID | Task |
|--------|-----|------|
| ✅ | 8.1.1 | State machine transitions (valid + invalid) |
| ✅ | 8.1.2 | Resource production formulas |
| ✅ | 8.1.3 | Catastrophe damage calculation |
| ✅ | 8.1.4 | Building lifecycle (build → upgrade → damage → repair → demolish) |
| ✅ | 8.1.5 | Market system (prices, buy/sell, stock limits) |
| ✅ | 8.1.6 | Scoring formula verification |
| ✅ | 8.1.7 | Catastrophe selection algorithm balance | 6 tests: diversity, severity progression, no duplicates, count, edge case, determinism |

### 8.2 — Integration Tests

| Status | ID | Task |
|--------|-----|------|
| ✅ | 8.2.1 | Full game lifecycle: create → join → setup → 2 catastrophes → scoring |
| ✅ | 8.2.2 | Multiplayer: 5 concurrent clients, no race conditions |
| ✅ | 8.2.3 | Reconnection: disconnect + reconnect, state intact |
| ✅ | 8.2.4 | Load: 50+ concurrent HTTP clients, measure perf |

### 8.3 — Manual Tests [P2]

| Status | ID | Task |
|--------|-----|------|
| ✅ | 8.3.1 | Playtest: 3-4 real players, full 45 min game |
| ✅ | 8.3.2 | Cross-platform: Windows + macOS + Linux terminals |
| ✅ | 8.3.3 | Fresh install test on clean machine |

---

## Epic 9: Packaging & Distribution

### 9.1 — Package Configuration [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 9.1.1 | Console script entry point | Needs update to `terminus = "terminus.__main__:main"` after rename |
| ✅ | 9.1.2 | Dependency version pins with compatible ranges | textual, fastapi, uvicorn, httpx, websockets |
| ✅ | 9.1.3 | `requires-python = ">=3.11"` | Set in pyproject.toml |
| ✅ | 9.1.4 | `README.md` — overview, install, quickstart | Needs update for Terminus name |
| ✅ | 9.1.5 | `.gitignore` for Python project | Created |

### 9.2 — Distribution Options [P2]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 9.2.1 | Document `pip install git+<url>` flow | README expanded with all install methods |
| ✅ | 9.2.2 | PyInstaller spec for single .exe | `terminus.spec` + `tools/build_exe.py` + frozen-path support in data loader |
| ✅ | 9.2.3 | GitHub Release workflow (tag → build → publish) | `.github/workflows/release.yml` — test→build→exe→release pipeline |
| ✅ | 9.2.4 | Publish to PyPI as `terminus-game` | Trusted Publisher (OIDC) via `pypa/gh-action-pypi-publish` |

---

## Epic 10: Stretch Goals (Post-V1) [P3]

### 10.1 — Singleplayer Mode

| Status | ID | Task |
|--------|-----|------|
| 💤 | 10.1.1 | AI settlement strategies (Balanced, Aggressive, Hoarder, Researcher) |
| 💤 | 10.1.2 | Singleplayer mode: 1 human vs 3-5 AI |
| 💤 | 10.1.3 | AI difficulty: Easy / Medium / Hard |

### 10.2 — Player-to-Player Trading

| Status | ID | Task |
|--------|-----|------|
| 💤 | 10.2.1 | Trade offer system (post offer, others accept/decline) |
| 💤 | 10.2.2 | Trade notification to target player |
| 💤 | 10.2.3 | P2P trade history |

### 10.3 — Game Replays

| Status | ID | Task |
|--------|-----|------|
| 💤 | 10.3.1 | Log all actions with timestamps |
| 💤 | 10.3.2 | Replay viewer (step through or accelerated) |

### 10.4 — Tournament Mode

| Status | ID | Task |
|--------|-----|------|
| 💤 | 10.4.1 | Multi-round tournament (3 games, aggregate) |
| 💤 | 10.4.2 | Elimination bracket |

---

## Epic 11: Developer Tools [P1]

### 11.1 — Admin API [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 11.1.1 | `GET /admin/state` — full game state dump (all players/colonies) | Gated by `TERMINUS_DEV_MODE=1` env var |
| ✅ | 11.1.2 | `POST /admin/set-resources` — override any player's resources | Accepts food/materials/knowledge/gold/population/morale |
| ✅ | 11.1.3 | `POST /admin/set-catastrophe-speed` — scale catastrophe intervals | Multiplier: 0.5=faster, 2.0=slower |
| ✅ | 11.1.4 | `POST /admin/trigger-catastrophe` — force next catastrophe immediately | Sets scheduled_time to now |
| ✅ | 11.1.5 | `POST /admin/complete-building` — instantly finish all construction | Calls `_update_colony_capacity` after |

### 11.2 — Dev Console TUI [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 11.2.1 | Dev console Textual app with retro terminal theme matching game | `python -m terminus.dev --server URL` |
| ✅ | 11.2.2 | Live game state view — phase, tick, players, catastrophe schedule | Auto-refresh every 2s |
| ✅ | 11.2.3 | Per-player resource controls — input fields + set button per colony | Also shows production rates, workers, buildings |

### 11.3 — Build Screen & Production UX [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 11.3.1 | Build screen shows current level badge, next-level costs, building effects | [NEW], [Lv.1], [MAX], [🔨] badges; effect descriptions |
| ✅ | 11.3.2 | Production rates displayed on resource bars | +X.X/t suffix on each resource bar |
| ✅ | 11.3.3 | Engine `get_production_rates()` — read-only rate calculation | Net food rate includes consumption |

### 11.4 — In-Game Dev Mode (Host-Only) [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ✅ | 11.4.1 | Dev mode toggle in lobby — host-only button to enable before starting | Stores `dev_mode: bool` on game state; hidden from other players |
| ✅ | 11.4.2 | Auto-launch dev console — spawn dev console in new terminal on game start | `subprocess.Popen` opens new terminal with `python -m terminus.dev --server URL` |
| ✅ | 11.4.3 | Server: allow admin endpoints via host token (no env var needed) | Admin endpoints accept host token OR `TERMINUS_DEV_MODE` env var |
| ✅ | 11.4.4 | In-game admin panel — host presses [F12] on colony screen to open DevPanel | Modal screen with player selector, resource editor, catastrophe controls |
| ✅ | 11.4.5 | DevPanel: player selector — list all players, highlight selected | OptionList of player names |
| ✅ | 11.4.6 | DevPanel: resource editor — input fields + Set button per player | Calls `POST /admin/set-resources` with selected player_id |
| ✅ | 11.4.7 | DevPanel: catastrophe controls — trigger now + speed (0.5×/1×/2×/5×) | Calls trigger + speed admin endpoints |
| ✅ | 11.4.8 | DevPanel: complete buildings — per selected player | Calls `POST /admin/complete-building` with player_id |
| ✅ | 11.4.9 | DevPanel: full state viewer — all players resources/workers/buildings/rates | Read-only display, auto-refreshes |
| ✅ | 11.4.10 | Dev mode hidden from non-host players — no badges or indicators | Host-only secret; admin gated by host token |

---

## Epic 12: LLM Benchmark Suite [P1]

### 12.1 — LLM Agent Interface [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.1.1 | `BenchmarkGameState` Pydantic schema — JSON sent to LLMs per turn | resources, buildings, workers, market, catastrophe_warning, opponents, available_actions |
| ⬜ | 12.1.2 | `ActionResponse` Pydantic schema — JSON received from LLMs | action, params, reasoning (structured factors + weights) |
| ⬜ | 12.1.3 | `ReasoningFactors` schema — 12 predefined decision factors with weights | resource_bottleneck, long_term_growth, opponent_pressure, catastrophe_preparation, market_opportunity, efficiency_optimization, defensive_positioning, cooperative_opportunity, specialization_synergy, immediate_survival, information_gathering, risk_diversification |
| ⬜ | 12.1.4 | Abstract `LLMAgent` base class — `async choose_action(state) -> ActionResponse` | Timeout, retry, validation interface |
| ⬜ | 12.1.5 | OpenAI-compatible adapter — covers GPT, Claude (via proxy), Ollama, vLLM | Uses httpx, configurable endpoint/model/temperature/max_tokens |
| ⬜ | 12.1.6 | Connection test method — validates API reachability with simple prompt | Returns latency + model name confirmation |
| ⬜ | 12.1.7 | Token counting — tiktoken for OpenAI models, heuristic (chars÷4) for others | Input + output tokens per turn |

### 12.2 — Built-in Opponents [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.2.1 | Random agent — uniform random from valid actions | Baseline floor (score = 0.0 in normalization) |
| ⬜ | 12.2.2 | Greedy heuristic — always picks highest immediate-value action | Mid-floor reference agent |
| ⬜ | 12.2.3 | Balanced heuristic — follows fixed optimal build order + allocation | Near-ceiling reference for scoring normalization |

### 12.3 — Benchmark Orchestrator [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.3.1 | `BenchmarkConfig` Pydantic model — game count, speed, max turns, seeds, metrics, weights, rate limit | JSON/YAML loadable, presets (Balanced, Reliability, Strategy, Triage, Endurance, Precision) |
| ⬜ | 12.3.2 | Speed multiplier module — divides all engine timers by multiplier (1×, 2×, 5×, 10×) | Build time, catastrophe interval, market tick — all scaled |
| ⬜ | 12.3.3 | Headless game runner — instantiate engine directly (no FastAPI/WS overhead) | Direct function calls to game engine, seeded RNG |
| ⬜ | 12.3.4 | Turn loop — send state to all agents simultaneously, collect responses, validate, apply | Respects rate limits, handles timeouts, logs invalid actions |
| ⬜ | 12.3.5 | Game sequence manager — runs N games sequentially with seed progression | Stores results per game, reports progress |
| ⬜ | 12.3.6 | Per-turn data recorder — snapshots full state + action + validation + timing + tokens | Stored in memory during game, serialized to JSON after |
| ⬜ | 12.3.7 | Rate limit controller — optional per-minute or per-concurrent cap with queue | Host-configurable, can be disabled for self-hosted models |
| ⬜ | 12.3.8 | Scripted disruption injector — engineers catastrophes/market shocks at fixed turns | For reproducible flexibility testing |

### 12.4 — Metrics Engine [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.4.1 | Abstract `MetricScorer` base class — `score(recording) -> DimensionResult` | Returns score (0-1), sub-scores, reported values dict |
| ⬜ | 12.4.2 | Tier 1 Planning metrics (6): build order, anticipation, market timing, catastrophe prep, housing, stockpile | Raw game measurements |
| ⬜ | 12.4.3 | Tier 1 Numerical metrics (6): invalid actions, worker sums, over-capacity, timing, trade math, feasibility | Raw game measurements |
| ⬜ | 12.4.4 | Tier 1 Flexibility metrics (7): recovery speed, reallocation, repair priority, market adapt, starvation, defense learn, distribution shift | Raw game measurements |
| ⬜ | 12.4.5 | Tier 2 Dimension 1: Multi-Decision Coherence Decay — inflection point detection, decay rate | From reasoning factors consistency + trigger correlation |
| ⬜ | 12.4.6 | Tier 2 Dimension 2: Applied Arithmetic Under Cognitive Load — load-weighted accuracy | From all numerical metrics + load factor computation |
| ⬜ | 12.4.7 | Tier 2 Dimension 3: Priority Triage Under Competing Constraints — expert ordering comparison | From multi-constraint event detection + action priority |
| ⬜ | 12.4.8 | Tier 2 Dimension 4: Compounding Error Recognition — detection lead time | From resource trajectory analysis + corrective action timing |
| ⬜ | 12.4.9 | Tier 2 Dimension 5: Justified Pivot vs Inconsistency — signal-to-noise ratio | From strategy change detection + trigger correlation |
| ⬜ | 12.4.10 | Tier 2 Dimension 6: Graceful Degradation Curve — failure mode classification | From per-turn quality curve fitting (linear, cliff, oscillating, stable, improving) |
| ⬜ | 12.4.11 | Tier 2 Dimension 7: Opportunity Cost Awareness — optimality gap measurement | From action value computation + 20-tick lookahead simulator |
| ⬜ | 12.4.12 | Composite scorer — weighted aggregation with 6 presets | Balanced, Reliability, Strategy, Triage, Endurance, Precision |
| ⬜ | 12.4.13 | Trend analysis — linear regression across N games, classification (Improving/Consistent/Degrading/Volatile) | Requires scipy or numpy for regression |
| ⬜ | 12.4.14 | LLM archetype classification — cross-dimension correlation analysis | Strategist, Accountant, Firefighter, Marathon Runner, All-Rounder, Specialist |

### 12.5 — Results & HTML Export [P0]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.5.1 | Results aggregation module — per-game scores, per-dimension breakdowns, confidence intervals | 95% CI on all scores |
| ⬜ | 12.5.2 | Jinja2 HTML template — self-contained report with embedded Chart.js | CDN for Chart.js, single-file output |
| ⬜ | 12.5.3 | Score progression line chart (per model across games) | Chart.js line chart, one series per LLM |
| ⬜ | 12.5.4 | Per-dimension grouped bar chart | 7 dimensions × N models, color-coded |
| ⬜ | 12.5.5 | Summary ranking table — model, composite score, trend, consistency | Sortable, with trend badges |
| ⬜ | 12.5.6 | Tier 1 detail section — expandable per-game sub-metric breakdowns | Collapsible HTML sections |
| ⬜ | 12.5.7 | Tier 3 mapping section — agentic workflow predictions per model | Table with production implications |
| ⬜ | 12.5.8 | Archetype classification display — radar chart per model | Spider chart showing dimension profile |
| ⬜ | 12.5.9 | JSON companion export — structured data matching HTML content | `results.json` alongside `report.html` |
| ⬜ | 12.5.10 | Export CLI — `terminus --benchmark --config FILE` produces output in `./benchmark-results/` | Creates directory, writes HTML + JSON |

### 12.6 — CLI & Integration [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.6.1 | `--benchmark` CLI flag in `__main__.py` | Launches benchmark mode instead of game |
| ⬜ | 12.6.2 | `--benchmark-config PATH` — load config from JSON/YAML file | Validates config, fails fast on missing fields |
| ⬜ | 12.6.3 | Interactive TUI setup screen — configure models, games, speed, metrics when no config file | Textual screen with form inputs |
| ⬜ | 12.6.4 | Progress display — live terminal output during benchmark (game N/M, turn X/Y, current scores) | Simple print-based, not full TUI |
| ⬜ | 12.6.5 | `[benchmark]` optional dependency group in `pyproject.toml` | jinja2, tiktoken |

### 12.7 — Testing & Verification [P1]

| Status | ID | Task | Notes |
|--------|-----|------|-------|
| ⬜ | 12.7.1 | Unit tests: schemas validation (valid + invalid action responses) | `tests/benchmark/test_schemas.py` |
| ⬜ | 12.7.2 | Unit tests: metric scorers (known inputs → expected scores) | `tests/benchmark/test_metrics.py` |
| ⬜ | 12.7.3 | Unit tests: orchestrator (mock LLM, verify turn loop) | `tests/benchmark/test_orchestrator.py` |
| ⬜ | 12.7.4 | Unit tests: HTML export (template renders without error) | `tests/benchmark/test_export.py` |
| ⬜ | 12.7.5 | Integration test: 1 game, Random vs Greedy, all metrics, verify HTML output | Smoke test with fixture config |
| ⬜ | 12.7.6 | Sanity check: Random agent scores lower than Greedy on all dimensions | Validates scoring logic direction |

---

## Dependency Graph

```
Epic 1 ✅ Foundation & Infrastructure (16/16 done)
  │
  ├──→ Epic 7 🔨 Visual Identity (58/67 done)
  │     ├── 7.1 ✅ Title Art (4/4)
  │     ├── 7.2-7.5 ✅ Art Assets (locations, specs, buildings, catastrophes)
  │     ├── 7.6 ✅ Theme (.tcss)
  │     ├── 7.7 ✅ Custom Widgets (7/7)
  │     ├── 7.8 ✅ Screen Integration (9/9)
  │     ├── 7.9 ✅ Animations (6/6)
  │     └── 7.10-7.11 ⬜ QoL + Audio (9 deferred)
  │
  ├──→ Epic 2 ✅ Game Engine (48/48 COMPLETE)
  │     ├── 2.1 ✅ Models (9/9)
  │     ├── 2.2 ✅ State Machine (7/7 — lobby leave/kick + host reassignment done)
  │     ├── 2.3 ✅ Resources (6/6)
  │     ├── 2.4 ✅ Buildings (7/7)
  │     ├── 2.5 ✅ Catastrophes (7/7 — location flavor text done)
  │     ├── 2.6 ✅ Market (6/6)
  │     └── 2.7 ✅ Scoring (6/6 — snapshots + stats done)
  │
  ├──→ Epic 3 ✅ Server API & Networking (28/28 COMPLETE)
  │     ├── 3.1 ✅ REST API (11/11)
  │     ├── 3.2 ✅ WebSocket Events (12/12 — game_over stats + market delta done)
  │     └── 3.3 ✅ Cloudflared (5/5 — tunnel URL in TUI + failure handling done)
  │
  ├──→ Epic 4 ✅ TUI Client (47/47 COMPLETE)
  │
  ├──→ Epic 5 ✅ Game Balance (12/12)
  ├──→ Epic 6 ✅ Persistence & Reliability (9/9)
  ├──→ Epic 8 ✅ Testing & Quality (14/14)
  ├──→ Epic 9 ✅ Packaging & Distribution (9/9 COMPLETE)
  └──→ Epic 10 💤 Stretch Goals (0/10, deferred)
  └──→ Epic 11 ✅ Developer Tools (18/18)
```

---

## Sprint Plan

### Sprint 2 — Rename + Visual Foundation
> **Goal**: Rename to Terminus, fix broken title, establish visual system

| # | Task | Epic | Priority |
|---|------|------|----------|
| 1 | Rename `colony/` → `terminus/`, update all imports + config | 1.3 | P0 |
| 2 | Design & implement TERMINUS title art (single-width, ≤60 cols) | 7.1.1 | P0 |
| 3 | Create external `theme.tcss` with full color palette + panel styles | 7.6.1-7.6.5 | P0 |
| 4 | Implement `ResourceBar` widget | 7.7.1 | P0 |
| 5 | Implement `CountdownTimer` widget | 7.7.4 | P0 |
| 6 | Implement `NotificationToast` widget | 7.7.5 | P0 |
| 7 | Create 5 location ASCII artworks | 7.2.1-7.2.5 | P0 |
| 8 | Create 4 specialization ASCII artworks | 7.3.1-7.3.4 | P0 |
| 9 | Wire title art + theme into main menu screen | 7.8.1 | P0 |
| 10 | Wire location/spec art into setup screen | 7.8.2 | P0 |

### Sprint 3 — Widget Integration + Building Art
> **Goal**: Colony screen uses widgets, building visuals complete

| # | Task | Epic | Priority |
|---|------|------|----------|
| 1 | Create 10 building mini-artworks | 7.4.1-7.4.10 | P1 |
| 2 | Implement `BuildingCard` widget | 7.7.2 | P0 |
| 3 | Implement `WorkerSlider` widget | 7.7.3 | P0 |
| 4 | Implement `AsciiArtPanel` widget | 7.7.6 | P1 |
| 5 | Rewrite Colony Screen with ResourceBar + BuildingCard + CountdownTimer | 7.8.3 | P0 |
| 6 | Rewrite Workers Screen with WorkerSlider widgets | 7.8.5 | P0 |
| 7 | Rewrite Build Screen with building art + affordability colors | 7.8.4 | P1 |
| 8 | Create 6 catastrophe category artworks | 7.5.1-7.5.6 | P1 |
| 9 | Rewrite Catastrophe Screen with art + damage animation | 7.8.6 | P1 |
| 10 | Implement `SparklineChart` widget | 7.7.7 | P1 |

### Sprint 4 — Polish + Engine Hardening
> **Goal**: Animations, market visuals, remaining engine gaps

| # | Task | Epic | Priority |
|---|------|------|----------|
| 1 | Title reveal animation | 7.9.1 | P2 |
| 2 | Catastrophe damage reveal animation | 7.9.2 | P1 |
| 3 | Timer urgency transitions | 7.9.3 | P1 |
| 4 | Market Screen with sparklines + styled panels | 7.8.7 | P1 |
| 5 | Leaderboard Screen with rank decorations + player highlight | 7.8.8 | P1 |
| 6 | Lobby Screen styled share box | 7.8.9 | P1 |
| 7 | State delta broadcasts (not just tick number) | 3.2.8 | P0 |
| 8 | Catastrophe results with avg comparison | 2.5.5 | P0 |
| 9 | WebSocket heartbeat + reconnection | 3.2.11-12 | P1 |
| 10 | Unit tests for engine core | 8.1.1-8.1.4 | P1 |

### Sprint 5 — Achievements, Trade Polish & Testing ✅
> **Goal**: Achievement system, market UX improvements, graceful shutdown, test coverage
> **Status**: COMPLETE — 39 tests passing (33 existing + 6 new)

| # | Task | Epic | Status |
|---|------|------|--------|
| 1 | Achievement model + detection (8 achievements) | 2.7.2 | ✅ |
| 2 | Achievement bonus points in scoring | 2.7.3 | ✅ |
| 3 | Achievement badges on leaderboard screen | 4.8.2 | ✅ |
| 4 | Trade history panel in market screen | 4.6.4 | ✅ |
| 5 | SparklineChart widget + price sparklines | 7.7.7, 4.6.5 | ✅ |
| 6 | Graceful tunnel stop (atexit + signals) | 3.3.4 | ✅ |
| 7 | Catastrophe selection algorithm tests (6 tests) | 8.1.7 | ✅ |

### Sprint 6 — Bug Fixes + Server Hardening ✅
> **Goal**: Fix engine bugs, harden REST API, improve WS events, add regression tests
> **Status**: COMPLETE — 55 tests passing (39 existing + 16 new)

| # | Task | Epic | Status |
|---|------|------|--------|
| 1 | Fix WORKER_ROLES missing import (NameError on allocate) | 2.2.2 | ✅ |
| 2 | Apply SPECIALIZATION_MODIFIERS in production formula | 2.3.1 | ✅ |
| 3 | Tick loop drift compensation (time.monotonic) | 2.2.7 | ✅ |
| 4 | Name uniqueness check (case-insensitive) in engine | 2.2.2 | ✅ |
| 5 | Create response: host field + name validation regex | 3.1.1 | ✅ |
| 6 | Ready toggle phase guard (LOBBY only) | 3.1.4 | ✅ |
| 7 | Start game: ≥1 ready check + 403 for non-host | 3.1.5 | ✅ |
| 8 | Setup resubmit guard + fixed response shape | 3.1.6 | ✅ |
| 9 | Market: sell_prices with trade discount + phase check | 3.1.8 | ✅ |
| 10 | Leaderboard: rank + is_you fields | 3.1.9 | ✅ |
| 11 | Per-endpoint rate limiting (5/sec GET, 10/sec actions) | 3.1.11 | ✅ |
| 12 | player_joined payload (player_name/player_count) | 3.2.2 | ✅ |
| 13 | Per-player state_update (colony + market data) | 3.2.8 | ✅ |
| 14 | Reconnect state_sync event | 3.2.11 | ✅ |
| 15 | 9 engine fix tests (test_engine_fixes.py) | 8.x | ✅ |
| 16 | 7 API validation tests (test_api_validation.py) | 8.x | ✅ |

### Sprint 7 — Client Polish + WS Events ✅
> **Goal**: Fix WS event architecture, polish TUI screens, improve catastrophe + game-over UX
> **Status**: COMPLETE — 61 tests passing (55 existing + 6 new)

| # | Task | Epic | Status |
|---|------|------|--------|
| 1 | App-level WS event dispatcher (events no longer lost) | 4.1.5 | ✅ |
| 2 | Handle `state_sync` on reconnect (client-side) | 3.2.11 | ✅ |
| 3 | Handle `market_update` (client caches + forwards) | 3.2.10 | ✅ |
| 4 | Ready button visual toggle (label + color) | 4.3.3 | ✅ |
| 5 | Game settings display (preset + max players) | 4.3.5 | ✅ |
| 6 | Skip-to-end catastrophe animation (Enter/Space) | 4.7.2 | ✅ |
| 7 | Staggered damage reveal (offset per stat) | 4.7.2 | ✅ |
| 8 | Before→after damage format + avg comparison | 4.7.3 | ✅ |
| 9 | Location + specialization labels on colony | 4.5.5 | ✅ |
| 10 | Score display on colony screen | 4.5.5 | ✅ |
| 11 | Construction ETA text + completion toast | 4.5.9 | ✅ |
| 12 | Play Again + Return to Menu buttons (game-over) | 4.8.4 | ✅ |
| 13 | Per-player catastrophe_warning with watchtower hints | 3.2.5 | ✅ |
| 14 | Individualized catastrophe_results with averages | 3.2.7 | ✅ |
| 15 | Use server `rank` + `is_you` in leaderboard | 3.1.9 | ✅ |
| 16 | 6 Sprint 7 tests (test_sprint7.py) | 8.x | ✅ |

### Sprint 8 — Close Out Core (Epics 2/3/4) ✅
> **Goal**: Make Epics 2, 3, and 4 feature-complete. Player leave/kick, game stats, WS event payloads, connection hardening, flavor text.
> **Status**: COMPLETE — 76 tests passing (61 existing + 15 new)

| # | Task | Epic | Status |
|---|------|------|--------|
| 1 | Proper `remove_player` + host reassignment (LOBBY=delete, PLAYING=soft) | 2.2.2 | ✅ |
| 2 | `POST /game/leave` endpoint (authenticated, cleans up WS+token) | 2.2.2 | ✅ |
| 3 | Enhanced `player_left` broadcast (adds `player_count`) | 3.2.3 | ✅ |
| 4 | Stat tracking fields on Colony model (5 new fields) | 2.7.6 | ✅ |
| 5 | Increment stat counters: build complete, buy/sell, catastrophe, peak pop | 2.7.6 | ✅ |
| 6 | Stats in `_calculate_scores` + `game_over` payload | 3.2.9 | ✅ |
| 7 | Game stats panel on leaderboard (is_game_over=True) | 4.8.3 | ✅ |
| 8 | Per-round scoring snapshots (`state.score_history`) | 2.7.5 | ✅ |
| 9 | `market_update` price_changes % delta | 3.2.10 | ✅ |
| 10 | Location-specific catastrophe flavor text (16 catastrophes × 5 locations) | 2.5.7 | ✅ |
| 11 | Connection retry: auto-retry on mount, exponential backoff, attempt counter | 4.1.5 | ✅ |
| 12 | Tunnel URL in TUI lobby (uses `_tunnel_url` module var) | 3.3.3 | ✅ |
| 13 | Tunnel failure handling (try/except, graceful fallback) | 3.3.5 | ✅ |
| 14 | 15 Sprint 8 tests (test_sprint8.py) | 8.x | ✅ |

---

## Files Affected by Visual Overhaul

| Action | Path | Purpose |
|--------|------|---------|
| **Rename** | `colony/` → `terminus/` | Package directory |
| **Create** | `terminus/data/art.py` | All ASCII art constants (title, locations, specs, buildings, catastrophes) |
| **Create** | `terminus/client/theme.tcss` | External Textual CSS theme |
| **Create** | `terminus/client/widgets/__init__.py` | Widget package init |
| **Create** | `terminus/client/widgets/resource_bar.py` | ResourceBar widget |
| **Create** | `terminus/client/widgets/building_card.py` | BuildingCard widget |
| **Create** | `terminus/client/widgets/worker_slider.py` | WorkerSlider widget |
| **Create** | `terminus/client/widgets/countdown_timer.py` | CountdownTimer widget |
| **Create** | `terminus/client/widgets/notification_toast.py` | NotificationToast widget |
| **Create** | `terminus/client/widgets/ascii_art_panel.py` | AsciiArtPanel widget |
| **Create** | `terminus/client/widgets/sparkline_chart.py` | SparklineChart widget |
| **Modify** | `terminus/client/app.py` | Remove inline CSS, load .tcss, rename class |
| **Modify** | `terminus/client/screens/main_menu.py` | New title art, animation, themed layout |
| **Modify** | `terminus/client/screens/setup.py` | Art panels for location/spec |
| **Modify** | `terminus/client/screens/colony.py` | Widget integration (ResourceBar, BuildingCard, CountdownTimer) |
| **Modify** | `terminus/client/screens/build.py` | Building art, affordability colors |
| **Modify** | `terminus/client/screens/workers.py` | WorkerSlider widgets |
| **Modify** | `terminus/client/screens/catastrophe.py` | Category art, damage animation |
| **Modify** | `terminus/client/screens/market.py` | SparklineChart, styled panels |
| **Modify** | `terminus/client/screens/leaderboard.py` | Rank decorations, player highlight |
| **Modify** | `terminus/client/screens/lobby.py` | Styled share box |
| **Modify** | `pyproject.toml` | Name, scripts, build targets |
| **Modify** | `test_engine.py` | Import paths |
| **Modify** | `README.md` | All references |

---

## Open Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|-----------|
| 1 | Endpoint security blocks venv python.exe on dev machine | Can't `pip install .` normally | Use `uv run` with base python + PYTHONPATH workaround |
| 2 | cloudflared free tier under 250 WebSocket load | Lag/drops during catastrophe | Load test early; document direct IP fallback |
| 3 | 250 WS × 2-sec broadcasts = high traffic | Server/network overwhelm | Send deltas not full state; batch broadcasts |
| 4 | Textual rendering over SSH/remote terminals | Degraded UX | Ensure keyboard-only nav works fully |
| 5 | Game balance: 20 catastrophes × 5 locations × 4 specs | Hard to balance perfectly | Accept ±5% variance; simulation runner |
| 6 | Windows cmd.exe vs Windows Terminal | Color/unicode issues | Recommend Windows Terminal; test both |
| 7 | ASCII art width inconsistency across terminals | Art may render differently in different font/terminal combos | Strict single-width chars only, test on Windows Terminal + cmd.exe |
| 8 | Large rename diff may break git history | Hard to trace file history through rename | Do rename as single atomic commit before any other changes |
