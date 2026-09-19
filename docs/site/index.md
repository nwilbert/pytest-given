---
title: Home
---

<div class="pg-hero" markdown>

<div class="pg-hero-title" markdown>
<svg class="pg-hero-logo" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h3"/><path d="M11 6h5"/><path d="M4 12h3"/><path d="M11 12h9"/><path d="M3.5 18.5l2 2 4-4.5"/><path d="M13 18h7"/></svg>

# pytest-given

</div>

<p class="pg-hero-gwt">
<span><b>Given</b> your pytest tests,</span>
<span><b>when</b> you narrate them with <code>given</code> / <code>when</code> / <code>then</code> (no Gherkin, no separate DSL),</span>
<span><b>then</b> documentation and behavior fuse into one report.</span>
</p>

<p class="pg-hero-punch">What people and agents read is what the code does.</p>

[Getting started](getting-started.md){ .md-button .md-button--primary }
[See a report](examples/coffeeshop.html){ .md-button target=_blank }

</div>

Live examples:

- **[Coffeeshop report](examples/coffeeshop.html){ target=_blank }**: tour of the core features, including `Annotated` `given` labels.
- **[Hotel-booking report](examples/hotel-booking.html){ target=_blank }**: Domain Storytelling: ubiquitous-language glossary, Domain Stories, and coverage.
- **[File-glossary report](examples/file-glossary-booking.html){ target=_blank }**: Domain Storytelling with a Markdown `FileGlossary` and kinds inferred from story activities.
- **[Self-report](examples/self-report.html){ target=_blank }**: pytest-given run against its own test suite (dogfooding).

## Why pytest-given?

Classical BDD tools (Cucumber, behave, pytest-bdd) center on a natural-language DSL like Gherkin, designed so stakeholders can author tests themselves and engineers maintain the glue that binds each step to a Python function.

pytest-given is for the opposite case: **engineers or their agents write normal tests, and the plugin turns them into readable documentation**. Stakeholders, domain experts, and engineers on adjacent teams can open the HTML report and follow it without touching the test suite; for the engineers writing the tests, the same narrative gives a domain-focused view of behavior that's easier to scan than raw test code — browsable by tag, glossary term, or module, with text search and status filters. The approach is the one [JGiven](https://jgiven.org/) pioneered for Java, brought to pytest.

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
