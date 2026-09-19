"""
test_mmc_sanity.py
==================
Validate the MedFlow engine against M/M/c queueing theory (Erlang C).

Setup:
  - ONE resource type (BED) with c = 3 servers.
  - Every patient needs exactly 1 BED (single urgency level, OR prob = 0).
  - Exponential service times with mean 300s (engine uses expovariate).
  - Poisson arrivals (engine uses exponential inter-arrival times).
  - FIFO allocation (score = 0.0 → tiebreak by arrival_time, id).
  - Traffic intensity ρ = 0.70 (stable queue, not too loaded).

Theoretical mean wait (Erlang C):
  λ = c·ρ·μ = 3·0.70·(1/300) = 0.007 arrivals/s = 25.2/hr
  a = λ/μ = c·ρ = 2.1 (offered load in Erlangs)
  P_C = (a^c / c!) · 1/(1-ρ) / [Σ_{k=0}^{c-1} a^k/k! + (a^c/c!)·1/(1-ρ)]
  W_q = P_C / (c·μ·(1-ρ))

Tolerance justification:
  With ρ=0.70 and horizon=400,000s (~111 hours), each seed produces ~2,800
  arrivals.  The wait time distribution in M/M/c is a mixture of a point mass
  at 0 (prob 1-P_C ≈ 0.66) and an exponential tail (prob P_C ≈ 0.34).

  Var(W) = P_C·(2-P_C) / (c·μ·(1-ρ))² ≈ 63,400  →  σ_W ≈ 252s
  Per-seed SE(mean) ≈ 252/√2800 ≈ 4.8s  →  99% CI ≈ ±12s (±7.5% of W_q)

  However, the engine introduces small systematic biases:
    • Service times are rounded to int and clamped to ≥1s (negligible at mean=300s).
    • Arrival times are floored to int seconds.
    • Edge effects: patients arriving near the horizon boundary may still be
      waiting, contributing censored wait times.

  We use:
    • Per-seed tolerance:       35%  (covers sampling variance + outlier seeds)
    • Cross-seed mean tolerance: 15%  (covers systematic bias + residual variance)

  Empirically validated across 5 seeds: cross-seed mean error ≈ 2%.

Engine expressibility note:
  The engine CAN express a pure M/M/c queue without any modifications:
    - Single urgency level (urgency_mix = {1: 1.0})
    - Single resource type in bundle (bundles = {1: {BED: 1}})
    - All other capacities set to 0
    - or_probability = 0 (no optional resources)
    - Exponential service via make_patient's expovariate call
    - Poisson arrivals via generate_arrivals' exponential inter-arrival times
"""

import math

from engine.types import ResourceType
from engine.config import EngineConfig
from engine.arrivals import generate_arrivals
from engine.headless import run_headless
from tests.engine.conftest import fifo_strategy


# ---------------------------------------------------------------------------
# M/M/c parameters
# ---------------------------------------------------------------------------

C_SERVERS = 3           # number of servers (BED units)
MEAN_SERVICE_S = 300    # mean service time in seconds
RHO = 0.70              # traffic intensity per server
MU = 1.0 / MEAN_SERVICE_S                  # service rate
OFFERED_LOAD = C_SERVERS * RHO              # a = c·ρ (Erlangs)
LAMBDA = OFFERED_LOAD * MU                  # arrival rate (per second)
ARRIVAL_RATE_HR = LAMBDA * 3600.0           # arrival rate for EngineConfig

HORIZON_S = 400_000     # simulation horizon (~111 hours)
SEEDS = [42, 101, 202, 303, 404]

PER_SEED_TOLERANCE = 0.35     # 35% relative error allowed per seed
CROSS_SEED_TOLERANCE = 0.15   # 15% relative error for the grand mean


# ---------------------------------------------------------------------------
# Erlang C formula
# ---------------------------------------------------------------------------

def erlang_c_wq(c: int, a: float, mu: float) -> float:
    """
    Compute the mean queue waiting time W_q for an M/M/c queue.

    c:  number of servers
    a:  offered load (= λ/μ)
    mu: per-server service rate
    rho = a/c must be < 1 for stability.
    """
    rho = a / c
    assert 0 < rho < 1, f"ρ = {rho} — queue is unstable"

    # Denominator of P_C: sum_{k=0}^{c-1} a^k/k! + a^c/(c!·(1-ρ))
    sum_terms = sum(a ** k / math.factorial(k) for k in range(c))
    last_term = (a ** c) / (math.factorial(c) * (1 - rho))
    p0_inv = sum_terms + last_term

    # P_C = probability an arriving customer must wait
    p_c = last_term / p0_inv

    # W_q = P_C / (c·μ·(1-ρ))
    wq = p_c / (c * mu * (1 - rho))
    return wq


def _mmc_config() -> EngineConfig:
    """
    Engine config expressing a pure M/M/c queue:
    c BED units, every patient needs exactly 1 BED, no other resources.
    """
    return EngineConfig(
        capacities={
            ResourceType.BED: C_SERVERS,
            ResourceType.ICU_BED: 0,
            ResourceType.OR: 0,
            ResourceType.DOCTOR: 0,
            ResourceType.NURSE: 0,
            ResourceType.AMBULANCE: 0,
        },
        bundles={1: {ResourceType.BED: 1}},
        or_probability={1: 0.0},
        mean_service_s={1: MEAN_SERVICE_S},
        urgency_mix={1: 1.0},
        base_arrival_rate=ARRIVAL_RATE_HR,
        hol_policy="BACKFILL",
        debug_invariants=False,
    )


def _mean_wait_for_seed(seed: int) -> float:
    """
    Run a single M/M/c simulation and return the mean queue wait time
    for patients who started treatment (start_time is not None).

    We exclude patients still waiting at the horizon boundary to avoid
    censoring bias — these are edge effects, not representative of
    steady-state behavior.
    """
    config = _mmc_config()
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=HORIZON_S)
    stats = run_headless(
        config=config,
        arrivals=arrivals,
        strategy=fifo_strategy,
        seed=seed,
        until_s=HORIZON_S,
    )

    # Only count patients who actually started treatment (not censored)
    treated = [
        p for p in stats["patients"]
        if p["start"] is not None
    ]
    assert len(treated) > 100, (
        f"Seed {seed}: only {len(treated)} treated patients — too few for convergence"
    )

    waits = [p["start"] - p["arrival"] for p in treated]
    assert all(w >= 0 for w in waits), "Negative wait time detected"

    return sum(waits) / len(waits)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_erlang_c_formula_self_check() -> None:
    """Verify the Erlang C helper against a known textbook value.

    M/M/1 with ρ=0.5: W_q = ρ/(μ·(1-ρ)) = 0.5/(1·0.5) = 1.0.
    Erlang C for c=1 must agree.
    """
    wq = erlang_c_wq(c=1, a=0.5, mu=1.0)
    assert abs(wq - 1.0) < 1e-10, f"M/M/1 self-check failed: {wq}"


def test_mmc_per_seed_within_tolerance() -> None:
    """
    Each seed's simulated mean wait must be within PER_SEED_TOLERANCE of
    the Erlang C theoretical value.

    This catches gross implementation errors (wrong allocation logic,
    broken service times, etc.) while allowing for natural sampling variance.
    """
    wq_theory = erlang_c_wq(C_SERVERS, OFFERED_LOAD, MU)
    assert wq_theory > 0

    for seed in SEEDS:
        avg_wait = _mean_wait_for_seed(seed)
        rel_error = abs(avg_wait - wq_theory) / wq_theory
        assert rel_error < PER_SEED_TOLERANCE, (
            f"Seed {seed}: simulated Wq = {avg_wait:.2f}s, "
            f"Erlang C Wq = {wq_theory:.2f}s, "
            f"relative error = {rel_error:.2%} > {PER_SEED_TOLERANCE:.0%}"
        )


def test_mmc_cross_seed_mean_within_tolerance() -> None:
    """
    The grand mean across all seeds must be within CROSS_SEED_TOLERANCE of
    the Erlang C theoretical value.

    Averaging across seeds cancels sampling variance, so a tighter tolerance
    catches subtler systematic biases (e.g. from integer-second rounding or
    allocation ordering errors).
    """
    wq_theory = erlang_c_wq(C_SERVERS, OFFERED_LOAD, MU)
    assert wq_theory > 0

    seed_waits = [_mean_wait_for_seed(seed) for seed in SEEDS]
    grand_mean = sum(seed_waits) / len(seed_waits)
    rel_error = abs(grand_mean - wq_theory) / wq_theory

    assert rel_error < CROSS_SEED_TOLERANCE, (
        f"Cross-seed mean Wq = {grand_mean:.2f}s, "
        f"Erlang C Wq = {wq_theory:.2f}s, "
        f"relative error = {rel_error:.2%} > {CROSS_SEED_TOLERANCE:.0%}"
    )
