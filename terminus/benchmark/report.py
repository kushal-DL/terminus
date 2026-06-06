"""HTML Report Generator — creates a self-contained HTML benchmark report."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any


# ─── Metric metadata ─────────────────────────────────────────────────────────
# Each entry: (short_label, feeds_dimension, tooltip_text)
# Tooltip format: plain text shown on hover — layman explanation +
# what HIGH / LOW scores mean for agentic workflows and LLM chat.

_TIER1_META: dict[str, tuple[str, str, str]] = {
    "1.1_build_order_efficiency": (
        "Build Order", "Coherence / Opportunity",
        "Did the model build prerequisites before advanced structures?\n"
        "HIGH (near 1.0): Model plans ahead — builds foundations first. "
        "In agentic workflows this means it sets up infrastructure before complex operations. "
        "In chat it means it lays out reasoning before conclusions.\n"
        "LOW (near 0.0): Model skips steps, tries advanced actions before basics are ready. "
        "Expect failed tool calls and wasted turns in production agents."
    ),
    "1.2_worker_allocation_anticipation": (
        "Worker Anticipation", "Triage",
        "Did the model reallocate resources BEFORE a bottleneck appeared, not after?\n"
        "HIGH: Model anticipates future needs — proactive resource management. "
        "Agents with high scores here self-manage capacity before queues fill.\n"
        "LOW: Model is purely reactive — only responds to problems already happening. "
        "Expect downstream failures in pipelines with latency."
    ),
    "1.3_market_timing": (
        "Market Timing", "Opportunity",
        "Did the model buy resources when prices were low and sell when high?\n"
        "HIGH: Model tracks trends and exploits price fluctuations — good temporal reasoning. "
        "Translates to: timing API calls, batching requests efficiently, exploiting cost windows.\n"
        "LOW: Model ignores market state, buys/sells randomly. "
        "Expect suboptimal resource use and missed optimisation windows in cost-sensitive agents."
    ),
    "1.4_catastrophe_preparation": (
        "Catastrophe Prep", "Triage",
        "Did the model build defenses BEFORE disaster warnings expired?\n"
        "HIGH: Model acts on early warnings — strong forward planning under uncertainty. "
        "In agents: handles edge cases and failure modes before they hit. "
        "In chat: anticipates follow-up questions and addresses them proactively.\n"
        "LOW: Model ignores warnings until it's too late. "
        "Expect fragile agents that break on first unexpected input."
    ),
    "1.5_housing_before_growth": (
        "Housing Timing", "Triage",
        "Did the model expand capacity before hitting limits?\n"
        "HIGH: Model plans for growth — doesn't wait until it's blocked to scale. "
        "Translates to: agents that provision resources before they're needed.\n"
        "LOW: Model hits hard limits repeatedly. "
        "Expect frequent blockers and retries in production workflows."
    ),
    "1.6_resource_stockpile_timing": (
        "Stockpile Timing", "Opportunity",
        "Did the model use PASS (do nothing) when it could have taken a productive action?\n"
        "HIGH: Model rarely wastes turns — consistently takes value-adding actions. "
        "Agents score high here when they always make progress rather than idling.\n"
        "LOW: Model frequently passes when better options exist — passive, low-engagement play. "
        "Expect agents that stall pipelines or give unhelpful 'I cannot help' responses."
    ),
    "2.1_invalid_action_rate": (
        "Valid Action Rate", "Arithmetic",
        "What fraction of the model's actions were accepted by the game engine?\n"
        "HIGH (near 1.0): Model's outputs are almost always correctly formatted and feasible. "
        "In agentic workflows: tool calls succeed, API params are correct, no retries needed.\n"
        "LOW: Model frequently produces malformed outputs or attempts impossible actions. "
        "Expect high retry rates, error handling overhead, and wasted API spend."
    ),
    "2.2_worker_sum_accuracy": (
        "Worker Sum Accuracy", "Arithmetic",
        "When allocating workers, did the numbers always sum to exactly the total population?\n"
        "HIGH: Model respects hard constraints — counts add up correctly. "
        "In agents: JSON payloads are internally consistent, budgets balance, totals are correct.\n"
        "LOW: Model makes off-by-one or proportion errors under constraint. "
        "Expect silent data corruption in financial, scheduling, or allocation agents."
    ),
    "2.3_over_capacity_errors": (
        "Capacity Errors", "Arithmetic",
        "Did the model attempt to store more than available capacity?\n"
        "HIGH: Model tracks limits and stays within bounds. "
        "Agents with high scores here respect rate limits, context windows, payload sizes.\n"
        "LOW: Model ignores capacity constraints — tries to overfill buffers. "
        "Expect overflow errors, truncated data, and silent failures in production."
    ),
    "2.4_production_rate_awareness": (
        "Production Awareness", "Arithmetic",
        "Did the model understand how fast resources accumulate and plan accordingly?\n"
        "HIGH: Model reasons about rates, not just snapshots — knows when it can afford something.\n"
        "LOW: Model treats the current state as static — attempts actions before sufficient "
        "resources accumulate. Translates to timing errors in rate-limited or async pipelines."
    ),
    "2.5_trade_math_accuracy": (
        "Trade Math", "Arithmetic",
        "Did the model correctly calculate expected gains/costs from market trades?\n"
        "HIGH: Model computes expected value accurately — good at cost-benefit reasoning. "
        "Agents score high here when they correctly estimate API costs, token budgets, trade-offs.\n"
        "LOW: Model miscalculates value, makes losing trades. "
        "Expect poor cost management and suboptimal decisions in resource-constrained agents."
    ),
    "2.6_multi_resource_feasibility": (
        "Multi-Resource", "Arithmetic",
        "Did the model correctly check ALL requirements simultaneously before acting?\n"
        "HIGH: Model handles multi-constraint satisfaction — checks food AND materials AND gold together.\n"
        "LOW: Model checks one constraint at a time, misses combined requirements. "
        "Translates to: agents that partially complete multi-step operations then fail mid-way."
    ),
    "3.1_post_catastrophe_recovery": (
        "Catastrophe Recovery", "Triage / Error Recog",
        "How quickly did production return to normal after a disaster?\n"
        "HIGH: Model recovers fast — resilient to disruption, good error recovery. "
        "In agents: bounces back from API failures, tool errors, or bad data quickly.\n"
        "LOW: Model stays damaged long after an event — poor recovery instincts. "
        "Expect long degraded states after any unexpected failure in production."
    ),
    "3.2_worker_reallocation_after_damage": (
        "Damage Response", "Pivot",
        "Did the model shift resources within 3 turns of a crisis?\n"
        "HIGH: Model responds quickly to change — adaptive and responsive. "
        "In chat: pivots gracefully when initial approach fails.\n"
        "LOW: Model sticks to the old plan even when circumstances changed. "
        "Expect rigid agents that don't adapt to feedback or errors."
    ),
    "3.3_repair_prioritization": (
        "Repair Priority", "Triage / Opportunity",
        "When multiple things were broken, did the model fix the most important one first?\n"
        "HIGH: Model correctly prioritises — fixes critical systems before cosmetic ones. "
        "In incident response agents: addresses P0 before P2.\n"
        "LOW: Model repairs randomly or in wrong order. "
        "Expect agents that patch minor issues while critical failures persist."
    ),
    "3.4_market_adaptation": (
        "Market Adaptation", "Pivot",
        "Did the model exploit price shocks (>30% change) when they occurred?\n"
        "HIGH: Model detects environmental changes and adapts strategy. "
        "Agents score high here when they notice and exploit changing conditions.\n"
        "LOW: Model ignores market signals — misses opportunities. "
        "Translates to rigid agents that don't adjust to new information in context."
    ),
    "3.5_starvation_response_speed": (
        "Starvation Response", "Triage / Error Recog",
        "How many turns did the model take to recover from food running out?\n"
        "HIGH (fast recovery): Model detects critical failures immediately and acts. "
        "In agents: catches and resolves blocking errors with minimal delay.\n"
        "LOW (slow recovery): Model lets critical problems persist. "
        "Expect cascading failures in agents where one blocked step halts the whole pipeline."
    ),
    "3.6_defense_investment_after_hit": (
        "Defense Learning", "Error Recognition",
        "After being hit by the first catastrophe, did the model build defenses within 30 turns?\n"
        "HIGH: Model learns from failure — invests in prevention after an incident. "
        "In agents: adds error handling, validation, or fallbacks after encountering a failure mode.\n"
        "LOW: Model repeats the same vulnerability. "
        "Expect agents that make the same mistakes repeatedly without self-correction."
    ),
    "3.7_action_distribution_shift": (
        "Strategy Shift", "Pivot",
        "Did the model's action mix change significantly after a disruption (catastrophe, crisis)?\n"
        "HIGH: Model shifted strategy in response to new circumstances — adaptive reasoning.\n"
        "LOW: Model used the same strategy regardless of what happened — rigid.\n"
        "Note: extreme shift (always changing) also scores low — justified pivots only. "
        "Best for agents that update their approach when the environment changes but stay consistent otherwise."
    ),
    "4.1_building_recall": (
        "Building Recall", "Coherence",
        "When asked, could the model accurately list what it had built from memory?\n"
        "HIGH: Model has accurate working memory of its own state. "
        "In agents: correctly remembers what tools it called, what state it modified.\n"
        "LOW: Model confabulates — invents buildings it doesn't have. "
        "Expect hallucinated tool results and false state assumptions in long agent runs.\n"
        "⚠️ Requires state probes enabled (enable_state_probes: true in config)."
    ),
    "4.2_resource_awareness": (
        "Resource Awareness", "Coherence",
        "Did the model's estimate of its own resources match reality?\n"
        "HIGH: Model has accurate self-knowledge — knows what it has. "
        "In LLM chat: accurate about its own capabilities and context window state.\n"
        "LOW: Model doesn't know its own state — attempts actions it can't complete. "
        "Expect overconfident agents that claim to have done things they haven't.\n"
        "⚠️ Requires state probes enabled."
    ),
    "4.3_strategy_consistency": (
        "Strategy Consistency", "Coherence",
        "Did the model's stated strategy match what it was actually doing?\n"
        "HIGH: Model's stated reasoning aligns with its actions — trustworthy chain-of-thought.\n"
        "LOW: Model says one thing, does another. "
        "Expect unreliable reasoning traces — the model's explanations can't be trusted for debugging.\n"
        "⚠️ Requires state probes enabled."
    ),
    "4.4_history_recall": (
        "History Recall", "Coherence",
        "Could the model recall key events (catastrophes, trades) that happened earlier?\n"
        "HIGH: Model maintains accurate event history — good episodic memory. "
        "In long agent runs: correctly references earlier steps, doesn't repeat completed work.\n"
        "LOW: Model forgets or misremembers events. "
        "Expect agents that redo completed steps or contradict earlier decisions.\n"
        "⚠️ Requires state probes enabled."
    ),
    "5.1_win_rate_vs_archetypes": (
        "Win Rate", "Game Theory",
        "How often did the model outscore opponents weighted by opponent difficulty?\n"
        "HIGH: Model can beat scripted opponents — including hard ones (adversarial, turtle). "
        "In multi-agent systems: holds its own against other agents.\n"
        "LOW: Model loses even to random opponents. "
        "Expect poor performance in any competitive or adversarial multi-agent deployment."
    ),
    "5.2_exploitation_resistance": (
        "Exploit Resistance", "Game Theory",
        "Did the model perform as well against an adversarial opponent as against a balanced one?\n"
        "HIGH (ratio near 1.0): Model is robust — adversarial tactics don't significantly hurt it.\n"
        "LOW: Model is vulnerable to manipulation — performs much worse when actively targeted. "
        "Do not deploy in adversarial environments (competitive auctions, negotiation agents) without mitigation."
    ),
    "5.3_counter_strategy_speed": (
        "Counter-Strategy", "Game Theory",
        "How quickly did the model start outpacing opponents after the game started?\n"
        "HIGH: Model adapts to the opponent's style quickly — good opponent modeling.\n"
        "LOW: Model takes many turns to find an effective counter. "
        "Expect slow convergence in multi-agent negotiations or iterative strategy games."
    ),
    "5.4_cooperative_surplus": (
        "Cooperation", "Game Theory",
        "Did the model accept mutually beneficial trades with opponents?\n"
        "HIGH: Model identifies and captures win-win opportunities — cooperative rationality.\n"
        "LOW: Model refuses beneficial cooperation — either too suspicious or doesn't analyse trade value. "
        "Translates to: poor performance in collaborative multi-agent tasks requiring negotiation."
    ),
    "5.5_market_manipulation_detection": (
        "Manip. Detection", "Game Theory",
        "Did the model avoid buying during opponent pump-and-dump patterns?\n"
        "HIGH: Model detects and avoids adversarial market manipulation.\n"
        "LOW: Model is fooled by price manipulation — buys at inflated prices. "
        "In agents: vulnerable to prompt injection or adversarial inputs that exploit predictable behaviour."
    ),
    "6.1_per_quartile_quality": (
        "Quartile Quality", "Degradation",
        "Was the model's decision quality in the final 25% of turns as good as the first 25%?\n"
        "HIGH (ratio near 1.0): Model doesn't degrade over time — consistent long-horizon performance.\n"
        "LOW: Late-game decisions are worse than early ones — context accumulation hurts the model. "
        "Directly predicts: how far into a long agentic task the model stays reliable."
    ),
    "6.2_historical_reference_rate": (
        "History Reference", "Degradation",
        "Did late-game actions build on decisions made early in the game?\n"
        "HIGH: Model uses its full history — upgrades buildings it built earlier, continues strategies.\n"
        "LOW: Model forgets early decisions — each turn treated in isolation. "
        "Expect agents that re-derive information they already established, wasting context and tokens."
    ),
    "6.3_context_collapse_point": (
        "Collapse Point", "Degradation",
        "At what turn did valid action rate drop more than 20% below the rolling average?\n"
        "HIGH (late collapse or none): Model stays coherent for many turns — large effective context window.\n"
        "LOW (early collapse): Model starts producing invalid outputs early. "
        "This directly maps to an agent's reliable step budget — the number of steps before quality degrades. "
        "Multiply by average turn time to get real-world operational horizon."
    ),
}

# ─── Dimension tooltips ───────────────────────────────────────────────────────
# (short_label, full_name, tooltip_text)

_DIM_TOOLTIPS: dict[str, tuple[str, str, str]] = {
    "dim_1_coherence": (
        "Coherence", "Multi-Decision Coherence",
        "Does the model stay consistent across 100+ sequential decisions?\n"
        "Measures: strategy coherence, accurate self-knowledge, memory fidelity.\n"
        "HIGH → long agent step budgets, trustworthy chain-of-thought, accurate self-reporting.\n"
        "LOW → self-contradiction after a few steps, hallucinated state, incoherent long tasks."
    ),
    "dim_2_arithmetic": (
        "Arithmetic", "Applied Arithmetic Under Load",
        "Can the model do correct math while simultaneously reasoning about strategy?\n"
        "Measures: valid actions, constraint satisfaction, multi-variable calculations under cognitive load.\n"
        "HIGH → reliable tool-call parameters, correct JSON payloads, budgets that balance.\n"
        "LOW → malformed API calls, off-by-one errors, silent data corruption in numeric workflows."
    ),
    "dim_3_triage": (
        "Triage", "Priority Triage Under Competing Constraints",
        "When multiple urgent problems exist simultaneously, does the model fix the right one first?\n"
        "Measures: correct priority ordering, speed of critical response, proactive preparation.\n"
        "HIGH → P0 handled before P2, incident response that addresses root cause first.\n"
        "LOW → cosmetic fixes while critical systems burn, poor on-call automation."
    ),
    "dim_4_error_recognition": (
        "Err. Recog.", "Compounding Error Recognition",
        "Does the model detect a small mistake snowballing into a crisis BEFORE it becomes critical?\n"
        "Measures: detection lead time, recovery speed, avoidance of cascading failures.\n"
        "HIGH → self-healing agents that catch drift early, short recovery times.\n"
        "LOW → problems compound undetected until catastrophic failure."
    ),
    "dim_5_pivot": (
        "Pivot", "Justified Pivot vs Inconsistency",
        "Can the model tell the difference between a justified strategy change and random incoherence?\n"
        "Measures: signal-to-noise ratio of strategy changes vs environmental triggers.\n"
        "HIGH → stable implementations that update for good reasons only.\n"
        "LOW → either rigid (never adapts) or chaotic (changes strategy randomly)."
    ),
    "dim_6_degradation": (
        "Degradation", "Graceful Degradation",
        "How does performance curve over many turns — stable, gradual decline, or cliff failure?\n"
        "Measures: quality in early vs late turns, context collapse point, history utilisation.\n"
        "HIGH → predictable SLA, model stays reliable deep into long tasks.\n"
        "LOW → cliff failure at a specific context length, or rapid degradation over time."
    ),
    "dim_7_opportunity": (
        "Opportunity", "Opportunity Cost Awareness",
        "Does the model choose the BEST available action, or just any valid one?\n"
        "Measures: action diversity, avoidance of passive play, strategic optimality.\n"
        "HIGH → solution quality ceiling is high, model exploits available options fully.\n"
        "LOW → model defaults to safe/passive actions (PASS), misses value-adding opportunities.\n"
        "Note: includes participation penalty — models that only PASS score near 0 here."
    ),
    "dim_8_game_theory": (
        "Game Theory", "Game-Theoretic Sophistication",
        "Does the model reason about other agents, or play as if it's alone?\n"
        "Measures: win rate vs opponents, exploitation resistance, cooperative trade capture.\n"
        "HIGH → strong in multi-agent systems, auctions, negotiations, adversarial environments.\n"
        "LOW → easily manipulated, misses cooperative opportunities, poor against adaptive opponents."
    ),
}

_TIER1_GROUPS = {
    "Planning": ["1.1","1.2","1.3","1.4","1.5","1.6"],
    "Arithmetic": ["2.1","2.2","2.3","2.4","2.5","2.6"],
    "Flexibility": ["3.1","3.2","3.3","3.4","3.5","3.6","3.7"],
    "State Probes": ["4.1","4.2","4.3","4.4"],
    "Opponent-Aware": ["5.1","5.2","5.3","5.4","5.5"],
    "Context Pressure": ["6.1","6.2","6.3"],
}

_DIM_DISPLAY = {
    "dim_1_coherence":        "Coherence",
    "dim_2_arithmetic":       "Arithmetic",
    "dim_3_triage":           "Triage",
    "dim_4_error_recognition":"Err. Recog.",
    "dim_5_pivot":            "Pivot",
    "dim_6_degradation":      "Degradation",
    "dim_7_opportunity":      "Opportunity",
    "dim_8_game_theory":      "Game Theory",
}

_DIM_FULL = {
    "dim_1_coherence":        "Multi-Decision Coherence",
    "dim_2_arithmetic":       "Applied Arithmetic Under Load",
    "dim_3_triage":           "Priority Triage",
    "dim_4_error_recognition":"Compounding Error Recognition",
    "dim_5_pivot":            "Justified Pivot",
    "dim_6_degradation":      "Graceful Degradation",
    "dim_7_opportunity":      "Opportunity Cost Awareness",
    "dim_8_game_theory":      "Game-Theoretic Sophistication",
}


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_report(results: dict[str, Any], config: dict[str, Any], output_path: str) -> str:
    """Generate an HTML benchmark report and write it to output_path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rankings   = results.get("rankings", [])
    model_stats = results.get("model_stats", {})
    total_games = results.get("total_games", 0)
    elapsed    = results.get("elapsed_seconds", 0)
    dimensions = results.get("dimensions", {})
    # Per-model metrics from the full BenchmarkResult (if available)
    models_detail = results.get("models_detail", {})

    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elapsed_str = f"{elapsed / 60:.1f} min" if elapsed < 3600 else f"{elapsed / 3600:.1f} hr"

    rankings_rows    = _build_rankings_rows(rankings)
    dimension_table  = _build_dimension_table(dimensions, rankings)
    tier1_section    = _build_tier1_section(models_detail, rankings)
    config_html      = _build_config_summary(config)
    per_model_html   = _build_per_model_details(model_stats, dimensions, rankings)

    content = _TEMPLATE.format(
        timestamp       = timestamp,
        total_games     = total_games,
        num_models      = len(rankings),
        elapsed         = elapsed_str,
        speed           = config.get("speed_multiplier", 1),
        max_turns       = config.get("max_turns", 100),
        num_catastrophes= config.get("num_catastrophes", 5),
        rankings_rows   = rankings_rows,
        dimension_table = dimension_table,
        tier1_section   = tier1_section,
        per_model_html  = per_model_html,
        config_html     = config_html,
    )

    path.write_text(content, encoding="utf-8")
    return str(path.resolve())


# ─── Section builders ─────────────────────────────────────────────────────────

def _build_rankings_rows(rankings: list[dict[str, Any]]) -> str:
    rows = []
    for r in rankings:
        name       = html.escape(str(r.get("name", "?")))
        composite  = r.get("composite_score")
        score      = r.get("score", r.get("avg_score", 0))
        valid_rate = r.get("valid_rate", 0)
        games      = r.get("games_played", 0)
        consistency= r.get("consistency", 0)
        trend      = html.escape(str(r.get("trend", "—")).title())
        archetype  = html.escape(str(r.get("archetype", "—")).title())
        rank       = r.get("rank", "?")
        rank_cls   = {1: "gold", 2: "silver", 3: "bronze"}.get(rank, "")
        comp_str   = f"{composite:.3f}" if composite is not None else "—"

        rows.append(
            f'<tr class="{rank_cls}">'
            f"<td>{rank}</td>"
            f"<td><strong>{name}</strong></td>"
            f"<td class='num'>{comp_str}</td>"
            f"<td class='num'>{score:.0f}</td>"
            f"<td class='num'>{valid_rate * 100:.0f}%</td>"
            f"<td class='num'>{games}</td>"
            f"<td>{archetype}</td>"
            f"<td>{trend}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _score_pill(score: float) -> str:
    """Render a score as a compact pill with colour coding."""
    score = max(0.0, min(1.0, score))
    pct   = int(score * 100)
    if score >= 0.75:
        cls = "pill-high"
    elif score >= 0.50:
        cls = "pill-mid"
    elif score >= 0.25:
        cls = "pill-low"
    else:
        cls = "pill-zero"
    return f'<span class="pill {cls}">{score:.2f}</span>'


def _build_dimension_table(dimensions: dict[str, Any], rankings: list[dict[str, Any]]) -> str:
    dim_ids = list(_DIM_DISPLAY.keys())
    model_names = [r.get("name", "?") for r in rankings]

    if not model_names:
        return "<p class='muted'>No models to display.</p>"

    # Header row
    th_models = "".join(f"<th>{html.escape(n)}</th>" for n in model_names)
    header = f"<tr><th>Dimension</th>{th_models}</tr>"

    rows = []
    for dim_id in dim_ids:
        short = _DIM_DISPLAY[dim_id]
        full  = _DIM_FULL[dim_id]
        tooltip_info = _DIM_TOOLTIPS.get(dim_id)
        if tooltip_info:
            tt_text = html.escape(tooltip_info[2].replace("\n", "&#10;"))
            label_html = (
                f'<span class="has-tooltip" data-tooltip="{tt_text}">'
                f'{short} <span class="tooltip-icon">?</span>'
                f'</span>'
            )
        else:
            label_html = short

        cells = ""
        for model_name in model_names:
            dim_scores = dimensions.get(model_name, {})
            val = dim_scores.get(full, None)
            if val is None:
                val = dim_scores.get(short, None)
            cells += f"<td>{_score_pill(val) if val is not None else '<span class=muted>—</span>'}</td>"
        rows.append(f"<tr><td class='dim-label'>{label_html}</td>{cells}</tr>")

    # Composite row
    comp_tooltip = html.escape(
        "Weighted average of all 8 dimensions + participation score (1.5× weight).&#10;"
        "Participation = model avg score ÷ best score in run.&#10;"
        "HIGH → model engages with the task AND reasons well about it.&#10;"
        "LOW → either passive play or poor cognitive performance."
    )
    comp_label = (
        f'<span class="has-tooltip" data-tooltip="{comp_tooltip}">'
        f'<strong>Composite</strong> <span class="tooltip-icon">?</span>'
        f'</span>'
    )
    comp_cells = ""
    for r in rankings:
        comp = r.get("composite_score")
        comp_cells += f"<td>{_score_pill(comp) if comp is not None else '<span class=muted>—</span>'}</td>"
    rows.append(f"<tr class='composite-row'><td class='dim-label'>{comp_label}</td>{comp_cells}</tr>")

    return (
        f"<div class='table-wrap'>"
        f"<table class='dim-table'>"
        f"<thead>{header}</thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        f"</table></div>"
    )


def _build_tier1_section(models_detail: dict[str, Any], rankings: list[dict[str, Any]]) -> str:
    """Build the Tier-1 metric drill-down, one accordion panel per model."""
    if not models_detail and not rankings:
        return ""

    # Try to get model names from rankings order
    model_names = [r.get("name", "?") for r in rankings]

    panels = []
    for model_name in model_names:
        detail   = models_detail.get(model_name, {})
        metrics  = detail.get("metrics", {})
        if not metrics:
            continue

        escaped = html.escape(str(model_name))
        group_html = ""

        for group_name, prefixes in _TIER1_GROUPS.items():
            # Find all metrics in this group
            group_metrics = {
                k: v for k, v in metrics.items()
                if any(k.startswith(p + "_") or k.startswith(p) for p in prefixes)
            }
            if not group_metrics:
                continue

            rows_html = ""
            for metric_id, result in sorted(group_metrics.items()):
                val     = result.get("value", 0) if isinstance(result, dict) else float(result)
                samples = result.get("sample_count", 0) if isinstance(result, dict) else 0
                meta    = _TIER1_META.get(metric_id, (metric_id, "", ""))
                label   = meta[0]
                feeds   = meta[1]
                tooltip = meta[2] if len(meta) > 2 else ""
                sample_str = f"<span class='sample-count'>n={samples}</span>" if samples else ""

                if tooltip:
                    tt_text = html.escape(tooltip.replace("\n", "&#10;"))
                    label_html = (
                        f'<span class="has-tooltip" data-tooltip="{tt_text}">'
                        f'{html.escape(label)} <span class="tooltip-icon">?</span>'
                        f'</span>'
                    )
                else:
                    label_html = html.escape(label)

                rows_html += (
                    f"<tr>"
                    f"<td class='metric-label'>{label_html}</td>"
                    f"<td>{_score_pill(val)}</td>"
                    f"<td class='metric-feeds muted'>{html.escape(feeds)}</td>"
                    f"<td>{sample_str}</td>"
                    f"</tr>"
                )

            group_html += (
                f"<div class='metric-group'>"
                f"<div class='metric-group-title'>{html.escape(group_name)}</div>"
                f"<table class='metric-table'>"
                f"<thead><tr>"
                f"<th>Metric</th><th>Score</th><th>Feeds dimension</th><th>Samples</th>"
                f"</tr></thead>"
                f"<tbody>{rows_html}</tbody>"
                f"</table></div>"
            )

        if not group_html:
            continue

        panels.append(
            f"<details class='accordion'>"
            f"<summary><strong>{escaped}</strong> — Tier-1 metric breakdown</summary>"
            f"<div class='accordion-body'>{group_html}</div>"
            f"</details>"
        )

    if not panels:
        return "<p class='muted'>Tier-1 metric detail not available. Check the JSON export for full data.</p>"

    return "\n".join(panels)


def _build_per_model_details(
    model_stats: dict[str, Any],
    dimensions: dict[str, Any],
    rankings: list[dict[str, Any]],
) -> str:
    if not model_stats:
        return "<p class='muted'>No model statistics available.</p>"

    sections = []
    for r in rankings:
        name  = r.get("name", "?")
        stats = model_stats.get(name, {})
        if not stats:
            continue

        escaped = html.escape(str(name))
        scores  = stats.get("scores", [])
        avg     = stats.get("avg_score", 0)
        valid   = stats.get("total_valid", 0)
        invalid = stats.get("total_invalid", 0)
        total   = valid + invalid
        valid_pct = f"{valid / total * 100:.0f}%" if total else "—"
        comp    = r.get("composite_score")
        arch    = str(r.get("archetype", "—")).title()
        trend   = str(r.get("trend", "—")).title()

        # Score sparkline
        sparkline = ""
        if len(scores) > 1:
            mn, mx = min(scores), max(scores)
            rng = mx - mn or 1
            pts = " ".join(f"{i*6},{44 - (s-mn)/rng*40:.1f}" for i, s in enumerate(scores))
            w   = len(scores) * 6
            sparkline = (
                f'<svg class="sparkline" width="{w}" height="48" viewBox="0 0 {w} 48">'
                f'<polyline points="{pts}" fill="none" stroke="#2563eb" stroke-width="2" stroke-linejoin="round"/>'
                f"</svg>"
            )

        comp_badge = f'<span class="badge badge-blue">Composite {comp:.3f}</span>' if comp is not None else ""
        arch_badge = f'<span class="badge badge-gray">{arch}</span>'
        trend_badge = f'<span class="badge badge-gray">{trend}</span>'

        sections.append(
            f'<div class="card">'
            f'<div class="card-header">'
            f'<span class="card-title">{escaped}</span>'
            f'<span class="badge-group">{comp_badge}{arch_badge}{trend_badge}</span>'
            f'</div>'
            f'<div class="card-stats">'
            f'<div class="stat-item"><span class="stat-val">{avg:.0f}</span><span class="stat-lbl">Avg Score</span></div>'
            f'<div class="stat-item"><span class="stat-val">{valid_pct}</span><span class="stat-lbl">Valid Rate</span></div>'
            f'<div class="stat-item"><span class="stat-val">{stats.get("games_played", 0)}</span><span class="stat-lbl">Games</span></div>'
            f'<div class="stat-item"><span class="stat-val">{stats.get("min_score", 0):.0f} – {stats.get("max_score", 0):.0f}</span><span class="stat-lbl">Score Range</span></div>'
            f'</div>'
            f'{sparkline}'
            f'</div>'
        )

    return "\n".join(sections)


def _build_config_summary(config: dict[str, Any]) -> str:
    models      = config.get("models", [])
    model_names = ", ".join(html.escape(m.get("name", "?")) for m in models) or "—"
    opponents   = config.get("opponents", config.get("num_opponents", "—"))
    if isinstance(opponents, list):
        opponents = ", ".join(str(o) for o in opponents)

    rows = [
        ("Models",             model_names),
        ("Games per matchup",  config.get("games_per_matchup", config.get("num_games", "—"))),
        ("Max turns",          config.get("max_turns", "—")),
        ("Speed multiplier",   f"{config.get('speed_multiplier', 1)}×"),
        ("Opponents",          opponents),
        ("Seed mode",          "Fixed" if config.get("seed_fixed", config.get("seed_mode") == "fixed") else "Random"),
        ("Weight preset",      str(config.get("weight_preset", "balanced")).title()),
    ]
    items = "".join(f"<tr><td class='cfg-key'>{k}</td><td>{html.escape(str(v))}</td></tr>" for k, v in rows)
    return f"<table class='cfg-table'><tbody>{items}</tbody></table>"


# ─── HTML Template ────────────────────────────────────────────────────────────

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Terminus LLM Benchmark — {timestamp}</title>
<style>
/* ── Reset & base ─────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  background: #f8fafc;
  color: #1e293b;
}}
a {{ color: #2563eb; text-decoration: none; }}

/* ── Layout ───────────────────────────────────── */
.page-wrap {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}}

/* ── Header ───────────────────────────────────── */
.report-header {{
  text-align: center;
  padding: 2.5rem 0 2rem;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 2rem;
}}
.report-header h1 {{
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #0f172a;
}}
.report-header .subtitle {{
  margin-top: 0.3rem;
  color: #64748b;
  font-size: 0.875rem;
}}

/* ── Stats bar ────────────────────────────────── */
.stats-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 2.5rem;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}}
.stat-item-top {{
  flex: 1;
  min-width: 120px;
  padding: 1.1rem 1rem;
  text-align: center;
  border-right: 1px solid #e2e8f0;
}}
.stat-item-top:last-child {{ border-right: none; }}
.stat-val-top {{
  display: block;
  font-size: 1.6rem;
  font-weight: 700;
  color: #2563eb;
  line-height: 1.2;
}}
.stat-lbl-top {{
  display: block;
  font-size: 0.75rem;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-top: 0.15rem;
}}

/* ── Section headings ─────────────────────────── */
.section-heading {{
  font-size: 1rem;
  font-weight: 700;
  color: #0f172a;
  margin: 2.5rem 0 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #e2e8f0;
  letter-spacing: 0.02em;
}}

/* ── Tables ───────────────────────────────────── */
.table-wrap {{
  width: 100%;
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  font-size: 13.5px;
}}
thead tr {{ background: #f1f5f9; }}
th {{
  padding: 0.75rem 1rem;
  text-align: left;
  font-weight: 600;
  color: #475569;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  border-bottom: 1px solid #e2e8f0;
}}
td {{
  padding: 0.65rem 1rem;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: middle;
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover {{ background: #f8fafc; }}
.num {{ text-align: right; }}

/* rank colouring */
tr.gold td:first-child   {{ color: #b45309; font-weight: 700; }}
tr.silver td:first-child {{ color: #64748b; font-weight: 700; }}
tr.bronze td:first-child {{ color: #b05e28; font-weight: 700; }}

/* dimension table */
.dim-table th:first-child,
.dim-table td:first-child {{ width: 150px; }}
.dim-table td {{ text-align: center; }}
.dim-label {{ text-align: left !important; color: #475569; font-size: 0.8rem; }}
.composite-row td {{ background: #f8fafc; }}
.composite-row td.dim-label {{ color: #0f172a; }}

/* config table */
.cfg-table {{ border: none; box-shadow: none; font-size: 13.5px; }}
.cfg-table td {{ border-bottom: 1px solid #f1f5f9; padding: 0.5rem 0.75rem; }}
.cfg-key {{ color: #64748b; font-weight: 500; width: 180px; }}

/* metric table */
.metric-table {{ font-size: 12.5px; border: none; box-shadow: none; }}
.metric-table th {{ background: #fff; font-size: 0.7rem; }}
.metric-table td {{ padding: 0.4rem 0.75rem; }}
.metric-label {{ color: #334155; }}
.metric-feeds {{ font-size: 0.7rem; }}
.sample-count {{ color: #94a3b8; font-size: 0.75rem; }}

/* ── Pill scores ──────────────────────────────── */
.pill {{
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  min-width: 44px;
  text-align: center;
}}
.pill-high  {{ background: #dcfce7; color: #15803d; }}
.pill-mid   {{ background: #fef9c3; color: #a16207; }}
.pill-low   {{ background: #ffedd5; color: #c2410c; }}
.pill-zero  {{ background: #fee2e2; color: #b91c1c; }}

/* ── Badges ───────────────────────────────────── */
.badge {{
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  margin-left: 0.4rem;
}}
.badge-blue {{ background: #dbeafe; color: #1d4ed8; }}
.badge-gray {{ background: #f1f5f9; color: #475569; }}
.badge-group {{ display: inline-flex; align-items: center; flex-wrap: wrap; gap: 0.2rem; }}

/* ── Model cards ──────────────────────────────── */
.card {{
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}}
.card-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
}}
.card-title {{ font-size: 1rem; font-weight: 700; color: #0f172a; }}
.card-stats {{
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}}
.stat-item {{ display: flex; flex-direction: column; }}
.stat-val {{ font-size: 1.1rem; font-weight: 700; color: #0f172a; }}
.stat-lbl {{ font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.04em; }}
.sparkline {{ display: block; margin-top: 1rem; }}

/* ── Accordion (Tier-1) ───────────────────────── */
.accordion {{
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 0.75rem;
  overflow: hidden;
  background: #fff;
}}
.accordion summary {{
  padding: 0.9rem 1.25rem;
  cursor: pointer;
  list-style: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #0f172a;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.9rem;
}}
.accordion summary::-webkit-details-marker {{ display: none; }}
.accordion summary::after {{
  content: "▾";
  color: #94a3b8;
  font-size: 1rem;
  transition: transform 0.2s;
}}
.accordion[open] summary::after {{ transform: rotate(-180deg); }}
.accordion-body {{ padding: 1rem 1.25rem; }}
.metric-group {{ margin-bottom: 1.25rem; }}
.metric-group:last-child {{ margin-bottom: 0; }}
.metric-group-title {{
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 0.5rem;
}}

/* ── Misc ─────────────────────────────────────── */
.muted {{ color: #94a3b8; font-size: 0.85rem; }}
.footer {{
  text-align: center;
  margin-top: 3rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e2e8f0;
  color: #94a3b8;
  font-size: 0.8rem;
}}

/* ── Tooltips ─────────────────────────────────── */
.has-tooltip {{
  position: relative;
  cursor: help;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}}
.tooltip-icon {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #cbd5e1;
  color: #475569;
  font-size: 0.6rem;
  font-weight: 700;
  font-style: normal;
  flex-shrink: 0;
  vertical-align: middle;
}}
.has-tooltip:hover .tooltip-icon {{
  background: #2563eb;
  color: #fff;
}}
.has-tooltip::after {{
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  min-width: 280px;
  max-width: 380px;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 0.75rem;
  font-weight: 400;
  line-height: 1.5;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  white-space: pre-line;
  box-shadow: 0 4px 16px rgba(0,0,0,0.25);
  z-index: 100;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.15s, visibility 0.15s;
}}
.has-tooltip::before {{
  content: '';
  position: absolute;
  bottom: calc(100% + 2px);
  left: 12px;
  border: 6px solid transparent;
  border-top-color: #1e293b;
  z-index: 101;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.15s, visibility 0.15s;
}}
.has-tooltip:hover::after,
.has-tooltip:hover::before {{
  opacity: 1;
  visibility: visible;
}}
/* Flip tooltip when near bottom of viewport */
.dim-table tbody tr:last-child .has-tooltip::after,
.dim-table tbody tr:nth-last-child(-n+3) .has-tooltip::after {{
  bottom: auto;
  top: calc(100% + 8px);
}}
.dim-table tbody tr:last-child .has-tooltip::before,
.dim-table tbody tr:nth-last-child(-n+3) .has-tooltip::before {{
  bottom: auto;
  top: calc(100% + 2px);
  border-top-color: transparent;
  border-bottom-color: #1e293b;
}}
</style>
</head>
<body>
<div class="page-wrap">

  <!-- Header -->
  <div class="report-header">
    <h1>TERMINUS LLM BENCHMARK</h1>
    <p class="subtitle">Report generated {timestamp}</p>
  </div>

  <!-- Stats bar -->
  <div class="stats-bar">
    <div class="stat-item-top">
      <span class="stat-val-top">{total_games}</span>
      <span class="stat-lbl-top">Games</span>
    </div>
    <div class="stat-item-top">
      <span class="stat-val-top">{num_models}</span>
      <span class="stat-lbl-top">Models</span>
    </div>
    <div class="stat-item-top">
      <span class="stat-val-top">{elapsed}</span>
      <span class="stat-lbl-top">Duration</span>
    </div>
    <div class="stat-item-top">
      <span class="stat-val-top">{speed}×</span>
      <span class="stat-lbl-top">Speed</span>
    </div>
    <div class="stat-item-top">
      <span class="stat-val-top">{max_turns}</span>
      <span class="stat-lbl-top">Max Turns</span>
    </div>
    <div class="stat-item-top">
      <span class="stat-val-top">{num_catastrophes}</span>
      <span class="stat-lbl-top">Catastrophes</span>
    </div>
  </div>

  <!-- Rankings -->
  <h2 class="section-heading">Final Rankings</h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th><th>Model</th><th>Composite</th>
          <th>Avg Score</th><th>Valid Rate</th><th>Games</th>
          <th>Archetype</th><th>Trend</th>
        </tr>
      </thead>
      <tbody>{rankings_rows}</tbody>
    </table>
  </div>

  <!-- Cognitive Dimensions -->
  <h2 class="section-heading">Cognitive Dimensions</h2>
  {dimension_table}

  <!-- Tier-1 Drill-down -->
  <h2 class="section-heading">Tier-1 Metric Drill-Down</h2>
  {tier1_section}

  <!-- Per-Model Summary -->
  <h2 class="section-heading">Per-Model Summary</h2>
  {per_model_html}

  <!-- Configuration -->
  <h2 class="section-heading">Configuration</h2>
  <div class="table-wrap">
    {config_html}
  </div>

  <div class="footer">
    <p>Generated by Terminus LLM Benchmark Suite &nbsp;·&nbsp;
       <a href="https://github.com/kushal-DL/terminus">github.com/kushal-DL/terminus</a>
    </p>
  </div>

</div>
</body>
</html>
"""
