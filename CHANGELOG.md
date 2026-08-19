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
  typed case table, instead of case 1's values standing in for all of them.
  A step that read `the drink costs 2.50 euros` now reads `the drink costs
  {price} euros`, with a `derived` column holding each case's price — hovering
  a row substitutes that case's value back into the token.
- A varying attachment payload likewise becomes an `attachment` column, leaving
  a badge in the step that points at it. A payload too long for its cell opens
  in a panel spanning the table (HTML) or a fence below it (Markdown).
- The HTML report's sidebar gains **Terms** as a third browse axis next to Tags
  and Modules, listing the glossary terms your scenarios reference, ordered by
  how many scenarios each one carries. Clicking a term filters the Scenarios
  view by it (the chevron expands the group instead), so a term filter no
  longer has to be started from the Glossary tab. Reports with a glossary now
  open on this axis; reports without one show no Terms segment and open on
  Tags as before.

### Fixed

- The active-term chip in the Scenarios header now shows the term's canonical
  name (`File glossary`) instead of its slug id (`file-glossary`).

### Changed

- The bundled authoring skill's tagging guidance now argues for sparse tagging:
  a tag should cut across modules and cover a minority of the suite. It no
  longer offers `happy-path` as an example — it labels a test category rather
  than a behaviour, and on a majority of scenarios it filters nothing.
- `activity(..., id=N)` is now `activity(..., activity_id=N)`. The keyword
  shadowed the `id` builtin; the `Activity.id` field itself is unchanged.
- **Breaking.** Step narration must now be uniform across parametrize cases.
  These raise `PytestGivenError` instead of quietly reporting case 1:

  - a plain `str` (usually an f-string) that renders differently per case;
  - a varying interpolation that is not a bare name (`t"{cup_size * 0.01}"`,
    `t"{m.balance}"`);
  - a t-string narrating a parametrize name that no longer holds the case's
    value — either a local rebound it, or the body mutated it in place;
  - a t-string or `Template` `attach` label;
  - a step whose set of `attach` labels differs between cases;
  - a glossary term ref whose pill varies. A pill that *is* a parametrize
    value stays supported.

  The fix is the same throughout: bind the varying part to a local and narrate
  it with a t-string, keeping labels and pills constant. Content may still vary
  freely — that is what the new `attachment` column is for.
- **Breaking (JSON report).** `parameters.names` becomes `parameters.columns`
  (`{id, name, kind}`), cells may hold an attachment object, placeholder parts
  gain `column_id`, and a grouped step's `narration.text` is the template
  rather than case 1's rendering.
- The bundled `pytest-given-authoring` skill now documents the report mechanics
  its rules depend on (story binding, coverage matching, lint severities), adds
  a symptom index, and groups the scenario rules under subheads.
- The bundled `pytest-given-reviewing` skill gains a completeness audit (what
  the report fails to say), a terminal-readable story-coverage check, and a
  full-suite fallback for adoption branches with no base report to diff.

### Fixed

- The grouped step tree now comes from the first case that *passed*. A skipped
  case 1 used to render an empty tree and hide later failures.
- A cell now reads the way the step that points at it read. It carries the
  interpolation's own format spec (`{price:.2f}` gives `2.50`, not `2.5`), and
  under `indirect=True` it holds the bound test argument rather than the
  parametrize input.
- Only a passing case with a value for the column contributes its glossary
  instance and story coverage.
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
