"""Load and validate game data from JSON files."""

import json
import sys
from pathlib import Path
from typing import Any

# Support PyInstaller frozen executables: data files are extracted to sys._MEIPASS
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _DATA_DIR = Path(sys._MEIPASS) / "terminus" / "data"
else:
    _DATA_DIR = Path(__file__).parent


def _load_json(filename: str) -> list[dict[str, Any]]:
    filepath = _DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Game data file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {filename}, got {type(data).__name__}")
    return data


def load_catastrophes() -> list[dict[str, Any]]:
    """Load all catastrophe definitions."""
    data = _load_json("catastrophes.json")
    required = {"id", "name", "category", "severity", "description", "primary_effect", "base_damage", "mitigation_building", "mitigation_factor"}
    for item in data:
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Catastrophe '{item.get('id', '?')}' missing fields: {missing}")
    return data


def load_buildings() -> list[dict[str, Any]]:
    """Load all building definitions."""
    data = _load_json("buildings.json")
    required = {"id", "name", "description", "max_level", "costs", "build_time_ticks", "effects"}
    for item in data:
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Building '{item.get('id', '?')}' missing fields: {missing}")
    return data


def load_locations() -> list[dict[str, Any]]:
    """Load all location definitions."""
    data = _load_json("locations.json")
    required = {"id", "name", "description", "starting_resources", "production_modifiers"}
    for item in data:
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Location '{item.get('id', '?')}' missing fields: {missing}")
    return data


def load_specializations() -> list[dict[str, Any]]:
    """Load all specialization definitions."""
    data = _load_json("specializations.json")
    required = {"id", "name", "description", "bonuses"}
    for item in data:
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Specialization '{item.get('id', '?')}' missing fields: {missing}")
    return data


def load_achievements() -> list[dict[str, Any]]:
    """Load all achievement definitions."""
    data = _load_json("achievements.json")
    required = {"id", "name", "description", "icon", "bonus_points"}
    for item in data:
        missing = required - set(item.keys())
        if missing:
            raise ValueError(f"Achievement '{item.get('id', '?')}' missing fields: {missing}")
    return data


# Cached lookups (loaded once at import)
_catastrophes: list[dict[str, Any]] | None = None
_buildings: list[dict[str, Any]] | None = None
_locations: list[dict[str, Any]] | None = None
_specializations: list[dict[str, Any]] | None = None
_achievements: list[dict[str, Any]] | None = None


def get_catastrophes() -> list[dict[str, Any]]:
    global _catastrophes
    if _catastrophes is None:
        _catastrophes = load_catastrophes()
    return _catastrophes


def get_buildings() -> list[dict[str, Any]]:
    global _buildings
    if _buildings is None:
        _buildings = load_buildings()
    return _buildings


def get_locations() -> list[dict[str, Any]]:
    global _locations
    if _locations is None:
        _locations = load_locations()
    return _locations


def get_specializations() -> list[dict[str, Any]]:
    global _specializations
    if _specializations is None:
        _specializations = load_specializations()
    return _specializations


def get_achievements() -> list[dict[str, Any]]:
    global _achievements
    if _achievements is None:
        _achievements = load_achievements()
    return _achievements


def get_achievement_by_id(achievement_id: str) -> dict[str, Any] | None:
    for a in get_achievements():
        if a["id"] == achievement_id:
            return a
    return None


def get_catastrophe_by_id(catastrophe_id: str) -> dict[str, Any] | None:
    for c in get_catastrophes():
        if c["id"] == catastrophe_id:
            return c
    return None


def get_building_by_id(building_id: str) -> dict[str, Any] | None:
    for b in get_buildings():
        if b["id"] == building_id:
            return b
    return None


def get_location_by_id(location_id: str) -> dict[str, Any] | None:
    for loc in get_locations():
        if loc["id"] == location_id:
            return loc
    return None


def get_specialization_by_id(spec_id: str) -> dict[str, Any] | None:
    for s in get_specializations():
        if s["id"] == spec_id:
            return s
    return None
