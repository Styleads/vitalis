# MedFlow — Person B Implementation Plan
**Scheduling & Priority Engine (the algorithmic core)**

---

## 1. Your Mandate

You own the decision-making brain of the system: given a waiting queue of patients and a pool of finite resources, decide *who gets what, when*. Person A feeds you patients and resources; Person C exposes your decisions over the API; Person D visualizes them. Everything downstream is only as good as the correctness and defensibility of this module — this is also what judges will interrogate hardest ("how do you guarantee no conflicts?" / "why is this fair?" / "how do the three strategies actually differ?"), so it is worth over-investing here relative to the other roles.

This plan is deliberately **not** the fastest possible path — it's the path that gets you a provably correct, explainable, and genuinely comparative algorithm, because that's what separates a MedFlow submission that *works* from one that *wins*.

---

## 2. Core Design Decisions (and why)

These are the load-bearing choices. Make them once, in Phase 0, and don't relitigate them mid-build.

**2.1 — Priority is recomputed every tick, not maintained in a live heap.**
Urgency + waiting-time creates a time-dependent priority score. A classic heap's invariant silently breaks as time passes (patient X's score overtakes patient Y's without either being pushed/popped). Rather than building a fragile time-indexed heap, recompute scores for all waiting patients each tick and re-sort. At hackathon scale (tens to low hundreds of waiting patients), this is O(n log n) — microseconds — and is trivially correct and debuggable. This is the right tradeoff: a "cleverer" lazy structure buys you nothing at this scale and multiplies your bug surface. Document this reasoning — it preempts a judge's "why not a heap?" question and turns it into a strength.

**2.2 — Allocation is a full-queue greedy scan, not "check the top, stop if blocked."**
Never stop at the first patient whose resource bundle isn't available. Continue scanning the whole priority-sorted queue and allocate to any patient whose *entire* required bundle is currently free. This prevents one blocked high-priority patient (e.g., waiting on the last ICU bed) from starving unrelated resources (e.g., a free general bed + doctor that a lower-priority patient could use right now). This single decision is what makes your utilization numbers good in the demo — call it out explicitly in your presentation.

**2.3 — Resource allocation is atomic (all-or-nothing) per patient.**
A patient only gets resources when *all* required types are simultaneously available. No partial holds. This avoids deadlock/fragmentation bugs (a patient holding a bed forever while waiting on a doctor, blocking that bed from anyone else) and is easy to prove correct. See §8 for the more realistic two-tier model as an optional Phase 7 stretch — don't attempt it until the core is bulletproof.

**2.4 — Determinism above all.**
Every tie in priority score must resolve the same way every time: `(priority_score desc, arrival_time asc, patient_id asc)`. This matters more than it sounds — non-deterministic ordering makes bugs unreproducible and makes your strategy-comparison numbers noisy/unconvincing. Determinism is close to free and worth insisting on.

**2.5 — Strategies differ only in the score function and (for strategy 3) an allocation-weighting hook — never in the allocation loop itself.**
This is what makes "compare strategies" cheap and safe to build: one allocation engine, three pluggable scoring policies. If strategies had separate allocation code paths you'd be debugging three systems instead of one.

---

## 3. Module Architecture

```
scheduling/
  models.py          # Patient, Resource, ResourceBundle, Allocation dataclasses
  scoring.py          # urgency scoring + the 3 strategy score functions
  engine.py           # SchedulingEngine: tick(), allocate(), switch_strategy()
  invariants.py        # runtime assertion checks (capacity, no double-assign)
  stats.py             # utilization, wait-time, comparison metrics
  strategies/
    urgency_only.py
    urgency_wait.py
    urgency_wait_utilization.py
  tests/
    test_scoring.py
    test_allocation.py
    test_invariants.py
    test_strategy_comparison.py
```

Keep `engine.py` strategy-agnostic. It should only ever call `strategy.score(patient, now)` and, for strategy 3, `strategy.allocation_weight(patient, resource_pool)` — it must never branch on "which strategy is active."

---

## 4. Interface Contract (agree with Person A & C in Phase 0, hour 0–0:30)

```python
# What Person A's simulation loop calls each tick:
engine.tick(now: float, queue: list[Patient], resources: ResourcePool) -> TickResult

# TickResult:
#   allocations: list[Allocation]      # new assignments made this tick
#   still_waiting: list[Patient]       # unchanged patients, now with updated scores
#   violations: list[str]              # should always be empty in production; non-empty = bug

# What Person C's API calls to switch strategies live:
engine.switch_strategy(name: Literal["urgency_only", "urgency_wait", "urgency_wait_utilization"])

# What Person C's /stats endpoint calls:
engine.get_stats() -> dict   # see §7 for exact fields

# What Person D needs for the comparison view — run the SAME recorded patient
# arrival batch through two strategies without mutating shared state:
engine.run_replay(strategy_name: str, recorded_arrivals: list[Patient]) -> ComparisonRun
```

Lock this contract before writing implementation — it's the seam between all four of you and changing it later is the most expensive kind of rework.

---

## 5. Phased Build Plan

### Phase 0 — Contracts & Data Structures — *0:00–0:30 (with full team)*
- Agree on `Patient`, `Resource`, `Allocation` dataclasses with A and C (see §4)
- Nail down the resource type enum: `BED, ICU_BED, OR, DOCTOR, NURSE, AMBULANCE`
- Nail down urgency levels: 5-level ESI-style (1 = Resuscitation/Critical → 5 = Non-urgent)
- Decide bundle requirements per urgency level as a starting config (tunable later), e.g.:
  - Level 1 (Critical): `{ICU_BED: 1, DOCTOR: 1, NURSE: 1}`
  - Level 2 (Emergent): `{BED: 1, DOCTOR: 1, NURSE: 1}` (or OR if surgical flag set)
  - Level 3 (Urgent): `{BED: 1, DOCTOR: 1}`
  - Level 4–5 (Less/Non-urgent): `{BED: 1}` or `{DOCTOR: 1}` only

### Phase 1 — Urgency Scoring Model — *0:30–2:00*
Build the pure scoring function first — it has no dependencies and is fully unit-testable in isolation.

```python
def base_urgency(triage_level: int) -> float:
    # invert so lower triage_level (more critical) => higher score
    return {1: 100, 2: 80, 3: 60, 4: 40, 5: 20}[triage_level]

def wait_bonus(wait_minutes: float, weight: float = 0.5, cap: float = 40.0) -> float:
    return min(wait_minutes * weight, cap)
```
- Unit test: confirm monotonicity (bonus never decreases as wait_minutes increases, until cap)
- Unit test: confirm a Level-1 patient at t=0 always outranks a Level-5 patient regardless of that Level-5 patient's wait time (i.e., `cap` is small enough that wait bonus alone can't invert life-threatening urgency — this is a clinical-plausibility invariant worth asserting explicitly and explaining in the demo)
- Decide and document the cap rationale: wait bonus should be able to promote a Level-3 over a stale Level-2, but never a Level-5 over a fresh Level-1. Pick `cap` values that satisfy this and write the reasoning down — a judge asking "could a paper cut jump the queue over a heart attack?" deserves a confident, designed-for answer, not a shrug.

### Phase 2 — Priority Ordering & Determinism — *2:00–3:00*
```python
def priority_key(p: Patient, now: float) -> tuple:
    score = base_urgency(p.triage_level) + wait_bonus(now - p.arrival_time)
    return (-score, p.arrival_time, p.id)   # sort ascending on this tuple
```
- Sorting the whole waiting list by this tuple each tick gives you a fully deterministic, tie-broken order in one `sorted()` call — resist the urge to hand-roll a heap here, it buys nothing at this scale (§2.1)
- Test: identical scores + identical arrival times (synthetic edge case) still resolve deterministically by `id`

### Phase 3 — Resource Matching / Allocation Algorithm — *3:00–5:30*
This is the core loop. Pseudocode:

```python
def allocate(sorted_queue, resource_pool, now):
    allocations = []
    for patient in sorted_queue:               # priority order, but NEVER stop early
        bundle = resource_requirements(patient)
        if resource_pool.has_available(bundle):        # atomic check across all types
            resource_pool.reserve(bundle, patient.id)   # atomic reserve, all-or-nothing
            allocations.append(Allocation(patient, bundle, now))
            sorted_queue.remove(patient)
        # else: patient stays in queue, tries again next tick with a higher score
    return allocations
```
- `resource_pool.has_available` / `.reserve` must be a single atomic operation (no check-then-act race — irrelevant if single-threaded/synchronous, but assert it in tests anyway since Person C's async API layer will be calling into this concurrently over WebSocket ticks)
- Complexity: O(n · r) per tick where n = queue length, r = number of resource types (≤6) — effectively linear, no scalability concern at hackathon scale
- **Correctness argument to have ready for judges**: for any single resource type in isolation, this scan always awards available units to the highest-priority requesters first (provably optimal for that slice). For multi-resource bundles, "continue scanning past a blocked patient" means the algorithm never leaves a satisfiable lower-priority patient waiting just because a higher-priority patient ahead of them is blocked on an unrelated resource — this is a first-fit-by-priority heuristic, not a global optimum solver, and that tradeoff (near-optimal, O(n·r), fully explainable) vs. (globally optimal, NP-hard multi-dimensional matching, unexplainable in a 3-minute demo) is exactly the right one for this problem. Say this out loud in your demo — naming the tradeoff explicitly reads as engineering maturity, not a limitation.

### Phase 4 — Multi-Strategy Framework — *5:30–8:00*
Three strategies, one allocation loop (§2.5):

1. **`urgency_only`**: `score = base_urgency(triage_level)` — wait_bonus always 0. Expect and be ready to show *starvation* of low-urgency patients in the comparison view — this is the point, not a bug.
2. **`urgency_wait`** (recommended default): `score = base_urgency + wait_bonus` as in Phase 1–2.
3. **`urgency_wait_utilization`**: same score as strategy 2, plus an allocation-order nudge — when multiple patients are simultaneously eligible for the *same scarce resource type* (utilization of that type currently ≥ 80%, tunable threshold), slightly deprioritize requests for it in favor of requests satisfiable with less-contended resources, so the system spreads load rather than exhausting one pool first. Implement this as a **secondary sort key**, not a rewrite of the allocation loop — e.g. `(-score, contention_penalty(bundle, resource_pool), arrival_time, id)`.

Each strategy is a small class/module implementing the same interface:
```python
class Strategy(Protocol):
    def score(self, patient: Patient, now: float) -> float: ...
    def sort_key(self, patient: Patient, now: float, resource_pool: ResourcePool) -> tuple: ...
```

### Phase 5 — Invariant & Correctness Test Suite — *8:00–9:30*
This is your safety net and your strongest demo asset — build it before you build bonus features, not after.

Run a scripted multi-hour simulated batch (thousands of ticks, randomized arrivals) and assert on every tick:
- **No double-assignment**: no resource id is ever attached to two active patients simultaneously
- **No capacity violation**: `occupied[type] <= capacity[type]` for every resource type at every tick
- **No lost patients**: every patient is in exactly one state (`waiting`, `assigned`, `treated`, `discharged`) — never both waiting and assigned, never neither
- **Monotonic wait bonus**: a patient's own score never decreases while waiting
- **Allocation faithfulness**: every `treated` patient actually held all resources their triage level required, for the full duration
- Wire this as an actual `pytest` suite plus a standalone `run_invariant_stress_test.py` script that Person C can run before the demo as a final sanity check — "we ran 10,000 simulated ticks with zero violations" is a genuinely strong line to have ready.

### Phase 6 — Statistics & Strategy Comparison Engine — *9:30–11:00*
```python
get_stats() -> {
  "avg_wait_time": float,
  "p95_wait_time": float,
  "utilization_by_type": dict[str, float],   # % occupied over the run
  "patients_treated": int,
  "patients_waiting": int,
  "starvation_events": int,   # patients who waited > threshold with no allocation
}
```
For the comparison feature: run the **same recorded arrival sequence** through each strategy independently (deterministic replay, no live randomness) and diff the stats. This is what makes the comparison *credible* rather than anecdotal — same patients, same arrival times, only the strategy changes. Expose this as `run_replay()` (§4) so Person C can trigger it from a "Compare Strategies" button and Person D can render it as a side-by-side bar/line chart.

### Phase 7 — Stretch: Advanced Realism *(only after Phase 5 passes clean — 11:00–13:00 if time allows)*
Attempt these in order, and stop the moment you're back-scheduled against the master timeline's 13:00 checkpoint:
1. **Contention-aware allocation weighting refinement** (extend §Phase 4.3 with real utilization feedback rather than a flat threshold) — cheap, do this first
2. **Two-tier resource model**: split `BED`/`ICU_BED` (held for full stay duration) from `DOCTOR`/`NURSE` (needed intermittently, released and re-acquired for rounds/procedures) — much more realistic, meaningfully more complex state machine; only attempt if Phase 5's test suite is green and you have a clean 2+ hour block
3. **Batch optimizer for strategy 3 (optional, high-risk/high-reward)**: use OR-Tools CP-SAT to solve a small weighted-matching ILP over the current tick's waiting queue and free resources, maximizing total priority-weighted patients served, and compare its output against the greedy heuristic's output in your stats/demo ("greedy achieved 94% of the provably optimal ILP solution, at a fraction of the compute cost" is an excellent line if you get here — but this is genuinely optional; don't let it threaten Phase 0–6)

### Phase 8 — Integration & Freeze — *13:00 checkpoint onward*
- By 13:00 your engine should be feature-frozen against the master timeline's working-prototype checkpoint — only bug fixes from here unless Phase 7 items are clearly ahead of schedule
- Sit with Person C during their bug-bash window (18:00–20:00) to jointly fuzz the API↔engine boundary — most real bugs live at that seam, not inside your pure functions
- Hand Person D the exact field names/shapes from `get_stats()` and `run_replay()` early (don't let this be a last-minute Slack message at hour 20)

---

## 6. What to Say in the Demo (your 30 seconds)

When the strategy-comparison segment comes up, be ready to state plainly: *"Urgency-only starves low-priority patients — average wait time for Level 5 patients grows unbounded. Adding wait-time weighting bounds that, but can't fully prevent resource contention. Our utilization-aware strategy reduces average wait time by [X]% and raises ICU utilization by [Y]% on the identical replayed patient batch — same patients, same arrival times, only the strategy changed."* Numbers from a real replay run beat any amount of hand-waving.
