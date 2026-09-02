# TODO

## Now

- [ ] continue work on the story-diagrams branch

## Next

- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] check support for https://library-skills.io/
- [ ] Enable optional custom IDs for activities (`str` instead of the current `int` numbers)
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios
- [ ] Glossary: Optionally hide kind? Group / filter by story?
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] How to handle work objects appearing multiple times in Domain Storytelling?

## Later

- [ ] `pytest-given audit` command: serialize the already-captured `Step.source` anchors and emit (step text, body source) pairs as a machine-readable feed for the reviewing skill's semantic audit (see the [lint spec](docs/specs/2026-07-05-narration-lint-design.md) non-goals and the [agent-skills spec](docs/specs/2026-07-11-agent-skills-design.md) phase 3). Validation showed hand-anchoring via `source.relpath:line` works fine on small suites — the command earns its keep when a large suite is fanned out to per-file reviewers.
- [ ] define a UI component library?
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Create a proper documentation page, maybe using https://posit-dev.github.io/great-docs
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] support `attach` with images, use this for the self-report
