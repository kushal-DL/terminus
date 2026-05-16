"""Market screen — buy and sell resources with price trend indicators."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from terminus.client.api import GameClient
from terminus.client.widgets.sparkline_chart import SparklineChart


class MarketScreen(Screen):
    """NPC market for buying and selling resources."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._prev_prices: dict[str, float] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="market-container"):
            yield Static("═══ NPC MARKET ═══", classes="panel-title")

            # Price display panel
            with Vertical(id="price-panel"):
                yield Static("┌─── Current Prices ───────────────────────┐", id="price-header")
                yield Label("  Loading...", id="market-prices")
                yield SparklineChart(label="Food", id="spark-food")
                yield SparklineChart(label="Mats", id="spark-materials")
                yield SparklineChart(label="Know", id="spark-knowledge")
                yield SparklineChart(label="Gold", id="spark-gold")
                yield Static("└──────────────────────────────────────────┘", id="price-footer")

            # Transaction panel
            with Vertical(id="trade-panel"):
                yield Static("┌─── Transaction ──────────────────────────┐", id="trade-header")
                yield Label("  Select resource:")
                yield OptionList(
                    Option("Food", id="food"),
                    Option("Materials", id="materials"),
                    Option("Knowledge", id="knowledge"),
                    id="resource-list",
                )
                yield Label("  Quantity:")
                yield Input(placeholder="10", id="input-qty", type="integer")
                with Horizontal(id="trade-buttons"):
                    yield Button("Buy ◄", id="btn-buy", variant="success")
                    yield Button("► Sell", id="btn-sell", variant="warning")
                yield Static("└──────────────────────────────────────────┘", id="trade-footer")

            # Trade history panel
            with Vertical(id="history-panel"):
                yield Static("┌─── Trade History ────────────────────────┐", id="history-header")
                yield DataTable(id="trade-history-table")
                yield Static("└──────────────────────────────────────────┘", id="history-footer")

            yield Label("", id="market-status")
            yield Button("← Back [Esc]", id="btn-back")
        yield Footer()

    async def on_mount(self) -> None:
        # Initialize trade history table
        table = self.query_one("#trade-history-table", DataTable)
        table.add_columns("Tick", "Action", "Resource", "Qty", "Price", "Total")

        await self._refresh_prices()
        await self._refresh_trade_history()
        # Register for market_update WS events
        client: GameClient = self.app._game_client  # type: ignore
        original_handler = client._event_handler

        async def _market_handler(event: str, data: dict) -> None:
            if event == "market_update":
                self._update_price_display(data.get("prices", {}), data.get("stock", {}))
            if original_handler:
                await original_handler(event, data)

        client.set_event_handler(_market_handler)

    async def _refresh_prices(self) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            market = await client.get_market()
            prices = market.get("prices", {})
            stock = market.get("stock", {})
            self._update_price_display(prices, stock)
            price_history = market.get("price_history", [])
            self._update_sparklines(price_history)
        except Exception:
            pass

    async def _refresh_trade_history(self) -> None:
        client: GameClient = self.app._game_client  # type: ignore
        try:
            state = await client.get_state()
            history = state.get("trade_history", [])
            table = self.query_one("#trade-history-table", DataTable)
            table.clear()
            # Show last 10 trades, most recent first
            for trade in reversed(history[-10:]):
                action_str = "BUY" if trade["action"] == "buy" else "SELL"
                table.add_row(
                    str(trade.get("tick", "")),
                    action_str,
                    trade.get("resource", "").capitalize(),
                    str(trade.get("quantity", "")),
                    f"{trade.get('price_per_unit', 0):.1f}g",
                    f"{trade.get('total', 0):.1f}g",
                )
        except Exception:
            pass

    def _update_price_display(self, prices: dict, stock: dict) -> None:
        """Format price display with trend arrows and color hints."""
        lines = []
        for resource, price in prices.items():
            s = stock.get(resource, 0)
            # Determine trend arrow
            prev = self._prev_prices.get(resource)
            if prev is not None:
                if price > prev:
                    trend = "▲"  # price went up (bad for buyer)
                elif price < prev:
                    trend = "▼"  # price went down (good for buyer)
                else:
                    trend = "─"
            else:
                trend = " "
            lines.append(f"  {trend} {resource.capitalize():12s} {price:5.1f}g  │  Stock: {s:.0f}")

        self._prev_prices = dict(prices)
        try:
            self.query_one("#market-prices", Label).update("\n".join(lines))
        except Exception:
            pass

    def _update_sparklines(self, price_history: list[dict]) -> None:
        """Update sparkline widgets from market price history."""
        resource_map = {
            "food": "#spark-food",
            "materials": "#spark-materials",
            "knowledge": "#spark-knowledge",
            "gold": "#spark-gold",
        }
        for resource, widget_id in resource_map.items():
            try:
                spark = self.query_one(widget_id, SparklineChart)
                values = [h.get(resource, 0) for h in price_history if resource in h]
                spark.data = values
            except Exception:
                pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
            return

        option_list = self.query_one("#resource-list", OptionList)
        highlighted = option_list.highlighted
        if highlighted is None:
            self.query_one("#market-status", Label).update("⚠ Select a resource")
            return

        resource = option_list.get_option_at_index(highlighted).id
        qty_input = self.query_one("#input-qty", Input)
        try:
            qty = int(qty_input.value or "0")
        except ValueError:
            qty = 0

        if qty <= 0:
            self.query_one("#market-status", Label).update("⚠ Enter a valid quantity")
            return

        client: GameClient = self.app._game_client  # type: ignore
        status = self.query_one("#market-status", Label)

        try:
            if event.button.id == "btn-buy":
                result = await client.submit_action("trade_buy", {"resource": resource, "quantity": qty})
                status.update(f"✓ Bought {qty} {resource} for {result.get('cost', 0):.1f} gold")
                self.app.notify_toast(f"✓ Bought {qty} {resource}", "success")
            elif event.button.id == "btn-sell":
                result = await client.submit_action("trade_sell", {"resource": resource, "quantity": qty})
                status.update(f"✓ Sold {qty} {resource} for {result.get('revenue', 0):.1f} gold")
                self.app.notify_toast(f"✓ Sold {qty} {resource}", "success")
            await self._refresh_prices()
            await self._refresh_trade_history()
        except Exception as e:
            status.update(f"✗ {e}")
            self.app.notify_toast(str(e), "error")

    def action_go_back(self) -> None:
        self.app.pop_screen()
