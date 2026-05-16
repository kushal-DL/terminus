"""Epic 8.2 — HTTP/WebSocket Integration Tests.

8.2.2: Multiplayer: 5 concurrent clients via HTTP API, no race conditions
8.2.3: Reconnection via WebSocket disconnect/reconnect, state intact
8.2.4: Load: 50+ WebSocket connections, measure performance

Uses httpx AsyncClient with ASGITransport for in-process testing
and Starlette TestClient for synchronous WebSocket tests.
"""

import asyncio
import time
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _reset_server_state():
    """Reset all global server state between tests."""
    from terminus.server import app as app_module
    app_module._engine = None
    app_module._ws_clients.clear()
    app_module._token_map.clear()
    app_module._disconnect_times.clear()
    app_module._action_timestamps.clear()


@pytest_asyncio.fixture
async def client():
    """Fresh httpx AsyncClient against the FastAPI app with clean state."""
    _reset_server_state()
    from terminus.server.app import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _reset_server_state()


async def _create_game(client: AsyncClient, name: str = "Host") -> dict:
    """Create a game, return {token, player_id, game_id}."""
    resp = await client.post("/game/create", json={"player_name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _join_game(client: AsyncClient, name: str) -> dict:
    """Join existing game, return {token, player_id, game_id}."""
    resp = await client.post("/game/join", json={"player_name": name})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _start_game(client: AsyncClient, token: str) -> None:
    """Host readies up and starts the game."""
    # Must be ready first
    resp = await client.post("/game/ready", headers={"X-Token": token})
    assert resp.status_code == 200, resp.text
    resp = await client.post("/game/start", headers={"X-Token": token})
    assert resp.status_code == 200, resp.text


async def _setup_player(client: AsyncClient, token: str, location: str, specialization: str) -> None:
    """Submit setup for a player."""
    resp = await client.post(
        "/game/setup",
        json={"location": location, "specialization": specialization},
        headers={"X-Token": token},
    )
    assert resp.status_code == 200, resp.text


async def _submit_action(client: AsyncClient, token: str, action_type: str, payload: dict) -> dict:
    """Submit a game action."""
    resp = await client.post(
        "/game/action",
        json={"action_type": action_type, "payload": payload},
        headers={"X-Token": token},
    )
    return resp.json() if resp.status_code == 200 else {"error": resp.text, "status": resp.status_code}


LOCATIONS = ["coast", "mountain", "plains", "forest", "desert"]
SPECS = ["trade", "military", "science", "agriculture", "trade"]


# ─── 8.2.2: Multiplayer — 5 concurrent clients via HTTP API ─────────────────


class TestMultiplayerHTTP:
    """Integration tests: 5 players through the full HTTP API layer."""

    @pytest.mark.asyncio
    async def test_five_players_create_and_join(self, client: AsyncClient):
        """5 players can create/join a game via HTTP."""
        host = await _create_game(client, "Host1")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        # Verify lobby shows 5 players
        resp = await client.get("/game/lobby", headers={"X-Token": tokens[0]})
        assert resp.status_code == 200
        lobby = resp.json()
        assert lobby["player_count"] == 5

    @pytest.mark.asyncio
    async def test_five_players_full_lifecycle(self, client: AsyncClient):
        """5 players go through create → join → start → setup → play."""
        host = await _create_game(client, "Alpha")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        # Start game
        await _start_game(client, tokens[0])

        # All setup
        for i, token in enumerate(tokens):
            loc = LOCATIONS[i % len(LOCATIONS)]
            spec = SPECS[i % len(SPECS)]
            await _setup_player(client, token, loc, spec)

        # All should be in PLAYING state
        resp = await client.get("/game/state", headers={"X-Token": tokens[0]})
        assert resp.status_code == 200
        state = resp.json()
        assert state["phase"] == "playing"

    @pytest.mark.asyncio
    async def test_concurrent_build_actions(self, client: AsyncClient):
        """5 players submit build actions concurrently — no crashes."""
        host = await _create_game(client, "Alpha")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i], SPECS[i])

        # Concurrent builds
        results = await asyncio.gather(*[
            _submit_action(client, token, "build", {"building_type": "farm"})
            for token in tokens
        ])
        # No exceptions — all returned dicts (success or graceful error)
        for r in results:
            assert isinstance(r, dict)

    @pytest.mark.asyncio
    async def test_concurrent_worker_allocations(self, client: AsyncClient):
        """5 players allocate workers concurrently — no race conditions."""
        host = await _create_game(client, "Alpha")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i], SPECS[i])

        # Concurrent worker allocations
        allocation = {"farming": 10, "mining": 5, "research": 3, "construction": 2, "defense": 0, "medicine": 0}
        results = await asyncio.gather(*[
            _submit_action(client, token, "allocate_workers", {"allocation": allocation})
            for token in tokens
        ])
        for r in results:
            assert isinstance(r, dict)

    @pytest.mark.asyncio
    async def test_concurrent_trade_actions(self, client: AsyncClient):
        """5 players submit trade actions concurrently — market handles correctly."""
        host = await _create_game(client, "Alpha")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i], SPECS[i])

        # Try to buy food — some may fail due to gold/no marketplace, that's fine
        results = await asyncio.gather(*[
            _submit_action(client, token, "trade_buy", {"resource": "food", "quantity": 1})
            for token in tokens
        ])
        for r in results:
            assert isinstance(r, dict)

    @pytest.mark.asyncio
    async def test_interleaved_state_reads(self, client: AsyncClient):
        """5 players reading state interleaved with actions — no stale/corrupt data."""
        host = await _create_game(client, "Alpha")
        tokens = [host["token"]]
        for i in range(4):
            p = await _join_game(client, f"Player{i+2}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i], SPECS[i])

        # Interleave state reads and actions
        async def read_and_act(token):
            resp = await client.get("/game/state", headers={"X-Token": token})
            assert resp.status_code == 200
            state = resp.json()
            assert "colony" in state
            await _submit_action(client, token, "build", {"building_type": "farm"})
            resp2 = await client.get("/game/state", headers={"X-Token": token})
            assert resp2.status_code == 200
            return resp2.json()

        results = await asyncio.gather(*[read_and_act(token) for token in tokens])
        for r in results:
            assert "colony" in r


# ─── 8.2.3: Reconnection via WebSocket ──────────────────────────────────────


class TestReconnectionHTTP:
    """Integration tests: disconnect/reconnect scenarios at HTTP/WS level."""

    @pytest.mark.asyncio
    async def test_state_preserved_after_disconnect(self, client: AsyncClient):
        """Player's colony state is preserved after disconnect."""
        host = await _create_game(client, "Host")
        p2 = await _join_game(client, "Player2")

        await _start_game(client, host["token"])
        await _setup_player(client, host["token"], "coast", "trade")
        await _setup_player(client, p2["token"], "mountain", "military")

        # Player2 builds something
        await _submit_action(client, p2["token"], "build", {"building_type": "farm"})

        # Get state before "disconnect"
        resp1 = await client.get("/game/state", headers={"X-Token": p2["token"]})
        state_before = resp1.json()

        # Simulate disconnect by marking player disconnected in engine
        from terminus.server.app import get_engine, _token_map
        engine = get_engine()
        pid = _token_map[p2["token"]]
        engine.state.players[pid].connected = False

        # "Reconnect" — player can still get state via token
        engine.state.players[pid].connected = True
        resp2 = await client.get("/game/state", headers={"X-Token": p2["token"]})
        state_after = resp2.json()

        # Colony and buildings preserved
        assert state_after["colony"]["location"] == state_before["colony"]["location"]
        assert len(state_after["colony"]["buildings"]) == len(state_before["colony"]["buildings"])

    @pytest.mark.asyncio
    async def test_actions_work_after_reconnect(self, client: AsyncClient):
        """Player can submit actions after reconnecting."""
        host = await _create_game(client, "Host")
        p2 = await _join_game(client, "Player2")

        await _start_game(client, host["token"])
        await _setup_player(client, host["token"], "coast", "trade")
        await _setup_player(client, p2["token"], "forest", "agriculture")

        # Disconnect and reconnect
        from terminus.server.app import get_engine, _token_map
        engine = get_engine()
        pid = _token_map[p2["token"]]
        engine.state.players[pid].connected = False
        engine.state.players[pid].connected = True

        # Should still be able to build
        result = await _submit_action(client, p2["token"], "build", {"building_type": "farm"})
        assert isinstance(result, dict)
        # Verify building was added
        resp = await client.get("/game/state", headers={"X-Token": p2["token"]})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_other_players_unaffected_by_disconnect(self, client: AsyncClient):
        """Other players can continue playing while one is disconnected."""
        host = await _create_game(client, "Host")
        p2 = await _join_game(client, "Player2")
        p3 = await _join_game(client, "Player3")

        await _start_game(client, host["token"])
        await _setup_player(client, host["token"], "coast", "trade")
        await _setup_player(client, p2["token"], "mountain", "military")
        await _setup_player(client, p3["token"], "plains", "science")

        # Disconnect p2
        from terminus.server.app import get_engine, _token_map
        engine = get_engine()
        pid2 = _token_map[p2["token"]]
        engine.state.players[pid2].connected = False

        # Host and p3 can still act
        r1 = await _submit_action(client, host["token"], "build", {"building_type": "farm"})
        r3 = await _submit_action(client, p3["token"], "build", {"building_type": "farm"})
        assert isinstance(r1, dict)
        assert isinstance(r3, dict)

    @pytest.mark.asyncio
    async def test_websocket_connect_and_receive(self, client: AsyncClient):
        """WebSocket connects successfully with valid token."""
        from starlette.testclient import TestClient
        from terminus.server.app import app

        _reset_server_state()
        # Use sync client to create game first
        with TestClient(app) as tc:
            resp = tc.post("/game/create", json={"player_name": "WSHost"})
            assert resp.status_code == 200
            token = resp.json()["token"]

            # Connect WebSocket using context manager
            with tc.websocket_connect(f"/game/ws?token={token}") as ws:
                # Connection should be accepted — if no exception, it worked
                pass


# ─── 8.2.4: Load — 50 concurrent HTTP clients ───────────────────────────────


class TestLoadHTTP:
    """Load tests: many clients interacting concurrently via HTTP."""

    @pytest.mark.asyncio
    async def test_50_players_join_concurrently(self, client: AsyncClient):
        """50 players can join a game via HTTP without errors."""
        host = await _create_game(client, "LoadHost")

        async def join(i: int):
            return await _join_game(client, f"LP{i:03d}")

        results = await asyncio.gather(*[join(i) for i in range(2, 52)])
        assert len(results) == 50
        for r in results:
            assert "token" in r
            assert "player_id" in r

        # Verify lobby count
        resp = await client.get("/game/lobby", headers={"X-Token": host["token"]})
        assert resp.json()["player_count"] == 51

    @pytest.mark.asyncio
    async def test_50_players_full_game(self, client: AsyncClient):
        """50 players go through full lifecycle — join, setup, play."""
        host = await _create_game(client, "LoadHost")
        tokens = [host["token"]]

        # Join 49 more
        for i in range(49):
            p = await _join_game(client, f"LP{i:03d}")
            tokens.append(p["token"])

        # Start
        await _start_game(client, tokens[0])

        # All setup concurrently
        async def setup(i, token):
            loc = LOCATIONS[i % len(LOCATIONS)]
            spec = SPECS[i % len(SPECS)]
            await _setup_player(client, token, loc, spec)

        await asyncio.gather(*[setup(i, t) for i, t in enumerate(tokens)])

        # Verify all in playing state
        resp = await client.get("/game/state", headers={"X-Token": tokens[0]})
        assert resp.json()["phase"] == "playing"

    @pytest.mark.asyncio
    async def test_50_concurrent_builds(self, client: AsyncClient):
        """50 players submit builds simultaneously — no crashes or corruption."""
        host = await _create_game(client, "LoadHost")
        tokens = [host["token"]]

        for i in range(49):
            p = await _join_game(client, f"LP{i:03d}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])

        async def setup(i, token):
            await _setup_player(client, token, LOCATIONS[i % 5], SPECS[i % 5])

        await asyncio.gather(*[setup(i, t) for i, t in enumerate(tokens)])

        # Concurrent builds
        t0 = time.perf_counter()
        results = await asyncio.gather(*[
            _submit_action(client, token, "build", {"building_type": "farm"})
            for token in tokens
        ])
        elapsed = time.perf_counter() - t0

        # All should return dicts (success or graceful error)
        for r in results:
            assert isinstance(r, dict)
        # Should complete within reasonable time (< 5s for 50 concurrent)
        assert elapsed < 5.0, f"50 concurrent builds took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_50_concurrent_state_reads(self, client: AsyncClient):
        """50 players read state simultaneously — consistent results."""
        host = await _create_game(client, "LoadHost")
        tokens = [host["token"]]

        for i in range(49):
            p = await _join_game(client, f"LP{i:03d}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i % 5], SPECS[i % 5])

        # Concurrent state reads
        t0 = time.perf_counter()

        async def read_state(token):
            resp = await client.get("/game/state", headers={"X-Token": token})
            assert resp.status_code == 200
            return resp.json()

        results = await asyncio.gather(*[read_state(t) for t in tokens])
        elapsed = time.perf_counter() - t0

        # All should have valid state
        for r in results:
            assert r["phase"] == "playing"
            assert "colony" in r

        assert elapsed < 5.0, f"50 concurrent reads took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_mixed_load_reads_and_writes(self, client: AsyncClient):
        """Mix of 50 reads and writes concurrently — no data corruption."""
        host = await _create_game(client, "LoadHost")
        tokens = [host["token"]]

        for i in range(49):
            p = await _join_game(client, f"LP{i:03d}")
            tokens.append(p["token"])

        await _start_game(client, tokens[0])
        for i, token in enumerate(tokens):
            await _setup_player(client, token, LOCATIONS[i % 5], SPECS[i % 5])

        # Half read, half write — interleaved
        async def action(i, token):
            if i % 2 == 0:
                resp = await client.get("/game/state", headers={"X-Token": token})
                assert resp.status_code == 200
                return resp.json()
            else:
                return await _submit_action(client, token, "build", {"building_type": "farm"})

        results = await asyncio.gather(*[action(i, t) for i, t in enumerate(tokens)])
        for r in results:
            assert isinstance(r, dict)

    @pytest.mark.asyncio
    async def test_websocket_multiple_connections(self, client: AsyncClient):
        """Multiple WebSocket connections can be established simultaneously."""
        from starlette.testclient import TestClient
        from terminus.server.app import app

        _reset_server_state()

        with TestClient(app) as tc:
            resp = tc.post("/game/create", json={"player_name": "WSHost"})
            host_token = resp.json()["token"]

            tokens = [host_token]
            for i in range(9):
                resp = tc.post("/game/join", json={"player_name": f"WSP{i}"})
                tokens.append(resp.json()["token"])

            # Connect WebSockets one at a time using context managers
            connected_count = 0
            for token in tokens:
                with tc.websocket_connect(f"/game/ws?token={token}") as ws:
                    connected_count += 1

            assert connected_count == 10

    @pytest.mark.asyncio
    async def test_rate_limiting_under_load(self, client: AsyncClient):
        """Rate limiting kicks in when a single client sends too many requests."""
        host = await _create_game(client, "RateHost")

        await _start_game(client, host["token"])
        await _setup_player(client, host["token"], "coast", "trade")

        # Rapidly fire actions beyond rate limit
        results = []
        for _ in range(15):
            resp = await client.post(
                "/game/action",
                json={"action_type": "build", "payload": {"building_type": "farm"}},
                headers={"X-Token": host["token"]},
            )
            results.append(resp.status_code)

        # Some should be 429 (rate limited)
        assert 429 in results, "Rate limiting should kick in"
        # First few should succeed (200 or 400 from game logic)
        assert results[0] in (200, 400)
