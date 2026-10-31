"""A throwaway git repository built with `git` itself, for tests that query one."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Passed on every call so the build needs no global git config.
_CONFIG = (
    '-c',
    'user.name=t',
    '-c',
    'user.email=t@t',
    '-c',
    'init.defaultBranch=main',
    '-c',
    'commit.gpgsign=false',
    '-c',
    'tag.gpgsign=false',
)
_COMMIT_DATE = '2020-01-01T00:00:00+0000'


@dataclass(frozen=True)
class GitRepo:
    """Two commits: `first` tagged `v1`, `head` tagged `v1.10` and `v1.9`."""

    path: Path
    first: str
    head: str


def make_git_repo(path: Path) -> GitRepo:
    path.mkdir(parents=True)
    run_git(path, 'init')
    first = _commit(path)
    run_git(path, 'tag', 'v1')
    head = _commit(path)
    run_git(path, 'tag', 'v1.9')
    run_git(path, 'tag', 'v1.10')
    return GitRepo(path=path, first=first, head=head)


def run_git(path: Path, *args: str) -> str:
    """No inherited `GIT_*` variable: run from a git hook, `GIT_DIR` and
    `GIT_INDEX_FILE` would aim these commits and tags at the real repository."""
    env = {
        **{
            name: value
            for name, value in os.environ.items()
            if not name.upper().startswith('GIT_')
        },
        'GIT_CEILING_DIRECTORIES': str(path.resolve().parent),
        'GIT_AUTHOR_DATE': _COMMIT_DATE,
        'GIT_COMMITTER_DATE': _COMMIT_DATE,
    }
    result = subprocess.run(
        ['git', *_CONFIG, '-C', str(path), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout.strip()


def _commit(path: Path) -> str:
    run_git(path, 'commit', '--allow-empty', '-m', 'commit')
    return run_git(path, 'rev-parse', 'HEAD')
