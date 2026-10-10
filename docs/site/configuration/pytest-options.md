# pytest options

A plain `pytest` run writes no report. Each `--given-*` output flag turns on one report format, and you can combine them. For example, pass both `--given-json` and `--given-html` to get both files from one run.

The checks, however, always run. Every run builds the report, even if it doesn't write it. So a step that can't be reported correctly, like one that breaks the [parametrize rules](../guide/parametrized.md#rejected-authoring-forms), fails every run, not just the first run that writes a report.

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--given-json[=PATH]` | off | Write the JSON report data. Without a path: `given-report/report-data.json`. |
| `--given-html[=PATH]` | off | Write the HTML report. Without a path: `given-report/report.html`. |
| `--given-md[=PATH]` | off | Write the Markdown report. **Without a path, it prints to stdout**, between `<!-- pytest-given:md:start -->` and `<!-- pytest-given:md:end -->` markers. |
| `--given-title=TEXT` | rootdir name | The report's name: the Markdown heading, and the HTML report's browser tab title and top bar. Ini setting: `given_title`. |
| `--given-source-link=PRESET` | `none` | An editor preset (`vscode`, `cursor`, `zed`, `pycharm`, `github`) or a URL template. **HTML only.** Adds a clickable file:line link to each scenario card, story panel, and expanded glossary term. Ini setting: `given_source_link`. See [Source links](source-links.md). |
| `--given-all-frames` | off | Keep pytest's and pytest-given's internal frames (`pluggy`, `_pytest`, pytest-given) in failure tracebacks. See [Traceback frames](source-links.md#traceback-frames). |
| `--given-lint` / `--no-given-lint` | `false` | Turn the narration lint on or off. A finding with severity `error` fails the run. Ini setting: `given_lint`; both flags override it. See [Narration lint](narration-lint.md). |
| `--given-theme=light\|dark\|auto` | `auto` | The theme the HTML report opens in. `auto` follows the viewer's system setting. The report's own Light / Dark / System switch overrides it in each browser. Ini setting: `given_theme`. |

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

Mind `-k`: it matches any part of a test's keywords, and a scenario's include `pytest_given` and `_scenario`, so `-k given` or `-k scenario` selects every scenario too.

## pytest-xdist

**pytest-given doesn't work with `pytest-xdist`.** With `-n`, tests run in worker processes, and their steps never reach the main process. The run passes, but the report is empty. Generate reports from a run without `-n`.

## Ini settings

Put ini settings in `[tool.pytest]` in `pyproject.toml` (pytest 9's native TOML table). pytest still reads the older `[tool.pytest.ini_options]`, but you can't use both: pytest raises `UsageError` if both are present.
