# TODO

## Now

- [ ] continue work on the story-diagrams branch

## Next

- [ ] Markdown rendering for review: opt-in `--given-md-source` inlining each scenario's body, plus a Stories section from the production coverage rollups — retires the two scripts the reviewing skill ships (see `docs/specs/proposed/2026-09-04-markdown-review-rendering-design.md`)
- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] check support for https://library-skills.io/
- [ ] Enable optional custom IDs for activities (`str` instead of the current `int` numbers)
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios
- [ ] Glossary: Optionally hide kind? Group / filter by story?
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] How to handle work objects appearing multiple times in Domain Storytelling?

## Later

- [ ] define a UI component library?
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Create a proper documentation page, maybe using https://posit-dev.github.io/great-docs
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] support `attach` with images, use this for the self-report
