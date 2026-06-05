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
    parser.add_argument(
        "--benchmark",
        metavar="CONFIG",
        nargs="?",          # optional: --benchmark alone launches TUI, --benchmark file.json runs headless
        const="__tui__",    # sentinel when flag given with no argument
        help="Run LLM benchmark. With no argument: opens the TUI benchmark setup screen. "
             "With a JSON config file: runs headlessly, progress to stdout, "
             "HTML/JSON/CSV/Markdown reports written to output_dir.",
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

    if args.benchmark == "__tui__":
        # --benchmark with no config file → open TUI on benchmark setup screen
        _run_tui_benchmark(args)
    elif args.benchmark:
        _run_benchmark_headless(args.benchmark, args.verbose)
    elif args.server_only:
        _run_server_only(args)
    else:
        _run_tui(args)


def _run_tui_benchmark(args) -> None:
    """Launch TUI directly on the benchmark setup screen."""
    from terminus.client.app import TerminusApp
    from terminus.client.screens.benchmark_setup import BenchmarkSetupScreen

    app = TerminusApp()
    app._cli_args = args  # type: ignore
    app._tunnel_url = _tunnel_url  # type: ignore
    # Push the benchmark setup screen on top of the main menu after launch
    app._initial_screen = BenchmarkSetupScreen  # type: ignore
    app.run()


def _run_benchmark_headless(config_path: str, verbose: bool = False) -> None:
    """Run the LLM benchmark headlessly from a JSON config file.

    Progress is printed to stdout. The HTML report is written to
    config.output_dir (default: ./benchmark-results/).
    """
    import asyncio
    import json
    import sys
    from pathlib import Path

    # Ensure stdout can handle Unicode on Windows (cmd.exe defaults to cp1252)
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    from pydantic import ValidationError

    from terminus.benchmark.schemas import BenchmarkConfig

    # ── Load config ──────────────────────────────────────────────────────────
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        bench_config = BenchmarkConfig.model_validate(raw)
    except ValidationError as exc:
        print(f"Error: invalid benchmark config:\n{exc}", file=sys.stderr)
        sys.exit(1)

    # ── Banner ────────────────────────────────────────────────────────────────
    model_names = ", ".join(m.name for m in bench_config.models)
    total_games = (
        len(bench_config.models)
        * len(bench_config.opponents)
        * bench_config.games_per_matchup
    )
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║       TERMINUS LLM BENCHMARK (HEADLESS)      ║")
    print("  ╚══════════════════════════════════════════════╝")
    print(f"  Models    : {model_names}")
    print(f"  Opponents : {', '.join(o.value for o in bench_config.opponents)}")
    print(f"  Games     : {bench_config.games_per_matchup} per matchup × "
          f"{len(bench_config.opponents)} opponents × "
          f"{len(bench_config.models)} models = {total_games} total")
    print(f"  Max turns : {bench_config.max_turns}  |  Speed: {bench_config.speed_multiplier}×")
    print(f"  Output    : {bench_config.output_dir}")
    print()

    # ── Run ───────────────────────────────────────────────────────────────────
    asyncio.run(_benchmark_async(bench_config, total_games, verbose))


async def _benchmark_async(
    bench_config: "BenchmarkConfig",
    total_games: int,
    verbose: bool,
) -> None:
    import asyncio
    import time

    from terminus.benchmark.events import (
        BenchmarkCompleted,
        BenchmarkEvent,
        CatastropheTriggered,
        ErrorOccurred,
        GameCompleted,
        GameStarted,
        TurnCompleted,
    )
    from terminus.benchmark.runner import BenchmarkRunner

    event_queue: asyncio.Queue[BenchmarkEvent] = asyncio.Queue()
    runner = BenchmarkRunner(config=bench_config, event_queue=event_queue)

    start_time = time.time()
    report_path: str | None = None

    # ── Event consumer (prints progress) ─────────────────────────────────────
    async def consume_events() -> None:
        nonlocal report_path
        current_game = 0
        current_model = ""
        current_opponent = ""

        while True:
            event = await event_queue.get()

            if isinstance(event, GameStarted):
                current_game = event.game_index + 1
                current_model = event.model_name
                current_opponent = event.opponent_strategy
                print(
                    f"  [{current_game:>3}/{total_games}] "
                    f"{current_model} vs {current_opponent} "
                    f"(seed {event.seed})",
                    end="",
                    flush=True,
                )

            elif isinstance(event, TurnCompleted):
                # Overwrite the current line with turn progress
                pct = int(event.turn / event.max_turns * 20)
                bar = "█" * pct + "░" * (20 - pct)
                icon = "✓" if event.action_valid else "✗"
                print(
                    f"\r  [{current_game:>3}/{total_games}] "
                    f"{current_model:<20} {bar} T{event.turn:>3}/{event.max_turns} "
                    f"{icon} {event.action_type:<18} score={event.score:>6.0f}",
                    end="",
                    flush=True,
                )

            elif isinstance(event, CatastropheTriggered):
                print(
                    f"\r  [{current_game:>3}/{total_games}] "
                    f"{current_model:<20} ⚡ CATASTROPHE: {event.catastrophe_name} "
                    f"(sev {event.severity})          ",
                    end="",
                    flush=True,
                )

            elif isinstance(event, GameCompleted):
                valid_pct = 0
                total_actions = event.valid_actions + event.invalid_actions
                if total_actions > 0:
                    valid_pct = int(event.valid_actions / total_actions * 100)
                print(
                    f"\r  [{current_game:>3}/{total_games}] "
                    f"{current_model:<20} ✓ done  "
                    f"score={event.final_score:>6.0f}  "
                    f"turns={event.turns_played:>3}  "
                    f"valid={valid_pct:>3}%  "
                    f"vs {event.opponent_strategy:<12}"
                )

            elif isinstance(event, ErrorOccurred):
                err_prefix = "  " if not verbose else f"  [{event.error_type}] "
                msg = event.message[:70]
                if event.recoverable:
                    print(f"\n  ⚠  {err_prefix}{event.model_name} T{event.turn}: {msg}")
                else:
                    print(f"\n  ✗  FATAL {err_prefix}{event.model_name} T{event.turn}: {msg}")

            elif isinstance(event, BenchmarkCompleted):
                report_path = event.report_path
                break

    # Run the benchmark and event consumer concurrently
    runner_task = asyncio.create_task(runner.run())
    await consume_events()
    await runner_task

    elapsed = time.time() - start_time
    elapsed_str = f"{elapsed / 60:.1f} min" if elapsed < 3600 else f"{elapsed / 3600:.1f} hr"

    # ── Final summary ─────────────────────────────────────────────────────────
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║              BENCHMARK COMPLETE              ║")
    print("  ╚══════════════════════════════════════════════╝")
    print(f"  Duration  : {elapsed_str}")
    print(f"  Games     : {runner.completed_games}/{total_games}")

    if report_path:
        from pathlib import Path
        base = Path(report_path).name.replace("_report.html", "")
        out_dir = str(Path(report_path).parent)
        print(f"  Output dir: {out_dir}")
        print(f"  HTML      : {base}_report.html")
        print(f"  JSON      : {base}_results.json")
        print(f"  CSV       : {base}_summary.csv  /  {base}_detailed.csv")
        print(f"  Markdown  : {base}_summary.md")
        print()
        print("  Open HTML report in browser:")
        print(f"    python -c \"import webbrowser; webbrowser.open('{report_path}')\"")
    else:
        print("  Report    : (not generated — check logs for errors)")
    print()


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
