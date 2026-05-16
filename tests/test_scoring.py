"""Tests for scoring formula verification."""
import pytest

from terminus.config import SCORE_WEIGHTS


@pytest.mark.asyncio
async def test_scoring_formula_correctness(playing_game):
    """Verify score = sum of component × weight for known values."""
    engine = playing_game
    host = [p for p in engine.state.players.values() if p.is_host][0]

    # Set known values
    host.colony.population = 20
    host.colony.resources.food = 100
    host.colony.resources.materials = 50
    host.colony.resources.knowledge = 30
    host.colony.resources.gold = 80
    host.colony.morale = 1.5
    host.colony.buildings = []  # No buildings

    scores = engine._calculate_scores()
    host_score = next(s for s in scores if s["player_id"] == host.player_id)

    expected = (
        20 * SCORE_WEIGHTS["population"]
        + 100 * SCORE_WEIGHTS["food"]
        + 50 * SCORE_WEIGHTS["materials"]
        + 30 * SCORE_WEIGHTS["knowledge"]
        + 80 * SCORE_WEIGHTS["gold"]
        + 1.5 * SCORE_WEIGHTS["morale"]
        + 0 * SCORE_WEIGHTS["building_health"]
    )

    assert host_score["score"] == round(expected, 1)


@pytest.mark.asyncio
async def test_scoring_averages_computed(playing_game):
    """Verify avg_score and delta_vs_avg are present and correct."""
    engine = playing_game
    scores = engine._calculate_scores()

    assert len(scores) == 2
    assert "avg_score" in scores[0]
    assert "delta_vs_avg" in scores[0]
    assert "avg_population" in scores[0]
    assert "avg_morale" in scores[0]

    # Average should be between min and max scores
    avg = scores[0]["avg_score"]
    all_scores = [s["score"] for s in scores]
    assert min(all_scores) <= avg <= max(all_scores)

    # Delta should sum to ~0
    total_delta = sum(s["delta_vs_avg"] for s in scores)
    assert abs(total_delta) < 1.0  # floating point tolerance


@pytest.mark.asyncio
async def test_scoring_order_descending(playing_game):
    """Verify scores are sorted descending."""
    engine = playing_game
    # Give one player much more resources
    host = [p for p in engine.state.players.values() if p.is_host][0]
    host.colony.resources.gold = 9999
    host.colony.population = 50

    scores = engine._calculate_scores()
    assert scores[0]["score"] >= scores[1]["score"]
    assert scores[0]["player_id"] == host.player_id
