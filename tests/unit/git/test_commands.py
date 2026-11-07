import ast
import subprocess
import sys
from pathlib import Path

import pytest

from pytest_given.git import (
    commits_between,
    detect_commit_sha,
    detect_github_repo,
    is_shallow,
    resolve_commits,
    tags_by_commit,
)
from pytest_given.git.commands import _COMMIT_ENV_VARS
from tests.git_repo import GitRepo, make_git_repo, run_git


def _clear_ci_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT'):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.parametrize(
    ('env_var', 'sha'),
    [
        ('GITHUB_SHA', 'abc123'),
        ('CI_COMMIT_SHA', 'def456'),
        ('BUILDKITE_COMMIT', '7890ab'),
    ],
)
def test_detect_commit_sha_from_a_ci_env_var(
    monkeypatch: pytest.MonkeyPatch, env_var: str, sha: str
) -> None:
    _clear_ci_vars(monkeypatch)
    monkeypatch.setenv(env_var, sha)
    assert detect_commit_sha() == sha


def test_detect_commit_sha_priority_github_over_gitlab(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ci_vars(monkeypatch)
    monkeypatch.setenv('GITHUB_SHA', 'gh')
    monkeypatch.setenv('CI_COMMIT_SHA', 'gl')
    assert detect_commit_sha() == 'gh'


def test_detect_commit_sha_git_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ci_vars(monkeypatch)
    captured: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='fakegitsha\n', stderr='')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert detect_commit_sha() == 'fakegitsha'
    assert captured == [['git', 'rev-parse', 'HEAD']]


def test_detect_commit_sha_git_failure_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ci_vars(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=128, cmd=cmd)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert detect_commit_sha() is None


def test_detect_commit_sha_git_not_installed_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_ci_vars(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError('git not found')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert detect_commit_sha() is None


def test_detect_commit_sha_unrunnable_git_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `git` that exists but cannot be executed is still "git cannot answer".

    `subprocess.run` raises `PermissionError` (an `OSError`, neither a
    `SubprocessError` nor a `FileNotFoundError`) for a non-executable `git` on
    PATH. Escaping here costs the whole report: session finish catches `OSError`
    and discards every sink over an optional SHA.
    """
    _clear_ci_vars(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError(13, 'Permission denied', 'git')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert detect_commit_sha() is None


def test_the_noxfile_unsets_every_ci_variable_a_commit_sha_is_read_from() -> None:
    """Else, on that CI, both versions of the example delta record its commit.
    nox runs without the package, so the noxfile keeps a copy."""
    noxfile = Path(__file__).parents[3] / 'noxfile.py'
    [copy] = [
        node.value
        for node in ast.parse(noxfile.read_text(encoding='utf-8')).body
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ['_COMMIT_ENV_VARS']
    ]
    assert ast.literal_eval(copy) == _COMMIT_ENV_VARS


def test_resolve_commits_maps_each_rev_naming_a_commit_to_its_sha(
    git_repo: GitRepo,
) -> None:
    """A tag counts only when it leads to a commit."""
    run_git(git_repo.path, 'tag', '-a', 'annotated', '-m', 'm', git_repo.first)
    tree = run_git(git_repo.path, 'rev-parse', 'HEAD^{tree}')
    run_git(git_repo.path, 'tag', 'on-a-tree', tree)
    short = git_repo.head[:12]
    revs = ['v1', short, 'annotated', 'on-a-tree', 'nope']
    assert resolve_commits(revs, git_repo.path) == {
        'v1': git_repo.first,
        short: git_repo.head,
        'annotated': git_repo.first,
    }


def test_resolve_commits_resolves_no_rev_holding_a_space(git_repo: GitRepo) -> None:
    """Each rev is a line of git's input: a newline would add another rev, and
    a space would end this one early."""
    revs = ['v1 v1.9', 'v1\nv1.9', 'v1']
    assert resolve_commits(revs, git_repo.path) == {'v1': git_repo.first}
    assert resolve_commits(['v1 v1.9'], git_repo.path) == {}


def test_is_shallow(git_repo: GitRepo, tmp_path: Path) -> None:
    clone = tmp_path / 'clone'
    run_git(
        tmp_path, 'clone', '--quiet', '--depth', '1', git_repo.path.as_uri(), str(clone)
    )
    assert is_shallow(git_repo.path) is False
    assert is_shallow(clone) is True


def test_commits_between_lists_what_the_tips_reach_and_the_base_does_not(
    git_repo: GitRepo,
) -> None:
    head, first = git_repo.head, git_repo.first
    assert commits_between([head], first, git_repo.path) == frozenset({head})
    assert commits_between([first], head, git_repo.path) == frozenset()
    assert commits_between([head], head, git_repo.path) == frozenset()


def test_commits_between_never_reads_an_error_as_no_commits(
    git_repo: GitRepo,
) -> None:
    """An empty answer would skip every rename-log entry outright."""
    assert commits_between(['f' * 40], git_repo.head, git_repo.path) is None


def test_tags_by_commit_highest_version_first(git_repo: GitRepo) -> None:
    assert tags_by_commit(git_repo.path) == {
        git_repo.head: ['v1.10', 'v1.9'],
        git_repo.first: ['v1'],
    }


def test_tags_by_commit_files_an_annotated_tag_under_its_commit(
    git_repo: GitRepo,
) -> None:
    run_git(git_repo.path, 'tag', '-a', 'v0.9', '-m', 'm', git_repo.first)
    assert tags_by_commit(git_repo.path)[git_repo.first] == ['v1', 'v0.9']


def test_tags_by_commit_names_a_tag_by_its_own_name_where_a_branch_shares_it(
    git_repo: GitRepo,
) -> None:
    run_git(git_repo.path, 'branch', 'v1', git_repo.first)
    assert tags_by_commit(git_repo.path)[git_repo.first] == ['v1']


def test_tags_by_commit_put_a_release_above_its_pre_releases(
    git_repo: GitRepo,
) -> None:
    tags = ['v2.0.0.dev1', 'v2.0.0a1', 'v2.0.0b2', 'v2.0.0rc1', 'v2.0.0', 'v2.0.0-rc.2']
    for tag in tags:
        run_git(git_repo.path, 'tag', tag, git_repo.first)

    assert tags_by_commit(git_repo.path)[git_repo.first][:6] == [
        'v2.0.0',
        'v2.0.0-rc.2',
        'v2.0.0rc1',
        'v2.0.0b2',
        'v2.0.0a1',
        'v2.0.0.dev1',
    ]


def test_tags_by_commit_reads_a_non_ascii_tag_as_utf8(git_repo: GitRepo) -> None:
    """Outside UTF-8 mode, a cp1252 locale cannot decode the 0x81 in 'Á'."""
    run_git(git_repo.path, 'tag', 'v1-Á', git_repo.first)
    code = (
        'import sys; from pathlib import Path; '
        'from pytest_given.git import tags_by_commit; '
        'print(ascii(tags_by_commit(Path(sys.argv[1]))))'
    )

    printed = subprocess.run(
        [sys.executable, '-X', 'utf8=0', '-c', code, git_repo.path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert ascii('v1-Á') in printed


@pytest.mark.usefixtures('isolated_git_env')
def test_tags_by_commit_leaves_an_untagged_commit_out(tmp_path: Path) -> None:
    other = make_git_repo(tmp_path / 'other')
    run_git(other.path, 'tag', '-d', 'v1')
    assert other.first not in tags_by_commit(other.path)


def test_the_test_repository_ignores_an_inherited_git_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """As under a git hook, whose `GIT_DIR` names the real repository."""
    elsewhere = tmp_path / 'elsewhere.git'
    monkeypatch.setenv('GIT_DIR', str(elsewhere))
    monkeypatch.setenv('GIT_INDEX_FILE', str(tmp_path / 'elsewhere-index'))
    repo = make_git_repo(tmp_path / 'repo')
    assert (repo.path / '.git').is_dir()
    assert not elsewhere.exists()
    assert not (tmp_path / 'elsewhere-index').exists()


@pytest.mark.usefixtures('isolated_git_env')
def test_outside_a_repository(tmp_path: Path) -> None:
    assert is_shallow(tmp_path) is None
    assert resolve_commits(['HEAD'], tmp_path) is None
    assert commits_between(['a' * 40], 'b' * 40, tmp_path) is None
    assert tags_by_commit(tmp_path) == {}


@pytest.mark.parametrize('rev', ['-x', '--all', '--upload-pack=evil'])
def test_a_revision_that_looks_like_an_option_never_reaches_git_s_arguments(
    monkeypatch: pytest.MonkeyPatch, git_repo: GitRepo, rev: str
) -> None:
    """`resolve_commits` reads it as input, where it names nothing."""
    real_run = subprocess.run
    calls: list[list[str]] = []

    def spy(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return real_run(cmd, **kwargs)  # type: ignore[call-overload, no-any-return]

    monkeypatch.setattr(subprocess, 'run', spy)
    assert resolve_commits([rev], git_repo.path) == {}
    assert commits_between([rev], git_repo.head, git_repo.path) is None
    assert commits_between([git_repo.head], rev, git_repo.path) is None
    assert all(rev not in cmd for cmd in calls)


def test_every_query_runs_in_the_repository_with_an_argument_list(
    monkeypatch: pytest.MonkeyPatch, git_repo: GitRepo
) -> None:
    real_run = subprocess.run
    calls: list[tuple[list[str], dict[str, object]]] = []

    def spy(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return real_run(cmd, **kwargs)  # type: ignore[call-overload, no-any-return]

    monkeypatch.setattr(subprocess, 'run', spy)
    resolve_commits(['v1'], git_repo.path)
    is_shallow(git_repo.path)
    commits_between([git_repo.head], git_repo.first, git_repo.path)
    tags_by_commit(git_repo.path)
    assert len(calls) == 4
    for cmd, kwargs in calls:
        assert isinstance(cmd, list)
        assert cmd[:3] == ['git', '-C', str(git_repo.path)]
        assert not kwargs.get('shell')
        assert not kwargs.get('check')


def test_session_finish_gives_git_less_time_than_a_delta_query(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A wedged git holds up an already-finished test session."""
    _clear_ci_vars(monkeypatch)
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)
    timeouts: list[object] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        timeouts.append(kwargs['timeout'])
        return subprocess.CompletedProcess(cmd, 1, stdout='', stderr='')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    detect_commit_sha()
    detect_github_repo()
    session = list(timeouts)
    timeouts.clear()
    resolve_commits(['v1'], tmp_path)
    assert session == [2, 2]
    assert timeouts == [5]


_UNANSWERABLE: list[Exception] = [
    FileNotFoundError('git not found'),
    PermissionError(13, 'Permission denied', 'git'),
    subprocess.TimeoutExpired(cmd='git', timeout=5),
]


@pytest.mark.parametrize('error', _UNANSWERABLE, ids=lambda error: type(error).__name__)
def test_a_git_that_cannot_run_answers_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, error: Exception
) -> None:
    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise error

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert resolve_commits(['v1'], tmp_path) is None
    assert is_shallow(tmp_path) is None
    assert commits_between(['a' * 40], 'b' * 40, tmp_path) is None
    assert tags_by_commit(tmp_path) == {}


def test_an_unrecognized_shallow_answer_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A git too old for `--is-shallow-repository` echoes the flag back."""

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='--is-shallow-repository\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert is_shallow(tmp_path) is None
