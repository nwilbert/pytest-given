"""Unit tests for resolving the suite's single glossary."""

import sys
from pathlib import Path

import pytest

from pytest_given import Glossary
from pytest_given.capture import (
    ParagraphGlossary,
    TableGlossary,
    sentence,
    session_glossary,
    story,
)
from pytest_given.capture.glossary import registered_glossaries
from pytest_given.capture.glossary_resolution import resolve_glossary
from pytest_given.model import (
    NarrationTermRef,
    PytestGivenError,
    SourceLocation,
    TermId,
)


def test_a_constructed_glossary_registers_with_its_construction_site() -> None:
    glossary, line = Glossary(), sys._getframe().f_lineno
    site = registered_glossaries()[glossary]
    assert site is not None
    assert (Path(site.relpath).name, site.line) == (Path(__file__).name, line)


def test_markdown_glossaries_register_too(tmp_path: Path) -> None:
    table_path = tmp_path / 'table.md'
    table_path.write_text('| Term | Meaning |\n|---|---|\n| Guest | A person. |\n')
    paragraph_path = tmp_path / 'paragraph.md'
    paragraph_path.write_text('**Order**:\nA request for goods.\n')
    table, paragraph = TableGlossary(table_path), ParagraphGlossary(paragraph_path)
    assert {table, paragraph} <= registered_glossaries().keys()


def test_a_registered_glossary_is_the_suite_glossary() -> None:
    glossary = Glossary()
    assert resolve_glossary({glossary: None}) is glossary


def test_two_registered_glossaries_raise_naming_both_sites() -> None:
    first = SourceLocation(relpath='tests/glossary.py', line=3)
    second = SourceLocation(relpath='tests/test_booking.py', line=9)
    with pytest.raises(PytestGivenError) as raised:
        resolve_glossary({Glossary(): first, Glossary(): second})
    message = str(raised.value)
    assert '2 distinct glossaries' in message
    assert 'tests/glossary.py:3' in message
    assert 'tests/test_booking.py:9' in message


def test_no_registered_glossary_resolves_to_none() -> None:
    assert resolve_glossary({}) is None


@pytest.mark.usefixtures('isolated_story_registry')
def test_the_session_glossary_has_its_kinds_inferred_and_its_refs_resolved() -> None:
    g = Glossary()
    guest = g('Guest', 'Books a **Room**.')
    room = g.work_object('Room')
    told = story('Booking', [sentence(guest, g.activity('book'), room)])
    resolved = session_glossary([told], {g: None})
    assert resolved is not None
    [guest_term, *_] = resolved.terms
    assert guest_term.kind == 'actor'
    assert guest_term.definition is not None
    assert NarrationTermRef(term_id=TermId('room'), display='Room') in (
        guest_term.definition.parts
    )


def test_no_glossary_is_no_session_glossary() -> None:
    assert session_glossary([], {}) is None


def test_a_markdown_glossary_that_fails_to_load_is_not_registered(
    tmp_path: Path,
) -> None:
    before = registered_glossaries()
    with pytest.raises(PytestGivenError, match='not found'):
        TableGlossary(tmp_path / 'missing.md')
    assert registered_glossaries() == before
