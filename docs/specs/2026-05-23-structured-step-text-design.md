# Structured Step Text — Design Spec

## Goal

Replace the ambiguous "literal `{name}` placeholder" mechanism with two distinct, explicit authoring forms — one for eager (test-body) substitution, one for deferred (decorator/Annotated) substitution — using the **same `{...}` syntax** across both:

```python
from pytest_given import given, scenario, Template

# Eager: values in scope, t-string interpolation
with given(t'a {cup_size} ml cup'):
    ...

# Deferred: values not in scope at the call site; Template substitutes per case
@scenario(Template('Brew {cup_size} ml'))
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(cup_size: int): ...
```

Drop the legacy `_PARAM_RE` regex highlight on plain strings and the `_templatize_step_text` `str.replace` reverse-templatize on f-strings. After this spec, three authoring forms remain — `str` (literal), `templatelib.Template` (t-string), and `pytest_given.Template` — non-overlapping and unambiguous.

## Background

Today, step text is a `str` and four authoring stories coexist:

1. **f-string in test body:** `with given(f'a {cup_size} ml cup')` interpolates eagerly; `_templatize_step_text` (plugin.py:332) reverse-engineers `'200'` back to `'{cup_size}'` via `str.replace`. Fragile — matches unrelated substrings, can't disambiguate two parameters with the same value.
2. **Plain `str` with `{name}` placeholder:** `@scenario('Brew {cup_size} ml')` and the (deferred) `Annotated[int, given('a {cup_size} ml cup')]`. The renderer's `{name}` regex highlights names that happen to be parametrize columns. Silent on typos; collides with literal `{` `}` in step text.
3. **Plain static `str`:** literal text — but the `{name}` regex still runs over it, so a stray `{example}` gets interpreted as a placeholder if `example` happens to be a parametrize name.
4. **Static `str` without braces:** literal — the only unambiguous case.

PEP 750 t-strings (Python 3.14+) give us an explicit eager mechanism. For the deferred case we introduce `pytest_given.Template` — a small wrapper around `string.Formatter` that uses the same `{...}` syntax as t-strings, so users learn one placeholder convention. The legacy regex and `str.replace` paths are removed.

## Approach

Three authoring forms, each with a clear lane — and each lane only accepts the forms that make sense for it:

| Form | Syntax | Where it is accepted | Evaluation |
|---|---|---|---|
| `str` | literal text | Everywhere (static labels) | None |
| `templatelib.Template` (t-string) | `t'a {cup_size} cup'` | Test bodies — values in scope | Eager, at construction |
| `pytest_given.Template` | `Template('a {cup_size} cup')` | `@scenario(...)` (and future Annotated) — substitution source is `callspec.params` | Deferred, at substitute time |

Test bodies use t-strings or plain strings only; deferred decorator contexts use `pytest_given.Template` or plain strings only. The lanes don't overlap.

When a step is recorded, the collector stores both a flat `text: str` and an optional structured `text_parts: list[NarrationPart] | None`. The same `text_parts` model serves both Template types:

- **t-string** → `text_parts` carries `NarrationLiteral` / `NarrationValue` (value-with-expression, already known).
- **`pytest_given.Template`** → `text_parts` carries `NarrationLiteral` / `NarrationPlaceholder` (name + format spec, unresolved until merge).

The renderer and templatizer dispatch on `text_parts`; plain `str` steps render verbatim with no regex pass.

## API

### `pytest_given.Template`

```python
from string import Formatter
from typing import Any, Mapping

class Template:
    """Deferred brace-style template. Same `{...}` syntax as f/t-strings."""

    def __init__(self, template: str) -> None:
        self.template = template
        formatter = Formatter()
        self.parts: list[NarrationPart] = []
        for literal, name, spec, conversion in formatter.parse(template):
            if literal:
                self.parts.append(NarrationLiteral(value=literal))
            if name is not None:
                if not name.isidentifier():
                    raise PytestGivenError(
                        f"pytest_given.Template only supports bare identifiers as placeholders; "
                        f"got {name!r}. For attribute access or expressions, use a t-string in the "
                        f"test body (where the value is in scope)."
                    )
                self.parts.append(
                    NarrationPlaceholder(name=name, format_spec=spec or '', conversion=conversion)
                )

    def substitute(self, mapping: Mapping[str, Any]) -> str:
        out: list[str] = []
        for part in self.parts:
            if isinstance(part, NarrationLiteral):
                out.append(part.value)
                continue
            if part.name not in mapping:
                raise KeyError(part.name)
            value = mapping[part.name]
            if part.conversion:
                value = {'s': str, 'r': repr, 'a': ascii}[part.conversion](value)
            out.append(format(value, part.format_spec))
        return ''.join(out)

    def get_identifiers(self) -> list[str]:
        return [p.name for p in self.parts if isinstance(p, NarrationPlaceholder)]
```

Syntax supported: **bare identifiers only** (`{name}`), with optional format specs (`{n:03d}`) and conversions (`{obj!r}`). **Not** supported: attribute access (`{obj.attr}`), indexing (`{d[key]}`), arbitrary expressions, method calls, walrus, ternaries. Rationale: the substitution source is the parametrize mapping (`callspec.params`), keyed by bare column names. Nested access would either need to alias to its root column (silently surprising) or synthesize derived columns (a separate, larger feature applied uniformly to t-strings and Template — out of scope here). T-strings remain the full-expressiveness form for in-scope authoring; if you want compositional narration, either parametrize by the attributes directly, or move the step into the test body with a t-string.

Construction-time validation: `Formatter().parse()` raises `ValueError` on unclosed `{` or invalid syntax — so `Template('a {cup_size')` errors at the call site, not later. The bare-identifier check (`name.isidentifier()`) raises `PytestGivenError` on non-identifier field names so `Template('{obj.attr}')` errors at the call site too. Literal braces use the `{{` / `}}` escape, identical to f/t-strings.

### `given(text)`, `when(text)`, `then(text)`

```python
def given(text: str | templatelib.Template) -> StepDescriptor: ...
def when(text: str | templatelib.Template) -> StepDescriptor: ...
def then(text: str | templatelib.Template) -> StepDescriptor: ...
```

Usage:

```python
with given(t'a {cup_size} ml cup'):                # eager — values in scope
    ...
with given('static label'):                        # literal
    ...
```

`pytest_given.Template` is **rejected** here: in a test body, values are in lexical scope and t-strings cover the dynamic case directly. A `Template` in `given/when/then` would just duplicate t-string behavior (parametrized scenarios) or fail with no substitution source (non-parametrized scenarios). Type signature excludes it; runtime `isinstance` check raises `PytestGivenError`:

> `given(Template(...)) is not supported in a test body; use a t-string for dynamic values, or a plain string for static labels. Template is for @scenario(...) (and the future Annotated fixture form), where deferred substitution from callspec.params is the only sensible option.`

The same rule applies to `when` / `then`.

### `attach(label, content)`

`label` accepts `str | templatelib.Template` only. T-strings render eagerly (values are in scope at the call site); plain strings render verbatim. `pytest_given.Template` is **rejected** — `attach` is called inside a test body where deferred substitution has no merge-time source, and attachment labels aren't per-case-merged. Type signature excludes it; runtime `isinstance` check raises `PytestGivenError` with the message: `"attach(Template(...)) is not supported; use a t-string (eager) or a plain string."`

### `scenario(name)`

```python
def scenario(name: str | Template, tags: list[str] | None = None) -> ScenarioDecorator: ...
```

Accepts `str | pytest_given.Template`. **Rejects t-string** — `@scenario` runs at module-import time, so a t-string referencing a parametrize parameter `NameError`s in Python before our code runs; if a t-string referencing only in-scope module constants somehow reaches `scenario()`, we still reject it with `PytestGivenError` (the type signature excludes it, runtime `isinstance` check enforces it).

The `ScenarioDecorator` stores the original `str | Template` on the test function's `_scenario` marker (currently `_scenario.name: str`). `plugin.pytest_runtest_setup` passes it through to `collector.start_scenario(name=...)`, which dispatches on type: `str` → `(name=str, name_parts=None)`; `Template` → `(name=template.template, name_parts=list(template.parts))`. This mirrors the per-step recording dispatch — one decision site, two storage fields.

The merge key for `_group_parameterized` is:

- `str` → the string itself (existing behavior).
- `Template` → `template.template` (the raw `{name}`-bearing source). All cases of a parametrized scenario share that exact raw string, so they merge into one group; per-case rendering substitutes from `callspec.params`.

JSON model for scenario names mirrors the step model: `Scenario.name: str` always holds the rendered (or raw, for Template) string; `Scenario.name_parts: list[NarrationPart] | None` holds the structured form when the name was a Template. Rendering dispatches on `name_parts` exactly like step text.

### Fixture-side decorators (`@given(text)` on a fixture)

Fixture decorators accept `str` only in this spec. T-strings can't reference fixture argument values at decoration time. `pytest_given.Template` on a fixture decorator is reserved for the future Annotated revisit (where the substitution source becomes the consuming scenario's params); not wired up here.

Rejection happens in `StepDescriptor.__call__(func)`: any `text_parts is not None` reaching the decorator-application path raises `PytestGivenError("@given(t'...') / @given(Template(...)) is not allowed on a fixture; the fixture's argument values aren't in scope at decoration time. Use a plain string label, or move the step into the test body.")`.

### Step model additions

```python
@dataclass(frozen=True, kw_only=True)
class NarrationLiteral:
    value: str

@dataclass(frozen=True, kw_only=True)
class NarrationValue:
    """A t-string interpolation — value already known."""
    rendered: str            # str(value) post-conversion+format_spec
    expression: str          # source expression text
    format_spec: str = ''    # preserved so templatize can hand it to NarrationPlaceholder
    conversion: str | None = None

@dataclass(frozen=True, kw_only=True)
class NarrationPlaceholder:
    """A deferred placeholder — resolved at render time against per-case mapping.

    Produced by pytest_given.Template, or by templatize when a NarrationValue's
    expression matches a parametrize name.
    """
    name: str
    format_spec: str = ''
    conversion: str | None = None

type NarrationPart = NarrationLiteral | NarrationValue | NarrationPlaceholder

@dataclass
class Step:
    ...
    text_parts: list[NarrationPart] | None = None  # None for plain-str authoring
```

Python-side dispatch uses `match` over `NarrationPart` (the union narrows exhaustively); the field sets are disjoint — `NarrationLiteral` has `value`, `NarrationValue` has `rendered`/`expression`, `NarrationPlaceholder` has `name` — so no `kind` discriminator is needed.

## Resolution Rules

1. **Validation (collection time).** A `pytest_collection_modifyitems` hook walks the collected items. For each item whose `_scenario` marker has a `Template` name, if the item has no `callspec` (i.e., the test is not parametrized), raise `PytestGivenError`:

   > `@scenario(Template(...)) on '<nodeid>' requires @pytest.mark.parametrize; the substitution source is callspec.params only. Use a plain string for static scenario names, or add @pytest.mark.parametrize.`

   Collection-time was chosen over decoration-time because Python decorator ordering is not fixed in user code — `@scenario` and `@pytest.mark.parametrize` can appear in either order, and decoration-time inspection of `func.pytestmark` only sees markers attached by earlier (bottom-up) decorators. By collection time, all markers are attached and parametrize has been expanded into per-case items, so the check is reliable regardless of decorator order. The error surfaces under `pytest --collect-only`, before any test body runs.

2. **Recording.** `collector.push_step(phase, text)` dispatches on type:
   - `str` → `Step(text=text, text_parts=None)`.
   - `templatelib.Template` → `_to_text_parts_tstring(t)` iterates the Template (yielding `str | Interpolation`), applies conversion then `format(value, format_spec)` per interpolation, and produces a rendered string plus `[NarrationLiteral | NarrationValue, ...]`.

   `pytest_given.Template` does not appear here — it is rejected by `given/when/then` (and `attach`) before reaching the collector. Scenario-name recording (via the `_scenario` marker) handles `pytest_given.Template` separately in `start_scenario`.

3. **Parametric merge.** `_group_parameterized` walks `first.steps` for the merged-template structure (existing first-case-is-template behavior). Per step:
   - `text_parts is None`: pass through unchanged.
   - `text_parts is not None`: walk parts.
     - `NarrationLiteral`: unchanged.
     - `NarrationValue`: if `expression in param_names`, **replace with** `NarrationPlaceholder(name=expression, format_spec=tv.format_spec, conversion=tv.conversion)`. The renderer's per-case logic then applies uniformly. Otherwise leave the `NarrationValue` verbatim (same value across all cases by construction; renders as a neutral value-highlight).
     - `NarrationPlaceholder`: if `name in param_names`, keep as-is (renderer substitutes per case from the parameter table). If `name not in param_names`, raise `PytestGivenError` with the file/line of the call site — Template placeholders that don't match a parametrize name are almost always typos.

   The same dispatch runs over the scenario's `name_parts` (if present) so a Template-named scenario merges and renders identically.

   `_templatize_step_text` is removed. F-strings in parametrized test bodies no longer reverse-templatize.

4. **Render.** New Jinja filter `step_text(step, case=None)` returns Markup. Single dispatch shape:
   - `step.text_parts is None`: render `step.text` HTML-escaped. No regex pass; braces render as braces.
   - `step.text_parts is not None`: walk parts.
     - `NarrationLiteral`: escaped literal.
     - `NarrationValue`: rendered string wrapped in `<span class="param-value">` (neutral highlight). Only reachable for non-parametrize t-string expressions — matching expressions have already been converted to `NarrationPlaceholder` by merge.
     - `NarrationPlaceholder`: look up color via `param_color_map[name]`. When `case is not None`, substitute via `mapping = dict(zip(param_names, case.values))`, apply `conversion` then `format(value, format_spec)`, and wrap the result in `<span class="param-color-N">`. When `case is None` (merged-template view), render as `{name}` wrapped in the param-color span.

   `scenario.name` rendering: same dispatch on `name_parts`.

   The old `highlight_params` filter and `_PARAM_RE` are removed.

5. **JSON model.** `text_parts` and the scenario-name `Template` serialize via `dataclasses.asdict` as plain field-shaped dicts. The renderer loads JSON as raw dict via `json.loads` (renderer.py:21); absent or `null` `text_parts` falls through to the literal-render path. Back-compatible: old reports still render (without the new highlights since they have no `text_parts`). Discrimination is structural — `NarrationLiteral` is the only part shape with a `value` key, `NarrationValue` is the only one with `rendered`+`expression`, and `NarrationPlaceholder` is the only one with `name`; no explicit `kind` field is needed.

   Plain-`str` steps and scenarios serialize `"text_parts": null` / `"name_parts": null` unconditionally — we don't strip `None` values from the dump. **Intentional**: it keeps a single dispatch shape on read (one branch on `is None`, no `dict.get(...)` ladder) and makes the JSON schema predictable for external consumers. The size impact is negligible.

## Implementation Touch Points

| File | Change |
|---|---|
| `pyproject.toml` | `requires-python = ">=3.14"`; `[tool.mypy] python_version = "3.14"`. Re-run `uv lock`. |
| `src/pytest_given/template.py` *(new)* | `Template` class + `NarrationLiteral` / `NarrationValue` / `NarrationPlaceholder` / `NarrationPart`. |
| `src/pytest_given/__init__.py` | Export `Template`. |
| `src/pytest_given/model.py` | Add `Step.text_parts: list[NarrationPart] \| None = None`. Add `Scenario.name_parts: list[NarrationPart] \| None = None`; `Scenario.name` stays `str` (the raw template when Template-authored). |
| `src/pytest_given/decorators.py` | `given/when/then` accept `str \| templatelib.Template` (import as `from string import templatelib` to avoid the name collision with `pytest_given.Template`; reference t-strings as `templatelib.Template`). Runtime `isinstance` check rejects `pytest_given.Template` with the documented message. `StepDescriptor` carries `text: str` and `text_parts`. Helper `_to_text_parts(text)`. Decorator-on-fixture path rejects `text_parts is not None`. `scenario(name)` accepts `str \| Template`. |
| `src/pytest_given/collector.py` | `push_step` accepts `str \| templatelib.Template`; `attach` accepts the same. `start_scenario` accepts `str \| Template` for the scenario name. |
| `src/pytest_given/plugin.py` | Remove `_templatize_step_text` and `_templatize_steps`. Add structural templatize. `_group_parameterized` merge key uses `template.template` when scenario name is a `Template`. Add `pytest_collection_modifyitems` hook for the Template-on-non-parametrized validation (Resolution Rule 1). |
| `src/pytest_given/renderer.py` | Replace `highlight_params` with `step_text`. Remove `_PARAM_RE`. Add `.param-value` highlight class. Per-case rendering for `NarrationPlaceholder` substitutes from the case's values. |
| `src/pytest_given/templates/report.html.j2` | Switch step-text and scenario-name call sites to the new filter. Per-case rows pass the case dict into the filter for placeholder substitution. |
| `src/pytest_given/templates/styles.css` | `.param-value` rule. |
| `tests/unit/test_template.py` *(new)* | `Template` parsing, substitution, errors, `get_identifiers`. |
| `tests/integration/test_plugin.py` | New cases below; remove cases that exercised the legacy `{name}` regex and `_templatize_step_text`. |
| `tests/examples/test_examples.py` | Migrate to t-strings + `Template`. Regenerate `examples/report.html` via `nox -s examples`. |
| `README.md`, `AGENTS.md` | "Step text & placeholders" section (table below). |
| `uv.lock` | Regenerate via `uv lock`. |

## Test Coverage

Integration (`tests/integration/test_plugin.py`):

1. **t-string in non-parametrized scenario** → value span with `param-value` highlight; no `{name}` token.
2. **t-string in parametrized scenario, expression matches param name** → merged template shows `{name}`; per-case parameter table renders values.
3. **t-string with arbitrary expression** (`t'cost: {price * 1.2}'`) → neutral highlight; no param-table link.
4. **t-string conversion + format_spec** (`t'{n:03d}'`, `t'{obj!r}'`) → `NarrationValue.rendered` matches Python `format(value, spec)` post-conversion.
5. **Template in `@scenario(name)`** in a parametrized scenario → cases group correctly; per-case rendered name substitutes values.
6. **`given(Template(...))` / `when(Template(...))` / `then(Template(...))`** → `PytestGivenError` with the documented message pointing to t-string.
7. **Mixed authoring within one scenario** — `@scenario(Template(...))` for the name, t-string and plain `str` steps inside — each rendered by its own path.
8. **Unmatched Template placeholder** (`Template('a {cup_zize} cup')` with `cup_size` parametrize) → `PytestGivenError` at scenario merge with helpful message.
9. **`@scenario(Template(...))` on a non-parametrized test** → `PytestGivenError` at collection (verified via `pytest --collect-only`), with the documented message referencing the nodeid.
10. **Same-value-different-name disambiguation**: `t'{cup_size}, {beans_g}'` with `cup_size=200, beans_g=200` → both correctly templatized; legacy regex couldn't have.
11. **`@given(t'...')` / `@given(Template(...))` on a fixture** → `PytestGivenError` at decoration time.
12. **`attach(Template(...), ...)`** → `PytestGivenError` with the documented message.
13. **Static `str` with literal braces** (`'config: {key: value}'`) → renders verbatim, no highlight, no error.
14. **Back-compat read of legacy JSON** (no `text_parts` field) → renders literal text; no crash.

Unit (`tests/unit/test_template.py` plus existing):

- `Template.substitute`: plain names, format specs, conversions.
- `Template.substitute` raises `KeyError` on missing mapping entry.
- `Template('a {cup_size')` raises `ValueError` at construction.
- `Template('count={obj.attr}')`, `Template('{d[key]}')`, `Template('{x + 1}')` each raise `PytestGivenError` at construction (bare-identifier check).
- `Template('escaped {{name}} literal').substitute({})` → `'escaped {name} literal'`.
- `Template.get_identifiers` returns placeholder names in source order.
- `_to_text_parts_tstring`: conversion + format_spec + consecutive interpolations + empty literal segments.

## Documentation

Add a "Step text & placeholders" section to README and AGENTS.md:

| Context | Form | Effect |
|---|---|---|
| Test body, values in scope | `with given(t'a {cup_size} cup')` | Eager interpolation; value highlighted; cross-linked to parameter table when expression matches a param name. |
| `@scenario(name)`, future Annotated | `@scenario(Template('Brew {cup_size} ml'))` | Deferred substitution; same `{...}` syntax; unmatched placeholders raise. |
| Static label | `with given('static text')` | Literal — braces are braces. |

Three forms, one placeholder syntax, no regex special case.

**The README and AGENTS.md sections MUST call out three things explicitly:**
1. **Bare-identifier restriction on `Template`** — no attribute access, indexing, or arbitrary expressions. Worked example showing the workaround: parametrize by the attributes, or use a t-string in the test body.
2. **Lane separation** — `pytest_given.Template` is for `@scenario(...)` (and future Annotated), not test bodies; t-strings are for test bodies. The two contexts don't overlap.
3. **First-case-is-template limitation for parametrized scenarios** — the merged report shows case 1's step structure for all rows of the parameter table; this is misleading if narration structure varies per case. Show the conditional-narration anti-pattern and point to the workaround (split into separate tests, or parametrize by the variant). Today's README parametrize example (around line 112-122) is a good anchor — extend it with a "Limitation" sub-section.

T-strings get the full expression syntax; `Template` does not. Surfacing these in user docs — not just in the spec caveats — is what keeps users from hitting the `PytestGivenError` on first try and from being misled by parametrize merging.

## Migration

What breaks for current pytest-given users (acceptable for a 0.1.0 project):

- `@scenario('Brew {cup_size} ml')` in a parametrized scenario → renders literally as `Brew {cup_size} ml`. **Fix:** `@scenario(Template('Brew {cup_size} ml'))`.
- `with given(f'a {cup_size} ml cup')` in a parametrized test body → renders the first case's value across all cases. **Fix:** `with given(t'a {cup_size} ml cup')`.
- `with given('a {cup_size} ml cup')` (plain str with placeholder) → renders literally. **Fix:** `t'a {cup_size} ml cup'` (in `given/when/then`, only t-strings work for dynamic narration).
- Literal `{` `}` in static step text — no longer interpreted as placeholders. (Quiet improvement.)

In-repo migration (`tests/examples/test_examples.py` + example report regeneration) is included in Implementation Touch Points.

## Relationship to the deferred Annotated spec

`proposed/2026-05-23-annotated-fixture-labels-design.md` stays **deferred**. When revisited, it inherits `pytest_given.Template` as the canonical authoring form for Annotated — `Annotated[int, given(Template('a {cup_size} ml cup'))]` — replacing the previous bare-`str`-with-`{name}` proposal. With t-strings covering parametrize narration in test bodies, the Annotated revisit's remaining motivators (per-consumer fixture relabeling, undecorated-fixture promotion) may justify a narrower follow-up or be dropped entirely.

## Caveats

- **`Template` only accepts bare identifiers.** No attribute access, indexing, arbitrary expressions, method calls, walrus, ternaries. Workaround: add a derived parametrize column (e.g., parametrize by `total, passed` rather than a packed `results` object), or move the value into a test-body t-string.
- **First case is the template (parametrized scenarios only).** When a scenario is parametrized, `_group_parameterized` collapses the N case-records into one logical scenario plus a parameter table; the step *structure* shown to the reader comes from case 1's `text_parts`. Cases 2..N's `text_parts` are discarded — only their per-case values are preserved (in the parameter table and, for matching placeholders, in per-case rendering). This is fine for the common pattern where every case runs the same code and the only per-case difference is values plugged into a fixed narration. It is **misleading** when the narration structure itself varies across cases (e.g., conditional `with given(t'...')` branches inside a parametrized test), because case 1's narration is shown for all rows of the parameter table. Workarounds today: split into separate `@scenario` tests, or parametrize by a column whose value *is* the variant (`parametrize('case_label', ['small', 'big'])` and use `t'{case_label} number: {n}'`). Future option (separate spec): a per-scenario opt-out flag — e.g., `@scenario(name, group_parametrized=False)` — that emits each case as its own scenario in the report (named by substituting Template placeholders per case, or by appending the parametrize id to a `str` name), bypassing the merge entirely. Out of scope here; this caveat documents the current behavior.
- **`NarrationValue.expression` is stored verbatim in JSON.** A step like `t'cost: {self._secret_attr}'` writes that expression text into the report. Niche concern.

## Out of Scope

- T-strings in `@scenario(...)` and `Annotated[...]` — rejected, and `NameError`-blocked by Python anyway.
- T-strings on fixture decorators.
- `Template` on fixture decorators — reserved for the future Annotated revisit.
- `Template` substitution from non-parametrize sources (fixtures, globals, computed values). Substitution mapping is `callspec.params` only.
- Backward-compatibility shim for the dropped `{name}` regex highlight or `_templatize_step_text`. Project is 0.1.0; clean break.
- Format-spec nesting (`{x:{width}}`) — accepted by `Formatter().parse`, not explicitly tested.
