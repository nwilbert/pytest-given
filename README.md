# pytest-given

A pytest plugin that generates interactive HTML reports from Given/When/Then annotated tests. Inspired by [JGiven](https://jgiven.org/) (Java). The code is the single source of truth — no separate Gherkin DSL.

## Quick start

```python
import pytest
from pytest_given import attach, given, scenario, then, when


@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}


@scenario('Buy coffee', tags=['billing', 'happy-path'])
def test_buy_coffee(machine):
    with when('I insert $2'):
        machine['coffees'] -= 1
    with then('I get a coffee'):
        assert machine['coffees'] == 9
        attach('Machine state', machine)
```

Run it:

```bash
pytest --given-html
```

This produces `given-report/report-data.json` and `given-report/report.html` — a single self-contained HTML file with all assets inlined.

## Why pytest-given?

Classical BDD tools (Cucumber, behave, pytest-bdd) center on a natural-language DSL like Gherkin, designed so stakeholders can author tests themselves and engineers maintain the glue that binds each step to a Python function.

pytest-given is for the opposite case: **engineers write normal tests, and the plugin turns them into readable documentation**. The HTML report is something stakeholders, domain experts, and engineers on adjacent teams can open and follow — without any of them needing to touch the test suite. For the engineers writing the tests, the same narrative gives a high-level, domain-focused view of behavior that's easier to scan than raw test code. Grouping by tag or module, text search across scenario names and tags, and status filters help zero in on what matters.

- Plain Python — no Gherkin, no `.feature` files, no parser.
- Tests stay first-class pytest tests; the report is a by-product.
- Self-contained HTML: open it locally or attach it to CI artifacts; no server, no external assets.

## Public API

### `@scenario(name, tags=None)`

Mark a test for inclusion in the report. Required for any test you want to appear.

```python
@scenario('Buy coffee', tags=['billing'])
def test_buy_coffee(machine):
    ...
```

### `given(text)`, `when(text)`, `then(text)`

Dual-purpose: use as a **context manager** inside a test body, or as a **decorator** on a fixture or helper function.

As context managers:

```python
@scenario('Place order')
def test_order():
    with given('an empty cart'):
        cart = []
    with when('I add an item'):
        cart.append('coffee')
    with then('the cart has one item'):
        assert len(cart) == 1
```

As a fixture decorator (**only `@given` is allowed** — fixtures are setup, so `@when`/`@then` on a fixture is rejected at runtime):

```python
@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}
```

Generator fixtures work too; teardown is silent (the post-`yield` block runs but recording steps from it is not allowed):

```python
@pytest.fixture
@given('a database connection')
def db():
    conn = open_conn()
    yield conn
    conn.close()
```

As a helper-function decorator (any phase):

```python
@when('inserting money')
def insert(amount):
    ...
```

Steps can be nested freely:

```python
with when('I place a large order'):
    with when('I select 3 coffees'):
        order_count = 3
    with when('I apply loyalty discount'):
        ...
```

Parameterized tests are automatically grouped into a single scenario with a parameter table. Use **t-strings** (`t'...'`) to interpolate parameter values into step text — the plugin recognizes parameter names in t-string interpolations and color-codes them in the report:

```python
@scenario('Pricing')
@pytest.mark.parametrize('euros,expect', [(1, False), (2, True), (3, True)])
def test_pricing(machine, euros, expect):
    with when(t'I insert ${euros}'):
        can_buy = euros >= machine['price']
    with then(t'can_buy is {expect}'):
        assert can_buy == expect
```

For a parametrized **scenario name**, use `pytest_given.Template` — deferred substitution against the parametrize columns:

```python
from pytest_given import Template, scenario

@scenario(Template('Brew {cup_size} ml'))
@pytest.mark.parametrize('cup_size', [200, 300])
def test_brew(cup_size):
    ...
```

#### Step text & placeholders

Three authoring forms, one `{...}` placeholder syntax, no regex special case:

| Context | Form | Effect |
|---|---|---|
| Test body, values in scope | `with given(t'a {cup_size} cup')` | Eager t-string interpolation; value color-coded when the interpolation expression matches a parametrize column, otherwise neutrally highlighted. |
| `@scenario(name)` | `@scenario(Template('Brew {cup_size} ml'))` | Deferred substitution at report time. Unmatched placeholders raise `PytestGivenError` at collection. |
| Static label | `with given('static text')` | Literal — braces are braces. No regex pass. |

Three things worth knowing:

1. **`pytest_given.Template` only accepts bare identifiers** — `{name}`, `{name:spec}`, `{name!conv}`. Attribute access (`{obj.attr}`), indexing (`{d[key]}`), and arbitrary expressions (`{x + 1}`) raise `PytestGivenError` at construction. Workaround: parametrize by the attributes directly, or move the step into a test-body t-string (which supports full expression syntax).

2. **`Template` is for `@scenario(...)`, not test bodies.** In a test body, values are in scope — use a t-string. `given(Template(...))` / `when(Template(...))` / `then(Template(...))` raise `PytestGivenError`. T-strings in `@scenario(...)` are rejected for the symmetric reason: parametrize columns aren't in scope at module-import time.

3. **First case is the template (parametrized scenarios).** The merged report shows case 1's step structure for all rows of the parameter table. Correct for the common pattern (every case runs the same code, only values differ). **Misleading** when the narration *structure* varies per case — e.g., a conditional `with given(t'...')` inside a parametrized test will only show case 1's branch. Workarounds: split into separate `@scenario` tests, or parametrize by a column whose value *is* the variant (e.g., `parametrize('case_label', ['small', 'big'])` and `t'{case_label}: ...'`).

### `attach(label, content)`

Attach data to the current step. Strings are stored verbatim; other types are JSON-serialized.

```python
attach('Receipt', 'Coffee x1     $2.00')             # text
attach('Machine state', {'coffees': 9, 'price': 2})  # JSON
```

## pytest options

The JSON report is **always written** whenever the plugin is loaded — every `pytest` run produces it at the path given by `--given-json` (the default is created if missing). The HTML report is opt-in via `--given-html`.

| Flag | Default | Description |
|------|---------|-------------|
| `--given-json=PATH` | `given-report/report-data.json` | JSON output path (always written) |
| `--given-html` | off | Also generate the HTML report |
| `--given-html-output=PATH` | `given-report/report.html` | HTML output path (used only with `--given-html`) |

## Standalone CLI

Regenerate the HTML from a saved JSON file at any time:

```bash
pytest-given report path/to/report-data.json -o path/to/report.html
```

## Examples

See [`examples/test_examples.py`](examples/test_examples.py) for a tour of every supported feature:

- Basic `when`/`then` blocks
- Generator fixtures with teardown
- Plain text and JSON attachments
- Parameterized tests rendered as parameter tables
- Helper functions that record their own steps
- Top-level `given` blocks and deeply nested steps
- Failure rendering
- Skipped scenarios with reason (including all-skipped parametrizes)

A pre-rendered report is committed under [`examples/`](examples/): the JSON ([`report-data.json`](examples/report-data.json)) and the rendered HTML ([`report.html`](examples/report.html) — [live preview](https://raw.githack.com/nwilbert/pytest-given/main/examples/report.html)). Run `nox -s examples` to regenerate both.

## Working with LLMs

pytest-given may be a good fit for AI-assisted workflows. A human can describe a scenario in plain prose — more flexible than a rigid Gherkin DSL — and an LLM can generate the full test: scaffolding, steps, and assertions. The explicit `with given(...)` / `with when(...)` / `with then(...)` blocks then act as a verifiable backbone: each step records *what* the implementation claims to do, making it easier for a human or another model to audit whether the generated code actually matches that intent.

As more implementation is generated rather than hand-written, the human's attention can shift away from line-by-line code review toward a domain-level view of behavior — which is exactly the artifact pytest-given produces. The HTML report reads as a behavior specification, useful for confirming that the generated code does what was asked.

## Development

See [AGENTS.md](AGENTS.md) for setup, quality gates, and conventions.

## License

MIT
