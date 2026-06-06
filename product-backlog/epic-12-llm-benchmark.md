# Epic 12: LLM Benchmark Suite

> **Priority**: P1  
> **Status**: ✅ Complete — full end-to-end LLM benchmark pipeline; 594 tests passing  
> **Last Updated**: 2026-06-05  
> **Reference Docs**: `docs/llm-benchmark/` (metrics, schemas, prompts, implementation-plan)  
> **Test Count**: 594 tests passing

---

## Feature 12.1 — LLM Agent Interface

> **Status**: ✅ Complete  
> **Files**: `terminus/benchmark/schemas.py`, `terminus/benchmark/agent.py`, `terminus/benchmark/adapters/`, `terminus/benchmark/prompt.py`, `terminus/benchmark/response_parser.py`, `terminus/benchmark/tokens.py`

### Story 12.1.1 — `BenchmarkGameState` Pydantic schema

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/schemas.py` — `BenchmarkGameState` model with full state: resources, buildings, workers, market, catastrophe_warning, opponents, available_actions, incoming/outgoing trade offers.

**Acceptance Criteria**:
- [x] Resources, workers, buildings, market prices all present
- [x] Available actions pre-filtered to affordable only
- [x] P2P trade offers included
- [x] Catastrophe warning field with category/type/ticks_until

---

### Story 12.1.2 — `ActionResponse` Pydantic schema

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/schemas.py` — `ActionResponse` with `action: BenchmarkActionType`, `params: dict`, `reasoning: Reasoning | None`.

**Acceptance Criteria**:
- [x] All 11 action types covered (BUILD, UPGRADE, ALLOCATE_WORKERS, TRADE_BUY, TRADE_SELL, TRADE_OFFER, TRADE_ACCEPT, TRADE_DECLINE, DEMOLISH, REPAIR, PASS)
- [x] Reasoning factors with weight validation (sum ~1.0 ±0.05)

---

### Story 12.1.3 — `ReasoningFactors` schema

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/schemas.py` — `ReasoningFactorType` enum (12 factors), `ReasoningFactor` model, `Reasoning` model with weight-sum validator.

---

### Story 12.1.4 — Abstract `LLMAdapter` base class

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/agent.py` — abstract `LLMAdapter` ABC with `get_action()`, `test_connection()`, `get_token_count()`, `get_model_info()`. Includes `Message` dataclass, `LLMError` exception, `create_adapter()` factory.

---

### Story 12.1.5 — Provider adapters

**Status**: ✅ Done

**Implementation**:
- `terminus/benchmark/adapters/openai_compat.py` — OpenAI / Ollama / vLLM
- `terminus/benchmark/adapters/anthropic.py` — Anthropic Messages API (separates system prompt)
- `terminus/benchmark/adapters/google.py` — Google Generative AI (countTokens, native JSON mode)

---

### Story 12.1.6 — Connection test method

**Status**: ✅ Done

**Implementation**: `test_connection()` on each adapter; also implemented in the setup screen's `_test_connection()` for direct TUI use.

---

### Story 12.1.7 — Token counting

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/tokens.py` — tiktoken for OpenAI, char÷4 estimate for Anthropic/Ollama, countTokens API for Google.

---

## Feature 12.2 — Built-in Opponents

> **Status**: ✅ Complete  
> **Files**: `terminus/benchmark/opponents/`

### Story 12.2.1 — Random agent

**Status**: ✅ Done — `terminus/benchmark/opponents/random_agent.py`

---

### Story 12.2.2 — Greedy heuristic agent

**Status**: ✅ Done — `terminus/benchmark/opponents/greedy_agent.py`

---

### Story 12.2.3 — Balanced heuristic agent

**Status**: ✅ Done — `terminus/benchmark/opponents/balanced_agent.py`

**Notes**: Additionally implemented Rush (`rush_agent.py`), Turtle (`turtle_agent.py`), and Adversarial (`adversarial_agent.py`) beyond the original MVP scope.

---

## Feature 12.3 — Benchmark Orchestrator

> **Status**: ✅ Complete  
> **Files**: `terminus/benchmark/orchestrator_v2.py`, `terminus/benchmark/runner.py`, `terminus/benchmark/state_converter.py`, `terminus/benchmark/recorder.py`, `terminus/benchmark/error_handler.py`, `terminus/benchmark/speed.py`

### Story 12.3.1 — `BenchmarkConfig` Pydantic model

**Status**: ✅ Done — `terminus/benchmark/schemas.py`

**Implementation**: Full model with models list, game settings, opponent types, weight presets, export options, error handling thresholds.

---

### Story 12.3.2 — Speed multiplier module

**Status**: ✅ Done — `terminus/benchmark/speed.py`

**Implementation**: `SpeedController` — adjusts catastrophe schedule by dividing times by multiplier. Supports 1×, 2×, 5×, 10×.

---

### Story 12.3.3 — Headless game runner

**Status**: ✅ Done — `terminus/benchmark/orchestrator_v2.py`

**Implementation**: `BenchmarkOrchestrator` runs single games headless (no FastAPI/WS). Engine called directly via `engine._tick()`, `engine.handle_action()`, etc.

---

### Story 12.3.4 — Turn loop

**Status**: ✅ Done — `BenchmarkOrchestrator._run_turn_loop()`

**Implementation**: State → LLM → validate → apply → opponent → tick → catastrophe check. ErrorHandler manages retries and DQ.

---

### Story 12.3.5 — Game sequence manager

**Status**: ✅ Done — `terminus/benchmark/runner.py`

**Implementation**: `BenchmarkRunner` coordinates models × opponents × games_per_matchup. Supports pause/resume/abort/skip.

---

### Story 12.3.6 — Per-turn data recorder

**Status**: ✅ Done — `terminus/benchmark/recorder.py`

**Implementation**: `TurnRecorder` → `TurnSnapshot` per turn → `GameRecording` on finalize.

---

### Story 12.3.7 — Rate limit controller

**Status**: ✅ Done — `terminus/benchmark/error_handler.py`

**Implementation**: Exponential backoff on 429/rate_limit errors. Configurable via `BenchmarkConfig`.

---

### Story 12.3.8 — P2P Trading (was stretch — now complete)

**Status**: ✅ Done

**Implementation**: `TRADE_OFFER/ACCEPT/DECLINE` action types in `server/models.py` and `server/engine.py`. Integrated in orchestrator and all opponent archetypes. (Implemented as Phase 3.5.)

---

## Feature 12.4 — Metrics Engine

> **Status**: ✅ Complete (129 tests)  
> **Files**: `terminus/benchmark/metrics/`, `terminus/benchmark/dimensions/`, `terminus/benchmark/scorer.py`

### Story 12.4.1 — Abstract `MetricCollector` base class

**Status**: ✅ Done — `terminus/benchmark/metrics/base.py`

---

### Story 12.4.2 — Tier 1 Planning metrics (6)

**Status**: ✅ Done — `terminus/benchmark/metrics/planning.py`

Metrics: build order efficiency, worker allocation anticipation, market timing, catastrophe preparation, housing-before-growth, resource stockpile timing.

---

### Story 12.4.3 — Tier 1 Numerical metrics (6)

**Status**: ✅ Done — `terminus/benchmark/metrics/numerical.py`

Metrics: invalid action rate, worker sum accuracy, over-capacity errors, production rate awareness, trade math accuracy, multi-resource feasibility.

---

### Story 12.4.4 — Tier 1 Flexibility metrics (7)

**Status**: ✅ Done — `terminus/benchmark/metrics/flexibility.py`

Metrics: post-catastrophe recovery speed, worker reallocation after damage, repair prioritization (Kendall Tau), market adaptation after price shock, starvation response speed, defense investment after first hit, action distribution shift (Jensen-Shannon divergence).

---

### Story 12.4.5–12.4.11 — Tier 2 Dimensions 1–7

**Status**: ✅ Done — `terminus/benchmark/dimensions/`

| Dimension | File | Status |
|-----------|------|--------|
| 1. Multi-Decision Coherence | `coherence.py` | ✅ |
| 2. Applied Arithmetic Under Load | `arithmetic.py` | ✅ |
| 3. Priority Triage | `triage.py` | ✅ |
| 4. Compounding Error Recognition | `error_recognition.py` | ✅ |
| 5. Justified Pivot vs Inconsistency | `pivot.py` | ✅ |
| 6. Graceful Degradation | `degradation.py` | ✅ |
| 7. Opportunity Cost Awareness | `opportunity.py` | ✅ |
| 8. Game-Theoretic Sophistication | `game_theory.py` | ✅ (bonus: beyond original scope) |

**Notes**: Dimension 8 (Game Theory) implemented beyond the original MVP scope. Required completion of Phase 3.5 (P2P Trading) and all 6 opponent archetypes.

---

### Story 12.4.12 — Composite scorer

**Status**: ✅ Done — updated 2026-06-06 with scoring fairness improvements

**Implementation**: `terminus/benchmark/dimensions/composite.py`

- 9 weight presets (balanced, reliability, strategy, triage, endurance, precision, adversarial, coordination, context)
- **Option B (2026-06-06):** `compute_participation_score()` — model avg score ÷ best score in run, weighted at 1.5× in composite. Prevents passive models from hiding behind high cognitive scores.
- **Option C (2026-06-06):** Monotony penalty in `opportunity.py` — non-linear PASS penalty + dominant-action penalty when any single action > 60% of turns. Catches all-PASS and BUILD-fixation failure modes.
- `reference_score` computed in `BenchmarkResult.from_recordings()` and passed to scorer

---

### Story 12.4.13 — Trend analysis

**Status**: ✅ Done — `terminus/benchmark/dimensions/trend.py`

**Implementation**: Linear regression slope, classifies as IMPROVING/CONSISTENT/DEGRADING/VOLATILE per dimension and overall.

---

### Story 12.4.14 — LLM archetype classification

**Status**: ✅ Done — `terminus/benchmark/dimensions/archetypes.py`

**Implementation**: 8 archetypes: Predator, Fortress, Diplomat, Chameleon, Scholar, Pragmatist, Cautious, Oblivious. Threshold-based rule classification from dimension scores.

---

## Feature 12.5 — Results & HTML Export

> **Status**: 🚧 Partial — pipeline and HTML done; CSV/Markdown/stats not started  
> **Files**: `terminus/benchmark/results.py` (new), `terminus/benchmark/runner.py` (updated), `terminus/benchmark/report.py` (unchanged — contract matched)

### Story 12.5.1 — Results aggregation module

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/results.py` — `BenchmarkResult.from_recordings()` groups recordings by model, runs `MetricsEngine.compute_all()` + `DimensionScorer.score()` per model, produces `ModelResult` (game stats + metrics + dimension_report), ranked `rankings` list with composite_score/archetype/trend, and `summary` dict for legacy consumers.

---

### Story 12.5.2–12.5.5 — HTML/JSON/CSV/Markdown export

**Status**: 🔨 Partial

**HTML**: `terminus/benchmark/report.py` now receives real dimension scores via `summary["dimensions"]`. No code change was needed — the summary contract already matched. Report includes dimension bar chart, per-model sparklines, rankings with valid rate.

**JSON/CSV/Markdown**: ⬜ TODO — `terminus/benchmark/export/` directory not yet created.

---

### Story 12.5.6 — Statistical analysis

**Status**: ⬜ TODO

---

### Story 12.5.7 — Wire runner to produce BenchmarkResult

**Status**: ✅ Done

**Implementation**: `terminus/benchmark/runner.py` — `_emit_completed()` calls `BenchmarkResult.from_recordings()`, then `write_report()`, then emits `BenchmarkCompleted` with `results=bench_result.summary` and `report_path`. Falls back to `_aggregate_results_fallback()` on any error so the TUI always gets something.

---

## Feature 12.6 — CLI & TUI Integration

> **Status**: 🚧 Phase A complete (runner wired in). CLI headless mode not started.  
> **Files modified**: `terminus/client/screens/benchmark_setup.py`, `terminus/client/screens/benchmark_live.py`

### Story 12.6.1 — `--benchmark` CLI flag

**Status**: ✅ Done

**Implementation**: `terminus/__main__.py` — `--benchmark CONFIG` argument. `_run_benchmark_headless()` validates the JSON config, prints a run banner, then calls `_benchmark_async()` which runs `BenchmarkRunner` and an async event consumer concurrently. Progress: turn updates overwrite the current line via `\r`; game completions print a full summary line; catastrophes annotated inline; final summary prints report path with a one-liner to open it in a browser.

**Example**: `python -m terminus --benchmark benchmark-config.example.json`

**Example config**: `benchmark-config.example.json` at repo root.

---

### Story 12.6.2 — `--benchmark-config PATH`

**Status**: ⬜ TODO — subsumed by 12.6.1 for now; `--benchmark` already takes a config path.

---

### Story 12.6.3 — TUI setup screen

**Status**: ✅ Done — `terminus/client/screens/benchmark_setup.py`

**Implementation**: Full setup screen with model management (add/test/remove), game parameters, opponent depth, weight presets, time estimates. `build_benchmark_config()` translates TUI state → `BenchmarkConfig`.

---

### Story 12.6.4 — Live progress screen

**Status**: ✅ Done — `terminus/client/screens/benchmark_live.py`

**Implementation (Phase B update)**: Now passes `display_config` to `BenchmarkRunner`; passes `report_path` from `BenchmarkCompleted` event to results screen.

---

### Story 12.6.5 — Results dashboard screen

**Status**: ✅ Done — `terminus/client/screens/benchmark_results.py`

**Implementation (Phase B)**: `__init__` accepts `report_path`; `_compute_dimensions` reads real `results["dimensions"]` (real Tier-1→Tier-2 scores); rankings table shows Composite + Archetype + Trend columns; dimension breakdown renders bar chart + composite per model.

---

## Feature 12.7 — Testing & Verification

> **Status**: ✅ Complete — 17 integration tests (594 total passing)  
> **File**: `tests/test_benchmark_integration.py`

### Story 12.7.1 — Schema validation tests

**Status**: ✅ Done — covered in `tests/test_agent_interface.py`

---

### Story 12.7.2 — Metric scorer tests

**Status**: ✅ Done — `tests/test_metrics_tier1.py` (65 tests), `tests/test_dimensions_tier2.py` (64 tests)

---

### Story 12.7.3 — Orchestrator tests

**Status**: ✅ Done — `tests/test_orchestrator_v2.py`, `tests/test_opponents.py`

---

### Story 12.7.4 — HTML export tests

**Status**: ✅ Done — `TestHtmlReportGeneration` (5 tests): report written to disk, model name present, dimension table present, `report_path` in `BenchmarkCompleted` event, `write_report()` standalone.

---

### Story 12.7.5 — End-to-end integration test

**Status**: ✅ Done — `TestEndToEndPipeline` (5 tests): single game → recording → MetricsEngine → DimensionScorer → `BenchmarkResult` → HTML. `TestCLIHeadless` (4 tests): CLI error paths + example config validation.

---

### Story 12.7.6 — Agent sanity check

**Status**: ✅ Done — `TestAgentSanityCheck` (3 tests): all 6 opponent archetypes produce valid recordings; BUILD actions are recorded in the TurnSnapshot; no negative scores.

**Note**: Also fixed a critical runner bug found during testing — duplicate old `run()` method (lines 313–382) was shadowing the new pipeline-wired version, causing `report_path` to always be `None` and the scoring pipeline to never run.
