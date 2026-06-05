"""Built-in benchmark opponents — agent registry and re-exports."""

from __future__ import annotations

from terminus.benchmark.opponents.base import BuiltInAgent
from terminus.benchmark.opponents.random_agent import RandomAgent
from terminus.benchmark.opponents.greedy_agent import GreedyAgent
from terminus.benchmark.opponents.balanced_agent import BalancedAgent
from terminus.benchmark.opponents.rush_agent import RushAgent
from terminus.benchmark.opponents.turtle_agent import TurtleAgent
from terminus.benchmark.opponents.adversarial_agent import AdversarialAgent

__all__ = [
    "BuiltInAgent",
    "RandomAgent",
    "GreedyAgent",
    "BalancedAgent",
    "RushAgent",
    "TurtleAgent",
    "AdversarialAgent",
    "get_agent",
    "AGENT_REGISTRY",
]

AGENT_REGISTRY: dict[str, type[BuiltInAgent]] = {
    "random": RandomAgent,
    "greedy": GreedyAgent,
    "balanced": BalancedAgent,
    "rush": RushAgent,
    "turtle": TurtleAgent,
    "adversarial": AdversarialAgent,
}


def get_agent(archetype: str, seed: int = 42) -> BuiltInAgent:
    """Create an agent instance by archetype name.

    Args:
        archetype: One of 'random', 'greedy', 'balanced', 'rush', 'turtle', 'adversarial'.
        seed: Random seed for reproducibility.

    Returns:
        BuiltInAgent instance.

    Raises:
        ValueError: If archetype is not recognized.
    """
    cls = AGENT_REGISTRY.get(archetype)
    if cls is None:
        valid = ", ".join(sorted(AGENT_REGISTRY.keys()))
        raise ValueError(f"Unknown agent archetype '{archetype}'. Valid: {valid}")
    return cls(seed=seed)
