"""Unit tests for the pre-getrepr traceback filter (`plugin/runtest.py`)."""

from collections.abc import Callable
from typing import Any, cast

from pytest_given.plugin.runtest import _filter_internal_frames


class _FakeEntry:
    def __init__(self, path: str) -> None:
        self.path = path


class _FakeTraceback(list):  # type: ignore[type-arg]
    def filter(self, fn: Callable[[Any], bool]) -> _FakeTraceback:
        return _FakeTraceback(e for e in self if fn(e))


class _FakeExcinfo:
    def __init__(self, *paths: str) -> None:
        self.traceback = _FakeTraceback(_FakeEntry(p) for p in paths)


def test_filter_internal_frames_keeps_only_user_entries() -> None:
    """The pre-filter drops pluggy/_pytest/decorator entries before getrepr, so
    only user frames survive to be formatted."""
    excinfo = _FakeExcinfo(
        '/venv/site-packages/pluggy/_hooks.py',
        '/venv/site-packages/_pytest/runner.py',
        '/proj/src/pytest_given/capture/decorators.py',
        '/proj/tests/test_billing.py',
    )
    _filter_internal_frames(cast(Any, excinfo))
    assert [str(e.path) for e in excinfo.traceback] == ['/proj/tests/test_billing.py']


def test_filter_internal_frames_keeps_original_when_all_internal() -> None:
    """A failure raised entirely within plugin/library code would filter to an
    empty traceback; the original is kept so getrepr still has a crash frame."""
    excinfo = _FakeExcinfo(
        '/venv/site-packages/pluggy/_hooks.py',
        '/venv/site-packages/_pytest/runner.py',
    )
    _filter_internal_frames(cast(Any, excinfo))
    assert len(excinfo.traceback) == 2
