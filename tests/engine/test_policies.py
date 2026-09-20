"""
test_policies.py
================
Tests for:
  - HOL allocation policy: BACKFILL vs BLOCK
  - Capacity reduction: never interrupts active treatment (lazy OFF via pending_off)
  - P-FAIL: resource failure interrupts treatment, requeues patient with:
      * remaining_service = max(0, service_time - elapsed)
      * unchanged arrival_time
      * interruptions incremented
      * all units released (failed unit → FAILED; others → FREE or OFF)
      * token bumped (old TREATMENT_DONE silently skipped via lazy deletion)
  - Interrupted patient's PatientView.wait_s = now - arrival_time - (service_time - remaining_service)

All expected values are derivable by hand from the tiny fixture configs below.
"""

from engine.types import ResourceType, Patient
from engine.config import EngineConfig
from engine.engine import Engine
from tests.engine.conftest import fifo_strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patient(pid: int, arrival: int, required: dict, service_time: int = 200,
             urgency: int = 1) -> Patient:
    return Patient(
        id=pid,
        arrival_time=arrival,
        urgency=urgency,
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
# HOL policy: BACKFILL vs BLOCK
# ---------------------------------------------------------------------------

def test_backfill_skips_head_allocates_next() -> None:
    """
    Spec §7: BACKFILL — if head patient can't be allocated, skip and continue.

    Config: 0 ICU_BED, 1 BED, 1 DOCTOR.
    p1 (head, higher score) needs ICU_BED → fails.
    p2 needs BED → must be allocated under BACKFILL.
    """
    config = EngineConfig(
        capacities={
            ResourceType.BED: 1,
            ResourceType.ICU_BED: 0,
            ResourceType.DOCTOR: 1,
        },
        bundles={
            1: {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1},
            2: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.0, 2: 0.0},
        mean_service_s={1: 100, 2: 100},
        urgency_mix={1: 0.5, 2: 0.5},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    # p1 has urgency 1 → scores first; p2 has urgency 2 → scores second.
    # Both arrive at t=0 so fifo_strategy (score 0) preserves id order.
    p1 = _patient(1, 0, {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1}, urgency=1)
    p2 = _patient(2, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, urgency=2)

    eng = Engine(config, [p1, p2], fifo_strategy, seed=42)
    eng.step()

    assert p1.status == "WAITING",      "Head patient (needs ICU_BED) must remain WAITING"
    assert p2.status == "IN_TREATMENT", "Under BACKFILL, second patient must be allocated"


def test_block_halts_at_head() -> None:
    """
    Spec §7: BLOCK — if the head patient can't be allocated, stop the pass entirely.

    Same setup as above, but hol_policy="BLOCK": p2 must stay WAITING.
    """
    config = EngineConfig(
        capacities={
            ResourceType.BED: 1,
            ResourceType.ICU_BED: 0,
            ResourceType.DOCTOR: 1,
        },
        bundles={
            1: {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1},
            2: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.0, 2: 0.0},
        mean_service_s={1: 100, 2: 100},
        urgency_mix={1: 0.5, 2: 0.5},
        base_arrival_rate=1.0,
        hol_policy="BLOCK",
        debug_invariants=True,
    )
    p1 = _patient(1, 0, {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1}, urgency=1)
    p2 = _patient(2, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, urgency=2)

    eng = Engine(config, [p1, p2], fifo_strategy, seed=42)
    eng.step()

    assert p1.status == "WAITING", "Head patient (needs ICU_BED) must remain WAITING"
    assert p2.status == "WAITING", "Under BLOCK, second patient must NOT be allocated"


# ---------------------------------------------------------------------------
# Capacity reduction: lazy OFF (never interrupts treatment)
# ---------------------------------------------------------------------------

def test_capacity_reduction_sets_pending_off_not_interrupting() -> None:
    """
    Spec §9 set_capacity: reducing capacity on occupied units sets pending_off=True
    and never interrupts active treatment.

    Config: 2 BED, 2 DOCTOR. Allocate both patients.
    Reduce BED capacity from 2 to 1 via scripted CAPACITY_CHANGE.
    Both patients must remain IN_TREATMENT; the highest-id occupied BED gets pending_off=True.
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 2, ResourceType.DOCTOR: 2},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 300},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p1 = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=300)
    p2 = _patient(2, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=300)

    # Capacity CHANGE at t=1 (while both patients are in treatment), reducing BED to 1
    scripted = [(1, "capacity", (ResourceType.BED, 1))]
    eng = Engine(config, [p1, p2], fifo_strategy, seed=42, scripted=scripted)

    # Step at t=0 allocates p1 and p2; step at t=1 processes CAPACITY_CHANGE
    eng.run_until(1)

    # p1 and p2 must be allocated (both were WAITING at t=0 when BEDs were still FREE)
    # After capacity reduction the occupied BED (highest id) should have pending_off=True
    beds = [u for u in eng.resources.units.values() if u.type == ResourceType.BED]

    # Treatment must NOT be interrupted
    assert p1.status == "IN_TREATMENT", "p1 must remain IN_TREATMENT after capacity reduction"
    assert p2.status == "IN_TREATMENT", "p2 must remain IN_TREATMENT after capacity reduction"

    occupied_beds = [u for u in beds if u.status == "OCCUPIED"]
    pending_beds  = [u for u in beds if u.pending_off]
    assert len(pending_beds) == 1, "Exactly one occupied BED must have pending_off=True"
    assert pending_beds[0].id == max(u.id for u in occupied_beds), (
        "pending_off must be set on the highest-id occupied BED"
    )


def test_pending_off_unit_goes_off_on_release() -> None:
    """
    When a pending_off patient completes treatment, the unit goes OFF (not FREE).
    Spec §8 release(): if pending_off then status=OFF and pending_off=False.
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=100)
    eng = Engine(config, [p], fifo_strategy, seed=42)

    eng.step()   # t=0: allocate p
    assert p.status == "IN_TREATMENT"

    # Mark all occupied units as pending_off
    for uid in p.assigned:
        eng.resources.units[uid].pending_off = True

    eng.step()   # t=100: TREATMENT_DONE → release → units go OFF

    for uid in p.assigned:
        assert eng.resources.units[uid].status == "OFF",  \
            f"Unit {uid} with pending_off=True must become OFF after release"
        assert eng.resources.units[uid].owner is None
        assert eng.resources.units[uid].pending_off is False


# ---------------------------------------------------------------------------
# P-FAIL: resource failure interrupts treatment
# ---------------------------------------------------------------------------

def test_p_fail_requeues_patient_with_remaining_service() -> None:
    """
    Spec §9 P-FAIL:
      - Patient releases all units; failed unit → FAILED; others → FREE.
      - Patient status → WAITING.
      - arrival_time unchanged.
      - remaining_service = service_time - elapsed_in_segment (clamped to ≥0).
      - interruptions += 1.
      - token bumped.
      - INTERRUPTED event logged.

    Setup: BED×1, DOCTOR×1.  Patient p starts at t=0 with service_time=100.
    BED (unit 1) fails at t=40.  Elapsed segment time = 40.
    Expected remaining_service = 100 - 40 = 60.
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=100)
    scripted = [(40, "fail", (1, 600))]   # fail BED (unit 1) at t=40 for 600s
    eng = Engine(config, [p], fifo_strategy, seed=42, scripted=scripted)

    eng.step()   # t=0: allocate p
    assert p.status == "IN_TREATMENT"
    token_before_fail = p.token
    assert p.segment_start == 0

    logs = eng.step()   # t=40: FAILURE fires → P-FAIL applied

    assert eng.clock == 40
    assert p.status == "WAITING",          "Patient must be re-queued as WAITING"
    assert p.assigned == [],               "All units must be released"
    assert p.arrival_time == 0,            "arrival_time must be unchanged"
    assert p.remaining_service == 60,      "remaining_service must be service_time - elapsed (100-40=60)"
    assert p.interruptions == 1,           "interruptions counter must increment to 1"
    assert p.token != token_before_fail,   "token must be bumped to invalidate old TREATMENT_DONE"

    interrupted = [lg for lg in logs if lg.get("type") == "INTERRUPTED"]
    assert len(interrupted) == 1,          "Exactly one INTERRUPTED event must be logged"


def test_p_fail_failed_unit_is_failed_others_are_free() -> None:
    """
    Spec §9 P-FAIL: 'The failed unit becomes FAILED (not released to FREE).'
    All other units held by the interrupted patient become FREE (or OFF if pending_off).
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 200},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=200)
    # Fail BED (unit 1) at t=50.  DOCTOR (unit 2) must go FREE.
    scripted = [(50, "fail", (1, 300))]
    eng = Engine(config, [p], fifo_strategy, seed=42, scripted=scripted)

    eng.step()   # allocate at t=0
    eng.step()   # fail at t=50

    # Unit 1 (BED, the failed one) must be FAILED
    bed_unit = eng.resources.units[1]
    assert bed_unit.status == "FAILED"
    assert bed_unit.owner is None

    # Unit 2 (DOCTOR, released) must be FREE
    doc_unit = eng.resources.units[2]
    assert doc_unit.status == "FREE"
    assert doc_unit.owner is None


def test_p_fail_lazy_deletion_of_treatment_done() -> None:
    """
    Spec §5 TREATMENT_DONE cancellation: token mismatch → event skipped silently.

    After P-FAIL, the old TREATMENT_DONE (with stale token) must be ignored when
    it fires.  The patient must NOT be discharged spuriously.
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 200},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=200)
    # Fail at t=60; old TREATMENT_DONE would fire at t=200.
    # Recovery at t=660 (60+600).  We run until well past t=200.
    scripted = [(60, "fail", (1, 600))]
    eng = Engine(config, [p], fifo_strategy, seed=42, scripted=scripted)

    eng.step()   # t=0: allocate
    eng.step()   # t=60: P-FAIL, token bumped

    # Run past t=200 — the stale TREATMENT_DONE must be silently dropped
    eng.run_until(250)

    # Patient must still be WAITING (re-queued), NOT discharged
    assert p.status == "WAITING", (
        "Stale TREATMENT_DONE must be silently dropped; patient must remain WAITING"
    )


def test_p_fail_wait_s_grows_after_interruption() -> None:
    """
    Spec §4 Patient.wait_s:
        wait_s(now) = now - arrival_time - (service_time - remaining_service)

    After P-FAIL at t=40 with remaining_service=60 (out of service_time=100):
        - At t=40:  40 - 0 - (100 - 60) = 0
        - At t=80:  80 - 0 - (100 - 60) = 40
    The patient is WAITING and wait_s must grow as simulated time advances.
    """
    config = EngineConfig(
        capacities={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, {ResourceType.BED: 1, ResourceType.DOCTOR: 1}, service_time=100)
    scripted = [(40, "fail", (1, 600))]
    eng = Engine(config, [p], fifo_strategy, seed=42, scripted=scripted)

    eng.step()   # t=0: allocate; remaining_service=100
    eng.step()   # t=40: P-FAIL; remaining_service=60

    assert p.status == "WAITING"
    assert p.remaining_service == 60

    # Compute wait_s at t=40 and t=80 via the PatientView built by the engine
    pv_at_40 = eng._make_patient_view(p, now=40)
    pv_at_80 = eng._make_patient_view(p, now=80)

    # wait_s = now - arrival_time - (service_time - remaining_service)
    expected_at_40 = 40 - 0 - (100 - 60)   # = 0
    expected_at_80 = 80 - 0 - (100 - 60)   # = 40

    assert pv_at_40.wait_s == expected_at_40, (
        f"wait_s at t=40 should be {expected_at_40}, got {pv_at_40.wait_s}"
    )
    assert pv_at_80.wait_s == expected_at_80, (
        f"wait_s at t=80 should be {expected_at_80}, got {pv_at_80.wait_s}"
    )
