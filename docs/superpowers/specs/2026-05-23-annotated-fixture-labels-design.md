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

The label is fixed at decoration time and applies to every consumer scenario. There is no per-consumer override and no way to label an undecorated fixture without editing it. `@pytest.mark.parametrize` values appear in the report as a column table (`plugin.py:_group_parameterized`) but have no narrative position in the scenario's step list — the reader has to translate `{name}` placeholders back to the table mentally.

## Approach

Read `Annotated` metadata from the test function signature in `pytest_runtest_setup`, after fixture setup, before the test body runs. For each test parameter:

- If its annotation carries a `StepDescriptor` (returned by `given(...)`), use it to graft or override a step in the active scenario.
- The descriptor's text replaces (or supplies, when absent) the fixture's labeled step. Recorded body steps from a decorated fixture are preserved by default and can be dropped with `flat=True`.
- For parametrize parameters, the descriptor produces a leaf `given` step in the scenario's step list; the existing param templatizer rewrites embedded values into `{name}` placeholders.

The recording machinery added by the fixture-step-recording spec is reused without changes. Only the grafting path is extended.

## API

### `given(text, *, flat=False)`

`given()` continues to return a `StepDescriptor`. New keyword:

```python
def given(text: str, *, flat: bool = False) -> StepDescriptor: ...
```

- `flat=False` (default): when used to override a decorated fixture, the recorded body (children and attachments under the fixture's root step) is preserved.
- `flat=True`: drop the recorded `root.children` and `root.attachments`; render only the leaf label.

`when()` and `then()` retain their current signatures. They are not extended with `flat`, and they are rejected when used inside `Annotated` (see "Forbidden usage" below).

### Usage

```python
# Override a decorated fixture's label, keep its recorded body
def test_a(machine: Annotated[Machine, given('a fancy espresso machine')]): ...

# Same, but drop the body and render only the leaf
def test_b(machine: Annotated[Machine, given('a fancy espresso machine', flat=True)]): ...

# Label an undecorated fixture (leaf step; no body recording possible)
def test_c(beans: Annotated[Beans, given('freshly ground beans')]): ...

# Label a parametrize value (leaf step; placeholder rendered per case)
@pytest.mark.parametrize('cup_size', [200, 300])
def test_d(cup_size: Annotated[int, given('a {cup_size} ml cup')]): ...
```

### Parametrize parameters and placeholder syntax

`Annotated` metadata is evaluated **at function-definition time**, so the parameter name in the test signature is not a value in scope — `f'a {cup_size} ml cup'` would `NameError`, and a bare `'a {cup_size} ml cup'` is the only thing that does anything useful. This differs from the `with given(f'a {cup_size} ml cup')` idiom inside the test body, where the f-string interpolates the runtime value before recording.

For parametrize parameters, **write `{name}` placeholders directly** in the Annotated text. The renderer (`renderer.py:_make_highlight_filter`) preserves and color-codes `{name}` tokens; per-case values appear in the parameter table below the step list.

The existing `_templatize_step_text` value-substitution path still runs over Annotated text, but in the placeholder form it is a no-op (the literal value of the first case is not present in the text, so nothing is replaced). Writing a literal value instead — e.g. `given('a 200 ml cup')` — happens to work for the first case (the templatizer rewrites `200` → `{cup_size}`) but is order-dependent and fragile; prefer placeholders.

Multi-name parametrize is handled per parameter — each name is its own entry in `callspec.params` and `item.fixturenames`, and the resolution rules in the next section fire independently per parameter:

```python
@pytest.mark.parametrize('cup_size,beans_g', [(200, 18), (300, 22)])
def test_e(
    cup_size: Annotated[int, given('a {cup_size} ml cup')],
    beans_g: Annotated[int, given('{beans_g} g of beans')],
): ...
```

A parametrize parameter **without** Annotated continues to appear only in the parameter table — no step is synthesized (current behavior, unchanged).

> **Footgun (pre-existing, not introduced here).** `_templatize_step_text` uses plain `str.replace`, so a literal parameter value appearing as a substring of unrelated text in a step (e.g. `'a 200 ml cup with 200 beans'` when `cup_size=200`) will be double-substituted into `{cup_size}`. The placeholder form sidesteps this; a future spec may tighten the templatizer.

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
| No | Yes | Current behavior: graft the recorded subtree with the decorator's label. |
| Yes (fixture) | No | Synthesize a leaf `given` step with the Annotated text. `with given(...)` inside the fixture body still raises (unchanged — undecorated fixtures cannot record). |
| Yes (fixture) | Yes | Deep-copy the recorded subtree, replace `root.text` with the Annotated descriptor's text. `root.phase` stays `given`. If `flat=True`, also clear `root.children` and `root.attachments`. |
| Yes (parametrize) | n/a | Synthesize a leaf `given` step with the Annotated text. Users should embed `{name}` placeholders directly (see "Parametrize parameters and placeholder syntax" above); the existing `_templatize_step_text` pass still runs and would also rewrite literal first-case values into `{name}` placeholders, but the placeholder form is the recommended idiom. |

   (`@when` / `@then` on fixtures are already rejected at fixture-setup time, so only `@given` is reachable here.)

5. **Ordering.** Grafted steps (decorator recordings + Annotated leaves + Annotated-overridden recordings) follow `item.fixturenames` order, unchanged from today. Direct parametrize parameters are injected into `item.fixturenames` by pytest's metafunc machinery (the same list that drives fixture resolution), so they interleave naturally with fixture grafts at the top of the scenario, before test body steps. Integration test 9 below pins the observed order.

### Forbidden usage

Hard errors (raise `PytestGivenError` during `pytest_runtest_setup`, failing the scenario with a clear message):

- `Annotated[..., when('...')]` or `Annotated[..., then('...')]` on any parameter.
- Multiple `StepDescriptor`s on a single parameter.
- `Annotated[..., given('...')]` on a parameter that is neither a fixture nor a parametrize value.

(A fixture decorated with `@when` or `@then` is independently rejected by `pytest_fixture_setup` regardless of Annotated usage — see the fixture-step-recording spec.)

`self` and `cls` are skipped silently — they are never fixtures, and warning on them would be noise for class-based tests.

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/decorators.py` | Extend `given(text)` to `given(text, *, flat: bool = False)`. Store `flat` on `StepDescriptor`. Default `flat=False` preserves current behavior. |
| `src/pytest_given/plugin.py` | In `pytest_runtest_setup`, replace `_graft_fixture_recordings(item)` with a new function that walks `item.fixturenames` in order, resolves Annotated metadata per parameter via `typing.get_type_hints(item.function, include_extras=True)`, and either grafts a fixture recording (optionally overriding label/dropping body) or synthesizes a leaf step. The recording lookup logic is reused. |
| `src/pytest_given/collector.py` | Add `graft_leaf_given(text: str)` that appends a leaf `Step(phase='given', text=text)` to the current scenario. Extend `graft_recording(recording, *, override_text: str \| None = None, flat: bool = False)` so the existing call site (no overrides) is unaffected while Annotated paths can override text and drop body. |
| `src/pytest_given/errors.py` | No new error type; reuse `PytestGivenError`. |
| `tests/unit/test_step_descriptor.py` (or new `tests/unit/test_decorators.py`) | Test that `given('x', flat=True)` stores the flag; that `when`/`then` retain their signatures. |
| `tests/integration/test_plugin.py` | New end-to-end tests (see below). |

No changes to the JSON data model. No changes to the renderer. The templatizer at `plugin.py:_templatize_steps` already walks the full scenario step tree and needs no extension — Annotated text is a plain string that flows through the same path.

## Test Coverage

Integration tests in `tests/integration/test_plugin.py`:

1. **Undecorated fixture + Annotated** → leaf `given` step appears with the Annotated text; the fixture body is not bracketed for recording, and `with given(...)` inside it still raises.
2. **Decorated fixture + Annotated, no `flat`** → recorded subtree is grafted with the Annotated label as the root; body children survive.
3. **Decorated fixture + Annotated, `flat=True`** → recorded subtree is grafted with the Annotated label; root has no children and no attachments.
4. **Parametrize param + Annotated** → leaf `given` step appears in the scenario; `{name}` placeholders in the Annotated text survive parametric grouping unchanged and render with the existing param highlight. A second variant uses `@pytest.mark.parametrize('a,b', [...])` with Annotated on both names to pin per-parameter handling.

   Also assert that a parametrize parameter **without** Annotated remains absent from the step list (only the parameter table reflects it).
5. **Annotated `when(...)` / `then(...)`** → `PytestGivenError`.
6. **Annotated `given(...)` on a non-fixture / non-parametrize parameter** → `PytestGivenError`.
7. **Multiple `StepDescriptor`s on one parameter** → `PytestGivenError`.
8. **Indirect parametrize fixture**: a fixture parametrized via `@pytest.mark.parametrize('name', [...], indirect=True)` with Annotated override behaves like the fixture case — label is overridden, body preserved (or dropped with `flat`).
9. **Mixed usage in the same scenario** — one decorator-only fixture, one Annotated-override fixture, one parametrize Annotated — all appear in `item.fixturenames` order at the top of the scenario.
10. **Class-based test method** — `self` is skipped without error; Annotated on other params behaves as elsewhere.

Unit tests in `tests/unit/`:

- `StepDescriptor.flat` defaults to `False` and is set when `given(text, flat=True)` is used.
- `when()` and `then()` do not accept `flat` (TypeError on misuse — comes from the function signature, not custom code).

## Out of Scope

- `Annotated` carrying `when(...)` or `then(...)` — explicitly forbidden. The narrative for actions and assertions lives in the test body via `with when(...)` / `with then(...)`.
- A fixture-side opt-in for "this fixture's body is always implementation detail" (i.e., decorating a fixture so that all consumers get `flat=True` by default). May be useful later; not needed now.
- Auto-templatization of Annotated text against fixture-resolved values that are not parametric (e.g., interpolating a constant from a session-scoped fixture into the label). Annotated metadata is evaluated at function-definition time and cannot reference runtime values; users use the existing `with given(f'... {value}')` pattern inside the test body for that.
- Reordering grafted steps by phase. All grafts follow `item.fixturenames` order; phase is not used to reorder.
