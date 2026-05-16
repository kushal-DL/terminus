# Terminus

Multiplayer CLI survival strategy game. Manage your settlement, allocate workers, build structures, and survive catastrophes — all in your terminal.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## Install

### From PyPI (recommended)

```bash
pip install terminus-game
```

### From GitHub

```bash
pip install git+https://github.com/terminus-game/terminus.git
```

### From source (development)

```bash
git clone https://github.com/terminus-game/terminus.git
cd terminus
pip install -e ".[dev]"
```

### Pre-built executable

Download the latest release for your platform from [GitHub Releases](https://github.com/terminus-game/terminus/releases) — no Python installation required.

## Prerequisites

- **Python 3.11 or newer** (for pip install methods)
- **Terminal with Unicode support** (Windows Terminal, iTerm2, most Linux terminals)
- **cloudflared** (optional — only needed for `--public` mode to share games over the internet)

## Run

```bash
terminus                # Launch the game (starts server + TUI client)
terminus --public       # Launch with public URL via cloudflared tunnel
terminus --server-only  # Run headless server (for dedicated hosting)
terminus --port 9090    # Use a custom port (default: 8080)
terminus --verbose      # Enable debug logging
```

## Quick Start

1. Run `terminus` — select **"Create Game"**
2. Choose your colony location and specialization
3. Share the displayed URL with other players (or use `--public` for internet access)
4. Other players run `terminus` → **"Join Game"** → paste the URL
5. Host starts the game once all players are ready
6. **Survive 5 catastrophes** over ~45 minutes. Highest score wins!

## Gameplay

- **Allocate workers** across farming, mining, research, construction, defense, and medicine
- **Build structures** (farms, walls, hospitals, labs, warehouses, housing) up to level 3
- **Trade resources** at the market — prices fluctuate each tick
- **Prepare for catastrophes** — the watchtower gives early warnings
- **Manage morale** — starvation and damage reduce it; good management boosts production

## Dev Console (Admin Tools)

For debugging and testing, Terminus includes a dev console TUI:

```bash
# Start the game server first
terminus --server-only

# In another terminal, launch the dev console
TERMINUS_DEV_MODE=1 python -m terminus.dev --server http://127.0.0.1:8080
```

The dev console provides: real-time state inspection, resource overrides, catastrophe controls, and instant building completion.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run balance simulator
python -m tools.balance.simulator --preset standard --games 10

# Run load test
python tools/load_test.py --players 20 --duration 60
```

## License

MIT — see [LICENSE](LICENSE) for details.
