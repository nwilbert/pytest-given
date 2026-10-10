# API quick reference

Everything is a top-level export of `pytest_given`:

```python
from pytest_given import (
    FileGlossary, Glossary, PytestGivenError, PytestGivenWarning, Template,
    attach, clause, given, scenario, sentence, story, then, when, when_then,
)
```

This page covers what you need for authoring, and it matches the installed package version. Installation, the report flags (`--given-html`, `--given-json`, `--given-md`), source-link presets and the lint configuration (`given_lint_rules`, `given_lint_ignore`) are setup topics. For those, see the project documentation at <https://nwilbert.github.io/pytest-given/>.

## Core

- **`@scenario(name, tags=None, *, stories=None, pins=None, group_parametrized=True)`** marks a test for the report. A test only appears in the report with it. `name` is a plain string, a `Template` (for parametrized names), or a t-string whose interpolations are all glossary handles; those render as term refs in the title. `stories=` takes one or more stories whose sentences the steps are matched against. `pins=` takes sentence handles (`the_story['name']`, `the_story[3]`). The scenario then covers those sentences plus its steps' pins, with no narration matching. `pins=[]` keeps only the steps' pins. Bare numbers and names raise an error. The decorator returns the function unwrapped, so it keeps its own signature.
- **`given(text, *, pins=None)`, `when(text, *, pins=None)` and `then(text, *, pins=None)`** each have several uses. `pins=` binds the step to story sentences instead of narration matching, and `pins=[]` turns matching off for the step (see [stories.md](stories.md)).
  - **As a context manager** in a test body: `with when('…'): result = sut(x)`. Steps can nest within one phase (a `when` inside a `when`). Nesting a step of another phase raises `PytestGivenError`. That includes calling a decorated helper of another phase inside an open step.
  - **As a fixture decorator**, with `@given` only. `@pytest.fixture` must be **outermost** (above `@given('…')`), and the label must be a plain string. Generator fixtures work, at any scope. A step or attachment after `yield` raises an error.
  - **As a helper-function decorator**, in any phase. The helper records its own step on each call. Use `Template` to reference the helper's parameters (`@when(Template('I insert {amount}'))`); each placeholder must name one of the helper's named parameters. An `async def` helper works too: the step stays open while the awaited body runs.
  - **As a label at the call site**, via `Annotated` on a test parameter, with `given` only: `def test(text: Annotated[str, given(Template('the name {text}'))])` shows a fixture or parametrize value as a `given` step. Only a plain string or a `Template` works here; a t-string is rejected. A label's `pins=` replaces the pins of the fixture's own label, and `pins=[]` clears them.
- **`when_then(when_text, then_text)`** is one `with` block that records a `when` around the body and a sibling `then`. The `then` is recorded once the body exits cleanly. Combine it with a nested `pytest.raises(...)` for scenarios that expect a raise. If the body raises an uncaught error, the `then` is skipped.
- **`attach(label, content)`** attaches data to the current step. A step must be open: calling it from the test body outside every `given`, `when` and `then` raises an error. `label` must be a plain `str`; a t-string or `Template` raises. Strings are stored as they are, and other types are serialized to JSON.

## Step text forms

| Form | Where | Behavior |
|---|---|---|
| Plain string / f-string | anywhere | Rendered as written; f-string values are not highlighted. In a parametrized scenario, text that varies between cases fails the run, so use a t-string. |
| T-string `t'a {cup_size} cup'` | test-body steps only | Interpolated at runtime. A value is color-coded when its expression matches a parametrize column. Any expression is allowed. |
| T-string `t'A {guest.l} checks in'` | `@scenario(...)` name, glossary handles only | Evaluated at import. Each handle renders as a term ref in the title. Interpolating a value or an expression is rejected, because values aren't available at import. |
| `Template('… {col} …')` | `@scenario(...)`, helper decorators, `Annotated[..., given(...)]` | Filled in later: from parametrize columns (`@scenario`, `Annotated`), or from the helper's arguments (decorators). |

Hard rules (each raises `PytestGivenError`):

1. **`Template` accepts bare identifiers only:** `{name}`, `{name:spec}`, `{name!conv}`. No attribute access, no indexing, no expressions. To work around this, parametrize by the attribute, or move the step into the test body as a t-string.
2. **`Template` and t-strings can't replace each other.** A `Template` in a test-body step is rejected, because the values are available there; use a t-string. A t-string on a fixture or helper decorator, or in `Annotated[..., given(...)]`, is rejected, because the values aren't available there; use a `Template` or a plain string. A t-string in `@scenario(...)` is the one exception. It is accepted when every interpolation is a glossary handle, since a handle exists at import and renders as a term ref in the title. Interpolating a value or an expression there is still rejected, so use a `Template` for a parametrized name. One name can't combine a term ref with a per-case value.

## Parametrized tests

- All cases are grouped into **one scenario with a parameter table**. T-string interpolations that name a parametrize column render as colored values in each row.
- **The steps of the first passing case are the template for every row**, but only their *structure*. A narrated value or an attachment content that varies between cases becomes its own column in the parameter table. When an authoring form can't be shown honestly against that template, pytest-given raises `PytestGivenError` instead of writing a wrong report, and each message names its fix. The habits that avoid these errors are in [scenarios.md](scenarios.md) under "Parameter tables".
- **When the narration really differs per case**, use `@scenario(..., group_parametrized=False)`. It declines the merge and records one scenario per case, titled `<name> [<parametrize id>]`, with any `Template` placeholders filled in per case. There is no parameter table. On a test that isn't parametrized, it raises an error at collection.
- To parametrize the **scenario name**, use `@scenario(Template('Brew {cup_size} ml'))`.
- To show a parametrize value as a `given`, put `Annotated[int, given(Template('a {cup_size} ml cup'))]` on the parameter.
- **Stacking:** `@scenario(...)` and `@pytest.mark.parametrize(...)` work in either order. `@scenario` returns the function unwrapped, so neither hides the other's marks.

## Glossary

- `Glossary()` offers `g.actor(name, definition=…)`, `g.work_object(…)`, `g.activity(…)` and `g('foo')` (kindless). `FileGlossary(path, *, term_column=0, description_column=1, kind_column=None)` loads a Markdown file. `g['Guest']` looks a term up, case-insensitive.

Handle forms, discovery, kinds and the one-glossary-per-suite rule are in [glossaries.md](glossaries.md).

## Stories

- **`story(title, [sentence(...), ...])`**: sentences are numbered by position (1 to N, never set by hand) and read from left to right: `sentence(actor, activity, work_object, ..., name=None)`. Each part is a handle or a bare string. Several arrow chains under one number take one `clause(...)` each: `sentence(clause(...), clause(...))`.
- **Sentence handles** for `pins=`: `the_story['cancel']` (by `name=`) or `the_story[3]` (by number).

Coverage matching, pins, and when a sentence counts as coverage-tracked are in [stories.md](stories.md).
