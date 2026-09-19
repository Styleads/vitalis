# AGENTS.md: rules for the coding agent (MedFlow engine)

Read this file and `docs/ENGINE_SPEC.md` before every task. The spec is the source of truth. `docs/TEAM_CONTRACT.md` defines what the other team members depend on.

## Scope
- Work only in `engine/`, `tests/engine/`, `scripts/`, and `ml/` (when a task says so). Do not touch `strategies/`, `api/`, or `frontend/`; they belong to teammates.
- Do NOT edit `docs/ENGINE_SPEC.md`, `docs/TEAM_CONTRACT.md`, this file, or any public interface signature. If the spec looks wrong, ambiguous, or contradictory, STOP and ask.

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
