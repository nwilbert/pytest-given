"""Which rename-log revs fall outside the compared range, as git answers it."""

from pathlib import Path

from ..git import is_ancestor, is_shallow, revision_exists
from ..model import Side, plural


def revs_outside_range(
    revs: frozenset[str], before_sha: str | None, after_sha: str | None, repo: Path
) -> tuple[frozenset[str], list[str]]:
    """The revs outside the range, and the warnings: an ancestor of the before
    commit, whose rename predates it, or a rev the after commit doesn't reach,
    whose rename postdates it. A rev git can't answer for applies."""
    if not revs:
        return frozenset(), []
    repo_reason = _no_repo_answer_reason(repo)
    reason = _no_ancestry_reason('before', before_sha, repo_reason, repo)
    if reason is not None:
        return frozenset(), [
            f'no ancestry answer ({reason}); rename-log entries with `rev` all apply'
        ]
    assert before_sha is not None
    skipped: set[str] = set()
    unknown: list[str] = []
    warnings: list[str] = []
    after_reason = _no_ancestry_reason('after', after_sha, repo_reason, repo)
    if after_reason is not None:
        warnings.append(
            f'no ancestry answer ({after_reason}); rename-log entries with a `rev` '
            'later than the after commit apply'
        )
    for rev in sorted(revs):
        if not revision_exists(rev, repo):
            warnings.append(
                f'rename-log rev {rev!r} does not resolve; its entries apply'
            )
            continue
        predates = is_ancestor(rev, before_sha, repo)
        if predates == 'yes':
            skipped.add(rev)
            continue
        reached = 'yes'
        if after_reason is None:
            assert after_sha is not None
            reached = is_ancestor(rev, after_sha, repo)
        if reached == 'no':
            skipped.add(rev)
        elif 'unknown' in (predates, reached):
            unknown.append(rev)
    if unknown:
        warnings.append(
            f'no ancestry answer for {plural(len(unknown), "rename-log rev")}; '
            'their entries apply'
        )
    return frozenset(skipped), warnings


def _no_repo_answer_reason(repo: Path) -> str | None:
    match is_shallow(repo):
        case None:
            return 'git cannot read a repository here'
        case True:
            return 'a shallow clone'
        case False:
            return None


def _no_ancestry_reason(
    side: Side, sha: str | None, repo_reason: str | None, repo: Path
) -> str | None:
    if sha is None:
        return f'the {side} report has no commit SHA'
    if repo_reason is not None:
        return repo_reason
    if not revision_exists(sha, repo):
        return f'git cannot resolve the {side} commit {sha}'
    return None
