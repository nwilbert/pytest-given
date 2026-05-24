# TODO

## Now

- [ ] Work on t-string step-text spec (preferred placeholder mechanism; bumps baseline to 3.14)

## Next

- [ ] Add option to not generate the JSON file, rethink default behavior
- [ ] Create UL md file
- [ ] Link report to source code

## Later

- [ ] Revisit Annotated fixture/parametrize labels spec — deferred pending structured step text (see `docs/superpowers/specs/2026-05-23-structured-step-text-design.md`)
- [ ] UI improvements in report
  - highlight on hover for parametrization table)
  - search box improvements 
- [ ] Think about UL support (e.g., by connecting the report to a glossary)
- [ ] Provide an agent skill for work with pytest-given
- [ ] Add `@scenario(group_parametrized=False)` option to opt out of parametrize merging — emit each case as its own scenario (named per case via Template substitution, or by appending the parametrize id to a `str` name). Needed when narration structure genuinely varies per case; today's behavior silently shows case 1's structure for all rows. See caveat in `docs/superpowers/specs/2026-05-23-structured-step-text-design.md`.
