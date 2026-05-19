# Terminus LLM Benchmarking Mode

## Overview

Terminus serves as a multi-dimensional benchmark for evaluating Large Language Models (LLMs) by having them play the colony-building game as autonomous agents. The benchmark mode runs models through 100-turn games against standardized opponents, scoring performance across **8 cognitive dimensions** using a **3-tier measurement framework** (31 game metrics → 8 dimensions → agentic workflow predictions).

Unlike traditional LLM benchmarks that test single-turn reasoning or static knowledge, Terminus evaluates **dynamic strategic decision-making** over extended multi-step interactions in a competitive multi-agent environment — directly predicting how models will perform in production agentic systems.

**Key differentiators:**
- Tests 100+ sequential decisions (not single-turn)
- Measures compounding errors and coherence decay over time
- Forces arithmetic under cognitive load (15+ simultaneous state variables)
- Requires adaptation to environmental disruptions (catastrophes, market shocks)
- Multi-agent: opponents' strategies directly affect optimal play
- Produces actionable predictions for agentic deployment (step budgets, context limits, failure modes)

---

## Documentation Map

| Document | Purpose |
|----------|---------|
| **README.md** (this file) | Overview, dimensions, architecture, user flow |
| [metrics.md](metrics.md) | Complete 3-tier metric specification (31 metrics, 8 dimensions, agentic mappings) |
| [prompt-template.md](prompt-template.md) | Exact prompts sent to LLMs, few-shot examples, context strategy |
| [schemas.md](schemas.md) | Pydantic models for all data contracts |
| [engine-integration.md](engine-integration.md) | How the orchestrator interfaces with the game engine |
| [error-handling.md](error-handling.md) | Failure modes, retry policies, disqualification rules |
| [implementation-plan.md](implementation-plan.md) | Technical implementation phases |
| [ui-flow.md](ui-flow.md) | ASCII mockups of TUI screens |

---

## Core Features

### 1. Test Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| Number of games | Games per matchup (model × opponent) | 10 |
| Game speed multiplier | Compresses catastrophe scheduling | 1× |
| Opponent depth | Quick (3 types) / Standard (6) / Deep (8) | Standard |
| LLM models | API endpoints + model identifiers | — |
| Dimensions selection | Which of the 8 cognitive dimensions to score | All |
| Weight preset | Relative importance of dimensions | Balanced |
| Seed mode | Fixed seeds for reproducibility or random for variance | Fixed |
| Max turns per game | Hard cap on game length | 100 |
| Context strategy | Full conversation or sliding window | Auto (by model context size) |
| Temperature | Generation temperature for all models | 0.3 |

### 2. Game Speed Multiplier

The speed multiplier compresses catastrophe scheduling within the same number of ticks. It does NOT reduce tick count — it makes catastrophes arrive sooner so the same 100 turns see more disruption events.

| Speed | Catastrophe Interval | Effect on 100-Turn Game |
|-------|---------------------|-------------------------|
| 1× | Normal (~255 ticks between events) | 1-2 catastrophes |
| 2× | ÷2 | 2-3 catastrophes |
| 5× | ÷5 | 4-5 catastrophes |
| 10× | ÷10 | 8-10 catastrophes |

Higher speeds stress-test flexibility and triage under pressure.

### 3. Results Dashboard

After all games complete, Terminus displays a scrollable vertical chart view:

- **Score progression chart**: Line chart per LLM showing colony score across all games
- **Trend classification**: Improving / Consistent / Degrading / Volatile (with p-values)
- **Dimension radar charts**: Spider chart per LLM showing strength across 8 dimensions
- **Head-to-head comparison**: Side-by-side bar charts when 2+ LLMs are tested
- **Consistency score**: Standard deviation of performance across games
- **LLM archetype**: Classification (Strategist, Accountant, Firefighter, Marathon Runner, Diplomat, Fortress, All-Rounder, Specialist)

### 4. Data Export

All benchmark data can be exported in:

- **JSON** — Full structured data with every turn snapshot, action, and metric
- **HTML** — Interactive report with charts and drill-down tables
- **CSV** — Tabular summary for spreadsheet analysis
- **Markdown** — Human-readable report

---

## The 8 Cognitive Dimensions

The benchmark measures 8 capabilities that predict production agentic performance. Each is computed from a subset of 31 game-level metrics (see [metrics.md](metrics.md) for full specification).

### Dimension 1: Multi-Decision Coherence (+ State Fidelity)

**Production prediction:** Agent step budget — how many sequential decisions before self-contradiction.

**What it measures:** Does the model maintain consistent strategy across 100+ decisions? Does it accurately recall its own state? Detects the inflection point where coherence degrades.

**Key outputs:** Coherence score (0–1), inflection point (turn #), state fidelity per checkpoint, coherence-fidelity quadrant classification.

---

### Dimension 2: Applied Arithmetic Under Cognitive Load

**Production prediction:** Tool-call parameter reliability — will API parameters be correct as context grows?

**What it measures:** Can the model do resource math (4 resources + 6 worker roles + 10 building costs + market prices + production rates) while simultaneously reasoning about strategy? Tests arithmetic that would be trivial in isolation but errors emerge under load.

**Key outputs:** Overall accuracy (0–1), accuracy at low vs high load, load degradation slope, error type breakdown.

---

### Dimension 3: Priority Triage Under Competing Constraints

**Production prediction:** Incident response automation — will the AI address P0 before P2?

**What it measures:** When multiple urgent things demand attention simultaneously (starvation + building damage + incoming catastrophe), does the model identify the most critical constraint? There's an objectively correct priority order.

**Key outputs:** Triage accuracy (0–1), average priority rank chosen, accuracy vs constraint count.

---

### Dimension 4: Compounding Error Recognition

**Production prediction:** Self-healing agent effectiveness — will it catch snowballing mistakes?

**What it measures:** Can the model detect that a small earlier mistake (e.g., wrong worker allocation) is creating a negative resource trajectory and correct course BEFORE crisis hits? Measures detection lead time.

**Key outputs:** Average detection lead time (ticks), crisis avoidance rate, false positive rate.

---

### Dimension 5: Justified Pivot vs Inconsistency

**Production prediction:** Code review stability — stable implementations vs constant rewrites.

**What it measures:** The difference between "I should change strategy because circumstances changed" and "I'm just being incoherent." Scores the ratio of justified strategy changes (triggered by events) to unjustified changes (random flipping).

**Key outputs:** Signal-to-noise ratio (0–1), pivot count, trigger response rate, stability periods.

---

### Dimension 6: Graceful Degradation (+ Context Window)

**Production prediction:** SLA predictability — gradual vs cliff failure + context management strategy.

**What it measures:** The shape of the performance curve over 100 turns. Classifies failure mode (Stable, Linear Decay, Cliff Failure, Oscillating, Improving). Separates turn-based degradation from token-based context pressure.

**Key outputs:** Failure mode classification, effective decision budget, operational context window (tokens), degradation driver (context-bound vs reasoning-bound).

---

### Dimension 7: Opportunity Cost Awareness

**Production prediction:** Solution quality ceiling — best solution vs merely acceptable.

**What it measures:** The gap between the model's chosen action value and the theoretically optimal action. A model can always produce *valid* actions while consistently choosing suboptimal ones. This measures whether it picks THE BEST valid action, not just ANY valid action.

**Key outputs:** Average opportunity cost, optimal action rate, near-optimal rate, worst decisions list.

---

### Dimension 8: Game-Theoretic Sophistication

**Production prediction:** Multi-agent robustness — auction systems, marketplace agents, adversarial environments.

**What it measures:** Does the model reason about opponents' strategies or play in a vacuum? Tests opponent modeling, exploitation resistance, strategic diversity, cooperative rationality, and market adversarial awareness across 6 opponent archetypes.

**Key outputs:** Overall game theory score (0–1), win rate matrix, adaptation speed, exploitation gap, Nash distance, strategy fingerprint.

---

## Composite Scoring

### Weighted Aggregate Score

```
Final Score = Σ (dimension_score × weight) / Σ weights
```

### 9 Preset Weight Distributions

| Preset | Coherence | Arithmetic | Triage | Error Recog | Pivot | Degradation | Opportunity | Game Theory |
|--------|-----------|-----------|--------|-------------|-------|-------------|-------------|-------------|
| **Balanced** | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| **Reliability** | 1.5 | 2.0 | 1.0 | 1.5 | 0.5 | 2.0 | 0.5 | 0.5 |
| **Strategy** | 1.0 | 0.5 | 1.5 | 1.0 | 2.0 | 0.5 | 2.0 | 1.5 |
| **Triage** | 0.5 | 1.0 | 3.0 | 2.0 | 1.0 | 1.0 | 0.5 | 0.5 |
| **Endurance** | 2.5 | 1.5 | 0.5 | 1.0 | 1.0 | 2.5 | 0.5 | 0.5 |
| **Precision** | 0.5 | 3.0 | 1.0 | 1.0 | 0.5 | 1.0 | 2.0 | 1.0 |
| **Adversarial** | 1.0 | 1.5 | 1.0 | 0.5 | 1.5 | 1.0 | 1.0 | 3.0 |
| **Coordination** | 1.5 | 1.0 | 1.0 | 1.0 | 1.5 | 1.0 | 1.0 | 2.5 |
| **Context** | 2.0 | 1.5 | 0.5 | 1.0 | 0.5 | 2.5 | 0.5 | 0.5 |

### Trend Analysis

Across N games, the system classifies performance trends:

| Classification | Criteria | Production Implication |
|---|---|---|
| **Improving** | Positive slope, p < 0.05 | Model benefits from repeated exposure |
| **Consistent** | Slope ≈ 0, std dev < 0.05 | Predictable — safe for SLA commitments |
| **Degrading** | Negative slope, p < 0.05 | May be memorizing failure patterns |
| **Volatile** | Std dev > 0.12 | Unreliable — not suitable for deterministic pipelines |

### LLM Archetypes (Cross-Dimension Correlations)

| Archetype | High Dimensions | Low Dimensions | Best For |
|-----------|----------------|----------------|----------|
| **Strategist** | Opportunity Cost, Pivot, Game Theory | Arithmetic, Degradation | Planning, architecture decisions |
| **Accountant** | Arithmetic, Coherence, Degradation | Pivot, Game Theory | Data pipelines, financial workflows |
| **Firefighter** | Triage, Error Recog, Pivot | Coherence, Opportunity Cost | Incident response, monitoring |
| **Marathon Runner** | Coherence, Degradation, Arithmetic | Triage, Pivot | Long-running research, documentation |
| **Diplomat** | Game Theory, Pivot, Coherence | Arithmetic, Triage | Multi-agent negotiation, coordination |
| **Fortress** | Game Theory (resistance), Degradation | Pivot, Cooperation | Adversarial environments, security |
| **All-Rounder** | Balanced (all 0.6–0.8) | None extreme | General-purpose agentic deployment |
| **Specialist** | One dimension > 0.9 | Others < 0.5 | Targeted use matching the strong dimension |

---

## LLM Interface

### Action Space

Each turn, the LLM receives a structured game state and must respond with a JSON action. See [prompt-template.md](prompt-template.md) for exact prompts and [schemas.md](schemas.md) for full schema definitions.

**State sent to LLM (abbreviated):**

```json
{
  "turn": 42,
  "max_turns": 100,
  "score": 1250,
  "rank": 1,
  "resources": {"food": 120, "materials": 85, "knowledge": 40, "gold": 200},
  "population": 35,
  "morale": 0.82,
  "workers": {"farming": 8, "mining": 6, "research": 5, "construction": 8, "defense": 4, "medicine": 4},
  "buildings": [{"type": "farm", "level": 2, "health": 100}],
  "market_prices": {"food": 3.2, "materials": 5.1, "knowledge": 8.7},
  "opponents": [{"name": "Greedy-Bot", "score": 980, "population": 28}],
  "available_actions": [{"action_type": "BUILD", "description": "Build Mine", "cost": "30 materials, 10 gold"}],
  "catastrophe_warning": null
}
```

**LLM responds with:**

```json
{
  "action": "BUILD",
  "params": {"building_type": "mine"},
  "reasoning": {
    "factors": [
      {"factor": "resource_bottleneck", "weight": 0.5},
      {"factor": "long_term_growth", "weight": 0.3},
      {"factor": "catastrophe_preparation", "weight": 0.2}
    ],
    "primary_goal": "materials_production"
  }
}
```

**7 action types:** BUILD, UPGRADE, ALLOCATE_WORKERS, TRADE_BUY, TRADE_SELL, DEMOLISH, REPAIR, PASS

**12 structured reasoning factors:** resource_bottleneck, long_term_growth, opponent_pressure, catastrophe_preparation, market_opportunity, efficiency_optimization, defensive_positioning, cooperative_opportunity, specialization_synergy, immediate_survival, information_gathering, risk_diversification

### Prompt Standardization

All LLMs receive identical:
- System prompt (~1300 tokens explaining rules, actions, format)
- Game state (same JSON schema via `BenchmarkGameState`)
- History window (same truncation policy per context strategy)
- Temperature (0.3) and max_tokens (300)

The only variable is the model itself.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Benchmark Host UI (TUI)                        │
│  - Configure LLMs, opponents, dimensions, weights            │
│  - Monitor live game progress (error rates, scores)          │
│  - View results (radar charts, trend lines, archetypes)      │
│  - Export (JSON, HTML, CSV, Markdown)                         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                 Benchmark Orchestrator                        │
│  - Manages game sequences (N games × M matchups)             │
│  - Seeds RNG for reproducibility                             │
│  - Controls turn loop (send state → get action → validate)   │
│  - Applies speed multiplier to catastrophe schedule          │
│  - Handles errors/retries/DQ (see error-handling.md)         │
│  - Records per-turn snapshots                                │
└────────────────────────────┬────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  LLM Adapter    │ │  LLM Adapter    │ │  Built-in Agent │
│  (OpenAI API)   │ │  (Anthropic)    │ │  (Greedy/Rush)  │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│               GameEngine (Headless Mode)                      │
│  - Direct method calls (no FastAPI/WebSocket)                 │
│  - Manual tick advancement (no async timer)                   │
│  - Full game rules, validation, catastrophe system           │
│  - See engine-integration.md for API surface                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Built-in Opponents

| Agent | Strategy | Tests |
|-------|----------|-------|
| **Random** | Uniform random from valid actions | Baseline — any competent model should dominate |
| **Greedy** | Always picks highest immediate-value action | Can the LLM outperform short-term optimization? |
| **Balanced** | Fixed optimal build order + smart allocation | Can the LLM beat a "textbook" strategy? |
| **Rush** | Aggressive early expansion, ignores defense | Can the LLM exploit overcommitment? |
| **Turtle** | Heavy defense, slow growth, strong late-game | Can the LLM win before turtle's advantage matures? |
| **Adversarial** | Adapts to target the LLM's observed weaknesses | Can the LLM resist active exploitation? |

**Opponent depth configurations:**
- **Quick** (3 types): Random + Greedy + Balanced → 3 × N games
- **Standard** (6 types): All six archetypes → 6 × N games
- **Deep** (8 games): Standard + repeated adversarial with adaptation → 8 × N games

---

## User Flow

1. **Launch**: `terminus --benchmark` or select "LLM Benchmark" from main menu
2. **Configure LLMs**: Add model endpoints (OpenAI-compatible API format), name each, test connection
3. **Configure test**: Set game count, speed multiplier, opponent depth, weight preset
4. **Run**: Games execute (concurrent LLM queries within turns, sequential turns)
5. **Monitor**: Live progress bar, error rates, current game score, turn counter, DQ warnings
6. **Results**: Scrollable vertical view with dimension charts, archetype classification, trend analysis
7. **Export**: Save results to JSON/HTML/CSV/Markdown

---

## Future Considerations

- **Public leaderboard**: Opt-in submission of results with standard preset seeds for fair comparison
- **Custom scenarios**: Pre-built stress tests ("catastrophe gauntlet" for Triage, "long game" for Degradation, "market chaos" for Arithmetic)
- **Prompt engineering comparison**: Same model, different system prompts — which yields best gameplay?
- **Fine-tuning signal**: Use benchmark game logs as training data for game-specific fine-tunes
- **Human baseline**: Let humans play the same scenarios for calibration
- **Cost tracking**: Track API tokens consumed per game for cost-efficiency analysis
- **HiveShip integration**: Auto-run benchmark before deploying models in agentic pipelines, using dimension scores to select the right model for each pipeline stage
