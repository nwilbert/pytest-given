# Scenarios & steps

Everything a narrated test uses: the decorator that puts it in the report, and the step context managers that describe it.

## `@scenario`

`@scenario(name, tags=None, *, story=None, activities=None, group_parametrized=True)`

Required for a test to appear in the report. `story=` / `activities=` bind it to a domain story (see [Domain Storytelling](domain-storytelling.md)) — `activities=` requires `story=` and takes an `int` or a sequence of them, never a string; `group_parametrized=False` declines parametrize merging. The decorated function is returned unwrapped.

## `given` / `when` / `then`

`given(text)`, `when(text)`, `then(text)`

Dual-purpose: use as a **context manager** inside a test body, or as a **decorator** on a fixture or helper function.

As context managers:

```python
with given('an empty cart'):
    cart = []
with when('I add an item'):
    cart.append('coffee')
with then('the cart has one item'):
    assert len(cart) == 1
```

Pick the phase by **role**, not syntax: all arrangement belongs in `given` — including state-mutating setup calls (`machine.insert(200)`, seeding a database) — `when` performs the one action under test, and `then` only observes its outcome. The [narration lint](../configuration/narration-lint.md) catches the usual slips: an arrangement hiding in a second `when`, an action folded into a `then`'s assertion.

A step recorded in a test with no `@scenario` is a no-op that warns with `pytest_given.PytestGivenWarning` — silence it with `filterwarnings = ["ignore::pytest_given.PytestGivenWarning"]` if a shared helper is used from both narrated and plain tests.

As a fixture decorator (**only `@given` is allowed** — fixtures are setup, so `@when`/`@then` on a fixture is rejected at runtime):

```python
@pytest.fixture
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}
```

Generator fixtures work too, but only their setup is narrated: the post-`yield` block runs outside the recording, and a step or `attach` there raises `PytestGivenError`. A fixture's label must be a plain string — `@given(Template(...))` on a fixture raises; move the step into a helper function if the label has to vary.

As a call-site label with `Annotated` (**only `given` is allowed**) — attach a `given` step to a fixture or a `@pytest.mark.parametrize` value from the test signature. This is the way to surface a parametrized input as a `given` (a direct parametrize value otherwise appears only in the parameter table), and it can label an undecorated or built-in fixture, or override a decorated fixture's label for one scenario:

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

A `Template` placeholder renders as `{col}` in the grouped view and as the concrete value per row. `when`/`then` are rejected here — the action and its outcome belong in the test body.

As a helper-function decorator (any phase). The helper records its own step on each call; for dynamic narration, use `pytest_given.Template` and reference the helper's parameters:

```python
@when('inserting money')
def insert(amount):
    ...

@when(Template('I insert ${amount}'))
def insert(amount):
    ...
```

`async def` helpers decorate the same way — the step wraps the awaited body — as do async generator fixtures.

Steps nest **within a phase** — a `when` inside a `when`, to break one action into named sub-actions:

```python
with when('I place a large order'):
    with when('I select 3 coffees'):
        order_count = 3
    with when('I apply loyalty discount'):
        ...
```

Crossing phases is rejected: a `then` opened inside a `when` raises `PytestGivenError`. That covers decorated helpers too — a `@when` helper called from inside a `given` block raises — so a helper used from more than one phase should stay undecorated and be narrated at its call site.

## `when_then`

`when_then(when_text, then_text)`

When a single call is both the action under test and the thing you assert about — most often an expected raise — pair it with `pytest.raises` and let `when_then` narrate both an action and its outcome from one `with`:

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

The body runs inside the `when`; the sibling `then` is emitted once the body exits cleanly (e.g. after the inner `pytest.raises` catches the error). If the body raises uncaught, the `when` is recorded, the `then` is skipped, and the exception propagates.

