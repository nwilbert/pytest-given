# Step text & placeholders

You can write step text in several forms. Which form to use depends on where the step is.

## Forms

| Form | Example | How it renders |
|---|---|---|
| Plain string (including f-strings) | `with given('a cup')` <br> `with given(f'a {cup_size} cup')` | Shown as written. Python fills in an f-string before pytest-given sees it, so its values aren't highlighted. |
| T-string | `with given(t'a {cup_size} cup')` | pytest-given fills in the values when the step runs. A value gets a color when its expression matches a parametrize argument, and a neutral highlight otherwise. |
| `Template` in `@scenario(...)` | `@scenario(Template('Brew {cup_size} ml'))` | Placeholders are filled in from the parametrize arguments when the report is built. A placeholder that matches no argument raises `PytestGivenError` at collection. |
| T-string in `@scenario(...)` | `@scenario(t'A {guest.l} checks in')` | Glossary handles become term refs in the title. The t-string is evaluated when the module is imported, so it can only contain glossary handles; any other value raises `PytestGivenError`. |
| `Template` on a helper-function decorator | `@when(Template('I insert {amount}'))` | Placeholders are filled in from the helper's arguments on each call. Each placeholder must be the name of one of the helper's parameters; `*args` and `**kwargs` don't count. Any other name raises `PytestGivenError` when the helper is decorated. |
| `Annotated[..., given(...)]` on a test parameter | `def test(text: Annotated[str, given(Template('a {text} cup'))])` | Adds a `given` step for a fixture or parametrize value. A plain string is shown as written; a `Template` is filled in from the parametrize arguments. Only `given` is allowed, and t-strings are not. |

## Formatting

Scenario titles, step text, glossary definitions and avoided words can use a little Markdown. Everything else shows exactly as written, in the HTML report, the Markdown report and citations alike.

| Text | Bold, italic, code | A newline shows as | `<br>` | Where it shows |
|---|---|---|---|---|
| Scenario title | rendered | a space | literal | HTML, Markdown, citations |
| Step text | rendered | a space | literal | HTML, Markdown, narrated citations |
| Glossary term definition | rendered | a line break | a line break | HTML: Glossary tab, term ref tooltip |
| Avoided word | rendered | a line break | a line break | HTML: Glossary tab |
| Markdown glossary term names, kind cells and section headings | removed: `**Guest**` reads as `Guest` | — | literal | wherever the term or section shows |
| Everything else | literal | — | literal | |

*Rendered* means `**bold**` shows as bold, `*italic*` as italic and `` `code` `` as code. *Literal* means the characters show as written in every output, the Markdown report included. *Everything else* is the report title, term names and term refs, interpolated values, case IDs, story titles and clauses, tags, skip and xfail reasons, parameter column names and values, attachments and error messages.

Spans are read as [CommonMark](https://spec.commonmark.org/0.31.2/#emphasis-and-strong-emphasis) reads them, with these differences:

- **Code takes single backticks.** A run like ` `` ` shows as written.
- **Underscores never format**, so `__init__`, `_private_` and `snake_case` show as written.
- **One level:** bold and italic can contain code, but nothing else.
- **No escapes:** a backslash shows as written. To show a marker, put it in a code span.

Markdown is read only in the text you write, never in a value or a term ref: a value such as `'*'` is always just an asterisk. So a span can't hold a value or a term ref. `t'**{guest}** books'` or ``t'`run {command}`'`` raises `PytestGivenError`, since its markers would show as written. Keep the span within the text beside it, as in ``t'`run` {command}'``.

## Template placeholders

`pytest_given.Template` only accepts plain names: `{name}`, `{name:spec}`, `{name!conv}`. Attribute access (`{obj.attr}`), indexing (`{d[key]}`) and other expressions (`{x + 1}`) raise `PytestGivenError` when the `Template` is created.

Instead, parametrize by the attribute values directly, or move the step into the test body and use a t-string, which allows any expression.

## Boolean phrases

To word a Boolean in a step, write two phrases in its format spec, separated by a `|`. The true phrase comes first:

```python
@scenario('Pinning a step')
@pytest.mark.parametrize('pinned', [False, True])
def test_pin(pinned):
    with given(t'a step that {pinned:pins it|does not pin it}'):
        ...
```

The step shows `a step that {pins it / does not pin it}`, and the parameter table keeps `True` and `False`. Hovering a row in the HTML report puts that row's phrase into the sentence.

This works in a t-string and in a `Template`. The two phrases should complete the same sentence and word what the column's name says.

- **Phrases are literal.** Spaces around each phrase are removed. A phrase holds no Markdown and no term ref.
- **An apostrophe needs double quotes.** `t'{pinned:doesn't pin it|pins it}'` is a Python syntax error, so write `t"{pinned:doesn't pin it|pins it}"`.
- **Only a `bool` can take phrases**, and the two phrases must differ. Anything else, or a conversion such as `!r`, raises `PytestGivenError`.
- **The shape is reserved.** A spec like `{when:%H|%M}` on a `datetime` reads as phrases and raises. Format the text into a local variable first (`clock = when.strftime('%H|%M')`) and use `{clock}`.

## Template or t-string

A t-string is evaluated right away, so its values must exist at that point. In a test body they do. On a decorator they don't: decorators run when the module is imported, before any test. That's what `Template` is for: it's filled in later, once the values are known.

So using one in the other's place raises `PytestGivenError`. `with given(Template(...))` raises when the step starts, and a t-string on a fixture or helper decorator raises too.

The one exception is a t-string in `@scenario(...)`. It can contain glossary handles, because they already exist when the module is imported.
