import pytest

from pytest_given.capture.source import current_rootdir, restore_rootdir
from pytest_given.capture.story import restore_story_registry, snapshot_story_registry


@pytest.fixture(autouse=True)
def _preserve_session_rootdir():
    """Hand each test back the rootdir the session started with.

    Rootdir is a module global, and the tests that exercise rootdir-dependent
    capture overwrite it. Leaving one cleared costs nothing where pytest
    relativizes `item.location` itself, so it stays invisible — but where it
    cannot (a shared WSL+Windows checkout, see docs/wsl-development.md) every
    scenario collected afterwards records an absolute path instead of a link.
    """
    previous = current_rootdir()
    yield
    restore_rootdir(previous)


@pytest.fixture(autouse=True)
def _utf8_subprocess_output(monkeypatch):
    """`runpytest_subprocess` decodes the child's output as UTF-8, but before
    Python 3.15 a Windows child writes a pipe in its code page (cp1252)."""
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')


@pytest.fixture
def isolated_story_registry():
    """An empty story registry for the test, and the session's back after.

    The registry is the report's story list, so a test that clears it rather
    than restoring it takes the self-report's own stories with it.
    """
    previous = snapshot_story_registry()
    restore_story_registry({})
    yield
    restore_story_registry(previous)
