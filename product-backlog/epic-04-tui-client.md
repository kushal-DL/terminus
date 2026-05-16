# Epic 4: TUI Client (Screens & Logic)

> **Priority**: P0  
> **Status**: 38 ✅ Done · 8 🔨 Scaffolded · 1 ⬜ TODO (47 stories)  
> **Framework**: Textual (Python TUI)  
> **Sprint**: 1 (basic), 3-4 (visual overhaul)

---

## Feature 4.1 — Application Shell

### Story 4.1.1 — Textual App Subclass

**As a** player  
**I want** a terminal-based application that manages game screens  
**So that** I can interact with the game in a structured, navigable way

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `ColonyApp` (→ `TerminusApp`) extends `textual.App`
- [ ] `q` quits from any screen
- [ ] App handles unhandled exceptions gracefully (display error, don't crash)
- [ ] On startup: connects to server (if joining) or starts server thread (if creating)

---

### Story 4.1.2 — Screen Navigation

**As a** player  
**I want** to navigate between game screens using push/pop  
**So that** I can access sub-menus (build, workers, market) and return

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Push screens: lobby → setup → colony (one-way progression)
- [ ] Overlay screens: colony → build/workers/market/leaderboard (push + pop back)
- [ ] Data passing via screen constructor (e.g., colony state passed to build screen)
- [ ] Back navigation via `Escape` key on overlay screens

---

### Story 4.1.3 — Global Status Bar

**As a** player  
**I want** a persistent status bar showing connection state, game phase, and timer  
**So that** I always know my game context regardless of which screen I'm on

**Status**: ✅ Done

**Implementation Notes**:
- `StatusBar(Static)` widget in `app.py` with `update_connection()`, `update_phase()`, `update_players()`, `update_timer()` methods
- Connection state: green ● connected / red ○ disconnected
- Updates from WS events + state refresh

**Acceptance Criteria**:
- [ ] Fixed footer bar on all screens (except main menu)
- [ ] Left: connection indicator (● green=connected, ● red=disconnected)
- [ ] Center: current phase name (LOBBY / SETUP / PLAYING / CATASTROPHE)
- [ ] Right: next catastrophe countdown (MM:SS) or phase-relevant timer
- [ ] Updates reactively via WebSocket events (not polling)

---

### Story 4.1.4 — Notification Toast System

**As a** player  
**I want** to see brief popup messages for important events  
**So that** I'm notified of key happenings without leaving my current screen

**Status**: ✅ Done

**Implementation Notes**:
- `ToastRack` mounted in app, `notify_toast()` helper method
- Wired to WS events (player_joined, catastrophe_warning, etc.)
- Uses `NotificationToast` widget from `terminus/client/widgets/`

**Acceptance Criteria**:
- [ ] Toast appears top-right corner, auto-dismisses after 3s
- [ ] Categories: info (cyan), success (green), warning (amber), error (red)
- [ ] Queue-based: max 3 visible, new toasts push old ones down
- [ ] Events triggering toasts: player joined/left, building complete, catastrophe warning, trade complete
- [ ] Toast includes icon + brief message (max 40 chars)

---

### Story 4.1.5 — Connection Loss UI

**As a** player  
**I want** to see a clear indicator when my connection drops and auto-retry  
**So that** I'm not confused by stale data and can reconnect without restarting

**Status**: 🔨 Scaffolded

**Notes**: App-level WS dispatcher prevents event loss; ConnectionLost modal works; still needs button disable + backoff

**Implementation Notes**:
- `ConnectionLostScreen(ModalScreen)` in `terminus/client/screens/connection_lost.py`
- Retry button calls `client.connect_ws()` + `get_state()`
- Quit button pops all screens
- Triggered by `handle_connection_event()` in app.py

**Acceptance Criteria**:
- [ ] On WebSocket disconnect: overlay banner "Connection lost — retrying..."
- [ ] Auto-retry with exponential backoff (1s, 2s, 4s, 8s, max 30s)
- [ ] After 5 failed retries: show "Reconnect" button + manual URL input
- [ ] On reconnection: fetch full state, dismiss banner, show "Reconnected!" toast
- [ ] During disconnection: all action buttons disabled (grayed out)

---

### Story 4.1.6 — External .tcss Theme File

**As a** developer  
**I want** all CSS in an external `.tcss` file rather than inline  
**So that** styling is maintainable and separated from logic

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Create `terminus/client/theme.tcss` containing all styles
- [ ] Remove `CSS = """..."""` from App class
- [ ] Load via `CSS_PATH = "theme.tcss"` on App class
- [ ] All screens use class-based selectors from the theme file
- [ ] Hot-reload works during development (`textual run --dev`)

---

## Feature 4.2 — Main Menu Screen

### Story 4.2.1 — ASCII Art Title

**As a** player  
**I want** to see an impressive retro ASCII art title on launch  
**So that** the game immediately establishes its visual identity

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] "TERMINUS" rendered in single-width ASCII art (see Epic 7.1)
- [ ] Max 60 columns wide, 6-8 lines tall
- [ ] Uses only: `/`, `\`, `|`, `_`, `=`, `-`, `#`, `*`, `.`, `~`, letters
- [ ] Renders correctly in 80-column terminal without wrapping
- [ ] Centered in viewport

---

### Story 4.2.2 — Menu Options

**As a** player  
**I want** clear menu options to create, join, learn, or quit  
**So that** I can quickly start or join a game

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Four buttons: Create Game / Join Game / How to Play / Quit
- [ ] Keyboard navigation: arrow keys or j/k, Enter to select
- [ ] Buttons have retro styling: `[ Create Game ]`
- [ ] Focus highlight clearly visible

---

### Story 4.2.3 — Create Game Flow

**As a** host  
**I want** to enter my name and create a game  
**So that** a server starts and I enter the lobby as host

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Input field: player name (1-20 chars)
- [ ] On submit: starts uvicorn server in background thread on localhost:8000
- [ ] Creates game via POST /game/create
- [ ] Receives token, transitions to lobby screen
- [ ] If `--public` flag: starts cloudflared tunnel (see Epic 3.3)
- [ ] Error handling: port in use → try next port, show error if all fail

---

### Story 4.2.4 — Join Game Flow

**As a** player  
**I want** to enter a server URL and my name to join an existing game  
**So that** I can connect to someone else's hosted game

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Input fields: server URL (with default `localhost:8000`), player name
- [ ] On submit: POST /game/join to server URL
- [ ] On success: receives token, transitions to lobby
- [ ] On failure: display error (server unreachable, game full, name taken)
- [ ] URL validation: strip trailing slash, add http:// if missing scheme
- [ ] Supports both `localhost:8000` and `https://xxx.trycloudflare.com` formats

---

### Story 4.2.5 — How to Play Screen

**As a** new player  
**I want** to read game rules and mechanics before playing  
**So that** I understand the game without external documentation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Scrollable Markdown-rendered help text
- [ ] Sections: Overview, Resources, Buildings, Catastrophes, Scoring, Controls
- [ ] Escape to return to main menu
- [ ] Concise but complete (~2 screens of content)

---

## Feature 4.3 — Lobby Screen

### Story 4.3.1 — Player List

**As a** player  
**I want** to see who's in the lobby and their ready status  
**So that** I know when we can start

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] List shows: player name, ready indicator (✓ / ✗), host badge (★)
- [ ] Updates in real-time via WebSocket events (player_joined, player_left, ready_changed)
- [ ] Currently polls every 2s (fallback) — should be event-driven

---

### Story 4.3.2 — Share URL Display

**As a** host  
**I want** to see the connection URL prominently displayed  
**So that** I can share it with other players

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] If public game: `https://xxx.trycloudflare.com` in bordered box
- [ ] If local: `localhost:8000` displayed
- [ ] Copy-to-clipboard hint shown
- [ ] URL visually prominent (bordered, colored)

---

### Story 4.3.3 — Ready Toggle

**Status**: ✅ Done

**Notes**: Toggles label (✓ Ready / ✗ Not Ready) + variant; syncs state from server on poll

**Acceptance Criteria**:
- [ ] Button toggles between "Ready" and "Not Ready"
- [ ] Sends POST /game/ready on press
- [ ] Visual feedback: button changes color (green when ready)

---

### Story 4.3.4 — Start Game (Host Only)

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] "Start Game" button visible only to host
- [ ] Enabled only when ≥1 player is ready
- [ ] Sends POST /game/start
- [ ] All clients transition to Setup screen via `game_phase_changed` event

---

### Story 4.3.5 — Game Settings Display

**Status**: ✅ Done

**Notes**: Shows preset, catastrophe count, max players; host can adjust catastrophe count

**Implementation Notes**:
- Host sees/adjusts catastrophe count via "Fewer Cats"/"More Cats" buttons in lobby
- Sends POST to `/game/settings` endpoint
- Non-host sees settings as read-only labels
- `_refresh_lobby()` updates settings from lobby response

**Acceptance Criteria**:
- [ ] Host can see/adjust: game preset (Quick/Standard/Extended), max players, catastrophe count
- [ ] Non-host players see settings as read-only
- [ ] Settings changes broadcast to all clients
- [ ] Preset selector with description of what changes

---

### Story 4.3.6 — Player Count

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Shows "X / 250 players" (or configured max)
- [ ] Updates on join/leave

---

## Feature 4.4 — Setup Screen

### Story 4.4.1 — Location Selection

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] OptionList with 5 locations: Coast, Mountain, Plains, Forest, Desert
- [ ] Each shows: name, brief description, resource modifiers
- [ ] Highlight shows starting resource preview in side panel
- [ ] Art panel shows location ASCII art (Epic 7.2) when highlighted

---

### Story 4.4.2 — Specialization Selection

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] OptionList with 4 specializations: Military, Trade, Science, Agriculture
- [ ] Each shows: name, bonus description
- [ ] Art panel shows spec ASCII art (Epic 7.3) when highlighted

---

### Story 4.4.3 — Countdown Timer

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] 90-second countdown displayed prominently
- [ ] Timer synchronized with server
- [ ] On timeout: auto-submits defaults (random location + first spec)
- [ ] Color changes: green → amber (30s) → red (10s)

---

### Story 4.4.4 — Confirm Button

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Submit button: sends POST /game/setup with selections
- [ ] Disabled until both location and spec selected
- [ ] After submit: shows "Waiting for other players..." with spinner
- [ ] On phase change to PLAYING: auto-navigate to colony screen

---

### Story 4.4.5 — Preview Panel

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Shows starting resources for selected location+spec combo
- [ ] Updates live as selection changes
- [ ] Displays: food, materials, knowledge, gold, population, storage cap

---

## Feature 4.5 — Colony Management Screen

### Story 4.5.1 — Resource Display

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] 4 resources shown with current / max values
- [ ] Color-coded by resource type (food=green, materials=amber, knowledge=cyan, gold=yellow)
- [ ] Updates every tick (2s) via WebSocket state_update
- [ ] Shows production rate (+X.X/tick) next to each resource
- [ ] Future: replace with `ResourceBar` widget (Epic 7.7.1)

---

### Story 4.5.2 — Worker Allocation Display

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Shows current workers per role (Farmers, Miners, Scholars, Soldiers, Traders, Builders)
- [ ] Total shown: "Workers: X / Y (Y = population)"
- [ ] Press `w` to open Workers editor screen
- [ ] Idle workers highlighted in warning color

---

### Story 4.5.3 — Buildings Panel

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] List of all built structures with: name, level (★★☆), health bar, status
- [ ] Status indicators: ✓ operational, 🔨 building (X%), ✗ damaged
- [ ] Press `b` to open Build screen
- [ ] Under construction shows progress percentage

---

### Story 4.5.4 — Build Menu Screen

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] List of all available buildings with costs
- [ ] Color indicates affordability: green=can afford, red=cannot
- [ ] Select + Enter to build
- [ ] Shows: name, level, cost (food/materials/knowledge), build time, effect description
- [ ] Already-built shows "Upgrade to Lv.X" with upgrade cost

---

### Story 4.5.5 — Colony Stats

**Status**: ✅ Done

**Notes**: Pop, morale, score, location label, specialization label all displayed

**Acceptance Criteria**:
- [ ] Population count with growth indicator
- [ ] Morale percentage with color (green >1.0, yellow 0.7-1.0, red <0.7)
- [ ] Score display
- [ ] Location + Specialization labels

---

### Story 4.5.6 — Catastrophe Countdown

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] MM:SS format countdown to next catastrophe
- [ ] Synced with server timer
- [ ] Color urgency: green > 60s, amber < 60s, red < 30s
- [ ] Flashes at < 10s

---

### Story 4.5.7 — Watchtower Hint Display

**Status**: ✅ Done

**Implementation Notes**:
- Server returns `watchtower_hint` in `get_player_state()` based on watchtower building level
- Level 1: category hint, Level 2: type name, Level 3: type + timing
- Colony screen shows 🔭 icon with hint text in `#watchtower-hint` label

**Acceptance Criteria**:
- [ ] If player has Watchtower: show hint text near catastrophe timer
- [ ] Level 1: shows category ("Natural disaster incoming")
- [ ] Level 2: shows type ("Earthquake approaching")
- [ ] Level 3: shows exact timing
- [ ] Hint appears 30s before catastrophe (via catastrophe_warning event)

---

### Story 4.5.8 — Quick Action Keybindings

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `b` → Build screen
- [ ] `w` → Workers screen
- [ ] `m` → Market screen
- [ ] `l` → Leaderboard screen
- [ ] Key hints displayed in footer or help bar
- [ ] `?` or `h` → Help overlay

---

### Story 4.5.9 — Construction Progress Bar

**Status**: ✅ Done

**Notes**: Progress bar + ~Xs ETA text + completion toast notification

**Implementation Notes**:
- Buildings under construction show `🔨 Farm [████░░░░░░] 42%`
- Uses `construction_progress/construction_target` from building model
- 10-char wide bar in colony screen buildings panel

**Acceptance Criteria**:
- [ ] Buildings under construction show `[████░░░░░░] 42%` bar
- [ ] Updates each tick based on construction worker progress
- [ ] Shows ETA: "~12s remaining"
- [ ] Completion triggers toast notification + flash

---

## Feature 4.6 — Market Screen

### Story 4.6.1 — Price Table

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Table: Resource | Buy Price | Sell Price | Stock Available
- [ ] Prices update on market_update events
- [ ] Color coding: cheap=green, expensive=red (relative to base)

---

### Story 4.6.2 — Buy Interface

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Select resource → enter quantity → confirm
- [ ] Shows total gold cost before confirming
- [ ] Validates: enough gold, enough stock
- [ ] On success: toast "Bought X food for Y gold"

---

### Story 4.6.3 — Sell Interface

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Select resource → enter quantity → confirm
- [ ] Shows gold received before confirming
- [ ] Validates: enough of resource to sell

---

### Story 4.6.4 — Trade History Panel

**Status**: ✅ Done

**Implementation Notes**:
- `DataTable` with columns: Tick, Action (BUY/SELL), Resource, Qty, Price, Total
- Shows last 10 trades, most recent first
- Fetched from `get_state()` which returns `trade_history` filtered per-player
- Refreshes after each buy/sell action

**Acceptance Criteria**:
- [ ] Scrollable list of recent trades (last 10)
- [ ] Format: "Bought 5 food @ 3.2g" / "Sold 10 materials @ 2.1g"
- [ ] Timestamp or tick number for each trade

---

### Story 4.6.5 — Price Sparkline Chart

**Status**: ✅ Done

**Implementation Notes**:
- Uses `SparklineChart` widget (Epic 7.7.7) — 4 instances in market screen
- One sparkline per resource (Food/Materials/Knowledge/Gold)
- Data sourced from `MarketState.price_history` via `GET /game/market`
- Trend coloring: green=up, red=down

**Acceptance Criteria**:
- [ ] `SparklineChart` widget (Epic 7.7.7) showing last 10 price points
- [ ] One sparkline per resource
- [ ] Trend arrow: ↑ ↓ → next to current price
- [ ] Green for price decrease (good for buying), red for increase

---

## Feature 4.7 — Catastrophe Event Screen

### Story 4.7.1 — Dramatic Announcement

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Full-screen overlay when catastrophe fires
- [ ] Shows: catastrophe name (large), category, flavor text
- [ ] Category-specific ASCII art (Epic 7.5)
- [ ] Brief pause (2-3s) before showing results

---

### Story 4.7.2 — Damage Animation

**Status**: ✅ Done

**Notes**: Staggered reveal (pop→food→mat→bld offset 3 steps each) + Enter/Space skip-to-end

**Implementation Notes**:
- 15-step progressive reveal over 3 seconds in catastrophe.py
- Numbers count up from 0 to final values
- Staggered per damage category

**Acceptance Criteria**:
- [ ] Numbers count up from 0 to final value over 5s
- [ ] Staggered reveal: population → resources → buildings (0.5s gap)
- [ ] Red color for losses, impacts feel dramatic
- [ ] Skip animation option (press Enter to reveal all)

---

### Story 4.7.3 — Survival Summary

**Status**: ✅ Done

**Notes**: Before→after format ('Population: 50→45 (lost 5)') + avg comparison from results

**Acceptance Criteria**:
- [ ] After damage reveal: show survival stats
- [ ] "Population: X → Y (lost Z)"
- [ ] "Resources lost: X food, Y materials, Z knowledge"
- [ ] "Buildings damaged: Farm (80% → 40%), Wall (destroyed)"
- [ ] Comparison to average: "You lost 2 fewer than average" (green) / "3 more" (red)

---

### Story 4.7.4 — Mitigation Display

**Status**: ✅ Done

**Implementation Notes**:
- Shows `mitigated_by` buildings with icons after damage animation
- Reads from `event_data["results"]` per-player breakdown
- Example: "🏥 Hospital reduced damage!"

**Acceptance Criteria**:
- [ ] Shows what reduced damage: "Hospital saved 3 population", "Wall blocked 20% damage"
- [ ] Listed after damage summary
- [ ] Color: green for mitigation effects
- [ ] If no mitigation: shows "No defenses active — consider building..."

---

### Story 4.7.5 — Continue Button

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] "Continue" button or auto-advance after 10s
- [ ] Returns to colony screen
- [ ] Phase transitions back to PLAYING on server signal

---

### Story 4.7.6 — Quick Leaderboard

**Status**: ✅ Done

**Implementation Notes**:
- Mini-leaderboard shown after damage animation on catastrophe screen
- Fetches top 5 scores via `client.get_leaderboard()`
- Shows current player marker (► name ◄)

**Acceptance Criteria**:
- [ ] Shows top 5 players + your rank (if not in top 5)
- [ ] Brief: rank, name, score only
- [ ] Updates after catastrophe results are final
- [ ] Position change indicator: ↑2, ↓1, — (unchanged)

---

## Feature 4.8 — Leaderboard Screen

### Story 4.8.1 — Ranked Table

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] DataTable columns: Rank, Player, Score, Population, Morale
- [ ] Sorted by score descending
- [ ] Updates when navigated to (fetches from /game/leaderboard)
- [ ] Top 3 have decorations: 🥇🥈🥉 or `[1st]` `[2nd]` `[3rd]`

---

### Story 4.8.2 — Achievement Badges

**Status**: ✅ Done

**Implementation Notes**:
- "Achievements" column added to leaderboard DataTable
- Shows earned achievement icons (🛡️📦🏗️🏰💰📚👥✨) per player
- Fetches from `/game/leaderboard` response which includes `achievements: list[str]`
- Uses `get_achievement_by_id()` to look up icon per achievement

**Acceptance Criteria**:
- [ ] After game ends: show achievements earned per player
- [ ] Achievements: "Survivor" (0 deaths), "Tycoon" (most gold), "Builder" (all buildings), etc.
- [ ] Shown as badges next to player name in final leaderboard
- [ ] Bonus points from achievements reflected in score

---

### Story 4.8.3 — Game Statistics

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Post-game stats panel: total resources produced, catastrophes survived, trades made
- [ ] Per-player highlights: "Most resilient", "Biggest trader", etc.
- [ ] Game duration, total ticks, catastrophe count

---

### Story 4.8.4 — Back/Return Button

**Status**: ✅ Done

**Notes**: Back + Play Again + Return to Menu buttons; game-over buttons via is_game_over flag

**Acceptance Criteria**:
- [ ] During game: Escape returns to colony screen
- [ ] After game over: "Return to Menu" button → main menu
- [ ] "Play Again" option → creates new game with same server

---

### Story 4.8.5 — Highlight Current Player

**Status**: ✅ Done

**Implementation Notes**:
- Player's own row marked with `► name ◄` decorations in leaderboard DataTable
- Summary label shows "Your rank: #N — Score: X (delta vs average)"

**Acceptance Criteria**:
- [ ] Player's own row highlighted (bold + different background color)
- [ ] `is_you` flag from API used to identify
- [ ] Always visible: if player is below scroll, show indicator
