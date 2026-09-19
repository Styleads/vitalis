"""
test_arrivals.py
================
Tests for engine/arrivals.py: make_patient and generate_arrivals.

All expected values are derivable by hand or from simple arithmetic.
Tests are written from the spec, not from the implementation.
"""

from __future__ import annotations

import math

import pytest

from engine.types import ResourceType, Patient
from engine.config import EngineConfig
from engine.arrivals import generate_arrivals, make_patient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _config(
    *,
    rate: float = 10.0,
    or_prob: float = 0.0,
    mean_service_s: int = 100,
) -> EngineConfig:
    """Single-urgency config for deterministic hand-verification."""
    return EngineConfig(
        capacities={
            ResourceType.BED: 5,
            ResourceType.DOCTOR: 5,
            ResourceType.ICU_BED: 0,
            ResourceType.OR: 2,
            ResourceType.NURSE: 0,
            ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: or_prob},
        mean_service_s={1: mean_service_s},
        urgency_mix={1: 1.0},
        base_arrival_rate=rate,
        hol_policy="BACKFILL",
        debug_invariants=False,
    )


def _multi_urgency_config() -> EngineConfig:
    """Multi-urgency config matching spec §4 placeholders."""
    return EngineConfig(
        capacities={
            ResourceType.BED: 10,
            ResourceType.ICU_BED: 2,
            ResourceType.OR: 1,
            ResourceType.DOCTOR: 5,
            ResourceType.NURSE: 8,
            ResourceType.AMBULANCE: 1,
        },
        bundles={
            1: {ResourceType.ICU_BED: 1, ResourceType.DOCTOR: 1, ResourceType.NURSE: 2},
            2: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            3: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1, ResourceType.NURSE: 1},
            4: {ResourceType.BED: 1,     ResourceType.DOCTOR: 1},
            5: {ResourceType.DOCTOR: 1},
        },
        or_probability={1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
        mean_service_s={1: 14400, 2: 10800, 3: 7200, 4: 3600, 5: 1200},
        urgency_mix={1: 0.05, 2: 0.15, 3: 0.30, 4: 0.30, 5: 0.20},
        base_arrival_rate=10.0,
        hol_policy="BACKFILL",
        debug_invariants=False,
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_same_seed_produces_identical_arrivals() -> None:
    """Spec core guarantee: same seed => identical output."""
    config = _config()
    a1 = generate_arrivals(seed=42, config=config, horizon_s=7200)
    a2 = generate_arrivals(seed=42, config=config, horizon_s=7200)
    assert len(a1) == len(a2)
    for p1, p2 in zip(a1, a2):
        assert p1.id            == p2.id
        assert p1.arrival_time  == p2.arrival_time
        assert p1.urgency       == p2.urgency
        assert p1.service_time  == p2.service_time
        assert p1.required      == p2.required


def test_different_seeds_produce_different_arrivals() -> None:
    """Different seeds must yield different sequences (with overwhelming probability)."""
    config = _config(rate=60.0)
    a42 = generate_arrivals(seed=42, config=config, horizon_s=3600)
    a43 = generate_arrivals(seed=43, config=config, horizon_s=3600)
    times_42 = [p.arrival_time for p in a42]
    times_43 = [p.arrival_time for p in a43]
    assert times_42 != times_43, "Different seeds must produce different arrival times"


def test_determinism_across_multiple_seeds() -> None:
    config = _multi_urgency_config()
    for seed in [0, 7, 101, 9999]:
        r1 = generate_arrivals(seed=seed, config=config, horizon_s=3600)
        r2 = generate_arrivals(seed=seed, config=config, horizon_s=3600)
        ids_1 = [(p.id, p.arrival_time) for p in r1]
        ids_2 = [(p.id, p.arrival_time) for p in r2]
        assert ids_1 == ids_2, f"Non-determinism for seed={seed}"


# ---------------------------------------------------------------------------
# Sequential ids
# ---------------------------------------------------------------------------

def test_patient_ids_are_sequential_from_one() -> None:
    """Patient ids start at 1 and increment by 1 in arrival order."""
    config = _config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    assert len(arrivals) > 0
    for expected_id, p in enumerate(arrivals, start=1):
        assert p.id == expected_id, (
            f"Patient at index {expected_id-1} has id={p.id}, expected {expected_id}"
        )


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def test_arrivals_sorted_by_arrival_time_then_id() -> None:
    """Spec: generate_arrivals returns patients sorted by (arrival_time, id)."""
    config = _config(rate=120.0)   # high rate → many arrivals, possible ties
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    keys = [(p.arrival_time, p.id) for p in arrivals]
    assert keys == sorted(keys), "Arrivals must be sorted by (arrival_time, id)"


def test_all_arrival_times_within_horizon() -> None:
    """No patient arrives at or after horizon_s."""
    horizon = 7200
    config = _config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=horizon)
    for p in arrivals:
        assert 0 <= p.arrival_time < horizon, (
            f"Patient {p.id} arrival_time={p.arrival_time} is outside [0, {horizon})"
        )


# ---------------------------------------------------------------------------
# Int-second times and service times
# ---------------------------------------------------------------------------

def test_arrival_times_are_ints() -> None:
    """Spec §3: time is an int in seconds."""
    config = _config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    for p in arrivals:
        assert isinstance(p.arrival_time, int), (
            f"arrival_time must be int, got {type(p.arrival_time)}"
        )


def test_service_times_are_positive_ints() -> None:
    """Service times must be int seconds >= 1."""
    config = _config(mean_service_s=100)
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=7200)
    for p in arrivals:
        assert isinstance(p.service_time, int), "service_time must be int"
        assert p.service_time >= 1, "service_time must be >= 1 second"


def test_remaining_service_equals_service_time_on_arrival() -> None:
    """At arrival, remaining_service must equal service_time (patient has not been treated)."""
    config = _config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    for p in arrivals:
        assert p.remaining_service == p.service_time, (
            f"Patient {p.id}: remaining_service={p.remaining_service} != "
            f"service_time={p.service_time}"
        )


# ---------------------------------------------------------------------------
# Mean arrival rate (statistical)
# ---------------------------------------------------------------------------

def test_mean_arrival_rate_within_tolerance() -> None:
    """
    Over a 24-hour horizon, the observed rate must be within ±15% of the
    configured rate.

    Tolerance reasoning: Poisson(n) has std dev sqrt(n).  For rate=10/hr,
    24h expected count = 240, std dev ≈ 15.5, so ±37 (±15%) gives > 5-sigma
    coverage; any single fixed seed in this range is overwhelmingly likely.
    """
    rate = 10.0      # patients/hour
    horizon = 86400  # 24 h
    config = _config(rate=rate)

    arrivals = generate_arrivals(seed=42, config=config, horizon_s=horizon)
    count = len(arrivals)
    expected = rate * (horizon / 3600)
    tolerance = 0.15   # ±15%

    assert expected * (1 - tolerance) <= count <= expected * (1 + tolerance), (
        f"Arrival count {count} is outside ±15% of expected {expected:.0f} "
        f"(rate={rate}/hr, horizon={horizon}s)"
    )


def test_mean_rate_at_higher_arrival_rate() -> None:
    """Rate=60/hr over 10 hours: expected 600, tolerance ±10%."""
    rate = 60.0
    horizon = 36000   # 10 h
    config = _config(rate=rate)
    arrivals = generate_arrivals(seed=101, config=config, horizon_s=horizon)
    count = len(arrivals)
    expected = rate * (horizon / 3600)
    tolerance = 0.10
    assert expected * (1 - tolerance) <= count <= expected * (1 + tolerance), (
        f"Arrival count {count} outside ±10% of expected {expected:.0f}"
    )


# ---------------------------------------------------------------------------
# Patient field defaults
# ---------------------------------------------------------------------------

def test_patient_defaults_on_arrival() -> None:
    """Freshly generated patients must have the expected default field values."""
    config = _config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    assert len(arrivals) > 0
    for p in arrivals:
        assert p.status             == "WAITING"
        assert p.start_time         is None
        assert p.end_time           is None
        assert p.assigned           == []
        assert p.interruptions      == 0
        assert p.segment_start      is None
        assert p.token              == 0
        assert p.predicted_service_time is None
        assert p.department         == "general"
        assert p.arrival_mode       == "WALK_IN"


# ---------------------------------------------------------------------------
# Urgency distribution
# ---------------------------------------------------------------------------

def test_urgency_values_in_valid_range() -> None:
    """All generated urgency values must be in 1..5."""
    config = _multi_urgency_config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=7200)
    for p in arrivals:
        assert 1 <= p.urgency <= 5, f"Invalid urgency {p.urgency} for patient {p.id}"


def test_urgency_mix_roughly_correct() -> None:
    """
    Over a long horizon, the fraction of patients at each urgency level should
    be within ±7 percentage points of the configured mix.

    This uses a wide tolerance because we fix a single seed; the test is only
    checking gross misconfiguration, not exact statistics.
    """
    config = _multi_urgency_config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=86400)
    total = len(arrivals)
    assert total > 200, "Need enough patients for meaningful statistics"

    counts = {lvl: 0 for lvl in config.urgency_mix}
    for p in arrivals:
        counts[p.urgency] += 1

    tolerance = 0.07   # ±7 percentage points
    for lvl, expected_frac in config.urgency_mix.items():
        observed_frac = counts[lvl] / total
        assert abs(observed_frac - expected_frac) <= tolerance, (
            f"Urgency {lvl}: observed {observed_frac:.3f}, expected {expected_frac:.3f}, "
            f"tolerance ±{tolerance}"
        )


# ---------------------------------------------------------------------------
# Bundle correctness
# ---------------------------------------------------------------------------

def test_bundle_matches_config_for_urgency() -> None:
    """Each patient's required bundle must equal config.bundles[urgency] (possibly + OR)."""
    config = _multi_urgency_config()
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    for p in arrivals:
        base = config.bundles[p.urgency]
        # required must contain at least the base bundle
        for rtype, count in base.items():
            assert p.required.get(rtype, 0) >= count, (
                f"Patient {p.id} urgency={p.urgency}: "
                f"required[{rtype}]={p.required.get(rtype, 0)} < base {count}"
            )
        # Any extra must only be OR (from or_probability)
        for rtype, count in p.required.items():
            if rtype not in base:
                assert rtype == ResourceType.OR, (
                    f"Patient {p.id} has unexpected resource {rtype} not in base bundle"
                )


def test_or_never_added_when_probability_zero() -> None:
    """When or_probability is 0 for all urgencies, no patient should have OR in bundle."""
    config = _multi_urgency_config()   # or_probability all 0.0
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=7200)
    for p in arrivals:
        assert ResourceType.OR not in p.required, (
            f"Patient {p.id} got OR in bundle despite or_probability=0"
        )


def test_or_sometimes_added_when_probability_nonzero() -> None:
    """When or_probability > 0, some patients should have OR added over a long run."""
    config = EngineConfig(
        capacities={
            ResourceType.BED: 5, ResourceType.DOCTOR: 5,
            ResourceType.OR: 3,
            ResourceType.ICU_BED: 0, ResourceType.NURSE: 0, ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.5},   # 50% chance → should appear frequently
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=60.0,
        hol_policy="BACKFILL",
        debug_invariants=False,
    )
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=3600)
    or_count = sum(1 for p in arrivals if ResourceType.OR in p.required)
    assert or_count > 0, "Expected some patients to have OR added when or_probability=0.5"


# ---------------------------------------------------------------------------
# Empty horizon
# ---------------------------------------------------------------------------

def test_zero_horizon_returns_empty_list() -> None:
    """horizon_s=0 means no arrivals are possible."""
    config = _config(rate=100.0)
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=0)
    assert arrivals == []


def test_very_short_horizon_may_return_empty() -> None:
    """A horizon of 1 second with a low rate almost certainly yields 0 arrivals."""
    config = _config(rate=1.0)   # 1 patient/hour → ~0.00028 per second
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=1)
    # Either 0 or 1 is fine; just confirm no crash and times are in-range.
    for p in arrivals:
        assert 0 <= p.arrival_time < 1
