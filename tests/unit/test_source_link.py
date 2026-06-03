import subprocess
from pathlib import Path

import pytest

from pytest_given.model import PytestGivenError, SourceLocation
from pytest_given.source_link import (
    detect_commit_sha,
    format_source_link,
    resolve_template,
)


def test_resolve_template_none_returns_none() -> None:
    assert resolve_template('none') is None


def test_resolve_template_empty_returns_none() -> None:
    assert resolve_template('') is None
    assert resolve_template(None) is None


def test_resolve_template_vscode_preset() -> None:
    assert resolve_template('vscode') == 'vscode://file/{path}:{line}'


def test_resolve_template_cursor_preset() -> None:
    assert resolve_template('cursor') == 'cursor://file/{path}:{line}'


def test_resolve_template_zed_preset() -> None:
    assert resolve_template('zed') == 'zed://file/{path}:{line}'


def test_resolve_template_pycharm_preset() -> None:
    assert resolve_template('pycharm') == 'pycharm://open?file={path}&line={line}'


def test_resolve_template_raw_template_passes_through() -> None:
    raw = 'https://github.com/o/r/blob/{sha}/{relpath}#L{line}'
    assert resolve_template(raw) == raw


def test_resolve_template_unknown_preset_raises() -> None:
    with pytest.raises(PytestGivenError) as exc:
        resolve_template('emacs')
    msg = str(exc.value)
    assert 'emacs' in msg
    assert 'vscode' in msg
    assert 'pycharm' in msg
    assert 'github' in msg


_GH_TEMPLATE = 'https://github.com/{org}/{repo}/blob/{{sha}}/{{relpath}}#L{{line}}'


def _clear_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)


def test_resolve_github_preset_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_github_env(monkeypatch)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'myorg/myrepo')
    assert resolve_template('github') == _GH_TEMPLATE.format(org='myorg', repo='myrepo')


def test_resolve_github_preset_env_beats_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'env-org/env-repo')

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='https://github.com/git-org/git-repo.git\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert resolve_template('github') == _GH_TEMPLATE.format(
        org='env-org', repo='env-repo'
    )


def test_resolve_github_preset_from_https_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='https://github.com/o/r.git\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert resolve_template('github') == _GH_TEMPLATE.format(org='o', repo='r')


def test_resolve_github_preset_from_https_remote_no_git_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='https://github.com/o/r\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert resolve_template('github') == _GH_TEMPLATE.format(org='o', repo='r')


def test_resolve_github_preset_from_ssh_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='git@github.com:o/r.git\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert resolve_template('github') == _GH_TEMPLATE.format(org='o', repo='r')


def test_resolve_github_preset_non_github_remote_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd, 0, stdout='https://gitlab.com/o/r.git\n', stderr=''
        )

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(PytestGivenError) as exc:
        resolve_template('github')
    msg = str(exc.value)
    assert 'GITHUB_REPOSITORY' in msg
    assert '{sha}' in msg


def test_resolve_github_preset_no_git_and_no_env_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError('git not found')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(PytestGivenError):
        resolve_template('github')


def _src(relpath: str = 'tests/test_x.py', line: int = 7) -> SourceLocation:
    return SourceLocation(relpath=relpath, line=line)


def test_format_vscode_uses_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    url = format_source_link(
        'vscode://file/{path}:{line}',
        source=_src(),
        project='proj',
        commit_sha=None,
    )
    expected = (tmp_path / 'tests/test_x.py').resolve().as_posix()
    assert url == f'vscode://file/{expected}:7'


def test_format_pycharm_uses_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    url = format_source_link(
        'pycharm://open?file={path}&line={line}',
        source=_src(),
        project='myproj',
        commit_sha=None,
    )
    expected = (tmp_path / 'tests/test_x.py').resolve().as_posix()
    assert url == f'pycharm://open?file={expected}&line=7'


def test_format_github_uses_sha_and_relpath() -> None:
    url = format_source_link(
        'https://github.com/o/r/blob/{sha}/{relpath}#L{line}',
        source=_src(),
        project='p',
        commit_sha='deadbeef',
    )
    assert url == 'https://github.com/o/r/blob/deadbeef/tests/test_x.py#L7'


def test_format_missing_sha_raises() -> None:
    with pytest.raises(PytestGivenError) as exc:
        format_source_link(
            'https://github.com/o/r/blob/{sha}/{relpath}#L{line}',
            source=_src(),
            project='p',
            commit_sha=None,
        )
    msg = str(exc.value)
    assert '{sha}' in msg
    assert 'GITHUB_SHA' in msg or 'git' in msg.lower()


def test_format_with_trailing_literal_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Templates with literal text after the last placeholder parse cleanly.

    `string.Formatter().parse` yields a final tuple with field_name=None for
    trailing literal text; the field-name extractor must skip those.
    """
    url = format_source_link(
        '{relpath}/done',
        source=_src('a.py', 1),
        project='p',
        commit_sha=None,
    )
    assert url == 'a.py/done'


def test_format_unknown_variable_raises() -> None:
    with pytest.raises(PytestGivenError) as exc:
        format_source_link(
            'foo://x/{branch}',
            source=_src(),
            project='p',
            commit_sha=None,
        )
    msg = str(exc.value)
    assert 'branch' in msg
    assert 'path' in msg
    assert 'relpath' in msg
    assert 'line' in msg


def _clear_ci_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ('GITHUB_SHA', 'CI_COMMIT_SHA', 'BUILDKITE_COMMIT'):
        monkeypatch.delenv(var, raising=False)


def test_detect_commit_sha_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ci_vars(monkeypatch)
    monkeypatch.setenv('GITHUB_SHA', 'abc123')
    assert detect_commit_sha() == 'abc123'


def test_detect_commit_sha_gitlab_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ci_vars(monkeypatch)
    monkeypatch.setenv('CI_COMMIT_SHA', 'def456')
    assert detect_commit_sha() == 'def456'


def test_detect_commit_sha_buildkite_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_ci_vars(monkeypatch)
    monkeypatch.setenv('BUILDKITE_COMMIT', '7890ab')
    assert detect_commit_sha() == '7890ab'


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
