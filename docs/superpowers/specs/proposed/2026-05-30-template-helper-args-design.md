# Template on Helper-Function Decorators — Design

## Goal

Let `pytest_given.Template` substitute against a decorated helper's bound argument values, so dynamic narration works for the helper-function case the same way it does for parametrized scenarios:

```python
@when(Template('I insert ${amount}'))
def insert(machine, amount):
    machine['balance'] += amount
```

Each call to `insert(machine, 2)` records a step `"I insert $2"`. Placeholder names must appear in the function's signature; mismatches raise at decoration time.

## Background

Three lanes exist today for narration source (see `2026-05-23-structured-step-text-design.md`):

| Lane | Eager / deferred | Substitution source |
|---|---|---|
| `t'...'` in test body | eager | lexical scope |
| `pytest_given.Template` in `@scenario(...)` | deferred | `callspec.params` |
| Plain `str` everywhere | none | — |

Helper-function decorators (`@given/@when/@then` on a non-fixture helper) sit in a fourth lane: deferred substitution, but the source is **the function's bound arguments** at each call, not parametrize columns. T-strings can't fill this slot — `amount` isn't in scope at `@when(...)` evaluation time, so `@when(t'I insert {amount}')` `NameError`s. `Template` is the right deferred form, and the function signature is in scope at decoration time, so unmatched placeholders can fail fast (cleaner than the collection-time check `@scenario(Template(...))` needs).

### Prerequisite (separate fix): helper-function step recording

`StepDescriptor.__call__` in `decorators.py:67` currently wraps the function but does **not** push a step on call — `_step_descriptor` is only consumed by `pytest_fixture_setup` (`plugin.py:149`). The README example

```python
@when('inserting money')
def insert(amount):
    ...
```

is therefore currently a no-op for non-fixture helpers: `'inserting money'` never reaches the report. Verified in `examples/test_examples.py:83-91`: two `@when`-decorated helpers (`validate_coin_step`, `update_balance_step`) are called from `validate_coin` in `test_buy_with_validation` ("Helper functions can record their own steps"), but `examples/report-data.json` for that scenario contains only the test-body steps — neither `"the coin is validated"` nor `"the balance is updated"` appears.

That's a separate bug, fixed before this spec lands. This spec assumes the helper-function decorator records a step on each call (push on entry, pop in `finally`, with the same "unannotated test" warning the context-manager path already has). Once that's in, the Template layer here is purely additive.

## Approach

`@given/@when/@then` accept `Template` in their decorator role (currently rejected for the fixture decorator path; permitted-and-validated here for the helper-function path). At decoration time, the decorator inspects the wrapped function's signature, checks every placeholder is a parameter, and stores the parsed `Template` on the wrapper. At each call, the wrapper binds the actual args to that signature, substitutes the Template against the bound mapping, and pushes a step whose narration carries the rendered text plus structured `parts` with placeholders resolved to `NarrationValue` (so values get the neutral highlight, same treatment as t-strings outside parametrize).

## API

```python
@when(Template('I insert ${amount}'))
def insert(machine, amount):
    ...

@given(Template('a balance of ${initial:,.2f}'))
def setup_balance(initial):
    return Account(initial)

@then(Template('the receipt says {message!r}'))
def assert_receipt(machine, message):
    ...
```

### Substitution source

The function's signature, bound per call:

```python
sig = inspect.signature(func)
# at call time:
bound = sig.bind(*args, **kwargs)
bound.apply_defaults()
mapping = bound.arguments  # dict[str, Any], keyed by parameter name
```

`Template.substitute(mapping)` produces the rendered string. `apply_defaults()` ensures placeholders that reference parameters with defaults still resolve when the caller omits them.

### Decoration-time validation

In `StepDescriptor.__call__(func)`, when the narration source was a `pytest_given.Template`:

1. `sig = inspect.signature(func)`.
2. Build `param_names = set(sig.parameters)` — includes positional, keyword, defaulted, and `*args` / `**kwargs` names (the *names* of the catch-alls, e.g. `'args'`, `'kwargs'`).
3. For each `name` in `template.get_identifiers()`, require `name in param_names`. Mismatch → `PytestGivenError`:

   > `@when(Template('I insert ${amount}')) references placeholder {amount} which is not a parameter of insert(machine, _). Available parameters: machine. Rename the placeholder, or add the parameter.`

`*args` and `**kwargs` placeholder behavior is **explicitly rejected at validation**: even though `kwargs` appears in `param_names`, `bound.arguments['kwargs']` is a dict and substituting it produces unhelpful output. We require placeholders to be regular positional-or-keyword parameters:

```python
allowed_kinds = {
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.KEYWORD_ONLY,
    inspect.Parameter.POSITIONAL_ONLY,
}
for name in template.get_identifiers():
    param = sig.parameters.get(name)
    if param is None or param.kind not in allowed_kinds:
        raise PytestGivenError(...)
```

### Call-time substitution

The prerequisite fix lands the push/pop machinery in `StepDescriptor.__call__`'s wrapper. This spec adds a single step before the push: building the per-call narration when the descriptor's source was a `Template`.

```python
@functools.wraps(func)
def wrapper(*args, **kwargs):
    narration = self._narration_for_call(func, sig, args, kwargs)
    # …existing push/pop machinery from the prerequisite fix…
```

Where `_narration_for_call`:

- If `self.narration.parts` is empty (plain `str` source): return `self.narration` unchanged.
- Otherwise (Template source): bind args, apply defaults, call `_resolve_template_parts(self.narration.parts, bound.arguments)` to produce the per-call `parts`, and use `Template.substitute` (or the equivalent reduction over the resolved parts) for `text`.

`sig` is captured once at decoration time (it doesn't change between calls), so `inspect.signature(func)` runs exactly once per decorated helper.

### Rendered-narration `parts`

For the report, each call produces a fresh `Narration` whose `parts` mirror the Template structure but with placeholders resolved to `NarrationValue`:

```python
def _resolve_template_parts(
    parts: list[NarrationPart],
    mapping: Mapping[str, Any],
) -> list[NarrationPart]:
    out: list[NarrationPart] = []
    for part in parts:
        match part:
            case NarrationLiteral():
                out.append(part)
            case NarrationPlaceholder(name=name, format_spec=spec, conversion=conv):
                resolved = _FORMATTER.convert_field(mapping[name], conv)
                rendered = format(resolved, spec)
                out.append(NarrationValue(
                    rendered=rendered,
                    expression=name,        # the parameter name doubles as the expression
                    format_spec=spec,
                    conversion=conv,
                ))
    return out
```

Effect in the report: substituted values render with the neutral value-highlight (`.param-value` class), identical to non-parametrize t-string interpolations. Literal text renders verbatim.

Helper calls are **not** tied to a scenario's parametrize cases, so the existing parametrize-merge path (which converts `NarrationValue` → `NarrationPlaceholder` when `expression in param_names`) is irrelevant — helper calls produce concrete values per call, not per case. If the same helper is called twice in one scenario with different args, two distinct steps render, each with its own resolved value. (See "Open question" #1 below.)

### Public-API surface change in `decorators.py`

The existing `StepDescriptor.__call__` guard

```python
if self.narration.parts:
    raise PytestGivenError("@given(t'...') / @given(Template(...)) is not allowed on a fixture; …")
```

becomes finer-grained:

- t-string (`templatelib.Template`) on any decorator path: still rejected. Values aren't in scope at decoration time.
- `pytest_given.Template` on a fixture (`@pytest.fixture` + `@given(Template(...))`): still rejected in this spec. Substitution source for a fixture is its own arg values (other fixtures); resolving those requires the fixture-recording machinery and per-consumer substitution — out of scope here. Reject with: `"@given(Template(...)) on a fixture is not yet supported; use a plain string label, or move the step into a helper function."` Discrimination: `getattr(func, '_pytestfixturefunction', None)` — pytest's fixture marker.
- `pytest_given.Template` on a non-fixture helper: **accepted**, with the validation above.

`_reject_pytest_given_template` in `decorators.py:126` no longer applies to decorator role — only to context-manager role inside test bodies (where t-strings remain the right tool).

## Data model

No changes. `Narration` already carries `text + parts`; per-call narrations slot in as ordinary steps. The Template's stored `parts` on the descriptor act as a render template; `_resolve_template_parts` produces the per-call list.

## Error handling

| Situation                                                                                  | Behavior                                                                                                  |
|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| Template placeholder doesn't match any parameter                                            | `PytestGivenError` at decoration time, listing available parameter names                                  |
| Template placeholder matches `*args` / `**kwargs` (catch-all)                               | `PytestGivenError` at decoration time, with workaround: "use a positional-or-keyword parameter"            |
| Helper called outside any active scenario (unannotated test)                                | Same warning as the context-manager case (`decorators.py:42`); function still runs                       |
| Helper called from fixture teardown                                                         | `PytestGivenError` raised by `collector.push_step` — existing behavior, unchanged                          |
| Helper raises mid-call                                                                      | `pop_step` runs in `finally`; the step is recorded as `failed` via the existing error-propagation path    |
| `sig.bind(*args, **kwargs)` raises `TypeError` (caller's bug, not ours)                     | Propagate untouched. The narration substitution never runs; the caller's `TypeError` surfaces naturally   |
| `pytest_given.Template` decorating a `@pytest.fixture`                                      | `PytestGivenError` with the documented "not yet supported" message                                        |

## Open questions

1. **Helper called multiple times in one scenario.** Each call produces a distinct step in the report. With dynamic narration, that's exactly what the reader wants (`"I insert $2"`, then `"I insert $5"`). Confirm this is the desired behavior — vs. e.g. coalescing identical-text calls (no, that's surprising) or showing a call count (probably also no, the report already lists each call as its own step).

2. **Should the fixture path also support `Template`?** Spec defers it. The fixture's arg values are other fixtures' return values; conceptually the same `inspect.signature` + bound-args trick works. The implementation friction is that the recording is per-fixture-instance, not per-consumer, so the substituted text bakes in at fixture-setup time — fine for typical usage. If this turns out to be one of those "actually trivial once Template-on-helpers is in" extensions, fold it into the same PR; otherwise file as a follow-up.

3. **Should the test-body `with when(Template(...))` rejection ease?** No. T-strings handle the test-body case cleanly; adding a third form there would just be three-ways-to-do-it. The rejection stays.

## Testing

Unit (`tests/unit/test_step_descriptor.py`):

- `@when(Template('I insert ${amount}'))` validates `amount` is in the signature; happy-path returns the wrapper.
- Placeholder not in signature → `PytestGivenError` at decoration time, message lists available parameters.
- Placeholder names a catch-all (`*args`, `**kwargs`) → `PytestGivenError` at decoration time.
- Defaulted parameter omitted at call → substitution uses the default.
- Format spec and conversion preserved through resolution (`Template('amount={x:.2f}')`, `Template('{obj!r}')`).
- Helper called without active collector / outside `@scenario` → warns and runs.
- Helper raises mid-call → step pops; exception propagates.

Integration (`tests/integration/test_plugin.py`):

- End-to-end `@when(Template(...))` helper called from a scenario → step appears in JSON with `narration.text` = rendered string, `narration.parts` containing `NarrationValue` for each substituted placeholder.
- Same helper called twice with different args → two distinct steps, each with its own resolved text.
- HTML report renders the substituted values with the `.param-value` highlight class.
- `@given(Template(...))` on a `@pytest.fixture` → `PytestGivenError` with the "not yet supported" message.

(Plain-`str` helper recording is covered by the prerequisite fix's tests, not here.)

Examples:

- Migrate `examples/test_examples.py:83-91` from `@when('the coin is validated')` (currently not recorded) to `@when(Template('the coin is validated for ${amount}'))` and regenerate `examples/report.html`.

## Documentation

- **README:** update the "Step text & placeholders" section. Add a row:

  | Form | Example | How it renders |
  |---|---|---|
  | `Template` in `@given/@when/@then` on a helper function | `@when(Template('I insert ${amount}'))` | Deferred substitution against the function's bound arguments at each call. |

  Update the existing "any phase" sentence in the helper-functions paragraph to note that the helper records its own step on each call.

- **AGENTS.md:** mirror the README addition.
- **GLOSSARY.md:** no new term — Template is already documented.

## Out of scope

- `Template` substitution from `*args` / `**kwargs` packed values. Use named parameters.
- `Template` on fixture decorators (`@pytest.fixture` + `@given(Template(...))`). Deferred — see Open question #2.
- T-strings on any decorator path. Continues to be rejected.
- Per-call coalescing or call-count summarization for repeated helper calls.
- Showing the helper's source location separately in the report. (The source-link spec, `2026-05-30-source-link-design.md`, surfaces the *scenario*'s source; helper source is a separate, narrower question.)
