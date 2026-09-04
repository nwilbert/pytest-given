# Markdown Rendering for Review — Design Spec

## Goal

Make the Markdown sink complete enough to *review* a suite from, and retire the two scripts the
reviewing skill ships to work around it:

1. **`--given-md-source`** (opt-in) inlines each scenario's test body under its steps, so the
   narration and the code it claims to describe sit side by side.
2. **A Stories section** (default on) renders story coverage from the production rollups, so the
   report says which activities are covered without opening the HTML.

Both are reachable post-hoc through `pytest-given report`, so a reviewer re-renders an existing
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
worth more than part 1.

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

`build_coverage_map(report)` → `build_story_rollups(report, maps)` → `build_activity_labels(report)`
are already the HTML template's inputs; the Markdown section reads the same three. Each activity
renders as its label prose plus one marker derived from `ActivityCoverage`: covered (`total > 0`),
uncovered, or not tracked (`untracked`). A report with no stories renders no section, so existing
suites see no change.

Default on: coverage is report data, not a review-only extra, and a coverage change *should* show
up in the `.md` delta that [AGENTS.md](../../../AGENTS.md) tells contributors to read first.

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

| # | Activity | Coverage |
|---|---|---|
| 1 | Domain Expert tells Story to the Developer | — not tracked |
| 2 | Developer captures Story as Activity | ✓ 3 scenarios |
| 3 | Developer builds Glossary with the Domain Expert | ✗ uncovered |
```

## Configuration

| Surface | Spelling |
|---|---|
| pytest flag | `--given-md-source` / `--no-given-md-source` |
| ini | `given_md_source` |
| CLI | `pytest-given report data.json --format md --with-source` |

Tri-state flag over ini, matching `--given-lint`. The flag is meaningful only alongside a Markdown
sink; like an unused `--given-source-link` on a Markdown run today, it is inert rather than an
error.

## Implementation touch points

- `report/md_renderer.py` — `sources` parameter, source block, Stories section.
- `report/sinks.py` — `SinkConfig.md_source: bool`, resolution hook, pass-through to `render_md`.
- `report/sources.py` (new) — read + AST span; no imports beyond `model/`, filesystem access
  injected by the caller.
- `plugin/options.py` — flag + ini, `SinkConfig` wiring.
- `cli/report.py` — `--with-source`.
- `README.md`, the authoring skill's `references/api.md` — flag tables.
- Reviewing skill `SKILL.md` — layer 2 renders with the flag; layer 4 reads the Stories section.
- `references/story-coverage.md` — retire the query, keep the matching rules as documentation.
- `references/pairs.md` — demoted to the fallback for a JSON-only workflow or an older version.
- `CHANGELOG.md` — Added (flag, CLI option), Changed (Markdown gains a Stories section).
- Regenerate `examples/` and `examples/self-report/`.

## Test coverage

- Renderer units: bodies present, absent, unreadable file, line with no enclosing function; a
  grouped parametrized scenario; a report with no stories; covered / uncovered / untracked rows.
- Integration: off by default; on, the body reaches the file; the flag alone writes nothing new.
- CLI: `--with-source` against a saved report, resolving from the working directory.
- `tests/unit/test_skills_scripts.py` drops the story-coverage case with the query, keeps pairs.

## Out of scope

- **Source links in Markdown.** The true analogue of the HTML feature, but the only preset worth
  having there (`github`) is SHA-pinned, and AGENTS.md's regeneration rule depends on the Markdown
  sink carrying no `commit_sha`. A relative-path link would be SHA-free and deterministic; it needs
  its own decision, and its value is to a human clicking through, not to this workflow.
- **Step-fixture bodies.** `Step.source` is recorded only under `--given-lint` (deliberately: the
  AST surface costs nothing when the lint is off), so inlining covers scenarios only.
- **A coverage gate.** `pytest-given coverage` exiting non-zero on an uncovered eligible activity is
  a different feature — a threshold, not a rendering.
- **`--changed-since`.** Selecting only scenarios whose bodies moved stays a CLI idea.

## Open questions

1. `<details>` wrapper or a plain fenced block? The wrapper reads better; the block diffs better.
2. Should the CLI take `--root` for a report rendered outside its own tree, or is the working
   directory enough?
3. Whole function, or only the `with` blocks the steps name? Whole function is simpler and shows
   the helpers a step calls; step-only would need `Step.source`, which is lint-gated.
