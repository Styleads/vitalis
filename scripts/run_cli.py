"""
scripts/run_cli.py
==================
Command-line debug harness for the MedFlow simulation engine.

Runs Engine through 10,000 steps with debug_invariants=True,
prints a log tail and stats_raw summary, and exits non-zero on
any invariant failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.types import PatientView, ResourceType, StateView
from engine.config import default_config
from engine.arrivals import generate_arrivals
from engine.engine import Engine
from engine.invariants import assert_invariants


def fifo_strategy(pv: PatientView, sv: StateView, now: int) -> float:
    """FIFO priority strategy: earlier arrival times receive higher score."""
    return float(-pv.arrival_time)


def urgency_strategy(pv: PatientView, sv: StateView, now: int) -> float:
    """Baseline urgency strategy: urgency 1 is highest, ties broken by arrival time."""
    return float((6 - pv.urgency) * 1000 - pv.arrival_time / 1000.0)


def format_duration(seconds: int | float) -> str:
    """Format seconds into human-readable H:MM:SS."""
    s = int(round(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h}h {m:02d}m {sec:02d}s"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MedFlow simulation engine CLI debug harness."
    )
    parser.add_argument(
        "seed_pos",
        nargs="?",
        type=int,
        default=None,
        help="Random seed for arrival generation and simulation",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--strategy",
        choices=["fifo", "urgency"],
        default="fifo",
        help="Allocation priority strategy: fifo or urgency (default: fifo)",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=10_000,
        help="Number of simulation steps to run (default: 10,000)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=3600 * 2000,
        help="Horizon in seconds for pre-generated arrival stream (default: 2,000 hours)",
    )

    args = parser.parse_args()
    seed = args.seed_pos if args.seed_pos is not None else args.seed

    strat_fn = fifo_strategy if args.strategy == "fifo" else urgency_strategy

    config = default_config()
    config.debug_invariants = True

    print("=" * 70)
    print("MEDFLOW SIMULATION ENGINE CLI HARNESS")
    print("=" * 70)
    print(f"Seed:             {seed}")
    print(f"Strategy:         {args.strategy}")
    print(f"Target steps:     {args.steps:,}")
    print(f"Arrival horizon:  {format_duration(args.horizon)}")
    print(f"Debug Invariants: {config.debug_invariants}")
    print("-" * 70)

    print("Generating arrivals...")
    arrivals = generate_arrivals(seed=seed, config=config, horizon_s=args.horizon)
    print(f"Generated {len(arrivals):,} patients across horizon.")

    print(f"Initializing engine with strategy '{args.strategy}'...")
    eng = Engine(
        config=config,
        arrivals=arrivals,
        strategy=strat_fn,
        seed=seed,
    )

    last_step_logs: list[dict] = []
    executed_steps = 0

    print(f"Running up to {args.steps:,} steps with invariant assertions enabled...")
    try:
        for step_i in range(args.steps):
            logs = eng.step()
            if not logs and not eng._heap:
                print(f"Event heap exhausted at step {step_i + 1}.")
                break
            last_step_logs = logs
            executed_steps += 1
    except AssertionError as err:
        print("\n" + "!" * 70)
        print(f"INVARIANT VIOLATION DETECTED AT STEP {executed_steps + 1}, CLOCK {eng.clock}:")
        print(f"  {err}")
        print("!" * 70)
        return 1

    print(f"Completed {executed_steps:,} steps successfully. Final clock: {eng.clock}s ({format_duration(eng.clock)}).")

    # ── Log tail ──
    print("\n" + "=" * 70)
    print(f"LOG TAIL (last {min(10, len(eng._recent_events))} events):")
    print("=" * 70)
    tail_events = list(eng._recent_events)[-10:]
    for evt in tail_events:
        t = evt.get("t", "?")
        etype = evt.get("type", "?")
        pid = evt.get("patient_id", "")
        note = evt.get("note", "")
        units = evt.get("units", "")
        extra = f" pid={pid}" if pid else ""
        if units:
            extra += f" units={units}"
        if note:
            extra += f" note={note}"
        print(f"  [{t:8d}s] {etype:<16}{extra}")

    # ── Stats Summary ──
    stats = eng.stats_raw()
    counts = stats["counts"]
    patients = stats["patients"]

    # Filter to patients who have actually arrived by the final simulated clock
    arrived_patients = [p for p in patients if p["arrival"] <= eng.clock]

    print("\n" + "=" * 70)
    print("RAW STATS SUMMARY:")
    print("=" * 70)
    print(f"  Patients Arrived:      {counts['arrived']:,}")
    print(f"  Patients Treated:      {counts['treated']:,}")
    print(f"  Patients Waiting:      {counts['waiting']:,}")
    print(f"  Patients In Treatment: {counts['in_treatment']:,}")
    print(f"  Total Interruptions:   {counts['interrupted']:,}")

    # ── Wait times per urgency ──
    print("\nWAIT TIMES PER URGENCY (ARRIVED PATIENTS ONLY):")
    print(f"  {'Urgency':<8} {'Count':<8} {'Avg Wait':<14} {'Min Wait':<12} {'Max Wait':<12}")
    print("  " + "-" * 56)
    for urg in range(1, 6):
        urg_patients = [
            p for p in arrived_patients
            if p["urgency"] == urg and (p["start"] is not None or p["status"] == "WAITING")
        ]
        if urg_patients:
            waits = [
                max(0, (p["start"] if p["start"] is not None else eng.clock) - p["arrival"])
                for p in urg_patients
            ]
            avg_w = sum(waits) / len(waits)
            min_w = min(waits)
            max_w = max(waits)
            print(f"  Level {urg:<2} {len(urg_patients):<8} {format_duration(avg_w):<14} {format_duration(min_w):<12} {format_duration(max_w):<12}")
        else:
            print(f"  Level {urg:<2} 0        N/A            N/A          N/A")

    # ── Utilization per ResourceType ──
    print("\nRESOURCE UTILIZATION:")
    print(f"  {'Resource Type':<16} {'Total':<6} {'Busy (s)':<12} {'Available (s)':<15} {'Utilization %':<12}")
    print("  " + "-" * 63)
    for rt in ResourceType:
        busy = stats["busy_s"].get(rt.value, 0)
        avail = stats["available_s"].get(rt.value, 0)
        total_units = config.capacities.get(rt, 0)
        util_pct = (busy / avail * 100.0) if avail > 0 else 0.0
        print(f"  {rt.value:<16} {total_units:<6} {busy:<12,d} {avail:<15,d} {util_pct:>6.2f}%")

    print("\n" + "=" * 70)
    print("ALL INVARIANTS SATISFIED (I1 - I10)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
