# MedFlow Engine Spec (Person A)

Status: DRAFT until section 13 is confirmed by Person A. Values marked *(placeholder)* are tunable defaults.

## 1. Purpose and scope
`engine/` is a pure, headless, deterministic discrete-event simulator of a hospital. It owns: patient generation, resource pools, the event loop, allocation, invariants, scripted/live scenarios, snapshots, and raw stats. It does NOT own: priority scoring (Person B, `strategies/`), HTTP/WebSocket (Person C, `api/`), UI (Person D, `frontend/`), and the optional ML models (`ml/`, plugged in via hooks).

**Core guarantee:** same seed + same config + same scripted actions + same strategy => byte-identical event log. This makes strategy comparison fair.

## 2. Repo layout
```
medflow/
├── AGENTS.md
├── README.md
├── docs/                 ENGINE_SPEC.md, TEAM_CONTRACT.md, AGENT_PROMPTS.md, ai-notes/
├── engine/
│   ├── __init__.py       public exports
│   ├── types.py          enums, Patient, Unit, PatientView, StateView, Event
│   ├── config.py         EngineConfig + defaults
│   ├── arrivals.py       make_patient, generate_arrivals
│   ├── resources.py      ResourcePool, try_reserve, release
│   ├── engine.py         Engine (heap, step, allocation pass, hooks, snapshot, stats)
│   ├── invariants.py     assert_invariants
│   └── headless.py       run_headless (used by B/C for comparisons)
├── strategies/           Person B
├── api/                  Person C
├── frontend/             Person D
├── ml/                   optional AI component (triage / length-of-stay)
├── scripts/run_cli.py    debug harness
└── tests/engine/
```

## 3. Conventions
- Time is an **int, seconds**. No float time. Service times are rounded to int seconds.
- Urgency: int 1..5, **1 = most critical**, 5 = non-urgent (ESI-style).
- Ids are ints assigned sequentially (patients from 1; units from 1 across all types). Ties always break by id.

## 4. Data model

### ResourceType (enum)
`BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE` (AMBULANCE exists but no default bundle uses it in v1).

### Unit
| field | notes |
|---|---|
| id | int, unique across all types |
| type | ResourceType |
| status | `FREE`, `OCCUPIED`, `FAILED`, `OFF` |
| owner | patient id or None (non-None iff OCCUPIED) |
| pending_off | bool, only ever true on an OCCUPIED unit (see set_capacity) |

`FAILED` = broken (fail_resource). `OFF` = unavailable through capacity/staff reduction. Neither can be allocated.

### Patient
| field | notes |
|---|---|
| id, arrival_time | int, int seconds |
| urgency | int 1..5 (scheduler-facing; a triage hook may overwrite it at arrival) |
| required | dict[ResourceType, int], the bundle |
| service_time | int seconds of treatment (the simulation's truth) |
| remaining_service | int seconds left (== service_time until interrupted) |
| predicted_service_time | Optional[int], set by the ML length-of-stay hook; strategies may read it, the engine never uses it for timing |
| arrival_mode | `WALK_IN` or `AMBULANCE` |
| department | str, default `"general"` |
| features | dict, free-form (vitals, complaint text) for the AI component |
| status | `WAITING`, `IN_TREATMENT`, `DISCHARGED` |
| start_time, end_time | Optional[int] (start_time = first treatment start) |
| assigned | list[unit ids], empty unless IN_TREATMENT |
| interruptions | int |
| segment_start | Optional[int], when the current treatment segment began (used by P-FAIL) |
| token | int, bumped on every assignment/interruption (lazy deletion of TREATMENT_DONE) |

`wait_time(now) = (start_time if not None else now) - arrival_time`. Interruptions never reset `arrival_time`.

### PatientView and StateView (what strategies see; frozen, read-only)
- `PatientView`: id, urgency, arrival_time, wait_s (at `now`), required, predicted_service_time, remaining_service, arrival_mode, department, interruptions.
- `StateView`: clock, free counts per type, total active counts per type, `waiting` (tuple of PatientView), in_treatment count, `flags` (e.g. arrival_multiplier).
Strategies must not mutate anything; the engine passes frozen copies so they cannot.

### Default bundles *(placeholder; live in EngineConfig, never hardcoded in logic)*
| urgency | required | mean service |
|---|---|---|
| 1 | ICU_BED 1, DOCTOR 1, NURSE 2 (+ OR 1 with prob `or_probability[1]`) | 4 h |
| 2 | BED 1, DOCTOR 1, NURSE 1 (+ OR 1 with prob `or_probability[2]`) | 3 h |
| 3 | BED 1, DOCTOR 1, NURSE 1 | 2 h |
| 4 | BED 1, DOCTOR 1 | 1 h |
| 5 | DOCTOR 1 | 20 min |

Service times are sampled per patient (exponential or lognormal around the mean) by the seeded RNG. Default urgency mix *(placeholder)*: 5% / 15% / 30% / 30% / 20% for levels 1..5. Default capacities *(placeholder)*: BED 20, ICU_BED 4, OR 2, DOCTOR 8, NURSE 16, AMBULANCE 3.

## 5. Events
Kinds: `ARRIVAL, TREATMENT_DONE, FAILURE, RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END`.

Event = `(time, kind_rank, seq, kind, payload)`. `seq` is a strictly increasing counter assigned at push time. The heap orders by `(time, kind_rank, seq)`.

`kind_rank` (lower runs first at the same timestamp):
- 0: TREATMENT_DONE, RECOVERY (resources are released)
- 1: FAILURE, CAPACITY_CHANGE
- 2: SURGE_START, SURGE_END
- 3: ARRIVAL

**TREATMENT_DONE cancellation** uses lazy deletion: the event payload carries `(patient_id, token)`; the patient stores its current `token`. A popped TREATMENT_DONE whose token does not match (or whose patient is not IN_TREATMENT) is skipped silently.

## 6. Engine loop
`step()`:
1. If the heap is empty, return `[]` (clock does not advance).
2. Let `t` = smallest event time. Update utilization integrals from `clock` to `t` (before any state change), then set `clock = t`.
3. Loop: while the heap top has time == `t`, pop and apply it (handlers may push new events at `t`, e.g. surge arrivals; those are processed in the same loop, in heap order).
4. Run the allocation pass (section 7) exactly once.
5. If `debug_invariants`, call `assert_invariants`.
6. Return the log events (dicts) produced by this step.

`run_until(t)`: call `step()` while the heap is non-empty and the next event time <= t; then accumulate utilization up to `t` and set `clock = t`.

## 7. Allocation pass
1. Waiting patients = status WAITING.
2. Score each with `strategy(PatientView, StateView, now)`; higher = sooner.
3. Sort by `(-score, arrival_time, id)`.
4. For each patient in order, `try_reserve(patient.required, patient.id)`:
   - Success: units OCCUPIED (owner = patient id), patient IN_TREATMENT, `assigned` set, `start_time` set if None, new token, push TREATMENT_DONE at `now + remaining_service`, log `ASSIGNED`.
   - Failure and `hol_policy == "BACKFILL"`: continue to the next patient.
   - Failure and `hol_policy == "BLOCK"`: stop the pass.
5. One pass suffices (allocating only shrinks the free pool). Scores are recomputed each pass since waiting time changes.
6. After the pass, the `StateView` passed to the strategy must reflect allocations made earlier in the same pass (rebuild or update it as units are taken).

## 8. Atomic reservation and release
`try_reserve(bundle, patient_id) -> list[unit ids] | None`:
- For each type in the bundle (in enum order), pick the required number of FREE units with the lowest ids.
- If **any** type has too few: return None and leave state completely unchanged.
- Otherwise mark all picked units OCCUPIED with owner and return their ids.
No partial allocation may ever be observable outside this function.

`release(unit)`: owner = None; if `pending_off` then status OFF and `pending_off = False`, else FREE. (Used by treatment completion and interruption.)

## 9. Scenario hooks
Hooks never mutate state directly. They **enqueue an event at the current clock** (or a future time when scripted). Their effect applies on the next `step()`/`run_until()`. Live callers should call `run_until(clock)` right after a hook if they want the effect immediately.

- `inject_surge(multiplier, duration_s)`: enqueues SURGE_START now with payload `(multiplier, duration_s)`. On processing: set `flags.arrival_multiplier`, generate extra Poisson arrivals at rate `(multiplier - 1) * base_arrival_rate` from `now` to `now + duration_s` using `random.Random(f"{seed}:surge:{k}")` where `k` is the index of this surge (0, 1, ...), push them as ARRIVAL events (continuing patient ids from a shared counter), and push SURGE_END at `now + duration_s`. SURGE_END resets the flag and logs.
- `set_capacity(rtype, n)`: enqueues CAPACITY_CHANGE. `n` is clamped to `[0, total units of that type]`. Reducing: FREE units become OFF (highest ids first); if more must go, OCCUPIED units get `pending_off = True` (highest ids first) and go OFF on release. **Reductions never interrupt treatment.** Increasing: OFF units return to FREE (lowest ids first), clear `pending_off` on occupied units first, then allocation runs.
- `fail_resource(rid, duration_s)`: enqueues FAILURE; schedules RECOVERY at `now + duration_s`. Ignored (and logged) if the unit is already FAILED or OFF. If the unit was OCCUPIED, apply **P-FAIL**. On RECOVERY: status becomes FREE (or OFF if `pending_off`).
- `set_strategy(fn)`: takes effect at the next allocation pass.

**P-FAIL:** the interrupted patient releases *all* their units, returns to WAITING with `remaining_service -= (now - treatment_segment_start)`, keeps `arrival_time`, `interruptions += 1`, gets a new token (which cancels the pending TREATMENT_DONE), and logs `INTERRUPTED`. The failed unit becomes FAILED (not released to FREE).

**Scripted scenarios** (for fair comparison): the constructor accepts `scripted: list[ScriptedAction]` where `ScriptedAction = (time_s, action, args)` with action in `{"surge", "capacity", "fail"}`. Each is pushed to the heap at init as the same events the live hooks create, so scripted and live paths are identical code.

## 10. AI hooks
- `triage_fn: Callable[[Patient], int] | None`: applied once at ARRIVAL; returns a new urgency 1..5. Default: identity.
- `los_fn: Callable[[Patient], int] | None`: applied once at ARRIVAL; sets `predicted_service_time` only. It never changes `service_time`.
Both must be pure and deterministic given the patient. If a hook raises or returns an invalid value, the engine logs `HOOK_ERROR`, keeps the generator's value, and continues. The engine never crashes because of a hook.

## 11. Invariants (`assert_invariants(engine)`)
Run after every step in debug mode and in the test suite.
- I1. A unit is OCCUPIED iff `owner` is not None.
- I2. No unit id appears in two patients' `assigned` lists.
- I3. Per type: occupied + free + failed + off == total units.
- I4. A FAILED or OFF unit never has an owner.
- I5. Every IN_TREATMENT patient's `assigned` satisfies its full `required` bundle (right types and counts).
- I6. Every IN_TREATMENT patient has exactly one valid (non-cancelled) pending TREATMENT_DONE; WAITING and DISCHARGED patients have none.
- I7. `clock` never decreases; every pushed event time >= clock.
- I8. DISCHARGED patients hold no units.
- I9. `pending_off` is only true on OCCUPIED units.
- I10. `0 <= remaining_service <= service_time` for all patients.

## 12. Public interface (do not change without telling B and C)

```python
Strategy = Callable[[PatientView, StateView, int], float]   # higher score = sooner

@dataclass
class EngineConfig:
    capacities: dict[ResourceType, int]
    bundles: dict[int, dict[ResourceType, int]]       # base bundle per urgency
    or_probability: dict[int, float]
    mean_service_s: dict[int, int]
    urgency_mix: dict[int, float]
    base_arrival_rate: float                          # patients per hour
    hol_policy: str = "BACKFILL"                      # or "BLOCK"
    debug_invariants: bool = False

ScriptedAction = tuple[int, str, tuple]               # (time_s, "surge"|"capacity"|"fail", args)

def generate_arrivals(seed: int, config: EngineConfig, horizon_s: int) -> list[Patient]: ...

class Engine:
    def __init__(self, config, arrivals: list[Patient], strategy: Strategy, seed: int,
                 scripted: list[ScriptedAction] = (), triage_fn=None, los_fn=None): ...
    def step(self) -> list[dict]: ...
    def run_until(self, t: int) -> None: ...
    def snapshot(self) -> dict: ...
    def stats_raw(self) -> dict: ...
    def inject_surge(self, multiplier: float, duration_s: int) -> None: ...
    def set_capacity(self, rtype: ResourceType, n: int) -> None: ...
    def fail_resource(self, rid: int, duration_s: int) -> None: ...
    def set_strategy(self, s: Strategy) -> None: ...

def assert_invariants(engine: Engine) -> None: ...
def run_headless(config, arrivals, strategy, seed, until_s, scripted=(),
                 triage_fn=None, los_fn=None) -> dict:  # returns stats_raw()
```
`run_headless` deep-copies `arrivals` so one arrival list can be reused across strategies.

### Log event schema
`{t, type, patient_id, units, note}`. Types: `ARRIVAL, ASSIGNED, DISCHARGED, INTERRUPTED, FAILURE, RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END, HOOK_ERROR`.

### snapshot() schema (JSON-safe copies)
```
{ clock, strategy_name, hol_policy,
  queue: [ {id, urgency, wait_s, score, required} ],        # in the order the next pass would sort
  in_treatment: [ {id, urgency, start_time, ends_at, assigned} ],
  resources: { TYPE: {total, free, occupied, failed, off} },
  flags: { arrival_multiplier },
  recent_events: [ ...last 50 log dicts ] }
```

### stats_raw()
```
{ patients: [ {id, urgency, arrival, start, end, interruptions, status} ],
  busy_s: {TYPE: int}, available_s: {TYPE: int},           # integrals; available excludes FAILED/OFF
  counts: {arrived, treated, waiting, in_treatment, interrupted} }
```
Utilization = busy_s / available_s (guard divide by zero). Person B turns these into displayed stats.

## 13. Decisions to confirm (Person A)
1. Default `hol_policy = BACKFILL` (agree with B).
2. P-FAIL policy (requeue with remaining time). Alternatives: restart from scratch, or move to another free unit.
3. Capacity reductions never interrupt treatment (lazy OFF).
4. Bundles, service times, urgency mix, capacities are placeholders.
5. Integer-seconds time is fine for B, C and D.
6. Scripted scenarios via `ScriptedAction` for comparisons (C must use this, never wall-clock, for compared runs).
7. Who owns the AI component (triage classifier / LOS predictor)? Hooks in section 10 exist for it.

## 14. Out of scope for v1
Multi-department routing (field only), ambulance transport modelling, persistence, any I/O.
