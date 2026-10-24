# Standalone CLI

Regenerate the HTML from a saved JSON file at any time:

```bash
pytest-given report path/to/report-data.json -o path/to/report.html \
    --source-link=vscode
```

Without a JSON file it reads `given-report/report-data.json`, where a bare `--given-json` writes it.

The CLI takes its settings from flags only, never from your pytest config, and imports none of your code, so it also runs without installing: `uvx pytest-given@<version> report …`, pinned to the version that wrote the JSON file.

`--source-link` takes the same presets and URL templates as `--given-source-link` (see [Source links](configuration/source-links.md)). Without it (or with `--source-link=none`), file:line is shown as plain text, without a link. With `--format md`, the option is checked but has no effect.

`--theme=light|dark|auto` sets the theme the report opens in, like `--given-theme`. The default is `auto`.

`--report-url` sets the URL the citations copied from the report link to, like `--given-report-url`, in place of the one stored in the JSON file: render a report this way for each place it is served from.

Pass `--format md` to get Markdown instead of HTML. You can also just use a `.md` or `.markdown` file name: `-o report.md` needs no `--format`.

`--no-lines` leaves the line out of each Markdown scenario anchor, like `--no-given-md-lines`. Render both sides of a diff this way.

With `--format md` and no `-o`, the Markdown is printed to stdout. Unlike the pytest plugin's output, it has no `<!-- pytest-given:md:start -->` markers; the plugin only adds them to separate the report from pytest's own output.

## Citations

`pytest-given citations check` verifies every link into the report in a set of Markdown files against a JSON report, and `citations update` rewrites the [citations](guide/citations.md) among them to match it:

```bash
pytest-given citations check docs/specs/ README.md \
    [--report PATH] [--report-url URL] [--report-path PATH]
pytest-given citations update …   # same arguments
```

A directory is searched recursively for `*.md`. Neither command runs tests: both read the JSON report of an earlier run, which must hold every scenario a document may cite (`pytest -m pytest_given --given-json`). `--report` defaults to `given-report/report-data.json`, where a bare `--given-json` writes it. `--report-url` defaults to the URL stored in the report (`--given-report-url`); `--report-path` names where the HTML report sits in the repository once your docs build has placed it, so relative links to it are read too.

`check` writes nothing and exits 1 on any citation finding; `update` exits 1 when a citation finding remains that it cannot fix, such as a target no longer in the report. Both exit 2, writing nothing, when the report or a document cannot be read, when neither a report URL nor a report path is known, or when no document links the report, as a mistyped URL or path would otherwise pass every document.

`check` takes two more options, which leave its summary and exit code as they are:

- `--list` prints every report link on a line of its own, `path:line: glyph kind key` (`link` in place of the glyph for a plain report link), with its citation findings indented under it.
- `--covering NODE_ID` narrows that list to the links that [may cite the scenario](guide/citations.md#finding-the-citations-of-a-scenario), and implies `--list`. Repeat it for several scenarios. A test function's node ID covers each of its scenarios, one per case under `group_parametrized=False`. It exits 2 when the report holds no scenario of that node ID.

The same command also installs the agent skills with `pytest-given skills install`; see [Agent skills](ai-agents.md#agent-skills).

