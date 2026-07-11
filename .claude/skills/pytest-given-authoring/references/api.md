# API quick reference

Everything is a top-level export of `pytest_given`:

```python
from pytest_given import (
    FileGlossary, Glossary, PytestGivenError, Template,
    activity, attach, given, path, scenario, story, then, when, when_then,
)
```

This is the authoring-relevant surface, version-matched to the installed package. Installation, report flags (`--given-html` / `--given-json` / `--given-md`), source-link presets, and lint configuration (`given_lint_rules`, `given_lint_ignore`) are setup concerns — see the project README.

## Core

- **`@scenario(name, tags=None, story=None)`** — marks a test for the report; required for it to appear. `name` is a plain string or a `Template` (for parametrized names). `story=` binds the scenario to a `story(...)` for coverage.
- **`given(text)` / `when(text)` / `then(text)`** — dual-purpose:
  - **Context manager** in a test body: `with when('…'): result = sut(x)`. Steps nest freely.
  - **Fixture decorator** — `@given` only (`@pytest.fixture` then `@given('…')`); `@when`/`@then` on a fixture is rejected at runtime. Generator fixtures work; recording steps after `yield` is not allowed.
  - **Helper-function decorator** (any phase): the helper records its own step per call; use `Template` to reference the helper's parameters (`@when(Template('I insert {amount}'))`).
  - **Call-site label** via `Annotated` on a test parameter — `given` only: `def test(text: Annotated[str, given(Template('the name {text}'))])` surfaces a fixture or parametrize value as a `given` step. Plain string or `Template` only; a t-string is rejected here.
- **`when_then(when_text, then_text)`** — one `with` emitting a `when` (wrapping the body) and a sibling `then` (emitted once the body exits cleanly). Pair with a nested `pytest.raises(...)` for expected-raise scenarios. If the body raises uncaught, the `then` is skipped.
- **`attach(label, content)`** — attach data to the current step. Strings stored verbatim; other types JSON-serialized.

## Step text forms

| Form | Where | Behaviour |
|---|---|---|
| Plain string / f-string | anywhere | Rendered verbatim; f-string values are not highlighted. |
| T-string `t'a {cup_size} cup'` | test-body steps only | Interpolated at runtime; values color-coded when the expression matches a parametrize column. Full expression syntax allowed. |
| `Template('… {col} …')` | `@scenario(...)`, helper decorators, `Annotated[..., given(...)]` | Deferred substitution — against parametrize columns (`@scenario`, `Annotated`) or the helper's bound arguments (decorators). |

Hard rules (each raises `PytestGivenError`):

1. **`Template` accepts bare identifiers only** — `{name}`, `{name:spec}`, `{name!conv}`. No attribute access, indexing, or expressions. Workaround: parametrize by the attribute, or move the step to a test-body t-string.
2. **`Template` and t-strings don't swap places.** A `Template` in a test-body step is rejected (values are in scope — use a t-string); a t-string in `@scenario(...)`, on a fixture/helper decorator, or in `Annotated[..., given(...)]` is rejected (values aren't in scope — use `Template` or a plain string).

## Parametrized tests

- All cases group into **one scenario with a parameter table**. T-string interpolations naming a parametrize column render as colored values per row.
- **Case 1's steps are the template for every row** — narration that branches on a parameter value silently shows case 1's shape for all rows. If steps genuinely differ per case, split into separate `@scenario` tests.
- Parametrized **scenario name**: `@scenario(Template('Brew {cup_size} ml'))`.
- Surface a parametrize value as a `given`: `Annotated[int, given(Template('a {cup_size} ml cup'))]` on the parameter.

## Glossary

- **Code-defined**: `g = Glossary()`, then `guest = g.actor('Guest', definition='…')`, `g.work_object('Room', …)`, `g.verb('search', …)`. Put `g` in a `conftest.py` so the plugin discovers it.
- **File-backed**: `g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')` — needs at least one GFM pipe table; first column = term, second = description by default (`term_column=` / `description_column=` / `kind_column=` override, 0-based index or header name, case-insensitive).
- **Handles in t-strings** render as kind-coloured pills with definition tooltips: `t'a {guest} {search("searches for")} a {room}'`. Calling a handle supplies the display text (verb conjugation `g["borrow"]("borrows")`, or a concrete instance `organizer('Carol')`).
- **Lookup and deferral**: `g['Guest']` fetches a declared term (case-insensitive; raises if unknown). `g('foo')` declares an as-yet-unclassified term (lands in *Uncategorized*, shows *Undefined* until `definition=` is supplied). Both return handles usable in t-strings and activities.
- Without a `kind_column`, kinds are inferred from story activity-slot positions (slot 0 → actor, 1 → verb, ≥2 → work object); a term used only in steps stays kindless.

## Stories

- `story('Name', [activity(...), ...])` — a flow of `activity(actor, verb, work_object, ...)` rows, read left-to-right; parts may be bare strings, but an activity needs **two distinct glossary terms** to be coverage-tracked. `path(...)` branches alternate sequences off a shared prefix.
- Bind a scenario with `@scenario(..., story=the_story)`; steps' term refs match against activities for coverage. A step can bind explicitly: `given(text, activity=...)`.

## Verifying

- `pytest <selection> --given-md` — render touched scenarios to stdout and read them as a spec.
- `pytest <selection> --given-lint=true` — narration lint; error findings fail the run. Rule catalog and per-project config live in the README.
