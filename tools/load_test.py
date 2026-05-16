"""Load test tool — spawn N concurrent WebSocket clients against a running server.

Usage:
    python -m tools.load_test --url ws://localhost:8080 --players 20 --duration 60
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import time
from typing import Any

import httpx
import websockets


async def _create_and_join(base_url: str, name: str) -> dict[str, str]:
    """Create or join a game, return {player_id, token, game_id}."""
    async with httpx.AsyncClient(base_url=base_url) as client:
        # Try joining first
        try:
            r = await client.get("/game/lobby")
            lobby = r.json()
            if lobby.get("phase") == "lobby":
                r2 = await client.post("/game/join", json={"player_name": name})
                if r2.status_code == 200:
                    return r2.json()
        except Exception:
            pass
        # Create new game
        r = await client.post("/game/create", json={"player_name": name})
        r.raise_for_status()
        return r.json()


async def _player_loop(
    ws_url: str,
    base_url: str,
    player_num: int,
    duration: float,
    stats: dict[str, Any],
) -> None:
    """Simulate a single player: connect WS, send random actions."""
    name = f"LoadBot_{player_num}"
    try:
        info = await _create_and_join(base_url, name)
    except Exception as e:
        stats["join_errors"] += 1
        print(f"  [{name}] Join failed: {e}")
        return

    token = info["token"]
    headers = {"X-Token": token}
    actions = ["build", "upgrade", "trade_buy", "trade_sell"]
    buildings = ["farm", "mine", "lab", "market"]
    resources = ["food", "materials", "knowledge"]

    try:
        async with websockets.connect(f"{ws_url}/ws?token={token}") as ws:
            stats["connected"] += 1
            end = time.time() + duration
            while time.time() < end:
                # Send a random action via REST
                action = random.choice(actions)
                payload: dict[str, Any] = {}
                if action in ("build", "upgrade", "demolish", "repair"):
                    payload["building_type"] = random.choice(buildings)
                elif action in ("trade_buy", "trade_sell"):
                    payload["resource"] = random.choice(resources)
                    payload["quantity"] = random.randint(1, 5)

                try:
                    async with httpx.AsyncClient(base_url=base_url) as client:
                        r = await client.post(
                            "/game/action",
                            json={"action_type": action, "payload": payload},
                            headers=headers,
                            timeout=5,
                        )
                    if r.status_code == 200:
                        stats["actions_ok"] += 1
                    elif r.status_code == 429:
                        stats["rate_limited"] += 1
                    else:
                        stats["actions_err"] += 1
                except Exception:
                    stats["actions_err"] += 1

                # Drain WS messages
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.1)
                    stats["ws_msgs"] += 1
                except (asyncio.TimeoutError, Exception):
                    pass

                await asyncio.sleep(random.uniform(0.2, 1.0))
    except Exception as e:
        stats["ws_errors"] += 1
        print(f"  [{name}] WS error: {e}")


async def run_load_test(ws_url: str, base_url: str, num_players: int, duration: float) -> None:
    stats: dict[str, Any] = {
        "connected": 0,
        "join_errors": 0,
        "actions_ok": 0,
        "actions_err": 0,
        "rate_limited": 0,
        "ws_msgs": 0,
        "ws_errors": 0,
    }

    print(f"Starting load test: {num_players} players, {duration}s duration")
    print(f"  Server: {base_url}")

    start = time.time()
    tasks = [
        _player_loop(ws_url, base_url, i, duration, stats)
        for i in range(num_players)
    ]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start

    print(f"\n{'='*50}")
    print(f"Load Test Results ({elapsed:.1f}s)")
    print(f"{'='*50}")
    print(f"  Players connected:  {stats['connected']}/{num_players}")
    print(f"  Join errors:        {stats['join_errors']}")
    print(f"  Actions OK:         {stats['actions_ok']}")
    print(f"  Actions errors:     {stats['actions_err']}")
    print(f"  Rate limited:       {stats['rate_limited']}")
    print(f"  WS messages recv:   {stats['ws_msgs']}")
    print(f"  WS errors:          {stats['ws_errors']}")
    if elapsed > 0:
        print(f"  Actions/sec:        {stats['actions_ok'] / elapsed:.1f}")


def main():
    parser = argparse.ArgumentParser(description="Terminus Load Test")
    parser.add_argument("--url", default="ws://localhost:8080", help="WebSocket base URL")
    parser.add_argument("--players", type=int, default=10, help="Number of concurrent players")
    parser.add_argument("--duration", type=float, default=30, help="Test duration in seconds")
    args = parser.parse_args()

    base_url = args.url.replace("ws://", "http://").replace("wss://", "https://")
    asyncio.run(run_load_test(args.url, base_url, args.players, args.duration))


if __name__ == "__main__":
    main()
