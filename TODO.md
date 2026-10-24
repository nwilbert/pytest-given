# TODO

## Now

## Next

- [ ] pytest-xdist support for reports and lint under `-n --dist loadfile` / `loadscope`, which keep a test function's cases on one worker (other `--dist` modes stay refused). Each worker groups its own scenarios, since `ParamSpec.values` are live Python objects, and ships them (with `Step.source`, which serde excludes), its stories and glossary to the controller via `workeroutput`. The controller merges them in collection order, then lints and writes the sinks.
- [ ] Support the glossary format of https://github.com/mattpocock/skills

## Later

- [ ] continue work on the story-diagrams branch
- [ ] Enable term descriptions referencing other terms (in MD glossaries maybe via *italics*; resolve any conflict with the inline Markdown definitions already render, where `*italic*` is plain italics)
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] enable free text stories / sentences with glossary term references
- [ ] Glossary: Optionally hide kind? Group / filter by story?
- [ ] Special handling for work objects appearing multiple times in Domain Storytelling?
- [ ] Enable a module & package level default story (for auto matching / unpinned scenarios)
- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] migrate JS to TS and add unittests
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] Support `attach` with images
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios (or just give a skill recipe)
- [ ] Default JSON report for the citations CLI: `citations check` / `update` require `--report`. Default it to the path a bare `--given-json` writes, read from a new `[tool.pytest]` setting (also the plugin's default, hard-coded today as `given-report/report-data.json`), so no CLI call repeats it. The CLI reads no `pyproject.toml` yet. Maybe the same for `--given-html` and `--report-path`.
- [ ] Maybe: a grouped scenario's citation summarizes its cases, as in `(3 ✅ · 1 ❌)`, while tag and story summaries keep counting scenarios like the report does. Held back because adding a case would make every citation of the scenario stale, the two summaries would count different things, and a narrated citation's parameter table already shows per-case status.