# Terminus

Multiplayer CLI survival strategy game — and LLM benchmark platform. Manage your settlement, allocate workers, build structures, survive catastrophes, and trade resources — all in your terminal. In benchmark mode, run any LLM through the same game and score it across 8 cognitive dimensions.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-594%20passing-brightgreen)
[![PyPI](https://img.shields.io/pypi/v/terminus-game)](https://pypi.org/project/terminus-game/)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Preview](#preview)
- [Install Options](#install-options)
- [Playing the Game](#playing-the-game)
- [Multiplayer Setup](#multiplayer-setup)
- [LLM Benchmark Mode](#llm-benchmark-mode)
- [Gameplay Guide](#gameplay-guide)
- [Audio](#audio)
- [Commands Reference](#commands-reference)
- [Dev Console](#dev-console)
- [Development](#development)
- [FAQ & Troubleshooting](#faq--troubleshooting)
- [License](#license)

---

## Quick Start

**Windows — double-click to play, no setup needed:**
1. [Download the repo](https://github.com/kushal-DL/terminus/archive/refs/heads/main.zip) and unzip
2. Double-click **`play.bat`**

That's it. The launcher creates a virtual environment, installs everything, and starts the game automatically. Subsequent launches are instant.

**Mac / Linux:**
```bash
git clone https://github.com/kushal-DL/terminus.git
cd terminus
bash play.sh
```

**pip install:**
```bash
pip install terminus-game
terminus
```

---

## Preview

<table>
<tr>
<td align="center"><strong>Main Menu</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/main-menu.gif" width="380" alt="Main menu and game creation flow"></td>
<td align="center"><strong>Colony Management</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/colony.gif" width="380" alt="Colony screen with live resources"></td>
</tr>
<tr>
<td align="center"><strong>Build & Upgrade</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/build.gif" width="380" alt="Building construction"></td>
<td align="center"><strong>Catastrophe!</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/catastrophe.gif" width="380" alt="Catastrophe event"></td>
</tr>
<tr>
<td align="center"><strong>Market Trading</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/market.gif" width="380" alt="Market buy and sell"></td>
<td align="center"><strong>Multiplayer Lobby</strong><br><img src="https://raw.githubusercontent.com/kushal-DL/terminus/develop/docs/gifs/lobby.gif" width="380" alt="Players joining lobby"></td>
</tr>
</table>

---

## Install Options

### Option 1: Launcher scripts (easiest — no terminal knowledge needed)

**Windows:** download the repo, double-click `play.bat`

**Mac/Linux:**
```bash
git clone https://github.com/kushal-DL/terminus.git && cd terminus && bash play.sh
```

The launcher automatically:
- Checks Python is installed (needs 3.11+)
- Creates a `.venv` virtual environment on first run
- Installs all dependencies
- Launches the game

### Option 2: pip install

```bash
pip install terminus-game
terminus
```

### Option 3: From source (for development)

```bash
git clone https://github.com/kushal-DL/terminus.git
cd terminus
pip install -e ".[dev]"
python -m terminus
```

### Prerequisites

- **Python 3.11 or newer** — download from [python.org](https://www.python.org/downloads/) (Windows: tick "Add Python to PATH")
- **Windows Terminal** recommended on Windows (not cmd.exe) for best Unicode rendering
- **cloudflared** — optional, only needed for `--public` internet multiplayer

---

## Playing the Game

```bash
terminus          # or: python -m terminus
```

### Command-Line Options

| Flag | Description |
|------|-------------|
| `--port PORT` | Server port (default: 8080) |
| `--host HOST` | Server bind address (default: 0.0.0.0) |
| `--public` | Create a public URL via cloudflared tunnel |
| `--server-only` | Run headless server without TUI client |
| `--verbose` | Enable debug logging |
| `--benchmark [CONFIG]` | Run LLM benchmark (see below) |

### Your First Game

1. **Launch** → Select **"Create Game"** → enter your name
2. **Choose location** (Coast, Mountain, Plains, Forest, Desert) and **specialization** (Military, Trade, Science, Agriculture)
3. **Manage your colony** — allocate workers, build structures, trade at the market
4. **Survive 5 catastrophes** — use the watchtower for early warnings, build defenses
5. **Highest score wins** — based on population, resources, buildings, and morale

---

## Multiplayer Setup

### Local Network (same WiFi)

1. **Host** runs: `terminus`
2. Host shares their IP and port shown in the lobby (e.g. `http://192.168.1.50:8080`)
3. **Players** run: `terminus` → "Join Game" → paste the URL

### Over the Internet

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. **Host** runs: `terminus --public`
3. A public URL (e.g. `https://abc-xyz.trycloudflare.com`) appears in the lobby
4. **Players** run: `terminus` → "Join Game" → paste the URL

### Dedicated Server

```bash
terminus --server-only --port 8080
```

---

## LLM Benchmark Mode

Terminus v0.3.0 ships a complete LLM benchmark platform. Run any LLM through headless games and score it across **8 cognitive dimensions** that predict production agentic performance.

### Quick benchmark run

```bash
# Copy and edit the example config
cp benchmark-config.example.json my-benchmark.json

# Run — no TUI needed
python run_benchmark.py my-benchmark.json
```

Or through the TUI:
```bash
terminus --benchmark   # opens the benchmark setup screen
```

### Config file format

```json
{
  "models": [
    {
      "name": "GPT-4o",
      "provider": "openai",
      "endpoint": "https://api.openai.com/v1",
      "model": "gpt-4o",
      "api_key_env": "OPENAI_API_KEY"
    }
  ],
  "games_per_matchup": 3,
  "max_turns": 100,
  "speed_multiplier": 5,
  "opponents": ["random", "greedy", "balanced"],
  "weight_preset": "balanced",
  "output_dir": "./benchmark-results"
}
```

Supported providers: `openai`, `anthropic`, `google`, `ollama` — and any OpenAI-compatible endpoint (NVIDIA Build, Together AI, Groq, vLLM, etc.).

For thinking/reasoning models (e.g. NVIDIA Nemotron):
```json
{
  "extra_body": {
    "chat_template_kwargs": {"enable_thinking": true},
    "reasoning_budget": 1024
  },
  "timeout_seconds": 180
}
```

### What gets measured

| Dimension | What it predicts |
|-----------|-----------------|
| Multi-Decision Coherence | Agent step budget before self-contradiction |
| Applied Arithmetic Under Load | Tool-call parameter reliability as context grows |
| Priority Triage | Incident response: does it address P0 before P2? |
| Compounding Error Recognition | Self-healing: catches snowballing mistakes early |
| Justified Pivot vs Inconsistency | Stable implementations vs constant rewrites |
| Graceful Degradation | SLA predictability — gradual vs cliff failure |
| Opportunity Cost Awareness | Solution quality ceiling |
| Game-Theoretic Sophistication | Multi-agent robustness |

### Outputs

Each run writes to `./benchmark-results/`:
- `*_report.html` — interactive report with dimension scores and rankings
- `*_results.json` — full structured data for programmatic analysis
- `*_summary.csv` — one row per model, all 8 dimensions as columns
- `*_detailed.csv` — one row per game
- `*_summary.md` — GitHub-ready markdown with archetype emoji

### 6 Built-in Opponents

| Opponent | Strategy | Tests |
|----------|----------|-------|
| Random | Uniform random actions | Baseline floor |
| Greedy | Maximises immediate value | Beats random but ignores future |
| Balanced | Optimal build order + smart allocation | "Par" opponent |
| Rush | Aggressive early expansion | Tests late-game consistency |
| Turtle | Heavy defense, slow growth | Tests patience and planning |
| Adversarial | Adapts to exploit LLM weaknesses | Tests manipulation resistance |

---

## Gameplay Guide

### Resources

| Resource | Produced By | Used For |
|----------|-------------|----------|
| 🌾 Food | Farming workers + Farm | Feeding population each tick |
| ⛏ Materials | Mining workers + Mine | Building and repairing |
| 🔬 Knowledge | Research workers + Lab | Upgrades |
| 💰 Gold | Trade + Market | Buying resources |

### Buildings (up to Level 3)

| Building | Effect |
|----------|--------|
| Farm | +food production |
| Mine | +materials production |
| Lab | +knowledge production |
| Market | +gold, market discounts |
| Hospital | Reduces plague/disease casualties |
| Wall | Reduces all catastrophe damage |
| Warehouse | Increases storage capacity |
| Housing | Increases max population |
| School | +knowledge, +morale |
| Watchtower | Catastrophe early warning |

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

- **Balance food production** — starvation kills morale and population fast
- **Build walls early** — reduces damage from all catastrophe types
- **Watch the watchtower** — gives hints about the next catastrophe
- **Trade wisely** — market prices fluctuate, buy low and sell high
- **Upgrade buildings** — level 2 and 3 are significantly more powerful

---

## Audio

Terminus includes retro 8-bit sound effects. Press **Ctrl+S** to toggle. For full audio support:

```bash
pip install terminus-game[audio]
```

On Windows, `winsound` is used as a fallback — no extra install needed. All sounds are synthesized in Python; no audio files are downloaded.

---

## Commands Reference

| Command | Description |
|---------|-------------|
| `terminus` | Launch game (server + TUI) |
| `terminus --public` | Launch with public cloudflared URL |
| `terminus --server-only` | Headless dedicated server |
| `terminus --port PORT` | Custom port (default: 8080) |
| `terminus --benchmark` | Open benchmark setup in TUI |
| `terminus --benchmark config.json` | Run benchmark headlessly from JSON config |
| `terminus --verbose` | Debug logging |
| `python -m terminus` | Alternative — works without PATH setup |

---

## Dev Console

```bash
# Start the game server
terminus --server-only

# In another terminal:
# Windows:
$env:TERMINUS_DEV_MODE = "1"; python -m terminus.dev --server http://127.0.0.1:8080

# Linux/macOS:
TERMINUS_DEV_MODE=1 python -m terminus.dev --server http://127.0.0.1:8080
```

Features: real-time state inspection, override resources, trigger catastrophes, speed up intervals, complete buildings instantly.

---

## Development

```bash
git clone https://github.com/kushal-DL/terminus.git
cd terminus
pip install -e ".[dev]"

# Run all tests (594 passing)
pytest

# Run fast subset (skips slow benchmark integration tests)
pytest -m "not slow"

# Run benchmark with mock LLM (no API key needed)
TERMINUS_BENCHMARK_MOCK=1 python -m terminus
```

---

## FAQ & Troubleshooting

### `play.bat` opens and closes instantly

Python is not installed or not on PATH. Install from [python.org](https://www.python.org/downloads/) — tick "Add Python to PATH" during install, then try again.

### `terminus` command not found after `pip install`

```bash
# Works immediately without PATH setup:
python -m terminus

# Or add pip's Scripts directory to PATH (shown in pip install output)
```

### `terminus` — "Access is denied" on Windows

```powershell
# Bypass the exe entirely — works the same:
python -m terminus
```

### `ModuleNotFoundError: No module named 'textual'`

```bash
pip install terminus-game --force-reinstall
```

### Port already in use

```bash
terminus --port 9090
```

### Game doesn't display correctly (garbled text)

Use **Windows Terminal** (not cmd.exe). Resize to at least 120×30 characters.

### Players can't connect

- Ensure port 8080 is open in your firewall
- For internet play, use `terminus --public`
- Players need the exact URL shown in your lobby (including port)

### LLM benchmark — model always returns PASS

Common causes:
1. **API key not set** — check with `terminus --benchmark config.json --verbose` and look for `401 Unauthorized`
2. **Windows env var not propagating** — use `run_benchmark.py` (sets key in Python, not shell)
3. **Model choosing PASS strategically** — valid behaviour; check the HTML report for reasoning factors

---

## License

MIT — see [LICENSE](LICENSE) for details.
