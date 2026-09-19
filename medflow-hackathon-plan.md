# MEDFLOW — 24-Hour Hackathon Implementation Plan
**Hospital Resource Management Simulator — Prioritize Patients, Optimize Resources**

---

## 1. Strategy: What Wins This

Judges will score you on: correctness of the scheduling logic, whether resource constraints are actually respected (no double-booking a bed), how well urgency + waiting time trade off, quality of the live dashboard, and whether you can *demonstrate* the bonus feature that's explicitly called out as most interesting — **comparing scheduling strategies** (urgency-only vs. waiting-time-weighted vs. utilization-aware). That comparison feature is cheap to build (it's just swapping the priority function and re-running the same simulation) and is the single highest-leverage bonus point, so treat it as a core requirement, not a stretch goal.

Second highest leverage: a **surge mode** button and a **staff-shortage toggle** — both are trivial to implement (they just perturb arrival rate / resource pool at runtime) but look extremely impressive live because the dashboard visibly reacts.

---

## 2. Team Roles (4 people)

### Person A — Backend & Simulation Core (Python)
Owns the "engine": patient generator, resource pool, state machine, simulation clock.
- Patient arrival generator (Poisson process, configurable rate, surge multiplier)
- Resource pool class (beds, ICU beds, OR, doctors, nurses, ambulances) with atomic allocate/release
- Simulation loop (tick-based or event-driven) that advances time, ages the queue, and re-runs allocation each tick
- Staff-shortage and resource-failure injection hooks

### Person B — Scheduling Algorithm & Priority Engine (Python)
Owns the "brain": this is the differentiator, keep it isolated as a pluggable module.
- Urgency scoring model (triage-style, see §4)
- Priority queue implementation (heapq-based) with tie-breaking rules
- Three interchangeable strategy functions: `urgency_only`, `urgency+wait_time`, `urgency+wait_time+utilization`
- Conflict/capacity-violation checker (assertion layer — this is what proves correctness to judges)
- Statistics module: avg wait time, utilization %, patients-treated vs. patients-waiting, strategy comparison metrics

### Person C — API / Integration Layer
Owns the wiring between engine and dashboard, and owns bonus feature plumbing.
- FastAPI (or Flask) service exposing REST endpoints + a WebSocket for live ticks
- Endpoints: `/patients`, `/resources`, `/allocate`, `/stats`, `/strategy` (switch), `/scenario` (trigger surge/shortage/failure)
- Serializes simulation state to JSON each tick and pushes over WebSocket
- Seeds demo scenarios (scripted patient batches for a reliable live demo, not pure randomness)

### Person D — Frontend / Dashboard (React)
Owns everything the judges actually look at.
- Live patient queue (sorted by priority, color-coded by urgency: Red/Orange/Yellow/Green)
- Resource utilization panel (beds/ICU/OR/doctors/nurses as gauges or bar charts, live %)
- Timeline/log feed ("Patient #14 [CRITICAL] assigned ICU Bed 3 at t=00:42")
- Controls: Start/Pause/Speed, "Trigger Surge", "Simulate Staff Shortage", strategy dropdown
- Side-by-side comparison view: run two strategies over the same patient batch, show wait-time/utilization deltas as a chart

---

## 3. Tech Stack

- **Backend**: Python 3.11, FastAPI, `heapq` for priority queue, `asyncio` for the tick loop, WebSocket for push updates
- **Frontend**: React + TypeScript + Vite, Recharts or Chart.js for gauges/graphs, plain CSS or Tailwind
- **Comms**: WebSocket (state broadcast every tick) + REST (control actions)
- **No database needed** — keep simulation state in memory for the demo; this saves hours and there's zero requirement for persistence

---

## 4. Urgency Scoring Model (Person B, build this first)

Use an ESI-inspired (Emergency Severity Index) 5-level triage as the base, then blend in waiting time so nobody starves:

```
base_urgency = triage_level score (1=Resuscitation..5=Non-urgent), inverted so 1(Critical)=100, 5=20
wait_bonus   = min(wait_minutes * WAIT_WEIGHT, WAIT_CAP)   # prevents low-urgency starvation
resource_penalty = if requires ICU/OR and none free -> deprioritize slightly in utilization-aware mode
priority_score = base_urgency + wait_bonus (+/- resource_penalty depending on strategy)
```

Three strategies (Person B exposes all three behind one interface so Person C/D can hot-swap):
1. **Urgency-only**: `priority = base_urgency` — simplest, but starves low-priority patients
2. **Urgency + wait time**: `priority = base_urgency + wait_bonus` — the "fair" default
3. **Urgency + wait + utilization-aware**: also considers current resource load to avoid assigning the last ICU bed to a borderline case when a more critical one is imminent (or batch-optimizes across a short lookahead window)

This 3-tier design directly satisfies the bonus point "allow users to compare different scheduling strategies."

---

## 5. Data Model (agree on this in the first hour — it's the API contract)

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

---

## 6. Hour-by-Hour Timeline (24 hours)

| Time | Milestone |
|---|---|
| **0:00–0:30** | Kickoff: lock data model + API contract (all 4 together) |
| **0:30–4:00** | Parallel build: A builds patient generator + resource pool; B builds priority queue + urgency scoring; C scaffolds FastAPI + WebSocket skeleton; D scaffolds React app + component shells with mock data |
| **4:00–5:00** | Checkpoint: A+B integrate (engine produces allocation decisions); C+D integrate (dashboard renders mock JSON matching real schema) |
| **5:00–9:00** | A: add capacity-violation checks + failure/shortage injection. B: implement all 3 strategies + comparison metrics. C: wire real engine to WebSocket, build `/scenario` and `/strategy` endpoints. D: build live queue view + resource gauges against real data |
| **9:00–10:00** | Checkpoint: full pipeline works end-to-end with default strategy, no bonus features yet — **this is your safety-net working prototype, commit it** |
| **10:00–13:00** | Bonus features: surge mode, staff shortage, strategy comparison view, ICU-specific constraints |
| **13:00–15:00** | *(sleep/break window for at least 2 people in shifts — protect this, exhausted debugging is slower than rested debugging)* |
| **15:00–18:00** | Multi-department support if time allows; polish urgency scoring edge cases; stats dashboard (avg wait, utilization %, comparison charts) |
| **18:00–20:00** | Bug bash: stress-test with rapid surge scenarios, fix race conditions in resource allocation, confirm no capacity violations ever occur |
| **20:00–21:30** | UI polish pass (color coding, animations for assignment events, responsive layout) |
| **21:30–22:30** | Script and record demo video (see §7) |
| **22:30–23:30** | Prep slides/README, rehearse live demo backup plan |
| **23:30–24:00** | Buffer for last-minute fixes, final commit, submission |

---

## 7. Demo Video Script (2–3 min, map directly to the deliverable checklist)

1. **(15s)** One-line problem framing: hospitals must allocate scarce beds/staff under uncertainty
2. **(20s)** Show patient arrivals streaming into the queue, color-coded by urgency
3. **(30s)** Show priority calculation live — point out a critical patient jumping the queue over an earlier-arrived low-urgency one
4. **(30s)** Show resource allocation happening — bed/doctor/ICU assignment animating, utilization gauges updating
5. **(30s)** Trigger **surge mode** — show queue spike and dashboard visibly adapting
6. **(30s)** Switch strategy live (urgency-only → urgency+wait+utilization) and show the comparison chart — call out the wait-time/utilization improvement numbers
7. **(15s)** Close with the stats panel: total treated, avg wait, utilization %, zero capacity violations

---

## 8. Bonus Feature Priority Order (build in this order if time runs short)

1. Strategy comparison (urgency-only vs. wait-aware vs. utilization-aware) — **highest value, do this**
2. Emergency surge simulation
3. Staff shortage simulation
4. ICU capacity constraints (can likely be folded into the core resource model from the start, not really "extra" work)
5. Ambulance arrival pattern modeling
6. Resource failure simulation
7. Multi-department support — lowest priority, cut first if behind schedule

---

## 9. Correctness Safety Net

Before the demo, run an automated check (Person B owns this): simulate several thousand ticks and assert (a) no resource is ever assigned to two patients at once, (b) no pool ever exceeds its capacity, (c) every "treated" patient actually had all required resources allocated at time of treatment. A judge asking "how do you guarantee no conflicts?" and you showing a passing assertion suite is a strong differentiator.
