"""Running `git`: the one place the package shells out to it.

A leaf like `markdown/`: it imports nothing else from the package, so every
package asks git the same way.
"""

from .commands import (
    commits_between,
    detect_commit_sha,
    detect_github_repo,
    is_shallow,
    resolve_commits,
    tags_by_commit,
)

__all__ = [
    'commits_between',
    'detect_commit_sha',
    'detect_github_repo',
    'is_shallow',
    'resolve_commits',
    'tags_by_commit',
]
