# API quick reference

Everything is a top-level export of `pytest_given`:

```python
from pytest_given import (
    FileGlossary, Glossary, PytestGivenError, PytestGivenWarning, Template,
    activity, attach, given, path, scenario, story, then, when, when_then,
)
```

This is the authoring-relevant surface, version-matched to the installed package. Installation, report flags (`--given-html` / `--given-json` / `--given-md`), source-link presets, and lint configuration (`given_lint_rules`, `given_lint_ignore`) are setup concerns — see the project README.

## Core

- **`@scenario(name, tags=None, *, story=None, activities=None, group_parametrized=True)`** — marks a test for the report; required for it to appear. `name` is a plain string, a `Template` (for parametrized names), or a t-string whose interpolations are all glossary handles (they render as term refs in the title). `story=` binds the scenario to a `story(...)` for coverage; `activities=` requires `story=` and narrows the scenario to those activity ids, so it can cover no others — an `int` or a sequence of them, never a string (`activities='13'` raises `TypeError` rather than becoming the ids 1 and 3). The decorated function is returned unwrapped, so it keeps its own signature.
- **`given(text)` / `when(text)` / `then(text)`** — dual-purpose:
  - **Context manager** in a test body: `with when('…'): result = sut(x)`. Steps nest within a phase (a `when` inside a `when`); crossing phases raises `PytestGivenError` — including a decorated helper of another phase called inside an open step.
  - **Fixture decorator** — `@given` only, with `@pytest.fixture` **outermost** (`@pytest.fixture` above `@given('…')`); the other order is rejected at decoration time, `@when`/`@then` on a fixture is rejected at runtime, and the label must be a plain string. Generator fixtures work, at any scope; recording steps after `yield` is not allowed.
  - **Helper-function decorator** (any phase): the helper records its own step per call; use `Template` to reference the helper's parameters (`@when(Template('I insert {amount}'))`). Placeholders must name one of the helper's named parameters; `*args`/`**kwargs` placeholders raise at decoration time. An `async def` helper works too: the step stays open across the awaited body.
  - **Call-site label** via `Annotated` on a test parameter — `given` only: `def test(text: Annotated[str, given(Template('the name {text}'))])` surfaces a fixture or parametrize value as a `given` step. Plain string or `Template` only; a t-string is rejected here.
- **`when_then(when_text, then_text)`** — one `with` emitting a `when` (wrapping the body) and a sibling `then` (emitted once the body exits cleanly). Pair with a nested `pytest.raises(...)` for expected-raise scenarios. If the body raises uncaught, the `then` is skipped.
- **`attach(label, content)`** — attach data to the current step. Must be called with a step open (a call from the test body, outside every `given`/`when`/`then`, raises). `label` is a plain `str` (a t-string or `Template` raises); strings stored verbatim, other types JSON-serialized.

## Step text forms

| Form | Where | Behavior |
|---|---|---|
| Plain string / f-string | anywhere | Rendered verbatim; f-string values are not highlighted. |
| T-string `t'a {cup_size} cup'` | test-body steps only | Interpolated at runtime; values color-coded when the expression matches a parametrize column. Full expression syntax allowed. |
| T-string `t'a {guest} checks in'` | `@scenario(...)` name — glossary handles only | Evaluated eagerly at import; each handle renders as a term ref in the title. A value/expression interpolation is rejected (values aren't in scope at import). |
| `Template('… {col} …')` | `@scenario(...)`, helper decorators, `Annotated[..., given(...)]` | Deferred substitution — against parametrize columns (`@scenario`, `Annotated`) or the helper's bound arguments (decorators). |

Hard rules (each raises `PytestGivenError`):

1. **`Template` accepts bare identifiers only** — `{name}`, `{name:spec}`, `{name!conv}`. No attribute access, indexing, or expressions. Workaround: parametrize by the attribute, or move the step to a test-body t-string.
2. **`Template` and t-strings don't swap places.** A `Template` in a test-body step is rejected (values are in scope — use a t-string); a t-string on a fixture/helper decorator or in `Annotated[..., given(...)]` is rejected (values aren't in scope — use `Template` or a plain string). A t-string in `@scenario(...)` is the one exception: it's accepted when every interpolation is a glossary handle (a term reference is in scope at import and renders as a title term ref), but a value/expression interpolation is still rejected — use `Template` for a parametrized name. A term ref and a per-case value can't combine in one name.

## Parametrized tests

- All cases group into **one scenario with a parameter table**. T-string interpolations naming a parametrize column render as colored values per row.
- **The baseline case's steps are the template for every row** (the first case that passed) — but only their *structure*: a narrated value or an attachment payload that varies across cases becomes its own parameter-table column. Six authoring forms cannot be rendered honestly against that template and raise `PytestGivenError` instead of shipping a wrong report; each message names its fix. The catalog and the authoring habits that avoid it: [scenarios.md](scenarios.md).
- **Narration that genuinely branches per case**: `@scenario(..., group_parametrized=False)` declines the merge and emits one scenario per case, each titled `<name> [<parametrize id>]` with any `Template` placeholders substituted per case first. No parameter table. On an unparametrized test it raises at collection.
- Parametrized **scenario name**: `@scenario(Template('Brew {cup_size} ml'))`.
- Surface a parametrize value as a `given`: `Annotated[int, given(Template('a {cup_size} ml cup'))]` on the parameter.
- **Stacking**: `@scenario(...)` and `@pytest.mark.parametrize(...)` compose in either order — `@scenario` returns the function unwrapped, so neither hides the other's marks.

## Glossary

- **Code-defined**: `g = Glossary()`, then `guest = g.actor('Guest', definition='…')`, `g.work_object('Room', …)`, `g.verb('search', …)`. Where to define `g`, and how `conftest.py` must bind it for the plugin to find it: [glossaries.md](glossaries.md).
- **File-backed**: `g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')` — needs at least one GFM pipe table; first column = term, second = description by default (`term_column=` / `description_column=` / `kind_column=` override, 0-based index or header name, case-insensitive).
- **Handles in t-strings** render as kind-colored words with definition tooltips: `t'a {guest} {search("searches for")} a {room}'`. Three surface forms on every handle: **bare** `g['Room']`, **`.low`** `g['Room'].low`, and a **callable** override `g['borrow']('borrows')`. Which to pick: [glossaries.md](glossaries.md).
- **Lookup and deferral**: `g['Guest']` fetches a declared term (case-insensitive; raises if unknown). On a code-defined glossary, `g('foo')` declares an as-yet-unclassified term (lands in *Uncategorized*, shows *Undefined* until `definition=` is supplied); on a `FileGlossary` the vocabulary is closed — `g('foo')` only looks up, and new terms are added as rows in the file. Both forms return handles usable in t-strings and activities.
- An undeclared kind is inferred from story activity-slot positions (position 0 → actor, odd → verb, even ≥ 2 → work object); a term used only in steps stays kindless. A *declared* kind is instead checked against its slot when `activity(...)` is built, so a mismatch raises there. Collision rules: [glossaries.md](glossaries.md).
- **One glossary per suite** — two distinct `Glossary` instances reaching the report raise `PytestGivenError`. Discovery (story tree first, then a `conftest.py` scan): [glossaries.md](glossaries.md).

## Stories

- `story('Name', [activity(...), ...])` — a flow of `activity(actor, verb, work_object, ...)` rows, read left-to-right; parts may be bare strings, but an activity needs **two distinct glossary terms** to be matched by narration; under-anchored activities render as "not coverage-tracked" unless a step pins them. `path(...)` branches alternate sequences off a shared prefix. Activity ids are the rows' 1-based list positions unless a row fixes its own with `activity(..., activity_id=N)` (`activity_id=0` is the unset sentinel and raises); since `activity=` pins name those numbers, inserting a row renumbers the pins after it — see [stories.md](stories.md).
- Bind a scenario with `@scenario(..., story=the_story)` — the only way a story reaches the report. Coverage matches **per step**, and `given(text, activity=3)` (a 1-based activity number or a sequence) pins a step to an activity regardless of its narration. The matching rule and what it costs you when authoring: [stories.md](stories.md).

## Verifying

`pytest <selection> --given-md` renders the touched scenarios to stdout; `--given-lint` runs the narration lint, where only *error* findings fail the run. Its rule catalog is in [scenarios.md](scenarios.md) under "Mechanical counterparts".
