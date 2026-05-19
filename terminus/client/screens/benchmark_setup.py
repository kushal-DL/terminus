"""Benchmark Setup screen — configure LLM providers, game parameters, and dimensions."""

from __future__ import annotations

import os
import math

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Label, Static, Switch
from textual.reactive import reactive


# ─── Weight Presets (from metrics.md) ─────────────────────────────────────────
DIMENSION_NAMES = [
    "Multi-Decision Coherence",
    "Applied Arithmetic Under Load",
    "Priority Triage",
    "Compounding Error Recognition",
    "Justified Pivot",
    "Graceful Degradation",
    "Opportunity Cost Awareness",
    "Game-Theoretic Sophistication",
]

PRESETS = {
    "Balanced": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "Reliability": [1.5, 2.0, 1.0, 1.5, 0.5, 2.0, 0.5, 0.5],
    "Strategy": [1.0, 0.5, 1.5, 1.0, 2.0, 0.5, 2.0, 1.5],
    "Triage": [0.5, 1.0, 3.0, 2.0, 1.0, 1.0, 0.5, 0.5],
    "Endurance": [2.5, 1.5, 0.5, 1.0, 1.0, 2.5, 0.5, 0.5],
    "Precision": [0.5, 3.0, 1.0, 1.0, 0.5, 1.0, 2.0, 1.0],
    "Adversarial": [1.0, 1.5, 1.0, 0.5, 1.5, 1.0, 1.0, 3.0],
    "Coordination": [1.5, 1.0, 1.0, 1.0, 1.5, 1.0, 1.0, 2.5],
    "Context": [2.0, 1.5, 0.5, 1.0, 0.5, 2.5, 0.5, 0.5],
}

SPEED_OPTIONS = [1, 2, 5, 10]
OPPONENT_CONFIGS = {"Quick (3)": 3, "Standard (6)": 6, "Deep (8)": 8}


class BenchmarkSetupScreen(Screen):
    """Configuration screen for LLM benchmark parameters."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    # ─── Reactive state ──────────────────────────────────────────────────────
    num_games: reactive[int] = reactive(10)
    speed_multiplier: reactive[int] = reactive(2)
    num_catastrophes: reactive[int] = reactive(5)
    max_turns: reactive[int] = reactive(100)
    num_opponents: reactive[int] = reactive(6)
    seed_fixed: reactive[bool] = reactive(True)
    active_preset: reactive[str] = reactive("Balanced")

    def __init__(self) -> None:
        super().__init__()
        self._models: list[dict] = []
        self._weights: list[float] = list(PRESETS["Balanced"])
        self._enabled_dims: list[bool] = [True] * 8
        self._show_add_form: bool = False

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="benchmark-setup-scroll"):
            yield Static("╔══════════════════════════════════════════════╗", classes="bench-header")
            yield Static("║          LLM BENCHMARK SETUP                ║", classes="bench-header")
            yield Static("╚══════════════════════════════════════════════╝", classes="bench-header")

            # ─── LLM Providers Section ────────────────────────────
            yield Label("")
            yield Static("─── LLM Providers ───", classes="panel-title")
            yield Label("")
            yield Static("", id="models-list")
            yield Label("")
            with Horizontal(id="model-actions"):
                yield Button("[+ Add Model]", id="btn-add-model", variant="success")
                yield Button("[Test All]", id="btn-test-all", variant="primary")

            # Add model form (hidden initially)
            with Vertical(id="add-model-form", classes="hidden"):
                yield Label("")
                yield Static("  ┌─ Add Model ────────────────────────────────┐", classes="panel-title")
                with Horizontal(classes="form-row"):
                    yield Label("  Provider: ", classes="form-label")
                    yield Button("OpenAI", id="btn-prov-openai", classes="provider-btn provider-active")
                    yield Button("Anthropic", id="btn-prov-anthropic", classes="provider-btn")
                    yield Button("Google", id="btn-prov-google", classes="provider-btn")
                    yield Button("Ollama", id="btn-prov-ollama", classes="provider-btn")
                with Horizontal(classes="form-row"):
                    yield Label("  URL:      ", classes="form-label")
                    yield Input(placeholder="https://api.openai.com/v1", id="input-url")
                with Horizontal(classes="form-row"):
                    yield Label("  API Key:  ", classes="form-label")
                    yield Input(placeholder="sk-... (or leave blank for env var)", id="input-apikey", password=True)
                with Horizontal(classes="form-row"):
                    yield Label("  Model ID: ", classes="form-label")
                    yield Input(placeholder="gpt-4o", id="input-model-id")
                with Horizontal(classes="form-row"):
                    yield Label("  Name:     ", classes="form-label")
                    yield Input(placeholder="GPT-4o", id="input-display-name")
                yield Label("")
                with Horizontal(classes="form-row"):
                    yield Button("[Save]", id="btn-save-model", variant="success")
                    yield Button("[Test Connection]", id="btn-test-single", variant="primary")
                    yield Button("[Cancel]", id="btn-cancel-add", variant="error")
                yield Static("  └──────────────────────────────────────────────┘", classes="panel-title")

            # ─── Game Parameters Section ──────────────────────────
            yield Label("")
            yield Static("─── Game Parameters ───", classes="panel-title")
            yield Label("")
            with Horizontal(classes="form-row"):
                yield Label("  Number of games:        ", classes="form-label")
                yield Button("−", id="btn-games-down", classes="spinner-btn")
                yield Label("  10  ", id="lbl-num-games", classes="spinner-value")
                yield Button("+", id="btn-games-up", classes="spinner-btn")
                yield Label("  (per model × opponent)", classes="text-muted")
            with Horizontal(classes="form-row"):
                yield Label("  Speed multiplier:       ", classes="form-label")
                yield Button("1×", id="btn-speed-1", classes="speed-btn")
                yield Button("2×", id="btn-speed-2", classes="speed-btn speed-active")
                yield Button("5×", id="btn-speed-5", classes="speed-btn")
                yield Button("10×", id="btn-speed-10", classes="speed-btn")
            with Horizontal(classes="form-row"):
                yield Label("  Number of catastrophes: ", classes="form-label")
                yield Button("−", id="btn-cats-down", classes="spinner-btn")
                yield Label("  5   ", id="lbl-num-cats", classes="spinner-value")
                yield Button("+", id="btn-cats-up", classes="spinner-btn")
                yield Label("  (per game)", classes="text-muted")
            with Horizontal(classes="form-row"):
                yield Label("  Max turns per game:     ", classes="form-label")
                yield Button("−", id="btn-turns-down", classes="spinner-btn")
                yield Label("  100 ", id="lbl-max-turns", classes="spinner-value")
                yield Button("+", id="btn-turns-up", classes="spinner-btn")
            with Horizontal(classes="form-row"):
                yield Label("  Opponent depth:         ", classes="form-label")
                yield Button("Quick (3)", id="btn-opp-quick", classes="opp-btn")
                yield Button("Standard (6)", id="btn-opp-standard", classes="opp-btn opp-active")
                yield Button("Deep (8)", id="btn-opp-deep", classes="opp-btn")
            with Horizontal(classes="form-row"):
                yield Label("  Seed mode:              ", classes="form-label")
                yield Button("Fixed", id="btn-seed-fixed", classes="seed-btn seed-active")
                yield Button("Random", id="btn-seed-random", classes="seed-btn")

            # ─── Cognitive Dimensions Section ─────────────────────
            yield Label("")
            yield Static("─── Cognitive Dimensions ───", classes="panel-title")
            yield Label("")
            yield Static("  Dimension                            Enabled  Weight", classes="text-muted")
            yield Static("  ─────────────────────────────────────────────────────", classes="text-muted")
            for i, dim_name in enumerate(DIMENSION_NAMES):
                with Horizontal(classes="dim-row"):
                    yield Label(f"  {i+1}. {dim_name:<36}", classes="dim-label")
                    yield Switch(value=True, id=f"sw-dim-{i}")
                    yield Label("  ", classes="dim-spacer")
                    yield Input(value="1.0", id=f"input-weight-{i}", classes="weight-input")
            yield Label("")
            yield Static("  Presets:", classes="panel-title")
            with Horizontal(id="preset-buttons"):
                for preset_name in PRESETS:
                    active_cls = "preset-active" if preset_name == "Balanced" else ""
                    yield Button(
                        preset_name,
                        id=f"btn-preset-{preset_name.lower()}",
                        classes=f"preset-btn {active_cls}",
                    )

            # ─── Time Estimates Section ───────────────────────────
            yield Label("")
            yield Static("─── Time Estimates ───", classes="panel-title")
            yield Label("")
            yield Static("", id="estimate-summary")
            yield Label("")
            yield Static("", id="estimate-per-game")
            yield Static("", id="estimate-total")
            yield Static("", id="estimate-total-games")

            # ─── Bottom Actions ───────────────────────────────────
            yield Label("")
            with Horizontal(id="bottom-bar"):
                yield Button("← Back", id="btn-back", variant="default")
                yield Button("Start Benchmark →", id="btn-start", variant="success", disabled=True)
        yield Footer()

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._refresh_models_list()
        self._refresh_estimates()
        self._refresh_speed_buttons()
        self._refresh_opp_buttons()
        self._refresh_seed_buttons()
        self._auto_detect_env_keys()

    # ─── Auto-detect API keys from environment ───────────────────────────────

    def _auto_detect_env_keys(self) -> None:
        """Pre-populate models from well-known env vars."""
        env_models = []
        if os.environ.get("OPENAI_API_KEY"):
            env_models.append({
                "provider": "OpenAI",
                "url": "https://api.openai.com/v1",
                "api_key": os.environ["OPENAI_API_KEY"],
                "model_id": "gpt-4o",
                "name": "GPT-4o",
                "status": "untested",
            })
        if os.environ.get("ANTHROPIC_API_KEY"):
            env_models.append({
                "provider": "Anthropic",
                "url": "https://api.anthropic.com",
                "api_key": os.environ["ANTHROPIC_API_KEY"],
                "model_id": "claude-sonnet-4-20250514",
                "name": "Claude Sonnet",
                "status": "untested",
            })
        if os.environ.get("GOOGLE_API_KEY"):
            env_models.append({
                "provider": "Google",
                "url": "https://generativelanguage.googleapis.com",
                "api_key": os.environ["GOOGLE_API_KEY"],
                "model_id": "gemini-2.5-flash",
                "name": "Gemini 2.5",
                "status": "untested",
            })
        if env_models:
            self._models = env_models
            self._refresh_models_list()

    # ─── Model list display ──────────────────────────────────────────────────

    def _refresh_models_list(self) -> None:
        """Update the models list display."""
        if not self._models:
            text = "  No models configured. Add at least one model to begin."
        else:
            lines = ["  # │ Name         │ Provider  │ URL                      │ Status"]
            lines.append("  ──┼──────────────┼───────────┼──────────────────────────┼────────────")
            for i, m in enumerate(self._models, 1):
                status_icon = {"ready": "✓ Ready", "untested": "? Untested", "failed": "✗ Failed"}.get(
                    m["status"], "? Unknown"
                )
                url_short = m["url"][:24]
                lines.append(
                    f"  {i} │ {m['name']:<12} │ {m['provider']:<9} │ {url_short:<24} │ {status_icon}"
                )
            text = "\n".join(lines)
        self.query_one("#models-list", Static).update(text)
        # Enable/disable start button
        has_ready = any(m["status"] == "ready" for m in self._models)
        self.query_one("#btn-start", Button).disabled = not has_ready
        self._refresh_estimates()

    # ─── Time Estimates ──────────────────────────────────────────────────────

    def _refresh_estimates(self) -> None:
        """Recompute and display time estimates."""
        num_models = max(len(self._models), 1)
        total_games = num_models * self.num_opponents * self.num_games
        # Assume ~2s per turn for cloud APIs as baseline
        avg_latency_s = 2.0
        per_game_s = self.max_turns * avg_latency_s
        per_game_min = per_game_s / 60
        total_s = per_game_s * total_games
        total_min = total_s / 60

        def fmt_time(minutes: float) -> str:
            if minutes < 60:
                return f"~{math.ceil(minutes)} min"
            hours = minutes / 60
            if hours < 24:
                return f"~{hours:.1f} hours"
            return f"~{hours / 24:.1f} days"

        try:
            self.query_one("#estimate-summary", Static).update(
                f"  Models: {num_models} │ Opponents: {self.num_opponents} │ Games per matchup: {self.num_games}"
            )
            self.query_one("#estimate-per-game", Static).update(
                f"  Est. per game:          {fmt_time(per_game_min):<12} ({self.max_turns} turns × ~2s avg latency)"
            )
            self.query_one("#estimate-total", Static).update(
                f"  Est. total benchmark:   {fmt_time(total_min):<12} ({num_models} × {self.num_opponents} opponents × {self.num_games} games)"
            )
            self.query_one("#estimate-total-games", Static).update(
                f"  Total games:            {total_games}"
            )
        except Exception:
            pass  # Widgets not yet mounted

    # ─── Watchers for reactive values ────────────────────────────────────────

    def watch_num_games(self, value: int) -> None:
        try:
            self.query_one("#lbl-num-games", Label).update(f"  {value:<4}")
        except Exception:
            pass
        self._refresh_estimates()

    def watch_speed_multiplier(self, value: int) -> None:
        self._refresh_speed_buttons()

    def watch_num_catastrophes(self, value: int) -> None:
        try:
            self.query_one("#lbl-num-cats", Label).update(f"  {value:<4}")
        except Exception:
            pass

    def watch_max_turns(self, value: int) -> None:
        try:
            self.query_one("#lbl-max-turns", Label).update(f"  {value:<4}")
        except Exception:
            pass
        self._refresh_estimates()

    def watch_num_opponents(self, value: int) -> None:
        self._refresh_opp_buttons()
        self._refresh_estimates()

    def watch_seed_fixed(self, value: bool) -> None:
        self._refresh_seed_buttons()

    # ─── Button group refresh helpers ────────────────────────────────────────

    def _refresh_speed_buttons(self) -> None:
        for spd in SPEED_OPTIONS:
            try:
                btn = self.query_one(f"#btn-speed-{spd}", Button)
                if spd == self.speed_multiplier:
                    btn.add_class("speed-active")
                else:
                    btn.remove_class("speed-active")
            except Exception:
                pass

    def _refresh_opp_buttons(self) -> None:
        mapping = {"quick": 3, "standard": 6, "deep": 8}
        for key, val in mapping.items():
            try:
                btn = self.query_one(f"#btn-opp-{key}", Button)
                if val == self.num_opponents:
                    btn.add_class("opp-active")
                else:
                    btn.remove_class("opp-active")
            except Exception:
                pass

    def _refresh_seed_buttons(self) -> None:
        try:
            btn_fixed = self.query_one("#btn-seed-fixed", Button)
            btn_random = self.query_one("#btn-seed-random", Button)
            if self.seed_fixed:
                btn_fixed.add_class("seed-active")
                btn_random.remove_class("seed-active")
            else:
                btn_random.add_class("seed-active")
                btn_fixed.remove_class("seed-active")
        except Exception:
            pass

    # ─── Button Handlers ─────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: C901
        btn_id = event.button.id or ""

        # ── Navigation ──
        if btn_id == "btn-back":
            self.app.pop_screen()
        elif btn_id == "btn-start":
            self._start_benchmark()

        # ── Model management ──
        elif btn_id == "btn-add-model":
            self._toggle_add_form(True)
        elif btn_id == "btn-cancel-add":
            self._toggle_add_form(False)
        elif btn_id == "btn-save-model":
            self._save_model()
        elif btn_id == "btn-test-single":
            self._test_single_model()
        elif btn_id == "btn-test-all":
            self._test_all_models()

        # ── Provider selection ──
        elif btn_id.startswith("btn-prov-"):
            provider = btn_id.replace("btn-prov-", "").title()
            if provider == "Openai":
                provider = "OpenAI"
            self._set_provider(provider)

        # ── Spinner: games ──
        elif btn_id == "btn-games-up":
            self.num_games = min(100, self.num_games + 5)
        elif btn_id == "btn-games-down":
            self.num_games = max(1, self.num_games - 5)

        # ── Speed buttons ──
        elif btn_id.startswith("btn-speed-"):
            spd = int(btn_id.replace("btn-speed-", ""))
            self.speed_multiplier = spd

        # ── Spinner: catastrophes ──
        elif btn_id == "btn-cats-up":
            self.num_catastrophes = min(20, self.num_catastrophes + 1)
        elif btn_id == "btn-cats-down":
            self.num_catastrophes = max(0, self.num_catastrophes - 1)

        # ── Spinner: turns ──
        elif btn_id == "btn-turns-up":
            self.max_turns = min(500, self.max_turns + 25)
        elif btn_id == "btn-turns-down":
            self.max_turns = max(25, self.max_turns - 25)

        # ── Opponent depth ──
        elif btn_id == "btn-opp-quick":
            self.num_opponents = 3
        elif btn_id == "btn-opp-standard":
            self.num_opponents = 6
        elif btn_id == "btn-opp-deep":
            self.num_opponents = 8

        # ── Seed mode ──
        elif btn_id == "btn-seed-fixed":
            self.seed_fixed = True
        elif btn_id == "btn-seed-random":
            self.seed_fixed = False

        # ── Presets ──
        elif btn_id.startswith("btn-preset-"):
            preset_key = btn_id.replace("btn-preset-", "").title()
            self._apply_preset(preset_key)

        # ── Model removal ──
        elif btn_id.startswith("btn-remove-model-"):
            idx = int(btn_id.replace("btn-remove-model-", ""))
            if 0 <= idx < len(self._models):
                self._models.pop(idx)
                self._refresh_models_list()

    # ─── Add Model Form ──────────────────────────────────────────────────────

    def _toggle_add_form(self, show: bool) -> None:
        form = self.query_one("#add-model-form", Vertical)
        if show:
            form.remove_class("hidden")
            form.add_class("visible")
        else:
            form.add_class("hidden")
            form.remove_class("visible")
            # Clear inputs
            for input_id in ["input-url", "input-apikey", "input-model-id", "input-display-name"]:
                self.query_one(f"#{input_id}", Input).value = ""

    def _set_provider(self, provider: str) -> None:
        """Update provider button states and set URL placeholder."""
        providers = {"OpenAI": "openai", "Anthropic": "anthropic", "Google": "google", "Ollama": "ollama"}
        for name, key in providers.items():
            btn = self.query_one(f"#btn-prov-{key}", Button)
            if name == provider:
                btn.add_class("provider-active")
            else:
                btn.remove_class("provider-active")

        url_input = self.query_one("#input-url", Input)
        placeholders = {
            "OpenAI": "https://api.openai.com/v1",
            "Anthropic": "https://api.anthropic.com",
            "Google": "https://generativelanguage.googleapis.com",
            "Ollama": "http://localhost:11434",
        }
        url_input.placeholder = placeholders.get(provider, "")

    def _save_model(self) -> None:
        """Save the model from the form."""
        url = self.query_one("#input-url", Input).value.strip()
        api_key = self.query_one("#input-apikey", Input).value.strip()
        model_id = self.query_one("#input-model-id", Input).value.strip()
        name = self.query_one("#input-display-name", Input).value.strip()

        # Determine active provider
        provider = "OpenAI"
        for prov_name, key in [("OpenAI", "openai"), ("Anthropic", "anthropic"), ("Google", "google"), ("Ollama", "ollama")]:
            try:
                btn = self.query_one(f"#btn-prov-{key}", Button)
                if btn.has_class("provider-active"):
                    provider = prov_name
                    break
            except Exception:
                pass

        if not url:
            url = {
                "OpenAI": "https://api.openai.com/v1",
                "Anthropic": "https://api.anthropic.com",
                "Google": "https://generativelanguage.googleapis.com",
                "Ollama": "http://localhost:11434",
            }.get(provider, "")

        if not model_id:
            self.notify("Model ID is required", severity="error")
            return
        if not name:
            name = model_id

        self._models.append({
            "provider": provider,
            "url": url,
            "api_key": api_key,
            "model_id": model_id,
            "name": name,
            "status": "untested",
        })
        self._toggle_add_form(False)
        self._refresh_models_list()
        self.notify(f"Added model: {name}", severity="information")

    # ─── Connection Testing ──────────────────────────────────────────────────

    async def _test_connection(self, model: dict) -> bool:
        """Test a single model's connection. Returns True if successful."""
        import httpx

        try:
            url = model["url"].rstrip("/")
            headers = {}
            if model["api_key"]:
                headers["Authorization"] = f"Bearer {model['api_key']}"

            # For OpenAI-compatible: POST /chat/completions with minimal payload
            if model["provider"] in ("OpenAI", "Ollama"):
                endpoint = f"{url}/chat/completions"
                payload = {
                    "model": model["model_id"],
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5,
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                return resp.status_code == 200

            elif model["provider"] == "Anthropic":
                endpoint = f"{url}/v1/messages"
                headers = {
                    "x-api-key": model["api_key"],
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                payload = {
                    "model": model["model_id"],
                    "messages": [{"role": "user", "content": "Say OK"}],
                    "max_tokens": 5,
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                return resp.status_code == 200

            elif model["provider"] == "Google":
                endpoint = f"{url}/v1beta/models/{model['model_id']}:generateContent"
                params = {"key": model["api_key"]}
                payload = {
                    "contents": [{"parts": [{"text": "Say OK"}]}],
                    "generationConfig": {"maxOutputTokens": 5},
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(endpoint, json=payload, params=params, headers=headers)
                return resp.status_code == 200

            return False
        except Exception:
            return False

    def _test_single_model(self) -> None:
        """Test the model currently being configured in the form."""
        url = self.query_one("#input-url", Input).value.strip()
        api_key = self.query_one("#input-apikey", Input).value.strip()
        model_id = self.query_one("#input-model-id", Input).value.strip()

        provider = "OpenAI"
        for prov_name, key in [("OpenAI", "openai"), ("Anthropic", "anthropic"), ("Google", "google"), ("Ollama", "ollama")]:
            try:
                btn = self.query_one(f"#btn-prov-{key}", Button)
                if btn.has_class("provider-active"):
                    provider = prov_name
                    break
            except Exception:
                pass

        if not url:
            url = {
                "OpenAI": "https://api.openai.com/v1",
                "Anthropic": "https://api.anthropic.com",
                "Google": "https://generativelanguage.googleapis.com",
                "Ollama": "http://localhost:11434",
            }.get(provider, "")

        if not model_id:
            self.notify("Enter a model ID first", severity="warning")
            return

        model = {"provider": provider, "url": url, "api_key": api_key, "model_id": model_id, "name": "test"}
        self.notify("Testing connection...", severity="information")
        self.run_worker(self._do_test_single(model), exclusive=True)

    async def _do_test_single(self, model: dict) -> None:
        success = await self._test_connection(model)
        if success:
            self.notify("✓ Connection successful!", severity="information")
        else:
            self.notify("✗ Connection failed — check URL, API key, and model ID", severity="error")

    def _test_all_models(self) -> None:
        """Test all configured models."""
        if not self._models:
            self.notify("No models to test", severity="warning")
            return
        self.notify("Testing all models...", severity="information")
        self.run_worker(self._do_test_all(), exclusive=True)

    async def _do_test_all(self) -> None:
        for model in self._models:
            success = await self._test_connection(model)
            model["status"] = "ready" if success else "failed"
        self._refresh_models_list()
        ready = sum(1 for m in self._models if m["status"] == "ready")
        self.notify(f"Testing complete: {ready}/{len(self._models)} models ready", severity="information")

    # ─── Preset Application ──────────────────────────────────────────────────

    def _apply_preset(self, preset_key: str) -> None:
        """Apply a weight preset to all dimension weights."""
        # Normalize key matching
        matched = None
        for key in PRESETS:
            if key.lower() == preset_key.lower():
                matched = key
                break
        if not matched:
            return

        weights = PRESETS[matched]
        self._weights = list(weights)
        self.active_preset = matched

        # Update UI
        for i, w in enumerate(weights):
            try:
                self.query_one(f"#input-weight-{i}", Input).value = str(w)
            except Exception:
                pass

        # Update preset button highlights
        for key in PRESETS:
            try:
                btn = self.query_one(f"#btn-preset-{key.lower()}", Button)
                if key == matched:
                    btn.add_class("preset-active")
                else:
                    btn.remove_class("preset-active")
            except Exception:
                pass

    # ─── Input Change Handlers ───────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle weight input changes — clear preset highlight."""
        if event.input.id and event.input.id.startswith("input-weight-"):
            # User manually edited a weight, clear preset selection
            for key in PRESETS:
                try:
                    self.query_one(f"#btn-preset-{key.lower()}", Button).remove_class("preset-active")
                except Exception:
                    pass

    # ─── Start Benchmark ─────────────────────────────────────────────────────

    def _start_benchmark(self) -> None:
        """Collect config and push the live monitoring screen."""
        # Gather enabled dimensions and weights
        enabled = []
        weights = []
        for i in range(8):
            try:
                sw = self.query_one(f"#sw-dim-{i}", Switch)
                w_input = self.query_one(f"#input-weight-{i}", Input)
                enabled.append(sw.value)
                try:
                    weights.append(float(w_input.value))
                except ValueError:
                    weights.append(1.0)
            except Exception:
                enabled.append(True)
                weights.append(1.0)

        config = {
            "models": [m for m in self._models if m["status"] == "ready"],
            "num_games": self.num_games,
            "speed_multiplier": self.speed_multiplier,
            "num_catastrophes": self.num_catastrophes,
            "max_turns": self.max_turns,
            "num_opponents": self.num_opponents,
            "seed_fixed": self.seed_fixed,
            "dimensions_enabled": enabled,
            "dimension_weights": weights,
        }

        if not config["models"]:
            self.notify("No models are ready. Test connections first.", severity="error")
            return

        from terminus.client.screens.benchmark_live import BenchmarkLiveScreen
        self.app.push_screen(BenchmarkLiveScreen(config))

    # ─── Actions ─────────────────────────────────────────────────────────────

    def action_go_back(self) -> None:
        self.app.pop_screen()
