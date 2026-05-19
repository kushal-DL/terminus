# Terminus LLM Benchmark — Metrics Specification

This document defines the complete 3-tier measurement framework: game-level metrics (raw data), cognitive dimension metrics (what we're actually measuring), and their mapping to production agentic workflows.

---

## Architecture: 3-Tier Metric System

```
┌─────────────────────────────────────────────────────────────────────┐
│  TIER 3: Agentic Workflow Predictions                                │
│  "What does this mean for my production AI system?"                  │
│  → Agent step budget, tool-call reliability, SLA predictability      │
├─────────────────────────────────────────────────────────────────────┤
│  TIER 2: Cognitive Dimensions (8)                                    │
│  "What does this reveal about the LLM's capabilities?"               │
│  → Coherence, Arithmetic, Triage, Error Recog, Pivot, Degradation,  │
│    Opportunity Cost, Game Theory                                     │
├─────────────────────────────────────────────────────────────────────┤
│  TIER 1: Game-Level Metrics (31 specific measurements)               │
│  "What happened in the game?"                                        │
│  → Build order, invalid actions, recovery speed, state probes,       │
│    opponent modeling, context pressure, etc.                          │
└─────────────────────────────────────────────────────────────────────┘
```

Tier 1 feeds Tier 2. Tier 2 feeds Tier 3. The HTML report shows all three.

---

# TIER 1: Game-Level Metrics

These are the raw measurements collected from gameplay. Each maps to one or more Tier 2 cognitive dimensions.

---

## 1. Planning Metrics (6 measurements)

### 1.1 Build Order Efficiency

**Definition:** Did the LLM build infrastructure prerequisites before production buildings? (Housing before Farm when pop-capped; Warehouse before stockpiling for L3 upgrades.)

**Data Collection:** Record every BUILD action. At each decision, check:
- Was population at cap (≥50 base or ≥ Housing limit) without Housing queued?
- Was any resource at capacity without Warehouse?
- Was a production building started before its prerequisite?

**Formula:**
```
build_order_score = (prerequisite_first_builds) / (builds_where_prerequisite_was_needed)
```

**Example:** LLM has pop=50 (cap), no Housing. It builds a Farm (food goes to waste since pop can't grow to use it). Score: 0. Correct action: Build Housing first.

---

### 1.2 Worker Allocation Anticipation

**Definition:** Did the LLM pre-allocate construction workers BEFORE starting a build?

**Data Collection:** Compare worker allocation at tick T-1 (before BUILD) vs tick T (after BUILD).

| Scenario | Score |
|----------|-------|
| Construction workers already allocated before build command | 1.0 |
| Construction workers allocated same tick as build | 0.5 |
| Construction workers allocated 1-3 ticks after build | 0.3 |
| Construction workers never allocated (build proceeds at minimum speed) | 0.0 |

**Formula:**
```
anticipation_score = mean(per_build_anticipation_scores)
```

---

### 1.3 Market Timing

**Definition:** Did the LLM buy when prices were below rolling average and sell when above?

**Data Collection:** Track market price at each TRADE action. Compute 20-tick rolling average per resource.

**Formula:**
```
For buys:  score = 1.0 if buy_price < rolling_avg, else 0.0
For sells: score = 1.0 if sell_price > rolling_avg, else 0.0
market_timing_score = mean(all_trade_scores)
```

---

### 1.4 Catastrophe Preparation

**Definition:** Did the LLM invest in mitigation buildings BEFORE the first catastrophe?

**Data Collection:** Record timing of defense building (Hospital, Wall, Watchtower) construction relative to first catastrophe tick.

| Timing | Score |
|--------|-------|
| Built before first catastrophe warning (30s prior) | 1.0 |
| Built between warning and catastrophe | 0.5 |
| Built within 30 ticks after first catastrophe | 0.2 |
| Never built | 0.0 |

---

### 1.5 Housing-Before-Growth

**Definition:** Did the LLM build Housing before hitting population cap, enabling continuous growth?

**Data Collection:** Track ticks where population == cap AND no Housing under construction.

**Formula:**
```
housing_score = 1.0 - min(1.0, capped_ticks_without_housing / 30)
```

30+ ticks at cap without Housing = 0.0.

---

### 1.6 Resource Stockpile Timing

**Definition:** When saving for an expensive upgrade (L2/L3), how many idle ticks (no productive action) passed?

**Data Collection:** At every tick with no active construction and no recent action: compute ticks-to-afford for best available upgrade. Track "dead time" — ticks where the LLM could have been producing but wasn't.

**Formula:**
```
stockpile_score = 1.0 - (idle_ticks / expected_optimal_ticks)
```

Clamped to [0, 1].

---

## 2. Numerical Metrics (6 measurements)

### 2.1 Invalid Action Rate

**Definition:** How often did the LLM attempt an action it cannot afford?

**Data Collection:** Every action passes through the engine validator. Record rejections with reason "insufficient resources."

**Formula:**
```
invalid_rate_score = 1.0 - (rejected_actions / total_actions_attempted)
```

**Examples of invalid actions:**
- BUILD Farm L1 when materials < 30 or gold < 10
- TRADE_BUY 50 food when gold < 50 × buy_price
- UPGRADE Wall to L2 when materials < 100 or gold < 25

---

### 2.2 Worker Sum Accuracy

**Definition:** Does the LLM's worker allocation always sum exactly to population?

**Data Collection:** Every ALLOCATE_WORKERS action: sum(farming + mining + research + construction + defense + medicine). Compare to current population.

**Formula:**
```
worker_sum_score = (correct_allocations) / (total_allocation_attempts)
```

A model that sends `{farming: 10, mining: 8, research: 5, construction: 3, defense: 2, medicine: 2}` when population is 28 → fails (sum=30≠28).

---

### 2.3 Over-Capacity Errors

**Definition:** Did the LLM buy more resources than storage capacity allows?

**Data Collection:** Record TRADE_BUY actions where: current_resource + quantity > max_capacity. (Excess is wasted — gold spent for nothing.)

**Formula:**
```
capacity_score = 1.0 - (wasted_purchases / total_purchases)
```

**Example:** Food capacity = 500. Current food = 480. LLM buys 50 food → 30 units wasted. Error flagged.

---

### 2.4 Production Rate Awareness

**Definition:** Does the LLM correctly time builds around production income?

**Data Collection:** When a BUILD fails (can't afford), then succeeds N ticks later:
- Compute: `expected_ticks = resource_deficit / production_rate_of_that_resource`
- Compare expected vs actual wait time

**Formula:**
```
timing_score = (builds_within_±3_ticks_of_optimal) / (total_deferred_builds)
```

---

### 2.5 Trade Math Accuracy

**Definition:** Does the LLM understand the sell spread (70% of buy price, or 85% for Trade spec)?

**Data Collection:** Flag trades where the LLM sells a resource it recently bought at a net loss (buy at price P, sell at P×0.70 — losing 30% immediately). This indicates the LLM doesn't understand the spread mechanic.

**Formula:**
```
trade_math_score = 1.0 - (loss_trades_within_10_ticks_of_buy / total_sell_trades)
```

---

### 2.6 Multi-Resource Feasibility

**Definition:** When a build requires 3+ resource types simultaneously, does the LLM verify ALL are sufficient?

**Data Collection:** Track builds requiring multiple resources (e.g., Hospital L1: 45 materials + 15 knowledge + 15 gold). Flag cases where the LLM has enough of 2/3 resources but not all, and attempts anyway.

**Formula:**
```
feasibility_score = (multi_resource_builds_where_all_sufficient) / (total_multi_resource_build_attempts)
```

---

## 3. Flexibility Metrics (7 measurements)

### 3.1 Post-Catastrophe Recovery Speed

**Definition:** Ticks to return to ≥90% of pre-catastrophe production rate.

**Data Collection:**
1. Record total production rate (food+materials+knowledge per tick) at catastrophe-5 ticks
2. After catastrophe resolves, measure ticks until production ≥ 90% of baseline

**Formula:**
```
recovery_score = max(0, 1.0 - (recovery_ticks / 30))
```
30+ ticks to recover = 0.0. Instant recovery = 1.0.

---

### 3.2 Worker Reallocation After Damage

**Definition:** Does the LLM shift workers to address the specific damage type?

**Data Collection:** Compare worker allocation at catastrophe-1 tick vs catastrophe+3 ticks.

| Catastrophe Type | Correct Response | Score |
|-----------------|-----------------|-------|
| Population (Plague, Disease) | Medicine workers increase | 1.0 |
| Infrastructure (Earthquake, Flood) | Construction workers increase | 1.0 |
| Resource (Drought, Locusts) | Farming workers increase | 1.0 |
| Economic (Raiders, Bandits) | Defense workers increase | 1.0 |
| No change in allocation | — | 0.0 |
| Wrong reallocation (e.g., mining after plague) | — | 0.1 |

---

### 3.3 Repair Prioritization

**Definition:** Does the LLM repair highest-value buildings first?

**Data Collection:** After building damage, record the order of REPAIR actions. Compute optimal order: buildings ranked by (score_contribution_per_HP × damage_taken).

**Formula:**
```
repair_score = kendall_tau(LLM_repair_order, optimal_repair_order)
```

Kendall's tau = 1.0 if perfectly matched, -1.0 if perfectly reversed, normalized to [0, 1].

---

### 3.4 Market Adaptation After Price Shock

**Definition:** Does the LLM exploit catastrophe-triggered price spikes?

**Data Collection:** After catastrophe price shocks (+30-40% on affected resources), track the LLM's next 10 ticks of trades.

| Action | Score |
|--------|-------|
| Sells the spiked resource (exploiting high price) | +1.0 |
| Holds (doesn't buy at inflated price) | +0.3 |
| Buys the spiked resource (paying premium) | -0.5 |

**Formula:**
```
market_adapt_score = mean(per_trade_scores), clamped [0, 1]
```

---

### 3.5 Starvation Response Speed

**Definition:** When food hits 0 and population starts dying (-1/tick), how fast does the LLM react?

**Data Collection:** Detect food=0 events. Measure:
- Ticks until farming workers increase (a)
- Ticks until TRADE_BUY food (b)
- Minimum of (a, b)

| Response Time | Score |
|---------------|-------|
| ≤ 2 ticks | 1.0 |
| 3-5 ticks | 0.7 |
| 6-10 ticks | 0.3 |
| > 10 ticks or never | 0.0 |

---

### 3.6 Defense Investment After First Hit

**Definition:** After surviving a catastrophe with >20% damage, does the LLM invest in mitigation?

**Data Collection:** After first catastrophe where damage > 20% of max possible: track whether a defense building (Hospital/Wall/Watchtower) is built or upgraded within 30 ticks.

**Formula:**
```
defense_learn_score = 1.0 if mitigation_built_within_30_ticks, else 0.0
```

---

### 3.7 Action Distribution Shift

**Definition:** Does the LLM's action pattern change meaningfully after a disruption?

**Data Collection:** Compute action type distribution (BUILD/TRADE/ALLOCATE/REPAIR/other) for 15 ticks pre-disruption and 15 ticks post-disruption.

**Formula:**
```
shift_score = jensen_shannon_divergence(pre_distribution, post_distribution)
```

Normalized to [0, 1]. Higher divergence = more flexibility. A model that does the exact same thing regardless of circumstances scores 0.

---

## 4. State Probe Metrics (4 measurements)

At turns 10, 25, 50, 75, and 100, the benchmark injects **off-clock state probes** — structured queries that ask the LLM about its own state. These are separate from gameplay turns (the game pauses, the probe doesn't consume a turn, and the response isn't an action). This directly tests the model's internal representation accuracy.

### 4.1 Building Inventory Recall

**Definition:** Can the LLM correctly list its current buildings, their levels, and health status?

**Data Collection:** At each probe checkpoint, ask:
```json
{"probe": "list_buildings", "instruction": "List all your buildings with their current level and health percentage."}
```

Compare LLM's response to actual building state.

**Formula:**
```
inventory_score = (correctly_listed_buildings) / (total_actual_buildings)

Penalties:
  - Hallucinated building (listed but doesn't exist): -0.2 per hallucination
  - Wrong level stated: -0.1 per error
  - Wrong health (>20% off): -0.05 per error
```

Clamped to [0, 1].

---

### 4.2 Resource Awareness Accuracy

**Definition:** Does the LLM know its current resource levels within ±15% of actual values?

**Data Collection:** At each probe checkpoint, ask:
```json
{"probe": "resource_state", "instruction": "State your current resource levels: food, materials, knowledge, gold, population, morale."}
```

Compare each stated value to actual.

**Formula:**
```
Per resource: accurate if |stated - actual| / max(actual, 1) ≤ 0.15
resource_score = (accurate_resources) / (total_resources_queried)
```

**Degradation tracking:** Plot resource_score at each checkpoint (turns 10/25/50/75/100) to detect drift over time.

---

### 4.3 Strategy Consistency Check

**Definition:** Does the LLM's stated strategy logically follow from its previous statements + events that have occurred?

**Data Collection:** At each probe checkpoint, ask:
```json
{"probe": "current_strategy", "instruction": "What is your current strategic priority and why?"}
```

Compare to:
- Previous checkpoint's stated strategy
- Environmental events between checkpoints
- Actual actions taken between checkpoints

**Scoring:**

| Scenario | Score |
|----------|-------|
| Strategy unchanged, no trigger for change, actions match | 1.0 |
| Strategy changed, valid trigger exists, actions match new strategy | 1.0 |
| Strategy unchanged, trigger exists that should have changed it | 0.3 |
| Strategy changed, no trigger, but actions still match new strategy | 0.4 |
| Strategy stated contradicts actual actions taken | 0.0 |
| Strategy changed, no trigger, actions don't match either strategy | 0.0 |

**Formula:**
```
strategy_score = mean(per_checkpoint_scores)
```

---

### 4.4 History Event Recall

**Definition:** Can the LLM correctly reference specific past events when asked?

**Data Collection:** At checkpoints ≥ turn 25, ask about a specific past event:
```json
{"probe": "history_recall", "instruction": "What was the last catastrophe that hit your colony, and what did you do in response?"}
```

Or: "What was your first building?" / "When did you last trade on the market and why?"

Compare stated event details to actual game log.

**Scoring:**

| Accuracy | Score |
|----------|-------|
| Correct event, correct details (type, timing, response) | 1.0 |
| Correct event, minor detail errors (off by 1-3 ticks) | 0.8 |
| Correct event type, wrong details (wrong severity, wrong response claimed) | 0.4 |
| Wrong event entirely (confabulation) | 0.0 |
| Admits uncertainty ("I don't recall exactly") | 0.3 |

**Formula:**
```
history_score = mean(per_probe_scores)
```

---

## 5. Opponent-Aware Metrics (5 measurements)

These metrics require running the LLM against multiple opponent types. Each opponent archetype creates a distinct strategic environment.

**Opponent Archetypes:**

| Agent | Strategy | Tests |
|-------|----------|-------|
| Random | Uniform random from valid actions | Baseline — any competent model should dominate |
| Greedy | Always picks highest immediate-value action | Can the LLM outperform short-term optimization? |
| Balanced | Fixed optimal build order + smart allocation | Can the LLM beat a "textbook" strategy? |
| Rush | Aggressive early expansion, ignores defense | Can the LLM exploit overcommitment? |
| Turtle | Heavy defense, slow growth, strong late-game | Can the LLM win before turtle's advantage matures? |
| Adversarial | Targets the LLM's observed weaknesses | Can the LLM resist active exploitation? |

### 5.1 Win Rate vs Opponent Archetypes

**Definition:** Normalized win rate across all opponent types, weighted by opponent difficulty.

**Data Collection:** Run N games per opponent type. Record wins/losses/draws.

**Formula:**
```
weighted_win_rate = Σ(win_rate_vs_type × difficulty_weight) / Σ(difficulty_weights)

Difficulty weights:
  Random: 0.5 (expected to win easily)
  Greedy: 1.0
  Balanced: 1.5
  Rush: 1.5
  Turtle: 1.5
  Adversarial: 2.0
```

---

### 5.2 Exploitation Resistance

**Definition:** How well does the LLM perform against an adversarial agent specifically targeting its weaknesses?

**Data Collection:** The adversarial agent observes the LLM's first 3 games, identifies patterns (e.g., always builds Farm first, never builds Wall, doesn't trade), then exploits those patterns in subsequent games.

**Formula:**
```
exploitation_resistance = LLM_score_vs_adversarial / LLM_score_vs_balanced

If ratio ≥ 0.85: resistance = 1.0 (barely affected by exploitation)
If ratio ≤ 0.40: resistance = 0.0 (highly exploitable)
Linear interpolation between.
```

**Reported:** Performance drop % when facing adversarial vs balanced opponent.

---

### 5.3 Counter-Strategy Detection Speed

**Definition:** How many turns does the LLM take to identify and adapt to an opponent's strategy?

**Data Collection:** Track the LLM's action distribution. Detect when the LLM's strategy shifts in a way that specifically counters the opponent's archetype.

| Opponent | Expected Counter | Detection Signal |
|----------|-----------------|-----------------|
| Rush | Build Wall/defense early, prioritize military workers | Defense allocation increases within N turns |
| Turtle | Aggressive early expansion to build lead | Build rate increases, market exploitation |
| Greedy | Long-term investments the greedy agent can't match | Infrastructure-heavy early game |

**Formula:**
```
detection_speed_score based on turns to detect:
  ≤ 10 turns: 1.0
  11-20 turns: 0.7
  21-35 turns: 0.4
  36-50 turns: 0.2
  Never detects: 0.0
```

---

### 5.4 Cooperative Surplus Capture

**Definition:** In scenarios where mutual benefit is possible (both players can gain more by coordinating than competing), does the LLM identify and pursue cooperative opportunities?

**Data Collection:** Create test scenarios where:
- Both players benefit from trading complementary resources (one overproduces food, other overproduces materials)
- Market dynamics reward coordination (both buying the same resource crashes its availability)
- Shared catastrophe defense (both building Walls reduces damage to both)

Measure: what % of the theoretically available cooperative surplus does the LLM capture?

**Formula:**
```
cooperative_surplus = (LLM_score_in_cooperative_scenario - LLM_score_in_competitive_scenario) / (theoretical_max_cooperative_gain)

Clamped to [0, 1]. 0 = never cooperates. 1 = captures all available mutual benefit.
```

**Note:** This is only measured in specific cooperative scenarios, not all games.

---

### 5.5 Market Manipulation Detection

**Definition:** Does the LLM detect and counter opponent market manipulation (pump-and-dump, price cornering)?

**Data Collection:** Use a specialized market-manipulator opponent that:
1. Buys large quantities of a resource (price spikes)
2. Waits for the LLM to panic-buy at inflated price
3. Sells its reserve at peak

Track whether the LLM:
- Buys at inflated price (falls for manipulation): 0.0
- Holds and waits for correction: 0.5
- Counter-trades (sells the resource the opponent is pumping): 0.8
- Explicitly identifies the pattern and exploits it (buys before pump, sells during): 1.0

**Formula:**
```
manipulation_score = mean(per_manipulation_event_scores)
```

---

## 6. Context Pressure Metrics (3 measurements)

These metrics specifically measure quality degradation correlated with context window growth (token count), distinct from turn-based degradation.

### 6.1 Per-Quartile Decision Quality

**Definition:** Decision quality measured at each quartile of the game, enabling direct comparison of early-context vs late-context performance.

**Data Collection:** Divide game into 4 quartiles by turn count:
- Q1: Turns 1–25 (small context, ~2K-8K tokens cumulative)
- Q2: Turns 26–50 (medium context, ~8K-20K tokens)
- Q3: Turns 51–75 (large context, ~20K-40K tokens)
- Q4: Turns 76–100 (very large context, ~40K-80K+ tokens)

For each quartile, compute:
- Action validity rate (valid / attempted)
- Optimal action rate (best action chosen / total actions)
- Reasoning factor consistency (from Dim 1 coherence metrics)

**Formula:**
```
quartile_quality(Q) = (validity_rate × 0.4) + (optimality_rate × 0.35) + (coherence × 0.25)
```

**Key output:** The ratio Q4/Q1 — values near 1.0 mean no degradation. Values < 0.7 indicate significant context pressure.

---

### 6.2 Historical Reference Rate

**Definition:** In late-game reasoning, does the LLM still reference and use information from early-game events?

**Data Collection:** In Q3 and Q4, examine the LLM's reasoning factors and actions for evidence that early-game information is being used:

| Signal | Evidence |
|--------|----------|
| References past catastrophe timing | Factor "catastrophe_preparation" weighted higher after prior hits |
| Uses early market price data | Trading patterns account for historical price trends, not just current |
| Maintains early-game build strategy | Actions consistent with Q1 declared strategy (unless pivoted) |
| Recalls opponent behavior | Counter-strategy accounts for opponent's full game behavior, not just recent |

**Formula:**
```
reference_rate = (decisions_with_historical_evidence) / (total_Q3_Q4_decisions)

Scored from probe responses:
  - Explicitly references a specific past event correctly: 1.0
  - References a general pattern from earlier game: 0.7
  - No evidence of using historical context: 0.0
  - References a past event incorrectly (confabulation): -0.3
```

Clamped to [0, 1].

---

### 6.3 Context Collapse Point

**Definition:** The specific token count (estimated) at which decision quality first drops >20% from peak — the model's effective operational context window.

**Data Collection:**
1. Track cumulative tokens (input + output) across all turns
2. Compute quality score per turn (same formula as per-quartile quality)
3. Apply smoothing (5-turn rolling average to reduce noise)
4. Find first turn where smoothed_quality < 0.8 × peak_quality

**Formula:**
```
collapse_point = cumulative_tokens_at_first_20%_drop

If no drop occurs: collapse_point = "none" (model handles full game context)
```

**Reported Values:**
- **Collapse point** (tokens): The practical context limit
- **Collapse point** (turns): Which turn it corresponds to
- **Pre-collapse quality**: Average quality before the drop
- **Post-collapse quality**: Average quality after the drop
- **Collapse severity**: Magnitude of quality drop (gradual vs cliff)

**Significance:** This gives a practical "effective context window" — more useful than the model's theoretical maximum. A model with 128K context that cliff-fails at 40K tokens effectively has a 40K operational window.

---

## Data Collection Infrastructure

The benchmark recorder captures **per tick**:

| Data Point | Source | Fed to Metrics |
|---|---|---|
| Full resource state (food, materials, knowledge, gold, population, morale) | Engine snapshot | All |
| Worker allocation (6 roles: farming, mining, research, construction, defense, medicine) | Engine snapshot | 1.2, 2.2, 3.2 |
| Buildings (type, level, health, under_construction, ticks_remaining) | Engine snapshot | 1.1, 1.4, 1.5, 3.3, 3.6, 4.1 |
| Action attempted (type, params) | LLM response | 2.1-2.6, 3.7, 5.1-5.5 |
| Action validation result (success/failure + rejection reason) | Engine validator | 2.1, 2.3, 2.6 |
| Reasoning factors + weights (12 predefined factors) | LLM structured response | Cross-reference with all |
| Market prices per resource (current tick, 20-tick rolling avg) | Engine market | 1.3, 3.4, 5.5 |
| Production rates per resource | Calculated: base × workers × location × spec × morale × buildings | 1.6, 2.4, 3.1 |
| Catastrophe events (type, category, severity, damage dealt, mitigation applied) | Engine event log | 1.4, 3.1-3.6 |
| Running score | Scoring formula applied each tick | Trend analysis |
| Token count (input + output) | Adapter measurement | 6.1, 6.3 |
| Response latency (ms) | Adapter timer | Performance tracking |
| Opponent actions + state (visible portion) | Engine snapshot | 5.1-5.5 |
| Cumulative context size (tokens) | Adapter accumulator | 6.1, 6.2, 6.3 |

**Per checkpoint (turns 10, 25, 50, 75, 100) — off-clock probes:**

| Data Point | Source | Fed to Metrics |
|---|---|---|
| State probe response (buildings query) | LLM probe response | 4.1 |
| State probe response (resources query) | LLM probe response | 4.2 |
| State probe response (strategy query) | LLM probe response | 4.3 |
| State probe response (history query) | LLM probe response | 4.4 |
| Probe token count (not charged to game context) | Adapter measurement | Overhead tracking |

---

# TIER 2: Cognitive Dimensions

These are the 8 capabilities we actually report. Each is computed from a subset of Tier 1 game metrics.

---

## Dimension 1: Multi-Decision Coherence Decay

**What it answers:** "If I deploy this model in an agentic loop that runs 100+ sequential decisions, at what point does it start contradicting itself?"

**Why it's novel:** MT-Bench tests 2-turn coherence. ChatBot Arena tests preference on single exchanges. Nothing tests whether a model making its 73rd decision still remembers what it decided on decision #12 — and whether its current action logically follows from its stated strategy.

### Definition

The model declares reasoning factors (e.g., "long_term_growth" weighted 0.5) at every turn. Coherence measures whether the model's factor selections and actions remain logically consistent with its own prior declarations — unless an environmental event justifies a change.

### Data Collection

1. Record the model's top-2 reasoning factors (by weight) at every turn
2. Flag "coherence breaks" — turns where the top factor changes WITHOUT a disruption event in the prior 5 ticks
3. Plot coherence score per turn using a sliding window of 10 turns
4. Identify the **inflection point** — the turn number where coherence score first drops below 0.7

### Scoring

```
coherence_score = (coherent_transitions) / (total_transitions)

Where:
  coherent_transition = top_factor unchanged, OR top_factor changed with trigger within 5 ticks
  incoherent_transition = top_factor changed with no environmental trigger
```

### Reported Values

- **Coherence score** (0.0–1.0): Overall proportion of justified transitions
- **Inflection point** (turn number): Where coherence begins degrading
- **Decay rate** (slope after inflection): How fast it degrades once it starts

### Fed by Tier 1 Metrics

- Reasoning factors (per-turn structured response)
- Catastrophe event log (triggers)
- Market price shocks (triggers)
- Resource depletion events (triggers)

### State Representation Fidelity (Sub-Dimension)

**What it adds:** Beyond action-level coherence, this directly tests whether the model's *internal representation* of its own state remains accurate over time. A model can produce coherent actions while having a completely wrong mental model (getting lucky), or produce correct state recall while taking incoherent actions. Both signals together give the full picture.

**Data Collection:**

Uses Tier 1 §4 (State Probe Metrics) — injected at turns 10, 25, 50, 75, 100.

1. Compute **state fidelity score** per checkpoint:
   ```
   state_fidelity = (inventory_recall × 0.3) + (resource_awareness × 0.25) + (strategy_consistency × 0.25) + (history_recall × 0.2)
   ```

2. Plot state_fidelity across checkpoints to detect **representation drift**:
   - Stable: all checkpoints within ±0.1 of mean
   - Gradual drift: linear regression slope < -0.05/checkpoint
   - Cliff amnesia: any checkpoint drops >0.3 from previous

3. Cross-correlate with action coherence:
   - **Coherent actions + accurate state** = genuine understanding (ideal)
   - **Coherent actions + inaccurate state** = pattern-matching without comprehension (brittle)
   - **Incoherent actions + accurate state** = knows what's happening but can't decide (execution failure)
   - **Incoherent actions + inaccurate state** = lost (total degradation)

**Integrated Coherence Score:**

```
integrated_coherence = (action_coherence_score × 0.6) + (state_fidelity_score × 0.4)
```

This combined score replaces the standalone coherence_score in the final dimension report.

**Additional Reported Values (alongside existing Dim 1 outputs):**

- **State fidelity per checkpoint**: 5 data points showing drift
- **Representation drift rate**: Slope of fidelity across checkpoints
- **Coherence-fidelity quadrant**: Which of the 4 quadrants does the model fall into?
- **Amnesia point** (if applicable): Turn number where fidelity first drops below 0.6

---

## Dimension 2: Applied Arithmetic Under Cognitive Load

**What it answers:** "Can this model still do basic math when it's simultaneously tracking 15+ state variables?"

**Why it's novel:** GSM8K tests math in isolation — one clean word problem, full attention on the numbers. In real agentic workflows, the model must compute costs/budgets/timelines while also reasoning about strategy, reading context, and deciding between options. Terminus forces arithmetic under load: 4 resources + 6 worker roles + 10 building costs + market prices + production rates + population + morale — all simultaneously in context.

### Definition

The proportion of the model's actions that are numerically valid, weighted by cognitive load at the time of decision.

### Data Collection

Combine Tier 1 metrics: Invalid Action Rate (2.1), Worker Sum Accuracy (2.2), Over-Capacity Errors (2.3), Production Rate Awareness (2.4), Trade Math Accuracy (2.5), Multi-Resource Feasibility (2.6).

Additionally, measure **load factor** at each tick:
```
load_factor = (active_buildings / 10) + (market_volatility > 20%) + (catastrophe_within_30_ticks) + (turn_number / 100)
```

### Scoring

```
arithmetic_score = weighted_mean(
    invalid_rate_score × 2.0,
    worker_sum_score × 1.5,
    capacity_score × 1.0,
    timing_score × 1.0,
    trade_math_score × 1.0,
    feasibility_score × 1.5
)
```

### Reported Values

- **Overall arithmetic accuracy** (0.0–1.0)
- **Accuracy at low load** (turns 1-25): Early game, few variables
- **Accuracy at high load** (turns 75-100): Late game, full state
- **Load degradation**: Difference between low-load and high-load accuracy
- **Error type breakdown**: Which kind of math errors dominate?

### Fed by Tier 1 Metrics

- 2.1 Invalid Action Rate
- 2.2 Worker Sum Accuracy
- 2.3 Over-Capacity Errors
- 2.4 Production Rate Awareness
- 2.5 Trade Math Accuracy
- 2.6 Multi-Resource Feasibility

---

## Dimension 3: Priority Triage Under Competing Constraints

**What it answers:** "When multiple urgent things demand attention simultaneously, does this model identify the most critical one?"

**Why it's novel:** No benchmark creates genuine urgency with trade-offs. When food hits 0 (population dying), buildings are damaged (score bleeding), AND a catastrophe is approaching — the model must decide what to address first. There's an objectively correct priority order, and the model either sees it or doesn't.

### Definition

The model's ability to identify and address the most critical constraint when multiple constraints are violated simultaneously.

### Data Collection

1. Detect **multi-constraint events** — ticks where 2+ of these are true simultaneously:
   - Food ≤ 0 (starvation active)
   - Buildings damaged (health < 50%)
   - Catastrophe warning active (30s countdown)
   - Population at cap (growth blocked)
   - Gold ≤ 0 (can't trade)
   - Morale < 0.7 (production penalty)

2. At each multi-constraint tick, compute **expert priority order**:
   ```
   Priority 1: Starvation (immediate population loss)
   Priority 2: Catastrophe preparation (imminent large damage)
   Priority 3: Building repair (ongoing score bleed)
   Priority 4: Population cap (blocked growth)
   Priority 5: Gold shortage (trading blocked)
   Priority 6: Low morale (production penalty)
   ```

3. Record what the LLM addressed first.

### Scoring

```
triage_score = (correct_priority_1_choices) / (total_multi_constraint_events)

Partial credit:
  Addressed Priority 1 first: 1.0
  Addressed Priority 2 first (when P1 present): 0.5
  Addressed Priority 3+ first (when P1 present): 0.1
```

### Reported Values

- **Triage accuracy** (0.0–1.0): Proportion of correct first-priority actions
- **Average priority rank chosen**: Mean rank of what the model addresses first (1.0 = perfect)
- **Constraint count vs accuracy**: Does accuracy drop as simultaneous constraints increase?
- **Decision latency under pressure**: Ticks between constraint detection and action

### Fed by Tier 1 Metrics

- 3.5 Starvation Response Speed
- 1.4 Catastrophe Preparation
- 3.3 Repair Prioritization
- Resource state monitoring (all)

---

## Dimension 4: Compounding Error Recognition

**What it answers:** "Can this model recognize that a small earlier mistake is snowballing, and correct course before it's too late?"

**Why it's novel:** Most benchmarks are single-shot — right or wrong, no compounding. In real agentic systems, a slightly wrong worker allocation at step 20 might be invisible at step 25 but causes system failure at step 40. The question isn't "does it make mistakes" — it's "does it catch and correct its own mistakes before they cascade?"

### Definition

The model's ability to detect negative resource trajectories (leading toward crisis) and correct them BEFORE the crisis point.

### Data Collection

1. Track per-resource trajectory: compute 10-tick slope for food, materials, knowledge, gold
2. Detect **negative trajectory events**: resource declining toward 0 at current rate within 20 ticks
3. Measure **detection lead time**: ticks between trajectory becoming negative and model taking corrective action
4. Classify correction quality:

| Lead Time | Classification | Score |
|-----------|---------------|-------|
| > 15 ticks before crisis | Early detection | 1.0 |
| 10-15 ticks | Adequate detection | 0.7 |
| 5-10 ticks | Late detection | 0.4 |
| 1-5 ticks | Crisis response only | 0.2 |
| 0 (only acts at crisis) | No detection | 0.0 |

### Scoring

```
error_recognition_score = mean(detection_lead_time_scores)
```

### Reported Values

- **Average detection lead time** (ticks): How early does the model catch problems?
- **Crisis avoidance rate**: % of detected negative trajectories corrected before hitting 0
- **False positive rate**: Corrections made when no real threat existed (over-cautious)
- **Trajectory types caught**: Which resource declines does the model notice? Which does it miss?

### Fed by Tier 1 Metrics

- Production rate tracking (calculated per tick)
- Resource state snapshots
- Action log (to detect corrective actions)
- 3.5 Starvation Response Speed (specific case of food trajectory)

---

## Dimension 5: Justified Pivot vs Inconsistency

**What it answers:** "Does this model know the difference between 'I should change strategy because circumstances changed' and 'I'm just being incoherent'?"

**Why it's novel:** Existing benchmarks can't distinguish good flexibility from bad inconsistency. A model that changes plan every turn is not "flexible" — it's unreliable. A model that never changes is not "consistent" — it's rigid. The sweet spot is changing only when the environment justifies it.

### Definition

The ratio of strategy changes that are triggered by environmental events to total strategy changes.

### Data Collection

1. Detect **strategy changes**: turns where the model's top-2 reasoning factors change, OR where action type shifts dramatically (action distribution divergence > 0.4 over 5 ticks)
2. For each strategy change, check for **environmental triggers** within the prior 5 ticks:
   - Catastrophe event
   - Market price shock (>30% change)
   - Resource hitting 0
   - Building destroyed
   - Population drop > 3
3. Classify each change:

| Classification | Criteria | Signal |
|---|---|---|
| **Justified pivot** | Strategy change WITH trigger | Good flexibility |
| **Unjustified change** | Strategy change WITHOUT trigger | Bad inconsistency |
| **Missed pivot** | Trigger present, NO strategy change when one was needed | Bad rigidity |

### Scoring

```
pivot_score = (justified_pivots) / (justified_pivots + unjustified_changes)

Penalty for missed pivots:
  final_score = pivot_score × (1.0 - 0.1 × missed_pivots)
```

### Reported Values

- **Signal-to-noise ratio** (0.0–1.0): Proportion of strategy changes that are justified
- **Pivot count**: Total strategy changes per game
- **Trigger response rate**: % of environmental triggers that produced a strategy change
- **Stability periods**: Average consecutive ticks without unjustified changes

### Fed by Tier 1 Metrics

- 3.7 Action Distribution Shift (detects changes)
- Reasoning factors (detects intent changes)
- Catastrophe events, market shocks (triggers)
- 3.2 Worker Reallocation After Damage (specific pivot case)

---

## Dimension 6: Graceful Degradation Curve

**What it answers:** "When this model starts failing, does it fail gracefully (performance dips 10-20%) or catastrophically (sudden collapse from 80% to 0%)?"

**Why it's novel:** Every benchmark reports a single score. But for production systems, the shape of failure matters enormously. A model that degrades smoothly gives warning and time to intervene. A model that cliff-fails gives zero warning.

### Definition

The shape of the model's per-turn performance curve over the full game, classified into failure modes.

### Data Collection

1. Compute **per-turn quality score**: composite of action validity, timing optimality, and resource efficiency
   ```
   turn_quality = (valid_action × 0.4) + (optimal_action × 0.3) + (resource_efficiency × 0.3)
   ```
2. Plot quality across all turns (100 data points per game)
3. Fit regression models:
   - Linear fit (R²)
   - Piecewise linear (detect breakpoints)
   - Constant fit (check for flat line)

### Classification

| Failure Mode | Criteria | Implication |
|---|---|---|
| **Stable** | Linear slope within ±0.002/turn, R² < 0.1 | Safe to deploy |
| **Linear decay** | Negative slope > 0.003/turn, R² > 0.5 | Predictable, manageable with monitoring |
| **Cliff failure** | Piecewise fit shows breakpoint with >0.3 drop | Dangerous — no warning before collapse |
| **Oscillating** | Std dev of 10-turn windows > 0.15 | Unpredictable quality, hard to rely on |
| **Improving** | Positive slope > 0.002/turn | Model gets better with more game context |

### Scoring

```
degradation_score based on classification:
  Stable: 1.0
  Improving: 1.0
  Linear decay: 0.7 - (slope × 50)  [mild decay scores higher]
  Oscillating: 0.4
  Cliff failure: 0.2
```

### Reported Values

- **Failure mode classification**: One of the 5 types above
- **Cliff point** (if applicable): Turn number where collapse occurs
- **Effective decision budget**: Number of turns before quality drops below 0.7
- **Quality variance**: Standard deviation across all turns
- **Per-quartile quality**: Q1, Q2, Q3, Q4 averages

### Fed by Tier 1 Metrics

- All Tier 1 metrics contribute to per-turn quality score
- Token count per turn (correlates with context growth)
- Turn number (x-axis of degradation curve)

### Context Window Correlation (Sub-Dimension)

**What it adds:** The base Graceful Degradation analysis uses *turn number* as the x-axis. This sub-dimension uses *cumulative token count* — because a model might degrade at turn 60 not due to "cognitive fatigue" but because its effective context window is full at that point. Separating turn-based from token-based degradation reveals whether the model is limited by sequential reasoning depth or by context capacity.

**Data Collection:**

Uses Tier 1 §6 (Context Pressure Metrics).

1. **Dual-axis analysis**: Plot quality against both:
   - Turn number (sequential reasoning limit)
   - Cumulative tokens (context capacity limit)

2. **Correlation test**: Compute Pearson correlation between quality degradation and each axis:
   ```
   r_turns = correlation(quality, turn_number)
   r_tokens = correlation(quality, cumulative_tokens)
   ```
   If `|r_tokens| > |r_turns| + 0.15`: degradation is context-bound (model ran out of window)
   If `|r_turns| > |r_tokens| + 0.15`: degradation is reasoning-bound (model loses coherence regardless of context size)
   Otherwise: mixed or no degradation

3. **Context efficiency**: How much useful information does the model extract per token of context?
   ```
   context_efficiency = historical_reference_rate × (1.0 / normalized_token_count)
   ```
   Models that use early information despite large context are efficient. Models that ignore early context despite having it are wasteful.

4. **Operational context window**: From Tier 1 metric 6.3 (Context Collapse Point), report the practical token limit.

**Scoring Integration:**

```
context_adjusted_degradation = degradation_score × context_modifier

Where context_modifier:
  No collapse detected: 1.0 (no penalty)
  Collapse at >60K tokens: 0.9 (mild penalty — most games won't hit this)
  Collapse at 30K-60K tokens: 0.7 (moderate — long games affected)
  Collapse at <30K tokens: 0.5 (severe — model can't handle full game)
```

This modifier adjusts the Graceful Degradation score to account for context-specific failure.

**Additional Reported Values (alongside existing Dim 6 outputs):**

- **Degradation driver**: "context-bound", "reasoning-bound", or "mixed"
- **Operational context window** (tokens): Practical limit before quality drops 20%
- **Context efficiency score** (0-1): How well the model uses its available context
- **Q4/Q1 quality ratio**: Direct comparison of late-game vs early-game performance
- **Historical reference rate**: % of late decisions that use early-game information
- **Token-at-cliff** vs **turn-at-cliff**: Helps distinguish whether the cliff is from context saturation or cognitive limits

**Production Implication:**

This directly predicts **context management strategy** for agentic deployment:
- Context-bound models → need trajectory compression, sliding windows, or RAG
- Reasoning-bound models → need re-planning checkpoints regardless of context size
- Mixed models → need both strategies

---

## Dimension 7: Opportunity Cost Awareness

**What it answers:** "Does this model understand that every action has a cost beyond its resource price — the cost of NOT doing something else?"

**Why it's novel:** A model that builds a Warehouse when it should be building a Hospital (catastrophe imminent) made a valid action — just the wrong one given what it's forgoing. Most benchmarks only test valid/invalid. Terminus tests optimal/suboptimal among valid options.

### Definition

The gap between the model's chosen action value and the theoretically optimal action value at each decision point.

### Data Collection

1. At each decision point (every tick where the LLM acts), compute all valid actions
2. For each valid action, estimate **expected value** over next 20 ticks:
   ```
   action_value = projected_score_at_tick+20 - current_score
   ```
   Using a deterministic simulator (same engine, greedy heuristic for future ticks)
3. Record:
   - Value of optimal action (max expected value)
   - Value of chosen action
   - Gap = optimal - chosen

### Scoring

```
opportunity_cost = mean(gaps_across_all_decisions)
opportunity_score = 1.0 - min(1.0, opportunity_cost / max_possible_gap)
```

Where `max_possible_gap` is calibrated from the Random agent's average gap (worst-case baseline).

### Reported Values

- **Average opportunity cost** (points/decision): How suboptimal is the model on average?
- **Optimal action rate**: % of decisions where the model chose THE best action
- **Near-optimal rate**: % of decisions within top-3 actions
- **Worst decisions**: Top 5 highest-gap decisions (for qualitative analysis)
- **Opportunity cost by game phase**: Early vs mid vs late game

### Fed by Tier 1 Metrics

- 1.1 Build Order Efficiency (opportunity cost of wrong build sequence)
- 1.3 Market Timing (opportunity cost of bad trades)
- 3.3 Repair Prioritization (opportunity cost of wrong repair order)
- Full action space evaluation (computed by benchmark engine)

---

## Dimension 8: Game-Theoretic Sophistication

**What it answers:** "Does this model reason about other agents' strategies, or does it play in a vacuum — ignoring that its environment contains adversaries with their own objectives?"

**Why it's novel:** Every existing LLM benchmark is single-agent. MMLU, HumanEval, GSM8K — the model solves problems in isolation. But production AI increasingly operates in multi-agent environments: competing bidders in auctions, negotiating agents, marketplace pricing bots, adversarial red-team/blue-team setups. Terminus is inherently multiplayer — the opponent's strategy directly affects optimal play, market prices, and resource availability.

### Definition

The model's ability to detect opponent strategy, adapt its own play accordingly, resist exploitation by adversarial opponents, and capture cooperative surplus when mutual benefit is available.

### Data Collection

Run the LLM against each of 6 opponent archetypes (Random, Greedy, Balanced, Rush, Turtle, Adversarial) for N games each. Collect:

1. **Win/loss/score differential** per opponent type
2. **Strategy adaptation timeline** — turn at which the LLM's action distribution shifts to specifically counter the opponent
3. **Exploitation vulnerability** — how much score the adversarial agent extracts vs the balanced agent
4. **Cooperative behavior** — in positive-sum scenarios, whether the LLM pursues mutual gain
5. **Market interaction quality** — whether the LLM's trading accounts for opponent's likely trades

### Sub-Scores

#### 8a. Opponent Modeling Accuracy

Does the LLM correctly identify what strategy the opponent is running?

```
modeling_score = counter_strategy_detection_speed (from Tier 1 §5.3)
```

A model that takes 10 turns to detect "this opponent always rushes" and shifts to defense scores 1.0. A model that never adapts to opponent type scores 0.0.

#### 8b. Exploitation Resistance

Can a smart adversary consistently beat this LLM by exploiting predictable patterns?

```
resistance_score = exploitation_resistance (from Tier 1 §5.2)
```

Score of 1.0 means the adversarial agent gains no advantage over the balanced agent. Score of 0.0 means the adversarial agent wins significantly more by targeting weaknesses.

#### 8c. Strategic Diversity

Does the LLM vary its strategy across games, or does it play the same opening regardless of opponent?

**Data Collection:** Compute action distribution for first 15 turns across all games. Measure variance.

```
diversity_score = mean_pairwise_jensen_shannon_divergence(all_game_openings)
```

Higher diversity = harder to predict/exploit. Normalized to [0, 1].

#### 8d. Cooperative Rationality

In positive-sum scenarios, does the LLM find cooperative equilibria?

```
cooperation_score = cooperative_surplus_capture (from Tier 1 §5.4)
```

#### 8e. Market Adversarial Awareness

Does the LLM account for opponent market behavior? (from Tier 1 §5.5)

```
market_awareness_score = manipulation_detection_score
```

### Composite Game Theory Score

```
game_theory_score = (
    opponent_modeling × 0.25 +
    exploitation_resistance × 0.25 +
    strategic_diversity × 0.15 +
    cooperative_rationality × 0.15 +
    market_adversarial_awareness × 0.20
)
```

### Reported Values

- **Overall game theory score** (0.0–1.0)
- **Win rate matrix**: Win rate vs each opponent type (6 values)
- **Adaptation speed**: Average turns to detect and counter opponent strategy
- **Exploitation gap**: Score differential (adversarial vs balanced opponent)
- **Strategy fingerprint**: The LLM's own archetype (aggressive, defensive, adaptive, cooperative)
- **Nash distance** (advanced): How close the LLM's mixed strategy is to the Nash equilibrium of the game (requires game-theoretic solver, computed offline)
- **Per-opponent-type breakdown**: Full sub-score table per archetype

### Classification

| Profile | Criteria | Implication |
|---------|----------|-------------|
| **Predator** | High exploitation of weak opponents, high diversity | Dominant in competitive environments, may over-exploit |
| **Fortress** | High resistance, low cooperation, consistent strategy | Safe against adversaries, misses cooperative gains |
| **Diplomat** | High cooperation, moderate resistance, adaptive | Excels in multi-agent coordination, vulnerable to pure defectors |
| **Chameleon** | Fast adaptation, high diversity, moderate everything | Versatile, hard to predict, but may lack deep strategy |
| **Oblivious** | Low modeling, low resistance, random-level diversity | Ignores opponents entirely — plays as if in single-agent mode |

### Fed by Tier 1 Metrics

- 5.1 Win Rate vs Opponent Archetypes
- 5.2 Exploitation Resistance
- 5.3 Counter-Strategy Detection Speed
- 5.4 Cooperative Surplus Capture
- 5.5 Market Manipulation Detection
- 1.3 Market Timing (extended to account for opponent trades)
- 3.4 Market Adaptation (opponent-triggered price changes)

### Benchmark Runtime Implications

Game-Theoretic scoring requires running the LLM against multiple opponent types:

| Configuration | Games Required | Runtime |
|---|---|---|
| **Quick** (Random + Greedy + Balanced) | 3 × N games | ~3× base runtime |
| **Standard** (all 6 archetypes) | 6 × N games | ~6× base runtime |
| **Deep** (6 archetypes + repeated adversarial adaptation) | 8 × N games | ~8× base runtime |

The host selects configuration depth. "Quick" is default for MVP. "Standard" recommended for serious evaluation.

---

# TIER 3: Mapping to Agentic Workflows

These are the production-relevant predictions an AI engineer extracts from the benchmark.

---

## Mapping Table

| Terminus Dimension | Production Prediction | How to Read the Score |
|---|---|---|
| **Multi-Decision Coherence** (+ State Fidelity) | **Agent step budget + RAG retrieval fidelity** — How many sequential steps can you chain before the model contradicts itself or loses track of its own state? Does it know what's in its context? | Inflection point = max reliable chain length. State fidelity quadrant reveals whether failures are execution (can't decide) or comprehension (lost the plot). Amnesia point = when to force context refresh |
| **Applied Arithmetic Under Load** | **Tool-call parameter reliability** — When the model fills in API parameters (counts, IDs, offsets, sizes), will the values be correct as context grows? | High-load accuracy predicts tool-call error rate in late-stage agent runs. 0.95 at high load = ~5% malformed tool calls expected |
| **Priority Triage** | **Incident response automation** — When your AI-powered runbook encounters multiple simultaneous alerts, will it address the P0 before the P2? | Triage accuracy directly predicts whether an automated incident responder will page on the right thing first |
| **Compounding Error Recognition** | **Self-healing agent effectiveness** — Will the agent notice its own earlier mistakes compounding, or will it only react after a full failure? | Detection lead time predicts MTTR for self-correcting systems. >15 ticks ≈ proactive healing. <5 ticks ≈ reactive crash recovery |
| **Justified Pivot vs Inconsistency** | **Code review stability** — Will the model produce a stable implementation, or will it keep rewriting its own code without justification? | SNR > 0.8 = stable agent that changes plans only when needed. SNR < 0.4 = agent that churns, producing inconsistent PRs |
| **Graceful Degradation** (+ Context Window) | **SLA predictability + long-session reliability** — When your AI service degrades, is it gradual or sudden? Is it because context is full or because reasoning decayed? | Cliff failure = deploy with aggressive circuit breakers. Context-bound = implement trajectory compression. Reasoning-bound = insert re-planning checkpoints. Operational window = max tokens before quality drop |
| **Opportunity Cost Awareness** | **Solution quality ceiling** — Will the agent produce the *best* solution or merely an *acceptable* one? Does it understand trade-offs? | Optimal rate > 60% = model finds best approach most of the time. Optimal rate < 30% = model produces working but mediocre solutions |
| **Game-Theoretic Sophistication** | **Multi-agent negotiation, competitive bidding, adversarial robustness** — In systems with multiple AI agents or human adversaries, will your model account for others' strategies or play in a vacuum? | High resistance + fast adaptation = safe for auction systems, marketplace agents, adversarial environments. Oblivious profile = dangerous in competitive deployments, fine for solo tasks |

---

## Use Case Mapping

### For HiveShip-style Agentic Pipelines

| HiveShip Component | Most Critical Terminus Dimension | Why |
|---|---|---|
| **Planner** (goal decomposition into DAG) | Opportunity Cost Awareness | Planner must choose the decomposition with lowest total cost, not just any valid one |
| **Agent execution** (code generation per task) | Applied Arithmetic Under Load | Agents must correctly compute file paths, line numbers, import paths under growing context |
| **Self-review loop** (reviewer + fixer cycle) | Compounding Error Recognition | Reviewer must catch subtle issues before they compound across files |
| **Helper spawning** (unblocking stuck agents) | Priority Triage | System must identify which blocked agent to unblock first when multiple are stuck |
| **Trajectory compression** (context management) | Graceful Degradation + Context Window | Must predict when model will cliff-fail to trigger compression proactively; operational window determines compression interval |
| **Webhook revision** (PR comment → fix → push) | Justified Pivot | Must change code only where the review comment applies, not refactor unrelated code |
| **Memory extraction** (post-PR learning) | Multi-Decision Coherence + State Fidelity | Must maintain consistent understanding of what was learned across the full run; state fidelity ensures accurate recall |
| **Multi-agent coordination** (parallel worker agents) | Game-Theoretic Sophistication | Workers must account for what other agents are doing — avoid conflicts, share context, coordinate merges |
| **Auction/bidding** (task allocation among agents) | Game-Theoretic Sophistication | Task assignment must account for agent capabilities and competing demands |

---

### For Other Agentic Systems

| System Type | Top 3 Dimensions to Prioritize | Weight Preset |
|---|---|---|
| **CI/CD automation** (generate, test, deploy) | Arithmetic, Degradation, Coherence | Reliability Focus |
| **Customer support agents** (multi-turn conversations) | Coherence, Triage, Pivot | Strategy Focus |
| **Code review bots** | Opportunity Cost, Pivot, Arithmetic | Competitive Focus |
| **Incident response automation** | Triage, Error Recognition, Degradation | Triage Focus |
| **Research assistants** (long-running analysis) | Coherence, Degradation, Arithmetic | Endurance Focus |
| **Trading/financial agents** | Arithmetic, Game Theory, Opportunity Cost | Precision Focus |
| **Marketplace bidding agents** | Game Theory, Arithmetic, Triage | Adversarial Focus |
| **Multi-agent orchestration** | Game Theory, Coherence, Pivot | Coordination Focus |
| **RAG-powered Q&A** (long context retrieval) | Coherence (State Fidelity), Degradation (Context Window), Arithmetic | Context Focus |

---

## Preset Weight Distributions

| Preset | Coherence | Arithmetic | Triage | Error Recog | Pivot | Degradation | Opportunity | Game Theory |
|--------|-----------|-----------|--------|-------------|-------|-------------|-------------|-------------|
| **Balanced** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| **Reliability Focus** | 1.5 | 2.0 | 1.0 | 1.5 | 0.5 | 2.0 | 0.5 | 0.5 |
| **Strategy Focus** | 1.0 | 0.5 | 1.5 | 1.0 | 2.0 | 0.5 | 2.0 | 1.5 |
| **Triage Focus** | 0.5 | 1.0 | 3.0 | 2.0 | 1.0 | 1.0 | 0.5 | 0.5 |
| **Endurance Focus** | 2.5 | 1.5 | 0.5 | 1.0 | 1.0 | 2.5 | 0.5 | 0.5 |
| **Precision Focus** | 0.5 | 3.0 | 1.0 | 1.0 | 0.5 | 1.0 | 2.0 | 1.0 |
| **Adversarial Focus** | 1.0 | 1.5 | 1.0 | 0.5 | 1.5 | 1.0 | 1.0 | 3.0 |
| **Coordination Focus** | 1.5 | 1.0 | 1.0 | 1.0 | 1.5 | 1.0 | 1.0 | 2.5 |
| **Context Focus** | 2.0 | 1.5 | 0.5 | 1.0 | 0.5 | 2.5 | 0.5 | 0.5 |

**Composite Score:**
```
final_score = Σ(dimension_score × weight) / Σ(weights)
```

---

## Trend Analysis Across Games

When running N games, classify the model's performance trend:

| Classification | Criteria | Production Implication |
|---|---|---|
| **Improving** | Positive slope, p < 0.05 | Model benefits from repeated exposure — fine-tuning potential |
| **Consistent** | Slope ≈ 0, std dev < 0.05 | Predictable performance — safe for SLA commitments |
| **Degrading** | Negative slope, p < 0.05 | Model may be memorizing failure patterns — investigate prompt structure |
| **Volatile** | Std dev > 0.12 regardless of slope | Unreliable — not suitable for deterministic pipelines |

---

## Statistical Validity

### Minimum Sample Sizes

- **Per matchup**: 10 games for trend detection, 30 for statistical significance (p < 0.05)
- **Per metric checkpoint**: Minimum 5 measurement points per game per dimension
- **Confidence intervals**: Report 95% CI on all dimension scores

### Variance Control

- Fixed random seeds for map generation, catastrophe timing, market fluctuations
- Symmetric matchups (A vs B AND B vs A with swapped starting positions)
- Baseline normalization: Random agent = 0.0, theoretically perfect play = 1.0

### Significance Testing

- Mann-Whitney U test for comparing two models (non-parametric, handles non-normal distributions)
- Kruskal-Wallis for comparing 3+ models
- Bonferroni correction for multiple comparisons
- Effect size (Cohen's d) reported alongside p-values
- All results reported with 95% confidence intervals

---

## Cross-Dimension Correlations & LLM Archetypes

Track correlations between dimensions to identify model archetypes:

| Archetype | High Dimensions | Low Dimensions | Best For |
|-----------|----------------|----------------|----------|
| **The Strategist** | Opportunity Cost, Pivot, Game Theory | Arithmetic, Degradation | Planning systems, architecture decisions, multi-agent coordination |
| **The Accountant** | Arithmetic, Coherence, Degradation | Pivot, Game Theory | Data pipelines, financial calculations, deterministic workflows |
| **The Firefighter** | Triage, Error Recog, Pivot | Coherence, Opportunity Cost | Incident response, monitoring, on-call automation |
| **The Marathon Runner** | Coherence, Degradation, Arithmetic | Triage, Pivot | Long-running research, documentation, multi-hour sessions |
| **The Diplomat** | Game Theory, Pivot, Coherence | Arithmetic, Triage | Multi-agent negotiation, marketplace agents, cooperative systems |
| **The Fortress** | Game Theory (resistance), Degradation, Arithmetic | Pivot, Cooperation | Adversarial environments, security applications |
| **The All-Rounder** | Balanced (all 0.6-0.8) | None extreme | General-purpose agentic deployment |
| **The Specialist** | One dimension > 0.9 | Others < 0.5 | Targeted use matching the strong dimension |
