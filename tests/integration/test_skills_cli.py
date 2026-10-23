from pathlib import Path

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.cli import main

AUTHORING = 'pytest-given-authoring'


def _install(dest: Path) -> int:
    return main(['skills', 'install', '--dest', str(dest)])


def test_install_writes_bundled_skill(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    assert _install(dest) == 0
    skill_md = dest / AUTHORING / 'SKILL.md'
    assert skill_md.read_text(encoding='utf-8').startswith('---')
    assert (dest / AUTHORING / 'references' / 'scenarios.md').is_file()


def test_install_overwrites_local_edits(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    skill_md = dest / AUTHORING / 'SKILL.md'
    original = skill_md.read_bytes()
    skill_md.write_text('locally edited', encoding='utf-8')
    assert _install(dest) == 0
    assert skill_md.read_bytes() == original


def test_install_removes_stale_files_inside_owned_dirs(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    stale = dest / AUTHORING / 'references' / 'obsolete.md'
    stale.write_text('from an older version', encoding='utf-8')
    assert _install(dest) == 0
    assert not stale.exists()


@scenario(
    '`skills install` removes what no bundled file accounts for, the directories '
    'it empties included'
)
def test_install_prunes_directories_emptied_by_stale_file_removal(
    tmp_path: Path,
) -> None:
    """A stale file's directory must not linger once the file is gone: the
    mirror owns the bundled trees, and an empty directory is drift too. A
    nested chain prunes in one pass, deepest first."""
    with given('installed skills holding a stale file two directories deep'):
        dest = tmp_path / 'skills'
        _install(dest)
        deep = dest / AUTHORING / 'references' / 'old' / 'older'
        deep.mkdir(parents=True)
        (deep / 'obsolete.md').write_text('from an older version', encoding='utf-8')
    with when('skills install runs again'):
        exit_code = _install(dest)
    with then('it succeeds'):
        assert exit_code == 0
    with then('the stale file and both directories it emptied are gone'):
        assert not (dest / AUTHORING / 'references' / 'old').exists()
    with then('a bundled file beside them stays in place'):
        assert (dest / AUTHORING / 'references' / 'scenarios.md').is_file()


def test_install_prunes_a_manually_created_empty_directory(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    empty = dest / AUTHORING / 'empty-dir'
    empty.mkdir()
    assert _install(dest) == 0
    assert not empty.exists()


def test_install_prunes_a_stale_directory_holding_a_symlink(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    stale = dest / AUTHORING / 'old'
    stale.mkdir()
    try:
        (stale / 'link').symlink_to(tmp_path, target_is_directory=True)
    except OSError:  # Windows without the right to create symlinks
        pytest.skip('this OS user cannot create symlinks')
    assert _install(dest) == 0
    assert not stale.exists()
    assert tmp_path.is_dir()


def test_install_keeps_directories_holding_bundled_files(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    assert (dest / AUTHORING / 'references').is_dir()
    assert _install(dest) == 0
    assert (dest / AUTHORING / 'references' / 'scenarios.md').is_file()


def test_install_leaves_sibling_skills_alone(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    own = dest / 'my-own-skill' / 'SKILL.md'
    own.parent.mkdir(parents=True)
    own.write_text('mine', encoding='utf-8')
    assert _install(dest) == 0
    assert own.read_text(encoding='utf-8') == 'mine'


def test_check_in_sync_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    assert main(['skills', 'install', '--dest', str(dest), '--check']) == 0
    assert 'in sync' in capsys.readouterr().out


def test_check_reports_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / 'skills'
    _install(dest)
    (dest / AUTHORING / 'SKILL.md').write_text('edited', encoding='utf-8')
    (dest / AUTHORING / 'references' / 'scenarios.md').unlink()
    (dest / AUTHORING / 'extra.md').write_text('stale', encoding='utf-8')
    capsys.readouterr()
    assert main(['skills', 'install', '--dest', str(dest), '--check']) == 1
    out = capsys.readouterr().out
    assert 'differs' in out
    assert 'missing' in out
    assert 'stale' in out


def test_check_reports_an_empty_directory_as_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A directory the mirror would prune is drift a `--check` must name, or
    an in-sync report lies about an install that would still write."""
    dest = tmp_path / 'skills'
    _install(dest)
    empty = dest / AUTHORING / 'empty-dir'
    empty.mkdir()
    capsys.readouterr()
    assert main(['skills', 'install', '--dest', str(dest), '--check']) == 1
    out = capsys.readouterr().out
    assert 'stale' in out
    assert 'empty-dir' in out
    assert '(directory)' in out


def test_check_writes_nothing(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    assert main(['skills', 'install', '--dest', str(dest), '--check']) == 1
    assert not dest.exists()


def test_skills_without_subcommand_reports_its_own_usage(capsys) -> None:
    """The usage names `install` — the root parser's help never did."""
    with pytest.raises(SystemExit) as excinfo:
        main(['skills'])
    assert excinfo.value.code == 2
    assert 'install' in capsys.readouterr().err


REPO_SKILLS = Path(__file__).resolve().parents[2] / '.claude' / 'skills'


def test_repo_dogfood_copy_is_in_sync() -> None:
    """`.claude/skills/` is regenerated via `uv run pytest-given skills install`."""
    assert main(['skills', 'install', '--dest', str(REPO_SKILLS), '--check']) == 0


def test_skills_install_reports_a_write_failure_as_a_cli_error(
    tmp_path, monkeypatch, capsys
) -> None:
    """An unwritable destination is a CLI error, not a traceback."""

    def refuse(self: Path, data: bytes) -> int:
        raise PermissionError('read-only file system')

    monkeypatch.setattr(Path, 'write_bytes', refuse)
    assert main(['skills', 'install', '--dest', str(tmp_path)]) == 1
    assert 'read-only file system' in capsys.readouterr().err
