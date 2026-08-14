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

- **`@scenario(name, tags=None, story=None)`** — marks a test for the report; required for it to appear. `name` is a plain string, a `Template` (for parametrized names), or a t-string whose interpolations are all glossary handles (they render as term pills in the title). `story=` binds the scenario to a `story(...)` for coverage.
- **`given(text)` / `when(text)` / `then(text)`** — dual-purpose:
  - **Context manager** in a test body: `with when('…'): result = sut(x)`. Steps nest freely.
  - **Fixture decorator** — `@given` only (`@pytest.fixture` then `@given('…')`); `@when`/`@then` on a fixture is rejected at runtime, and the label must be a plain string. Generator fixtures work; recording steps after `yield` is not allowed.
  - **Helper-function decorator** (any phase): the helper records its own step per call; use `Template` to reference the helper's parameters (`@when(Template('I insert {amount}'))`). Placeholders must name a positional-or-keyword parameter — `*args`/`**kwargs` placeholders raise at decoration time.
  - **Call-site label** via `Annotated` on a test parameter — `given` only: `def test(text: Annotated[str, given(Template('the name {text}'))])` surfaces a fixture or parametrize value as a `given` step. Plain string or `Template` only; a t-string is rejected here.
- **`when_then(when_text, then_text)`** — one `with` emitting a `when` (wrapping the body) and a sibling `then` (emitted once the body exits cleanly). Pair with a nested `pytest.raises(...)` for expected-raise scenarios. If the body raises uncaught, the `then` is skipped.
- **`attach(label, content)`** — attach data to the current step. Strings stored verbatim; other types JSON-serialized.

## Step text forms

| Form | Where | Behaviour |
|---|---|---|
| Plain string / f-string | anywhere | Rendered verbatim; f-string values are not highlighted. |
| T-string `t'a {cup_size} cup'` | test-body steps only | Interpolated at runtime; values color-coded when the expression matches a parametrize column. Full expression syntax allowed. |
| T-string `t'a {guest} checks in'` | `@scenario(...)` name — glossary handles only | Evaluated eagerly at import; each handle renders as a term pill in the title. A value/expression interpolation is rejected (values aren't in scope at import). |
| `Template('… {col} …')` | `@scenario(...)`, helper decorators, `Annotated[..., given(...)]` | Deferred substitution — against parametrize columns (`@scenario`, `Annotated`) or the helper's bound arguments (decorators). |

Hard rules (each raises `PytestGivenError`):

1. **`Template` accepts bare identifiers only** — `{name}`, `{name:spec}`, `{name!conv}`. No attribute access, indexing, or expressions. Workaround: parametrize by the attribute, or move the step to a test-body t-string.
2. **`Template` and t-strings don't swap places.** A `Template` in a test-body step is rejected (values are in scope — use a t-string); a t-string on a fixture/helper decorator or in `Annotated[..., given(...)]` is rejected (values aren't in scope — use `Template` or a plain string). A t-string in `@scenario(...)` is the one exception: it's accepted when every interpolation is a glossary handle (a term reference is in scope at import and renders as a title pill), but a value/expression interpolation is still rejected — use `Template` for a parametrized name. A term pill and a per-case value can't combine in one name.

## Parametrized tests

- All cases group into **one scenario with a parameter table**. T-string interpolations naming a parametrize column render as colored values per row.
- **Case 1's steps are the template for every row** — narration that branches on a parameter value silently shows case 1's shape for all rows (see [scenarios.md](scenarios.md)).
- Parametrized **scenario name**: `@scenario(Template('Brew {cup_size} ml'))`.
- Surface a parametrize value as a `given`: `Annotated[int, given(Template('a {cup_size} ml cup'))]` on the parameter.

## Glossary

- **Code-defined**: `g = Glossary()`, then `guest = g.actor('Guest', definition='…')`, `g.work_object('Room', …)`, `g.verb('search', …)`. Where to define `g`, and how `conftest.py` must bind it for the plugin to find it: [glossaries.md](glossaries.md).
- **File-backed**: `g = FileGlossary(Path(__file__).parent / 'GLOSSARY.md')` — needs at least one GFM pipe table; first column = term, second = description by default (`term_column=` / `description_column=` / `kind_column=` override, 0-based index or header name, case-insensitive).
- **Handles in t-strings** render as kind-coloured pills with definition tooltips: `t'a {guest} {search("searches for")} a {room}'`. Three surface forms: **bare** `g['Room']` (the canonical text), **`.low`** `g['Room'].low` (lowercased), and a **callable** override `g['borrow']('borrows')` for any other inflection, plural (`g['Term']('terms')`), or instance (`organizer('Carol')`). Which to pick: [glossaries.md](glossaries.md).
- **Lookup and deferral**: `g['Guest']` fetches a declared term (case-insensitive; raises if unknown). On a code-defined glossary, `g('foo')` declares an as-yet-unclassified term (lands in *Uncategorized*, shows *Undefined* until `definition=` is supplied); on a `FileGlossary` the vocabulary is closed — `g('foo')` only looks up, and new terms are added as rows in the file. Both forms return handles usable in t-strings and activities.
- Without a `kind_column`, kinds are inferred from story activity-slot positions (position 0 → actor, odd → verb, even ≥ 2 → work object); a term used only in steps stays kindless. Collision rules: [glossaries.md](glossaries.md).

## Stories

- `story('Name', [activity(...), ...])` — a flow of `activity(actor, verb, work_object, ...)` rows, read left-to-right; parts may be bare strings, but an activity needs **two distinct glossary terms** to be coverage-tracked. `path(...)` branches alternate sequences off a shared prefix.
- Bind a scenario with `@scenario(..., story=the_story)` — the only way a story reaches the report. Coverage matches **per step**: an activity is covered when a single step's term refs include all the activity's terms. A step can pin an activity explicitly with `given(text, activity=3)` (1-based activity number or sequence); a pinned step covers regardless of its narration. What that costs you when authoring: [stories.md](stories.md).

## Verifying

- `pytest <selection> --given-md` — render touched scenarios to stdout.
- `pytest <selection> --given-lint=true` — narration lint; only *error* findings fail the run. Rule catalog and per-project config live in the README.
