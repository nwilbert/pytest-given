import pytest

from pytest_given.capture.kind_resolution import resolve_glossary_kinds
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    GlossaryTerm,
    PytestGivenError,
    Story,
    StoryId,
    TermId,
)


def _term(term_id, kind=None):
    return GlossaryTerm(id=TermId(term_id), kind=kind, canonical=term_id.title())


def _story(title, *triples):
    activities = tuple(
        Activity(
            id=ActivityId(index + 1),
            paths=(
                ActivityPath(
                    parts=tuple(
                        ActivityTermRef(term_id=TermId(tid), display=tid.title())
                        for tid in triple
                    )
                ),
            ),
        )
        for index, triple in enumerate(triples)
    )
    return Story(id=StoryId(title), title=title, activities=activities)


def _kind(glossary, term_id):
    return glossary[TermId(term_id)].kind


def test_infers_actor_verb_object_by_position():
    glossary = Glossary(terms=[_term('guest'), _term('search'), _term('room')])
    resolved = resolve_glossary_kinds(
        glossary, [_story('S', ('guest', 'search', 'room'))]
    )
    assert _kind(resolved, 'guest') == 'actor'
    assert _kind(resolved, 'search') == 'verb'
    assert _kind(resolved, 'room') == 'object'


def test_actor_anywhere_beats_object():
    # 'guest' appears at noun slot in story 1, actor slot in story 2 → actor wins
    glossary = Glossary(
        terms=[_term('host'), _term('greet'), _term('guest'), _term('wave')]
    )
    stories = [
        _story('S1', ('host', 'greet', 'guest')),
        _story('S2', ('guest', 'wave', 'host')),
    ]
    resolved = resolve_glossary_kinds(glossary, stories)
    assert _kind(resolved, 'guest') == 'actor'


def test_never_used_stays_kindless():
    glossary = Glossary(terms=[_term('orphan')])
    resolved = resolve_glossary_kinds(glossary, [])
    assert _kind(resolved, 'orphan') is None


def test_verb_and_noun_conflict_raises():
    glossary = Glossary(terms=[_term('a'), _term('book'), _term('c'), _term('d')])
    stories = [
        _story('S1', ('a', 'book', 'c')),  # book = verb slot
        _story('S2', ('a', 'd', 'book')),  # book = noun slot
    ]
    with pytest.raises(PytestGivenError, match='book'):
        resolve_glossary_kinds(glossary, stories)


def test_declared_kind_verified_and_kept():
    glossary = Glossary(
        terms=[
            _term('guest', 'actor'),
            _term('search', 'verb'),
            _term('room', 'object'),
        ]
    )
    resolved = resolve_glossary_kinds(
        glossary, [_story('S', ('guest', 'search', 'room'))]
    )
    assert _kind(resolved, 'guest') == 'actor'


def test_declared_verb_in_actor_slot_raises():
    glossary = Glossary(terms=[_term('search', 'verb'), _term('x'), _term('y')])
    with pytest.raises(PytestGivenError, match='search'):
        resolve_glossary_kinds(glossary, [_story('S', ('search', 'x', 'y'))])
