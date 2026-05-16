# Epic 2: Game Engine (Server-Side Core Logic)

> **Priority**: P0  
> **Status**: 42 Done, 3 Scaffolded, 3 TODO (48 total)  
> **Owner**: Core team  
> **Sprint**: 1 (models), 2-3 (hardening), 5 (achievements)

---

## Epic Description

The game engine is the authoritative source of truth for all game state. It runs server-side, processes player actions, advances the simulation tick-by-tick, manages catastrophe events, and calculates scores. All game logic lives here — the client is a "dumb" renderer that displays state received from the server.

**Key Design Principles**:
- **Server-authoritative**: All state mutations happen in the engine. Client sends requests; server validates and applies.
- **Deterministic**: Given the same initial state + actions, the engine always produces the same result.
- **Async-first**: The tick loop runs as an asyncio task alongside the FastAPI server.
- **Single-game**: One engine instance serves one game session (simplifies concurrency model).

---

## Feature 2.1 — Data Models (Pydantic)

### Overview
All game state is represented as Pydantic v2 models — validated, serializable, and type-safe. These models are the shared language between engine, server API, and client.

---

### Story 2.1.1 — GameState Model

**As a** developer  
**I want** a single root model representing the entire game state  
**So that** the game can be serialized, inspected, and transmitted as a single object

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `game_id` (UUID), `phase` (GamePhase enum), `players` (dict[str, Player]), `catastrophe_schedule` (list[CatastropheEvent]), `market` (MarketState), `settings` (GameSettings), `elapsed_ticks` (int), `created_at` (datetime)
- [ ] `GamePhase` enum values: `lobby`, `setup`, `playing`, `catastrophe`, `scoring`, `finished`
- [ ] Serializes to JSON via `.model_dump()`
- [ ] Can be reconstructed from JSON via `GameState.model_validate(data)`

---

### Story 2.1.2 — Player Model

**As a** developer  
**I want** a player model with identity, auth, connection state, and colony  
**So that** multi-player state is tracked per-player with proper authentication

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `player_id` (UUID, auto-generated), `name` (str, 1-20 chars), `token` (UUID, auto-generated for auth), `connected` (bool), `ready` (bool), `is_host` (bool), `colony` (Colony | None)
- [ ] `player_id` and `token` are generated on construction (uuid4)
- [ ] `colony` is None until SETUP phase completes
- [ ] Token is never exposed to other players (used for request auth)

---

### Story 2.1.3 — Colony Model

**As a** developer  
**I want** a colony model representing a player's entire settlement state  
**So that** all per-player game state is encapsulated in one structure

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `name` (str), `location` (Location enum), `specialization` (Specialization enum), `resources` (Resources), `buildings` (list[Building]), `workers` (WorkerAllocation), `population` (int), `max_population` (int), `morale` (float, 0.5-1.5), `score` (float)
- [ ] `Location` enum: `coast`, `mountain`, `plains`, `forest`, `desert`
- [ ] `Specialization` enum: `military`, `trade`, `science`, `agriculture`
- [ ] Default colony is initialized with starting resources from config + location modifiers

---

### Story 2.1.4 — Resources Model

**As a** developer  
**I want** a resources model with four tracked resource types  
**So that** resource state is validated and operations are clean

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `food` (float, ge=0), `materials` (float, ge=0), `knowledge` (float, ge=0), `gold` (float, ge=0)
- [ ] Non-negative validation on all fields (Pydantic `ge=0`)
- [ ] Helper methods or operators for adding/subtracting resources (with floor at 0)

---

### Story 2.1.5 — Building Model

**As a** developer  
**I want** a building model tracking construction state and health  
**So that** building lifecycle (construct → use → damage → repair → destroy) is represented

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `building_type` (str — references building ID from JSON), `level` (int, 0-3), `health` (float), `max_health` (float), `under_construction` (bool), `construction_progress` (float, 0.0-1.0), `construction_target` (int — target level being built toward)
- [ ] Level 0 = building slot exists but building not yet constructed
- [ ] `health <= 0` = building destroyed, effects removed
- [ ] `under_construction = True` means building is being built/upgraded, no effects apply yet

---

### Story 2.1.6 — CatastropheEvent Model

**As a** developer  
**I want** a model for scheduled and resolved catastrophe events  
**So that** catastrophe state can be tracked throughout the game

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `catastrophe_id` (str — references catastrophe from JSON), `scheduled_tick` (int — which tick it fires), `resolved` (bool), `results` (dict[str, CatastropheResult] — player_id → results)
- [ ] `CatastropheResult`: `population_lost` (int), `food_lost` (float), `materials_lost` (float), `knowledge_lost` (float), `gold_lost` (float), `buildings_damaged` (list[str]), `mitigation_applied` (dict[str, float])
- [ ] `resolved = False` until catastrophe is processed, then `True`

---

### Story 2.1.7 — MarketState Model

**As a** developer  
**I want** a market model tracking prices, stock, and history  
**So that** the NPC trading system has proper state

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `prices` (dict[str, float] — resource → buy price), `stock` (dict[str, int] — resource → available units), `price_history` (list[dict] — snapshots per round)
- [ ] Prices are always positive floats
- [ ] Stock is always non-negative integers
- [ ] Sell price = buy price × (1 - MARKET_SPREAD)

---

### Story 2.1.8 — GameSettings Model

**As a** developer  
**I want** configurable game settings selectable at game creation  
**So that** hosts can choose game length and difficulty

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Fields: `preset` (str: "quick"/"standard"/"extended"), `max_players` (int, default 250), `num_catastrophes` (int, 4-6), `catastrophe_interval_ticks` (int), `allow_late_join` (bool), `game_duration_target_minutes` (int)
- [ ] Presets:
  - Quick: 30 min, 4 catastrophes, ~7 min intervals
  - Standard: 45 min, 5 catastrophes, ~8 min intervals
  - Extended: 60 min, 6 catastrophes, ~9 min intervals
- [ ] Host can override individual settings after selecting a preset

---

### Story 2.1.9 — Action Models

**As a** developer  
**I want** typed action models for every player action  
**So that** action validation is clean and actions can be serialized/logged

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `ActionType` enum: `build`, `upgrade`, `allocate_workers`, `trade_buy`, `trade_sell`, `demolish`, `repair`
- [ ] Each action type has a corresponding request model:
  - `BuildAction`: `building_type` (str)
  - `UpgradeAction`: `building_type` (str)
  - `AllocateWorkersAction`: `allocation` (dict[str, int] — role → count)
  - `TradeBuyAction`: `resource` (str), `amount` (int)
  - `TradeSellAction`: `resource` (str), `amount` (int)
  - `DemolishAction`: `building_type` (str)
  - `RepairAction`: `building_type` (str)
- [ ] All models validate input ranges (positive amounts, valid building_type, etc.)

---

## Feature 2.2 — Game State Machine

### Overview
The game progresses through a fixed sequence of phases. The state machine enforces valid transitions and phase-specific behavior — e.g., you can't build during LOBBY, can't trade during CATASTROPHE.

**Phase flow**: `LOBBY → SETUP → PLAYING ↔ CATASTROPHE → ... → SCORING → FINISHED`

---

### Story 2.2.1 — State Machine Core

**As a** developer  
**I want** a state machine that enforces valid phase transitions  
**So that** the game can never enter an invalid state

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Valid transitions:
  - LOBBY → SETUP (via host start)
  - SETUP → PLAYING (all players confirmed or timeout)
  - PLAYING → CATASTROPHE (catastrophe timer triggers)
  - CATASTROPHE → PLAYING (catastrophe resolved)
  - PLAYING → SCORING (all catastrophes resolved + final tick)
  - SCORING → FINISHED (scores calculated)
- [ ] Invalid transitions raise `InvalidTransitionError` with message: `"Cannot transition from {current} to {target}"`
- [ ] Current phase is always queryable: `engine.state.phase`
- [ ] Phase change broadcasts event to all connected clients

**Technical Notes**:
- Transitions are method calls on GameEngine: `start_game()`, `complete_setup()`, `trigger_catastrophe()`, `resolve_catastrophe()`, `end_game()`
- Each transition method validates preconditions before mutating state

---

### Story 2.2.2 — LOBBY Phase Logic

**As a** player  
**I want** to join a game lobby, see other players, and ready up  
**So that** the game doesn't start until enough players are prepared

**Status**: 🔨 Scaffolded

**Implementation Notes**:
- Name uniqueness enforced (case-insensitive); remove_player soft-disconnects only, no leave/kick

**Acceptance Criteria**:
- [ ] Players can join freely while in LOBBY phase
- [ ] Each player has a `ready` toggle (default False)
- [ ] Player list is broadcast to all on join/leave/ready change
- [ ] Host can start game when at least 1 player is ready (including self)
- [ ] Non-host calling start gets `PermissionError`
- [ ] Max player limit enforced (default 250): joining at capacity returns error
- [ ] Player names must be unique within the lobby (case-insensitive)
- [ ] Players can leave lobby (removed from player list)

**Not yet implemented**:
- Leave/kick support
- Settings adjustment by host

---

### Story 2.2.3 — SETUP Phase Logic

**As a** player  
**I want** a timed selection period to choose my location and specialization  
**So that** I can make a strategic decision without holding up the game forever

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] On entering SETUP: 90-second countdown begins
- [ ] Each player submits: `{location: str, specialization: str}`
- [ ] Selections are validated against enum values
- [ ] Multiple players CAN choose the same location/specialization (no exclusivity)
- [ ] If player doesn't submit before timeout: random location + agriculture (safe default)
- [ ] Once all players have submitted (or timeout): transition to PLAYING
- [ ] Colony is initialized for each player: starting resources adjusted by location, bonuses applied from specialization
- [ ] Initial worker allocation: evenly distributed across farming/mining/research

**Not yet implemented**:
- Countdown broadcast to clients every few seconds
- "Waiting for X players" status updates

---

### Story 2.2.4 — PLAYING Phase Logic

**As a** player  
**I want** to take actions (build, trade, allocate workers) while the game advances in real-time  
**So that** I can manage my settlement strategically between catastrophes

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Player actions are accepted and validated (Epic 2.3, 2.4, 2.6)
- [ ] Server tick runs every 2 seconds (configurable):
  - Resource production calculated for all colonies
  - Food consumption applied
  - Construction progress advanced
  - Population growth/starvation checked
  - Morale updated
- [ ] Catastrophe timer counts down; when it hits 0, transition to CATASTROPHE
- [ ] State updates broadcast to clients every tick (via WebSocket)
- [ ] Actions during CATASTROPHE phase are rejected with clear error

---

### Story 2.2.5 — CATASTROPHE Phase Logic

**As a** player  
**I want** catastrophes to create dramatic, consequential events with clear results  
**So that** the game has tension and my preparation choices matter

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] On entering CATASTROPHE phase:
  1. All player actions are frozen (rejected with `"Actions not allowed during catastrophe"`)
  2. Catastrophe event is identified from schedule
  3. Damage calculated per player (see Epic 2.5)
  4. Damage applied to all colonies simultaneously
  5. Results generated and broadcast to all players
  6. 60-second display period (for clients to show dramatic reveal)
  7. Transition back to PLAYING (or to SCORING if final catastrophe)
- [ ] Workers auto-reallocated if population drops below total allocation
- [ ] Buildings at 0 HP have effects removed immediately
- [ ] Market refreshes after catastrophe (prices may shift)
- [ ] If this was the last scheduled catastrophe: game continues for 2 more minutes, then SCORING

---

### Story 2.2.6 — SCORING Phase Logic

**As a** player  
**I want** fair, transparent final scoring  
**So that** I understand why I won or lost and what I could have done better

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Score formula: `(population × 10) + (total_resources × 1) + (buildings_health × 5) + (knowledge × 3) + (morale × 20)`
- [ ] Players ranked by score descending
- [ ] Tie-breaking: higher population wins; if still tied, fewer total deaths wins
- [ ] Final leaderboard broadcast to all clients
- [ ] Phase transitions to FINISHED after scores sent
- [ ] Game is now read-only — no further state mutations

---

### Story 2.2.7 — Async Tick Loop

**As a** developer  
**I want** a reliable async tick loop that doesn't drift over a 60-minute game  
**So that** production rates and catastrophe timing are predictable

**Status**: ✅ Done

**Implementation Notes**:
- Drift-compensated via time.monotonic(), tested

**Acceptance Criteria**:
- [ ] Tick loop starts when game enters PLAYING phase
- [ ] Fires every `SERVER_TICK_INTERVAL` seconds (default 2.0)
- [ ] Compensates for processing time (if tick takes 0.1s, waits 1.9s not 2.0s)
- [ ] Increments `state.elapsed_ticks` each iteration
- [ ] Calls `_process_all_colonies()` for production/consumption
- [ ] Checks catastrophe schedule against current tick
- [ ] Broadcasts state update event after each tick
- [ ] Stops when game leaves PLAYING phase (catastrophe pause or game end)
- [ ] Resumes when CATASTROPHE → PLAYING transition occurs
- [ ] Drift over 60 minutes < 5 seconds

**Technical Notes**:
- Implemented with `asyncio.create_task()` and `asyncio.sleep()` with time-correction
- The tick loop is the engine's heartbeat — all time-dependent logic keys off tick count

---

## Feature 2.3 — Resource System

### Overview
Resources are the core economic layer. Four resources (food, materials, knowledge, gold) are produced by workers, consumed by population, spent on buildings, and traded at market. The system creates tension between growth (more population = more production but more consumption) and investment (buildings cost resources but provide multipliers).

---

### Story 2.3.1 — Resource Production Calculator

**As a** player  
**I want** my resource production to reflect my location, specialization, workers, buildings, and morale  
**So that** my strategic choices compound into meaningful advantages

**Status**: ✅ Done

**Implementation Notes**:
- Spec modifiers applied; tested: agriculture/science/military bonuses verified

**Acceptance Criteria**:
- [ ] Per-tick production formula for each resource:
  ```
  production = BASE_RATE
             × location_modifier        (from locations.json)
             × specialization_modifier   (from specializations.json)
             × (workers_in_role / total_population)  (worker ratio)
             × morale                    (0.5 - 1.5 multiplier)
             × building_bonus            (1.0 + sum of relevant building effects)
  ```
- [ ] Base rates (per tick): food=2.0, materials=1.5, knowledge=1.0, gold=1.0
- [ ] Zero workers in a role = zero production for that resource
- [ ] All modifiers stack multiplicatively
- [ ] Production added to current resources (capped at capacity)

**Example calculation**:
- Plains location (food modifier 1.2) + Agriculture spec (+40% food = ×1.4) + 10/20 workers farming (ratio 0.5) + morale 1.1 + Farm L2 (+60% = ×1.6)
- Food/tick = 2.0 × 1.2 × 1.4 × 0.5 × 1.1 × 1.6 = **2.96 food per tick**

---

### Story 2.3.2 — Food Consumption & Starvation

**As a** player  
**I want** population to consume food and starve if I run out  
**So that** food management is a core strategic tension

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Each tick: food consumed = `population × BASE_FOOD_CONSUMPTION_PER_POP` (default 0.5)
- [ ] If `food >= consumption`: food decremented normally
- [ ] If `food < consumption` (starvation):
  - Food set to 0
  - Population decreases by `STARVATION_DEATH_PER_TICK` (default 1)
  - Morale decreases by `MORALE_STARVATION_PENALTY` (default 0.05)
  - Workers auto-reallocated (proportional reduction across all roles)
- [ ] At population 0: game continues (player is "dead" — score frozen, can't act, but still sees events)
- [ ] Starvation deaths are logged for end-game statistics

---

### Story 2.3.3 — Morale System

**As a** player  
**I want** morale to reflect my settlement's well-being and affect all production  
**So that** keeping my people happy is strategically important

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Morale range: 0.5 (minimum) to 1.5 (maximum), default 1.0
- [ ] Morale affects all production as a direct multiplier
- [ ] Morale changes per tick:
  - `+0.02` if food surplus (production > consumption)
  - `-0.05` if starving (food = 0)
  - `-0.10` per population death this tick
  - `+0.01` per successful trade completed this tick
  - `+0.05` if survived catastrophe with < average damage
  - `-0.05` if suffered catastrophe with > average damage
- [ ] Morale is clamped to [0.5, 1.5] after all adjustments
- [ ] Recovery is slow, decline can be fast — losing morale is easier than gaining it

---

### Story 2.3.4 — Resource Capacity

**As a** player  
**I want** resource storage limits that I can expand with buildings  
**So that** hoarding requires investment and there's tension between spending vs saving

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Base capacities: food=500, materials=500, knowledge=200, gold=300
- [ ] Warehouse building increases all capacities: L1=+200, L2=+500, L3=+1000
- [ ] Production that would exceed capacity is lost ("overflow" — wasted)
- [ ] Capacity displayed to player: `"Food: 450/500"` or `"Food: 450/700"` (with warehouse)
- [ ] Capacity update recalculated whenever a warehouse is built/upgraded/destroyed

---

### Story 2.3.5 — Worker Allocation

**As a** player  
**I want** to distribute my population across specialized roles  
**So that** I can focus production on the resources I need most

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] 6 worker roles: `farming`, `mining`, `research`, `construction`, `defense`, `medicine`
- [ ] Allocation must exactly sum to current population (validated on submit)
- [ ] Allocation can be changed at any time during PLAYING phase (instant, no cooldown)
- [ ] Each role's contribution:
  - `farming`: drives food production (worker ratio for food)
  - `mining`: drives materials production
  - `research`: drives knowledge production
  - `construction`: speeds building construction (progress per tick)
  - `defense`: reduces catastrophe damage (direct mitigation factor)
  - `medicine`: reduces population death from catastrophes, speeds morale recovery
- [ ] On population death: workers auto-reduced proportionally across all roles
- [ ] Initial allocation: population ÷ 6 (rounded, remainder to farming)

---

### Story 2.3.6 — Population Growth

**As a** player  
**I want** my population to slowly grow when conditions are good  
**So that** successful resource management is rewarded with compounding production

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Growth check each tick: `food > population × 1.5` (50% surplus threshold)
- [ ] Growth rate: +1 population per 15 ticks when conditions met (~30 seconds real time)
- [ ] Growth capped at `max_population` (base 50, increased by housing-type buildings)
- [ ] Agriculture specialization: growth rate increased by 20% (every 12 ticks instead of 15)
- [ ] Hospital L3 bonus: +1 additional growth per cycle
- [ ] Population growth increases worker pool (added to farming by default)

---

## Feature 2.4 — Building System

### Overview
Buildings provide permanent bonuses, catastrophe mitigation, and special abilities. The construction process requires resources upfront and construction workers over time. Buildings can be damaged by catastrophes and repaired with materials.

---

### Story 2.4.1 — Build Action

**As a** player  
**I want** to start constructing a building by spending resources  
**So that** I can invest in long-term bonuses and catastrophe protection

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Player selects building type to construct
- [ ] Validation:
  - Building type exists in `buildings.json`
  - Player doesn't already have this building at max level
  - Player doesn't already have this building under construction
  - Player has sufficient resources for Level 1 cost
- [ ] On success:
  - Resources deducted (level 1 costs from `buildings.json`)
  - Building entry created: `level=0, under_construction=True, construction_progress=0.0, construction_target=1`
  - Response: `{"status": "construction_started", "building": "farm", "target_level": 1}`
- [ ] On failure: resources NOT deducted, error returned with reason

---

### Story 2.4.2 — Construction Progress

**As a** player  
**I want** buildings to be constructed over time based on my construction workers  
**So that** workforce allocation creates meaningful trade-offs

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Each tick: `progress += (construction_workers / total_population) × CONSTRUCTION_SPEED_PER_WORKER`
- [ ] When `progress >= 1.0`:
  - Building level set to `construction_target`
  - `under_construction = False`
  - `health = max_health` for new level
  - Building effects now apply
  - Notification sent to player: `"Farm Level 1 complete!"`
- [ ] Workshop building reduces build time: L1=-10%, L2=-20%, L3=-30% (applied as speed multiplier)
- [ ] Zero construction workers = zero progress (building stalls but doesn't regress)
- [ ] Multiple buildings can be under construction simultaneously (progress shared across all)

---

### Story 2.4.3 — Building Effects

**As a** player  
**I want** completed buildings to provide bonuses to my settlement  
**So that** investment in construction pays off with compounding advantages

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Effects apply immediately when construction completes
- [ ] Effects are removed immediately if building is destroyed (health → 0)
- [ ] Effects scale with building level (see building table in Epic 1 Story 1.2.2)
- [ ] Effect types:
  - Production bonuses: additive multiplier to relevant resource (Farm L1: food production ×1.3)
  - Capacity bonuses: flat addition to resource caps (Warehouse L1: +200 all)
  - Mitigation: reduces specific catastrophe damage (Hospital L1: -20% plague deaths)
  - Special: unique mechanics (Watchtower: catastrophe hints, Market: trade spread reduction)
- [ ] Multiple buildings' effects stack (Farm L2 ×1.6 + agriculture spec ×1.4 = ×2.24 food bonus)
- [ ] Partial health reduces effectiveness proportionally: `effective_bonus = bonus × (health / max_health)`

---

### Story 2.4.4 — Building Upgrades

**As a** player  
**I want** to upgrade buildings to higher levels for better bonuses  
**So that** I have a long-term investment path for each building

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Upgrade action: same as build but targets next level (L1→L2 or L2→L3)
- [ ] Preconditions:
  - Building must exist at current level (can't skip from L0 to L2)
  - Building must NOT be under construction
  - Building must NOT be destroyed (health > 0)
  - Player has resources for upgrade cost
- [ ] Upgrade costs from `buildings.json` level costs
- [ ] During upgrade: existing effects continue at current level (upgrade doesn't disable building)
- [ ] On completion: effects upgraded to new level, max_health updated, health set to new max

---

### Story 2.4.5 — Building Destruction (from Catastrophe)

**As a** player  
**I want** buildings to take damage from catastrophes proportional to severity  
**So that** catastrophe preparation (walls, barracks) has tangible value

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Catastrophe damage to buildings: `damage = base_building_damage × vulnerability_modifier × (1 - wall_mitigation)`
- [ ] Damage applied to building HP
- [ ] If HP reaches 0: building is destroyed
  - Level set to 0
  - All effects removed immediately
  - Building can be reconstructed (starts from L1 again, costs L1 resources)
- [ ] Partial damage: building still functions but at reduced effectiveness
  - `effective_bonus = full_bonus × (current_health / max_health)`
- [ ] Catastrophe can damage multiple buildings (infrastructure-type catastrophes target 2-3 random buildings)

---

### Story 2.4.6 — Building Repair

**As a** player  
**I want** to spend materials to repair damaged buildings  
**So that** catastrophe damage isn't permanent if I invest in recovery

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Repair action: spend materials to restore building health
- [ ] Cost: `materials_cost = (max_health - current_health) × 0.5` (50% of max health value in materials)
- [ ] Repair is instant (no construction time) — reflects emergency patching
- [ ] Cannot repair a destroyed building (must rebuild from L1)
- [ ] Cannot repair a building at full health
- [ ] Cannot repair if insufficient materials

---

### Story 2.4.7 — Building Demolition

**As a** player  
**I want** to voluntarily destroy a building to recover some resources  
**So that** I can pivot my strategy if a building is no longer needed

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Demolish action: remove building, return 50% of original construction cost
- [ ] Only works on completed buildings (not under construction)
- [ ] Only works on buildings with level > 0
- [ ] Resources returned for current level's cost × 50%
- [ ] Building removed from colony (slot freed for rebuilding)
- [ ] Effects removed immediately
- [ ] Instant action (no construction time)

---

## Feature 2.5 — Catastrophe System

### Overview
Catastrophes are the game's core dramatic beats — timed events that test each player's preparation. The system selects catastrophes ensuring progressive difficulty and fair aggregate challenge across all location/specialization combinations.

---

### Story 2.5.1 — Catastrophe Selection Algorithm

**As a** game designer  
**I want** catastrophes selected to ensure fair, progressive difficulty  
**So that** no player is systematically advantaged or disadvantaged by the random catastrophe sequence

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Input: player location distribution, game settings (num_catastrophes, preset)
- [ ] Selection rules:
  1. Draw from each category (population, resource, infrastructure, economic) in round-robin
  2. Severity progresses: round 1-2 draw from tier 1-2, round 3-4 from tier 2-3, final round from tier 3
  3. No two consecutive catastrophes from the same category
  4. Maximum aggregate vulnerability variance across players ≤ 20%
- [ ] Output: ordered list of catastrophe_ids with scheduled ticks
- [ ] Algorithm is deterministic given same player setup + random seed
- [ ] If constraint can't be satisfied exactly: best-effort with logging

**Technical Notes**:
- Aggregate vulnerability = sum of all damage multipliers for a player across all selected catastrophes
- The goal is that Coast players face roughly the same total challenge as Mountain players
- Not perfectly balanced (would over-constrain selections) — target is "no one gets screwed"

---

### Story 2.5.2 — Catastrophe Scheduling

**As a** player  
**I want** catastrophes spaced evenly throughout the game with slight unpredictability  
**So that** I can plan but not perfectly predict timing

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Base interval: `game_duration / (num_catastrophes + 1)` (evenly spaced)
- [ ] Jitter: ±60 seconds randomness added to each scheduled time
- [ ] First catastrophe: no earlier than 6 minutes into game
- [ ] Last catastrophe: no later than 5 minutes before game end
- [ ] Minimum gap between consecutive catastrophes: 5 minutes
- [ ] Schedule is determined at game start (not dynamically during play)
- [ ] Countdown is visible to players (without jitter — they see "approximately" when)

---

### Story 2.5.3 — Catastrophe Damage Calculation

**As a** player  
**I want** damage calculated based on my preparation (buildings, workers, location)  
**So that** my strategic choices directly affect my survival

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Per-player damage formula:
  ```
  effective_damage = base_damage
                   × location_vulnerability[player_location]
                   × (1 - building_mitigation)
                   × (1 - defense_worker_mitigation)
                   × (1 - wall_general_mitigation)
  ```
- [ ] `building_mitigation`: from specific mitigation building (e.g., Hospital vs plague) = `level_factor × building_health_ratio`
- [ ] `defense_worker_mitigation`: `min(0.3, defense_workers / total_population × 0.6)` — caps at 30%
- [ ] `wall_general_mitigation`: Wall building reduces ALL damage: L1=15%, L2=30%, L3=45%
- [ ] Minimum damage: even fully mitigated catastrophe deals 10% of base (never zero)
- [ ] Damage applied to: population, food, materials, knowledge, gold, buildings (varies by catastrophe type)

---

### Story 2.5.4 — Damage Application

**As a** developer  
**I want** catastrophe damage applied atomically and consistently  
**So that** all players are damaged simultaneously and state remains consistent

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] All player damage calculated FIRST, then ALL applied simultaneously (not sequential)
- [ ] Population loss: integer, minimum 0 (can't go negative)
- [ ] Resource loss: float, floored at 0
- [ ] Building damage: reduce HP by calculated amount, check for destruction
- [ ] Worker reallocation: if pop drops below total workers, reduce proportionally
- [ ] Morale impact applied based on damage relative to average
- [ ] Market refresh triggered after damage applied (prices may react)

---

### Story 2.5.5 — Catastrophe Results Generation

**As a** player  
**I want** to see exactly what happened to my settlement and how I compared to others  
**So that** I understand the consequence and feel the drama

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Results per player include:
  - Population lost (and new total)
  - Each resource lost
  - Buildings damaged (which ones, how much HP lost)
  - Mitigation that helped: `"Your Hospital saved 8 people from plague"`
  - Comparison to average: `"You lost 3 population (average: 7)"`
- [ ] Results broadcast to each player individually (they only see their own detail + averages)
- [ ] Results stored on CatastropheEvent model for post-game review
- [ ] Summary statistics: total dead across all players, most/least damaged player

---

### Story 2.5.6 — Watchtower Hints

**As a** player  
**I want** early warning about upcoming catastrophes if I built a Watchtower  
**So that** I'm rewarded for investing in intelligence/preparation

**Status**: ✅ Done

**Implementation Notes**:
- Wired to client: colony.py reads watchtower_hint from state

**Acceptance Criteria**:
- [ ] Watchtower L1: reveals category of next catastrophe (e.g., "Next threat: Population category")
- [ ] Watchtower L2: reveals exact type (e.g., "Next threat: The Great Plague")
- [ ] Watchtower L3: reveals type AND approximate timing (e.g., "The Great Plague in ~3 minutes")
- [ ] Science specialization bonus: hints one tier better (L1 gets L2 info, L2 gets L3)
- [ ] Hint displayed in colony management screen between catastrophes
- [ ] Hint updates after each catastrophe resolves (shows info about the next one)
- [ ] No watchtower = no hint (just generic countdown timer)

---

### Story 2.5.7 — Location-Specific Flavor Text

**As a** player  
**I want** catastrophe descriptions to mention my specific location  
**So that** the narrative feels personalized and immersive

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Each catastrophe has variant flavor text per location (or at least per vulnerable/resistant)
- [ ] Vulnerable location gets alarming text: "The earthquake tears through your mountain settlement, loosening boulders..."
- [ ] Resistant location gets mitigated text: "The coastal winds carry much of the plague away from your settlement..."
- [ ] Neutral location gets standard text
- [ ] Falls back to default flavor text if variant not defined

---

## Feature 2.6 — NPC Market System

### Overview
The market allows players to buy and sell resources at fluctuating NPC-set prices. It provides an economic valve — players with excess of one resource can convert to another, at a cost. Trade specialization reduces that cost.

---

### Story 2.6.1 — Base Price Fluctuation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Base prices: food=1.5, materials=2.0, knowledge=3.0, gold=N/A (gold IS the currency)
- [ ] Each round (after catastrophe): prices recalculated with ±20% random fluctuation
- [ ] Fluctuation uses seeded randomness (reproducible given same game seed)
- [ ] Prices have floor (50% of base) and ceiling (200% of base) — never extreme
- [ ] Price history stored for sparkline display (last 6 values)

---

### Story 2.6.2 — Supply/Demand Price Shifts

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] After drought: food prices rise 30-50%
- [ ] After raid: materials prices rise 20-30%
- [ ] After economic catastrophe: gold prices/all prices shift
- [ ] Shift applied on top of random fluctuation
- [ ] Creates opportunity for prepared players (stockpiled food before drought = can sell high)

---

### Story 2.6.3 — Buy Action

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Player spends gold to buy resources at market buy price
- [ ] `gold_cost = amount × buy_price`
- [ ] Trade specialization discount: 15% off buy price
- [ ] Market L1/L2/L3 building: additional 10/20/30% off spread
- [ ] Must have sufficient gold
- [ ] Must have sufficient market stock
- [ ] Resources added immediately (no delivery time)

---

### Story 2.6.4 — Sell Action

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Player sells resources for gold at sell price
- [ ] `sell_price = buy_price × (1 - MARKET_SPREAD)` (default 0.3 = 30% spread)
- [ ] Trade specialization: spread reduced to 15% (sell_price = buy × 0.85)
- [ ] Market building further reduces spread
- [ ] Must have sufficient resources to sell
- [ ] Gold received immediately

---

### Story 2.6.5 — Market Stock Limits

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Each resource has limited stock per round (first-come-first-served)
- [ ] Default stock: 100 units of each resource per round
- [ ] Stock replenishes fully after each catastrophe (new round)
- [ ] Remaining stock displayed to players
- [ ] Buying reduces stock; selling DOES NOT increase stock (it's NPC-sourced)

---

### Story 2.6.6 — Trade History

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Every trade logged: `{tick, player_id, direction (buy/sell), resource, amount, price_per_unit, total_gold}`
- [ ] History available to player (their own trades) for market screen
- [ ] History used for end-game statistics
- [ ] Shows last 10 trades in market screen panel

---

## Feature 2.7 — Scoring & Leaderboard

### Overview
Final scoring determines the winner. The formula rewards a balanced colony — population, resources, buildings, and knowledge all contribute. Achievements provide bonus points for exceptional play.

---

### Story 2.7.1 — Score Calculation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Formula: `score = (population × 10) + (food + materials + knowledge + gold) × 1 + (sum_building_health × 5) + (knowledge × 3) + (morale × 20)`
- [ ] Scores in typical range: 500-2000 for an average game, 2000+ for excellent play
- [ ] No single factor dominates: a player with high pop but no buildings shouldn't beat a balanced player
- [ ] Displayed as integer (rounded)

---

### Story 2.7.2 — Achievement System

**Status**: ✅ Done

**Implementation Notes**:
- 8 achievements defined in `terminus/data/achievements.json` with id, name, description, icon, bonus_points
- `Colony.achievements: list[str]` field stores earned achievement IDs
- `_check_achievements()` called every tick: Builder (5+ buildings), Scholar (library L3), Populous (200+ pop), Hoarder (max capacity), Fortified (barracks+wall L2+), Trader (10+ trades)
- `_check_catastrophe_achievements()` called after each catastrophe: Survivor (0 pop loss), Untouched (0 building damage)
- Loader: `get_achievements()`, `get_achievement_by_id()` in `terminus/data/loader.py`

**Acceptance Criteria**:
- [ ] 8-10 achievements detected at game end:
  - **First Builder**: first player to complete any building
  - **Untouched**: survived a catastrophe with 0 population loss
  - **Hoarder**: highest total resources at game end
  - **Researcher**: most knowledge at game end
  - **Commander**: highest population at game end
  - **Trader**: most total gold traded (buy+sell volume)
  - **Survivor**: lowest total population loss across all catastrophes
  - **Architect**: most buildings at max level
  - **Comeback Kid**: recovered from lowest score to top 3
  - **Speed Builder**: first to reach Level 3 on any building
- [ ] Each achievement: +50 bonus points (5-10% of typical score)
- [ ] Player can earn multiple achievements
- [ ] Achievements shown on leaderboard alongside player name

---

### Story 2.7.3 — Achievement Bonus Points

**Status**: ✅ Done

**Implementation Notes**:
- `_calculate_scores()` sums `bonus_points` from each earned achievement via `get_achievement_by_id()`
- Achievements included in score output dict: `"achievements": list[str]`
- Bonus points per achievement: 30-60 pts (defined in achievements.json)

**Acceptance Criteria**:
- [ ] Flat +50 points per achievement earned
- [ ] Max possible achievement bonus: 500 (if someone earned all 10, which is virtually impossible)
- [ ] Bonus meaningful but not game-deciding
- [ ] Added after base score calculation

---

### Story 2.7.4 — Leaderboard Ranking

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] All players sorted by final score (descending)
- [ ] Tie-breaking: population → fewer deaths → alphabetical name
- [ ] Ranking is deterministic (same inputs = same ranking)
- [ ] Available during PLAYING phase as "live leaderboard" (current scores)
- [ ] Finalized during SCORING phase

---

### Story 2.7.5 — Per-Round Scoring Snapshots

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Score snapshot taken after each catastrophe resolves
- [ ] Stores: `{tick, player_id, score, rank}` per player
- [ ] Used for post-game score progression display
- [ ] Shows who was leading at each point in the game

---

### Story 2.7.6 — Game Statistics

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Tracked across all players:
  - Total population lost to catastrophes
  - Total population lost to starvation
  - Total resources produced
  - Total resources traded
  - Total buildings constructed
  - Total buildings destroyed
  - Most devastating catastrophe (highest total damage)
  - Longest survival streak (ticks without population loss)
- [ ] Displayed on final leaderboard screen
