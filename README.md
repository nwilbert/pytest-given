# pytest-given

A pytest plugin that turns Given/When/Then annotated tests into interactive HTML reports.

**Given** your pytest tests,<br>
**when** you narrate them with `given` / `when` / `then`,<br>
**then** documentation and behavior fuse into one report.

**What people and agents read is what the code does.**

Inspired by [JGiven](https://jgiven.org/) (Java).

**Documentation: <https://nwilbert.github.io/pytest-given/dev/>**

Live examples:
- **[Coffeeshop](https://nwilbert.github.io/pytest-given/dev/examples/coffeeshop.html)**: a tour of the core features.
- **[Hotel booking](https://nwilbert.github.io/pytest-given/dev/examples/hotel-booking.html)**: a glossary and domain stories, with story coverage.
- **[File glossary](https://nwilbert.github.io/pytest-given/dev/examples/file-glossary-booking.html)**: the same, with the glossary kept in a Markdown file.
- **[Self-report](https://nwilbert.github.io/pytest-given/dev/examples/self-report.html)**: pytest-given's own test suite.

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

Classical BDD tools (Cucumber, behave, pytest-bdd) center on Gherkin, a natural-language DSL: stakeholders write the tests, and engineers maintain the glue code behind each step.

pytest-given works the other way round: **engineers or their agents write normal tests, and pytest-given turns them into readable documentation.** Stakeholders and domain experts can follow the HTML report without ever opening the test suite. Engineers get a view of the system's behavior that is easier to scan than test code, browsable by tag, glossary term, or module. The approach is the one [JGiven](https://jgiven.org/) pioneered for Java, brought to pytest.

- Plain Python: no Gherkin, no `.feature` files, no parser.
- Tests stay first-class pytest tests, and the report is a by-product.
- Self-contained HTML: open it locally or attach it to a CI run, with no server and no external assets.

### Written by agents, reviewed by people

More and more tests aren't written by hand. A person describes a scenario, an AI agent writes the test along with the code, and people review the narrated report instead of the test code. The diagram shows this loop, and [Working with AI agents](https://nwilbert.github.io/pytest-given/dev/ai-agents/) explains how to set it up.

<p align="center">
  <img src="https://raw.githubusercontent.com/nwilbert/pytest-given/main/docs/pytest-given-diagram.svg" alt="A loop between people, agents, and artifacts: developers and domain experts instruct AI agents, which write annotated tests and code. The tests verify the code and generate a report that domain experts validate and developers review, feeding back to the agents." width="640">
</p>

### Glossary and Domain Storytelling

pytest-given goes beyond JGiven by tying tests to the domain itself. A [glossary](https://nwilbert.github.io/pytest-given/dev/guide/glossary/) defines the terms your team uses, and the report highlights them wherever a test mentions them. [Domain Storytelling](https://nwilbert.github.io/pytest-given/dev/guide/domain-storytelling/) adds the big picture: stories of how the domain works, with the report showing which scenarios cover each sentence of a story.

## Features

- **[Step context managers](https://nwilbert.github.io/pytest-given/dev/guide/scenarios/)**: `with given(...)`, `when(...)`, `then(...)` blocks in plain pytest tests, nesting within a phase.
- **[Narrated fixtures](https://nwilbert.github.io/pytest-given/dev/guide/scenarios/)**: `@given` on a fixture, or `Annotated[..., given(...)]` on a parameter, records setup as a step.
- **[Parametrized scenarios](https://nwilbert.github.io/pytest-given/dev/guide/parametrized/)**: one narrated tree plus a parameter table per case, or one scenario per case on request.
- **[Glossary](https://nwilbert.github.io/pytest-given/dev/guide/glossary/)**: your domain's terms, declared in code or loaded from a `GLOSSARY.md`, rendered as highlighted term refs in the narration.
- **[Domain Storytelling](https://nwilbert.github.io/pytest-given/dev/guide/domain-storytelling/)**: Domain Stories as sequences of sentences, and per-sentence coverage in the report.
- **[Narration lint](https://nwilbert.github.io/pytest-given/dev/configuration/narration-lint/)**: structural checks that a step's text is honest about its body: empty steps, a `then` that checks nothing, a missing phase.
- **[Agent skills](https://nwilbert.github.io/pytest-given/dev/ai-agents/)**: bundled Agent Skills for authoring, navigating and reviewing narrated tests, installable with one command.

The full reference — pytest options, source links, the standalone CLI — is on the [documentation site](https://nwilbert.github.io/pytest-given/dev/).

## License

[MIT](https://github.com/nwilbert/pytest-given/blob/main/LICENSE.md). The bundled Alpine.js runtime is also MIT; its notice is in [THIRD-PARTY-LICENSES](https://github.com/nwilbert/pytest-given/blob/main/THIRD-PARTY-LICENSES).
