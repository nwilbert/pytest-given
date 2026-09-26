# Scenarios & steps

A narrated test uses two things: the `@scenario` decorator, which puts the test in the report, and the steps `given`, `when` and `then`, which describe what it does.

## `@scenario`

`@scenario(name, tags=None, *, stories=None, pins=None, group_parametrized=True)`

Only tests with `@scenario` appear in the report. The decorator returns your function unchanged.

- `stories=` takes one story or a list of stories, and `pins=` one sentence handle or a list. Both link the scenario to domain stories; see [Domain Storytelling](domain-storytelling.md).
- `group_parametrized=False` turns off grouping for a parametrized test; see [Parametrized scenarios](parametrized.md#declining-the-merge).

`tags=` takes any strings. Use `/` to nest tags in the report's Tags sidebar: `ticket/ABC-123` appears under a `ticket` heading, and selecting the heading shows all tags below it. Tags only affect the report; they are not pytest marks.

## `given` / `when` / `then`

`given(text, *, pins=None)`, `when(text, *, pins=None)`, `then(text, *, pins=None)`

You can use a step in four places: as a **context manager** in a test body, as a **decorator** on a fixture or a helper function, or as an **`Annotated` label** on a test parameter.

`pins=` links the step to specific story sentences; see [Pins](domain-storytelling.md#pins).

### In a test body

Each `with` block narrates the code inside it:

```python
with given('an empty cart'):
    cart = []
with when('I add an item'):
    cart.append('coffee')
with then('the cart has one item'):
    assert len(cart) == 1
```

### Choosing the phase

Choose the phase by what the code does:

- `given` sets things up. This includes setup calls that change state, like `machine.insert(200)` or seeding a database.
- `when` performs the one action under test.
- `then` only checks the outcome.

The [narration lint](../configuration/narration-lint.md) catches common mistakes, like setup hidden in a second `when`, or an action done inside a `then`'s assertion.

### Steps outside a scenario

A step in a test without `@scenario` does nothing, except emit a `pytest_given.PytestGivenWarning`. If you share a helper between narrated and plain tests, you can silence the warning with `filterwarnings = ["ignore::pytest_given.PytestGivenWarning"]`.

### On fixtures

Fixtures are setup, so **only `@given` is allowed** on a fixture. `@when` or `@then` on a fixture raises an error when the fixture runs:

```python
@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}
```

Generator fixtures work too, but only the part before `yield` is narrated. The teardown after `yield` isn't recorded, and a step or `attach` there raises `PytestGivenError`.

A fixture's label must be a plain string; `@given(Template(...))` on a fixture raises an error. If the label needs to change, move the step into a helper function.

### On test parameters

With `Annotated`, you can add a `given` step to a test parameter: a fixture or a `@pytest.mark.parametrize` value. Use it to:

- show a parametrized value as a `given` step (otherwise it only appears in the parameter table)
- label a fixture that has no `@given`, including pytest's built-in fixtures
- replace a fixture's `@given` label in one scenario

Only `given` is allowed here:

```python
from typing import Annotated

@scenario('Underpayment is rejected')
@pytest.mark.parametrize('cents', [0, 50, 199])
def test_rejects_underpayment(
    machine, cents: Annotated[int, given(Template('{cents} cents inserted'))]
):
    with (
        when_then('a customer tries to buy a coffee',
                  'the machine reports the shortfall'),
        pytest.raises(ValueError, match='insufficient'),
    ):
        buy_coffee(machine, cents)
```

The report shows a `Template` placeholder as `{cents}` in the grouped scenario, and the actual value in each row of the parameter table. `when` and `then` raise an error here, because the action and its check belong in the test body.

The label takes `pins=` like any step. On a fixture with its own `@given(..., pins=...)`, the label's pins replace the fixture's pins; `pins=[]` removes them. Pins of steps inside the fixture body stay as they are.

### On helper functions

`given`, `when` and `then` can all decorate a helper function. The helper then records a step each time it's called. To put argument values into the step text, use `pytest_given.Template` with the helper's parameter names:

```python
@when('inserting money')
def insert(amount):
    ...

@when(Template('I insert ${amount}'))
def insert(amount):
    ...
```

This works the same for `async def` helpers and async generator fixtures.

### Nesting steps

You can nest steps **of the same phase**, for example to split one action into named sub-actions:

```python
with when('I place a large order'):
    with when('I select 3 coffees'):
        order_count = 3
    with when('I apply loyalty discount'):
        ...
```

Nesting a different phase raises `PytestGivenError`, for example a `then` inside a `when`. This includes decorated helpers: calling a `@when` helper inside a `given` block raises too. So if you call a helper from more than one phase, don't decorate it; narrate it where you call it instead.

## `when_then`

`when_then(when_text, then_text)`

Sometimes one call is both the action and the thing you check, most often when you expect an exception. Combine `when_then` with `pytest.raises` to narrate the action and its outcome in one `with`:

```python
from pytest_given import when_then

@scenario('Sold out is rejected')
def test_sold_out(machine):
    with given('a machine that has sold its last coffee'):
        machine['coffees'] = 0
    with (
        when_then('a customer tries to buy a coffee',
                  'the machine reports it is sold out'),
        pytest.raises(ValueError, match='sold out'),
    ):
        buy_coffee(machine)
```

The body runs as the `when` step. The `then` step is recorded after the body finishes without an error (here: after `pytest.raises` catches the exception). If an exception escapes the body, only the `when` is recorded, and the exception propagates as usual.

