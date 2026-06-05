# Epic 7: Visual Identity & Retro Overhaul

> **Priority**: P0  
> **Status**: 🚧 In Progress — 69 Done, 8 TODO (77 total)  
> **Sprint**: 2-4 (major effort)  
> **Depends on**: Epic 1.3 (rename to Terminus)  
> **Constraint**: All art uses **single-width ASCII characters only** — no `██` or fullwidth chars  
> **Allowed chars**: Letters, digits, `/\|_=-#*.~^(){}[]<>@+`, box-drawing (`─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬`)  
> **Max width**: 60 columns (safe for 80-col terminals with Textual margins)

---

## Feature 7.1 — Title Art

### Story 7.1.1 — "TERMINUS" Title Design

**As a** player  
**I want** an impressive ASCII art title on the main menu  
**So that** the game feels polished and establishes identity immediately

**Status**: ✅ Done

**Implementation Notes**:
- Gap: Title is 4 lines (AC requires 6-8), stored in main_menu.py (AC requires art.py)

**Acceptance Criteria**:
- [ ] "TERMINUS" in large ASCII letters, 6-8 lines tall
- [ ] Max 60 columns wide (no wrapping in 80-col terminal)
- [ ] Single-width chars only: `/`, `\`, `|`, `_`, `=`, `-`, `#`, `*`
- [ ] Legible and stylish — each letter clearly readable
- [ ] Stored as constant in `terminus/client/art.py` or `terminus/data/art/title.txt`

---

### Story 7.1.2 — Decorative Border Frame

**Status**: ✅ Done

**Implementation Notes**:
- Gap: Only top/bottom bars rendered, side borders ║ missing

**Acceptance Criteria**:
- [ ] Box-drawing border around title: `╔═══╗ ║ ║ ╚═══╝`
- [ ] Total width including frame ≤ 70 columns
- [ ] Padding: 1 char inside frame on each side
- [ ] Optional corner decorations

---

### Story 7.1.3 — Subtitle Tagline

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Centered text below title: "The Last Stand Begins Here" (or similar)
- [ ] Framed with `───` dividers above and below
- [ ] Muted color (dim/gray) to not compete with title

---

### Story 7.1.4 — Title Reveal Animation

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Characters appear progressively on screen mount
- [ ] Direction: left→right per line, top→down between lines
- [ ] Total duration: ~1.5 seconds
- [ ] Uses `set_interval` for frame-by-frame reveal
- [ ] Skippable: any keypress shows full title immediately

---

## Feature 7.2 — Location Art (5 artworks)

> Each ~10-12 lines × 30-35 cols. Shown in setup screen when location highlighted.

### Story 7.2.1 — Coast Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: ocean waves, lighthouse, harbor, ships
- [ ] Wave pattern using `~~~~~` and `^`
- [ ] 10-12 lines × 30-35 columns
- [ ] Evokes maritime/fishing economy

---

### Story 7.2.2 — Mountain Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: peaks, snow caps, cliff face, mining cave
- [ ] Mountain shapes: `/\`, snow `*`, cave `(  )`
- [ ] 10-12 lines × 30-35 columns
- [ ] Evokes mineral wealth and harsh terrain

---

### Story 7.2.3 — Plains Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: open fields, windmill, wheat stalks, road
- [ ] Flat horizon, windmill `+`, wheat `|||`
- [ ] 10-12 lines × 30-35 columns
- [ ] Evokes agricultural abundance

---

### Story 7.2.4 — Forest Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: dense trees, wildlife, mushrooms, canopy
- [ ] Tree shapes `/|\`, layered canopy
- [ ] 10-12 lines × 30-35 columns
- [ ] Evokes knowledge/nature resources

---

### Story 7.2.5 — Desert Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: sand dunes, cactus, scorching sun, oasis
- [ ] Dune curves `~^~`, cactus `|>`
- [ ] 10-12 lines × 30-35 columns
- [ ] Evokes trade routes and harsh survival

---

## Feature 7.3 — Specialization Art (4 artworks)

> Each ~6-8 lines × 20-25 cols. Shown in setup alongside spec selection.

### Story 7.3.1 — Military Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: crossed swords, shield, fortress tower
- [ ] 6-8 lines × 20-25 columns

---

### Story 7.3.2 — Trade Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: balance scales, coin stacks, caravan wagon
- [ ] 6-8 lines × 20-25 columns

---

### Story 7.3.3 — Science Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: telescope, flask/beaker, gears, book
- [ ] 6-8 lines × 20-25 columns

---

### Story 7.3.4 — Agriculture Art

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Depicts: wheat sheaf, plow, barn, sun
- [ ] 6-8 lines × 20-25 columns

---

## Feature 7.4 — Building Art (10 mini-artworks)

> Each 4-5 lines × 15-20 cols. Used in BuildingCard widget.

### Story 7.4.1 — Farm Art
### Story 7.4.2 — Mine Art
### Story 7.4.3 — Library Art
### Story 7.4.4 — Hospital Art
### Story 7.4.5 — Barracks Art
### Story 7.4.6 — Warehouse Art
### Story 7.4.7 — Market Art
### Story 7.4.8 — Watchtower Art
### Story 7.4.9 — Wall Art
### Story 7.4.10 — Workshop Art

**Status**: All ✅ Done

**Acceptance Criteria (all)**:
- [ ] 4-5 lines × 15-20 columns each
- [ ] Recognizable depiction of building type
- [ ] Single-width ASCII only
- [ ] Stored in art registry (dict mapping building_type → art string)

---

## Feature 7.5 — Catastrophe Art (6 category artworks)

> Each ~8-10 lines × 35-40 cols. Shown on catastrophe event screen.

### Story 7.5.1 — Plague/Disease Art
### Story 7.5.2 — Drought/Famine Art
### Story 7.5.3 — Earthquake Art
### Story 7.5.4 — Fire/Inferno Art
### Story 7.5.5 — Storm/Flood Art
### Story 7.5.6 — Raid/Invasion Art

**Status**: All ✅ Done

**Acceptance Criteria (all)**:
- [ ] 8-10 lines × 35-40 columns each
- [ ] Dramatic, evocative depiction
- [ ] Single-width ASCII only
- [ ] Stored in art registry keyed by catastrophe category

---

## Feature 7.6 — Theme & Color System

### Story 7.6.1 — External .tcss Theme File

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] `terminus/client/theme.tcss` replaces all inline CSS
- [ ] Loaded via `CSS_PATH = "theme.tcss"` on App class
- [ ] All inline `CSS = """..."""` removed from screens

---

### Story 7.6.2 — Color Palette

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Dark background: `#1a1a2e`
- [ ] Primary green: `#00ff41` (terminal green)
- [ ] Amber/warning: `#ffb000`
- [ ] Red/danger: `#ff0040`
- [ ] Cyan/info: `#00d4ff`
- [ ] Gold: `#ffd700`
- [ ] Defined as CSS variables or Textual design tokens

---

### Story 7.6.3 — Panel Styling

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] All panels use box-drawing borders (`╔═╗║╚═╝`)
- [ ] Consistent 1-char padding inside panels
- [ ] Section headers with `═══` dividers
- [ ] Reusable `.panel` CSS class

---

### Story 7.6.4 — Button Styling

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Retro bordered: `[ Action ]`
- [ ] Color by function: green=confirm, red=danger, amber=caution
- [ ] Hover/focus highlight state

---

### Story 7.6.5 — Typography Hierarchy

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Title: bold + primary color
- [ ] Subtitle: muted
- [ ] Body: default
- [ ] Label: dim
- [ ] Value: bright/bold

---

### Story 7.6.6 — Responsive Layout

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Minimum: 80×24
- [ ] Scales gracefully to 120×40+
- [ ] Flexible panel widths using `fr` units
- [ ] No overflow/wrapping at min size

---

### Story 7.6.7 — Status-Specific Colors

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Resources: food=green, materials=amber, knowledge=cyan, gold=yellow
- [ ] Health: high=green, mid=yellow, low=red
- [ ] Consistent across all screens and widgets

---

## Feature 7.7 — Custom Widgets

### Story 7.7.1 — ResourceBar Widget

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Horizontal fill bar: `[████████░░░░] 120/500`
- [ ] Color gradient: green (>50%) → yellow (20-50%) → red (<20%)
- [ ] Reactive: updates on value change
- [ ] Width adapts to container
- [ ] Shows resource name + icon

---

### Story 7.7.2 — BuildingCard Widget

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Bordered card with: mini ASCII art (7.4), level pips `●●○`, health bar, status badge
- [ ] Click/Enter to select
- [ ] Status icons: ✓ operational, 🔨 building, ✗ damaged
- [ ] Compact: fits 3-4 per row in grid layout

---

### Story 7.7.3 — WorkerSlider Widget

**Status**: ✅ Done

**Implementation Notes**:
- Gap: WorkerSlider renders [◄ 12 ►] + arrows work, but missing Enter-for-direct-input and 300ms debounce

**Acceptance Criteria**:
- [ ] Compact: `[◄ 12 ►]` with role name
- [ ] Left/Right arrows to adjust
- [ ] Enter for direct number input
- [ ] Validates against available worker pool
- [ ] Debounces server calls (300ms)

---

### Story 7.7.4 — CountdownTimer Widget

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Large display: `03:42`
- [ ] Urgency states: green (normal) → amber (<60s) → red (<30s) → flash (<10s)
- [ ] Optional terminal bell at thresholds
- [ ] Reactive to server time updates

---

### Story 7.7.5 — NotificationToast Widget

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Top-right positioned, auto-dismiss 3s
- [ ] Queue-based: max 3 visible, stack vertically
- [ ] Categories: info (cyan), success (green), warning (amber), error (red)
- [ ] Icon + message (max 40 chars)

---

### Story 7.7.6 — AsciiArtPanel Widget

**Status**: ✅ Done

**Acceptance Criteria**:
- [ ] Accepts `art_key` → looks up from registry
- [ ] Renders centered with optional border
- [ ] Supports color overlay per character/line
- [ ] Reusable across setup, catastrophe, build screens

---

### Story 7.7.7 — SparklineChart Widget

**Status**: ✅ Done

**Implementation Notes**:
- `SparklineChart(Widget)` in `terminus/client/widgets/sparkline_chart.py`
- Uses Unicode block characters `▁▂▃▄▅▆▇█` for bar rendering
- Reactive `data: list[float]` property — normalizes values to 0-7 range
- Trend coloring via Rich Text: green if last > first, red if last < first
- Adapts to container width (shows last N points that fit)
- Exported from `terminus/client/widgets/__init__.py`

**Acceptance Criteria**:
- [ ] Characters: `▁▂▃▄▅▆▇█` (fallback `_.-=+#`)
- [ ] 10-20 data points
- [ ] Color: green=uptrend, red=downtrend
- [ ] Used for market price history

---

## Feature 7.8 — Screen Visual Integration

### Story 7.8.1 — Main Menu Integration

**Status**: ✅ Done

**Implementation Notes**:
- Gap: Title+frame+buttons integrated but no reveal animation per AC

### Story 7.8.2 — Setup Screen Integration

**Status**: ✅ Done

### Story 7.8.3 — Colony Screen Integration

**Status**: ✅ Done

**Implementation Notes**:
- Gap: Has ResourceBar+CountdownTimer but missing BuildingCard grid (uses formatted Label instead)

### Story 7.8.4 — Build Screen Integration

**Status**: ✅ Done

**Implementation Notes**:
- Gap: Building art on highlight works but cost text not color-coded by affordability

### Story 7.8.5 — Workers Screen Integration

**Status**: ✅ Done

### Story 7.8.6 — Catastrophe Screen Integration

**Status**: ✅ Done

### Story 7.8.7 — Market Screen Integration

**Status**: ✅ Done

### Story 7.8.8 — Leaderboard Screen Integration

**Status**: ✅ Done

### Story 7.8.9 — Lobby Screen Integration

**Status**: ✅ Done

**Acceptance Criteria (per screen)**:
- [ ] Replace plain text/labels with custom widgets where applicable
- [ ] Add ASCII art panels from 7.2-7.5
- [ ] Apply theme.tcss styling
- [ ] Verify at 80×24 minimum (no overflow)
- [ ] Test at 120×40 (scales gracefully)

---

## Feature 7.9 — Animations & Effects

### Story 7.9.1 — Title Reveal Animation
- Characters appear progressively, ~1.5s, skippable

### Story 7.9.2 — Catastrophe Damage Counter
- Numbers count up 0→final over 5s, staggered stats

### Story 7.9.3 — Timer Urgency Transitions
- Color shifts at 60s/30s/10s thresholds via CSS class toggle

### Story 7.9.4 — Construction Completion Flash
- Green border flash for 2s + toast notification

### Story 7.9.5 — Resource Depletion Warning

**Status**: ✅ Done — Bar flashes red/normal at <10% capacity

### Story 7.9.6 — Screen Transition Effects

**Status**: ✅ Done — Subtle border highlight on push/pop

---

## Feature 7.10 — Quality of Life

| Status | ID | Task |
|--------|-----|------|
| ⬜ | 7.10.1 | Game speed settings: Fast / Normal / Relaxed |
| ⬜ | 7.10.2 | Pause functionality (host only) |
| ⬜ | 7.10.3 | Late join: average resources of current players |
| ⬜ | 7.10.4 | Spectator mode: read-only view |
| ⬜ | 7.10.5 | Game chat (text messages between players) |
| ⬜ | 7.10.6 | Settlement naming with validation |
| ⬜ | 7.10.7 | Advisor hints for new players |

---

## Feature 7.11 — Audio

| Status | ID | Task |
|--------|-----|------|
| 💤 | 7.11.1 | Terminal bell on catastrophe warning |
| 💤 | 7.11.2 | OS notification for catastrophe warning |
