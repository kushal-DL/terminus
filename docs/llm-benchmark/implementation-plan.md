# LLM Benchmark — Implementation Plan

This document outlines the technical implementation phases. **No code changes until approved.**

---

## Phase 1: LLM Agent Interface

**Goal:** Define the API contract between the game and LLM agents.

### Tasks:
1. Define JSON schema for game state representation sent to LLMs
2. Define JSON schema for action responses from LLMs
3. Create LLM adapter interface (abstract class) supporting:
   - OpenAI-compatible API (covers GPT, Claude via proxy, local models via LM Studio/Ollama)
   - Direct Anthropic API
   - Direct Google Generative AI API
4. Implement connection testing (ping with simple prompt)
5. Implement retry/timeout logic (LLMs can be slow or rate-limited)
6. Token counting for Context Window metric

### New Files:
```
terminus/benchmark/
├── __init__.py
├── agent.py           # Abstract LLMAgent class
├── adapters/
│   ├── __init__.py
│   ├── openai_compat.py   # OpenAI-compatible adapter
│   ├── anthropic.py       # Direct Anthropic adapter
│   └── google.py          # Direct Google AI adapter
└── schemas.py         # Pydantic models for game state / action JSON
```

### Dependencies:
- `httpx` (already in project) for API calls
- `tiktoken` or equivalent for token counting
- No new heavy dependencies

---

## Phase 2: Benchmark Orchestrator

**Goal:** Run multiple games with LLM agents, collect data.

### Tasks:
1. Create orchestrator that:
   - Instantiates game server in "headless" mode (no TUI, API only)
   - Connects LLM agents as players
   - Manages turn loop (send state → get action → validate → apply)
   - Applies speed multiplier to all timing
   - Seeds RNG for reproducibility
2. Per-turn data recording:
   - Full game state snapshot
   - LLM's raw response (action + reasoning)
   - Validation result (valid/invalid action)
   - Time taken for LLM to respond
   - Token count of prompt + response
3. Game result aggregation

### New Files:
```
terminus/benchmark/
├── orchestrator.py    # Main benchmark runner
├── recorder.py        # Per-turn data collection
├── config.py          # BenchmarkConfig pydantic model
└── speed.py           # Speed multiplier logic
```

---

## Phase 3: Metrics Engine

**Goal:** Score LLMs across the 6 dimensions.

### Tasks:
1. Implement each metric scorer as an independent class
2. Each scorer receives the full game recording and produces a 0.0–1.0 score
3. Planning Horizon scorer: requires "optimal play" reference (heuristic-based approximation)
4. Numerical Grounding scorer: compares stated reasoning to actual math
5. State Tracking scorer: injects state queries at checkpoints, compares responses
6. Flexibility scorer: detects disruption events, measures response quality
7. Game Theory scorer: analyzes opponent-aware behavior patterns
8. Context Window scorer: measures quality degradation over game length
9. Composite scorer: weighted aggregation with configurable weights

### New Files:
```
terminus/benchmark/
├── metrics/
│   ├── __init__.py
│   ├── base.py              # Abstract MetricScorer
│   ├── planning.py          # Planning Horizon
│   ├── numerical.py         # Numerical Grounding
│   ├── state_tracking.py    # State Tracking Fidelity
│   ├── flexibility.py       # Strategic Flexibility
│   ├── game_theory.py       # Game-Theoretic Sophistication
│   ├── context_window.py    # Context Window Utilization
│   └── composite.py         # Weighted composite scorer
```

---

## Phase 4: Results UI

**Goal:** TUI screens for configuration and results viewing.

### Tasks:
1. LLM configuration screen (add/edit/test models)
2. Test configuration screen (game count, speed, metrics, weights)
3. Live progress screen (real-time scores, turn counter, ETA)
4. Results dashboard (scrollable vertical charts)
5. ASCII chart rendering (line charts, bar charts, tables)
6. Export functionality (JSON, CSV, Markdown)

### New Files:
```
terminus/client/screens/
├── benchmark_setup.py      # Screens 1 & 2 (config)
├── benchmark_progress.py   # Screen 3 (live monitoring)
├── benchmark_results.py    # Screen 4 (charts/tables)
└── benchmark_export.py     # Screen 5 (export dialog)

terminus/client/widgets/
├── ascii_chart.py          # Reusable ASCII line chart widget
└── metric_table.py         # Colored metric comparison table
```

---

## Phase 5: Built-in Opponents

**Goal:** Provide standardized opponents for consistent benchmarking.

### Tasks:
1. Random agent (uniform random from valid actions)
2. Greedy heuristic (always picks highest immediate value)
3. Rush strategy (prioritize military/expansion)
4. Turtle strategy (prioritize defense/economy)
5. Mirror agent (copies opponent's last action)
6. Adversarial agent (simple counter-strategy rules)

### New Files:
```
terminus/benchmark/
├── opponents/
│   ├── __init__.py
│   ├── random_agent.py
│   ├── greedy_agent.py
│   ├── rush_agent.py
│   ├── turtle_agent.py
│   ├── mirror_agent.py
│   └── adversarial_agent.py
```

---

## Phase 6: Data Export & Analysis

**Goal:** Make results portable and analyzable.

### Tasks:
1. JSON export (full fidelity — every turn, every action, every metric)
2. CSV export (summary — one row per model per game)
3. Markdown export (human-readable report with inline ASCII charts)
4. Optional: HTML export with interactive charts (stretch goal)
5. Statistical analysis: significance tests, confidence intervals, effect sizes

### New Files:
```
terminus/benchmark/
├── export/
│   ├── __init__.py
│   ├── json_export.py
│   ├── csv_export.py
│   ├── markdown_export.py
│   └── statistics.py      # Significance tests, CI calculations
```

---

## Phase 7: CLI & Menu Integration

**Goal:** Wire everything into the existing game.

### Tasks:
1. Add "LLM Benchmark" to main menu
2. Add `--benchmark` CLI flag
3. Add `--benchmark-config <path>` for headless/CI runs
4. Store API keys in OS keyring (not config files)
5. Add benchmark results to a local SQLite table for historical comparison

---

## Dependency Summary

| Package | Purpose | Already in project? |
|---------|---------|---------------------|
| httpx | LLM API calls | ✓ Yes |
| pydantic | Config/schema validation | ✓ Yes |
| aiosqlite | Results storage | ✓ Yes |
| tiktoken | Token counting (OpenAI models) | ✗ New |
| keyring | Secure API key storage | ✗ New |
| scipy | Statistical tests (Mann-Whitney, etc.) | ✗ New (optional) |

---

## Estimated Scope

| Phase | Files | Complexity |
|-------|-------|-----------|
| 1. Agent Interface | ~6 | Medium |
| 2. Orchestrator | ~5 | High |
| 3. Metrics Engine | ~9 | High |
| 4. Results UI | ~6 | Medium |
| 5. Opponents | ~7 | Low |
| 6. Export | ~5 | Low |
| 7. Integration | ~3 | Low |
| **Total** | **~41** | — |

---

## Decisions (Resolved)

### 1. Turn Mode: Simultaneous (Real-Time)

LLMs play simultaneously. All agents receive game state at the same time and submit actions within a turn window. This tests real-time strategic thinking and avoids giving later players an information advantage. The turn window is configurable and scales with the game speed multiplier.

### 2. Async Tournament Brackets: Yes

The benchmark supports overnight/unattended tournament runs:
- Host configures a bracket (round-robin, elimination, or Swiss-system)
- Games run sequentially or in parallel (configurable)
- Progress is persisted to SQLite — can resume after interruption
- Results are available when the host returns
- Optional: email/webhook notification on completion

### 3. Public Leaderboard API: Yes

A public API endpoint allows hosts to submit benchmark results:
- Submission includes: model name, version, benchmark config hash, metric scores, game count
- Server validates result integrity (config hash must match a known standard benchmark preset)
- Leaderboard viewable at a public URL
- Opt-in only — results are never submitted without explicit host action
- Anti-gaming: standard benchmark presets with fixed seeds required for leaderboard submissions

### 4. Rate Limiting: Host-Configurable (Optional)

The host can set a common rate limit that applies to all LLM API calls:

| Setting | Behavior |
|---------|----------|
| No limit (default for self-hosted) | Fire requests as fast as the game loop allows |
| Requests/minute cap | Queue actions, delay turns if limit would be exceeded |
| Concurrent request cap | Limit parallel API calls across all agents |
| Per-model override | Different limits per model (e.g., cloud API = 60rpm, local vLLM = unlimited) |

This accommodates both cloud APIs with strict rate limits and self-hosted vLLM/Ollama instances with no limits. When rate-limited, the orchestrator slows the game loop rather than dropping actions.

### 5. Reasoning: Hybrid Structured Method

Instead of free-text reasoning (expensive, hard to evaluate) or no reasoning (loses metric signal), we use a **structured hybrid approach**:

The LLM selects from a predefined list of **decision factors** and assigns weights indicating how much each factor influenced the decision:

```json
{
  "action": "build",
  "params": {"building_type": "solar_array"},
  "reasoning": {
    "factors": [
      {"factor": "resource_bottleneck", "weight": 0.5},
      {"factor": "long_term_growth", "weight": 0.3},
      {"factor": "opponent_pressure", "weight": 0.1},
      {"factor": "catastrophe_preparation", "weight": 0.1}
    ],
    "primary_goal": "energy_production"
  }
}
```

**Available decision factors** (predefined list the LLM selects from):
- `resource_bottleneck` — Addressing a resource shortage
- `long_term_growth` — Investing in future capacity
- `opponent_pressure` — Responding to opponent's actions
- `catastrophe_preparation` — Hedging against disasters
- `market_opportunity` — Exploiting favorable prices
- `efficiency_optimization` — Improving resource conversion rates
- `defensive_positioning` — Protecting existing assets
- `cooperative_opportunity` — Pursuing mutual benefit with another player
- `specialization_synergy` — Leveraging specialization bonuses
- `immediate_survival` — Preventing colony collapse
- `information_gathering` — Acting to learn about game state
- `risk_diversification` — Spreading investment across areas

**Benefits:**
- Cheap (structured output, minimal tokens)
- Consistent across models (same vocabulary)
- Directly feeds metrics (Planning Horizon can check if "long_term_growth" was selected when optimal; Flexibility can check if factor weights shift after disruptions)
- Weights reveal the LLM's "thought process" without requiring free text parsing

### 6. Minimum Viable Version (MVP)

**MVP = Phase 1 + Phase 2 + Simplified Phase 3 + Basic Phase 4**

| Phase | MVP Scope | Deferred to Post-MVP |
|-------|-----------|---------------------|
| Phase 1 | OpenAI-compatible adapter only, basic schema | Anthropic/Google direct adapters |
| Phase 2 | Sequential games, fixed seeds, speed multiplier | Parallel games, bracket system |
| Phase 3 | 3 metrics (Planning, Numerical, Flexibility) | State Tracking, Game Theory, Context Window |
| Phase 4 | Summary table + score progression chart | Full scrollable dashboard, radar charts |
| Phase 5 | Random + Greedy agents only | Rush, Turtle, Mirror, Adversarial |
| Phase 6 | JSON export only | CSV, Markdown, HTML |
| Phase 7 | CLI flag `--benchmark` | Menu integration, keyring |

**MVP delivers:** Run N games with 2+ LLMs via OpenAI-compatible API, score on 3 dimensions, show results table and line chart, export as JSON.

---

## Post-MVP Roadmap

| Milestone | Adds |
|-----------|------|
| v0.1 (MVP) | Core benchmarking, 3 metrics, basic UI |
| v0.2 | All 6 metrics, full results dashboard, CSV/MD export |
| v0.3 | Tournament brackets, async overnight runs, all opponent types |
| v0.4 | Public leaderboard API, submission/validation |
| v0.5 | Direct Anthropic/Google adapters, HTML reports, CI integration |
