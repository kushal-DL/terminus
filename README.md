# Terminus

Multiplayer CLI survival strategy game. Manage your settlement, allocate workers, build structures, and survive catastrophes — all in your terminal.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
[![PyPI](https://img.shields.io/pypi/v/terminus-game)](https://pypi.org/project/terminus-game/)

---

## Table of Contents

- [Install](#install)
- [Run the Game](#run-the-game)
- [Step-by-Step: Playing Your First Game](#step-by-step-playing-your-first-game)
- [Multiplayer Setup](#multiplayer-setup)
- [Gameplay Guide](#gameplay-guide)
- [Commands Reference](#commands-reference)
- [Dev Console (Admin Tools)](#dev-console-admin-tools)
- [Development](#development)
- [FAQ & Troubleshooting](#faq--troubleshooting)
- [License](#license)

---

## Install

### Option 1: pip install (recommended)

```bash
pip install terminus-game
```

This installs the `terminus` command and all dependencies automatically.

### Option 2: Install from GitHub (latest development version)

```bash
pip install git+https://github.com/kushal-DL/terminus.git
```

### Option 3: Clone and install from source

```bash
git clone https://github.com/kushal-DL/terminus.git
cd terminus
pip install .
```

For development (editable install with test dependencies):

```bash
pip install -e ".[dev]"
```

### Option 4: Pre-built executable (no Python needed)

Download the latest release for your platform from [GitHub Releases](https://github.com/kushal-DL/terminus/releases). Just download, extract, and run — no Python installation required.

### Prerequisites

- **Python 3.11 or newer** (for pip install methods)
- **Terminal with Unicode support** (Windows Terminal, iTerm2, most Linux terminals)
- **cloudflared** (optional — only for `--public` mode to share games over the internet)

---

## Run the Game

After installing, run the game with:

```bash
terminus
```

Or if the `terminus` command isn't found (see [FAQ](#faq--troubleshooting)):

```bash
python -m terminus
```

### Command-Line Options

| Flag | Description |
|------|-------------|
| `--port PORT` | Server port (default: 8080) |
| `--host HOST` | Server bind address (default: 0.0.0.0) |
| `--public` | Create a public URL via cloudflared tunnel |
| `--server-only` | Run headless server without TUI client |
| `--verbose` | Enable debug logging |

### Examples

```bash
terminus                     # Start game (server + client)
terminus --port 9090         # Use custom port
terminus --public            # Share over internet via tunnel
terminus --server-only       # Dedicated server mode
python -m terminus --verbose # Debug mode (alternative invocation)
```

---

## Step-by-Step: Playing Your First Game

### 1. Launch

```bash
pip install terminus-game
terminus
```

You'll see the main menu with retro terminal aesthetics.

### 2. Create a Game

- Select **"Create Game"**
- Enter your player name
- The game will start a local server and show you in the lobby

### 3. Choose Location & Specialization

Once the host starts the game, you'll pick:
- **Location** (Coast, Mountain, Plains, Forest, Desert) — affects production multipliers
- **Specialization** (Military, Trade, Science, Agriculture) — gives bonus effects

### 4. Play

The main colony screen shows your resources, workers, and buildings. Each "tick" (every few seconds):
- Workers produce resources based on their role
- Food is consumed by your population
- Buildings under construction make progress

### 5. Survive Catastrophes

Five catastrophes hit during the game. Build defenses, allocate workers to defense/medicine, and use the watchtower for early warnings.

### 6. Win

After all catastrophes, the player with the highest score wins! Score is based on: population, resources, buildings, morale, and survival.

---

## Multiplayer Setup

### Local Network (same WiFi/LAN)

1. **Host** runs: `terminus`
2. Host shares their local IP and port (shown in game), e.g. `http://192.168.1.50:8080`
3. **Players** run: `terminus` → "Join Game" → paste the URL

### Over the Internet (public URL)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. **Host** runs: `terminus --public`
3. A public URL (e.g. `https://abc-xyz.trycloudflare.com`) will be displayed
4. **Players** run: `terminus` → "Join Game" → paste the public URL

### Dedicated Server

```bash
terminus --server-only --port 8080
```

Players connect via the server's IP. The server runs headless (no TUI). Supports up to 250 concurrent players.

---

## Gameplay Guide

### Resources

| Resource | Produced By | Used For |
|----------|-------------|----------|
| 🌾 Food | Farming workers + Farm building | Feeding population (consumed each tick) |
| ⛏ Materials | Mining workers + Mine building | Building & repairing structures |
| 🔬 Knowledge | Research workers + Lab building | Unlocking upgrades |
| 💰 Gold | Trade + Market | Buying resources at market |

### Buildings (up to Level 3)

| Building | Effect |
|----------|--------|
| Farm | +food production |
| Wall | Reduces catastrophe damage |
| Hospital | +healing, reduces population loss |
| Lab | +knowledge production |
| Warehouse | Increases resource storage capacity |
| Housing | Increases max population |

### Worker Roles

| Role | Effect |
|------|--------|
| 🌾 Farming | Produces food |
| ⛏ Mining | Produces materials |
| 🔬 Research | Produces knowledge |
| 🔨 Construction | Speeds up building |
| 🛡 Defense | Reduces catastrophe damage |
| 💊 Medicine | Heals population after catastrophes |

### Key Strategies

- **Balance food production** — starvation kills morale and population
- **Build walls early** — reduces damage from all catastrophes
- **Watch the watchtower** — gives hints about the next catastrophe type
- **Trade wisely** — market prices fluctuate, buy low and sell high
- **Upgrade buildings** — level 2 and 3 buildings are significantly more powerful

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `terminus` | Launch game (server + TUI client) |
| `terminus --public` | Launch with public cloudflared URL |
| `terminus --server-only` | Headless dedicated server |
| `terminus --port PORT` | Custom port (default: 8080) |
| `terminus --verbose` | Debug logging |
| `python -m terminus` | Alternative invocation (no PATH needed) |
| `python -m terminus.dev --server URL` | Dev console (requires `TERMINUS_DEV_MODE=1`) |

---

## Dev Console (Admin Tools)

For debugging and testing, Terminus includes a dev console TUI:

```bash
# Start the game server first
terminus --server-only

# In another terminal, launch the dev console
# Windows PowerShell:
$env:TERMINUS_DEV_MODE = "1"
python -m terminus.dev --server http://127.0.0.1:8080

# Linux/macOS:
TERMINUS_DEV_MODE=1 python -m terminus.dev --server http://127.0.0.1:8080
```

**Features:**
- Real-time state inspection (resources, workers, buildings per player)
- Override player resources
- Trigger catastrophes instantly
- Speed up/slow down catastrophe intervals
- Instantly complete all buildings under construction

---

## Development

```bash
# Clone and install
git clone https://github.com/kushal-DL/terminus.git
cd terminus
pip install -e ".[dev]"

# Run tests (135 tests)
pytest tests/ -v

# Run balance simulator
python -m tools.balance.simulator --preset standard --games 10

# Run load test
python tools/load_test.py --players 20 --duration 60

# Build standalone executable
pip install -e ".[build]"
python tools/build_exe.py
```

---

## FAQ & Troubleshooting

### `terminus` command not found after install

**Cause:** pip installed the script to a directory not on your PATH.

**Fix (Windows):**
```powershell
# Option A: Use python -m (works immediately)
python -m terminus

# Option B: Add Scripts to PATH permanently
# pip shows the path in install output, e.g.:
# C:\Users\YOU\AppData\Local\...\Scripts
# Add that directory to your system PATH, then restart your terminal.
```

**Fix (Linux/macOS):**
```bash
# The script is usually in ~/.local/bin — add to PATH:
export PATH="$HOME/.local/bin:$PATH"
# Add to ~/.bashrc or ~/.zshrc to make permanent
```

### `ModuleNotFoundError: No module named 'textual'`

**Cause:** Dependencies didn't install into the same Python environment.

**Fix:**
```bash
pip install terminus-game --force-reinstall
```

### Port already in use

**Cause:** Another instance of the game (or another app) is using port 8080.

**Fix:**
```bash
terminus --port 9090  # Use a different port
```

### Game shows "Connection lost" or 401 errors

**Cause:** The server may have restarted or the session expired.

**Fix:** Return to the main menu and rejoin the game. If hosting, restart with `terminus`.

### Players can't connect to my game

**Cause:** Firewall blocking the port, or players are on a different network.

**Fix:**
- Ensure port 8080 (or your custom port) is open in your firewall
- For internet play, use `terminus --public` to create a cloudflared tunnel
- Players must use the exact URL shown in your game (including port)

### Build/upgrade/trade shows an error

**Cause:** Insufficient resources, building already at max level, or market stock depleted.

**Fix:** These are gameplay constraints, not bugs. The error message tells you exactly what's wrong:
- `"Insufficient gold (need 150.0)"` — earn more gold via trading or mining
- `"Building at max level"` — building is already level 3
- `"Insufficient market stock"` — wait for market to restock

### Game doesn't display correctly (garbled text)

**Cause:** Terminal doesn't support Unicode or is too small.

**Fix:**
- Use **Windows Terminal** (not cmd.exe) on Windows
- Resize terminal to at least 120×30 characters
- Ensure your terminal supports Unicode (UTF-8 encoding)

### `cloudflared` not found for `--public` mode

**Cause:** cloudflared is not installed.

**Fix:** Download from [Cloudflare Downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) and add to PATH. The game works without it (LAN only).

---

## License

MIT — see [LICENSE](LICENSE) for details.
