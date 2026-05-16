# Epic 10: Stretch Goals (Post-V1)

> **Priority**: P3  
> **Status**: 💤 Deferred  
> **Sprint**: Post-launch

---

## Feature 10.1 — Singleplayer Mode

### Story 10.1.1 — AI Settlement Strategies

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] 4 AI strategies: Balanced, Aggressive (military focus), Hoarder (resource stockpile), Researcher (science/knowledge)
- [ ] Each strategy has decision logic for: worker allocation, building priority, market trading
- [ ] AI makes decisions once per tick (same cadence as production)
- [ ] Difficulty scales reaction speed and optimality of decisions

---

### Story 10.1.2 — Singleplayer Game Mode

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] CLI flag: `terminus --singleplayer` or menu option "Play vs AI"
- [ ] 1 human + 3-5 AI players (configurable)
- [ ] Server runs locally, AI clients simulated in-process
- [ ] Same rules, same catastrophes, same scoring
- [ ] AI names randomly generated (thematic: "Iron Ridge", "Dusthaven", etc.)

---

### Story 10.1.3 — AI Difficulty Levels

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] Easy: suboptimal decisions, slow reactions, no market trading
- [ ] Medium: reasonable play, occasional mistakes, basic trading
- [ ] Hard: near-optimal, exploits market, pre-builds for catastrophes
- [ ] Difficulty affects: decision delay, strategy optimality, information usage

---

## Feature 10.2 — Player-to-Player Trading

### Story 10.2.1 — Trade Offer System

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] POST /game/trade/offer: `{to_player: str, offer: Resources, request: Resources}`
- [ ] Offer visible to target player as notification
- [ ] Target can accept or decline
- [ ] On accept: resources exchanged atomically
- [ ] Offers expire after 30 seconds

---

### Story 10.2.2 — Trade Notification

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] WebSocket event: `trade_offer_received`
- [ ] Toast notification on target's screen
- [ ] Trade review popup: shows what's offered and what's requested
- [ ] Accept/Decline buttons

---

### Story 10.2.3 — P2P Trade History

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] Log of all P2P trades (both parties see)
- [ ] Viewable in market screen "Trade History" tab
- [ ] Shows: partner name, resources exchanged, tick

---

## Feature 10.3 — Game Replays

### Story 10.3.1 — Action Logging

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] Full action log persisted (see Epic 6.1.4)
- [ ] Export format: JSON array of `{tick, event_type, data}`
- [ ] Includes: all player actions, catastrophe events, phase changes, scores per tick

---

### Story 10.3.2 — Replay Viewer

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] CLI: `terminus replay {game_id}`
- [ ] Step-through mode: Enter advances one tick
- [ ] Accelerated mode: 10× speed playback
- [ ] Shows: resource graphs, event timeline, colony states
- [ ] Read-only TUI (no actions possible)

---

## Feature 10.4 — Tournament Mode

### Story 10.4.1 — Multi-Round Tournament

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] 3-game series, aggregate scores
- [ ] Players keep same name across rounds
- [ ] Location/spec randomized each round (or player chooses)
- [ ] Final ranking: sum of 3 game scores
- [ ] Trophy display for winner

---

### Story 10.4.2 — Elimination Bracket

**Status**: 💤 Deferred

**Acceptance Criteria**:
- [ ] 8/16/32 player bracket
- [ ] Groups of 4-8 per round, top 2 advance
- [ ] Bracket visualization in TUI
- [ ] Automated matchmaking and progression
- [ ] Finals: top 4 in final showdown
