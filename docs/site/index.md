---
title: Home
---

<div class="pg-hero" markdown>

<div class="pg-hero-title" markdown>
<p class="pg-hero-logo-wrap"><svg class="pg-hero-logo" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h3"/><path d="M11 6h5"/><path d="M4 12h3"/><path d="M11 12h9"/><path d="M3.5 18.5l2 2 4-4.5"/><path d="M13 18h7"/></svg></p>

# pytest-given

</div>

<p class="pg-hero-gwt">
<span><b>Given</b> your pytest tests,</span>
<span><b>when</b> you narrate them with <code>given</code> / <code>when</code> / <code>then</code>,</span>
<span><b>then</b> documentation and behavior fuse into one report.</span>
</p>

<p class="pg-hero-punch">What people and agents read is what the code does.</p>

<p class="pg-hero-actions" markdown>
[Getting started](getting-started.md){ .md-button .md-button--primary }
[See a report](examples/coffeeshop.html){ .md-button target=_blank }
</p>

</div>

## Why pytest-given?

Classical BDD tools (Cucumber, behave, pytest-bdd) center on Gherkin, a natural-language DSL: stakeholders write the tests, and engineers maintain the glue code behind each step.

pytest-given works the other way round: **engineers or their agents write normal tests, and pytest-given turns them into readable documentation.** Stakeholders and domain experts can follow the HTML report without ever opening the test suite. Engineers get a view of the system's behavior that is easier to scan than test code, browsable by tag, glossary term, or module. The approach is the one [JGiven](https://jgiven.org/) pioneered for Java, brought to pytest.

- Plain Python: no Gherkin, no `.feature` files, no parser.
- Tests stay first-class pytest tests, and the report is a by-product.
- Self-contained HTML: open it locally or attach it to a CI run, with no server and no external assets.

### Written by agents, reviewed by people

More and more tests aren't written by hand. A person describes a scenario, an AI agent writes the test along with the code, and people review the narrated report instead of the test code. The diagram shows this loop, and [Working with AI agents](ai-agents.md) explains how to set it up.

<figure class="pg-diagram">
  --8<-- "docs/site/assets/pytest-given-diagram.svg"
  <figcaption><a href="assets/pytest-given-diagram-full.svg">Open at full size</a></figcaption>
</figure>

### Glossary and Domain Storytelling

pytest-given goes beyond JGiven by tying tests to the domain itself. A [glossary](guide/glossary.md) defines the terms your team uses, and the report highlights them wherever a test mentions them. [Domain Storytelling](guide/domain-storytelling.md) adds the big picture: stories of how the domain works, with the report showing which scenarios cover each sentence of a story.

## Example reports

- **[Coffeeshop](examples/coffeeshop.html){ target=_blank }**: a tour of the core features.
- **[Hotel booking](examples/hotel-booking.html){ target=_blank }**: a glossary and domain stories, with story coverage.
- **[File glossary](examples/file-glossary-booking.html){ target=_blank }**: the same, with the glossary kept in a Markdown file.
- **[Self-report](examples/self-report.html){ target=_blank }**: pytest-given's own test suite.

The [Examples](examples.md) page links the test code behind each report.

## Development and license

See [AGENTS.md](https://github.com/nwilbert/pytest-given/blob/main/AGENTS.md) for setup, quality gates, and conventions. pytest-given is [MIT](https://github.com/nwilbert/pytest-given/blob/main/LICENSE.md) licensed. The bundled Alpine.js runtime is also MIT; its notice is in [THIRD-PARTY-LICENSES](https://github.com/nwilbert/pytest-given/blob/main/THIRD-PARTY-LICENSES).
