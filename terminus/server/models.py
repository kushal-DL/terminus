"""Pydantic models for all game state."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from terminus.config import (
    BASE_RESOURCE_CAPACITY,
    MAX_BUILDING_LEVEL,
    STARTING_MORALE,
    STARTING_POPULATION,
    STARTING_RESOURCES,
    WORKER_ROLES,
)


# ─── Enums ───────────────────────────────────────────────────────────────────


class GamePhase(str, Enum):
    LOBBY = "lobby"
    SETUP = "setup"
    PLAYING = "playing"
    CATASTROPHE = "catastrophe"
    SCORING = "scoring"
    FINISHED = "finished"


class Location(str, Enum):
    COAST = "coast"
    MOUNTAIN = "mountain"
    PLAINS = "plains"
    FOREST = "forest"
    DESERT = "desert"


class Specialization(str, Enum):
    MILITARY = "military"
    TRADE = "trade"
    SCIENCE = "science"
    AGRICULTURE = "agriculture"


class ActionType(str, Enum):
    BUILD = "build"
    UPGRADE = "upgrade"
    ALLOCATE_WORKERS = "allocate_workers"
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    DEMOLISH = "demolish"
    REPAIR = "repair"


# ─── Resource & Building Models ──────────────────────────────────────────────


class Resources(BaseModel):
    food: float = Field(default=0, ge=0)
    materials: float = Field(default=0, ge=0)
    knowledge: float = Field(default=0, ge=0)
    gold: float = Field(default=0, ge=0)

    def to_dict(self) -> dict[str, float]:
        return {"food": self.food, "materials": self.materials, "knowledge": self.knowledge, "gold": self.gold}


class ResourceCapacity(BaseModel):
    food: float = Field(default=BASE_RESOURCE_CAPACITY["food"])
    materials: float = Field(default=BASE_RESOURCE_CAPACITY["materials"])
    knowledge: float = Field(default=BASE_RESOURCE_CAPACITY["knowledge"])
    gold: float = Field(default=BASE_RESOURCE_CAPACITY["gold"])


class Building(BaseModel):
    building_type: str
    level: int = Field(default=0, ge=0, le=MAX_BUILDING_LEVEL)
    health: float = Field(default=100, ge=0)
    max_health: float = Field(default=100)
    under_construction: bool = False
    construction_progress: float = Field(default=0, ge=0)
    construction_target: float = Field(default=0, ge=0)  # ticks needed


class WorkerAllocation(BaseModel):
    farming: int = Field(default=0, ge=0)
    mining: int = Field(default=0, ge=0)
    research: int = Field(default=0, ge=0)
    construction: int = Field(default=0, ge=0)
    defense: int = Field(default=0, ge=0)
    medicine: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return self.farming + self.mining + self.research + self.construction + self.defense + self.medicine

    def to_dict(self) -> dict[str, int]:
        return {role: getattr(self, role) for role in WORKER_ROLES}


# ─── Colony Model ────────────────────────────────────────────────────────────


class Colony(BaseModel):
    name: str
    location: Location | None = None
    specialization: Specialization | None = None
    resources: Resources = Field(default_factory=lambda: Resources(**STARTING_RESOURCES))
    capacity: ResourceCapacity = Field(default_factory=ResourceCapacity)
    buildings: list[Building] = Field(default_factory=list)
    workers: WorkerAllocation = Field(default_factory=WorkerAllocation)
    population: int = Field(default=STARTING_POPULATION, ge=0)
    max_population: int = Field(default=50)
    morale: float = Field(default=STARTING_MORALE)
    score: float = Field(default=0)
    achievements: list[str] = Field(default_factory=list)  # earned achievement IDs
    # Stat tracking
    buildings_built: int = Field(default=0)
    trades_completed: int = Field(default=0)
    total_trade_volume: float = Field(default=0)
    catastrophes_survived: int = Field(default=0)
    peak_population: int = Field(default=STARTING_POPULATION)


# ─── Player Model ────────────────────────────────────────────────────────────


class Player(BaseModel):
    player_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    token: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connected: bool = True
    ready: bool = False
    is_host: bool = False
    colony: Colony | None = None


# ─── Catastrophe Event ───────────────────────────────────────────────────────


class CatastropheResult(BaseModel):
    player_id: str
    population_lost: int = 0
    resources_lost: dict[str, float] = Field(default_factory=dict)
    buildings_damaged: list[str] = Field(default_factory=list)
    morale_change: float = 0
    mitigated_by: list[str] = Field(default_factory=list)


class CatastropheEvent(BaseModel):
    catastrophe_id: str
    scheduled_time: float  # seconds from game start
    resolved: bool = False
    results: dict[str, CatastropheResult] = Field(default_factory=dict)  # player_id → result


# ─── Market ──────────────────────────────────────────────────────────────────


class MarketState(BaseModel):
    prices: dict[str, float] = Field(default_factory=dict)
    stock: dict[str, float] = Field(default_factory=dict)
    price_history: list[dict[str, float]] = Field(default_factory=list)


class TradeRecord(BaseModel):
    tick: int = 0
    player_id: str
    player_name: str = ""
    action: str  # "buy" or "sell"
    resource: str
    quantity: int
    price_per_unit: float
    total: float


# ─── Game Settings ───────────────────────────────────────────────────────────


class GameSettings(BaseModel):
    preset: str = "standard"
    max_players: int = 250
    num_catastrophes: int = 5
    catastrophe_interval_seconds: int = 420
    allow_late_join: bool = True


# ─── Game State ──────────────────────────────────────────────────────────────


class GameState(BaseModel):
    game_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phase: GamePhase = GamePhase.LOBBY
    players: dict[str, Player] = Field(default_factory=dict)  # player_id → Player
    settings: GameSettings = Field(default_factory=GameSettings)
    catastrophe_schedule: list[CatastropheEvent] = Field(default_factory=list)
    current_catastrophe_index: int = 0
    market: MarketState = Field(default_factory=MarketState)
    trade_history: list[TradeRecord] = Field(default_factory=list)
    game_start_time: float | None = None  # timestamp when PLAYING started
    elapsed_ticks: int = 0
    score_history: list[dict[str, Any]] = Field(default_factory=list)  # snapshots after each catastrophe
    dev_mode: bool = False  # Host-enabled dev mode (allows admin endpoints without env var)


# ─── Action Models ───────────────────────────────────────────────────────────


class BuildAction(BaseModel):
    action_type: ActionType = ActionType.BUILD
    building_type: str


class UpgradeAction(BaseModel):
    action_type: ActionType = ActionType.UPGRADE
    building_type: str


class AllocateWorkersAction(BaseModel):
    action_type: ActionType = ActionType.ALLOCATE_WORKERS
    allocation: dict[str, int]  # role → count


class TradeBuyAction(BaseModel):
    action_type: ActionType = ActionType.TRADE_BUY
    resource: str
    quantity: int = Field(gt=0)


class TradeSellAction(BaseModel):
    action_type: ActionType = ActionType.TRADE_SELL
    resource: str
    quantity: int = Field(gt=0)


class DemolishAction(BaseModel):
    action_type: ActionType = ActionType.DEMOLISH
    building_type: str


class RepairAction(BaseModel):
    action_type: ActionType = ActionType.REPAIR
    building_type: str


# ─── API Request/Response Models ─────────────────────────────────────────────


class CreateGameRequest(BaseModel):
    player_name: str
    settings: GameSettings = Field(default_factory=GameSettings)


class CreateGameResponse(BaseModel):
    game_id: str
    player_id: str
    token: str
    host: bool = True


class JoinGameRequest(BaseModel):
    player_name: str


class JoinGameResponse(BaseModel):
    game_id: str
    player_id: str
    token: str


class SetupRequest(BaseModel):
    location: Location
    specialization: Specialization


class GameActionRequest(BaseModel):
    action_type: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)


# ─── WebSocket Event Models ──────────────────────────────────────────────────


class WSEvent(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)
