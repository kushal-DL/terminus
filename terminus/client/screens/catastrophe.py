"""Catastrophe event screen — dramatic display of incoming damage."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Label, Static

from terminus.client.art import get_catastrophe_art


class CatastropheScreen(Screen):
    """Shows catastrophe event and its results with ASCII art and damage animation."""

    BINDINGS = [("enter", "continue_game", "Continue"), ("escape", "continue_game", "Continue")]

    def __init__(self, event_data: dict, **kwargs):
        super().__init__(**kwargs)
        self.event_data = event_data
        self._auto_close_task: asyncio.Task | None = None
        self._damage_anim_task: asyncio.Task | None = None
        self._catastrophe_results: dict | None = None
        self._skip_requested: bool = False
        self._animation_done: bool = False

    def compose(self) -> ComposeResult:
        name = self.event_data.get("name", "CATASTROPHE")
        description = self.event_data.get("description", "")
        flavor = self.event_data.get("flavor_text", "")
        category = self.event_data.get("category", "")

        # Get art for this catastrophe category
        art = get_catastrophe_art(category)

        with Vertical(id="catastrophe-container"):
            yield Static( "╔══════════════════════════════════════════════╗", classes="panel-title")
            yield Static(f"║  ⚠  CATASTROPHE: {name.upper():25s}    ║", classes="panel-title")
            yield Static( "╚══════════════════════════════════════════════╝", classes="panel-title")
            yield Label("")
            if art:
                yield Static(art, id="catastrophe-art")
            yield Label(f"  {flavor}", id="flavor-text")
            yield Label("")
            yield Label(f"  {description}", id="description-text")
            yield Label("")
            yield Static("─── DAMAGE REPORT ───", classes="panel-title")
            yield Label("  👥 Population lost:   ...", id="dmg-population")
            yield Label("  🍞 Food lost:         ...", id="dmg-food")
            yield Label("  🪨 Materials lost:    ...", id="dmg-materials")
            yield Label("  🏗  Building damage:   ...", id="dmg-buildings")
            yield Label("")
            yield Label("", id="mitigation-display")
            yield Label("")
            yield Static("─── STANDINGS ───", classes="panel-title")
            yield Label("  (loading...)", id="mini-leaderboard")
            yield Label("")
            yield Button("▶ Continue [Enter]", id="btn-continue", variant="primary")
        yield Footer()

    def on_mount(self) -> None:
        self._auto_close_task = asyncio.create_task(self._wait_for_results())

    def receive_results(self, data: dict) -> None:
        """Called by ColonyScreen when catastrophe_results WS event arrives."""
        client = getattr(self.app, "_game_client", None)
        player_id = client.player_id if client else None
        # Store per-player results and the raw data
        self.event_data["results"] = data.get("results", {})
        if player_id and player_id in data.get("results", {}):
            self._catastrophe_results = data["results"][player_id]

    async def _wait_for_results(self) -> None:
        """Wait for catastrophe results from server, then animate damage numbers."""
        client = self.app._game_client  # type: ignore
        try:
            # Poll for state after catastrophe resolves
            pre_state = await client.get_state()
            pre_colony = pre_state.get("colony", {})
            pre_res = pre_colony.get("resources", {})
            pre_pop = pre_colony.get("population", 0)

            for _ in range(30):
                await asyncio.sleep(2)
                state = await client.get_state()
                if state.get("phase") == "playing":
                    # Catastrophe resolved — calculate damage
                    colony = state.get("colony", {})
                    res = colony.get("resources", {})
                    pop = colony.get("population", 0)

                    pre_pop = int(pre_pop)
                    pop = int(pop)
                    pop_lost = max(0, pre_pop - pop)
                    pre_food = int(pre_res.get("food", 0))
                    post_food = int(res.get("food", 0))
                    food_lost = max(0, pre_food - post_food)
                    pre_mat = int(pre_res.get("materials", 0))
                    post_mat = int(res.get("materials", 0))
                    mat_lost = max(0, pre_mat - post_mat)

                    # Build per-building damage details
                    pre_buildings = {b.get("building_type", ""): b for b in pre_colony.get("buildings", [])}
                    post_buildings = {b.get("building_type", ""): b for b in colony.get("buildings", [])}
                    bld_details: list[tuple[str, int, int]] = []  # (type, pre_hp, post_hp)
                    for btype, pre_b in pre_buildings.items():
                        pre_hp = int(pre_b.get("health", 100))
                        post_b = post_buildings.get(btype)
                        post_hp = int(post_b.get("health", 100)) if post_b else 0
                        if post_hp < pre_hp:
                            bld_details.append((btype, pre_hp, post_hp))

                    # Animate the damage numbers counting up
                    await self._animate_damage(
                        pre_pop, pop, pop_lost,
                        pre_food, post_food, food_lost,
                        pre_mat, post_mat, mat_lost,
                        bld_details,
                    )

                    # Show mini-leaderboard
                    await self._show_mini_leaderboard()
                    return
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _animate_damage(
        self,
        pre_pop: int, post_pop: int, pop_lost: int,
        pre_food: int, post_food: int, food_lost: int,
        pre_mat: int, post_mat: int, mat_lost: int,
        bld_details: list[tuple[str, int, int]],
    ) -> None:
        """Progressive staggered damage reveal — each stat starts with an offset."""
        steps = 15
        delay = 0.15
        # Stagger offsets: each stat starts animating N steps later
        offsets = [0, 3, 6, 9]  # pop, food, materials, buildings

        bld_text = self._format_building_damage(bld_details)

        for i in range(steps + offsets[-1] + 1):
            if self._skip_requested:
                break
            try:
                # Population (offset 0)
                frac_pop = min(1.0, max(0, i - offsets[0]) / steps)
                cur_lost = int(pop_lost * frac_pop)
                if frac_pop >= 1.0:
                    self.query_one("#dmg-population", Label).update(
                        f"  👥 Population: {pre_pop}→{post_pop} (lost {pop_lost})"
                    )
                elif frac_pop > 0:
                    self.query_one("#dmg-population", Label).update(
                        f"  👥 Population lost:   {cur_lost}"
                    )

                # Food (offset 3)
                frac_food = min(1.0, max(0, i - offsets[1]) / steps)
                cur_food = int(food_lost * frac_food)
                if frac_food >= 1.0:
                    self.query_one("#dmg-food", Label).update(
                        f"  🍞 Food: {pre_food}→{post_food} (lost {food_lost})"
                    )
                elif frac_food > 0:
                    self.query_one("#dmg-food", Label).update(
                        f"  🍞 Food lost:         {cur_food}"
                    )

                # Materials (offset 6)
                frac_mat = min(1.0, max(0, i - offsets[2]) / steps)
                cur_mat = int(mat_lost * frac_mat)
                if frac_mat >= 1.0:
                    self.query_one("#dmg-materials", Label).update(
                        f"  🪨 Materials: {pre_mat}→{post_mat} (lost {mat_lost})"
                    )
                elif frac_mat > 0:
                    self.query_one("#dmg-materials", Label).update(
                        f"  🪨 Materials lost:    {cur_mat}"
                    )

                # Buildings (offset 9)
                frac_bld = min(1.0, max(0, i - offsets[3]) / steps)
                if frac_bld > 0:
                    self.query_one("#dmg-buildings", Label).update(bld_text)

            except Exception:
                return
            await asyncio.sleep(delay)

        # Show final values immediately (in case of skip)
        try:
            self.query_one("#dmg-population", Label).update(
                f"  👥 Population: {pre_pop}→{post_pop} (lost {pop_lost})"
            )
            self.query_one("#dmg-food", Label).update(
                f"  🍞 Food: {pre_food}→{post_food} (lost {food_lost})"
            )
            self.query_one("#dmg-materials", Label).update(
                f"  🪨 Materials: {pre_mat}→{post_mat} (lost {mat_lost})"
            )
            self.query_one("#dmg-buildings", Label).update(bld_text)
        except Exception:
            pass

        # Show mitigation info + average comparison
        self._show_mitigation()
        self._show_avg_comparison(pop_lost, food_lost, mat_lost)
        self._animation_done = True

    BUILDING_ICONS = {
        "hospital": "🏥",
        "wall": "🏰",
        "farm": "🌾",
        "warehouse": "📦",
    }

    def _format_building_damage(self, bld_details: list[tuple[str, int, int]]) -> str:
        """Format per-building damage into a multi-line display string."""
        if not bld_details:
            return "  🏗  Building damage:   None"
        lines = [f"  🏗  Building damage:   {len(bld_details)} building(s)"]
        for btype, pre_hp, post_hp in bld_details:
            icon = self.BUILDING_ICONS.get(btype, "🏗 ")
            dmg = pre_hp - post_hp
            lines.append(f"    {icon} {btype.title()}: {pre_hp}→{post_hp} (-{dmg} hp)")
        return "\n".join(lines)

    def _show_mitigation(self) -> None:
        """Display mitigation summary after damage animation."""
        try:
            client = self.app._game_client  # type: ignore
            player_id = client.player_id
            results = self.event_data.get("results", {})
            player_result = results.get(player_id, {})
            mitigated_by = player_result.get("mitigated_by", [])

            if mitigated_by:
                lines = ["  ─── Mitigation ───"]
                for building in mitigated_by:
                    icon = self.BUILDING_ICONS.get(building, "🛡")
                    lines.append(f"  {icon} {building.title()} reduced damage!")
                self.query_one("#mitigation-display", Label).update("\n".join(lines))
        except Exception:
            pass

    def _show_avg_comparison(self, pop_lost: int, food_lost: int, mat_lost: int) -> None:
        """Show average loss comparison from catastrophe results."""
        try:
            results = self.event_data.get("results", {})
            if not results:
                return
            # Calculate average losses across all players
            all_pop_losses = []
            all_food_losses = []
            for _pid, r in results.items():
                all_pop_losses.append(r.get("population_lost", 0))
                all_food_losses.append(r.get("food_lost", 0))
            if all_pop_losses:
                avg_pop = sum(all_pop_losses) / len(all_pop_losses)
                avg_food = sum(all_food_losses) / len(all_food_losses)
                diff = pop_lost - avg_pop
                indicator = "▲ worse" if diff > 0 else ("▼ better" if diff < 0 else "= average")
                text = f"  ─── Average Comparison ───\n  Avg pop lost: {avg_pop:.0f}  │  You: {pop_lost} ({indicator})"
                try:
                    self.query_one("#mitigation-display", Label).update(
                        self.query_one("#mitigation-display", Label).renderable + "\n" + text  # type: ignore
                    )
                except Exception:
                    self.query_one("#mitigation-display", Label).update(text)
        except Exception:
            pass

    async def _show_mini_leaderboard(self) -> None:
        """Fetch and display top 5 players + current player rank."""
        try:
            client = self.app._game_client  # type: ignore
            scores = await client.get_leaderboard()
            if not scores:
                return

            player_id = client.player_id
            lines = []
            for i, s in enumerate(scores[:5], 1):
                name = s.get("name", "?")
                score = s.get("score", 0)
                marker = " ◄" if s.get("player_id") == player_id else ""
                lines.append(f"  #{i} {name:12s} {score:.0f}{marker}")

            # If player not in top 5, show their rank
            if player_id and not any(s.get("player_id") == player_id for s in scores[:5]):
                for i, s in enumerate(scores, 1):
                    if s.get("player_id") == player_id:
                        lines.append(f"  ...")
                        lines.append(f"  #{i} {s['name']:12s} {s['score']:.0f} ◄")
                        break

            self.query_one("#mini-leaderboard", Label).update("\n".join(lines))
        except Exception:
            self.query_one("#mini-leaderboard", Label).update("  (unavailable)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-continue":
            self.action_continue_game()

    def action_continue_game(self) -> None:
        if not self._animation_done:
            # First press: skip animation
            self._skip_requested = True
            return
        # Second press (or first if animation already done): close
        if self._auto_close_task:
            self._auto_close_task.cancel()
        self.app.pop_screen()

    def on_unmount(self) -> None:
        if self._auto_close_task:
            self._auto_close_task.cancel()
