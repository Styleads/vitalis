"""MedFlow - Shortest Predicted Service First Strategy (Person B - Experimental).

Phase 7 Stretch Strategy:
Incorporates Shortest Processing Time First (SPTF) heuristics into priority scoring
using predicted_service_time.

CLINICAL / ETHICAL CAVEAT:
In clinical healthcare operations, deprioritizing patients with longer expected length
of stay (LOS) creates fairness and equity issues because more complex or severely ill
patients may be penalized. This strategy is exposed strictly as an experimental
benchmark for comparing hospital throughput against clinical triage fairness.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from strategies.scoring import base_urgency, wait_bonus

if TYPE_CHECKING:
    from engine.types import PatientView, StateView


def shortest_predicted_service_first(
    p: Any,
    s: Any,
    now: int,
    service_weight: float = 10.0,
) -> float:
    """Score patient using urgency, wait time, and predicted service time bonus.
    
    Score = base_urgency(p.urgency) + wait_bonus(p.wait_s) + service_bonus
    
    Where service_bonus gives a slight priority boost to patients with shorter
    expected treatment durations (normalized to hours).
    
    Args:
        p: PatientView (frozen copy of patient state).
        s: StateView (frozen copy of engine state).
        now: Current simulation time in seconds.
        service_weight: Maximum points awarded for short treatment (default 10.0).
        
    Returns:
        float priority score. Higher score = allocated sooner.
    """
    base = base_urgency(p.urgency)
    bonus = wait_bonus(p.wait_s)

    predicted_s = getattr(p, "predicted_service_time", None)
    if predicted_s is None or predicted_s <= 0:
        predicted_s = getattr(p, "remaining_service", 3600)

    # Shorter predicted time -> higher bonus, scaled between [0, service_weight]
    # e.g., 10 min treatment -> ~8.5 pts, 4 hour treatment -> ~2.0 pts
    service_hours = max(0.1, predicted_s / 3600.0)
    service_bonus = service_weight / (1.0 + service_hours)

    return base + bonus + service_bonus
