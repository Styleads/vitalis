"""
test_determinism.py
===================
The ENGINE_SPEC guarantees:

    same seed + same config + same scripted actions + same strategy
    => byte-identical event log

These tests verify that guarantee and only that guarantee.
snapshot() / stats_raw() determinism is NOT part of the core contract and is
kept in a clearly separated optional section at the bottom.
"""

from engine.types import ResourceType
from engine.config import EngineConfig
from engine.engine import Engine
from engine.arrivals import generate_arrivals
from tests.engine.conftest import fifo_strategy, make_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_to_completion(eng: Engine) -> list[dict]:
    """Step until the heap is empty; return the concatenated log."""
    all_logs: list[dict] = []
    while True:
        step_logs = eng.step()
        if not step_logs:        # empty list == heap exhausted, clock unchanged
            break
        all_logs.extend(step_logs)
    return all_logs


def _make_engine(config, seed: int, scripted: list) -> Engine:
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=3_600 * 4)
    return Engine(config, arrivals, fifo_strategy, seed=seed, scripted=scripted)


# ---------------------------------------------------------------------------
# Core contract: identical runs → identical event logs
# ---------------------------------------------------------------------------

def test_same_seed_produces_identical_event_log() -> None:
    """
    Core determinism guarantee from the spec:
    same seed + config + arrivals + strategy + scripted actions =>
    byte-identical event log.

    We run the engine twice from the same seed and assert the full,
    ordered list of log dicts is equal.
    """
    config = make_config(debug_invariants=False)
    seed = 42
    scripted = [
        (1_800, "surge",    (2.0, 1_800)),
        (3_600, "capacity", (ResourceType.DOCTOR, 1)),
        (5_400, "fail",     (1, 900)),
    ]

    logs_1 = _run_to_completion(_make_engine(config, seed, scripted))
    logs_2 = _run_to_completion(_make_engine(config, seed, scripted))

    assert logs_1, "Simulation must produce at least one log event"
    assert logs_1 == logs_2, (
        "Same seed + config + scripted actions must produce a byte-identical event log"
    )


def test_different_seeds_produce_different_event_logs() -> None:
    """
    A different seed must yield a different event log (different arrivals →
    different trace).  The assertion is on the event log, matching the spec
    guarantee.
    """
    config = make_config(debug_invariants=False)
    scripted: list = []

    logs_42 = _run_to_completion(_make_engine(config, 42, scripted))
    logs_43 = _run_to_completion(_make_engine(config, 43, scripted))

    assert logs_42 != logs_43, (
        "Different seeds must produce different event logs"
    )


def test_determinism_across_seeds_parametrised() -> None:
    """For every seed in the list, two identical runs yield identical logs."""
    config = make_config(debug_invariants=False)
    scripted = [(900, "surge", (1.5, 600))]

    for seed in [0, 7, 101, 2026]:
        logs_a = _run_to_completion(_make_engine(config, seed, scripted))
        logs_b = _run_to_completion(_make_engine(config, seed, scripted))
        assert logs_a == logs_b, f"Non-determinism detected for seed={seed}"


# ---------------------------------------------------------------------------
# Optional: scripted vs scripted with different actions differ
# ---------------------------------------------------------------------------

def test_different_scripted_actions_produce_different_logs() -> None:
    """
    Changing the scripted actions (while keeping the seed and config fixed)
    must alter the event log.
    """
    config = make_config(debug_invariants=False)
    seed = 55

    scripted_a = [(1_800, "surge", (2.0, 600))]
    scripted_b = [(1_800, "surge", (3.0, 600))]   # higher multiplier → more arrivals

    logs_a = _run_to_completion(_make_engine(config, seed, scripted_a))
    logs_b = _run_to_completion(_make_engine(config, seed, scripted_b))

    assert logs_a != logs_b, (
        "Different scripted actions must produce different event logs"
    )
