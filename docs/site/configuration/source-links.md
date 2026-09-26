# Source links & tracebacks

## Source links

Source links add a clickable file:line link to each scenario card, story panel, and expanded glossary term, so you can jump straight to the code.

Source links only exist in the HTML report. A run that writes no HTML ignores the setting completely and doesn't even check it, so a typo in the preset only shows up when you run with `--given-html`.

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

For your own URL template, use any of these variables:

| Variable     | Source                                                                                                   |
|--------------|----------------------------------------------------------------------------------------------------------|
| `{path}`     | Absolute POSIX path (resolved at render time against the cwd)                                            |
| `{relpath}`  | POSIX path relative to pytest's rootdir                                                                  |
| `{line}`     | 1-indexed line of the scenario's `def`                                                                   |
| `{project}`  | Basename of pytest's rootdir                                                                             |
| `{sha}`      | Commit SHA from `GITHUB_SHA` / `CI_COMMIT_SHA` / `BUILDKITE_COMMIT`, falling back to `git rev-parse HEAD` |

For reports archived in CI, `given_source_link = "github"` links to the exact commit. If `origin` is a mirror, a fork, or a remote the preset can't read, write the same link as a template: `"https://github.com/myorg/myrepo/blob/{sha}/{relpath}#L{line}"`.

Caveats:

- Editor presets (`vscode`, `cursor`, `zed`) build `{path}` from the current working directory when the report is rendered. If you download a JSON report from CI and render it in a different directory, the links break.
- GitHub links point to a specific commit, so they keep working after the code moves. That's what an archived CI report needs.

## Traceback frames

When a scenario fails, the report shows its traceback. By default, it only keeps frames from your own code. Frames from `pluggy`, pytest's runner (`_pytest`), and pytest-given itself are dropped, because you rarely need them.

Dropping them early also keeps the report fast when many scenarios fail: pytest's analysis of each frame is the slowest part of building the report then.

Pass `--given-all-frames` to keep every frame. Each frame is then stored with an `is_internal` flag, and the HTML report shows a **Show internal frames** toggle on each failure. Use it to debug pytest-given or pytest itself; it makes reports with many failures slower again.

Skipped scenarios have no traceback. The report shows their skip reason instead.

