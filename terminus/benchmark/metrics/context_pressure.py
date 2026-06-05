"""Context pressure metrics (6.1–6.3) — measure degradation under context load."""

from __future__ import annotations

from terminus.benchmark.metrics.base import MetricCollector, MetricResult
from terminus.benchmark.metrics.utils import clamp, detect_change_point, rolling_average
from terminus.benchmark.schemas import GameRecording


class ContextPressureCollector(MetricCollector):
    """Computes metrics 6.1–6.3: quality degradation as context grows."""

    def compute(self, recording: GameRecording) -> list[MetricResult]:
        return [
            self._per_quartile_quality(recording),
            self._historical_reference_rate(recording),
            self._context_collapse_point(recording),
        ]

    # ─── 6.1 Per-Quartile Decision Quality ───────────────────────────────

    def _per_quartile_quality(self, recording: GameRecording) -> MetricResult:
        """Compare decision quality across game quartiles."""
        turns = recording.turns
        n = len(turns)
        if n < 8:
            return MetricResult(metric_id="6.1_per_quartile_quality", value=0.5, raw_value=0.0, sample_count=0)

        q_size = n // 4
        quartiles = [
            turns[:q_size],
            turns[q_size:2 * q_size],
            turns[2 * q_size:3 * q_size],
            turns[3 * q_size:],
        ]

        q_scores: list[float] = []
        for q_turns in quartiles:
            if not q_turns:
                q_scores.append(0.5)
                continue
            valid_rate = sum(1 for t in q_turns if t.valid) / len(q_turns)

            # Score delta as quality proxy: how much score improves per turn
            if len(q_turns) >= 2:
                score_start = q_turns[0].state.score
                score_end = q_turns[-1].state.score
                score_delta = (score_end - score_start) / len(q_turns)
                # Normalize delta: assume max reasonable delta is 50 per turn
                delta_norm = clamp(score_delta / 50 + 0.5)
            else:
                delta_norm = 0.5

            # Composite quality: 60% validity + 40% score progress
            q_scores.append(0.6 * valid_rate + 0.4 * delta_norm)

        # Score = Q4 quality / Q1 quality (no degradation = 1.0)
        q1 = q_scores[0] if q_scores[0] > 0 else 0.01
        q4 = q_scores[3]
        ratio = q4 / q1

        score = clamp(ratio, 0.0, 1.0)

        return MetricResult(
            metric_id="6.1_per_quartile_quality",
            value=score,
            raw_value=ratio,
            sample_count=n,
            details={
                "quartile_scores": q_scores,
                "q1": q_scores[0],
                "q4": q_scores[3],
                "ratio": ratio,
            },
        )

    # ─── 6.2 Historical Reference Rate ───────────────────────────────────

    def _historical_reference_rate(self, recording: GameRecording) -> MetricResult:
        """Check if late-game actions reference early-game decisions."""
        turns = recording.turns
        n = len(turns)
        if n < 8:
            return MetricResult(metric_id="6.2_historical_reference_rate", value=0.5, raw_value=0.0, sample_count=0)

        # Track early-game building types (Q1)
        q1_end = n // 4
        early_buildings: set[str] = set()
        for snap in turns[:q1_end]:
            if snap.parsed_response and snap.parsed_response.action.value == "BUILD" and snap.valid:
                btype = snap.parsed_response.params.get("building_type", "")
                if btype:
                    early_buildings.add(btype)

        if not early_buildings:
            return MetricResult(metric_id="6.2_historical_reference_rate", value=0.5, raw_value=0.0, sample_count=0)

        # In Q3+Q4: check if actions reference early buildings (upgrades, repairs)
        q3_start = n // 2
        late_turns = turns[q3_start:]
        references = 0
        total_late_actions = 0

        for snap in late_turns:
            if not snap.parsed_response:
                continue
            total_late_actions += 1
            action = snap.parsed_response.action
            params = snap.parsed_response.params
            btype = params.get("building_type", "")

            # Upgrade or repair of early-game building = historical reference
            if action in (
                "UPGRADE",
                "REPAIR",
            ) or (hasattr(action, 'value') and action.value in ("UPGRADE", "REPAIR")):
                if btype in early_buildings:
                    references += 1

        if total_late_actions == 0:
            return MetricResult(metric_id="6.2_historical_reference_rate", value=0.5, raw_value=0.0, sample_count=0)

        rate = references / total_late_actions
        # A rate of 0.2+ is good (not all actions should be references)
        score = clamp(rate / 0.3)  # 0.3 rate = perfect score

        return MetricResult(
            metric_id="6.2_historical_reference_rate",
            value=score,
            raw_value=rate,
            sample_count=total_late_actions,
            details={
                "references": references,
                "total_late_actions": total_late_actions,
                "early_buildings": list(early_buildings),
            },
        )

    # ─── 6.3 Context Collapse Point ──────────────────────────────────────

    def _context_collapse_point(self, recording: GameRecording) -> MetricResult:
        """Find turn where quality drops >20% from rolling average."""
        turns = recording.turns
        n = len(turns)
        if n < 10:
            return MetricResult(metric_id="6.3_context_collapse_point", value=1.0, raw_value=0.0, sample_count=0)

        # Build per-turn validity series
        validity_series = [1.0 if t.valid else 0.0 for t in turns]

        # Detect collapse: 5-turn rolling average drops below 80% of overall
        collapse_idx = detect_change_point(validity_series, threshold=0.8)

        if collapse_idx is None:
            # No collapse detected — perfect
            score = 1.0
            raw = float(n)
        else:
            # Score = how late the collapse happens (later = better)
            score = clamp(collapse_idx / n)
            raw = float(collapse_idx)

        # Also compute cumulative token context at collapse
        cumulative_tokens = 0
        collapse_tokens = 0
        for i, t in enumerate(turns):
            cumulative_tokens += t.tokens_used
            if collapse_idx is not None and i == collapse_idx:
                collapse_tokens = cumulative_tokens

        return MetricResult(
            metric_id="6.3_context_collapse_point",
            value=score,
            raw_value=raw,
            sample_count=n,
            details={
                "collapse_turn": collapse_idx,
                "total_turns": n,
                "collapse_tokens": collapse_tokens,
                "total_tokens": cumulative_tokens,
            },
        )
