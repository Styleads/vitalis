"""MedFlow - Scheduling Strategies Package (Person B).

Exports scoring functions, registry of strategies, scoring primitives,
and stats transformation/comparison helpers.
"""

from __future__ import annotations

from typing import Callable, Any
from strategies.scoring import (
    base_urgency,
    wait_bonus,
    contention_penalty,
    DEFAULT_WAIT_WEIGHT_PER_MIN,
    DEFAULT_WAIT_CAP,
    DEFAULT_CONTENTION_WEIGHT,
    DEFAULT_CONTENTION_THRESHOLD,
)
from strategies.urgency_only import urgency_only
from strategies.urgency_wait import urgency_wait
from strategies.urgency_wait_utilization import urgency_wait_utilization
from strategies.stats_display import to_display_stats, compare_strategies

# Strategy type signature: Callable[[PatientView, StateView, int], float]
Strategy = Callable[[Any, Any, int], float]

# Registry populated with the three core interchangeable strategies
STRATEGIES: dict[str, Strategy] = {
    "urgency_only": urgency_only,
    "urgency_wait": urgency_wait,
    "urgency_wait_utilization": urgency_wait_utilization,
}


def register_strategy(name: str, fn: Strategy) -> Strategy:
    """Register a strategy function by name."""
    STRATEGIES[name] = fn
    return fn


def get_strategy(name: str) -> Strategy:
    """Retrieve a strategy by name.
    
    Raises:
        KeyError: If strategy name is not registered.
    """
    if name not in STRATEGIES:
        available = ", ".join(repr(k) for k in STRATEGIES.keys())
        raise KeyError(f"Unknown strategy: {name!r}. Available: [{available}]")
    return STRATEGIES[name]


__all__ = [
    "Strategy",
    "STRATEGIES",
    "register_strategy",
    "get_strategy",
    "base_urgency",
    "wait_bonus",
    "contention_penalty",
    "urgency_only",
    "urgency_wait",
    "urgency_wait_utilization",
    "to_display_stats",
    "compare_strategies",
    "DEFAULT_WAIT_WEIGHT_PER_MIN",
    "DEFAULT_WAIT_CAP",
    "DEFAULT_CONTENTION_WEIGHT",
    "DEFAULT_CONTENTION_THRESHOLD",
]
