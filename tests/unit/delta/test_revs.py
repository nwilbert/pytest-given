"""`revs_outside_range` keeps every entry whose ancestry it can't establish."""

import subprocess
from pathlib import Path

import pytest

from pytest_given.delta import revs
from pytest_given.delta.revs import revs_outside_range
from tests.git_repo import GitRepo


def test_no_revs_ask_git_nothing(tmp_path: Path) -> None:
    assert revs_outside_range(frozenset(), None, None, tmp_path) == (frozenset(), [])


@pytest.mark.usefixtures('isolated_git_env')
def test_outside_a_repository_every_rev_applies(tmp_path: Path) -> None:
    skipped, warnings = revs_outside_range(
        frozenset({'v1'}), 'a' * 40, 'a' * 40, tmp_path
    )
    assert skipped == frozenset()
    assert warnings == [
        (
            'no ancestry answer (git cannot read a repository here); '
            'rename-log entries with `rev` all apply'
        )
    ]


def test_in_a_shallow_clone_every_rev_applies(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(revs, 'is_shallow', lambda repo: True)
    skipped, [warning] = revs_outside_range(
        frozenset({'v1'}), git_repo.head, git_repo.head, git_repo.path
    )
    assert skipped == frozenset()
    assert '(a shallow clone)' in warning


def test_an_unresolvable_before_sha_applies_every_rev(git_repo: GitRepo) -> None:
    skipped, [warning] = revs_outside_range(
        frozenset({'v1'}), 'f' * 40, git_repo.head, git_repo.path
    )
    assert skipped == frozenset()
    assert f'git cannot resolve the before commit {"f" * 40}' in warning


def test_an_after_report_without_a_sha_checks_the_before_commit_alone(
    git_repo: GitRepo,
) -> None:
    skipped, [warning] = revs_outside_range(
        frozenset({'v1', 'v1.9'}), git_repo.first, None, git_repo.path
    )
    assert skipped == frozenset({'v1'})
    assert warning == (
        'no ancestry answer (the after report has no commit SHA); rename-log '
        'entries with a `rev` later than the after commit apply'
    )


def test_an_unresolvable_rev_is_named_and_applies(git_repo: GitRepo) -> None:
    skipped, warnings = revs_outside_range(
        frozenset({'v1', 'nope'}), git_repo.head, git_repo.head, git_repo.path
    )
    assert skipped == frozenset({'v1'})
    assert warnings == ["rename-log rev 'nope' does not resolve; its entries apply"]
    assert revs_outside_range(
        frozenset({'nope'}), git_repo.head, git_repo.head, git_repo.path
    ) == (frozenset(), warnings)


def test_unknown_ancestry_applies_with_one_warning_in_all(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(revs, 'commits_between', lambda tips, base, repo: None)
    skipped, warnings = revs_outside_range(
        frozenset({'v1', 'v1.9'}), git_repo.head, git_repo.head, git_repo.path
    )
    assert skipped == frozenset()
    assert warnings == ['no ancestry answer for 2 rename-log revs; their entries apply']


def test_a_rev_applies_only_within_the_range(git_repo: GitRepo) -> None:
    """The before commit and its ancestors predate the range; a commit the
    after one doesn't reach postdates it."""
    revs_to_check = frozenset({'v1', 'v1.9'})
    assert revs_outside_range(
        revs_to_check, git_repo.first, git_repo.head, git_repo.path
    ) == (frozenset({'v1'}), [])
    assert revs_outside_range(
        revs_to_check, git_repo.first, git_repo.first, git_repo.path
    ) == (revs_to_check, [])


def test_every_rev_costs_git_the_same_three_calls(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A call per rev would cost a long rename log seconds on Windows."""
    real_run = subprocess.run
    calls: list[list[str]] = []

    def spy(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return real_run(cmd, **kwargs)  # type: ignore[call-overload, no-any-return]

    monkeypatch.setattr(subprocess, 'run', spy)
    revs_outside_range(
        frozenset({'v1', 'v1.9', 'v1.10', 'nope'}),
        git_repo.first,
        git_repo.head,
        git_repo.path,
    )
    assert len(calls) == 3
