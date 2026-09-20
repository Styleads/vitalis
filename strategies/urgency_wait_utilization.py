"""MedFlow - Urgency + Wait + Utilization Strategy (Person B).

Pure scoring function matching the Strategy type:
    Strategy = Callable[[PatientView, StateView, int], float]

Strategy 3: Nudges patients requesting an already-contended resource type
slightly behind otherwise-equal patients requesting less-contended ones.
This spreads resource load without ever inverting a genuine clinical urgency gap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from strategies.scoring import base_urgency, wait_bonus, contention_penalty

if TYPE_CHECKING:
    from engine.types import PatientView, StateView


def urgency_wait_utilization(p: Any, s: Any, now: int) -> float:
    """Score patient using urgency, wait time, and resource contention penalty.
    
    Score = base_urgency(p.urgency) + wait_bonus(p.wait_s) - contention_penalty(p.required, s)
    
    Uses:
      - p.wait_s: Precomputed by Engine (wait_time(now)).
      - p.required: Bundle of required resources.
      - s.active_capacities and s.free_counts: Locked StateView resource counts.
      
    Args:
        p: PatientView (frozen copy of patient state).
        s: StateView (frozen copy of engine state).
        now: Current simulation time in seconds.
        
    Returns:
        float priority score. Higher score = allocated sooner.
    """
    base = base_urgency(p.urgency)
    bonus = wait_bonus(p.wait_s)
    penalty = contention_penalty(p.required, s)
    return base + bonus - penalty
