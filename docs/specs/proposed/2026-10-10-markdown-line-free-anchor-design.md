# Line-Free Markdown Anchor — Design Spec

## Goal

Let the Markdown sink leave the line number out of each scenario's anchor, so a Markdown diff
shows behavior changes instead of every anchor below an inserted test:

```toml
[tool.pytest]
given_md_lines = false
```

## Background

The reviewing skill tells a reviewer to diff the Markdown at base and head as "the behavioral delta
in prose", and [AGENTS.md](../../../AGENTS.md) tells contributors to read the `.md` diff of a
regenerated report first. Every scenario's anchor is `relpath:line::test_name`, so one inserted
test shifts the anchor of every scenario below it in the same file; in practice anchor moves can
make up half a diff. In this repository they also turn an unrelated test edit into a self-report
change, which AGENTS.md has to explain as "real".

The JSON keeps `Scenario.source.line` regardless, and the HTML keeps its source links, so the
Markdown can drop the line without losing anything a reader cannot recover.

## Design

With `given_md_lines = false` the anchor renders `relpath::test_name`, which is what the renderer
already falls back to for a scenario without a `source`. The parametrize suffix is stripped as
today, so the anchor is a pytest node id: pasted after `pytest`, it runs the scenario, every case
of a grouped one included.

`render_md` takes the setting as a parameter, so it stays a total function of its inputs. Only the
Markdown sink reads it; on a run without one it is inert, like `given_source_link` on a
Markdown-only run.

- **Default on.** The navigating skill sends agents to the code through the anchor's `file:line`,
  and a terminal makes it clickable. Projects that commit their Markdown turn it off.
- **Ini and flag.** `given_md_lines` sets it for a project's committed reports;
  `--given-md-lines` / `--no-given-md-lines` override it for one run, a tri-state flag over its
  ini like `--given-lint`.
- **CLI:** `pytest-given report data.json --format md --no-lines`, since the CLI reads no pytest
  config. Re-rendering a saved base this way needs no second run.
- **A switch, not a template** like `given_source_link`. A source link adds navigation; this
  setting exists for diff stability, which is a matter of showing *less*, and any template that
  links to the code would bring the line back through the URL.

This repository sets `given_md_lines = false`, so the committed example and self-report Markdown
change only when narration does.

## Implementation touch points

- `report/md_renderer.py` — a `lines: bool = True` parameter on `render_md`, threaded to the
  anchor.
- `report/sinks.py` — `SinkConfig.md_lines`, passed to `render_md`.
- `plugin/options.py` — `--given-md-lines` / `--no-given-md-lines`
  (`argparse.BooleanOptionalAction`) over the `given_md_lines` ini (`type='bool'`, default
  `true`), wired into `SinkConfig`.
- `cli/report.py` — `--no-lines`.
- `docs/site/configuration/pytest-options.md` (flag table) and `docs/site/cli.md`.
- Navigating skill `SKILL.md` — the anchor may come without its line; then jump through the JSON
  `source.line`, or search for the test name.
- Reviewing skill `SKILL.md`, layer 2 — render base and head with `--no-given-md-lines`
  (`--no-lines` for a saved JSON) before diffing.
- `pyproject.toml` — `given_md_lines = false`.
- `AGENTS.md`, Quality gates — a shifted source line no longer shows in the `.md`, so drop the
  advice that it marks a real self-report change.
- Self-report: decorate the test that states "the Markdown anchor leaves out the line under
  `given_md_lines = false`".
- `CHANGELOG.md` — Added: `--given-md-lines` / `--no-given-md-lines` with the `given_md_lines`
  ini, and the CLI's `--no-lines`.
- Regenerate `examples/` and `examples/self-report/`; every anchor loses its line, nothing else
  changes.

## Test coverage

- Renderer units: the anchor with and without its line; a grouped scenario's anchor without the
  case suffix either way; a scenario without `source` unchanged by the setting.
- Integration: the ini reaches the written file, and the flag overrides it either way; the default
  keeps the line.
- CLI: `--no-lines` against a saved report.

## Out of scope

- **Narration beside test bodies.** The reviewing skill's `references/pairs.md` dumps each
  scenario's narration beside its test function, one file per test file, with line numbers to
  cite. That is the unit a split layer-2 audit hands out, and the dump is a review aid nobody
  commits, so it stays a skill script rather than a sink option.
- **A Stories section.** The JSON's `coverage[]` already carries story coverage from the code that
  renders the Stories tab, and the reviewing skill queries it. Story coverage is for discovery,
  so a Markdown rendering of it would list the covering scenarios per sentence; that is a
  navigation feature with its own spec, not a review aid.
- **Source links in Markdown.** The only preset worth having there (`github`) is SHA-pinned, and
  the Markdown's diff value depends on it carrying no `commit_sha`.
