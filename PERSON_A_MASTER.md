# PERSON A MASTER FILE: MedFlow Engine + Integration

**Owner:** Person A (backend and simulation core) · **Project:** Hack-a-Matics 2026, MedFlow
This is the single file you work from. It has everything: what you build, how the frontend/API link to it, the full engine spec, the rules file for your coding agent, and the exact prompts to run in order.

> **Timing note:** the rules say all code must be written during the hackathon window (starts 19 Sep, 6:00 PM). This file contains **no engine code**, only the design, contracts and prompts. Generate the code with your agent after the window opens. Commit this file and `AGENTS.md` once the window is open, or keep them out of the repo until then if you want to be extra safe.

## Contents
- Part 0: Quick start and your job in one page
- Part 1: Linking with C (API) and D (frontend): contract, sample JSON, TypeScript types, tick loop, button map
- Part 2: Engine spec (source of truth for the agent)
- Part 3: `AGENTS.md` (paste into the repo root / your agent's rules location)
- Part 4: Agent prompts, in order, with schedule
- Part 5: Definition of done, checkpoints, and integration checklist

---

## Part 0: Quick start and your job in one page

### Your job
Build `engine/`: a pure, headless, deterministic discrete-event hospital simulator that everyone else plugs into.
- **You own:** patient generation, resource pools, event loop, atomic allocation, invariants, scenario hooks (surge / staff shortage / resource failure), `snapshot()`, `stats_raw()`, `run_headless()`.
- **You do not own:** scoring strategies (B, `strategies/`), FastAPI/WebSocket (C, `api/`), React (D, `frontend/`), ML models (`ml/`, owner TBD; plugs in through your two hooks).
- **Guarantee you give the team:** same seed + config + scripted actions + strategy ⇒ identical event log; no double-booking, no capacity violations, ever.

### Order of work
1. **First 30 min (team sync):** confirm Part 2 §13 decisions, give D the sample snapshot (Part 1.3), give B the Strategy signature, give C the driving pattern (Part 1.5). Decide who owns the AI component.
2. **Setup:** repo, folders, paste Part 3 into `AGENTS.md`, install Python 3.11 + pytest.
3. **Prompt 0 → Step A (tests) → Step B (stubs)**, then Slices 1-8 (Part 4). Read every diff; run pytest yourself.
4. **Hour-4 checkpoint:** CLI harness runs 10k steps with invariants on.
5. **Hours 4-9:** hooks, snapshot/stats, AI hooks; help C and D integrate.
6. **Hour 9:** safety-net prototype committed. Then bonus scenarios, M/M/c test, bug bash, README.

### What the others need from you, and when
| To | What | When |
|---|---|---|
| D | Sample snapshot JSON + TS types (Part 1.3, 1.4) | Hour 0:30 |
| B | `Strategy` signature, `PatientView`/`StateView`, BACKFILL default | Hour 0:30 |
| C | Driving pattern, `run_headless`, `ScriptedAction` (Part 1.5-1.6) | Hour 0:30 |
| B + C + D | Working engine behind the same shapes | Hour 4:00 |
| Everyone | Merged prototype | Hour 9:00 |

---

## Part 1: Linking with C (API) and D (frontend)

### 1.1 Data flow
```
frontend (D)  ⇄  api (C)  ⇄  engine (A)  ⇄  strategies (B) / ml hooks
   WebSocket: state each tick     Engine.run_until + snapshot()
   REST: controls, compare        hooks: inject_surge / set_capacity / fail_resource / set_strategy
```
`engine/` never imports asyncio or does I/O. C runs the wall-clock tick loop and calls into you.

### 1.2 Conventions all layers must share
- Time = int **seconds of simulated time** (`clock`, `wait_s`, `start_time`, `ends_at`). D formats it as `HH:MM` or `Xh Ym` for display.
- Urgency 1..5, **1 = most critical**. Colors: 1 red, 2 orange, 3 yellow, 4 green, 5 blue/grey.
- Resource type strings: `BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE`.
- Unit ids are ints, sequential across types in that order.

### 1.3 Sample `snapshot()` (give this to D as `frontend/mock/snapshot.json`)
Tiny demo config (not the defaults): BED 6, ICU_BED 1, OR 1, DOCTOR 2, NURSE 4, AMBULANCE 1. Unit ids: BED 1-6, ICU_BED 7, OR 8, DOCTOR 9-10, NURSE 11-14, AMBULANCE 15. Strategy is `urgency_wait` (score = base + wait bonus). Patient 14 (critical) is waiting because the only ICU bed is taken; patients 9 and 12 are waiting because both doctors are busy.

```json
{
  "clock": 9000,
  "strategy_name": "urgency_wait",
  "hol_policy": "BACKFILL",
  "queue": [
    {"id": 14, "urgency": 1, "wait_s": 120,  "score": 101.0, "required": {"ICU_BED": 1, "DOCTOR": 1, "NURSE": 2}},
    {"id": 9,  "urgency": 3, "wait_s": 2700, "score": 82.5,  "required": {"BED": 1, "DOCTOR": 1, "NURSE": 1}},
    {"id": 12, "urgency": 4, "wait_s": 1500, "score": 52.5,  "required": {"BED": 1, "DOCTOR": 1}}
  ],
  "in_treatment": [
    {"id": 5, "urgency": 1, "start_time": 7800, "ends_at": 22200, "assigned": [7, 9, 11, 12]},
    {"id": 8, "urgency": 3, "start_time": 8400, "ends_at": 15600, "assigned": [1, 10, 13]}
  ],
  "resources": {
    "BED":       {"total": 6, "free": 5, "occupied": 1, "failed": 0, "off": 0},
    "ICU_BED":   {"total": 1, "free": 0, "occupied": 1, "failed": 0, "off": 0},
    "OR":        {"total": 1, "free": 1, "occupied": 0, "failed": 0, "off": 0},
    "DOCTOR":    {"total": 2, "free": 0, "occupied": 2, "failed": 0, "off": 0},
    "NURSE":     {"total": 4, "free": 1, "occupied": 3, "failed": 0, "off": 0},
    "AMBULANCE": {"total": 1, "free": 1, "occupied": 0, "failed": 0, "off": 0}
  },
  "flags": {"arrival_multiplier": 1.0},
  "recent_events": [
    {"t": 8400, "type": "ASSIGNED", "patient_id": 8,  "units": [1, 10, 13], "note": "urgency 3"},
    {"t": 8880, "type": "ARRIVAL",  "patient_id": 14, "units": [], "note": "urgency 1"},
    {"t": 8880, "type": "ARRIVAL",  "patient_id": 12, "units": [], "note": "urgency 4"}
  ]
}
```
`queue` is already in the order the next allocation pass will use, so D can render it as-is.

### 1.4 TypeScript types for D
```ts
export type ResourceType = "BED" | "ICU_BED" | "OR" | "DOCTOR" | "NURSE" | "AMBULANCE";
export type Bundle = Partial<Record<ResourceType, number>>;

export interface QueueItem { id: number; urgency: 1|2|3|4|5; wait_s: number; score: number; required: Bundle; }
export interface TreatmentItem { id: number; urgency: 1|2|3|4|5; start_time: number; ends_at: number; assigned: number[]; }
export interface PoolState { total: number; free: number; occupied: number; failed: number; off: number; }

export type LogType = "ARRIVAL"|"ASSIGNED"|"DISCHARGED"|"INTERRUPTED"|"FAILURE"|"RECOVERY"
  |"CAPACITY_CHANGE"|"SURGE_START"|"SURGE_END"|"HOOK_ERROR";
export interface LogEvent { t: number; type: LogType; patient_id: number | null; units: number[]; note: string; }

export interface Snapshot {
  clock: number;
  strategy_name: string;
  hol_policy: "BACKFILL" | "BLOCK";
  queue: QueueItem[];
  in_treatment: TreatmentItem[];
  resources: Record<ResourceType, PoolState>;
  flags: { arrival_multiplier: number };
  recent_events: LogEvent[];
}
```
Utilization % for a gauge = `occupied / (total - failed - off)` (guard divide-by-zero).

### 1.5 How C drives the engine (usage pattern, not implementation)
```python
from engine import Engine, generate_arrivals, run_headless, ResourceType

arrivals = generate_arrivals(seed, config, horizon_s)
eng = Engine(config, arrivals, strategy, seed, scripted=[], triage_fn=None, los_fn=None)

# wall-clock tick loop lives in api/ (asyncio), e.g. every 0.5 s:
eng.run_until(eng.clock + int(speed * dt))
await broadcast({"type": "state", "data": eng.snapshot()})

# demo buttons (see 1.7); effect applies on the next run_until:
eng.inject_surge(3.0, 3600)
eng.set_capacity(ResourceType.NURSE, 6)
eng.fail_resource(unit_id, 1800)
eng.set_strategy(other_strategy)
eng.run_until(eng.clock)          # apply immediately so the UI updates now
```

### 1.6 Strategy comparison (fair A/B)
Every compared run must share **the same arrivals list, seed, and scripted actions**:
```python
arrivals = generate_arrivals(seed, config, horizon_s)
scripted = [(3600, "surge", (3.0, 3600)), (7200, "capacity", (ResourceType.NURSE, 6)), (10800, "fail", (7, 1800))]
results = {name: run_headless(config, arrivals, strat, seed, until_s, scripted) for name, strat in strategies.items()}
```
`run_headless` deep-copies `arrivals`, so reuse the list. Never trigger scenario events by wall-clock in compared runs. B turns each `stats_raw()` into displayed stats.

### 1.7 UI button → hook map
| Dashboard control | REST (C) | Engine call |
|---|---|---|
| Start / Pause / Speed | `/sim/start`, `/pause`, `/resume`, `/speed` | C's loop calls `run_until` |
| Trigger Surge | `POST /scenario/surge {multiplier, duration_s}` | `inject_surge` |
| Staff Shortage | `POST /scenario/capacity {type, n}` | `set_capacity` |
| Fail a Resource | `POST /scenario/fail {unit_id, duration_s}` | `fail_resource` |
| Strategy dropdown | `POST /strategy {name}` | `set_strategy` |
| Compare | `POST /compare {...}` | `run_headless` per strategy |

### 1.8 Integration gotchas to prevent
- Hooks take effect on the **next** `step()`/`run_until()`; call `run_until(clock)` after a hook.
- `snapshot()` returns copies; C can serialize it directly with `json.dumps`.
- Surges triggered live use the engine's RNG derived from the seed; only **scripted** ones are guaranteed identical across compared strategies (which is why compare uses `scripted`).
- Any change to a shape in Part 1 or the `Engine` signatures: tell B/C/D immediately.

---

## Part 2: Engine spec (source of truth for the agent)
Section numbers below are referenced by the prompts in Part 4 (e.g. "spec §8").

### 1. Purpose and scope
`engine/` is a pure, headless, deterministic discrete-event simulator of a hospital. It owns: patient generation, resource pools, the event loop, allocation, invariants, scripted/live scenarios, snapshots, and raw stats. It does NOT own: priority scoring (Person B, `strategies/`), HTTP/WebSocket (Person C, `api/`), UI (Person D, `frontend/`), and the optional ML models (`ml/`, plugged in via hooks).

**Core guarantee:** same seed + same config + same scripted actions + same strategy => byte-identical event log. This makes strategy comparison fair.

### 2. Repo layout
```
medflow/
├── AGENTS.md
├── README.md
├── docs/                 PERSON_A_MASTER.md (this file), ai-notes/
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

### 3. Conventions
- Time is an **int, seconds**. No float time. Service times are rounded to int seconds.
- Urgency: int 1..5, **1 = most critical**, 5 = non-urgent (ESI-style).
- Ids are ints assigned sequentially (patients from 1; units from 1 across all types). Ties always break by id.

### 4. Data model

#### ResourceType (enum)
`BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE` (AMBULANCE exists but no default bundle uses it in v1).

#### Unit
| field | notes |
|---|---|
| id | int, unique across all types |
| type | ResourceType |
| status | `FREE`, `OCCUPIED`, `FAILED`, `OFF` |
| owner | patient id or None (non-None iff OCCUPIED) |
| pending_off | bool, only ever true on an OCCUPIED unit (see set_capacity) |

`FAILED` = broken (fail_resource). `OFF` = unavailable through capacity/staff reduction. Neither can be allocated.

#### Patient
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

#### PatientView and StateView (what strategies see; frozen, read-only)
- `PatientView`: id, urgency, arrival_time, wait_s (at `now`), required, predicted_service_time, remaining_service, arrival_mode, department, interruptions.
- `StateView`: clock, free counts per type, total active counts per type, `waiting` (tuple of PatientView), in_treatment count, `flags` (e.g. arrival_multiplier).
Strategies must not mutate anything; the engine passes frozen copies so they cannot.

#### Default bundles *(placeholder; live in EngineConfig, never hardcoded in logic)*
| urgency | required | mean service |
|---|---|---|
| 1 | ICU_BED 1, DOCTOR 1, NURSE 2 (+ OR 1 with prob `or_probability[1]`) | 4 h |
| 2 | BED 1, DOCTOR 1, NURSE 1 (+ OR 1 with prob `or_probability[2]`) | 3 h |
| 3 | BED 1, DOCTOR 1, NURSE 1 | 2 h |
| 4 | BED 1, DOCTOR 1 | 1 h |
| 5 | DOCTOR 1 | 20 min |

Service times are sampled per patient (exponential or lognormal around the mean) by the seeded RNG. Default urgency mix *(placeholder)*: 5% / 15% / 30% / 30% / 20% for levels 1..5. Default capacities *(placeholder)*: BED 20, ICU_BED 4, OR 2, DOCTOR 8, NURSE 16, AMBULANCE 3.

### 5. Events
Kinds: `ARRIVAL, TREATMENT_DONE, FAILURE, RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END`.

Event = `(time, kind_rank, seq, kind, payload)`. `seq` is a strictly increasing counter assigned at push time. The heap orders by `(time, kind_rank, seq)`.

`kind_rank` (lower runs first at the same timestamp):
- 0: TREATMENT_DONE, RECOVERY (resources are released)
- 1: FAILURE, CAPACITY_CHANGE
- 2: SURGE_START, SURGE_END
- 3: ARRIVAL

**TREATMENT_DONE cancellation** uses lazy deletion: the event payload carries `(patient_id, token)`; the patient stores its current `token`. A popped TREATMENT_DONE whose token does not match (or whose patient is not IN_TREATMENT) is skipped silently.

### 6. Engine loop
`step()`:
1. If the heap is empty, return `[]` (clock does not advance).
2. Let `t` = smallest event time. Update utilization integrals from `clock` to `t` (before any state change), then set `clock = t`.
3. Loop: while the heap top has time == `t`, pop and apply it (handlers may push new events at `t`, e.g. surge arrivals; those are processed in the same loop, in heap order).
4. Run the allocation pass (section 7) exactly once.
5. If `debug_invariants`, call `assert_invariants`.
6. Return the log events (dicts) produced by this step.

`run_until(t)`: call `step()` while the heap is non-empty and the next event time <= t; then accumulate utilization up to `t` and set `clock = t`.

### 7. Allocation pass
1. Waiting patients = status WAITING.
2. Score each with `strategy(PatientView, StateView, now)`; higher = sooner.
3. Sort by `(-score, arrival_time, id)`.
4. For each patient in order, `try_reserve(patient.required, patient.id)`:
   - Success: units OCCUPIED (owner = patient id), patient IN_TREATMENT, `assigned` set, `start_time` set if None, new token, push TREATMENT_DONE at `now + remaining_service`, log `ASSIGNED`.
   - Failure and `hol_policy == "BACKFILL"`: continue to the next patient.
   - Failure and `hol_policy == "BLOCK"`: stop the pass.
5. One pass suffices (allocating only shrinks the free pool). Scores are recomputed each pass since waiting time changes.
6. After the pass, the `StateView` passed to the strategy must reflect allocations made earlier in the same pass (rebuild or update it as units are taken).

### 8. Atomic reservation and release
`try_reserve(bundle, patient_id) -> list[unit ids] | None`:
- For each type in the bundle (in enum order), pick the required number of FREE units with the lowest ids.
- If **any** type has too few: return None and leave state completely unchanged.
- Otherwise mark all picked units OCCUPIED with owner and return their ids.
No partial allocation may ever be observable outside this function.

`release(unit)`: owner = None; if `pending_off` then status OFF and `pending_off = False`, else FREE. (Used by treatment completion and interruption.)

### 9. Scenario hooks
Hooks never mutate state directly. They **enqueue an event at the current clock** (or a future time when scripted). Their effect applies on the next `step()`/`run_until()`. Live callers should call `run_until(clock)` right after a hook if they want the effect immediately.

- `inject_surge(multiplier, duration_s)`: enqueues SURGE_START now with payload `(multiplier, duration_s)`. On processing: set `flags.arrival_multiplier`, generate extra Poisson arrivals at rate `(multiplier - 1) * base_arrival_rate` from `now` to `now + duration_s` using `random.Random(f"{seed}:surge:{k}")` where `k` is the index of this surge (0, 1, ...), push them as ARRIVAL events (continuing patient ids from a shared counter), and push SURGE_END at `now + duration_s`. SURGE_END resets the flag and logs.
- `set_capacity(rtype, n)`: enqueues CAPACITY_CHANGE. `n` is clamped to `[0, total units of that type]`. Reducing: FREE units become OFF (highest ids first); if more must go, OCCUPIED units get `pending_off = True` (highest ids first) and go OFF on release. **Reductions never interrupt treatment.** Increasing: OFF units return to FREE (lowest ids first), clear `pending_off` on occupied units first, then allocation runs.
- `fail_resource(rid, duration_s)`: enqueues FAILURE; schedules RECOVERY at `now + duration_s`. Ignored (and logged) if the unit is already FAILED or OFF. If the unit was OCCUPIED, apply **P-FAIL**. On RECOVERY: status becomes FREE (or OFF if `pending_off`).
- `set_strategy(fn)`: takes effect at the next allocation pass.

**P-FAIL:** the interrupted patient releases *all* their units, returns to WAITING with `remaining_service -= (now - treatment_segment_start)`, keeps `arrival_time`, `interruptions += 1`, gets a new token (which cancels the pending TREATMENT_DONE), and logs `INTERRUPTED`. The failed unit becomes FAILED (not released to FREE).

**Scripted scenarios** (for fair comparison): the constructor accepts `scripted: list[ScriptedAction]` where `ScriptedAction = (time_s, action, args)` with action in `{"surge", "capacity", "fail"}`. Each is pushed to the heap at init as the same events the live hooks create, so scripted and live paths are identical code.

### 10. AI hooks
- `triage_fn: Callable[[Patient], int] | None`: applied once at ARRIVAL; returns a new urgency 1..5. Default: identity.
- `los_fn: Callable[[Patient], int] | None`: applied once at ARRIVAL; sets `predicted_service_time` only. It never changes `service_time`.
Both must be pure and deterministic given the patient. If a hook raises or returns an invalid value, the engine logs `HOOK_ERROR`, keeps the generator's value, and continues. The engine never crashes because of a hook.

### 11. Invariants (`assert_invariants(engine)`)
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

### 12. Public interface (do not change without telling B and C)

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

#### Log event schema
`{t, type, patient_id, units, note}`. Types: `ARRIVAL, ASSIGNED, DISCHARGED, INTERRUPTED, FAILURE, RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END, HOOK_ERROR`.

#### snapshot() schema (JSON-safe copies)
```
{ clock, strategy_name, hol_policy,
  queue: [ {id, urgency, wait_s, score, required} ],        # in the order the next pass would sort
  in_treatment: [ {id, urgency, start_time, ends_at, assigned} ],
  resources: { TYPE: {total, free, occupied, failed, off} },
  flags: { arrival_multiplier },
  recent_events: [ ...last 50 log dicts ] }
```

#### stats_raw()
```
{ patients: [ {id, urgency, arrival, start, end, interruptions, status} ],
  busy_s: {TYPE: int}, available_s: {TYPE: int},           # integrals; available excludes FAILED/OFF
  counts: {arrived, treated, waiting, in_treatment, interrupted} }
```
Utilization = busy_s / available_s (guard divide by zero). Person B turns these into displayed stats.

### 13. Decisions to confirm (Person A)
1. Default `hol_policy = BACKFILL` (agree with B).
2. P-FAIL policy (requeue with remaining time). Alternatives: restart from scratch, or move to another free unit.
3. Capacity reductions never interrupt treatment (lazy OFF).
4. Bundles, service times, urgency mix, capacities are placeholders.
5. Integer-seconds time is fine for B, C and D.
6. Scripted scenarios via `ScriptedAction` for comparisons (C must use this, never wall-clock, for compared runs).
7. Who owns the AI component (triage classifier / LOS predictor)? Hooks in section 10 exist for it.

### 14. Out of scope for v1
Multi-department routing (field only), ambulance transport modelling, persistence, any I/O.

---

## Part 3: `AGENTS.md` (paste into the repo root or your agent's rules location)

````markdown
# AGENTS.md: rules for the coding agent (MedFlow engine)

Read this file and `docs/PERSON_A_MASTER.md` before every task. Part 2 (the engine spec) is the source of truth; Part 1 defines what the other team members depend on.

## Scope
- Work only in `engine/`, `tests/engine/`, `scripts/`, and `ml/` (when a task says so). Do not touch `strategies/`, `api/`, or `frontend/`; they belong to teammates.
- Do NOT edit `docs/PERSON_A_MASTER.md`, this file, or any public interface signature. If the spec looks wrong, ambiguous, or contradictory, STOP and ask.

## Hard constraints (engine/)
- Python 3.11, **standard library only**. No new dependencies without asking.
- No `asyncio`, threads, network, file I/O, or database. `engine/` is a pure, headless, deterministic library.
- Determinism: never use `time.time()`, `datetime.now()`, the global `random` module, or `hash()` ordering. All randomness comes from `random.Random` instances seeded from the passed seed. Simulation time is an **int in seconds**. Never iterate a `set` where order affects behavior; sort by id.
- `snapshot()` returns plain JSON-safe copies only (dict, list, int, str, float, bool, None), never live objects.
- Keep it simple: no plugin systems, base-class hierarchies, or abstraction layers the spec does not ask for.

## Testing rules
- Write tests from the spec, not from your implementation. Test the behavior the spec states.
- **Never weaken, delete, skip, or rewrite an existing assertion to make a test pass.** If you think a test is wrong, say so and stop.
- Run `pytest tests/engine -q` before saying a task is done and paste the result. State clearly anything you could not verify.
- If `assert_invariants` fails, that is a bug in the implementation, not in the checker.

## Workflow per task
1. Restate the task in 2-3 lines and list the files you will change. If the change is larger than ~150 lines, present a plan and wait for approval.
2. Make the smallest change that satisfies the task.
3. Run the tests. Report pass/fail honestly.
4. Do not commit. The human reads the diff and commits.
5. When you finish, list any spec ambiguities you resolved yourself, so the human can confirm them.

## Style
- Type hints on all public functions. Dataclasses for records. Docstrings that say *why*, not *what*.
- Write allocation and event-ordering code plainly (no clever one-liners): a human must be able to explain it line by line to a judge.
- Save any plan or design notes you produce to `docs/ai-notes/` as markdown.
````

---

## Part 4: Agent prompts (run in order)


Flow for every step: paste the prompt, read the plan, let it implement, **read the diff yourself**, run `pytest tests/engine -q` yourself, then commit. Do not paste the next prompt until the current step is green and committed. Save any agent plans to `docs/ai-notes/`.

### Your schedule (24h plan, Person A)
| Hours | Goal |
|---|---|
| 0:00-0:30 | Team sync; confirm Part 2 §13 and the Part 1 contracts. Commit docs + AGENTS.md. |
| 0:30-1:30 | Prompt 0, Step A (tests), Step B (stubs). |
| 1:30-4:00 | Slices 1-3 (generator, resources, event loop + allocation). |
| 4:00 | **Checkpoint:** Slice 7 CLI harness passes 10k steps with invariants on. |
| 4:00-9:00 | Slices 4-6 (hooks, snapshot/stats, AI hooks). Support C/D integration. |
| 9:00 | Commit the safety-net prototype. |
| 10:00-13:00 | Bonus scenarios polish; Slice 8 (M/M/c); ICU/OR constraints check. |
| 13:00-15:00 | Sleep in shifts. |
| 15:00-20:00 | Bug bash with B; stress-test surges/failures; fix races. |
| 21:30+ | Demo video support, README AI-usage section, final commit. |

---

### Prompt 0: session start (paste at the start of every new agent session)
```
Read AGENTS.md and docs/PERSON_A_MASTER.md (Part 1 contracts and Part 2 spec) fully. Do not write
code yet. Summarize back in <=12 bullets: the constraints you must obey, the public
interface, the event ordering rule, the allocation pass, and the invariants. List
any ambiguity or contradiction you find in the spec. Do not fix them, only list them.
```

### Step A: tests first
```
Write the test suite for the engine from docs/PERSON_A_MASTER.md Part 2 ONLY (not from any
implementation). Create:
- tests/engine/test_invariants.py: property-style test running 10,000 steps across
  several seeds with debug_invariants=True; plus targeted unit tests for I1..I10.
- tests/engine/test_determinism.py: same seed/arrivals/strategy/scripted actions
  twice gives an identical event log; a different seed differs.
- tests/engine/test_reservation.py: a bundle needing more of one type than is free
  leaves EVERY unit unchanged (atomic rollback); successful reserve takes the
  lowest ids; release honors pending_off.
- tests/engine/test_ordering.py: a unit released at time t is usable by an arrival
  at time t; kind_rank ordering; events pushed at t during step t are processed
  in the same step; one allocation pass per step.
- tests/engine/test_policies.py: BACKFILL vs BLOCK with an ICU-blocked head
  patient; capacity reduction never interrupts treatment; failure interrupts and
  requeues with correct remaining_service, unchanged arrival_time, released units,
  cancelled TREATMENT_DONE (lazy deletion).
- tests/engine/test_snapshot.py: json.dumps(snapshot) works; mutating the snapshot
  does not change engine state; queue order matches the next allocation pass.
- tests/engine/test_hooks.py: triage_fn/los_fn defaults, override, raising hooks
  (HOOK_ERROR logged, simulation continues, service_time unchanged by los_fn).
- tests/engine/test_scenarios.py: scripted and live surges produce identical
  arrivals for the same seed; run_headless does not mutate the shared arrivals list.
Use small hand-constructed configs so expected values can be computed by hand.
Use a trivial FIFO strategy defined in the tests. The tests must currently FAIL
(nothing is implemented). Do not create any implementation beyond what imports need.
```
Read the assertions after this step. They are your definition of correct.

### Step B: stubs
```
Create importable stubs in engine/ (types.py, config.py, arrivals.py,
resources.py, engine.py, invariants.py, headless.py, __init__.py) with the
dataclasses, enums, and signatures from spec sections 4 and 12. Function bodies
raise NotImplementedError. Do not modify any test. Run pytest and confirm tests
fail for NotImplementedError, not import errors.
```

### Slice 1: config and arrival generator
```
Implement engine/config.py (EngineConfig with the placeholder defaults from spec
section 4, plus a default_config() helper) and engine/arrivals.py:
make_patient(rng, patient_id, t, config) and generate_arrivals(seed, config, horizon_s).
Poisson arrivals at base_arrival_rate patients/hour using random.Random(seed);
int-second times; sample urgency from urgency_mix, bundle (OR with probability),
service_time from mean_service_s; sequential ids; sorted by (arrival_time, id).
Add tests/engine/test_arrivals.py (same seed identical, different seed differs,
mean rate roughly matches over a long horizon with a stated tolerance).
Run pytest and report. Touch only these files.
```

### Slice 2: resource pool and atomic reservation
```
Implement engine/resources.py per spec section 8: ResourcePool built from
config.capacities (unit ids sequential across types in enum order), try_reserve
(check-then-commit, lowest free ids, returns None with zero state change on
failure), release (honors pending_off). Also capacity helpers used later by
set_capacity (count of free/occupied/failed/off per type). Make
tests/engine/test_reservation.py pass. Write the code plainly; I must be able to
explain try_reserve line by line. Run pytest and report.
```

### Slice 3: event heap, step loop, allocation pass
```
Implement in engine/engine.py per spec sections 5, 6 and 7: the heap ordered by
(time, kind_rank, seq), lazy deletion of TREATMENT_DONE via tokens, Engine.__init__
(pushes arrivals and scripted actions), step(), run_until(), the allocation pass
(score, sort by (-score, arrival_time, id), atomic reserve, BACKFILL/BLOCK),
utilization integral updates BEFORE state changes, the log event list, and
engine/invariants.py assert_invariants (I1..I10). Make test_ordering.py,
test_invariants.py and test_determinism.py pass (hooks and snapshot can wait).
Also implement engine/headless.py run_headless. Present a short plan first;
implement after I approve. Run pytest and report.
```
After this step, read `step()` and `try_reserve()` until you can explain them (judges will ask "how do you guarantee no double-booking?").

### Slice 4: scenario hooks
```
Implement spec section 9 in engine/engine.py: inject_surge, set_capacity,
fail_resource, set_strategy, the handlers for SURGE_START/SURGE_END,
CAPACITY_CHANGE, FAILURE, RECOVERY, and ScriptedAction scheduling (scripted and
live paths must share the same handlers). Exactly as specified: P-FAIL
interruption; lazy capacity reduction (FREE units OFF first, then pending_off on
occupied, never interrupt); surge RNG = random.Random(f"{seed}:surge:{k}");
failures on FAILED/OFF units are ignored and logged. Make test_policies.py and
test_scenarios.py pass. Run pytest with debug_invariants on and report.
```

### Slice 5: snapshot and stats_raw
```
Implement Engine.snapshot() and Engine.stats_raw() exactly per spec section 12
(schemas included). Snapshot: JSON-safe copies only, queue in next-pass order
with score, last 50 log events. stats_raw: per-type busy_s/available_s integrals
(available excludes FAILED/OFF), per-patient records, counts. Make
test_snapshot.py pass and add a test where utilization is hand-computed for a
tiny scenario. Run pytest and report.
```

### Slice 6: AI hooks
```
Implement triage_fn and los_fn handling at ARRIVAL per spec section 10, including
HOOK_ERROR fallback for exceptions and invalid values (urgency outside 1..5,
negative or non-int LOS). los_fn sets predicted_service_time only. Make
test_hooks.py pass. Run pytest and report.
```

### Slice 7: CLI harness (hour-4 checkpoint)
```
Create scripts/run_cli.py: builds default_config(), generates arrivals with a seed
from argv, defines a FIFO strategy (score = -arrival_time), runs the engine
through 10,000 steps with debug_invariants=True, prints a log tail and a
stats_raw summary (avg wait per urgency, utilization per type), and exits
non-zero on any invariant failure. Also add an option --strategy urgency that
uses score = (6 - urgency) * 1000 - arrival_time/1000 as a baseline.
```

### Slice 8 (optional): M/M/c sanity check
```
Add tests/engine/test_mmc_sanity.py: ONE resource type with c units, every
patient needing exactly one unit, exponential service, Poisson arrivals, FIFO,
long horizon, several seeds. Compare mean simulated wait against Erlang C and
assert agreement within a tolerance you justify from run length. If the engine
config cannot express this, stop and tell me what is missing; do NOT alter
engine logic to force a pass.
```

### Slice 9 (only if you take the AI component): `ml/`
Coordinate with the team first. Separate from `engine/`, so the engine stays stdlib-only.
```
In ml/, build the product's AI component (allowed deps: numpy, scikit-learn;
ask before adding others). Steps:
1. ml/synth.py: generate synthetic patient records (vitals, age, complaint
   category, optional short complaint text) using a seeded RNG. Data is created
   here during the hackathon; document the generating assumptions.
2. ml/triage.py: train a classifier predicting urgency 1..5 from features; expose
   triage_fn(patient) -> int reading patient.features. Include a real held-out
   evaluation (accuracy and a confusion matrix) in a script.
3. ml/los.py: train a regressor predicting service time in seconds from features;
   expose los_fn(patient) -> int.
Both functions must be deterministic and pure at inference. Persist trained
models to a file loaded at startup, plus a train script. No hardcoded lookup
tables pretending to be a model. Write ml/README.md describing the models, data,
and metrics honestly.
```

---

### Utility prompts

**Diff review before every commit**
```
Review my staged diff only against AGENTS.md and docs/PERSON_A_MASTER.md. Flag: spec
deviations, nondeterminism (global random, set order, wall-clock, float time),
weakened or deleted assertions, new dependencies, I/O or async in engine/, and
mutable state leaking through snapshot or strategy views. Do not edit files.
```

**Bug triage (a test fails)**
```
This test fails: <paste output>. Do not change any test. Explain the most likely
root cause in 3 sentences, name the exact function and line, then propose the
smallest fix. Wait for my approval before editing.
```

**Invariant stress run (bug bash)**
```
Write a script scripts/stress.py that runs 200 seeds x 20,000 steps with random
scripted surges, capacity cuts and resource failures at random simulated times
and debug_invariants=True, and prints the first failing seed with a minimal
event trace. Do not modify engine logic.
```

**Judge explainer**
```
Explain step() and try_reserve() as to a judge who asks "how do you guarantee
no double-booking and no partial allocation?" Cite the exact lines and the tests
that prove it. Under 200 words.
```

**README AI-usage section (fill the blanks)**
```
Write a README section "AI usage" with two parts: (1) Development: name the coding
assistant(s) and model(s) used and what they were used for; (2) Product AI
component: <triage classifier / length-of-stay predictor>, library or model,
data source, evaluation metrics. Use clear placeholders for anything I have not
told you. Do not invent facts.
```

---

## Part 5: Definition of done, checkpoints, integration checklist

### Definition of done (engine v1)
- [ ] `pytest tests/engine -q` passes; no test was weakened by the agent (check `git diff tests/`).
- [ ] 10k steps × several seeds with `debug_invariants=True` and zero invariant failures.
- [ ] Determinism test passes (identical logs for identical inputs).
- [ ] `scripts/run_cli.py` runs FIFO and urgency baselines and prints sensible stats.
- [ ] `snapshot()` output validates against the Part 1.3 shape and passes `json.dumps`.
- [ ] `run_headless` reuses one arrivals list across strategies without mutating it.
- [ ] Scenario hooks work live and via `scripted`: surge, capacity cut, resource failure (P-FAIL).
- [ ] Hooks `triage_fn` / `los_fn` tested, including failure fallback.
- [ ] You can explain `step()` and `try_reserve()` line by line.
- [ ] Optional: M/M/c sanity test passes; stress script (200 seeds × 20k steps) clean.

### Checkpoints
| Time | You should have |
|---|---|
| 0:30 | Part 2 §13 confirmed; sample JSON, TS types, Strategy signature shared |
| 4:00 | Slices 1-3 + CLI harness green; invariants clean over 10k steps |
| 9:00 | Hooks, snapshot, stats done; C and D integrated on real data; prototype committed |
| 13:00 | Bonus scenarios verified in the UI; M/M/c done |
| 20:00 | Stress suite clean; no known invariant failures |
| 22:30 | README sections for the engine and AI usage filled in |

### Integration checklist (with C, D, B)
- [ ] D renders the real snapshot with no shape changes from the mock.
- [ ] C's tick loop uses only `run_until` + `snapshot()` (no private engine access).
- [ ] Surge / staff shortage / failure buttons work end-to-end and the UI updates immediately.
- [ ] `/compare` uses one arrivals list, one seed, one `scripted` list for all strategies.
- [ ] B's strategies run against `PatientView`/`StateView` without mutating anything.
- [ ] AI hooks plugged in (or explicitly disabled) and documented in the README.
- [ ] Zero capacity violations shown in a stress run for the demo ("N steps, 0 violations").

### If you fall behind (cuts, in order)
1. Slice 8 (M/M/c), 2. multi-department field usage, 3. ambulance modelling, 4. resource failure polish. Never cut: atomic allocation, invariants, determinism, snapshot, scripted scenarios, `run_headless`.
