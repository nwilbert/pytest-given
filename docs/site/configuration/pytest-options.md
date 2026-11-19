# pytest options

A plain `pytest` run writes no report. Each `--given-*` output flag turns on one report format, and you can combine them. For example, pass both `--given-json` and `--given-html` to get both files from one run.

The checks, however, always run. Every run builds the report, even if it doesn't write it. So a step that can't be reported correctly, like one that breaks the [parametrize rules](../guide/parametrized.md#rejected-authoring-forms), fails every run, not just the first run that writes a report.

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--given-json[=PATH]` | off | Write the JSON report data. Without a path: `given-report/report-data.json`. The [standalone CLI](../cli.md) renders HTML or Markdown from it later, without running the tests. |
| `--given-html[=PATH]` | off | Write the HTML report. Without a path: `given-report/report.html`. |
| `--given-md[=PATH]` | off | Write the [Markdown report](../markdown-report.md). **Without a path, it prints to stdout**, between `<!-- pytest-given:md:start -->` and `<!-- pytest-given:md:end -->` markers. |
| `--given-md-lines` / `--no-given-md-lines` | `true` | Show the line in the `file.py:line::test_name` anchor under each Markdown heading. Off, the anchor is the node ID, so a Markdown diff doesn't show every anchor below an inserted test. |
| `--given-md-source` | off | End each Markdown scenario with its test function, decorators included, each line under its number in the file, for reviewing step text against step body. Only the test function is shown, not the step fixtures or helpers it uses. |
| `--given-title=TEXT` | rootdir name | The report's name: the Markdown heading, and the HTML report's browser tab title and top bar. |
| `--given-report-url=URL` | unset | The public URL the HTML report will be served from, such as its page on your docs site. The report then shows copy buttons that put a Markdown [citation](../guide/citations.md) linking there on the clipboard, and `pytest-given citations` checks links to it. |
| `--given-source-link=PRESET` | `none` | An editor preset (`vscode`, `cursor`, `zed`, `pycharm`, `github`) or a URL template. **HTML only.** Adds a clickable file:line link to each scenario card, story panel, and expanded glossary term. See [Source links](source-links.md). |
| `--given-all-frames` | off | Keep pytest's and pytest-given's internal frames (`pluggy`, `_pytest`, pytest-given) in failure tracebacks. See [Traceback frames](source-links.md#traceback-frames). |
| `--given-lint` / `--no-given-lint` | `false` | Turn the narration lint on or off. A lint finding with severity `error` fails the run. See [Narration lint](narration-lint.md). |
| `--given-theme=light\|dark\|auto` | `auto` | The theme the HTML report opens in. `auto` follows the viewer's system setting. The report's own Light / Dark / System switch overrides it in each browser. |

## Configuration file

Put settings in `[tool.pytest]` in `pyproject.toml` (pytest 9's native TOML table). pytest still reads the older `[tool.pytest.ini_options]`, but you can't use both: pytest raises `UsageError` if both are present.

| Setting | Type | Flag |
|---------|------|------|
| `given_title` | string | `--given-title` |
| `given_report_url` | string | `--given-report-url` |
| `given_source_link` | string | `--given-source-link` |
| `given_theme` | string | `--given-theme` |
| `given_md_lines` | boolean | `--given-md-lines` / `--no-given-md-lines` |
| `given_lint` | boolean | `--given-lint` / `--no-given-lint` |
| `given_lint_rules` | array of strings | none, see [Narration lint](narration-lint.md#configuration) |
| `given_lint_ignore` | array of strings | none, see [Narration lint](narration-lint.md#configuration) |

Each setting takes the values its flag does and has the same default. A flag overrides its setting for one run.

```toml
[tool.pytest]
given_title = "Coffeeshop"
given_source_link = "vscode"
given_lint = true
```

The other flags have no setting. To pass one on every run, add it to pytest's `addopts` setting, which adds its flags to every run's command line:

```toml
[tool.pytest]
addopts = ["--given-html"]
```

## Flag order

If an output flag has no `=PATH`, pytest reads the next word on the command line as its path, not as a test to run. To avoid this, either:

- put `--given-json`, `--given-html` or `--given-md` **last** on the command line, or
- use the `=PATH` form: `--given-html=out.html`, not `--given-html out.html`.

If that path can't be a report file, like a `.py` test file, pytest-given stops before running the tests, so it never overwrites your test.

## Selecting scenarios

pytest-given marks every `@scenario` test, each case of a parametrized one included, with the `pytest_given` marker. You don't apply it yourself: a hand-written `@pytest.mark.pytest_given` on a plain test makes it selectable, but records nothing. The marker is registered, so `--strict-markers` accepts it. Select with pytest's own `-m`:

- **A report without running the plain tests.** The report holds only scenarios, so `pytest -m pytest_given --given-html` writes the same report as a full run, faster.
- **Code coverage of the scenarios.** `pytest -m pytest_given --cov=mypkg` (with pytest-cov), or `coverage run -m pytest -m pytest_given`. It counts the lines the scenarios *run*, not the lines a step *describes*, so it is an upper bound on what the report documents. Compare it with a full run's coverage: lines the suite covers but the scenarios don't are behavior only plain tests reach, and the report doesn't show.
- **The plain tests alone**, with `pytest -m "not pytest_given"`.

A `-m` on the command line replaces one in your `addopts`, so combine them yourself: `-m "pytest_given and not slow"`. In a suite with no scenarios, `-m pytest_given` deselects every test and pytest exits with code 5.

Mind `-k`: `-k given` and `-k scenario` select every scenario too, because a scenario's keywords include those words.

## pytest-xdist

**pytest-given writes reports and runs the narration lint under `pytest-xdist` with `--dist loadfile`.** Grouping a parametrized scenario needs all its cases on one worker, and `loadfile` sends each file to one worker.

When a `-n` run asks for a report (`--given-json`, `--given-html`, `--given-md`) or the narration lint:

- a bare `-n` becomes `--dist loadfile`.
- any other `--dist` or `-d`, including one in `addopts`, stops the run with a usage error.
- a crashed worker fails the run, and no report is written.
- a run interrupted before every worker reported keeps the previous report.

Without a report or the lint, `--dist` is left alone.

## JSON schema

The JSON report follows a published [JSON Schema](../schemas/report-v1.schema.json). Every report names it under a top-level `$schema` key, so an editor can validate and complete the file. `metadata.schema_version` holds the report's version. pytest-given reads only reports of its own version. `pytest-given report`, `citations`, `coverage` and `delta` refuse any other with one line saying to regenerate it.
