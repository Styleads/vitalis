"""
engine/invariants.py
====================
assert_invariants — spec §11.

Run after every step() when debug_invariants=True, and directly in the test
suite to verify broken-state detection.  A failing invariant is always a bug
in the implementation, never in the checker.

The ten invariants are:
  I1.  A unit is OCCUPIED iff its owner is not None.
  I2.  No unit id appears in two patients' assigned lists.
  I3.  Per type: free + occupied + failed + off == _total[rtype].
  I4.  A FAILED or OFF unit never has an owner.
  I5.  Every IN_TREATMENT patient's assigned list satisfies its full
       required bundle (count of each type in assigned >= required count).
  I6.  Every IN_TREATMENT patient has exactly one valid (token-matching)
       pending TREATMENT_DONE in the heap; WAITING and DISCHARGED patients
       have none.
  I7.  Every pending event has time >= clock.
  I8.  DISCHARGED patients hold no units (assigned is empty).
  I9.  pending_off is True only on OCCUPIED units.
  I10. 0 <= remaining_service <= service_time for every patient.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.types import ResourceType

if TYPE_CHECKING:
    from engine.engine import Engine


def assert_invariants(engine: "Engine") -> None:
    """
    Check all ten invariants.  Raise AssertionError on the first violation
    found.  Checks are ordered by ease of diagnosis (structural first).
    """
    units    = engine.resources.units
    patients = engine._patients

    # ── I1: OCCUPIED ↔ owner is not None ─────────────────────────────────
    for u in units.values():
        if u.status == "OCCUPIED":
            assert u.owner is not None, (
                f"I1: unit {u.id} is OCCUPIED but owner is None"
            )
        else:
            assert u.owner is None, (
                f"I1: unit {u.id} has status={u.status} but owner={u.owner} (expected None)"
            )

    # ── I2: no unit id claimed by two patients ────────────────────────────
    assigned_flat: list[int] = []
    for p in patients.values():
        assigned_flat.extend(p.assigned)
    assert len(assigned_flat) == len(set(assigned_flat)), (
        f"I2: duplicate unit ids in patient assigned lists: {sorted(assigned_flat)}"
    )

    # ── I3: per type totals are conserved ────────────────────────────────
    pool = engine.resources
    for rt in ResourceType:
        total    = pool._total[rt]
        computed = (
            pool.free_count(rt)
            + pool.occupied_count(rt)
            + pool.failed_count(rt)
            + pool.off_count(rt)
        )
        assert computed == total, (
            f"I3: {rt.value}: free+occupied+failed+off={computed} != total={total}"
        )

    # ── I4: FAILED and OFF units have no owner ───────────────────────────
    for u in units.values():
        if u.status in ("FAILED", "OFF"):
            assert u.owner is None, (
                f"I4: unit {u.id} has status={u.status} but owner={u.owner}"
            )

    # ── I5: IN_TREATMENT patient's assigned satisfies required ───────────
    for p in patients.values():
        if p.status != "IN_TREATMENT":
            continue
        # Count how many of each type are in the assigned list.
        assigned_by_type: dict[ResourceType, int] = {}
        for uid in p.assigned:
            rt = units[uid].type
            assigned_by_type[rt] = assigned_by_type.get(rt, 0) + 1
        for rt, count in p.required.items():
            have = assigned_by_type.get(rt, 0)
            assert have >= count, (
                f"I5: patient {p.id} needs {count}×{rt.value} but assigned only {have}"
            )

    # ── I6: valid TREATMENT_DONE cardinality ─────────────────────────────
    # A TREATMENT_DONE event is "valid" (non-cancelled) when its token matches
    # the patient's current token.  Stale events (token mismatch) are ignored
    # during dispatch; they do NOT count here.
    valid_td: dict[int, int] = {}   # patient_id → count of matching events
    for event in engine._heap:
        if event.kind != "TREATMENT_DONE":
            continue
        pid, tok = event.payload[0], event.payload[1]
        pat = patients.get(pid)
        if pat is not None and pat.token == tok:
            valid_td[pid] = valid_td.get(pid, 0) + 1

    for p in patients.values():
        count = valid_td.get(p.id, 0)
        if p.status == "IN_TREATMENT":
            assert count == 1, (
                f"I6: IN_TREATMENT patient {p.id} has {count} valid TREATMENT_DONE "
                f"(expected 1)"
            )
        else:
            assert count == 0, (
                f"I6: {p.status} patient {p.id} has {count} valid TREATMENT_DONE "
                f"(expected 0)"
            )

    # ── I7: every pending event has time >= clock ─────────────────────────
    # Since engine._heap is a min-heap ordered by (time, kind_rank, seq),
    # the minimum timestamp across all pending events is always at engine._heap[0].time.
    # Therefore, checking the heap root is mathematically equivalent to checking all events.
    if engine._heap:
        assert engine._heap[0].time >= engine.clock, (
            f"I7: event '{engine._heap[0].kind}' at t={engine._heap[0].time} < clock={engine.clock}"
        )

    # ── I8: DISCHARGED patients hold no units ────────────────────────────
    for p in patients.values():
        if p.status == "DISCHARGED":
            assert p.assigned == [], (
                f"I8: DISCHARGED patient {p.id} still has assigned={p.assigned}"
            )

    # ── I9: pending_off only on OCCUPIED units ────────────────────────────
    for u in units.values():
        if u.pending_off:
            assert u.status == "OCCUPIED", (
                f"I9: unit {u.id} has pending_off=True but status={u.status}"
            )

    # ── I10: 0 <= remaining_service <= service_time ───────────────────────
    for p in patients.values():
        assert 0 <= p.remaining_service <= p.service_time, (
            f"I10: patient {p.id} remaining_service={p.remaining_service} "
            f"outside [0, service_time={p.service_time}]"
        )
