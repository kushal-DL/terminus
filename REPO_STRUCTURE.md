# Terminus — Repository Structure

> Last updated: 2026-06-06 | v0.3.0

This document describes every directory and significant file in the repository, what it does, and its status.

---

## Root

| File | Purpose |
|------|---------|
| `play.bat` | **Windows launcher** — double-click to create venv, install deps, start game |
| `play.sh` | **Mac/Linux launcher** — same as above for Unix |
| `run_benchmark.py` | Benchmark helper script — sets API key in-process (bypasses Windows env var issue) |
| `benchmark-config.example.json` | Example benchmark config — copy and edit to run your own LLM benchmark |
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `README.md` | User-facing documentation |
| `CLAUDE.md` | AI assistant context — project overview, conventions, architecture notes |
| `REPO_STRUCTURE.md` | This file |
| `LICENSE` | MIT licence |

---

## `terminus/` — Main Package

### `terminus/__main__.py`
CLI entry point. Handles `--host`, `--port`, `--public`, `--server-only`, `--verbose`, `--benchmark` flags. Routes to TUI, server-only, or headless benchmark mode.

### `terminus/config.py`
All tunable game constants — tick timing, resource rates, scoring weights, market spread, etc. Single source of truth for balance numbers.

---

### `terminus/server/` — Game Server

| File | Purpose |
|------|---------|
| `engine.py` | **Core game logic** — `GameEngine` class, all actions, ticks, catastrophes, scoring. Everything runs through here. |
| `models.py` | Pydantic models — `GameState`, `Player`, `Colony`, `ActionType` enum, all game data structures |
| `app.py` | FastAPI application — REST API + WebSocket handler |
| `persistence.py` | SQLite game state persistence via aiosqlite |

---

### `terminus/client/` — TUI Client

| File | Purpose |
|------|---------|
| `app.py` | `TerminusApp` — root Textual application, screen stack management, WS dispatcher |
| `api.py` | REST + WebSocket client wrapper used by all screens |
| `art.py` | All ASCII art constants (title, locations, specs, buildings, catastrophes) |
| `theme.tcss` | External Textual CSS — full retro terminal theme |

#### `terminus/client/screens/`

| Screen | Purpose |
|--------|---------|
| `main_menu.py` | Title screen with animated reveal, main navigation |
| `lobby.py` | Multiplayer lobby — player list, ready state, share URL |
| `setup.py` | Location + specialization selection |
| `colony.py` | Main colony screen — resources, buildings, workers, score |
| `build.py` | Building construction screen |
| `workers.py` | Worker allocation with sliders |
| `market.py` | Market trading — price sparklines, buy/sell, history |
| `catastrophe.py` | Catastrophe event — dramatic reveal, damage animation |
| `leaderboard.py` | Rankings with achievements and game stats |
| `help.py` | How to Play screen |
| `settings.py` | Audio and display settings |
| `connection_lost.py` | Disconnection modal with auto-retry |
| `dev_panel.py` | Host-only dev panel (F12) — admin controls |
| `benchmark_setup.py` | LLM benchmark configuration screen |
| `benchmark_live.py` | Live benchmark monitoring — leaderboard, game state, action log |
| `benchmark_results.py` | Post-benchmark results — dimension scores, export buttons |

#### `terminus/client/widgets/`

| Widget | Purpose |
|--------|---------|
| `resource_bar.py` | Horizontal fill bar for resources |
| `building_card.py` | Building card with art, level pips, health bar |
| `worker_slider.py` | Worker allocation control `[◄ 12 ►]` |
| `countdown_timer.py` | MM:SS timer with urgency colour states |
| `notification_toast.py` | Auto-dismissing toast notifications |
| `ascii_art_panel.py` | Reusable ASCII art container |
| `sparkline_chart.py` | Inline price/score sparkline |

---

### `terminus/data/` — Static Game Data

| File | Purpose |
|------|---------|
| `loader.py` | JSON loader with caching — `get_buildings()`, `get_catastrophes()`, etc. |
| `buildings.json` | 10 buildings with costs, build times, effects per level |
| `catastrophes.json` | 20 catastrophes with damage, vulnerability, mitigation data |
| `locations.json` | 5 locations with production modifiers |
| `specializations.json` | 4 specializations with bonuses |

---

### `terminus/audio/` — Sound Effects

| File | Purpose |
|------|---------|
| `synth.py` | Pure-Python WAV synthesis — square, sine, sawtooth, triangle, noise |
| `sounds.py` | 10 retro sound event definitions |
| `player.py` | Cross-platform playback (simpleaudio → winsound → aplay → silent) |

Optional dependency: `python -m pip install simpleaudio` for Mac/Linux. Windows uses `winsound` automatically.

---

### `terminus/dev/` — Developer Tools

| File | Purpose |
|------|---------|
| `console.py` | Dev console TUI — live state view, resource controls |
| `__main__.py` | Entry point: `python -m terminus.dev --server URL` |

Requires `TERMINUS_DEV_MODE=1` env var or host-only token. Accessed via F12 in the game (host only).

---

### `terminus/benchmark/` — LLM Benchmark System

The benchmark subsystem runs LLMs through headless games and scores them across 8 cognitive dimensions.

#### Pipeline (top-down)

```
BenchmarkConfig (schemas.py)
  ↓
BenchmarkRunner (runner.py)           — coordinates model × opponent × game schedule
  ↓
BenchmarkOrchestrator (orchestrator_v2.py) — runs one game headlessly
  ├── LLMAdapter (agent.py + adapters/)     — calls the LLM API
  ├── BuiltInAgent (opponents/)             — scripted opponent decisions
  ├── StateConverter (state_converter.py)   — engine state → BenchmarkGameState
  ├── ErrorHandler (error_handler.py)       — retries, DQ logic
  └── TurnRecorder (recorder.py)            — snapshots → GameRecording
  ↓
BenchmarkResult (results.py)          — runs MetricsEngine + DimensionScorer pipeline
  ├── MetricsEngine (metrics/)         — 31 Tier-1 metrics
  └── DimensionScorer (dimensions/)    — 8 Tier-2 dimension scores
  ↓
Exports (export/)                     — HTML / JSON / CSV / Markdown / statistics
```

#### Core files

| File | Purpose |
|------|---------|
| `schemas.py` | All Pydantic models — `BenchmarkConfig`, `GameRecording`, `BenchmarkGameState`, etc. |
| `agent.py` | Abstract `LLMAdapter` ABC, `Message`, `LLMError`, `create_adapter()` factory |
| `orchestrator_v2.py` | Single-game headless runner — turn loop, catastrophe handling, event emission |
| `runner.py` | Multi-game coordinator — model × opponent × repetition schedule, pause/abort |
| `state_converter.py` | Converts `engine.get_player_state()` dict to typed `BenchmarkGameState` |
| `recorder.py` | `TurnRecorder` → `TurnSnapshot` per turn → `GameRecording` on finalize |
| `error_handler.py` | Retry logic, rate-limit backoff, DQ thresholds |
| `speed.py` | `SpeedController` — divides catastrophe intervals by multiplier |
| `prompt.py` | System prompt, turn messages, retry prompts, per-turn recommendations |
| `response_parser.py` | JSON extraction, schema coercion, action validation |
| `tokens.py` | Token counting — tiktoken (OpenAI), char÷4 (Anthropic), countTokens API (Google) |
| `events.py` | `BenchmarkEvent` subclasses — `TurnCompleted`, `GameCompleted`, etc. |
| `results.py` | `BenchmarkResult.from_recordings()` — full scoring pipeline entry point |
| `report.py` | HTML report generator — enterprise white theme, JS tooltips |
| `scorer.py` | Bridge: `DimensionScorer` (new) + `score_dimensions()` legacy API |
| `mock_orchestrator.py` | Fake benchmark runner for TUI demo mode (`TERMINUS_BENCHMARK_MOCK=1`) |

#### `terminus/benchmark/adapters/`

| File | Provider |
|------|---------|
| `openai_compat.py` | OpenAI, NVIDIA, Together, Groq, Ollama, vLLM — any OpenAI-compatible endpoint |
| `anthropic.py` | Anthropic Messages API (Claude) |
| `google.py` | Google Generative AI (Gemini) |

#### `terminus/benchmark/opponents/`

6 scripted opponents for consistent benchmarking:

| Agent | Strategy |
|-------|---------|
| `random_agent.py` | Uniform random — baseline floor |
| `greedy_agent.py` | Always picks highest immediate-value action |
| `balanced_agent.py` | Phase-based build order — "par" opponent |
| `rush_agent.py` | Aggressive early population growth |
| `turtle_agent.py` | Heavy defense, slow growth |
| `adversarial_agent.py` | Trust-build → pattern-detect → exploit |

#### `terminus/benchmark/metrics/` — Tier-1 Metrics (31 total)

| File | Metrics |
|------|---------|
| `planning.py` | 1.1–1.6 — build order, worker anticipation, market timing, catastrophe prep |
| `numerical.py` | 2.1–2.6 — valid action rate, worker sum, capacity errors, trade math |
| `flexibility.py` | 3.1–3.7 — catastrophe recovery, damage response, repair priority, strategy shift |
| `state_probes.py` | 4.1–4.4 — building recall, resource awareness, strategy consistency, history recall |
| `opponent_aware.py` | 5.1–5.5 — win rate, exploit resistance, counter-strategy, cooperation |
| `context_pressure.py` | 6.1–6.3 — quartile quality, history reference, context collapse point |
| `base.py` | `MetricCollector` ABC, `MetricResult` dataclass |
| `utils.py` | Shared helpers — rolling avg, Kendall tau, Jensen-Shannon divergence |

#### `terminus/benchmark/dimensions/` — Tier-2 Dimensions (8 total)

| File | Dimension |
|------|---------|
| `coherence.py` | Dim 1: Multi-Decision Coherence |
| `arithmetic.py` | Dim 2: Applied Arithmetic Under Load |
| `triage.py` | Dim 3: Priority Triage |
| `error_recognition.py` | Dim 4: Compounding Error Recognition |
| `pivot.py` | Dim 5: Justified Pivot vs Inconsistency |
| `degradation.py` | Dim 6: Graceful Degradation |
| `opportunity.py` | Dim 7: Opportunity Cost Awareness |
| `game_theory.py` | Dim 8: Game-Theoretic Sophistication |
| `composite.py` | Weighted composite + 9 weight presets + participation score |
| `trend.py` | Trend classification (Improving/Consistent/Degrading/Volatile) |
| `archetypes.py` | Cross-dimension archetype classification (8 archetypes) |
| `base.py` | `DimensionScore`, `DimensionReport`, `DimensionComputer` ABC |

#### `terminus/benchmark/export/`

| File | Output |
|------|--------|
| `json_export.py` | Full-fidelity JSON — all dimension scores, metrics, per-game data |
| `csv_export.py` | Summary (1 row/model) + detailed (1 row/game) CSV |
| `markdown_export.py` | GFM tables with archetype emoji and trend arrows |
| `statistics.py` | Bootstrap 95% CIs + Mann-Whitney U pairwise comparisons |

---

## `tests/` — Test Suite (594 tests)

| File | Tests |
|------|-------|
| `test_state_machine.py` | Game phase transitions |
| `test_buildings.py` | Building lifecycle |
| `test_market.py` | Market trading |
| `test_resources.py` | Resource production |
| `test_catastrophe.py` | Catastrophe damage |
| `test_catastrophe_selection.py` | Catastrophe selection algorithm |
| `test_scoring.py` | Score calculation |
| `test_integration.py` | Full game lifecycle |
| `test_engine_fixes.py` | Engine regression tests |
| `test_api_validation.py` | REST API validation |
| `test_multiplayer.py` | Concurrent clients |
| `test_reconnection.py` | Player reconnection |
| `test_persistence.py` | State persistence |
| `test_load.py` | 250-connection load test (`@slow`) |
| `test_balance_data.py` | Balance constraint validation |
| `test_p2p_trading.py` | P2P trade offers |
| `test_sprint7.py` | Sprint 7 regression tests |
| `test_sprint8.py` | Sprint 8 regression tests |
| `test_epic8_integration.py` | Epic 8 integration |
| `test_validation_fuzz.py` | Malformed payload fuzz tests |
| `test_audio.py` | Audio synthesis |
| `test_agent_interface.py` | LLM adapter + prompt builder |
| `test_benchmark.py` | Mock orchestrator, legacy scorer API |
| `test_opponents.py` | All 6 opponent agents |
| `test_orchestrator_v2.py` | Orchestrator components (StateConverter, ErrorHandler, Recorder) |
| `test_metrics_tier1.py` | 31 Tier-1 metric collectors (65 tests) |
| `test_dimensions_tier2.py` | 8 Tier-2 dimension scorers (64 tests) |
| `test_benchmark_integration.py` | End-to-end pipeline (17 tests) |

---

## `tools/` — Developer Utilities

| File | Purpose |
|------|---------|
| `build_exe.py` | PyInstaller build helper (legacy — exe approach retired) |
| `load_test.py` | Spawns N WebSocket clients for load/stress testing |
| `balance/simulator.py` | Headless batch simulator for game balance tuning |
| `balance/strategies.py` | Heuristic AI strategies used by balance simulator |
| `balance/constraints.py` | Balance constraint definitions |
| `balance/report.py` | Balance test report generation |

---

## `docs/` — Documentation

| Path | Contents |
|------|---------|
| `docs/llm-benchmark/` | Full benchmark spec — metrics, schemas, prompts, implementation plan |
| `docs/llm-benchmark/implementation-plan.md` | **Authoritative phase status** — what's built and what isn't |
| `docs/tapes/` | VHS tape files for recording demo GIFs (original set) |
| `docs/gifs/` | Output GIFs (empty — generate with `_workspace/record-gifs.ps1`) |

---

## `product-backlog/` — Product Backlog

| File | Contents |
|------|---------|
| `BACKLOG.md` | Master backlog — all epics, progress summary, dependency graph |
| `epic-01-foundation.md` through `epic-12-llm-benchmark.md` | Per-epic story breakdowns with status |

---

## `.github/workflows/`

| File | Trigger | Does |
|------|---------|------|
| `ci.yml` | Push/PR to `main` | Runs tests on Python 3.11/3.12/3.13 |
| `release.yml` | Push `v*` tag | Tests → build wheel → create GitHub release with `play.bat`, `play.sh`, wheel |
