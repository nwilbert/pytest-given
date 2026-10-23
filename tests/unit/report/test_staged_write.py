from pathlib import Path

import pytest

from pytest_given.report import write_all_or_none


def test_a_failing_rename_leaves_no_temporary_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / 'a.json', tmp_path / 'b.html'
    real_replace = Path.replace

    def replace(self: Path, target: Path) -> Path:
        if Path(target).name == second.name:
            raise PermissionError('locked')
        return real_replace(self, target)

    monkeypatch.setattr(Path, 'replace', replace)
    with pytest.raises(PermissionError):
        write_all_or_none([(first, 'one'), (second, 'two')])
    assert sorted(path.name for path in tmp_path.iterdir()) == ['a.json']
