import subprocess
from pathlib import Path
from typing import Annotated

import pytest

from pytest_given import Template, given, scenario, then, when, when_then
from pytest_given.model import PytestGivenError, SourceLocation
from pytest_given.report.source_link import (
    compile_source_link,
    detect_commit_sha,
    resolve_template,
)
from tests.ubiquitous_language import pg


def test_compile_source_link_rejects_positional_index_field() -> None:
    # A positional field passes name validation but would raise IndexError at
    # substitution; reject it up front so bad templates fail fast and uniformly.
    with pytest.raises(PytestGivenError, match='positional field'):
        compile_source_link('file://{0}:{line}', project='p', commit_sha=None)


def test_compile_source_link_rejects_empty_positional_field() -> None:
    with pytest.raises(PytestGivenError, match='positional field'):
        compile_source_link('file://{}', project='p', commit_sha=None)


@scenario(t'The literal `none` disables the {pg["Source link"].low}')
def test_resolve_template_none_returns_none() -> None:
    with given(t'the {pg["Source link"].low} config set to `none`'):
        value = 'none'
    with when('the config value is resolved'):
        template = resolve_template(value)
    with then('no template comes back, so no link is rendered'):
        assert template is None


def test_resolve_template_empty_returns_none() -> None:
    assert resolve_template('') is None
    assert resolve_template(None) is None


@scenario(
    t"A named editor preset becomes that editor's {pg['Source link'].low} template"
)
@pytest.mark.parametrize(
    ('preset', 'url_scheme'),
    [
        ('vscode', 'vscode://file/{path}:{line}'),
        ('cursor', 'cursor://file/{path}:{line}'),
        ('zed', 'zed://file/{path}:{line}'),
        ('pycharm', 'pycharm://open?file={path}&line={line}'),
    ],
)
def test_resolve_template_editor_preset(
    preset: Annotated[str, given(Template('the config set to the {preset} preset'))],
    url_scheme: str,
) -> None:
    with when('the config value is resolved'):
        template = resolve_template(preset)
    with then("the template is that editor's URL scheme"):
        assert template == url_scheme


@scenario(t'A raw URL template is used as the {pg["Source link"].low} verbatim')
def test_resolve_template_raw_template_passes_through() -> None:
    with given('a raw blob-URL template rather than a preset name'):
        raw = 'https://github.com/o/r/blob/{sha}/{relpath}#L{line}'
    with when('the config value is resolved'):
        template = resolve_template(raw)
    with then('it comes back unchanged'):
        assert template == raw


@scenario(
    'An unknown preset name is refused, with the valid ones listed',
    tags=['diagnostics'],
)
def test_resolve_template_unknown_preset_raises() -> None:
    with given('a bareword that is neither a known preset nor a template'):
        value = 'emacs'
    with (
        when_then('the config value is resolved', 'the value is refused'),
        pytest.raises(PytestGivenError) as exc,
    ):
        resolve_template(value)
    with then('the error names the offender and lists every valid preset'):
        msg = str(exc.value)
        assert 'emacs' in msg
        assert 'vscode' in msg
        assert 'cursor' in msg
        assert 'zed' in msg
        assert 'pycharm' in msg
        assert 'github' in msg


_GH_TEMPLATE = 'https://github.com/{org}/{repo}/blob/{{sha}}/{{relpath}}#L{{line}}'


def _clear_github_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('GITHUB_REPOSITORY', raising=False)


def test_resolve_github_preset_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_github_env(monkeypatch)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'myorg/myrepo')
    assert resolve_template('github') == _GH_TEMPLATE.format(org='myorg', repo='myrepo')


@scenario('The github preset prefers GITHUB_REPOSITORY over the git remote')
def test_resolve_github_preset_env_beats_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with given('GITHUB_REPOSITORY naming one repository'):
        _clear_github_env(monkeypatch)
        monkeypatch.setenv('GITHUB_REPOSITORY', 'env-org/env-repo')
    with given('an origin remote naming a different one'):

        def fake_run(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='https://github.com/git-org/git-repo.git\n', stderr=''
            )

        monkeypatch.setattr(subprocess, 'run', fake_run)
    with when('the github preset is resolved'):
        template = resolve_template('github')
    with then("the template points at the environment's repository"):
        assert template == _GH_TEMPLATE.format(org='env-org', repo='env-repo')


@scenario('The github preset derives org and repo from the git origin remote')
def test_resolve_github_preset_from_https_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with given('no GITHUB_REPOSITORY, and an https origin remote'):
        _clear_github_env(monkeypatch)

        def fake_run(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='https://github.com/o/r.git\n', stderr=''
            )

        monkeypatch.setattr(subprocess, 'run', fake_run)
    with when('the github preset is resolved'):
        template = resolve_template('github')
    with then("the blob-URL template names the remote's org and repo"):
        assert template == _GH_TEMPLATE.format(org='o', repo='r')


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


@scenario(
    'The github preset refuses a remote that is not on GitHub',
    tags=['diagnostics'],
)
def test_resolve_github_preset_non_github_remote_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with given('no GITHUB_REPOSITORY, and an origin remote on another host'):
        _clear_github_env(monkeypatch)

        def fake_run(
            cmd: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='https://gitlab.com/o/r.git\n', stderr=''
            )

        monkeypatch.setattr(subprocess, 'run', fake_run)
    with (
        when_then('the github preset is resolved', 'the preset is refused'),
        pytest.raises(PytestGivenError) as exc,
    ):
        resolve_template('github')
    with then('the error points at the env var and the raw-template escape hatch'):
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
    url = compile_source_link(
        'vscode://file/{path}:{line}',
        project='proj',
        commit_sha=None,
    )(_src())
    expected = (tmp_path / 'tests/test_x.py').resolve().as_posix()
    assert url == f'vscode://file/{expected}:7'


def test_format_pycharm_uses_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    url = compile_source_link(
        'pycharm://open?file={path}&line={line}',
        project='myproj',
        commit_sha=None,
    )(_src())
    expected = (tmp_path / 'tests/test_x.py').resolve().as_posix()
    assert url == f'pycharm://open?file={expected}&line=7'


def test_format_github_uses_sha_and_relpath() -> None:
    url = compile_source_link(
        'https://github.com/o/r/blob/{sha}/{relpath}#L{line}',
        project='p',
        commit_sha='deadbeef',
    )(_src())
    assert url == 'https://github.com/o/r/blob/deadbeef/tests/test_x.py#L7'


def test_compile_reuses_validation_across_sources() -> None:
    """A compiled template substitutes each SourceLocation independently."""
    substitute = compile_source_link(
        'foo://{relpath}#L{line}', project='p', commit_sha=None
    )
    assert substitute(_src('a.py', 1)) == 'foo://a.py#L1'
    assert substitute(_src('b.py', 2)) == 'foo://b.py#L2'


def test_compile_missing_sha_raises_eagerly() -> None:
    """Validation happens at compile time — no SourceLocation required."""
    with pytest.raises(PytestGivenError) as exc:
        compile_source_link(
            'https://github.com/o/r/blob/{sha}/{relpath}#L{line}',
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
    url = compile_source_link(
        '{relpath}/done',
        project='p',
        commit_sha=None,
    )(_src('a.py', 1))
    assert url == 'a.py/done'


def test_format_attribute_access_raises_clear_error() -> None:
    """`{path.parent}` passes head-only validation but explodes at format()
    time with a confusing AttributeError on str — reject it up front."""
    with pytest.raises(PytestGivenError) as exc:
        compile_source_link(
            'foo://x/{path.parent}',
            project='p',
            commit_sha=None,
        )
    msg = str(exc.value)
    assert 'path.parent' in msg or 'attribute' in msg.lower()


def test_format_index_access_raises_clear_error() -> None:
    with pytest.raises(PytestGivenError) as exc:
        compile_source_link(
            'foo://x/{relpath[0]}',
            project='p',
            commit_sha=None,
        )
    msg = str(exc.value)
    assert 'relpath[0]' in msg or 'index' in msg.lower() or 'attribute' in msg.lower()


def test_format_unknown_variable_raises() -> None:
    with pytest.raises(PytestGivenError) as exc:
        compile_source_link(
            'foo://x/{branch}',
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


def test_resolve_github_preset_unrunnable_git_raises_the_plugin_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same failure on the preset path stays a `PytestGivenError`.

    `pytest_configure` catches only that; a bare `PermissionError` reaches the
    user as an INTERNALERROR instead of the message naming the escape hatch.
    """
    _clear_github_env(monkeypatch)

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError(13, 'Permission denied', 'git')

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(PytestGivenError, match='could not detect an org/repo'):
        resolve_template('github')
