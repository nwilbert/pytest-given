# Standalone CLI

Regenerate the HTML from a saved JSON file at any time:

```bash
pytest-given report path/to/report-data.json -o path/to/report.html \
    --source-link=vscode
```

The CLI takes its settings from flags only, never from your pytest config, and imports none of your code, so it also runs without installing: `uvx pytest-given@<version> report …`, pinned to the version that wrote the JSON file.

`--source-link` takes the same presets and URL templates as `--given-source-link` (see [Source links](configuration/source-links.md)). Without it (or with `--source-link=none`), file:line is shown as plain text, without a link. With `--format md`, the option is checked but has no effect.

`--theme=light|dark|auto` sets the theme the report opens in, like `--given-theme`. The default is `auto`.

Pass `--format md` to get Markdown instead of HTML. You can also just use a `.md` or `.markdown` file name: `-o report.md` needs no `--format`.

`--no-lines` leaves the line out of each Markdown scenario anchor, like `--no-given-md-lines`. Render both sides of a diff this way.

With `--format md` and no `-o`, the Markdown is printed to stdout. Unlike the pytest plugin's output, it has no `<!-- pytest-given:md:start -->` markers; the plugin only adds them to separate the report from pytest's own output.

The same command also installs the agent skills with `pytest-given skills install`; see [Agent skills](ai-agents.md#agent-skills).

