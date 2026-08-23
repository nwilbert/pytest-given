"""Source-link preset resolution and template substitution.

Resolves a config value into a substitution template, and substitutes the
template variables against a SourceLocation + metadata. Errors raised here
are PytestGivenError, so they surface uniformly through both the plugin
session-finish path and the standalone CLI.
"""

import os
import re
import string
import subprocess
from collections.abc import Callable
from pathlib import Path

from ..model import PytestGivenError, SourceLocation

_STATIC_PRESETS: dict[str, str] = {
    'vscode': 'vscode://file/{path}:{line}',
    'cursor': 'cursor://file/{path}:{line}',
    'zed': 'zed://file/{path}:{line}',
    'pycharm': 'pycharm://open?file={path}&line={line}',
}

# `github` is a preset but resolves via _detect_github_repo (next task), not
# the static table. Listed here so the unknown-preset error advertises it.
_ALL_PRESET_NAMES = frozenset(_STATIC_PRESETS) | {'github'}

_VALID_VARS = frozenset({'path', 'relpath', 'line', 'project', 'sha'})


def _valid_vars() -> str:
    """The substitutable variables, for the messages that list them."""
    return ', '.join(sorted(_VALID_VARS))


def resolve_template(value: str | None) -> str | None:
    """Resolve a config value into a template string (or None for 'none').

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
        return value
    valid = ', '.join(sorted(_ALL_PRESET_NAMES))
    raise PytestGivenError(
        f'Unknown given_source_link preset {value!r}. '
        f'Valid presets: {valid}, none. '
        f'Or pass a raw template string containing {{path}}, {{relpath}}, '
        f'{{line}}, {{project}}, or {{sha}}.'
    )


def compile_source_link(
    template: str,
    *,
    project: str,
    commit_sha: str | None,
) -> Callable[[SourceLocation], str]:
    """Validate `template` once and return a per-location substitution function.

    The returned function substitutes `{path}`, `{relpath}`, `{line}`,
    `{project}`, `{sha}` for a given `SourceLocation`. Validation (unknown
    variables, attribute/index access, and the `{sha}` → `commit_sha`
    requirement) depends only on the template, so it runs once here rather
    than on every call — a render substitutes one template across every
    scenario, story, and term. Template errors therefore surface eagerly, at
    compile time, before any location is rendered.

    `{path}` is resolved against the current working directory at call time;
    `{sha}` requires `commit_sha`; unknown variables raise.
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

    def substitute(source: SourceLocation) -> str:
        abspath = (Path.cwd() / source.relpath).resolve().as_posix()
        return template.format(
            path=abspath,
            relpath=source.relpath,
            line=source.line,
            project=project,
            sha=commit_sha or '',
        )

    return substitute


def _extract_field_names(template: str) -> list[str]:
    """Return the field names referenced inside `{...}` placeholders, using
    str.format semantics. Rejects attribute / index access up front rather
    than letting `template.format()` surface it as an opaque AttributeError
    on a substituted string."""
    fields: list[str] = []
    for _literal, field_name, _spec, _conv in string.Formatter().parse(template):
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


_GITHUB_URL_RE = re.compile(
    r'(?:https://github\.com/|git@github\.com:)'
    r'(?P<org>[^/]+)/'
    r'(?P<repo>[^/]+?)'
    r'(?:\.git)?'
    r'/?$'
)


def _resolve_github_preset() -> str:
    """Detect org/repo and bake into the GitHub permalink template.

    Raises PytestGivenError when neither GITHUB_REPOSITORY nor a parseable
    GitHub remote is available; the message points users at the raw-template
    escape hatch.
    """
    detected = _detect_github_repo()
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


def _detect_github_repo() -> tuple[str, str] | None:
    """Return (org, repo) from GITHUB_REPOSITORY env or `git remote get-url
    origin`; None if neither yields a recognizable GitHub remote."""
    env = os.environ.get('GITHUB_REPOSITORY')
    if env and '/' in env:
        org, _, repo = env.partition('/')
        if org and repo:
            return (org, repo)
    remote = _git('remote', 'get-url', 'origin')
    if remote is None:
        return None
    match = _GITHUB_URL_RE.match(remote)
    if match is None:
        return None
    return (match['org'], match['repo'])


def _git(*args: str) -> str | None:
    """The stripped stdout of a `git` call, or None when it cannot answer.

    Both callers want the same thing and the same failure policy — no git on
    PATH, no repository, a non-zero exit — so the run lives here once. Timed
    out rather than left to hang: this runs on the report path, where a wedged
    git would hold up a finished test session.
    """
    try:
        result = subprocess.run(
            ['git', *args],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except subprocess.SubprocessError, FileNotFoundError:
        return None
    return result.stdout.strip()


_COMMIT_ENV_VARS = ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT')


def detect_commit_sha() -> str | None:
    """Return the current commit SHA, or None if it can't be determined.

    Checks CI env vars in priority order (GitHub → GitLab → Buildkite) then
    falls back to `git rev-parse HEAD`. Any subprocess failure returns None
    silently — only relevant if the user's template references `{sha}`, and
    that case raises a clearer error in `compile_source_link`.
    """
    for var in _COMMIT_ENV_VARS:
        if sha := os.environ.get(var):
            return sha
    return _git('rev-parse', 'HEAD')
