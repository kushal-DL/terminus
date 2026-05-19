"""Benchmark schemas — Pydantic models for config, game state, and LLM responses."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Enums ────────────────────────────────────────────────────────────────────


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
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ContextStrategy(str, Enum):
    FULL = "full"
    SLIDING = "sliding"
    AUTO = "auto"


class BenchmarkActionType(str, Enum):
    BUILD = "BUILD"
    UPGRADE = "UPGRADE"
    ALLOCATE_WORKERS = "ALLOCATE_WORKERS"
    TRADE_BUY = "TRADE_BUY"
    TRADE_SELL = "TRADE_SELL"
    TRADE_OFFER = "TRADE_OFFER"
    TRADE_ACCEPT = "TRADE_ACCEPT"
    TRADE_DECLINE = "TRADE_DECLINE"
    DEMOLISH = "DEMOLISH"
    REPAIR = "REPAIR"
    PASS = "PASS"


class ReasoningFactorType(str, Enum):
    RESOURCE_BOTTLENECK = "resource_bottleneck"
    LONG_TERM_GROWTH = "long_term_growth"
    OPPONENT_PRESSURE = "opponent_pressure"
    CATASTROPHE_PREPARATION = "catastrophe_preparation"
    MARKET_OPPORTUNITY = "market_opportunity"
    EFFICIENCY_OPTIMIZATION = "efficiency_optimization"
    DEFENSIVE_POSITIONING = "defensive_positioning"
    COOPERATIVE_OPPORTUNITY = "cooperative_opportunity"
    SPECIALIZATION_SYNERGY = "specialization_synergy"
    IMMEDIATE_SURVIVAL = "immediate_survival"
    INFORMATION_GATHERING = "information_gathering"
    RISK_DIVERSIFICATION = "risk_diversification"


# ─── Configuration Models ─────────────────────────────────────────────────────


class ModelConfig(BaseModel):
    """Configuration for a single LLM to benchmark."""

    name: str = Field(..., min_length=1, max_length=64)
    provider: Literal["openai", "anthropic", "google", "ollama", "custom"] = "openai"
    endpoint: str = Field(...)
    model: str = Field(...)
    api_key: str | None = None
    api_key_env: str | None = None
    context_window: int = Field(128000, ge=4096)
    context_strategy: ContextStrategy = ContextStrategy.AUTO
    rate_limit_rpm: int | None = Field(None, ge=1)
    rate_limit_concurrent: int | None = Field(None, ge=1)
    timeout_seconds: float = Field(30.0, ge=5.0, le=300.0)

    @model_validator(mode="after")
    def validate_auth(self) -> "ModelConfig":
        if self.provider != "ollama" and not self.api_key and not self.api_key_env:
            raise ValueError("Either api_key or api_key_env must be set (unless provider is 'ollama')")
        return self


class DimensionWeights(BaseModel):
    """Custom weights for each cognitive dimension."""

    coherence: float = Field(1.0, ge=0.0, le=5.0)
    arithmetic: float = Field(1.0, ge=0.0, le=5.0)
    triage: float = Field(1.0, ge=0.0, le=5.0)
    error_recognition: float = Field(1.0, ge=0.0, le=5.0)
    pivot: float = Field(1.0, ge=0.0, le=5.0)
    degradation: float = Field(1.0, ge=0.0, le=5.0)
    opportunity_cost: float = Field(1.0, ge=0.0, le=5.0)
    game_theory: float = Field(1.0, ge=0.0, le=5.0)


class BenchmarkConfig(BaseModel):
    """Top-level benchmark run configuration."""

    # Models
    models: list[ModelConfig] = Field(..., min_length=1, max_length=10)

    # Game settings
    games_per_matchup: int = Field(10, ge=1, le=100)
    max_turns: int = Field(100, ge=20, le=500)
    speed_multiplier: Literal[1, 2, 5, 10] = 5
    seed_mode: Literal["fixed", "random"] = "fixed"
    base_seed: int = 42

    # Opponents
    opponents: list[OpponentType] = Field(
        default=[OpponentType.RANDOM, OpponentType.GREEDY, OpponentType.BALANCED],
        min_length=1,
    )
    game_theory_depth: GameTheoryDepth = GameTheoryDepth.QUICK

    # Metrics
    weight_preset: WeightPreset = WeightPreset.BALANCED
    custom_weights: DimensionWeights | None = None
    enable_state_probes: bool = True
    probe_turns: list[int] = Field(default=[10, 25, 50, 75, 100])

    # Output
    output_dir: str = "./benchmark-results"
    export_json: bool = True
    export_html: bool = True

    # Error handling
    max_retries_invalid_json: int = Field(3, ge=1, le=5)
    consecutive_invalid_dq: int = Field(10, ge=5, le=50)
    refusal_dq: int = Field(5, ge=3, le=20)


# ─── Game State Models (sent to LLM each turn) ───────────────────────────────


class ResourceState(BaseModel):
    """Current resource levels."""

    food: float = Field(0, ge=0)
    materials: float = Field(0, ge=0)
    knowledge: float = Field(0, ge=0)
    gold: float = Field(0, ge=0)


class ResourceCapacity(BaseModel):
    """Maximum storage per resource."""

    food: int = Field(500, ge=0)
    materials: int = Field(500, ge=0)
    knowledge: int = Field(200, ge=0)
    gold: int = Field(300, ge=0)


class ProductionRates(BaseModel):
    """Net production per tick."""

    food: float = 0.0
    materials: float = 0.0
    knowledge: float = 0.0
    gold: float = 0.0


class BenchmarkWorkerAllocation(BaseModel):
    """Worker distribution across roles."""

    farming: int = Field(0, ge=0)
    mining: int = Field(0, ge=0)
    research: int = Field(0, ge=0)
    construction: int = Field(0, ge=0)
    defense: int = Field(0, ge=0)
    medicine: int = Field(0, ge=0)


class BuildingState(BaseModel):
    """State of a single building."""

    type: str
    level: int = Field(1, ge=1, le=3)
    health: int = Field(100, ge=0)
    max_health: int = Field(100, ge=0)
    under_construction: bool = False
    ticks_remaining: int | None = None


class MarketPrices(BaseModel):
    """Current market prices."""

    food: float = Field(1.0, gt=0)
    materials: float = Field(1.0, gt=0)
    knowledge: float = Field(1.0, gt=0)


class OpponentInfo(BaseModel):
    """Visible information about an opponent."""

    name: str
    score: int = Field(0, ge=0)
    population: int = Field(0, ge=0)
    building_count: int = Field(0, ge=0)
    specialization: str | None = None


class CatastropheWarning(BaseModel):
    """Active catastrophe warning."""

    category: Literal["population", "resource", "infrastructure", "economic"]
    type: str | None = None
    ticks_until: int = Field(0, ge=0)
    estimated_severity: int | None = Field(None, ge=1, le=3)


class LastCatastropheResult(BaseModel):
    """Result of the most recent catastrophe."""

    name: str
    category: str
    damage_summary: str
    population_lost: int = Field(0, ge=0)
    resources_lost: dict[str, float] = Field(default_factory=dict)
    building_damage: int = Field(0, ge=0)
    morale_change: float = 0.0


class TradeOfferInfo(BaseModel):
    """A P2P trade offer visible to the LLM."""

    offer_id: str
    from_player: str
    to_player: str
    offer_resources: dict[str, float]
    request_resources: dict[str, float]
    ticks_remaining: int = Field(0, ge=0)


class AvailableAction(BaseModel):
    """A single available action this turn."""

    action_type: str
    description: str
    cost: str | None = None
    params_hint: dict | None = None


class BenchmarkGameState(BaseModel):
    """Complete game state sent to LLM each turn."""

    # Meta
    turn: int = Field(1, ge=1)
    max_turns: int = Field(100, ge=20)
    score: int = Field(0, ge=0)
    rank: int = Field(1, ge=1)
    total_players: int = Field(2, ge=2)

    # Colony identity
    location: str = ""
    specialization: str = ""

    # Population & morale
    population: int = Field(0, ge=0)
    population_cap: int = Field(0, ge=0)
    morale: float = Field(1.0, ge=0.5, le=1.5)

    # Resources
    resources: ResourceState = Field(default_factory=ResourceState)
    capacity: ResourceCapacity = Field(default_factory=ResourceCapacity)
    production: ProductionRates = Field(default_factory=ProductionRates)
    food_consumption: float = Field(0.0, ge=0.0)

    # Workers
    workers: BenchmarkWorkerAllocation = Field(default_factory=BenchmarkWorkerAllocation)

    # Buildings
    buildings: list[BuildingState] = Field(default_factory=list)

    # Market
    market_prices: MarketPrices = Field(default_factory=MarketPrices)
    sell_spread: float = Field(0.7, ge=0.0, le=1.0)

    # Opponents
    opponents: list[OpponentInfo] = Field(default_factory=list)

    # Events
    catastrophe_warning: CatastropheWarning | None = None
    last_catastrophe: LastCatastropheResult | None = None

    # P2P Trading
    incoming_trade_offers: list[TradeOfferInfo] = Field(default_factory=list)
    outgoing_trade_offers: list[TradeOfferInfo] = Field(default_factory=list)

    # Available actions
    available_actions: list[AvailableAction] = Field(default_factory=list)


# ─── Action Response Models (returned by LLM) ────────────────────────────────


class ReasoningFactor(BaseModel):
    """A single reasoning factor with its influence weight."""

    factor: ReasoningFactorType
    weight: float = Field(..., ge=0.0, le=1.0)


class Reasoning(BaseModel):
    """Structured reasoning output from the LLM."""

    factors: list[ReasoningFactor] = Field(..., min_length=1, max_length=6)

    @field_validator("factors")
    @classmethod
    def weights_sum_approximately_one(cls, v: list[ReasoningFactor]) -> list[ReasoningFactor]:
        total = sum(f.weight for f in v)
        if not (0.8 <= total <= 1.2):
            raise ValueError(f"Factor weights must sum to ~1.0, got {total:.2f}")
        return v


class BuildParams(BaseModel):
    building_type: str


class UpgradeParams(BaseModel):
    building_type: str


class AllocateWorkersParams(BaseModel):
    allocation: BenchmarkWorkerAllocation


class TradeBuyParams(BaseModel):
    resource: Literal["food", "materials", "knowledge"]
    quantity: int = Field(..., ge=1)


class TradeSellParams(BaseModel):
    resource: Literal["food", "materials", "knowledge"]
    quantity: int = Field(..., ge=1)


class TradeOfferParams(BaseModel):
    to_player_id: str
    offer_resources: dict[str, float]
    request_resources: dict[str, float]


class TradeAcceptParams(BaseModel):
    offer_id: str


class TradeDeclineParams(BaseModel):
    offer_id: str


class DemolishParams(BaseModel):
    building_type: str


class RepairParams(BaseModel):
    building_type: str


class PassParams(BaseModel):
    pass


ActionParams = (
    BuildParams
    | UpgradeParams
    | AllocateWorkersParams
    | TradeBuyParams
    | TradeSellParams
    | TradeOfferParams
    | TradeAcceptParams
    | TradeDeclineParams
    | DemolishParams
    | RepairParams
    | PassParams
)


class ActionResponse(BaseModel):
    """The complete response from an LLM player."""

    action: BenchmarkActionType
    params: dict = Field(default_factory=dict)
    reasoning: Reasoning | None = None


# ─── Recording Models ─────────────────────────────────────────────────────────


class TurnSnapshot(BaseModel):
    """Per-turn recording data."""

    turn: int
    state: BenchmarkGameState
    raw_response: str = ""
    parsed_response: ActionResponse | None = None
    valid: bool = True
    error_message: str | None = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    retry_count: int = 0


class GameRecording(BaseModel):
    """Complete recording of a benchmark game."""

    model_name: str
    opponent_type: str
    seed: int = 0
    turns: list[TurnSnapshot] = Field(default_factory=list)
    final_score: int = 0
    opponent_final_score: int = 0
    duration_seconds: float = 0.0
    total_tokens: int = 0
    invalid_action_count: int = 0
    dq_reason: str | None = None
