# Test Source in the Markdown Report — Design Spec

## Goal

Let a run print each scenario's test function below its narration in the Markdown report, so a
reviewer reads step text and step body side by side without a script:

```bash
pytest tests/test_booking.py --given-md --given-md-source
```

## Background

The reviewing skill's semantic audit (layer 2) judges each step's text against the code under it.
Today [pairs.md](../../src/pytest_given/.agents/skills/pytest-given-reviewing/references/pairs.md)
gets the two side by side with a 75-line script: it reads the JSON report, finds each test
function with `ast`, and writes the recorded steps, the parameter table and the function into one
dump file per test file. The script re-implements a cruder version of what the Markdown renderer
already prints (steps, parameter tables, case IDs), so it drifts with the report schema, and it is
the largest block of code in any skill.

The Markdown renderer can do the same with one flag, and the skill shrinks to a command.

## Design

### Output

With `--given-md-source`, each scenario's section ends with the test function's source, after the
steps, the parameter table and any error block. The source is the function as written, decorators
included, in a fenced `python` block, each line prefixed with its line number in the file. The
fence outgrows any run of backticks in the source, as an attachment's does:

````markdown
## ✓ A booking that overlaps another is refused
`tests/test_booking.py:41::test_overlap_is_refused`

- **given** a booking for room A, hours 10 to 20
- **when** a second booking for room A, hours 15 to 25, is made
- **then** it is refused

```python
41  @scenario('A booking that overlaps another is refused')
42  def test_overlap_is_refused(calendar):
43      with given('a booking for room A, hours 10 to 20'):
...
```
````

- **The test function only.** A step fixture's body, a module-level constant or a helper the
  body calls is not shown. The heading's anchor and the line numbers lead to the file, which the
  reviewer opens for the rest.
- **The function is the innermost `def` or `async def` whose span, decorators included, holds the
  scenario's `source.line`.** `source.line` is the first decorator's line (`co_firstlineno`) or
  the `def` line, and a test defined inside a helper still resolves to the test, not the helper.
  This is the lookup the pairs script does today.
- **A parametrized scenario shows its function once**, like its narration. A scenario that
  declines grouping (`group_parametrized=False`) is one scenario per case, so each shows the same
  function.
- **Line numbers always show**, whatever `given_md_lines` says. `given_md_lines = false` exists
  for committed Markdown reports, whose diffs shouldn't shift. Test source is a review aid, not
  something to commit, and a reviewer cites `file:line` from it.
- **Source that can't be read doesn't fail the report.** When the file can't be read or parsed,
  or no function holds the line, the section ends with a one-line note saying so in place of the
  code block.
  Every other sink and scenario renders as usual.

### Where the source comes from

The Markdown sink renders from the report model, not from the JSON file: at session finish the
plugin builds the report dict, and `emit_sinks` parses it and renders every configured sink from
the result. The source is not added to the report dict. It never reaches the JSON, and the report
schema does not change.

Instead, the renderer reads the test files from disk, as the HTML renderer's source links already
resolve against `SinkConfig.source_root`, the rootdir of a live run:

- `SinkConfig` gains `md_source: bool`.
- When it is set, the sink step reads each scenario's file from `source_root / source.relpath`,
  once per file, and extracts its function, and `render_md` takes the excerpts as a parameter.
  `render_md` stays a pure function of its inputs, and reading files stays outside it, in a
  sibling of `source_link.py`. The sink step still writes nothing before every sink has
  rendered.
- The files are read at session finish, so the source is the code that just ran, unless a file
  changed during the run.

### Flag

- **`--given-md-source`, flag only, off by default.** No ini setting: the source is for one review
  run, and a project that committed its Markdown with the source would see every body change in
  its report diffs.
- **Inert without a Markdown sink**, like `--given-md-lines` on a run that writes no Markdown.
- **Plugin only.** `pytest-given report` re-renders a saved JSON report, which carries neither the
  source nor a `source_root`, so it does not offer the flag.

### Not affected

- **Narrated citations.** Their body is `narration_body_md`, the steps and the parameter table.
  The source block is added in the scenario section, not in that body, so a citation never
  carries it.
- **The JSON and HTML sinks.** Neither changes.

## Skills and documentation

- **Reviewing skill:** `pairs.md` is replaced by the flag. Layer 2 renders
  `pytest <test file> --given-md=<file> --given-md-source` once per test file and hands each file
  to a reviewer, which also splits the audit. The script, its "Run it from the rootdir" note and
  `tests/unit/test_skills_scripts.py`, which tests only that script, go, and so does the
  sentence in `AGENTS.md` that names it. The notes under "Reading the dump" that
  still hold move into the reviewing `SKILL.md`: step fixtures, module-level values, one file per
  reviewer.
- **Navigating skill:** "When to go to the code" names the flag for reading a scenario's
  narration beside its body.
- **Site:** a `--given-md-source` row in `docs/site/configuration/pytest-options.md`.
- **CHANGELOG:** one entry under `[Unreleased]`, `Added`.
- **Self-report:** one scenario stating the rule, a run with the flag whose Markdown shows the
  test function below its narration.

## Cost

One run per test file instead of one run of the whole suite costs pytest's startup and collection
each time. On this repository's 26 test files with scenarios, the scenario runs took 10.8 s in
total, against 6.0 s for one run. The per-file runs can go in parallel.

## Left to the builder

- The note's wording for source that can't be read, and the module and type names for the excerpt.
- The width and alignment of the line-number prefix.
- How the file is decoded: as UTF-8, or with the encoding detection `tokenize` uses.
