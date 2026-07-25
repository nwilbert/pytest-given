# TODO

## Now

- [ ] add skill to support Domain Storytelling session (update & regenerate diagram continously, update glossary)

## Next

- [ ] update README with section on glossary
- [ ] Enable optional custom IDs for activities (`str` instead of the current `int` numbers)
- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios
- [ ] Glossary: Optionally hide kind? Group / filter by story?
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] How to handle work objects appearing multiple times in Domain Storrytelling?
- [ ] Narrate more backend tests into scenarios — continue the dogfood conversion, converting behaviour, not plumbing (leave schema/serde round-trips, metadata/protocol checks, and config parsing plain). In priority order:
  - lint rule tests (`tests/unit/lint/test_runtime_rules.py`, `test_ast_rules.py`, ~65) — each asserts a user-facing rule ("missing-phase fires on a two-phase scenario"); the report would document the lint's semantics
  - source-link preset resolution (`tests/unit/report/test_source_link.py`) — the preset rules earn narration; the URL-template internals stay plain
  - integration-test spike (`tests/integration/`, 124 plain): the plugin's outermost behaviour — "when the suite runs with `--given-json` then the report shows …". Technically feasible (`test_plugin_session_isolation.py` proves narrated outer scenarios survive nested pytester runs) but needs its own spike for nested-session edge cases around open step stacks. Would retire the `Plain fixture` dead term (the last one).

## Later

- [ ] `pytest-given audit` command: serialize the already-captured `Step.source` anchors and emit (step text, body source) pairs as a machine-readable feed for the reviewing skill's semantic audit (see the [lint spec](docs/specs/2026-07-05-narration-lint-design.md) non-goals and the [agent-skills spec](docs/specs/2026-07-11-agent-skills-design.md) phase 3). Validation showed hand-anchoring via `source.relpath:line` works fine on small suites — the command earns its keep when a large suite is fanned out to per-file reviewers.
- [ ] define a UI component library?
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Create a proper documentation page, maybe using https://posit-dev.github.io/great-docs
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] Add `@scenario(group_parametrized=False)` option to opt out of parametrize merging 
  - emit each case as its own scenario (named per case via Template substitution, or by appending the parametrize id to a `str` name).
  - Needed when narration structure genuinely varies per case; today's behavior silently shows case 1's structure for all rows. See caveat in `docs/specs/2026-05-23-structured-step-text-design.md`.
  - This is also where per-case substitution of `Template` scenario names and t-string step text (`step_text(case=...)` / `Template.substitute(...)`) becomes load-bearing. Today the substitution machinery is wired but unreachable — the merged view only shows `{name}` tokens, so `Template` for scenario names mostly just Questioncontributes the placeholder highlight in the merged title.
