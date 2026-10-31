"""Source-link preset resolution and template substitution.

Resolves a config value into a substitution template, and substitutes the
template variables against a SourceLocation + metadata. Errors raised here
are PytestGivenError, so they surface uniformly through both the plugin
session-finish path and the standalone CLI.
"""

import string
from collections.abc import Callable
from pathlib import Path

from ..git import detect_github_repo
from ..model import PytestGivenError, SourceLocation

_STATIC_PRESETS: dict[str, str] = {
    'vscode': 'vscode://file/{path}:{line}',
    'cursor': 'cursor://file/{path}:{line}',
    'zed': 'zed://file/{path}:{line}',
    'pycharm': 'pycharm://open?file={path}&line={line}',
}

# `github` is a preset but resolves via `detect_github_repo`, not the static
# table. Listed here so the unknown-preset error advertises it.
_ALL_PRESET_NAMES = frozenset(_STATIC_PRESETS) | {'github'}

_VALID_VARS = frozenset({'path', 'relpath', 'line', 'project', 'sha'})

# The one help text for `--given-source-link` and the CLI's `--source-link`,
# so the two entry points advertise the same presets and the same docs page.
SOURCE_LINK_HELP = (
    'Source-link template or preset (vscode, cursor, zed, pycharm, github, '
    'none). Variables: see "Source links & tracebacks" in the pytest-given '
    'docs.'
)


def _valid_vars() -> str:
    """The substitutable variables, for the messages that list them."""
    return ', '.join(sorted(_VALID_VARS))


def resolve_source_link_template(
    value: str | None, setting: str = 'given_source_link'
) -> str | None:
    """Resolve a config value into a template string (or None for 'none').

    `setting` names the option in the error, so a CLI flag and an ini that feed
    the same resolver each report under the spelling the user actually typed.

    Accepts a static preset name, the `github` preset (auto-detects org/repo
    via env or `git remote`), a raw template containing `{...}` placeholders,
    or the literal `'none'` / empty / None to disable source linking. A
    bareword that is neither a known preset nor a raw template raises
    PytestGivenError listing valid presets.
    """
    if not value or value == 'none':
        return None
    if value == 'github':
        return _resolve_github_preset()
    if value in _STATIC_PRESETS:
        return _STATIC_PRESETS[value]
    if '{' in value or '://' in value:
        # Compiled against stand-in values, so a typo fails before the suite
        # runs; only a `{sha}` with no commit is left for render time.
        compile_source_link(value, project='project', commit_sha='0' * 40)
        return value
    valid = ', '.join(sorted(_ALL_PRESET_NAMES))
    raise PytestGivenError(
        f'Unknown {setting} preset {value!r}. '
        f'Valid presets: {valid}, none. '
        f'Or pass a raw template string containing {{path}}, {{relpath}}, '
        f'{{line}}, {{project}}, or {{sha}}.'
    )


def compile_source_link(
    template: str,
    *,
    project: str,
    commit_sha: str | None,
    root: Path | None = None,
) -> Callable[[SourceLocation], str]:
    """Validate `template` once and return a per-location substitution function.

    The returned function substitutes `{path}`, `{relpath}`, `{line}`,
    `{project}`, `{sha}` for a given `SourceLocation`. Validation depends only
    on the template, so it runs once here and its errors surface before any
    location is rendered.

    `{path}` joins `relpath` to `root`, the directory it is relative to. Only
    a live run knows that — a saved report does not carry its rootdir — so
    without one the working directory stands in.
    """
    used = set(_extract_field_names(template))
    unknown = used - _VALID_VARS
    if unknown:
        raise PytestGivenError(
            f'Unknown source-link template variable(s) {sorted(unknown)!r}. '
            f'Valid: {_valid_vars()}.'
        )
    if 'sha' in used and commit_sha is None:
        raise PytestGivenError(
            'Source-link template uses {sha} but no commit SHA was detected. '
            'Set GITHUB_SHA / CI_COMMIT_SHA / BUILDKITE_COMMIT in CI, or run '
            'from a git working tree so `git rev-parse HEAD` can resolve.'
        )

    base = Path.cwd() if root is None else root

    def substitute(source: SourceLocation) -> str:
        abspath = (base / source.relpath).resolve().as_posix()
        return template.format(
            path=abspath,
            relpath=source.relpath,
            line=source.line,
            project=project,
            sha=commit_sha or '',
        )

    # A bad format spec (`{line:>{width}}`) or conversion (`{line!x}`) fails
    # only when formatting, so one dry run fails it here rather than mid-render.
    try:
        substitute(SourceLocation(relpath='test_x.py', line=1))
    except (KeyError, ValueError, IndexError) as error:
        raise PytestGivenError(
            f'Source-link template {template!r} fails to format: '
            f'{type(error).__name__}: {error}. Valid: {_valid_vars()}.'
        ) from error
    return substitute


def _extract_field_names(template: str) -> list[str]:
    """Return the field names referenced inside `{...}` placeholders, using
    str.format semantics. Rejects attribute / index access up front rather
    than letting `template.format()` surface it as an opaque AttributeError
    on a substituted string."""
    try:
        parsed = list(string.Formatter().parse(template))
    except ValueError as error:
        raise PytestGivenError(
            f'Source-link template {template!r} cannot be read: {error}. '
            'Escape a literal brace as {{ or }}.'
        ) from error
    fields: list[str] = []
    for _literal, field_name, _spec, _conv in parsed:
        if field_name is None:
            continue
        if '.' in field_name or '[' in field_name:
            raise PytestGivenError(
                f'Source-link template field {{{field_name}}} uses attribute '
                f'or index access; only bare variable names are supported. '
                f'Valid: {_valid_vars()}.'
            )
        if not field_name or field_name.isdigit():
            raise PytestGivenError(
                f'Source-link template uses a positional field {{{field_name}}}; '
                f'only named variables are supported (substitution passes '
                f'keywords only). Valid: {_valid_vars()}.'
            )
        fields.append(field_name)
    return fields


def _resolve_github_preset() -> str:
    """Detect org/repo and bake into the GitHub permalink template.

    Raises PytestGivenError when neither GITHUB_REPOSITORY nor a parseable
    GitHub remote is available; the message points users at the raw-template
    escape hatch.
    """
    detected = detect_github_repo()
    if detected is None:
        raise PytestGivenError(
            "given_source_link='github' could not detect an org/repo. "
            "Set the GITHUB_REPOSITORY env var (format 'org/repo') or run "
            'from a checkout whose `origin` remote points at github.com. '
            'Or use a raw template, e.g.: '
            "'https://github.com/myorg/myrepo/blob/{sha}/{relpath}#L{line}'."
        )
    org, repo = detected
    return f'https://github.com/{org}/{repo}/blob/{{sha}}/{{relpath}}#L{{line}}'
