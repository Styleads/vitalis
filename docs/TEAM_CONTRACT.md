# MedFlow Team Contract (agree on this in the first 30 minutes)

Owner of this file: Person A. Full details live in `docs/ENGINE_SPEC.md`. If anything here changes, tell the team immediately.

## Ownership
| Person | Area | Folder |
|---|---|---|
| A | Simulation engine, scenarios, invariants, snapshot/stats | `engine/`, `tests/engine/`, `scripts/` |
| B | Priority scoring, 3 strategies, stats module, correctness suite | `strategies/` |
| C | FastAPI + WebSocket, scenario endpoints, demo seeding | `api/` |
| D | React dashboard | `frontend/` |
| Unowned | AI component: triage classifier and/or length-of-stay predictor | `ml/` |

## Shared conventions
- Time: int seconds of **simulated** time. Urgency 1..5 (1 = critical). Ids are ints.
- Urgency colors: 1 red, 2 orange, 3 yellow, 4 green, 5 blue/grey.

## For Person B: strategy interface
```python
Strategy = Callable[[PatientView, StateView, int], float]   # higher score = sooner
```
- `PatientView`: id, urgency, arrival_time, wait_s, required, predicted_service_time, remaining_service, arrival_mode, department, interruptions.
- `StateView`: clock, free counts per type, total active counts per type, `waiting` (tuple of PatientView), in_treatment count, flags.
- Frozen and read-only; you cannot mutate engine state.
- Engine sorts by `(-score, arrival_time, id)`. Head-of-line policy is `BACKFILL` (skip a patient who cannot get resources) by default; the utilization-aware strategy may reason about scarce units (e.g. ICU) using `StateView`.
- B owns the stats module: it consumes `engine.stats_raw()` and produces avg wait per urgency, utilization %, treated vs waiting, and strategy deltas.
- B's correctness suite can call `assert_invariants(engine)`.

## For Person C: driving the engine
```python
from engine import Engine, EngineConfig, generate_arrivals, run_headless, ScriptedAction

arrivals = generate_arrivals(seed, config, horizon_s)
eng = Engine(config, arrivals, strategy, seed, scripted=[...])

# live mode (async loop lives in api/, not in engine/):
eng.run_until(eng.clock + int(sim_speed * dt))    # every wall-clock tick
state = eng.snapshot()                             # JSON-safe, push over WebSocket

# demo buttons:
eng.inject_surge(3.0, 3600)                        # takes effect on next run_until
eng.set_capacity(ResourceType.NURSE, 6)
eng.fail_resource(unit_id, 1800)
eng.set_strategy(other_strategy)
```
- Hooks enqueue events at the current simulated time. Call `run_until(eng.clock)` right after a hook if the UI must update immediately.
- **Strategy comparison must use `run_headless`** with the SAME `arrivals` list, seed and `scripted` actions for every strategy. Never trigger surges by wall-clock in compared runs. `run_headless` deep-copies arrivals, so reuse the list.
- `snapshot()` shape and `stats_raw()` shape are in ENGINE_SPEC section 12.
- Suggested WebSocket message: `{"type": "state", "data": <snapshot>}` each tick, plus `{"type": "log", "data": [...events]}` if you want the feed separate.

## For Person D: what you can render
From `snapshot()`: `queue` (sorted, with score and wait_s), `in_treatment`, `resources` (total/free/occupied/failed/off per type), `flags.arrival_multiplier`, `recent_events`. Assignment animations can key off `ASSIGNED` and `INTERRUPTED` log events. Comparison charts come from B's stats over `run_headless` results via C.

## AI component (needs an owner in the first-hour sync)
The rules require the README to name the AI component, and faking or hardcoding it risks disqualification. The engine has two hooks so whoever owns it needs no engine changes:
- `triage_fn(patient) -> urgency 1..5` (applied at arrival)
- `los_fn(patient) -> predicted_service_time_s` (strategies may read `predicted_service_time`)
Both must be pure and deterministic. Training/synthetic data must be created during the hackathon.

## What A needs from the others
- B: confirm the Strategy signature and BACKFILL default within the first hour.
- C: confirm you use `run_headless` + `ScriptedAction` for comparisons and only the listed hooks for scenarios.
- D: confirm the snapshot fields cover the UI; ask A early if you need another field.

## Checkpoints
- Hour 0:30: this file agreed.
- Hour 4:00: A's CLI harness runs 10k steps with invariants on; C+D render mock JSON in the real snapshot shape.
- Hour 9:00: end-to-end prototype committed (safety net).
