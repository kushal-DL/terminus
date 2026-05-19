# LLM Benchmark — Prompt Template Specification

This document defines the exact prompts sent to LLMs during benchmark games. Every model receives identical prompts for fair comparison.

---

## Architecture: What Gets Sent Each Turn

```
┌───────────────────────────────────────────────────────┐
│  SYSTEM PROMPT (sent once, included in every call)    │
│  ~1200 tokens — game rules, actions, response format  │
├───────────────────────────────────────────────────────┤
│  TURN MESSAGE (changes every tick)                    │
│  ~400-800 tokens — current state, available actions   │
├───────────────────────────────────────────────────────┤
│  HISTORY WINDOW (grows, then truncated)               │
│  ~200-2000 tokens — last N turns of actions + results │
└───────────────────────────────────────────────────────┘

Total per-turn context: ~1800-4000 tokens (varies by game phase)
```

---

## Token Budget

| Component | Tokens (est.) | Notes |
|-----------|---------------|-------|
| System prompt | ~1200 | Fixed, never truncated |
| Current state | ~400-600 | Grows slightly as buildings increase |
| Available actions | ~150-250 | Filtered to affordable actions only |
| History window | ~200-2000 | Sliding window, oldest dropped first |
| LLM response | ~100-200 | Structured JSON, compact |
| **Total per turn** | **~2000-4000** | Well within any model's context |
| **Cumulative (100 turns)** | **~60K-80K** | Tests context window limits |

For models with smaller context windows, the history window is the pressure relief valve — it gets truncated first.

---

## System Prompt

```
You are playing Terminus, a colony management strategy game. You control a colony and must maximize your score over 100 turns by building infrastructure, managing workers, trading resources, and surviving catastrophes.

## GAME RULES

RESOURCES: Food, Materials, Knowledge, Gold. Each has a capacity limit (base 500/500/200/300, increased by Warehouse).

POPULATION: Starts at 20. Grows +1 when food surplus > 60. Dies -1/turn when food = 0. Max = 50 + (Housing level × 15).

MORALE: Range 0.5–1.5. Multiplies ALL production. Rises with food surplus (+0.01/turn) and successful trades (+0.01). Falls with starvation (-0.05/turn) and population deaths (-0.02 each).

WORKERS: You have exactly [population] workers. Allocate across 6 roles:
- Farming → produces Food
- Mining → produces Materials  
- Research → produces Knowledge
- Construction → builds/upgrades buildings (progress = workers × 2 ticks/tick)
- Defense → reduces raid/attack damage
- Medicine → reduces plague/disease damage

PRODUCTION: Per tick = base_rate × (role_workers / population) × location_mod × spec_mod × morale × (1 + building_bonus)

BUILDINGS: Max one of each type, max level 3. Must have resources to build. Construction takes time (needs Construction workers).

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

MARKET: Buy resources with Gold. Sell resources for Gold.
- Buy price = base_price (Food:2, Materials:3, Knowledge:5) ± 20% volatility
- Sell revenue = buy_price × 0.7 (or ×0.85 with Trade specialization)
- Prices spike after catastrophes

CATASTROPHES: Occur periodically (every ~8-10 minutes). 30-second warning before impact. Types:
- Population (plague, disease, blizzard) → kills colonists. Mitigate: Hospital, Medicine workers
- Resource (drought, locusts, famine) → destroys food/materials. Mitigate: Warehouse, Farm
- Infrastructure (earthquake, flood, fire) → damages buildings. Mitigate: Wall
- Economic (raiders, bandits) → steals gold/resources. Mitigate: Wall, Defense workers

SCORING: population×10 + food×1 + materials×1 + knowledge×3 + gold×2 + building_health×5 + morale×150 + achievements

## RESPONSE FORMAT

Respond with a single JSON object. No other text.

{
  "action": "ACTION_TYPE",
  "params": { ... },
  "reasoning": {
    "factors": [
      {"factor": "FACTOR_NAME", "weight": 0.0-1.0},
      {"factor": "FACTOR_NAME", "weight": 0.0-1.0}
    ]
  }
}

ACTION TYPES AND PARAMS:
- {"action": "BUILD", "params": {"building_type": "farm"}}
- {"action": "UPGRADE", "params": {"building_type": "farm"}}
- {"action": "ALLOCATE_WORKERS", "params": {"allocation": {"farming": N, "mining": N, "research": N, "construction": N, "defense": N, "medicine": N}}}
- {"action": "TRADE_BUY", "params": {"resource": "food", "quantity": N}}
- {"action": "TRADE_SELL", "params": {"resource": "materials", "quantity": N}}
- {"action": "DEMOLISH", "params": {"building_type": "farm"}}
- {"action": "REPAIR", "params": {"building_type": "wall"}}
- {"action": "PASS", "params": {}}

ALLOCATE_WORKERS: All 6 roles required. Sum MUST equal current population exactly.

REASONING FACTORS (select 2-4 that most influenced your decision, weights must sum to 1.0):
- resource_bottleneck: Addressing a critical resource shortage
- long_term_growth: Investing in future capacity/production
- opponent_pressure: Responding to opponent's strategy or lead
- catastrophe_preparation: Building defenses before disaster
- market_opportunity: Exploiting favorable prices
- efficiency_optimization: Improving resource conversion rates
- defensive_positioning: Protecting existing assets
- cooperative_opportunity: Pursuing mutual benefit
- specialization_synergy: Leveraging location/specialization bonuses
- immediate_survival: Preventing colony collapse (starvation, morale crash)
- information_gathering: Acting to learn game state
- risk_diversification: Spreading investment across areas
```

---

## Per-Turn User Message Template

Sent every tick as the user message. Variables in `{{brackets}}` are filled by the orchestrator.

```
Turn {{turn_number}}/100 | Score: {{current_score}} (Rank {{rank}}/{{total_players}})

## YOUR COLONY
Location: {{location}} | Specialization: {{specialization}}
Population: {{population}}/{{pop_cap}} | Morale: {{morale}}

Resources:
- Food: {{food}}/{{food_cap}} ({{food_production}}/tick, consuming {{food_consumption}}/tick)
- Materials: {{materials}}/{{materials_cap}} ({{materials_production}}/tick)
- Knowledge: {{knowledge}}/{{knowledge_cap}} ({{knowledge_production}}/tick)
- Gold: {{gold}}/{{gold_cap}} ({{gold_production}}/tick)

Workers: {{total_workers}} allocated as:
  Farming: {{farming}} | Mining: {{mining}} | Research: {{research}}
  Construction: {{construction}} | Defense: {{defense}} | Medicine: {{medicine}}

Buildings:
{{#each buildings}}
- {{name}} L{{level}} ({{health}}/{{max_health}} HP){{#if under_construction}} [BUILDING: {{ticks_remaining}} ticks left]{{/if}}
{{/each}}
{{#if no_buildings}}
- None built yet
{{/if}}

## MARKET PRICES (current)
- Food: {{food_price}}G | Materials: {{mat_price}}G | Knowledge: {{know_price}}G
{{#if price_trend}}
Price trend: {{price_trend}}
{{/if}}

## OPPONENTS
{{#each opponents}}
- {{name}}: Score {{score}} | Pop {{population}} | Notable: {{visible_info}}
{{/each}}

{{#if catastrophe_warning}}
## ⚠️ CATASTROPHE WARNING
Type: {{catastrophe_category}}{{#if catastrophe_type}} ({{catastrophe_type}}){{/if}}
Arriving in: {{ticks_until}} ticks
{{/if}}

{{#if last_catastrophe_result}}
## LAST CATASTROPHE RESULT
{{catastrophe_name}}: {{damage_summary}}
{{/if}}

## AVAILABLE ACTIONS
{{#each available_actions}}
- {{action_type}}: {{description}} {{#if cost}}(Cost: {{cost}}){{/if}}
{{/each}}

Choose one action. Respond with JSON only.
```

---

## History Window

Included between system prompt and current turn message. Shows the LLM its recent actions and their outcomes.

### Format

```
## RECENT HISTORY (last {{window_size}} turns)

Turn {{N-5}}: Action: BUILD farm | Result: Success, construction started (15 ticks)
Turn {{N-4}}: Action: ALLOCATE_WORKERS {farming:8, mining:5, research:3, construction:3, defense:1, medicine:0} | Result: Applied
Turn {{N-3}}: Action: TRADE_BUY food 20 | Result: Success, spent 42G, received 20 food
Turn {{N-2}}: Action: BUILD hospital | Result: FAILED - insufficient resources (need 15K, have 10K)
Turn {{N-1}}: Action: PASS | Result: No action taken
```

### Truncation Policy

| Context Budget Remaining | History Window Size |
|--------------------------|---------------------|
| > 4000 tokens free | Last 20 turns |
| 2000-4000 tokens free | Last 10 turns |
| 1000-2000 tokens free | Last 5 turns |
| < 1000 tokens free | Last 2 turns |

History is always truncated from the oldest entries first. The system prompt and current state are never truncated.

---

## State Probe Prompts (Off-Clock)

These are sent at turns 10, 25, 50, 75, and 100 as separate API calls. They don't consume a game turn — the game pauses, the probe is sent, the response is recorded for metrics, then normal play resumes.

### Probe 1: Building Inventory

```
This is a state awareness check. Do not take an action.

From memory, list ALL buildings in your colony with their current level and approximate health status. Do not look at the game state above — answer from what you remember.

Respond with JSON:
{
  "probe_response": {
    "buildings": [
      {"type": "building_name", "level": N, "health_pct": N}
    ]
  }
}
```

### Probe 2: Resource Awareness

```
This is a state awareness check. Do not take an action.

Without looking at the current numbers, estimate your current resource levels and production rates from memory.

Respond with JSON:
{
  "probe_response": {
    "estimated_resources": {
      "food": N,
      "materials": N,
      "knowledge": N,
      "gold": N,
      "population": N,
      "morale": N
    }
  }
}
```

### Probe 3: Strategy Check

```
This is a strategy consistency check. Do not take an action.

What is your current strategic priority? What are you working toward in the next 10-20 turns? Has your strategy changed recently, and if so, why?

Respond with JSON:
{
  "probe_response": {
    "current_priority": "brief description",
    "next_goal": "what you're building toward",
    "strategy_changed": true/false,
    "change_reason": "why it changed (if applicable)"
  }
}
```

### Probe 4: History Recall

```
This is a memory recall check. Do not take an action.

Answer the following from memory:
1. What was the last catastrophe that hit your colony? What type was it and roughly when?
2. What was the first building you constructed this game?
3. Have you made any trades in the last 10 turns? If so, what?

Respond with JSON:
{
  "probe_response": {
    "last_catastrophe": {"type": "name", "approximate_turn": N},
    "first_building": "building_name",
    "recent_trades": [{"type": "buy/sell", "resource": "name", "quantity": N}]
  }
}
```

### Probe Implementation Notes

- Probes are sent as a **new message in the same conversation** (maintaining context)
- The game state header is NOT included in probe messages (that's the point — test memory)
- Probe responses are stored but NOT included in the history window for subsequent turns
- Token cost of probes is tracked separately (not charged to the game's context budget)
- If a model refuses to answer or returns invalid JSON, score as 0 for that probe

---

## Few-Shot Examples

Included in the system prompt during the first 3 turns only (to bootstrap behavior), then removed to save tokens.

### Example 1: Early Game Build

```json
{
  "action": "BUILD",
  "params": {"building_type": "farm"},
  "reasoning": {
    "factors": [
      {"factor": "long_term_growth", "weight": 0.6},
      {"factor": "immediate_survival", "weight": 0.4}
    ]
  }
}
```

### Example 2: Worker Allocation

```json
{
  "action": "ALLOCATE_WORKERS",
  "params": {
    "allocation": {
      "farming": 8,
      "mining": 5,
      "research": 2,
      "construction": 3,
      "defense": 1,
      "medicine": 1
    }
  },
  "reasoning": {
    "factors": [
      {"factor": "resource_bottleneck", "weight": 0.5},
      {"factor": "long_term_growth", "weight": 0.3},
      {"factor": "catastrophe_preparation", "weight": 0.2}
    ]
  }
}
```

### Example 3: Market Trade

```json
{
  "action": "TRADE_BUY",
  "params": {"resource": "materials", "quantity": 15},
  "reasoning": {
    "factors": [
      {"factor": "market_opportunity", "weight": 0.7},
      {"factor": "efficiency_optimization", "weight": 0.3}
    ]
  }
}
```

---

## Available Actions Filtering

The per-turn message includes only **actions the LLM can actually perform** given current state. This reduces invalid actions from models that can't do math well, while still allowing the "invalid action rate" metric to trigger when a model attempts an action with wrong quantities.

### Filtering Rules

| Action | Shown When |
|--------|-----------|
| BUILD X | Colony doesn't have building X AND can afford L1 cost |
| UPGRADE X | Colony has building X at level < 3 AND can afford next level AND building not under construction |
| ALLOCATE_WORKERS | Always shown (population > 0) |
| TRADE_BUY X | Colony has gold > 0 AND market has stock |
| TRADE_SELL X | Colony has resource X > 0 |
| DEMOLISH X | Colony has building X AND it's not under construction |
| REPAIR X | Colony has building X AND building health < max AND has materials |
| PASS | Always shown |

### Example Available Actions Section

```
## AVAILABLE ACTIONS
- BUILD farm (Cost: 30 materials, 10 gold)
- BUILD mine (Cost: 20 food, 15 gold)
- ALLOCATE_WORKERS (reassign your 20 workers across 6 roles)
- TRADE_BUY food (Price: 2.1G/unit, you have 50G)
- TRADE_BUY materials (Price: 3.2G/unit, you have 50G)
- TRADE_SELL knowledge (Price: 3.5G/unit sell, you have 10K)
- PASS (do nothing this turn)
```

Note: TRADE quantities are NOT pre-filled — the LLM must choose how much to buy/sell. This tests numerical grounding (can it compute max affordable quantity?).

---

## Error Recovery Prompts

When the LLM returns invalid responses, a retry prompt is appended:

### Invalid JSON

```
Your previous response was not valid JSON. Please respond with ONLY a JSON object in the exact format specified. No markdown, no explanation, no code blocks. Just the JSON object.

Previous response (invalid): {{truncated_response}}

Try again:
```

### Invalid Action (game rules violated)

```
Your previous action was invalid: {{rejection_reason}}

Examples of what went wrong:
{{#if insufficient_resources}}- You tried to {{action}} but need {{required}} and only have {{actual}}{{/if}}
{{#if worker_sum_mismatch}}- Worker allocation must sum to exactly {{population}} (you specified {{sum}}){{/if}}
{{#if building_exists}}- You already have a {{building_type}}{{/if}}
{{#if max_level}}- {{building_type}} is already at max level 3{{/if}}

Your current state hasn't changed. Choose a different action:
```

### Retry Policy

| Attempt | Prompt Modification |
|---------|-------------------|
| 1st try | Normal turn prompt |
| 2nd try (after invalid JSON) | Append error recovery + last response |
| 3rd try (after 2nd invalid) | Append error recovery + simplified format reminder |
| 4th failure | Default to PASS, record as 3 invalid attempts |

For game-invalid actions (valid JSON but rule violation): **no retry**. The invalid action is recorded and scored. The next turn proceeds normally. This is intentional — retries would hide the model's numerical errors from metrics.

---

## Conversation Structure

Each turn is a single API call with the full conversation:

```
messages: [
  {role: "system", content: SYSTEM_PROMPT},
  {role: "user", content: "Turn 1/100 | Score: 0 ...\n\n## RECENT HISTORY\n(none)\n\nChoose one action."},
  {role: "assistant", content: '{"action": "BUILD", "params": {"building_type": "farm"}, "reasoning": {...}}'},
  {role: "user", content: "Turn 2/100 | Score: 15 ...\n\n## RECENT HISTORY\nTurn 1: BUILD farm | Success\n\nChoose one action."},
  {role: "assistant", content: '{"action": "ALLOCATE_WORKERS", ...}'},
  ...
  {role: "user", content: "Turn N/100 | Score: 342 ...\n\n## RECENT HISTORY\n...\n\nChoose one action."}
]
```

### Context Management Strategy

As the conversation grows, the orchestrator manages context using one of two strategies (configurable):

**Strategy A: Full Conversation (Default for models with 128K+ context)**
- Keep the entire conversation history
- System prompt + all user/assistant message pairs
- Tests true context window utilization
- Cumulative tokens grow: ~60-80K by turn 100

**Strategy B: Sliding Window (For models with <32K context)**
- System prompt (always kept)
- Last N turns as conversation pairs
- Summarized history replacing older turns
- Keeps total under model's context limit

The strategy is auto-selected based on the model's known context window, but can be overridden in config.

---

## Temperature & Generation Settings

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| temperature | 0.3 | Low enough for consistent play, high enough for strategy diversity |
| max_tokens | 300 | Sufficient for any valid response, prevents runaway generation |
| top_p | 0.95 | Standard nucleus sampling |
| response_format | json_object | Force JSON mode where supported (OpenAI, some others) |
| stop sequences | None | JSON mode handles termination |

These are fixed across all models for fair comparison. Not configurable per-run.

---

## Adapter-Specific Formatting

### OpenAI-Compatible (GPT, Claude via proxy, Ollama, vLLM)

```python
{
    "model": config.model_name,
    "messages": messages,
    "temperature": 0.3,
    "max_tokens": 300,
    "top_p": 0.95,
    "response_format": {"type": "json_object"}  # if supported
}
```

### Anthropic Direct

```python
{
    "model": config.model_name,
    "system": SYSTEM_PROMPT,
    "messages": messages[1:],  # exclude system (it's separate)
    "temperature": 0.3,
    "max_tokens": 300
}
```

### Google Generative AI

```python
{
    "model": config.model_name,
    "contents": convert_to_google_format(messages),
    "generationConfig": {
        "temperature": 0.3,
        "maxOutputTokens": 300,
        "topP": 0.95,
        "responseMimeType": "application/json"
    }
}
```

---

## Design Decisions & Rationale

### Why structured reasoning factors instead of free-text?

1. **Token efficiency**: ~30 tokens vs ~100-200 for free text reasoning
2. **Fair comparison**: All models use the same vocabulary — no advantage to more eloquent models
3. **Metric signal**: Directly feeds Dimension 1 (Coherence) — can algorithmically detect factor drift without NLP parsing
4. **Reproducibility**: Structured output is deterministically parseable

### Why filter available actions?

1. **Reduces noise**: Models that can't count won't spam impossible builds every turn
2. **Preserves signal**: Quantity errors in TRADE and worker sums still test arithmetic (those aren't pre-computed)
3. **Fairness**: Weaker models aren't penalized for not knowing game rules — they're penalized for not doing math within those rules
4. **Realism**: Real agentic systems tell the model what tools are available — we're testing tool USE, not tool DISCOVERY

### Why include few-shots only for first 3 turns?

1. **Bootstrap**: Ensures even weak models produce valid JSON from turn 1
2. **Token savings**: ~300 tokens saved per turn after turn 3 (30K tokens saved over 100 turns)
3. **Tests learning**: After turn 3, the model must rely on its own prior responses as examples
4. **Fairness**: All models get the same bootstrap period

### Why 0.3 temperature?

1. **Consistency**: Lower variance between runs of the same model — important for statistical significance
2. **Strategy diversity**: Not 0.0, because we want models to explore different strategies across games
3. **Compromise**: High enough to avoid repetitive play, low enough to make metrics meaningful

---

## Appendix: Complete System Prompt Token Count Estimate

| Section | Tokens (approx.) |
|---------|-------------------|
| Introduction + rules overview | ~200 |
| Resources, population, morale, workers | ~250 |
| Production formula | ~50 |
| Building table | ~300 |
| Market rules | ~100 |
| Catastrophe summary | ~100 |
| Scoring formula | ~50 |
| Response format + action types | ~150 |
| Reasoning factors list | ~100 |
| **Total** | **~1300** |

With few-shot examples (first 3 turns): +~200 tokens = ~1500 total system prompt.

This leaves ample room for state + history within any model's context window.
