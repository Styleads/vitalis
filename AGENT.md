# AGENT.md — MedFlow

**Hospital Resource Management Simulator — Prioritize Patients, Optimize Resources**
**Event:** Hack-a-Matics 2026 · 24-hour build window (starts 19 Sep, 6:00 PM)

> **Single source of truth for the whole team.** This file merges:
> - the team-level hackathon plan (strategy, roles, timeline, demo script, bonus priority),
> - `PERSON_A_MASTER.md` (engine spec + agent rules + agent prompts),
> - Person B's implementation plan v2 (`strategies/`),
> - Person C's implementation plan (`api/`), expanded to full detail,
> - the contract decisions Person A standardized after the first review pass (§2).
>
> **Nothing from the source documents has been dropped.** Where a source was vague and has since been
> pinned down, the old wording is kept with a ⚠️ / ✅ note so no one is confused by a stale memory.

> **Timing note (rules compliance):** all *code* must be written inside the hackathon window. This file
> contains **no engine/API/strategy implementation code** — only design, contracts, signatures, and prompts.
> Generate implementation with your agent after the window opens. Commit this file and `AGENTS.md` once the
> window is open, or keep them out of the repo until then if you want to be extra safe.

---

## Table of contents

**Part I — Shared ground (everyone reads this)**
- 1. Strategy: what wins this
- 2. 🔒 Locked contract decisions (read before writing a line of code)
- 3. Team roles and ownership boundaries
- 4. Tech stack
- 5. Shared conventions (time, urgency, ids, resource types)
- 6. Data model / API contract
- 7. System data flow

**Part II — Person A: Engine & simulation core (`engine/`)**
- 8. Quick start and job in one page
- 9. Linking with C and D: sample snapshot, TS types, driving pattern, button map, gotchas
- 10. Engine spec (source of truth §1–§14)
- 11. `AGENTS.md` agent rules file
- 12. Agent prompts, in order, with schedule
- 13. Definition of done, checkpoints, integration checklist, cut order

**Part III — Person B: Scheduling strategies (`strategies/`)**
- 14. Mandate, contract, module architecture
- 15. Phased build plan (Phases 0–7)
- 16. Demo talking points and open items

**Part IV — Person C: API / integration layer (`api/`)**
- 17. Mandate and architecture
- 18. Tasks 1–8 (expanded)
- 19. Full endpoint reference
- 20. WebSocket protocol
- 21. Tick loop, scenario controls, demo seeding, integration testing
- 22. Phased build plan and open items

**Part V — Person D: Frontend dashboard (`frontend/`)**
- 23. Scope and components

**Part VI — Program level**
- 24. Unified hour-by-hour timeline
- 25. Bonus feature priority order
- 26. Demo video script
- 27. Correctness safety net
- 28. Repo layout
- 29. Open items register

---
---

# PART I — SHARED GROUND

## 1. Strategy: what wins this

Judges will score on: correctness of the scheduling logic, whether resource constraints are actually
respected (no double-booking a bed), how well urgency + waiting time trade off, quality of the live
dashboard, and whether you can *demonstrate* the bonus feature that's explicitly called out as most
interesting — **comparing scheduling strategies** (urgency-only vs. waiting-time-weighted vs.
utilization-aware).

That comparison feature is cheap to build (it's just swapping the priority function and re-running the same
simulation) and is the single highest-leverage bonus point, so **treat it as a core requirement, not a
stretch goal**.

Second highest leverage: a **surge mode** button and a **staff-shortage toggle** — both are trivial to
implement (they just perturb arrival rate / resource pool at runtime) but look extremely impressive live
because the dashboard visibly reacts.

**Core guarantee the engine gives the team:** same seed + same config + same scripted actions + same
strategy ⇒ byte-identical event log; no double-booking, no capacity violations, ever. This is what makes
strategy comparison *fair*, and it is the strongest single answer to a judge's hardest question.

---

## 2. 🔒 Locked contract decisions

These were open questions in the original per-person plans. **Person A has now standardized them.** They
are binding on B, C and D. The engine spec text in Part II has been updated to match.

### 2.1 `StateView` field names — LOCKED ✅

The original `ENGINE_SPEC` described these in prose only and did not lock exact attribute names
(Person B's plan flagged this with a ⚠️ and listed it as open item #1). **Resolved. Standardized on:**

| Field | Type | Meaning |
|---|---|---|
| `free_counts` | `dict[ResourceType, int]` | Units currently FREE (allocatable right now) per type |
| `active_capacities` | `dict[ResourceType, int]` | Total *active* units per type — i.e. `total − failed − off` |
| `clock` | `int` | Current simulated time, seconds |
| `flags` | `dict` | Runtime flags, e.g. `{"arrival_multiplier": 1.0}` |

Plus, as already specified: `waiting` (tuple of `PatientView`) and `in_treatment` (int count).

> **Migration note for B:** anywhere the v2 plan wrote `state.total_active[rtype]`, write
> `state.active_capacities[rtype]`. Anywhere it wrote `state.free[rtype]`, write `state.free_counts[rtype]`.
> B's open item "confirm the literal field names before writing `contention_penalty`" is now **closed**.

### 2.2 Import path — LOCKED ✅

`Patient`, `PatientView`, `StateView`, and `ResourceType` are all defined in and exported from
**`engine.types`**.

```python
from engine.types import Patient, PatientView, StateView, ResourceType
```

`engine/__init__.py` may re-export them for convenience, but `engine.types` is the canonical path and the
one B and C should import from. B must not import anything from `engine.engine`, `engine.resources`, or
`engine.invariants`.

### 2.3 HOL (head-of-line) policy — LOCKED ✅

**`hol_policy = "BACKFILL"` is the agreed default.** The engine will still support `"BLOCK"` as a
selectable alternative (it's useful to demo the contrast), but BACKFILL is what ships and what the demo
runs.

Rationale to state out loud to judges: BACKFILL is what prevents one ICU-blocked critical patient from
starving a free bed + doctor combo that a lower-priority patient could use *right now*. It's the difference
between a demo with good utilization numbers and one without. There is no scenario where BLOCK is
preferable for this problem.

> Spec §13 Decision #1 and Person B open item #2 are both **closed** by this.

### 2.4 Still open

See §29 for the live register (AI component ownership, `/compare` call shape, etc.).

---

## 3. Team roles and ownership boundaries

### Person A — Backend & Simulation Core (Python, `engine/`)
Owns the **engine**: a pure, headless, deterministic discrete-event hospital simulator that everyone else
plugs into.
- Patient arrival generator (Poisson process, configurable rate, surge multiplier)
- Resource pool class (beds, ICU beds, OR, doctors, nurses, ambulances) with atomic allocate/release
- Simulation loop (event-driven) that advances time, ages the queue, and re-runs allocation each tick
- Staff-shortage and resource-failure injection hooks
- Invariants (`assert_invariants`, I1–I10), `snapshot()`, `stats_raw()`, `run_headless()`
- **Does not own:** scoring strategies (B), FastAPI/WebSocket (C), React (D), ML models (`ml/`, owner TBD)

### Person B — Scheduling Algorithm & Priority Engine (Python, `strategies/`)
Owns the **brain**: pluggable, isolated, pure scoring functions.
- Urgency scoring model (triage-style, see §15 Phase 1)
- Three interchangeable strategy functions: `urgency_only`, `urgency_wait`, `urgency_wait_utilization`
- Statistics display layer: avg wait time, utilization %, patients-treated vs. waiting, strategy comparison
- **Does not own:** the event loop, atomic reservation, the allocation pass itself, the invariant checker,
  `snapshot()`. The priority-queue mechanics and tie-breaking are A's — B returns a float, that's it.

> **Scope correction (from B's plan v2):** the first draft of B's plan assumed B owned the whole scheduling
> engine — tick loop, atomic reservation, greedy allocation scan, invariant checker. `PERSON_A_MASTER`
> shows A's `engine/` already owns all of that. B's real surface is `Strategy = Callable[[PatientView,
> StateView, int], float]` — a pure scoring function — plus the stats display transform. Narrower than v1,
> not less rigorous. **This is a good division of labour:** A's guarantees (atomicity, no double-booking,
> determinism) hold *regardless* of what score B's function returns, so nothing B does can break a capacity
> invariant.

### Person C — API / Integration Layer (Python, `api/`)
Owns the **wiring** between engine and dashboard, and owns bonus-feature plumbing.
- FastAPI service exposing REST endpoints + a WebSocket for live ticks
- The wall-clock tick loop (asyncio) that drives `Engine.run_until()`
- Serializes simulation state to JSON each tick and pushes over WebSocket
- Scenario controls: surge, staff shortage, resource failure
- Strategy switching and the `/compare` endpoint
- Seeds demo scenarios (scripted patient batches for a reliable live demo, not pure randomness)
- End-to-end integration testing of the whole pipeline

### Person D — Frontend / Dashboard (React, `frontend/`)
Owns **everything the judges actually look at**. See Part V.

---

## 4. Tech stack

- **Backend engine:** Python 3.11, **standard library only** (`heapq` for the event heap). No asyncio, no
  I/O, no DB inside `engine/`.
- **API:** FastAPI + Pydantic, `asyncio` for the tick loop, WebSocket for push updates, `uvicorn` to serve.
- **Frontend:** React + TypeScript + Vite, Recharts or Chart.js for gauges/graphs, plain CSS or Tailwind.
- **Comms:** WebSocket (state broadcast every tick) + REST (control actions).
- **No database.** Simulation state lives in memory for the demo — saves hours, zero requirement for
  persistence.
- **Optional `ml/`:** numpy, scikit-learn (ask before adding others). Kept out of `engine/` so the engine
  stays stdlib-only.

---

## 5. Shared conventions (all layers must obey)

- **Time** is an **int, seconds of simulated time** (`clock`, `wait_s`, `start_time`, `ends_at`,
  `arrival_time`). **No float time.** Service times are rounded to int seconds. D formats for display as
  `HH:MM` or `Xh Ym`.
- **Urgency** is an int `1..5`, **1 = most critical**, 5 = non-urgent (ESI-style).
  Colors: 1 red, 2 orange, 3 yellow, 4 green, 5 blue/grey.
- **Resource type strings:** `BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE`.
- **Ids** are ints assigned sequentially — patients from 1; units from 1 across *all* types, in the enum
  order above. **Ties always break by id.**
- **Determinism:** never `time.time()`, `datetime.now()`, the global `random` module, or `hash()` ordering.
  All randomness comes from `random.Random` instances seeded from the passed seed. Never iterate a `set`
  where order affects behaviour; sort by id.

---

## 6. Data model / API contract

> Locked in the first 30 minutes — it *is* the API contract. Any change to a shape here or to an `Engine`
> signature must be told to B, C and D immediately.

Conceptual model (from the team plan):

```python
Patient:
  id, arrival_time, urgency_level (1-5), required_resources (list),
  status (waiting/assigned/treated/discharged), wait_time, assigned_resources

Resource:
  type (bed/icu_bed/or/doctor/nurse/ambulance), id, status (free/occupied),
  assigned_patient_id

SimulationState:
  clock, patient_queue, resource_pools (dict by type), stats, active_strategy, scenario_flags
```

The authoritative, implemented version of this model is the engine's — see §10.4 (`Patient`, `Unit`,
`PatientView`, `StateView`), §10.12 (`snapshot()`, `stats_raw()`, log events) and §9.3–9.4 (sample JSON +
TypeScript types). **When the two disagree, the engine spec wins.**

---

## 7. System data flow

```
frontend (D)  ⇄  api (C)  ⇄  engine (A)  ⇄  strategies (B) / ml hooks
   WebSocket: state each tick     Engine.run_until + snapshot()
   REST: controls, compare        hooks: inject_surge / set_capacity / fail_resource / set_strategy
```

```
React ──REST──▶ FastAPI ──▶ Simulation Service ──▶ Engine (A) ──▶ Strategy (B)
  ▲                                     │
  └──────────── WebSocket ◀─────────────┘   (snapshot broadcast every tick)
```

`engine/` never imports asyncio and never does I/O. **C runs the wall-clock tick loop and calls into A.**

---
---

# PART II — PERSON A: ENGINE & SIMULATION CORE

## 8. Quick start and your job in one page

### 8.1 Your job
Build `engine/`: a pure, headless, deterministic discrete-event hospital simulator that everyone else plugs
into.
- **You own:** patient generation, resource pools, event loop, atomic allocation, invariants, scenario
  hooks (surge / staff shortage / resource failure), `snapshot()`, `stats_raw()`, `run_headless()`.
- **You do not own:** scoring strategies (B, `strategies/`), FastAPI/WebSocket (C, `api/`), React
  (D, `frontend/`), ML models (`ml/`, owner TBD; plugs in through your two hooks).
- **Guarantee you give the team:** same seed + config + scripted actions + strategy ⇒ identical event log;
  no double-booking, no capacity violations, ever.

### 8.2 Order of work
1. **First 30 min (team sync):** confirm Part 2 §13 decisions (§10.13 here), give D the sample snapshot
   (§9.3), give B the `Strategy` signature, give C the driving pattern (§9.5). Decide who owns the AI
   component.
2. **Setup:** repo, folders, paste §11 into `AGENTS.md`, install Python 3.11 + pytest.
3. **Prompt 0 → Step A (tests) → Step B (stubs)**, then Slices 1–8 (§12). Read every diff; run pytest
   yourself.
4. **Hour-4 checkpoint:** CLI harness runs 10k steps with invariants on.
5. **Hours 4–9:** hooks, snapshot/stats, AI hooks; help C and D integrate.
6. **Hour 9:** safety-net prototype committed. Then bonus scenarios, M/M/c test, bug bash, README.

### 8.3 What the others need from you, and when
| To | What | When |
|---|---|---|
| D | Sample snapshot JSON + TS types (§9.3, §9.4) | Hour 0:30 |
| B | `Strategy` signature, `PatientView`/`StateView`, BACKFILL default | Hour 0:30 |
| C | Driving pattern, `run_headless`, `ScriptedAction` (§9.5–9.6) | Hour 0:30 |
| B + C + D | Working engine behind the same shapes | Hour 4:00 |
| Everyone | Merged prototype | Hour 9:00 |

---

## 9. Linking with C (API) and D (frontend)

### 9.1 Data flow
See §7. `engine/` never imports asyncio or does I/O. C runs the wall-clock tick loop and calls into you.

### 9.2 Conventions all layers must share
See §5.

### 9.3 Sample `snapshot()` — give this to D as `frontend/mock/snapshot.json`

Tiny demo config (not the defaults): BED 6, ICU_BED 1, OR 1, DOCTOR 2, NURSE 4, AMBULANCE 1.
Unit ids: BED 1–6, ICU_BED 7, OR 8, DOCTOR 9–10, NURSE 11–14, AMBULANCE 15.
Strategy is `urgency_wait` (score = base + wait bonus). Patient 14 (critical) is waiting because the only
ICU bed is taken; patients 9 and 12 are waiting because both doctors are busy.

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

### 9.4 TypeScript types for D

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

### 9.5 How C drives the engine (usage pattern, not implementation)

```python
from engine import Engine, generate_arrivals, run_headless
from engine.types import ResourceType

arrivals = generate_arrivals(seed, config, horizon_s)
eng = Engine(config, arrivals, strategy, seed, scripted=[], triage_fn=None, los_fn=None)

# wall-clock tick loop lives in api/ (asyncio), e.g. every 0.5 s:
eng.run_until(eng.clock + int(speed * dt))
await broadcast({"type": "state", "data": eng.snapshot()})

# demo buttons (see 9.7); effect applies on the next run_until:
eng.inject_surge(3.0, 3600)
eng.set_capacity(ResourceType.NURSE, 6)
eng.fail_resource(unit_id, 1800)
eng.set_strategy(other_strategy)
eng.run_until(eng.clock)          # apply immediately so the UI updates now
```

### 9.6 Strategy comparison (fair A/B)

Every compared run must share **the same arrivals list, seed, and scripted actions**:

```python
arrivals = generate_arrivals(seed, config, horizon_s)
scripted = [(3600, "surge", (3.0, 3600)), (7200, "capacity", (ResourceType.NURSE, 6)), (10800, "fail", (7, 1800))]
results = {name: run_headless(config, arrivals, strat, seed, until_s, scripted) for name, strat in strategies.items()}
```

`run_headless` deep-copies `arrivals`, so reuse the list. **Never trigger scenario events by wall-clock in
compared runs.** B turns each `stats_raw()` into displayed stats.

### 9.7 UI button → hook map

| Dashboard control | REST (C) | Engine call |
|---|---|---|
| Start / Pause / Speed | `/sim/start`, `/pause`, `/resume`, `/speed` | C's loop calls `run_until` |
| Trigger Surge | `POST /scenario/surge {multiplier, duration_s}` | `inject_surge` |
| Staff Shortage | `POST /scenario/capacity {type, n}` | `set_capacity` |
| Fail a Resource | `POST /scenario/fail {unit_id, duration_s}` | `fail_resource` |
| Strategy dropdown | `POST /strategy {name}` | `set_strategy` |
| Compare | `POST /compare {...}` | `run_headless` per strategy |

### 9.8 Integration gotchas to prevent
- Hooks take effect on the **next** `step()`/`run_until()`; call `run_until(clock)` after a hook.
- `snapshot()` returns copies; C can serialize it directly with `json.dumps`.
- Surges triggered live use the engine's RNG derived from the seed; only **scripted** ones are guaranteed
  identical across compared strategies (which is why compare uses `scripted`).
- Any change to a shape in Part II §9 or to the `Engine` signatures: **tell B/C/D immediately.**

---

## 10. Engine spec (source of truth for the agent)

Section numbers below are referenced by the prompts in §12 (e.g. "spec §8" = §10.8 here).

### 10.1 Purpose and scope
`engine/` is a pure, headless, deterministic discrete-event simulator of a hospital. It owns: patient
generation, resource pools, the event loop, allocation, invariants, scripted/live scenarios, snapshots, and
raw stats. It does NOT own: priority scoring (Person B, `strategies/`), HTTP/WebSocket (Person C, `api/`),
UI (Person D, `frontend/`), and the optional ML models (`ml/`, plugged in via hooks).

**Core guarantee:** same seed + same config + same scripted actions + same strategy ⇒ byte-identical event
log. This makes strategy comparison fair.

### 10.2 Repo layout
See §28.

### 10.3 Conventions
- Time is an **int, seconds**. No float time. Service times are rounded to int seconds.
- Urgency: int 1..5, **1 = most critical**, 5 = non-urgent (ESI-style).
- Ids are ints assigned sequentially (patients from 1; units from 1 across all types). Ties always break by id.

### 10.4 Data model

#### `ResourceType` (enum) — in `engine.types`
`BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE` (AMBULANCE exists but no default bundle uses it in v1).

#### `Unit`
| field | notes |
|---|---|
| id | int, unique across all types |
| type | ResourceType |
| status | `FREE`, `OCCUPIED`, `FAILED`, `OFF` |
| owner | patient id or None (non-None iff OCCUPIED) |
| pending_off | bool, only ever true on an OCCUPIED unit (see `set_capacity`) |

`FAILED` = broken (`fail_resource`). `OFF` = unavailable through capacity/staff reduction. **Neither can be
allocated.**

#### `Patient` — in `engine.types`
| field | notes |
|---|---|
| id, arrival_time | int, int seconds |
| urgency | int 1..5 (scheduler-facing; a triage hook may overwrite it at arrival) |
| required | `dict[ResourceType, int]`, the bundle |
| service_time | int seconds of treatment (the simulation's truth) |
| remaining_service | int seconds left (== service_time until interrupted) |
| predicted_service_time | `Optional[int]`, set by the ML length-of-stay hook; strategies may read it, the engine never uses it for timing |
| arrival_mode | `WALK_IN` or `AMBULANCE` |
| department | str, default `"general"` |
| features | dict, free-form (vitals, complaint text) for the AI component |
| status | `WAITING`, `IN_TREATMENT`, `DISCHARGED` |
| start_time, end_time | `Optional[int]` (start_time = first treatment start) |
| assigned | `list[unit ids]`, empty unless IN_TREATMENT |
| interruptions | int |
| segment_start | `Optional[int]`, when the current treatment segment began (used by P-FAIL) |
| token | int, bumped on every assignment/interruption (lazy deletion of TREATMENT_DONE) |

`wait_time(now) = (start_time if not None else now) - arrival_time`. **Interruptions never reset
`arrival_time`.**

#### `PatientView` and `StateView` (what strategies see; frozen, read-only) — in `engine.types`

**`PatientView`** — `id, urgency, arrival_time, wait_s` (at `now`)`, required, predicted_service_time,
remaining_service, arrival_mode, department, interruptions`.

**`StateView`** — 🔒 **field names locked per §2.1:**

| Field | Type | Meaning |
|---|---|---|
| `clock` | `int` | current simulated time in seconds |
| `free_counts` | `dict[ResourceType, int]` | FREE units per type |
| `active_capacities` | `dict[ResourceType, int]` | active units per type (`total − failed − off`) |
| `waiting` | `tuple[PatientView, ...]` | all currently waiting patients |
| `in_treatment` | `int` | count of patients currently in treatment |
| `flags` | `dict` | e.g. `{"arrival_multiplier": 1.0}` |

> *Superseded prose (kept for traceability):* the original spec said only "free counts per type, total
> active counts per type". Those are now literally `free_counts` and `active_capacities`.

Strategies must not mutate anything; the engine passes **frozen** copies so they cannot.

#### Default bundles *(placeholder; live in `EngineConfig`, never hardcoded in logic)*
| urgency | required | mean service |
|---|---|---|
| 1 | ICU_BED 1, DOCTOR 1, NURSE 2 (+ OR 1 with prob `or_probability[1]`) | 4 h |
| 2 | BED 1, DOCTOR 1, NURSE 1 (+ OR 1 with prob `or_probability[2]`) | 3 h |
| 3 | BED 1, DOCTOR 1, NURSE 1 | 2 h |
| 4 | BED 1, DOCTOR 1 | 1 h |
| 5 | DOCTOR 1 | 20 min |

Service times are sampled per patient (exponential or lognormal around the mean) by the seeded RNG.
Default urgency mix *(placeholder)*: 5% / 15% / 30% / 30% / 20% for levels 1..5.
Default capacities *(placeholder)*: BED 20, ICU_BED 4, OR 2, DOCTOR 8, NURSE 16, AMBULANCE 3.

### 10.5 Events
Kinds: `ARRIVAL, TREATMENT_DONE, FAILURE, RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END`.

Event = `(time, kind_rank, seq, kind, payload)`. `seq` is a strictly increasing counter assigned at push
time. The heap orders by `(time, kind_rank, seq)`.

`kind_rank` (lower runs first at the same timestamp):
- 0: TREATMENT_DONE, RECOVERY (resources are released)
- 1: FAILURE, CAPACITY_CHANGE
- 2: SURGE_START, SURGE_END
- 3: ARRIVAL

**TREATMENT_DONE cancellation** uses lazy deletion: the event payload carries `(patient_id, token)`; the
patient stores its current `token`. A popped TREATMENT_DONE whose token does not match (or whose patient is
not IN_TREATMENT) is skipped silently.

### 10.6 Engine loop
`step()`:
1. If the heap is empty, return `[]` (clock does not advance).
2. Let `t` = smallest event time. **Update utilization integrals from `clock` to `t` (before any state
   change)**, then set `clock = t`.
3. Loop: while the heap top has time == `t`, pop and apply it (handlers may push new events at `t`, e.g.
   surge arrivals; those are processed in the same loop, in heap order).
4. Run the allocation pass (§10.7) **exactly once**.
5. If `debug_invariants`, call `assert_invariants`.
6. Return the log events (dicts) produced by this step.

`run_until(t)`: call `step()` while the heap is non-empty and the next event time <= t; then accumulate
utilization up to `t` and set `clock = t`.

### 10.7 Allocation pass
1. Waiting patients = status WAITING.
2. Score each with `strategy(PatientView, StateView, now)`; **higher = sooner**.
3. Sort by `(-score, arrival_time, id)`.
4. For each patient in order, `try_reserve(patient.required, patient.id)`:
   - **Success:** units OCCUPIED (owner = patient id), patient IN_TREATMENT, `assigned` set, `start_time`
     set if None, new token, push TREATMENT_DONE at `now + remaining_service`, log `ASSIGNED`.
   - **Failure and `hol_policy == "BACKFILL"`** (the default, §2.3): continue to the next patient.
   - **Failure and `hol_policy == "BLOCK"`:** stop the pass.
5. One pass suffices (allocating only shrinks the free pool). Scores are recomputed each pass since waiting
   time changes.
6. After the pass, the `StateView` passed to the strategy must reflect allocations made earlier **in the
   same pass** (rebuild or update it as units are taken).

### 10.8 Atomic reservation and release
`try_reserve(bundle, patient_id) -> list[unit ids] | None`:
- For each type in the bundle (in enum order), pick the required number of FREE units with the lowest ids.
- If **any** type has too few: return None and leave state **completely unchanged**.
- Otherwise mark all picked units OCCUPIED with owner and return their ids.

**No partial allocation may ever be observable outside this function.**

`release(unit)`: owner = None; if `pending_off` then status OFF and `pending_off = False`, else FREE.
(Used by treatment completion and interruption.)

### 10.9 Scenario hooks
Hooks never mutate state directly. They **enqueue an event at the current clock** (or a future time when
scripted). Their effect applies on the next `step()`/`run_until()`. Live callers should call
`run_until(clock)` right after a hook if they want the effect immediately.

- **`inject_surge(multiplier, duration_s)`** — enqueues SURGE_START now with payload
  `(multiplier, duration_s)`. On processing: set `flags.arrival_multiplier`, generate extra Poisson arrivals
  at rate `(multiplier - 1) * base_arrival_rate` from `now` to `now + duration_s` using
  `random.Random(f"{seed}:surge:{k}")` where `k` is the index of this surge (0, 1, ...), push them as
  ARRIVAL events (continuing patient ids from a shared counter), and push SURGE_END at
  `now + duration_s`. SURGE_END resets the flag and logs.
- **`set_capacity(rtype, n)`** — enqueues CAPACITY_CHANGE. `n` is clamped to `[0, total units of that
  type]`. **Reducing:** FREE units become OFF (highest ids first); if more must go, OCCUPIED units get
  `pending_off = True` (highest ids first) and go OFF on release. **Reductions never interrupt treatment.**
  **Increasing:** OFF units return to FREE (lowest ids first), clear `pending_off` on occupied units first,
  then allocation runs.
- **`fail_resource(rid, duration_s)`** — enqueues FAILURE; schedules RECOVERY at `now + duration_s`.
  Ignored (and logged) if the unit is already FAILED or OFF. If the unit was OCCUPIED, apply **P-FAIL**.
  On RECOVERY: status becomes FREE (or OFF if `pending_off`).
- **`set_strategy(fn)`** — takes effect at the next allocation pass.

**P-FAIL:** the interrupted patient releases *all* their units, returns to WAITING with
`remaining_service -= (now - treatment_segment_start)`, keeps `arrival_time`, `interruptions += 1`, gets a
new token (which cancels the pending TREATMENT_DONE), and logs `INTERRUPTED`. The failed unit becomes
FAILED (not released to FREE).

**Scripted scenarios** (for fair comparison): the constructor accepts `scripted: list[ScriptedAction]` where
`ScriptedAction = (time_s, action, args)` with action in `{"surge", "capacity", "fail"}`. Each is pushed to
the heap at init as the *same events* the live hooks create, so scripted and live paths are identical code.

### 10.10 AI hooks
- `triage_fn: Callable[[Patient], int] | None` — applied once at ARRIVAL; returns a new urgency 1..5.
  Default: identity.
- `los_fn: Callable[[Patient], int] | None` — applied once at ARRIVAL; sets `predicted_service_time` only.
  **It never changes `service_time`.**

Both must be pure and deterministic given the patient. If a hook raises or returns an invalid value, the
engine logs `HOOK_ERROR`, keeps the generator's value, and continues. **The engine never crashes because of
a hook.**

### 10.11 Invariants (`assert_invariants(engine)`)
Run after every step in debug mode and in the test suite.
- **I1.** A unit is OCCUPIED iff `owner` is not None.
- **I2.** No unit id appears in two patients' `assigned` lists.
- **I3.** Per type: occupied + free + failed + off == total units.
- **I4.** A FAILED or OFF unit never has an owner.
- **I5.** Every IN_TREATMENT patient's `assigned` satisfies its full `required` bundle (right types and counts).
- **I6.** Every IN_TREATMENT patient has exactly one valid (non-cancelled) pending TREATMENT_DONE; WAITING
  and DISCHARGED patients have none.
- **I7.** `clock` never decreases; every pushed event time >= clock.
- **I8.** DISCHARGED patients hold no units.
- **I9.** `pending_off` is only true on OCCUPIED units.
- **I10.** `0 <= remaining_service <= service_time` for all patients.

### 10.12 Public interface (do not change without telling B and C)

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
    hol_policy: str = "BACKFILL"                      # or "BLOCK"   (§2.3: BACKFILL is the agreed default)
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

**Type import path (§2.2):** `Patient`, `PatientView`, `StateView`, `ResourceType` all live in and are
exported from `engine.types`.

#### Log event schema
`{t, type, patient_id, units, note}`. Types: `ARRIVAL, ASSIGNED, DISCHARGED, INTERRUPTED, FAILURE,
RECOVERY, CAPACITY_CHANGE, SURGE_START, SURGE_END, HOOK_ERROR`.

#### `snapshot()` schema (JSON-safe copies)
```
{ clock, strategy_name, hol_policy,
  queue: [ {id, urgency, wait_s, score, required} ],        # in the order the next pass would sort
  in_treatment: [ {id, urgency, start_time, ends_at, assigned} ],
  resources: { TYPE: {total, free, occupied, failed, off} },
  flags: { arrival_multiplier },
  recent_events: [ ...last 50 log dicts ] }
```

#### `stats_raw()` schema
```
{ patients: [ {id, urgency, arrival, start, end, interruptions, status} ],
  busy_s: {TYPE: int}, available_s: {TYPE: int},           # integrals; available excludes FAILED/OFF
  counts: {arrived, treated, waiting, in_treatment, interrupted} }
```
Utilization = `busy_s / available_s` (guard divide by zero). **Person B turns these into displayed stats.**

### 10.13 Decisions to confirm (Person A)
1. ✅ **CLOSED —** Default `hol_policy = BACKFILL` (agreed with B; see §2.3). BLOCK stays supported as the
   alternative.
2. **P-FAIL policy** (requeue with remaining time). Alternatives considered: restart from scratch, or move
   to another free unit. *Current choice: requeue with remaining time.*
3. **Capacity reductions never interrupt treatment** (lazy OFF).
4. Bundles, service times, urgency mix, capacities are **placeholders**.
5. Integer-seconds time is fine for B, C and D.
6. Scripted scenarios via `ScriptedAction` for comparisons (**C must use this, never wall-clock, for
   compared runs**).
7. ⏳ **OPEN —** Who owns the AI component (triage classifier / LOS predictor)? Hooks in §10.10 exist for it.

### 10.14 Out of scope for v1
Multi-department routing (field only), ambulance transport modelling, persistence, any I/O.

---

## 11. `AGENTS.md` — rules for the coding agent

Paste the block below into the repo root as `AGENTS.md` (or your agent's rules location).

````markdown
# AGENTS.md: rules for the coding agent (MedFlow engine)

Read this file and `docs/AGENT.md` before every task. Part II §10 (the engine spec) is the source of
truth; Part II §9 defines what the other team members depend on.

## Scope
- Work only in `engine/`, `tests/engine/`, `scripts/`, and `ml/` (when a task says so). Do not touch
  `strategies/`, `api/`, or `frontend/`; they belong to teammates.
- Do NOT edit `docs/AGENT.md`, this file, or any public interface signature. If the spec looks wrong,
  ambiguous, or contradictory, STOP and ask.

## Hard constraints (engine/)
- Python 3.11, **standard library only**. No new dependencies without asking.
- No `asyncio`, threads, network, file I/O, or database. `engine/` is a pure, headless, deterministic
  library.
- Determinism: never use `time.time()`, `datetime.now()`, the global `random` module, or `hash()`
  ordering. All randomness comes from `random.Random` instances seeded from the passed seed. Simulation
  time is an **int in seconds**. Never iterate a `set` where order affects behavior; sort by id.
- `snapshot()` returns plain JSON-safe copies only (dict, list, int, str, float, bool, None), never live
  objects.
- Keep it simple: no plugin systems, base-class hierarchies, or abstraction layers the spec does not ask
  for.

## Testing rules
- Write tests from the spec, not from your implementation. Test the behavior the spec states.
- **Never weaken, delete, skip, or rewrite an existing assertion to make a test pass.** If you think a
  test is wrong, say so and stop.
- Run `pytest tests/engine -q` before saying a task is done and paste the result. State clearly anything
  you could not verify.
- If `assert_invariants` fails, that is a bug in the implementation, not in the checker.

## Workflow per task
1. Restate the task in 2-3 lines and list the files you will change. If the change is larger than ~150
   lines, present a plan and wait for approval.
2. Make the smallest change that satisfies the task.
3. Run the tests. Report pass/fail honestly.
4. Do not commit. The human reads the diff and commits.
5. When you finish, list any spec ambiguities you resolved yourself, so the human can confirm them.

## Style
- Type hints on all public functions. Dataclasses for records. Docstrings that say *why*, not *what*.
- Write allocation and event-ordering code plainly (no clever one-liners): a human must be able to explain
  it line by line to a judge.
- Save any plan or design notes you produce to `docs/ai-notes/` as markdown.
````

---

## 12. Agent prompts (run in order)

Flow for every step: paste the prompt, read the plan, let it implement, **read the diff yourself**, run
`pytest tests/engine -q` yourself, then commit. Do not paste the next prompt until the current step is
green and committed. Save any agent plans to `docs/ai-notes/`.

### 12.1 Person A's schedule (24h)
| Hours | Goal |
|---|---|
| 0:00-0:30 | Team sync; confirm §10.13 and the §9 contracts. Commit docs + AGENTS.md. |
| 0:30-1:30 | Prompt 0, Step A (tests), Step B (stubs). |
| 1:30-4:00 | Slices 1-3 (generator, resources, event loop + allocation). |
| 4:00 | **Checkpoint:** Slice 7 CLI harness passes 10k steps with invariants on. |
| 4:00-9:00 | Slices 4-6 (hooks, snapshot/stats, AI hooks). Support C/D integration. |
| 9:00 | Commit the safety-net prototype. |
| 10:00-13:00 | Bonus scenarios polish; Slice 8 (M/M/c); ICU/OR constraints check. |
| 13:00-15:00 | Sleep in shifts. |
| 15:00-20:00 | Bug bash with B; stress-test surges/failures; fix races. |
| 21:30+ | Demo video support, README AI-usage section, final commit. |

### Prompt 0: session start (paste at the start of every new agent session)
```
Read AGENTS.md and docs/AGENT.md (Part II §9 contracts and §10 spec) fully. Do not write
code yet. Summarize back in <=12 bullets: the constraints you must obey, the public
interface, the event ordering rule, the allocation pass, and the invariants. List
any ambiguity or contradiction you find in the spec. Do not fix them, only list them.
```

### Step A: tests first
```
Write the test suite for the engine from docs/AGENT.md Part II §10 ONLY (not from any
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
Read the assertions after this step. **They are your definition of correct.**

### Step B: stubs
```
Create importable stubs in engine/ (types.py, config.py, arrivals.py,
resources.py, engine.py, invariants.py, headless.py, __init__.py) with the
dataclasses, enums, and signatures from spec sections 4 and 12. Patient,
PatientView, StateView and ResourceType must all live in engine/types.py and be
exported from there. StateView fields are exactly: clock, free_counts,
active_capacities, waiting, in_treatment, flags. Function bodies raise
NotImplementedError. Do not modify any test. Run pytest and confirm tests fail for
NotImplementedError, not import errors.
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
After this step, read `step()` and `try_reserve()` until you can explain them (judges will ask "how do you
guarantee no double-booking?").

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

### 12.2 Utility prompts

**Diff review before every commit**
```
Review my staged diff only against AGENTS.md and docs/AGENT.md. Flag: spec
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

## 13. Definition of done, checkpoints, integration checklist (Person A)

### 13.1 Definition of done (engine v1)
- [ ] `pytest tests/engine -q` passes; no test was weakened by the agent (check `git diff tests/`).
- [ ] 10k steps × several seeds with `debug_invariants=True` and zero invariant failures.
- [ ] Determinism test passes (identical logs for identical inputs).
- [ ] `scripts/run_cli.py` runs FIFO and urgency baselines and prints sensible stats.
- [ ] `snapshot()` output validates against the §9.3 shape and passes `json.dumps`.
- [ ] `run_headless` reuses one arrivals list across strategies without mutating it.
- [ ] Scenario hooks work live and via `scripted`: surge, capacity cut, resource failure (P-FAIL).
- [ ] Hooks `triage_fn` / `los_fn` tested, including failure fallback.
- [ ] You can explain `step()` and `try_reserve()` line by line.
- [ ] Optional: M/M/c sanity test passes; stress script (200 seeds × 20k steps) clean.

### 13.2 Checkpoints
| Time | You should have |
|---|---|
| 0:30 | §10.13 confirmed; sample JSON, TS types, Strategy signature shared |
| 4:00 | Slices 1-3 + CLI harness green; invariants clean over 10k steps |
| 9:00 | Hooks, snapshot, stats done; C and D integrated on real data; prototype committed |
| 13:00 | Bonus scenarios verified in the UI; M/M/c done |
| 20:00 | Stress suite clean; no known invariant failures |
| 22:30 | README sections for the engine and AI usage filled in |

### 13.3 Integration checklist (with C, D, B)
- [ ] D renders the real snapshot with no shape changes from the mock.
- [ ] C's tick loop uses only `run_until` + `snapshot()` (no private engine access).
- [ ] Surge / staff shortage / failure buttons work end-to-end and the UI updates immediately.
- [ ] `/compare` uses one arrivals list, one seed, one `scripted` list for all strategies.
- [ ] B's strategies run against `PatientView`/`StateView` without mutating anything.
- [ ] AI hooks plugged in (or explicitly disabled) and documented in the README.
- [ ] Zero capacity violations shown in a stress run for the demo ("N steps, 0 violations").

### 13.4 If you fall behind (cuts, in order)
1. Slice 8 (M/M/c)
2. Multi-department field usage
3. Ambulance modelling
4. Resource failure polish

**Never cut:** atomic allocation, invariants, determinism, snapshot, scripted scenarios, `run_headless`.

---
---

# PART III — PERSON B: SCHEDULING STRATEGIES (`strategies/`)

> *(Person B implementation plan v2 — conforms to Part II. Updated to the locked decisions in §2.)*

## 14. Mandate, contract, module architecture

### 14.1 What changed from B's v1 plan, and why

The first draft assumed B owned the whole scheduling engine — the tick loop, atomic resource reservation,
the greedy allocation scan, and the invariant checker. Part II shows Person A's `engine/` already owns all
of that. B's actual surface area is much smaller and much more precisely specified than v1 assumed:

> `Strategy = Callable[[PatientView, StateView, int], float]` — a pure scoring function. That's it.

This version is scoped exactly to that contract. It's **narrower than v1, not less rigorous** — the goal is
still the best possible scoring design, just without re-building machinery A has already specced, tested,
and locked.

### 14.2 Your actual mandate

**You own:**
- `strategies/` — the scoring functions matching the `Strategy` type
- Turning `Engine.stats_raw()` into the displayed/comparison stats ("B turns each `stats_raw()` into
  displayed stats" — §9.6, §10.12)

**You explicitly do not own** (all owned by Person A's `engine/`):
- The event loop, `step()`, `run_until()`
- Atomic reservation (`try_reserve`) and the resource pool
- The allocation pass itself — sorting by `(-score, arrival_time, id)` and the BACKFILL/BLOCK continuation
  policy are already implemented in `engine.py` (§10.7)
- `assert_invariants` / I1–I10 — fully owned and tested by A
- `snapshot()` — A's job; you never touch engine state directly

This is a good division of labor: A's guarantees (atomicity, no double-booking, determinism) hold
*regardless* of what score your function returns, so your entire job is to return good numbers from a pure
function — **nothing you do can break a capacity invariant.**

### 14.3 The contract you're building against

Quoted directly from Part II so there's no drift between this section and the source of truth. If any of
this looks wrong at the Hour 0:30 sync, raise it then — don't silently assume.

```python
from engine.types import PatientView, StateView, ResourceType   # 🔒 locked import path, §2.2

Strategy = Callable[[PatientView, StateView, int], float]   # higher score = sooner
```

**`PatientView`** (frozen, read-only): `id, urgency, arrival_time, wait_s` (at `now`)`, required,
predicted_service_time, remaining_service, arrival_mode, department, interruptions`

**`StateView`** (frozen, read-only) — 🔒 **field names now locked (§2.1)**:
`clock`, `free_counts`, `active_capacities`, `waiting` (tuple of `PatientView`), `in_treatment` (count),
`flags`.

> ✅ *Resolved.* The v2 plan carried a ⚠️ here: "Exact attribute names for the per-type count dicts aren't
> shown as code in the spec, only described in prose. Confirm the literal field names with A at the Hour
> 0:30 sync — don't guess and hardcode something that silently `KeyError`s or (worse) silently returns 0
> everywhere." A has now fixed them as `free_counts` / `active_capacities`. **Use those names; no guessing
> required.**

**Already handled by the Engine — do not re-implement:**
- **Tie-breaking:** sort is `(-score, arrival_time, id)`. Your function only needs to return a float; the
  Engine breaks ties.
- **Continue-past-a-blocked-patient behavior:** this is the `hol_policy`. ✅ **BACKFILL is confirmed as the
  default (§2.3)**; BLOCK remains available as an alternative. (§10.13 Decision #1 asked B to explicitly
  agree to BACKFILL — that sign-off is now given.)
- **Atomicity:** `try_reserve` is all-or-nothing across the full bundle. You never see partial allocations.

**Rules that bind your code specifically:**
- Time is **int seconds**, never float. `now` is passed as `int`.
- `PatientView`/`StateView` are frozen — your functions must not attempt to mutate them (nothing to enforce
  on your end since they're frozen copies, but write tests confirming your code never tries).
- **Determinism:** no `time.time()`, no global `random` module. If a strategy ever needs randomness (it
  shouldn't for v1), it must take a seeded `random.Random` explicitly — flag this with A before doing it,
  since it changes the `Strategy` signature.
- `stats_raw()` schema (what you consume for the comparison layer):
  ```
  { patients: [ {id, urgency, arrival, start, end, interruptions, status} ],
    busy_s: {TYPE: int}, available_s: {TYPE: int},
    counts: {arrived, treated, waiting, in_treatment, interrupted} }
  ```
  Utilization per type = `busy_s[TYPE] / available_s[TYPE]` (**guard divide-by-zero** — a type can have
  `available_s == 0` if it was fully OFF/FAILED for the whole run).

### 14.4 Module architecture

```
strategies/
  __init__.py              # STRATEGIES: dict[str, Strategy], get_strategy(name)
  scoring.py               # base_urgency(), wait_bonus(), contention_penalty() — pure math
  urgency_only.py
  urgency_wait.py
  urgency_wait_utilization.py
  stats_display.py         # stats_raw() -> DisplayStats; compare_strategies(results)
  tuning.py                # optional Phase 7: parameter sweep harness
tests/strategies/
  test_scoring.py
  test_strategies.py       # hand-computed expected scores, per A's testing philosophy
  test_determinism.py      # same inputs -> same output, always
  test_stats_display.py
```

Keep every file in `strategies/` free of any import from `engine.engine`, `engine.resources`, or
`engine.invariants` — **you should only ever import the frozen view types from `engine.types`** (§2.2) and
stdlib. If you find yourself importing anything stateful from `engine/`, stop — that's a sign you've
drifted back into v1's scope.

---

## 15. Phased build plan (Person B)

### Phase 0 — Contract intake & sign-off — *0:00–0:30 (team sync)*
- Get the `Strategy` signature, `PatientView`/`StateView` shapes, and the BACKFILL default from A directly
  (they've committed to delivering this at 0:30 — §8.3).
- **Explicitly answer §10.13 Decision #1:** agree `hol_policy = BACKFILL`. ✅ *Done — see §2.3.* Rationale
  to state out loud: BACKFILL is what prevents one ICU-blocked critical patient from starving a free bed +
  doctor combo a lower-priority patient could use right now — it's the difference between a demo with good
  utilization numbers and one without. There's no scenario where `BLOCK` is preferable for this problem, so
  this should be a fast yes.
- Confirm the literal `StateView` attribute names. ✅ *Done — `free_counts`, `active_capacities` (§2.1).*
  This was the one place a wrong guess would have cost real debugging time later.
- Confirm the import path. ✅ *Done — `engine.types` (§2.2).*

### Phase 1 — Core scoring primitives — *0:30–1:30*
Pure, dependency-free, unit-testable before anything else exists.

```python
def base_urgency(urgency: int) -> float:
    return {1: 100.0, 2: 80.0, 3: 60.0, 4: 40.0, 5: 20.0}[urgency]

def wait_bonus(wait_s: int, weight_per_min: float = 0.5, cap: float = 40.0) -> float:
    return min((wait_s / 60.0) * weight_per_min, cap)
```

- **Use `patient_view.wait_s` directly** — it's already computed by the Engine as `wait_time(now)`. Do not
  recompute it yourself from `arrival_time` and `now`; that's a second source of truth for the same number
  and a guaranteed source of subtle drift bugs if the Engine's definition ever changes (e.g. if it later
  accounts for `interruptions` differently).
- Pick `cap` so wait-time can never let a stale Level-5 outrank a fresh Level-1
  (`base_urgency(5) + cap < base_urgency(1)` must hold — with the numbers above, `20 + 40 = 60 < 100`,
  safe). **Write this as an explicit unit test, not just a comment** — it's the answer to "could a paper cut
  jump the queue over a heart attack?" and you want it enforced, not just asserted in prose.
- Test **monotonicity**: `wait_bonus` never decreases as `wait_s` increases, up to the cap.

### Phase 2 — Strategies 1 & 2 — *1:30–2:30*

```python
def urgency_only(p: PatientView, s: StateView, now: int) -> float:
    return base_urgency(p.urgency)

def urgency_wait(p: PatientView, s: StateView, now: int) -> float:
    return base_urgency(p.urgency) + wait_bonus(p.wait_s)
```

- `urgency_only` is **deliberately the "bad" baseline** — its whole purpose is to visibly starve
  low-urgency patients in the comparison view later. Don't be tempted to "improve" it; the contrast is the
  point.
- `urgency_wait` is your **recommended default** — matches the sample `snapshot()` in the spec
  (`strategy_name: "urgency_wait"`), so this is almost certainly what the demo runs by default.

### Phase 3 — Strategy 3: utilization-aware — *2:30–4:00*

The one genuinely interesting algorithmic decision left in your scope. Because `Strategy` must return a
single `float` (not a tuple, not a secondary sort key — that was a v1 mistake), fold contention into the
additive score directly:

```python
def contention_penalty(required: dict, state: StateView,
                       weight: float = 10.0, threshold: float = 0.8) -> float:
    penalty = 0.0
    for rtype, qty in required.items():
        total = state.active_capacities[rtype]   # 🔒 locked field name, §2.1
        free  = state.free_counts[rtype]         # 🔒 locked field name, §2.1
        if total <= 0:
            continue
        occupancy = 1.0 - (free / total)
        if occupancy >= threshold:
            penalty += weight * (occupancy - threshold)
    return penalty

def urgency_wait_utilization(p: PatientView, s: StateView, now: int) -> float:
    return base_urgency(p.urgency) + wait_bonus(p.wait_s) - contention_penalty(p.required, s)
```

- This nudges patients requesting an already-contended resource type slightly behind otherwise-equal
  patients requesting less-contended ones, spreading load **without ever inverting a genuine urgency gap**
  (the penalty is bounded and small relative to `base_urgency`'s step size — **verify this bound explicitly
  in a test**: no combination of `contention_penalty` should let a Level-3 outrank a Level-1 that arrived
  at the same time).
- **Do not** use `predicted_service_time` to deprioritize patients with long expected treatment (a tempting
  "efficiency" lever). It reads as the algorithm punishing sicker patients for being sicker, which is both
  a bad look in a demo and a real fairness problem. Leave it unused in the three required strategies; if
  you want to experiment with it, do so as a clearly-labeled *fourth, optional* strategy in Phase 7, never
  the default.

### Phase 4 — Correctness & determinism test suite — *4:00–6:00*
You don't own invariants (A does), but you own correctness of the math:
- Hand-computed expected scores for small fixed inputs, matching A's own testing philosophy ("use small
  hand-constructed configs so expected values can be computed by hand" — mirror that discipline here)
- **Determinism:** same `(PatientView, StateView, now)` in ⇒ identical float out, every call, no hidden
  state
- The clinical-plausibility bound from Phase 1 (fresh critical always beats stale non-urgent) as an
  explicit **property** test, not just a fixed example
- A test that each strategy function never raises on the full range of valid `urgency` (1–5) and on
  `required` bundles with zero, one, and multiple resource types

### Phase 5 — Stats display & comparison layer — *6:00–8:00 (build), integrate live ~9:00*

A's `stats_raw()` won't exist as real, callable output until their Slices 4–6 land (~hour 9, per their own
schedule). **Don't block on that** — build against the **documented schema** now (§14.3) using
hand-constructed fixture dicts shaped exactly like it, then swap in the real thing at the Hour 9
integration checkpoint.

```python
def to_display_stats(raw: dict) -> dict:
    # avg/p95 wait per urgency level, utilization % per type (busy_s/available_s, guarded),
    # patients_treated, patients_waiting, interrupted count
    ...

def compare_strategies(results: dict[str, dict]) -> dict:
    # results = {strategy_name: stats_raw()} from run_headless() calls (A's function,
    # likely invoked by C's /compare endpoint) over the SAME arrivals/seed/scripted actions
    # — diff avg wait, utilization, and starvation indicators across strategies
    ...
```

- `run_headless` is **A's function** and the comparison call is likely triggered from **C's API layer** —
  your contribution is the `dict[str, dict] -> comparison view` transform, not the replay execution itself.
- This is what feeds the "Compare Strategies" chart in the dashboard and the numbers you'll say out loud in
  the demo (§26).

### Phase 6 — Integration checkpoints
Align to the team's existing checkpoint table rather than inventing your own:
- **0:30** — contract received from A, BACKFILL sign-off given
- **4:00** — all three strategies implemented and unit-tested against fixture data (real engine not
  required yet)
- **9:00** — swap fixtures for A's real `PatientView`/`StateView`/`stats_raw()`; confirm
  `strategies.STRATEGIES` registry is what C's `/strategy` endpoint calls into for `set_strategy`
- **13:00** — Phase 7 stretch items, if ahead
- **20:00** — join A+C's bug-bash window; **most real bugs live at the Engine↔Strategy boundary** (wrong
  field names, unit mismatches), not inside your pure functions

### Phase 7 — Stretch (only if ahead of schedule, 9:00–13:00)
In order; stop the moment you're back-scheduled:
1. **Parameter tuning harness** (`tuning.py`): sweep `weight_per_min` / `cap` / contention `weight` across
   seeds using `run_headless` (A's function, called read-only — you're not modifying the Engine) and pick
   defaults empirically rather than by feel. *"We grid-searched these constants against 50 simulated runs"*
   is a strong line to have.
2. **A fourth, explicitly experimental strategy** (e.g. shortest-predicted-treatment-first using
   `predicted_service_time`) — clearly labeled as an experiment for the comparison view, never wired as a
   default, with the fairness caveat from Phase 3 stated up front in its docstring.
3. **Propose, don't build, a batch-optimization mode:** if you genuinely have time and the core is
   rock-solid, raise with A whether a batch/ILP allocation mode is worth a scoped interface change. This
   touches `engine.py`'s allocation pass, which A owns — **do not implement it unilaterally** against the
   locked interface.

---

## 16. Demo talking points and open items (Person B)

### 16.1 Demo talking points (your real scope)

> *"Our scoring functions are pure — same patient, same system state, same time always produces the same
> priority number, which is what makes our strategy comparison trustworthy: we replay the identical arrival
> sequence through each strategy and only the scoring changes. Urgency-only starves low-priority patients —
> you can see average wait time for Level 5 patients grow unbounded. Adding wait-time weighting bounds that.
> Our utilization-aware strategy spreads load across contended resources without ever letting a wait bonus
> outrank a genuine urgency gap — we enforce that as a hard test, not just a design intent."*

### 16.2 Open items to resolve with A (bring these to the 0:30 sync explicitly)
- [x] ✅ Literal `StateView` field names for per-type free/active counts → `free_counts`,
      `active_capacities` (§2.1)
- [x] ✅ Confirm `hol_policy = BACKFILL` as default (§10.13 Decision #1) → confirmed (§2.3)
- [x] ✅ Import path for `Patient` / `PatientView` / `StateView` / `ResourceType` → `engine.types` (§2.2)
- [ ] ⏳ Confirm where `strategies.STRATEGIES` registry is imported from (does C import it directly, or
      does A re-export it through `engine/__init__.py`?)
- [ ] ⏳ Confirm whether `/compare` (C's endpoint) calls `run_headless` directly and hands B raw results,
      or expects B to expose a single `compare(...)` entry point it calls

---
---

# PART IV — PERSON C: API / INTEGRATION LAYER (`api/`)

> *(Person C's task list, expanded into a full implementation plan. Every original task is preserved and
> marked with its original priority: 🔴 critical · 🟠 important · 🟢 finishing.)*

## 17. Mandate and architecture

### 17.1 What you own

You own the **wiring between the engine and the dashboard**, and the plumbing for every bonus feature.
Nobody else can demo anything until your layer works, and **no one else is allowed to touch it** — A's
agent rules explicitly forbid the engine agent from editing `api/`.

- FastAPI service exposing REST endpoints + a WebSocket for live ticks
- The **wall-clock tick loop** (asyncio) — the engine has no concept of real time; you supply it
- Serializing simulation state to JSON each tick and pushing it over WebSocket
- Scenario controls: surge, staff shortage, resource failure
- Strategy switching (`/strategy`) and fair strategy comparison (`/compare`)
- Deterministic, scripted **demo scenarios** so the live demo never depends on luck
- **End-to-end integration testing of the entire pipeline**

### 17.2 What you must not do

- **Don't duplicate A's or B's logic.** You never compute a priority score, never allocate a resource,
  never decide who goes next. If you catch yourself writing `if urgency == 1`, stop.
- **Don't reach into engine internals.** Your only contact surface is the public interface in §10.12:
  `run_until`, `snapshot`, `stats_raw`, `inject_surge`, `set_capacity`, `fail_resource`, `set_strategy`,
  plus `generate_arrivals` and `run_headless`. A's integration checklist has a literal line item for this:
  *"C's tick loop uses only `run_until` + `snapshot()` (no private engine access)."*
- **Don't reshape the snapshot.** `snapshot()` is already JSON-safe and already in the order D needs.
  Pass it through. If you transform it, D's mock and the real data diverge and you'll burn an hour at 09:00.
- **Don't trigger compared runs by wall-clock.** Comparison runs use `ScriptedAction` only (§10.13 #6).

### 17.3 Module architecture

```
api/
  __init__.py
  main.py             # FastAPI app, CORS, router registration, lifespan startup/shutdown
  deps.py             # get_sim() dependency — returns the SimulationService singleton
  schemas.py          # Pydantic request/response models (the wire contract)
  sim_service.py      # SimulationService: owns the Engine instance + the asyncio tick loop
  ws.py               # ConnectionManager: WebSocket connect/disconnect/broadcast
  routers/
    simulation.py     # /sim/*      — start, pause, resume, speed, reset, status
    patients.py       # /patients   — queue + in-treatment
    resources.py      # /resources  — pools + utilization
    stats.py          # /stats      — display stats (via B's to_display_stats)
    strategy.py       # /strategy   — list + switch
    scenario.py       # /scenario/* — surge, capacity, fail
    compare.py        # /compare    — fair A/B across strategies
    demo.py           # /demo/*     — scripted demo scenarios
  demo_seeds.py       # hand-authored patient batches + scripted action timelines
tests/api/
  test_endpoints.py
  test_websocket.py
  test_pipeline.py    # full end-to-end integration
```

### 17.4 The one architectural rule that matters

**`SimulationService` is the only object that touches the `Engine`.** Routers call methods on the service;
the service calls the engine. This keeps the "am I duplicating A's logic?" question trivially answerable —
if a router contains simulation logic, it's in the wrong file.

Because the engine is synchronous and CPU-bound and the tick loop is a single asyncio task, **there is
exactly one writer to engine state**. Guard every mutation path (hooks, strategy switch, reset) with an
`asyncio.Lock` so a REST call can't land mid-`run_until`.

---

## 18. Tasks 1–8, expanded

### 🔴 Task 1 — API contract  *(Hour 0:00–0:30, whole team)*

**Do this first, with the whole team.** The plan specifically says the data model should be agreed in the
first hour **because it becomes the API contract**.

Agree on and write down:
- **Patient JSON** — see `queue[]` / `in_treatment[]` in §9.3
- **Resource JSON** — see `resources{}` in §9.3 (`total, free, occupied, failed, off`)
- **SimulationState JSON** — the full `snapshot()` shape (§10.12)
- **Stats JSON** — `stats_raw()` (§10.12) and B's display transform (§15 Phase 5)

**Your specific outputs from this meeting:**
- [ ] Take A's sample `snapshot()` (§9.3) and commit it verbatim to `frontend/mock/snapshot.json` for D
- [ ] Confirm with A the driving pattern (§9.5), `run_headless` signature, and `ScriptedAction` shape
- [ ] Confirm with B how `STRATEGIES` is exposed (open item, §16.2) — you need the name→callable registry
- [ ] Confirm 🔒 the locked decisions in §2 so your Pydantic models use `free_counts` /
      `active_capacities` / `engine.types` / BACKFILL
- [ ] Agree the WebSocket envelope shape (§20) with D **now**, not at hour 9

> ⚠️ Anything in the contract that's still "we'll figure it out later" is a bug scheduled for 09:00.

---

### 🔴 Task 2 — FastAPI setup  *(Hour 0:30–2:00)*

Learn/build: **FastAPI · Pydantic · Routes · Request/Response · CORS.**

**Concretely:**
1. `pip install fastapi uvicorn[standard] pydantic` (+ `pytest httpx` for tests).
2. `api/main.py` — create the app, register routers, add a `lifespan` handler that constructs the
   `SimulationService` on startup and cancels the tick task on shutdown.
3. **CORS is not optional.** Vite dev-serves D's app on `http://localhost:5173` and your API is on
   `:8000` — without `CORSMiddleware` every fetch fails with an opaque browser error and you'll waste 20
   minutes. Allow the Vite origin (and `http://127.0.0.1:5173`), all methods, all headers, credentials on.
4. `api/schemas.py` — Pydantic models for every request body and every response. Use enums for
   `ResourceType` and strategy names so a typo is a 422 instead of a silent no-op.
5. Add `GET /health` returning `{"ok": true, "clock": ...}` — D and you both use it to check the server is
   alive, and it's the first thing you hit when something's broken.
6. Run with `uvicorn api.main:app --reload --port 8000`. Confirm the auto-generated docs at `/docs` — this
   is also a nice thing to flash at a judge.

**Deliverable at 2:00:** server boots, `/docs` lists every planned endpoint (stubs returning mock data are
fine), D can fetch from the browser without CORS errors.

---

### 🔴 Task 3 — REST endpoints  *(Hour 2:00–5:00)*

Implement, per the original task list:

```
GET  /patients      GET  /resources      GET  /stats
POST /allocate      POST /strategy       POST /scenario
```

...plus the control endpoints A's button map (§9.7) requires: `/sim/start`, `/sim/pause`, `/sim/resume`,
`/sim/speed`, `/scenario/surge`, `/scenario/capacity`, `/scenario/fail`, `/compare`.

Full reference with bodies and responses: **§19**.

**Build order:** `/sim/*` first (nothing else is demonstrable without start/pause), then `/patients` and
`/resources` (D's two main panels), then `/strategy` and `/scenario/*`, then `/stats`, then `/compare`.

**Until A's engine lands (~hour 4), serve A's sample snapshot from `frontend/mock/snapshot.json`** behind
the real endpoint shapes. D then builds against the real URLs from hour 1 and nothing changes at
integration time except the data being live.

---

### 🔴 Task 4 — Integration with A + B  *(Hour 4:00–9:00)* — **the core of your role**

```
FastAPI
   ↓
Simulation Service
   ↓
Person A (engine)  +  Person B (strategies)
```

**Make sure you're not duplicating their logic.**

`SimulationService` responsibilities, and nothing more:

| Responsibility | How |
|---|---|
| Build the engine | `arrivals = generate_arrivals(seed, config, horizon_s)`; `Engine(config, arrivals, strategy, seed, scripted=[], triage_fn=..., los_fn=...)` |
| Resolve a strategy name → callable | `strategies.STRATEGIES[name]` (B's registry) — never implement scoring |
| Advance time | `eng.run_until(eng.clock + int(speed * dt))` — never call `step()` in a loop yourself |
| Read state | `eng.snapshot()` — pass through unmodified |
| Read stats | `eng.stats_raw()` → hand to B's `to_display_stats()` |
| Apply a scenario | call the matching hook, then `eng.run_until(eng.clock)` so the UI updates *now* |
| Compare strategies | one `arrivals` list + one seed + one `scripted` list → `run_headless` per strategy → B's `compare_strategies()` |
| Reset | build a fresh `Engine`; never mutate the old one |

**Integration gotchas that will bite you (from §9.8):**
- Hooks take effect on the **next** `step()`/`run_until()`. **Always** follow a hook with
  `eng.run_until(eng.clock)`, or the judge presses "Surge" and nothing visibly happens.
- `snapshot()` already returns copies — `json.dumps` it directly, no custom encoder, no `.dict()` dance.
- Live surges use the engine's seeded RNG; **only scripted surges are identical across compared runs.**
  That's why `/compare` takes a `scripted` list and never replays live button presses.
- If A changes any shape in §9 or any `Engine` signature, they will tell you immediately — and you must
  tell D immediately in turn.
- `ResourceType` arrives from the wire as a string (`"NURSE"`); convert to the enum with
  `ResourceType[name]` at the boundary, once, in the router. Never pass raw strings into engine calls.

**AI hooks:** if the team takes the `ml/` component (§10.13 #7), you pass `triage_fn` / `los_fn` into the
`Engine` constructor. Expose a boolean in the sim-config request so the demo can toggle AI triage on and
off — a visible before/after is worth a lot and costs you one parameter.

---

### 🔴 Task 5 — WebSocket  *(Hour 5:00–7:00)*

Build `/ws/simulation` and **broadcast simulation state every tick**.

Design:
- A `ConnectionManager` holding `set[WebSocket]`: `connect`, `disconnect`, `broadcast(payload)`.
- **On connect, immediately send one full snapshot** so a late-joining client isn't staring at an empty
  dashboard until the next tick.
- The tick loop is **one** background `asyncio.Task` started at app startup — *not* one per connection.
  Two judges opening two browser tabs must not double the simulation speed.
- Wrap each send in try/except; drop dead sockets from the set rather than letting one closed tab kill the
  loop.
- Broadcast on **every** tick and also immediately after any scenario/strategy mutation.

Protocol and message shapes: **§20.** Tick loop details: **§21.1.**

---

### 🟠 Task 6 — Scenario controls  *(Hour 7:00–9:00, polish 10:00–13:00)*

Implement **surge · staff shortage · resource failure**.

The first two are **especially important** because the plan puts them high in the bonus priority order
(§25: surge is #2, staff shortage is #3, resource failure is #6).

| Control | Endpoint | Engine hook | Demo-ready defaults |
|---|---|---|---|
| Emergency surge | `POST /scenario/surge` | `inject_surge(multiplier, duration_s)` | `multiplier=3.0, duration_s=3600` |
| Staff shortage | `POST /scenario/capacity` | `set_capacity(rtype, n)` | `NURSE 16 → 6`, `DOCTOR 8 → 3` |
| Resource failure | `POST /scenario/fail` | `fail_resource(unit_id, duration_s)` | fail an **occupied ICU bed**, `duration_s=1800` |

Notes:
- **Staff shortage is `set_capacity`, not a separate concept.** Store the pre-shortage capacity per type in
  the service so the UI can offer a "restore staffing" button that just calls `set_capacity` with the
  original number.
- **Capacity reductions never interrupt treatment** (§10.9) — units already in use get `pending_off` and go
  OFF when released. Say this out loud in the demo; it's a realism point judges notice.
- **Failing an occupied unit is the dramatic one:** P-FAIL requeues the patient with their *remaining*
  service time and their original `arrival_time`, so they come back high in the queue and finish the rest
  of their treatment later. `/resources` should expose unit ids so D's UI can let you pick a specific
  occupied unit to break.
- `n` in `set_capacity` is clamped by the engine to `[0, total]`, but validate in Pydantic anyway so the
  user gets a clean 422 instead of a silent clamp.
- **Every scenario handler ends with `run_until(clock)` + an immediate broadcast.**

---

### 🟠 Task 7 — Demo data  *(Hour 9:00–11:00; rehearse later)*

**Don't rely completely on random patients.** Create predictable demo scenarios:

```
Patient 1 → Critical
Patient 2 → Low
Patient 3 → Critical
Patient 4 → Moderate
...
```

Then the judges can actually see the scheduling behaviour. **The plan explicitly assigns Person C scripted
patient batches for a reliable live demo.**

`api/demo_seeds.py` should provide named, hand-authored scenarios:

| Name | What it shows | Shape |
|---|---|---|
| `queue_jump` | A critical patient arriving late jumps ahead of an earlier low-urgency patient | 4–6 patients, staggered arrivals, one Level-1 arriving last |
| `icu_contention` | Two Level-1s, one ICU bed → the second visibly waits; BACKFILL lets a Level-4 with a free bed+doctor start meanwhile | matches the §9.3 sample situation |
| `starvation` | Under `urgency_only`, a Level-5 waits forever; under `urgency_wait` it eventually runs | long horizon, steady Level-1..3 stream + one Level-5 |
| `surge_demo` | Scripted surge at a known time so the spike lands exactly when you're talking about it | `scripted=[(t, "surge", (3.0, 3600))]` |
| `full_demo` | The whole 2–3 min video run in one deterministic scenario | scripted surge + capacity cut + one failure |

Implementation notes:
- Build these as explicit `list[Patient]` passed to the `Engine` **in place of** `generate_arrivals(...)`,
  or as `generate_arrivals(...)` with a **pinned seed** plus a prepended hand-authored batch. Either is
  fine; pinning a seed is less code and A's determinism guarantee makes it just as reproducible.
- Pair each scenario with a `scripted: list[ScriptedAction]` timeline so surges and failures happen at
  known simulated times rather than whenever someone remembers to click.
- Expose `GET /demo/scenarios` (list) and `POST /demo/load {name}` (reset the engine into that scenario).
- **Write down the seed that produces the nicest run** and hard-code it as the demo default. "It looked
  better last time" is not a recovery plan at 23:00.

---

### 🟢 Task 8 — Integration testing  *(Hour 18:00–20:00, plus continuously)*

Test the pipeline:

```
React → FastAPI → Simulation → FastAPI → WebSocket → React
```

**Don't just test your endpoints individually. Test the entire pipeline.**

`tests/api/test_pipeline.py` — use FastAPI's `TestClient` (it supports `websocket_connect`) and drive real
end-to-end flows:

1. **Boot → tick → broadcast:** start the sim, connect a WS client, assert ≥3 `state` messages arrive and
   `clock` strictly increases between them.
2. **Snapshot shape parity:** assert every received `state.data` payload matches the keys in
   `frontend/mock/snapshot.json`. **This is the test that stops D's dashboard silently breaking.**
3. **Control round-trip:** `POST /sim/pause` → clock stops advancing across two ticks; `POST /sim/resume` →
   it advances again.
4. **Surge round-trip:** capture queue length → `POST /scenario/surge` → within N ticks, queue length
   increased and `flags.arrival_multiplier` changed in the broadcast payload.
5. **Shortage round-trip:** `POST /scenario/capacity {NURSE, 2}` → `/resources` shows `off > 0` for NURSE
   and **no patient was interrupted** (`counts.interrupted` unchanged).
6. **Failure round-trip:** fail an occupied unit → an `INTERRUPTED` event appears in `recent_events` and
   the patient is back in the queue with `arrival_time` unchanged.
7. **Strategy switch:** `POST /strategy {name}` → next broadcast has the new `strategy_name` and the queue
   order changes for a scenario constructed to make it change.
8. **Compare fairness:** `POST /compare` twice with the same body → **byte-identical** results. This is A's
   determinism guarantee observed from outside, and it's the single most convincing automated test you own.
9. **No capacity violations end-to-end:** run the `full_demo` scenario with `debug_invariants=True` and
   assert it completes without raising.
10. **Reconnect:** connect, disconnect, reconnect → the new client gets a full snapshot immediately.

Also keep a `scripts/smoke.sh` that curls every endpoint in order and prints status codes — 30 seconds to
run, catches "someone broke the server" instantly during the bug bash.

---

## 19. Full endpoint reference

All bodies and responses are JSON. All times are **int seconds of simulated time** (§5).

### 19.1 Simulation control

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/health` | — | `{ok, clock}` |
| `POST` | `/sim/start` | `{seed?, horizon_s?, speed?, strategy?, demo?}` | full snapshot |
| `POST` | `/sim/pause` | — | `{running: false, clock}` |
| `POST` | `/sim/resume` | — | `{running: true, clock}` |
| `POST` | `/sim/speed` | `{speed: float}` — simulated seconds per real second | `{speed}` |
| `POST` | `/sim/reset` | `{seed?, demo?}` | full snapshot |
| `GET` | `/sim/status` | — | `{running, clock, speed, seed, strategy_name, hol_policy}` |

`speed` is the multiplier in `run_until(clock + int(speed * dt))`. Sensible values: 60 (1 min/s) for a
readable demo, up to 600 to fast-forward into an interesting state.

### 19.2 State reads

| Method | Path | Returns |
|---|---|---|
| `GET` | `/state` | the complete `snapshot()` — identical to what the WS broadcasts |
| `GET` | `/patients` | `{queue: [...], in_treatment: [...], clock}` — sliced straight from the snapshot |
| `GET` | `/resources` | `{resources: {TYPE: {total, free, occupied, failed, off}}, units?: [...]}` plus a derived `utilization` per type = `occupied / (total − failed − off)`, guarded |
| `GET` | `/stats` | B's `to_display_stats(eng.stats_raw())` — avg/p95 wait per urgency, utilization % per type, treated / waiting / interrupted counts |

> These are **convenience views over the same snapshot**, for D's polling fallback and for curl-based
> debugging. The WebSocket remains the primary path.

### 19.3 Allocation

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/allocate` | `{}` | `{events: [...], snapshot: {...}}` |

Advances the simulation to the next allocation point and returns the events produced — effectively a
manual "step". **It does not implement allocation**; it calls into the engine, which runs A's allocation
pass. Useful for step-by-step debugging and for a "Step" button in the UI when the sim is paused. Don't
let it become a second, competing tick path: refuse it (409) while the tick loop is running.

### 19.4 Strategy

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/strategy` | — | `{active, available: ["urgency_only","urgency_wait","urgency_wait_utilization", ...]}` |
| `POST` | `/strategy` | `{name}` | `{active, snapshot}` |

Resolve via B's `STRATEGIES` registry, call `eng.set_strategy(fn)`, then `run_until(clock)` and broadcast,
so the queue visibly re-orders the instant the dropdown changes. Unknown name → 422 listing valid names.

### 19.5 Scenario

| Method | Path | Body | Engine hook |
|---|---|---|---|
| `POST` | `/scenario/surge` | `{multiplier: float, duration_s: int}` | `inject_surge` |
| `POST` | `/scenario/capacity` | `{type: ResourceType, n: int}` | `set_capacity` |
| `POST` | `/scenario/fail` | `{unit_id: int, duration_s: int}` | `fail_resource` |
| `POST` | `/scenario` | `{kind: "surge"\|"capacity"\|"fail", ...args}` | dispatches to the above |

The generic `POST /scenario` exists because it's named in the original team plan and D's early code may
target it; it is a thin dispatcher over the three specific routes, which are canonical (they're what A's
button map in §9.7 specifies). Every handler: call hook → `run_until(clock)` → broadcast → return the fresh
snapshot.

### 19.6 Compare

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/compare` | `{seed, horizon_s, until_s, strategies: [names], scripted: [[t, kind, args], ...]}` | `{raw: {name: stats_raw}, comparison: {...}}` |

**Fairness rules, non-negotiable (§9.6, §10.13 #6):**
- Generate `arrivals` **once**, reuse the same list for every strategy — `run_headless` deep-copies it.
- Same `seed`, same `scripted` list, same `until_s` for every strategy.
- **Never** use live wall-clock scenario events in a compared run.
- Hand `{name: stats_raw()}` to B's `compare_strategies()`; return both raw and comparison so D can chart
  whichever it likes.
- This runs headless and synchronously and can take a second or two. Run it in a threadpool
  (`run_in_executor` / `anyio.to_thread`) so the tick loop doesn't stall, and return a
  `{"job": id}` + WS `compare_result` message if it's slow enough to notice.

### 19.7 Demo

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/demo/scenarios` | — | `[{name, description}]` |
| `POST` | `/demo/load` | `{name}` | full snapshot (engine reset into that scenario) |

### 19.8 Error conventions

- `422` — Pydantic validation failure (bad enum, negative duration, unknown strategy name).
- `409` — action invalid for current state (e.g. `/allocate` while running, `/sim/resume` when not started).
- `404` — unknown demo scenario or unknown unit id.
- Every error body: `{"error": "...", "hint": "..."}`. D shows `hint` in a toast; it saves both of you
  guessing during the bug bash.

---

## 20. WebSocket protocol — `/ws/simulation`

**Envelope (server → client):**

```json
{ "type": "state", "data": { ...full snapshot()... } }
```

Message types:

| `type` | `data` | When |
|---|---|---|
| `state` | full `snapshot()` (§10.12) | every tick, on connect, and immediately after any mutation |
| `events` | `[log event, ...]` | optional, for D's log feed if they want only the delta |
| `stats` | display stats | every N ticks (stats are heavier; don't send every tick) |
| `compare_result` | comparison payload | when an async `/compare` job finishes |
| `error` | `{message}` | engine exception caught by the tick loop |

Client → server: **nothing required.** Keep it one-directional; all control goes through REST. (If you want
a `{"type":"ping"}` keepalive, fine, but don't build a second control channel — two ways to do the same
thing is two ways to have a bug on stage.)

Rules:
- Send a full `state` on connect, before the first tick.
- One shared tick task drives all clients; connections never affect simulation speed.
- Broadcast is best-effort: failed send → remove that socket, continue.
- `snapshot()` is already JSON-safe, so `websocket.send_json(snapshot)` works with no custom encoder.
- `recent_events` carries the last 50 log dicts, which is what D's timeline feed renders
  (`"Patient #14 [CRITICAL] assigned ICU Bed 3 at t=00:42"`).

---

## 21. Tick loop, scenario handling, demo seeding, testing notes

### 21.1 The tick loop

```
every dt real seconds (default 0.5):
    if not running: continue
    async with lock:
        eng.run_until(eng.clock + int(speed * dt))
        snap = eng.snapshot()
    await manager.broadcast({"type": "state", "data": snap})
```

- `dt = 0.5s` and `speed = 60` gives 30 simulated seconds per real second — fast enough that the dashboard
  visibly moves, slow enough to narrate.
- **The engine is synchronous.** If a `run_until` ever spans a long horizon it will block the event loop;
  keep per-tick advances small and push long/headless work to a thread.
- The loop must never die. Wrap the body in try/except, log the exception, broadcast an `error` message,
  and keep going — a crashed tick task looks exactly like a frozen dashboard, at the worst possible moment.
- Hold the lock around engine mutation only, never around `await broadcast(...)`.

### 21.2 Scenario handler pattern (identical for all three)

```
validate body (Pydantic)  →  convert strings to engine enums  →  async with lock:
    hook(...)                       # enqueues an event at the current clock
    eng.run_until(eng.clock)        # ⚠️ REQUIRED — applies it now, §9.8
    snap = eng.snapshot()
→ broadcast snap  →  return snap
```

Forgetting the `run_until(clock)` line is the single most likely reason a demo button "does nothing".

### 21.3 Demo seeding

See Task 7 (§18). Two extra points:
- Keep the scripted timeline **in simulated seconds**, so the demo is identical at any playback speed.
- Have a `full_demo` scenario that maps 1:1 onto the demo video script (§26): arrivals → queue jump →
  allocation → surge → strategy switch → stats. Rehearse against it.

### 21.4 Testing notes

- `TestClient(app)` from `fastapi.testclient` gives you both HTTP and `websocket_connect`.
- For deterministic tests, drive the engine directly through the service with the tick loop **stopped**,
  calling an internal `advance(n)` — don't `sleep()` in tests waiting for wall-clock ticks.
- Keep at least two tests that would fail if someone reshapes the snapshot (parity with the mock file, and
  the compare-determinism test).

---

## 22. Person C phased build plan and open items

### 22.1 Schedule

| Hours | Goal |
|---|---|
| 0:00–0:30 | **Task 1.** Team sync: lock data model + API contract. Commit `frontend/mock/snapshot.json` for D. |
| 0:30–2:00 | **Task 2.** FastAPI scaffold, CORS, Pydantic schemas, `/health`, `/docs` listing all routes. |
| 2:00–4:00 | **Task 3.** REST endpoints against A's mock snapshot. D can now integrate for real. |
| 4:00 | **Checkpoint:** C+D integrated — dashboard renders mock JSON matching the real schema. |
| 4:00–7:00 | **Task 4 + 5.** Wire the real engine into `SimulationService`; tick loop; `/ws/simulation` live. |
| 7:00–9:00 | **Task 6.** `/scenario/*` and `/strategy` endpoints wired to A's hooks. |
| 9:00 | **Checkpoint:** full pipeline end-to-end with the default strategy. **Safety-net prototype — commit it.** |
| 9:00–13:00 | **Task 7** demo seeds + `/compare` wired to B's comparison layer. Bonus features live. |
| 13:00–15:00 | Sleep in shifts. |
| 15:00–18:00 | `/stats` polish, `/demo/*`, error handling, reconnect behaviour. |
| 18:00–20:00 | **Task 8.** Bug bash with A and B: full-pipeline tests, surge stress, race conditions. |
| 20:00–21:30 | Support D's UI polish; freeze the API. |
| 21:30–22:30 | Demo run-throughs against the pinned seed; record video. |
| 22:30–24:00 | README (API section), final commit, submission. |

### 22.2 Definition of done (API v1)
- [ ] `uvicorn api.main:app` boots clean; `/docs` lists every endpoint in §19.
- [ ] CORS verified from D's Vite dev server.
- [ ] Tick loop runs as a single shared task; two browser tabs do not double the sim speed.
- [ ] `/ws/simulation` sends a full snapshot on connect and on every tick.
- [ ] Every scenario endpoint calls its hook **and** `run_until(clock)` **and** broadcasts.
- [ ] `/strategy` resolves through B's `STRATEGIES` registry; unknown name → 422.
- [ ] `/compare` is byte-identical across repeated identical requests.
- [ ] `/compare` uses one arrivals list, one seed, one `scripted` list for all strategies.
- [ ] No engine internals touched anywhere outside `sim_service.py`.
- [ ] Snapshot passed through unmodified; parity test against `frontend/mock/snapshot.json` passes.
- [ ] `tests/api/test_pipeline.py` covers the 10 flows in Task 8 and passes.
- [ ] At least three named demo scenarios load reliably from a pinned seed.

### 22.3 Open items for Person C
- [ ] ⏳ Does C import `strategies.STRATEGIES` directly, or does A re-export it through
      `engine/__init__.py`? (mirrors B's open item, §16.2)
- [ ] ⏳ Does `/compare` call `run_headless` itself and hand raw results to B, or call a single
      `compare(...)` entry point B exposes? (mirrors B's open item, §16.2)
- [ ] ⏳ If the team takes the AI component (§10.13 #7), C passes `triage_fn`/`los_fn` into the `Engine`
      constructor and exposes an on/off toggle in `/sim/start`.
- [ ] ⏳ Default demo `speed` and `seed` — pin both before the video recording at 21:30.

### 22.4 If C falls behind (cuts, in order)
1. `/demo/*` endpoints (hard-code one scenario instead)
2. `/stats` endpoint (D can derive headline numbers from the snapshot)
3. `events` and `stats` WS message types (ship `state` only)
4. Async `/compare` job + `compare_result` message (run it synchronously and accept the pause)

**Never cut:** the tick loop, `/ws/simulation`, `/scenario/surge`, `/scenario/capacity`, `/strategy`,
`/compare` fairness (one arrivals list, one seed, one scripted list).

---
---

# PART V — PERSON D: FRONTEND / DASHBOARD (`frontend/`)

## 23. Scope and components

Person D owns **everything the judges actually look at**.

- **Live patient queue** — sorted by priority, color-coded by urgency: Red/Orange/Yellow/Green
  (1 red, 2 orange, 3 yellow, 4 green, 5 blue/grey per §5). `snapshot().queue` is **already in the order
  the next allocation pass will use**, so render it as-is — do not re-sort it client-side.
- **Resource utilization panel** — beds / ICU / OR / doctors / nurses as gauges or bar charts, live %.
  Gauge value = `occupied / (total − failed − off)`, guard divide-by-zero (§9.4).
- **Timeline / log feed** — e.g. `"Patient #14 [CRITICAL] assigned ICU Bed 3 at t=00:42"`, rendered from
  `snapshot().recent_events` (last 50 log dicts).
- **Controls** — Start / Pause / Speed, "Trigger Surge", "Simulate Staff Shortage", strategy dropdown.
  Each maps to a REST call in §19 and to an engine hook per §9.7.
- **Side-by-side comparison view** — run two strategies over the same patient batch, show
  wait-time / utilization deltas as a chart. Fed by `POST /compare` → B's `compare_strategies()` output.

Working notes:
- Build against `frontend/mock/snapshot.json` (A's sample, §9.3) from hour 0:30 — the real data has the
  identical shape, so hour-9 integration should change nothing but the source of the JSON.
- Use the TypeScript types in §9.4 verbatim.
- Format int-second simulated time as `HH:MM` or `Xh Ym` for display (§5).
- Subscribe to `/ws/simulation` for state; use REST only for control actions (§20).

---
---

# PART VI — PROGRAM LEVEL

## 24. Unified hour-by-hour timeline (24 hours)

| Time | Milestone |
|---|---|
| **0:00–0:30** | **Kickoff:** lock data model + API contract (all 4 together). A confirms §10.13 decisions, hands D the sample snapshot + TS types, hands B the `Strategy` signature + `StateView` field names + BACKFILL, hands C the driving pattern + `run_headless` + `ScriptedAction`. Decide who owns the AI component. |
| **0:30–4:00** | **Parallel build:** A builds patient generator + resource pool (Prompt 0, Step A tests, Step B stubs, Slices 1–3); B builds scoring primitives + strategies 1 & 2 (Phases 1–2); C scaffolds FastAPI + WebSocket skeleton (Tasks 2–3); D scaffolds React app + component shells with mock data. |
| **4:00–5:00** | **Checkpoint:** A+B integrate (engine produces allocation decisions; A's CLI harness runs 10k steps with invariants on). C+D integrate (dashboard renders mock JSON matching the real schema). B has all three strategies unit-tested against fixtures. |
| **5:00–9:00** | A: capacity-violation checks + failure/shortage injection (Slices 4–6). B: comparison metrics + stats display layer (Phases 4–5). C: wire real engine to WebSocket, build `/scenario` and `/strategy` (Tasks 4–6). D: live queue view + resource gauges against real data. |
| **9:00–10:00** | **Checkpoint:** full pipeline works end-to-end with the default strategy, no bonus features yet — **this is your safety-net working prototype, commit it.** B swaps fixtures for A's real views and `stats_raw()`. |
| **10:00–13:00** | **Bonus features:** surge mode, staff shortage, strategy comparison view, ICU-specific constraints. A: Slice 8 (M/M/c), scenario polish. C: demo seeds + `/compare`. B: Phase 7 stretch if ahead. |
| **13:00–15:00** | *(sleep/break window for at least 2 people in shifts — **protect this**, exhausted debugging is slower than rested debugging)* |
| **15:00–18:00** | Multi-department support if time allows; polish urgency scoring edge cases; stats dashboard (avg wait, utilization %, comparison charts). |
| **18:00–20:00** | **Bug bash:** stress-test with rapid surge scenarios, fix race conditions in resource allocation, confirm no capacity violations ever occur. A runs the 200-seed × 20k-step stress script. B joins — most real bugs live at the Engine↔Strategy boundary. C runs the full-pipeline test suite. |
| **20:00–21:30** | UI polish pass (color coding, animations for assignment events, responsive layout). API freeze. |
| **21:30–22:30** | Script and record demo video (§26). |
| **22:30–23:30** | Prep slides/README (including the AI-usage section), rehearse live demo backup plan. |
| **23:30–24:00** | Buffer for last-minute fixes, final commit, submission. |

---

## 25. Bonus feature priority order

Build in this order if time runs short:

1. **Strategy comparison** (urgency-only vs. wait-aware vs. utilization-aware) — **highest value, do this**
2. **Emergency surge simulation**
3. **Staff shortage simulation**
4. **ICU capacity constraints** — can likely be folded into the core resource model from the start, not
   really "extra" work
5. **Ambulance arrival pattern modeling**
6. **Resource failure simulation**
7. **Multi-department support** — lowest priority, cut first if behind schedule

---

## 26. Demo video script (2–3 min, maps directly to the deliverable checklist)

1. **(15s)** One-line problem framing: hospitals must allocate scarce beds/staff under uncertainty
2. **(20s)** Show patient arrivals streaming into the queue, color-coded by urgency
3. **(30s)** Show priority calculation live — point out a critical patient jumping the queue over an
   earlier-arrived low-urgency one
4. **(30s)** Show resource allocation happening — bed/doctor/ICU assignment animating, utilization gauges
   updating
5. **(30s)** Trigger **surge mode** — show queue spike and dashboard visibly adapting
6. **(30s)** Switch strategy live (urgency-only → urgency+wait+utilization) and show the comparison chart —
   call out the wait-time/utilization improvement numbers
7. **(15s)** Close with the stats panel: total treated, avg wait, utilization %, **zero capacity
   violations**

Run it against C's `full_demo` scenario with a pinned seed (§18 Task 7) so it behaves identically every
take.

---

## 27. Correctness safety net

Before the demo, run an automated check (**Person B owns the framing; Person A owns
`assert_invariants`**): simulate several thousand ticks and assert

1. no resource is ever assigned to two patients at once (I2),
2. no pool ever exceeds its capacity (I3),
3. every "treated" patient actually had all required resources allocated at time of treatment (I5).

A judge asking *"how do you guarantee no conflicts?"* and you showing a passing assertion suite is a strong
differentiator. Have the number ready: **"200 seeds × 20,000 steps, 0 violations"** (A's `scripts/stress.py`,
§12.2).

Have A's judge-explainer answer rehearsed too: `try_reserve` is check-then-commit across the full bundle,
so a failed reservation leaves every unit untouched and no partial allocation is ever observable.

---

## 28. Repo layout

```
medflow/
├── AGENTS.md                 rules for the coding agent (Part II §11)
├── README.md
├── docs/
│   ├── AGENT.md              this file — the combined team spec
│   └── ai-notes/             agent-produced plans and design notes
├── engine/                   Person A — stdlib only, no I/O, no asyncio
│   ├── __init__.py           public exports
│   ├── types.py              enums, Patient, Unit, PatientView, StateView, Event  🔒 §2.2
│   ├── config.py             EngineConfig + defaults
│   ├── arrivals.py           make_patient, generate_arrivals
│   ├── resources.py          ResourcePool, try_reserve, release
│   ├── engine.py             Engine (heap, step, allocation pass, hooks, snapshot, stats)
│   ├── invariants.py         assert_invariants
│   └── headless.py           run_headless (used by B/C for comparisons)
├── strategies/               Person B — pure scoring functions + stats display
├── api/                      Person C — FastAPI, WebSocket, sim service, demo seeds
├── frontend/                 Person D — React + TS + Vite (incl. mock/snapshot.json)
├── ml/                       optional AI component (triage / length-of-stay), owner TBD
├── scripts/
│   ├── run_cli.py            A's debug harness
│   ├── stress.py             A's invariant stress run
│   └── smoke.sh              C's endpoint smoke test
└── tests/
    ├── engine/               Person A
    ├── strategies/           Person B
    └── api/                  Person C
```

---

## 29. Open items register

### Closed ✅
| # | Item | Resolution | Ref |
|---|---|---|---|
| 1 | Literal `StateView` field names | `free_counts`, `active_capacities`, `clock`, `flags` (+ `waiting`, `in_treatment`) | §2.1 |
| 2 | Import path for shared types | `engine.types` exports `Patient`, `PatientView`, `StateView`, `ResourceType` | §2.2 |
| 3 | HOL policy default (spec §13 Decision #1) | **BACKFILL**; BLOCK supported as the alternative | §2.3 |

### Open ⏳
| # | Item | Owner | Needed by |
|---|---|---|---|
| 4 | Who owns the AI component (triage classifier / LOS predictor)? Hooks in §10.10 exist for it | Team | Hour 0:30 |
| 5 | Is `strategies.STRATEGIES` imported directly by C, or re-exported via `engine/__init__.py`? | A + B + C | Hour 4:00 |
| 6 | Does `/compare` call `run_headless` itself and hand raw results to B, or call one `compare(...)` entry point B exposes? | B + C | Hour 9:00 |
| 7 | P-FAIL policy confirmation (requeue with remaining time vs. restart vs. migrate unit) | A | Hour 0:30 |
| 8 | Final placeholder values: bundles, service times, urgency mix, capacities | A | Hour 4:00 |
| 9 | Pinned demo seed + default speed for the recorded video | C + D | Hour 21:30 |

---

*End of AGENT.md — MedFlow. If this file and any per-person document disagree, **this file wins**; raise
the discrepancy at the next checkpoint rather than resolving it silently.*
