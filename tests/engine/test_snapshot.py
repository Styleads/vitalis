"""
test_snapshot.py
================
Tests for Engine.snapshot():
  1. json.dumps(snapshot()) succeeds (all values are JSON-safe primitives).
  2. Mutating the returned dict does not change engine-internal state.
  3. snapshot().queue order matches the sort key (-score, arrival_time, id)
     the next allocation pass would use.

Expected values are computable by hand from the tiny fixture configs.
"""

import json

from engine.types import ResourceType, Patient
from engine.config import EngineConfig
from engine.engine import Engine
from tests.engine.conftest import fifo_strategy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patient(pid: int, arrival: int, urgency: int, required: dict,
             service_time: int = 100) -> Patient:
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


def _no_capacity_config() -> EngineConfig:
    """Zero capacity so all patients stay WAITING — snapshot queue is easy to inspect."""
    return EngineConfig(
        capacities={
            ResourceType.BED: 0,
            ResourceType.DOCTOR: 0,
            ResourceType.ICU_BED: 0,
            ResourceType.OR: 0,
            ResourceType.NURSE: 0,
            ResourceType.AMBULANCE: 0,
        },
        bundles={
            1: {ResourceType.BED: 1},
            2: {ResourceType.BED: 1},
            3: {ResourceType.BED: 1},
        },
        or_probability={1: 0.0, 2: 0.0, 3: 0.0},
        mean_service_s={1: 100, 2: 100, 3: 100},
        urgency_mix={1: 0.33, 2: 0.33, 3: 0.34},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )


def _urgency_strategy(pv, sv, now: int) -> float:
    """Higher urgency (lower number) → higher score, so urgency 1 → score 5."""
    return float(6 - pv.urgency)


# ---------------------------------------------------------------------------
# 1. JSON serializability
# ---------------------------------------------------------------------------

def test_snapshot_json_serializable() -> None:
    """json.dumps(snapshot()) must succeed with no TypeError or ValueError."""
    config = EngineConfig(
        capacities={
            ResourceType.BED: 2,
            ResourceType.DOCTOR: 2,
            ResourceType.ICU_BED: 1,
            ResourceType.OR: 1,
            ResourceType.NURSE: 2,
            ResourceType.AMBULANCE: 1,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 120},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, 1, {ResourceType.BED: 1, ResourceType.DOCTOR: 1})
    eng = Engine(config, [p], fifo_strategy, seed=42)
    eng.step()

    snap = eng.snapshot()
    # Must not raise
    serialized = json.dumps(snap)
    parsed = json.loads(serialized)

    # Required top-level keys per spec §12
    for key in ("clock", "strategy_name", "hol_policy", "queue",
                 "in_treatment", "resources", "flags", "recent_events"):
        assert key in parsed, f"snapshot() must contain key '{key}'"

    assert parsed["hol_policy"] in ("BACKFILL", "BLOCK")
    assert isinstance(parsed["clock"], int)
    assert isinstance(parsed["flags"]["arrival_multiplier"], float)


def test_snapshot_contains_only_json_safe_primitives() -> None:
    """All leaf values in snapshot() must be dict, list, int, str, float, bool, or None."""
    config = EngineConfig(
        capacities={
            ResourceType.BED: 1, ResourceType.DOCTOR: 1,
            ResourceType.ICU_BED: 0, ResourceType.OR: 0,
            ResourceType.NURSE: 0, ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, 1, {ResourceType.BED: 1, ResourceType.DOCTOR: 1})
    eng = Engine(config, [p], fifo_strategy, seed=42)
    eng.step()

    def _check(val, path="snapshot"):
        if isinstance(val, dict):
            for k, v in val.items():
                _check(v, f"{path}.{k}")
        elif isinstance(val, list):
            for i, v in enumerate(val):
                _check(v, f"{path}[{i}]")
        else:
            assert isinstance(val, (int, float, str, bool, type(None))), (
                f"Non-JSON-safe value at {path}: {type(val)}"
            )

    _check(eng.snapshot())


# ---------------------------------------------------------------------------
# 2. Mutation isolation
# ---------------------------------------------------------------------------

def test_snapshot_mutation_does_not_affect_engine_state() -> None:
    """
    snapshot() must return deep copies.  Mutating the returned dict or its
    nested lists must not change any engine-internal state.
    """
    config = EngineConfig(
        capacities={
            ResourceType.BED: 2, ResourceType.DOCTOR: 2,
            ResourceType.ICU_BED: 0, ResourceType.OR: 0,
            ResourceType.NURSE: 0, ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 100},
        urgency_mix={1: 1.0},
        base_arrival_rate=1.0,
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    p = _patient(1, 0, 1, {ResourceType.BED: 1, ResourceType.DOCTOR: 1})
    eng = Engine(config, [p], fifo_strategy, seed=42)

    snap1 = eng.snapshot()
    original_clock = snap1["clock"]
    original_free = snap1["resources"][ResourceType.BED.value]["free"]

    # Aggressively mutate every mutable part of the snapshot
    snap1["clock"] = 99_999
    snap1["queue"].clear()
    snap1["in_treatment"].clear()
    snap1["recent_events"].append({"t": -1, "type": "FAKE"})
    snap1["flags"]["arrival_multiplier"] = 99.9
    for rtype_key in snap1["resources"]:
        snap1["resources"][rtype_key]["free"] = 999

    # The engine must be completely unaffected
    snap2 = eng.snapshot()
    assert snap2["clock"] == original_clock
    assert snap2["resources"][ResourceType.BED.value]["free"] == original_free
    assert snap2["flags"]["arrival_multiplier"] == 1.0


# ---------------------------------------------------------------------------
# 3. Queue order matches the next allocation pass
# ---------------------------------------------------------------------------

def test_snapshot_queue_order_matches_allocation_sort() -> None:
    """
    Spec §12 snapshot(): queue is 'in the order the next pass would sort'.
    Sort key: (-score, arrival_time, id).

    Three patients, all WAITING (0-capacity pool so none can be allocated):
      p1: urgency=3, arrival=10  → score 3.0 (via _urgency_strategy)
      p2: urgency=1, arrival=20  → score 5.0
      p3: urgency=2, arrival=5   → score 4.0

    Expected order: p2 (score 5), p3 (score 4), p1 (score 3).
    """
    config = _no_capacity_config()
    p1 = _patient(1, arrival=10, urgency=3, required={ResourceType.BED: 1})
    p2 = _patient(2, arrival=20, urgency=1, required={ResourceType.BED: 1})
    p3 = _patient(3, arrival=5,  urgency=2, required={ResourceType.BED: 1})

    eng = Engine(config, [p1, p2, p3], _urgency_strategy, seed=42)
    eng.step()   # process arrivals; all remain WAITING

    snap = eng.snapshot()
    queue_ids = [item["id"] for item in snap["queue"]]
    assert queue_ids == [2, 3, 1], (
        f"Expected queue order [2, 3, 1] by (-score, arrival_time, id), got {queue_ids}"
    )


def test_snapshot_queue_tiebreak_by_arrival_then_id() -> None:
    """
    When scores are equal (fifo_strategy → 0.0), sort by (arrival_time, id).
    p1: arrival=10, id=1  → second
    p2: arrival=5,  id=2  → first (earlier arrival)
    p3: arrival=10, id=3  → third (same arrival as p1 but higher id)
    """
    config = _no_capacity_config()
    p1 = _patient(1, arrival=10, urgency=1, required={ResourceType.BED: 1})
    p2 = _patient(2, arrival=5,  urgency=1, required={ResourceType.BED: 1})
    p3 = _patient(3, arrival=10, urgency=1, required={ResourceType.BED: 1})

    eng = Engine(config, [p1, p2, p3], fifo_strategy, seed=42)
    eng.step()

    snap = eng.snapshot()
    queue_ids = [item["id"] for item in snap["queue"]]
    assert queue_ids == [2, 1, 3], (
        f"Expected tiebreak order [2, 1, 3] by arrival_time then id, got {queue_ids}"
    )


def test_snapshot_recent_events_capped_at_50() -> None:
    """spec §12: snapshot() recent_events shows at most the last 50 log events."""
    config = EngineConfig(
        capacities={
            ResourceType.BED: 10, ResourceType.DOCTOR: 10,
            ResourceType.ICU_BED: 0, ResourceType.OR: 0,
            ResourceType.NURSE: 0, ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1, ResourceType.DOCTOR: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: 1},      # very short service → fast churn
        urgency_mix={1: 1.0},
        base_arrival_rate=60.0,     # high arrival rate → many events
        hol_policy="BACKFILL",
        debug_invariants=True,
    )
    from engine.arrivals import generate_arrivals
    arrivals = generate_arrivals(seed=42, config=config, horizon_s=300)
    eng = Engine(config, arrivals, fifo_strategy, seed=42)
    eng.run_until(300)

    snap = eng.snapshot()
    assert len(snap["recent_events"]) <= 50, (
        f"recent_events must be capped at 50; got {len(snap['recent_events'])}"
    )
