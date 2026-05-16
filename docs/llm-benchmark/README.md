# Terminus LLM Benchmarking Mode

## Overview

Terminus can serve as a multi-dimensional benchmark for evaluating Large Language Models (LLMs) by having them play the game as autonomous agents. The benchmarking mode allows a host to configure test parameters, run multiple games, and analyze LLM performance across several cognitive dimensions.

Unlike traditional LLM benchmarks that test single-turn reasoning or static knowledge, Terminus evaluates **dynamic strategic decision-making** over extended interactions in a multi-agent competitive environment.

---

## Core Features

### 1. Test Configuration

The host configures a benchmark run with the following parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| Number of games | How many consecutive games to run per matchup | 10 |
| Game speed multiplier | Speeds up all timers (build times, catastrophes, market ticks) | 1× |
| Players per game | Number of LLM agents in each game | 2-6 |
| LLM models | Which models to test (API endpoints + model identifiers) | — |
| Metrics selection | Which of the 6 evaluation dimensions to score | All |
| Metric weights | Relative importance of each selected metric | Equal |
| Seed mode | Fixed seeds for reproducibility or random for variance testing | Fixed |
| Max turns per game | Hard cap on game length | 100 |

### 2. Game Speed Multiplier

The speed multiplier affects all time-based mechanics proportionally:

| Speed | Build Time | Catastrophe Interval | Market Tick | Turn Duration |
|-------|-----------|---------------------|-------------|---------------|
| 1× | Normal | Normal | Normal | Normal |
| 2× | ÷2 | ÷2 | ÷2 | ÷2 |
| 5× | ÷5 | ÷5 | ÷5 | ÷5 |
| 10× | ÷10 | ÷10 | ÷10 | ÷10 |

Higher speeds test LLMs under time pressure and with less "thinking time" budget per decision.

### 3. Results Dashboard

After all games complete, Terminus displays a scrollable vertical chart view:

- **Score progression chart**: Line chart per LLM showing total colony score across all games (X = game number, Y = final score)
- **Trend analysis**: Whether the LLM improved, stayed consistent, or degraded over repeated games
- **Per-metric radar charts**: Spider/radar chart per LLM showing strength across the 6 dimensions
- **Head-to-head comparison**: Side-by-side bar charts when 2+ LLMs are tested
- **Consistency score**: Standard deviation of performance across games (lower = more consistent)

### 4. Data Export

All benchmark data can be exported in:

- **JSON** — Full structured data with every game state, action, and metric
- **CSV** — Tabular summary for spreadsheet analysis
- **Markdown** — Human-readable report with embedded ASCII charts

---

## Evaluation Dimensions

### Dimension 1: Planning Horizon

**What it measures:** Can the LLM sacrifice short-term gain for long-term advantage?

**How it's scored:**
- Track decisions where an immediately profitable action was available but a strategically superior delayed-payoff action existed
- Score = (delayed-payoff actions chosen) / (total decision points with delayed-payoff options)
- Bonus: Measure the actual payoff delta — did the delayed choice actually result in better outcomes N turns later?

**Indicators:**
- Building order efficiency (infrastructure before production)
- Resource stockpiling before large construction projects
- Timing of specialization-synergistic builds
- Market position building (buying low to sell high later, not just immediate arbitrage)

**Scoring range:** 0.0 (purely greedy) to 1.0 (optimal long-term planning)

---

### Dimension 2: Numerical Grounding

**What it measures:** Does the LLM actually compute resource math correctly or hallucinate plausible numbers?

**How it's scored:**
- Present the LLM with its current resource state and ask it to choose actions
- Track whether chosen actions are actually affordable (resources sufficient)
- Track whether the LLM's stated reasoning about costs matches actual game math
- Penalize actions attempted that fail due to insufficient resources

**Indicators:**
- Invalid action rate (attempted actions that are impossible given current state)
- Resource prediction accuracy (if LLM states "I'll have 50 ore after this" — is it correct?)
- Build order feasibility (does the planned sequence actually work given income rates?)
- Trade math accuracy (does the LLM correctly compute profit/loss on trades?)

**Scoring range:** 0.0 (frequent impossible actions / wrong math) to 1.0 (perfect resource tracking)

---

### Dimension 3: State Tracking Fidelity

**What it measures:** After many turns, does the LLM still accurately remember its colony state and strategy?

**How it's scored:**
- At periodic checkpoints, query the LLM about its current state (resources, buildings, strategy)
- Compare stated state to actual game state
- Measure drift: does accuracy degrade as game progresses?
- Track strategy consistency: does the LLM contradict its earlier stated plan without a valid reason?

**Indicators:**
- State recall accuracy at turn 10, 25, 50, 75, 100
- Strategy drift rate (plan changes without environmental trigger)
- Building inventory accuracy (does LLM know what it has built?)
- Resource level awareness (within ±10% of actual values)

**Scoring range:** 0.0 (severe hallucination of state) to 1.0 (perfect state awareness throughout)

---

### Dimension 4: Strategic Flexibility

**What it measures:** Can the LLM pivot when circumstances change?

**How it's scored:**
- Track performance before and after disruptive events (catastrophes, market crashes, opponent aggression)
- Measure recovery time: how many turns to return to pre-disruption growth rate
- Measure plan adaptation: did the LLM change strategy appropriately, or rigidly continue a now-suboptimal plan?
- Penalize both over-reaction (panicking, abandoning good plans) and under-reaction (ignoring threats)

**Indicators:**
- Post-catastrophe recovery speed (turns to regain positive growth)
- Worker reallocation speed after disruption
- Build order changes in response to market shifts
- Shield/defense investment after first catastrophe (learning)
- Strategy diversity across games (not repeating same fixed opening)

**Scoring range:** 0.0 (rigid, no adaptation) to 1.0 (optimal pivoting with appropriate magnitude)

---

### Dimension 5: Game-Theoretic Sophistication

**What it measures:** Does the LLM reason about other players' strategies and respond optimally?

**How it's scored:**
- Track whether the LLM's actions account for opponent behavior
- Measure counter-strategy effectiveness: when opponent does X, does the LLM adjust?
- Test for exploitability: can a simple counter-strategy consistently beat the LLM?
- Evaluate cooperation detection: does the LLM recognize mutually beneficial situations?

**Indicators:**
- Win rate against diverse opponent strategies (aggressive, defensive, economic, random)
- Exploitation resistance (performance against adversarial strategy specifically targeting its weaknesses)
- Trade behavior adaptation (does it adjust prices based on opponent's trading patterns?)
- Market manipulation detection (does it notice and respond to pump-and-dump?)
- Cooperative surplus capture (in positive-sum scenarios, does it find cooperative equilibria?)

**Scoring range:** 0.0 (completely exploitable, ignores opponents) to 1.0 (near-Nash-equilibrium play with exploitation of weaker opponents)

---

### Dimension 6: Context Window Utilization

**What it measures:** As game history grows, does decision quality degrade?

**How it's scored:**
- Compare decision quality in early turns (small context) vs. late turns (large context)
- Measure whether the LLM references and uses early-game information in late-game decisions
- Track response latency and coherence as context grows
- Detect "context collapse" — the point where the LLM starts ignoring relevant history

**Indicators:**
- Decision quality slope (positive = improving with experience, negative = context overload)
- Historical reference rate (does late-game reasoning cite early-game events?)
- Consistency of resource tracking as state description grows
- Performance cliff detection (sudden quality drop at specific context lengths)
- Repeated mistake rate (does the LLM make the same error twice, suggesting it lost track of history?)

**Scoring range:** 0.0 (severe degradation with context growth) to 1.0 (stable or improving performance regardless of context size)

---

## Composite Scoring

### Weighted Aggregate Score

```
Final Score = Σ (metric_score × weight) / Σ weights
```

The host assigns weights to each of the 6 dimensions based on what they care about. Presets:

| Preset | Planning | Numerical | State | Flexibility | Game Theory | Context |
|--------|----------|-----------|-------|-------------|-------------|---------|
| Balanced | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Strategy Focus | 2.0 | 0.5 | 1.0 | 2.0 | 2.0 | 1.0 |
| Reliability Focus | 0.5 | 2.0 | 2.0 | 1.0 | 0.5 | 2.0 |
| Competitive Focus | 1.5 | 1.0 | 1.0 | 1.5 | 3.0 | 1.0 |

### Trend Analysis

Across N games, the system calculates:

- **Improvement rate**: Linear regression slope of scores over games
- **Consistency**: Standard deviation of scores
- **Peak performance**: Best single-game score
- **Floor performance**: Worst single-game score
- **Classification**:
  - **Improving**: Positive slope with p < 0.05
  - **Consistent**: Slope ≈ 0, low standard deviation
  - **Degrading**: Negative slope with p < 0.05
  - **Volatile**: High standard deviation regardless of slope

---

## LLM Interface

### Action Space

Each turn, the LLM receives a JSON game state and must respond with a valid action:

```json
{
  "game_state": {
    "turn": 42,
    "resources": {"credits": 150, "ore": 30, "food": 45, "energy": 20, "population": 12},
    "buildings": [...],
    "workers": {"total": 12, "assigned": 8, "idle": 4},
    "market_prices": {"ore": 12.5, "food": 8.2, "energy": 15.0},
    "catastrophe_warning": null,
    "opponents": [{"name": "LLM-B", "score": 320, "visible_buildings": [...]}]
  },
  "available_actions": ["build", "trade", "assign_workers", "upgrade", "research", "pass"],
  "history_summary": "..."
}
```

The LLM responds with:

```json
{
  "action": "build",
  "params": {"building_type": "solar_array", "position": 3},
  "reasoning": "Energy is my bottleneck at 20 units. Solar Array produces +5/turn, enabling Mining Drill next turn."
}
```

The `reasoning` field is optional but enables the State Tracking and Planning Horizon metrics to evaluate stated vs. actual logic.

### Prompt Standardization

To ensure fair comparison, all LLMs receive identical:
- System prompt (explaining game rules, available actions, response format)
- Game state representation (same JSON schema)
- History window (same number of past turns included)

The only variable is the model itself.

---

## Architecture (High Level)

```
┌─────────────────────────────────────────────────┐
│              Benchmark Host UI (TUI)             │
│  - Configure test parameters                     │
│  - Monitor live game progress                    │
│  - View results charts                           │
│  - Export data                                   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│            Benchmark Orchestrator                 │
│  - Manages game sequences                        │
│  - Seeds random number generators                │
│  - Applies speed multiplier                      │
│  - Collects metrics per turn                     │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  LLM Agent  │ │  LLM Agent  │ │  LLM Agent  │
│  Adapter A  │ │  Adapter B  │ │  Adapter C  │
│  (GPT-4o)   │ │  (Claude)   │ │  (Gemini)   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       ▼
┌──────────────────────────────────────────────────┐
│            Terminus Game Server                    │
│  (existing FastAPI + WebSocket server)            │
│  - Runs game logic at configured speed            │
│  - Exposes game state via API                     │
│  - Validates actions                              │
└──────────────────────────────────────────────────┘
```

---

## User Flow

1. **Launch**: `terminus --benchmark` or select "LLM Benchmark" from main menu
2. **Configure LLMs**: Add model endpoints (OpenAI-compatible API format), name each
3. **Configure test**: Set game count, speed, metrics, weights
4. **Run**: Games execute sequentially (or in parallel if server supports it)
5. **Monitor**: Live progress bar, current game score, turn counter
6. **Results**: Scrollable vertical view with all charts
7. **Export**: Save results to JSON/CSV/Markdown

---

## Future Considerations

- **Leaderboard**: Public leaderboard of model performance (opt-in submission)
- **Custom scenarios**: Pre-built test scenarios that stress-test specific dimensions (e.g., "catastrophe gauntlet" for Flexibility, "long game" for Context Window)
- **Prompt engineering comparison**: Same model, different prompt strategies — which system prompt yields best gameplay?
- **Fine-tuning signal**: Use benchmark results to generate training data for game-specific fine-tunes
- **Human baseline**: Let humans play the same scenarios for calibration
- **Cost tracking**: Track API tokens consumed per game for cost-efficiency analysis
