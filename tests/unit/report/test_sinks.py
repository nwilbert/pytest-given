"""Unit tests for the sink render/write/discard split (`report/sinks.py`)."""

from pathlib import Path

import pytest

from pytest_given import PytestGivenError
from pytest_given.report.sinks import SinkConfig, discard_stale_sinks


def test_discard_stale_sinks_removes_the_paths_this_run_would_have_written(
    tmp_path,
) -> None:
    stale = tmp_path / 'report.html'
    stale.write_text('previous run', encoding='utf-8')
    notes = discard_stale_sinks(SinkConfig(html_path=stale))
    assert not stale.exists()
    assert notes == [f'Removed the previous {stale} — it would read as current.']


def test_discard_stale_sinks_reports_an_unlink_failure_instead_of_raising(
    tmp_path, monkeypatch
) -> None:
    """The caller is already handling a failed write; the usual reason that
    write failed is also a reason the unlink will, and an exception here would
    escape `pytest_sessionfinish` as the bare traceback the handler exists to
    prevent."""
    stale = tmp_path / 'report.html'
    stale.write_text('previous run', encoding='utf-8')

    def refuse(self: Path, **kwargs: object) -> None:
        raise PermissionError('read-only file system')

    monkeypatch.setattr(Path, 'unlink', refuse)
    [note] = discard_stale_sinks(SinkConfig(html_path=stale))
    assert note == f'Could not remove the previous {stale}: read-only file system'


def test_a_sink_path_that_cannot_be_a_report_file_is_refused(tmp_path) -> None:
    """A bare `--given-html` consumes the next argument, so a mis-ordered
    invocation would otherwise aim the renderer at the user's own source file —
    and `discard_stale_sinks` would then unlink it as a stale report."""
    source = tmp_path / 'test_demo.py'
    source.write_text('def test_x(): pass', encoding='utf-8')
    with pytest.raises(PytestGivenError) as excinfo:
        SinkConfig(html_path=source)
    assert 'must end in .html or .htm' in str(excinfo.value)
    assert 'test_demo.py' in str(excinfo.value)
    assert source.read_text(encoding='utf-8') == 'def test_x(): pass'


@pytest.mark.parametrize(
    ('field', 'expected'),
    [
        ('json_path', '.json'),
        ('html_path', '.html or .htm'),
        ('md_path', '.md or .markdown'),
    ],
)
def test_every_sink_states_the_suffixes_it_accepts(field: str, expected: str) -> None:
    with pytest.raises(PytestGivenError) as excinfo:
        SinkConfig(**{field: Path('report.py')})
    assert f'must end in {expected}' in str(excinfo.value)


@pytest.mark.parametrize(
    'path', [Path('r.json'), Path('R.JSON'), Path('nested/dir/r.json')]
)
def test_a_well_formed_sink_path_is_accepted(path: Path) -> None:
    assert SinkConfig(json_path=path).json_path == path
