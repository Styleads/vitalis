"""
test_hooks.py
=============
Tests for the two AI hook points (spec §10):
  - triage_fn: applied once at ARRIVAL; may change urgency 1..5.
  - los_fn:    applied once at ARRIVAL; sets predicted_service_time only.

Error-handling spec:
  - If a hook raises or returns an invalid value → log HOOK_ERROR, keep
    the generator's value, and continue.
  - The engine must never crash because of a hook.
"""

from engine.types import ResourceType, Patient
from engine.config import EngineConfig
from engine.engine import Engine
from tests.engine.conftest import fifo_strategy


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _small_config() -> EngineConfig:
    return EngineConfig(
        capacities={
            ResourceType.BED: 2,
            ResourceType.DOCTOR: 2,
            ResourceType.ICU_BED: 0,
            ResourceType.OR: 0,
            ResourceType.NURSE: 0,
            ResourceType.AMBULANCE: 0,
        },
        bundles={
            1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
            3: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
            4: {ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.0, 3: 0.0, 4: 0.0},
        mean_service_s={1: 100, 3: 100, 4: 100},
        urgency_mix={1: 0.5, 3: 0.3, 4: 0.2},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )


def _patient_arriving_at_0(pid: int = 1, urgency: int = 4, service_time: int = 120) -> Patient:
    return Patient(
        id=pid,
        arrival_time=0,
        urgency=urgency,
        required={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        service_time=service_time,
        remaining_service=service_time,
        predicted_service_time=None,
        arrival_mode="WALK_IN",
        department="general",
        features={"spo2": 88, "pain": 7},
        status="WAITING",
        start_time=None,
        end_time=None,
        assigned=[],
        interruptions=0,
        segment_start=None,
        token=0,
    )


# ---------------------------------------------------------------------------
# Default hooks (None)
# ---------------------------------------------------------------------------

def test_no_triage_fn_preserves_urgency() -> None:
    """Default triage_fn=None: patient urgency must not be changed at ARRIVAL."""
    config = _small_config()
    p = _patient_arriving_at_0(urgency=4)
    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=None, los_fn=None)
    eng.step()
    assert p.urgency == 4, "Default triage (None) must preserve the generator's urgency"


def test_no_los_fn_leaves_predicted_service_time_none() -> None:
    """Default los_fn=None: predicted_service_time must remain None."""
    config = _small_config()
    p = _patient_arriving_at_0()
    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=None, los_fn=None)
    eng.step()
    assert p.predicted_service_time is None, \
        "Default los_fn (None) must leave predicted_service_time as None"


# ---------------------------------------------------------------------------
# Custom hook overrides
# ---------------------------------------------------------------------------

def test_triage_fn_overrides_urgency() -> None:
    """A custom triage_fn that returns a valid urgency 1..5 must take effect."""
    config = _small_config()
    p = _patient_arriving_at_0(urgency=4)     # generator gives urgency 4

    def escalate(_pat):
        # Always escalate to urgency 1 based on feature data
        return 1

    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=escalate, los_fn=None)
    eng.step()
    assert p.urgency == 1, "triage_fn result must override the generator's urgency"


def test_los_fn_sets_predicted_service_time_without_altering_service_time() -> None:
    """
    Custom los_fn must populate predicted_service_time (a hint for strategies).
    It must NEVER change the simulation truth service_time.
    """
    config = _small_config()
    p = _patient_arriving_at_0(service_time=120)
    original_service_time = p.service_time    # 120

    def predict_300(_pat):
        return 300

    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=None, los_fn=predict_300)
    eng.step()
    assert p.predicted_service_time == 300, \
        "los_fn result must set predicted_service_time"
    assert p.service_time == original_service_time, \
        "los_fn must NEVER change the simulation truth service_time"


def test_triage_and_los_applied_exactly_once_at_arrival() -> None:
    """Both hooks are applied exactly once, at ARRIVAL — not again later."""
    config = _small_config()
    p = _patient_arriving_at_0(urgency=3, service_time=100)

    triage_calls = 0
    los_calls = 0

    def counting_triage(pat):
        nonlocal triage_calls
        triage_calls += 1
        return 2   # escalate

    def counting_los(pat):
        nonlocal los_calls
        los_calls += 1
        return 200

    eng = Engine(config, [p], fifo_strategy, seed=42,
                 triage_fn=counting_triage, los_fn=counting_los)

    # Step multiple times to ensure hooks aren't called more than once
    for _ in range(5):
        eng.step()

    assert triage_calls == 1, f"triage_fn must be called exactly once; called {triage_calls} times"
    assert los_calls == 1,    f"los_fn must be called exactly once; called {los_calls} times"


# ---------------------------------------------------------------------------
# Error-handling: raising hooks
# ---------------------------------------------------------------------------

def test_raising_triage_fn_logs_hook_error_and_keeps_default() -> None:
    """
    Spec §10: 'If a hook raises ... the engine logs HOOK_ERROR, keeps the
    generator's value, and continues.'
    """
    config = _small_config()
    p = _patient_arriving_at_0(urgency=3)

    def bad_triage(_pat):
        raise RuntimeError("triage model crashed")

    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=bad_triage)
    step_logs = eng.step()   # must not raise

    hook_errors = [lg for lg in step_logs if lg.get("type") == "HOOK_ERROR"]
    assert len(hook_errors) >= 1, "HOOK_ERROR must be logged when triage_fn raises"
    assert p.urgency == 3, "Generator's urgency must be preserved on hook error"


def test_raising_los_fn_logs_hook_error_and_keeps_none() -> None:
    """los_fn raising an exception must log HOOK_ERROR; predicted_service_time stays None."""
    config = _small_config()
    p = _patient_arriving_at_0()

    def bad_los(_pat):
        raise ValueError("LOS model unavailable")

    eng = Engine(config, [p], fifo_strategy, seed=42, los_fn=bad_los)
    step_logs = eng.step()   # must not raise

    hook_errors = [lg for lg in step_logs if lg.get("type") == "HOOK_ERROR"]
    assert len(hook_errors) >= 1, "HOOK_ERROR must be logged when los_fn raises"
    assert p.predicted_service_time is None, \
        "predicted_service_time must remain None when los_fn raises"


def test_invalid_triage_urgency_logs_hook_error_and_keeps_default() -> None:
    """
    Spec §10: 'returns an invalid value' → log HOOK_ERROR, keep generator's value.
    Invalid values: outside 1..5 range.
    """
    config = _small_config()
    p = _patient_arriving_at_0(urgency=4)

    def invalid_triage(_pat):
        return 99   # out of range

    eng = Engine(config, [p], fifo_strategy, seed=42, triage_fn=invalid_triage)
    step_logs = eng.step()

    hook_errors = [lg for lg in step_logs if lg.get("type") == "HOOK_ERROR"]
    assert len(hook_errors) >= 1, "HOOK_ERROR must be logged for invalid triage urgency"
    assert p.urgency == 4, "Generator's urgency must be kept on invalid triage result"


def test_invalid_los_value_logs_hook_error() -> None:
    """A negative LOS prediction is invalid; HOOK_ERROR must be logged."""
    config = _small_config()
    p = _patient_arriving_at_0()

    def negative_los(_pat):
        return -50

    eng = Engine(config, [p], fifo_strategy, seed=42, los_fn=negative_los)
    step_logs = eng.step()

    hook_errors = [lg for lg in step_logs if lg.get("type") == "HOOK_ERROR"]
    assert len(hook_errors) >= 1, "HOOK_ERROR must be logged for negative LOS prediction"


def test_engine_continues_after_hook_error() -> None:
    """The engine must remain fully operational after a hook error on one patient."""
    config = _small_config()
    p1 = _patient_arriving_at_0(pid=1, urgency=4)
    p2 = Patient(
        id=2, arrival_time=0, urgency=3,
        required={ResourceType.BED: 1, ResourceType.DOCTOR: 1},
        service_time=100, remaining_service=100, predicted_service_time=None,
        arrival_mode="WALK_IN", department="general", features={},
        status="WAITING", start_time=None, end_time=None, assigned=[],
        interruptions=0, segment_start=None, token=0,
    )

    def bad_triage(pat):
        if pat.id == 1:
            raise RuntimeError("only p1 breaks")
        return pat.urgency

    eng = Engine(config, [p1, p2], fifo_strategy, seed=42, triage_fn=bad_triage)
    step_logs = eng.step()   # must not raise; p2 should be processed normally

    hook_errors = [lg for lg in step_logs if lg.get("type") == "HOOK_ERROR"]
    assert len(hook_errors) >= 1
    # p2's urgency must be unchanged (hook only fails for p1)
    assert p2.urgency == 3
