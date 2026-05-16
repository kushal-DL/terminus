"""How to Play screen — game rules and mechanics."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Label, Markdown, Static


HELP_TEXT = """
# How to Play Terminus

## Objective
Manage your settlement to survive a series of catastrophes. The player with the
highest score at the end wins!

## Game Flow
1. **Lobby** — Host creates game, players join and ready up
2. **Setup** — Choose your settlement location and specialization (90 seconds)
3. **Play** — Manage resources, build structures, trade with NPCs
4. **Catastrophes** — Every ~7-8 minutes, a disaster strikes!
5. **Final Score** — After all catastrophes, rankings are revealed

## Resources
- **Food** 🍞 — Feeds your population. If food runs out, people starve.
- **Materials** 🪨 — Used for building and repairs.
- **Knowledge** 📚 — Research points for advanced structures.
- **Gold** 💰 — Currency for trading at the NPC market.
- **Morale** 😊 — Multiplier on all production (0.5x to 1.5x).

## Workers
Assign your population to roles:
- **Farming** — Produces food
- **Mining** — Produces materials
- **Research** — Produces knowledge
- **Construction** — Speeds up building construction
- **Defense** — Reduces raid/attack damage
- **Medicine** — Reduces plague/disease damage

## Buildings
- **Farm** — Boosts food production
- **Mine** — Boosts material production
- **Lab** — Boosts knowledge production
- **Market** — Boosts gold + enables NPC trading
- **Hospital** — Mitigates plague/disease
- **Wall** — Mitigates raids, floods, earthquakes
- **Warehouse** — Increases resource storage capacity
- **Housing** — Increases max population
- **School** — Boosts knowledge + morale
- **Watchtower** — Reveals hints about next catastrophe

## Catastrophes
- 5-6 catastrophes per game, drawn from a pool of 20
- Each targets different resources/buildings
- Build the right defenses to mitigate damage!
- **Watchtower** reveals what's coming next

## Scoring
Final score = Population × 10 + Resources + Buildings + Knowledge × 3 + Morale × 200

## Tips
- Balance your workers — don't neglect any role
- Build a Watchtower early for intel
- Trade at the market when prices are low
- Keep food surplus above 50 for population growth
"""


class HelpScreen(Screen):
    """Displays game rules and instructions."""

    BINDINGS = [("escape", "go_back", "Back"), ("q", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Markdown(HELP_TEXT)
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()
