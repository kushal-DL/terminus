# Epic 5: Game Balance & Data Tuning

> **Priority**: P1  
> **Status**: ✅ DONE  
> **Sprint**: 10  
> **Depends on**: Epic 2 (engine logic finalized)

---

## Feature 5.1 — Balance Framework

### Story 5.1.1 — Define Balance Constraints

**As a** game designer  
**I want** measurable balance targets  
**So that** no location/spec combo dominates and all strategies are viable

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] No single location+spec combo wins >25% of games in simulation
- [x] All 20 combos win at least 2% of games
- [x] Average game length within ±5 min of target (45 min standard)
- [x] Population survival rate across all catastrophes: 60-80% (not trivial, not instant death)
- [x] Constraints defined in `tools/balance/constraints.py` (7 constraints)

**Implementation**: `tools/balance/constraints.py` — 7 constraint classes: WinRateSpread, GameDuration, SurvivalRate, ScoreVariation, NoEarlyStarvation, FirstBuildingAffordable, NoDominantCombo

---

### Story 5.1.2 — Simulation Runner

**As a** developer  
**I want** a headless batch simulator that runs 100+ games with heuristic AI  
**So that** I can measure balance without manual playtesting

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] CLI command: `python -m tools.balance.simulator --games 100 --preset standard`
- [x] Heuristic AI players (4 strategies: balanced, aggressive, hoarder, researcher)
- [x] Random location+spec assignment per player + `--all-combos` mode
- [x] Output: win rates per combo, average game length, avg survival, score distribution
- [x] JSON report generation via `tools/balance/report.py`
- [x] Runs 50 games in ~30 seconds (headless, no network)

**Implementation**: `tools/balance/simulator.py` (SimulationRunner), `tools/balance/strategies.py` (4 AI strategies), `tools/balance/report.py` (text + JSON reports)

---

### Story 5.1.3 — Production Rate Tuning

**As a** game designer  
**I want** production rates calibrated so players feel comfortable by round 2  
**So that** early game isn't frustratingly slow

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] By tick 8: players can afford first building (avg tick 8 in sims)
- [x] By round 2 (after first catastrophe): 2-3 buildings built is typical
- [x] Food production exceeds consumption with 60% farmers allocated
- [x] No combo starts with negative resource flow (all can sustain without trading)
- [x] Surplus generation requires strategic allocation (not automatic)

**Tuned values**: BASE_PRODUCTION_PER_TICK: food=3.2, materials=2.6, knowledge=1.6, gold=2.2; POPULATION_GROWTH_RATE=0.4; FOOD_SURPLUS_THRESHOLD=60

---

### Story 5.1.4 — Catastrophe Damage Tuning

**As a** game designer  
**I want** catastrophes to feel threatening but not game-ending  
**So that** players experience tension without hopeless situations

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] First catastrophe: 5-15% population loss (warning shot)
- [x] Mid-game: 10-25% population loss without mitigation
- [x] Late-game: 20-40% population loss without mitigation (survival critical)
- [x] With full mitigation: damage reduced by 50-70%
- [x] Severity progression: each catastrophe ~1.5× worse than previous
- [x] No single catastrophe can kill >60% of population (minimum survival floor)

**Tuned values**: CATASTROPHE_MIN_DAMAGE=0.08, CATASTROPHE_POP_DAMAGE_SCALE=0.5; 84% survival rate on quick preset

---

### Story 5.1.5 — Building Cost Tuning

**As a** game designer  
**I want** building costs that create meaningful economic choices  
**So that** players can't build everything and must prioritize

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] First building affordable within 2 minutes of play (avg tick 8 = ~16s)
- [x] Level 3 upgrade requires saving across multiple production cycles
- [x] Total cost of all buildings at max level > total producible resources in one game
- [x] Players can realistically max 4-5 buildings (not all 10)
- [x] Cost ratios: Lv1 = base, Lv2 = 2.5×, Lv3 = 5×

**Validation**: 0/200 players failed to build in 50-game sim; existing costs in buildings.json are balanced

---

### Story 5.1.6 — Game Timing Tuning

**As a** game designer  
**I want** the game to consistently hit its time target  
**So that** sessions are predictable for scheduling

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Quick preset: 28.1 min avg (target 25-35 min, 4 catastrophes @ 420s)
- [x] Standard preset: 42.5 min avg (target 40-50 min, 5 catastrophes @ 510s)
- [x] Extended preset: 57.0 min avg (target 55-65 min, 6 catastrophes @ 570s)
- [x] Catastrophe intervals even with ±60s jitter
- [x] Setup phase: fixed 90s
- [x] Scoring phase: auto-calculate

---

### Story 5.1.7 — Difficulty Presets

**As a** host  
**I want** to choose game length/difficulty presets  
**So that** I can match the available time and player skill

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Quick: 4 catastrophes, 420s intervals
- [x] Standard: 5 catastrophes, 510s intervals
- [x] Extended: 6 catastrophes, 570s intervals
- [x] Presets defined in config.py as GAME_PRESETS dict
- [x] Host can adjust catastrophe count in lobby

---

## Feature 5.2 — Catastrophe Balance

### Story 5.2.1 — Category Distribution Verification

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] 20 catastrophes across 5 categories (population, resource, infrastructure, economic, military)
- [x] 2-6 per category (economic has 2, others have 3-6)
- [x] Selection algorithm uses round-robin categories
- [x] No category repeated until all categories have been used

---

### Story 5.2.2 — Severity Tier Validation

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Severity tiers 1-3 with progressive damage
- [x] Within each category: mixed severity levels
- [x] Selection prioritizes lower severity early, higher severity late
- [x] Average damage increases with severity (validated in tests)

---

### Story 5.2.3 — Location Vulnerability Matrix

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Each location has vulnerability values across all catastrophes
- [x] All 5 locations covered in vulnerability matrix
- [x] No location is universally safe or universally vulnerable
- [x] Each location has at least one high-vulnerability catastrophe
- [x] Validated in `tests/test_balance_data.py::TestLocationVulnerability`

---

### Story 5.2.4 — Mitigation Mapping Validation

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Every catastrophe has ≥1 building that mitigates it
- [x] All mitigation buildings reference valid building types from buildings.json
- [x] Mitigation factors validated (minimum threshold)
- [x] Worker mitigation has valid roles
- [x] Validated in `tests/test_balance_data.py::TestMitigationMapping`

---

### Story 5.2.5 — Selection Algorithm Testing

**Status**: ✅ DONE

**Acceptance Criteria**:
- [x] Run selection for all 20 location×spec combos across 5-catastrophe games
- [x] No duplicates in selected catastrophes
- [x] Severity progression validated (progressive severity)
- [x] Category diversity verified
- [x] Validated in `tests/test_balance_data.py::TestSelectionAlgorithm` (5 tests)
