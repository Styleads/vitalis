"""
engine/config.py
================
EngineConfig dataclass and ScriptedAction type alias.  Spec §12.

Placeholder defaults live here (spec §4), NOT in engine logic.
They are tagged *(placeholder)* in the spec and are tunable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from engine.types import ResourceType

# (time_s, "surge"|"capacity"|"fail", args-tuple)
ScriptedAction = tuple[int, str, tuple]


@dataclass
class EngineConfig:
    """
    Spec §12 public interface — do not change field names without telling B and C.

    All bundle/capacity/rate values are *placeholders* (spec §4, §13) and live
    here so they can be tuned without touching engine logic.
    """
    capacities:        dict[ResourceType, int]    # units per type
    bundles:           dict[int, dict[ResourceType, int]]   # base bundle per urgency
    or_probability:    dict[int, float]           # prob of needing OR, per urgency
    mean_service_s:    dict[int, int]             # mean service time per urgency (seconds)
    urgency_mix:       dict[int, float]           # probability mass per urgency level
    base_arrival_rate: float                      # patients per hour
    hol_policy:        str = "BACKFILL"           # "BACKFILL" or "BLOCK"
    debug_invariants:  bool = False               # call assert_invariants after every step


def default_config() -> EngineConfig:
    """
    Return an EngineConfig populated with the placeholder defaults from spec §4.
    Use this for the CLI harness and integration tests; unit tests should build
    their own small configs so expected values are hand-verifiable.
    """
    return EngineConfig(
        capacities={
            ResourceType.BED:       20,
            ResourceType.ICU_BED:   4,
            ResourceType.OR:        2,
            ResourceType.DOCTOR:    8,
            ResourceType.NURSE:     16,
            ResourceType.AMBULANCE: 3,
        },
        bundles={
            1: {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1, ResourceType.NURSE: 2},
            2: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            3: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            4: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1},
            5: {ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.3, 2: 0.1, 3: 0.0, 4: 0.0, 5: 0.0},
        mean_service_s={
            1: 4 * 3600,    # 4 h
            2: 3 * 3600,    # 3 h
            3: 2 * 3600,    # 2 h
            4: 1 * 3600,    # 1 h
            5: 20 * 60,     # 20 min
        },
        urgency_mix={1: 0.05, 2: 0.15, 3: 0.30, 4: 0.30, 5: 0.20},
        base_arrival_rate=10.0,   # patients per hour — placeholder
        hol_policy="BACKFILL",
        debug_invariants=False,
    )
