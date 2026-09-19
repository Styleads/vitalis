"""
test_reservation.py
===================
Spec §8: atomic reservation and release.

All expected values are computable by hand from a tiny, fixed pool.

Unit-id assignment order (enum order, sequential from 1):
  BED: 1, 2, 3
  ICU_BED: 4
  OR: 5
  DOCTOR: 6, 7
  NURSE: 8, 9, 10
  AMBULANCE: 11

Only the resource types used in each test's EngineConfig are created.
"""

import pytest

from engine.types import ResourceType, Unit
from engine.resources import ResourcePool, try_reserve, release
from engine.config import EngineConfig


# ---------------------------------------------------------------------------
# Helper: build a ResourcePool from a dict of capacities
# ---------------------------------------------------------------------------

def _pool(capacities: dict) -> ResourcePool:
    """Build a ResourcePool from a capacity dict; unit ids are sequential."""
    config = EngineConfig(
        capacities=capacities,
        bundles={},
        or_probability={},
        mean_service_s={},
        urgency_mix={},
        base_arrival_rate=1.0,
    )
    return ResourcePool(config.capacities)


# ---------------------------------------------------------------------------
# Atomic rollback
# ---------------------------------------------------------------------------

def test_try_reserve_atomic_rollback_no_state_change() -> None:
    """
    Spec §8: if any type in the bundle has too few free units, return None and
    leave state completely unchanged.

    Pool: BED×2, DOCTOR×2, ICU_BED×1.
    Pre-occupy the only ICU_BED (unit 5).
    Request BED+DOCTOR+ICU_BED — must fail atomically.
    No unit other than the pre-occupied one must change.
    """
    pool = _pool({
        ResourceType.BED: 2,
        ResourceType.DOCTOR: 2,
        ResourceType.ICU_BED: 1,
    })
    # Unit ids: BED=1,2  DOCTOR=3,4  ICU_BED=5
    icu_unit = next(u for u in pool.units.values() if u.type == ResourceType.ICU_BED)
    icu_unit.status = "OCCUPIED"
    icu_unit.owner = 100

    before = {uid: (u.status, u.owner, u.pending_off) for uid, u in pool.units.items()}

    result = try_reserve(pool, {ResourceType.BED: 1, ResourceType.DOCTOR: 1, ResourceType.ICU_BED: 1}, 200)

    assert result is None
    after = {uid: (u.status, u.owner, u.pending_off) for uid, u in pool.units.items()}
    assert before == after, "try_reserve must not change any unit state on failure"


def test_try_reserve_rollback_when_partially_satisfiable() -> None:
    """
    Bundle: NURSE×3 but only 2 are free (one pre-occupied).
    No BED or DOCTOR must be disturbed.
    """
    pool = _pool({
        ResourceType.BED: 2,
        ResourceType.NURSE: 3,
    })
    # Pre-occupy one NURSE
    nurses = [u for u in pool.units.values() if u.type == ResourceType.NURSE]
    nurses[0].status = "OCCUPIED"
    nurses[0].owner = 77

    before = {uid: (u.status, u.owner, u.pending_off) for uid, u in pool.units.items()}

    result = try_reserve(pool, {ResourceType.BED: 1, ResourceType.NURSE: 3}, 10)

    assert result is None
    after = {uid: (u.status, u.owner, u.pending_off) for uid, u in pool.units.items()}
    assert before == after


# ---------------------------------------------------------------------------
# Lowest-id selection
# ---------------------------------------------------------------------------

def test_try_reserve_takes_lowest_ids() -> None:
    """
    Spec §8: pick the required number of FREE units with the lowest ids.

    Pool: BED×3, DOCTOR×3.
    Pre-occupy BED id=1 and DOCTOR id=4.
    Request BED×1, DOCTOR×2 → expect BED=2, DOCTOR=5,6.
    """
    pool = _pool({
        ResourceType.BED: 3,
        ResourceType.DOCTOR: 3,
    })
    # Unit ids: BED=1,2,3  DOCTOR=4,5,6
    pool.units[1].status = "OCCUPIED"; pool.units[1].owner = 99
    pool.units[4].status = "OCCUPIED"; pool.units[4].owner = 99

    result = try_reserve(pool, {ResourceType.BED: 1, ResourceType.DOCTOR: 2}, patient_id=10)

    # Returned list must be [2, 5, 6] in enum order then by id
    assert result == [2, 5, 6], f"Expected [2, 5, 6], got {result}"
    assert pool.units[2].status == "OCCUPIED" and pool.units[2].owner == 10
    assert pool.units[5].status == "OCCUPIED" and pool.units[5].owner == 10
    assert pool.units[6].status == "OCCUPIED" and pool.units[6].owner == 10
    # Un-requested units unchanged
    assert pool.units[3].status == "FREE"
    assert pool.units[3].owner is None


def test_try_reserve_enum_order_respected() -> None:
    """
    try_reserve must iterate types in enum order (BED before DOCTOR before NURSE),
    picking lowest ids within each type.
    """
    pool = _pool({
        ResourceType.BED: 2,
        ResourceType.DOCTOR: 2,
        ResourceType.NURSE: 2,
    })
    # All free; request one of each
    result = try_reserve(pool, {ResourceType.BED: 1, ResourceType.NURSE: 1, ResourceType.DOCTOR: 1}, 1)
    # BED ids 1,2; DOCTOR ids 3,4; NURSE ids 5,6 → lowest of each
    # Spec: for each type in enum order → BED(1), DOCTOR(3), NURSE(5)
    assert set(result) == {1, 3, 5}


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

def test_release_normal_unit_becomes_free() -> None:
    """release() on a non-pending_off unit sets status=FREE, owner=None."""
    unit = Unit(id=1, type=ResourceType.BED, status="OCCUPIED", owner=42, pending_off=False)
    release(unit)
    assert unit.status == "FREE"
    assert unit.owner is None
    assert unit.pending_off is False


def test_release_pending_off_unit_becomes_off() -> None:
    """release() on a pending_off=True unit sets status=OFF, clears pending_off, clears owner."""
    unit = Unit(id=2, type=ResourceType.BED, status="OCCUPIED", owner=42, pending_off=True)
    release(unit)
    assert unit.status == "OFF"
    assert unit.owner is None
    assert unit.pending_off is False


def test_release_does_not_affect_other_units() -> None:
    """Releasing one unit must not touch any other unit in the pool."""
    pool = _pool({ResourceType.BED: 3})
    # Manually occupy unit 2
    pool.units[2].status = "OCCUPIED"
    pool.units[2].owner = 5

    before_1 = (pool.units[1].status, pool.units[1].owner)
    before_3 = (pool.units[3].status, pool.units[3].owner)

    release(pool.units[2])

    assert pool.units[2].status == "FREE"
    assert (pool.units[1].status, pool.units[1].owner) == before_1
    assert (pool.units[3].status, pool.units[3].owner) == before_3


def test_try_reserve_empty_bundle_succeeds() -> None:
    """
    An empty bundle is vacuously satisfiable — should return [] and touch nothing.
    (Edge-case that falls out of the spec's 'for each type in bundle' loop.)
    """
    pool = _pool({ResourceType.BED: 2})
    before = {uid: (u.status, u.owner) for uid, u in pool.units.items()}
    result = try_reserve(pool, {}, patient_id=1)
    assert result == []
    after = {uid: (u.status, u.owner) for uid, u in pool.units.items()}
    assert before == after
