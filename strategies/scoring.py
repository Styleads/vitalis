"""MedFlow - Core Scoring Primitives (Person B).

Pure, deterministic math functions for patient priority calculation.
Conforms to docs/AGENT.md (Person B spec §14-15).
"""

from __future__ import annotations

from typing import Any, Mapping

# ESI-inspired 5-level base urgency mapping (1 = Resuscitation / Critical, 5 = Non-urgent)
BASE_URGENCY_MAP: dict[int, float] = {
    1: 100.0,
    2: 80.0,
    3: 60.0,
    4: 40.0,
    5: 20.0,
}

# Default hyperparameters
DEFAULT_WAIT_WEIGHT_PER_MIN: float = 0.5
DEFAULT_WAIT_CAP: float = 40.0
DEFAULT_CONTENTION_WEIGHT: float = 10.0
DEFAULT_CONTENTION_THRESHOLD: float = 0.8


def base_urgency(urgency: int) -> float:
    """Return the base priority score for an ESI urgency level (1-5).
    
    1 (Critical) = 100.0
    2 (Emergent) = 80.0
    3 (Urgent) = 60.0
    4 (Less Urgent) = 40.0
    5 (Non-urgent) = 20.0
    
    Raises:
        KeyError: If urgency is not in 1..5.
    """
    if urgency not in BASE_URGENCY_MAP:
        raise KeyError(f"Invalid urgency level: {urgency}. Must be in 1..5.")
    return BASE_URGENCY_MAP[urgency]


def wait_bonus(
    wait_s: int,
    weight_per_min: float = DEFAULT_WAIT_WEIGHT_PER_MIN,
    cap: float = DEFAULT_WAIT_CAP,
) -> float:
    """Calculate the wait-time bonus to prevent starvation of low-urgency patients.
    
    Args:
        wait_s: Waiting time in simulated seconds (from patient_view.wait_s).
        weight_per_min: Priority points added per minute of waiting (default: 0.5).
        cap: Maximum wait bonus achievable (default: 40.0).
        
    Returns:
        float wait bonus in [0.0, cap].
        
    Invariant:
        base_urgency(5) + cap < base_urgency(1) (20.0 + 40.0 = 60.0 < 100.0).
        A stale Level-5 can never outrank a fresh Level-1.
    """
    if wait_s <= 0:
        return 0.0
    raw_bonus = (wait_s / 60.0) * weight_per_min
    return min(raw_bonus, cap)


def contention_penalty(
    required: Mapping[Any, int],
    state: Any,
    weight: float = DEFAULT_CONTENTION_WEIGHT,
    threshold: float = DEFAULT_CONTENTION_THRESHOLD,
) -> float:
    """Calculate contention penalty based on active resource pool occupancy.
    
    Nudges patients requesting an already-contended resource type slightly behind
    otherwise-equal patients requesting less-contended ones.
    
    Uses locked field names on StateView (§2.1):
      - state.active_capacities[rtype]: Total active units (total - failed - off).
      - state.free_counts[rtype]: Allocatable free units right now.
      
    Args:
        required: Mapping of ResourceType to quantity required by patient.
        state: StateView snapshot.
        weight: Scale factor for contention above threshold.
        threshold: Occupancy ratio above which penalty kicks in (e.g. 0.8 = 80%).
        
    Returns:
        float penalty >= 0.0.
    """
    active_capacities = getattr(state, "active_capacities", None)
    if active_capacities is None:
        active_capacities = getattr(state, "total", None)

    free_counts = getattr(state, "free_counts", None)
    if free_counts is None:
        free_counts = getattr(state, "free", None)

    # If state is a dict or mock object, support dict-like access as fallback
    if active_capacities is None and isinstance(state, dict):
        active_capacities = state.get("active_capacities", state.get("total", {}))
    if free_counts is None and isinstance(state, dict):
        free_counts = state.get("free_counts", state.get("free", {}))

    if not active_capacities or not free_counts:
        return 0.0

    penalty = 0.0
    for rtype, qty in required.items():
        if qty <= 0:
            continue
        total = active_capacities.get(rtype, 0)
        free = free_counts.get(rtype, 0)
        if total <= 0:
            continue
        occupancy = 1.0 - (free / total)
        if occupancy >= threshold:
            penalty += weight * (occupancy - threshold)

    return penalty
