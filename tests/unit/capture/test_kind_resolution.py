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
    with pytest.raises(PytestGivenError, match=r'(?i)book'):
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
    with pytest.raises(PytestGivenError, match=r'(?i)search'):
        resolve_glossary_kinds(glossary, [_story('S', ('search', 'x', 'y'))])


def test_verb_and_actor_conflict_raises():
    glossary = Glossary(terms=[_term('a'), _term('examine'), _term('b'), _term('c')])
    stories = [
        _story('S1', ('a', 'examine', 'b')),  # examine = verb slot
        _story('S2', ('examine', 'c', 'a')),  # examine = actor slot
    ]
    with pytest.raises(PytestGivenError, match=r'(?i)examine'):
        resolve_glossary_kinds(glossary, stories)


def test_declared_object_in_actor_slot_raises():
    glossary = Glossary(terms=[_term('room', 'object'), _term('x'), _term('y')])
    with pytest.raises(PytestGivenError, match=r'(?i)room'):
        resolve_glossary_kinds(glossary, [_story('S', ('room', 'x', 'y'))])


def test_declared_actor_in_verb_slot_raises():
    """A term declared kind 'actor' that appears at position 1 (verb slot) raises."""
    glossary = Glossary(terms=[_term('subject'), _term('guest', 'actor'), _term('y')])
    with pytest.raises(PytestGivenError, match=r'(?i)verb slot'):
        resolve_glossary_kinds(glossary, [_story('S', ('subject', 'guest', 'y'))])


def test_conflict_where_names_only_offending_stories():
    """The conflict message lists only the stories that contributed the
    offending slots, not every story the term appears in."""
    glossary = Glossary(terms=[_term('guest', 'actor'), _term('x'), _term('y')])
    stories = [
        _story('ActorStory', ('guest', 'x', 'y')),  # guest = actor slot (ok)
        _story('VerbStory', ('x', 'guest', 'y')),  # guest = verb slot (violation)
    ]
    with pytest.raises(PytestGivenError) as excinfo:
        resolve_glossary_kinds(glossary, stories)
    message = str(excinfo.value)
    assert 'VerbStory' in message
    assert 'ActorStory' not in message


def test_inferred_conflict_where_excludes_unrelated_slot_stories():
    """An inferred (kindless) term used in verb, actor, and noun slots conflicts
    on verb-vs-actor; the message names those stories but not the noun-only one."""
    glossary = Glossary(terms=[_term('run'), _term('x'), _term('y'), _term('z')])
    stories = [
        _story('VerbStory', ('x', 'run', 'y')),  # run = verb slot
        _story('ActorStory', ('run', 'x', 'y')),  # run = actor slot
        _story('NounStory', ('x', 'y', 'run')),  # run = noun slot only
    ]
    with pytest.raises(PytestGivenError) as excinfo:
        resolve_glossary_kinds(glossary, stories)
    message = str(excinfo.value)
    assert 'VerbStory' in message
    assert 'ActorStory' in message
    assert 'NounStory' not in message


def test_declared_verb_in_noun_slot_raises():
    """A term declared kind 'verb' that appears at position ≥2 (noun slot) raises."""
    glossary = Glossary(
        terms=[_term('subject'), _term('action'), _term('search', 'verb')]
    )
    with pytest.raises(PytestGivenError, match=r'(?i)noun slot'):
        resolve_glossary_kinds(glossary, [_story('S', ('subject', 'action', 'search'))])
