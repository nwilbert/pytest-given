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
- A parametrized scenario's cases now share one narrated step tree above a typed
  case table.
- `@scenario(group_parametrized=False)` declines that merge and emits each case
  as its own scenario, titled by its parametrize id.
- A varying attachment payload becomes an `attachment` column of its own.
- The HTML report's sidebar gains **Terms** as a third browse axis beside Tags
  and Modules.
- All three browse axes — Tags, Terms, Modules — now filter the Scenarios view
  the same way, with each active filter carried in the sharable URL.
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
  - a t-string `attach` label — `attach` now takes a plain `str`;
  - a step whose set of `attach` labels differs between cases;
  - a glossary term ref whose term varies. A term ref that *is* a parametrize
    value stays supported;
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
- Glossary terms in a step or a scenario title now read as a word under a light
  wash rather than a bordered pill, with the kind in the ink and a neutral wash
  where there is no kind; parametrize column colours are generated per column
  rather than drawn from a fixed list of six, so a seventh column no longer
  wraps back onto the first. The Glossary view keeps its pills.
- An attachment badge in the HTML report now takes its icon from the payload's
  content type — braces for JSON, a page for text — instead of a paperclip for
  both. The Markdown report keeps its `📎`.

### Removed

- **Breaking.** The `divergent-case-structure` lint rule; delete any
  `given_lint_rules` or `given_lint_ignore` entry naming it, which would
  otherwise fail config parsing.

### Fixed

#### Plugin and run behaviour

- A nested in-process pytest run that dies while parsing its arguments no longer
  strands the outer session's captured rootdir, which silently dropped every
  later step's source anchor and with it the lint's whole AST-rule surface.
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
  search box and `jq` queries no longer match a spec the page never displays.
- The grouped step tree now comes from the first case that *passed* — a skipped
  case 1 used to render an empty tree and hide later failures.

#### HTML report

- Two test files sharing a basename across directories no longer abort the HTML
  report; the scenarios' `#scenario=` slugs gain directory components instead.
- Attachment content now scrolls instead of being silently cut off, and
  attachment badges are keyboard-operable.
- Jumping to a scenario from a story activity, or to a term's scenarios from the
  Glossary tab, now clears filters that would hide the target; the filters in a
  `#scenario=` deep link still win.
- The HTML report's colours are retuned into one system, so glossary term kinds,
  statuses and parametrize columns can no longer land on the same colour.
- Accent-coloured text and the parametrize column colours in the HTML report now
  meet WCAG AA, and term kinds stay distinguishable for red-green colour
  blindness.
- A scenario title carrying glossary terms no longer wraps early in Firefox,
  breaking to a second line with the rest of the row empty.
- The source link in a scenario card no longer sits on top of the card's last
  element, where it covered the final row and status column of a full-width case
  table.
- A case table too wide for its card now scrolls instead of being clipped with
  no scrollbar.
- A source path and a traceback's frame location now wrap rather than spilling
  past a narrow card's edge.

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
