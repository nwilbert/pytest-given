# Standalone CLI

Regenerate the HTML from a saved JSON file at any time:

```bash
pytest-given report path/to/report-data.json -o path/to/report.html \
    --source-link=vscode
```

`--source-link` accepts the same presets and raw templates as `--given-source-link` (see [Source links](configuration/source-links.md)); omit it (or pass `--source-link=none`) to render plain file:line text without an anchor. On a `--format md` run it is validated but unused.

`--theme=light|dark|auto` sets the theme the report opens in, like `--given-theme` (default `auto`).

Pass `--format md` for Markdown instead of HTML; it is also inferred from the `-o` extension, so `-o report.md` needs no `--format`. Omit `-o` with `--format md` to print to stdout — bare, unlike the plugin's `--given-md=-`, which fences its output in `<!-- pytest-given:md:start -->` markers so it can be found in pytest's mixed output.

The same script owns `skills install` — see [Agent skills](ai-agents.md#agent-skills).

