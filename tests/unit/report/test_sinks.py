"""Unit tests for the sink render/write/discard split (`report/sinks.py`)."""

from pathlib import Path

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
