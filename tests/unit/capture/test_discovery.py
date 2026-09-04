"""Unit tests for resolving the suite's single glossary."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from pytest_given import Glossary
from pytest_given.capture import (
    FileGlossary,
    activity,
    path,
    resolve_glossary,
    story,
)
from pytest_given.capture.story import restore_story_registry
from pytest_given.model import PytestGivenError


class _FakeConftest:
    """Stands in for a conftest module object: a `__file__` and some attributes.

    `resolve_glossary` takes plain module objects rather than a pytest session,
    so this is the whole of the scaffolding a test needs.
    """

    def __init__(self, file: str, **attrs: object) -> None:
        self.__file__ = file
        for name, value in attrs.items():
            setattr(self, name, value)


@pytest.fixture
def _clean_story_registry() -> Iterator[None]:
    restore_story_registry({})
    yield
    restore_story_registry({})


@pytest.mark.usefixtures('_clean_story_registry')
def test_two_stories_reaching_different_glossaries_raise() -> None:
    """Read straight off the story tree, so two stories cannot smuggle in two
    glossaries between them."""
    g1 = Glossary()
    g2 = Glossary()
    first = story(
        'Coverage Story A',
        [activity(g1.actor('Guest One'), g1.verb('search'), g1.work_object('Room'))],
    )
    second = story(
        'Coverage Story B',
        [activity(g2.actor('Guest Two'), g2.verb('book'), g2.work_object('Suite'))],
    )
    with pytest.raises(PytestGivenError, match='distinct Glossary'):
        resolve_glossary([first, second], [])


@pytest.mark.usefixtures('_clean_story_registry')
def test_a_storys_glossary_wins_over_the_conftest_scan() -> None:
    g = Glossary()
    told = story(
        'Coverage Story',
        [activity(g.actor('Guest'), g.verb('search'), g.work_object('Room'))],
    )
    other = Glossary()
    assert resolve_glossary([told], [_FakeConftest('/x/conftest.py', g=other)]) is g


def test_a_file_glossary_on_a_conftest_is_discovered(tmp_path: Path) -> None:
    md_path = tmp_path / 'conftest_glossary.md'
    md_path.write_text(
        '| Term | Meaning |\n|---|---|\n| Guest | A person booking. |\n',
        encoding='utf-8',
    )
    file_glossary = FileGlossary(md_path)
    modules = [_FakeConftest('/x/conftest.py', g=file_glossary)]
    assert resolve_glossary([], modules) is file_glossary


def test_a_plain_glossary_on_a_conftest_is_discovered() -> None:
    g = Glossary()
    g.actor('Guest')
    assert resolve_glossary([], [_FakeConftest('/x/conftest.py', g=g)]) is g


def test_a_module_that_is_not_a_conftest_is_ignored() -> None:
    g = Glossary()
    g.actor('Guest')
    assert resolve_glossary([], [_FakeConftest('/x/plugin.py', g=g)]) is None


def test_two_conftest_glossaries_raise() -> None:
    first, second = Glossary(), Glossary()
    first.actor('Guest')
    second.actor('Host')
    modules = [
        _FakeConftest('/a/conftest.py', g=first),
        _FakeConftest('/b/conftest.py', g=second),
    ]
    with pytest.raises(PytestGivenError, match='multiple Glossary instances'):
        resolve_glossary([], modules)


def test_one_glossary_shared_by_two_conftests_is_one_glossary() -> None:
    """Deduped by identity — the same object imported twice is not a conflict."""
    g = Glossary()
    g.actor('Guest')
    modules = [
        _FakeConftest('/a/conftest.py', g=g),
        _FakeConftest('/b/conftest.py', g=g),
    ]
    assert resolve_glossary([], modules) is g


def test_no_stories_and_no_conftest_glossary_resolves_to_none() -> None:
    assert resolve_glossary([], []) is None


@pytest.mark.usefixtures('_clean_story_registry')
def test_a_story_referencing_no_glossary_falls_back_to_the_conftest_scan() -> None:
    bare = story('Wordless Story', [activity(path('a guest', 'books', 'a room'))])
    g = Glossary()
    g.actor('Guest')
    assert resolve_glossary([bare], [_FakeConftest('/x/conftest.py', g=g)]) is g
