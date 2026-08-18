# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow reads the section matching the version in `pyproject.toml`
and uses it as the GitHub Release body, so each version needs a heading of the
form `## [x.y.z] - YYYY-MM-DD`.

## [Unreleased]

### Added

- A t-string interpolation whose value varies across parametrize cases is now a
  `derived` column in the case table, with a `{name}` placeholder left in the
  grouped step, instead of being frozen to the first case's value.
- An attachment whose payload varies across parametrize cases is now an
  `attachment` column in the case table, and the grouped step keeps a
  content-less badge pointing at that column instead of showing one case's
  payload as if it spoke for all of them. A case that attaches a label more
  times than the baseline case gets a column per extra occurrence, which
  carries no badge — the grouped step has no slot for an attachment the
  baseline never recorded. A payload only sits in the cell when it is short and
  single-line: in HTML the badge opens a panel spanning the table under its
  row, and in Markdown a longer payload is fenced below the table. Neither
  squeezes the column, and a line too wide for the panel scrolls rather than
  being cut off. No two columns share a header: a
  label attached twice in one step, or one expression promoted in two steps,
  gives the second and later columns a ` #2` / ` #3` suffix, and the step
  tree's badge or `{name}` token carries the suffixed name too — a pointer
  names the column it points at.

- A parametrize case that passed while recording a different step structure
  than the grouped tree is now marked as such — `≠` beside its status in HTML,
  a note under the table in Markdown, `divergent: true` in JSON — so its blank
  generated cells read as "took another path" rather than as missing data.

### Changed

- **Breaking (JSON report).** `parameters.names` becomes `parameters.columns`,
  each `{id, name, kind}` with `kind` one of `param` / `derived` /
  `attachment`; a case's `values` stays positionally aligned with it and a cell
  may now be an attachment object rather than a scalar. Placeholder narration
  parts gain `column_id`, and a step attachment may be a content-less
  `{label, content_type, column_id}` reference to a column. Update any `jq`
  reading `parameters`. There is no migration: re-run the suite to regenerate a
  report saved before this change — `pytest-given report` on an older one says
  so instead of failing with a bare `KeyError`.
- `activity(..., id=N)` is now `activity(..., activity_id=N)`. The keyword
  shadowed the `id` builtin; the `Activity.id` field itself is unchanged.
- The bundled `pytest-given-authoring` skill now documents the report mechanics
  its rules depend on (story binding, coverage matching, lint severities), adds
  a symptom index, and groups the scenario rules under subheads.
- The bundled `pytest-given-reviewing` skill gains a completeness audit (what
  the report fails to say), a terminal-readable story-coverage check, and a
  full-suite fallback for adoption branches with no base report to diff.
- **Breaking.** `attach` takes a plain `str` label; a t-string or `Template`
  label now raises `PytestGivenError` instead of being silently flattened. Use
  an f-string — `attach(f'{kind} log', …)` — keeping the label identical across
  parametrize cases, since a label that varies per case is itself rejected.
- **Breaking.** A parametrized scenario whose step narration is a plain `str`
  (usually an f-string) that renders differently per case now raises
  `PytestGivenError`; the run fails and writes no report. Use a t-string so the
  varying part is recorded as a part instead of baked into case 1's text.
- **Breaking (JSON report).** A grouped parametrized scenario's step
  `narration.text` is now the template (`the drink costs {price} euros`), not
  the first case's rendering. HTML and Markdown output is unchanged; JSON
  readers only.
- **Breaking.** A varying t-string interpolation whose expression is not a bare
  name (`t"{cup_size * 0.01}"`, `t"{m.balance}"`) now raises
  `PytestGivenError`. Bind it to a local and narrate that.
- **Breaking.** A step whose set of `attach` labels differs between parametrize
  cases now raises `PytestGivenError`. Use a constant label and let the content
  vary — the content is what the new `attachment` column is for.
- **Breaking.** A glossary term ref whose pill differs between parametrize
  cases now raises `PytestGivenError` — unless the pill *is* a parametrize
  value, which stays supported. Split the pill from the value:
  `given(t"{pg['Customer']} {name} places an order")`.

### Fixed

- An attachment line wider than its container was silently cut off — `<pre>`
  does not wrap and nothing scrolled. Attachment content now scrolls
  horizontally, in the step tree as well as the case table.

- A run that ends in a parametrize grouping error now deletes the report files
  it was told to write instead of leaving the previous run's behind, where they
  read as current and say nothing about the failure.
- A parametrize case that did not pass no longer speaks for a glossary term
  pill bound to a parametrize column: it can neither cover a story activity nor
  be listed in the Glossary as an instance the suite exercised. A case with no
  value for that column contributes nothing either, instead of falling back to
  the display the grouped step tree happens to carry.
- The `unused-interpolation` lint rule never fired on a parametrized scenario:
  the lint reads the grouped scenario, where a varying interpolation is a
  placeholder rather than a value, and the rule only scanned values.

- The bundled authoring skill's glossary-discovery advice: `conftest.py` must
  bind the `Glossary` / `FileGlossary` handle itself, not merely import the
  module defining it, or the report's Glossary tab stays empty.
- Parametrizing over a glossary term instance stored a dataclass repr of the
  whole glossary in the parameter table; the column now holds the term's
  display, and story coverage and the Glossary view see every case's instance
  rather than only the first's.
- A grouped parametrized scenario whose first case was skipped rendered an empty
  step tree even though later cases ran. The grouped tree now comes from the
  first case that passed, or — when no case passed — from the first case that
  recorded a tree at all, so a failure is no longer hidden behind a skip.
- **Breaking.** A t-string interpolating a *rebound* parametrize name rendered
  the parameter's value rather than the narrated one — wrong for every case, not
  just the first. It now raises `PytestGivenError`; rename the local. The
  comparison is against the value the test argument was bound to, so an
  `indirect=True` parameter is judged by what its fixture returned — which is
  also what its case cell now holds.

## [0.1.0] - 2026-08-08

First public release.

### Added

- `@scenario` decorator plus `given` / `when` / `then` step blocks, usable as
  both context managers and decorators, including on fixtures.
- Self-contained interactive HTML report (`--given-html`), Markdown report
  (`--given-md`), and JSON report (`--given-json`). The HTML bundles Alpine.js
  and needs no server or external assets.
- Structured step text: plain strings, `Template` objects, and t-strings
  ([PEP 750](https://peps.python.org/pep-0750/)), with parameter interpolation
  rendered as highlighted values.
- `attach()` for text and JSON attachments on a step.
- Domain Storytelling support: ubiquitous-language glossaries (inline or
  Markdown-backed via `FileGlossary`), Domain Stories, and story coverage.
- Narration lint (`--given-lint`) with a configurable rule catalog via
  `given_lint_rules` and `given_lint_ignore`.
- `--given-source-link` with `vscode`, `cursor`, `zed`, `pycharm`, and `github`
  presets for jumping from a report step to its source.
- `pytest-given` console script: `report` to re-render a saved JSON report, and
  `skills install` to mirror the bundled agent skills into a project's
  `.claude/skills/`.
- Bundled authoring, navigating, and reviewing skills for AI agents, shipped in
  the wheel and version-matched to the plugin.

[Unreleased]: https://github.com/nwilbert/pytest-given/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nwilbert/pytest-given/releases/tag/v0.1.0
