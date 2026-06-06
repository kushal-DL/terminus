# Terminus — CLAUDE.md

## Project Overview

Terminus is a **multiplayer CLI survival strategy game** and **LLM benchmark platform**. Players manage colonies, allocate workers, construct buildings, survive catastrophes, and trade resources. In benchmark mode, LLM agents play autonomously — their decisions are scored across 8 cognitive dimensions to predict production agentic performance.

**Stack:** Python 3.11+, Textual (TUI), FastAPI + WebSocket (multiplayer server), Pydantic v2, httpx (async HTTP), aiosqlite (persistence). No React, no frontend framework.

**Entry point:** `python -m terminus` (TUI + server) or `terminus` (installed CLI)

---

## Repository Layout

```
terminus/
├── server/          # FastAPI game server + WebSocket
│   ├── engine.py    # Core GameEngine — all game logic lives here
│   ├── models.py    # Pydantic models: Player, Colony, GameState, ActionType, etc.
│   ├── app.py       # FastAPI routes + WebSocket handler
│   └── persistence.py  # aiosqlite game state persistence
├── client/          # Textual TUI client
│   ├── app.py       # TerminusApp — root Textual app
│   ├── screens/     # One file per screen (colony, build, market, lobby, benchmark_*)
│   └── widgets/     # Reusable Textual widgets
├── benchmark/       # LLM benchmarking subsystem (see section below)
├── audio/           # Optional audio (simpleaudio)
├── data/            # Static game data (buildings, catastrophes, etc.)
├── config.py        # Global constants
└── __main__.py      # CLI entry point
tests/               # pytest suite (594 tests, all passing)
docs/
└── llm-benchmark/   # Benchmark documentation (metrics, schemas, prompts, UI flow)
    └── implementation-plan.md   # ← AUTHORITATIVE phase status document
product-backlog/     # Per-epic backlog files (BACKLOG.md + epic-*.md)
play.bat             # Windows double-click launcher
play.sh              # Mac/Linux launcher
run_benchmark.py     # Benchmark runner helper (sets API key in-process)
benchmark-config.example.json  # Example benchmark config
```

---

## How to Run

```bash
# Easiest — Windows double-click launcher (handles venv + deps automatically)
play.bat          # or: bash play.sh on Mac/Linux

# Install (editable) for development
pip install -e ".[dev]"

# Run TUI + server
python -m terminus

# Run all tests (594 passing)
pytest

# Run fast subset only (skips slow benchmark integration tests, ~10s)
pytest -m "not slow"

# Run only benchmark unit tests (~2s)
pytest tests/test_metrics_tier1.py tests/test_dimensions_tier2.py tests/test_opponents.py tests/test_orchestrator_v2.py

# Run benchmark with mock LLM (no real API key needed)
TERMINUS_BENCHMARK_MOCK=1 python -m terminus

# Run benchmark headlessly
python run_benchmark.py benchmark-config.example.json
```

---

## Doc Maintenance Rule

**Every code change that touches benchmark logic MUST update all three of these:**

1. `docs/llm-benchmark/implementation-plan.md` — update the phase Status field, check off acceptance criteria, update test counts, update File Structure if files changed
2. `product-backlog/BACKLOG.md` — update the Epic 12 table rows (⬜ → ✅/🔨/🚧), update the Progress Summary table counts, update Last Updated date
3. `product-backlog/epic-12-llm-benchmark.md` — update story Status fields and Implementation Notes
4. `CLAUDE.md` Phase Status table — mirror the implementation-plan statuses

The implementation plan and backlog are the canonical sources of truth for what's done. Letting them go stale defeats their purpose.

---

## Benchmark System — Architecture & Status

The benchmark subsystem lives entirely in `terminus/benchmark/`. It runs LLMs through headless games and scores them across 8 cognitive dimensions using a 3-tier pipeline.

### Pipeline (top-down)

```
BenchmarkSetupScreen (TUI config)
  ↓ BenchmarkConfig (Pydantic)
BenchmarkRunner (terminus/benchmark/runner.py)
  ↓ for each (model × opponent × game):
BenchmarkOrchestrator (terminus/benchmark/orchestrator_v2.py)
  ├── LLMAdapter (benchmark/adapters/) → API calls
  ├── BuiltInAgent (benchmark/opponents/) → opponent decisions
  ├── StateConverter → engine state → BenchmarkGameState
  ├── ErrorHandler → retries, DQ logic
  └── TurnRecorder → GameRecording
  ↓ list[GameRecording]
MetricsEngine (benchmark/metrics/) → 31 Tier-1 metrics
  ↓ dict[str, MetricResult]
DimensionScorer (benchmark/dimensions/) → 8 Tier-2 dimensions
  ↓ DimensionReport
BenchmarkResult → export (JSON/HTML/CSV/Markdown)
```

### Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | LLM Agent Interface (adapters, schemas, prompt, parser, tokens) | **COMPLETE** |
| 2 | Built-in Opponents (random, greedy, balanced, rush, turtle, adversarial) | **COMPLETE** |
| 3 | Orchestrator v2 + BenchmarkRunner + StateConverter + ErrorHandler + Recorder + SpeedController | **COMPLETE** |
| 3.5 | P2P Trading engine extension | **COMPLETE** |
| 4C | Tier-1 Metric Collectors (31 metrics across 6 categories) | **COMPLETE** (65 tests) |
| 4D | Tier-2 Dimension Scorers (8 dimensions + composite + trend + archetypes) | **COMPLETE** (64 tests) |
| 5 | Results aggregation + MetricsEngine/DimensionScorer pipeline wiring + HTML report | **COMPLETE** (pipeline + HTML + JSON + CSV + Markdown + statistical analysis) |
| 6 | CLI & TUI Integration | **COMPLETE** (TUI wired, real scores, `--benchmark` CLI headless + `--benchmark` → TUI setup, export buttons) |
| 7 | Testing & Verification — full integration, headless end-to-end | **COMPLETE** (17 integration tests; 594 total passing) |

### What's left

The LLM benchmark feature is complete. Optional quality-of-life items only:
- Keyring-based API key storage (env vars + `run_benchmark.py` currently used)
- Jinja2 + Chart.js HTML with interactive radar charts (current HTML is string-template based)
- `scipy` for statistical significance tests (bootstrap CIs work without it)

### Known LLM behaviour notes

- **Windows `set VAR=val && python` doesn't propagate env vars** — use `run_benchmark.py` which sets the key inside Python before running
- **Models choosing PASS every turn** usually means `401 Unauthorized` — the API key isn't reaching the adapter. Run with `--verbose` to confirm.
- **Thinking/reasoning models** (Nemotron, o1, etc.) need `extra_body` in `ModelConfig` and `timeout_seconds` ≥ 120. Set `reasoning_budget` low (512) to keep latency under 2 min/turn.
- **`speed_multiplier`** should be 1 for slow models (reasoning models) — high multipliers compress catastrophe timing so much the game ends before the model finishes thinking.

---

## Key Files

| File | Purpose |
|------|---------|
| `terminus/server/engine.py` | All game logic. Every action, tick, catastrophe, scoring rule. |
| `terminus/server/models.py` | Pydantic models for game state. `ActionType` enum here. |
| `terminus/benchmark/schemas.py` | Benchmark-specific Pydantic models (`BenchmarkConfig`, `GameRecording`, `BenchmarkGameState`, etc.) |
| `terminus/benchmark/orchestrator_v2.py` | New single-game runner — uses adapters, opponents, recorder |
| `terminus/benchmark/runner.py` | Multi-game coordinator — iterates model × opponent × repetition |
| `terminus/benchmark/agent.py` | Abstract `LLMAdapter` ABC + `Message` + `LLMError` + `create_adapter()` |
| `terminus/benchmark/adapters/` | Provider-specific adapters: `anthropic.py`, `openai_compat.py`, `google.py` |
| `terminus/benchmark/opponents/` | Built-in agents: `random_agent.py`, `greedy_agent.py`, `balanced_agent.py`, `rush_agent.py`, `turtle_agent.py`, `adversarial_agent.py` |
| `terminus/benchmark/metrics/` | Tier-1 metric collectors (31 metrics across planning, numerical, flexibility, context_pressure, opponent_aware, state_probes) |
| `terminus/benchmark/dimensions/` | Tier-2 dimension scorers (8 dimensions + composite + trend + archetypes) |
| `terminus/benchmark/results.py` | `BenchmarkResult` aggregator — runs MetricsEngine + DimensionScorer, builds rankings + summary |
| `terminus/benchmark/report.py` | HTML report generator — receives real dimension scores from `results.py` |
| `terminus/client/screens/benchmark_setup.py` | TUI setup screen — `build_benchmark_config()` translates UI state → `BenchmarkConfig` |
| `terminus/client/screens/benchmark_live.py` | TUI live monitoring screen — wired to `BenchmarkRunner` |
| `terminus/client/screens/benchmark_results.py` | TUI results screen |
| `docs/llm-benchmark/implementation-plan.md` | Authoritative phase-by-phase implementation plan |

---

## Testing Conventions

- Framework: `pytest` with `pytest-asyncio` (mode=auto, configured in `pyproject.toml`)
- All async tests use `@pytest.mark.asyncio` or rely on auto mode
- No live API calls in tests — adapters are mocked via `unittest.mock` or scripted responses
- Test files live flat in `tests/`, named `test_<module>.py`
- Run `pytest -x` to stop at first failure, `pytest -m "not slow"` to skip long tests
- **When adding benchmark features, add tests.** The test count per phase is tracked in the implementation plan.

---

## Game Engine Notes

- `GameEngine` in `server/engine.py` can run **headless** (no WebSocket, no persistence):
  ```python
  engine = GameEngine(settings=settings)
  engine._persist = None
  engine.set_broadcast(noop_fn)
  ```
- Manual tick advancement: `await engine._tick()` — no real-time timer
- Action dispatch: `await engine.handle_action(player_id, ActionType.BUILD, {"building_type": "farm"})`
- Catastrophe resolution: `await engine._end_catastrophe()` (skips the real-time countdown)
- Score calculation: `engine._calculate_scores()` → list of `{"player_id": ..., "score": ...}`

---

## LLM Adapter Notes

- All adapters implement `LLMAdapter` ABC from `benchmark/agent.py`
- `create_adapter(model_config: ModelConfig) -> LLMAdapter` is the factory
- Provider routing: `ModelConfig.provider` in `{"openai", "anthropic", "google", "ollama"}`
- Anthropic adapter (`adapters/anthropic.py`): separates system prompt from messages (API format requirement)
- All adapters use `httpx.AsyncClient` with configurable timeout
- Token counting strategy: OpenAI=tiktoken exact, Anthropic=char÷4 estimate, Google=countTokens API
- `ModelConfig.extra_body` — dict merged verbatim into the API request payload (used for `reasoning_budget`, `enable_thinking` on Nemotron/o1 etc.)
- Streaming is triggered automatically when `extra_body` is non-empty (required for thinking models)

---

## Benchmark Configuration

`BenchmarkConfig` is the top-level Pydantic model. Key fields:

```python
models: list[ModelConfig]          # which LLMs to test
opponents: list[OpponentType]      # which built-in agents
games_per_matchup: int = 10        # repetitions per model×opponent pair
max_turns: int = 100
speed_multiplier: int = 1          # divides catastrophe intervals
base_seed: int = 42
seed_mode: str = "fixed"           # "fixed" or "random"
weight_preset: str = "balanced"    # one of 9 presets
```

The setup screen (`benchmark_setup.py`) translates UI state to `BenchmarkConfig` via `build_benchmark_config()`. The live screen passes both the typed config and the display dict to `BenchmarkRunner`. The runner runs the scoring pipeline on completion and writes the HTML report automatically.

---

## Benchmark Event System

`BenchmarkEvent` subclasses (all in `benchmark/events.py`) flow through an `asyncio.Queue`:

| Event | When |
|-------|------|
| `GameStarted` | Before each game |
| `TurnCompleted` | After each turn |
| `GameCompleted` | After each game |
| `CatastropheTriggered` | When a catastrophe fires |
| `ErrorOccurred` | On LLM errors |
| `BenchmarkCompleted` | When all games finish |

The live screen polls this queue every 100ms. `BenchmarkRunner` accepts an optional `event_queue` and emits all events.

---

## CSS / Styling

Textual CSS files live alongside their screens (Textual's default lookup pattern). The TUI uses Textual's built-in theme. No external CSS frameworks.

---

## Dependencies

Core: `textual`, `fastapi`, `uvicorn`, `httpx`, `websockets`, `pydantic`, `aiosqlite`, `tiktoken`
Dev: `pytest`, `pytest-asyncio`
Optional: `simpleaudio` (audio), `scipy` (statistical tests in Phase 5), `jinja2` (HTML templates in Phase 5)
