# Standalone CLI

## Report

`pytest-given report` renders the HTML or Markdown report from a saved JSON file at any time:

```bash
pytest-given report path/to/report-data.json -o path/to/report.html \
    --source-link=vscode
```

The CLI takes its settings from flags only, never from your pytest config, and imports none of your code. So it also runs without installing: `uvx pytest-given@<version> report …`, pinned to the version that wrote the JSON file.

| Option | Default | Description |
|--------|---------|-------------|
| `JSON_FILE` | `given-report/report-data.json` | The JSON report to render. The default is where a bare `--given-json` writes it. |
| `-o PATH` | `given-report/report.html`, stdout for Markdown | The output file. A `.md` or `.markdown` name implies `--format md`. |
| `--format html\|md` | `html` | The output format. Markdown printed to stdout has no `<!-- pytest-given:md:start -->` markers. The plugin adds them only to separate the report from pytest's own output. |
| `--source-link=PRESET` | `none` | The same presets and URL templates as `--given-source-link` (see [Source links](configuration/source-links.md)). With `none`, file:line is shown as plain text. With `--format md`, the option is checked but has no effect. |
| `--theme=light\|dark\|auto` | `auto` | The theme the report opens in, like `--given-theme`. |
| `--report-url=URL` | the URL in the JSON file | The URL the citations copied from the report link to, like `--given-report-url`. Render a report this way for each place it is served from. |
| `--no-lines` | off | Leave the line out of each Markdown scenario anchor, like `--no-given-md-lines`. Render both sides of a diff this way. |
| `--glossary-only` | off | Render an HTML report with only the Glossary tab, for readers who need the vocabulary and not the tests. Scenarios, stories, each term's *Other forms* list and the citation copy menus are left out. The JSON file is not changed. |

`pytest-given report` exits 2 when:

- it cannot read the JSON file, or cannot render or write the report.
- an option value is invalid, such as an unknown `--theme` or `--source-link` preset, or a `--report-url` that is not an absolute http(s) URL.
- `--glossary-only` comes with Markdown output or a `--report-url`, or the report has no glossary terms.
- the report is malformed. The message names the path and reason of each problem.
- the report is of another schema version. One line says to regenerate it. That includes every report written by pytest-given 0.6.0 or earlier.

## Citations

`pytest-given citations check` verifies every link into the report in a set of Markdown files against a JSON report, and `citations update` rewrites the [citations](guide/citations.md) among them to match it:

```bash
pytest-given citations check docs/specs/ README.md \
    [--report PATH] [--report-url URL] [--report-path PATH]
pytest-given citations update …   # same arguments
```

A directory is searched recursively for `*.md`. Neither command runs tests: both read the JSON report of an earlier run, which must hold every scenario a document may cite (`pytest -m pytest_given --given-json`). `--report` defaults to `given-report/report-data.json`, where a bare `--given-json` writes it. `--report-url` defaults to the URL stored in the report (`--given-report-url`); `--report-path` names where the HTML report sits in the repository once your docs build has placed it, so relative links to it are read too.

`check` writes nothing and exits 1 on any citation finding; `update` exits 1 when a citation finding remains that it cannot fix, such as a target no longer in the report. Both exit 2, writing nothing, when the report or a document cannot be read, when neither a report URL nor a report path is known, or when no document links the report, as a mistyped URL or path would otherwise pass every document. A malformed report and a report of another schema version count as unreadable.

`check` takes two more options, which leave its summary and exit code as they are:

- `--list` prints every report link on a line of its own, `path:line: glyph kind key` (`link` in place of the glyph for a plain report link), with its citation findings indented under it.
- `--covering NODE_ID` narrows that list to the links that [may cite the scenario](guide/citations.md#finding-the-citations-of-a-scenario), and implies `--list`. Repeat it for several scenarios. A test function's node ID covers each of its scenarios, one per case under `group_parametrized=False`. It exits 2 when the report holds no scenario of that node ID.

## Delta

`pytest-given delta` builds a [delta report](delta-report.md) from two JSON reports, or re-renders the HTML of a delta JSON:

```bash
pytest-given delta before.json after.json [--json PATH] [--html PATH] \
    [--renames PATH] [--before-label LABEL] [--after-label LABEL] \
    [--title TITLE] [--source-link PRESET] [--theme light|dark|auto]
pytest-given delta given-report/delta-data.json [--html PATH]
```

- `--json` and `--html` name the delta JSON and HTML paths. With neither, two inputs write `given-report/delta-data.json` and `given-report/delta.html`, and one input writes the HTML. With only one of them, only that file is written.
- `--renames` names the [rename log](delta-report.md#the-rename-log). It defaults to `given-renames.toml` in the working directory, when that exists.
- `--before-label` and `--after-label` set the version label of each side. They default to the git tag on that side's commit.
- `--title` sets the delta's title, kept in its JSON. It defaults to the after report's title.
- `--source-link` and `--theme` work as for `report`. The source link defaults to none.

One input only re-renders, so `--json`, `--renames`, `--before-label`, `--after-label` and `--title` with one input are refused. Run the command from your current checkout, so it reads the current rename log.

It prints a summary of the counts and exits 0 whether or not anything changed. It exits 2 when it cannot build the delta:

- a report is not of the schema version of the pytest-given that compares it. That includes a report from a pytest-given that predates the schema version, so regenerate it.
- a delta JSON is of another delta schema version.
- a report is given where a delta JSON is expected, or the reverse.
- a report or delta JSON is malformed. The message names the path and reason of each problem.
- the rename log is malformed.

## Coverage

`pytest-given coverage` prints the [story coverage](guide/domain-storytelling.md#coverage-in-the-report) of a JSON report, as the Stories tab shows it:

```bash
pytest-given coverage [path/to/report-data.json]
```

It prints a JSON array to stdout, one record per sentence in story then sentence order: `story_id`, `sentence_id`, `tracked` (false for a sentence narration matching never reaches) and `scenario_ids`. The report defaults to `given-report/report-data.json`, where a bare `--given-json` writes it.

It exits 1 when a tracked sentence has no scenario, and says on stderr how many. It exits 2 when it cannot read the report, under the same rules as `report`.

## Skills

`pytest-given skills install` installs the bundled agent skills. See [Agent skills](ai-agents.md#agent-skills) for its options.

## Exit status

Every subcommand uses the same codes, so a script can branch on the code alone:

- `0` means there is nothing to act on. The command succeeded, and every citation or skill is current.
- `1` means something to act on. A citation finding remains, a tracked sentence has no scenario, or `skills install --check` finds drift. Fix it and run again.
- `2` means the command could not do its job. A file could not be read or written, or a flag value was refused. The message goes to stderr.

`report`, `delta` and a plain `skills install` never exit 1, since none reports findings.

When `report` or `delta` exits 2, it leaves no output behind that could pass for current.
