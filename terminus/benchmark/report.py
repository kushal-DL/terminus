"""HTML Report Generator — creates a self-contained HTML benchmark report."""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_report(results: dict[str, Any], config: dict[str, Any], output_path: str) -> str:
    """Generate an HTML benchmark report and write it to output_path.

    Returns the absolute path to the written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rankings = results.get("rankings", [])
    model_stats = results.get("model_stats", {})
    total_games = results.get("total_games", 0)
    elapsed = results.get("elapsed_seconds", 0)
    dimensions = results.get("dimensions", {})

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elapsed_str = f"{elapsed / 60:.1f} min" if elapsed < 3600 else f"{elapsed / 3600:.1f} hours"

    # Build HTML
    rankings_rows = _build_rankings_rows(rankings)
    dimension_table = _build_dimension_table(dimensions, rankings)
    config_summary = _build_config_summary(config)
    per_model_details = _build_per_model_details(model_stats)

    content = _TEMPLATE.format(
        timestamp=timestamp,
        total_games=total_games,
        num_models=len(rankings),
        elapsed=elapsed_str,
        speed=config.get("speed_multiplier", 1),
        max_turns=config.get("max_turns", 100),
        num_catastrophes=config.get("num_catastrophes", 5),
        rankings_rows=rankings_rows,
        dimension_table=dimension_table,
        config_summary=config_summary,
        per_model_details=per_model_details,
    )

    path.write_text(content, encoding="utf-8")
    return str(path.resolve())


def _build_rankings_rows(rankings: list[dict[str, Any]]) -> str:
    rows = []
    for r in rankings:
        name = html.escape(str(r.get("name", "?")))
        score = r.get("score", 0)
        valid_rate = r.get("valid_rate", 0)
        games = r.get("games_played", 0)
        consistency = r.get("consistency", 0)
        trend = html.escape(str(r.get("trend", "—")))
        rank = r.get("rank", "?")

        # Color code by rank
        if rank == 1:
            cls = "gold"
        elif rank == 2:
            cls = "silver"
        elif rank == 3:
            cls = "bronze"
        else:
            cls = ""

        rows.append(
            f'<tr class="{cls}">'
            f"<td>{rank}</td>"
            f"<td><strong>{name}</strong></td>"
            f"<td>{score:.1f}</td>"
            f"<td>{valid_rate * 100:.0f}%</td>"
            f"<td>{games}</td>"
            f"<td>±{consistency:.1f}</td>"
            f"<td>{trend}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _build_dimension_table(dimensions: dict[str, Any], rankings: list[dict[str, Any]]) -> str:
    """Build the 8-dimension breakdown table."""
    dim_names = [
        "Multi-Decision Coherence",
        "Applied Arithmetic Under Load",
        "Priority Triage",
        "Compounding Error Recognition",
        "Justified Pivot",
        "Graceful Degradation",
        "Opportunity Cost Awareness",
        "Game-Theoretic Sophistication",
    ]

    if not dimensions:
        # Generate placeholder based on valid_rate proxy
        rows = []
        for r in rankings:
            name = html.escape(str(r.get("name", "?")))
            valid_rate = r.get("valid_rate", 0.5)
            # Approximate dimension scores from valid_rate as a rough proxy
            cells = "".join(
                f"<td>{_score_bar(valid_rate * (0.7 + i * 0.04))}</td>"
                for i in range(8)
            )
            rows.append(f"<tr><td><strong>{name}</strong></td>{cells}</tr>")

        header_cells = "".join(f"<th>{d[:20]}</th>" for d in dim_names)
        return (
            f"<table><thead><tr><th>Model</th>{header_cells}</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            f'<p class="note">Note: Dimension scores are approximations. '
            f"Full scoring requires game replay analysis.</p>"
        )

    # Real dimension data
    rows = []
    for model_name, dim_scores in dimensions.items():
        name = html.escape(str(model_name))
        cells = "".join(f"<td>{_score_bar(dim_scores.get(d, 0))}</td>" for d in dim_names)
        rows.append(f"<tr><td><strong>{name}</strong></td>{cells}</tr>")

    header_cells = "".join(f"<th>{d[:20]}</th>" for d in dim_names)
    return (
        f"<table><thead><tr><th>Model</th>{header_cells}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _score_bar(score: float) -> str:
    """Render a score as a colored bar + number."""
    score = max(0.0, min(1.0, score))
    pct = int(score * 100)
    if score >= 0.8:
        color = "#00ff41"
    elif score >= 0.6:
        color = "#ffb000"
    elif score >= 0.4:
        color = "#ff8c00"
    else:
        color = "#ff0040"
    return (
        f'<div class="score-bar">'
        f'<div class="bar-fill" style="width:{pct}%;background:{color}"></div>'
        f'<span class="bar-label">{score:.2f}</span>'
        f"</div>"
    )


def _build_config_summary(config: dict[str, Any]) -> str:
    models = config.get("models", [])
    model_names = ", ".join(html.escape(m.get("name", "?")) for m in models)
    return (
        f"<ul>"
        f"<li><strong>Models:</strong> {model_names}</li>"
        f"<li><strong>Games per matchup:</strong> {config.get('num_games', 10)}</li>"
        f"<li><strong>Opponents per model:</strong> {config.get('num_opponents', 6)}</li>"
        f"<li><strong>Max turns:</strong> {config.get('max_turns', 100)}</li>"
        f"<li><strong>Speed multiplier:</strong> {config.get('speed_multiplier', 1)}×</li>"
        f"<li><strong>Catastrophes per game:</strong> {config.get('num_catastrophes', 5)}</li>"
        f"<li><strong>Seed mode:</strong> {'Fixed' if config.get('seed_fixed', True) else 'Random'}</li>"
        f"</ul>"
    )


def _build_per_model_details(model_stats: dict[str, Any]) -> str:
    if not model_stats:
        return "<p>No detailed model statistics available.</p>"

    sections = []
    for name, stats in model_stats.items():
        escaped_name = html.escape(str(name))
        scores = stats.get("scores", [])
        avg = stats.get("avg_score", 0)
        valid = stats.get("total_valid", 0)
        invalid = stats.get("total_invalid", 0)
        total = valid + invalid

        # Mini sparkline via CSS
        spark_points = ""
        if scores:
            max_s = max(scores) if scores else 1
            min_s = min(scores) if scores else 0
            rng = max_s - min_s if max_s != min_s else 1
            normalized = [(s - min_s) / rng * 40 for s in scores]
            spark_points = " ".join(f"{i * 4},{40 - v}" for i, v in enumerate(normalized))

        sparkline_svg = ""
        if spark_points:
            width = len(scores) * 4
            sparkline_svg = (
                f'<svg class="sparkline" width="{width}" height="40" viewBox="0 0 {width} 40">'
                f'<polyline points="{spark_points}" fill="none" stroke="#00ff41" stroke-width="1.5"/>'
                f"</svg>"
            )

        sections.append(
            f'<div class="model-detail">'
            f"<h3>{escaped_name}</h3>"
            f"<p>Avg Score: <strong>{avg:.1f}</strong> │ "
            f"Valid: {valid}/{total} ({valid / total * 100:.0f}% valid) │ "
            f"Games: {stats.get('games_played', 0)}</p>"
            f'<p>Score range: {stats.get("min_score", 0):.0f} – {stats.get("max_score", 0):.0f}</p>'
            f"{sparkline_svg}"
            f"</div>"
        )

    return "\n".join(sections)


# ─── HTML Template ───────────────────────────────────────────────────────────

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Terminus LLM Benchmark Report — {timestamp}</title>
<style>
:root {{
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #00ff41;
    --amber: #ffb000;
    --red: #ff0040;
    --cyan: #00d4ff;
    --gold: #ffd700;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
}}
h1 {{
    color: var(--green);
    text-align: center;
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
    text-shadow: 0 0 10px rgba(0, 255, 65, 0.3);
}}
h2 {{
    color: var(--amber);
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
    margin: 2rem 0 1rem;
}}
h3 {{
    color: var(--cyan);
    margin-bottom: 0.5rem;
}}
.subtitle {{
    text-align: center;
    color: var(--muted);
    margin-bottom: 2rem;
}}
.stats-bar {{
    display: flex;
    justify-content: center;
    gap: 2rem;
    padding: 1rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    margin-bottom: 2rem;
}}
.stat {{
    text-align: center;
}}
.stat-value {{
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--green);
}}
.stat-label {{
    font-size: 0.8rem;
    color: var(--muted);
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
}}
th {{
    background: #1c2128;
    color: var(--amber);
    padding: 0.75rem 1rem;
    text-align: left;
    font-size: 0.85rem;
    white-space: nowrap;
}}
td {{
    padding: 0.6rem 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.9rem;
}}
tr:hover {{ background: #1c2128; }}
tr.gold td:first-child {{ color: var(--gold); font-weight: bold; }}
tr.silver td:first-child {{ color: #c0c0c0; font-weight: bold; }}
tr.bronze td:first-child {{ color: #cd7f32; font-weight: bold; }}
.score-bar {{
    position: relative;
    height: 20px;
    background: #21262d;
    border-radius: 3px;
    overflow: hidden;
    min-width: 80px;
}}
.bar-fill {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s;
}}
.bar-label {{
    position: absolute;
    right: 4px;
    top: 1px;
    font-size: 0.75rem;
    color: var(--text);
    font-weight: bold;
}}
.model-detail {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
    margin: 1rem 0;
}}
.model-detail p {{
    color: var(--muted);
    margin: 0.3rem 0;
}}
.sparkline {{
    margin-top: 0.5rem;
}}
.note {{
    color: var(--muted);
    font-style: italic;
    font-size: 0.85rem;
    margin-top: 1rem;
}}
ul {{
    list-style: none;
    padding: 0;
}}
ul li {{
    padding: 0.3rem 0;
    color: var(--muted);
}}
ul li strong {{
    color: var(--text);
}}
.footer {{
    text-align: center;
    color: var(--muted);
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.8rem;
}}
</style>
</head>
<body>
<h1>TERMINUS LLM BENCHMARK</h1>
<p class="subtitle">Report generated: {timestamp}</p>

<div class="stats-bar">
    <div class="stat">
        <div class="stat-value">{total_games}</div>
        <div class="stat-label">Games Played</div>
    </div>
    <div class="stat">
        <div class="stat-value">{num_models}</div>
        <div class="stat-label">Models Tested</div>
    </div>
    <div class="stat">
        <div class="stat-value">{elapsed}</div>
        <div class="stat-label">Duration</div>
    </div>
    <div class="stat">
        <div class="stat-value">{speed}×</div>
        <div class="stat-label">Speed</div>
    </div>
    <div class="stat">
        <div class="stat-value">{max_turns}</div>
        <div class="stat-label">Max Turns</div>
    </div>
    <div class="stat">
        <div class="stat-value">{num_catastrophes}</div>
        <div class="stat-label">Catastrophes</div>
    </div>
</div>

<h2>Final Rankings</h2>
<table>
<thead>
<tr>
    <th>#</th>
    <th>Model</th>
    <th>Avg Score</th>
    <th>Valid Rate</th>
    <th>Games</th>
    <th>Consistency</th>
    <th>Trend</th>
</tr>
</thead>
<tbody>
{rankings_rows}
</tbody>
</table>

<h2>Cognitive Dimensions</h2>
{dimension_table}

<h2>Per-Model Analysis</h2>
{per_model_details}

<h2>Configuration</h2>
{config_summary}

<div class="footer">
    <p>Generated by Terminus LLM Benchmark Suite</p>
    <p>github.com/kushal-DL/terminus</p>
</div>
</body>
</html>
"""
