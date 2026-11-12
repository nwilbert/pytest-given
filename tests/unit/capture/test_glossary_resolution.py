"""Unit tests for resolving the suite's single glossary."""

from pathlib import Path

import pytest

from pytest_given import Glossary
from pytest_given.capture import (
    FileGlossary,
    clause,
    sentence,
    session_glossary,
    story,
)
from pytest_given.capture.glossary_resolution import resolve_glossary
from pytest_given.model import NarrationTermRef, PytestGivenError, TermId


class _FakeConftest:
    """Stands in for a conftest module object: a `__file__` and some attributes.

    `resolve_glossary` takes plain module objects rather than a pytest session,
    so this is the whole of the scaffolding a test needs.
    """

    def __init__(self, file: str, **attrs: object) -> None:
        self.__file__ = file
        for name, value in attrs.items():
            setattr(self, name, value)


@pytest.mark.usefixtures('isolated_story_registry')
def test_two_stories_reaching_different_glossaries_raise() -> None:
    """Read straight off the story tree, so two stories cannot smuggle in two
    glossaries between them."""
    g1 = Glossary()
    g2 = Glossary()
    first = story(
        'Coverage Story A',
        [
            sentence(
                g1.actor('Guest One'), g1.activity('search'), g1.work_object('Room')
            )
        ],
    )
    second = story(
        'Coverage Story B',
        [sentence(g2.actor('Guest Two'), g2.activity('book'), g2.work_object('Suite'))],
    )
    with pytest.raises(PytestGivenError, match='distinct Glossary'):
        resolve_glossary([first, second], [])


@pytest.mark.usefixtures('isolated_story_registry')
def test_a_storys_glossary_wins_over_the_conftest_scan() -> None:
    g = Glossary()
    told = story(
        'Coverage Story',
        [sentence(g.actor('Guest'), g.activity('search'), g.work_object('Room'))],
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


@pytest.mark.usefixtures('isolated_story_registry')
def test_a_story_referencing_no_glossary_falls_back_to_the_conftest_scan() -> None:
    bare = story('Wordless Story', [sentence(clause('a guest', 'books', 'a room'))])
    g = Glossary()
    g.actor('Guest')
    assert resolve_glossary([bare], [_FakeConftest('/x/conftest.py', g=g)]) is g


@pytest.mark.usefixtures('isolated_story_registry')
def test_the_session_glossary_has_its_kinds_inferred_and_its_refs_resolved() -> None:
    g = Glossary()
    guest = g('Guest', 'Books a **Room**.')
    room = g.work_object('Room')
    told = story('Booking', [sentence(guest, g.activity('book'), room)])
    resolved = session_glossary([told], [])
    assert resolved is not None
    [guest_term, *_] = resolved.terms
    assert guest_term.kind == 'actor'
    assert guest_term.definition is not None
    assert NarrationTermRef(term_id=TermId('room'), display='Room') in (
        guest_term.definition.parts
    )


def test_no_glossary_is_no_session_glossary() -> None:
    assert session_glossary([], []) is None
