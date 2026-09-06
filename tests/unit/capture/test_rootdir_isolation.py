"""The session rootdir is a module global that rootdir-dependent tests
overwrite. `tests/conftest.py` restores it after each test, because a test that
leaves it cleared unlinks every scenario collected after it — silently, and only
where pytest cannot relativize `item.location` on its own (see
docs/wsl-development.md).
"""

from pytest_given.capture.source import current_rootdir, restore_rootdir


def test_a_test_may_clear_the_session_rootdir() -> None:
    restore_rootdir(None)
    assert current_rootdir() is None


def test_the_next_test_still_sees_the_session_rootdir() -> None:
    assert current_rootdir() is not None
