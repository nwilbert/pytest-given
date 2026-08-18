# TODO

## Now

- [ ] Bug: when the glossary term filter is active in the Scenarios tab, jumping to a scenario from the Stories tab doesn't reset this filter
- [ ] implement the parametrized-case-columns-design spec

## Next

- [ ] Turn on branch coverage: `nox -s coverage` runs `coverage run` without `--branch`, so the 100% gate is line coverage only and a compound condition passes it with an untested False outcome. Found during the per-case columns work, where three unexercised conditions in one filter shipped inside a green 100% run. Enabling it (`--branch`, or `[tool.coverage.run] branch = true` in `pyproject.toml`) will surface partial branches in pre-existing code, so it needs its own pass rather than riding along with a feature branch.
- [ ] check support for https://library-skills.io/
- [ ] Enable optional custom IDs for activities (`str` instead of the current `int` numbers)
- [ ] Add sort option in Glossary, to sort by number of scenarios, instances, or stories
- [ ] enable definition of a custom mapping for boolean (or general) values to strings in parameterized scenarios
- [ ] Attachment badges: pick the icon from `content_type` instead of always a paperclip — a document glyph for `text`, braces for `json`. Replaces the HTML report's paperclip SVG and the Markdown renderer's `📎`: a branch in the badge macro plus a second inline SVG, no new data. Split out of the [per-case columns spec](docs/specs/2026-08-14-parametrized-case-columns-design.md), which touches the same badge macro but doesn't need this; `AttachmentRef` there carries `content_type` for it to read.
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
  - Scope narrowed by the [per-case columns spec](docs/specs/2026-08-14-parametrized-case-columns-design.md): varying attachments and varying derived values become columns there, and five unrenderable authoring forms raise. Structural divergence is all that is left for the opt-out.
  - That spec defers one question to this item: whether the opt-out should also apply *automatically* when structure diverges, rather than only on request — `divergent-case-structure` is lint-only and `given_lint` defaults off, so today that case still renders the baseline's structure silently. Deciding that here retires the lint rule.
  - It also defers **hard validation of structural variance** to here, and with it the narrower case of narration that changes shape without changing structure (a conditional `when(t"…" if n else "…")` keeps `(phase, children)` equal, so the merge still walks parts by index into a differently-shaped sentence). Both want the same treatment — refuse to merge and emit one scenario per case — which only exists once the opt-out does.
  - This is also where per-case substitution of `Template` scenario names and t-string step text (`step_text(case=...)` / `Template.substitute(...)`) becomes load-bearing. Today the substitution machinery is wired but unreachable — the merged view only shows `{name}` tokens, so `Template` for scenario names mostly just contributes the placeholder highlight in the merged title.
