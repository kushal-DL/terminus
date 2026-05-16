"""SQLite persistence layer for game state snapshots and action logging."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

# Default storage directory
_DEFAULT_DATA_DIR = Path.home() / ".terminus" / "games"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS game_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    state_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    tick INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    params_json TEXT NOT NULL,
    result_json TEXT,
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_game ON game_snapshots(game_id, tick);
CREATE INDEX IF NOT EXISTS idx_actions_game ON action_log(game_id, tick);
"""


class StatePersistence:
    """Manages SQLite-based game state persistence."""

    def __init__(self, game_id: str, data_dir: Path | None = None):
        self.game_id = game_id
        self._data_dir = data_dir or _DEFAULT_DATA_DIR
        self._db_path = self._data_dir / f"{game_id}.db"
        self._db: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> Path:
        return self._db_path

    async def init_db(self) -> None:
        """Create the database and tables if they don't exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"Persistence initialized: {self._db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def save_snapshot(self, state_json: str, tick: int) -> None:
        """Save a game state snapshot."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO game_snapshots (game_id, tick, timestamp, state_json) VALUES (?, ?, ?, ?)",
            (self.game_id, tick, time.time(), state_json),
        )
        await self._db.commit()
        # Rolling cleanup — keep only last N snapshots
        await self._cleanup_snapshots(keep=3)

    async def load_latest_snapshot(self) -> str | None:
        """Load the most recent snapshot JSON for this game."""
        if not self._db:
            return None
        async with self._db.execute(
            "SELECT state_json FROM game_snapshots WHERE game_id = ? ORDER BY tick DESC LIMIT 1",
            (self.game_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def _cleanup_snapshots(self, keep: int = 3) -> None:
        """Remove old snapshots, keeping only the most recent N."""
        if not self._db:
            return
        await self._db.execute(
            """DELETE FROM game_snapshots WHERE game_id = ? AND id NOT IN (
                SELECT id FROM game_snapshots WHERE game_id = ? ORDER BY tick DESC LIMIT ?
            )""",
            (self.game_id, self.game_id, keep),
        )

    async def log_action(
        self,
        tick: int,
        player_id: str,
        action_type: str,
        params: dict[str, Any],
        result: dict[str, Any] | None = None,
    ) -> None:
        """Append an action to the action log."""
        if not self._db:
            return
        await self._db.execute(
            "INSERT INTO action_log (game_id, tick, player_id, action_type, params_json, result_json, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                self.game_id,
                tick,
                player_id,
                action_type,
                json.dumps(params),
                json.dumps(result) if result else None,
                time.time(),
            ),
        )
        await self._db.commit()

    async def get_action_log(self) -> list[dict[str, Any]]:
        """Return the full action log as a list of dicts."""
        if not self._db:
            return []
        async with self._db.execute(
            "SELECT tick, player_id, action_type, params_json, result_json, timestamp "
            "FROM action_log WHERE game_id = ? ORDER BY id",
            (self.game_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            {
                "tick": r[0],
                "player_id": r[1],
                "action_type": r[2],
                "params": json.loads(r[3]),
                "result": json.loads(r[4]) if r[4] else None,
                "timestamp": r[5],
            }
            for r in rows
        ]


def find_resumable_games(data_dir: Path | None = None, max_age_minutes: int = 30) -> list[dict[str, Any]]:
    """Scan for unfinished games that can be resumed.

    Returns list of dicts with game_id, db_path, tick, timestamp, phase.
    """
    data_dir = data_dir or _DEFAULT_DATA_DIR
    if not data_dir.exists():
        return []

    import sqlite3

    cutoff = time.time() - max_age_minutes * 60
    results = []

    for db_file in data_dir.glob("*.db"):
        try:
            conn = sqlite3.connect(str(db_file))
            row = conn.execute(
                "SELECT game_id, tick, timestamp, state_json FROM game_snapshots "
                "ORDER BY tick DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row and row[2] >= cutoff:
                state = json.loads(row[3])
                phase = state.get("phase", "finished")
                if phase not in ("finished", "scoring"):
                    results.append({
                        "game_id": row[0],
                        "db_path": str(db_file),
                        "tick": row[1],
                        "timestamp": row[2],
                        "phase": phase,
                        "age_minutes": (time.time() - row[2]) / 60,
                    })
        except Exception:
            continue

    return results
