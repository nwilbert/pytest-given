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

Three authoring forms, each with a clear lane:

| Form | Syntax | Use site | Evaluation |
|---|---|---|---|
| `str` | literal text | Static labels | None |
| `templatelib.Template` (t-string) | `t'a {cup_size} cup'` | Test bodies — values in scope | Eager, at construction |
| `pytest_given.Template` | `Template('a {cup_size} cup')` | `@scenario`, future Annotated | Deferred, at substitute time |

When a step is recorded, the collector stores both a flat `text: str` and an optional structured `text_parts: list[TextPart] | None`. The same `text_parts` model serves both Template types:

- **t-string** → `text_parts` carries `TextLiteral` / `TextValue` (value-with-expression, already known).
- **`pytest_given.Template`** → `text_parts` carries `TextLiteral` / `TextPlaceholder` (name + format spec, unresolved until merge).

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
        self.parts: list[TextPart] = []
        for literal, name, spec, conversion in formatter.parse(template):
            if literal:
                self.parts.append(TextLiteral(value=literal))
            if name is not None:
                self.parts.append(
                    TextPlaceholder(name=name, format_spec=spec or '', conversion=conversion)
                )

    def substitute(self, mapping: Mapping[str, Any]) -> str:
        out: list[str] = []
        for part in self.parts:
            if isinstance(part, TextLiteral):
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
        return [p.name for p in self.parts if isinstance(p, TextPlaceholder)]
```

Syntax supported (inherited from `string.Formatter`): plain `{name}`, attribute access `{obj.attr}`, string-key indexing `{d[key]}`, format specs `{n:03d}`, conversions `{obj!r}`. **Not** supported: arbitrary expressions, method calls with `()`, walrus, ternaries — that's the right ceiling for deferred substitution where values come from a mapping, not lexical scope. T-strings remain the full-expressiveness form for in-scope authoring.

Construction-time validation: `Formatter().parse()` raises `ValueError` on unclosed `{` or invalid syntax — so `Template('a {cup_size')` errors at the call site, not later. Literal braces use the `{{` / `}}` escape, identical to f/t-strings.

### `given(text)`, `when(text)`, `then(text)`

```python
def given(text: str | templatelib.Template | Template) -> StepDescriptor: ...
def when(text: str | templatelib.Template | Template) -> StepDescriptor: ...
def then(text: str | templatelib.Template | Template) -> StepDescriptor: ...
```

Usage:

```python
with given(t'a {cup_size} ml cup'):                # eager — preferred for in-scope values
    ...
with given(Template('a {cup_size} ml cup')):       # deferred — rare in test body
    ...
with given('static label'):                        # literal
    ...
```

### `attach(label, content)`

`label` accepts `str | templatelib.Template | Template`. Renders to a string at recording time; structural info discarded — attachment labels don't carry per-case substitution.

### `scenario(name)`

```python
def scenario(name: str | Template, tags: list[str] | None = None) -> ScenarioDecorator: ...
```

Accepts `str | pytest_given.Template`. **Rejects t-string** — `@scenario` runs at module-import time, so a t-string referencing a parametrize parameter `NameError`s in Python before our code runs; if a t-string referencing only in-scope module constants somehow reaches `scenario()`, we still reject it with `PytestGivenError` (the type signature excludes it, runtime `isinstance` check enforces it).

The merge key for `_group_parameterized` is:

- `str` → the string itself (existing behavior).
- `Template` → `template.template` (the raw `{name}`-bearing source). All cases of a parametrized scenario share that exact raw string, so they merge into one group; per-case rendering substitutes from `callspec.params`.

JSON model for scenario names mirrors the step model: `Scenario.name: str` always holds the rendered (or raw, for Template) string; `Scenario.name_parts: list[TextPart] | None` holds the structured form when the name was a Template. Rendering dispatches on `name_parts` exactly like step text.

### Fixture-side decorators (`@given(text)` on a fixture)

Fixture decorators accept `str` only in this spec. T-strings can't reference fixture argument values at decoration time. `pytest_given.Template` on a fixture decorator is reserved for the future Annotated revisit (where the substitution source becomes the consuming scenario's params); not wired up here.

Rejection happens in `StepDescriptor.__call__(func)`: any `text_parts is not None` reaching the decorator-application path raises `PytestGivenError("@given(t'...') / @given(Template(...)) is not allowed on a fixture; the fixture's argument values aren't in scope at decoration time. Use a plain string label, or move the step into the test body.")`.

### Step model additions

```python
from typing import Literal

@dataclass(frozen=True)
class TextLiteral:
    kind: Literal['literal'] = 'literal'
    value: str = ''

@dataclass(frozen=True)
class TextValue:
    """A t-string interpolation — value already known."""
    kind: Literal['value'] = 'value'
    rendered: str = ''        # str(value) post-conversion+format_spec
    expression: str = ''      # source expression text

@dataclass(frozen=True)
class TextPlaceholder:
    """A deferred placeholder from pytest_given.Template — resolved at merge/render time."""
    kind: Literal['placeholder'] = 'placeholder'
    name: str = ''
    format_spec: str = ''
    conversion: str | None = None

TextPart = TextLiteral | TextValue | TextPlaceholder

@dataclass
class Step:
    ...
    text_parts: list[TextPart] | None = None  # None for plain-str authoring
```

## Resolution Rules

1. **Recording.** `collector.push_step(phase, text)` dispatches on type:
   - `str` → `Step(text=text, text_parts=None)`.
   - `templatelib.Template` → `_to_text_parts_tstring(t)` iterates the Template (yielding `str | Interpolation`), applies conversion then `format(value, format_spec)` per interpolation, and produces a rendered string plus `[TextLiteral | TextValue, ...]`.
   - `pytest_given.Template` → `(template.template, list(template.parts))`. The flat `text` field holds the raw template; substitution happens at merge/render time.

2. **Parametric merge.** `_group_parameterized` walks `first.steps` for the merged-template structure (existing first-case-is-template behavior). Per step:
   - `text_parts is None`: pass through unchanged.
   - `text_parts is not None`: walk parts.
     - `TextLiteral`: unchanged.
     - `TextValue`: if `expression in param_names`, rewrite `rendered = '{' + expression + '}'` so the renderer highlights it with the param color. Otherwise leave verbatim (same value across all cases by construction).
     - `TextPlaceholder`: if `name in param_names`, keep as-is (renderer substitutes per case from the parameter table). If `name not in param_names`, raise `PytestGivenError` with the file/line of the call site — Template placeholders that don't match a parametrize name are almost always typos.

   `_templatize_step_text` is removed. F-strings in parametrized test bodies no longer reverse-templatize.

3. **Render.** New Jinja filter `step_text(step, case=None)` returns Markup:
   - `step.text_parts is None`: render `step.text` HTML-escaped. No regex pass; braces render as braces.
   - `step.text_parts is not None`: walk parts.
     - `TextLiteral`: escaped literal.
     - `TextValue`: `<span class="param-color-N">…</span>` if `expression in param_color_map`, else `<span class="param-value">…</span>`.
     - `TextPlaceholder`: when rendering a specific case, substitute via `mapping = dict(zip(param_names, case.values))` and wrap the substituted value in `<span class="param-color-N">`. When rendering the merged-template view (no case), render as `{name}` wrapped in the param-color span.

   `scenario.name` rendering: same dispatch on the scenario name — `str` → literal, `Template` → walk `template.parts`.

   The old `highlight_params` filter and `_PARAM_RE` are removed.

4. **JSON model.** `text_parts` and the scenario-name `Template` serialize via `dataclasses.asdict` as dicts with a `kind` discriminator. The renderer loads JSON as raw dict via `json.loads` (renderer.py:21); absent or `null` `text_parts` falls through to the literal-render path. Back-compatible: old reports still render (without the new highlights since they have no `text_parts`).

## Implementation Touch Points

| File | Change |
|---|---|
| `pyproject.toml` | `requires-python = ">=3.14"`; `[tool.mypy] python_version = "3.14"`. Re-run `uv lock`. |
| `src/pytest_given/template.py` *(new)* | `Template` class + `TextLiteral` / `TextValue` / `TextPlaceholder` / `TextPart`. |
| `src/pytest_given/__init__.py` | Export `Template`. |
| `src/pytest_given/model.py` | Add `Step.text_parts: list[TextPart] \| None = None`. Add `Scenario.name_parts: list[TextPart] \| None = None`; `Scenario.name` stays `str` (the raw template when Template-authored). |
| `src/pytest_given/decorators.py` | `given/when/then` accept `str \| templatelib.Template \| Template` (import as `from string import templatelib` to avoid the name collision with `pytest_given.Template`; reference t-strings as `templatelib.Template`). `StepDescriptor` carries `text: str` and `text_parts`. Helper `_to_text_parts(text)`. Decorator-on-fixture path rejects `text_parts is not None`. `scenario(name)` accepts `str \| Template`. |
| `src/pytest_given/collector.py` | `push_step` and `attach` accept the same union. |
| `src/pytest_given/plugin.py` | Remove `_templatize_step_text` and `_templatize_steps`. Add structural templatize. `_group_parameterized` merge key uses `template.template` when scenario name is a `Template`. |
| `src/pytest_given/renderer.py` | Replace `highlight_params` with `step_text`. Remove `_PARAM_RE`. Add `.param-value` highlight class. Per-case rendering for `TextPlaceholder` substitutes from the case's values. |
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
4. **t-string conversion + format_spec** (`t'{n:03d}'`, `t'{obj!r}'`) → `TextValue.rendered` matches Python `format(value, spec)` post-conversion.
5. **Template in `@scenario(name)`** in a parametrized scenario → cases group correctly; per-case rendered name substitutes values.
6. **Template in a test-body step** → `text_parts` carries `TextPlaceholder`s; merge resolves them against `param_names`; renders identically to a matching t-string.
7. **Mixed authoring** — plain str, t-string, Template — each rendered by its own path.
8. **Unmatched Template placeholder** (`Template('a {cup_zize} cup')` with `cup_size` parametrize) → `PytestGivenError` at scenario merge with helpful message.
9. **Same-value-different-name disambiguation**: `t'{cup_size}, {beans_g}'` with `cup_size=200, beans_g=200` → both correctly templatized; legacy regex couldn't have.
10. **`@given(t'...')` / `@given(Template(...))` on a fixture** → `PytestGivenError` at decoration time.
11. **Static `str` with literal braces** (`'config: {key: value}'`) → renders verbatim, no highlight, no error.
12. **Back-compat read of legacy JSON** (no `text_parts` field) → renders literal text; no crash.

Unit (`tests/unit/test_template.py` plus existing):

- `Template.substitute`: plain names, attribute access, indexing, format specs, conversions.
- `Template.substitute` raises `KeyError` on missing mapping entry.
- `Template('a {cup_size')` raises `ValueError` at construction.
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

## Migration

What breaks for current pytest-given users (acceptable for a 0.1.0 project):

- `@scenario('Brew {cup_size} ml')` in a parametrized scenario → renders literally as `Brew {cup_size} ml`. **Fix:** `@scenario(Template('Brew {cup_size} ml'))`.
- `with given(f'a {cup_size} ml cup')` in a parametrized test body → renders the first case's value across all cases. **Fix:** `with given(t'a {cup_size} ml cup')`.
- `with given('a {cup_size} ml cup')` (plain str with placeholder) → renders literally. **Fix:** `t'...'` or `Template('...')`.
- Literal `{` `}` in static step text — no longer interpreted as placeholders. (Quiet improvement.)

In-repo migration (`tests/examples/test_examples.py` + example report regeneration) is included in Implementation Touch Points.

## Relationship to the deferred Annotated spec

`2026-05-23-annotated-fixture-labels-design.md` stays **deferred**. When revisited, it inherits `pytest_given.Template` as the canonical authoring form for Annotated — `Annotated[int, given(Template('a {cup_size} ml cup'))]` — replacing the previous bare-`str`-with-`{name}` proposal. With t-strings covering parametrize narration in test bodies, the Annotated revisit's remaining motivators (per-consumer fixture relabeling, undecorated-fixture promotion) may justify a narrower follow-up or be dropped entirely.

## Caveats

- **`Template` is a subset of f-string expressiveness.** No arbitrary expressions, method calls with `()`, walrus, ternaries. Workaround: add a derived parametrize column, or move the value into a test-body t-string.
- **First case is the template.** `_group_parameterized` uses `first.steps` for the merged-template structure (existing behavior). Non-first cases' `text_parts` are discarded.
- **`TextValue.expression` is stored verbatim in JSON.** A step like `t'cost: {self._secret_attr}'` writes that expression text into the report. Niche concern.

## Out of Scope

- T-strings in `@scenario(...)` and `Annotated[...]` — rejected, and `NameError`-blocked by Python anyway.
- T-strings on fixture decorators.
- `Template` on fixture decorators — reserved for the future Annotated revisit.
- `Template` substitution from non-parametrize sources (fixtures, globals, computed values). Substitution mapping is `callspec.params` only.
- Backward-compatibility shim for the dropped `{name}` regex highlight or `_templatize_step_text`. Project is 0.1.0; clean break.
- Format-spec nesting (`{x:{width}}`) — accepted by `Formatter().parse`, not explicitly tested.
