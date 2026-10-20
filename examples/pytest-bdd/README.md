# The README scenario in pytest-bdd

The quick start's coffee scenario, written for [pytest-bdd](https://pytest-bdd.readthedocs.io/) to contrast the two approaches. It is not a pytest-given example: this folder narrates nothing and has no report.

pytest-bdd starts from a Gherkin `.feature` file, [`coffee.feature`](coffee.feature):

```gherkin
Feature: Coffee machine

  @checkout
  Scenario: Buying a coffee takes one from the machine
    Given a coffee machine with 10 coffees
    When I buy a coffee
    Then the machine has 9 coffees left
```

Python step definitions, in [`test_coffee.py`](test_coffee.py), bind each line to code by matching its text:

```python
from pytest_bdd import given, parsers, scenarios, then, when

scenarios('coffee.feature')


@given(
    parsers.parse('a coffee machine with {coffees:d} coffees'),
    target_fixture='machine',
)
def machine(coffees):
    return {'coffees': coffees, 'price': 2}


@when('I buy a coffee')
def buy_coffee(machine):
    machine['coffees'] -= 1


@then(parsers.parse('the machine has {coffees:d} coffees left'))
def coffees_left(machine, coffees):
    assert machine['coffees'] == coffees
```

The same scenario in pytest-given, as the [README](../../README.md#quick-start) writes it, is one test:

```python
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

## What differs

- **Where the text lives.** In pytest-bdd, the feature file is the source and the Python is glue behind it. In pytest-given, the test is the source and the narration sits on the code it describes.
- **What the text does.** A pytest-bdd step's text is a pattern that has to match a step definition, so rewording a line in the feature file means changing its pattern too. A pytest-given step's text is a label on a block, so rewording it breaks nothing.
- **How values flow.** pytest-bdd parses `10` and `9` out of the text and hands them to the step functions, and `target_fixture` turns a step's return value into a fixture. In pytest-given the values are plain Python, and a t-string puts one into the step text when the narration should show it.
- **How the test reads.** A pytest-bdd scenario's code is spread over step functions that any feature file may reuse. A pytest-given test reads top-down as one pytest function, with fixtures, parametrize and the debugger working as usual.
- **Who reads it, and when.** A feature file can be written and agreed on before any code exists, which suits stakeholders who write the specification. pytest-given's readable form is the report, which comes out of a test run and shows each step's outcome and attachments.

## Running it

`uv run nox -s bdd_example` runs it. In that run:

1. When pytest imports `test_coffee.py`, `scenarios('coffee.feature')` reads the feature file and generates one test per scenario, here `test_buying_a_coffee_takes_one_from_the_machine`.
2. That test walks the scenario's lines in order and looks up a step definition for each by its text. `a coffee machine with 10 coffees` matches the `@given` pattern, which parses `10` into the `coffees` argument. Through `target_fixture`, the step's return value becomes the `machine` fixture.
3. The `@when` and `@then` steps take `machine` like any fixture, and the `then` step's `assert` decides the outcome. A line that matches no step definition fails the test with `StepDefinitionNotFoundError`.
4. The `@checkout` tag becomes a pytest mark, so `-m checkout` selects the scenario. `conftest.py` registers that mark, since pytest warns about an unregistered one.

The session passes `--gherkin-terminal-reporter`, so the output replays the scenario's lines:

```text
Feature: Coffee machine
    Scenario: Buying a coffee takes one from the machine
        Given a coffee machine with 10 coffees
        When I buy a coffee
        Then the machine has 9 coffees left
    PASSED
```

## The reports

pytest-bdd renders no HTML itself. It writes a Cucumber JSON file (`--cucumberjson`), and third-party tools turn that into a report. The best known is [cucumber-reporting](https://github.com/damianszczepanik/cucumber-reporting), which also backs Jenkins' Cucumber Reports plugin. Its [live demo](https://damianszczepanik.github.io/cucumber-html-reports/overview-features.html) shows a typical report. pytest-given renders its own report, and the [Coffeeshop report](https://nwilbert.github.io/pytest-given/latest/examples/coffeeshop.html#scenario=examples/coffeeshop/test_coffeeshop.py::test_buy_coffee) opens on this same scenario.

- **What the report is for.** A Cucumber report is a dashboard over the feature files. Its tables and charts count steps and scenarios by status, per feature and per tag, with trends across builds. pytest-given's report is for reading the scenarios themselves, browsable by tag, glossary term or module.
- **What a step shows.** A Cucumber report shows each step's keyword, text and duration, plus its attachments. A pytest-given step shows its narration, with term refs and interpolated values, its nested steps, and its attachments.
- **What it connects to.** A Cucumber report stays within the feature files. pytest-given links each scenario to its source code, and its glossary and domain stories tie the scenarios to the domain.
- **What gets written.** cucumber-reporting writes a folder of pages. pytest-given writes one self-contained HTML file.

## The same feature file in behave

[behave](https://github.com/behave/behave), the other Gherkin tool for Python, would run `coffee.feature` unchanged. Its step definitions match text the same way, but they pass state through a shared `context` object instead of fixtures:

```python
from behave import given


@given('a coffee machine with {coffees:d} coffees')
def machine(context, coffees):
    context.machine = {'coffees': coffees, 'price': 2}
```

behave is its own runner rather than a pytest plugin, so its scenarios run apart from pytest's tests, fixtures and plugins. Everything under [What differs](#what-differs) applies to it as well.

behave renders no HTML itself either. Third-party formatters add it:

| Formatter | What it writes | Example |
|---|---|---|
| [behave-html-pretty-formatter](https://github.com/behave-contrib/behave-html-pretty-formatter) | One HTML file listing the features, scenarios and steps | [Example report](https://behave-contrib.github.io/behave-html-pretty-formatter/) |
| [behave-modern-html-report](https://github.com/MathiasPaulenko/behave-modern-html-report) | One HTML file with dashboard views by feature, tag and statistic | [Demo report](https://raw.githack.com/MathiasPaulenko/behave-modern-html-report/main/examples/behave_project/reports/demo.html) |
| [allure-behave](https://pypi.org/project/allure-behave/) | Results for [Allure](https://allurereport.org/), a report tool that serves many test frameworks | — |
