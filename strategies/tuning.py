"""MedFlow - Strategy Parameter Tuning and Sweep Harness (Person B).

Phase 7 Stretch:
Provides grid search and empirical parameter optimization across seeds
using headless simulations.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence
from dataclasses import dataclass

from strategies.scoring import (
    base_urgency,
    wait_bonus,
    contention_penalty,
    DEFAULT_WAIT_WEIGHT_PER_MIN,
    DEFAULT_WAIT_CAP,
    DEFAULT_CONTENTION_WEIGHT,
    DEFAULT_CONTENTION_THRESHOLD,
)
from strategies.stats_display import to_display_stats


def make_custom_strategy(
    weight_per_min: float = DEFAULT_WAIT_WEIGHT_PER_MIN,
    cap: float = DEFAULT_WAIT_CAP,
    contention_weight: float = DEFAULT_CONTENTION_WEIGHT,
    contention_threshold: float = DEFAULT_CONTENTION_THRESHOLD,
) -> Callable[[Any, Any, int], float]:
    """Factory function producing a customized urgency_wait_utilization strategy."""
    def custom_strategy(p: Any, s: Any, now: int) -> float:
        base = base_urgency(p.urgency)
        bonus = wait_bonus(p.wait_s, weight_per_min=weight_per_min, cap=cap)
        penalty = contention_penalty(
            p.required,
            s,
            weight=contention_weight,
            threshold=contention_threshold,
        )
        return base + bonus - penalty

    custom_strategy.__name__ = (
        f"urgency_wait_util_w{weight_per_min}_c{cap}_cw{contention_weight}_t{contention_threshold}"
    )
    return custom_strategy


@dataclass
class TuningResult:
    """Evaluation output for a single hyperparameter configuration."""
    weight_per_min: float
    cap: float
    contention_weight: float
    contention_threshold: float
    avg_wait_s: float
    p95_wait_s: float
    critical_avg_wait_s: float
    nonurgent_avg_wait_s: float
    starvation_pct: float
    score: float


def evaluate_parameters(
    params: dict[str, float],
    seeds: Sequence[int] = (42, 101, 777),
    horizon_s: int = 14400,  # 4 hours
) -> TuningResult:
    """Evaluate a parameter set across multiple seeds using run_headless.
    
    Returns aggregated TuningResult.
    """
    from engine.config import default_config
    from engine.arrivals import generate_arrivals
    from engine.headless import run_headless

    w_min = params.get("weight_per_min", DEFAULT_WAIT_WEIGHT_PER_MIN)
    cap = params.get("cap", DEFAULT_WAIT_CAP)
    cw = params.get("contention_weight", DEFAULT_CONTENTION_WEIGHT)
    ct = params.get("contention_threshold", DEFAULT_CONTENTION_THRESHOLD)

    strat = make_custom_strategy(
        weight_per_min=w_min,
        cap=cap,
        contention_weight=cw,
        contention_threshold=ct,
    )
    config = default_config()

    all_waits: list[float] = []
    all_p95: list[float] = []
    all_crit_waits: list[float] = []
    all_nonurg_waits: list[float] = []
    all_starvations: list[float] = []

    for seed in seeds:
        arrivals = generate_arrivals(seed, config, horizon_s)
        raw = run_headless(config, arrivals, strat, seed=seed, until_s=horizon_s)
        display = to_display_stats(raw)

        all_waits.append(display["wait_times"]["overall"]["avg_wait_s"])
        all_p95.append(display["wait_times"]["overall"]["p95_wait_s"])
        all_crit_waits.append(display["wait_times"]["by_urgency"][1]["avg_wait_s"])
        all_nonurg_waits.append(display["wait_times"]["by_urgency"][5]["avg_wait_s"])
        all_starvations.append(display["starvation"]["starvation_pct"])

    avg_wait = sum(all_waits) / len(all_waits) if all_waits else 0.0
    p95_wait = sum(all_p95) / len(all_p95) if all_p95 else 0.0
    crit_wait = sum(all_crit_waits) / len(all_crit_waits) if all_crit_waits else 0.0
    nonurg_wait = sum(all_nonurg_waits) / len(all_nonurg_waits) if all_nonurg_waits else 0.0
    starv_pct = sum(all_starvations) / len(all_starvations) if all_starvations else 0.0

    # Composite objective: heavy penalty on critical wait + moderate penalty on starvation & avg wait
    composite_score = (crit_wait * 5.0) + (avg_wait * 1.0) + (starv_pct * 10.0)

    return TuningResult(
        weight_per_min=w_min,
        cap=cap,
        contention_weight=cw,
        contention_threshold=ct,
        avg_wait_s=round(avg_wait, 2),
        p95_wait_s=round(p95_wait, 2),
        critical_avg_wait_s=round(crit_wait, 2),
        nonurgent_avg_wait_s=round(nonurg_wait, 2),
        starvation_pct=round(starv_pct, 2),
        score=round(composite_score, 2),
    )


def grid_search(
    weight_per_min_vals: Sequence[float] = (0.25, 0.5, 0.75),
    cap_vals: Sequence[float] = (30.0, 40.0),
    contention_weights: Sequence[float] = (5.0, 10.0),
    seeds: Sequence[int] = (42, 101),
    horizon_s: int = 7200,
) -> list[TuningResult]:
    """Execute grid search across parameter values and rank by composite score."""
    results: list[TuningResult] = []

    for w_min in weight_per_min_vals:
        for cap in cap_vals:
            for cw in contention_weights:
                params = {
                    "weight_per_min": w_min,
                    "cap": cap,
                    "contention_weight": cw,
                    "contention_threshold": DEFAULT_CONTENTION_THRESHOLD,
                }
                res = evaluate_parameters(params, seeds=seeds, horizon_s=horizon_s)
                results.append(res)

    results.sort(key=lambda r: r.score)
    return results


if __name__ == "__main__":
    print("Running parameter sweep across sample seeds...")
    results = grid_search()
    print("\nTop 3 Parameter Configurations:")
    for i, r in enumerate(results[:3], 1):
        print(
            f"#{i} Score={r.score} | w_min={r.weight_per_min}, cap={r.cap}, cw={r.contention_weight} "
            f"| CritWait={r.critical_avg_wait_s}s, AvgWait={r.avg_wait_s}s, Starvation={r.starvation_pct}%"
        )
