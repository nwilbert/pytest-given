"""Which rename-log revs fall outside the compared range, as git answers it."""

from pathlib import Path

from ..git import commits_between, is_shallow, resolve_commits
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
    sides = [sha for sha in (before_sha, after_sha) if sha is not None]
    resolved = (
        {} if repo_reason else resolve_commits([*sides, *sorted(revs)], repo) or {}
    )
    reason = _no_ancestry_reason('before', before_sha, repo_reason, resolved)
    if reason is not None:
        return frozenset(), [
            f'no ancestry answer ({reason}); rename-log entries with `rev` all apply'
        ]
    assert before_sha is not None
    warnings: list[str] = []
    after_reason = _no_ancestry_reason('after', after_sha, repo_reason, resolved)
    if after_reason is not None:
        warnings.append(
            f'no ancestry answer ({after_reason}); rename-log entries with a `rev` '
            'later than the after commit apply'
        )
    known: dict[str, str] = {}
    for rev in sorted(revs):
        if rev in resolved:
            known[rev] = resolved[rev]
        else:
            warnings.append(
                f'rename-log rev {rev!r} does not resolve; its entries apply'
            )
    if not known:
        return frozenset(), warnings
    # The range is what the after commit reaches and the before one doesn't.
    # Without an after commit, a rev applies unless the before one reaches it.
    if after_reason is None:
        assert after_sha is not None
        tips = [resolved[after_sha]]
    else:
        tips = sorted(set(known.values()))
    in_range = commits_between(tips, resolved[before_sha], repo)
    if in_range is None:
        warnings.append(
            f'no ancestry answer for {plural(len(known), "rename-log rev")}; '
            'their entries apply'
        )
        return frozenset(), warnings
    return frozenset(rev for rev, sha in known.items() if sha not in in_range), warnings


def _no_repo_answer_reason(repo: Path) -> str | None:
    match is_shallow(repo):
        case None:
            return 'git cannot read a repository here'
        case True:
            return 'a shallow clone'
        case False:
            return None


def _no_ancestry_reason(
    side: Side, sha: str | None, repo_reason: str | None, resolved: dict[str, str]
) -> str | None:
    if sha is None:
        return f'the {side} report has no commit SHA'
    if repo_reason is not None:
        return repo_reason
    if sha not in resolved:
        return f'git cannot resolve the {side} commit {sha}'
    return None
