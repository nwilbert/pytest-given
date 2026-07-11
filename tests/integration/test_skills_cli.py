from pathlib import Path

import pytest

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


def test_check_writes_nothing(tmp_path: Path) -> None:
    dest = tmp_path / 'skills'
    assert main(['skills', 'install', '--dest', str(dest), '--check']) == 1
    assert not dest.exists()


def test_skills_without_subcommand_prints_help_and_fails() -> None:
    assert main(['skills']) == 1
