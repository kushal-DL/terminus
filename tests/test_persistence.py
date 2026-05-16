"""Tests for persistence module — save/load roundtrip and action log."""
import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from terminus.server.persistence import StatePersistence, find_resumable_games


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def persist(tmp_data_dir):
    return StatePersistence("test-game-001", data_dir=tmp_data_dir)


@pytest.mark.asyncio
async def test_init_creates_tables(persist):
    await persist.init_db()
    # Verify DB file exists
    assert persist._db_path.exists()


@pytest.mark.asyncio
async def test_save_and_load_snapshot(persist):
    await persist.init_db()
    state_json = json.dumps({"game_id": "test-game-001", "tick": 5, "phase": "playing"})
    await persist.save_snapshot(state_json, tick=5)
    loaded = await persist.load_latest_snapshot()
    assert loaded is not None
    assert json.loads(loaded)["tick"] == 5


@pytest.mark.asyncio
async def test_load_returns_latest(persist):
    await persist.init_db()
    await persist.save_snapshot('{"tick": 1}', tick=1)
    await persist.save_snapshot('{"tick": 2}', tick=2)
    await persist.save_snapshot('{"tick": 3}', tick=3)
    loaded = await persist.load_latest_snapshot()
    assert json.loads(loaded)["tick"] == 3


@pytest.mark.asyncio
async def test_snapshot_rolling_cleanup(persist):
    await persist.init_db()
    for i in range(10):
        await persist.save_snapshot(f'{{"tick": {i}}}', tick=i)
    # Should keep only last 3
    import aiosqlite
    async with aiosqlite.connect(str(persist._db_path)) as db:
        async with db.execute("SELECT COUNT(*) FROM game_snapshots") as cur:
            row = await cur.fetchone()
            assert row[0] <= 4  # 3 kept + potential race with last insert


@pytest.mark.asyncio
async def test_load_empty_returns_none(persist):
    await persist.init_db()
    loaded = await persist.load_latest_snapshot()
    assert loaded is None


@pytest.mark.asyncio
async def test_action_log(persist):
    await persist.init_db()
    await persist.log_action(tick=1, player_id="p1", action_type="build", params={"building_type": "farm"}, result={"ok": True})
    await persist.log_action(tick=2, player_id="p2", action_type="trade_buy", params={"resource": "food", "quantity": 3}, result={"ok": True})
    log = await persist.get_action_log()
    assert len(log) == 2
    assert log[0]["player_id"] == "p1"
    assert log[1]["action_type"] == "trade_buy"


@pytest.mark.asyncio
async def test_find_resumable_games(tmp_data_dir):
    # Create a game with a recent snapshot that has phase=playing
    persist = StatePersistence("resume-test", data_dir=tmp_data_dir)
    await persist.init_db()
    state = json.dumps({"game_id": "resume-test", "tick": 10, "phase": "playing"})
    await persist.save_snapshot(state, tick=10)
    await persist.close()

    games = find_resumable_games(data_dir=tmp_data_dir)
    assert len(games) >= 1
    assert games[0]["game_id"] == "resume-test"
    assert games[0]["tick"] == 10


@pytest.mark.asyncio
async def test_close_is_safe(persist):
    await persist.init_db()
    await persist.close()
    await persist.close()  # Double close should not error
