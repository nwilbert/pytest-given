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
  rootdir name.
- A parametrized scenario's case table now carries a typed column per varying
  value — `param`, `derived` or `attachment` — rather than one column per
  parametrize name.
- A varying attachment payload becomes an `attachment` column of its own.
- `@scenario(group_parametrized=False)` declines the grouping and emits each case
  as its own scenario, titled by its parametrize id.
- The HTML report's sidebar gains **Terms** as a third browse axis, and all three
  axes — Tags, Terms, Modules — now filter the Scenarios view the same way, with
  each active filter carried in the sharable URL.
- The sidebar's browse list can be ordered by group size as well as by name, via
  an **A–Z / Count** toggle.
- A selected activity in the Stories view offers **Open in Scenarios**, filtering
  the Scenarios view down to the scenarios covering it.

### Changed

- **Breaking.** Step narration must now be uniform across parametrize cases;
  these fail the run with `PytestGivenError`, writing no report, instead of
  quietly reporting case 1:

  - a plain `str` (usually an f-string) that renders differently per case;
  - a varying interpolation that is not a bare name (`t"{cup_size * 0.01}"`,
    `t"{m.balance}"`);
  - a t-string narrating a parametrize name that no longer holds the case's
    value — either a local rebound it, or the body mutated it in place;
  - a step whose set of `attach` labels differs between cases;
  - a glossary term ref that names a different term or reads differently
    between cases. A term ref that *is* a parametrize value stays supported;
  - passed cases that narrate different templates altogether.

  Every one but the last has the same fix: bind the varying part to a local and
  narrate it with a t-string, keeping labels and term refs constant; content may
  still vary freely, which is what the new `attachment` column is for. The last
  needs `@scenario(..., group_parametrized=False)`, giving each case its own
  scenario.
- **Breaking (JSON report).** `parameters.names` becomes `parameters.columns`
  (`{id, name, kind}`), cells may hold an attachment object, placeholder parts
  gain `column_id`, and a grouped step's `narration.text` is the template rather
  than case 1's rendering.
- A glossary term placed in an activity slot its declared kind forbids now
  raises `PytestGivenError` when `activity(...)` is built rather than at session
  finish, naming the term and its kind instead of dumping handle reprs.
- **Breaking.** `attach()` now takes a plain `str` label; a t-string label raises
  `PytestGivenError` — use an f-string.
- **Breaking.** `attach()` called with no step open now raises `PytestGivenError`
  instead of silently discarding the payload; move the call inside the `given` /
  `when` / `then` block it belongs to.
- **Breaking.** `activity(..., id=N)` is now `activity(..., activity_id=N)`; the
  `Activity.id` field itself is unchanged.
- An unknown `given_source_link` preset is now a `UsageError` raised before the
  suite runs.
- The collection-time `@scenario` checks now report as a `UsageError` instead of
  an `INTERNALERROR` traceback.
- The bundled authoring skill's tagging guidance now argues for sparse tagging: a
  tag should cut across modules and cover a minority of the suite.
- The bundled authoring and reviewing skills gain the report mechanics their
  rules depend on, a symptom index, and a completeness audit.
- The Scenarios sidebar and its header chips are visually tidied.
- The HTML report's colors are retuned into one system, so glossary term kinds,
  statuses and parametrize columns can no longer land on the same color: a term
  ref in a step or a scenario title reads as a word under a light wash rather
  than a bordered pill (the Glossary view keeps its pills), and column colors are
  generated per column, so a seventh column no longer wraps back onto the first.
- An attachment badge in the HTML report now takes its icon from the payload's
  content type — braces for JSON, a page for text — instead of a paperclip for
  both. The Markdown report keeps its `📎`.

### Removed

- **Breaking.** The `divergent-case-structure` lint rule; delete any
  `given_lint_rules` or `given_lint_ignore` entry naming it, which would
  otherwise fail config parsing.

### Fixed

#### Plugin and run behavior

- A nested in-process pytest run that dies while parsing its arguments no longer
  strands the outer session's captured rootdir, which silently dropped every
  later step's source anchor.
- A finished scenario no longer leaves its collector — and every scenario and
  step it recorded — reachable from a process-global for the rest of the
  process.
- A fixture that raises after its `yield` now fails the scenario it tore down,
  instead of leaving it green in a report pytest counted as an error.
- Every report-building failure — a suite reaching two glossaries, a term used in
  incompatible slots, an unusable source-link template — now surfaces as a
  terminal summary and a failing exit code, where only grouping errors did.
- The sinks are now rendered in full before any is written, so a failing render
  can no longer leave this run's JSON beside the previous run's HTML.

#### Report content (all formats)

- A case-table cell now reads the way the step pointing at it read, carrying the
  interpolation's own format spec and, under `indirect=True`, the bound test
  argument; one parameter formatted two ways gets a column each.
- A `Template` narration's `text` is now what its parts render, so the report's
  search box and `jq` queries match what the page displays.
- The grouped step tree now comes from the first case that *passed*, where a
  skipped case 1 used to render an empty tree.

#### HTML report

- Two test files sharing a basename across directories no longer abort the HTML
  report; the scenarios' `#scenario=` slugs gain directory components instead.
- Content reaching past a scenario card's right edge is no longer clipped beyond
  reach: a wide case table and an attachment payload scroll, a source path and a
  traceback's frame location wrap, and the source link sits under the card's last
  element instead of on top of it.
- Jumping to a scenario from a story activity, or to a term's scenarios from the
  Glossary tab, now clears filters that would hide the target; the filters in a
  `#scenario=` deep link still win.
- Accent-colored text and the parametrize column colors now meet WCAG AA, term
  kinds stay distinguishable for red-green color blindness, and attachment badges
  are keyboard-operable.

#### Bundled skills

- The bundled skills are corrected against the shipped behavior: the navigating
  skill's term query and JSON reference, the authoring skill's guidance for
  divergent parametrize narration, glossary discovery order, `@scenario`'s
  keyword-only arguments, the scope of a pinned step, and the oversized-glossary
  advice.

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
