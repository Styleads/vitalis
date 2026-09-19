"""MedFlow - Stats Display and Strategy Comparison (Person B).

Conforms to AGENT.md §14.3, §15 (Phase 5), §16.
Transforms Engine.stats_raw() into frontend/API-ready display stats,
and provides side-by-side strategy comparison metrics.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


def _compute_percentile(values: list[float], percentile: float) -> float:
    """Compute percentile from sorted list of numbers (nearest rank)."""
    if not values:
        return 0.0
    k = (len(values) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return float(d0 + d1)


def to_display_stats(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Transform Engine.stats_raw() dictionary into displayed statistics.
    
    Expected raw schema (§14.3):
      {
        "patients": [
          {"id": int, "urgency": int, "arrival": int, "start": int | None,
           "end": int | None, "interruptions": int, "status": str}
        ],
        "busy_s": {TYPE: int},
        "available_s": {TYPE: int},
        "counts": {"arrived": int, "treated": int, "waiting": int,
                   "in_treatment": int, "interrupted": int}
      }
      
    Returns:
      Structured display dictionary containing:
        - wait_times: overall avg/p95/max, and breakdown by urgency level 1..5
        - utilization_pct: per-resource-type and overall average (guarded div-by-zero)
        - counts: arrived, treated, waiting, in_treatment, interrupted
        - starvation: count and percentage of level 4/5 patients waiting > 1 hr
    """
    patients = raw.get("patients", [])
    busy_s = raw.get("busy_s", {})
    available_s = raw.get("available_s", {})
    raw_counts = raw.get("counts", {})

    # Compute wait times per patient and group by urgency
    wait_times_all: list[float] = []
    wait_times_by_urgency: dict[int, list[float]] = {u: [] for u in range(1, 6)}
    starvation_count_level_4_5 = 0
    total_level_4_5 = 0

    for p in patients:
        urgency = p.get("urgency", 5)
        arrival = p.get("arrival", 0)
        start = p.get("start")
        end = p.get("end")

        # Wait time is calculated from arrival to first treatment start (or completion)
        if start is not None:
            wait = float(max(0, start - arrival))
        elif end is not None:
            wait = float(max(0, end - arrival))
        else:
            # If not yet started, wait time not finalised for service
            continue

        wait_times_all.append(wait)
        if urgency in wait_times_by_urgency:
            wait_times_by_urgency[urgency].append(wait)

        if urgency in (4, 5):
            total_level_4_5 += 1
            if wait > 3600.0:  # Waited over 1 hour
                starvation_count_level_4_5 += 1

    wait_times_all.sort()

    overall_wait = {
        "avg_wait_s": round(sum(wait_times_all) / len(wait_times_all), 2) if wait_times_all else 0.0,
        "p95_wait_s": round(_compute_percentile(wait_times_all, 95.0), 2) if wait_times_all else 0.0,
        "max_wait_s": round(max(wait_times_all), 2) if wait_times_all else 0.0,
        "sample_count": len(wait_times_all),
    }

    by_urgency_wait: dict[int, dict[str, Any]] = {}
    for u in range(1, 6):
        u_waits = sorted(wait_times_by_urgency[u])
        by_urgency_wait[u] = {
            "avg_wait_s": round(sum(u_waits) / len(u_waits), 2) if u_waits else 0.0,
            "p95_wait_s": round(_compute_percentile(u_waits, 95.0), 2) if u_waits else 0.0,
            "max_wait_s": round(max(u_waits), 2) if u_waits else 0.0,
            "sample_count": len(u_waits),
        }

    # Resource utilization % per type (guarding against divide-by-zero)
    utilization_pct: dict[str, float] = {}
    valid_utilization_vals: list[float] = []
    for rtype, avail in available_s.items():
        busy = busy_s.get(rtype, 0)
        key_str = rtype.name if hasattr(rtype, "name") else str(rtype)
        if avail > 0:
            pct = round(min(100.0, (busy / avail) * 100.0), 2)
            utilization_pct[key_str] = pct
            valid_utilization_vals.append(pct)
        else:
            utilization_pct[key_str] = 0.0

    avg_utilization_pct = (
        round(sum(valid_utilization_vals) / len(valid_utilization_vals), 2)
        if valid_utilization_vals
        else 0.0
    )

    return {
        "wait_times": {
            "overall": overall_wait,
            "by_urgency": by_urgency_wait,
        },
        "utilization_pct": utilization_pct,
        "avg_utilization_pct": avg_utilization_pct,
        "counts": {
            "arrived": raw_counts.get("arrived", len(patients)),
            "treated": raw_counts.get("treated", 0),
            "waiting": raw_counts.get("waiting", 0),
            "in_treatment": raw_counts.get("in_treatment", 0),
            "interrupted": raw_counts.get("interrupted", 0),
        },
        "starvation": {
            "starved_level_4_5_count": starvation_count_level_4_5,
            "total_level_4_5": total_level_4_5,
            "starvation_pct": (
                round((starvation_count_level_4_5 / total_level_4_5) * 100.0, 2)
                if total_level_4_5 > 0
                else 0.0
            ),
        },
    }


def compare_strategies(results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Compare multiple strategy simulation runs over the same arrivals and seed.
    
    Args:
        results: Mapping of {strategy_name: stats_raw()} from run_headless().
        
    Returns:
      Comparison report containing:
        - "strategies": {strategy_name: display_stats}
        - "summary": list of comparative rows for dashboard tables/charts
        - "deltas_vs_baseline": metrics delta compared to 'urgency_only' baseline
    """
    display_by_strat: dict[str, dict[str, Any]] = {
        name: to_display_stats(raw) for name, raw in results.items()
    }

    summary: list[dict[str, Any]] = []
    for name, stats in display_by_strat.items():
        summary.append({
            "strategy": name,
            "avg_wait_s": stats["wait_times"]["overall"]["avg_wait_s"],
            "p95_wait_s": stats["wait_times"]["overall"]["p95_wait_s"],
            "critical_avg_wait_s": stats["wait_times"]["by_urgency"][1]["avg_wait_s"],
            "nonurgent_avg_wait_s": stats["wait_times"]["by_urgency"][5]["avg_wait_s"],
            "avg_utilization_pct": stats["avg_utilization_pct"],
            "treated_count": stats["counts"]["treated"],
            "starvation_level_4_5_pct": stats["starvation"]["starvation_pct"],
        })

    # Sort summary: best average wait first
    summary.sort(key=lambda s: s["avg_wait_s"])

    # Compute deltas against urgency_only baseline if present
    deltas: dict[str, Any] = {}
    baseline = display_by_strat.get("urgency_only")
    if baseline:
        base_avg_wait = baseline["wait_times"]["overall"]["avg_wait_s"]
        base_nonurgent_wait = baseline["wait_times"]["by_urgency"][5]["avg_wait_s"]
        base_starvation_pct = baseline["starvation"]["starvation_pct"]

        for name, stats in display_by_strat.items():
            if name == "urgency_only":
                continue
            deltas[name] = {
                "overall_wait_delta_s": round(
                    stats["wait_times"]["overall"]["avg_wait_s"] - base_avg_wait, 2
                ),
                "nonurgent_wait_delta_s": round(
                    stats["wait_times"]["by_urgency"][5]["avg_wait_s"] - base_nonurgent_wait, 2
                ),
                "starvation_reduction_pct": round(
                    base_starvation_pct - stats["starvation"]["starvation_pct"], 2
                ),
                "treated_delta": (
                    stats["counts"]["treated"] - baseline["counts"]["treated"]
                ),
            }

    return {
        "strategies": display_by_strat,
        "summary_table": summary,
        "deltas_vs_baseline": deltas,
    }
