# Fixture Step Recording — Design Spec

## Goal

Make `@given/@when/@then` on fixtures, and `with given(...)` / `attach(...)` calls *inside* fixture bodies, behave correctly across all pytest fixture scopes (function, class, module, session) and across parametrized fixtures. The fixture body is where the "Given" of a scenario often actually happens (DB seeding, service config, browser navigation); excluding it makes reports misrepresent the scenario.

## Background

Current behavior (`plugin.py:93-107`) lifts the fixture decorator's label out of execution: `_get_fixture_steps()` reads `_step_descriptor` from every name in `item.fixturenames` and pushes an empty step into the test's scenario. This correctly attributes the *label* to each consumer test (including each test using a session-scoped fixture), but it has three leaks:

1. `with when(...)` / `attach(...)` calls *inside* a fixture body land on whichever scenario was active when the body actually ran — only the first consumer for session/module/class scope. Other consumers see the bare label with no detail.
2. The decorator's wrapper at `decorators.py:45-51` does not push/pop a step at call time; the recorded duration is always zero and there is no parent step to nest body steps under.
3. Programming errors that should fail loudly (steps at import time, steps in conftest hooks, steps in undecorated fixtures) silently no-op.

## Approach

Record-and-replay, driven by pytest's fixture lifecycle hooks:

- When a decorated fixture body runs, record a subtree of steps/attachments into a per-instance buffer.
- When a test materializes its scenario, graft the recorded subtree under the fixture's labeled step.

For function-scoped fixtures this collapses to "record straight into the active scenario." Session/module/class scopes hit the buffer once and replay into each consumer's scenario tree.

## Recording

### Hook

Bracket fixture body execution via `pytest_fixture_setup`:

```python
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    desc = getattr(fixturedef.func, '_step_descriptor', None)
    if desc is None:
        outcome = yield
        return
    recording = FixtureRecording(phase=desc.phase, text=desc.text)
    token = _start_recording(recording)  # state machine: FIXTURE_SETUP(name)
    try:
        outcome = yield
    finally:
        _finish_recording(token)
        key = _fixture_instance_key(fixturedef, request)
        _recordings[key] = recording
```

### Fixture instance key

Recordings are keyed by fixture *instance*, not by fixture name, so parametrized fixtures get a recording per variant. The key combines:

- The `FixtureDef` identity (covers shadowing and per-conftest defs).
- The param id (`request.param` index when parametrized; `None` otherwise).

`FixtureDef.cached_result` identity also works — it changes when the cache is invalidated and a new instance is created.

### What gets recorded

While the recording is active:

- `with given/when/then(...)`: appended as a child of the recording's root step.
- `attach(...)`: appended to the innermost open recording step.
- Nested fixture activations: do not nest into the parent recording. Each decorated fixture owns its own recording; they are grafted as siblings into the consumer test in pytest's fixture-resolution order.

## Replay

When a test materializes its scenario in `pytest_runtest_setup`, iterate `item.fixturenames` in pytest's resolution order. For each name whose `FixtureDef.func` has a `_step_descriptor`:

1. Look up the recording by the (`FixtureDef`, param) instance key for *this* item.
2. Deep-copy the recorded subtree into the scenario's top-level step list.

Deep copy is required so that parametrized templatization (see below) does not mutate the shared recording for other consumers.

### Parameter templatization

The existing templatizer at `plugin.py:227-247` walks the scenario's step tree and replaces param values with `{name}` placeholders, using names from `callspec.params`. Pytest's `callspec.params` already includes indirectly-parametrized fixture params — so step text interpolated inside a fixture body (e.g., `with given(f"a shop with {request.param} items"):`) will render as `{shop_size}` in the report without any new logic, as long as the recording is grafted in before templatization runs.

## Lifecycle State Machine

A small state on the collector centralizes the rules for where `given/when/then/attach` are legal:

```
IDLE
  ├── start_scenario ────────> TEST
  └── pytest_fixture_setup ──> FIXTURE_SETUP(name)
                                 ├── yield ─────────> FIXTURE_TEARDOWN(name)
                                 └── finish ────────> IDLE | TEST
TEST
  └── finish_scenario ───────> IDLE
```

`given/when/then/attach` consult the current state:

| State | Behavior |
|-------|----------|
| `TEST` | Record into the active scenario (current behavior). |
| `FIXTURE_SETUP(name)` | Record into the fixture's recording buffer. |
| `FIXTURE_TEARDOWN(name)` | Raise `PytestGivenError` — teardown is technical, not narrative. |
| `IDLE` | Raise `PytestGivenError` — no scenario or fixture owns the step. |

Generator-fixture transition from `FIXTURE_SETUP` to `FIXTURE_TEARDOWN` happens at the `yield`. This can be hooked via the `pytest_fixture_post_finalizer` hook or by wrapping the generator.

## Forbidden Contexts

Hard errors (raise `PytestGivenError`):

- Module top-level / import time.
- Pytest hooks in conftest (`pytest_collection_modifyitems`, custom `pytest_runtest_*`, etc.).
- Fixture teardown (post-yield in generator fixtures).
- Class-level `tearDownClass` (unittest style).
- Fixture body of an *undecorated* fixture — without a labeled root, there is no honest place to graft children.

Soft warning (`PytestUserWarning`):

- Test function without `@scenario` — gradual migration is a real use case, so do not block the run.

## Decorator Behavior

`@given/@when/@then` as a decorator on a fixture currently only attaches `_step_descriptor` metadata. Under this design the metadata role is preserved (used to detect that a fixture should be recorded) but the wrapper no longer needs to push/pop at call time — recording is driven by the `pytest_fixture_setup` hook instead.

`@given/@when/@then` as a decorator on a *non-fixture* helper function: out of scope for this spec. Helpers should use `with given(...)` inline, which records under whatever state is currently active.

## Threading

`ContextVar`-based state does not propagate to `threading.Thread.start()`. Steps emitted from worker threads silently vanish. Document this clearly; asyncio is unaffected (`ContextVar` propagates to tasks).

## Files Changed

| File | Change |
|------|--------|
| `src/pytest_given/collector.py` | Add `RecordingState` enum and current-state field; route `push_step`/`pop_step`/`attach` through the state machine; add per-fixture-instance recording buffers; expose grafting helper. |
| `src/pytest_given/plugin.py` | Replace `_get_fixture_steps()` flat push/pop with `pytest_fixture_setup` hookwrapper that brackets recording; in `pytest_runtest_setup`, graft recordings by fixture instance key instead of pushing empty steps. |
| `src/pytest_given/decorators.py` | Decorator wrapper no longer needs to be call-time transparent; keep `_step_descriptor` metadata as the marker. Context-manager `__enter__`/`__exit__` consult the collector state and raise/warn per the table above. |
| `src/pytest_given/__init__.py` | Export `PytestGivenError`. |
| `tests/unit/test_collector.py` | New tests for state machine transitions and forbidden-context errors. |
| `tests/integration/test_plugin.py` | New tests for session/module/class fixture recording, generator fixture teardown rejection, parametrized fixture per-variant recordings, nested decorated fixtures. |

No changes to the JSON data model or renderer.

## Out of Scope

- `@given/@when/@then` on non-fixture helper functions as a recording-capable construct (use inline context managers instead).
- Recording teardown steps as a separate narrative (teardown is forbidden by design).
- Cross-thread step propagation.
- Automatic param-name inference for f-string interpolation that does not exactly match a `callspec.params` value (templatizer already handles the common case via string replacement).
