# Source links & tracebacks

## Source links

Add a clickable file:line anchor to each scenario card, story panel, and expanded glossary term card so devs can jump straight to the source. Source links are an HTML-report feature: a run writing no HTML ignores the setting entirely — it isn't even validated there, so a mistyped preset surfaces only on a `--given-html` run.

```toml
# pyproject.toml — pytest 9+ canonical form
[tool.pytest]
given_source_link = "vscode"
```

Or pass it on the CLI: `pytest --given-html --given-source-link=vscode`.

| Preset    | Opens in     | Template                                                                              |
|-----------|--------------|----------------------------------------------------------------------------------------|
| `none`    | (no link)    | —                                                                                      |
| `vscode`  | VS Code      | `vscode://file/{path}:{line}`                                                          |
| `cursor`  | Cursor       | `cursor://file/{path}:{line}`                                                          |
| `zed`     | Zed          | `zed://file/{path}:{line}`                                                             |
| `pycharm` | PyCharm      | `pycharm://open?file={path}&line={line}`                                               |
| `github`  | GitHub (web) | `https://github.com/<org>/<repo>/blob/{sha}/{relpath}#L{line}` — `<org>/<repo>` auto-detected from `GITHUB_REPOSITORY` or `git remote get-url origin` (HTTPS and SSH forms both supported) |

For a raw template, use any of these variables:

| Variable     | Source                                                                                                   |
|--------------|----------------------------------------------------------------------------------------------------------|
| `{path}`     | Absolute POSIX path (resolved at render time against the cwd)                                            |
| `{relpath}`  | POSIX path relative to pytest's rootdir                                                                  |
| `{line}`     | 1-indexed line of the scenario's `def`                                                                   |
| `{project}`  | Basename of pytest's rootdir                                                                             |
| `{sha}`      | Commit SHA from `GITHUB_SHA` / `CI_COMMIT_SHA` / `BUILDKITE_COMMIT`, falling back to `git rev-parse HEAD` |

For CI archives, `given_source_link = "github"` gives SHA-pinned permalinks. Spell the same thing as a raw template when `origin` is a mirror, a fork, or a remote the preset cannot parse: `"https://github.com/myorg/myrepo/blob/{sha}/{relpath}#L{line}"`.

Caveats:

- Editor presets (`vscode` / `cursor` / `zed`) resolve `{path}` from the current working directory at render time. Re-rendering a CI-downloaded JSON from a different directory will produce broken links.
- The GitHub-permalink template is SHA-pinned, so links remain stable after the line moves — what an archived CI report wants.

## Traceback frames

When a scenario fails, its traceback is captured into the report. By default only your own frames are kept — the `pluggy` dispatcher, the `_pytest` runner, and pytest-given's own step-recording frames are dropped, since they're implementation noise you rarely need. Dropping them before they are formatted also keeps large failing suites fast: pytest's per-frame source analysis is the dominant cost when many scenarios fail.

Pass `--given-all-frames` to retain every frame (each stored with an `is_internal` flag; the HTML report then shows a **"Show internal frames"** toggle on each failure). It's a debugging escape hatch for troubleshooting the plugin or pytest itself, and it re-introduces that per-frame cost.

Skipped scenarios never capture a traceback at all — they carry their skip reason instead.

