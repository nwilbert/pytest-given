# Annotated Fixture & Parametrize Labels — Design Spec

## Goal

Let scenarios attach a `given` step label to a fixture or parametrize parameter at the *call site* via PEP 593 `Annotated`:

```python
from typing import Annotated
from pytest_given import scenario, given

@scenario('Brew espresso')
def test_brew(
    machine: Annotated[CoffeeMachine, given('a fancy espresso machine')],
    beans: Annotated[Beans, given('freshly ground beans')],
):
    ...
```

This complements the existing fixture-side `@given/@when/@then` decorator. The same fixture can be described differently from different scenarios; a plain `@pytest.fixture` can be promoted to a labeled step without modifying the fixture itself; and parametrize parameters can be narrated alongside the parameter table.

## Background

Today, a fixture appears as a labeled `given` step in the report only if it is decorated:

```python
@given('a coffee machine')
@pytest.fixture
def machine(): ...
```

The label is fixed at decoration time and applies to every consumer scenario. There is no per-consumer override and no way to label an undecorated fixture without editing it. `@pytest.mark.parametrize` values appear in the report as a column table (`plugin.py:_group_parameterized`) but have no narrative position in the scenario's step list — the reader has to translate parameter values back to the table mentally.

## Approach

Read `Annotated` metadata from the test function signature in `pytest_runtest_setup`, after fixture setup, before the test body runs. For each test parameter:

- If its annotation carries a `StepDescriptor` (returned by `given(...)`), use it to graft or override a step in the active scenario.
- The descriptor's `Narration` replaces (or supplies, when absent) the fixture's labeled step. Recorded body steps from a decorated fixture are preserved.
- For parametrize parameters, the descriptor produces a leaf `given` step in the scenario's step list. Dynamic per-case text uses `pytest_given.Template(...)` (the same deferred-substitution form `@scenario(Template(...))` uses).

The recording machinery added by the fixture-step-recording spec is reused without changes. The grafting path is rewritten to walk `item.fixturenames` order so Annotated-driven parametrize leaves interleave naturally with fixture grafts.

## API

`given()` is unchanged. `Annotated[..., given(text)]` accepts the same forms `given()` already accepts in other contexts, with one form forbidden:

| Form | Accepted in `Annotated` | Why |
|---|---|---|
| `given('static text')` | Yes | Plain label, no substitution needed. |
| `given(Template('a {cup_size} ml cup'))` | Yes | Deferred placeholder, substituted from `callspec.params` per case — the same mechanism `@scenario(Template(...))` uses. |
| `given(t'a {cup_size} ml cup')` | **No** | T-strings evaluate at function-definition time; the parameter name isn't in scope, so the t-string would `NameError` (or, for an unrelated in-scope name, eagerly interpolate the wrong value). Rejected with `PytestGivenError`. |

### Usage

```python
# Override a decorated fixture's label, keep its recorded body
def test_a(machine: Annotated[Machine, given('a fancy espresso machine')]): ...

# Label an undecorated fixture (leaf step; no body recording possible)
def test_b(beans: Annotated[Beans, given('freshly ground beans')]): ...

# Label a parametrize value with a dynamic per-case placeholder
@pytest.mark.parametrize('cup_size', [200, 300])
def test_c(cup_size: Annotated[int, given(Template('a {cup_size} ml cup'))]): ...
```

### Parametrize parameters and placeholder syntax

For dynamic per-case narration on parametrize parameters, use `pytest_given.Template(...)`. This is the canonical deferred-substitution form across the project — `@scenario(Template(...))` and decorated helpers (per the template-helper-args spec) use it the same way.

`Annotated[int, given(Template('a {cup_size} ml cup'))]` produces a `StepDescriptor` whose `Narration` carries structured `NarrationPlaceholder` parts. At render time, `_templatize_narration` (`plugin.py`) discovers the matching parametrize column and the renderer's structural `narration` filter color-codes the placeholder. Per-case values appear in the parameter table below the step list.

A plain string `given('a {cup_size} ml cup')` is not interpreted as a template — `narration_from(str)` produces a `Narration` with empty `parts`, so the renderer emits the literal text `a {cup_size} ml cup` (braces and all). If the test author wanted a placeholder, they need `Template(...)`. Mistakes here are loud, not silent.

Multi-name parametrize is handled per parameter — each name is its own entry in `callspec.params` and `item.fixturenames`, and the resolution rules in the next section fire independently per parameter:

```python
@pytest.mark.parametrize('cup_size,beans_g', [(200, 18), (300, 22)])
def test_e(
    cup_size: Annotated[int, given(Template('a {cup_size} ml cup'))],
    beans_g: Annotated[int, given(Template('{beans_g} g of beans'))],
): ...
```

A parametrize parameter **without** Annotated continues to appear only in the parameter table — no step is synthesized (current behavior, unchanged).

## Resolution Rules

For each parameter in the test function signature, excluding `self` and `cls`:

1. **Extract Annotated metadata.** Call `typing.get_type_hints(func, include_extras=True)` once per test function. For each parameter, scan the metadata tuple of any `Annotated[...]` annotation for `StepDescriptor` instances.
2. **Validate the descriptor.** If two or more `StepDescriptor`s appear on a single parameter, raise `PytestGivenError('multiple given()/when()/then() on parameter <name>')`. If the descriptor's phase is not `given`, raise `PytestGivenError("only given() is supported inside Annotated; use 'with when(...)' / 'with then(...)' in the test body for <name>")`.
3. **Classify the parameter.** Using `item`:
   - If `item.callspec` exists and `name in item.callspec.params` **and** the session fixture manager does not return a user-defined `FixtureDef` for the name → **parametrize parameter** (a direct parametrize value with no fixture body).
   - Else if the fixture manager returns a `FixtureDef` whose `func` is a user-defined callable for the name → **fixture parameter**. This branch covers both ordinary fixtures and indirect-parametrize fixtures (where the name is *both* in `callspec.params` and has a real fixture).
   - Otherwise → raise `PytestGivenError('Annotated given() on <name> is neither a fixture nor a parametrize parameter')`.

   "User-defined `FixtureDef`" is distinguished from pytest's synthetic parametrize defs by inspecting the def — concrete approach is a plan-time decision (`fixturedef.baseid` non-empty, or `fixturedef.func` not being a pytest internal). The classification is what matters for the spec; the discriminator is implementation detail.
4. **Apply per category.**

| Annotated `given(...)` on param | Fixture has `@given` decorator | Behavior |
|---|---|---|
| No | No | No graft (current behavior for parametrize params; nothing to record for undecorated fixtures). |
| No | Yes | Current behavior: graft the recorded subtree with the decorator's narration. |
| Yes (fixture) | No | Synthesize a leaf `given` step with the Annotated `Narration`. `with given(...)` inside the fixture body still raises (unchanged — undecorated fixtures cannot record). |
| Yes (fixture) | Yes | Deep-copy the recorded subtree, replace `root.narration` with the Annotated descriptor's narration. `root.phase` stays `given`; `root.children` and `root.attachments` are preserved as-is. |
| Yes (parametrize) | n/a | Synthesize a leaf `given` step with the Annotated `Narration`. For per-case dynamic text, the descriptor wraps a `Template(...)` (see "Parametrize parameters and placeholder syntax" above); `_templatize_narration` then rewrites matching `NarrationPlaceholder` parts to point at the parametrize column. |

   (`@when` / `@then` on fixtures are already rejected at fixture-setup time, so only `@given` is reachable here.)

5. **Ordering.** Grafted steps interleave fixture-recording grafts with Annotated leaves following `item.fixturenames` order — pytest's metafunc machinery puts direct parametrize parameters in the same list that drives fixture resolution, so iterating it gives a natural top-of-scenario layout before test-body steps. This replaces today's setup-order iteration over `collector.recordings()` (which works for fixture-only grafts but can't position Annotated leaves on parametrize params, since those have no recording to be ordered by setup time). In practice setup order and `fixturenames` order coincide for pure fixture grafts (dependencies set up before dependents); the change is necessary for the parametrize case and a no-op for the existing fixture case. Integration test 9 below pins the observed order.

### Forbidden usage

Hard errors (raise `PytestGivenError` during `pytest_runtest_setup`, failing the scenario with a clear message):

- `Annotated[..., when('...')]` or `Annotated[..., then('...')]` on any parameter.
- `Annotated[..., given(t'...')]` on any parameter (t-strings are nonsensical in Annotated metadata; see the API table).
- Multiple `StepDescriptor`s on a single parameter.
- `Annotated[..., given('...')]` on a parameter that is neither a fixture nor a parametrize value.

(A fixture decorated with `@when` or `@then` is independently rejected by `pytest_fixture_setup` regardless of Annotated usage — see the fixture-step-recording spec.)

`self` and `cls` are skipped silently — they are never fixtures, and warning on them would be noise for class-based tests.

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/plugin.py` | In `pytest_runtest_setup`, replace `_graft_fixture_recordings(item)` with a new function that walks `item.fixturenames` in order, resolves Annotated metadata per parameter via `typing.get_type_hints(item.function, include_extras=True)`, and either grafts a fixture recording (optionally overriding the root narration) or synthesizes a leaf step. Reject t-strings on extracted descriptors here (the Annotated resolution path is the natural choke point). The recording lookup logic (`fm.getfixturedefs`, `_step_descriptor`, `cached_result`) is reused. |
| `src/pytest_given/capture/collector.py` | Add `graft_leaf_given(narration: Narration)` that appends a leaf `Step(phase='given', narration=narration)` to the current scenario. Extend `graft_recording(recording, *, override_narration: Narration \| None = None)` so the existing call site (no overrides) is unaffected while the Annotated path can override the root narration. |
| `src/pytest_given/capture/decorators.py` | No change. `given/when/then` signatures stay as-is. |
| `src/pytest_given/model/errors.py` | No change. Reuse `PytestGivenError`. |
| `tests/integration/test_plugin.py` | New end-to-end tests (see below). |

No changes to the JSON data model. No changes to the renderer. No new unit tests are needed by this spec — the Annotated → descriptor → narration plumbing is exercised end-to-end. The structural templatize at `plugin.py:_templatize_narration` already walks the full scenario step tree and rewrites matching `NarrationValue` / `NarrationPlaceholder` parts against parametrize columns — Annotated narrations from `Template(...)` flow through the same path unchanged.

## Test Coverage

Integration tests in `tests/integration/test_plugin.py`:

1. **Undecorated fixture + Annotated** → leaf `given` step appears with the Annotated narration; the fixture body is not bracketed for recording, and `with given(...)` inside it still raises.
2. **Decorated fixture + Annotated** → recorded subtree is grafted with the Annotated narration as the root; body children and attachments survive.
3. **Parametrize param + Annotated (`Template`)** → leaf `given` step appears in the scenario; the `Template`'s `NarrationPlaceholder` parts survive parametric grouping and render color-coded by the `narration` filter. A second variant uses `@pytest.mark.parametrize('a,b', [...])` with `Template`-wrapped Annotated on both names to pin per-parameter handling.

   Also assert that a parametrize parameter **without** Annotated remains absent from the step list (only the parameter table reflects it).
4. **Parametrize param + Annotated (plain string)** → the literal text (including any `{name}` braces) renders verbatim in every case — no substitution, no highlight. Confirms `Template(...)` is the only path to per-case dynamic narration.
5. **Annotated `when(...)` / `then(...)`** → `PytestGivenError`.
6. **Annotated `given(t'...')`** → `PytestGivenError` (t-strings are forbidden in Annotated metadata).
7. **Annotated `given(...)` on a non-fixture / non-parametrize parameter** → `PytestGivenError`.
8. **Multiple `StepDescriptor`s on one parameter** → `PytestGivenError`.
9. **Indirect parametrize fixture**: a fixture parametrized via `@pytest.mark.parametrize('name', [...], indirect=True)` with Annotated override behaves like the fixture case — narration is overridden, body preserved.
10. **Mixed usage in the same scenario** — one decorator-only fixture, one Annotated-override fixture, one parametrize Annotated — all appear in `item.fixturenames` order at the top of the scenario.
11. **Class-based test method** — `self` is skipped without error; Annotated on other params behaves as elsewhere.

## Out of Scope

- `Annotated` carrying `when(...)` or `then(...)` — explicitly forbidden. The narrative for actions and assertions lives in the test body via `with when(...)` / `with then(...)`.
- T-strings inside `Annotated` metadata — forbidden, see the API table.
- Auto-templatization of Annotated narration against fixture-resolved values that are not parametric (e.g., interpolating a constant from a session-scoped fixture into the label). Annotated metadata is evaluated at function-definition time and cannot reference runtime values; users use the existing `with given(t'... {value}')` pattern inside the test body for that.
- Reordering grafted steps by phase. All grafts follow `item.fixturenames` order; phase is not used to reorder.
- Hiding a decorated fixture's recorded body when overriding its label from `Annotated`. The override always preserves the body.
