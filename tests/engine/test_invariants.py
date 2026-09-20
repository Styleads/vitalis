"""
test_invariants.py
==================
Two layers of testing:

1. Property test — run 10 000 simulation steps across multiple seeds with
   debug_invariants=True enabled so assert_invariants() fires inside step().
   If any invariant is violated the engine itself raises AssertionError.

2. Targeted unit tests (I1–I10) — each test deliberately puts the engine into
   a state that breaks exactly one invariant and confirms assert_invariants()
   raises AssertionError.

Tests are written from the spec (Part 2, §11), never from an implementation.
"""

import pytest

from engine.types import ResourceType, Patient, Unit
from engine.config import EngineConfig
from engine.engine import Engine
from engine.invariants import assert_invariants
from engine.arrivals import generate_arrivals
from tests.engine.conftest import fifo_strategy, make_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_patient(
    pid: int,
    arrival: int = 0,
    urgency: int = 5,
    required: dict | None = None,
    service_time: int = 100,
    status: str = "WAITING",
    assigned: list | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    interruptions: int = 0,
    segment_start: int | None = None,
    token: int = 0,
    remaining_service: int | None = None,
) -> Patient:
    if required is None:
        required = {ResourceType.DOCTOR: 1}
    if assigned is None:
        assigned = []
    rs = remaining_service if remaining_service is not None else service_time
    return Patient(
        id=pid,
        arrival_time=arrival,
        urgency=urgency,
        required=required,
        service_time=service_time,
        remaining_service=rs,
        predicted_service_time=None,
        arrival_mode="WALK_IN",
        department="general",
        features={},
        status=status,
        start_time=start_time,
        end_time=end_time,
        assigned=assigned,
        interruptions=interruptions,
        segment_start=segment_start,
        token=token,
    )


# ---------------------------------------------------------------------------
# Property test: 10 000 steps, several seeds, dynamic scenario actions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [42, 123, 999, 2026])
def test_property_10000_steps_debug_invariants(seed: int) -> None:
    """
    Run 10 000 simulation steps with debug_invariants=True so assert_invariants
    fires automatically inside every step().  If any invariant is violated the
    engine raises AssertionError and this test fails.
    Includes surges, capacity changes, and resource failures so all paths are
    exercised.
    """
    config = make_config(debug_invariants=True)
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=18_000)
    scripted = [
        (1_000, "surge",    (2.5, 1_200)),
        (2_500, "capacity", (ResourceType.NURSE, 1)),
        (3_600, "fail",     (1, 600)),
        (5_000, "capacity", (ResourceType.NURSE, 3)),
        (7_200, "surge",    (1.5, 600)),
        (9_000, "fail",     (2, 300)),
    ]
    eng = Engine(config, arrivals, fifo_strategy, seed=seed, scripted=scripted)

    for _ in range(10_000):
        logs = eng.step()
        if logs is None:          # empty heap: simulation exhausted
            break


# ---------------------------------------------------------------------------
# I1 — OCCUPIED iff owner is not None
# ---------------------------------------------------------------------------

def test_i1_occupied_must_have_owner() -> None:
    """I1: OCCUPIED unit with owner=None must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    # Mark one FREE unit as OCCUPIED but leave owner None
    u = next(u for u in eng.resources.units.values() if u.status == "FREE")
    u.status = "OCCUPIED"
    u.owner = None           # violates I1
    with pytest.raises(AssertionError):
        assert_invariants(eng)


def test_i1_free_must_not_have_owner() -> None:
    """I1: FREE unit with a non-None owner must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    u = next(u for u in eng.resources.units.values() if u.status == "FREE")
    u.owner = 99             # violates I1 (FREE ↔ owner=None)
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I2 — No unit id in two patients' assigned lists
# ---------------------------------------------------------------------------

def test_i2_duplicate_unit_assignment() -> None:
    """I2: same unit id in two patients' assigned lists must be detected."""
    config = make_config(debug_invariants=False)
    # Two patients both claim unit 1
    p1 = _make_patient(1, status="IN_TREATMENT", assigned=[1], start_time=0, segment_start=0, token=1)
    p2 = _make_patient(2, status="IN_TREATMENT", assigned=[1], start_time=0, segment_start=0, token=1)
    eng = Engine(config, [p1, p2], fifo_strategy, seed=0)
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I3 — Per type: occupied + free + failed + off == total
# ---------------------------------------------------------------------------

def test_i3_resource_totals_must_be_conserved() -> None:
    """I3: adding a phantom unit (bumping total) must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    # Corrupt the stored total for BED so the sum no longer matches
    eng.resources._total[ResourceType.BED] += 1   # ghost unit in the total
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I4 — FAILED or OFF unit never has an owner
# ---------------------------------------------------------------------------

def test_i4_failed_unit_must_not_have_owner() -> None:
    """I4: FAILED unit with a non-None owner must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    u = next(iter(eng.resources.units.values()))
    u.status = "FAILED"
    u.owner = 42
    with pytest.raises(AssertionError):
        assert_invariants(eng)


def test_i4_off_unit_must_not_have_owner() -> None:
    """I4: OFF unit with a non-None owner must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    u = next(iter(eng.resources.units.values()))
    u.status = "OFF"
    u.owner = 7
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I5 — IN_TREATMENT patient's assigned satisfies full required bundle
# ---------------------------------------------------------------------------

def test_i5_missing_resource_in_bundle() -> None:
    """I5: IN_TREATMENT patient whose assigned list doesn't cover required bundle must be detected."""
    config = make_config(debug_invariants=False)
    # Patient needs BED + DOCTOR but is only assigned one unit (missing DOCTOR)
    p = _make_patient(
        1,
        required={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        status="IN_TREATMENT",
        assigned=[1],       # only BED, no DOCTOR unit
        start_time=0,
        segment_start=0,
        token=1,
    )
    eng = Engine(config, [p], fifo_strategy, seed=0)
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I6 — IN_TREATMENT: exactly one valid pending TREATMENT_DONE;
#       WAITING/DISCHARGED: none
# ---------------------------------------------------------------------------

def test_i6_waiting_patient_must_not_have_treatment_done_event() -> None:
    """I6: a WAITING patient with a valid pending TREATMENT_DONE must be detected."""
    config = make_config(debug_invariants=False)
    p = _make_patient(1, status="WAITING", token=0)
    eng = Engine(config, [p], fifo_strategy, seed=0)
    # Push a (supposedly valid) TREATMENT_DONE for a WAITING patient
    eng._push_event(100, 0, "TREATMENT_DONE", (p.id, p.token))
    with pytest.raises(AssertionError):
        assert_invariants(eng)


def test_i6_in_treatment_must_have_exactly_one_treatment_done() -> None:
    """I6: IN_TREATMENT patient with NO pending TREATMENT_DONE must be detected."""
    config = make_config(debug_invariants=False)
    p = _make_patient(1, status="IN_TREATMENT", assigned=[1], start_time=0, segment_start=0, token=1)
    eng = Engine(config, [p], fifo_strategy, seed=0)
    # No TREATMENT_DONE pushed for this patient — should fail I6
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I7 — clock never decreases; every pushed event time >= clock
# ---------------------------------------------------------------------------

def test_i7_event_in_the_past_must_be_detected() -> None:
    """I7: an event with time < clock must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    eng.clock = 200
    # Push an event scheduled before current clock
    eng._push_event(50, 3, "ARRIVAL", (999,))
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I8 — DISCHARGED patients hold no units
# ---------------------------------------------------------------------------

def test_i8_discharged_patient_with_assigned_units() -> None:
    """I8: DISCHARGED patient still listing unit ids in assigned must be detected."""
    config = make_config(debug_invariants=False)
    p = _make_patient(
        1,
        status="DISCHARGED",
        assigned=[1],       # should be empty after discharge
        start_time=0,
        end_time=100,
        remaining_service=0,
    )
    eng = Engine(config, [p], fifo_strategy, seed=0)
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I9 — pending_off only on OCCUPIED units
# ---------------------------------------------------------------------------

def test_i9_pending_off_on_free_unit() -> None:
    """I9: pending_off=True on a FREE unit must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    u = next(u for u in eng.resources.units.values() if u.status == "FREE")
    u.pending_off = True
    with pytest.raises(AssertionError):
        assert_invariants(eng)


def test_i9_pending_off_on_failed_unit() -> None:
    """I9: pending_off=True on a FAILED unit must be detected."""
    config = make_config(debug_invariants=False)
    eng = Engine(config, [], fifo_strategy, seed=0)
    u = next(iter(eng.resources.units.values()))
    u.status = "FAILED"
    u.pending_off = True
    with pytest.raises(AssertionError):
        assert_invariants(eng)


# ---------------------------------------------------------------------------
# I10 — 0 <= remaining_service <= service_time
# ---------------------------------------------------------------------------

def test_i10_remaining_service_above_service_time() -> None:
    """I10: remaining_service > service_time must be detected."""
    config = make_config(debug_invariants=False)
    p = _make_patient(1, service_time=100, remaining_service=150)
    eng = Engine(config, [p], fifo_strategy, seed=0)
    with pytest.raises(AssertionError):
        assert_invariants(eng)


def test_i10_remaining_service_negative() -> None:
    """I10: remaining_service < 0 must be detected."""
    config = make_config(debug_invariants=False)
    p = _make_patient(1, service_time=100, remaining_service=-1)
    eng = Engine(config, [p], fifo_strategy, seed=0)
    with pytest.raises(AssertionError):
        assert_invariants(eng)
