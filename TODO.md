# TODO

## Now

- [ ] remove pip exclude-newer workaround
- [ ] add parameterized scenario in hotel example
- [ ] improve / add links in report, between scenarios, terms / glossary, and stories
- [ ] use >> for activity paths?
- [ ] add diagram to readme with Agent <-> Dev <-> Domain Expert

## Next

- [ ] polish the JSON format and possibly turn it into proper API spec using Pydantic
- [ ] add a graphical view for stories
- [ ] Add option to not generate the JSON file on test run, rethink default behavior

## Later

- [ ] Implement Annotated fixture/parametrize labels (`docs/superpowers/specs/proposed/2026-05-23-annotated-fixture-labels-design.md`)
- [ ] Maybe: implement flat-step-display — opt-in body hiding on `given`/`when`/`then` (see `docs/superpowers/specs/proposed/2026-06-06-flat-step-display-design.md`)
- [ ] Provide an agent skill for work with pytest-given, and document how LLM agents can benefit from pytest-given
- [ ] Add `@scenario(group_parametrized=False)` option to opt out of parametrize merging 
  - emit each case as its own scenario (named per case via Template substitution, or by appending the parametrize id to a `str` name).
  - Needed when narration structure genuinely varies per case; today's behavior silently shows case 1's structure for all rows. See caveat in `docs/superpowers/specs/2026-05-23-structured-step-text-design.md`.
  - This is also where per-case substitution of `Template` scenario names and t-string step text (`step_text(case=...)` / `Template.substitute(...)`) becomes load-bearing. Today the substitution machinery is wired but unreachable — the merged view only shows `{name}` tokens, so `Template` for scenario names mostly just Questioncontributes the placeholder highlight in the merged title.