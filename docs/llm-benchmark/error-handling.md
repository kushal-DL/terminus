# LLM Benchmark — Error Handling & Recovery

This document specifies every failure mode the benchmark orchestrator must handle, the recovery policy for each, how failures affect scoring, and when a model is disqualified.

---

## Design Principles

1. **Never crash the benchmark** — every error is caught, logged, and recovered from.
2. **Fairness** — all models face the same retry/timeout/penalty rules.
3. **Signal preservation** — errors themselves are data. A model that produces more invalid JSON is worse at structured output, and that should be measurable.
4. **Minimal retries** — retries cost time and money. Only retry when there's reasonable hope the model will self-correct.
5. **Deterministic fallback** — when recovery fails, the fallback action is always PASS (do nothing). This is the safest no-op that keeps the game valid.

---

## Error Taxonomy

| # | Error Class | Source | Retryable | Max Retries | Fallback |
|---|-------------|--------|-----------|-------------|----------|
| E1 | Malformed JSON | LLM output | Yes | 3 | PASS |
| E2 | Schema violation | LLM output | Yes | 2 | PASS |
| E3 | Invalid game action | Engine rejection | No | 0 | Record as invalid |
| E4 | Response timeout | Network/model | Yes | 1 | PASS |
| E5 | Rate limit (429) | API provider | Yes (wait) | 5 | Abort game |
| E6 | API error (5xx) | API provider | Yes (backoff) | 3 | PASS |
| E7 | Context length exceeded | API provider | No | 0 | Truncate + retry once |
| E8 | Content refusal | Safety filter | No | 0 | PASS + flag |
| E9 | Empty response | LLM output | Yes | 2 | PASS |
| E10 | Connection failure | Network | Yes (backoff) | 3 | Abort game |

---

## Detailed Error Specifications

### E1: Malformed JSON

**Detection:** Response cannot be parsed by `json.loads()`.

**Examples:**
- Markdown code fences wrapping JSON: `` ```json {...} ``` ``
- Trailing commas: `{"action": "BUILD",}`
- Natural language before/after JSON: `"Sure! Here's my action: {...}"`
- Truncated response (hit max_tokens mid-JSON)

**Recovery flow:**

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ LLM Response│────►│ JSON Parse Error  │────►│ Retry Prompt    │
│ (invalid)   │     │ detected          │     │ with error msg  │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │ Attempt 2/3     │
                                              │ Still invalid?  │
                                              └────────┬────────┘
                                                       │ Yes
                                              ┌────────▼────────┐
                                              │ PASS fallback   │
                                              │ + record error  │
                                              └─────────────────┘
```

**Retry prompt (appended to conversation):**

```
Your previous response was not valid JSON. The parser returned:
  {error_message}

Please respond with ONLY a JSON object matching this schema:
{
  "action": "BUILD|UPGRADE|ALLOCATE_WORKERS|TRADE_BUY|TRADE_SELL|DEMOLISH|REPAIR|PASS",
  "params": { ... },
  "reasoning": "brief explanation"
}

Do not include markdown formatting, code fences, or any text outside the JSON object.
```

**Extraction attempt before retry:** Before counting as a parse failure, attempt to extract JSON from common wrappers:

```python
def extract_json(raw: str) -> dict | None:
    """Try to extract JSON from common LLM output patterns."""
    # Strip markdown code fences
    if "```" in raw:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    
    # Find first { ... } block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    
    return None  # Truly unparseable → trigger retry
```

**Scoring impact:**
- Each malformed response (before extraction saves it) increments `json_errors` counter
- Successfully extracted responses (from wrappers) increment `json_extracted` counter (no penalty)
- Final metric: `json_compliance_rate = 1 - (json_errors / total_turns)`

---

### E2: Schema Violation

**Detection:** JSON parses successfully but doesn't match `ActionResponse` schema.

**Examples:**
- Missing required field: `{"action": "BUILD"}` (no `params`)
- Invalid action type: `{"action": "CONSTRUCT", ...}`
- Wrong param types: `{"action": "BUILD", "params": {"building_type": 123}}`
- Extra nesting: `{"response": {"action": "BUILD", ...}}`

**Recovery flow:**

```python
def validate_response(data: dict) -> ActionResponse | ValidationError:
    # Attempt 1: Direct validation
    try:
        return ActionResponse.model_validate(data)
    except ValidationError as e:
        pass
    
    # Attempt 2: Unwrap common nesting patterns
    for key in ["response", "action_response", "result", "output"]:
        if key in data and isinstance(data[key], dict):
            try:
                return ActionResponse.model_validate(data[key])
            except ValidationError:
                pass
    
    # Attempt 3: Coerce known issues
    if "action" in data:
        # Normalize action name (lowercase → uppercase)
        data["action"] = data["action"].upper().replace(" ", "_")
        # Add empty params if missing
        if "params" not in data:
            data["params"] = {}
        # Add default reasoning if missing
        if "reasoning" not in data:
            data["reasoning"] = ""
        try:
            return ActionResponse.model_validate(data)
        except ValidationError as e:
            return e
    
    return ValidationError("No 'action' field found")
```

**Retry prompt:**

```
Your response was valid JSON but doesn't match the required schema.
Validation error: {validation_error_message}

Required schema:
{
  "action": one of "BUILD", "UPGRADE", "ALLOCATE_WORKERS", "TRADE_BUY", "TRADE_SELL", "DEMOLISH", "REPAIR", "PASS",
  "params": { action-specific parameters },
  "reasoning": "string explaining your decision"
}

For BUILD/UPGRADE/DEMOLISH/REPAIR: params = {"building_type": "farm|mine|laboratory|market|hospital|wall|warehouse|housing|school|watchtower"}
For ALLOCATE_WORKERS: params = {"farming": int, "mining": int, "research": int, "construction": int, "defense": int, "medicine": int}
For TRADE_BUY/TRADE_SELL: params = {"resource": "food|materials|knowledge", "quantity": int}
For PASS: params = {}
```

**Max retries:** 2 (schema errors are harder to self-correct than JSON syntax)

**Scoring impact:** Increments `schema_errors` counter. Included in `structured_output_rate`.

---

### E3: Invalid Game Action

**Detection:** `engine.handle_action()` raises `ValueError`.

**Examples:**
- Building already exists
- Insufficient resources
- Worker allocation doesn't sum to population
- Upgrading a building under construction

**Policy: NO RETRY.** The model made a strategically incorrect decision. This is a signal about the model's ability to reason about game state, not a formatting issue. Retrying would mask the error.

**Handling:**

```python
try:
    await engine.handle_action(player_id, action_type, params)
    turn_result = TurnResult(valid=True, action_applied=True)
except ValueError as e:
    turn_result = TurnResult(
        valid=False,
        action_applied=False,
        rejection_reason=str(e),
        error_class="E3_INVALID_ACTION"
    )
    # Action is NOT applied. Game state unchanged.
    # Turn still counts — the model wasted its action.
```

**Scoring impact:**
- Increments `invalid_actions` counter
- Contributes to `action_validity_rate = valid_actions / total_actions`
- Consecutive invalid actions tracked for disqualification (see DQ rules)
- Each invalid action is categorized by root cause for diagnostics:
  - `RESOURCE_ERROR` — tried to spend more than available
  - `STATE_ERROR` — building doesn't exist, already at max, etc.
  - `ARITHMETIC_ERROR` — worker sum doesn't match population
  - `LOGIC_ERROR` — other (demolish during construction, etc.)

---

### E4: Response Timeout

**Detection:** LLM API call exceeds configured timeout.

**Configuration:**

```python
class TimeoutConfig(BaseModel):
    first_response_timeout: int = 30_000   # ms — initial response
    retry_timeout: int = 20_000            # ms — retry attempts (shorter)
    total_turn_budget: int = 60_000        # ms — absolute max per turn including retries
```

**Policy:**
- If first attempt times out: retry once with same prompt (model may have had a cold start)
- If retry also times out: PASS fallback
- If `total_turn_budget` exceeded at any point: immediate PASS, no more retries

**Scoring impact:**
- Increments `timeouts` counter
- Contributes to `response_reliability = 1 - (timeouts + empty_responses) / total_turns`
- Latency still recorded as `timeout_value` for percentile calculations (censored data point)

---

### E5: Rate Limit (HTTP 429)

**Detection:** API returns 429 status code with `Retry-After` header.

**Policy:**
- Wait for `Retry-After` duration (or default 60s if header missing)
- Retry up to 5 times with exponential backoff: `wait × 2^attempt`
- If 5 consecutive rate limits: abort current game, mark as `RATE_LIMITED`
- Rate limit time does NOT count toward turn timeout

**Implementation:**

```python
async def call_with_rate_limit_handling(
    adapter: LLMAdapter,
    prompt: list[Message],
    max_retries: int = 5
) -> str | RateLimitAbort:
    for attempt in range(max_retries):
        try:
            return await adapter.generate(prompt)
        except RateLimitError as e:
            wait_time = e.retry_after or (60 * (2 ** attempt))
            logger.warning(f"Rate limited. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait_time)
    
    return RateLimitAbort(total_wait=sum(60 * (2**i) for i in range(max_retries)))
```

**Game impact:** If a game is aborted due to rate limiting:
- Game is excluded from scoring (not fair to penalize the model)
- Logged as `game_status: "rate_limited"`
- Orchestrator pauses before starting next game for that model
- If 3+ games are rate-limited: halt benchmark for that model, report partial results

---

### E6: API Error (5xx)

**Detection:** HTTP 500, 502, 503, or other server-side errors.

**Policy:**
- Retry with exponential backoff: 1s, 2s, 4s
- Max 3 retries
- If all fail: PASS fallback for this turn

**Scoring impact:** Same as timeout — increments `api_errors` counter, affects `response_reliability`.

---

### E7: Context Length Exceeded

**Detection:** API returns error indicating prompt exceeds model's context window. Common error patterns:
- OpenAI: `"maximum context length is X tokens"`
- Anthropic: `"prompt is too long: X tokens > Y maximum"`
- Google: `"content too long"`

**Policy:** This is NOT retried with the same prompt. Instead:

```
1. Detect context overflow
2. Truncate conversation history (keep system prompt + last 3 turns + current state)
3. Retry ONCE with truncated prompt
4. If still fails: PASS fallback (model's context is too small for even minimal prompt)
```

**Truncation strategy:**

```python
def truncate_for_context(
    messages: list[Message],
    max_tokens: int,
    model_context_limit: int
) -> list[Message]:
    """Emergency truncation when context is exceeded."""
    # Always keep: system prompt (index 0) + current turn (last message)
    system = messages[0]
    current = messages[-1]
    
    # Estimate tokens for fixed parts
    fixed_tokens = estimate_tokens(system) + estimate_tokens(current) + 200  # buffer
    remaining = model_context_limit - fixed_tokens
    
    # Fill remaining with most recent history (newest first)
    history = messages[1:-1]
    kept_history = []
    for msg in reversed(history):
        msg_tokens = estimate_tokens(msg)
        if remaining - msg_tokens < 0:
            break
        kept_history.insert(0, msg)
        remaining -= msg_tokens
    
    return [system] + kept_history + [current]
```

**Scoring impact:**
- Increments `context_truncations` counter
- Tracked per-turn: which turns required truncation
- Correlates with Dimension 6 (Graceful Degradation) — models that need truncation earlier score lower

---

### E8: Content Refusal

**Detection:** Model refuses to generate a game action, typically returning safety-filter responses:
- `"I cannot assist with that"`
- `"I'm not able to provide..."`
- Response contains no JSON and matches refusal patterns

**Detection heuristics:**

```python
REFUSAL_PATTERNS = [
    r"I (?:cannot|can't|won't|am unable to)",
    r"I'm (?:sorry|afraid|not able)",
    r"(?:violates|against) (?:my|our) (?:policy|guidelines)",
    r"(?:inappropriate|harmful|offensive)",
    r"as an AI",
]

def is_refusal(response: str) -> bool:
    """Detect safety-filter refusals."""
    if any(re.search(p, response, re.IGNORECASE) for p in REFUSAL_PATTERNS):
        # Confirm it's not just the model explaining its reasoning about in-game actions
        if "{" not in response:  # No JSON present at all
            return True
    return False
```

**Policy:**
- No retry (refusals are typically deterministic at temperature=0.3)
- Count as PASS
- Flag for human review (the system prompt should not trigger safety filters for a colony-building game, but edge cases exist — e.g., "raiders" catastrophe language)

**Scoring impact:**
- Increments `refusals` counter
- If `refusals > 5` in a single game: flag in results report
- Does NOT trigger disqualification (it's the model being overly cautious, not broken)

---

### E9: Empty Response

**Detection:** API returns successfully but response body is empty string or whitespace-only.

**Policy:**
- Retry up to 2 times (empty responses are often transient)
- If still empty: PASS fallback

**Scoring impact:** Same as timeout.

---

### E10: Connection Failure

**Detection:** Network-level errors — DNS resolution failure, TCP connection refused, TLS errors.

**Policy:**
- Retry with exponential backoff: 2s, 4s, 8s
- Max 3 retries
- If all fail: abort game, mark as `CONNECTION_FAILURE`
- Connection failures affect all models equally (usually means local network is down)

**Game impact:** Same as rate limit abort — game excluded from scoring.

---

## Retry Budget & Turn Cost

Each turn has a **total cost budget** that limits how much can be spent on retries:

```python
class TurnBudget(BaseModel):
    max_llm_calls: int = 4          # Original + up to 3 retries
    max_wall_time_ms: int = 60_000  # 60s absolute cap per turn
    max_retry_tokens: int = 2000    # Max tokens spent on retry prompts (not counted in model billing)
```

**Cost tracking per turn:**

```python
@dataclass
class TurnCost:
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_time_ms: int = 0
    retries_used: int = 0
    
    @property
    def budget_exhausted(self) -> bool:
        return (
            self.llm_calls >= 4 or
            self.wall_time_ms >= 60_000
        )
```

---

## Disqualification Rules

A model is disqualified from a **single game** (not the entire benchmark) if it demonstrates persistent inability to produce valid actions.

### DQ Triggers

| Rule | Threshold | Consequence |
|------|-----------|-------------|
| Consecutive invalid actions | 10 in a row | DQ from current game |
| Total error rate | >80% of turns are errors | DQ from current game |
| Consecutive PASS-by-fallback | 15 in a row | DQ from current game |
| Consecutive timeouts | 5 in a row | DQ from current game |

### DQ Handling

```python
class DisqualificationTracker:
    def __init__(self):
        self.consecutive_invalid = 0
        self.consecutive_fallback_pass = 0
        self.consecutive_timeouts = 0
        self.total_errors = 0
        self.total_turns = 0
    
    def record_turn(self, result: TurnResult) -> bool:
        """Returns True if model should be disqualified."""
        self.total_turns += 1
        
        if result.valid and result.action_applied:
            # Reset consecutive counters on success
            self.consecutive_invalid = 0
            self.consecutive_fallback_pass = 0
            self.consecutive_timeouts = 0
        elif result.error_class == "E3_INVALID_ACTION":
            self.consecutive_invalid += 1
            self.consecutive_fallback_pass = 0
            self.total_errors += 1
        elif result.error_class == "E4_TIMEOUT":
            self.consecutive_timeouts += 1
            self.consecutive_fallback_pass += 1
            self.total_errors += 1
        elif result.fallback_used:
            self.consecutive_fallback_pass += 1
            self.total_errors += 1
        
        # Check DQ conditions
        if self.consecutive_invalid >= 10:
            return True
        if self.consecutive_fallback_pass >= 15:
            return True
        if self.consecutive_timeouts >= 5:
            return True
        if self.total_turns >= 20 and (self.total_errors / self.total_turns) > 0.80:
            return True
        
        return False
```

### DQ Scoring

When a model is disqualified mid-game:
- Game is scored at the point of DQ (not excluded)
- All remaining turns are scored as 0 (no actions taken)
- Final game score reflects the DQ penalty naturally (colony stagnates/collapses)
- `game_status` marked as `"disqualified"`
- DQ turn number recorded for diagnostics

---

## Error Logging Schema

Every error is logged with full context for debugging and analysis:

```python
class ErrorLog(BaseModel):
    game_id: str
    turn: int
    player_id: str
    model_id: str
    timestamp: datetime
    error_class: str                    # "E1" through "E10"
    error_message: str                  # Human-readable description
    raw_response: str | None            # Full LLM output (for E1/E2/E8/E9)
    retry_attempt: int                  # 0 = first try, 1+ = retry
    resolved: bool                      # Did retry succeed?
    resolution: str                     # "retry_success", "fallback_pass", "dq", "abort"
    latency_ms: int                     # Time taken for this attempt
    token_usage: TokenUsage | None      # Input/output tokens consumed
    context_length_at_error: int | None # For E7: how many tokens were in the prompt
```

---

## Error Recovery Prompts (Complete Set)

### After E1 (Malformed JSON) — Retry 1

```
ERROR: Your response was not valid JSON.
Parse error: {json_error_message}

Respond with ONLY a JSON object. No markdown, no explanation outside the JSON.
Example: {"action": "BUILD", "params": {"building_type": "farm"}, "reasoning": "Need food production"}
```

### After E1 (Malformed JSON) — Retry 2

```
ERROR: Still not valid JSON. This is attempt 3 of 3.

RESPOND WITH EXACTLY ONE LINE containing a JSON object:
{"action": "PASS", "params": {}, "reasoning": "your reason here"}

Replace "PASS" with your chosen action if you want to do something else.
```

### After E1 (Malformed JSON) — Retry 3 (Final)

```
FINAL ATTEMPT. Respond with valid JSON or your turn will be skipped.
Minimum valid response: {"action": "PASS", "params": {}, "reasoning": "skip"}
```

### After E2 (Schema Violation)

```
ERROR: Your JSON was parseable but doesn't match the required format.
Issue: {validation_error}

Required format:
{"action": "<ACTION_TYPE>", "params": {<action_params>}, "reasoning": "<explanation>"}

Valid action types: BUILD, UPGRADE, ALLOCATE_WORKERS, TRADE_BUY, TRADE_SELL, DEMOLISH, REPAIR, PASS
```

### After E4 (Timeout) — Retry

```
[No additional prompt — same prompt is resent. The timeout is a network/latency issue, not a prompt issue.]
```

### After E7 (Context Overflow) — Truncated Retry

```
[System note: Conversation history has been truncated to fit within context limits. Only the most recent turns are shown. Full game state is current as of this turn.]
```

---

## Aggregate Error Metrics (Per Model)

After all games complete, compute these error-related metrics:

```python
class ErrorMetrics(BaseModel):
    # Raw counts
    total_turns: int
    total_errors: int
    json_errors: int                    # E1 (after extraction attempt)
    schema_errors: int                  # E2 (after coercion attempt)  
    invalid_actions: int                # E3
    timeouts: int                       # E4
    api_errors: int                     # E5 + E6
    context_truncations: int            # E7
    refusals: int                       # E8
    empty_responses: int                # E9
    
    # Rates (0.0 to 1.0, higher is better)
    json_compliance_rate: float         # 1 - json_errors / total_turns
    schema_compliance_rate: float       # 1 - schema_errors / total_turns
    action_validity_rate: float         # valid_actions / total_actions_attempted
    response_reliability: float         # 1 - (timeouts + empty) / total_turns
    overall_success_rate: float         # turns_with_valid_applied_action / total_turns
    
    # Retry effectiveness
    retry_success_rate: float           # retries_that_fixed_issue / total_retries
    avg_retries_per_error: float        # total_retries / total_errors
    
    # DQ stats
    games_completed: int
    games_disqualified: int
    games_aborted: int                  # Rate limit / connection failures
    
    # Error patterns
    invalid_action_breakdown: dict[str, int]   # RESOURCE_ERROR: 5, STATE_ERROR: 3, etc.
    errors_by_turn_quartile: dict[str, int]    # "Q1": 12, "Q2": 5, "Q3": 3, "Q4": 8
```

---

## Error Impact on Tier 1 Metrics

How errors flow into the scoring framework:

| Error Type | Affected Tier 1 Metrics | Impact |
|---|---|---|
| E1 (Malformed JSON) | `structured_output_compliance` | Direct: lowers compliance rate |
| E2 (Schema violation) | `structured_output_compliance` | Direct: lowers compliance rate |
| E3 (Invalid action) | `action_validity_rate`, `resource_arithmetic_accuracy` | Direct: proves reasoning failure |
| E3 (worker sum wrong) | `arithmetic_precision` | Direct: mathematical error |
| E3 (can't afford) | `resource_forecast_accuracy` | Model misread its own resources |
| E4 (Timeout) | `response_reliability` | Penalizes slow models |
| E7 (Context overflow) | `context_degradation_score` | Measures graceful handling |
| E8 (Refusal) | Not scored (model limitation) | Flagged only |

---

## Configuration Defaults

All error handling parameters are configurable per benchmark run:

```python
class ErrorHandlingConfig(BaseModel):
    """Error handling configuration for benchmark runs."""
    
    # Retry limits
    max_json_retries: int = 3
    max_schema_retries: int = 2
    max_timeout_retries: int = 1
    max_rate_limit_retries: int = 5
    max_api_error_retries: int = 3
    max_connection_retries: int = 3
    
    # Timeouts (milliseconds)
    response_timeout_ms: int = 30_000
    retry_timeout_ms: int = 20_000
    total_turn_budget_ms: int = 60_000
    
    # Rate limit handling
    rate_limit_base_wait_s: int = 60
    rate_limit_max_wait_s: int = 600    # 10 minutes max single wait
    games_aborted_before_halt: int = 3
    
    # Disqualification thresholds
    dq_consecutive_invalid: int = 10
    dq_consecutive_fallback: int = 15
    dq_consecutive_timeouts: int = 5
    dq_error_rate_threshold: float = 0.80
    dq_min_turns_for_rate: int = 20     # Don't DQ on rate until 20 turns played
    
    # JSON extraction
    attempt_json_extraction: bool = True  # Try to extract from wrappers before counting as error
    attempt_schema_coercion: bool = True  # Try to fix common schema issues
    
    # Logging
    log_raw_responses: bool = True        # Store full LLM outputs (for debugging)
    log_level: str = "WARNING"            # ERROR, WARNING, INFO, DEBUG
```

---

## State Diagram: Turn Error Resolution

```
                    ┌─────────────────┐
                    │  Send prompt    │
                    │  to LLM        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
              ┌─────│  Response       │─────┐
              │     │  received?      │     │ No (timeout)
              │ Yes └─────────────────┘     │
              │                             ▼
     ┌────────▼────────┐          ┌─────────────────┐
     │  Valid JSON?     │          │ Retry once      │
     └───┬─────────┬───┘          │ (same prompt)   │
     Yes │         │ No           └────────┬────────┘
         │         │                       │
         │    ┌────▼──────────┐    ┌───────▼────────┐
         │    │ Extract JSON  │    │ Success?       │
         │    │ from wrappers │    └──┬──────────┬──┘
         │    └───┬───────┬───┘   Yes │          │ No
         │    Yes │       │ No        │          ▼
         │        │       ▼           │    ┌─────────┐
         │        │  ┌────────┐       │    │  PASS   │
         │        │  │Retry   │       │    │fallback │
         │        │  │(max 3) │       │    └─────────┘
         │        │  └───┬────┘       │
         │        │      │            │
         ▼        ▼      ▼            ▼
    ┌─────────────────────────────────────┐
    │  Valid schema?                       │
    └───┬───────────────────────────┬─────┘
    Yes │                           │ No
        │                      ┌────▼──────┐
        │                      │Coerce     │
        │                      │& retry(2) │
        │                      └────┬──────┘
        │                           │
        ▼                           ▼
    ┌─────────────────────────────────────┐
    │  Submit to engine.handle_action()   │
    └───┬───────────────────────────┬─────┘
   Valid│                           │ ValueError
        │                           │
        ▼                           ▼
    ┌──────────┐              ┌──────────────┐
    │ SUCCESS  │              │ INVALID      │
    │ Record   │              │ Record error │
    │ turn     │              │ (no retry)   │
    └──────────┘              └──────────────┘
```

---

## Edge Cases & Special Handling

### 1. Model returns multiple actions in one response

```json
{"actions": [{"action": "BUILD", ...}, {"action": "TRADE_BUY", ...}]}
```

**Policy:** Only the first action is used. Log as `schema_coerced`. The game allows exactly one action per turn.

### 2. Model asks a question instead of acting

```
"What are the current market prices? I need more information before deciding."
```

**Policy:** Treated as E1 (no JSON). Retry prompt reminds model that all information is in the game state. After retries exhausted: PASS.

### 3. Model tries to "hack" the game

```json
{"action": "BUILD", "params": {"building_type": "nuclear_reactor"}}
```

**Policy:** Engine rejects with ValueError (building type doesn't exist). Scored as E3 invalid action. No special handling — the engine's validation is the security boundary.

### 4. Model produces valid PASS for every turn

**Policy:** This is technically valid. Not an error. But it results in terrible scores naturally (colony never grows). The benchmark measures strategic quality, not just compliance. A model that always PASSes will score near 0 on all gameplay metrics.

### 5. Retry succeeds but response contradicts previous reasoning

**Policy:** Only the final successful response is used for scoring. Previous failed attempts are logged but don't affect game state. Reasoning consistency is measured across successful turns only.

### 6. Model returns action for wrong game phase

E.g., trying to BUILD during CATASTROPHE phase (when actions are suspended).

**Policy:** Engine rejects. Scored as E3. The available_actions list in the prompt would have been empty or contained only PASS during catastrophe phases.

---

## Monitoring & Alerting (Benchmark Runtime)

During a benchmark run, the orchestrator surfaces real-time error rates:

```
╭─ Benchmark Progress ──────────────────────────────────────────╮
│ Model: GPT-4o | Game 3/10 | Turn 45/100                      │
│ Error rate: 8% (4 invalid actions, 0 timeouts, 0 JSON errors)│
│ Status: HEALTHY                                               │
╰───────────────────────────────────────────────────────────────╯

╭─ Benchmark Progress ──────────────────────────────────────────╮
│ Model: Claude-3.5 | Game 7/10 | Turn 12/100                  │
│ Error rate: 92% (11 consecutive invalid actions)              │
│ Status: ⚠ APPROACHING DQ (10/10 consecutive invalid)         │
╰───────────────────────────────────────────────────────────────╯
```

---

## Summary Table

| Scenario | Retries | Fallback | Scores As | DQ Risk |
|----------|---------|----------|-----------|---------|
| Good response, valid action | 0 | — | Full credit | None |
| Good response, engine rejects | 0 | None (action lost) | Invalid action | Yes (if consecutive) |
| JSON wrapped in markdown | 0 (extracted) | — | Full credit | None |
| Truly malformed JSON | Up to 3 | PASS | JSON error | Yes (if consecutive) |
| Schema violation | Up to 2 | PASS | Schema error | Yes (if consecutive) |
| Timeout | 1 | PASS | Timeout | Yes (if 5 consecutive) |
| Rate limited | Up to 5 (with wait) | Abort game | Game excluded | No |
| Server error (5xx) | Up to 3 | PASS | API error | No |
| Context overflow | 1 (truncated) | PASS | Context error | No |
| Safety refusal | 0 | PASS | Flagged only | No |
| Empty response | Up to 2 | PASS | Empty error | Yes (if consecutive) |
| Connection failure | Up to 3 | Abort game | Game excluded | No |
