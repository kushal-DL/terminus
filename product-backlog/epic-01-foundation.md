# Epic 1: Project Foundation & Infrastructure

> **Priority**: P0  
> **Status**: ✅ Done (1.1, 1.2) | ⬜ TODO (1.3 Rename)  
> **Owner**: Core team  
> **Sprint**: 1 (scaffolding), 2 (rename)

---

## Epic Description

Establish the foundational project structure, package configuration, data definitions, and development workflow for Terminus (currently named Colony). This epic includes all the scaffolding needed before any game logic can be written — directory layout, dependency management, configuration system, static game data files, and the eventual rename from `colony` to `terminus`.

---

## Feature 1.1 — Project Scaffolding

### Overview
Set up the Python package structure with proper build tooling, entry points, CLI argument parsing, and configuration system. The game must be installable via `pip install .` and runnable via `python -m terminus` (or `terminus` console command).

---

### Story 1.1.1 — Package Configuration (pyproject.toml)

**As a** developer  
**I want** a properly configured `pyproject.toml` with all metadata, dependencies, and build settings  
**So that** the game can be installed as a Python package and dependencies are managed declaratively

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `pyproject.toml` exists at repository root
- [ ] Project name is set (currently `colony-game`, will become `terminus-game`)
- [ ] All runtime dependencies listed with compatible version ranges:
  - `textual>=0.40,<1.0` — TUI framework
  - `fastapi>=0.100,<1.0` — HTTP/WS server
  - `uvicorn[standard]>=0.20,<1.0` — ASGI server
  - `httpx>=0.24,<1.0` — async HTTP client
  - `websockets>=11.0,<14.0` — WebSocket client
  - `pydantic>=2.0,<3.0` — data models
- [ ] Build backend is `hatchling` with `[tool.hatch.build.targets.wheel] packages = ["colony"]`
- [ ] Console script entry point defined: `colony = "colony.__main__:main"`
- [ ] `requires-python = ">=3.11"` constraint set
- [ ] `pip install .` succeeds without errors on Python 3.11+

**Technical Notes**:
- Using `hatchling` because it's fast, well-maintained, and handles src-less layouts
- Version pinning uses compatible ranges (`>=X,<Y`) not exact pins — allows patch updates
- The `packages` setting is needed because the project name differs from the directory name

---

### Story 1.1.2 — Package Directory Structure

**As a** developer  
**I want** a clean, organized package directory with proper module boundaries  
**So that** imports are clear and the codebase scales without circular dependencies

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Directory tree:
  ```
  colony/
    __init__.py
    __main__.py
    config.py
    server/
      __init__.py
      app.py
      engine.py
      models.py
    client/
      __init__.py
      app.py
      api.py
      screens/
        __init__.py
        main_menu.py
        lobby.py
        setup.py
        colony.py
        build.py
        workers.py
        market.py
        catastrophe.py
        leaderboard.py
        help.py
      widgets/
        __init__.py
    data/
      __init__.py
      loader.py
      catastrophes.json
      buildings.json
      locations.json
      specializations.json
  ```
- [ ] All `__init__.py` files exist (may be empty)
- [ ] No circular imports between `server/` and `client/`
- [ ] `server/` has zero dependency on `client/` (server can run standalone)

**Technical Notes**:
- `server/` is the FastAPI game server — runs the engine, exposes REST+WS API
- `client/` is the Textual TUI — connects to server via HTTP/WS
- `data/` holds static JSON game data + the loader utility
- `widgets/` will hold reusable Textual Widget subclasses (Epic 7)

---

### Story 1.1.3 — CLI Entry Point (__main__.py)

**As a** player  
**I want** to launch the game with simple CLI flags for different modes  
**So that** I can host a server, join as client, or run both together easily

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `python -m colony` launches the full TUI client (which also starts an embedded server)
- [ ] `--host 0.0.0.0` sets the server bind address (default: `0.0.0.0`)
- [ ] `--port 8080` sets the server port (default: `8080`)
- [ ] `--public` attempts to start a cloudflared tunnel for public internet access
- [ ] `--server-only` runs only the FastAPI server without the TUI (headless mode)
- [ ] `--verbose` enables DEBUG level logging to stdout
- [ ] `--help` shows usage information
- [ ] Invalid arguments produce helpful error messages
- [ ] Exit code 0 on clean shutdown, non-zero on errors

**Technical Notes**:
- Uses `argparse` from stdlib (no click dependency needed)
- In normal mode: starts uvicorn server in a background thread, then launches Textual app in main thread
- In `--server-only` mode: runs uvicorn.run() directly (blocking)
- The `--public` flag triggers cloudflared tunnel subprocess (Epic 3.3)

---

### Story 1.1.4 — Game Configuration Constants

**As a** developer  
**I want** all tunable game parameters in a single config module  
**So that** balance adjustments don't require hunting through game logic code

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/config.py` contains all game constants organized by category
- [ ] Categories include:
  - **Timing**: `SETUP_PHASE_SECONDS=90`, `SERVER_TICK_INTERVAL=2.0`, `CATASTROPHE_PAUSE_SECONDS=60`
  - **Resources**: `STARTING_RESOURCES` dict, `BASE_PRODUCTION_PER_TICK` dict, `BASE_FOOD_CONSUMPTION_PER_POP=0.5`
  - **Population**: `STARTING_POPULATION=20`, `MAX_POPULATION_BASE=50`, `STARVATION_DEATH_PER_TICK=1`
  - **Morale**: `MORALE_MIN=0.5`, `MORALE_MAX=1.5`, `MORALE_STARVATION_PENALTY=0.05`
  - **Buildings**: `MAX_BUILDING_LEVEL=3`, `CONSTRUCTION_SPEED_PER_WORKER=0.1`
  - **Market**: `MARKET_SPREAD=0.3`, `TRADE_SPEC_DISCOUNT=0.15`, `PRICE_FLUCTUATION=0.2`
  - **Scoring**: `SCORE_WEIGHT_POPULATION=10`, `SCORE_WEIGHT_RESOURCES=1`, `SCORE_WEIGHT_BUILDINGS=5`
  - **Network**: `DEFAULT_HOST`, `DEFAULT_PORT=8080`, `WS_HEARTBEAT_INTERVAL=15`
- [ ] Constants are plain Python values (not environment variables) — balance tuning is code-level
- [ ] No magic numbers in game logic files — all reference `config.CONSTANT_NAME`

**Technical Notes**:
- Config is importable as `from colony.config import CONSTANT_NAME` or `from colony import config`
- Some constants (DEFAULT_HOST, DEFAULT_PORT) are overridden by CLI args at runtime
- Future: difficulty presets will multiply groups of constants (Epic 5)

---

### Story 1.1.5 — Logging System

**As a** developer  
**I want** structured logging with a verbose flag  
**So that** I can debug game state issues during development and playtesting

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Normal mode: only WARNING and above logged
- [ ] `--verbose` mode: DEBUG and above logged
- [ ] Log format: `2026-05-15 14:30:22 [terminus.server.engine] DEBUG: Tick 42 processing`
- [ ] Each module uses `logging.getLogger(__name__)`
- [ ] No print statements for debug output — all goes through logging
- [ ] Server tick loop doesn't spam logs in normal mode (only errors/warnings)

---

## Feature 1.2 — Data Definitions

### Overview
Define all static game data in JSON files — catastrophes, buildings, locations, and specializations. These files drive the game mechanics without hardcoding values in Python. A loader module provides validated access with caching.

---

### Story 1.2.1 — Catastrophe Definitions

**As a** game designer  
**I want** all 20 catastrophes defined in a structured JSON file  
**So that** catastrophe content can be tuned without modifying Python code

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/data/catastrophes.json` contains exactly 20 catastrophe definitions
- [ ] Each catastrophe has:
  - `id` — unique string identifier (e.g., `"plague"`, `"earthquake"`, `"drought"`)
  - `name` — display name (e.g., `"The Great Plague"`)
  - `description` — 1-2 sentence mechanical description
  - `flavor_text` — dramatic narrative text shown during event
  - `category` — one of: `"population"`, `"resource"`, `"infrastructure"`, `"economic"`
  - `severity` — integer 1-3 (tier for difficulty progression)
  - `damage` — object with `population_loss`, `food_loss`, `materials_loss`, `knowledge_loss`, `gold_loss`, `building_damage`
  - `vulnerability` — object mapping location_id → damage multiplier (1.0=normal, 1.2=vulnerable, 0.8=resistant)
  - `mitigation` — object mapping building_id → mitigation_factor (0.0-1.0)
- [ ] Categories are evenly distributed: ~5 per category
- [ ] Severity tiers: ~7 at tier 1, ~7 at tier 2, ~6 at tier 3
- [ ] Every catastrophe is mitigatable by at least one building
- [ ] Every location has 3-4 vulnerabilities and 3-4 resistances across all catastrophes

**Technical Notes**:
- Damage values are "base damage" — actual damage = base × vulnerability × (1 - mitigation)
- The selection algorithm (Epic 2.5) uses category and severity for progressive difficulty
- Flavor text should be evocative but brief (1-2 sentences, shown full-screen during event)

---

### Story 1.2.2 — Building Definitions

**As a** game designer  
**I want** all 10 buildings defined with multi-level costs and effects  
**So that** building progression creates meaningful strategic choices

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/data/buildings.json` contains exactly 10 building definitions
- [ ] Buildings: Farm, Mine, Library, Hospital, Barracks, Warehouse, Market, Watchtower, Wall, Workshop
- [ ] Each building has:
  - `id` — unique string (e.g., `"farm"`, `"hospital"`)
  - `name` — display name
  - `description` — what it does
  - `costs` — object with keys `"1"`, `"2"`, `"3"` (per level), each containing `{food, materials, knowledge, gold}`
  - `build_time_ticks` — object with keys `"1"`, `"2"`, `"3"` (ticks to construct per level)
  - `effects` — object with keys `"1"`, `"2"`, `"3"`, each describing bonuses at that level
  - `max_health` — object with keys `"1"`, `"2"`, `"3"` (HP per level)
- [ ] Cost progression: Level 2 costs ~2.5× level 1, Level 3 costs ~3× level 2
- [ ] Build time progression: increases ~1.5× per level
- [ ] Effects include: production bonuses, capacity increases, mitigation factors, special abilities
- [ ] Level 1 of cheapest building (Farm) is affordable within ~2 minutes of game start

**Building effects summary**:
| Building | L1 Effect | L2 Effect | L3 Effect |
|----------|-----------|-----------|-----------|
| Farm | +30% food production | +60% food | +100% food |
| Mine | +30% materials | +60% materials | +100% materials |
| Library | +30% knowledge | +60% knowledge | +100% knowledge, +research speed |
| Hospital | -20% plague deaths | -40% plague deaths | -60% plague deaths, +pop growth |
| Barracks | -20% raid damage | -40% raid damage | -60% raid damage, +defense workers effectiveness |
| Warehouse | +200 resource cap | +500 resource cap | +1000 resource cap |
| Market | -10% trade spread | -20% trade spread | -30% trade spread, +sell prices |
| Watchtower | Category hint for next catastrophe | Exact type hint | Type + timing hint |
| Wall | -15% all damage | -30% all damage | -45% all damage |
| Workshop | -10% build time | -20% build time | -30% build time, -10% costs |

---

### Story 1.2.3 — Location Definitions

**As a** game designer  
**I want** 5 distinct locations with unique modifier profiles  
**So that** location choice creates asymmetric starting conditions and strategic identity

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/data/locations.json` contains exactly 5 locations
- [ ] Each location has:
  - `id` — `"coast"`, `"mountain"`, `"plains"`, `"forest"`, `"desert"`
  - `name` — display name (e.g., `"Coastal Settlement"`)
  - `description` — 2-3 sentence flavor text about the location
  - `production_modifiers` — `{food, materials, knowledge, gold}` multipliers (0.5–1.5 range)
  - `starting_resources` — override for initial resource amounts
  - `vulnerability_profile` — summary of which catastrophe types this location is weak/strong against
- [ ] No location is strictly dominant — each has trade-offs:

| Location | Strengths | Weaknesses |
|----------|-----------|------------|
| Coast | High gold (trade routes), good food (fishing) | Vulnerable to storms/floods, weak materials |
| Mountain | High materials (mining), natural defense | Low food, vulnerable to earthquakes, slow construction |
| Plains | Balanced production, fast construction | No strong bonuses, vulnerable to drought/invasion |
| Forest | High food (hunting/gathering), knowledge (herbs) | Vulnerable to fire, limited gold |
| Desert | High gold (rare minerals), knowledge (ancient ruins) | Very low food, vulnerable to drought, extreme conditions |

---

### Story 1.2.4 — Specialization Definitions

**As a** game designer  
**I want** 4 specializations with distinct bonus profiles  
**So that** players within the same location can differentiate their strategy

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/data/specializations.json` contains exactly 4 specializations
- [ ] Each specialization has:
  - `id` — `"military"`, `"trade"`, `"science"`, `"agriculture"`
  - `name` — display name
  - `description` — what this specialization provides
  - `bonuses` — specific mechanical advantages
- [ ] Specialization bonuses:

| Spec | Primary Bonus | Secondary Bonus | Unique Ability |
|------|--------------|-----------------|----------------|
| Military | +40% defense worker effectiveness | +20% barracks/wall effects | Reduced raid damage even without buildings |
| Trade | +15% gold production, -15% market spread | +10% sell prices | Can trade during catastrophe pause (others can't) |
| Science | +40% knowledge production | -15% build times | Watchtower hints one tier better |
| Agriculture | +40% food production | +20% population growth rate | Food surplus generates small morale bonus |

---

### Story 1.2.5 — Data Loader Module

**As a** developer  
**I want** a validated, cached data loading system  
**So that** JSON data is loaded once, validated for required fields, and accessible throughout the codebase

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `colony/data/loader.py` provides: `get_catastrophes()`, `get_buildings()`, `get_locations()`, `get_specializations()`
- [ ] First call loads from JSON file + validates required fields exist
- [ ] Subsequent calls return cached result (no re-reading file)
- [ ] Missing required field raises `ValueError` with clear message: `"Building 'farm' missing field 'costs'"`
- [ ] Individual lookup functions: `get_building(building_id)`, `get_location(location_id)`, etc.
- [ ] Returns plain dicts (not Pydantic models — those are in `server/models.py`)
- [ ] JSON files are loaded relative to the `data/` package directory (works in installed packages)

**Technical Notes**:
- Uses `importlib.resources` or `pathlib` relative to `__file__` for file location
- Caching via module-level variables (simple, no external caching library)
- Validation is structural (required keys exist) not semantic (values are in range) — semantic validation is in the engine

---

## Feature 1.3 — Rename Refactor: Colony → Terminus

### Overview
Rename the entire package from `colony` to `terminus`. This is a mechanical refactor that touches every file but changes no logic. Must be done as a single atomic commit to preserve git blame utility.

---

### Story 1.3.1 — Rename Package Directory

**As a** developer  
**I want** the package directory renamed from `colony/` to `terminus/`  
**So that** the package name matches the game's identity

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Directory `colony/` renamed to `terminus/`
- [ ] All subdirectories preserved: `terminus/server/`, `terminus/client/`, `terminus/data/`
- [ ] All files within preserved unchanged (content updated in separate stories)
- [ ] Git history tracks this as a rename (not delete + create)

---

### Story 1.3.2 — Update All Python Imports

**As a** developer  
**I want** all `from colony.` and `import colony` statements updated to `terminus`  
**So that** the package is importable under its new name

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Every `.py` file: `from colony.` → `from terminus.`
- [ ] Every `.py` file: `import colony` → `import terminus`
- [ ] No remaining references to `colony` as a Python package name
- [ ] `python -c "import terminus"` succeeds
- [ ] `python -m terminus --help` works

**Estimated scope**: ~30+ files with import changes

---

### Story 1.3.3 — Update Package Configuration

**As a** developer  
**I want** `pyproject.toml` updated for the new name  
**So that** the package installs and runs under the `terminus` name

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] `[project] name = "terminus-game"`
- [ ] `[project.scripts] terminus = "terminus.__main__:main"`
- [ ] `[tool.hatch.build.targets.wheel] packages = ["terminus"]`
- [ ] `pip install .` installs as `terminus-game`
- [ ] `terminus` console command works after install
- [ ] `python -m terminus` works

---

### Story 1.3.4 — Update Test File Imports

**As a** developer  
**I want** `test_engine.py` updated with new import paths  
**So that** the integration test still passes after rename

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] `from terminus.server.engine import GameEngine`
- [ ] `from terminus.server.models import GameSettings, Player, Location, Specialization, ActionType`
- [ ] Test passes with same output as before

---

### Story 1.3.5 — Update Documentation

**As a** developer  
**I want** README and all docs updated with Terminus branding  
**So that** the game presents consistently under its new name

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] `README.md`: all "Colony" → "Terminus", all `colony` commands → `terminus`
- [ ] Install command: `pip install .` then `terminus` or `python -m terminus`
- [ ] No remaining "Colony" references in docs (except historical changelog if any)

---

### Story 1.3.6 — Update Display Text in Code

**As a** developer  
**I want** all user-facing text updated from Colony to Terminus  
**So that** the game UI shows the correct name everywhere

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] `TerminusApp` class name (was `ColonyApp`)
- [ ] `TITLE = "TERMINUS"` (was `"COLONY"`)
- [ ] CLI description: "Terminus — Multiplayer CLI survival strategy game"
- [ ] Screen labels: "CHOOSE YOUR SETTLEMENT SETUP" (was "COLONY SETUP")
- [ ] Any "colony" references in help text, button labels, notifications
- [ ] Subtitle: "The Last Stand Begins Here" (was "Survive. Build. Conquer.")
