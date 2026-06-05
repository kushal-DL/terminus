# Epic 8: Testing & Quality

> **Priority**: P1  
> **Status**: ✅ All unit tests done (8.1.1–8.1.7) | ✅ Integration lifecycle (8.2.1)  
> **Sprint**: 3-5  
> **Framework**: pytest

---

## Feature 8.1 — Unit Tests

### Story 8.1.1 — State Machine Transitions

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test all valid transitions: LOBBY→SETUP→PLAYING→CATASTROPHE→PLAYING→SCORING→FINISHED
- [ ] Test invalid transitions raise appropriate errors (e.g., LOBBY→PLAYING directly)
- [ ] Test phase-specific action restrictions (can't build in LOBBY)
- [ ] Test host-only actions (start) rejected for non-host
- [ ] 100% branch coverage on state machine logic

---

### Story 8.1.2 — Resource Production Formulas

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test base production for each resource type
- [ ] Test location modifiers applied correctly (Coast +20% food, etc.)
- [ ] Test specialization bonuses (Agriculture +food, etc.)
- [ ] Test worker ratio effect (0 workers = 0 production)
- [ ] Test morale multiplier (0.5× at min, 1.5× at max)
- [ ] Test building bonus stacking
- [ ] Test food consumption and starvation trigger

---

### Story 8.1.3 — Catastrophe Damage Calculation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test base damage per severity level
- [ ] Test location vulnerability multiplier
- [ ] Test building mitigation reduction
- [ ] Test soldier worker mitigation
- [ ] Test damage floor (can't lose more than population)
- [ ] Test resource loss proportional to severity
- [ ] Test building health reduction

---

### Story 8.1.4 — Building Lifecycle

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test build: cost deducted, construction starts
- [ ] Test construction progress per tick (based on builders)
- [ ] Test completion: effects activate
- [ ] Test upgrade: higher cost, preserves health
- [ ] Test damage: effects degrade at low health
- [ ] Test repair: materials consumed, health restored
- [ ] Test demolish: building removed, 50% resources returned

---

### Story 8.1.5 — Market System

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test buy: gold deducted, resource added, stock decremented
- [ ] Test sell: resource deducted, gold added (with spread)
- [ ] Test stock limits: buy fails when stock = 0
- [ ] Test price fluctuation within ±20% bounds
- [ ] Test trade spec discount applied correctly
- [ ] Test insufficient gold/resource rejected

---

### Story 8.1.6 — Scoring Formula

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Test weighted sum: population × W1 + resources × W2 + buildings × W3 + morale × W4
- [ ] Test all players scored and ranked correctly
- [ ] Test tie-breaking (population wins ties)
- [ ] Test score never negative
- [ ] Test achievement bonus added when implemented

---

### Story 8.1.7 — Catastrophe Selection Algorithm

**Status**: ✅ Done

**Implementation Notes**:
- 6 tests in `tests/test_catastrophe_selection.py`
- Tests: category diversity, severity progression, no duplicate selection, correct count returned, handles overflow, deterministic with seed

**Acceptance Criteria**:
- [ ] Test category diversity (no same category back-to-back)
- [ ] Test severity progression (monotonically increasing ± jitter)
- [ ] Test all 20 catastrophes can be selected
- [ ] Test with fewer rounds than categories (still diverse)
- [ ] Test deterministic with seed (reproducible for debugging)

---

## Feature 8.2 — Integration Tests

### Story 8.2.1 — Full Game Lifecycle

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Automated test: create → join (3 players) → ready → start → setup → play 2 catastrophes → scoring → finished
- [ ] All phases transition correctly
- [ ] Final scores are non-zero and ranked
- [ ] No exceptions raised during entire flow
- [ ] Runs in <30 seconds (accelerated ticks)

---

### Story 8.2.2 — Multiplayer Concurrency

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] 5 concurrent async clients performing actions simultaneously
- [ ] No race conditions (double-spend, state corruption)
- [ ] All clients receive consistent state updates
- [ ] Actions from multiple clients interleave correctly
- [ ] Stress test: 50 actions/second across all clients

---

### Story 8.2.3 — Reconnection Test

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Client disconnects WebSocket mid-game
- [ ] Reconnects within 60s with same token
- [ ] State is intact (resources, buildings, workers unchanged)
- [ ] Resumes receiving tick broadcasts
- [ ] Other clients see player_reconnected event

---

### Story 8.2.4 — Load Test (250 Connections)

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Script spawns 250 WebSocket clients
- [ ] All connect successfully within 10s
- [ ] Server broadcasts tick to all within 500ms
- [ ] Memory <2GB, CPU <80% sustained
- [ ] No dropped connections over 5-minute test
- [ ] Measure: p50/p95/p99 latency for broadcasts

---

## Feature 8.3 — Manual Tests

### Story 8.3.1 — Full Playtest (3-4 Players)

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] 3-4 real players complete a 45-minute Standard game
- [ ] All screens functional and navigable
- [ ] No crashes or freezes
- [ ] Game feels fair and engaging (subjective)
- [ ] Document bugs found during playtest

---

### Story 8.3.2 — Cross-Platform Verification

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Windows Terminal: renders correctly
- [ ] macOS Terminal.app: renders correctly
- [ ] Linux (gnome-terminal): renders correctly
- [ ] Box-drawing chars display properly on all platforms
- [ ] Colors render as intended (no invisible text on light backgrounds)

---

### Story 8.3.3 — Fresh Install Test

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Clean Python 3.11+ machine (no prior deps)
- [ ] `pip install .` succeeds first try
- [ ] `python -m terminus` launches without error
- [ ] Create + join game works between two machines
- [ ] Document any missing system dependencies
