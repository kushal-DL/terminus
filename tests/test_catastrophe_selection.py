"""Tests for catastrophe selection algorithm balance."""
import random

import pytest

from terminus.data.loader import get_catastrophes
from terminus.server.engine import GameEngine
from terminus.server.models import GameSettings


@pytest.fixture
def all_cats():
    return get_catastrophes()


@pytest.fixture
def engine():
    return GameEngine(settings=GameSettings(preset="quick"))


def test_category_diversity(engine, all_cats):
    """Selected catastrophes should represent multiple categories."""
    selected = engine._select_balanced_catastrophes(all_cats, 5)
    categories = {c["category"] for c in selected}
    # With round-robin across 4 categories and 5 picks, expect at least 3 categories
    assert len(categories) >= 3, f"Only {len(categories)} categories: {categories}"


def test_severity_progression(engine, all_cats):
    """Earlier catastrophes should generally have lower severity than later ones."""
    selected = engine._select_balanced_catastrophes(all_cats, 6)
    severities = [c["severity"] for c in selected]
    # First half average severity should be <= second half average severity
    first_half = sum(severities[:3]) / 3
    second_half = sum(severities[3:]) / 3
    assert first_half <= second_half, f"Severity not progressing: {severities}"


def test_no_duplicate_selection(engine, all_cats):
    """Same catastrophe should not be selected twice."""
    selected = engine._select_balanced_catastrophes(all_cats, 6)
    ids = [c["id"] for c in selected]
    assert len(ids) == len(set(ids)), f"Duplicates found: {ids}"


def test_correct_count_returned(engine, all_cats):
    """Should return exactly the requested number of catastrophes."""
    for num in (1, 3, 5, 6):
        selected = engine._select_balanced_catastrophes(all_cats, num)
        assert len(selected) == num, f"Requested {num}, got {len(selected)}"


def test_handles_more_than_available(engine, all_cats):
    """When requesting more than available, should return up to what's available."""
    total = len(all_cats)
    selected = engine._select_balanced_catastrophes(all_cats, total + 5)
    assert len(selected) <= total


def test_deterministic_with_seed(engine, all_cats):
    """Same random seed should produce identical selection."""
    random.seed(42)
    first = engine._select_balanced_catastrophes(all_cats, 5)
    random.seed(42)
    second = engine._select_balanced_catastrophes(all_cats, 5)
    assert [c["id"] for c in first] == [c["id"] for c in second]
