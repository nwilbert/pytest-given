# pytest-given

A pytest plugin that generates interactive HTML reports from Given/When/Then annotated tests. Inspired by [JGiven](https://jgiven.org/) (Java). The code is the single source of truth — no separate Gherkin DSL.

**Documentation: <https://nwilbert.github.io/pytest-given/dev/>**

Live examples:
- **[Coffeeshop report →](https://nwilbert.github.io/pytest-given/dev/examples/coffeeshop.html)** — tour of the core features, including `Annotated` `given` labels.
- **[Hotel-booking report →](https://nwilbert.github.io/pytest-given/dev/examples/hotel-booking.html)** — Domain Storytelling: ubiquitous-language glossary, Domain Stories, and coverage.
- **[File-glossary report →](https://nwilbert.github.io/pytest-given/dev/examples/file-glossary-booking.html)** — Domain Storytelling with a Markdown `FileGlossary` and kinds inferred from story activities.
- **[Self-report →](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html)** — pytest-given run against its own test suite (dogfooding).

## Quick start

```bash
pip install pytest-given
```

Requires **Python ≥ 3.14** (t-strings — [PEP 750](https://peps.python.org/pep-0750/) — are part of the step-text API) and **pytest ≥ 9.0**.

If AI agents work in your repo, also install the bundled [agent skills](https://nwilbert.github.io/pytest-given/dev/ai-agents/#agent-skills) — with pytest-given's own command, or with [library-skills](https://library-skills.io) alongside the skills of your other dependencies:

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
@given('a coffee machine')
def machine():
    return {'coffees': 10, 'price': 2}


@scenario('Buy coffee', tags=['billing'])
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

This produces `given-report/report.html` — one file you can open directly in a browser.

## Why pytest-given?

Classical BDD tools (Cucumber, behave, pytest-bdd) center on a natural-language DSL like Gherkin, designed so stakeholders can author tests themselves and engineers maintain the glue that binds each step to a Python function.

pytest-given is for the opposite case: **engineers write normal tests, and the plugin turns them into readable documentation**. Stakeholders, domain experts, and engineers on adjacent teams can open the HTML report and follow it without touching the test suite; for the engineers writing the tests, the same narrative gives a domain-focused view of behavior that's easier to scan than raw test code — browsable by tag, glossary term, or module, with text search and status filters.

- Plain Python — no Gherkin, no `.feature` files, no parser.
- Tests stay first-class pytest tests; the report is a by-product.
- Self-contained HTML: open it locally or attach it to CI artifacts; no server, no external assets.

Increasingly those tests aren't hand-written at all: a human describes a scenario in prose and an AI agent generates the test alongside the code it exercises, so the narrated report — not the raw test code — becomes the artifact humans review. The diagram below sketches that loop between people, agents, and artifacts; [Working with AI agents](https://nwilbert.github.io/pytest-given/dev/ai-agents/) covers how to drive it.

<p align="center">
  <img src="https://raw.githubusercontent.com/nwilbert/pytest-given/main/docs/pytest-given-diagram.png" alt="A loop between people, agents, and artifacts: developers and domain experts instruct AI agents, which write annotated tests and code. The tests verify the code and generate a report that domain experts validate and developers review, feeding back to the agents." width="640">
</p>

## Features

- **Step context managers** — `with given(...)`, `when(...)`, `then(...)` blocks in plain pytest tests, nesting within a phase. [Scenarios & steps →](https://nwilbert.github.io/pytest-given/dev/guide/scenarios/)
- **Narrated fixtures** — `@given` on a fixture, or `Annotated[..., given(...)]` on a parameter, records setup as a step. [Scenarios & steps →](https://nwilbert.github.io/pytest-given/dev/guide/scenarios/)
- **Parametrized scenarios** — one narrated tree plus a parameter table per case, or one scenario per case on request. [Parametrized scenarios →](https://nwilbert.github.io/pytest-given/dev/guide/parametrized/)
- **Domain Storytelling** — a glossary of ubiquitous-language terms, Domain Stories as activity sequences, and per-activity coverage in the report. [Domain Storytelling →](https://nwilbert.github.io/pytest-given/dev/guide/domain-storytelling/)
- **Narration lint** — structural checks that a step's text is honest about its body: empty steps, a `then` that checks nothing, a missing phase. [Narration lint →](https://nwilbert.github.io/pytest-given/dev/configuration/narration-lint/)
- **Agent skills** — bundled Agent Skills for authoring, navigating and reviewing narrated tests, installable with one command. [Working with AI agents →](https://nwilbert.github.io/pytest-given/dev/ai-agents/)

The full reference — pytest options, source links, the standalone CLI — is on the [documentation site](https://nwilbert.github.io/pytest-given/dev/).

## License

MIT
