# LLM Benchmark Metrics — Detailed Specification

This document defines exactly how each of the 6 evaluation dimensions is measured, what data is collected, and how scores are calculated.

---

## Metric 1: Planning Horizon

### Data Collection

For every decision point, record:
- Available actions and their immediate reward (resource gain this turn)
- Available actions and their projected N-turn reward (estimated payoff over next 5/10/20 turns)
- Which action the LLM chose
- The actual outcome N turns later

### Decision Point Classification

Each decision is classified as:
- **Greedy-optimal**: The action with highest immediate payoff is also strategically best
- **Delayed-payoff available**: A suboptimal immediate action has higher long-term value
- **Sacrifice required**: Long-term optimal action has negative immediate payoff

Only "delayed-payoff available" and "sacrifice required" decisions count toward this metric.

### Score Calculation

```
planning_score = (correct_delayed_choices / total_delayed_opportunities) × 0.7
                + (actual_realized_value / theoretical_optimal_value) × 0.3
```

The 70/30 split weights choice-making higher than outcome (since outcomes have variance).

### Example Scenarios

| Turn | State | Greedy Action | Strategic Action | Optimal Choice |
|------|-------|---------------|------------------|----------------|
| 5 | 50 ore, need income | Build Mine (+3 ore/turn) | Build Power Plant (enables 2 mines next turn) | Power Plant |
| 12 | Market ore=8, has 100 ore | Sell now for 800 credits | Hold, price trending to 15 | Hold |
| 30 | Under attack, 3 workers | Repair buildings (immediate) | Build shield (prevents future damage) | Context-dependent |

---

## Metric 2: Numerical Grounding

### Data Collection

For every action the LLM takes, record:
- Whether the action is valid given current resources (binary: valid/invalid)
- If the LLM stated expected outcomes in its reasoning, compare to actual
- Track "near misses" — actions that are valid but leave the LLM with 0 of a critical resource

### Validation Categories

1. **Hard failures**: Action attempted with insufficient resources (e.g., build costs 50 ore, LLM has 30)
2. **Soft failures**: Action is valid but reasoning shows incorrect math (e.g., "I have 80 ore" when actual is 60, but action only costs 30 so it still works)
3. **Prediction errors**: LLM predicts future state incorrectly (e.g., "after 3 turns I'll have 100 energy" but actual projection is 75)

### Score Calculation

```
numerical_score = 1.0 - (hard_failures × 0.5 + soft_failures × 0.3 + prediction_errors × 0.2) / total_decisions
```

Clamped to [0.0, 1.0].

### Stress Tests

Specific scenarios designed to test numerical grounding:
- Multi-resource builds (requires exact amounts of 3+ resources simultaneously)
- Market arbitrage (must compute buy price × quantity vs. sell price × quantity)
- Worker efficiency calculations (must understand diminishing returns)
- Production chain math (ore → alloy conversion ratios)

---

## Metric 3: State Tracking Fidelity

### Data Collection

At turns 10, 25, 50, 75, and 100, inject a "state query" alongside the normal game state:

```json
{
  "state_query": {
    "questions": [
      "What is your current strategy?",
      "List your buildings and their levels.",
      "What was your last major decision and why?",
      "What do you expect to build next?"
    ]
  }
}
```

Compare responses to actual game records.

### Accuracy Categories

1. **Building inventory accuracy**: Does the LLM correctly list its buildings?
2. **Resource awareness**: Are stated resource levels within ±15% of actual?
3. **Strategy consistency**: Does the current stated strategy logically follow from previous statements + events?
4. **History recall**: Can the LLM reference specific past events correctly?

### Score Calculation

```
state_score = (building_accuracy × 0.3) + (resource_accuracy × 0.25) 
            + (strategy_consistency × 0.25) + (history_recall × 0.2)
```

Each sub-score is 0.0–1.0.

### Degradation Curve

Plot state_score at each checkpoint. Calculate:
- **Degradation rate**: Linear regression slope across checkpoints
- **Cliff detection**: Any checkpoint where score drops > 0.3 from previous

---

## Metric 4: Strategic Flexibility

### Data Collection

Track all "disruption events":
- Catastrophes (type, severity, timing)
- Market crashes (resource price drops > 30% in one tick)
- Opponent aggression (opponent builds military, trades aggressively)
- Resource depletion (a key resource hits 0)

For each disruption, record:
- LLM's growth rate (score/turn) for 5 turns before
- LLM's growth rate for 5 turns after
- Time to return to pre-disruption growth rate
- Whether the LLM changed its action pattern after the disruption

### Response Classification

| Response Type | Description | Score Impact |
|---------------|-------------|--------------|
| Optimal pivot | Changes strategy appropriately, fast recovery | +1.0 |
| Adequate adaptation | Adjusts somewhat, moderate recovery | +0.6 |
| Delayed response | Takes 3+ turns to react | +0.3 |
| No response | Continues as if nothing happened | +0.0 |
| Over-reaction | Panics, abandons viable strategy | +0.2 |

### Score Calculation

```
flexibility_score = mean(response_scores) × recovery_bonus

recovery_bonus = 1.0 + (0.1 × number_of_successful_recoveries) - capped at 1.5
```

### Engineered Disruptions

In benchmark mode, disruptions can be scripted at specific turns for reproducibility:
- Turn 15: Minor catastrophe (10% damage)
- Turn 30: Market crash (ore price halved)
- Turn 45: Major catastrophe (30% damage)
- Turn 60: Opponent switches to aggressive strategy
- Turn 80: Resource scarcity (mine output halved)

---

## Metric 5: Game-Theoretic Sophistication

### Data Collection

Track opponent-aware decision-making:
- Did the LLM's market trades account for opponent's likely trades?
- Did the LLM adjust building priorities based on opponent's specialization?
- Did the LLM time actions to preempt or respond to opponent moves?
- In cooperative scenarios, did the LLM identify and pursue mutual benefit?

### Testing Methodology

Run each LLM against standardized opponent strategies:

1. **Random agent**: Baseline (any decent model should beat this easily)
2. **Greedy heuristic**: Always takes highest immediate-value action
3. **Rush strategy**: Aggressive early military/expansion
4. **Turtle strategy**: Defensive, slow growth, strong late-game
5. **Mirror strategy**: Copies the LLM's last action (tests for exploitation)
6. **Adversarial**: Specifically targets the LLM's weaknesses

### Score Calculation

```
game_theory_score = (win_rate_vs_strategies × 0.4)
                  + (exploitation_resistance × 0.3)
                  + (cooperation_capture × 0.2)
                  + (adaptation_rate × 0.1)
```

Where:
- `win_rate_vs_strategies`: Normalized win rate across all opponent types
- `exploitation_resistance`: 1.0 - (adversarial win rate against LLM)
- `cooperation_capture`: In positive-sum games, % of available cooperative surplus captured
- `adaptation_rate`: Performance improvement against same opponent over repeated games

---

## Metric 6: Context Window Utilization

### Data Collection

Divide the game into quartiles by turn count:
- Q1: Turns 1–25 (small context)
- Q2: Turns 26–50 (medium context)
- Q3: Turns 51–75 (large context)
- Q4: Turns 76–100 (very large context)

For each quartile, measure:
- Decision quality (using a composite of other metrics)
- Response coherence (does the response make logical sense?)
- Historical reference rate (how often does reasoning cite past events?)
- Error rate (invalid actions, contradictions)

### Context Pressure Test

Deliberately include verbose game state descriptions to inflate context size:
- Full market history (all price changes)
- Complete building log (every construction event)
- Full chat/interaction history with opponents
- Detailed event log (every catastrophe, trade, etc.)

This tests whether the LLM can extract relevant information from a large context window under load.

### Score Calculation

```
context_score = 1.0 - max(0, quality_degradation_rate)

quality_degradation_rate = (Q1_quality - Q4_quality) / Q1_quality
```

If Q4 quality > Q1 quality (model improves with more context), score = 1.0.

### Cliff Detection

Report the specific context size (in tokens, estimated) where quality first drops > 20%. This gives a practical "effective context window" measurement that's more meaningful than the model's theoretical maximum.

---

## Cross-Metric Correlations

Track correlations between metrics to identify LLM archetypes:

| Archetype | High Metrics | Low Metrics | Description |
|-----------|-------------|-------------|-------------|
| Strategist | Planning, Game Theory | Numerical, Context | Great plans, sloppy execution |
| Accountant | Numerical, State Tracking | Flexibility, Game Theory | Precise but rigid |
| Adaptor | Flexibility, Context | Planning, Numerical | Reactive but undirected |
| All-Rounder | Balanced | None extreme | Competent generalist |
| Savant | One metric near 1.0 | Others low | Specialist model |

---

## Statistical Validity

### Minimum Sample Sizes

- **Per matchup**: Minimum 10 games for trend detection, 30 for statistical significance
- **Per metric checkpoint**: Minimum 5 measurement points per game
- **Confidence intervals**: Report 95% CI on all metric scores

### Variance Control

- Fixed random seeds for map generation, catastrophe timing, market fluctuations
- Symmetric matchups (if A vs B, also run B vs A with swapped positions)
- Baseline normalization (all scores relative to random agent = 0.0, perfect play = 1.0)

### Significance Testing

- Mann-Whitney U test for comparing two models
- Kruskal-Wallis for comparing 3+ models
- Bonferroni correction for multiple comparisons
- Effect size (Cohen's d) reported alongside p-values
