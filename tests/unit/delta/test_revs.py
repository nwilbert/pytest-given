"""`revs_outside_range` keeps every entry whose ancestry it can't establish."""

from pathlib import Path

import pytest

from pytest_given.delta import revs, revs_outside_range
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


def test_unknown_ancestry_applies_with_one_warning_in_all(
    git_repo: GitRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(revs, 'is_ancestor', lambda rev, sha, repo: 'unknown')
    skipped, warnings = revs_outside_range(
        frozenset({'v1', 'v1.9'}), git_repo.head, git_repo.head, git_repo.path
    )
    assert skipped == frozenset()
    assert warnings == ['no ancestry answer for 2 rename-log revs; their entries apply']
