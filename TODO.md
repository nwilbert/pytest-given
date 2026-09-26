# TODO

## Now

- [ ] Rename to Domain Storytelling vocabulary: sentence, activity, clause ([spec](docs/specs/proposed/2026-09-26-sentences-and-clauses-design.md))
- [ ] Implement pins: named sentences, sentence handles, multi-story scenarios; same release as the rename ([spec](docs/specs/proposed/2026-09-21-pins-design.md))
- [ ] Make the docs sections for https://nwilbert.github.io/pytest-given/dev/guide/domain-storytelling/ more explicit. Check for other pages that are too dense / unstructured.

## Next

- [ ] ability to mark scenarios as not implemented yet (for TDD, should affect linting and show up in the report)
- [ ] Markdown rendering for review: opt-in `--given-md-source` inlining each scenario's body, plus a Stories section from the production coverage rollups — retires the two scripts the reviewing skill ships (see `docs/specs/proposed/2026-09-04-markdown-review-rendering-design.md`)
- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios
- [ ] Glossary: Optionally hide kind? Group / filter by story?
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] How to handle work objects appearing multiple times in Domain Storytelling?
- [ ] Rename `capture.glossary.TermRef` (the abstract base of `TermHandle` / `TermInstance`) to match the glossary: it is handle-side, while a *term ref* is the recorded occurrence (`NarrationTermRef`, `ActivityTermRef`) — e.g. `TermHandleBase`

## Later

- [ ] continue work on the story-diagrams branch
- [ ] define a UI component library?
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] support `attach` with images, use this for the self-report
