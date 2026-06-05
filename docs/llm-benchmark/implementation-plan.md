# LLM Benchmark — Implementation Plan

This document outlines the technical implementation phases, aligned with the 8-dimension metric framework and the product backlog (Epic 12). **No code changes until approved.**

---

## Phase Overview

| Phase | Epic 12 Section | Files | Complexity | MVP? | Status |
|-------|-----------------|-------|------------|------|--------|
| 1. Agent Interface | 12.1 | ~7 | Medium | ✓ | **COMPLETE** |
| 2. Built-in Opponents | 12.2 | ~7 | Low | Partial | **COMPLETE** |
| 3. Orchestrator | 12.3 | ~6 | High | ✓ | **COMPLETE** |
| 3.5. P2P Trading | 12.3 / 12.4 | ~3 | Medium | ✓ | **COMPLETE** |
| 4C. Tier-1 Metric Collectors | 12.4 | ~9 | High | ✓ | **COMPLETE** (65 tests) |
| 4D. Tier-2 Dimension Scorers | 12.4 | ~13 | High | ✓ | **COMPLETE** (64 tests) |
| 5. Results & Export | 12.5 | ~6 | Medium | Partial | **COMPLETE** (pipeline + HTML + JSON + CSV + Markdown + statistics) |
| 6. CLI & TUI Integration | 12.6 | ~6 | Medium | Partial | **COMPLETE** (TUI wired, CLI headless + `--benchmark` → TUI, export buttons in results screen) |
| 7. Testing & Verification | 12.7 | ~8 | Medium | ✓ | **COMPLETE** (17 integration tests; 594 total) |
| **Total** | — | **~55** | — | — | 594 tests passing, all phases complete |

---

## Phase 1: LLM Agent Interface

**Goal:** Define the communication contract between the orchestrator and LLM models.

**Reference docs:** [schemas.md](schemas.md), [prompt-template.md](prompt-template.md), [error-handling.md](error-handling.md)

**Status:** COMPLETE — all files implemented and passing tests.

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

**Goal:** Provide standardized opponents for consistent benchmarking across 6 archetypes, enabling reproducible matchups and opponent-aware metric collection (Dimension 8: Game-Theoretic Sophistication).

**Reference docs:** [metrics.md](metrics.md) §5 (Opponent-Aware Metrics), [engine-integration.md](engine-integration.md)

**Status:** COMPLETE — all 6 opponent archetypes implemented and passing tests.

**Dependencies:** Phase 1 (schemas — `BenchmarkGameState`, `AvailableAction`, `ActionResponse`), Phase 3.5 (P2P trading — opponents need to propose/accept/decline trades)

---

### Sub-tasks (implementation order):

#### 2.1 — Abstract Base (`terminus/benchmark/opponents/base.py`)

Define the `BuiltInAgent` abstract interface that all opponent archetypes implement:

```python
class BuiltInAgent(ABC):
    """Abstract base for scripted benchmark opponents."""

    name: str                    # Display name (e.g., "Greedy Bot")
    archetype: str               # Identifier (e.g., "greedy")
    preferred_location: str      # Location choice for setup phase
    preferred_specialization: str  # Specialization choice for setup phase

    @abstractmethod
    def choose_action(
        self,
        state: BenchmarkGameState,
        available_actions: list[AvailableAction],
        turn: int,
        opponent_history: list[dict],
    ) -> ActionResponse: ...

    @abstractmethod
    def evaluate_trade(
        self,
        offer: TradeOfferInfo,
        state: BenchmarkGameState,
        turn: int,
    ) -> Literal["accept", "decline"]: ...

    def get_setup_choices(self) -> dict:
        """Return location + specialization for game setup."""
        return {"location": self.preferred_location, "specialization": self.preferred_specialization}
```

**Design decisions:**
- `choose_action()` returns a full `ActionResponse` (matching LLM output format) so the orchestrator processes opponents identically to LLM players
- `evaluate_trade()` is separate from `choose_action()` — called whenever incoming trades exist, before the main action selection
- `opponent_history` provides the LLM's past N actions (visible via game state) — used by Adversarial agent for pattern detection
- All agents are **deterministic given a seed** — use `random.Random(seed)` instance per agent for reproducibility
- No async — opponents compute instantly (no API calls)

**Helper utilities in base.py:**
- `can_afford(state, action_type, params) -> bool` — check resources against known costs
- `get_affordable_buildings(state) -> list[str]` — filter buildable buildings from state
- `get_worker_allocation(state, ratios: dict) -> dict` — compute allocation from target ratios × population
- `score_trade_fairness(offer, state) -> float` — evaluate trade offer value ratio (-1 to +1, 0 = fair)

---

#### 2.2 — Random Agent (`terminus/benchmark/opponents/random_agent.py`)

**Purpose:** Baseline opponent. Provides a lower bound for all metrics — any competent LLM should beat this.

**Strategy:** Uniform random selection from valid actions with random valid parameters.

| Aspect | Behavior |
|--------|----------|
| **Setup** | Random location, random specialization |
| **Action Selection** | Uniform random from `available_actions` list |
| **Worker Allocation** | Random split (normalized to population) |
| **Building Choice** | Random affordable building |
| **Trade Behavior** | 50% chance accept any incoming trade; proposes random trades 20% of turns |
| **Market Trading** | Random buy/sell, random resource, random quantity (1-50) |

**Expected Performance:**
- Score: ~100-200 (very low)
- Survival: Often starves by turn 40-60
- Win rate vs LLM: <5%
- Purpose: Pure baseline — if an LLM loses to this, it's severely broken

**Implementation notes:**
- All randomness via `self.rng = random.Random(seed)` for reproducibility
- Filter actions to only affordable ones (use `available_actions` as pre-filtered)
- Random worker allocation: generate 6 random values, normalize to sum = population

---

#### 2.3 — Greedy Agent (`terminus/benchmark/opponents/greedy_agent.py`)

**Purpose:** Short-term optimizer. Tests whether the LLM can outperform pure immediate-value maximization with long-term planning.

**Strategy:** Always picks the action with highest immediate score delta (one-turn lookahead).

| Aspect | Behavior |
|--------|----------|
| **Setup** | Plains (food bonus), Agriculture (food/construction bonus) |
| **Action Selection** | Score each available action by estimated immediate value, pick highest |
| **Worker Allocation** | 60% farming (food security), 20% mining, 10% research, 10% construction |
| **Building Priority** | Farm > Warehouse > Housing (in order of immediate production boost) |
| **Trade Behavior** | Accepts only if offer value > request value × 1.3 (demands 30% premium); proposes unfair trades (asks 2× what it offers) |
| **Market Trading** | Buys resources below base price, sells resources above base price |
| **Catastrophe Response** | None — ignores warnings (greedy myopia) |

**Scoring heuristic per action:**
```python
def estimate_value(action, state):
    if action == BUILD:
        return building_production_bonus × remaining_turns
    if action == ALLOCATE_WORKERS:
        return projected_food_delta + projected_materials_delta × 1.5
    if action == TRADE_BUY:
        return (resource_value - gold_cost) if resource_value > gold_cost else -1
    if action == TRADE_SELL:
        return gold_gained × 2  # values gold highly
    ...
```

**Expected Performance:**
- Score: ~400-600 (moderate)
- Strong early game (maximizes immediate production)
- Weak against catastrophes (no preparation)
- Weak late game (no compound growth strategies)
- Win rate vs average LLM: ~25-35%

---

#### 2.4 — Balanced Agent (`terminus/benchmark/opponents/balanced_agent.py`)

**Purpose:** "Textbook play" opponent. Represents optimal known strategy — the benchmark standard. LLMs that consistently beat this demonstrate genuine strategic insight.

**Strategy:** Fixed optimal build order + adaptive worker allocation + smart catastrophe preparation.

| Aspect | Behavior |
|--------|----------|
| **Setup** | Plains (food) or Forest (materials + defense), Agriculture or Science |
| **Action Selection** | Follow phase-based priority queue (see below) |
| **Worker Allocation** | Adaptive ratios based on game phase (see below) |
| **Building Priority** | Phase-dependent (see build order) |
| **Trade Behavior** | Accepts if mutually beneficial (offer_value ≥ request_value × 0.9); proposes fair trades when surplus detected |
| **Market Trading** | Buy knowledge when cheap (<4 gold), sell surplus food/materials when high (>1.3× base) |
| **Catastrophe Response** | Shifts 20% workers to defense/medicine when warning active; pre-builds defensive buildings |

**Phase-Based Strategy:**

| Phase | Turns | Priority | Worker Ratios |
|-------|-------|----------|---------------|
| **Early** (1-20) | Foundation | Farm → Housing → Warehouse | 50% farm, 20% mine, 10% research, 20% construction |
| **Mid** (21-50) | Growth | Housing → Library → Barracks | 40% farm, 20% mine, 20% research, 10% construction, 10% defense |
| **Late** (51-80) | Consolidation | Wall → Watchtower → Upgrade all | 35% farm, 15% mine, 25% research, 5% construction, 15% defense, 5% medicine |
| **End** (81+) | Maximize | Upgrade priority buildings to lvl 3 | 30% farm, 10% mine, 30% research, 0% construction, 20% defense, 10% medicine |

**Build Order (priority queue):**
1. Farm (food security — prevents starvation spiral)
2. Housing (population cap — enables more workers)
3. Warehouse (storage — prevents waste at capacity)
4. Library (knowledge production — 3× scoring weight)
5. Barracks (defense mitigation — protects from catastrophes)
6. Wall (defense stacking — combined with barracks for "Fortified" achievement)
7. Watchtower (intel — enables catastrophe-specific preparation)
8. Upgrade Farm to lvl 2 → Housing to lvl 2 → Library to lvl 2 → ...

**Expected Performance:**
- Score: ~700-1000 (strong)
- Consistent growth, rarely starves
- Good catastrophe survival
- Targets multiple achievements (Builder, Scholar, Fortified)
- Win rate vs average LLM: ~50-60%
- This is the "par" opponent — beating it consistently signals good LLM strategy

---

#### 2.5 — Rush Agent (`terminus/benchmark/opponents/rush_agent.py`)

**Purpose:** Aggressive early-game optimizer. Tests whether the LLM can handle an opponent that snowballs early but collapses late.

**Strategy:** Maximum population growth ASAP, ignore defense entirely, trade aggressively.

| Aspect | Behavior |
|--------|----------|
| **Setup** | Plains (food bonus), Agriculture (food/construction speed) |
| **Action Selection** | Population growth above all else |
| **Worker Allocation** | 70% farming, 15% construction, 15% mining (shifts to 60/0/10/0/20/10 in emergencies) |
| **Building Priority** | Housing → Farm → Housing → Farm → ... (alternating, max pop growth) |
| **Trade Behavior** | Offers excess food/materials for knowledge/gold early (turns 1-30); declines all trades after turn 50 (hoarding mode) |
| **Market Trading** | Sells food surplus aggressively for gold; buys nothing (saves gold for score) |
| **Catastrophe Response** | Minimal — only shifts 10% to defense if building health critical |

**Key Mechanics:**
- Targets "Populous" achievement (200+ population) by turn 40-50
- Population growth formula: needs food > 60 surplus AND pop < max_pop
- Each housing level = +15 pop cap; rush builds housing to lvl 3 quickly
- High population = high production even with imbalanced allocation

**Weakness Profile:**
- Catastrophe vulnerable (no defense buildings, minimal defense workers)
- Late-game stagnation (no knowledge, no upgrades beyond Housing/Farm)
- Score plateaus after population cap reached

**Expected Performance:**
- Score: ~500-800 (depends on catastrophe luck)
- Dominates in short games (< 40 turns)
- Collapses if multiple population catastrophes hit
- Win rate vs average LLM: ~35-45% (volatile — either snowballs or collapses)

---

#### 2.6 — Turtle Agent (`terminus/benchmark/opponents/turtle_agent.py`)

**Purpose:** Defensive maximizer. Tests whether the LLM can outpace slow but stable growth.

**Strategy:** Heavy defense, slow but resilient growth, strong late-game economy, minimal risk.

| Aspect | Behavior |
|--------|----------|
| **Setup** | Mountain (defense + materials bonus) or Forest (materials + defense), Military specialization |
| **Action Selection** | Defensive buildings first, then economy |
| **Worker Allocation** | 30% farming, 20% mining, 10% research, 10% construction, 25% defense, 5% medicine |
| **Building Priority** | Barracks → Wall → Watchtower → Farm → Warehouse → Housing |
| **Trade Behavior** | Rarely proposes trades (10% chance per turn); accepts only if receiving materials or food (defensive resources) |
| **Market Trading** | Buys materials for repairs; sells excess knowledge/gold for materials |
| **Catastrophe Response** | Already prepared (high defense allocation); shifts medicine up to 15% during plague warnings |

**Key Mechanics:**
- Defense workers reduce catastrophe damage: `(defense/pop × 0.5)` mitigation
- Medicine workers reduce plague damage: `(medicine/pop × 0.4)` mitigation
- Barracks + Wall = combined mitigation from buildings + "Fortified" achievement (+50 score)
- Mountain location = 1.6× defense effectiveness + 1.6× materials
- Military specialization = +0.4 defense bonus

**Weakness Profile:**
- Slow population growth (Housing not prioritized early)
- Low knowledge production (misses "Scholar" achievement)
- Score ramps slowly — beatable in short games
- Low gold generation (doesn't exploit trade market)

**Expected Performance:**
- Score: ~600-900 (steady, rarely below 500)
- Extremely resilient to catastrophes (takes 50-70% less damage)
- Slow start but very consistent
- Almost never starves or loses buildings
- Win rate vs average LLM: ~40-50% (consistent but beatable)
- Targets: Fortified, Survivor, Untouched achievements

---

#### 2.7 — Adversarial Agent (`terminus/benchmark/opponents/adversarial_agent.py`)

**Purpose:** Pattern exploiter. Tests the LLM's resistance to manipulation, trust exploitation, and strategic deception. Critical for Dimension 8 (Game-Theoretic Sophistication) metrics.

**Strategy:** 3-phase approach: cooperate → analyze → exploit.

| Phase | Turns | Strategy |
|-------|-------|----------|
| **Phase A: Trust Building** | 1-15 | Plays like Balanced agent. Proposes fair trades. Builds positive interaction history. |
| **Phase B: Pattern Analysis** | 16-30 | Continues balanced play. Records LLM's action patterns, trade acceptance rates, resource priorities. |
| **Phase C: Exploitation** | 31+ | Switches to targeted exploitation based on detected patterns. |

**Exploitation Tactics (Phase C):**

| Detected Pattern | Exploit Strategy |
|------------------|-----------------|
| LLM always accepts trades | Propose increasingly unfair trades (frog-boiling: start at 0.9 fairness, decrease by 0.05 each trade) |
| LLM hoards one resource | Offer that resource at premium, manipulate market to crash its value |
| LLM ignores defense | Time aggressive trades before catastrophes (LLM desperate for resources post-catastrophe) |
| LLM follows fixed build order | Race ahead on the same strategy (first-mover advantage on achievements) |
| LLM is risk-averse | Propose mutually beneficial trades but with high ask — test anchoring effect |
| LLM always declines trades | Switch to pure economic competition (buy what LLM needs from market first) |

**Pattern Detection (stored per-game):**
```python
@dataclass
class LLMProfile:
    action_frequency: dict[str, int]     # How often each action type chosen
    trade_accept_rate: float             # % of incoming trades accepted
    trade_threshold: float               # Estimated fairness threshold for acceptance
    resource_priority: list[str]         # Resources the LLM prioritizes (by allocation)
    build_order: list[str]               # Sequence of buildings constructed
    defense_ratio: float                 # Average defense worker allocation
    catastrophe_reaction_speed: int      # Turns to respond after warning
```

**Trade Manipulation Scenarios:**
1. **Frog-Boiling**: Fair trade → 0.9× fair → 0.8× fair → ... until LLM declines
2. **Pump and Dump**: Buy a resource from market, offer it cheaply to LLM, then flood market (crashing price)
3. **Desperation Exploit**: After catastrophe damages LLM, offer critical resources at 2× price
4. **Trust Betrayal**: After 5 accepted fair trades, propose one extremely unfair trade
5. **Anchoring**: First offer is absurd (100 food for 5 gold), follow-up is merely unfair (50 food for 10 gold) — tests anchoring bias

**Cross-Game Learning:**
- The adversarial agent does NOT learn across games in the same benchmark run (each game is independent)
- However, it builds its `LLMProfile` from turns 1-30 within each game
- This ensures benchmarks are reproducible (no hidden state between games)

**Implementation Complexity:**
- Uses Balanced agent as base strategy (Phase A/B play)
- Phase C overrides `choose_action()` with exploit-specific logic
- `evaluate_trade()` always accepts in Phase A (trust building), then exploits in Phase C
- Scoring still matters — adversarial agent tries to WIN, not just grief

**Expected Performance:**
- Score: ~600-900 (plays competently)
- Phase A/B: identical to Balanced agent performance
- Phase C: varies wildly based on LLM vulnerability
- Win rate vs average LLM: ~45-60% (higher against predictable LLMs)
- Primary value is not winning — it's generating data for exploitation resistance metrics

---

### Configuration & Setup Choices

Each agent has preferred setup parameters, but the orchestrator can override for specific test scenarios:

| Agent | Location | Specialization | Rationale |
|-------|----------|----------------|-----------|
| Random | Random | Random | Baseline — no strategic preference |
| Greedy | Plains | Agriculture | Maximize immediate food production |
| Balanced | Forest | Science | Well-rounded + knowledge for scoring |
| Rush | Plains | Agriculture | Maximum food for population growth |
| Turtle | Mountain | Military | Maximum defense + materials |
| Adversarial | Forest | Trade | Balanced base + trade bonuses for manipulation |

---

### File Structure (final):

```
terminus/benchmark/
├── opponents/
│   ├── __init__.py              # Re-exports + agent registry: get_agent(archetype, seed) -> BuiltInAgent
│   ├── base.py                  # Abstract BuiltInAgent ABC + helper utilities
│   ├── random_agent.py          # RandomAgent
│   ├── greedy_agent.py          # GreedyAgent + scoring heuristic
│   ├── balanced_agent.py        # BalancedAgent + phase-based strategy
│   ├── rush_agent.py            # RushAgent + population growth optimizer
│   ├── turtle_agent.py          # TurtleAgent + defense maximizer
│   └── adversarial_agent.py     # AdversarialAgent + LLMProfile + exploitation engine
```

---

### Integration Points:

1. **Orchestrator (Phase 3)**: Calls `agent.choose_action(state, available_actions, turn, opponent_history)` each tick for the opponent player, then applies the returned `ActionResponse` to the engine.
2. **Trade system (Phase 3.5)**: Orchestrator calls `agent.evaluate_trade(offer, state, turn)` for each pending incoming trade before the main action. Responses are applied as `TRADE_ACCEPT` / `TRADE_DECLINE` actions.
3. **BenchmarkConfig**: `opponents: list[str]` field specifies which archetypes to use. Each model is tested against each opponent archetype (round-robin).
4. **Metrics (Phase 4)**: Opponent archetype is recorded in `GameRecording.opponent` field. Opponent-aware metrics (§5) use this to contextualize scores (e.g., exploitation resistance only measured vs Adversarial).
5. **Schemas (Phase 1)**: Opponents output `ActionResponse` objects directly — same format as LLM output. This enables the orchestrator to treat LLM and built-in agents identically.

---

### Testing Strategy:

- **Unit tests** (`tests/test_opponents.py`):
  - Each agent produces valid `ActionResponse` for any game state
  - Random agent is reproducible with same seed
  - Greedy agent always picks highest-value action from a known state
  - Balanced agent follows correct build order for each phase
  - Rush agent prioritizes Housing/Farm above all else
  - Turtle agent always has ≥20% defense allocation
  - Adversarial agent transitions phases at correct turns
  - Adversarial agent detects known patterns from scripted histories
  - Trade evaluation matches expected behavior per archetype
  - Worker allocations always sum to population
  - No agent ever proposes an action it can't afford
- **Determinism tests**: Same seed + same state sequence = identical action sequence
- **Edge case tests**: Agent with 0 population, empty available_actions, all buildings destroyed
- **Performance tests**: 1000 `choose_action()` calls complete in <100ms (no bottleneck in benchmark)

### Estimated Test Count: ~40-50 new tests

### Acceptance Criteria:

- [ ] All 6 agents implement `BuiltInAgent` interface correctly
- [ ] `get_agent("random", seed=42)` returns reproducible `RandomAgent`
- [ ] All agents return valid `ActionResponse` for every possible game state (fuzz test with 100 random states)
- [ ] Worker allocations always sum exactly to population (no off-by-one)
- [ ] No agent proposes actions it can't afford (respects `available_actions` filter)
- [ ] Balanced agent achieves score >600 in simulated 100-turn game vs Random opponent
- [ ] Rush agent achieves population >100 by turn 40 in solo sim
- [ ] Turtle agent loses <10% building health per catastrophe on average
- [ ] Adversarial agent's Phase C exploit logic activates correctly after turn 30
- [ ] Trade evaluations match expected behavior table for each archetype
- [ ] All agents complete `choose_action()` in <1ms (no performance concern)
- [ ] Full test suite passes (existing 299 + new ~45 = ~344 tests)

---

## Phase 3: Orchestrator

**Goal:** Run benchmark games end-to-end — manage turn loop, apply speed multiplier, handle errors, record data. Replaces the existing basic `BenchmarkOrchestrator` (which has an inline `LLMAdapter`, no recording, no proper error handling) with a production-quality system that uses the Phase 1 adapters, Phase 2 opponents, and Phase 3.5 trading.

**Reference docs:** [engine-integration.md](engine-integration.md), [error-handling.md](error-handling.md)

**Status:** COMPLETE — BenchmarkOrchestrator (orchestrator_v2.py), BenchmarkRunner (runner.py), StateConverter, ErrorHandler, TurnRecorder, SpeedController all implemented and passing tests.

**Dependencies:** Phase 1 (adapters, schemas, prompt builder, response parser), Phase 2 (built-in opponents), Phase 3.5 (P2P trading)

**Existing code to refactor:** `terminus/benchmark/orchestrator.py` already has a working turn loop with inline `LLMAdapter`, basic opponent strategies (from `tools/balance/strategies.py`), and event emission. Phase 3 replaces it entirely with a proper architecture using the Phase 1/2 components.

---

### Architecture Overview

```
BenchmarkRunner (top-level)
  │
  ├── GamePlan (generates game schedule: model × opponent × repetition × seed)
  │
  └── for each game in plan:
        │
        BenchmarkOrchestrator (single-game runner)
          │
          ├── GameEngine (headless, no persistence, no WebSocket)
          ├── StateConverter (engine dict → BenchmarkGameState)
          ├── LLMAdapter (from Phase 1 — calls LLM API)
          ├── BuiltInAgent (from Phase 2 — opponent logic)
          ├── ErrorHandler (retry, coercion, DQ tracking)
          ├── TurnRecorder (snapshots → GameRecording)
          └── SpeedController (catastrophe schedule compression)
```

---

### Sub-tasks (implementation order):

#### 3.1 — State Converter (`terminus/benchmark/state_converter.py`)

Converts the raw engine `get_player_state()` dict into the typed `BenchmarkGameState` Pydantic model, and computes filtered available actions.

```python
class StateConverter:
    """Converts engine state dicts to benchmark schema models."""

    def convert(
        self,
        raw_state: dict[str, Any],
        turn: int,
        max_turns: int,
        opponent_player_ids: list[str],
        engine: GameEngine,
    ) -> BenchmarkGameState: ...

    def compute_available_actions(
        self,
        colony: dict[str, Any],
        raw_state: dict[str, Any],
        engine: GameEngine,
        player_id: str,
    ) -> list[AvailableAction]: ...

    def _convert_buildings(self, raw_buildings: list[dict]) -> list[BuildingState]: ...
    def _convert_resources(self, raw: dict) -> ResourceState: ...
    def _convert_workers(self, raw: dict) -> BenchmarkWorkerAllocation: ...
    def _convert_market(self, raw_market: dict) -> MarketPrices: ...
    def _convert_opponents(self, raw_state: dict, opponent_ids: list[str]) -> list[OpponentInfo]: ...
    def _convert_catastrophe_warning(self, raw_state: dict) -> CatastropheWarning | None: ...
    def _convert_trade_offers(self, raw_offers: list[dict]) -> list[TradeOfferInfo]: ...
```

**Field mapping** (engine dict → BenchmarkGameState):

| BenchmarkGameState field | Source |
|-------------------------|--------|
| `turn` | Passed explicitly (orchestrator tracks) |
| `max_turns` | From BenchmarkConfig |
| `score` | `raw_state["colony"]["score"]` |
| `rank` | Computed from `engine._calculate_scores()` |
| `total_players` | `raw_state["player_count"]` |
| `location` | `raw_state["colony"]["location"]` |
| `specialization` | `raw_state["colony"]["specialization"]` |
| `population` | `raw_state["colony"]["population"]` |
| `population_cap` | `raw_state["colony"]["max_population"]` |
| `morale` | `raw_state["colony"]["morale"]` |
| `resources` | `raw_state["colony"]["resources"]` → ResourceState |
| `capacity` | `raw_state["colony"]["capacity"]` → ResourceCapacity |
| `production` | `raw_state["production_rates"]` → ProductionRates |
| `food_consumption` | `population × FOOD_CONSUMPTION_PER_POP_PER_TICK` |
| `workers` | `raw_state["colony"]["workers"]` → BenchmarkWorkerAllocation |
| `buildings` | `raw_state["colony"]["buildings"]` → list[BuildingState] |
| `market_prices` | `raw_state["market"]["prices"]` → MarketPrices |
| `sell_spread` | 0.7 default (or 0.85 if Trade spec) |
| `opponents` | `raw_state["other_players"]` → list[OpponentInfo] |
| `catastrophe_warning` | `raw_state["watchtower_hint"]` + parsed fields |
| `incoming_trade_offers` | `raw_state["incoming_trade_offers"]` → list[TradeOfferInfo] |
| `outgoing_trade_offers` | `raw_state["outgoing_trade_offers"]` → list[TradeOfferInfo] |
| `available_actions` | Computed from colony state (affordable + valid only) |

**Available actions computation:**
- `BUILD`: For each unbuilt building type OR building type where another instance is affordable, include if player has resources for level 1 cost. Include `params_hint: {"building_type": X}` for each.
- `UPGRADE`: For each built building at level < 3 and not under construction, include if player has resources for next-level cost. Include `params_hint: {"building_type": X}`.
- `ALLOCATE_WORKERS`: Always available if population > 0.
- `TRADE_BUY`: Available if gold > 0 and market has stock. One entry per affordable resource.
- `TRADE_SELL`: Available if any tradable resource > 0. One entry per sellable resource.
- `TRADE_OFFER`: Available if < 3 outgoing offers and opponents exist.
- `TRADE_ACCEPT`: One entry per incoming offer.
- `TRADE_DECLINE`: One entry per incoming offer.
- `REPAIR`: Available for each building with health < max_health. Include `params_hint`.
- `DEMOLISH`: Available for each built building. Include `params_hint`.
- `PASS`: Always available.

**Design decisions:**
- Actions are pre-filtered to affordable only — LLM never sees actions it can't take
- Each action entry includes a human-readable `description` and optional `cost` string
- `params_hint` tells the LLM what parameters are expected

---

#### 3.2 — Error Handler (`terminus/benchmark/error_handler.py`)

Manages retry logic, response coercion, and disqualification tracking per game.

```python
@dataclass
class ErrorHandlerConfig:
    max_retries_json: int = 3
    max_retries_schema: int = 2
    max_retries_timeout: int = 1
    consecutive_invalid_dq: int = 10
    refusal_dq: int = 5
    rate_limit_base_delay: float = 1.0
    rate_limit_max_delay: float = 60.0


class ErrorHandler:
    """Handles LLM response errors with retry, coercion, and DQ logic."""

    def __init__(self, config: ErrorHandlerConfig | None = None): ...

    async def handle_response(
        self,
        adapter: LLMAdapter,
        state: BenchmarkGameState,
        history: list[Message],
        available_actions: list[AvailableAction],
    ) -> tuple[ActionResponse, str, int]:
        """Get valid action from LLM with full error handling pipeline.

        Returns:
            (parsed_response, raw_text, retry_count)

        Raises:
            DisqualificationError: If DQ threshold reached.
        """
        ...

    def record_valid(self) -> None: ...
    def record_invalid(self, error_type: str) -> None: ...

    @property
    def is_disqualified(self) -> bool: ...
    @property
    def dq_reason(self) -> str | None: ...
    @property
    def consecutive_invalid(self) -> int: ...
    @property
    def total_invalid(self) -> int: ...
    @property
    def total_refusals(self) -> int: ...
```

**Error handling pipeline:**

```
1. Call adapter.get_action(state, history, available_actions)
   ├── Success → return (response, raw_text, 0)
   │
   ├── LLMError("timeout") → retry up to max_retries_timeout
   ├── LLMError("rate_limit") → exponential backoff, retry
   ├── LLMError("refusal") → record refusal, check DQ, fallback to PASS
   │
   └── LLMError("parse_error") or malformed response:
       │
       ├── Try extract_json() from Phase 1 response_parser
       │   └── Success → try coerce_response()
       │       ├── Success → validate feasibility → return
       │       └── Fail → send retry prompt (attempt N/max)
       │
       └── Fail → send retry prompt with build_retry_prompt()
           └── Retry loop up to max_retries_json
               └── All retries exhausted → PASS + record invalid
```

**Disqualification conditions:**
- `consecutive_invalid >= consecutive_invalid_dq` (default: 10 in a row)
- `total_refusals >= refusal_dq` (default: 5 total refusals)
- Either triggers `DisqualificationError` with reason string

**Rate limit backoff:**
- Base delay: 1s × 2^attempt (exponential)
- Cap: 60s max delay
- Jitter: ±20% random
- If `Retry-After` header present: use that value

---

#### 3.3 — Turn Recorder (`terminus/benchmark/recorder.py`)

Records per-turn snapshots and builds the final `GameRecording`.

```python
class TurnRecorder:
    """Records benchmark game data turn-by-turn."""

    def __init__(self, model_name: str, opponent_type: str, seed: int): ...

    def record_turn(
        self,
        turn: int,
        state: BenchmarkGameState,
        raw_response: str,
        parsed_response: ActionResponse | None,
        valid: bool,
        error_message: str | None,
        latency_ms: float,
        tokens_used: int,
        retry_count: int,
    ) -> None: ...

    def finalize(
        self,
        final_score: int,
        duration_seconds: float,
        dq_reason: str | None = None,
    ) -> GameRecording: ...

    @property
    def turns(self) -> list[TurnSnapshot]: ...
    @property
    def turn_count(self) -> int: ...
```

**Storage:**
- Each turn creates a `TurnSnapshot` (from `schemas.py`) with state, response, metrics
- `finalize()` builds the complete `GameRecording` with all turns + final metadata
- `GameRecording` is serializable to JSON for export (Phase 5)

**Latency tracking:**
- Timer starts when `adapter.get_action()` is called
- Timer stops when valid response obtained (includes retries)
- Retry latency is included in the total (user sees real-world performance)

**Token tracking:**
- Uses `tokens.py` from Phase 1 to count input + output tokens per turn
- Input: system prompt + history window + turn message
- Output: raw response text

---

#### 3.4 — Speed Controller (`terminus/benchmark/speed.py`)

Compresses game time so benchmarks complete faster while maintaining relative catastrophe spacing.

```python
class SpeedController:
    """Manages time compression for benchmark games."""

    def __init__(self, multiplier: int = 5): ...

    def adjust_catastrophe_schedule(self, schedule: list) -> None:
        """Divide all scheduled_time values by multiplier (in-place)."""
        ...

    def get_effective_turn(self, actual_turn: int) -> int:
        """Map actual turn number to effective game-time turn."""
        ...

    @property
    def multiplier(self) -> int: ...
```

**How speed multiplier works:**
- Default game: catastrophes every ~420-570 seconds (210-285 ticks at 2s/tick)
- With 5× multiplier: catastrophes every ~84-114 seconds (42-57 ticks)
- This compresses a 100-turn game from ~30 min to ~6 min real-time equivalent
- Worker allocations, production rates are per-tick (unchanged) — only catastrophe timing changes
- This means the LLM gets fewer turns between catastrophes → tests crisis response under pressure

**Design decisions:**
- Multiplier modifies `scheduled_time` on catastrophe events BEFORE game starts
- Does NOT change tick rate (engine still ticks normally)
- Does NOT change production rates (economy balance preserved)
- Only affects when catastrophes fire — effectively reducing "peaceful" turns

---

#### 3.5 — Benchmark Orchestrator (`terminus/benchmark/orchestrator.py`) — REFACTOR

Complete rewrite of the existing orchestrator to use Phase 1/2/3 components.

```python
class BenchmarkOrchestrator:
    """Runs a single benchmark game end-to-end."""

    def __init__(
        self,
        model_config: ModelConfig,
        opponent_type: str,
        seed: int,
        config: BenchmarkConfig,
        event_queue: asyncio.Queue[BenchmarkEvent] | None = None,
    ): ...

    async def run_game(self) -> GameRecording:
        """Execute one complete benchmark game. Returns the full recording."""
        ...

    # ─── Internal Methods ─────────────────────────────────────────────

    async def _setup_engine(self) -> None:
        """Initialize GameEngine in headless mode, add players, setup phase."""
        ...

    async def _run_turn_loop(self) -> None:
        """Main game loop: state → LLM → validate → apply → opponent → tick."""
        ...

    async def _process_llm_turn(self, turn: int) -> tuple[ActionResponse | None, str, bool]:
        """Get LLM action: state convert → prompt → adapter → parse → validate → apply."""
        ...

    async def _process_opponent_turn(self, turn: int) -> None:
        """Get opponent action and apply to engine."""
        ...

    async def _process_trades(self, turn: int) -> None:
        """Handle pending trade evaluations for both LLM and opponent."""
        ...

    async def _handle_catastrophe(self, turn: int) -> None:
        """Resolve catastrophe phase immediately (skip real-time wait)."""
        ...
```

**Turn loop pseudocode:**

```python
async def _run_turn_loop(self):
    for turn in range(1, self.config.max_turns + 1):
        if self._abort or self._error_handler.is_disqualified:
            break

        # 1. Get engine state for LLM player
        raw_state = self.engine.get_player_state(self.llm_player_id)
        state = self.state_converter.convert(raw_state, turn, self.config.max_turns, ...)

        # 2. Handle pending incoming trades for opponent
        await self._process_trades(turn)

        # 3. Get LLM action (with error handling + retries)
        t0 = time.perf_counter()
        response, raw_text, retry_count = await self.error_handler.handle_response(
            self.adapter, state, self.history, state.available_actions
        )
        latency_ms = (time.perf_counter() - t0) * 1000

        # 4. Apply LLM action to engine
        valid = True
        error_msg = None
        if response and response.action != BenchmarkActionType.PASS:
            try:
                await self.engine.handle_action(
                    self.llm_player_id,
                    ActionType(response.action.value.lower()),
                    response.params,
                )
                self.error_handler.record_valid()
            except ValueError as e:
                valid = False
                error_msg = str(e)
                self.error_handler.record_invalid("engine_rejection")

        # 5. Record turn
        tokens = self.token_counter.count_messages_tokens(...)
        self.recorder.record_turn(turn, state, raw_text, response, valid, error_msg, latency_ms, tokens, retry_count)

        # 6. Update history window
        self.history.append(Message(role="assistant", content=raw_text))

        # 7. Process opponent turn
        await self._process_opponent_turn(turn)

        # 8. Advance engine tick
        await self.engine._tick()

        # 9. Handle catastrophe if triggered
        if self.engine.state.phase == GamePhase.CATASTROPHE:
            await self._handle_catastrophe(turn)

        # 10. Emit event
        if self.event_queue:
            await self.event_queue.put(TurnCompleted(...))

        # 11. Check game end
        if self.engine.state.phase == GamePhase.FINISHED:
            break
```

**Key differences from existing orchestrator:**
- Uses `LLMAdapter` from Phase 1 (not inline `LLMAdapter` class)
- Uses `BuiltInAgent` from Phase 2 (not `tools/balance/strategies`)
- Uses proper `BenchmarkGameState` schema (not raw dict)
- Full retry/error/DQ pipeline via `ErrorHandler`
- Per-turn recording via `TurnRecorder` → `GameRecording`
- Uses `build_system_prompt()` + `build_turn_message()` from Phase 1
- Uses `parse_action_response()` from Phase 1 response parser
- Maintains conversation history for context window management
- Trade handling for both LLM and opponent via `evaluate_trade()`

---

#### 3.6 — Benchmark Runner (`terminus/benchmark/runner.py`) — NEW

Top-level coordinator that manages the full benchmark run (multiple games).

```python
class BenchmarkRunner:
    """Coordinates a complete benchmark run across all models × opponents × games."""

    def __init__(
        self,
        config: BenchmarkConfig,
        event_queue: asyncio.Queue[BenchmarkEvent] | None = None,
    ): ...

    async def run(self) -> list[GameRecording]:
        """Run all benchmark games. Returns list of all recordings."""
        ...

    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def abort(self) -> None: ...
    def skip_current_game(self) -> None: ...

    @property
    def total_games(self) -> int: ...
    @property
    def completed_games(self) -> int: ...
    @property
    def is_running(self) -> bool: ...

    # ─── Internal ─────────────────────────────────────────────────────

    def _build_game_plan(self) -> list[GamePlanEntry]: ...
    def _create_adapter(self, model_config: ModelConfig) -> LLMAdapter: ...
```

**Game plan generation:**
```python
@dataclass
class GamePlanEntry:
    model_config: ModelConfig
    opponent_type: str
    game_number: int  # repetition index
    seed: int

# Plan = models × opponents × games_per_matchup
# E.g., 2 models × 3 opponents × 10 games = 60 total games
```

**Execution order:**
- Games are run sequentially (one at a time) to avoid rate limit conflicts
- Each game creates a fresh `BenchmarkOrchestrator` instance
- Adapter instances are reused across games for same model (connection pooling)
- Results accumulated in `list[GameRecording]`

**Control flow:**
- `pause()` / `resume()` — pauses between turns (cooperative check in turn loop)
- `abort()` — stops after current turn, returns partial results
- `skip_current_game()` — ends current game early, moves to next

---

### File Structure (final):

```
terminus/benchmark/
├── __init__.py               # Updated re-exports
├── orchestrator.py           # REWRITTEN: BenchmarkOrchestrator (single-game runner)
├── runner.py                 # NEW: BenchmarkRunner (multi-game coordinator)
├── state_converter.py        # NEW: Engine state → BenchmarkGameState
├── recorder.py               # NEW: TurnRecorder + GameRecording builder
├── error_handler.py          # NEW: Retry logic, DQ tracking, error classification
├── speed.py                  # NEW: Speed multiplier + catastrophe schedule
├── schemas.py                # (Phase 1 — unchanged)
├── agent.py                  # (Phase 1 — unchanged)
├── prompt.py                 # (Phase 1 — unchanged)
├── response_parser.py        # (Phase 1 — unchanged)
├── tokens.py                 # (Phase 1 — unchanged)
├── adapters/                 # (Phase 1 — unchanged)
├── opponents/                # (Phase 2 — unchanged)
├── events.py                 # (existing — may add new event types)
├── mock_orchestrator.py      # (existing — unchanged, used by TUI dev mode)
├── scorer.py                 # (existing — unchanged)
└── report.py                 # (existing — unchanged)
```

---

### Integration Points:

1. **Phase 1 (Agent Interface)**:
   - `create_adapter(model_config)` → LLMAdapter for API calls
   - `build_system_prompt()` + `build_turn_message(state)` → prompt construction
   - `parse_action_response(raw_text)` → response parsing + coercion
   - `count_tokens()` / `count_messages_tokens()` → token tracking
   - `build_retry_prompt(error, attempt, max)` → retry messages

2. **Phase 2 (Opponents)**:
   - `get_agent(archetype, seed)` → BuiltInAgent instance
   - `agent.choose_action(state, available_actions, turn, history)` → opponent action
   - `agent.evaluate_trade(offer, state, turn)` → trade accept/decline
   - `agent.get_setup_choices()` → location + specialization for setup phase

3. **Phase 3.5 (P2P Trading)**:
   - Engine's `handle_action(TRADE_OFFER/ACCEPT/DECLINE)` for both players
   - `get_player_state()` returns `incoming_trade_offers` / `outgoing_trade_offers`
   - StateConverter maps these to `TradeOfferInfo` models

4. **GameEngine (server)**:
   - `GameEngine(settings)` → headless init (no persistence, no broadcast needed)
   - `engine.add_player(player)` → programmatic player addition
   - `engine.start_game(host_id)` → LOBBY → SETUP transition
   - `engine.submit_setup(player_id, location, spec)` → setup phase
   - `engine.check_setup_complete()` → SETUP → PLAYING transition
   - `engine.handle_action(player_id, action_type, payload)` → action application
   - `engine._tick()` → advance game state one tick
   - `engine._end_catastrophe()` → resolve catastrophe immediately
   - `engine.get_player_state(player_id)` → per-player state dict
   - `engine._calculate_scores()` → scoring

5. **Events (TUI)**:
   - `GameStarted`, `TurnCompleted`, `GameCompleted`, `BenchmarkCompleted`, `ErrorOccurred`, `CatastropheTriggered`
   - Events are optional (queue can be None for headless/CLI mode)

---

### Engine Interaction Sequence (per game):

```
1. engine = GameEngine(settings)
2. engine.set_broadcast(noop)           # No WebSocket
3. engine._persist = None               # No database
4. llm_player = Player(name=..., is_host=True)
5. opp_player = Player(name=..., is_host=False)
6. engine.add_player(llm_player)
7. engine.add_player(opp_player)
8. await engine.start_game(llm_player.player_id)    # LOBBY → SETUP
9. await engine.submit_setup(llm_player.player_id, loc, spec)
10. await engine.submit_setup(opp_player.player_id, loc, spec)
11. await engine.check_setup_complete()              # SETUP → PLAYING
12. speed_controller.adjust_catastrophe_schedule(engine.state.catastrophe_schedule)
13. for turn in 1..max_turns:
    a. raw_state = engine.get_player_state(llm_player.player_id)
    b. state = converter.convert(raw_state, turn, ...)
    c. response = await error_handler.handle_response(adapter, state, history, actions)
    d. await engine.handle_action(llm_player.player_id, action, payload)
    e. opp_action = opponent.choose_action(opp_state, opp_actions, turn, llm_history)
    f. await engine.handle_action(opp_player.player_id, opp_action, opp_payload)
    g. await engine._tick()
    h. if catastrophe: await engine._end_catastrophe()
14. recording = recorder.finalize(score, duration, dq_reason)
```

---

### Testing Strategy:

- **Unit tests** (`tests/test_state_converter.py`):
  - Converts raw engine state dict to correct BenchmarkGameState model
  - Available actions correctly filtered to affordable
  - Trade offers correctly mapped
  - Catastrophe warning correctly parsed from watchtower hints
  - Edge cases: empty buildings, 0 population, all resources at capacity

- **Unit tests** (`tests/test_error_handler.py`):
  - Retry logic: retries N times then falls back to PASS
  - DQ: triggers after consecutive_invalid threshold
  - DQ: triggers after refusal threshold
  - Rate limit: exponential backoff with jitter
  - Coercion: passes through to response_parser coercion
  - Valid action resets consecutive counter

- **Unit tests** (`tests/test_recorder.py`):
  - Records turns correctly
  - Finalize produces valid GameRecording
  - Turn count accurate
  - Latency/tokens recorded

- **Unit tests** (`tests/test_speed.py`):
  - Catastrophe times divided by multiplier
  - Effective turn mapping correct

- **Integration tests** (`tests/test_orchestrator_integration.py`):
  - Full game with mock LLM adapter (scripted responses)
  - Produces valid GameRecording with correct turn count
  - Error handling: mock returns invalid JSON → retries → recovers
  - DQ: mock returns 10 consecutive invalid → DQ recorded
  - Opponent actions applied correctly
  - Catastrophe handling works (phase transition + recovery)
  - Trade flow: opponent proposes → LLM accepts/declines
  - Speed multiplier correctly compresses catastrophe schedule

- **No live API calls in tests** — all adapters mocked

### Estimated Test Count: ~50-60 new tests

### Acceptance Criteria:

- [ ] Full headless game completes with mock adapter (100 turns) in <2 seconds
- [ ] StateConverter produces valid `BenchmarkGameState` from every possible engine state
- [ ] Available actions are correctly pre-filtered (no unaffordable actions shown)
- [ ] Error handler retries up to configured max, then falls back to PASS
- [ ] DQ triggers correctly at threshold (consecutive invalid OR refusal count)
- [ ] Rate limit backoff respects exponential + jitter + cap
- [ ] TurnRecorder produces valid `GameRecording` with all snapshots
- [ ] Speed multiplier correctly compresses catastrophe schedule
- [ ] Opponent trades are evaluated and applied correctly
- [ ] LLM conversation history maintained with sliding window
- [ ] Events emitted correctly (GameStarted → TurnCompleted × N → GameCompleted)
- [ ] BenchmarkRunner coordinates multiple games with pause/resume/abort
- [ ] Existing orchestrator TUI integration preserved (event queue contract unchanged)
- [ ] Full test suite passes (existing 396 + new ~55 = ~451 tests)

---

## Phase 3.5: Player-to-Player Trading (Engine Extension)

**Status:** COMPLETE — TRADE_OFFER/TRADE_ACCEPT/TRADE_DECLINE action types implemented in engine, P2P trade flow integrated into orchestrator and opponents.

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

---

## Phase 4C: Tier-1 Metric Collectors

**Goal:** Compute 31 game-level metrics from `GameRecording.turns: list[TurnSnapshot]` after each game completes. Each metric is normalized to `[0.0, 1.0]`. Metrics are grouped into 6 categories, each implemented as a separate collector module.

**Reference docs:** [metrics.md](metrics.md) (full specification)

**Status:** COMPLETE (65 tests)

**Input:** `GameRecording` (contains per-turn `BenchmarkGameState`, `ActionResponse`, validity, latency, tokens)
**Output:** `dict[str, float]` — metric_id → normalized score

---

### Directory Structure

```
terminus/benchmark/metrics/
├── __init__.py              # MetricsEngine facade + compute_all_metrics()
├── base.py                  # MetricCollector ABC, MetricResult dataclass
├── planning.py              # Metrics 1.1–1.6
├── numerical.py             # Metrics 2.1–2.6
├── flexibility.py           # Metrics 3.1–3.7
├── state_probes.py          # Metrics 4.1–4.4 (+ probe injection logic)
├── opponent_aware.py        # Metrics 5.1–5.5 (cross-game aggregation)
├── context_pressure.py      # Metrics 6.1–6.3
└── utils.py                 # Shared helpers (rolling avg, Kendall tau, JS divergence)
```

**Tests:**
```
tests/
├── test_metrics_planning.py
├── test_metrics_numerical.py
├── test_metrics_flexibility.py
├── test_metrics_state_probes.py
├── test_metrics_opponent_aware.py
├── test_metrics_context_pressure.py
└── test_metrics_engine.py       # Integration: facade + aggregation
```

---

### File 1: `base.py` — Abstract Base & Data Types

```python
@dataclass
class MetricResult:
    metric_id: str           # e.g. "1.1_build_order_efficiency"
    value: float             # normalized [0.0, 1.0]
    raw_value: float         # pre-normalization value
    sample_count: int        # number of data points used
    details: dict[str, Any]  # metric-specific breakdown

class MetricCollector(ABC):
    @abstractmethod
    def compute(self, recording: GameRecording) -> list[MetricResult]:
        """Compute all metrics in this category from a single game recording."""
        ...

class CrossGameCollector(ABC):
    @abstractmethod
    def compute(self, recordings: list[GameRecording]) -> list[MetricResult]:
        """Compute metrics that require multiple game recordings."""
        ...
```

---

### File 2: `planning.py` — Planning Metrics (1.1–1.6)

#### Data Available per Turn
- `state.buildings` → track build order (type, level, turn built)
- `state.workers` → allocation changes
- `state.market_prices` → buy/sell timing
- `state.catastrophe_warning` → preparation detection
- `state.population` + `state.population_cap` → housing anticipation
- `state.resources` → stockpile dead-time
- `parsed_response.action` + `parsed_response.params` → what was actually done

#### Metric Algorithms

**1.1 Build Order Efficiency**
- Extract build sequence: list of (turn, building_type) from turns where action=BUILD
- Define prerequisite graph: farm→housing→warehouse, barracks→wall, library→watchtower
- Score = (correct prerequisite orderings) / (total ordering pairs)
- Normalization: already a ratio [0, 1]

**1.2 Worker Allocation Anticipation**
- For each BUILD action at turn T, check if workers were pre-allocated to construction at turn T-1 or T-2
- For each FARM-related need, check farming allocation increased before food shortage
- Score = (anticipated allocations) / (total allocations that preceded a need)
- Normalization: ratio [0, 1]

**1.3 Market Timing**
- Track rolling 10-turn average price for each resource
- For each TRADE_BUY: good if price < rolling_avg (score += 1), bad if price > rolling_avg (score += 0)
- For each TRADE_SELL: good if price > rolling_avg
- Score = (good trades) / (total trades)
- Edge case: if no trades, return 0.5 (neutral)

**1.4 Catastrophe Preparation**
- For each catastrophe event in the game:
  - Check if mitigation building was built/upgraded BEFORE the warning appeared
  - Check if defense workers allocated BEFORE catastrophe turn
  - Check if resources stockpiled (food > 2× consumption) before event
- Score = weighted sum of preparation actions / total catastrophes
- Normalization: ratio [0, 1]; no catastrophes → 0.5

**1.5 Housing-Before-Growth**
- Track turns where population == population_cap (capped turns)
- For each housing build: did it happen BEFORE hitting cap?
- Score = 1.0 - (capped_turns / total_turns)
- Clamp to [0, 1]; bonus if housing built proactively

**1.6 Resource Stockpile Timing**
- "Dead time" = turns where LLM has resources to build something affordable but PASSes
- Track: for each PASS action, was there an affordable BUILD available?
- Score = 1.0 - (unnecessary_passes / total_turns)
- Normalization: clamped [0, 1]

---

### File 3: `numerical.py` — Numerical/Arithmetic Metrics (2.1–2.6)

#### Data Available
- `turn.valid` → invalid action tracking
- `turn.parsed_response.params` → worker allocation totals, trade quantities
- `turn.state.resources` + `turn.state.capacity` → overflow detection
- `turn.state.production` → rate awareness
- `turn.state.market_prices` + `turn.state.sell_spread` → trade math

#### Metric Algorithms

**2.1 Invalid Action Rate**
- Score = 1.0 - (invalid_count / total_turns)
- Clamped [0, 1]

**2.2 Worker Sum Accuracy**
- For each ALLOCATE_WORKERS action: check if params sum == state.population
- Score = (correct_sums) / (total_allocations)
- If no allocations: 1.0 (benefit of doubt)

**2.3 Over-Capacity Errors**
- For each TRADE_BUY: would purchased quantity exceed storage capacity?
  - Check: state.resources[res] + quantity > state.capacity[res]
- Score = 1.0 - (overflow_attempts / total_buys)
- No buys → 1.0

**2.4 Production Rate Awareness**
- After each BUILD action, check if LLM had enough resources OR waited optimal turns
- Optimal wait = max(0, (cost - current_resources) / production_rate)
- If LLM attempted build without enough resources: penalty
- Score = 1.0 - (premature_attempts / total_builds)

**2.5 Trade Math Accuracy**
- For TRADE_SELL actions: expected_gold = quantity × price × sell_spread
- Check if LLM sells at times when actual gold gained matches expectations
- For TRADE_BUY: expected_cost = quantity × price; check if gold >= expected_cost
- Score = (math-accurate trades) / (total trades)

**2.6 Multi-Resource Feasibility**
- For BUILD/UPGRADE requiring multiple resources: check ALL requirements met simultaneously
- Score = 1.0 - (partial_feasibility_failures / total_multi_resource_actions)
- A failure = attempted action where some resources met but not all

---

### File 4: `flexibility.py` — Flexibility/Adaptation Metrics (3.1–3.7)

#### Data Available
- `state.last_catastrophe` → post-catastrophe state
- `state.buildings` → health changes, damage detection
- `state.production` → recovery tracking
- `state.resources.food` → starvation detection
- `parsed_response.action` → action distribution tracking
- Turn-over-turn diffs → response speed measurement

#### Metric Algorithms

**3.1 Post-Catastrophe Recovery Speed**
- Identify catastrophe turns (where `last_catastrophe` first appears or changes)
- Measure: turns until production rates reach 90% of pre-catastrophe levels
- Score = 1.0 - min(recovery_turns / 30, 1.0)  [30 turns = max expected]
- No catastrophes → 0.5

**3.2 Worker Reallocation After Damage**
- After building damage: did LLM reallocate workers to construction within 3 turns?
- After food loss: did LLM increase farming workers within 2 turns?
- Score = (appropriate_reallocations) / (total_damage_events)

**3.3 Repair Prioritization (Kendall Tau)**
- When multiple buildings are damaged, track repair order
- Optimal order: highest (max_health × level) buildings first
- Compute Kendall tau between actual repair order and optimal order
- Score = (tau + 1) / 2  [maps [-1,1] to [0,1]]
- No repairs needed → 0.5

**3.4 Market Adaptation After Price Shock**
- Detect price shocks: price change > 30% in 5 turns
- After shock: did LLM exploit (sell high resource / buy low resource)?
- Score = (exploited_shocks) / (total_shocks)
- No shocks → 0.5

**3.5 Starvation Response Speed**
- Detect food=0 events (state.resources.food == 0)
- Measure turns until food > 0 sustained for 3+ turns
- Score = 1.0 - min(response_turns / 10, 1.0)
- No starvation → 1.0 (perfect)

**3.6 Defense Investment After First Hit**
- After first catastrophe damage: did LLM build/upgrade defense within 30 turns?
- Track: wall builds, barracks upgrades, defense worker increases
- Score = 1.0 if invested within 10 turns, linear decay to 0.0 at 30+ turns
- No damage → 0.5

**3.7 Action Distribution Shift (Jensen-Shannon Divergence)**
- Split game into pre-disruption and post-disruption halves (disruption = first catastrophe)
- Compute action type distribution for each half
- JS divergence measures how much strategy shifted
- Score = divergence value (higher = more adaptive), capped at 1.0
- Want moderate shift (0.3-0.7 is ideal); too low = rigid, too high = incoherent
- Score function: 1.0 - |divergence - 0.5| × 2  [peaks at 0.5 divergence]

---

### File 5: `state_probes.py` — State Probe Metrics (4.1–4.4)

#### Architecture

State probes are **off-clock questions** injected at specific turns. They require:
1. Pausing the game loop
2. Sending a probe prompt to the LLM (separate from action prompt)
3. Parsing the LLM's response
4. Comparing to ground truth from engine state
5. Resuming the game loop

**Probe injection points:** turns 10, 25, 50, 75, 100 (configurable via `BenchmarkConfig.probe_turns`)

#### Integration with Orchestrator

The orchestrator needs a hook:
```python
# In orchestrator_v2.py _process_turn():
if turn in self._config.probe_turns and self._config.enable_state_probes:
    probe_results = await self._run_state_probes(turn, state)
    self._recorder.record_probes(turn, probe_results)
```

#### Probe Prompts

**4.1 Building Inventory Recall**
- Prompt: "List all your current buildings with their levels and health percentages."
- Ground truth: state.buildings
- Score: F1 between recalled buildings and actual buildings (type+level match)

**4.2 Resource Awareness Accuracy**
- Prompt: "Estimate your current resource levels (food, materials, knowledge, gold)."
- Ground truth: state.resources
- Score: 1.0 - avg(|estimated - actual| / actual) for each resource; ±15% tolerance

**4.3 Strategy Consistency Check**
- Prompt: "In one sentence, what is your current strategy and primary goal?"
- Compare stated strategy to actual action distribution over last 10 turns
- Score: cosine similarity between stated focus area and action vector
- Requires lightweight NLP (keyword extraction from strategy statement)

**4.4 History Event Recall**
- Prompt: "List the major events that have happened so far (catastrophes, trades, milestones)."
- Ground truth: catastrophe events + trade completions from recording
- Score: (correct_events - confabulated_events) / total_actual_events, clamped [0,1]

#### New Schema Additions

```python
@dataclass
class ProbeResult:
    probe_type: str            # "building_recall", "resource_awareness", etc.
    turn: int
    prompt: str
    raw_response: str
    ground_truth: dict
    score: float               # [0.0, 1.0]
    details: dict[str, Any]    # breakdown
```

#### Dependencies
- Requires `LLMAdapter.get_probe_response(prompt, history)` method (new)
- Or reuse `get_action()` with a probe-specific system prompt
- Probe responses don't count toward action token budgets

---

### File 6: `opponent_aware.py` — Opponent-Aware Metrics (5.1–5.5)

#### Cross-Game Nature

These metrics require **multiple GameRecordings** across different opponent types. They use `CrossGameCollector` base.

**Input:** `list[GameRecording]` grouped by opponent_type

#### Metric Algorithms

**5.1 Win Rate vs Archetypes**
- Group recordings by opponent_type
- Win = final_score > opponent_final_score
- Per-archetype win rate, weighted by difficulty:
  - random: 0.5×, greedy: 0.8×, balanced: 1.0×, rush: 1.2×, turtle: 1.0×, adversarial: 2.0×
- Score = weighted_wins / weighted_total, clamped [0, 1]

**5.2 Exploitation Resistance**
- Ratio = avg_score_vs_adversarial / avg_score_vs_balanced
- Score = min(ratio, 1.0)  [1.0 = performs equally well against adversarial]
- If no adversarial games: N/A → 0.5

**5.3 Counter-Strategy Detection Speed**
- For each game: identify turn where LLM's score growth rate exceeds opponent's
- Earlier detection = higher score
- Score = 1.0 - (detection_turn / max_turns), clamped [0, 1]
- Averaged across all games

**5.4 Cooperative Surplus Capture**
- In games with trade offers: measure mutual benefit from accepted trades
- Surplus = (LLM_value_gained + opponent_value_gained) vs no-trade baseline
- Score = min(surplus_captured / max_possible_surplus, 1.0)
- No trade games → 0.5

**5.5 Market Manipulation Detection**
- Detect opponent pump-and-dump patterns (buy heavily → sell after price rise)
- Measure: did LLM avoid buying during pump phase?
- Score = 1.0 - (tokens_lost_to_manipulation / total_gold_spent)
- Requires tracking price movements correlated with opponent actions

---

### File 7: `context_pressure.py` — Context Pressure Metrics (6.1–6.3)

#### Data Available
- `turn.tokens_used` → per-turn token count
- `turn.valid` → per-turn validity
- `turn.latency_ms` → response time
- Cumulative token count → context window pressure

#### Metric Algorithms

**6.1 Per-Quartile Decision Quality**
- Split turns into 4 quartiles (Q1=turns 1-25%, Q2=25-50%, Q3=50-75%, Q4=75-100%)
- Per-quartile: compute valid_rate + action optimality proxy (score_delta per turn)
- Score = Q4_quality / Q1_quality  [1.0 = no degradation]
- Clamped [0, 1.5] then normalized to [0, 1]

**6.2 Historical Reference Rate**
- In Q3+Q4 actions: does reasoning reference early-game context?
- Proxy: check if actions in Q3/Q4 respond to patterns established in Q1/Q2
- Implementation: track if building types started in Q1 are upgraded in Q3/Q4
- Score = (late-game references to early decisions) / (total late-game actions)

**6.3 Context Collapse Point**
- Cumulative tokens per turn → track where valid_rate drops >20% from rolling average
- collapse_turn = first turn where 5-turn rolling valid_rate < 0.8 × overall_valid_rate
- Score = collapse_turn / max_turns  [later collapse = better]
- No collapse → 1.0

---

### File 8: `utils.py` — Shared Helpers

```python
def rolling_average(values: list[float], window: int) -> list[float]: ...
def kendall_tau(actual: list, expected: list) -> float: ...
def jensen_shannon_divergence(p: dict, q: dict) -> float: ...
def normalize_score(value: float, min_val: float, max_val: float) -> float: ...
def detect_change_point(series: list[float], threshold: float) -> int | None: ...
def linear_regression_slope(x: list[float], y: list[float]) -> float: ...
def action_distribution(turns: list[TurnSnapshot]) -> dict[str, float]: ...
def find_catastrophe_turns(recording: GameRecording) -> list[int]: ...
def find_starvation_turns(recording: GameRecording) -> list[int]: ...
def resource_at_turn(recording: GameRecording, turn: int, resource: str) -> float: ...
```

---

### File 9: `__init__.py` — MetricsEngine Facade

```python
class MetricsEngine:
    def __init__(self, config: BenchmarkConfig):
        self._config = config
        self._collectors = [
            PlanningCollector(),
            NumericalCollector(),
            FlexibilityCollector(),
            StateProbeCollector(config),
            ContextPressureCollector(),
        ]
        self._cross_game_collectors = [
            OpponentAwareCollector(),
        ]

    def compute_game_metrics(self, recording: GameRecording) -> dict[str, MetricResult]:
        """Compute all single-game metrics."""
        results = {}
        for collector in self._collectors:
            for result in collector.compute(recording):
                results[result.metric_id] = result
        return results

    def compute_cross_game_metrics(self, recordings: list[GameRecording]) -> dict[str, MetricResult]:
        """Compute metrics requiring multiple recordings."""
        results = {}
        for collector in self._cross_game_collectors:
            for result in collector.compute(recordings):
                results[result.metric_id] = result
        return results

    def compute_all(self, recordings: list[GameRecording]) -> dict[str, MetricResult]:
        """Compute all metrics (per-game averaged + cross-game)."""
        per_game_results: dict[str, list[float]] = {}
        for rec in recordings:
            game_metrics = self.compute_game_metrics(rec)
            for mid, result in game_metrics.items():
                per_game_results.setdefault(mid, []).append(result.value)

        all_results = {}
        for mid, values in per_game_results.items():
            avg = sum(values) / len(values)
            all_results[mid] = MetricResult(metric_id=mid, value=avg, raw_value=avg, sample_count=len(values), details={})

        cross_results = self.compute_cross_game_metrics(recordings)
        all_results.update(cross_results)
        return all_results
```

---

### Implementation Order

| Step | File | Metrics | Dependencies | Est. Tests |
|------|------|---------|-------------|------------|
| 1 | `base.py` + `utils.py` | — | None | 15 |
| 2 | `numerical.py` | 2.1–2.6 | base, utils | 18 |
| 3 | `planning.py` | 1.1–1.6 | base, utils | 18 |
| 4 | `flexibility.py` | 3.1–3.7 | base, utils | 21 |
| 5 | `context_pressure.py` | 6.1–6.3 | base, utils | 12 |
| 6 | `opponent_aware.py` | 5.1–5.5 | base, utils | 15 |
| 7 | `state_probes.py` | 4.1–4.4 | base, utils, adapter hook | 12 |
| 8 | `__init__.py` | facade | all collectors | 8 |

**Total estimated: ~120 tests**

### Rationale for Order
1. **base + utils first** — everything depends on them
2. **numerical next** — simplest metrics, validates data access patterns
3. **planning** — moderate complexity, pure computation from snapshot data
4. **flexibility** — needs catastrophe/starvation detection helpers (utils)
5. **context_pressure** — independent, uses token tracking
6. **opponent_aware** — cross-game, needs multiple recordings
7. **state_probes last** — requires orchestrator integration (probe injection hook)
8. **facade** — ties everything together

---

### Orchestrator Integration Points

#### Required Changes to `orchestrator_v2.py`

1. **State probe hook** (for metrics 4.1–4.4):
   ```python
   if turn in self._config.probe_turns and self._config.enable_state_probes:
       probe_results = await self._state_probe_runner.run_probes(turn, state, self._adapter, self._history)
       self._recorder.record_probes(turn, probe_results)
   ```

2. **Token tracking** (for metrics 6.1–6.3):
   - Already captured in `TurnSnapshot.tokens_used` ✓
   - Need adapter to actually return token counts (currently 0)

3. **No other changes needed** — all other data already in TurnSnapshot via BenchmarkGameState

#### Required Changes to `recorder.py`

1. Add `record_probes(turn, probe_results)` method
2. Add `probes: list[ProbeResult]` field to `GameRecording` schema

#### Required Changes to `schemas.py`

1. Add `ProbeResult` model
2. Add `probes: list[ProbeResult] = []` to `GameRecording`

---

### Key Design Decisions

1. **Normalization:** All metrics → [0.0, 1.0] where 1.0 = perfect, 0.0 = worst
2. **Missing data:** When a metric can't be computed (e.g., no catastrophes for 3.1), return 0.5 (neutral)
3. **Sample count:** Each MetricResult reports how many data points it used, enabling confidence weighting
4. **Deterministic:** All metrics are deterministic given the same GameRecording input
5. **No engine dependency:** Metrics compute from recordings only (no live engine access)
6. **State probes are optional:** Controlled by `config.enable_state_probes`; if disabled, 4.1–4.4 return 0.5

---

## Phase 4D: Tier-2 Dimension Scorers

**Goal:** Compute 8 cognitive dimension scores from Tier-1 `MetricResult` outputs. Each dimension aggregates multiple Tier-1 metrics into a single `DimensionScore` (0.0–1.0) with sub-scores and diagnostic details. Additionally: a composite scorer with 9 weight presets, trend analysis, and archetype classification.

**Status:** COMPLETE (64 tests)

**Input:** `dict[str, MetricResult]` from `MetricsEngine.compute_all()`
**Output:** `DimensionReport` containing 8 `DimensionScore` objects + composite + trend + archetype

---

### Directory Structure

```
terminus/benchmark/
├── scorer.py                   # DimensionScorer facade (consumes Tier-1 → produces Tier-2)
├── dimensions/
│   ├── __init__.py             # Re-exports + DimensionScorer facade
│   ├── base.py                 # DimensionScore model, DimensionComputer ABC
│   ├── coherence.py            # Dim 1: Multi-Decision Coherence + State Fidelity
│   ├── arithmetic.py           # Dim 2: Applied Arithmetic Under Cognitive Load
│   ├── triage.py               # Dim 3: Priority Triage Under Competing Constraints
│   ├── error_recognition.py    # Dim 4: Compounding Error Recognition
│   ├── pivot.py                # Dim 5: Justified Pivot vs Inconsistency
│   ├── degradation.py          # Dim 6: Graceful Degradation + Context Window
│   ├── opportunity.py          # Dim 7: Opportunity Cost Awareness
│   ├── game_theory.py          # Dim 8: Game-Theoretic Sophistication
│   ├── composite.py            # Weighted aggregation + 9 presets
│   ├── trend.py                # Trend analysis + classification
│   └── archetypes.py           # Cross-dimension archetype classification
```

**Tests:**
```
tests/
└── test_dimensions_tier2.py    # All 8 scorers + composite + trend + archetypes (64 tests)
```

---

### File 1: `base.py` — Abstract Base & Data Types

```python
from dataclasses import dataclass, field
from typing import Any
from enum import Enum
from abc import ABC, abstractmethod
from terminus.benchmark.metrics.base import MetricResult
from terminus.benchmark.schemas import GameRecording


class FailureMode(str, Enum):
    STABLE = "stable"
    IMPROVING = "improving"
    LINEAR_DECAY = "linear_decay"
    CLIFF_FAILURE = "cliff_failure"
    OSCILLATING = "oscillating"


class TrendClassification(str, Enum):
    IMPROVING = "improving"
    CONSISTENT = "consistent"
    DEGRADING = "degrading"
    VOLATILE = "volatile"


class ArchetypeLabel(str, Enum):
    PREDATOR = "predator"
    FORTRESS = "fortress"
    DIPLOMAT = "diplomat"
    CHAMELEON = "chameleon"
    SCHOLAR = "scholar"
    PRAGMATIST = "pragmatist"
    CAUTIOUS = "cautious"
    OBLIVIOUS = "oblivious"


@dataclass
class DimensionScore:
    """Score for a single cognitive dimension."""
    dimension_id: str           # e.g. "dim_1_coherence"
    dimension_name: str         # e.g. "Multi-Decision Coherence"
    score: float                # normalized [0.0, 1.0]
    sub_scores: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0     # based on sample counts of input metrics
    contributing_metrics: list[str] = field(default_factory=list)


@dataclass
class DimensionReport:
    """Complete Tier-2 report for a model."""
    model_name: str
    dimensions: dict[str, DimensionScore]  # dimension_id → score
    composite_score: float                  # weighted aggregate
    trend: TrendClassification
    archetype: ArchetypeLabel
    weight_preset: str
    details: dict[str, Any] = field(default_factory=dict)


class DimensionComputer(ABC):
    """Abstract base for computing a single dimension score."""

    dimension_id: str
    dimension_name: str
    required_metrics: list[str]  # Tier-1 metric IDs this dimension needs

    @abstractmethod
    def compute(self, metrics: dict[str, MetricResult], recordings: list[GameRecording]) -> DimensionScore: ...

    def _get_metric_value(self, metrics: dict[str, MetricResult], metric_id: str) -> float:
        """Safely extract metric value, defaulting to 0.5 if missing."""
        if metric_id in metrics:
            return metrics[metric_id].value
        return 0.5

    def _compute_confidence(self, metrics: dict[str, MetricResult]) -> float:
        """Confidence based on how many required metrics have sufficient samples."""
        if not self.required_metrics:
            return 1.0
        available = sum(1 for mid in self.required_metrics if mid in metrics and metrics[mid].sample_count > 0)
        return available / len(self.required_metrics)
```

---

### File 2: `coherence.py` — Dimension 1: Multi-Decision Coherence Decay

#### Input Metrics
- `4.1_building_recall` → state fidelity (inventory)
- `4.2_resource_awareness` → state fidelity (resources)
- `4.3_strategy_consistency` → state fidelity (strategy)
- `4.4_history_recall` → state fidelity (history)

#### Additional Analysis from Recordings
- **Reasoning factor tracking**: Extract top-2 factors per turn from `parsed_response.reasoning.factors`
- **Coherence breaks**: Turns where top factor changes WITHOUT an environmental trigger in prior 5 turns
- **Inflection point detection**: Turn where rolling coherence drops below 0.7

#### Algorithm

```python
def compute(self, metrics, recordings):
    # 1. Action coherence (from reasoning factors)
    action_coherence = triggered_changes / total_transitions if total_transitions > 0 else 1.0

    # 2. Inflection point (later = better)
    inflection_score = inflection_turn / max_turns if inflection_turn else 1.0

    # 3. State fidelity (from probe metrics)
    state_fidelity = get("4.1") * 0.3 + get("4.2") * 0.25 + get("4.3") * 0.25 + get("4.4") * 0.2

    # 4. Integrated coherence
    score = action_coherence * 0.35 + inflection_score * 0.25 + state_fidelity * 0.4
```

#### Sub-scores
- `action_coherence` — proportion of justified factor transitions
- `inflection_point` — normalized turn where coherence starts degrading
- `state_fidelity` — weighted average of 4 probe metrics

#### Environmental Triggers (justify factor changes)
- `last_catastrophe` appears or changes
- Market price change > 30% on any resource
- `resources.food` hits 0
- Any building health drops below 50%
- Population drop > 3 between consecutive turns

---

### File 3: `arithmetic.py` — Dimension 2: Applied Arithmetic Under Cognitive Load

#### Input Metrics
- `2.1_invalid_action_rate` (weight: 2.0)
- `2.2_worker_sum_accuracy` (weight: 1.5)
- `2.3_over_capacity_errors` (weight: 1.0)
- `2.4_production_rate_awareness` (weight: 1.0)
- `2.5_trade_math_accuracy` (weight: 1.0)
- `2.6_multi_resource_feasibility` (weight: 1.5)

#### Algorithm
- Weighted mean → `base_score`
- Load degradation: Q1 valid rate vs Q4 valid rate
- Penalty: `score = base_score * (1.0 - load_degradation * 0.3)`

#### Sub-scores
- `base_accuracy`, `early_load_accuracy`, `late_load_accuracy`, `load_degradation`

---

### File 4: `triage.py` — Dimension 3: Priority Triage Under Competing Constraints

#### Input Metrics
- `3.5_starvation_response_speed`
- `1.4_catastrophe_preparation`
- `3.3_repair_prioritization`
- `1.5_housing_before_growth`

#### Multi-Constraint Detection
Active constraints: starvation, catastrophe_imminent, building_damage, pop_cap, gold_zero, low_morale

#### Priority Order (canonical)
1. Starvation → 2. Catastrophe → 3. Building repair → 4. Pop cap → 5. Gold zero → 6. Low morale

#### Algorithm
```python
score = triage_accuracy * 0.40 + starvation * 0.20 + catastrophe * 0.20 + repair * 0.10 + housing * 0.10
```

---

### File 5: `error_recognition.py` — Dimension 4: Compounding Error Recognition

#### Input Metrics
- `3.5_starvation_response_speed`
- `3.1_post_catastrophe_recovery`
- `1.6_resource_stockpile_timing`

#### Negative Trajectory Detection
- 10-turn rolling slope for each resource
- Flag when projected-to-zero within 20 turns
- Lead time scoring: >15→1.0, 10-15→0.7, 5-10→0.4, 1-5→0.2, 0→0.0

#### Algorithm
```python
score = lead_time * 0.35 + avoidance * 0.25 + starvation * 0.15 + recovery * 0.15 + stockpile * 0.10
```

---

### File 6: `pivot.py` — Dimension 5: Justified Pivot vs Inconsistency

#### Input Metrics
- `3.7_action_distribution_shift`
- `3.2_worker_reallocation_after_damage`

#### Strategy Change Detection
- Top reasoning factor change OR JSD > 0.4 over 5-turn windows
- Trigger correlation: environmental trigger within 5 prior turns
- Missed pivot detection: trigger present but no strategy change within 5 turns

#### Algorithm
```python
score = SNR * 0.50 + (1.0 - missed_penalty) * 0.20 + action_shift * 0.15 + worker_realloc * 0.15
```

---

### File 7: `degradation.py` — Dimension 6: Graceful Degradation + Context Window

#### Input Metrics
- `6.1_per_quartile_quality`
- `6.2_historical_reference_rate`
- `6.3_context_collapse_point`

#### Failure Mode Classification
- Check cliff first (10-turn window mean drop > 0.3), then oscillation (std_windows > 0.15)
- Modes: STABLE, IMPROVING, LINEAR_DECAY, CLIFF_FAILURE, OSCILLATING
- Mode base scores: stable/improving→1.0, oscillating→0.4, cliff→0.2

#### Algorithm
```python
score = base_score * 0.40 + quartile_quality * 0.20 + collapse_point * 0.20 + historical_ref * 0.20
```

---

### File 8: `opportunity.py` — Dimension 7: Opportunity Cost Awareness

#### Input Metrics
- `1.1_build_order_efficiency`
- `1.3_market_timing`
- `1.6_resource_stockpile_timing`
- `3.3_repair_prioritization`

#### Additional Analysis
- Unnecessary PASS rate: PASS when `available_actions > 1`
- Action diversity: Shannon entropy normalized by log2(num_types)

#### Algorithm
```python
score = build * 0.25 + market * 0.20 + stockpile * 0.15 + repair * 0.15 + pass_score * 0.15 + diversity * 0.10
```

---

### File 9: `game_theory.py` — Dimension 8: Game-Theoretic Sophistication

#### Input Metrics
- `5.1_win_rate_vs_archetypes`
- `5.2_exploitation_resistance`
- `5.3_counter_strategy_speed`
- `5.4_cooperative_surplus`
- `5.5_market_manipulation_detection`

#### Additional Analysis
- Strategic diversity: mean pairwise JSD of first-15-turn action distributions across games

#### Algorithm
```python
score = modeling * 0.20 + resistance * 0.25 + diversity * 0.10 + cooperation * 0.15 + market * 0.15 + win_rate * 0.15
```

#### Strategy Profile Classification
| Profile | Criteria |
|---------|----------|
| Oblivious | modeling < 0.3 AND diversity < 0.2 |
| Predator | win_rate > 0.7 AND diversity > 0.5 |
| Fortress | resistance > 0.8 AND cooperative < 0.4 |
| Diplomat | cooperative > 0.7 AND resistance > 0.5 |
| Chameleon | diversity > 0.6 AND modeling > 0.7 |
| Pragmatist | (default) balanced scores |

---

### File 10: `composite.py` — Weighted Composite Scorer

#### 9 Weight Presets

| Preset | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | Focus |
|--------|----|----|----|----|----|----|----|----|-------|
| balanced | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | Equal weight |
| reliability | 1.5 | 2.0 | 1.0 | 1.5 | 0.5 | 2.0 | 0.5 | 0.5 | Low error, stable |
| strategy | 0.5 | 0.5 | 1.5 | 1.0 | 1.5 | 0.5 | 2.0 | 2.0 | Planning + game theory |
| triage | 0.5 | 1.0 | 2.5 | 2.0 | 1.0 | 0.5 | 1.0 | 0.5 | Crisis handling |
| endurance | 2.0 | 1.0 | 0.5 | 1.0 | 0.5 | 2.5 | 0.5 | 0.5 | Long-running stability |
| precision | 0.5 | 2.5 | 0.5 | 0.5 | 0.5 | 0.5 | 2.0 | 0.5 | Math + optimization |
| adversarial | 0.5 | 0.5 | 1.0 | 0.5 | 1.0 | 0.5 | 0.5 | 3.0 | Multi-agent focus |
| coordination | 1.0 | 0.5 | 1.5 | 0.5 | 1.5 | 1.0 | 0.5 | 2.0 | Cooperation + pivot |
| context | 2.0 | 0.5 | 0.5 | 0.5 | 0.5 | 3.0 | 0.5 | 0.5 | Context window focus |

#### Algorithm
Weighted average: `composite = Σ(weight_i × score_i) / Σ(weight_i)` for dimensions present.
Supports custom `DimensionWeights` model (0.0–5.0 per dimension).

---

### File 11: `trend.py` — Trend Analysis

- **Per-dimension trend**: Linear regression slope of per-game scores
  - variance > 0.04 → VOLATILE
  - slope > 0.01 → IMPROVING
  - slope < -0.01 → DEGRADING
  - else → CONSISTENT
- **Overall trend**: Majority vote across per-dimension trends

---

### File 12: `archetypes.py` — Cross-Dimension Archetype Classification

Threshold-based rule classification from dimension scores:

| Archetype | Rule |
|-----------|------|
| Oblivious | triage < 0.3 AND pivot < 0.3 AND game_theory < 0.3 |
| Predator | game_theory > 0.7 AND opportunity > 0.7 |
| Fortress | coherence > 0.7 AND degradation > 0.8 |
| Scholar | coherence > 0.8 AND arithmetic > 0.7 AND opportunity > 0.7 |
| Diplomat | triage > 0.6 AND error_recognition > 0.6 AND pivot > 0.7 |
| Chameleon | pivot > 0.7 AND triage > 0.6 AND error_recognition > 0.6 |
| Cautious | arithmetic > 0.6 AND error_recognition > 0.7 AND degradation > 0.7 |
| Pragmatist | (default) |

---

## Phase 5: Results & Export

**Goal:** Build the complete results aggregation and multi-format export pipeline. Integrates the MetricsEngine + DimensionScorer scoring pipeline into the runner, then exports to JSON/HTML/CSV/Markdown with statistical analysis.

**Reference docs:** [metrics.md](metrics.md) (dimension definitions), Phase 4C/4D (scoring APIs)

**Status:** COMPLETE — pipeline + HTML + JSON + CSV + Markdown + statistical analysis all implemented.

**Final changes (2026-06-05):**
- `terminus/benchmark/results.py` — `BenchmarkResult.from_recordings()` wires MetricsEngine → DimensionScorer
- `terminus/benchmark/export/json_export.py` — full-fidelity JSON with dimensions, metrics, per-game scores
- `terminus/benchmark/export/csv_export.py` — summary (1 row/model) + detailed (1 row/game) modes
- `terminus/benchmark/export/markdown_export.py` — GFM tables with archetype emoji, trend arrows
- `terminus/benchmark/export/statistics.py` — bootstrap 95% CIs + Mann-Whitney U (scipy optional)
- `terminus/benchmark/runner.py` — calls all four exports in `_emit_completed()`, appends stats to markdown

**Dependencies:** Phase 4C (MetricsEngine), Phase 4D (DimensionScorer), Phase 3 (runner produces `list[GameRecording]`)

---

### Critical Gap: Pipeline Integration

Currently `BenchmarkRunner._aggregate_results()` produces basic game stats (scores, valid/invalid counts) but **never invokes MetricsEngine or DimensionScorer**. Phase 5 closes this gap:

```
BenchmarkRunner.run()
  → list[GameRecording]
  → MetricsEngine.compute_all(recordings)          ← NEW (Tier-1 metrics)
  → DimensionScorer.score(metrics, recordings)     ← NEW (Tier-2 dimensions)
  → BenchmarkResult aggregation                     ← NEW (structured results)
  → Export (JSON/HTML/CSV/Markdown)                 ← NEW (multi-format output)
```

---

### Sub-tasks (implementation order):

#### 5.1 — BenchmarkResult Aggregator (`terminus/benchmark/results.py`)

Central data model that holds all computed results for a complete benchmark run.

```python
class ModelResult(BaseModel):
    """Complete results for a single model across all its games."""
    model_name: str
    games_played: int
    recordings: list[GameRecording]

    # Game-level stats
    avg_score: float
    max_score: int
    min_score: int
    score_std: float
    total_valid_actions: int
    total_invalid_actions: int
    valid_rate: float
    dq_count: int
    avg_duration_seconds: float
    total_tokens: int

    # Tier-1 metrics (averaged across games)
    metrics: dict[str, MetricResult]

    # Tier-2 dimensions
    dimension_report: DimensionReport

    # Per-game dimension scores (for trend analysis)
    per_game_dimensions: list[dict[str, float]]


class HeadToHead(BaseModel):
    """Pairwise comparison between two models."""
    model_a: str
    model_b: str
    wins_a: int
    wins_b: int
    draws: int
    avg_score_diff: float
    statistical_significance: float | None  # p-value from Mann-Whitney U


class BenchmarkResult(BaseModel):
    """Complete aggregated results for the entire benchmark run."""
    # Metadata
    run_id: str                            # UUID for this run
    timestamp: str                         # ISO 8601
    config: BenchmarkConfig                # Config used
    elapsed_seconds: float

    # Per-model results
    models: dict[str, ModelResult]         # model_name → ModelResult
    rankings: list[dict[str, Any]]         # Sorted by composite_score

    # Cross-model analysis
    head_to_head: list[HeadToHead]         # Pairwise comparisons
    archetype_distribution: dict[str, int] # archetype → count of models

    # Dimension comparison matrix
    dimension_matrix: dict[str, dict[str, float]]  # model → dim_id → score

    @classmethod
    def from_recordings(
        cls,
        recordings: list[GameRecording],
        config: BenchmarkConfig,
        elapsed_seconds: float,
    ) -> "BenchmarkResult":
        """Build complete results from raw recordings + scoring pipeline."""
        # 1. Group recordings by model
        # 2. Run MetricsEngine.compute_all() per model
        # 3. Run DimensionScorer.score() per model
        # 4. Compute rankings, head-to-head, archetype distribution
        ...
```

**Design decisions:**
- `BenchmarkResult` is a Pydantic model → serializable to JSON via `.model_dump()`
- `from_recordings()` is the factory that runs the full scoring pipeline
- Rankings sorted by composite_score (descending), with tie-breaking by valid_rate
- Head-to-head only computed for games where models share the same opponent+seed
- `recordings` field on `ModelResult` can be excluded from exports via `model_dump(exclude={"recordings"})` for compact output

---

#### 5.2 — Runner Integration (update `terminus/benchmark/runner.py`)

Modify the runner to produce `BenchmarkResult` instead of raw dict.

**Changes:**

```python
# In BenchmarkRunner.run(), after all games complete:
async def run(self) -> BenchmarkResult:
    # ... existing game loop ...

    # NEW: Build full results with scoring pipeline
    result = BenchmarkResult.from_recordings(
        recordings=self._recordings,
        config=self._config,
        elapsed_seconds=time.time() - self._start_time,
    )

    # NEW: Run exports
    await self._export_results(result)

    # Emit event (backward compat: pass legacy dict + full result)
    if self._event_queue:
        await self._event_queue.put(BenchmarkCompleted(
            total_games=len(self._recordings),
            total_turns=sum(len(r.turns) for r in self._recordings),
            elapsed_seconds=result.elapsed_seconds,
            results=self._aggregate_results(),  # legacy dict for TUI compat
            report_path=str(output_dir / "report.html"),
        ))

    return result

async def _export_results(self, result: BenchmarkResult) -> None:
    """Run configured exports."""
    output_dir = Path(self._config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if self._config.export_json:
        export_json(result, output_dir / "results.json")
    if self._config.export_html:
        export_html(result, output_dir / "report.html")
    if self._config.export_csv:
        export_csv(result, output_dir / "results.csv")
    if self._config.export_markdown:
        export_markdown(result, output_dir / "summary.md")
```

**Backward compatibility:**
- `_aggregate_results()` remains for legacy TUI event consumers
- `BenchmarkCompleted.results` still carries the old dict format
- Return type changes from `list[GameRecording]` to `BenchmarkResult`
- Old code accessing `runner.run()` as list must be updated

---

#### 5.3 — Export Dispatcher (`terminus/benchmark/export/__init__.py`)

Central export interface.

```python
from terminus.benchmark.export.json_export import export_json
from terminus.benchmark.export.csv_export import export_csv
from terminus.benchmark.export.html_export import export_html
from terminus.benchmark.export.markdown_export import export_markdown
from terminus.benchmark.export.statistics import compute_statistics

__all__ = [
    "export_json",
    "export_csv",
    "export_html",
    "export_markdown",
    "compute_statistics",
]
```

---

#### 5.4 — JSON Export (`terminus/benchmark/export/json_export.py`)

Full-fidelity export containing everything needed to reproduce analysis.

```python
def export_json(
    result: BenchmarkResult,
    output_path: Path,
    *,
    compact: bool = False,
    include_recordings: bool = True,
) -> Path:
    """Export complete results to JSON.

    Args:
        result: Full benchmark result
        output_path: Destination path
        compact: If True, exclude per-turn state data (reduces file ~10×)
        include_recordings: If False, omit raw GameRecording data entirely

    Returns:
        Absolute path to written file.
    """
```

**JSON Structure:**

```json
{
  "meta": {
    "run_id": "uuid",
    "timestamp": "2025-05-20T14:30:00Z",
    "terminus_version": "1.0.0",
    "elapsed_seconds": 1847.3
  },
  "config": { /* BenchmarkConfig */ },
  "rankings": [
    {
      "rank": 1,
      "model": "gpt-4o",
      "composite_score": 0.82,
      "archetype": "scholar",
      "trend": "consistent",
      "games_played": 30,
      "valid_rate": 0.97
    }
  ],
  "models": {
    "gpt-4o": {
      "dimension_report": { /* DimensionReport */ },
      "metrics": { /* dict[metric_id, MetricResult] */ },
      "game_stats": { /* avg_score, valid_rate, etc. */ },
      "per_game_dimensions": [ /* list of per-game dim scores for trend */ ],
      "recordings": [ /* list[GameRecording] — optional */ ]
    }
  },
  "head_to_head": [ /* HeadToHead comparisons */ ],
  "statistics": { /* CIs, p-values, effect sizes */ }
}
```

**File size considerations:**
- Full export with recordings: ~10-50MB per run (60 games × 100 turns × rich state)
- Compact mode (no per-turn state): ~1-5MB
- Without recordings: ~50-200KB (metrics + dimensions only)

---

#### 5.5 — CSV Export (`terminus/benchmark/export/csv_export.py`)

Tabular format for spreadsheet analysis and pandas import.

```python
def export_csv(
    result: BenchmarkResult,
    output_path: Path,
    *,
    mode: str = "summary",
) -> Path:
    """Export results to CSV.

    Args:
        mode: "summary" (1 row per model) or "detailed" (1 row per game)
    """
```

**Summary mode** (`results_summary.csv`):

| model | composite | archetype | trend | d1_coherence | d2_arithmetic | d3_triage | d4_error | d5_pivot | d6_degradation | d7_opportunity | d8_game_theory | games | valid_rate | avg_score |
|-------|-----------|-----------|-------|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4o | 0.82 | scholar | consistent | 0.91 | 0.88 | 0.76 | 0.79 | 0.82 | 0.85 | 0.78 | 0.71 | 30 | 0.97 | 842 |

**Detailed mode** (`results_detailed.csv`):

| model | game_idx | opponent | seed | score | opp_score | valid_rate | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 | dq |
|-------|----------|----------|------|-------|-----------|---|---|---|---|---|---|---|---|---|---|
| gpt-4o | 1 | balanced | 42 | 892 | 710 | 0.98 | 0.93 | 0.90 | ... | ... | ... | ... | ... | ... | N |

**Implementation:**
- Use Python's `csv.DictWriter` (no pandas dependency)
- Numeric values rounded to 4 decimal places
- Boolean fields encoded as "Y"/"N"
- Header row with descriptive names

---

#### 5.6 — Markdown Export (`terminus/benchmark/export/markdown_export.py`)

Human-readable summary designed for GitHub READMEs, PR descriptions, and documentation.

```python
def export_markdown(
    result: BenchmarkResult,
    output_path: Path,
) -> Path:
    """Export human-readable markdown summary."""
```

**Output structure:**

```markdown
# LLM Benchmark Results

**Run:** 2025-05-20 14:30 UTC | **Duration:** 30m 47s | **Games:** 60

## Rankings

| # | Model | Composite | Archetype | Trend | Win Rate |
|---|-------|-----------|-----------|-------|----------|
| 1 | gpt-4o | 0.82 | 🎓 Scholar | → Consistent | 73% |
| 2 | claude-3.5 | 0.78 | 🏰 Fortress | ↑ Improving | 67% |

## Dimension Scores

| Dimension | gpt-4o | claude-3.5 | delta |
|-----------|--------|------------|-------|
| 1. Coherence | 0.91 | 0.85 | +0.06 |
| 2. Arithmetic | 0.88 | 0.90 | -0.02 |
| ... | ... | ... | ... |

## Head-to-Head

| Matchup | Wins | Losses | Draws |
|---------|------|--------|-------|
| gpt-4o vs claude-3.5 | 18 | 12 | 0 |

## Configuration

- Weight preset: balanced
- Games per matchup: 10
- Max turns: 100
- Opponents: balanced, rush, adversarial
```

**Design decisions:**
- Archetype badges use emoji: 🦅 Predator, 🏰 Fortress, 🤝 Diplomat, 🦎 Chameleon, 🎓 Scholar, ⚖️ Pragmatist, 🛡️ Cautious, 😶 Oblivious
- Trend arrows: ↑ Improving, → Consistent, ↓ Degrading, ↕ Volatile
- Tables use GFM (GitHub Flavored Markdown) pipe syntax
- Delta column highlights biggest advantages/disadvantages
- Keep total output under 200 lines for readability

---

#### 5.7 — HTML Export (`terminus/benchmark/export/html_export.py`)

Interactive self-contained HTML report. Refactors existing `report.py`.

```python
def export_html(
    result: BenchmarkResult,
    output_path: Path,
) -> Path:
    """Export interactive HTML report with embedded charts."""
```

**Approach:** Jinja2 templating with embedded Chart.js (CDN link for interactivity).

**Report sections:**
1. **Header**: Run metadata, timestamp, duration, config summary
2. **Rankings table**: Sortable, color-coded by archetype
3. **Radar chart**: 8-dimension comparison across all models (Chart.js radar)
4. **Score progression**: Line chart showing per-game composite scores over time
5. **Dimension breakdown**: Per-model expandable sections with sub-scores
6. **Head-to-head matrix**: Win/loss/draw grid
7. **Statistical summary**: Confidence intervals, significance markers
8. **Archetype gallery**: Visual archetype badges with dimension profile explanations

**Template structure:**
```
terminus/benchmark/export/templates/
├── report.html.j2          # Main report template
├── components/
│   ├── rankings.html.j2    # Rankings table partial
│   ├── radar.html.j2       # Radar chart partial (Chart.js)
│   ├── dimensions.html.j2  # Dimension breakdown partial
│   └── head2head.html.j2   # Head-to-head matrix partial
```

**Self-contained:** Single HTML file with inline CSS + JS. Chart.js loaded from CDN (`<script src="https://cdn.jsdelivr.net/npm/chart.js">`). Works offline except for CDN scripts — fallback: render static tables if CDN unavailable.

**Backward compatibility:** Keep `terminus/benchmark/report.py` as a thin wrapper:
```python
def generate_report(results: dict[str, Any], config: dict[str, Any], output_path: str) -> str:
    """Legacy API — delegates to new export system."""
    # Convert legacy dict to BenchmarkResult (best-effort)
    # Call export_html()
    # Return path
```

---

#### 5.8 — Statistical Analysis (`terminus/benchmark/export/statistics.py`)

Provides statistical rigor for cross-model comparisons.

```python
def compute_statistics(result: BenchmarkResult) -> StatisticalReport:
    """Compute confidence intervals, significance tests, and effect sizes."""


@dataclass
class DimensionCI:
    """Confidence interval for a dimension score."""
    dimension_id: str
    mean: float
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    n_games: int


@dataclass
class PairwiseComparison:
    """Statistical comparison between two models on one dimension."""
    dimension_id: str
    model_a: str
    model_b: str
    mean_diff: float
    p_value: float         # Mann-Whitney U
    effect_size: float     # Cohen's d
    significant: bool      # p < 0.05


@dataclass
class StatisticalReport:
    """Complete statistical analysis."""
    confidence_intervals: dict[str, list[DimensionCI]]  # model → per-dim CIs
    pairwise_comparisons: list[PairwiseComparison]
    overall_significance: float  # Kruskal-Wallis across all models
```

**Methods:**

| Analysis | Method | When |
|----------|--------|------|
| Confidence intervals | Bootstrap (n=1000) or normal approx if n>30 | Always |
| Pairwise comparison | Mann-Whitney U (non-parametric) | 2+ models |
| Multi-model comparison | Kruskal-Wallis H-test | 3+ models |
| Effect size | Cohen's d (mean diff / pooled SD) | Always |
| Multiple testing correction | Bonferroni | 3+ comparisons |

**Dependency:** `scipy` for Mann-Whitney and Kruskal-Wallis. If scipy unavailable, fall back to:
- Bootstrap CI (pure Python, no scipy needed)
- Skip significance tests, report "scipy not installed" in output
- Effect size computed manually (no scipy required)

```python
try:
    from scipy import stats as scipy_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
```

---

#### 5.9 — Schema Updates (`terminus/benchmark/schemas.py`)

Add export configuration fields to `BenchmarkConfig`:

```python
class BenchmarkConfig(BaseModel):
    # ... existing fields ...

    # Output & Export
    output_dir: str = "./benchmark-results"
    export_json: bool = True
    export_html: bool = True
    export_csv: bool = True           # NEW
    export_markdown: bool = True      # NEW
    export_compact_json: bool = False  # NEW — omit per-turn state from JSON
```

---

#### 5.10 — Tests (`tests/test_results_export.py`)

```python
class TestBenchmarkResult:
    def test_from_recordings_runs_scoring_pipeline(self): ...
    def test_rankings_sorted_by_composite(self): ...
    def test_head_to_head_correct(self): ...
    def test_empty_recordings(self): ...
    def test_single_model(self): ...

class TestJsonExport:
    def test_full_export_round_trip(self): ...
    def test_compact_mode_smaller(self): ...
    def test_without_recordings(self): ...
    def test_output_is_valid_json(self): ...

class TestCsvExport:
    def test_summary_mode_one_row_per_model(self): ...
    def test_detailed_mode_one_row_per_game(self): ...
    def test_header_matches_data_columns(self): ...
    def test_numeric_precision(self): ...

class TestMarkdownExport:
    def test_contains_rankings_table(self): ...
    def test_contains_dimension_table(self): ...
    def test_archetype_emojis(self): ...
    def test_gfm_table_format(self): ...

class TestHtmlExport:
    def test_produces_valid_html(self): ...
    def test_contains_chart_js_reference(self): ...
    def test_all_models_present(self): ...
    def test_legacy_generate_report_works(self): ...

class TestStatistics:
    def test_confidence_intervals_contain_mean(self): ...
    def test_pairwise_p_values_bounded(self): ...
    def test_effect_size_positive_when_a_better(self): ...
    def test_no_scipy_fallback(self): ...
    def test_bonferroni_correction_applied(self): ...
```

---

### File Structure (final):

```
terminus/benchmark/
├── results.py                   # NEW: BenchmarkResult + ModelResult + from_recordings()
├── runner.py                    # UPDATED: calls scoring pipeline + exports
├── report.py                    # KEPT: thin backward-compat wrapper → export/html_export
├── export/
│   ├── __init__.py              # NEW: re-exports all export functions
│   ├── json_export.py           # NEW: full-fidelity JSON export
│   ├── csv_export.py            # NEW: summary + detailed CSV modes
│   ├── markdown_export.py       # NEW: GFM summary with emoji badges
│   ├── html_export.py           # NEW: Jinja2 + Chart.js interactive report
│   ├── statistics.py            # NEW: CIs, Mann-Whitney, effect sizes
│   └── templates/
│       ├── report.html.j2       # NEW: main HTML template
│       └── components/
│           ├── rankings.html.j2     # NEW
│           ├── radar.html.j2        # NEW
│           ├── dimensions.html.j2   # NEW
│           └── head2head.html.j2    # NEW
├── schemas.py                   # UPDATED: add export_csv, export_markdown, export_compact_json
├── metrics/__init__.py          # (Phase 4C — unchanged, consumed by results.py)
├── dimensions/__init__.py       # (Phase 4D — unchanged, consumed by results.py)

tests/
└── test_results_export.py       # NEW: ~35-40 tests
```

---

### Dependencies:

```toml
# Add to pyproject.toml [project.dependencies]
jinja2 >= 3.1.0     # HTML report templating

# Add to pyproject.toml [project.optional-dependencies]
stats = ["scipy >= 1.11.0"]   # Statistical tests (optional)
```

---

### Integration Points:

1. **Runner (Phase 3)**: `BenchmarkRunner.run()` now calls `BenchmarkResult.from_recordings()` which internally invokes MetricsEngine + DimensionScorer. Return type changes to `BenchmarkResult`.
2. **MetricsEngine (Phase 4C)**: `compute_all(recordings)` produces `dict[str, MetricResult]` per model — called inside `BenchmarkResult.from_recordings()`.
3. **DimensionScorer (Phase 4D)**: `score(metrics, recordings, model_name)` produces `DimensionReport` — called per model inside `from_recordings()`.
4. **BenchmarkCompleted event**: Legacy `results` dict maintained for backward compat with TUI `benchmark_progress.py`. New code should use `BenchmarkResult` directly.
5. **report.py**: Existing legacy callers still work — `generate_report()` wraps `export_html()` with dict-to-model conversion.
6. **BenchmarkConfig**: `output_dir` controls where all exports write. Export flags (json/html/csv/markdown) control which formats are produced.

---

### Implementation Order:

| Step | File | Dependencies | Est. Tests |
|------|------|-------------|------------|
| 1 | `results.py` | MetricsEngine, DimensionScorer | 5 |
| 2 | `runner.py` (update) | results.py | 2 |
| 3 | `export/__init__.py` | — | 0 |
| 4 | `export/json_export.py` | results.py | 4 |
| 5 | `export/csv_export.py` | results.py | 4 |
| 6 | `export/markdown_export.py` | results.py | 4 |
| 7 | `export/statistics.py` | results.py, scipy (optional) | 5 |
| 8 | `export/html_export.py` + templates | results.py, jinja2 | 4 |
| 9 | `report.py` (refactor to wrapper) | export/html_export | 2 |
| 10 | `schemas.py` (add fields) | — | 2 |
| 11 | `tests/test_results_export.py` | all above | ~35 |

**Total estimated: ~35-40 new tests**

### Rationale for Order:
1. **results.py first** — central model that all exporters consume
2. **runner.py next** — wires scoring pipeline into the run loop
3. **JSON export** — simplest format, validates result serialization works
4. **CSV export** — tabular, good for debugging dimension scores
5. **Markdown** — human-readable, useful for CI output
6. **Statistics** — can be developed in parallel with formats
7. **HTML last** — most complex (templates, Chart.js), depends on statistics for significance markers
8. **report.py refactor** — thin wrapper, minimal risk

---

### Acceptance Criteria:

- [ ] `BenchmarkResult.from_recordings()` correctly invokes MetricsEngine → DimensionScorer pipeline
- [ ] Rankings sort by composite_score with correct tie-breaking
- [ ] JSON export round-trips: write → read back → validate all fields match
- [ ] JSON compact mode produces file <10% the size of full mode
- [ ] CSV summary mode: exactly 1 row per model, all dimensions as columns
- [ ] CSV detailed mode: 1 row per game, loadable by `csv.DictReader`
- [ ] Markdown output renders correctly on GitHub (pipe tables, emoji)
- [ ] HTML report is self-contained (single file, inline CSS)
- [ ] HTML radar chart renders all 8 dimensions per model
- [ ] Statistical CIs contain the sample mean in all test cases
- [ ] Mann-Whitney p-values are in [0, 1] range
- [ ] Graceful fallback when scipy not installed (no crash, warning logged)
- [ ] Legacy `generate_report()` still works with old dict format
- [ ] `BenchmarkCompleted` event still carries legacy results dict for TUI compat
- [ ] All exports write to `config.output_dir` with correct filenames
- [ ] Full test suite passes (existing 577 + new ~35 = ~612 tests)

---

## Phase 6: CLI & TUI Integration

**Goal:** Wire benchmark into the existing game interface.

**Status:** COMPLETE — all TUI screens wired, CLI headless mode, `--benchmark` → TUI, export buttons in results screen.

### Task Status:
- [x] 1. "LLM Benchmark" in main TUI menu — was already present
- [x] 2. Benchmark setup screen (`benchmark_setup.py`) — `build_benchmark_config()` added
- [x] 3. Live progress screen (`benchmark_live.py`) — wired to `BenchmarkRunner`, shows reasoning + opponent score + trade activity
- [x] 4. Results dashboard screen (`benchmark_results.py`) — real 8-dimension scores, composite, archetype, trend, export buttons
- [x] 5. Export buttons — [Open CSV] and [Open JSON] buttons in results screen
- [x] 6. `--benchmark CONFIG` CLI flag for headless runs — prints all export file paths
- [x] 7. `--benchmark` with no file → launches TUI benchmark setup screen directly
- [ ] 8. Secure API key handling via keyring — env vars supported; keyring not implemented (deferred)

### Phase D Changes (completed 2026-06-05):
- `terminus/__main__.py`: Added `--benchmark CONFIG` flag. `_run_benchmark_headless()` loads and validates `BenchmarkConfig` from the JSON path, prints a banner with run summary, then calls `_benchmark_async()`. `_benchmark_async()` runs `BenchmarkRunner` and an event consumer concurrently — turn progress overwrites the current line via `\r`, game completions print a full line with score/turns/valid%, catastrophes are annotated inline. `BenchmarkCompleted` breaks the consumer loop and prints the final summary with the report path.
- `benchmark-config.example.json`: New example config at repo root showing all key fields with comments.

### Remaining files from original plan:
```
terminus/client/screens/
└── benchmark_export.py      # Export dialog — NOT STARTED

terminus/client/widgets/
├── radar_chart.py           # ASCII radar chart widget — NOT STARTED
├── dimension_table.py       # Colored dimension comparison table — NOT STARTED
└── progress_bar.py          # Benchmark-specific progress display — NOT STARTED
```

---

## Phase 7: Testing & Verification

**Goal:** Ensure correctness of metrics, integration, and edge cases.

**Status:** COMPLETE (17 integration tests, 594 total tests passing)

**Phase 7 changes (2026-06-05):**
- `tests/test_benchmark_integration.py` — NEW: 17 tests across 4 classes:
  - `TestEndToEndPipeline` (5 tests): single game → recording → MetricsEngine → DimensionScorer → BenchmarkResult, runner event emission
  - `TestHtmlReportGeneration` (5 tests): HTML written to `tmp_path`, model name present, dimension table present, `report_path` in event, `write_report()` standalone
  - `TestAgentSanityCheck` (3 tests): all 6 opponent archetypes produce valid recordings, BUILD actions are recorded, sanity checks on scoring
  - `TestCLIHeadless` (4 tests): missing file → exit 1, invalid JSON → exit 1, invalid config → exit 1, example config validates cleanly
- Also fixed a critical bug: `runner.py` had a duplicate old `run()` method (lines 313–382) left over from the Phase B edit that was shadowing the new pipeline-wired version. Removed the duplicate — the old `_aggregate_results()` method was winning over `_emit_completed()`, so the HTML report was never being written and `report_path` was always `None`.

**Task Status:**
- [x] 1. Unit tests for Tier 1 metrics — `tests/test_metrics_tier1.py` (65 tests)
- [x] 2. Unit tests for Tier 2 dimension scorers — `tests/test_dimensions_tier2.py` (64 tests)
- [x] 3. Integration test: headless game with mock LLM → full pipeline — `tests/test_benchmark_integration.py`
- [x] 4. HTML report written and non-empty — `TestHtmlReportGeneration`
- [x] 5. Agent sanity checks — `TestAgentSanityCheck`
- [x] 6. All 6 opponent archetypes produce valid recordings — `test_all_opponent_types_produce_valid_recordings`
- [x] 7. CLI error handling verified — `TestCLIHeadless`
- [ ] Regression tests: fixed seed → identical recordings (deferred — not blocking)
- [ ] Performance test: 100-turn game < 5 min with local model (deferred — requires Ollama)

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
