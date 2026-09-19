"""
engine/headless.py
==================
run_headless — spec §12.

Provides a fair, reproducible single-strategy run:
  - Deep-copies arrivals so the shared list is never mutated.
    This allows the same arrival list to be passed to multiple run_headless
    calls for strategy A/B comparison without any cross-contamination.
  - Uses the same scripted actions for every call.
  - Returns stats_raw() when finished.
"""

from __future__ import annotations

import copy
from typing import Callable, Optional

from engine.types import PatientView, StateView
from engine.config import EngineConfig, ScriptedAction

Strategy = Callable[[PatientView, StateView, int], float]


def run_headless(
    config: EngineConfig,
    arrivals: list,
    strategy: Strategy,
    seed: int,
    until_s: int,
    scripted: list[ScriptedAction] = (),
    triage_fn: Optional[Callable] = None,
    los_fn:    Optional[Callable] = None,
) -> dict:
    """
    Run the engine to until_s with the given strategy; return stats_raw().

    Why deep-copy: the same arrivals list must be reusable across multiple
    strategy runs for a fair A/B comparison (spec §9 / TEAM_CONTRACT).
    Mutating the shared list would corrupt subsequent runs.
    """
    from engine.engine import Engine

    arrivals_copy: list = copy.deepcopy(arrivals)
    eng = Engine(
        config,
        arrivals_copy,
        strategy,
        seed,
        scripted=list(scripted),
        triage_fn=triage_fn,
        los_fn=los_fn,
    )
    eng.run_until(until_s)
    return eng.stats_raw()
