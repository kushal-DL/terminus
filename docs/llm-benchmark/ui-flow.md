# LLM Benchmark — User Interface & Flow

This document describes the TUI screens and user interactions for the benchmarking mode. The benchmark UI consists of 3 screens accessed from the main menu.

---

## Entry Point

From the main menu, a new button: **"[ LLM Benchmark ]"** (variant: warning/amber)

Alternatively via CLI: `terminus --benchmark` (headless) or `terminus --benchmark-config <path.json>` (CI mode)

---

## Screen Flow

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Main Menu  │────►│  Benchmark Setup │────►│  Benchmark Live  │────►│  Benchmark      │
│             │     │  (configuration) │     │  (monitoring)    │     │  Results        │
└─────────────┘     └──────────────────┘     └──────────────────┘     └─────────────────┘
       ▲                   │ Escape                                           │
       │                   ▼                                                  │
       │              Main Menu                                               │
       └──────────────────────────────────────────────────────────────────────┘
                                                                    "Return to Menu"
```

- Setup → Live: triggered by "Start Benchmark" button
- Live → Results: triggered automatically when benchmark completes
- Results → Menu: triggered by "Return to Menu" button
- Escape from Setup: returns to Main Menu
- Escape from Live: shows abort confirmation dialog

---

## Screen 1: Benchmark Setup

A single scrollable screen with all configuration parameters. The host configures everything here before starting.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        ═══ LLM BENCHMARK SETUP ═══                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─ LLM PROVIDERS ─────────────────────────────────────────────────────┐    ║
║  │                                                                      │    ║
║  │  # │ Name       │ Provider │ URL                    │ Status         │    ║
║  │ ───┼────────────┼──────────┼────────────────────────┼───────────     │    ║
║  │  1 │ GPT-4o     │ OpenAI   │ api.openai.com         │ ✓ Ready       │    ║
║  │  2 │ Claude 4   │ Anthropic│ api.anthropic.com      │ ✓ Ready       │    ║
║  │  3 │ Local-LLM  │ Ollama   │ localhost:11434        │ ✗ Unreachable │    ║
║  │                                                                      │    ║
║  │  [+ Add Model]  [Test All]                                           │    ║
║  │                                                                      │    ║
║  │  ┌─ Add Model Form (shown when [+ Add Model] pressed) ───────────┐  │    ║
║  │  │  Provider: [OpenAI ▼] [Anthropic] [Google] [Ollama/Local]      │  │    ║
║  │  │  URL:      [https://api.openai.com/v1___________________]      │  │    ║
║  │  │  API Key:  [●●●●●●●●●●●●●●●●●●●●●●●____________________]     │  │    ║
║  │  │  Model ID: [gpt-4o-2025-05-01__________________________ ]      │  │    ║
║  │  │  Name:     [GPT-4o___________________________________ __ ]      │  │    ║
║  │  │  [Save]  [Test Connection]  [Cancel]                            │  │    ║
║  │  └─────────────────────────────────────────────────────────────────┘  │    ║
║  └───────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌─ GAME PARAMETERS ───────────────────────────────────────────────────┐    ║
║  │                                                                      │    ║
║  │  Number of games:       [ 10  ] ▲▼     (per model × opponent)       │    ║
║  │  Speed multiplier:      [1×] [2×] [5×] [10×]                        │    ║
║  │  Number of catastrophes: [ 5  ] ▲▼     (per game)                   │    ║
║  │  Max turns per game:    [ 100 ] ▲▼                                   │    ║
║  │  Opponent depth:        [Quick (3)] [Standard (6)] [Deep (8)]        │    ║
║  │  Seed mode:             [Fixed] [Random]                             │    ║
║  │                                                                      │    ║
║  └───────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌─ COGNITIVE DIMENSIONS ──────────────────────────────────────────────┐    ║
║  │                                                                      │    ║
║  │  Dimension                              Enabled    Weight            │    ║
║  │  ─────────────────────────────────────  ────────   ──────            │    ║
║  │  1. Multi-Decision Coherence            [✓]        [ 1.0 ]           │    ║
║  │  2. Applied Arithmetic Under Load       [✓]        [ 1.0 ]           │    ║
║  │  3. Priority Triage                     [✓]        [ 1.0 ]           │    ║
║  │  4. Compounding Error Recognition       [✓]        [ 1.0 ]           │    ║
║  │  5. Justified Pivot                     [✓]        [ 1.0 ]           │    ║
║  │  6. Graceful Degradation                [✓]        [ 1.0 ]           │    ║
║  │  7. Opportunity Cost Awareness          [✓]        [ 1.0 ]           │    ║
║  │  8. Game-Theoretic Sophistication       [✓]        [ 1.0 ]           │    ║
║  │                                                                      │    ║
║  │  PRESETS:                                                            │    ║
║  │  [Balanced] [Reliability] [Strategy] [Triage] [Endurance]           │    ║
║  │  [Precision] [Adversarial] [Coordination] [Context]                  │    ║
║  │                                                                      │    ║
║  └───────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  ┌─ TIME ESTIMATES ────────────────────────────────────────────────────┐    ║
║  │                                                                      │    ║
║  │  Models: 2 │ Opponents: 6 │ Games per matchup: 10                   │    ║
║  │                                                                      │    ║
║  │  Est. per game:          ~3 min    (100 turns × ~2s avg latency)    │    ║
║  │  Est. total benchmark:   ~6 hours  (2 models × 6 opponents × 10)   │    ║
║  │  Total games:            120                                         │    ║
║  │                                                                      │    ║
║  └───────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  [← Back]                                          [Start Benchmark →]      ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Setup Screen Behavior:

- **Add Model form**: Hidden by default. Shown inline when "[+ Add Model]" pressed. Provider selector changes the URL placeholder and validation rules.
- **API Key**: Displayed masked (●●●●). Auto-detected from environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) — shows "(from env)" if found.
- **Test Connection**: Sends a minimal prompt ("Say OK") to verify the endpoint responds. Updates status to ✓ Ready or ✗ with error message.
- **Speed multiplier**: Radio-button style — only one active at a time. Active button highlighted green.
- **Opponent depth**: Radio-button style. Quick = Random+Greedy+Balanced. Standard = all 6 archetypes. Deep = Standard + adversarial adaptation.
- **Presets**: Clicking a preset auto-fills all 8 weights from the predefined distributions (see metrics.md). The active preset button is highlighted; editing any weight manually switches to "Custom" state.
- **Time estimates**: Recomputed reactively whenever games, speed, opponents, or model count changes. Formula: `per_game = max_turns × avg_latency / 60` (2s for cloud APIs, 0.3s for Ollama). `total = per_game × total_games`. `total_games = num_models × num_opponents × games_per_matchup`.
- **Start Benchmark**: Validates that ≥1 model is configured and reachable. Disabled (greyed out) if no models pass connection test.
- **Escape / Back**: Returns to main menu. Config is NOT persisted (must be re-entered each session).

### Keyboard Shortcuts (Setup):

| Key | Action |
|-----|--------|
| Escape | Return to main menu |
| Enter | Activate focused button |
| Tab / Shift+Tab | Navigate between fields |
| ↑/↓ | Adjust numeric inputs |

---

## Screen 2: Benchmark Live

Split-panel layout with leaderboard (left) and game state viewer (right). The host can watch any model's game state in real time.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ═══ BENCHMARK IN PROGRESS ═══                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Game 4/10 │ Turn 37/100 │ Speed: 2× │ Catastrophes: 2/5 │ ETA: ~8 min    ║
║  ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ 33%       ║
║                                                                              ║
╠═══════════════════════════════════╦══════════════════════════════════════════╣
║  LEADERBOARD                      ║  GAME STATE: [GPT-4o] [Claude 4] [All] ║
║                                   ║                                          ║
║  # │ Model     │ Score │ Game#    ║  ┌─ Resources ─────────────────────┐    ║
║  ──┼───────────┼───────┼────────  ║  │ Food:      [████████░░] 120/500 │    ║
║  1 │ GPT-4o    │  420  │  4/10   ║  │ Materials: [██████░░░░]  85/500 │    ║
║  2 │ Claude 4  │  385  │  4/10   ║  │ Knowledge: [███░░░░░░░]  40/300 │    ║
║  3 │ Greedy    │  310  │  4/10   ║  │ Gold:      [██████████] 200/200 │    ║
║                                   ║  └──────────────────────────────────┘    ║
║  Trend: GPT-4o ▲+12 │ Claude ▲+8 ║                                          ║
║                                   ║  Pop: 35/50 │ Morale: 82% │ Score: 420  ║
║  CUMULATIVE (all games):          ║                                          ║
║  ┌───────────┬───────┬────────┐   ║  ┌─ Buildings ────────────────────────┐ ║
║  │ Model     │ Avg   │W/L     │   ║  │ Farm L2 ♥100% │ Mine L1 ♥100%     │ ║
║  ├───────────┼───────┼────────┤   ║  │ Hospital L1 ♥80% │ Wall L2 ♥100%  │ ║
║  │ GPT-4o    │  780  │ 3/0    │   ║  │ Housing L1 ♥100% │ Market L1 ♥60% │ ║
║  │ Claude 4  │  740  │ 2/1    │   ║  └────────────────────────────────────┘ ║
║  └───────────┴───────┴────────┘   ║                                          ║
║                                   ║  ┌─ Workers ──────────────────────────┐ ║
║  ERRORS THIS GAME:                ║  │ Farm:8 Mine:6 Res:5 Con:8 Def:4    │ ║
║  GPT-4o: 0 invalid │ 0 retries   ║  │ Med:4                              │ ║
║  Claude:  1 invalid │ 0 retries   ║  └────────────────────────────────────┘ ║
║                                   ║                                          ║
║                                   ║  ┌─ Last 3 Actions ───────────────────┐ ║
║                                   ║  │ T37: ✓ BUILD mine                  │ ║
║                                   ║  │ T36: ✓ ALLOCATE_WORKERS            │ ║
║                                   ║  │ T35: ✗ TRADE_BUY food (no gold)    │ ║
║                                   ║  └────────────────────────────────────┘ ║
║                                   ║                                          ║
╠═══════════════════════════════════╩══════════════════════════════════════════╣
║  [Pause]  [Skip Game]  [Abort]               Est. per game: ~3 min         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Live Screen Behavior:

- **Progress bar**: Shows overall benchmark progress (`completed_games + current_turn_fraction`) / `total_games`.
- **Top status line**: Updates every tick. Shows current game#/total, turn#/max, speed, catastrophes encountered/total scheduled, ETA.
- **Leaderboard (left panel)**:
  - Shows all models + built-in opponents ranked by current game score
  - "Game#" column shows the current game number out of total for that model (e.g., "4/10")
  - Cumulative section shows average score and win/loss record across completed games
  - Error counter per model for current game
  - Refreshes every 500ms via orchestrator event queue
- **Game State Viewer (right panel)**:
  - Tab buttons at top: one per LLM model (not opponents). Plus `[All]` for compact summary.
  - Selected model's full colony state displayed with:
    - 4 `ResourceBar` widgets (food, materials, knowledge, gold) with current/capacity
    - Population, morale percentage, score
    - Building list: compact format "Type Lx ♥xx%" — red highlight if damaged
    - Worker allocation: single line, all 6 roles
    - Last 3 actions with turn number and ✓ (valid) or ✗ (invalid + reason)
  - `[All]` view shows 2-line summary per model: "ModelName: Score=420 Pop=35 Buildings=6 Last=BUILD mine ✓"
  - Red flash animation on invalid actions
- **Controls**:
  - `[Pause]` — toggles to `[Resume]` when paused. Stops between turns.
  - `[Skip Game]` — ends current game immediately, scores at current state, moves to next
  - `[Abort]` — shows confirmation dialog ("Abort benchmark? Partial results will be saved."). On confirm → push Results screen with data collected so far.
- **Auto-transition**: When all games complete, automatically pushes `BenchmarkResultsScreen`.

### Keyboard Shortcuts (Live):

| Key | Action |
|-----|--------|
| 1–9 | Switch game state viewer to model N |
| 0 / a | Switch to "All" compact view |
| p | Pause / Resume |
| s | Skip current game |
| Escape | Abort (with confirmation) |

---

## Screen 3: Benchmark Results

Displayed automatically when the benchmark completes (or when aborted with partial results). Shows final rankings, dimension scores, and the exported HTML report path. Vertically scrollable.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                       ═══ BENCHMARK COMPLETE ═══                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  120 games │ 11,847 total turns │ Duration: 2h 14m │ 2 models tested       ║
║                                                                              ║
║  ╔═══════════════════════════════════════════════════════════════════════╗   ║
║  ║  📄 HTML Report exported to:                                          ║   ║
║  ║     ./benchmark-results/2026-05-19T14-30_report.html                  ║   ║
║  ║                                                                       ║   ║
║  ║  [Open in Browser]                                                    ║   ║
║  ╚═══════════════════════════════════════════════════════════════════════╝   ║
║                                                                              ║
║  ─── FINAL RANKINGS ───────────────────────────────────────────────────     ║
║                                                                              ║
║  #  │ Model      │ Composite │ Trend      │ Archetype      │ Consistency   ║
║  ───┼────────────┼───────────┼────────────┼────────────────┼─────────────  ║
║  1  │ Claude 4   │   0.82    │ Improving  │ Strategist     │ ±0.04        ║
║  2  │ GPT-4o     │   0.78    │ Consistent │ Marathon Runner│ ±0.03        ║
║                                                                              ║
║  ─── DIMENSION BREAKDOWN ──────────────────────────────────────────────     ║
║                                                                              ║
║  Dimension                     │ GPT-4o │ Claude 4 │ Winner                 ║
║  ──────────────────────────────┼────────┼──────────┼────────                ║
║  1. Coherence + State Fidelity │  0.75  │   0.82   │ Claude 4              ║
║  2. Arithmetic Under Load      │  0.92  │   0.88   │ GPT-4o               ║
║  3. Priority Triage            │  0.70  │   0.80   │ Claude 4              ║
║  4. Error Recognition          │  0.68  │   0.74   │ Claude 4              ║
║  5. Justified Pivot            │  0.72  │   0.85   │ Claude 4              ║
║  6. Graceful Degradation       │  0.80  │   0.78   │ GPT-4o               ║
║  7. Opportunity Cost           │  0.83  │   0.79   │ GPT-4o               ║
║  8. Game-Theoretic             │  0.78  │   0.84   │ Claude 4              ║
║                                                                              ║
║  ─── TREND ANALYSIS ──────────────────────────────────────────────────      ║
║                                                                              ║
║  GPT-4o:    ████████████████████████████ Consistent (σ=0.03)               ║
║             Avg: 780 │ Best: 810 │ Worst: 770 │ Games won: 52/120          ║
║                                                                              ║
║  Claude 4:  ████████████████████████████████▶ Improving (+2.1%/game)       ║
║             Avg: 820 │ Best: 900 │ Worst: 700 │ Games won: 68/120          ║
║                                                                              ║
║  ─── ERROR SUMMARY ───────────────────────────────────────────────────      ║
║                                                                              ║
║  Model     │ Invalid Actions │ JSON Errors │ Timeouts │ DQ Games            ║
║  ──────────┼─────────────────┼─────────────┼──────────┼──────────           ║
║  GPT-4o    │      23 (1.9%)  │     0       │    1     │    0                ║
║  Claude 4  │      41 (3.4%)  │     2       │    0     │    0                ║
║                                                                              ║
║                                                                              ║
║  [Open in Browser]                                    [Return to Menu]      ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Results Screen Behavior:

- **HTML Report path**: Prominently displayed in a double-bordered box at the top. The report is auto-exported when the benchmark completes (no manual export step needed).
- **Report filename format**: `YYYY-MM-DDThh-mm_report.html` in `./benchmark-results/` directory.
- **"Open in Browser"**: Calls `webbrowser.open(report_path)` to open the HTML report in the user's default browser. The HTML report contains interactive charts, drill-down tables, and full per-game details.
- **Rankings table**: Shows composite score, trend classification, archetype label, and consistency (σ).
- **Dimension breakdown**: Shows all 8 dimension scores per model with winner highlighted.
- **Trend analysis**: ASCII bar charts + key stats (avg, best, worst, win count).
- **Error summary**: Compact error rates per model.
- **"Return to Menu"**: Pops all benchmark screens, returns to main menu.
- **Partial results**: If benchmark was aborted, header shows "BENCHMARK ABORTED — Partial Results (X/Y games)" and available data is displayed.

### Keyboard Shortcuts (Results):

| Key | Action |
|-----|--------|
| ↑/↓ | Scroll through results |
| PgUp/PgDn | Jump between sections |
| o | Open HTML report in browser |
| q / Escape | Return to main menu |

---

## Responsive Behavior

- **Minimum terminal size**: 80×24 (screens degrade gracefully at smaller sizes)
- **Wide terminal (>100 cols)**: Live screen panels expand; tables get more breathing room
- **Narrow terminal (<80 cols)**: Live screen stacks panels vertically (leaderboard on top, state viewer below)
- **Setup screen**: Always scrollable (content may exceed terminal height)

---

## Color Scheme (follows existing theme.tcss)

| Element | Color | Usage |
|---------|-------|-------|
| Panel borders | `#00ff41` (green) at 30% | Section boundaries |
| Active/selected | `#00ff41` (green) full | Active buttons, selected tabs |
| Warning/benchmark accent | `#ffb000` (amber) | Benchmark menu button, time estimates |
| Error/invalid | `#ff0040` (red) | Failed connections, invalid actions |
| Info/labels | `#00d4ff` (cyan) | Section headers, dimension names |
| Score/gold | `#ffd700` (gold) | Score values, report path box |
| Muted text | `#666680` | Descriptions, secondary info |
| Progress bar fill | `#00ff41` (green) | Benchmark progress |
| Progress bar empty | `#333350` | Unfilled portion |
