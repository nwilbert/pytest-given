"""Every `git` call the package makes.

Nothing here parses prose output, so locale and git version wording don't
matter. A query git couldn't answer returns None, never an empty answer:
reading a failure as "no commits" would skip what should apply. Every query
takes `-C repo` and never goes through a shell, and the delta's take each a
fixed number of calls, however many revs they ask about.
"""

import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

# Session finish asks the working directory's git, and a wedged one holds up an
# already-finished test session, so it gets less time than the delta's queries.
_SESSION_TIMEOUT_SECONDS = 2
_QUERY_TIMEOUT_SECONDS = 5
_COMMIT_ENV_VARS = ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT')
# Without these, version sort puts `v1.0rc1` above `v1.0`. Listed lowest first.
_PRE_RELEASES_FIRST = tuple(
    arg
    for suffix in ('.dev', 'a', 'b', 'rc', '-alpha', '-beta', '-rc')
    for arg in ('-c', f'versionsort.suffix={suffix}')
)

_SPACE = re.compile(r'\s')

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


def resolve_commits(revs: Iterable[str], repo: Path) -> dict[str, str] | None:
    """Each rev naming a commit in `repo`, to its full SHA; None when git can't
    answer. The revs are git's input, one a line, so none is read as an option,
    and one holding a space names nothing."""
    asked = [rev for rev in revs if rev and not _SPACE.search(rev)]
    if not asked:
        return {}
    answer = _stdout(
        'cat-file',
        '--batch-check=%(objectname) %(objecttype)',
        stdin=''.join(f'{rev}^{{commit}}\n' for rev in asked),
        repo=repo,
    )
    lines = None if answer is None else answer.splitlines()
    if lines is None or len(lines) != len(asked):
        return None
    resolved: dict[str, str] = {}
    for rev, line in zip(asked, lines, strict=True):
        # A rev naming no commit answers `<rev>^{commit} missing`, or `ambiguous`.
        sha, kind = line.split(' ')
        if kind == 'commit':
            resolved[rev] = sha
    return resolved


def is_shallow(repo: Path) -> bool | None:
    """Whether `repo` is a shallow clone; None when git can't answer."""
    answer = _stdout('rev-parse', '--is-shallow-repository', repo=repo)
    # A git too old for the flag echoes it back, which is no answer.
    return {'true': True, 'false': False}.get(answer or '')


def commits_between(
    tips: Iterable[str], base: str, repo: Path
) -> frozenset[str] | None:
    """The commits the `tips` reach and `base` doesn't, `base..tip` for one
    tip; None when git can't answer."""
    revs = [*tips, base]
    if any(_looks_like_option(rev) for rev in revs):
        return None
    listed = _stdout('rev-list', *revs[:-1], '--not', base, repo=repo)
    return None if listed is None else frozenset(listed.split())


def tags_by_commit(repo: Path) -> dict[str, list[str]]:
    """Each tagged commit's tags, highest version first; empty when git can't
    answer. An annotated tag is filed under the commit it peels to."""
    listed = _stdout(
        *_PRE_RELEASES_FIRST,
        'for-each-ref',
        'refs/tags',
        '--sort=-version:refname',
        '--format=%(objectname) %(*objectname) %(refname:lstrip=2)',
        repo=repo,
    )
    tags: dict[str, list[str]] = {}
    for line in (listed or '').splitlines():
        target, peeled, name = line.split(' ', 2)
        tags.setdefault(peeled or target, []).append(name)
    return tags


def _looks_like_option(rev: str) -> bool:
    """A leading `-` would be read as an option, so such a rev never reaches git."""
    return rev.startswith('-')


def _stdout(
    *args: str, repo: Path | None = None, stdin: str | None = None
) -> str | None:
    """The stripped stdout of a `git` call, or None when it cannot answer.
    Without a `repo` it asks the working directory, for session finish."""
    timeout = _QUERY_TIMEOUT_SECONDS if repo else _SESSION_TIMEOUT_SECONDS
    result = _run(list(args), repo, timeout, stdin)
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _run(
    args: list[str],
    repo: Path | None = None,
    timeout: float = _QUERY_TIMEOUT_SECONDS,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """The finished process, or None when git could not run to completion.

    `OSError` covers the whole exec side: a `git` that exists but is not
    executable raises `PermissionError`, and letting that escape would cost the
    entire report — session finish catches `OSError` and discards every sink.
    Timed out rather than left to hang. Git writes ref names as UTF-8 whatever
    the locale's codec.
    """
    location = [] if repo is None else ['-C', str(repo)]
    try:
        return subprocess.run(
            ['git', *location, *args],
            input=stdin,
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
