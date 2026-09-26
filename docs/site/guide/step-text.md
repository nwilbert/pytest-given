# Step text & placeholders

You can write step text in several forms. Which form to use depends on where the step is.

## Forms

| Form | Example | How it renders |
|---|---|---|
| Plain string (including f-strings) | `with given('a cup')` <br> `with given(f'a {cup_size} cup')` | Shown as written. Python fills in an f-string before pytest-given sees it, so its values aren't highlighted. |
| T-string | `with given(t'a {cup_size} cup')` | pytest-given fills in the values when the step runs. A value gets a color when its expression matches a parametrize argument, and a neutral highlight otherwise. |
| `Template` in `@scenario(...)` | `@scenario(Template('Brew {cup_size} ml'))` | Placeholders are filled in from the parametrize arguments when the report is built. A placeholder that matches no argument raises `PytestGivenError` at collection. |
| T-string in `@scenario(...)` | `@scenario(t'a {guest} checks in')` | Glossary handles become term refs in the title. The t-string is evaluated when the module is imported, so it can only contain glossary handles; any other value raises `PytestGivenError`. |
| `Template` on a helper-function decorator | `@when(Template('I insert {amount}'))` | Placeholders are filled in from the helper's arguments on each call. Each placeholder must be the name of one of the helper's parameters; `*args` and `**kwargs` don't count. Any other name raises `PytestGivenError` when the helper is decorated. |
| `Annotated[..., given(...)]` on a test parameter | `def test(text: Annotated[str, given(Template('a {text} cup'))])` | Adds a `given` step for a fixture or parametrize value. A plain string is shown as written; a `Template` is filled in from the parametrize arguments. Only `given` is allowed, and t-strings are not. |

## Template placeholders

`pytest_given.Template` only accepts plain names: `{name}`, `{name:spec}`, `{name!conv}`. Attribute access (`{obj.attr}`), indexing (`{d[key]}`) and other expressions (`{x + 1}`) raise `PytestGivenError` when the `Template` is created.

Instead, parametrize by the attribute values directly, or move the step into the test body and use a t-string, which allows any expression.

## Template or t-string

A t-string is evaluated right away, so its values must exist at that point. In a test body they do. On a decorator they don't: decorators run when the module is imported, before any test. That's what `Template` is for: it's filled in later, once the values are known.

So using one in the other's place raises `PytestGivenError`. `with given(Template(...))` raises when the step starts, and a t-string on a fixture or helper decorator raises too.

The one exception is a t-string in `@scenario(...)`. It can contain glossary handles, because they already exist when the module is imported.
