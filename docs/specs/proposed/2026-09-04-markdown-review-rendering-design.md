# Markdown Rendering for Review — Design Spec

## Goal

Make the Markdown sink complete enough to *review* a suite from, and retire the two scripts the
reviewing skill ships to work around it:

1. **`--given-md-source`** (opt-in) inlines each scenario's test body under its steps, so the
   narration and the code it claims to describe sit side by side.
2. **A Stories section** (default on) renders story coverage from the production rollups, so the
   report says which sentences are covered without opening the HTML.
3. **`--no-given-md-lines`** (opt-out) drops the line number from each scenario's anchor, so a
   Markdown diff shows behavior changes instead of every anchor below an inserted test.

All three are reachable post-hoc through `pytest-given report`, so a reviewer re-renders an existing
JSON report instead of re-running the suite.

## Background

The reviewing skill audits narration against bodies (layer 2) and story coverage (layer 4). The
Markdown sink supports neither, so the skill ships two scripts as references:

- `references/pairs.md` reads `Scenario.source` and dumps each narration beside its test's source.
  New work, not a duplicate of anything in the package.
- `references/story-coverage.md` reimplements coverage over the JSON — and this one *is* a
  duplicate. `report/coverage.py` and `report/story_view.py` already compute it for the HTML
  Stories tab; the shipped query is a deliberately lossy shadow (term ids only, no instance
  identities, a pinned step matched by narration as well as by its pin), documented as "a floor".

`tests/unit/test_skills_scripts.py` runs both against a report built from the model, so neither can
drift from the *schema* silently. Nothing pins the coverage query to the *algorithm*: it can stay
green while disagreeing with the report a reviewer is auditing. That asymmetry is what makes part 2
worth more than part 1. The query's "names a story yet covers none of it" variant is not a
rendering at all but a rule, and moves to the [`unused-story` lint](2026-10-10-unused-story-lint-design.md).

The reviewing skill tells a reviewer to diff the Markdown at base and head as "the behavioral delta
in prose". Every scenario's anchor carries `relpath:line`, so one inserted test shifts the anchor of
every scenario below it in the same file; in practice anchor moves can make up half a diff. The
JSON keeps the line regardless, so the Markdown can drop it without losing anything a reviewer
cannot recover.

Supersedes the `pytest-given audit` entry that stood under TODO "Later" (a subcommand emitting
(step text, body source) pairs; see the [lint spec](../2026-07-05-narration-lint-design.md)
non-goals and [agent-skills spec](../2026-07-11-agent-skills-design.md) phase 3). The pairs feed
lands as a rendering option on a sink that already exists, and `pytest-given report` already
re-renders Markdown from a saved JSON, so no new subcommand is needed.

## Approach

### Part 1 — `--given-md-source`

`Scenario.source` (POSIX relpath + 1-indexed line) is captured on every run; the body is read at
render time and the enclosing function found by AST — the innermost `FunctionDef` whose span,
decorators included, contains that line.

**The renderer stays pure.** `report/` may import only `model/`, and `render_md(report) -> str` is
a total function of its input today. Resolution therefore happens at the sink boundary and the
bodies are passed in:

```python
def render_md(report: ReportData, sources: Mapping[NodeId, str] | None = None) -> str: ...
```

The entry points own the filesystem: the plugin resolves against `config.rootdir`, the CLI against
the current directory. A file that cannot be read, or a line with no enclosing function, degrades
to today's plain anchor — a review aid must never fail a run that would otherwise write a report.

A grouped parametrized scenario inlines one function, which is the truth: one test function, one
body, N cases in the parameter table.

### Part 2 — Stories section

`build_coverage_map(report)` → `build_story_rollups(report, maps)` → `build_sentence_labels(report)`
are already the HTML template's inputs; the Markdown section reads the same three. Each sentence
renders as its label prose plus one marker derived from `SentenceCoverage`: covered (`total > 0`),
uncovered, or not tracked (`untracked`). A report with no stories renders no section, so existing
suites see no change.

Default on: coverage is report data, not a review-only extra, and a coverage change *should* show
up in the `.md` delta that [AGENTS.md](../../../AGENTS.md) tells contributors to read first.

### Part 3 — `--no-given-md-lines`

The subtitle anchor is `relpath:line::test_name` today, a terminal-clickable `file:line`. With the
setting off it renders `relpath::test_name`, still unique within the report and greppable. The
setting changes only the Markdown sink: the JSON keeps `Scenario.source.line`, and the HTML keeps
its source links. `render_md` takes it as a parameter like `sources`, so `render_md` stays a total
function of its inputs.

It is a switch, not a template like `given_source_link`. A source link adds navigation; this
setting exists for diff stability, which is a matter of showing *less*, and any template that
links to the code would bring the line back through the URL.

Default on, so the anchor stays clickable in a terminal. A reviewer diffing two renders turns it off
for both; because the JSON keeps the line, `pytest-given report --format md --no-lines` re-renders
a saved base without re-running it. This repository sets the ini off for its committed reports, so
a test inserted above a decorated one no longer counts as a self-report change.

## Markdown format

````markdown
## ✓ A step fixture is grafted in as a given step
`tests/integration/test_plugin.py:205::test_step_fixture_appears_as_given_step`

- **given** a «scenario» consuming a «step fixture»
- **when** the suite runs with --given-json
- **then** the «step» from the fixture leads the recorded steps

<details><summary>source</summary>

```python
@scenario(...)
def test_step_fixture_appears_as_given_step(pytester, tmp_path):
    ...
```

</details>
````

The `<details>` wrapper keeps a sourced report readable on GitHub and in editors that render it,
and collapses the bulk for anyone reading the prose. Plain fenced blocks are the fallback if the
wrapper proves awkward in a diff — see Open Questions.

```markdown
# Stories

## Adopt pytest-given

| # | Sentence | Coverage |
|---|---|---|
| 1 | Domain Expert tells Story to the Developer | — not tracked |
| 2 | Developer captures Story as Sentence | ✓ 3 scenarios |
| 3 | Developer builds Glossary with the Domain Expert | ✗ uncovered |
```

## Configuration

| Surface | Spelling |
|---|---|
| pytest flag | `--given-md-source` / `--no-given-md-source` |
| ini | `given_md_source` |
| CLI | `pytest-given report data.json --format md --with-source` |
| pytest flag | `--given-md-lines` / `--no-given-md-lines` |
| ini | `given_md_lines` (default `true`) |
| CLI | `pytest-given report data.json --format md --no-lines` |

Each is a tri-state flag over its ini, matching `--given-lint`. Both are meaningful only alongside a
Markdown sink; like an unused `--given-source-link` on a Markdown run today, they are inert rather
than an error.

## Implementation touch points

- `report/md_renderer.py` — `sources` and `lines` parameters, source block, line-free anchor,
  Stories section.
- `report/sinks.py` — `SinkConfig.md_source: bool`, `SinkConfig.md_lines: bool`, resolution hook,
  pass-through to `render_md`.
- `report/sources.py` (new) — read + AST span; no imports beyond `model/`, filesystem access
  injected by the caller.
- `plugin/options.py` — flags + inis, `SinkConfig` wiring.
- `cli/report.py` — `--with-source`, `--lines` / `--no-lines`.
- `README.md`, `docs/site/configuration/pytest-options.md`, `docs/site/cli.md`, the authoring
  skill's `references/api.md` — flag tables.
- Reviewing skill `SKILL.md` — layer 2 renders with `--given-md-source` and diffs base and head
  under `--no-given-md-lines`; layer 4 reads the Stories section.
- `references/story-coverage.md` — retire the queries, keep the matching rules as documentation.
- `references/pairs.md` — demoted to the fallback for a JSON-only workflow or an older version.
- `pyproject.toml` — `given_md_lines = false` for this repository's committed reports.
- `AGENTS.md` — Quality gates: a shifted source line no longer shows in the `.md`, so drop the
  advice that it marks a real self-report change.
- `CHANGELOG.md` — Added (flags, CLI options), Changed (Markdown gains a Stories section).
- Regenerate `examples/` and `examples/self-report/`.

## Test coverage

- Renderer units: bodies present, absent, unreadable file, line with no enclosing function; a
  grouped parametrized scenario; a report with no stories; covered / uncovered / untracked rows;
  the anchor with and without its line.
- Integration: `--given-md-source` off by default, and on, the body reaches the file;
  `--no-given-md-lines` reaches the file; neither flag alone writes anything new.
- CLI: `--with-source` against a saved report, resolving from the working directory; `--no-lines`
  against a saved report.
- `tests/unit/test_skills_scripts.py` drops the story-coverage case with the query, keeps pairs.

## Out of scope

- **Source links in Markdown.** The true analogue of the HTML feature, but the only preset worth
  having there (`github`) is SHA-pinned, and AGENTS.md's regeneration rule depends on the Markdown
  sink carrying no `commit_sha`. A relative-path link would be SHA-free and deterministic; it needs
  its own decision, and its value is to a human clicking through, not to this workflow.
- **Step-fixture bodies.** `Step.source` is recorded only under `--given-lint` (deliberately: the
  AST surface costs nothing when the lint is off), so inlining covers scenarios only.
- **A coverage gate.** `pytest-given coverage` exiting non-zero on an uncovered eligible sentence is
  a different feature — a threshold, not a rendering.
- **`--changed-since`.** Selecting only scenarios whose bodies moved stays a CLI idea.

## Open questions

1. `<details>` wrapper or a plain fenced block? The wrapper reads better; the block diffs better.
2. Should the CLI take `--root` for a report rendered outside its own tree, or is the working
   directory enough?
3. Whole function, or only the `with` blocks the steps name? Whole function is simpler and shows
   the helpers a step calls; step-only would need `Step.source`, which is lint-gated.
