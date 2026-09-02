# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The release workflow reads the section matching the version in `pyproject.toml`
and uses it as the GitHub Release body, so each version needs a heading of the
form `## [x.y.z] - YYYY-MM-DD`.

## [Unreleased]

### Added

- `pytest_given.PytestGivenWarning` is a top-level export, and a step or
  `attach()` recorded in a test without `@scenario` now warns with it instead of
  `pytest.PytestWarning`.
- `--given-title=TEXT` (or the `given_title` ini) names the report, replacing the
  rootdir name.
- A parametrized scenario's parameter table now carries a typed column per varying
  value — `param`, `derived`, or `attachment` for a varying attachment payload —
  rather than one column per parametrize name.
- `@scenario(group_parametrized=False)` declines the grouping and emits each case
  as its own scenario, titled by its parametrize id.
- The HTML report's sidebar gains **Terms** as a third browse axis, and all three
  axes — Tags, Terms, Modules — now filter the Scenarios view the same way, with
  each active filter carried in the URL.
- The sidebar can be ordered by group size as well as by name, and resized by
  dragging its seam or with the arrow keys.
- A selected activity in the Stories view offers **Open in Scenarios**, filtering
  the Scenarios view down to the scenarios covering it.

### Changed

#### Authoring API

- **Breaking.** Step narration must now be uniform across parametrize cases;
  these fail the run with `PytestGivenError`, writing no report, instead of
  quietly reporting case 1:

  - a plain `str` (usually an f-string) that renders differently per case;
  - a varying interpolation that is not a bare name (`t"{cup_size * 0.01}"`,
    `t"{m.balance}"`);
  - a t-string narrating a parametrize name that no longer holds the case's
    value — either a local rebound it, or the body mutated it in place;
  - a step whose set of `attach` labels differs between cases;
  - a glossary term ref that names a different term or reads differently between
    cases, including one bound to a parametrize column;
  - passed cases that narrate different templates altogether.

  Every one but the last is fixed by binding the varying part to a local and
  narrating it with a t-string, keeping labels and term refs constant; varying
  content belongs in the new `attachment` column. The last needs
  `@scenario(..., group_parametrized=False)`, giving each case its own scenario.
- **Breaking.** `attach()` now takes a plain `str` label; a t-string label raises
  `PytestGivenError` — use an f-string.
- **Breaking.** `attach()` called with no step open now raises `PytestGivenError`
  instead of silently discarding the payload; move the call inside the step it
  belongs to.
- **Breaking.** `activity(..., id=N)` is now `activity(..., activity_id=N)`; the
  `Activity.id` field itself is unchanged.
- A glossary term placed in an activity slot its declared kind forbids now raises
  `PytestGivenError` when `activity(...)` is built rather than at session finish.
- A glossary file whose table has a header and separator but no data rows now
  says so, instead of reporting that no table was found.
- `@scenario(activities=...)` now rejects a `str` and non-`int` members with a
  `TypeError`.
- `@scenario` now returns the test function itself rather than a wrapper, so the
  test keeps its own signature.

#### Plugin and run behavior

- An unknown `given_source_link` preset is now a `UsageError` raised before the
  suite runs.
- The collection-time `@scenario` checks now report as a `UsageError` instead of
  an `INTERNALERROR` traceback.
- The narration lint summary prints each finding's location in its own column
  rather than appended to the message.
- `pytest-given` with no subcommand, and `pytest-given skills` with no
  subcommand, now print that parser's usage and exit 2 instead of the root help
  and exit 1.

#### Report content (all formats)

- **Breaking (JSON report).** `parameters.names` becomes `parameters.columns`
  (`{id, name, kind}`), cells may hold an attachment object, placeholder parts
  gain `column_id`, term-ref parts lose `param_column`, and a grouped step's
  `narration.text` is the template rather than case 1's rendering.
- **Breaking (JSON report).** A step no longer carries `status` or `error`;
  failure lives on the scenario and on the parameter table's cases. A consumer
  reading `step.status` should read `scenario.status` instead.
- The Markdown report now shows a scenario's failure reason — the message and the
  failing frame — under the scenario, and under the parameter table for each
  failed case.

#### HTML report

- The browse sidebar leads with **Modules** and renders them as a collapsible
  package tree whose nodes filter by path prefix; it no longer lists individual
  scenarios under each group.
- The report's colors are retuned into one system — a term ref in a step or a
  scenario title reads as a word under a light wash rather than a bordered pill
  (the Glossary view keeps its pills), and column colors are generated per
  column — and the sidebar, its filter chips and the attachment badges are
  tidied along with it.
- The report opens and filters substantially faster on large suites, and its file
  is smaller.

#### Bundled skills

- The authoring and reviewing skills gain the report mechanics their rules depend
  on, a symptom index, a completeness audit, the full lint rule catalog, and
  guidance for sparser tagging.

### Removed

- **Breaking.** The `divergent-case-structure` lint rule; delete any
  `given_lint_rules` or `given_lint_ignore` entry naming it, which would
  otherwise fail config parsing.

### Fixed

#### Authoring API

- `@scenario(activities=...)` is now typed `int | Sequence[int] | None`, so a
  bare `activities=2` type-checks.
- Glossary term handles are now hashable, and equal for the same term whichever
  accessor produced them.
- A `when_then` step in a test without `@scenario` now points its warning at the
  test rather than at pytest-given's own module.

#### Plugin and run behavior

- A `git` on PATH that cannot be executed no longer fails the run.
- A nested in-process pytest run that dies while parsing its arguments no longer
  strands the outer session's captured rootdir, which silently dropped every
  later step's source anchor.
- `@given`/`@when`/`@then` on an `async def` helper now records around the
  awaited body, and async generator fixtures are handled too.
- The narration lint now inspects `async def` step helpers, whose bodies were
  invisible to every AST rule.
- An explicit `--given-source-link=` now disables source links instead of falling
  through to the `given_source_link` ini.
- A finished scenario no longer leaves its collector — and every scenario and
  step it recorded — reachable from a process-global for the rest of the process.
- An error-level lint finding no longer overwrites a more specific exit code, so
  an interrupted or nothing-collected run keeps reporting as one.
- A report that cannot be written into an unwritable directory now reports
  through the terminal summary instead of escaping as a bare traceback.
- `pytest-given report` and `pytest-given skills install` now report a failed
  write as a CLI error, and a failed `report` write discards the previous run's
  report rather than leaving it to read as current.
- `pytest-given report` now reports a bad input file — missing, unparsable, or
  JSON that is not a pytest-given report — as a CLI error instead of a traceback,
  as does an unknown `--source-link` preset.
- A fixture that raises after its `yield` now fails the scenario it tore down,
  instead of leaving it green in a report pytest counted as an error.
- An error-level narration-lint finding now counts as an error in the run's
  summary line.
- Every failure building or writing a report — a suite reaching two glossaries, a
  term used in incompatible slots, an unusable source-link template, an
  unwritable output path — now surfaces as a terminal summary and a failing exit
  code, where only grouping errors did.
- The sinks are now rendered in full before any is written, and a failure on
  either side discards all of them.

#### Report content (all formats)

- A parametrized scenario now keeps its place in source order instead of moving
  below every unparametrized one.
- A glossary term written as a code span keeps the markup inside it, so
  `` `a*b*c` `` canonicalizes to `a*b*c`.
- A parameter-table cell now reads the way the step pointing at it read, carrying
  the interpolation's own format spec and, under `indirect=True`, the bound test
  argument.
- A `Template` narration's `text` is now what its parts render, so the report's
  search box and `jq` queries match what the page displays.
- The grouped step tree now comes from the first case that *passed*, where a
  skipped case 1 used to render an empty tree.
- A parametrize value that is a glossary term instance now narrates as its
  display rather than the whole `Glossary` dataclass repr — in a step's
  `Template` slot, in a scenario name, and in an
  `Annotated[..., given(Template(...))]` parameter label.

#### HTML report

- Two test files sharing a basename across directories no longer abort the HTML
  report; the scenarios' `#scenario=` slugs gain directory components instead.
- A `#view=stories`, `#view=glossary` or `#term=` link opened against a report
  that has no such tab now falls back to the Scenarios view.
- The Glossary view's kind headings and their term counts now follow the search
  and definition filters, and a filter matching nothing says so.
- Content reaching past a scenario card's right edge is no longer clipped: a wide
  parameter table and an attachment payload scroll, a source path and a
  traceback's frame location wrap, and the source link no longer overlaps the
  card's last element.
- Jumping to a scenario from a story activity, or to a term's scenarios from the
  Glossary tab, now clears filters that would hide the target; the filters in a
  `#scenario=` deep link still win.
- Accent-colored text and the parametrize column colors now meet WCAG AA, and
  term kinds stay distinguishable for red-green color blindness.
- The report is operable from the keyboard: status pills, browse-axis and
  browse-tree rows, tag pills, story sidebar entries, activity and attachment
  badges, and every expand/collapse chevron are now real buttons, and the view
  tabs report which one is selected.
- A step pinned with `given(..., activity=N)` now covers an activity regardless
  of its term count; an under-anchored activity previously still rendered as
  "not coverage-tracked".

#### Bundled skills

- The bundled skills are corrected against the shipped behavior.

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
