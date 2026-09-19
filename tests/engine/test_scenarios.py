"""
test_scenarios.py
=================
Tests for scripted vs live scenarios and run_headless.

1. Scripted and live surges with the same seed and parameters must generate
   identical arrival events (same patient ids, arrival_time, urgency, etc.).

2. run_headless() must deep-copy the arrivals list; the original is untouched.

All expected values are derivable from the spec (Part 2, §9, §12).
"""

import copy

from engine.types import ResourceType
from engine.config import EngineConfig
from engine.engine import Engine
from engine.arrivals import generate_arrivals
from engine.headless import run_headless
from tests.engine.conftest import fifo_strategy, make_config


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_and_collect_arrivals(eng: Engine) -> list[dict]:
    """Run simulation to completion; return only ARRIVAL log events."""
    arrival_logs: list[dict] = []
    while True:
        step_logs = eng.step()
        if not step_logs:
            break
        arrival_logs.extend(lg for lg in step_logs if lg.get("type") == "ARRIVAL")
    return arrival_logs


# ---------------------------------------------------------------------------
# 1. Scripted surge == live inject_surge (same arrivals)
# ---------------------------------------------------------------------------

def test_scripted_and_live_surges_produce_identical_arrivals() -> None:
    """
    Spec §9 scripted: 'Each is pushed to the heap at init as the same events
    the live hooks create, so scripted and live paths are identical code.'

    Run A: scripted surge at t=600 with multiplier=2.5, duration=1800.
    Run B: live inject_surge(2.5, 1800) called at t=600 then run_until(600).

    Both must produce the same ARRIVAL events (same patient ids, times, urgencies).
    """
    config = make_config(debug_invariants=False)
    seed = 77
    horizon_s = 3600 * 3
    surge_t = 600
    multiplier = 2.5
    duration = 1800

    # --- Run A: scripted ---
    arrivals_a = generate_arrivals(seed=seed, config=config, horizon_s=horizon_s)
    scripted = [(surge_t, "surge", (multiplier, duration))]
    eng_scripted = Engine(config, arrivals_a, fifo_strategy, seed=seed, scripted=scripted)
    surge_arrivals_scripted = _run_and_collect_arrivals(eng_scripted)

    # --- Run B: live inject_surge ---
    arrivals_b = generate_arrivals(seed=seed, config=config, horizon_s=horizon_s)
    eng_live = Engine(config, arrivals_b, fifo_strategy, seed=seed, scripted=[])
    # Advance to just before the surge timestamp
    eng_live.run_until(surge_t - 1)
    # Fire the live hook, then advance to surge_t to process it
    eng_live.inject_surge(multiplier, duration)
    # Collect all remaining arrivals after the surge fires
    eng_live.run_until(surge_t)
    surge_arrivals_live = _run_and_collect_arrivals(eng_live)

    # The surge-generated arrivals must be identical in both runs
    # Filter to only surge-period arrivals (t > surge_t, t <= surge_t + duration)
    def _surge_period(logs):
        return [
            lg for lg in logs
            if surge_t < lg["t"] <= surge_t + duration
        ]

    scripted_in_surge = _surge_period(surge_arrivals_scripted)
    live_in_surge     = _surge_period(surge_arrivals_live)

    assert scripted_in_surge == live_in_surge, (
        "Scripted and live surges with the same seed must produce identical ARRIVAL events"
    )


def test_scripted_and_live_surges_same_patient_count() -> None:
    """Extra sanity: surge arrivals count matches in both run modes."""
    config = make_config(base_arrival_rate=30.0, debug_invariants=False)
    seed = 12
    horizon_s = 7200
    scripted = [(1800, "surge", (3.0, 900))]

    arrivals_a = generate_arrivals(seed=seed, config=config, horizon_s=horizon_s)
    arrivals_b = generate_arrivals(seed=seed, config=config, horizon_s=horizon_s)

    eng_s = Engine(config, arrivals_a, fifo_strategy, seed=seed, scripted=scripted)
    eng_l = Engine(config, arrivals_b, fifo_strategy, seed=seed, scripted=[])

    all_a = _run_and_collect_arrivals(eng_s)
    eng_l.run_until(1799)
    eng_l.inject_surge(3.0, 900)
    eng_l.run_until(1800)
    all_l = _run_and_collect_arrivals(eng_l)

    def _surge_arrivals(logs, t_start, t_end):
        return [lg for lg in logs if t_start < lg["t"] <= t_end]

    count_s = len(_surge_arrivals(all_a, 1800, 2700))
    count_l = len(_surge_arrivals(all_l, 1800, 2700))
    assert count_s == count_l, (
        f"Surge arrival counts differ: scripted={count_s} vs live={count_l}"
    )


# ---------------------------------------------------------------------------
# 2. run_headless does not mutate the shared arrivals list
# ---------------------------------------------------------------------------

def test_run_headless_does_not_mutate_arrivals_list() -> None:
    """
    Spec §12: 'run_headless deep-copies arrivals so one arrival list can be
    reused across strategies.'

    After calling run_headless(), the original arrivals list must be identical
    to what it was before the call.
    """
    config = make_config(debug_invariants=False)
    seed = 33
    horizon_s = 3600

    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=horizon_s)
    # Record a deep snapshot of the arrivals list before the call
    arrivals_before = copy.deepcopy(arrivals)

    run_headless(
        config=config,
        arrivals=arrivals,
        strategy=fifo_strategy,
        seed=seed,
        until_s=horizon_s,
        scripted=[],
    )

    # Every patient object in the list must be identical
    assert len(arrivals) == len(arrivals_before), \
        "run_headless must not add or remove items from the arrivals list"
    for pat, orig in zip(arrivals, arrivals_before):
        assert pat.id           == orig.id
        assert pat.arrival_time == orig.arrival_time
        assert pat.urgency      == orig.urgency
        assert pat.service_time == orig.service_time
        assert pat.status       == orig.status, (
            f"Patient {pat.id} status mutated by run_headless: "
            f"{orig.status!r} → {pat.status!r}"
        )


def test_run_headless_returns_stats_raw_shape() -> None:
    """run_headless must return a dict matching the stats_raw() schema from spec §12."""
    config = make_config(debug_invariants=False)
    seed = 1
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=3600)

    result = run_headless(
        config=config,
        arrivals=arrivals,
        strategy=fifo_strategy,
        seed=seed,
        until_s=3600,
    )

    assert isinstance(result, dict), "run_headless must return a dict"
    for key in ("patients", "busy_s", "available_s", "counts"):
        assert key in result, f"stats_raw() must contain key '{key}'"

    counts = result["counts"]
    for k in ("arrived", "treated", "waiting", "in_treatment", "interrupted"):
        assert k in counts, f"stats_raw().counts must contain '{k}'"


def test_run_headless_reuse_arrivals_across_strategies() -> None:
    """
    The same arrivals list can be passed to multiple run_headless calls.
    Results may differ by strategy, but arrivals are never mutated.
    """
    config = make_config(debug_invariants=False)
    seed = 99
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=3600)
    arrivals_snapshot = copy.deepcopy(arrivals)

    def urgency_strategy(pv, sv, now):
        return float(6 - pv.urgency)

    for strat in [fifo_strategy, urgency_strategy]:
        run_headless(config=config, arrivals=arrivals, strategy=strat, seed=seed, until_s=3600)

    # Arrivals untouched after both runs
    assert len(arrivals) == len(arrivals_snapshot)
    for pat, orig in zip(arrivals, arrivals_snapshot):
        assert pat.id == orig.id
        assert pat.status == orig.status
