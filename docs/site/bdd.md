# Behavior-driven development

Behavior-driven development (BDD) tools such as [Cucumber](https://cucumber.io/), [behave](https://behave.readthedocs.io/) and [pytest-bdd](https://pytest-bdd.readthedocs.io/) describe behavior in [Gherkin](https://cucumber.io/docs/gherkin/), a plain-language format of `Given`, `When` and `Then` lines kept in `.feature` files. This page writes the [quick start](getting-started.md)'s coffee scenario for pytest-bdd and compares the two approaches, how they group scenarios, and their reports.

pytest-bdd starts from a Gherkin `.feature` file, [`coffee.feature`](https://github.com/nwilbert/pytest-given/blob/main/examples/pytest-bdd/coffee.feature):

```gherkin
--8<-- "examples/pytest-bdd/coffee.feature"
```

Python step definitions, in [`test_coffee.py`](https://github.com/nwilbert/pytest-given/blob/main/examples/pytest-bdd/test_coffee.py), bind each line to code by matching its text:

```python
--8<-- "examples/pytest-bdd/test_coffee.py"
```

The same scenario in pytest-given, as the quick start writes it, is one test:

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

## Above the scenarios: rules and stories

Both approaches can group scenarios under something larger, but they group them by different ideas.

Gherkin's `Rule` keyword sits between a feature and its scenarios. It comes from [Example Mapping](https://cucumber.io/docs/bdd/example-mapping), a short conversation held before a user story is built. The team writes the user story on a yellow card, the rules it must follow on blue cards, concrete examples of each rule on green cards, and open questions on red ones. Each rule then becomes a `Rule:`, and each example a scenario under it:

```gherkin
Feature: Coffee machine

  Rule: A coffee can only be bought while the machine has stock

    Scenario: Buying a coffee takes one from the machine
      ...

    Scenario: An empty machine refuses the sale
      ...
```

pytest-given has no rules. [Domain Storytelling](guide/domain-storytelling.md) plays a similar part above the scenarios. A domain story is a numbered list of sentences, who does what with what, written in code from glossary terms. A scenario links to stories with `stories=`, and the report shows which scenarios cover each sentence.

- **What it captures.** A rule is a constraint the behavior must respect, and its scenarios are examples of it. A domain story is a flow through the domain, and each of its scenarios details one part of that flow.
- **How a scenario joins.** A Gherkin scenario belongs to the rule it stands under in the feature file, so it has at most one. A pytest-given scenario can join several stories. The sentences it covers are matched from its steps' term refs, or stated with pins.
- **What it spans.** Example Mapping works on one user story at a time, a unit of planned work. A domain story describes how the domain works, across as many features as the flow touches.

## Running it

In the pytest-given repository, `uv run nox -s bdd_example` runs the [pytest-bdd example](https://github.com/nwilbert/pytest-given/tree/main/examples/pytest-bdd). In that run:

1. When pytest imports `test_coffee.py`, `scenarios('coffee.feature')` reads the feature file and generates one test per scenario, here `test_buying_a_coffee_takes_one_from_the_machine`.
2. That test walks the scenario's lines in order and looks up a step definition for each by its text. `a coffee machine with 10 coffees` matches the `@given` pattern, which parses `10` into the `coffees` argument. Through `target_fixture`, the step's return value becomes the `machine` fixture.
3. The `@when` and `@then` steps take `machine` like any fixture, and the `then` step's `assert` decides the outcome. A line that matches no step definition fails the test with `StepDefinitionNotFoundError`.
4. The `@checkout` tag becomes a pytest mark, so `-m checkout` selects the scenario. The example's [`conftest.py`](https://github.com/nwilbert/pytest-given/blob/main/examples/pytest-bdd/conftest.py) registers that mark, since pytest warns about an unregistered one.

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

pytest-bdd renders no HTML itself. It writes Cucumber JSON (`--cucumberjson`), a format Cucumber itself now calls legacy in favor of [Cucumber Messages](https://github.com/cucumber/messages), and third-party tools turn that into a report. The best known is [cucumber-reporting](https://github.com/damianszczepanik/cucumber-reporting), which also backs Jenkins' Cucumber Reports plugin. Its [live demo](https://damianszczepanik.github.io/cucumber-html-reports/overview-features.html) shows a typical report. pytest-given, by contrast, renders its HTML report itself, with no extra tool. The [Coffeeshop report](examples/coffeeshop.html#scenario=examples/coffeeshop/test_coffeeshop.py::test_buy_coffee) shows this same scenario.

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

behave renders no HTML itself either. For an HTML report, it needs one of these third-party formatters:

| Formatter | What it writes | Example |
|---|---|---|
| [behave-html-pretty-formatter](https://github.com/behave-contrib/behave-html-pretty-formatter) | One HTML file listing the features, scenarios and steps | [Example report](https://behave-contrib.github.io/behave-html-pretty-formatter/) |
| [behave-modern-html-report](https://github.com/MathiasPaulenko/behave-modern-html-report) | One HTML file with dashboard views by feature, tag and statistic | [Demo report](https://raw.githack.com/MathiasPaulenko/behave-modern-html-report/main/examples/behave_project/reports/demo.html) |
| [allure-behave](https://pypi.org/project/allure-behave/) | Results for [Allure](https://allurereport.org/), a report tool that serves many test frameworks | — |
