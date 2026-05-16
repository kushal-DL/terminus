"""Terminus game entry point — python -m terminus."""

from __future__ import annotations

import argparse
import atexit
import signal
import sys

# Module-level reference to tunnel subprocess for cleanup
_tunnel_proc = None
_tunnel_url: str | None = None


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="terminus",
        description="Terminus — Multiplayer CLI survival strategy game",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Server bind host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Start cloudflared tunnel for public access",
    )
    parser.add_argument(
        "--server-only",
        action="store_true",
        help="Run only the server (no TUI client)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    import logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # Update config with CLI args
    from terminus import config
    config.DEFAULT_HOST = args.host
    config.DEFAULT_PORT = args.port

    if args.server_only:
        _run_server_only(args)
    else:
        _run_tui(args)


def _run_server_only(args) -> None:
    """Run just the FastAPI server without TUI."""
    import uvicorn
    from terminus.server.app import app, get_engine, _init_persistence
    from terminus.server.persistence import find_resumable_games

    # Check for resumable games
    resumable = find_resumable_games()
    if resumable:
        print("\n  Resumable games found:")
        for i, info in enumerate(resumable, 1):
            print(f"    {i}. {info['game_id']} (tick {info['tick']}, age {info['age_minutes']:.0f}m)")
        print(f"    {len(resumable) + 1}. Start new game")
        choice = input("\n  Choose [1]: ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        if 0 <= idx < len(resumable):
            import asyncio
            from terminus.models.game_state import GameState
            from terminus.server.persistence import StatePersistence

            chosen = resumable[idx]
            persist = StatePersistence(chosen["game_id"])

            async def _resume():
                await persist.init_db()
                snapshot = await persist.load_latest_snapshot()
                if snapshot:
                    state = GameState.model_validate_json(snapshot)
                    engine = get_engine()
                    engine.state = state
                    engine._persist = persist
                    print(f"  ✓ Resumed game {chosen['game_id']} at tick {chosen['tick']}")
                else:
                    print("  ✗ Snapshot missing — starting new game")

            asyncio.run(_resume())

    print(f"Terminus server starting on {args.host}:{args.port}")
    if args.public:
        _start_tunnel(args.port)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def _run_tui(args) -> None:
    """Run the Textual TUI client."""
    from terminus.client.app import TerminusApp

    if args.public:
        try:
            _start_tunnel(args.port)
        except Exception as e:
            print(f"⚠  Tunnel unavailable — using LAN only: {e}")

    app = TerminusApp()
    app._cli_args = args  # type: ignore
    app._tunnel_url = _tunnel_url  # type: ignore
    app.run()


def _start_tunnel(port: int) -> None:
    """Attempt to start cloudflared tunnel."""
    import shutil
    import subprocess
    import threading

    global _tunnel_proc, _tunnel_url

    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        print("⚠  cloudflared not found in PATH. Install it for public access:")
        print("   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        print(f"   Game will be available at http://localhost:{port}")
        return

    def run_tunnel():
        global _tunnel_proc, _tunnel_url
        try:
            proc = subprocess.Popen(
                [cloudflared, "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            _tunnel_proc = proc
            for line in proc.stdout:
                if ".trycloudflare.com" in line:
                    # Extract the URL
                    parts = line.split()
                    for part in parts:
                        if "trycloudflare.com" in part:
                            url = part.strip()
                            if not url.startswith("http"):
                                url = "https://" + url
                            _tunnel_url = url
                            print(f"\n🌐 PUBLIC URL: {url}\n")
                            print("Share this URL with players!")
                            break
        except Exception as e:
            print(f"⚠  Failed to start cloudflared tunnel: {e}")

    thread = threading.Thread(target=run_tunnel, daemon=True)
    thread.start()


def _cleanup_tunnel() -> None:
    """Terminate the cloudflared tunnel subprocess if running."""
    global _tunnel_proc
    if _tunnel_proc is not None:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=5)
        except Exception:
            try:
                _tunnel_proc.kill()
            except Exception:
                pass
        _tunnel_proc = None


atexit.register(_cleanup_tunnel)


def _signal_handler(signum, frame):
    _cleanup_tunnel()
    sys.exit(0)


# Register signal handlers for clean shutdown
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


if __name__ == "__main__":
    main()
