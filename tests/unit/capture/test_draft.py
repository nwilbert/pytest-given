import pytest

from pytest_given import PytestGivenError
from pytest_given.capture.draft import (
    DraftActor,
    DraftVerb,
    DraftWorkObject,
    draft,
)


def test_draft_actor_holds_kind_and_text():
    d = draft.actor('Concierge')
    assert isinstance(d, DraftActor)
    assert d.kind == 'actor'
    assert d.text == 'Concierge'


def test_draft_work_object_holds_kind_and_text():
    d = draft.work_object('loyalty bonus')
    assert isinstance(d, DraftWorkObject)
    assert d.kind == 'object'
    assert d.text == 'loyalty bonus'


def test_draft_verb_holds_kind_and_text():
    d = draft.verb('redeems')
    assert isinstance(d, DraftVerb)
    assert d.kind == 'verb'
    assert d.text == 'redeems'


def test_two_drafts_with_same_text_compare_equal():
    assert draft.actor('Concierge') == draft.actor('Concierge')


def test_draft_str_returns_text():
    assert str(draft.actor('Concierge')) == 'Concierge'
    assert str(draft.verb('redeems')) == 'redeems'


@pytest.mark.parametrize('text', ['', '   ', '\t'])
def test_draft_actor_empty_text_raises(text):
    with pytest.raises(PytestGivenError, match='draft text is empty'):
        draft.actor(text)


@pytest.mark.parametrize('text', ['', '   '])
def test_draft_work_object_empty_text_raises(text):
    with pytest.raises(PytestGivenError, match='draft text is empty'):
        draft.work_object(text)


@pytest.mark.parametrize('text', ['', '   '])
def test_draft_verb_empty_text_raises(text):
    with pytest.raises(PytestGivenError, match='draft text is empty'):
        draft.verb(text)
