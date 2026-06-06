# Flat Step Display — Design Spec

## Goal

Let any step opt out of rendering its recorded body. A `flat=True` step appears in the report as a leaf — its children and attachments are hidden — even though the collector captured them normally.

```python
from pytest_given import given, when, then

# In-body context manager: hide helper-driven internal recordings
with given(t'a fully provisioned environment', flat=True):
    bootstrap()  # internally calls `with given(...)`, `attach(...)` — all hidden

# Fixture decorator: hide DB seeding internals from every consumer's report
@given('a seeded database', flat=True)
@pytest.fixture
def db(): ...

# Helper decorator (per the helper-args spec): collapse a multi-step routine
@when(Template('I insert ${amount}'), flat=True)
def insert(machine, amount): ...

# Annotated override: collapse someone else's noisy fixture body at the call site
def test_x(db: Annotated[Database, given('a fresh DB', flat=True)]): ...
```

`flat` works the same way at every site, on all three phases, and is honored by the renderer (not the collector). Errors auto-reveal the hidden body.

## Background

The collector records a step's body as children + attachments under its root step. That richness is the point — readers see the narrative without having to trace through helper code. But it's also a liability when:

- A high-level step orchestrates lower-level helpers whose internal narration is noise from the reader's perspective.
- A fixture's body is implementation detail; a test-level Annotated override wants a clean leaf.
- A scenario author wants to hide setup plumbing behind a single abstraction line.

Today the only way to achieve this is to not record the body at all — e.g. by using a plain `@pytest.fixture` without `@given`, or by calling helpers that don't use `with given(...)`. That loses the recording's other affordances (consistent step nesting, attachments-for-debugging) and forces the author to choose between "always show" and "never recorded."

`flat=True` adds a third option: **always record, decide later whether to show**. The decision lives on the step itself; the renderer applies it.

## Approach

`flat` is a display property of a `Step`. It rides on the dataclass, survives JSON round-trips, and is read at render time. Recording is unchanged: the collector still pushes/pops, still appends children, still routes attachments to the active step. The renderer skips children + attachments when it sees `flat=True` — unless any descendant carries a failure, in which case it falls back to the full subtree (auto-reveal).

The runtime path is: descriptor stores `flat` → `push_step` / fixture-recording root copies it onto the `Step` → JSON serde preserves it → renderer honors it. No change to the collector's hot path beyond forwarding one bool.

## API

`given()`, `when()`, and `then()` gain a keyword-only `flat: bool = False`:

```python
def given(
    text: str | templatelib.Template | Template,
    *,
    flat: bool = False,
) -> StepDescriptor: ...

def when(
    text: str | templatelib.Template | Template,
    *,
    flat: bool = False,
) -> StepDescriptor: ...

def then(
    text: str | templatelib.Template | Template,
    *,
    flat: bool = False,
) -> StepDescriptor: ...
```

The default `False` preserves current behavior at every call site. `flat` is keyword-only so positional misuse fails at the signature (no custom validation).

### Usage by site

| Site | What `flat=True` hides |
|---|---|
| `with given(t'...', flat=True): ...` | Nested `with given/when/then(...)` blocks and `attach(...)` calls made inside the with-body. |
| `@given('...', flat=True)` on a fixture | The fixture's recorded subtree (everything the body recorded). |
| `@when('...', flat=True)` on a helper | The helper's recorded subtree per call. |
| `Annotated[..., given('...', flat=True)]` | The underlying decorated fixture's recorded subtree, after override. |

In every case, the visible leaf is the step's narration; failures escalate to the scenario; the JSON keeps the full subtree.

### Symmetry across phases

`when` and `then` get `flat` for the same reasons `given` does — they have the same recording semantics. A helper `@when` that internally calls three smaller `@when`-decorated helpers benefits from `flat=True` exactly as a `@given` fixture would. The API mirror is intentional: divergence between the three phase factories is noise.

`when` and `then` remain forbidden in `Annotated` metadata (per the annotated-fixture-labels spec); that's about *where* steps can be authored, not *how* they render once authored.

## Data Model

One new field on `Step`:

```python
@dataclass
class Step:
    phase: Phase
    narration: Narration
    status: str = 'passed'
    children: list[Step] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    error: ErrorInfo | None = None
    flat: bool = False   # NEW
```

`StepDescriptor` gains a parallel `flat: bool` attribute, set in `__init__` from the constructor kwarg. Each path that builds a `Step` from the descriptor reads `flat` off the descriptor and copies it onto the step:

- `Collector.push_step(phase, narration, *, flat=False)` — extended to accept the flag and stamp it onto the new step. The two descriptor wrappers (context-manager `__enter__` and decorator-call wrapper) pass `desc.flat` through.
- `pytest_fixture_setup` (in `plugin.py`) — when building the `FixtureRecording`'s root, sets `root.flat = desc.flat`.

### Serde

`step_to_dict` includes `'flat': True` when `step.flat`, omits the key when `False` — keeps existing JSON files unchanged when nothing opts in. `step_from_dict` defaults to `False` when the key is absent (forward-compatible with older JSON).

## Recording Semantics

**Unchanged.** The collector pushes/pops, nests children, routes attachments to the top of the active stack — exactly as today. `flat` is metadata that travels with the step; it does not alter what gets recorded.

This matters for two reasons:

1. **Auto-reveal needs the body.** If a hidden subtree contains a failure, the renderer reveals it. Recording-time suppression would make this impossible.
2. **Tooling stays open.** A future "show hidden bodies" toggle in the report UI, an external HTML report consumer, or a JSON-level diff tool all keep the full picture.

## Rendering Semantics

The renderer's step template (and the `narration` filter, where step children are walked) checks `step.flat` before recursing into `children` and `attachments`:

```python
def _is_visibly_flat(step: Step) -> bool:
    """A step is rendered flat iff `flat=True` and nothing failed in its body."""
    if not step.flat:
        return False
    return not _has_failed_descendant(step)


def _has_failed_descendant(step: Step) -> bool:
    for child in step.children:
        if child.status == 'failed' or child.error is not None:
            return True
        if _has_failed_descendant(child):
            return True
    return False
```

When `_is_visibly_flat(step)` returns `True`:

- Children are not rendered.
- Attachments on the step are not rendered.
- The step's own `narration`, `status`, `error`, and source-link metadata render normally.

When it returns `False` (either because `flat=False` or because the subtree has a failure), the full body renders unchanged.

The scan is O(steps-in-subtree) per flat step. In practice flat subtrees are small (a fixture body, a helper invocation) and there are few of them per scenario, so the cost is negligible. If a future profile shows it's hot, the dataclass could cache a `_has_failures` derived field after recording finishes — not needed now.

## Annotated Graft Interaction

The annotated-fixture-labels spec proposes a `flat=True` option on `Annotated[..., given(..., flat=True)]` that drops the underlying fixture's recorded `root.children` and `root.attachments` during graft. With this spec landed first, that mechanism collapses to:

```python
# inside the Annotated graft path:
new_root = copy.deepcopy(recording.root)
new_root.narration = override_narration  # from the Annotated descriptor
new_root.flat = desc.flat                # from the Annotated descriptor
collector.current_scenario.steps.append(new_root)
```

No pruning. The renderer hides what needs to be hidden, and auto-reveal still works if the fixture body's recording captured a failure path.

## Implementation Touch Points

| File | Change |
|---|---|
| `src/pytest_given/capture/decorators.py` | Add `flat: bool = False` keyword-only param to `given`, `when`, `then`. Store on `StepDescriptor`. Pass through to `collector.push_step` in `__enter__` and the decorator-call wrapper. |
| `src/pytest_given/capture/collector.py` | Extend `push_step(phase, narration, *, flat=False)` to stamp `flat` onto the new `Step`. |
| `src/pytest_given/model/schema.py` | Add `flat: bool = False` field to `Step`. |
| `src/pytest_given/model/serde.py` | Emit `'flat': True` when set; read it back, default `False`. |
| `src/pytest_given/plugin.py` | In `pytest_fixture_setup`, set `recording.root.flat = desc.flat` when building the recording. |
| `src/pytest_given/report/renderer.py` | Add `_is_visibly_flat` / `_has_failed_descendant` helpers; gate child/attachment rendering on them in the step Jinja template (via a filter or a `is_visibly_flat(step)` global). |
| `src/pytest_given/report/templates/report.html.j2` | Wrap children/attachments blocks in `{% if not step | is_visibly_flat %}`. |
| `tests/unit/capture/test_step_descriptor.py` | Cover `flat` storage on descriptor (all three phases); keyword-only enforcement. |
| `tests/unit/model/test_serde.py` | Round-trip `flat=True`; absence defaults to `False`. |
| `tests/unit/report/test_renderer.py` | Cover rendering: flat hides body; failure in body auto-reveals. |
| `tests/integration/test_plugin.py` | End-to-end tests (see below). |

## Test Coverage

Integration tests in `tests/integration/test_plugin.py`:

1. **In-body context manager, flat=True** — a test with `with given(t'…', flat=True):` containing nested `with` blocks and `attach()` calls produces a JSON where the step has `children`/`attachments` populated, and rendered HTML shows only the leaf.
2. **Fixture decorator, flat=True** — a `@given('…', flat=True)`-decorated fixture with body-internal `with given(...)` produces a JSON with the full subtree under the fixture's root step, and rendered HTML shows only the leaf per consumer scenario.
3. **Helper decorator, flat=True** — a `@when('…', flat=True)`-decorated helper that internally records `with given(...)` produces a JSON with nested children under the helper's step, and rendered HTML with the leaf only per call.
4. **Auto-reveal on failure** — a `flat=True` step containing a child with `status='failed'` renders the full subtree, including the failing leaf and its error. JSON is identical to the non-flat case.
5. **Flat across phases** — symmetric tests for `given`, `when`, `then`: same shape, same outcomes.
6. **Nested flat steps** — `with given(t'…', flat=True): with when(t'…', flat=True): ...`. The outer flat hides everything inside; the inner flat is preserved in JSON but invisible in the report (because the outer hid it).
7. **Annotated override + flat=True** — `Annotated[..., given('…', flat=True)]` on a decorated fixture: JSON keeps the recorded subtree under the overridden root; HTML shows only the leaf. (Cross-references the annotated-fixture-labels spec; this test lives here once both specs land.)

Unit tests in `tests/unit/capture/test_step_descriptor.py`:

- `given('x', flat=True).flat is True`; default `False`. Same for `when` and `then`.
- `flat` is keyword-only: `given('x', True)` raises `TypeError` (from the signature; no custom check needed).

Unit tests in `tests/unit/model/test_serde.py`:

- `Step(..., flat=True)` round-trips through `step_to_dict` / `step_from_dict`.
- A dict without a `'flat'` key reads back as `flat=False`.
- A `Step(..., flat=False)` does not emit a `'flat'` key.

Unit tests in `tests/unit/report/test_renderer.py`:

- `_has_failed_descendant` returns `True` when any descendant has `status='failed'` or non-`None` `error`, regardless of depth.
- `_is_visibly_flat` returns `True` iff `step.flat and not _has_failed_descendant(step)`.

## Out of Scope

- A renderer UI toggle to reveal hidden bodies on demand. The JSON already carries the full tree; a future HTML feature could surface it (e.g., a "show internals" affordance per flat step). Not needed now.
- Per-scope or per-decorator-class defaults (e.g., "all session-scoped fixtures default to `flat=True`"). YAGNI; users opt in at the call site they care about.
- Suppressing recording entirely (vs. presentation). If a future workload measures the recording cost as load-bearing, that's a separate spec — and would change the auto-reveal contract.
- Caching `_has_failed_descendant` on the `Step` dataclass. Easy to add later if rendering ever shows up in a profile; not justified by the current cost.
- Propagating `flat` semantics to ancestors. Each step's `flat` is independent; nested flats don't combine.
