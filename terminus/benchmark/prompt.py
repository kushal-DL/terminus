"""Prompt builder — system prompt, turn messages, retry prompts, probe prompts."""

from __future__ import annotations

from terminus.benchmark.schemas import (
    AvailableAction,
    BenchmarkGameState,
)


# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are playing Terminus, a colony management strategy game. You control a colony and must maximize your score over {max_turns} turns by building infrastructure, managing workers, trading resources, and surviving catastrophes.

## GAME RULES

RESOURCES: Food, Materials, Knowledge, Gold. Each has a capacity limit (base 500/500/200/300, increased by Warehouse).

POPULATION: Starts at 20. Grows +1 when food surplus > 60. Dies -1/turn when food = 0. Max = 50 + (Housing level × 15).

MORALE: Range 0.5–1.5. Multiplies ALL production. Rises with food surplus (+0.01/turn) and successful trades (+0.01). Falls with starvation (-0.05/turn) and population deaths (-0.02 each).

WORKERS: You have exactly [population] workers. Allocate across 6 roles:
- Farming → produces Food
- Mining → produces Materials
- Research → produces Knowledge
- Construction → builds/upgrades buildings (progress = workers × 2/tick)
- Defense → reduces raid/attack damage
- Medicine → reduces plague/disease damage

PRODUCTION: Per tick = base_rate × (role_workers / population) × location_mod × spec_mod × morale × (1 + building_bonus)

BUILDINGS: Max one of each type, max level 3. Must have resources to build. Construction takes time.

| Building | L1 Cost | Effect |
|----------|---------|--------|
| Farm | 30M, 10G | +30/60/100% food production |
| Mine | 20F, 15G | +30/60/100% materials |
| Laboratory | 40M, 20G | +40/80/130% knowledge |
| Market | 35M, 15F | +30/60/100% gold, trade discounts |
| Hospital | 45M, 15K, 15G | Plague mitigation 30/60/90% |
| Wall | 50M, 10G | Defense 30/60/90%, raid mitigation |
| Warehouse | 35M, 5G | Storage capacity ×1/×2/×3 |
| Housing | 40M, 20F | Pop cap +15/+30/+50 |
| School | 30M, 10K, 10G | Knowledge +15/30/50%, morale +5/10/15% |
| Watchtower | 25M, 20K | Catastrophe warnings (better with level) |

MARKET: Buy resources with Gold. Sell for Gold × 0.7 (×0.85 with Trade spec). Prices fluctuate ±20%.

CATASTROPHES: Occur periodically. 30-tick warning before impact. Types:
- Population (plague, disease) → kills colonists. Mitigate: Hospital, Medicine workers
- Resource (drought, locusts) → destroys food/materials. Mitigate: Warehouse, Farm
- Infrastructure (earthquake, flood) → damages buildings. Mitigate: Wall
- Economic (raiders) → steals gold/resources. Mitigate: Wall, Defense workers

P2P TRADING: You can offer resources to opponents or accept/decline their offers. Offers expire after 30 ticks.

SCORING: population×10 + food×1 + materials×1 + knowledge×3 + gold×2 + building_health×5 + morale×150 + achievements

## RESPONSE FORMAT

Respond with a single JSON object. No other text.

{{
  "action": "ACTION_TYPE",
  "params": {{ ... }},
  "reasoning": {{
    "factors": [
      {{"factor": "FACTOR_NAME", "weight": 0.0-1.0}},
      {{"factor": "FACTOR_NAME", "weight": 0.0-1.0}}
    ]
  }}
}}

ACTION TYPES: BUILD, UPGRADE, ALLOCATE_WORKERS, TRADE_BUY, TRADE_SELL, TRADE_OFFER, TRADE_ACCEPT, TRADE_DECLINE, DEMOLISH, REPAIR, PASS

REASONING FACTORS (select 2-4, weights must sum to 1.0):
resource_bottleneck, long_term_growth, opponent_pressure, catastrophe_preparation, market_opportunity, efficiency_optimization, defensive_positioning, cooperative_opportunity, specialization_synergy, immediate_survival, information_gathering, risk_diversification"""


def build_system_prompt(max_turns: int = 100) -> str:
    """Build the system prompt with game rules and response format."""
    return SYSTEM_PROMPT.format(max_turns=max_turns)


# ─── Turn Message ─────────────────────────────────────────────────────────────


def build_turn_message(state: BenchmarkGameState, available_actions: list[AvailableAction]) -> str:
    """Build the per-turn user message from current game state."""
    lines: list[str] = []

    # Header
    lines.append(f"Turn {state.turn}/{state.max_turns} | Score: {state.score} (Rank {state.rank}/{state.total_players})")
    lines.append("")

    # Colony identity
    lines.append("## YOUR COLONY")
    lines.append(f"Location: {state.location} | Specialization: {state.specialization}")
    lines.append(f"Population: {state.population}/{state.population_cap} | Morale: {state.morale:.2f}")
    lines.append("")

    # Resources
    lines.append("Resources:")
    r = state.resources
    p = state.production
    lines.append(f"- Food: {r.food:.0f}/{state.capacity.food} ({p.food:+.1f}/tick, consuming {state.food_consumption:.1f}/tick)")
    lines.append(f"- Materials: {r.materials:.0f}/{state.capacity.materials} ({p.materials:+.1f}/tick)")
    lines.append(f"- Knowledge: {r.knowledge:.0f}/{state.capacity.knowledge} ({p.knowledge:+.1f}/tick)")
    lines.append(f"- Gold: {r.gold:.0f}/{state.capacity.gold} ({p.gold:+.1f}/tick)")
    lines.append("")

    # Workers
    w = state.workers
    total = w.farming + w.mining + w.research + w.construction + w.defense + w.medicine
    lines.append(f"Workers: {total} allocated as:")
    lines.append(f"  Farming: {w.farming} | Mining: {w.mining} | Research: {w.research}")
    lines.append(f"  Construction: {w.construction} | Defense: {w.defense} | Medicine: {w.medicine}")
    lines.append("")

    # Buildings
    lines.append("Buildings:")
    if state.buildings:
        for b in state.buildings:
            status = f" [BUILDING: {b.ticks_remaining} ticks left]" if b.under_construction else ""
            lines.append(f"- {b.type} L{b.level} ({b.health}/{b.max_health} HP){status}")
    else:
        lines.append("- None built yet")
    lines.append("")

    # Market
    mp = state.market_prices
    lines.append("## MARKET PRICES")
    lines.append(f"- Food: {mp.food:.1f}G | Materials: {mp.materials:.1f}G | Knowledge: {mp.knowledge:.1f}G")
    lines.append(f"- Sell multiplier: {state.sell_spread:.2f}")
    lines.append("")

    # Opponents
    if state.opponents:
        lines.append("## OPPONENTS")
        for opp in state.opponents:
            spec = f" ({opp.specialization})" if opp.specialization else ""
            lines.append(f"- {opp.name}: Score {opp.score} | Pop {opp.population} | Buildings {opp.building_count}{spec}")
        lines.append("")

    # Catastrophe
    if state.catastrophe_warning:
        cw = state.catastrophe_warning
        lines.append("## ⚠️ CATASTROPHE WARNING")
        type_str = f" ({cw.type})" if cw.type else ""
        lines.append(f"Category: {cw.category}{type_str}")
        lines.append(f"Arriving in: {cw.ticks_until} ticks")
        if cw.estimated_severity:
            lines.append(f"Estimated severity: {cw.estimated_severity}/3")
        lines.append("")

    if state.last_catastrophe:
        lc = state.last_catastrophe
        lines.append("## LAST CATASTROPHE")
        lines.append(f"{lc.name}: {lc.damage_summary}")
        lines.append("")

    # P2P Trades
    if state.incoming_trade_offers:
        lines.append("## INCOMING TRADE OFFERS")
        for offer in state.incoming_trade_offers:
            offer_str = ", ".join(f"{v:.0f} {k}" for k, v in offer.offer_resources.items())
            request_str = ", ".join(f"{v:.0f} {k}" for k, v in offer.request_resources.items())
            lines.append(f"- [{offer.offer_id[:8]}] {offer.from_player} offers {offer_str} for {request_str} (expires in {offer.ticks_remaining} ticks)")
        lines.append("")

    if state.outgoing_trade_offers:
        lines.append("## OUTGOING TRADE OFFERS (pending)")
        for offer in state.outgoing_trade_offers:
            offer_str = ", ".join(f"{v:.0f} {k}" for k, v in offer.offer_resources.items())
            request_str = ", ".join(f"{v:.0f} {k}" for k, v in offer.request_resources.items())
            lines.append(f"- [{offer.offer_id[:8]}] to {offer.to_player}: {offer_str} for {request_str} ({offer.ticks_remaining} ticks left)")
        lines.append("")

    # Available actions
    lines.append("## AVAILABLE ACTIONS")
    for a in available_actions:
        cost_str = f" (Cost: {a.cost})" if a.cost else ""
        lines.append(f"- {a.action_type}: {a.description}{cost_str}")
    lines.append("")
    lines.append("Choose one action. Respond with JSON only.")

    return "\n".join(lines)


# ─── History Formatting ───────────────────────────────────────────────────────


def format_history_entry(turn: int, action: str, params: dict, result: str) -> str:
    """Format a single history entry."""
    params_str = ""
    if params:
        if action == "ALLOCATE_WORKERS" and "allocation" in params:
            alloc = params["allocation"]
            params_str = f" {alloc}"
        elif "building_type" in params:
            params_str = f" {params['building_type']}"
        elif "resource" in params:
            qty = params.get("quantity", "")
            params_str = f" {params['resource']} {qty}".strip()
    return f"Turn {turn}: Action: {action}{params_str} | Result: {result}"


def build_history_window(history_entries: list[str], max_tokens: int = 2000) -> str:
    """Build the history window, truncating oldest if over budget."""
    if not history_entries:
        return ""

    # Estimate ~4 chars per token
    char_budget = max_tokens * 4
    selected: list[str] = []
    total_chars = 0

    for entry in reversed(history_entries):
        if total_chars + len(entry) + 1 > char_budget:
            break
        selected.insert(0, entry)
        total_chars += len(entry) + 1

    if not selected:
        return ""

    header = f"## RECENT HISTORY (last {len(selected)} turns)\n\n"
    return header + "\n".join(selected)


# ─── Retry Prompt ─────────────────────────────────────────────────────────────


def build_retry_prompt(error_message: str, attempt: int, max_attempts: int) -> str:
    """Build a retry prompt when the LLM's response was invalid."""
    return (
        f"Your previous response was invalid (attempt {attempt}/{max_attempts}).\n"
        f"Error: {error_message}\n\n"
        "Please try again. Respond with ONLY a valid JSON object matching the required format:\n"
        '{"action": "ACTION_TYPE", "params": {...}, "reasoning": {"factors": [...]}}\n\n'
        "Do not include any text outside the JSON."
    )


# ─── State Probe Prompts ──────────────────────────────────────────────────────


def build_probe_building_recall() -> str:
    """Probe: can the LLM recall its buildings from memory?"""
    return (
        "This is a state awareness check. Do not take an action.\n\n"
        "From memory, list ALL buildings in your colony with their current level "
        "and approximate health status. Do not look at the game state above — "
        "answer from what you remember.\n\n"
        "Respond with JSON:\n"
        '{"probe_response": {"buildings": [{"type": "name", "level": N, "health_pct": N}]}}'
    )


def build_probe_resource_awareness() -> str:
    """Probe: can the LLM estimate its resources from memory?"""
    return (
        "This is a state awareness check. Do not take an action.\n\n"
        "Without looking at the current numbers, estimate your current resource levels "
        "and production rates from memory.\n\n"
        "Respond with JSON:\n"
        '{"probe_response": {"estimated_resources": {"food": N, "materials": N, "knowledge": N, "gold": N}, '
        '"estimated_production": {"food": N, "materials": N, "knowledge": N, "gold": N}}}'
    )


def build_probe_strategy_consistency() -> str:
    """Probe: does the LLM have a consistent strategy?"""
    return (
        "This is a strategy check. Do not take an action.\n\n"
        "In 2-3 sentences, describe your current strategy and what you plan to do "
        "in the next 10 turns. What is your primary goal?\n\n"
        "Respond with JSON:\n"
        '{"probe_response": {"strategy": "your description", "next_priority": "primary goal"}}'
    )
