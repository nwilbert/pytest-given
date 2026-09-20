# pytest options

All report outputs are opt-in — a bare `pytest` writes nothing. Each `--given-*` flag enables its own sink independently, and they combine freely (e.g. pass both `--given-json` and `--given-html` to get both files from one run).

The *checks* are not opt-in. Every run builds the report it would have written, so an authoring form that cannot be narrated honestly — the [parametrize rules](../guide/parametrized.md) among them — fails the run whether or not a sink was configured, rather than surfacing on the first run that happens to ask for HTML.

| Flag | Default | Description |
|------|---------|-------------|
| `--given-json[=PATH]` | off | Write JSON report data (bare → `given-report/report-data.json`). |
| `--given-html[=PATH]` | off | Write the HTML report (bare → `given-report/report.html`). |
| `--given-md[=PATH]` | off | Write the Markdown report; **bare renders to stdout**, between `<!-- pytest-given:md:start -->` and `<!-- pytest-given:md:end -->` markers. |
| `--given-title=TEXT` | rootdir name | Name the report, shown as the Markdown heading and the HTML tab title and topbar. Also settable as the `given_title` ini. |
| `--given-source-link=PRESET` | `none` | Editor preset (`vscode`, `cursor`, `zed`, `pycharm`, `github`) or raw URL template, **HTML only**. Renders a clickable file:line anchor on each scenario card, story panel, and expanded glossary term card. Also settable as the `given_source_link` ini. See [Source links](source-links.md). |
| `--given-all-frames` | off | Keep internal `pluggy`/`_pytest`/pytest-given frames in failure tracebacks. See [Traceback frames](source-links.md#traceback-frames). |
| `--given-lint` / `--no-given-lint` | `false` | Run the narration lint; an error-level finding fails the run. Also settable as the `given_lint` ini, which either form overrides. See [Narration lint](narration-lint.md). |
| `--given-theme=light\|dark\|auto` | `auto` | Theme the HTML report opens in; `auto` follows the viewer's system. The report's own Light / Dark / System control overrides it per browser. Also settable as the `given_theme` ini. |

Put a bare `--given-json` / `--given-html` / `--given-md` **last** on the command line, or use the `=PATH` form (`--given-html=out.html`, not `--given-html out.html`) — argparse treats a path token right after a bare flag as that flag's value, not a test selection. A path that could not be a report file (a `.py` test path, say) is refused before the suite runs rather than written over.

**Not compatible with `pytest-xdist`.** Under `-n`, tests run in worker processes whose recordings never reach the controller: the run passes and the report comes out empty. Generate reports from a non-distributed run.

The ini settings live in `[tool.pytest]`, pytest 9's native TOML table. The legacy `[tool.pytest.ini_options]` is still read, but the two are mutually exclusive — pytest raises `UsageError` if both are present.

