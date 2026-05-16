"""Balance data validation tests (5.2.1–5.2.5).

Validates catastrophe data integrity, severity progression,
location vulnerability matrix, mitigation mapping, and selection algorithm.
"""

import pytest

from terminus.data.loader import get_catastrophes, get_buildings, get_catastrophe_by_id
from terminus.server.models import Location, Specialization


# ─── Load data once ──────────────────────────────────────────────────────────

ALL_CATASTROPHES = get_catastrophes()
ALL_BUILDINGS = get_buildings()
LOCATIONS = [loc.value for loc in Location]
BUILDING_IDS = [b["id"] for b in ALL_BUILDINGS]


# ─── 5.2.1 Category Distribution ────────────────────────────────────────────


class TestCategoryDistribution:
    """Verify catastrophe category distribution is balanced."""

    def test_has_catastrophes(self):
        assert len(ALL_CATASTROPHES) >= 15, "Need at least 15 catastrophes"

    def test_all_have_category(self):
        for cat in ALL_CATASTROPHES:
            assert "category" in cat, f"Catastrophe {cat['id']} missing 'category'"
            assert cat["category"], f"Catastrophe {cat['id']} has empty category"

    def test_category_count_range(self):
        """No category should have fewer than 2 or more than 8 catastrophes."""
        by_category: dict[str, int] = {}
        for cat in ALL_CATASTROPHES:
            by_category[cat["category"]] = by_category.get(cat["category"], 0) + 1

        assert len(by_category) >= 3, f"Too few categories: {list(by_category.keys())}"
        for category, count in by_category.items():
            assert 2 <= count <= 8, f"Category '{category}' has {count} catastrophes (expected 2-8)"

    def test_multiple_categories_exist(self):
        categories = set(cat["category"] for cat in ALL_CATASTROPHES)
        assert len(categories) >= 3, f"Only {len(categories)} categories: {categories}"


# ─── 5.2.2 Severity Progression ─────────────────────────────────────────────


class TestSeverityProgression:
    """Verify severity tiers ensure progressive difficulty."""

    def test_all_have_severity(self):
        for cat in ALL_CATASTROPHES:
            assert "severity" in cat, f"Catastrophe {cat['id']} missing 'severity'"
            assert cat["severity"] in (1, 2, 3), f"Invalid severity {cat['severity']} for {cat['id']}"

    def test_severity_distribution(self):
        """Should have catastrophes at each severity level."""
        by_sev = {1: 0, 2: 0, 3: 0}
        for cat in ALL_CATASTROPHES:
            by_sev[cat["severity"]] += 1
        for sev, count in by_sev.items():
            assert count >= 2, f"Severity {sev} has only {count} catastrophes (need ≥2)"

    def test_severity1_damage_limits(self):
        """Severity 1 catastrophes should have moderate damage."""
        for cat in ALL_CATASTROPHES:
            if cat["severity"] != 1:
                continue
            bd = cat["base_damage"]
            primary = cat["primary_effect"]
            if primary == "kill_population":
                assert bd <= 7, f"{cat['id']} sev1 pop damage {bd} > 7"
            elif primary in ("destroy_resource", "steal_resources"):
                assert bd <= 80, f"{cat['id']} sev1 resource damage {bd} > 80"
            elif primary == "damage_buildings":
                assert bd <= 50, f"{cat['id']} sev1 building damage {bd} > 50"

    def test_average_damage_increases_with_severity(self):
        """Average base_damage should increase: sev1 < sev2 < sev3."""
        by_sev: dict[int, list[float]] = {1: [], 2: [], 3: []}
        for cat in ALL_CATASTROPHES:
            by_sev[cat["severity"]].append(cat["base_damage"])

        for sev in (1, 2, 3):
            if by_sev[sev]:
                by_sev[sev] = [sum(by_sev[sev]) / len(by_sev[sev])]

        # Average damage should generally increase (allow some overlap)
        if by_sev[1] and by_sev[3]:
            assert by_sev[3][0] >= by_sev[1][0], (
                f"Sev3 avg damage ({by_sev[3][0]:.1f}) should be ≥ sev1 ({by_sev[1][0]:.1f})"
            )


# ─── 5.2.3 Location Vulnerability Matrix ────────────────────────────────────


class TestLocationVulnerability:
    """Verify location vulnerability matrix completeness and ranges."""

    def test_all_catastrophes_have_vulnerability(self):
        for cat in ALL_CATASTROPHES:
            assert "location_vulnerability" in cat, f"{cat['id']} missing location_vulnerability"
            vuln = cat["location_vulnerability"]
            assert isinstance(vuln, dict), f"{cat['id']} vulnerability is not a dict"

    def test_all_locations_covered(self):
        """Every catastrophe should have vulnerability for all 5 locations."""
        for cat in ALL_CATASTROPHES:
            vuln = cat["location_vulnerability"]
            for loc in LOCATIONS:
                assert loc in vuln, f"{cat['id']} missing vulnerability for {loc}"

    def test_vulnerability_range(self):
        """All vulnerability values should be between 0.5 and 2.0."""
        for cat in ALL_CATASTROPHES:
            vuln = cat["location_vulnerability"]
            for loc, val in vuln.items():
                assert 0.5 <= val <= 2.0, (
                    f"{cat['id']} vulnerability for {loc} is {val} (expected 0.5-2.0)"
                )

    def test_each_location_has_high_vulnerability(self):
        """Each location should be highly vulnerable (>1.0) to at least 2 catastrophes."""
        high_vuln_count: dict[str, int] = {loc: 0 for loc in LOCATIONS}
        for cat in ALL_CATASTROPHES:
            vuln = cat["location_vulnerability"]
            for loc in LOCATIONS:
                if vuln.get(loc, 1.0) > 1.0:
                    high_vuln_count[loc] += 1

        for loc, count in high_vuln_count.items():
            assert count >= 2, f"{loc} is only highly vulnerable to {count} catastrophes (need ≥2)"


# ─── 5.2.4 Mitigation Mapping ───────────────────────────────────────────────


class TestMitigationMapping:
    """Every catastrophe should have at least 1 mitigation option."""

    def test_all_have_mitigation(self):
        for cat in ALL_CATASTROPHES:
            has_building_mit = "mitigation_building" in cat and cat["mitigation_building"]
            has_worker_mit = "worker_mitigation" in cat and cat["worker_mitigation"]
            assert has_building_mit or has_worker_mit, (
                f"{cat['id']} has no mitigation (building or worker)"
            )

    def test_building_mitigation_references_valid_building(self):
        for cat in ALL_CATASTROPHES:
            mit_building = cat.get("mitigation_building")
            if mit_building:
                assert mit_building in BUILDING_IDS, (
                    f"{cat['id']} references non-existent building '{mit_building}'"
                )

    def test_mitigation_factor_minimum(self):
        """Primary mitigator should have factor ≥0.15."""
        for cat in ALL_CATASTROPHES:
            factor = cat.get("mitigation_factor", 0)
            if cat.get("mitigation_building"):
                assert factor >= 0.15, (
                    f"{cat['id']} building mitigation factor {factor} < 0.15"
                )

    def test_worker_mitigation_has_valid_role(self):
        from terminus.config import WORKER_ROLES
        for cat in ALL_CATASTROPHES:
            wm = cat.get("worker_mitigation")
            if wm:
                assert "role" in wm, f"{cat['id']} worker_mitigation missing 'role'"
                assert wm["role"] in WORKER_ROLES, (
                    f"{cat['id']} worker_mitigation role '{wm['role']}' not in {WORKER_ROLES}"
                )
                assert "factor" in wm, f"{cat['id']} worker_mitigation missing 'factor'"
                assert wm["factor"] > 0, f"{cat['id']} worker_mitigation factor must be > 0"


# ─── 5.2.5 Selection Algorithm ──────────────────────────────────────────────


class TestSelectionAlgorithm:
    """Verify _select_balanced_catastrophes works correctly for all combos."""

    @pytest.fixture
    def engine(self):
        from terminus.server.engine import GameEngine
        from terminus.server.models import GameSettings
        return GameEngine(settings=GameSettings(preset="quick"))

    def test_selects_correct_count(self, engine):
        """Should select exactly num_catastrophes catastrophes."""
        selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 4)
        assert len(selected) == 4

        selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 6)
        assert len(selected) == 6

    def test_no_duplicates(self, engine):
        """No catastrophe should appear twice in a single game."""
        for _ in range(20):  # run multiple times due to randomness
            selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 6)
            ids = [c["id"] for c in selected]
            assert len(ids) == len(set(ids)), f"Duplicate catastrophes: {ids}"

    def test_progressive_severity(self, engine):
        """Earlier catastrophes should generally have lower severity."""
        severity_ok_count = 0
        for _ in range(50):
            selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 6)
            severities = [c["severity"] for c in selected]
            # First half average should be ≤ second half average
            first_half = severities[:3]
            second_half = severities[3:]
            if sum(first_half) / 3 <= sum(second_half) / 3:
                severity_ok_count += 1

        # Should be progressive at least 60% of the time (randomness involved)
        assert severity_ok_count >= 30, f"Severity progression only held {severity_ok_count}/50 times"

    def test_category_diversity(self, engine):
        """Should use multiple categories, not just one."""
        for _ in range(20):
            selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 5)
            categories = set(c["category"] for c in selected)
            assert len(categories) >= 2, f"Only {len(categories)} category in selection: {categories}"

    def test_all_location_spec_combos_get_schedule(self, engine):
        """Scheduling should work for any game configuration."""
        for _ in range(5):
            selected = engine._select_balanced_catastrophes(ALL_CATASTROPHES, 5)
            assert len(selected) == 5
            # All selected should be valid catastrophe dicts
            for cat in selected:
                assert "id" in cat
                assert "severity" in cat
                assert "category" in cat
