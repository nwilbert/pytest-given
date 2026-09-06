# Expose the pytest-given FileGlossary at conftest module level so the plugin
# discovers it and renders the Glossary tab for the self-documenting scenarios.
import pytest

from pytest_given.capture.source import current_rootdir, restore_rootdir
from tests.ubiquitous_language import pg  # noqa: F401


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
