# Getting started

```bash
pip install pytest-given
```

Requires **Python ≥ 3.14** (t-strings — [PEP 750](https://peps.python.org/pep-0750/) — are part of the step-text API) and **pytest ≥ 9.0**.

If AI agents work in your repo, also install the bundled [agent skills](ai-agents.md#agent-skills) — with pytest-given's own command, or with [library-skills](https://library-skills.io) alongside the skills of your other dependencies:

```bash
pytest-given skills install
# or
uvx library-skills install --claude
```

Then narrate a test:

```python
import pytest
from pytest_given import attach, given, scenario, then, when


@pytest.fixture
@given('a coffee machine with 10 coffees')
def machine():
    return {'coffees': 10, 'price': 2}


@scenario('Buying a coffee takes one from the machine', tags=['checkout'])
def test_buy_coffee(machine):
    with when('I buy a coffee'):
        machine['coffees'] -= 1
    with then('the machine has 9 coffees left'):
        assert machine['coffees'] == 9
        attach('Machine state', machine)
```

Run it:

```bash
pytest --given-html
```

This produces `given-report/report.html` — one file you can open directly in a browser.

The Coffeeshop example's report shows this same scenario:

✅ [Buying a coffee takes one from the machine](examples/coffeeshop.html#scenario=examples/coffeeshop/test_coffeeshop.py::test_buy_coffee)

To write the report without running your plain tests, see [Selecting scenarios](configuration/pytest-options.md#selecting-scenarios).

Next: [Scenarios & steps](guide/scenarios.md) for the full API, or the [Coffeeshop report](examples/coffeeshop.html) to see what a finished report looks like.
