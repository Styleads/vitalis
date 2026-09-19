"""
test_ordering.py
================
Tests for event-heap ordering (kind_rank), the step() event loop, and the
"exactly one allocation pass per step" rule.

All expected values are derivable by hand.
"""

from unittest.mock import patch

from engine.types import ResourceType, Patient
from engine.config import EngineConfig
from engine.engine import Engine
from tests.engine.conftest import fifo_strategy


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _single_bed_config(hol_policy: str = "BACKFILL") -> EngineConfig:
    """Minimal config: 1 BED + 1 DOCTOR, single urgency-1 bundle."""
    return EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy=hol_policy,
        debug_invariants=True,
    )


def _patient(pid: int, arrival: int, required: dict, service_time: int = 100) -> Patient:
    return Patient(
        id=pid,
        arrival_time=arrival,
        urgency=1,
        required=required,
        service_time=service_time,
        remaining_service=service_time,
        predicted_service_time=None,
        arrival_mode="WALK_IN",
        department="general",
        features={},
        status="WAITING",
        start_time=None,
        end_time=None,
        assigned=[],
        interruptions=0,
        segment_start=None,
        token=0,
    )


# ---------------------------------------------------------------------------
# Unit freed at t is usable by an arrival at t (rank 0 before rank 3)
# ---------------------------------------------------------------------------

def test_released_unit_usable_by_same_timestamp_arrival() -> None:
    """
    Spec §5 kind_rank: TREATMENT_DONE fires at rank 0, ARRIVAL at rank 3.
    At the same timestamp t, the done patient releases its units before the
    new arrival is processed, so the new arrival can be allocated immediately
    in the single allocation pass that follows.

    Setup:
      - p1 arrives t=0, service_time=100 → finishes at t=100.
      - p2 arrives t=100 (same timestamp as p1's completion).
      - Pool has exactly 1 BED + 1 DOCTOR.
    After step at t=100, p1 must be DISCHARGED and p2 must be IN_TREATMENT.
    """
    config = _single_bed_config()
    p1 = _patient(1, arrival=0,   required={ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=100)
    p2 = _patient(2, arrival=100, required={ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=100)

    eng = Engine(config, [p1, p2], fifo_strategy, seed=42)

    # Step at t=0: p1 arrives, allocation allocates p1
    eng.step()
    assert eng.clock == 0
    assert p1.status == "IN_TREATMENT"
    assert p2.status == "WAITING"

    # Step at t=100: TREATMENT_DONE(p1) fires first (rank 0), then ARRIVAL(p2) (rank 3),
    # then allocation pass assigns the now-free units to p2.
    eng.step()
    assert eng.clock == 100
    assert p1.status == "DISCHARGED"
    assert p2.status == "IN_TREATMENT"
    assert p2.start_time == 100


# ---------------------------------------------------------------------------
# kind_rank ordering: events at same timestamp run rank 0 → 3
# ---------------------------------------------------------------------------

def test_kind_rank_ordering_at_same_timestamp() -> None:
    """
    Spec §5: heap orders by (time, kind_rank, seq).  At the same timestamp
    events with lower kind_rank run first.

    We push events out of rank order and peek the heap to confirm ordering.
    """
    config = _single_bed_config()
    eng = Engine(config, [], fifo_strategy, seed=0)

    # Push at t=500 in reverse rank order
    eng._push_event(500, 3, "ARRIVAL",          (99,))           # rank 3
    eng._push_event(500, 2, "SURGE_START",       (2.0, 60))      # rank 2
    eng._push_event(500, 1, "CAPACITY_CHANGE",   (ResourceType.BED, 1))  # rank 1
    eng._push_event(500, 0, "TREATMENT_DONE",    (1, 1))         # rank 0

    popped_kinds = []
    while eng._heap and eng._peek_time() == 500:
        evt = eng._pop_event()
        popped_kinds.append(evt.kind)

    assert popped_kinds == ["TREATMENT_DONE", "CAPACITY_CHANGE", "SURGE_START", "ARRIVAL"], (
        f"Expected rank 0→1→2→3 order, got {popped_kinds}"
    )


def test_seq_breaks_ties_within_same_kind_rank() -> None:
    """
    Within the same (time, kind_rank), seq (push order) breaks the tie.
    Earlier-pushed events must pop first.
    """
    config = _single_bed_config()
    eng = Engine(config, [], fifo_strategy, seed=0)

    eng._push_event(300, 3, "ARRIVAL", (10,))   # pushed first → lower seq
    eng._push_event(300, 3, "ARRIVAL", (11,))   # pushed second → higher seq

    evt_a = eng._pop_event()
    evt_b = eng._pop_event()

    # payload patient id: first pushed is patient 10
    assert evt_a.payload[0] == 10
    assert evt_b.payload[0] == 11


# ---------------------------------------------------------------------------
# Events pushed at t during step(t) are processed in the same step
# ---------------------------------------------------------------------------

def test_events_pushed_at_t_processed_in_same_step() -> None:
    """
    Spec §6 step() rule 3: 'while the heap top has time == t, pop and apply it
    (handlers may push new events at t ... those are processed in the same loop).'

    inject_surge(multiplier, duration_s) enqueues SURGE_START at now=0.
    SURGE_START handler then pushes new ARRIVAL events at t=0 into the heap.
    Those arrivals must appear as log events within that same step() call.
    """
    config = EngineConfig(
        capacities={
            ResourceType.BED: 5,
            ResourceType.DOCTOR: 5,
            ResourceType.ICU_BED: 1,
            ResourceType.OR: 1,
            ResourceType.NURSE: 5,
            ResourceType.AMBULANCE: 1,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=10000.0,   # high rate → surge produces arrivals at t=0
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    eng = Engine(config, [], fifo_strategy, seed=42)
    eng.inject_surge(multiplier=5.0, duration_s=3600)   # enqueues SURGE_START at t=0

    step_logs = eng.step()   # processes SURGE_START and any t=0 arrivals it generates

    types_in_step = {log["type"] for log in step_logs}
    assert "SURGE_START" in types_in_step
    # Surge-generated arrivals at t=0 must also appear in the same step
    arrival_count = sum(1 for log in step_logs if log["type"] == "ARRIVAL")
    assert arrival_count > 0, (
        "Arrivals generated by SURGE_START at t=0 must be processed in the same step"
    )


# ---------------------------------------------------------------------------
# Exactly one allocation pass per step
# ---------------------------------------------------------------------------

def test_one_allocation_pass_per_step() -> None:
    """
    Spec §6 step() rule 4: 'Run the allocation pass exactly once.'

    Even when multiple events fire at the same timestamp, the allocation pass
    runs exactly once, after all events at that timestamp are processed.
    """
    config = _single_bed_config()
    p1 = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1})
    p2 = _patient(2, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1})

    eng = Engine(config, [p1, p2], fifo_strategy, seed=42)

    call_count = 0
    original = eng._allocation_pass

    def counting_pass():
        nonlocal call_count
        call_count += 1
        return original()

    # Patch the method on this instance
    eng._allocation_pass = counting_pass

    # Two arrivals at t=0
    eng.step()
    assert call_count == 1, (
        f"Allocation pass must run exactly once per step, but ran {call_count} times"
    )
