"""Running `git`: the one place the package shells out to it.

A leaf like `markdown/`: it imports nothing else from the package, so every
package asks git the same way.
"""

from .commands import (
    Ancestry,
    detect_commit_sha,
    detect_github_repo,
    is_ancestor,
    is_shallow,
    revision_exists,
    tags_pointing_at,
)

__all__ = [
    'Ancestry',
    'detect_commit_sha',
    'detect_github_repo',
    'is_ancestor',
    'is_shallow',
    'revision_exists',
    'tags_pointing_at',
]
