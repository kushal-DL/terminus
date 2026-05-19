# LLM Benchmark — Schema Specification

This document defines the exact Pydantic models used throughout the benchmark system. These are the contracts between components — the orchestrator, LLM adapters, metrics engine, and export system all communicate through these schemas.

---

## Overview

```
BenchmarkConfig          → Orchestrator reads this to configure a run
BenchmarkGameState       → Sent to LLM each turn (serialized from engine state)
ActionResponse           → Received from LLM each turn
GameRecording            → Stored per-game for metrics computation
TurnSnapshot             → One tick's worth of data within a recording
ProbeResponse            → LLM's answer to off-clock state probes
BenchmarkResult          → Output of metrics engine (feeds HTML report)
```

---

## 1. BenchmarkConfig

The top-level configuration for a benchmark run. Loaded from JSON or YAML file.

### Pydantic Model

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from enum import Enum

class WeightPreset(str, Enum):
    BALANCED = "balanced"
    RELIABILITY = "reliability"
    STRATEGY = "strategy"
    TRIAGE = "triage"
    ENDURANCE = "endurance"
    PRECISION = "precision"
    ADVERSARIAL = "adversarial"
    COORDINATION = "coordination"
    CONTEXT = "context"
    CUSTOM = "custom"

class OpponentType(str, Enum):
    RANDOM = "random"
    GREEDY = "greedy"
    BALANCED = "balanced"
    RUSH = "rush"
    TURTLE = "turtle"
    ADVERSARIAL = "adversarial"

class GameTheoryDepth(str, Enum):
    QUICK = "quick"          # Random + Greedy + Balanced (3 types)
    STANDARD = "standard"    # All 6 archetypes
    DEEP = "deep"            # 6 archetypes + repeated adversarial adaptation

class ContextStrategy(str, Enum):
    FULL = "full"            # Keep entire conversation (128K+ models)
    SLIDING = "sliding"      # Sliding window (smaller models)
    AUTO = "auto"            # Auto-select based on model's context limit

class ModelConfig(BaseModel):
    """Configuration for a single LLM to benchmark."""
    name: str = Field(..., description="Display name for this model", min_length=1, max_length=64)
    provider: Literal["openai", "anthropic", "google", "ollama", "custom"] = Field(
        "openai", description="API provider type"
    )
    endpoint: str = Field(..., description="API base URL")
    model: str = Field(..., description="Model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')")
    api_key: str | None = Field(None, description="API key. If None, reads from env var.")
    api_key_env: str | None = Field(None, description="Environment variable name containing API key")
    context_window: int = Field(128000, description="Model's max context window in tokens", ge=4096)
    context_strategy: ContextStrategy = Field(ContextStrategy.AUTO)
    rate_limit_rpm: int | None = Field(None, description="Max requests per minute. None = unlimited", ge=1)
    rate_limit_concurrent: int | None = Field(None, description="Max concurrent requests. None = unlimited", ge=1)
    timeout_seconds: float = Field(30.0, description="Max seconds to wait for LLM response", ge=5.0, le=300.0)

    @field_validator("api_key", "api_key_env")
    @classmethod
    def at_least_one_auth(cls, v, info):
        # Validated at model level — at least one of api_key or api_key_env must be set
        # (unless provider is "ollama" which needs no auth)
        return v

class DimensionWeights(BaseModel):
    """Custom weights for each cognitive dimension. All values >= 0."""
    coherence: float = Field(1.0, ge=0.0, le=5.0)
    arithmetic: float = Field(1.0, ge=0.0, le=5.0)
    triage: float = Field(1.0, ge=0.0, le=5.0)
    error_recognition: float = Field(1.0, ge=0.0, le=5.0)
    pivot: float = Field(1.0, ge=0.0, le=5.0)
    degradation: float = Field(1.0, ge=0.0, le=5.0)
    opportunity_cost: float = Field(1.0, ge=0.0, le=5.0)
    game_theory: float = Field(1.0, ge=0.0, le=5.0)

class BenchmarkConfig(BaseModel):
    """Top-level benchmark configuration."""
    # Models to test
    models: list[ModelConfig] = Field(..., min_length=1, max_length=10)

    # Game settings
    games_per_matchup: int = Field(10, ge=1, le=100, description="Games per model-vs-opponent pairing")
    max_turns: int = Field(100, ge=20, le=500, description="Turns per game")
    speed_multiplier: Literal[1, 2, 5, 10] = Field(5, description="Game speed (divides all timers)")
    seed_mode: Literal["fixed", "random"] = Field("fixed", description="Fixed seeds for reproducibility")
    base_seed: int = Field(42, description="Starting seed (incremented per game)")

    # Opponents
    opponents: list[OpponentType] = Field(
        default=[OpponentType.RANDOM, OpponentType.GREEDY, OpponentType.BALANCED],
        min_length=1
    )
    game_theory_depth: GameTheoryDepth = Field(GameTheoryDepth.QUICK)

    # Metrics
    weight_preset: WeightPreset = Field(WeightPreset.BALANCED)
    custom_weights: DimensionWeights | None = Field(
        None, description="Only used when weight_preset='custom'"
    )
    enable_state_probes: bool = Field(True, description="Run off-clock state probes at checkpoints")
    probe_turns: list[int] = Field(default=[10, 25, 50, 75, 100], description="Turns to inject probes")

    # Output
    output_dir: str = Field("./benchmark-results", description="Directory for HTML + JSON output")
    export_json: bool = Field(True)
    export_html: bool = Field(True)

    # Advanced
    max_retries_invalid_json: int = Field(3, ge=1, le=5)
    consecutive_invalid_dq: int = Field(10, ge=5, le=50, description="DQ after N consecutive invalid actions")
    refusal_dq: int = Field(5, ge=3, le=20, description="DQ after N refusals to play")
```

### Example JSON

```json
{
  "models": [
    {
      "name": "GPT-4o",
      "provider": "openai",
      "endpoint": "https://api.openai.com/v1/chat/completions",
      "model": "gpt-4o",
      "api_key_env": "OPENAI_API_KEY",
      "context_window": 128000,
      "rate_limit_rpm": 60
    },
    {
      "name": "Claude Sonnet",
      "provider": "anthropic",
      "endpoint": "https://api.anthropic.com/v1/messages",
      "model": "claude-sonnet-4-20250514",
      "api_key_env": "ANTHROPIC_API_KEY",
      "context_window": 200000
    },
    {
      "name": "Llama 3.1 70B (local)",
      "provider": "ollama",
      "endpoint": "http://localhost:11434/v1/chat/completions",
      "model": "llama3.1:70b",
      "context_window": 32000,
      "context_strategy": "sliding",
      "rate_limit_rpm": null
    }
  ],
  "games_per_matchup": 10,
  "max_turns": 100,
  "speed_multiplier": 5,
  "seed_mode": "fixed",
  "base_seed": 42,
  "opponents": ["random", "greedy", "balanced"],
  "game_theory_depth": "quick",
  "weight_preset": "balanced",
  "enable_state_probes": true,
  "output_dir": "./benchmark-results",
  "export_json": true,
  "export_html": true
}
```

---

## 2. BenchmarkGameState

What the LLM sees each turn. Serialized from the engine's internal state via `get_player_state()`, restructured for clarity.

### Pydantic Model

```python
class ResourceState(BaseModel):
    """Current resource levels and rates."""
    food: int = Field(..., ge=0)
    materials: int = Field(..., ge=0)
    knowledge: int = Field(..., ge=0)
    gold: int = Field(..., ge=0)

class ResourceCapacity(BaseModel):
    """Maximum storage for each resource."""
    food: int = Field(500, ge=0)
    materials: int = Field(500, ge=0)
    knowledge: int = Field(200, ge=0)
    gold: int = Field(300, ge=0)

class ProductionRates(BaseModel):
    """Net production per tick (after consumption)."""
    food: float = Field(..., description="Food produced minus consumed per tick")
    materials: float = Field(..., ge=0.0)
    knowledge: float = Field(..., ge=0.0)
    gold: float = Field(..., ge=0.0)

class WorkerAllocation(BaseModel):
    """Current worker distribution across roles."""
    farming: int = Field(..., ge=0)
    mining: int = Field(..., ge=0)
    research: int = Field(..., ge=0)
    construction: int = Field(..., ge=0)
    defense: int = Field(..., ge=0)
    medicine: int = Field(..., ge=0)

class BuildingState(BaseModel):
    """State of a single building."""
    type: str = Field(..., description="Building type identifier")
    level: int = Field(..., ge=1, le=3)
    health: int = Field(..., ge=0)
    max_health: int = Field(..., ge=100, le=300)
    under_construction: bool = Field(False)
    ticks_remaining: int | None = Field(None, ge=0, description="Ticks until construction complete")

class MarketPrices(BaseModel):
    """Current market buy prices per unit."""
    food: float = Field(..., gt=0.0)
    materials: float = Field(..., gt=0.0)
    knowledge: float = Field(..., gt=0.0)

class OpponentInfo(BaseModel):
    """Visible information about an opponent."""
    name: str
    score: int = Field(..., ge=0)
    population: int = Field(..., ge=0)
    building_count: int = Field(..., ge=0)
    specialization: str | None = Field(None)

class CatastropheWarning(BaseModel):
    """Active catastrophe warning (30 ticks before impact)."""
    category: Literal["population", "resource", "infrastructure", "economic"]
    type: str | None = Field(None, description="Specific type (only with Watchtower L2+)")
    ticks_until: int = Field(..., ge=0, le=30)
    estimated_severity: int | None = Field(None, ge=1, le=3, description="Only with Watchtower L3")

class LastCatastropheResult(BaseModel):
    """Result of the most recent catastrophe."""
    name: str
    category: str
    damage_summary: str = Field(..., description="Human-readable damage description")
    population_lost: int = Field(0, ge=0)
    resources_lost: dict[str, int] = Field(default_factory=dict)
    building_damage: int = Field(0, ge=0, description="Total HP lost across all buildings")
    morale_change: float = Field(0.0)

class AvailableAction(BaseModel):
    """A single action available to the player this turn."""
    action_type: str
    description: str
    params_hint: dict | None = Field(None, description="Example params or constraints")
    cost: str | None = Field(None, description="Human-readable cost string")

class BenchmarkGameState(BaseModel):
    """Complete game state sent to LLM each turn."""
    # Meta
    turn: int = Field(..., ge=1, description="Current turn number")
    max_turns: int = Field(100, ge=20)
    score: int = Field(..., ge=0)
    rank: int = Field(..., ge=1)
    total_players: int = Field(..., ge=2)

    # Colony identity
    location: str
    specialization: str

    # Population & morale
    population: int = Field(..., ge=0)
    population_cap: int = Field(..., ge=0)
    morale: float = Field(..., ge=0.5, le=1.5)

    # Resources
    resources: ResourceState
    capacity: ResourceCapacity
    production: ProductionRates
    food_consumption: float = Field(..., ge=0.0, description="Food consumed per tick by population")

    # Workers
    workers: WorkerAllocation

    # Buildings
    buildings: list[BuildingState] = Field(default_factory=list)

    # Market
    market_prices: MarketPrices
    sell_spread: float = Field(0.7, description="Sell multiplier (0.7 default, 0.85 for Trade spec)")

    # Opponents
    opponents: list[OpponentInfo] = Field(default_factory=list)

    # Events
    catastrophe_warning: CatastropheWarning | None = Field(None)
    last_catastrophe: LastCatastropheResult | None = Field(None)

    # Available actions (filtered)
    available_actions: list[AvailableAction] = Field(default_factory=list)
```

### Example JSON (Turn 15, Early-Mid Game)

```json
{
  "turn": 15,
  "max_turns": 100,
  "score": 285,
  "rank": 1,
  "total_players": 3,
  "location": "plains",
  "specialization": "agriculture",
  "population": 28,
  "population_cap": 50,
  "morale": 1.05,
  "resources": {
    "food": 142,
    "materials": 67,
    "knowledge": 18,
    "gold": 35
  },
  "capacity": {
    "food": 500,
    "materials": 500,
    "knowledge": 200,
    "gold": 300
  },
  "production": {
    "food": 4.8,
    "materials": 2.1,
    "knowledge": 0.9,
    "gold": 1.6
  },
  "food_consumption": 2.8,
  "workers": {
    "farming": 10,
    "mining": 6,
    "research": 3,
    "construction": 5,
    "defense": 2,
    "medicine": 2
  },
  "buildings": [
    {"type": "farm", "level": 1, "health": 100, "max_health": 100, "under_construction": false, "ticks_remaining": null},
    {"type": "mine", "level": 1, "health": 100, "max_health": 100, "under_construction": false, "ticks_remaining": null},
    {"type": "housing", "level": 1, "health": 100, "max_health": 100, "under_construction": true, "ticks_remaining": 8}
  ],
  "market_prices": {
    "food": 1.8,
    "materials": 3.4,
    "knowledge": 5.2
  },
  "sell_spread": 0.7,
  "opponents": [
    {"name": "Greedy-Bot", "score": 240, "population": 24, "building_count": 2, "specialization": "trade"},
    {"name": "Balanced-Bot", "score": 260, "population": 26, "building_count": 3, "specialization": "science"}
  ],
  "catastrophe_warning": null,
  "last_catastrophe": null,
  "available_actions": [
    {"action_type": "BUILD", "description": "Build Laboratory", "cost": "40 materials, 20 gold", "params_hint": {"building_type": "laboratory"}},
    {"action_type": "BUILD", "description": "Build Warehouse", "cost": "35 materials, 5 gold", "params_hint": {"building_type": "warehouse"}},
    {"action_type": "UPGRADE", "description": "Upgrade Farm to L2", "cost": "60 materials, 25 gold", "params_hint": {"building_type": "farm"}},
    {"action_type": "ALLOCATE_WORKERS", "description": "Reassign 28 workers across 6 roles", "params_hint": null, "cost": null},
    {"action_type": "TRADE_BUY", "description": "Buy food (1.8G/unit)", "params_hint": {"resource": "food"}, "cost": null},
    {"action_type": "TRADE_BUY", "description": "Buy materials (3.4G/unit)", "params_hint": {"resource": "materials"}, "cost": null},
    {"action_type": "TRADE_BUY", "description": "Buy knowledge (5.2G/unit)", "params_hint": {"resource": "knowledge"}, "cost": null},
    {"action_type": "TRADE_SELL", "description": "Sell food (1.3G/unit)", "params_hint": {"resource": "food"}, "cost": null},
    {"action_type": "TRADE_SELL", "description": "Sell materials (2.4G/unit)", "params_hint": {"resource": "materials"}, "cost": null},
    {"action_type": "PASS", "description": "Do nothing this turn", "params_hint": null, "cost": null}
  ]
}
```

---

## 3. ActionResponse

What the LLM returns each turn.

### Pydantic Model

```python
class ReasoningFactor(BaseModel):
    """A single reasoning factor with its influence weight."""
    factor: Literal[
        "resource_bottleneck",
        "long_term_growth",
        "opponent_pressure",
        "catastrophe_preparation",
        "market_opportunity",
        "efficiency_optimization",
        "defensive_positioning",
        "cooperative_opportunity",
        "specialization_synergy",
        "immediate_survival",
        "information_gathering",
        "risk_diversification"
    ]
    weight: float = Field(..., ge=0.0, le=1.0)

class Reasoning(BaseModel):
    """Structured reasoning output from the LLM."""
    factors: list[ReasoningFactor] = Field(..., min_length=1, max_length=6)

    @field_validator("factors")
    @classmethod
    def weights_sum_to_one(cls, v):
        total = sum(f.weight for f in v)
        if not (0.95 <= total <= 1.05):  # Allow small floating point tolerance
            raise ValueError(f"Factor weights must sum to ~1.0, got {total}")
        return v

class ActionType(str, Enum):
    BUILD = "BUILD"
    UPGRADE = "UPGRADE"
    ALLOCATE_WORKERS = "ALLOCATE_WORKERS"
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    DEMOLISH = "DEMOLISH"
    REPAIR = "REPAIR"
    PASS = "PASS"

class BuildParams(BaseModel):
    building_type: Literal[
        "farm", "mine", "laboratory", "market", "hospital",
        "wall", "warehouse", "housing", "school", "watchtower"
    ]

class UpgradeParams(BaseModel):
    building_type: Literal[
        "farm", "mine", "laboratory", "market", "hospital",
        "wall", "warehouse", "housing", "school", "watchtower"
    ]

class AllocateWorkersParams(BaseModel):
    allocation: WorkerAllocation

    @field_validator("allocation")
    @classmethod
    def no_negative(cls, v):
        for role in ["farming", "mining", "research", "construction", "defense", "medicine"]:
            if getattr(v, role) < 0:
                raise ValueError(f"Worker role '{role}' cannot be negative")
        return v

class TradeBuyParams(BaseModel):
    resource: Literal["food", "materials", "knowledge"]
    quantity: int = Field(..., ge=1)

class TradeSellParams(BaseModel):
    resource: Literal["food", "materials", "knowledge"]
    quantity: int = Field(..., ge=1)

class DemolishParams(BaseModel):
    building_type: Literal[
        "farm", "mine", "laboratory", "market", "hospital",
        "wall", "warehouse", "housing", "school", "watchtower"
    ]

class RepairParams(BaseModel):
    building_type: Literal[
        "farm", "mine", "laboratory", "market", "hospital",
        "wall", "warehouse", "housing", "school", "watchtower"
    ]

class PassParams(BaseModel):
    pass  # Empty — no params needed

class ActionResponse(BaseModel):
    """The complete response from an LLM player."""
    action: ActionType
    params: BuildParams | UpgradeParams | AllocateWorkersParams | TradeBuyParams | TradeSellParams | DemolishParams | RepairParams | PassParams
    reasoning: Reasoning

    @field_validator("params", mode="before")
    @classmethod
    def validate_params_match_action(cls, v, info):
        # Discriminated union validation happens at usage time
        # The orchestrator validates params type matches action type
        return v
```

### Example JSON — Valid Responses

**BUILD:**
```json
{
  "action": "BUILD",
  "params": {"building_type": "hospital"},
  "reasoning": {
    "factors": [
      {"factor": "catastrophe_preparation", "weight": 0.6},
      {"factor": "long_term_growth", "weight": 0.4}
    ]
  }
}
```

**ALLOCATE_WORKERS (population = 28):**
```json
{
  "action": "ALLOCATE_WORKERS",
  "params": {
    "allocation": {
      "farming": 9,
      "mining": 6,
      "research": 4,
      "construction": 5,
      "defense": 2,
      "medicine": 2
    }
  },
  "reasoning": {
    "factors": [
      {"factor": "resource_bottleneck", "weight": 0.4},
      {"factor": "efficiency_optimization", "weight": 0.3},
      {"factor": "defensive_positioning", "weight": 0.3}
    ]
  }
}
```

**TRADE_BUY:**
```json
{
  "action": "TRADE_BUY",
  "params": {"resource": "materials", "quantity": 10},
  "reasoning": {
    "factors": [
      {"factor": "market_opportunity", "weight": 0.7},
      {"factor": "long_term_growth", "weight": 0.3}
    ]
  }
}
```

**PASS:**
```json
{
  "action": "PASS",
  "params": {},
  "reasoning": {
    "factors": [
      {"factor": "long_term_growth", "weight": 0.5},
      {"factor": "risk_diversification", "weight": 0.5}
    ]
  }
}
```

### Validation Rules (Applied by Orchestrator)

| Check | Failure Mode | Consequence |
|-------|------|-------------|
| JSON parseable | Invalid JSON | Retry (up to 3×), then PASS |
| `action` field is valid ActionType | Schema error | Retry (up to 3×), then PASS |
| `params` matches action type | Schema error | Retry (up to 3×), then PASS |
| `reasoning.factors` weights sum ≈ 1.0 | Soft violation | Normalize weights, log warning |
| `reasoning.factors` uses valid factor names | Soft violation | Ignore unknown factors, log |
| ALLOCATE_WORKERS sum == population | Game rule violation | Reject action, score as invalid (2.2) |
| TRADE quantity ≤ affordable | Game rule violation | Reject action, score as invalid (2.1) |
| BUILD building doesn't already exist | Game rule violation | Reject action, score as invalid |
| Resources sufficient for action | Game rule violation | Reject action, score as invalid (2.1) |

---

## 4. GameRecording

The complete recording of a single game, stored for metrics computation.

### Pydantic Model

```python
from datetime import datetime

class ActionAttempt(BaseModel):
    """Record of an action attempted by a player."""
    action: ActionType
    params: dict  # Raw params as received
    reasoning: Reasoning | None = None
    valid: bool = Field(..., description="Whether the engine accepted the action")
    rejection_reason: str | None = Field(None, description="Why the action was rejected")
    response_time_ms: float = Field(..., ge=0.0, description="LLM response latency")
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cumulative_tokens: int = Field(..., ge=0, description="Total tokens used up to this point")
    retry_count: int = Field(0, ge=0, description="Number of retries needed for valid JSON")
    raw_response: str | None = Field(None, description="Raw LLM output (for debugging)")

class TurnSnapshot(BaseModel):
    """Complete state + action record for one tick of one player."""
    turn: int = Field(..., ge=1)
    timestamp: datetime

    # Pre-action state
    state: BenchmarkGameState

    # Action taken
    action: ActionAttempt

    # Post-action deltas (what changed)
    score_delta: int = Field(0)
    resource_deltas: dict[str, int] = Field(default_factory=dict)
    population_delta: int = Field(0)
    morale_delta: float = Field(0.0)

    # Events this tick
    catastrophe_triggered: bool = Field(False)
    catastrophe_result: LastCatastropheResult | None = None
    buildings_completed: list[str] = Field(default_factory=list)
    population_died: int = Field(0, ge=0)

class ProbeResult(BaseModel):
    """Result of a single off-clock state probe."""
    probe_type: Literal["building_inventory", "resource_awareness", "strategy_check", "history_recall"]
    turn: int = Field(..., ge=1)
    raw_response: str
    parsed_response: dict | None = Field(None, description="Parsed JSON if valid")
    response_time_ms: float = Field(..., ge=0.0)
    tokens_used: int = Field(..., ge=0)
    score: float | None = Field(None, ge=0.0, le=1.0, description="Computed later by metrics engine")

class PlayerRecording(BaseModel):
    """Complete recording of one player's game."""
    model_name: str
    model_config_hash: str = Field(..., description="SHA256 of ModelConfig for reproducibility")
    player_id: str
    location: str
    specialization: str

    # Turn-by-turn data
    turns: list[TurnSnapshot] = Field(default_factory=list)

    # Probe data
    probes: list[ProbeResult] = Field(default_factory=list)

    # Summary
    final_score: int = Field(..., ge=0)
    final_rank: int = Field(..., ge=1)
    total_actions: int = Field(0, ge=0)
    invalid_actions: int = Field(0, ge=0)
    total_tokens_input: int = Field(0, ge=0)
    total_tokens_output: int = Field(0, ge=0)
    disqualified: bool = Field(False)
    dq_reason: str | None = None
    dq_turn: int | None = None

class GameRecording(BaseModel):
    """Complete recording of a single game (all players)."""
    game_id: str = Field(..., description="UUID for this game")
    config_hash: str = Field(..., description="SHA256 of BenchmarkConfig")
    seed: int = Field(..., description="RNG seed used for this game")
    game_number: int = Field(..., ge=1, description="Sequence number in the benchmark run")
    started_at: datetime
    finished_at: datetime
    total_turns: int = Field(..., ge=1)

    # Game setup
    speed_multiplier: int
    opponent_type: OpponentType

    # Players
    players: list[PlayerRecording] = Field(..., min_length=2)

    # Global events (shared across all players)
    catastrophe_log: list[dict] = Field(default_factory=list, description="All catastrophes with timing and type")
    market_price_history: list[dict] = Field(default_factory=list, description="Price per tick per resource")
```

### Example JSON (Abbreviated — 2 turns of a recording)

```json
{
  "game_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "config_hash": "sha256:abc123...",
  "seed": 42,
  "game_number": 1,
  "started_at": "2026-05-18T14:30:00Z",
  "finished_at": "2026-05-18T14:35:22Z",
  "total_turns": 100,
  "speed_multiplier": 5,
  "opponent_type": "greedy",
  "players": [
    {
      "model_name": "GPT-4o",
      "model_config_hash": "sha256:def456...",
      "player_id": "player_1",
      "location": "plains",
      "specialization": "agriculture",
      "turns": [
        {
          "turn": 1,
          "timestamp": "2026-05-18T14:30:01Z",
          "state": { "...": "full BenchmarkGameState for turn 1" },
          "action": {
            "action": "BUILD",
            "params": {"building_type": "farm"},
            "reasoning": {"factors": [{"factor": "long_term_growth", "weight": 0.6}, {"factor": "specialization_synergy", "weight": 0.4}]},
            "valid": true,
            "rejection_reason": null,
            "response_time_ms": 842.3,
            "input_tokens": 1580,
            "output_tokens": 62,
            "cumulative_tokens": 1642,
            "retry_count": 0,
            "raw_response": null
          },
          "score_delta": 0,
          "resource_deltas": {"materials": -30, "gold": -10},
          "population_delta": 0,
          "morale_delta": 0.0,
          "catastrophe_triggered": false,
          "catastrophe_result": null,
          "buildings_completed": [],
          "population_died": 0
        },
        {
          "turn": 2,
          "timestamp": "2026-05-18T14:30:02Z",
          "state": { "...": "full BenchmarkGameState for turn 2" },
          "action": {
            "action": "ALLOCATE_WORKERS",
            "params": {"allocation": {"farming": 8, "mining": 4, "research": 2, "construction": 4, "defense": 1, "medicine": 1}},
            "reasoning": {"factors": [{"factor": "resource_bottleneck", "weight": 0.5}, {"factor": "efficiency_optimization", "weight": 0.5}]},
            "valid": true,
            "rejection_reason": null,
            "response_time_ms": 756.1,
            "input_tokens": 2420,
            "output_tokens": 95,
            "cumulative_tokens": 4157,
            "retry_count": 0,
            "raw_response": null
          },
          "score_delta": 15,
          "resource_deltas": {"food": 3, "materials": 2},
          "population_delta": 0,
          "morale_delta": 0.01,
          "catastrophe_triggered": false,
          "catastrophe_result": null,
          "buildings_completed": [],
          "population_died": 0
        }
      ],
      "probes": [],
      "final_score": 485,
      "final_rank": 1,
      "total_actions": 100,
      "invalid_actions": 3,
      "total_tokens_input": 245000,
      "total_tokens_output": 8200,
      "disqualified": false,
      "dq_reason": null,
      "dq_turn": null
    }
  ],
  "catastrophe_log": [
    {"turn": 35, "type": "drought", "category": "resource", "severity": 1},
    {"turn": 62, "type": "earthquake", "category": "infrastructure", "severity": 2}
  ],
  "market_price_history": [
    {"turn": 1, "food": 2.0, "materials": 3.0, "knowledge": 5.0},
    {"turn": 2, "food": 2.1, "materials": 2.9, "knowledge": 5.1}
  ]
}
```

---

## 5. BenchmarkResult

Output of the metrics engine. One per benchmark run, feeds the HTML report.

### Pydantic Model

```python
class DimensionScore(BaseModel):
    """Score for a single cognitive dimension."""
    dimension: str
    score: float = Field(..., ge=0.0, le=1.0)
    confidence_interval: tuple[float, float] = Field(..., description="95% CI lower, upper")
    sub_scores: dict[str, float] = Field(default_factory=dict, description="Component scores")
    reported_values: dict[str, float | int | str] = Field(
        default_factory=dict, description="Dimension-specific reported values"
    )

class ModelResult(BaseModel):
    """Complete benchmark result for a single model."""
    model_name: str
    games_played: int
    games_completed: int  # May differ if DQ'd in some
    disqualifications: int = Field(0, ge=0)

    # Scores
    composite_score: float = Field(..., ge=0.0, le=1.0)
    dimensions: list[DimensionScore] = Field(..., min_length=8, max_length=8)

    # Performance stats
    avg_response_time_ms: float
    total_tokens_used: int
    avg_tokens_per_turn: float
    invalid_action_rate: float = Field(..., ge=0.0, le=1.0)

    # Trend
    trend_classification: Literal["improving", "consistent", "degrading", "volatile"]
    trend_slope: float
    trend_p_value: float
    consistency_std: float

    # Per-game scores (for charts)
    per_game_scores: list[int] = Field(default_factory=list)
    per_game_composite: list[float] = Field(default_factory=list)

    # Archetype
    archetype: str = Field(..., description="LLM archetype classification")
    game_theory_profile: str | None = Field(None, description="Predator/Fortress/Diplomat/Chameleon/Oblivious")

class ModelComparison(BaseModel):
    """Statistical comparison between two models."""
    model_a: str
    model_b: str
    dimension: str
    score_diff: float  # A - B
    p_value: float
    effect_size: float  # Cohen's d
    significant: bool  # p < 0.05 after Bonferroni

class BenchmarkResult(BaseModel):
    """Complete output of a benchmark run."""
    # Meta
    benchmark_id: str
    config: BenchmarkConfig
    started_at: datetime
    finished_at: datetime
    total_games: int
    total_runtime_seconds: float

    # Results per model
    models: list[ModelResult] = Field(..., min_length=1)

    # Rankings
    ranking: list[dict] = Field(
        ..., description="Models sorted by composite score: [{name, score, rank}]"
    )

    # Statistical comparisons
    comparisons: list[ModelComparison] = Field(
        default_factory=list, description="Pairwise significance tests"
    )

    # Dimension weights used
    weights_applied: DimensionWeights

    # Raw data reference
    recordings_dir: str = Field(..., description="Path to GameRecording JSON files")
```

### Example JSON (Summary)

```json
{
  "benchmark_id": "bench-20260518-143000",
  "started_at": "2026-05-18T14:30:00Z",
  "finished_at": "2026-05-18T15:45:22Z",
  "total_games": 60,
  "total_runtime_seconds": 4522.0,
  "models": [
    {
      "model_name": "GPT-4o",
      "games_played": 30,
      "games_completed": 30,
      "disqualifications": 0,
      "composite_score": 0.74,
      "dimensions": [
        {"dimension": "coherence", "score": 0.82, "confidence_interval": [0.76, 0.88], "sub_scores": {"action_coherence": 0.85, "state_fidelity": 0.78}, "reported_values": {"inflection_point": 68, "decay_rate": -0.003}},
        {"dimension": "arithmetic", "score": 0.91, "confidence_interval": [0.87, 0.95], "sub_scores": {"invalid_rate": 0.95, "worker_sum": 0.98, "capacity": 0.88}, "reported_values": {"low_load_accuracy": 0.95, "high_load_accuracy": 0.87}},
        {"dimension": "triage", "score": 0.65, "confidence_interval": [0.58, 0.72], "sub_scores": {}, "reported_values": {"avg_priority_rank": 1.8}},
        {"dimension": "error_recognition", "score": 0.58, "confidence_interval": [0.50, 0.66], "sub_scores": {}, "reported_values": {"avg_lead_time": 8.2}},
        {"dimension": "pivot", "score": 0.77, "confidence_interval": [0.71, 0.83], "sub_scores": {}, "reported_values": {"snr": 0.82}},
        {"dimension": "degradation", "score": 0.85, "confidence_interval": [0.80, 0.90], "sub_scores": {"turn_based": 0.88, "context_window": 0.82}, "reported_values": {"failure_mode": "stable", "operational_window": 95000}},
        {"dimension": "opportunity_cost", "score": 0.62, "confidence_interval": [0.55, 0.69], "sub_scores": {}, "reported_values": {"optimal_rate": 0.38, "near_optimal_rate": 0.72}},
        {"dimension": "game_theory", "score": 0.71, "confidence_interval": [0.64, 0.78], "sub_scores": {"opponent_modeling": 0.75, "exploitation_resistance": 0.82, "diversity": 0.55, "cooperation": 0.68, "market_awareness": 0.72}, "reported_values": {"profile": "chameleon"}}
      ],
      "avg_response_time_ms": 1240.5,
      "total_tokens_used": 7350000,
      "avg_tokens_per_turn": 2450.0,
      "invalid_action_rate": 0.05,
      "trend_classification": "consistent",
      "trend_slope": 0.001,
      "trend_p_value": 0.42,
      "consistency_std": 0.04,
      "per_game_scores": [485, 502, 478, 510, 495, 488, 501, 492, 507, 498],
      "per_game_composite": [0.72, 0.75, 0.71, 0.76, 0.74, 0.73, 0.75, 0.73, 0.76, 0.74],
      "archetype": "The All-Rounder",
      "game_theory_profile": "chameleon"
    }
  ],
  "ranking": [
    {"name": "GPT-4o", "score": 0.74, "rank": 1},
    {"name": "Claude Sonnet", "score": 0.71, "rank": 2}
  ],
  "comparisons": [
    {"model_a": "GPT-4o", "model_b": "Claude Sonnet", "dimension": "arithmetic", "score_diff": 0.08, "p_value": 0.023, "effect_size": 0.45, "significant": true}
  ],
  "weights_applied": {"coherence": 1.0, "arithmetic": 1.0, "triage": 1.0, "error_recognition": 1.0, "pivot": 1.0, "degradation": 1.0, "opportunity_cost": 1.0, "game_theory": 1.0}
}
```

---

## 6. ProbeResponse Schemas

Exact schemas for validating probe responses from LLMs.

### Building Inventory Probe

```python
class BuildingRecall(BaseModel):
    type: str
    level: int = Field(..., ge=1, le=3)
    health_pct: int = Field(..., ge=0, le=100)

class BuildingInventoryProbe(BaseModel):
    probe_response: dict  # Contains "buildings" list
    
    # Validated structure:
    # {"buildings": [{"type": "farm", "level": 2, "health_pct": 100}, ...]}
```

### Resource Awareness Probe

```python
class ResourceAwarenessProbe(BaseModel):
    probe_response: dict  # Contains "estimated_resources"
    
    # Validated structure:
    # {"estimated_resources": {"food": 142, "materials": 67, "knowledge": 18, "gold": 35, "population": 28, "morale": 1.05}}
```

### Strategy Check Probe

```python
class StrategyCheckProbe(BaseModel):
    probe_response: dict
    
    # Validated structure:
    # {"current_priority": "...", "next_goal": "...", "strategy_changed": bool, "change_reason": "..." | null}
```

### History Recall Probe

```python
class HistoryRecallProbe(BaseModel):
    probe_response: dict
    
    # Validated structure:
    # {"last_catastrophe": {"type": "drought", "approximate_turn": 35}, "first_building": "farm", "recent_trades": [...]}
```

---

## Schema Relationships

```
BenchmarkConfig ──────────────────────────────┐
    │                                         │
    ▼                                         │
Orchestrator                                  │
    │                                         │
    ├─► BenchmarkGameState ──► LLM            │
    │                            │            │
    │                            ▼            │
    │                      ActionResponse     │
    │                            │            │
    ├─► TurnSnapshot ◄───────────┘            │
    │       │                                 │
    ├─► ProbeResult                           │
    │       │                                 │
    ▼       ▼                                 │
GameRecording ───────► Metrics Engine         │
                            │                 │
                            ▼                 │
                     BenchmarkResult ◄────────┘
                            │
                            ▼
                      HTML Report + JSON Export
```

---

## Serialization Notes

| Schema | Storage Format | Size Estimate |
|--------|---------------|---------------|
| BenchmarkConfig | JSON/YAML file | ~2 KB |
| BenchmarkGameState | In-memory only (not persisted separately) | ~1.5 KB/turn |
| ActionResponse | Embedded in TurnSnapshot | ~200 bytes |
| GameRecording | JSON file per game | ~500 KB - 2 MB |
| BenchmarkResult | JSON file (summary) | ~50 KB |
| Full benchmark run (30 games) | Directory with all recordings + result | ~15-60 MB |

### Compression

GameRecordings can be gzipped for storage (typical 5-8× compression ratio on JSON). The orchestrator writes `.json.gz` files by default, with an option for uncompressed.

---

## Versioning

All schemas include a version field at the root level for forward compatibility:

```python
SCHEMA_VERSION = "1.0.0"
```

Breaking changes increment major version. The metrics engine and HTML exporter check schema version and fail fast if incompatible.
