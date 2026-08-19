# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow reads the section matching the version in `pyproject.toml`
and uses it as the GitHub Release body, so each version needs a heading of the
form `## [x.y.z] - YYYY-MM-DD`.

## [Unreleased]

### Added

- `--given-title=TEXT` (or the `given_title` ini) names the report, replacing the
  rootdir name in the Markdown heading and the HTML tab title and topbar.
- A parametrized scenario's cases now share one narrated step tree above a
  typed case table, instead of case 1's values standing in for all of them.
- A varying attachment payload becomes an `attachment` column of its own,
  leaving a badge in the step that points at it.
- The HTML report's sidebar gains **Terms** as a third browse axis beside Tags
  and Modules, listing the glossary terms your scenarios reference.
- All three browse axes — Tags, Terms, Modules — now filter the Scenarios view
  the same way, each active filter showing as a dismissable chip that the
  sharable URL carries.
- The sidebar's browse list can be ordered by group size as well as by name,
  via an **A–Z / Count** toggle on the Browse-by line.
- A selected activity in the Stories view offers **Open in Scenarios**, which
  filters the Scenarios view down to the scenarios covering that activity.

### Changed

- **Breaking.** Step narration must now be uniform across parametrize cases;
  these raise `PytestGivenError` instead of quietly reporting case 1:

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
- `activity(..., id=N)` is now `activity(..., activity_id=N)`; the
  `Activity.id` field itself is unchanged.
- The bundled authoring skill's tagging guidance now argues for sparse tagging:
  a tag should cut across modules and cover a minority of the suite.
- The bundled authoring and reviewing skills gain the report mechanics their
  rules depend on, a symptom index, and a completeness audit.
- The Scenarios sidebar and its header chips are visually tidied: a selected
  row and the chip mirroring it now share one shape, unselected groups no
  longer dim, and chips name a term the way the glossary does.

### Fixed

- The grouped step tree now comes from the first case that *passed* — a skipped
  case 1 used to render an empty tree and hide later failures.
- A cell now reads the way the step pointing at it read, carrying the
  interpolation's own format spec and, under `indirect=True`, the bound test
  argument.
- Only a passing case with a value for the column contributes its glossary
  instance and story coverage.
- Attachment content now scrolls instead of being silently cut off, and
  attachment badges are keyboard-operable.
- Jumping to a scenario from a story activity, or to a term's scenarios from
  the Glossary tab, now clears filters that would hide the target; the filters
  in a `#scenario=` deep link still win.
- Accent-coloured text across the HTML report now meets WCAG AA.
- A run that ends in a parametrize grouping error now deletes the report files
  it was told to write, instead of leaving the previous run's behind.

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
