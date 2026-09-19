# Step text & placeholders

| Form | Example | How it renders |
|---|---|---|
| Plain string (including f-strings) | `with given('a cup')` <br> `with given(f'a {cup_size} cup')` | Rendered verbatim. F-string interpolation happens before pytest-given runs, so values aren't highlighted. |
| T-string | `with given(t'a {cup_size} cup')` | pytest-given interpolates at runtime. Values are color-coded when the interpolation expression matches a parametrize column; otherwise highlighted neutrally. |
| `Template` in `@scenario(...)` | `@scenario(Template('Brew {cup_size} ml'))` | Deferred substitution against parametrize columns at report time. Unmatched placeholders raise `PytestGivenError` at collection. |
| T-string in `@scenario(...)` | `@scenario(t'a {guest} checks in')` | Glossary handles render as term refs in the title. Evaluated eagerly at import, so only glossary handles are allowed; a value/expression interpolation raises `PytestGivenError`. |
| `Template` on a helper-function decorator | `@when(Template('I insert {amount}'))` | Deferred substitution against the function's bound arguments at each call. Placeholders must name one of the helper's named parameters; an unmatched name — `*args`/`**kwargs` among them — raises `PytestGivenError` at decoration time. |
| `Annotated[..., given(...)]` on a test parameter | `def test(text: Annotated[str, given(Template('a {text} cup'))])` | Synthesizes a `given` step for a fixture or parametrize value at the call site. Plain string renders verbatim; `Template` does deferred substitution against parametrize columns. Only `given` is allowed; a t-string is rejected. |

Two rules follow from that split:

1. **`pytest_given.Template` only accepts bare identifiers** — `{name}`, `{name:spec}`, `{name!conv}`. Attribute access (`{obj.attr}`), indexing (`{d[key]}`), and arbitrary expressions (`{x + 1}`) raise `PytestGivenError` at construction. Workaround: parametrize by the attributes directly, or move the step into a test-body t-string (which supports full expression syntax).

2. **`Template` and a t-string are each rejected in the other's place**, because the split is about scope: `with given(Template(...))` raises `PytestGivenError` at entry, as does a t-string on a fixture or helper decorator. The one exception is the `@scenario(...)` t-string in the table — glossary handles, unlike values, *are* in scope at import.

