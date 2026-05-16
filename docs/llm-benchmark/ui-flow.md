# LLM Benchmark — User Interface & Flow

This document describes the TUI screens and user interactions for the benchmarking mode.

---

## Entry Point

From the main menu, a new option: **"LLM Benchmark"**

Alternatively via CLI: `terminus --benchmark`

---

## Screen 1: LLM Configuration

```
╔══════════════════════════════════════════════════════════╗
║              ═══ LLM BENCHMARK SETUP ═══                ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  MODELS TO TEST:                                         ║
║  ┌──────────────────────────────────────────────────┐   ║
║  │ 1. GPT-4o        api.openai.com      ✓ Ready    │   ║
║  │ 2. Claude 4      api.anthropic.com   ✓ Ready    │   ║
║  │ 3. Gemini 2.5    generativelanguage  ✓ Ready    │   ║
║  │ [+] Add model...                                 │   ║
║  └──────────────────────────────────────────────────┘   ║
║                                                          ║
║  For each model, configure:                              ║
║  • API endpoint (OpenAI-compatible format)               ║
║  • API key (stored in local keyring)                     ║
║  • Model identifier (e.g., "gpt-4o-2025-01-01")         ║
║  • Display name (for charts)                             ║
║  • Temperature (default: 0.3)                            ║
║  • Max tokens per response (default: 1024)               ║
║                                                          ║
║  [Test Connection]  [Next →]                             ║
╚══════════════════════════════════════════════════════════╝
```

### Notes:
- All LLM APIs must be OpenAI-compatible (messages format)
- API keys stored in OS keyring (never in config files)
- "Test Connection" sends a simple prompt to verify connectivity
- Minimum 2 models required (or 1 model + built-in heuristic agent)

---

## Screen 2: Test Configuration

```
╔══════════════════════════════════════════════════════════╗
║              ═══ TEST CONFIGURATION ═══                  ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  GAME SETTINGS:                                          ║
║  ├─ Number of games:     [  10  ] ▲▼                    ║
║  ├─ Game speed:          [ 2×   ] ▲▼                    ║
║  ├─ Max turns per game:  [ 100  ] ▲▼                    ║
║  ├─ Players per game:    [  4   ] ▲▼                    ║
║  ├─ Map seed mode:       [Fixed / Random]               ║
║  └─ Include heuristic baseline: [Yes / No]              ║
║                                                          ║
║  EVALUATION METRICS:                    Weight           ║
║  ├─ [✓] Planning Horizon               [ 1.0 ] ▲▼      ║
║  ├─ [✓] Numerical Grounding            [ 1.0 ] ▲▼      ║
║  ├─ [✓] State Tracking Fidelity        [ 1.0 ] ▲▼      ║
║  ├─ [✓] Strategic Flexibility           [ 1.0 ] ▲▼      ║
║  ├─ [✓] Game-Theoretic Sophistication  [ 1.0 ] ▲▼      ║
║  └─ [✓] Context Window Utilization     [ 1.0 ] ▲▼      ║
║                                                          ║
║  PRESETS: [Balanced] [Strategy] [Reliability] [Custom]  ║
║                                                          ║
║  [← Back]  [Start Benchmark →]                          ║
╚══════════════════════════════════════════════════════════╝
```

### Notes:
- Checkboxes enable/disable individual metrics
- Weights only matter for the composite score — individual metric scores always shown
- Speed multiplier options: 1×, 2×, 5×, 10×, 20×
- Preset buttons auto-fill weight configurations

---

## Screen 3: Live Progress

```
╔══════════════════════════════════════════════════════════╗
║           ═══ BENCHMARK IN PROGRESS ═══                 ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Game 4 of 10 │ Turn 37/100 │ Speed: 2× │ ETA: ~8 min  ║
║  ════════════════════════════════════════                 ║
║  ████████████████████░░░░░░░░░░░░░░░░░░ 37%             ║
║                                                          ║
║  CURRENT SCORES:                                         ║
║  ┌──────────────┬────────┬────────┬────────┐            ║
║  │ Model        │ Score  │ Trend  │ Actions│            ║
║  ├──────────────┼────────┼────────┼────────┤            ║
║  │ GPT-4o       │  420   │  ▲ +12 │   37   │            ║
║  │ Claude 4     │  385   │  ▲ +8  │   35   │            ║
║  │ Gemini 2.5   │  310   │  ▼ -3  │   36   │            ║
║  │ Heuristic    │  290   │  ▲ +5  │   37   │            ║
║  └──────────────┴────────┴────────┴────────┘            ║
║                                                          ║
║  LAST ACTIONS:                                           ║
║  GPT-4o:    Built Solar Array (level 2)                  ║
║  Claude 4:  Sold 20 ore @ $14.50                         ║
║  Gemini:    Assigned 2 workers to Research Lab           ║
║                                                          ║
║  [Pause]  [Skip Game]  [Abort]                          ║
╚══════════════════════════════════════════════════════════╝
```

### Notes:
- Real-time updates as turns process
- ETA calculated from average turn processing time × remaining turns/games
- "Pause" stops between turns (useful for debugging)
- "Skip Game" ends current game early, moves to next
- "Abort" stops the entire benchmark (results so far are preserved)

---

## Screen 4: Results Dashboard (Scrollable)

The results screen is a vertically scrollable container. User scrolls with arrow keys/mouse wheel.

### Section A: Summary Header

```
═══════════════════════════════════════════════════════
         BENCHMARK RESULTS — 10 Games Complete
═══════════════════════════════════════════════════════

  Overall Rankings (Weighted Composite):
  ┌────┬──────────────┬────────┬───────────┬──────────┐
  │ #  │ Model        │ Score  │ Trend     │ Consistency │
  ├────┼──────────────┼────────┼───────────┼──────────┤
  │ 1  │ Claude 4     │ 0.82   │ Improving │ ±0.04    │
  │ 2  │ GPT-4o       │ 0.78   │ Consistent│ ±0.03    │
  │ 3  │ Gemini 2.5   │ 0.71   │ Volatile  │ ±0.12    │
  │ 4  │ Heuristic    │ 0.45   │ Consistent│ ±0.02    │
  └────┴──────────────┴────────┴───────────┴──────────┘
```

### Section B: Score Progression Chart (ASCII)

```
  Score Across Games
  1000 ┤
   900 ┤                              ╭──── Claude 4
   800 ┤           ╭───╮    ╭────╮  ╭─╯
   700 ┤     ╭─────╯   ╰────╯    ╰──╯─── GPT-4o
   600 ┤  ╭──╯
   500 ┤──╯        ╭╮  ╭╮                ── Gemini 2.5
   400 ┤     ╭─╮╭─╯╰──╯╰──╮   ╭╮
   300 ┤─────╯  ╰╯          ╰───╯╰───────── Heuristic
   200 ┤
       └──┬───┬───┬───┬───┬───┬───┬───┬───┬───┬──
          1   2   3   4   5   6   7   8   9   10
                          Game #
```

### Section C: Per-Metric Breakdown

```
  METRIC BREAKDOWN (per model):

  ┌──────────────────┬─────────┬─────────┬─────────┬──────────┐
  │ Metric           │ GPT-4o  │ Claude 4│ Gemini  │ Heuristic│
  ├──────────────────┼─────────┼─────────┼─────────┼──────────┤
  │ Planning Horizon │  0.81   │  0.85   │  0.72   │   0.40   │
  │ Numerical Ground │  0.92   │  0.88   │  0.78   │   0.95   │
  │ State Tracking   │  0.75   │  0.82   │  0.65   │   1.00   │
  │ Flexibility      │  0.70   │  0.80   │  0.74   │   0.30   │
  │ Game Theory      │  0.78   │  0.84   │  0.68   │   0.20   │
  │ Context Window   │  0.72   │  0.73   │  0.69   │   1.00   │
  └──────────────────┴─────────┴─────────┴─────────┴──────────┘
```

### Section D: Trend Analysis

```
  TREND CLASSIFICATION:

  GPT-4o:      ████████████████████████████ Consistent (σ=0.03)
               Scores: 780, 800, 770, 790, 810, 780, 800, 790, 795, 785

  Claude 4:    ████████████████████████████████▶ Improving (+2.1%/game)
               Scores: 700, 730, 760, 780, 810, 830, 850, 870, 880, 900

  Gemini 2.5:  ██▓▓██░░██▓▓██░░██▓▓██░░██ Volatile (σ=0.12)
               Scores: 600, 750, 500, 720, 680, 800, 550, 710, 640, 780

  Heuristic:   ████████████████████████████ Consistent (σ=0.02)
               Scores: 290, 295, 285, 290, 300, 285, 295, 290, 290, 280
```

### Section E: Detailed Per-Game Log (Collapsed by Default)

Expandable section showing turn-by-turn decisions for each game.

---

## Screen 5: Export

```
╔══════════════════════════════════════════════════════════╗
║              ═══ EXPORT RESULTS ═══                      ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Export format:                                          ║
║  ├─ [JSON] Full structured data (all games, all turns)  ║
║  ├─ [CSV]  Summary table (one row per model per game)   ║
║  └─ [MD]   Markdown report with ASCII charts            ║
║                                                          ║
║  Export path: ./benchmark-results/                        ║
║                                                          ║
║  Files to generate:                                      ║
║  • results-summary.{json|csv|md}                         ║
║  • per-game-detail.{json|csv}                            ║
║  • metric-scores.{json|csv}                              ║
║  • raw-actions.json (full action log)                    ║
║                                                          ║
║  [Export All]  [Export Selected]  [← Back to Results]   ║
╚══════════════════════════════════════════════════════════╝
```

---

## Keyboard Shortcuts (Results Screen)

| Key | Action |
|-----|--------|
| ↑/↓ | Scroll through charts |
| PgUp/PgDn | Jump between sections |
| Tab | Cycle focus between models in charts |
| E | Open export dialog |
| R | Re-run benchmark with same config |
| Q | Return to main menu |
| 1-6 | Toggle individual metric visibility in charts |
| W | Toggle between weighted and unweighted view |
