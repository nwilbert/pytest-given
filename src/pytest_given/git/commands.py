"""Every `git` call the package makes.

Nothing here parses prose output, so locale and git version wording don't
matter. An ancestry answer keeps exit 1 ("not an ancestor") apart from every
other failure: reading exit 128 as "no" would apply what should be skipped.
Every query takes `-C repo` and never goes through a shell.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Literal

type Ancestry = Literal['yes', 'no', 'unknown']

_QUERY_TIMEOUT_SECONDS = 5
_COMMIT_ENV_VARS = ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT')

_GITHUB_URL_RE = re.compile(
    r'(?:https://github\.com/|git@github\.com:)'
    r'(?P<org>[^/]+)/'
    r'(?P<repo>[^/]+?)'
    r'(?:\.git)?'
    r'/?$'
)


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
    return _stdout('rev-parse', 'HEAD')


def detect_github_repo() -> tuple[str, str] | None:
    """Return (org, repo) from GITHUB_REPOSITORY env or `git remote get-url
    origin`; None if neither yields a recognizable GitHub remote."""
    env = os.environ.get('GITHUB_REPOSITORY')
    if env and '/' in env:
        org, _, repo = env.partition('/')
        if org and repo:
            return (org, repo)
    remote = _stdout('remote', 'get-url', 'origin')
    if remote is None:
        return None
    match = _GITHUB_URL_RE.match(remote)
    if match is None:
        return None
    return (match['org'], match['repo'])


def resolve_revision(rev: str, repo: Path) -> str | None:
    """The commit SHA `rev` names in `repo`, or None when it doesn't resolve."""
    if _looks_like_option(rev):
        return None
    result = _run(['rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}'], repo)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def is_shallow(repo: Path) -> bool | None:
    """Whether `repo` is a shallow clone; None when git can't answer."""
    result = _run(['rev-parse', '--is-shallow-repository'], repo)
    if result is None or result.returncode != 0:
        return None
    # A git too old for the flag echoes it back, which is no answer.
    return {'true': True, 'false': False}.get(result.stdout.strip())


def is_ancestor(rev: str, sha: str, repo: Path) -> Ancestry:
    """Whether `rev` is an ancestor of `sha`: exit 0 yes, 1 no, else unknown."""
    if _looks_like_option(rev) or _looks_like_option(sha):
        return 'unknown'
    result = _run(['merge-base', '--is-ancestor', rev, sha], repo)
    if result is None:
        return 'unknown'
    match result.returncode:
        case 0:
            return 'yes'
        case 1:
            return 'no'
        case _:
            return 'unknown'


def tags_pointing_at(sha: str, repo: Path) -> list[str]:
    """The tags on `sha`, highest version first; empty when git can't answer."""
    if _looks_like_option(sha):
        return []
    result = _run(['tag', '--points-at', sha, '--sort=-version:refname'], repo)
    if result is None or result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _looks_like_option(rev: str) -> bool:
    """A leading `-` would be read as an option, so such a rev never reaches git."""
    return rev.startswith('-')


def _run(args: list[str], repo: Path) -> subprocess.CompletedProcess[str] | None:
    """The finished process, or None when git could not run to completion.

    `OSError` covers the whole exec side: a `git` that exists but is not
    executable raises `PermissionError`, not `FileNotFoundError`. Git writes
    ref names as UTF-8 whatever the locale's codec.
    """
    try:
        return subprocess.run(
            ['git', '-C', str(repo), *args],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=_QUERY_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None


def _stdout(*args: str) -> str | None:
    """The stripped stdout of a `git` call, or None when it cannot answer.

    `OSError` covers the whole exec side: a `git` that exists but is not
    executable raises `PermissionError`, and letting that escape would cost the
    entire report — session finish catches `OSError` and discards every sink.
    Timed out rather than left to hang, since a wedged git would hold up an
    already-finished test session. Git writes a remote URL as UTF-8 whatever
    the locale's codec.
    """
    try:
        result = subprocess.run(
            ['git', *args],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=2,
            check=True,
        )
    except OSError, subprocess.SubprocessError:
        return None
    return result.stdout.strip()
