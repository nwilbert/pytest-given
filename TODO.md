# TODO

## Now

- [ ] Link report to source code — see `docs/superpowers/specs/proposed/2026-05-30-source-link-design.md`

## Next

- [ ] Add option to not generate the JSON file, rethink default behavior

## Later

- [ ] Revisit Annotated fixture/parametrize labels spec — deferred pending structured step text (see `docs/superpowers/specs/proposed/2026-05-23-annotated-fixture-labels-design.md`)
- [ ] UI improvements in report
  - highlight on hover for parametrization table)
  - search box improvements 
- [ ] Think about UL support (e.g., by connecting the report to a glossary)
- [ ] Provide an agent skill for work with pytest-given
- [ ] Add `@scenario(group_parametrized=False)` option to opt out of parametrize merging 
  - emit each case as its own scenario (named per case via Template substitution, or by appending the parametrize id to a `str` name).
  - Needed when narration structure genuinely varies per case; today's behavior silently shows case 1's structure for all rows. See caveat in `docs/superpowers/specs/2026-05-23-structured-step-text-design.md`.
  - This is also where per-case substitution of `Template` scenario names and t-string step text (`step_text(case=...)` / `Template.substitute(...)`) becomes load-bearing. Today the substitution machinery is wired but unreachable — the merged view only shows `{name}` tokens, so `Template` for scenario names mostly just contributes the placeholder highlight in the merged title.