"""
engine/arrivals.py
==================
Patient generation — spec §4 (data model) and §12 (public interface).

make_patient  — sample one Patient from the seeded RNG and EngineConfig.
generate_arrivals — Poisson arrival stream for [0, horizon_s), sorted by
                    (arrival_time, id), ids sequential from 1.

Randomness contract: every call to the RNG is routed through the
random.Random instance that was seeded at construction time.
The global `random` module is never imported or used.
"""

from __future__ import annotations

import random as _random_stdlib
from typing import TYPE_CHECKING

from engine.types import Patient, ResourceType
from engine.config import EngineConfig

if TYPE_CHECKING:
    pass


def make_patient(
    rng: _random_stdlib.Random,
    patient_id: int,
    t: int,
    config: EngineConfig,
) -> Patient:
    """
    Sample a single Patient that arrives at simulated time t.

    Steps (order determines which RNG calls are made, so do not reorder):
      1. Sample urgency using config.urgency_mix as a cumulative CDF.
         Keys are iterated in ascending sorted order so the draw is stable
         regardless of dict insertion order.
      2. Copy config.bundles[urgency] as the base required bundle.
      3. Optionally add OR (ResourceType.OR += 1) with probability
         config.or_probability[urgency].
      4. Sample service_time from Exponential(1/mean) around
         config.mean_service_s[urgency], rounded to int, clamped to >= 1.

    Why make_patient is separate: surge handlers generate individual patients
    on demand; the same sampling logic must be reused without duplicating code.
    """
    # Step 1: sample urgency from the CDF.
    # Sort keys ascending so the draw is deterministic regardless of dict order.
    u = rng.random()
    cumulative = 0.0
    urgency = max(config.urgency_mix.keys())   # fallback to highest urgency
    for level in sorted(config.urgency_mix.keys()):
        cumulative += config.urgency_mix[level]
        if u < cumulative:
            urgency = level
            break

    # Step 2: copy the base bundle for this urgency.
    required: dict[ResourceType, int] = dict(config.bundles[urgency])

    # Step 3: probabilistically add OR.
    or_prob = config.or_probability.get(urgency, 0.0)
    if or_prob > 0.0 and rng.random() < or_prob:
        required[ResourceType.OR] = required.get(ResourceType.OR, 0) + 1

    # Step 4: sample service_time from Exp(1/mean), rounded to int seconds.
    mean_s = config.mean_service_s[urgency]
    service_time = max(1, int(round(rng.expovariate(1.0 / mean_s))))

    return Patient(
        id=patient_id,
        arrival_time=t,
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


def generate_arrivals(
    seed: int,
    config: EngineConfig,
    horizon_s: int,
) -> list[Patient]:
    """
    Generate a Poisson arrival stream for [0, horizon_s).

    Inter-arrival times are Exponential(base_arrival_rate / 3600) in seconds,
    i.e. the rate is in patients/hour and we convert to per-second here.
    Arrival times are truncated (floor) to int seconds; service times are
    rounded to int seconds.  Patient ids start at 1 and are assigned in
    arrival order before the final sort.

    The sort by (arrival_time, id) is technically redundant for a Poisson
    process (arrivals are already time-ordered) but is required by the spec
    so that any caller can rely on the ordering guarantee.

    All randomness goes through random.Random(seed); the global random module
    is never touched.
    """
    rng = _random_stdlib.Random(seed)
    rate_per_second = config.base_arrival_rate / 3600.0

    patients: list[Patient] = []
    t_float = 0.0
    patient_id = 1

    while True:
        # Draw next inter-arrival gap (seconds, continuous).
        inter = rng.expovariate(rate_per_second)
        t_float += inter
        if t_float >= horizon_s:
            break
        arrival_time = int(t_float)   # floor to int seconds
        p = make_patient(rng, patient_id, arrival_time, config)
        patients.append(p)
        patient_id += 1

    # Spec: sorted by (arrival_time, id).
    patients.sort(key=lambda p: (p.arrival_time, p.id))
    return patients
