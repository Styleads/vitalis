# Agent prompts (Person A)

Flow for every step: paste the prompt, read the plan, let it implement, **read the diff yourself**, run `pytest tests/engine -q` yourself, then commit. Do not paste the next prompt until the current step is green and committed. Save any agent plans to `docs/ai-notes/`.

## Your schedule (24h plan, Person A)
| Hours | Goal |
|---|---|
| 0:00-0:30 | Team sync; confirm ENGINE_SPEC section 13 and TEAM_CONTRACT. Commit docs + AGENTS.md. |
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

## Prompt 0: session start (paste at the start of every new agent session)
```
Read AGENTS.md, docs/ENGINE_SPEC.md and docs/TEAM_CONTRACT.md fully. Do not write
code yet. Summarize back in <=12 bullets: the constraints you must obey, the public
interface, the event ordering rule, the allocation pass, and the invariants. List
any ambiguity or contradiction you find in the spec. Do not fix them, only list them.
```

## Step A: tests first
```
Write the test suite for the engine from docs/ENGINE_SPEC.md ONLY (not from any
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

## Step B: stubs
```
Create importable stubs in engine/ (types.py, config.py, arrivals.py,
resources.py, engine.py, invariants.py, headless.py, __init__.py) with the
dataclasses, enums, and signatures from spec sections 4 and 12. Function bodies
raise NotImplementedError. Do not modify any test. Run pytest and confirm tests
fail for NotImplementedError, not import errors.
```

## Slice 1: config and arrival generator
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

## Slice 2: resource pool and atomic reservation
```
Implement engine/resources.py per spec section 8: ResourcePool built from
config.capacities (unit ids sequential across types in enum order), try_reserve
(check-then-commit, lowest free ids, returns None with zero state change on
failure), release (honors pending_off). Also capacity helpers used later by
set_capacity (count of free/occupied/failed/off per type). Make
tests/engine/test_reservation.py pass. Write the code plainly; I must be able to
explain try_reserve line by line. Run pytest and report.
```

## Slice 3: event heap, step loop, allocation pass
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

## Slice 4: scenario hooks
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

## Slice 5: snapshot and stats_raw
```
Implement Engine.snapshot() and Engine.stats_raw() exactly per spec section 12
(schemas included). Snapshot: JSON-safe copies only, queue in next-pass order
with score, last 50 log events. stats_raw: per-type busy_s/available_s integrals
(available excludes FAILED/OFF), per-patient records, counts. Make
test_snapshot.py pass and add a test where utilization is hand-computed for a
tiny scenario. Run pytest and report.
```

## Slice 6: AI hooks
```
Implement triage_fn and los_fn handling at ARRIVAL per spec section 10, including
HOOK_ERROR fallback for exceptions and invalid values (urgency outside 1..5,
negative or non-int LOS). los_fn sets predicted_service_time only. Make
test_hooks.py pass. Run pytest and report.
```

## Slice 7: CLI harness (hour-4 checkpoint)
```
Create scripts/run_cli.py: builds default_config(), generates arrivals with a seed
from argv, defines a FIFO strategy (score = -arrival_time), runs the engine
through 10,000 steps with debug_invariants=True, prints a log tail and a
stats_raw summary (avg wait per urgency, utilization per type), and exits
non-zero on any invariant failure. Also add an option --strategy urgency that
uses score = (6 - urgency) * 1000 - arrival_time/1000 as a baseline.
```

## Slice 8 (optional): M/M/c sanity check
```
Add tests/engine/test_mmc_sanity.py: ONE resource type with c units, every
patient needing exactly one unit, exponential service, Poisson arrivals, FIFO,
long horizon, several seeds. Compare mean simulated wait against Erlang C and
assert agreement within a tolerance you justify from run length. If the engine
config cannot express this, stop and tell me what is missing; do NOT alter
engine logic to force a pass.
```

## Slice 9 (only if you take the AI component): `ml/`
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

## Utility prompts

**Diff review before every commit**
```
Review my staged diff only against AGENTS.md and ENGINE_SPEC.md. Flag: spec
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
