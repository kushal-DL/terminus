"""Archetype classification — maps dimension profile to cognitive archetype."""

from __future__ import annotations

from terminus.benchmark.dimensions.base import ArchetypeLabel, DimensionScore


def classify_archetype(dimensions: dict[str, DimensionScore]) -> ArchetypeLabel:
    """Classify model archetype from dimension score profile.

    Uses deterministic threshold-based rules.
    """
    d1 = _get(dimensions, "dim_1_coherence")
    d2 = _get(dimensions, "dim_2_arithmetic")
    d3 = _get(dimensions, "dim_3_triage")
    d4 = _get(dimensions, "dim_4_error_recognition")
    d5 = _get(dimensions, "dim_5_pivot")
    d6 = _get(dimensions, "dim_6_degradation")
    d7 = _get(dimensions, "dim_7_opportunity")
    d8 = _get(dimensions, "dim_8_game_theory")

    # Oblivious: low across environment-awareness dimensions
    if d8 < 0.3 and d5 < 0.3 and d3 < 0.3:
        return ArchetypeLabel.OBLIVIOUS

    # Predator: high opportunity + game theory + triage
    if d7 > 0.7 and d8 > 0.7 and d3 > 0.6:
        return ArchetypeLabel.PREDATOR

    # Fortress: high stability + arithmetic + coherence
    if d6 > 0.8 and d2 > 0.7 and d1 > 0.7:
        return ArchetypeLabel.FORTRESS

    # Scholar: high coherence + opportunity + arithmetic
    if d1 > 0.8 and d7 > 0.7 and d2 > 0.7:
        return ArchetypeLabel.SCHOLAR

    # Diplomat: high pivot + game theory + coherence
    if d5 > 0.7 and d8 > 0.6 and d1 > 0.6:
        return ArchetypeLabel.DIPLOMAT

    # Chameleon: high pivot + triage + error recognition
    if d5 > 0.7 and d3 > 0.6 and d4 > 0.6:
        return ArchetypeLabel.CHAMELEON

    # Cautious: high degradation + error recognition + arithmetic
    if d6 > 0.7 and d4 > 0.7 and d2 > 0.6:
        return ArchetypeLabel.CAUTIOUS

    # Default: Pragmatist
    return ArchetypeLabel.PRAGMATIST


def _get(dimensions: dict[str, DimensionScore], dim_id: str) -> float:
    """Get dimension score value, defaulting to 0.5."""
    if dim_id in dimensions:
        return dimensions[dim_id].score
    return 0.5
