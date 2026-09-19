# pytest-given

A pytest plugin that generates interactive HTML reports from Given/When/Then annotated tests. Inspired by [JGiven](https://jgiven.org/) (Java). The code is the single source of truth — no separate Gherkin DSL.

Live examples:

- **[Coffeeshop report →](examples/coffeeshop.html)** — tour of the core features, including `Annotated` `given` labels.
- **[Hotel-booking report →](examples/hotel-booking.html)** — Domain Storytelling: ubiquitous-language glossary, Domain Stories, and coverage.
- **[File-glossary report →](examples/file-glossary-booking.html)** — Domain Storytelling with a Markdown `FileGlossary` and kinds inferred from story activities.
- **[Self-report →](examples/self-report.html)** — pytest-given run against its own test suite (dogfooding).

New here? Start with [Getting started](getting-started.md).

## Why pytest-given?

Classical BDD tools (Cucumber, behave, pytest-bdd) center on a natural-language DSL like Gherkin, designed so stakeholders can author tests themselves and engineers maintain the glue that binds each step to a Python function.

pytest-given is for the opposite case: **engineers write normal tests, and the plugin turns them into readable documentation**. Stakeholders, domain experts, and engineers on adjacent teams can open the HTML report and follow it without touching the test suite; for the engineers writing the tests, the same narrative gives a domain-focused view of behavior that's easier to scan than raw test code — browsable by tag, glossary term, or module, with text search and status filters.

- Plain Python — no Gherkin, no `.feature` files, no parser.
- Tests stay first-class pytest tests; the report is a by-product.
- Self-contained HTML: open it locally or attach it to CI artifacts; no server, no external assets.

Increasingly those tests aren't hand-written at all: a human describes a scenario in prose and an AI agent generates the test alongside the code it exercises, so the narrated report — not the raw test code — becomes the artifact humans review. The diagram below sketches that loop between people, agents, and artifacts; [Working with AI agents](ai-agents.md) covers how to drive it.

<p align="center">
  <img src="assets/pytest-given-diagram.png" alt="A loop between people, agents, and artifacts: developers and domain experts instruct AI agents, which write annotated tests and code. The tests verify the code and generate a report that domain experts validate and developers review, feeding back to the agents." width="640">
</p>

## Development

See [AGENTS.md](https://github.com/nwilbert/pytest-given/blob/main/AGENTS.md) for setup, quality gates, and conventions.

## License

MIT
