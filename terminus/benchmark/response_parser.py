"""Response parser — JSON extraction, schema coercion, and validation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from terminus.benchmark.schemas import (
    ActionResponse,
    BenchmarkActionType,
    BenchmarkGameState,
    Reasoning,
    ReasoningFactor,
    ReasoningFactorType,
)

logger = logging.getLogger(__name__)


def parse_action_response(raw_text: str) -> ActionResponse:
    """Parse raw LLM text into an ActionResponse.

    Applies extraction pipeline:
    1. Strip markdown fences
    2. Find JSON object boundaries
    3. Fix common JSON issues
    4. Parse and coerce to ActionResponse
    """
    extracted = extract_json(raw_text)
    if extracted is None:
        raise ValueError(f"Could not extract valid JSON from response: {raw_text[:200]}")
    return coerce_response(extracted)


def extract_json(raw_text: str) -> dict | None:
    """Extract a JSON object from raw LLM text.

    Handles:
    - Markdown code fences (```json ... ```)
    - Natural language before/after JSON
    - Trailing commas
    - Single quotes
    """
    text = raw_text.strip()

    # Strip markdown code fences
    text = _strip_code_fences(text)

    # Find the first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    json_str = text[start : end + 1]

    # Fix common issues
    json_str = _fix_json_issues(json_str)

    try:
        data = json.loads(json_str)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        return None


def coerce_response(raw_dict: dict) -> ActionResponse:
    """Coerce a raw dict into an ActionResponse, applying soft fixes."""
    # Normalize action type
    action_str = raw_dict.get("action", raw_dict.get("action_type", "PASS"))
    action_str = str(action_str).upper().strip()

    try:
        action = BenchmarkActionType(action_str)
    except ValueError:
        # Try fuzzy match
        action = _fuzzy_match_action(action_str)

    # Extract params
    params = raw_dict.get("params", raw_dict.get("payload", {}))
    if params is None:
        params = {}

    # Extract and coerce reasoning
    reasoning = _coerce_reasoning(raw_dict.get("reasoning"))

    return ActionResponse(
        action=action,
        params=params,
        reasoning=reasoning,
    )


def validate_action_feasibility(
    response: ActionResponse,
    state: BenchmarkGameState,
) -> list[str]:
    """Validate that an action is feasible given the current state.

    Returns a list of error messages (empty if valid).
    """
    errors: list[str] = []
    params = response.params

    if response.action == BenchmarkActionType.ALLOCATE_WORKERS:
        allocation = params.get("allocation", {})
        if isinstance(allocation, dict):
            total = sum(allocation.values())
            if total != state.population:
                errors.append(
                    f"Worker allocation sums to {total}, but population is {state.population}"
                )

    elif response.action == BenchmarkActionType.TRADE_BUY:
        quantity = params.get("quantity", 0)
        resource = params.get("resource", "")
        if quantity <= 0:
            errors.append("Trade quantity must be positive")
        if resource not in ("food", "materials", "knowledge"):
            errors.append(f"Invalid trade resource: {resource}")

    elif response.action == BenchmarkActionType.TRADE_SELL:
        quantity = params.get("quantity", 0)
        resource = params.get("resource", "")
        if quantity <= 0:
            errors.append("Trade quantity must be positive")
        if resource not in ("food", "materials", "knowledge"):
            errors.append(f"Invalid trade resource: {resource}")
        # Check if player has enough
        if resource and hasattr(state.resources, resource):
            available = getattr(state.resources, resource)
            if quantity > available:
                errors.append(f"Insufficient {resource}: have {available}, want to sell {quantity}")

    elif response.action == BenchmarkActionType.TRADE_OFFER:
        if not params.get("to_player_id"):
            errors.append("TRADE_OFFER requires to_player_id")
        if not params.get("offer_resources") and not params.get("request_resources"):
            errors.append("TRADE_OFFER requires at least offer_resources or request_resources")

    elif response.action == BenchmarkActionType.TRADE_ACCEPT:
        if not params.get("offer_id"):
            errors.append("TRADE_ACCEPT requires offer_id")

    elif response.action == BenchmarkActionType.TRADE_DECLINE:
        if not params.get("offer_id"):
            errors.append("TRADE_DECLINE requires offer_id")

    return errors


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences."""
    # Match ```json ... ``` or ``` ... ```
    pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def _fix_json_issues(json_str: str) -> str:
    """Fix common JSON formatting issues from LLMs."""
    # Remove trailing commas before } or ]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
    # Replace single quotes with double quotes (naive — doesn't handle apostrophes in values well)
    # Only do this if there are no double quotes (likely the LLM used all single quotes)
    if '"' not in json_str and "'" in json_str:
        json_str = json_str.replace("'", '"')
    return json_str


def _fuzzy_match_action(action_str: str) -> BenchmarkActionType:
    """Try to match a malformed action string to a valid action type."""
    # Remove common prefixes/suffixes
    cleaned = action_str.strip().upper().replace("-", "_").replace(" ", "_")

    # Direct enum lookup
    for action in BenchmarkActionType:
        if action.value == cleaned:
            return action

    # Partial match
    for action in BenchmarkActionType:
        if cleaned in action.value or action.value in cleaned:
            return action

    # Default fallback
    return BenchmarkActionType.PASS


def _coerce_reasoning(raw: Any) -> Reasoning | None:
    """Coerce raw reasoning data into a Reasoning model."""
    if raw is None:
        return None

    if isinstance(raw, str):
        # LLM returned reasoning as a string — can't parse structured factors
        return None

    if isinstance(raw, dict):
        factors_raw = raw.get("factors", [])
        if not factors_raw:
            return None

        factors: list[ReasoningFactor] = []
        for f in factors_raw:
            if not isinstance(f, dict):
                continue
            factor_name = f.get("factor", "")
            weight = f.get("weight", 0.0)

            # Normalize factor name
            try:
                factor_type = ReasoningFactorType(factor_name)
            except ValueError:
                # Try to match by partial name
                factor_type = _fuzzy_match_factor(factor_name)
                if factor_type is None:
                    continue

            try:
                weight = float(weight)
                weight = max(0.0, min(1.0, weight))
            except (TypeError, ValueError):
                weight = 0.25

            factors.append(ReasoningFactor(factor=factor_type, weight=weight))

        if not factors:
            return None

        # Normalize weights to sum to ~1.0
        total = sum(f.weight for f in factors)
        if total > 0 and not (0.8 <= total <= 1.2):
            for f in factors:
                f.weight = f.weight / total

        try:
            return Reasoning(factors=factors)
        except ValueError:
            return None

    return None


def _fuzzy_match_factor(name: str) -> ReasoningFactorType | None:
    """Try to match a malformed factor name."""
    cleaned = name.lower().strip().replace("-", "_").replace(" ", "_")

    for factor in ReasoningFactorType:
        if factor.value == cleaned:
            return factor

    # Partial match
    for factor in ReasoningFactorType:
        if cleaned in factor.value or factor.value in cleaned:
            return factor

    return None
