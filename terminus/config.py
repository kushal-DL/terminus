"""Game configuration constants and balance numbers.

All magic numbers live here. Imported by both server and client.
"""

# ─── Server ──────────────────────────────────────────────────────────────────

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080

# ─── Persistence ─────────────────────────────────────────────────────────────

PERSISTENCE_INTERVAL_TICKS = 5  # Save snapshot every N ticks (~10s at 2s/tick)

# ─── Game Timing ─────────────────────────────────────────────────────────────

SETUP_PHASE_SECONDS = 90
CATASTROPHE_RESOLUTION_SECONDS = 60
CATASTROPHE_WARNING_SECONDS = 30
SERVER_TICK_INTERVAL = 2.0  # seconds between game ticks

# Presets: (num_catastrophes, interval_seconds_between)
GAME_PRESETS = {
    "quick": {"num_catastrophes": 4, "interval_seconds": 420, "label": "Quick (~30 min)"},
    "standard": {"num_catastrophes": 5, "interval_seconds": 510, "label": "Standard (~45 min)"},
    "extended": {"num_catastrophes": 6, "interval_seconds": 570, "label": "Extended (~60 min)"},
}
DEFAULT_PRESET = "standard"

# ─── Player Limits ───────────────────────────────────────────────────────────

MAX_PLAYERS = 250
MIN_PLAYERS_TO_START = 1
MAX_PLAYER_NAME_LENGTH = 20
MAX_COLONY_NAME_LENGTH = 20

# ─── Resources ───────────────────────────────────────────────────────────────

STARTING_RESOURCES = {
    "food": 100,
    "materials": 80,
    "knowledge": 10,
    "gold": 50,
}

BASE_RESOURCE_CAPACITY = {
    "food": 500,
    "materials": 500,
    "knowledge": 200,
    "gold": 300,
}

WAREHOUSE_CAPACITY_BONUS_PER_LEVEL = {
    "food": 200,
    "materials": 200,
    "knowledge": 100,
    "gold": 150,
}

# Base production per tick (with 100% of population assigned to that role)
BASE_PRODUCTION_PER_TICK = {
    "food": 3.2,
    "materials": 2.6,
    "knowledge": 1.6,
    "gold": 2.2,
}

# ─── Population ──────────────────────────────────────────────────────────────

STARTING_POPULATION = 20
MAX_POPULATION_BASE = 50  # Without housing
HOUSING_POP_BONUS_PER_LEVEL = 15
FOOD_CONSUMPTION_PER_POP_PER_TICK = 0.1
STARVATION_DEATHS_PER_TICK = 1
POPULATION_GROWTH_RATE = 0.4  # Pop gained per tick when food surplus > threshold
FOOD_SURPLUS_THRESHOLD_FOR_GROWTH = 60  # Need this much food to grow

# ─── Morale ──────────────────────────────────────────────────────────────────

STARTING_MORALE = 1.0
MORALE_MIN = 0.5
MORALE_MAX = 1.5
MORALE_FOOD_SURPLUS_BONUS = 0.01  # per tick when food > threshold
MORALE_STARVATION_PENALTY = 0.05  # per tick when starving
MORALE_DEATH_PENALTY = 0.02  # per death
MORALE_BUILDING_DESTROYED_PENALTY = 0.03  # per building destroyed
MORALE_CATASTROPHE_SURVIVAL_BONUS = 0.05  # if you lose 0 pop in catastrophe
MORALE_TRADE_BONUS = 0.01  # per successful trade

# ─── Buildings ───────────────────────────────────────────────────────────────

MAX_BUILDING_LEVEL = 3
BUILDING_HEALTH_PER_LEVEL = 100  # health = level * this
REPAIR_COST_PER_HEALTH = 0.5  # materials per health point restored
DEMOLISH_REFUND_RATIO = 0.5  # get back 50% of build cost

# Construction speed: progress_per_tick = construction_workers * this
CONSTRUCTION_SPEED_MULTIPLIER = 2.0

# ─── Worker Roles ────────────────────────────────────────────────────────────

WORKER_ROLES = ["farming", "mining", "research", "construction", "defense", "medicine"]

# Defense reduces raid damage: damage_reduction = defense_workers / population * 0.5
DEFENSE_EFFECTIVENESS = 0.5

# Medicine reduces plague damage: similar formula
MEDICINE_EFFECTIVENESS = 0.4

# ─── Market ──────────────────────────────────────────────────────────────────

BASE_MARKET_PRICES = {
    "food": 2.0,
    "materials": 3.0,
    "knowledge": 5.0,
}

MARKET_PRICE_VOLATILITY = 0.2  # ±20% random fluctuation per round
MARKET_SELL_SPREAD = 0.7  # sell price = buy price * this
TRADE_SPEC_BUY_DISCOUNT = 0.85  # trade specialization pays 85% of price
TRADE_SPEC_SELL_BONUS = 0.85  # trade spec gets sell_spread of 0.85 instead of 0.7

MARKET_STOCK_PER_RESOURCE = 200  # units available per resource per round

# ─── Player-to-Player Trading ────────────────────────────────────────────────

TRADE_OFFER_EXPIRY_TICKS = 30  # offers expire after this many ticks
MAX_PENDING_OFFERS = 3  # max concurrent outgoing offers per player
TRADABLE_RESOURCES = ["food", "materials", "knowledge", "gold"]

# ─── Catastrophe ─────────────────────────────────────────────────────────────

CATASTROPHE_MIN_DAMAGE = 0.08  # Even fully mitigated, take 8% of base damage
CATASTROPHE_INTERVAL_JITTER = 60  # ±60 seconds randomness on timing
CATASTROPHE_POP_DAMAGE_SCALE = 0.5  # Scale factor for kill_population damage

# Watchtower hint levels
WATCHTOWER_HINTS = {
    1: "category",  # e.g., "A natural disaster approaches..."
    2: "type",  # e.g., "An earthquake is coming!"
    3: "type_and_timing",  # e.g., "Earthquake in ~2 minutes!"
}

# ─── Scoring ─────────────────────────────────────────────────────────────────

SCORE_WEIGHTS = {
    "population": 10,
    "food": 1,
    "materials": 1,
    "knowledge": 3,
    "gold": 2,
    "building_health": 5,  # per total health across all buildings
    "morale": 150,  # morale * this
}

ACHIEVEMENT_BONUS_POINTS = 50  # flat bonus per achievement earned

# ─── Location Modifiers ──────────────────────────────────────────────────────
# Multipliers on base production. All locations have total multiplier sum = 7.0

LOCATION_MODIFIERS = {
    "coast": {"food": 1.5, "materials": 1.0, "knowledge": 1.0, "gold": 1.5, "defense": 1.0},
    "mountain": {"food": 0.8, "materials": 1.6, "knowledge": 1.0, "gold": 1.0, "defense": 1.6},
    "plains": {"food": 1.6, "materials": 1.0, "knowledge": 1.0, "gold": 1.0, "defense": 1.4},
    "forest": {"food": 1.2, "materials": 1.5, "knowledge": 1.0, "gold": 0.8, "defense": 1.5},
    "desert": {"food": 0.8, "materials": 1.0, "knowledge": 1.6, "gold": 1.6, "defense": 1.0},
}

# ─── Specialization Modifiers ────────────────────────────────────────────────
# Additive bonuses on top of location. Total bonus sum = 1.0 for each spec.

SPECIALIZATION_MODIFIERS = {
    "military": {"food": 0.0, "materials": 0.1, "knowledge": 0.0, "gold": 0.0, "defense": 0.4, "construction_speed": 0.5},
    "trade": {"food": 0.0, "materials": 0.0, "knowledge": 0.0, "gold": 0.5, "defense": 0.0, "market_bonus": 0.5},
    "science": {"food": 0.0, "materials": 0.0, "knowledge": 0.5, "gold": 0.0, "defense": 0.0, "research_speed": 0.5},
    "agriculture": {"food": 0.5, "materials": 0.0, "knowledge": 0.0, "gold": 0.0, "defense": 0.0, "construction_speed": 0.5},
}
