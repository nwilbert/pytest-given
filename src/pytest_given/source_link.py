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
from pathlib import Path
from typing import Literal

from pytest_given.errors import PytestGivenError
from pytest_given.model import SourceLocation

type SourceLinkPreset = Literal['vscode', 'cursor', 'zed', 'pycharm', 'github']

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


def format_source_link(
    template: str,
    *,
    source: SourceLocation,
    project: str,
    commit_sha: str | None,
) -> str:
    """Substitute `{path}`, `{relpath}`, `{line}`, `{project}`, `{sha}` in `template`.

    `{path}` is resolved against the current working directory at call time.
    `{sha}` requires `commit_sha`; unknown variables raise.
    """
    used = set(_extract_field_names(template))
    unknown = used - _VALID_VARS
    if unknown:
        valid = ', '.join(sorted(_VALID_VARS))
        raise PytestGivenError(
            f'Unknown source-link template variable(s) {sorted(unknown)!r}. '
            f'Valid: {valid}.'
        )
    if 'sha' in used and commit_sha is None:
        raise PytestGivenError(
            'Source-link template uses {sha} but no commit SHA was detected. '
            'Set GITHUB_SHA / CI_COMMIT_SHA / BUILDKITE_COMMIT in CI, or run '
            'from a git working tree so `git rev-parse HEAD` can resolve.'
        )
    abspath = (Path.cwd() / source.relpath).resolve().as_posix()
    return template.format(
        path=abspath,
        relpath=source.relpath,
        line=source.line,
        project=project,
        sha=commit_sha or '',
    )


def _extract_field_names(template: str) -> list[str]:
    """Return the field names referenced inside `{...}` placeholders, using
    str.format semantics."""
    fields: list[str] = []
    for _literal, field_name, _spec, _conv in string.Formatter().parse(template):
        if field_name is None:
            continue
        head = re.split(r'[.\[]', field_name, maxsplit=1)[0]
        if head and not head.isdigit():
            fields.append(head)
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
    origin`; None if neither yields a recognisable GitHub remote."""
    env = os.environ.get('GITHUB_REPOSITORY')
    if env and '/' in env:
        org, _, repo = env.partition('/')
        if org and repo:
            return (org, repo)
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except subprocess.SubprocessError, FileNotFoundError:
        return None
    match = _GITHUB_URL_RE.match(result.stdout.strip())
    if match is None:
        return None
    return (match['org'], match['repo'])


_COMMIT_ENV_VARS = ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT')


def detect_commit_sha() -> str | None:
    """Return the current commit SHA, or None if it can't be determined.

    Checks CI env vars in priority order (GitHub → GitLab → Buildkite) then
    falls back to `git rev-parse HEAD`. Any subprocess failure returns None
    silently — only relevant if the user's template references `{sha}`, and
    that case raises a clearer error in `format_source_link`.
    """
    for var in _COMMIT_ENV_VARS:
        if sha := os.environ.get(var):
            return sha
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except subprocess.SubprocessError, FileNotFoundError:
        return None
    return result.stdout.strip()
