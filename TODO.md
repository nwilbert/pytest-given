# TODO

## Now

- [ ] Replace "Other" in glossary with something better
- [ ] When a parameter row is hovered on, show the row values instead of the placeholders
- [ ] integrate SVG diagram
- [ ] Example PDF attachment in report
- [ ] cache `format_source_link` template parse/validation in the renderer: it re-runs `string.Formatter().parse(template)` + field-name validation once per scenario, story, and term. Validate once per render, reuse the parsed template across all calls.

## Next

- [ ] add a diagram to the readme with Agent <-> Dev <-> Domain Expert
- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] add a graphical view for stories (e.g., with https://js.cytoscape.org/)
- [ ] Add option to not generate the JSON file on test run, rethink default behavior
- [ ] use >> for activity paths?

## Later

- [ ] define a UI component library?
- [ ] `GLOSSARY.md` export from a code-defined glossary (reverse direction of `FileGlossary`), plus sectioned/heading-scoped glossaries — one table per section on input, grouped sections in the HTML Glossary view. Both features pair naturally and were deferred from the file-backed glossary spec (see `docs/superpowers/specs/2026-06-18-file-backed-glossary-design.md` forward notes).
- [ ] Create a proper documentation page, maybe using https://posit-dev.github.io/great-docs
- [ ] Implement Annotated fixture/parametrize labels (`docs/superpowers/specs/proposed/2026-05-23-annotated-fixture-labels-design.md`)
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/superpowers/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] Provide an agent skill for work with pytest-given, and document how LLM agents can benefit from pytest-given
- [ ] Add `@scenario(group_parametrized=False)` option to opt out of parametrize merging 
  - emit each case as its own scenario (named per case via Template substitution, or by appending the parametrize id to a `str` name).
  - Needed when narration structure genuinely varies per case; today's behavior silently shows case 1's structure for all rows. See caveat in `docs/superpowers/specs/2026-05-23-structured-step-text-design.md`.
  - This is also where per-case substitution of `Template` scenario names and t-string step text (`step_text(case=...)` / `Template.substitute(...)`) becomes load-bearing. Today the substitution machinery is wired but unreachable — the merged view only shows `{name}` tokens, so `Template` for scenario names mostly just Questioncontributes the placeholder highlight in the merged title.
- [ ] Use annotations in prod code to connect to glossary? Probably not worth it. 