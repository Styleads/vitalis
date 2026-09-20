"""MedFlow - Urgency + Wait Time Strategy (Person B).

Pure scoring function matching the Strategy type:
    Strategy = Callable[[PatientView, StateView, int], float]

The default fair strategy: balances clinical urgency with starvation prevention
by adding a capped wait-time bonus derived from patient_view.wait_s.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from strategies.scoring import base_urgency, wait_bonus

if TYPE_CHECKING:
    from engine.types import PatientView, StateView


def urgency_wait(p: Any, s: Any, now: int) -> float:
    """Score patient based on triage urgency and waiting time.
    
    Score = base_urgency(p.urgency) + wait_bonus(p.wait_s)
    
    Uses p.wait_s directly (precomputed by Engine as wait_time(now)) to prevent
    drift bugs from dual sources of truth.
    
    Args:
        p: PatientView (frozen copy of patient state).
        s: StateView (frozen copy of engine state).
        now: Current simulation time in seconds.
        
    Returns:
        float priority score. Higher score = allocated sooner.
    """
    return base_urgency(p.urgency) + wait_bonus(p.wait_s)
