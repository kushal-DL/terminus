# LLM Benchmark — Implementation Plan

This document outlines the technical implementation phases, aligned with the 8-dimension metric framework and the product backlog (Epic 12). **No code changes until approved.**

---

## Phase Overview

| Phase | Epic 12 Section | Files | Complexity | MVP? |
|-------|-----------------|-------|------------|------|
| 1. Agent Interface | 12.1 | ~7 | Medium | ✓ |
| 2. Built-in Opponents | 12.2 | ~7 | Low | Partial |
| 3. Orchestrator | 12.3 | ~6 | High | ✓ |
| 4. Metrics Engine | 12.4 | ~12 | High | Partial |
| 5. Results & Export | 12.5 | ~6 | Medium | Partial |
| 6. CLI & TUI Integration | 12.6 | ~6 | Medium | Partial |
| 7. Testing & Verification | 12.7 | ~8 | Medium | ✓ |
| **Total** | — | **~52** | — | — |

---

## Phase 1: LLM Agent Interface

**Goal:** Define the communication contract between the orchestrator and LLM models.

**Reference docs:** [schemas.md](schemas.md), [prompt-template.md](prompt-template.md)

### Tasks:
1. Implement `BenchmarkGameState` Pydantic model (what the LLM sees each turn)
2. Implement `ActionResponse` Pydantic model (what the LLM returns — action + structured reasoning)
3. Create abstract `LLMAdapter` interface with:
   - `async get_action(state: BenchmarkGameState, history: list[Message]) → ActionResponse`
   - `async test_connection() → bool`
   - `get_token_count(messages: list[Message]) → int`
4. Implement OpenAI-compatible adapter (covers GPT-4o, Claude via proxy, local via Ollama/vLLM/LM Studio)
5. Implement direct Anthropic adapter (native Messages API)
6. Implement direct Google Generative AI adapter (Gemini)
7. Implement JSON extraction + schema coercion logic (see [error-handling.md](error-handling.md) §E1/E2)
8. Implement token counting per adapter (tiktoken for OpenAI, character estimation for others)

### New Files:
```
terminus/benchmark/
├── __init__.py
├── agent.py              # Abstract LLMAdapter class + AdapterConfig
├── adapters/
│   ├── __init__.py
│   ├── openai_compat.py  # OpenAI-compatible adapter (+ Ollama, vLLM, LM Studio)
│   ├── anthropic.py      # Direct Anthropic Messages API
│   └── google.py         # Direct Google Generative AI
├── schemas.py            # BenchmarkGameState, ActionResponse, BenchmarkConfig, etc.
└── prompt.py             # System prompt builder, retry prompts, probe prompts
```

### Dependencies:
- `httpx` (already in project) for API calls
- `tiktoken` for OpenAI token counting (new, lightweight)
- No other new dependencies

---

## Phase 2: Built-in Opponents

**Goal:** Provide standardized opponents for consistent benchmarking across 6 archetypes.

**Reference docs:** [metrics.md](metrics.md) §5 (Opponent-Aware Metrics), [engine-integration.md](engine-integration.md)

### Tasks:
1. Define abstract `BuiltInAgent` interface: `choose_action(state: dict) → (ActionType, dict)`
2. **Random agent** — uniform random from valid actions (baseline)
3. **Greedy agent** — always picks highest immediate-value action (score delta heuristic)
4. **Balanced agent** — fixed optimal build order + smart worker allocation (textbook play)
5. **Rush agent** — aggressive early expansion, population maximization, ignores defense
6. **Turtle agent** — heavy defense, slow growth, strong late-game economy
7. **Adversarial agent** — observes LLM patterns over games, then exploits weaknesses

### New Files:
```
terminus/benchmark/
├── opponents/
│   ├── __init__.py
│   ├── base.py              # Abstract BuiltInAgent
│   ├── random_agent.py
│   ├── greedy_agent.py
│   ├── balanced_agent.py
│   ├── rush_agent.py
│   ├── turtle_agent.py
│   └── adversarial_agent.py
```

---

## Phase 3: Orchestrator

**Goal:** Run benchmark games end-to-end — manage turn loop, apply speed multiplier, handle errors, record data.

**Reference docs:** [engine-integration.md](engine-integration.md), [error-handling.md](error-handling.md)

### Tasks:
1. Create `BenchmarkOrchestrator`:
   - Initialize GameEngine in headless mode (no persistence, no WebSocket)
   - Add LLM player + opponent player
   - Skip lobby/setup phase (programmatic assignment)
   - Run synchronous turn loop (state → prompt → response → validate → apply → tick)
   - Apply speed multiplier to catastrophe schedule
   - Seed RNG for reproducibility
2. Create `StateConverter`:
   - Engine `get_player_state()` dict → `BenchmarkGameState` schema
   - Compute available actions (filtered to affordable)
   - Track market rolling averages for context
3. Create `TurnRecorder`:
   - Store per-turn `TurnSnapshot` (state, response, validity, latency, tokens)
   - Finalize into `GameRecording` with scores
4. Create `ErrorHandler`:
   - JSON extraction + retry logic (max 3 retries)
   - Schema coercion + retry (max 2)
   - Timeout handling (30s default, 1 retry)
   - Rate limit queueing with exponential backoff
   - Disqualification tracking (10 consecutive invalid = DQ)
5. Create `SpeedController`:
   - Modify catastrophe schedule based on multiplier
   - Track effective turn mapping
6. Implement concurrent LLM queries (asyncio.gather for multiple agents per tick)

### New Files:
```
terminus/benchmark/
├── orchestrator.py       # Main benchmark runner (turn loop, game management)
├── state_converter.py    # Engine state → BenchmarkGameState
├── recorder.py           # TurnRecorder + GameRecording builder
├── error_handler.py      # Retry logic, DQ tracking, error classification
├── speed.py              # Speed multiplier + catastrophe schedule compression
└── config.py             # BenchmarkConfig, ErrorHandlingConfig, TimeoutConfig
```

---

## Phase 4: Metrics Engine

**Goal:** Score LLMs across 8 cognitive dimensions using 31 Tier 1 game metrics.

**Reference docs:** [metrics.md](metrics.md) (full specification)

### Tasks:
1. Create abstract `MetricScorer` base: receives `GameRecording`, returns `DimensionScore`
2. Implement Tier 1 collectors (31 game metrics computed from turn data):
   - Planning metrics (6): build order, worker anticipation, market timing, catastrophe prep, housing, stockpile
   - Numerical metrics (6): invalid rate, worker sum, over-capacity, production timing, trade math, multi-resource
   - Flexibility metrics (7): recovery speed, worker realloc, repair priority, market adapt, starvation response, defense learning, action shift
   - State probe metrics (4): building recall, resource awareness, strategy consistency, history recall
   - Opponent-aware metrics (5): win rate, exploitation resistance, counter-detection, cooperation, manipulation detection
   - Context pressure metrics (3): per-quartile quality, historical reference rate, collapse point
3. Implement Tier 2 dimension scorers (8):
   - `coherence.py` — Multi-Decision Coherence + State Fidelity (Dim 1)
   - `arithmetic.py` — Applied Arithmetic Under Cognitive Load (Dim 2)
   - `triage.py` — Priority Triage Under Competing Constraints (Dim 3)
   - `error_recognition.py` — Compounding Error Recognition (Dim 4)
   - `pivot.py` — Justified Pivot vs Inconsistency (Dim 5)
   - `degradation.py` — Graceful Degradation + Context Window (Dim 6)
   - `opportunity.py` — Opportunity Cost Awareness (Dim 7)
   - `game_theory.py` — Game-Theoretic Sophistication (Dim 8)
4. Implement composite scorer: weighted aggregation with 9 presets
5. Implement trend analysis: linear regression, classification (Improving/Consistent/Degrading/Volatile)
6. Implement archetype classification: cross-dimension correlation → 8 archetype labels
7. Implement Tier 3 mapping: dimension scores → agentic workflow predictions
8. Implement optimal action evaluator (for Opportunity Cost): deterministic 20-tick simulator

### New Files:
```
terminus/benchmark/
├── metrics/
│   ├── __init__.py
│   ├── base.py                # Abstract MetricScorer, DimensionScore model
│   ├── tier1/
│   │   ├── __init__.py
│   │   ├── planning.py        # 6 planning metrics
│   │   ├── numerical.py       # 6 numerical metrics
│   │   ├── flexibility.py     # 7 flexibility metrics
│   │   ├── state_probes.py    # 4 state probe metrics
│   │   ├── opponent.py        # 5 opponent-aware metrics
│   │   └── context.py         # 3 context pressure metrics
│   ├── tier2/
│   │   ├── __init__.py
│   │   ├── coherence.py       # Dimension 1
│   │   ├── arithmetic.py      # Dimension 2
│   │   ├── triage.py          # Dimension 3
│   │   ├── error_recognition.py  # Dimension 4
│   │   ├── pivot.py           # Dimension 5
│   │   ├── degradation.py     # Dimension 6
│   │   ├── opportunity.py     # Dimension 7
│   │   └── game_theory.py     # Dimension 8
│   ├── composite.py           # Weighted composite scorer + 9 presets
│   ├── trend.py               # Trend analysis + classification
│   ├── archetypes.py          # Cross-dimension archetype classification
│   └── optimal_evaluator.py   # Deterministic simulator for opportunity cost
```

---

## Phase 5: Results & Export

**Goal:** Display results in TUI and export in multiple formats.

### Tasks:
1. Create `BenchmarkResult` aggregator (per-model scores, per-dimension, trends, archetypes)
2. JSON export — full fidelity (every turn, every action, every metric, per Pydantic schema)
3. HTML export — interactive report with:
   - Dimension radar charts (per model)
   - Score progression line charts
   - Head-to-head comparison tables
   - Archetype badges
   - Drill-down to individual games/turns
4. CSV export — one row per model per game, dimension scores as columns
5. Markdown export — human-readable summary with inline tables
6. Statistical analysis: Mann-Whitney U, Kruskal-Wallis, confidence intervals, effect sizes

### New Files:
```
terminus/benchmark/
├── results.py             # BenchmarkResult aggregator
├── export/
│   ├── __init__.py
│   ├── json_export.py
│   ├── html_export.py     # Jinja2 templates + embedded charts
│   ├── csv_export.py
│   ├── markdown_export.py
│   └── statistics.py      # Significance tests, CI calculations
```

---

## Phase 6: CLI & TUI Integration

**Goal:** Wire benchmark into the existing game interface.

### Tasks:
1. Add "LLM Benchmark" to main TUI menu
2. Create benchmark setup screen (model config, test params, weight presets)
3. Create live progress screen (turn counter, error rates, live scores, DQ warnings)
4. Create results dashboard screen (radar charts, trends, archetypes, comparison)
5. Create export dialog (format selection, path)
6. Add `--benchmark` CLI flag for headless runs
7. Add `--benchmark-config <path.json>` for CI/automation
8. Secure API key handling (environment variables or OS keyring)

### New Files:
```
terminus/client/screens/
├── benchmark_setup.py       # Model config + test params
├── benchmark_progress.py    # Live monitoring
├── benchmark_results.py     # Charts + tables + archetypes
└── benchmark_export.py      # Export dialog

terminus/client/widgets/
├── radar_chart.py           # ASCII radar chart widget
├── dimension_table.py       # Colored dimension comparison table
└── progress_bar.py          # Benchmark-specific progress display
```

---

## Phase 7: Testing & Verification

**Goal:** Ensure correctness of metrics, integration, and edge cases.

### Tasks:
1. Unit tests for each Tier 1 metric calculator (known inputs → expected scores)
2. Unit tests for each Tier 2 dimension scorer (mocked Tier 1 → expected composites)
3. Integration test: headless game with mock LLM (scripted responses) → full pipeline
4. Integration test: real OpenAI-compatible API (Ollama local) → end-to-end
5. Regression tests: fixed seed games produce identical recordings
6. Edge case tests: DQ triggers, rate limit aborts, context overflow
7. Performance tests: 100-turn game completes in <5 min with local model
8. Validation: Random agent scores near 0, Greedy agent scores ~0.3–0.5 (sanity check)

### New Files:
```
tests/benchmark/
├── __init__.py
├── test_schemas.py          # Schema validation, serialization
├── test_adapters.py         # Adapter mock tests
├── test_orchestrator.py     # Turn loop, error handling
├── test_metrics_tier1.py    # All 31 Tier 1 metrics
├── test_metrics_tier2.py    # All 8 dimension scorers
├── test_composite.py        # Weighted scoring, presets, archetypes
├── test_opponents.py        # Built-in agent correctness
├── test_headless.py         # Full headless integration
└── test_export.py           # Export format validation
```

---

## Dependency Summary

| Package | Purpose | Already in project? |
|---------|---------|---------------------|
| httpx | LLM API calls | ✓ Yes |
| pydantic | Config/schema validation | ✓ Yes |
| aiosqlite | Results storage (optional) | ✓ Yes |
| tiktoken | Token counting (OpenAI models) | ✗ New |
| jinja2 | HTML report templates | ✗ New |
| scipy | Statistical tests (Mann-Whitney, etc.) | ✗ New (optional) |
| keyring | Secure API key storage | ✗ New (optional) |

---

## Decisions (Resolved)

### 1. Turn Mode: Synchronous Manual Advancement

The orchestrator controls tick advancement explicitly — no real-time timer, no sleep. All agents receive state simultaneously, submit actions, then the tick advances. This eliminates timing variance between models. See [engine-integration.md](engine-integration.md) for details.

### 2. Headless Mode (Direct Method Calls)

No FastAPI/WebSocket layer. The orchestrator calls `GameEngine` methods directly:
- `get_player_state()` → state dict
- `handle_action()` → validate + apply
- `_tick()` → advance game

This eliminates HTTP overhead and makes the benchmark purely CPU + LLM-API bound.

### 3. Structured Reasoning (Hybrid Method)

The LLM selects from 12 predefined decision factors and assigns weights. This is:
- Cheap (minimal tokens vs free-text)
- Consistent across models (same vocabulary)
- Directly feeds metrics (Coherence tracks factor shifts; Pivot checks if shifts are triggered)

See [prompt-template.md](prompt-template.md) for full factor list.

### 4. Available Actions: Filtered to Affordable

The prompt includes ONLY actions the player can currently afford. This reduces noise (model doesn't need to verify affordability) but still tests arithmetic (quantities and multi-resource interactions are NOT pre-computed).

### 5. Temperature: Fixed 0.3

All models use temperature=0.3 for consistency + some diversity. Configurable but fixed across models in a single benchmark run to ensure fair comparison.

### 6. Context Strategy: Auto-Select

- Models with 128K+ context: full conversation history
- Models with <128K: sliding window (system prompt + last N turns)

Configurable override available.

### 7. Speed Multiplier: Compresses Catastrophes Only

Does NOT reduce tick count. Divides catastrophe scheduling so the same 100 turns encounter more disruption events. Production, consumption, and market mechanics remain per-tick unchanged.

### 8. State Probes: Off-Clock

At turns 10/25/50/75/100, the benchmark pauses, sends 4 structured queries, collects state recall data. These do NOT consume a game turn and are NOT included in the model's conversation history for subsequent turns.

### 9. Opponent Depth: Configurable

- **Quick** (MVP): Random + Greedy + Balanced (3 × N games)
- **Standard**: All 6 archetypes (6 × N games, recommended)
- **Deep**: Standard + repeated adversarial with adaptation (8 × N games)

---

## Minimum Viable Version (MVP)

**MVP = Phase 1 + Phase 2 (partial) + Phase 3 + Phase 4 (partial) + Phase 7**

| Phase | MVP Scope | Deferred to Post-MVP |
|-------|-----------|---------------------|
| Phase 1 | All adapters, full schema | — (complete) |
| Phase 2 | Random + Greedy + Balanced only | Rush, Turtle, Adversarial |
| Phase 3 | Full orchestrator, error handling, recording | — (complete) |
| Phase 4 | Dims 1–4 + composite scorer | Dims 5–8 (require multiple opponents), archetypes, Tier 3 |
| Phase 5 | JSON export + summary table | HTML, CSV, Markdown, statistics |
| Phase 6 | `--benchmark` CLI flag only | Full TUI screens, menu integration |
| Phase 7 | Core tests (schemas, orchestrator, Dims 1–4) | Full test suite |

**MVP delivers:** Run N games with LLM via any adapter against 3 opponents, score on 4 dimensions (Coherence, Arithmetic, Triage, Error Recognition), show JSON results + summary table via CLI.

---

## Post-MVP Roadmap

| Milestone | Adds |
|-----------|------|
| **v0.1 (MVP)** | Core benchmarking, 4 dimensions, 3 opponents, JSON export, CLI |
| **v0.2** | All 8 dimensions, all 6 opponents, composite scoring + presets |
| **v0.3** | Full TUI (setup, progress, results screens), HTML export, archetypes |
| **v0.4** | Trend analysis, statistical significance, CSV/Markdown export |
| **v0.5** | Deep opponent mode (adversarial adaptation), Tier 3 agentic predictions |
| **v0.6** | Public leaderboard API, CI integration, overnight tournament brackets |

---

## Estimated Runtimes

| Configuration | Games | Time per Game | Total Estimate |
|---|---|---|---|
| MVP (1 model, 3 opponents, 10 games each) | 30 | ~3 min | ~90 min |
| Standard (2 models, 6 opponents, 10 games) | 120 | ~3 min | ~6 hours |
| Deep (3 models, 8 opponents, 30 games) | 720 | ~3 min | ~36 hours |
| Local model (Ollama, ~300ms/turn) | 30 | ~45 sec | ~22 min |

Parallelization across independent games can significantly reduce wall-clock time for multi-model benchmarks.
