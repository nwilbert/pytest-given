# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow reads the section matching the version in `pyproject.toml`
and uses it as the GitHub Release body, so each version needs a heading of the
form `## [x.y.z] - YYYY-MM-DD`.

## [Unreleased]

### Added

- A parametrized scenario's cases now share one narrated step tree above a
  typed case table, instead of the first case's values standing in for all of
  them. A varying t-string interpolation becomes a `derived` column and leaves
  a `{name}` placeholder in the step; a varying attachment payload becomes an
  `attachment` column and leaves a badge pointing at it. Column headers are
  unique (` #2`, ` #3` suffixes, carried by the badge or `{name}` token that
  points there), and a payload too long for its cell opens in a panel spanning
  the table (HTML) or a fence below it (Markdown).
- A case that passed while recording a different step structure than the
  grouped tree is now marked as such — `≠` in HTML, a note under the table in
  Markdown, `divergent: true` in JSON — so its blank cells read as "took
  another path" rather than as missing data.

### Changed

- **Breaking.** Step narration must now be uniform across parametrize cases.
  These raise `PytestGivenError` instead of quietly reporting case 1: a plain
  `str` (usually an f-string) that renders differently per case; a varying
  interpolation whose expression is not a bare name (`t"{cup_size * 0.01}"`,
  `t"{m.balance}"`); a t-string interpolating a *rebound* parametrize name; a
  t-string or `Template` `attach` label; a step whose set of `attach` labels
  differs between cases; and a glossary term ref whose pill varies — a pill
  that *is* a parametrize value stays supported. The fix is the same
  throughout: bind the varying part to a local and narrate it with a t-string,
  keeping labels and pills constant. Content may still vary freely — that is
  what the new `attachment` column is for.
- **Breaking (JSON report).** `parameters.names` becomes `parameters.columns`,
  each `{id, name, kind}` with `kind` one of `param` / `derived` /
  `attachment`; `values` stays positionally aligned with it and a cell may now
  be an attachment object rather than a scalar. Placeholder narration parts
  gain `column_id`, a step attachment may be a content-less
  `{label, content_type, column_id}` column reference, and a grouped step's
  `narration.text` is now the template (`the drink costs {price} euros`) rather
  than case 1's rendering. HTML and Markdown output is unchanged; update any
  `jq` reading `parameters`. There is no migration: re-run the suite to
  regenerate an older report — `pytest-given report` on one says so instead of
  failing with a bare `KeyError`.
- `activity(..., id=N)` is now `activity(..., activity_id=N)`. The keyword
  shadowed the `id` builtin; the `Activity.id` field itself is unchanged.
- The bundled `pytest-given-authoring` skill now documents the report mechanics
  its rules depend on (story binding, coverage matching, lint severities), adds
  a symptom index, and groups the scenario rules under subheads.
- The bundled `pytest-given-reviewing` skill gains a completeness audit (what
  the report fails to say), a terminal-readable story-coverage check, and a
  full-suite fallback for adoption branches with no base report to diff.

### Fixed

- Parametrized-scenario reporting: the grouped step tree now comes from the
  first case that passed — previously a skipped case 1 rendered an empty tree
  and hid later failures; parametrizing over a glossary term instance stores
  the term's display rather than a repr of the whole glossary; only a passing
  case with a value for the column contributes its glossary instance and story
  coverage; `unused-interpolation` fires on parametrized scenarios again, where
  a varying interpolation is a placeholder rather than a value; and an
  `indirect=True` parameter's cells held the parametrize input while the step
  narrated what the fixture returned, so row hover substituted a value the step
  never rendered — cells now hold the bound test argument.
- Attachment content scrolls horizontally instead of being silently cut off
  (`<pre>` does not wrap), in the step tree as well as the case table. Badges
  are keyboard-operable too: focusable, with a focus ring, Enter and Space, and
  a reported expanded state.
- A run that ends in a parametrize grouping error now deletes the report files
  it was told to write instead of leaving the previous run's behind, where they
  read as current and say nothing about the failure.
- The bundled authoring skill's glossary-discovery advice: `conftest.py` must
  bind the `Glossary` / `FileGlossary` handle itself, not merely import the
  module defining it, or the report's Glossary tab stays empty.

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
