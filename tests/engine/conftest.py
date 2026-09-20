"""
Shared fixtures and the trivial FIFO strategy used across all engine tests.

fifo_strategy: scores every patient 0.0, so allocation order is determined
solely by (arrival_time, id) — pure FIFO, easy to reason about by hand.
"""

from engine.types import ResourceType
from engine.config import EngineConfig


def fifo_strategy(pv, sv, now: int) -> float:
    """Trivial strategy: all patients score 0, sorted by arrival_time then id."""
    return 0.0


def make_config(
    *,
    bed: int = 3,
    icu: int = 1,
    or_: int = 1,
    doctor: int = 2,
    nurse: int = 3,
    ambulance: int = 1,
    hol_policy: str = "BACKFILL",
    debug_invariants: bool = True,
    base_arrival_rate: float = 20.0,
) -> EngineConfig:
    """Small, hand-verifiable config.  All OR-probability is 0 so bundles are deterministic."""
    return EngineConfig(
        capacities={
            ResourceType.BED: bed,
            ResourceType.ICU_BED: icu,
            ResourceType.OR: or_,
            ResourceType.DOCTOR: doctor,
            ResourceType.NURSE: nurse,
            ResourceType.AMBULANCE: ambulance,
        },
        bundles={
            1: {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1, ResourceType.NURSE: 2},
            2: {ResourceType.BED: 1, ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            3: {ResourceType.BED: 1, ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            4: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
            5: {ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
        mean_service_s={1: 300, 2: 200, 3: 150, 4: 100, 5: 50},
        urgency_mix={1: 0.1, 2: 0.2, 3: 0.3, 4: 0.2, 5: 0.2},
        base_arrival_rate=base_arrival_rate,
        hol_policy=hol_policy,
        debug_invariants=debug_invariants,
    )
