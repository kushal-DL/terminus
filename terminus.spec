# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Terminus — single-file executable."""

import os
from pathlib import Path

block_cipher = None

ROOT = Path(SPECPATH)

# Collect data files
datas = [
    # Game data JSON files
    (str(ROOT / "terminus" / "data" / "*.json"), os.path.join("terminus", "data")),
    # Textual CSS theme
    (str(ROOT / "terminus" / "client" / "theme.tcss"), os.path.join("terminus", "client")),
]

# Hidden imports that PyInstaller can't auto-detect
hiddenimports = [
    # ── Core ──────────────────────────────────────────────────────────────────
    "terminus",
    "terminus.config",
    "terminus.data",
    "terminus.data.loader",

    # ── Server ────────────────────────────────────────────────────────────────
    "terminus.server",
    "terminus.server.app",
    "terminus.server.engine",
    "terminus.server.models",
    "terminus.server.persistence",

    # ── Client screens ────────────────────────────────────────────────────────
    "terminus.client",
    "terminus.client.app",
    "terminus.client.api",
    "terminus.client.art",
    "terminus.client.screens",
    "terminus.client.screens.main_menu",
    "terminus.client.screens.lobby",
    "terminus.client.screens.setup",
    "terminus.client.screens.colony",
    "terminus.client.screens.build",
    "terminus.client.screens.workers",
    "terminus.client.screens.market",
    "terminus.client.screens.catastrophe",
    "terminus.client.screens.leaderboard",
    "terminus.client.screens.help",
    "terminus.client.screens.settings",
    "terminus.client.screens.connection_lost",
    "terminus.client.screens.dev_panel",
    "terminus.client.screens.benchmark_setup",
    "terminus.client.screens.benchmark_live",
    "terminus.client.screens.benchmark_results",

    # ── Client widgets ────────────────────────────────────────────────────────
    "terminus.client.widgets",
    "terminus.client.widgets.resource_bar",
    "terminus.client.widgets.building_card",
    "terminus.client.widgets.worker_slider",
    "terminus.client.widgets.countdown_timer",
    "terminus.client.widgets.notification_toast",
    "terminus.client.widgets.ascii_art_panel",
    "terminus.client.widgets.sparkline_chart",

    # ── Audio ─────────────────────────────────────────────────────────────────
    "terminus.audio",
    "terminus.audio.player",
    "terminus.audio.synth",
    "terminus.audio.sounds",

    # ── Dev tools ─────────────────────────────────────────────────────────────
    "terminus.dev",
    "terminus.dev.console",

    # ── Benchmark — core ──────────────────────────────────────────────────────
    "terminus.benchmark",
    "terminus.benchmark.agent",
    "terminus.benchmark.events",
    "terminus.benchmark.error_handler",
    "terminus.benchmark.mock_orchestrator",
    "terminus.benchmark.orchestrator",
    "terminus.benchmark.orchestrator_v2",
    "terminus.benchmark.prompt",
    "terminus.benchmark.recorder",
    "terminus.benchmark.report",
    "terminus.benchmark.response_parser",
    "terminus.benchmark.results",
    "terminus.benchmark.runner",
    "terminus.benchmark.schemas",
    "terminus.benchmark.scorer",
    "terminus.benchmark.speed",
    "terminus.benchmark.state_converter",
    "terminus.benchmark.tokens",

    # ── Benchmark — adapters ──────────────────────────────────────────────────
    "terminus.benchmark.adapters",
    "terminus.benchmark.adapters.openai_compat",
    "terminus.benchmark.adapters.anthropic",
    "terminus.benchmark.adapters.google",

    # ── Benchmark — opponents ─────────────────────────────────────────────────
    "terminus.benchmark.opponents",
    "terminus.benchmark.opponents.base",
    "terminus.benchmark.opponents.random_agent",
    "terminus.benchmark.opponents.greedy_agent",
    "terminus.benchmark.opponents.balanced_agent",
    "terminus.benchmark.opponents.rush_agent",
    "terminus.benchmark.opponents.turtle_agent",
    "terminus.benchmark.opponents.adversarial_agent",

    # ── Benchmark — metrics ───────────────────────────────────────────────────
    "terminus.benchmark.metrics",
    "terminus.benchmark.metrics.base",
    "terminus.benchmark.metrics.utils",
    "terminus.benchmark.metrics.planning",
    "terminus.benchmark.metrics.numerical",
    "terminus.benchmark.metrics.flexibility",
    "terminus.benchmark.metrics.context_pressure",
    "terminus.benchmark.metrics.opponent_aware",
    "terminus.benchmark.metrics.state_probes",

    # ── Benchmark — dimensions ────────────────────────────────────────────────
    "terminus.benchmark.dimensions",
    "terminus.benchmark.dimensions.base",
    "terminus.benchmark.dimensions.coherence",
    "terminus.benchmark.dimensions.arithmetic",
    "terminus.benchmark.dimensions.triage",
    "terminus.benchmark.dimensions.error_recognition",
    "terminus.benchmark.dimensions.pivot",
    "terminus.benchmark.dimensions.degradation",
    "terminus.benchmark.dimensions.opportunity",
    "terminus.benchmark.dimensions.game_theory",
    "terminus.benchmark.dimensions.composite",
    "terminus.benchmark.dimensions.trend",
    "terminus.benchmark.dimensions.archetypes",

    # ── Benchmark — exports ───────────────────────────────────────────────────
    "terminus.benchmark.export",
    "terminus.benchmark.export.json_export",
    "terminus.benchmark.export.csv_export",
    "terminus.benchmark.export.markdown_export",
    "terminus.benchmark.export.statistics",

    # ── Server framework ──────────────────────────────────────────────────────
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    "aiosqlite",
    "pydantic",
    "pydantic_core",

    # ── HTTP / async ──────────────────────────────────────────────────────────
    "httpx",
    "httpx._transports",
    "httpx._transports.default",
    "anyio",
    "anyio._backends",
    "anyio._backends._asyncio",
    "starlette",
    "starlette.routing",
    "starlette.middleware",

    # ── Textual TUI ───────────────────────────────────────────────────────────
    "textual",
    "textual.app",
    "textual.widgets",
    "textual.screen",
    "textual.css",
    "textual._xterm_parser",

    # ── Token counting ────────────────────────────────────────────────────────
    "tiktoken",
    "tiktoken.core",
    "tiktoken_ext",
    "tiktoken_ext.openai_public",
]

a = Analysis(
    [str(ROOT / "terminus" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "PIL",
        "cv2",
        "jupyter",
        "notebook",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="terminus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
