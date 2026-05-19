# LLM Benchmark — Game Engine Integration

This document maps the exact integration surface between the benchmark orchestrator and the existing Terminus game engine. It defines what to call, what to bypass, and how to convert the real-time engine into a synchronous turn-based benchmark runner.

---

## Architecture: Headless Mode

```
Normal Game:                          Benchmark Mode:
┌──────────┐    ┌──────────────┐      ┌──────────────────┐
│  TUI     │◄──►│  FastAPI +   │      │  Orchestrator    │
│  Client  │    │  WebSocket   │      │  (direct calls)  │
└──────────┘    └──────┬───────┘      └────────┬─────────┘
                       │                       │
                       ▼                       ▼
                ┌──────────────┐        ┌──────────────┐
                │  GameEngine  │        │  GameEngine  │
                │  (async tick │        │  (manual tick│
                │   loop, 2s)  │        │   advance)   │
                └──────────────┘        └──────────────┘
```

**Key difference:** In normal play, the engine runs an autonomous async tick loop every 2 seconds. In benchmark mode, the orchestrator controls tick advancement explicitly — no timer, no sleep, fully synchronous per-turn.

---

## What to Keep vs Bypass

| Component | Keep | Bypass | Reason |
|-----------|------|--------|--------|
| `GameEngine` core logic | ✓ | | All game rules, validation, production |
| `_tick()` processing | ✓ | | Resource production, construction, catastrophes |
| Action validation | ✓ | | Must accurately reject invalid actions |
| Catastrophe scheduling | ✓ | | Critical for flexibility metrics |
| Scoring calculation | ✓ | | Final scores needed for results |
| Market mechanics | ✓ | | Price volatility, spreads, all needed |
| FastAPI / REST endpoints | | ✓ | No HTTP overhead |
| WebSocket broadcasting | | ✓ | No clients to broadcast to |
| Rate limiting (10/sec API) | | ✓ | Benchmark controls its own pacing |
| Persistence (SQLite saves) | | ✓ | Benchmark records its own data |
| Lobby/ready system | | ✓ | Players added programmatically |
| Setup timer (90s deadline) | | ✓ | Setup assigned instantly |

---

## Step-by-Step: Running a Benchmark Game

### Phase 1: Initialization

```python
from terminus.server.engine import GameEngine
from terminus.server.models import GameSettings, Player, Location, Specialization

# 1. Create engine with settings
settings = GameSettings(preset="standard")  # or "quick" / "extended"
engine = GameEngine(settings=settings)

# 2. Disable unnecessary subsystems
engine._persist = None                        # No SQLite writes
engine.set_broadcast(lambda *a, **k: None)    # No-op broadcasts

# 3. Add players (LLM agents + built-in opponents)
llm_player = Player(name="GPT-4o", is_host=True)
opponent = Player(name="Greedy-Bot", is_host=False)
engine.add_player(llm_player)
engine.add_player(opponent)
```

### Phase 2: Game Setup (Skip Lobby)

```python
# 4. Start game immediately (skip lobby wait)
await engine.start_game(llm_player.player_id)

# 5. Submit location + specialization for each player
#    (In normal play this is a 90-second phase with user input)
await engine.submit_setup(
    llm_player.player_id,
    location=Location.PLAINS,
    specialization=Specialization.AGRICULTURE
)
await engine.submit_setup(
    opponent.player_id,
    location=Location.MOUNTAIN,
    specialization=Specialization.MILITARY
)

# 6. Mark setup complete (transitions to PLAYING phase)
await engine.check_setup_complete()
```

### Phase 3: Turn Loop (Core Benchmark Logic)

```python
for turn in range(1, max_turns + 1):
    # 7. Get state for each player
    llm_state = engine.get_player_state(llm_player.player_id)
    opponent_state = engine.get_player_state(opponent.player_id)

    # 8. Convert engine state → BenchmarkGameState schema
    game_state = convert_to_benchmark_state(llm_state, turn)

    # 9. Send to LLM, get ActionResponse
    response = await llm_adapter.get_action(game_state)

    # 10. Apply LLM's action
    try:
        result = await engine.handle_action(
            llm_player.player_id,
            ActionType(response.action),
            response.params.model_dump()
        )
        valid = True
        rejection = None
    except ValueError as e:
        valid = False
        rejection = str(e)

    # 11. Apply opponent's action (built-in agent)
    opponent_action = greedy_agent.choose_action(opponent_state)
    try:
        await engine.handle_action(
            opponent.player_id,
            opponent_action.type,
            opponent_action.params
        )
    except ValueError:
        pass  # Built-in agents can also fail; just skip

    # 12. Advance one tick (all game logic processes)
    await engine._tick()

    # 13. Record the turn snapshot
    recorder.record_turn(turn, game_state, response, valid, rejection)

    # 14. Check for game end conditions
    if engine.state.phase == GamePhase.FINISHED:
        break
```

### Phase 4: Results

```python
# 15. Get final scores
scores = engine._calculate_scores()

# 16. Store game recording
recording = recorder.finalize(scores)
```

---

## Key Method Signatures

### GameEngine

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `__init__` | `(settings: GameSettings \| None = None)` | `GameEngine` | Settings apply preset defaults |
| `add_player` | `(player: Player)` | `str` (player_id) | Creates colony, assigns defaults |
| `start_game` | `(host_player_id: str)` | `None` | Transitions LOBBY → SETUP |
| `submit_setup` | `(player_id: str, location: Location, specialization: Specialization)` | `None` | Assigns colony attributes |
| `check_setup_complete` | `()` | `None` | Transitions SETUP → PLAYING if all submitted |
| `get_player_state` | `(player_id: str)` | `dict` | Full colony + market + opponents |
| `handle_action` | `(player_id: str, action_type: ActionType, payload: dict)` | `dict` | Raises `ValueError` on invalid |
| `_tick` | `()` | `None` | Process one game tick (async) |
| `_calculate_scores` | `()` | `list[dict]` | Ranked scores for all players |
| `set_broadcast` | `(broadcast_fn)` | `None` | Set event callback |

### GameSettings

```python
class GameSettings(BaseModel):
    preset: Literal["quick", "standard", "extended"] = "standard"
    max_players: int = 6
    num_catastrophes: int = 5        # 4/5/6 for quick/standard/extended
    catastrophe_interval: int = 510  # seconds between catastrophes
    allow_late_join: bool = False
```

### Player

```python
class Player(BaseModel):
    player_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    is_host: bool = False
    # Colony auto-created on add_player()
```

### get_player_state() Return Structure

```python
{
    "game_id": str,
    "phase": str,                    # "playing", "catastrophe", "finished"
    "colony": {
        "resources": {"food": int, "materials": int, "knowledge": int, "gold": int},
        "capacity": {"food": int, "materials": int, "knowledge": int, "gold": int},
        "population": int,
        "population_cap": int,
        "morale": float,
        "workers": {"farming": int, "mining": int, "research": int, "construction": int, "defense": int, "medicine": int},
        "buildings": [{"type": str, "level": int, "health": int, "max_health": int, "under_construction": bool, "ticks_remaining": int | None}],
        "location": str,
        "specialization": str,
        "achievements": [str],
        "buildings_built": int,
        "trades_completed": int,
        "catastrophes_survived": int
    },
    "market": {
        "prices": {"food": float, "materials": float, "knowledge": float},
        "stock": {"food": int, "materials": int, "knowledge": int}
    },
    "other_players": [{"name": str, "score": int, "population": int, "building_count": int, "specialization": str}],
    "catastrophes_remaining": int,
    "next_catastrophe_in": int | None,  # ticks until next (only with Watchtower)
    "tick": int,
    "production_rates": {"food": float, "materials": float, "knowledge": float, "gold": float}
}
```

### handle_action() Error Messages

The `ValueError` messages follow patterns the orchestrator can parse:

| Action | Possible Error Messages |
|--------|------------------------|
| BUILD | `"Building '{type}' already exists"`, `"Insufficient resources: need {cost}, have {current}"` |
| UPGRADE | `"Building '{type}' not found"`, `"Building already at max level"`, `"Building under construction"`, `"Insufficient resources..."` |
| ALLOCATE_WORKERS | `"Worker allocation must sum to {population}, got {sum}"`, `"All 6 roles required"`, `"Negative values not allowed"` |
| TRADE_BUY | `"Insufficient gold: need {cost}, have {gold}"`, `"Exceeds storage capacity"`, `"Insufficient market stock"` |
| TRADE_SELL | `"Insufficient {resource}: need {qty}, have {current}"` |
| DEMOLISH | `"Building '{type}' not found"`, `"Cannot demolish during construction"` |
| REPAIR | `"Building '{type}' not found"`, `"Building not damaged"`, `"Insufficient materials: need {cost}, have {current}"` |

---

## State Conversion: Engine → BenchmarkGameState

The orchestrator must convert the engine's `get_player_state()` dict into the `BenchmarkGameState` schema (defined in schemas.md).

```python
def convert_to_benchmark_state(
    engine_state: dict,
    turn: int,
    max_turns: int,
    scores: list[dict],  # from _calculate_scores()
    catastrophe_warning: dict | None,
    last_catastrophe: dict | None
) -> BenchmarkGameState:
    """Convert raw engine state to benchmark schema."""
    colony = engine_state["colony"]
    market = engine_state["market"]
    
    # Find this player's rank
    player_score = next(s for s in scores if s["player_id"] == player_id)
    
    return BenchmarkGameState(
        turn=turn,
        max_turns=max_turns,
        score=player_score["score"],
        rank=player_score["rank"],
        total_players=len(scores),
        location=colony["location"],
        specialization=colony["specialization"],
        population=colony["population"],
        population_cap=colony["population_cap"],
        morale=colony["morale"],
        resources=ResourceState(**colony["resources"]),
        capacity=ResourceCapacity(**colony["capacity"]),
        production=ProductionRates(**engine_state["production_rates"]),
        food_consumption=colony["population"] * 0.1,
        workers=WorkerAllocation(**colony["workers"]),
        buildings=[BuildingState(**b) for b in colony["buildings"]],
        market_prices=MarketPrices(**market["prices"]),
        sell_spread=0.85 if colony["specialization"] == "trade" else 0.7,
        opponents=[OpponentInfo(**p) for p in engine_state["other_players"]],
        catastrophe_warning=catastrophe_warning,
        last_catastrophe=last_catastrophe,
        available_actions=compute_available_actions(colony, market)
    )
```

---

## Available Actions Computation

Filter the full action space to only actions the player can currently perform:

```python
from terminus.data.loader import get_building_costs

def compute_available_actions(colony: dict, market: dict) -> list[AvailableAction]:
    actions = []
    resources = colony["resources"]
    buildings_map = {b["type"]: b for b in colony["buildings"]}
    
    # BUILD — for each building type not yet built
    all_buildings = ["farm", "mine", "laboratory", "market", "hospital",
                     "wall", "warehouse", "housing", "school", "watchtower"]
    for btype in all_buildings:
        if btype not in buildings_map:
            cost = get_building_costs(btype, level=1)
            if can_afford(resources, cost):
                actions.append(AvailableAction(
                    action_type="BUILD",
                    description=f"Build {btype.title()}",
                    cost=format_cost(cost),
                    params_hint={"building_type": btype}
                ))
    
    # UPGRADE — for each building at level < 3, not under construction
    for btype, building in buildings_map.items():
        if building["level"] < 3 and not building["under_construction"]:
            cost = get_building_costs(btype, level=building["level"] + 1)
            if can_afford(resources, cost):
                actions.append(AvailableAction(
                    action_type="UPGRADE",
                    description=f"Upgrade {btype.title()} to L{building['level'] + 1}",
                    cost=format_cost(cost),
                    params_hint={"building_type": btype}
                ))
    
    # ALLOCATE_WORKERS — always available
    actions.append(AvailableAction(
        action_type="ALLOCATE_WORKERS",
        description=f"Reassign {colony['population']} workers across 6 roles",
        params_hint=None, cost=None
    ))
    
    # TRADE_BUY — for each resource if gold > 0 and market has stock
    for resource in ["food", "materials", "knowledge"]:
        price = market["prices"][resource]
        if resources["gold"] >= price and market["stock"][resource] > 0:
            actions.append(AvailableAction(
                action_type="TRADE_BUY",
                description=f"Buy {resource} ({price:.1f}G/unit)",
                params_hint={"resource": resource}, cost=None
            ))
    
    # TRADE_SELL — for each resource if player has > 0
    for resource in ["food", "materials", "knowledge"]:
        if resources[resource] > 0:
            sell_price = market["prices"][resource] * (0.85 if colony["specialization"] == "trade" else 0.7)
            actions.append(AvailableAction(
                action_type="TRADE_SELL",
                description=f"Sell {resource} ({sell_price:.1f}G/unit)",
                params_hint={"resource": resource}, cost=None
            ))
    
    # REPAIR — for each damaged building
    for btype, building in buildings_map.items():
        if building["health"] < building["max_health"]:
            repair_cost = int((building["max_health"] - building["health"]) * 0.5)
            if resources["materials"] >= repair_cost:
                actions.append(AvailableAction(
                    action_type="REPAIR",
                    description=f"Repair {btype.title()} ({building['health']}/{building['max_health']} HP)",
                    cost=f"{repair_cost} materials",
                    params_hint={"building_type": btype}
                ))
    
    # DEMOLISH — for each building not under construction
    for btype, building in buildings_map.items():
        if not building["under_construction"]:
            actions.append(AvailableAction(
                action_type="DEMOLISH",
                description=f"Demolish {btype.title()} (50% refund)",
                params_hint={"building_type": btype}, cost=None
            ))
    
    # PASS — always available
    actions.append(AvailableAction(
        action_type="PASS",
        description="Do nothing this turn",
        params_hint=None, cost=None
    ))
    
    return actions
```

---

## Speed Multiplier Implementation

The speed multiplier divides all time-based constants. Since we control tick advancement manually, this affects the engine's internal timers:

```python
def apply_speed_multiplier(engine: GameEngine, multiplier: int):
    """Modify engine constants to simulate faster game."""
    # Construction times: divide by multiplier
    # (Applied when computing ticks_remaining for new builds)
    engine._speed_multiplier = multiplier
    
    # Catastrophe schedule: divide scheduled_time by multiplier
    for event in engine.state.catastrophe_schedule:
        event.scheduled_time //= multiplier
    
    # Market volatility: unchanged (per-tick, not time-based)
    # Production rates: unchanged (already per-tick)
    # Food consumption: unchanged (per-tick)
```

**Effect on game length:**
| Multiplier | Effective Ticks per "minute" | 100-turn game feels like |
|---|---|---|
| 1× | 30 ticks/min | Full 45-min game |
| 2× | 30 ticks/min (same ticks, just catastrophes sooner) | Tighter scheduling |
| 5× | 30 ticks/min | Catastrophes every ~20 ticks |
| 10× | 30 ticks/min | Catastrophes every ~10 ticks |

Note: Speed multiplier doesn't reduce tick count — it compresses catastrophe scheduling so the same 100 turns see more events.

---

## Catastrophe Access for Scripted Disruptions

For reproducible benchmark runs, the orchestrator can access and optionally override the catastrophe schedule:

```python
# Read pre-generated schedule
schedule = engine.state.catastrophe_schedule
for event in schedule:
    print(f"Turn ~{event.scheduled_time // 2}: {event.catastrophe_id} (severity {event.severity})")

# Override with scripted disruptions (for specific metric tests)
from terminus.data.loader import get_catastrophe_by_id

engine.state.catastrophe_schedule = [
    CatastropheEvent(catastrophe_id="drought", scheduled_time=30, severity=1),  # Turn 15
    CatastropheEvent(catastrophe_id="earthquake", scheduled_time=60, severity=2),  # Turn 30
    CatastropheEvent(catastrophe_id="plague", scheduled_time=90, severity=2),  # Turn 45
    CatastropheEvent(catastrophe_id="raiders", scheduled_time=120, severity=1),  # Turn 60
    CatastropheEvent(catastrophe_id="meteor", scheduled_time=160, severity=3),  # Turn 80
]
```

---

## Seeding for Reproducibility

The engine uses Python's `random` module for:
- Catastrophe selection and scheduling jitter
- Market price volatility (±20% per tick)
- Population growth probability

For reproducible benchmarks:

```python
import random

def seed_game(seed: int):
    """Set seed before engine initialization for full reproducibility."""
    random.seed(seed)
    # Engine picks catastrophes and schedules during __init__
    # Market volatility uses random.uniform() each tick
    # All deterministic given same seed

# Per-game seed progression
for game_num in range(games_per_matchup):
    game_seed = config.base_seed + game_num
    seed_game(game_seed)
    engine = GameEngine(settings=settings)
    # ... run game ...
```

---

## Concurrent Model Queries

Within a single tick, all LLM players should be queried simultaneously (they all see state from the same tick):

```python
import asyncio

async def query_all_llms(agents: list[LLMAgent], states: list[BenchmarkGameState]) -> list[ActionResponse]:
    """Query all LLM agents concurrently. Respects per-model rate limits."""
    tasks = [
        agent.get_action(state)
        for agent, state in zip(agents, states)
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle timeouts/errors
    results = []
    for i, response in enumerate(responses):
        if isinstance(response, Exception):
            results.append(ActionResponse(action="PASS", params={}, reasoning=default_reasoning()))
        else:
            results.append(response)
    return results
```

---

## Modifications Needed to Existing Engine

The benchmark needs **minimal changes** to the existing engine code. Most integration works by:
1. Calling internal methods directly (no API layer)
2. Setting callbacks to no-ops
3. Disabling persistence

### Required New Code (in benchmark module, not engine)

| Component | Purpose | Touches Engine? |
|-----------|---------|-----------------|
| `BenchmarkOrchestrator` | Turn loop, state conversion, recording | Calls existing methods |
| `StateConverter` | Engine dict → BenchmarkGameState | No |
| `ActionFilter` | Compute available actions | Reads engine data files |
| `SpeedController` | Modify catastrophe schedule | Writes engine.state |
| `TurnRecorder` | Store TurnSnapshot per tick | No |

### Optional Engine Modifications (for cleaner integration)

These are nice-to-have but not strictly required:

```python
# In engine.py — add a public method for manual tick advance
async def advance_tick(self):
    """Advance game by one tick. For benchmark/test use."""
    await self._tick()

# In engine.py — add method to get score without side effects  
def get_scores(self) -> list[dict]:
    """Public accessor for score calculation."""
    return self._calculate_scores()

# In engine.py — add seed parameter
def __init__(self, settings=None, seed=None):
    if seed is not None:
        random.seed(seed)
    # ... rest of init
```

---

## Performance Characteristics

| Metric | Estimate | Notes |
|--------|----------|-------|
| Engine tick (no I/O) | ~0.5ms | Pure Python computation |
| State serialization | ~0.2ms | dict → Pydantic → JSON |
| LLM API call | 500-3000ms | Dominates total time |
| Full turn (1 LLM) | ~1-3 seconds | Mostly LLM latency |
| Full turn (3 LLMs concurrent) | ~1-3 seconds | Parallel queries |
| 100-turn game (1 LLM, 5× speed) | ~2-5 minutes | Depends on model latency |
| Full benchmark (10 games × 3 opponents × 2 models) | ~60-150 minutes | Configurable parallelism |

### Optimization Levers

1. **Skip persistence**: Already disabled. Saves ~2ms/tick.
2. **Skip broadcasts**: Already no-op. Saves ~1ms/tick of JSON serialization.
3. **Batch opponent actions**: Built-in opponents are instant (<0.01ms). No batching needed.
4. **Parallel games**: Run multiple engine instances for different seeds. Thread-safe since each engine is independent.
5. **Local models**: Ollama/vLLM eliminates network latency. Can achieve 100-300ms/turn.

---

## Error Boundary: What Can Go Wrong

| Failure | Engine Behavior | Orchestrator Response |
|---------|----------------|----------------------|
| `handle_action` raises `ValueError` | Action not applied, state unchanged | Record as invalid, continue |
| `_tick()` raises exception | Shouldn't happen (engine is well-tested) | Log, abort game, mark as error |
| Population hits 0 | Colony still exists, just can't do worker actions | Game continues, score tanks |
| All buildings destroyed | Colony still exists, production at base rates | Game continues |
| Food at 0 for 50+ turns | Population drops to 0 eventually | Not a crash — just a lost game |
| Engine phase → FINISHED | Game over signal | Stop turn loop, collect scores |
| Catastrophe phase (60s) | In real-time, blocks actions during resolution | In benchmark: skip wait, process immediately |

### Catastrophe Phase Handling

In the real game, catastrophe phases last 60 seconds (players watch damage resolve). In benchmark mode, we process catastrophe damage immediately within the same tick:

```python
# After _tick() triggers a catastrophe:
if engine.state.phase == GamePhase.CATASTROPHE:
    # Process damage immediately (skip 60s wait)
    await engine._resolve_catastrophe()
    # Phase returns to PLAYING
```

---

## File Dependencies

Files the benchmark module imports from the existing codebase:

```
terminus/server/engine.py       → GameEngine class
terminus/server/models.py       → GameSettings, Player, Colony, Building, etc.
terminus/server/models.py       → ActionType enum, Location enum, Specialization enum
terminus/server/models.py       → GamePhase enum
terminus/data/loader.py         → get_building_costs(), get_catastrophe_by_id()
terminus/config.py              → BASE_PRODUCTION_PER_TICK, SCORE_WEIGHTS, etc.
```

No modifications to these files are needed for the benchmark to work. The benchmark module is purely additive.

---

## Testing the Integration

Verify the headless runner works before building the full orchestrator:

```python
# tests/benchmark/test_headless.py
import pytest
from terminus.server.engine import GameEngine
from terminus.server.models import GameSettings, Player, Location, Specialization, ActionType

@pytest.mark.asyncio
async def test_headless_game_runs():
    """Verify we can run a game without any I/O subsystems."""
    engine = GameEngine(settings=GameSettings(preset="quick"))
    engine._persist = None
    engine.set_broadcast(lambda *a, **k: None)
    
    p1 = Player(name="Test-1", is_host=True)
    p2 = Player(name="Test-2", is_host=False)
    engine.add_player(p1)
    engine.add_player(p2)
    
    await engine.start_game(p1.player_id)
    await engine.submit_setup(p1.player_id, Location.PLAINS, Specialization.AGRICULTURE)
    await engine.submit_setup(p2.player_id, Location.COAST, Specialization.TRADE)
    await engine.check_setup_complete()
    
    # Run 10 ticks
    for _ in range(10):
        await engine._tick()
    
    # Verify state accessible
    state = engine.get_player_state(p1.player_id)
    assert state["colony"]["population"] >= 20
    assert state["tick"] == 10
    
    # Verify action works
    await engine.handle_action(p1.player_id, ActionType.BUILD, {"building_type": "farm"})
    state = engine.get_player_state(p1.player_id)
    assert any(b["type"] == "farm" for b in state["colony"]["buildings"])

@pytest.mark.asyncio
async def test_invalid_action_raises():
    """Verify invalid actions raise ValueError with useful messages."""
    engine = GameEngine(settings=GameSettings(preset="quick"))
    engine._persist = None
    engine.set_broadcast(lambda *a, **k: None)
    
    p1 = Player(name="Test", is_host=True)
    engine.add_player(p1)
    await engine.start_game(p1.player_id)
    await engine.submit_setup(p1.player_id, Location.PLAINS, Specialization.AGRICULTURE)
    await engine.check_setup_complete()
    
    # Try to build something we can't afford (lab costs 40M + 20G, we start with 80M + 50G)
    # First build lab (should work)
    await engine.handle_action(p1.player_id, ActionType.BUILD, {"building_type": "laboratory"})
    
    # Try to build lab again (already exists)
    with pytest.raises(ValueError, match="already exists"):
        await engine.handle_action(p1.player_id, ActionType.BUILD, {"building_type": "laboratory"})
```
