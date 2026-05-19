# LLM Benchmark — Implementation Plan

This document outlines the technical implementation phases, aligned with the 8-dimension metric framework and the product backlog (Epic 12). **No code changes until approved.**

---

## Phase Overview

| Phase | Epic 12 Section | Files | Complexity | MVP? |
|-------|-----------------|-------|------------|------|
| 1. Agent Interface | 12.1 | ~7 | Medium | ✓ |
| 2. Built-in Opponents | 12.2 | ~7 | Low | Partial |
| 3. Orchestrator | 12.3 | ~6 | High | ✓ |
| 3.5. P2P Trading | 12.3 / 12.4 | ~3 | Medium | ✓ |
| 4. Metrics Engine | 12.4 | ~12 | High | Partial |
| 5. Results & Export | 12.5 | ~6 | Medium | Partial |
| 6. CLI & TUI Integration | 12.6 | ~6 | Medium | Partial |
| 7. Testing & Verification | 12.7 | ~8 | Medium | ✓ |
| **Total** | — | **~55** | — | — |

---

## Phase 1: LLM Agent Interface

**Goal:** Define the communication contract between the orchestrator and LLM models.

**Reference docs:** [schemas.md](schemas.md), [prompt-template.md](prompt-template.md), [error-handling.md](error-handling.md)

**Status:** NOT STARTED

**Existing code to refactor:** `terminus/benchmark/orchestrator.py` already has a basic `LLMAdapter` class with `_build_prompt()`, `_call_api()`, and `_parse_response()`. Phase 1 replaces this with a proper multi-provider architecture using the schemas defined in [schemas.md](schemas.md).

---

### Sub-tasks (implementation order):

#### 1.1 — Schemas (`terminus/benchmark/schemas.py`)

Create all Pydantic v2 models from [schemas.md](schemas.md):

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `ModelConfig` | Per-model API configuration | provider, endpoint, model, api_key_env, context_window, rate_limit_rpm, timeout_seconds |
| `BenchmarkConfig` | Top-level run configuration | models[], games_per_matchup, max_turns, speed_multiplier, opponents[], weight_preset |
| `ResourceState` | Current resource levels | food, materials, knowledge, gold |
| `WorkerAllocation` | Worker distribution | farming, mining, research, construction, defense, medicine |
| `BuildingState` | Single building state | type, level, health, under_construction, ticks_remaining |
| `MarketPrices` | Market prices | food, materials, knowledge |
| `OpponentInfo` | Visible opponent data | name, score, population, building_count |
| `CatastropheWarning` | Active warning | category, type, ticks_until, estimated_severity |
| `TradeOfferInfo` | P2P trade offer visible to LLM | offer_id, from_player, offer_resources, request_resources, ticks_remaining |
| `AvailableAction` | Filtered action option | action_type, description, cost, params_hint |
| `BenchmarkGameState` | Complete state sent to LLM each turn | turn, score, resources, workers, buildings, market, opponents, available_actions, incoming_trades |
| `ReasoningFactor` | Single reasoning factor | factor (enum), weight (0-1) |
| `Reasoning` | Structured reasoning | factors[] (sum to ~1.0) |
| `ActionResponse` | LLM's complete response | action (ActionType), params (union), reasoning |
| `TurnSnapshot` | Per-turn recording | state, response, validity, latency_ms, tokens_used, retry_count |
| `GameRecording` | Full game record | turns[], final_score, opponent, duration, dq_reason |

**Validation rules:**
- `ReasoningFactor.weight` values must sum to ~1.0 (±0.05 tolerance)
- `WorkerAllocation` fields must all be ≥ 0
- `ModelConfig` must have either `api_key` or `api_key_env` (unless provider="ollama")
- `BenchmarkConfig.custom_weights` only used when `weight_preset="custom"`

**Design decisions:**
- Use Pydantic v2 `model_validator` for cross-field validation
- ActionResponse.params uses discriminated union via action type
- All enums use string values for JSON serialization clarity
- TradeOfferInfo added (new vs. original schema spec) to expose P2P trading to LLMs

---

#### 1.2 — Abstract LLM Adapter (`terminus/benchmark/agent.py`)

Replace the existing basic `LLMAdapter` class with a proper abstract interface:

```python
class LLMAdapter(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def get_action(
        self,
        state: BenchmarkGameState,
        history: list[Message],
        available_actions: list[AvailableAction],
    ) -> ActionResponse: ...

    @abstractmethod
    async def test_connection(self) -> bool: ...

    @abstractmethod
    def get_token_count(self, messages: list[Message]) -> int: ...

    @abstractmethod
    def get_model_info(self) -> dict[str, Any]: ...
```

**Additional classes in this file:**
- `Message` — dataclass with `role: Literal["system", "user", "assistant"]` and `content: str`
- `LLMError` — exception with `error_type` (timeout/rate_limit/api_error/parse_error) and `details`
- `AdapterFactory` — factory function: `create_adapter(config: ModelConfig) -> LLMAdapter`

**Design decisions:**
- History is passed as `list[Message]` — adapter is stateless (orchestrator manages conversation)
- `get_action` handles prompt construction internally (each adapter formats for its API)
- All adapters use `httpx.AsyncClient` with configurable timeout
- Rate limiting is NOT in the adapter — it's in the orchestrator's scheduling layer

---

#### 1.3 — OpenAI-Compatible Adapter (`terminus/benchmark/adapters/openai_compat.py`)

Covers: GPT-4o, GPT-4o-mini, o1, o3, any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, Together, Groq).

**API contract:**
- Endpoint: `{base_url}/chat/completions`
- Auth: `Authorization: Bearer {api_key}`
- Request: `{"model": ..., "messages": [...], "temperature": 0.3, "max_tokens": 500, "response_format": {"type": "json_object"}}`
- Response: `data["choices"][0]["message"]["content"]`

**Implementation details:**
- Use `response_format: {"type": "json_object"}` when available (GPT-4o, GPT-4o-mini)
- Fall back to prompt-only JSON for models that don't support it (Ollama, older endpoints)
- Token counting via `tiktoken` library (model-specific encoding: `cl100k_base` for GPT-4, `o200k_base` for GPT-4o)
- For Ollama/local: skip auth header, use `http://localhost:11434/v1/chat/completions` default
- Streaming not needed — we need the full response for parsing

**Error handling:**
- 429 → raise `LLMError("rate_limit", retry_after=headers["Retry-After"])`
- 5xx → raise `LLMError("api_error", status_code=...)`
- Timeout → raise `LLMError("timeout")`
- Connection refused → raise `LLMError("connection_error")`

---

#### 1.4 — Anthropic Adapter (`terminus/benchmark/adapters/anthropic.py`)

Covers: Claude Opus, Sonnet, Haiku via native Messages API.

**API contract:**
- Endpoint: `https://api.anthropic.com/v1/messages`
- Auth: `x-api-key: {api_key}`, `anthropic-version: 2023-06-01`
- Request: `{"model": ..., "system": ..., "messages": [...], "max_tokens": 500, "temperature": 0.3}`
- Response: `data["content"][0]["text"]`

**Key differences from OpenAI:**
- System prompt is a top-level field, not a message
- No native JSON mode — rely on prompt engineering + extraction
- Token counting: character-based estimation (÷4 for English text) — Anthropic doesn't expose tokenizer
- Context window: 200K tokens for Claude 3.5+, 100K for Claude 3

**Implementation details:**
- Separate system prompt from conversation messages (Anthropic API format)
- Handle `overloaded` error (529) with backoff similar to 429
- Handle `content_filter` stops — map to `LLMError("refusal")`

---

#### 1.5 — Google Generative AI Adapter (`terminus/benchmark/adapters/google.py`)

Covers: Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 2.0.

**API contract:**
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Auth: `?key={api_key}` query parameter
- Request: `{"contents": [...], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 500, "responseMimeType": "application/json"}}`
- Response: `data["candidates"][0]["content"]["parts"][0]["text"]`

**Key differences:**
- Auth via query param, not header
- System instruction is a separate field: `"systemInstruction": {"parts": [{"text": ...}]}`
- Native JSON mode via `responseMimeType: "application/json"` (Gemini 1.5+)
- Token counting via `countTokens` API endpoint (free, accurate)
- Conversation format: alternating `user`/`model` roles (not `assistant`)

**Implementation details:**
- Use `countTokens` endpoint for accurate pre-flight token budget checks
- Handle `SAFETY` block reasons → map to `LLMError("refusal")`
- Handle `RECITATION` block → retry with slightly rephrased prompt

---

#### 1.6 — Prompt Builder (`terminus/benchmark/prompt.py`)

Builds the system prompt, turn messages, retry prompts, and state probe prompts.

**Components:**
- `build_system_prompt() -> str` — ~1200 token game rules (from [prompt-template.md](prompt-template.md))
- `build_turn_message(state: BenchmarkGameState) -> str` — serialize state + available actions
- `build_retry_prompt(error: str, attempt: int) -> str` — "Your response was invalid because X. Try again."
- `build_probe_prompt(probe_type: str, state: BenchmarkGameState) -> str` — off-clock state probes

**Design decisions:**
- System prompt is static text (loaded once, included in every call)
- Turn message serializes `BenchmarkGameState` to human-readable format (not raw JSON — LLMs perform better on structured text)
- Include P2P trade offers in turn message: "Incoming trade offers: [Player X offers 20 food for 10 gold (expires in 5 turns)]"
- Available actions are pre-filtered to affordable ones only (reduces LLM decision space)
- History window: last N turns summarized as "Turn X: You chose BUILD farm. Result: success."

**Token budget management:**
- `estimate_tokens(text: str, model: str) -> int` — quick estimation without full tokenization
- `truncate_history(messages: list[Message], max_tokens: int) -> list[Message]` — drop oldest messages first, keep system + current state intact
- For `context_strategy="sliding"`: always keep system prompt + last 10 turns
- For `context_strategy="full"`: keep everything until 90% of context window

---

#### 1.7 — JSON Extraction & Schema Coercion (`terminus/benchmark/response_parser.py`)

Handles E1 (malformed JSON) and E2 (schema violation) from [error-handling.md](error-handling.md).

**JSON extraction pipeline:**
```
Raw LLM text
  → Strip markdown fences (```json ... ```)
  → Strip natural language prefix/suffix (find first { and last })
  → Fix trailing commas
  → Fix single quotes → double quotes
  → json.loads()
  → Pydantic ActionResponse.model_validate()
```

**Schema coercion (soft fixes before retry):**
- `action_type` case normalization: `"build"` → `"BUILD"`
- Missing `reasoning` field → inject default `{"factors": [{"factor": "immediate_survival", "weight": 1.0}]}`
- `params` as flat dict → wrap in correct typed model based on `action_type`
- Worker allocation doesn't sum to population → proportionally scale

**When coercion fails:**
- Return `None` → orchestrator sends retry prompt with specific error
- After max retries → fallback to PASS action, record as invalid turn

**Functions:**
- `extract_json(raw_text: str) -> dict | None`
- `coerce_response(raw_dict: dict, state: BenchmarkGameState) -> ActionResponse | None`
- `validate_action_params(action: ActionResponse, state: BenchmarkGameState) -> list[str]` — returns list of validation errors

---

#### 1.8 — Token Counting (`terminus/benchmark/tokens.py`)

**Per-provider strategy:**

| Provider | Method | Library |
|----------|--------|---------|
| OpenAI | Exact tokenization | `tiktoken` (cl100k_base / o200k_base) |
| Anthropic | Character estimation (÷4) | None (no public tokenizer) |
| Google | `countTokens` API call | `httpx` (API call) |
| Ollama/local | Character estimation (÷4) | None |

**Functions:**
- `count_tokens(text: str, provider: str, model: str) -> int`
- `count_messages_tokens(messages: list[Message], provider: str, model: str) -> int`
- `get_encoding_for_model(model: str) -> str` — returns tiktoken encoding name

**Design decisions:**
- `tiktoken` is the only new dependency (lightweight, no native bindings needed)
- Google's `countTokens` is async — called sparingly (cached for repeated system prompt)
- Character estimation is a fallback, not primary — used only for providers without tokenizers
- Token counts are recorded in `TurnSnapshot` for cost analysis in reports

---

### File Structure (final):

```
terminus/benchmark/
├── __init__.py              # (existing — add re-exports)
├── schemas.py               # NEW: All Pydantic models (BenchmarkConfig, BenchmarkGameState, ActionResponse, etc.)
├── agent.py                 # NEW: Abstract LLMAdapter ABC, Message, LLMError, AdapterFactory
├── adapters/
│   ├── __init__.py          # NEW: Re-exports + adapter registry
│   ├── openai_compat.py     # NEW: OpenAI/Ollama/vLLM/LM Studio adapter
│   ├── anthropic.py         # NEW: Native Anthropic Messages API adapter
│   └── google.py            # NEW: Google Generative AI adapter
├── prompt.py                # NEW: System prompt builder, turn messages, retry prompts
├── response_parser.py       # NEW: JSON extraction, schema coercion, validation
├── tokens.py                # NEW: Token counting per provider
├── orchestrator.py          # (existing — will be refactored in Phase 3 to use new adapters)
├── mock_orchestrator.py     # (existing — unchanged)
├── scorer.py                # (existing — unchanged)
├── report.py                # (existing — unchanged)
└── events.py                # (existing — unchanged)
```

### Dependencies:

```toml
# Add to pyproject.toml [project.dependencies]
tiktoken >= 0.7.0    # OpenAI token counting (pure Python wheels available)
```

No other new dependencies — `httpx` and `pydantic` already in project.

### Integration Points:

1. **Existing orchestrator** (`orchestrator.py`): Currently has inline `LLMAdapter`. Phase 1 creates the proper interface; Phase 3 refactors the orchestrator to use it.
2. **TUI benchmark setup** (`benchmark_setup.py`): Already collects provider/model/URL/key. Will pass to `AdapterFactory.create_adapter()`.
3. **Config loading**: `BenchmarkConfig` model enables loading from JSON file via `--benchmark-config` CLI flag (Phase 6).

### Testing Strategy:

- **Unit tests** (`tests/test_benchmark_schemas.py`): Validate all Pydantic models serialize/deserialize correctly, validation rules trigger on bad input
- **Unit tests** (`tests/test_response_parser.py`): Test JSON extraction edge cases (markdown fences, trailing commas, natural language wrapping, truncated JSON)
- **Unit tests** (`tests/test_prompt_builder.py`): Verify prompt output structure, token budget enforcement, history truncation
- **Integration tests** (`tests/test_adapters.py`): Mock httpx responses for each provider, verify correct API formatting
- **No live API calls in CI** — all adapter tests use `httpx` mock/respx fixtures

### Estimated Test Count: ~35-45 new tests

### Acceptance Criteria:

- [ ] `BenchmarkConfig` validates example JSON from schemas.md without error
- [ ] `ActionResponse` correctly parses all example responses from schemas.md
- [ ] Each adapter formats requests correctly for its provider's API spec
- [ ] JSON extraction handles all E1 cases from error-handling.md
- [ ] Schema coercion handles all E2 cases from error-handling.md
- [ ] Token counting returns accurate counts (within 5%) for OpenAI models
- [ ] `test_connection()` works for each adapter (mocked)
- [ ] System prompt fits within 1500 tokens across all models
- [ ] Full test suite passes (existing 233 + new ~40 = ~273 tests)

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

## Phase 3.5: Player-to-Player Trading (Engine Extension)

**Goal:** Enable direct resource trading between players (LLM ↔ opponents) so Game Theory metrics (§5.4 Cooperative Surplus, §5.5 Market Manipulation Detection) and adversarial exploitation scenarios can be measured.

**Why this is a prerequisite for Phase 4:**
- Metric 5.4 (Cooperative Surplus Capture) requires observing whether the LLM proposes/accepts mutually beneficial trades
- Metric 5.5 (Market Manipulation Detection) requires opponents able to propose manipulative trades
- The Adversarial agent (Phase 2) needs trade-based exploitation as an attack vector
- Dimension 8 (Game-Theoretic Sophistication) composite score relies on 5.4 and 5.5 having data

**Reference:** Currently only market trading exists (buy/sell to centralized market with global prices and finite stock). P2P trading was deferred post-V1 (Epic 10.2) but is now required for benchmark completeness.

### Tasks:
1. Add new `ActionType` values: `TRADE_OFFER`, `TRADE_ACCEPT`, `TRADE_DECLINE`
2. Create `TradeOffer` model:
   - Fields: `offer_id`, `from_player_id`, `to_player_id`, `offer_resources: dict[str, float]`, `request_resources: dict[str, float]`, `tick_created`, `expires_tick`
   - Validation: at least one side non-empty, quantities > 0, player has offered resources at creation time
3. Add `pending_trades: dict[str, TradeOffer]` to game engine state
4. Implement `_action_trade_offer()`:
   - Validate proposer has the offered resources
   - Create offer with 30-tick expiry (configurable via `TRADE_OFFER_EXPIRY_TICKS`)
   - Max 3 concurrent outgoing offers per player
   - Emit `trade_offered` event to target player
5. Implement `_action_trade_accept()`:
   - **Atomic resource swap**: validate BOTH sides have resources at acceptance time
   - Transfer resources simultaneously (prevents exploit on disconnect)
   - Remove offer from pending, emit `trade_accepted` to both players
   - Record in trade history with both sides' details
6. Implement `_action_trade_decline()`:
   - Remove offer, emit `trade_declined` to proposer
7. Add trade expiry cleanup in `_tick()`:
   - Remove expired offers, emit `trade_expired` to proposer
8. Expose trades in `get_player_state()`:
   - Add `incoming_trade_offers: list[TradeOffer]` (offers received from others)
   - Add `outgoing_trade_offers: list[TradeOffer]` (offers sent by this player)
9. Add trade actions to benchmark `available_actions`:
   - `TRADE_OFFER` available when opponents exist and < 3 pending outgoing offers
   - `TRADE_ACCEPT` / `TRADE_DECLINE` available when incoming offers exist
10. Wire into benchmark orchestrator:
    - Opponent agents can propose/respond to trades (scripted behavior per archetype)
    - LLM sees incoming offers in game state prompt
    - LLM can return `TRADE_OFFER` / `TRADE_ACCEPT` / `TRADE_DECLINE` actions

### Opponent Trade Behaviors (for benchmark scenarios):

| Archetype | Trade Strategy |
|-----------|----------------|
| Random | Proposes random trades; accepts randomly |
| Greedy | Demands more than offered; accepts only if clearly favorable |
| Balanced | Proposes fair trades based on mutual surplus; accepts if NPV positive |
| Rush | Offers excess food/materials for knowledge/gold early; declines late-game |
| Turtle | Rarely proposes; accepts only defensive resources (materials, food) |
| Adversarial | Rounds 1–3: proposes fair trades (trust building). Rounds 4+: exploitative offers, pump-and-dump coordination |

### Game Theory Scenarios Enabled:

| Scenario | Mechanism | What It Tests |
|----------|-----------|---------------|
| **Prisoner's Dilemma** | Both players have surplus of different resources; trade benefits both but non-trading is "safe" | Cooperative rationality (5.4) |
| **Trust Building → Betrayal** | Adversarial cooperates early, then defects with unfair demands | Exploitation resistance (5.2), pattern detection (5.3) |
| **Market Manipulation** | Opponent proposes buying LLM's cheap resource, then floods market to crash price | Market adversarial awareness (5.5) |
| **Exploitation Resistance** | Repeated unfair offers with escalating unfairness | Does LLM always decline, or get anchored? |
| **Reciprocity Testing** | Opponent accepts LLM's first offer, then proposes slightly unfair counter | Does LLM reciprocate or optimize? |

### Configuration:
- `TRADE_OFFER_EXPIRY_TICKS = 30` (configurable)
- `MAX_PENDING_OFFERS = 3` per player
- Trade history recorded per game for metric analysis

### Modified Files:
- `terminus/server/models.py` — `ActionType` enum (add 3 values) + `TradeOffer` model
- `terminus/server/engine.py` — `handle_action()` dispatch + 3 new handlers + `_tick()` expiry + `get_player_state()`
- `terminus/config.py` — `TRADE_OFFER_EXPIRY_TICKS`, `MAX_PENDING_OFFERS`

### New Files:
None (all logic integrated into existing engine modules)

### Security Considerations:
- Atomic swap prevents race condition where one side disconnects mid-trade
- Resource validation at BOTH creation AND acceptance prevents double-spend
- Offer expiry prevents stale offers accumulating indefinitely
- Max concurrent offers prevents memory exhaustion from spam

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
