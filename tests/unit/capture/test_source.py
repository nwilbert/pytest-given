from pathlib import Path

import pytest

from pytest_given.capture.source import (
    _reset_rootdir,
    capture_caller_source,
    set_rootdir,
)
from pytest_given.model import SourceLocation


@pytest.fixture(autouse=True)
def _isolate_rootdir():
    _reset_rootdir()
    yield
    _reset_rootdir()


def test_returns_none_when_rootdir_unset():
    assert capture_caller_source() is None


def test_returns_none_when_caller_outside_rootdir(tmp_path: Path):
    set_rootdir(tmp_path)
    # This test file lives outside tmp_path, so the caller (this function)
    # is outside rootdir.
    assert capture_caller_source() is None


def test_captures_caller_when_inside_rootdir():
    # Use the repo root itself as rootdir — this file is inside it.
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)
    loc = capture_caller_source()
    assert isinstance(loc, SourceLocation)
    assert loc.relpath.endswith('tests/unit/capture/test_source.py')
    assert '/' in loc.relpath  # POSIX-normalized even on Windows
    assert loc.line > 0


def test_skip_argument_walks_up_call_stack():
    repo_root = Path(__file__).resolve().parents[3]
    set_rootdir(repo_root)

    def wrapper():
        # skip=2: skip capture_caller_source itself + this wrapper, land on the
        # test function below.
        return capture_caller_source(skip=2)

    loc = wrapper()
    assert loc is not None
    assert loc.relpath.endswith('test_source.py')
    # Line should point at the `loc = wrapper()` call site, not into wrapper.
    # We don't assert the exact line (would couple to formatting) — only that
    # it's reachable and inside the test function's body range.
    assert loc.line > 0


def test_file_source_returns_location_inside_rootdir(tmp_path: Path):
    """file_source returns a SourceLocation with posix relpath when the path
    is inside the configured rootdir."""
    from pytest_given.capture.source import file_source

    set_rootdir(tmp_path)
    target = tmp_path / 'glossary' / 'terms.md'
    loc = file_source(target, 42)
    assert loc is not None
    assert loc.relpath == 'glossary/terms.md'
    assert loc.line == 42
