"""MedFlow - Urgency Only Strategy (Person B).

Pure scoring function matching the Strategy type:
    Strategy = Callable[[PatientView, StateView, int], float]

Urgency-only is deliberately the baseline strategy. Its clinical priority is
solely derived from the patient's triage urgency level, meaning it ignores wait
time and will visibly starve low-urgency patients in comparisons.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from strategies.scoring import base_urgency

if TYPE_CHECKING:
    from engine.types import PatientView, StateView


def urgency_only(p: Any, s: Any, now: int) -> float:
    """Score patient based purely on triage urgency level.
    
    Score = base_urgency(p.urgency)
    
    Args:
        p: PatientView (frozen copy of patient state).
        s: StateView (frozen copy of engine state).
        now: Current simulation time in seconds.
        
    Returns:
        float priority score in [20.0, 100.0]. Higher score = allocated sooner.
    """
    return base_urgency(p.urgency)
