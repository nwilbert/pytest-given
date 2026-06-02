# Source Link — Design

## Goal

Let devs jump from a scenario in the HTML report straight to the test source in their editor (VSCode, Cursor, Zed, PyCharm), and let CI archives link to GitHub permalinks. One config option, sensible presets, raw-template escape hatch for anything else.

## Background

Today the report shows the scenario narration, steps, parameters, status, duration — but no way to navigate from the report back to the test code. Devs viewing the report locally have to manually find the test file. CI archives have no link to the source on GitHub either.

Modern editors register URL handlers (`vscode://`, `cursor://`, `zed://`, `pycharm://`) that open a file at a specific line when a browser follows that URL. GitHub permalinks (`https://github.com/<org>/<repo>/blob/<sha>/<path>#L<line>`) provide the same affordance for archived reports.

## User-facing API

A single ini/CLI option, `given_source_link`, accepting either a preset name or a raw template string.

```toml
# pyproject.toml (pytest 9+ canonical form)
[tool.pytest]
given_source_link = "vscode"
```

```bash
# CLI override (plugin and standalone renderer)
pytest --given-html --given-source-link=vscode
pytest-given report report-data.json -o report.html --source-link=vscode
```

Resolution order: CLI flag → ini value → default `"none"`.

### Presets

| Preset    | Expanded template                                                                              |
|-----------|------------------------------------------------------------------------------------------------|
| `none`    | (no link — render plain `relpath:line`)                                                        |
| `vscode`  | `vscode://file/{path}:{line}`                                                                  |
| `cursor`  | `cursor://file/{path}:{line}`                                                                  |
| `zed`     | `zed://file/{path}:{line}`                                                                     |
| `pycharm` | `pycharm://open?file={path}&line={line}`                                                       |
| `github`  | `https://github.com/<org>/<repo>/blob/{sha}/{relpath}#L{line}` — `<org>/<repo>` auto-detected (see below) |

The `github` preset is the canonical choice for CI-archived reports: it produces SHA-pinned permalinks without the user having to hardcode org/repo in their config. `<org>/<repo>` is detected once at config-resolution time in this order:

1. `GITHUB_REPOSITORY` env var (set by GitHub Actions, format `org/repo`).
2. `git remote get-url origin`, parsed for both forms:
   - HTTPS: `https://github.com/<org>/<repo>(.git)?`
   - SSH:   `git@github.com:<org>/<repo>(.git)?`

If neither yields a GitHub remote, `resolve_template` raises `PytestGivenError` pointing the user at the raw-template form (the example in the README). The detected `org/repo` is baked into the returned template — no new `{org}`/`{repo}` variables are exposed.

### Template variables

| Variable     | Source                                                          | Notes                                                  |
|--------------|-----------------------------------------------------------------|--------------------------------------------------------|
| `{relpath}`  | `scenario.source.relpath`                                       | POSIX-normalized, relative to pytest rootdir           |
| `{line}`     | `scenario.source.line`                                          | 1-indexed                                              |
| `{project}`  | `metadata.project`                                              | Basename of pytest rootdir                             |
| `{sha}`      | `metadata.commit_sha`                                           | From `GITHUB_SHA` / `CI_COMMIT_SHA` / `BUILDKITE_COMMIT` env vars, falling back to `git rev-parse HEAD`. `None` if unavailable. |
| `{path}`     | `(Path.cwd() / scenario.source.relpath).resolve().as_posix()`   | Computed at render time, never stored                  |

### Worked examples for the README

```toml
# PyCharm preset — uses the pycharm:// scheme registered by PyCharm.app
[tool.pytest]
given_source_link = "pycharm"

# Zed (raw template; no preset would differ here, but shown for symmetry):
given_source_link = "zed://file/{path}:{line}"

# CI archives → GitHub permalinks (auto-detects org/repo from git remote
# or GITHUB_REPOSITORY env var):
given_source_link = "github"

# Same thing as a raw template — pin org/repo explicitly. Useful when the
# remote is non-standard (mirrored repo, monorepo subdirectory, fork URL):
given_source_link = "https://github.com/myorg/myrepo/blob/{sha}/{relpath}#L{line}"
```

### Caveats documented in README

- VSCode / Cursor / Zed / PyCharm presets resolve `{path}` from the render-time current working directory; re-rendering a CI-downloaded JSON from the wrong directory will produce broken links.
- The `pycharm` preset uses the direct `pycharm://open` scheme registered by `PyCharm.app`, not the Toolbox `jetbrains://pycharm/navigate/reference?...` URL. The Toolbox URL is theoretically more flexible (specifies project + relpath, doesn't depend on a `pycharm://` handler being claimed by a specific IDE), but in practice the Toolbox-managed PyCharm Professional install on macOS rejects it with `launch method not available` — see [JetBrains support thread](https://intellij-support.jetbrains.com/hc/en-us/community/posts/21787338788882). The direct scheme works for both Community and Professional, but if multiple JetBrains IDEs are installed, `pycharm://` resolves to whichever one most recently registered the handler.
- The GitHub-permalink template is SHA-pinned, so links remain stable after the line moves — exactly what an archived CI report wants.
- The `github` preset is resolved at config-resolution time (session start / CLI invocation), not at render time. If the JSON is re-rendered later from a different machine, the org/repo baked in is the one detected on the original run — usually what you want for CI archives.
- Pytest 9+ uses `[tool.pytest]`; older pytest used `[tool.pytest.ini_options]` (still accepted by pytest 9 for back-compat).

## Data model changes

### `model.py`

```python
@dataclass(frozen=True)
class SourceLocation:
    relpath: str   # POSIX-normalized, relative to pytest rootdir
    line: int     # 1-indexed

@dataclass
class Scenario:
    ...
    source: SourceLocation | None = None  # new

@dataclass
class Metadata:
    project: str           # unchanged
    timestamp: str         # unchanged
    pytest_version: str    # unchanged
    plugin_version: str    # unchanged
    commit_sha: str | None = None  # new
```

`SourceLocation` is stored at the *scenario* level only (not per step) — the test function is the navigation target the dev wants. Parametrized scenarios share one `SourceLocation` (the test function); `_group_parameterized` carries `first.source` through unchanged.

`rootdir` is **not** stored: it's the only field that would leak a local username path, and it's only needed to compute `{path}`, which is render-time-only.

### `template.py` (new module section or new file `source_link.py`)

```python
type SourceLinkPreset = Literal['vscode', 'cursor', 'zed', 'pycharm', 'github']

_STATIC_PRESETS: dict[str, str] = {
    'vscode':  'vscode://file/{path}:{line}',
    'cursor':  'cursor://file/{path}:{line}',
    'zed':     'zed://file/{path}:{line}',
    'pycharm': 'pycharm://open?file={path}&line={line}',
}

_VALID_VARS = frozenset({'path', 'relpath', 'line', 'project', 'sha'})

def resolve_template(value: str) -> str | None:
    """Resolve a config value into a template string (or None for 'none').

    Static presets ('vscode' / 'cursor' / 'zed' / 'pycharm') map directly.
    The 'github' preset detects org/repo (GITHUB_REPOSITORY env, then
    `git remote get-url origin`) and bakes them into a permalink template.

    Raises PytestGivenError for unknown presets, malformed input, or a
    'github' preset that can't resolve org/repo.
    """

def _detect_github_repo() -> tuple[str, str] | None:
    """Return (org, repo) from GITHUB_REPOSITORY env or `git remote get-url
    origin`, parsing both HTTPS and SSH GitHub URL forms. None if neither
    yields a recognisable GitHub remote."""

def format_source_link(
    template: str,
    *,
    source: SourceLocation,
    project: str,
    commit_sha: str | None,
) -> str:
    """Substitute template variables. Raises PytestGivenError if the template
    references {sha} when commit_sha is None, or any unknown variable."""
```

## Capture flow

### Plugin (`plugin.py`)

In `pytest_runtest_setup`, after `start_scenario` is called:

```python
relpath_raw, lineno0, _ = item.location  # pytest: (relfspath, 0-indexed line, name)
source = SourceLocation(
    relpath=PurePath(relpath_raw).as_posix(),  # PurePath(...).as_posix() normalizes
    line=lineno0 + 1,                           # editors and GitHub expect 1-indexed
)                                               # back- to forward-slashes on Windows;
                                                # PurePosixPath does NOT.
collector.set_scenario_source(source)
```

(Or pass `source` into `start_scenario` directly — the implementation plan will pick the smaller diff.)

In `pytest_sessionfinish`, when building `Metadata`:

```python
metadata = Metadata(
    project=session.config.rootpath.name,
    timestamp=...,
    pytest_version=pytest.__version__,
    plugin_version='0.1.0',
    commit_sha=_detect_commit_sha(),
)
```

```python
def _detect_commit_sha() -> str | None:
    for var in ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT'):
        if sha := os.environ.get(var):
            return sha
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, timeout=2, check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
```

### Config plumbing (`plugin.py`)

```python
def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('given', ...)
    ...
    group.addoption(
        '--given-source-link',
        default=None,
        help='Source-link template or preset (vscode, cursor, zed, pycharm, none). '
             'See README for variables.',
    )
    parser.addini(
        'given_source_link',
        type='string',
        default='none',
        help='Source-link template or preset name (CLI flag overrides this).',
    )
```

In `pytest_sessionfinish`, when `--given-html` is set, resolve once and pass into the renderer:

```python
raw = session.config.getoption('given_source_link') \
      or session.config.getini('given_source_link')
template = resolve_template(raw)
render_html(json_path, html_path, source_link_template=template)
```

### Standalone CLI (`cli.py`)

```python
report_parser.add_argument(
    '--source-link',
    default='none',
    help='Source-link template or preset (vscode, cursor, zed, pycharm, none).',
)
```

Resolves via the same `resolve_template`. No ini lookup (CLI is invoked outside pytest).

## Render flow

`render_html(json_path, html_path, source_link_template: str | None = None)` walks scenarios, computing `(scenario_index → resolved_url_or_None)` once before template rendering:

```python
source_urls: dict[int, str | None] = {}
for idx, scenario in enumerate(data['scenarios']):
    src = scenario.get('source')
    if src is None or source_link_template is None:
        source_urls[idx] = None
        continue
    source_urls[idx] = format_source_link(
        source_link_template,
        source=SourceLocation(**src),
        project=data['metadata']['project'],
        commit_sha=data['metadata'].get('commit_sha'),
    )
```

Passed to Jinja as `source_urls`. The template uses `source_urls[loop.index0]`.

## UI placement (templates/report.html.j2)

Inside the expanded scenario card, as the **last** row of the body — after `steps`, `parameters`, and any error info. Rationale: source location is dev plumbing; non-technical stakeholders should see the narration first, not a file path.

```jinja
{% if scenario.source %}
<div class="scenario-source">
  {% set url = source_urls[loop.index0] %}
  {% if url %}
    <a href="{{ url }}">{{ scenario.source.relpath }}:{{ scenario.source.line }}</a>
  {% else %}
    <span>{{ scenario.source.relpath }}:{{ scenario.source.line }}</span>
  {% endif %}
</div>
{% endif %}
```

Same DOM in both modes; the `<a>` wrapper is the only difference. CSS: small font, muted color, right-aligned or block-level depending on what looks best in `examples/report.html` — not load-bearing for the spec.

## Error handling

| Situation                                                       | Behavior                                                                                              |
|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `given_source_link` is unknown preset and not a template        | `PytestGivenError` at config resolution time, listing valid presets                                   |
| `given_source_link = "github"` but no GitHub remote detected    | `PytestGivenError` at config resolution time: explains the detection rules and points to the raw-template form |
| Template uses `{sha}` but `commit_sha` is `None`                | `PytestGivenError` at render time: explains how to provide a SHA (env var or git repo)                |
| Template uses an unknown variable like `{branch}`               | `PytestGivenError` at render time, listing valid variables                                            |
| `git rev-parse HEAD` fails / git not installed                  | Silently fall back to `commit_sha = None`; only relevant if `{sha}` is referenced                     |
| `item.location` unavailable on some pytest item shape           | `scenario.source = None`; link block doesn't render                                                   |
| Renderer called with template set but `scenario.source = None`  | Skip the link block for that scenario; no error                                                       |

Template resolution happens once (not per scenario); malformed templates fail fast at session start / CLI invocation.

## Testing

- `tests/unit/test_source_link.py`:
  - `resolve_template`: each static preset name resolves; `'none'` → `None`; raw template strings pass through; unknown values raise with a clear error listing valid options.
  - `resolve_template('github')`: org/repo baked into the returned template from `GITHUB_REPOSITORY`, from HTTPS remote, from SSH remote; raises when neither is parseable as a GitHub URL (use `monkeypatch.setenv` / patched `subprocess.run`).
  - `format_source_link`: each template variable substitutes correctly; missing `{sha}` raises; unknown variable raises; POSIX path normalization preserved on Windows-style input.
  - `_detect_commit_sha`: each env var detected in priority order; subprocess fake for the git fallback; returns `None` when both fail (use `monkeypatch` to clear env and patch `subprocess.run`).
  - `_detect_github_repo`: HTTPS form (`https://github.com/o/r.git`), SSH form (`git@github.com:o/r.git`), `.git` suffix optional in both, env var beats remote, non-GitHub remote (e.g. GitLab URL) returns None.
- `tests/integration/test_plugin.py`:
  - End-to-end run with `--given-source-link=vscode`: JSON contains `source: {relpath, line}` for each scenario and `metadata.commit_sha` is set; HTML contains `<a href="vscode://file/.../test_*.py:N">` in the expanded card.
  - End-to-end run with default (`given_source_link` unset): JSON still contains `source` data; HTML contains plain `<span>` (no link).
- `tests/integration/test_cli.py`:
  - `pytest-given report ... --source-link=zed` produces the expected `<a href="zed://...">` in HTML.
- Coverage stays at 100% (per project convention).

## Documentation

- **README:** new "Source links" section with the preset table, variable table, three worked examples (PyCharm, Zed, GitHub-permalink for CI), and the caveats listed above.
- **GLOSSARY.md:** add "source link" entry.
- **AGENTS.md Architecture section:** mention the new `source_link.py` (if extracted) under the file list; mention `SourceLocation` under model.

## Out of scope (explicitly)

- Per-step source links. The expanded card surfaces the test function only; steps live in fixtures or inline and would require capturing source per call site, which complicates the recording stack for marginal value.
- Auto-detecting the user's editor (e.g., from `$TERM_PROGRAM`). Explicit config beats magic; the one-line preset is a low bar.
- Moving the scenario duration display to the bottom of the card. Independent layout decision; file as a separate spec.
- A `--given-source-base <dir>` flag to override the render-time cwd for `{path}` resolution. Add later only if anyone hits the limitation.
- Custom URL encoding beyond what Jinja's `autoescape` already provides for the `href` attribute.
