# Expose the pytest-given TableGlossary at conftest module level so the plugin
# discovers it and renders the Glossary tab for the self-documenting scenarios.
import os
from pathlib import Path

import pytest

from pytest_given.capture.source import current_rootdir, restore_rootdir
from pytest_given.capture.story import restore_story_registry, snapshot_story_registry
from tests.git_repo import GitRepo, make_git_repo
from tests.ubiquitous_language import pg  # noqa: F401


@pytest.fixture
def git_repo(tmp_path: Path, isolated_git_env: None) -> GitRepo:
    return make_git_repo(tmp_path / 'repo')


@pytest.fixture
def isolated_git_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No inherited `GIT_*` variable, and no repository found above `tmp_path`:
    run from a git hook, `GIT_DIR` would aim the git helpers at the real one."""
    for name in list(os.environ):
        if name.upper().startswith('GIT_'):
            monkeypatch.delenv(name)
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.resolve().parent))


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
