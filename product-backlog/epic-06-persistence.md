# Epic 6: Persistence & Reliability

> **Priority**: P1  
> **Status**: ⬜ TODO  
> **Sprint**: 4-5  
> **Depends on**: Epic 2 (stable engine), Epic 3 (server running)

---

## Feature 6.1 — Game State Persistence

### Story 6.1.1 — SQLite State Serialization

**As a** host  
**I want** the game state saved to disk periodically  
**So that** a crash doesn't lose the entire game

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] SQLite database at `~/.terminus/games/{game_id}.db`
- [ ] Full state serialized every 10 seconds (Pydantic `.model_dump_json()`)
- [ ] Schema: `game_state` table with `id`, `timestamp`, `state_json`, `tick`
- [ ] Keep last 3 snapshots (rolling — delete older)
- [ ] Write is async (doesn't block tick loop)
- [ ] DB created on game start, closed on game end

---

### Story 6.1.2 — Server Restart Recovery

**As a** host  
**I want** to resume a game after a server crash  
**So that** a brief outage doesn't ruin an ongoing session

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] On server start: check for existing `.db` files in `~/.terminus/games/`
- [ ] If found and game not FINISHED: offer "Resume last game? (Y/n)"
- [ ] On resume: deserialize latest snapshot, restore engine state
- [ ] Tick counter continues from saved value
- [ ] Catastrophe schedule preserved (adjusted for elapsed real-time)
- [ ] Players must reconnect (tokens still valid)
- [ ] If game is >30 min stale: auto-discard, don't offer resume

---

### Story 6.1.3 — Disconnect Tolerance

**As a** player  
**I want** my colony to survive if I briefly disconnect  
**So that** network hiccups don't destroy my game progress

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Colony continues producing/consuming while disconnected
- [ ] No actions taken on player's behalf (passive mode)
- [ ] Workers remain in last-set allocation
- [ ] Reconnection within 60s: seamless, full state restored
- [ ] Reconnection after 60s: still works, but "grace period" expired (no special protection)
- [ ] Colony never deleted for disconnection (persists until game ends)

---

### Story 6.1.4 — Action Log for Replays

**As a** player  
**I want** a full log of game actions  
**So that** games can potentially be replayed or analyzed

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Every action logged: `{tick, player_id, action_type, params, result}`
- [ ] Stored in SQLite `action_log` table
- [ ] Append-only (never modified after write)
- [ ] Includes engine events: catastrophe triggers, phase changes, scoring
- [ ] Export as JSON: `terminus export-log {game_id}`

---

## Feature 6.2 — Error Handling & Resilience

### Story 6.2.1 — Malformed Request Handling

**As a** developer  
**I want** the server to gracefully reject invalid inputs  
**So that** malicious or buggy clients can't crash the server

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] All endpoints use Pydantic models for request validation
- [ ] Invalid JSON: 422 with clear error message
- [ ] Missing fields: 422 with field name indicated
- [ ] Oversized payloads rejected: max 10KB per request
- [ ] Invalid action_type: 400 "Unknown action type: {x}"
- [ ] Fuzz-tested: no crashes with random payloads

---

### Story 6.2.2 — Client Disconnection UI

**As a** player  
**I want** clear feedback when my connection drops  
**So that** I know what's happening and can act

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Red banner: "Connection lost — retrying in Xs..."
- [ ] Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
- [ ] Retry counter shown: "Attempt 3/10"
- [ ] After 10 failures: "Reconnect" button (manual retry)
- [ ] All UI actions disabled during disconnection
- [ ] On reconnect: full state sync, banner dismissed, green toast "Reconnected"

---

### Story 6.2.3 — Load Testing (250 Players)

**As a** developer  
**I want** the server to handle 250 concurrent WebSocket connections  
**So that** large games work without degradation

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Load test script: spawn 250 WebSocket clients
- [ ] All receive tick broadcasts within 500ms of each other
- [ ] Server memory <2GB with 250 connections
- [ ] No dropped messages under sustained load
- [ ] Tick loop maintains 2s cadence (±100ms) under load
- [ ] CPU usage measured and documented

---

### Story 6.2.4 — Graceful Shutdown

**As a** host  
**I want** Ctrl+C to cleanly save and notify players  
**So that** an intentional shutdown doesn't corrupt data

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] SIGINT/SIGTERM handler registered
- [ ] On signal: save final state to SQLite
- [ ] Broadcast `server_shutdown` event to all WebSocket clients
- [ ] Close all WebSocket connections cleanly (code 1001)
- [ ] Stop cloudflared tunnel if running
- [ ] Exit with code 0
- [ ] Completes within 5 seconds

---

### Story 6.2.5 — Input Validation & Security

**As a** developer  
**I want** strict input validation at all boundaries  
**So that** the server is secure against injection and abuse

**Status**: ⬜ TODO

**Acceptance Criteria**:
- [ ] Player names: 1-20 chars, alphanumeric + spaces only, stripped
- [ ] Action params: type-checked, range-checked (no negative quantities)
- [ ] Token format: valid UUID4 only
- [ ] URL path: no path traversal possible
- [ ] WebSocket messages: max 4KB, JSON-only
- [ ] No SQL injection risk (Pydantic models, parameterized queries)
- [ ] No server-side template rendering (pure JSON API)
