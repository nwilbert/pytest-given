import pytest

from pytest_given import given, scenario, then, when, when_then
from pytest_given.capture.kind_inference import infer_glossary_kinds, slot_for
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    Glossary,
    GlossaryTerm,
    PytestGivenError,
    Sentence,
    SentenceId,
    Story,
    StoryId,
    TermId,
)
from tests.ubiquitous_language import pg


def _term(term_id, kind=None):
    return GlossaryTerm(id=TermId(term_id), kind=kind, canonical=term_id.title())


def _story(title, *triples):
    sentences = tuple(
        Sentence(
            id=SentenceId(index + 1),
            clauses=(
                Clause(
                    parts=tuple(
                        ClauseTermRef(term_id=TermId(tid), display=tid.title())
                        for tid in triple
                    )
                ),
            ),
        )
        for index, triple in enumerate(triples)
    )
    return Story(id=StoryId(title), title=title, sentences=sentences)


def _kind(glossary, term_id):
    return glossary.get(TermId(term_id)).kind


@scenario(
    t'{pg["Term"]} kinds are inferred from clause-slot positions',
)
def test_infers_actor_activity_object_by_position():
    with given(t'a glossary of three {pg["Kindless"]} {pg["Term"]} entries'):
        glossary = Glossary(terms=[_term('guest'), _term('search'), _term('room')])
    with when(t'{pg["Kind inference"]} runs over a {pg["Story"]}'):
        inferred = infer_glossary_kinds(
            glossary, [_story('S', ('guest', 'search', 'room'))]
        )
    with then(
        t'they are inferred as {pg["Actor"]}, {pg["Activity"]}, '
        t'{pg["Work Object"]} by slot'
    ):
        assert _kind(inferred, 'guest') == 'actor'
        assert _kind(inferred, 'search') == 'activity'
        assert _kind(inferred, 'room') == 'object'


@scenario(
    t'A {pg["Term"].low} named only in the second {pg["Clause"].low} of a '
    t'{pg["Sentence"].low} gets its kind inferred',
)
def test_infers_kinds_from_a_second_clause():
    with given(t'a glossary of {pg["Kindless"]} {pg["Term"]} entries'):
        glossary = Glossary(
            terms=[_term('guest'), _term('clerk'), _term('sign'), _term('register')]
        )

    def clause_of(*term_ids):
        return Clause(
            parts=tuple(
                ClauseTermRef(term_id=TermId(tid), display=tid.title())
                for tid in term_ids
            )
        )

    with given(
        t'a {pg["Sentence"]} whose second {pg["Clause"]} starts at another '
        t'{pg["Actor"].low}'
    ):
        sentence = Sentence(
            id=SentenceId(1),
            clauses=(
                clause_of('guest', 'sign', 'register'),
                clause_of('clerk', 'sign', 'register'),
            ),
        )
        story = Story(id=StoryId('S'), title='S', sentences=(sentence,))
    with when(t'{pg["Kind inference"]} runs over its {pg["Story"]}'):
        inferred = infer_glossary_kinds(glossary, [story])
    with then(t'the first {pg["Term"]} of the second clause is an {pg["Actor"]}'):
        assert _kind(inferred, 'clerk') == 'actor'


@scenario(
    t'An {pg["Actor"].low} {pg["Slot"].low} anywhere wins over a noun '
    t'{pg["Slot"].low} elsewhere',
)
def test_actor_anywhere_beats_object():
    with given(t'a {pg["Glossary"].low} of {pg["Kindless"]} {pg["Term"]} entries'):
        glossary = Glossary(
            terms=[_term('host'), _term('greet'), _term('guest'), _term('wave')]
        )
    with given(
        t'one {pg["Story"]} putting a {pg["Term"]} in a noun slot and another '
        t'putting it in an {pg["Actor"]} slot'
    ):
        stories = [
            _story('S1', ('host', 'greet', 'guest')),
            _story('S2', ('guest', 'wave', 'host')),
        ]
    with when(t'{pg["Kind inference"]} runs over both {pg["Story"]("stories")}'):
        inferred = infer_glossary_kinds(glossary, stories)
    with then(t'its inferred kind is {pg["Actor"]}'):
        assert _kind(inferred, 'guest') == 'actor'


@scenario(
    t'A {pg["Term"].low} used in no {pg["Story"].low} stays {pg["Kindless"].low}',
)
def test_never_used_stays_kindless():
    with given(t'a {pg["Term"]} referenced by no {pg["Story"]}'):
        glossary = Glossary(terms=[_term('orphan')])
    with when(t'{pg["Kind inference"]} runs with no stories'):
        inferred = infer_glossary_kinds(glossary, [])
    with then(t'the {pg["Term"]} remains {pg["Kindless"]}'):
        assert _kind(inferred, 'orphan') is None


@scenario(
    t'A {pg["Term"].low} in both a verb and a noun {pg["Slot"].low} is a conflict',
    tags=['diagnostics', 'validation'],
)
def test_activity_and_noun_conflict_raises():
    with given(t'a {pg["Kindless"]} {pg["Term"]} used in a verb slot and a noun slot'):
        glossary = Glossary(terms=[_term('a'), _term('book'), _term('c'), _term('d')])
        stories = [
            _story('S1', ('a', 'book', 'c')),  # book = verb slot
            _story('S2', ('a', 'd', 'book')),  # book = noun slot
        ]
    with (
        when_then(
            'kind resolution runs over both stories',
            'a PytestGivenError names the conflicting term',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)book'),
    ):
        infer_glossary_kinds(glossary, stories)


@scenario(
    t'A declared kind consistent with its {pg["Slot"].low} is kept',
)
def test_declared_kind_verified_and_kept():
    with given(t'a glossary with explicitly declared {pg["Term"]} kinds'):
        glossary = Glossary(
            terms=[
                _term('guest', 'actor'),
                _term('search', 'activity'),
                _term('room', 'object'),
            ]
        )
    with when(t'{pg["Kind inference"]} runs over a matching {pg["Story"]}'):
        inferred = infer_glossary_kinds(
            glossary, [_story('S', ('guest', 'search', 'room'))]
        )
    with then('the declared kinds are verified and preserved'):
        assert _kind(inferred, 'guest') == 'actor'
        assert _kind(inferred, 'search') == 'activity'
        assert _kind(inferred, 'room') == 'object'


@scenario(
    t'A declared {pg["Activity"].low} in an {pg["Actor"].low} {pg["Slot"].low} '
    t'is rejected',
    tags=['diagnostics', 'validation'],
)
def test_declared_activity_in_actor_slot_raises():
    with given(t'a {pg["Term"]} declared as an {pg["Activity"]}'):
        glossary = Glossary(terms=[_term('search', 'activity'), _term('x'), _term('y')])
    with (
        when_then(
            t'kind resolution places it in the {pg["Actor"]} slot',
            'a PytestGivenError names the misplaced term',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)search'),
    ):
        infer_glossary_kinds(glossary, [_story('S', ('search', 'x', 'y'))])


@scenario(
    t'A {pg["Term"].low} used as both {pg["Activity"].low} and '
    t'{pg["Actor"].low} is a conflict',
    tags=['diagnostics', 'validation'],
)
def test_activity_and_actor_conflict_raises():
    with given(
        t'a {pg["Kindless"]} {pg["Term"]} used in a verb slot and an actor slot'
    ):
        glossary = Glossary(
            terms=[_term('a'), _term('examine'), _term('b'), _term('c')]
        )
        stories = [
            _story('S1', ('a', 'examine', 'b')),  # examine = verb slot
            _story('S2', ('examine', 'c', 'a')),  # examine = actor slot
        ]
    with (
        when_then(
            'kind resolution runs over both stories',
            'a PytestGivenError names the conflicting term',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)examine'),
    ):
        infer_glossary_kinds(glossary, stories)


@scenario(
    t'A declared {pg["Work Object"].low} in an {pg["Actor"].low} '
    t'{pg["Slot"].low} is rejected',
    tags=['diagnostics', 'validation'],
)
def test_declared_object_in_actor_slot_raises():
    with given(t'a {pg["Term"]} declared as a {pg["Work Object"]}'):
        glossary = Glossary(terms=[_term('room', 'object'), _term('x'), _term('y')])
    with (
        when_then(
            t'kind resolution places it in the {pg["Actor"]} slot',
            'a PytestGivenError names the misplaced term',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)room'),
    ):
        infer_glossary_kinds(glossary, [_story('S', ('room', 'x', 'y'))])


@scenario(
    t'A declared {pg["Actor"].low} in a verb {pg["Slot"].low} is rejected',
    tags=['validation'],
)
def test_declared_actor_in_verb_slot_raises():
    with given(t'a {pg["Term"]} declared as an {pg["Actor"]}'):
        glossary = Glossary(
            terms=[_term('subject'), _term('guest', 'actor'), _term('y')]
        )
    with (
        when_then(
            'kind resolution places it at position 1 (the verb slot)',
            'a PytestGivenError says an actor cannot fill the verb slot',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)verb slot'),
    ):
        infer_glossary_kinds(glossary, [_story('S', ('subject', 'guest', 'y'))])


@scenario(
    t'A conflict error names only the offending {pg["Story"]("stories")}',
    tags=['diagnostics', 'validation'],
)
def test_conflict_where_names_only_offending_stories():
    with given(t'an {pg["Actor"]} {pg["Term"]} that also appears in a verb slot'):
        glossary = Glossary(terms=[_term('guest', 'actor'), _term('x'), _term('y')])
        stories = [
            _story('ActorStory', ('guest', 'x', 'y')),  # actor slot (ok)
            _story('VerbStory', ('x', 'guest', 'y')),  # verb slot (violation)
        ]
    with when('kind resolution raises'):
        with pytest.raises(PytestGivenError) as excinfo:
            infer_glossary_kinds(glossary, stories)
    with then('only the offending story is named in the message'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' not in message


@scenario(
    t'A conflict message excludes {pg["Story"]("stories")} with an unrelated '
    t'{pg["Slot"].low}',
    tags=['diagnostics', 'validation'],
)
def test_inferred_conflict_where_excludes_unrelated_slot_stories():
    with given(t'a {pg["Kindless"]} {pg["Term"]} used in verb, actor and noun slots'):
        glossary = Glossary(terms=[_term('run'), _term('x'), _term('y'), _term('z')])
        stories = [
            _story('VerbStory', ('x', 'run', 'y')),  # verb slot
            _story('ActorStory', ('run', 'x', 'y')),  # actor slot
            _story('NounStory', ('x', 'y', 'run')),  # noun slot only
        ]
    with when('the verb-vs-actor conflict is raised'):
        with pytest.raises(PytestGivenError) as excinfo:
            infer_glossary_kinds(glossary, stories)
    with then('only the verb and actor stories are named, not the noun one'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' in message
        assert 'NounStory' not in message


@scenario(
    t'A declared {pg["Activity"].low} in a noun {pg["Slot"].low} is rejected',
    tags=['validation'],
)
def test_declared_activity_in_noun_slot_raises():
    with given(t'a {pg["Term"]} declared as an {pg["Activity"]}'):
        glossary = Glossary(
            terms=[_term('subject'), _term('action'), _term('search', 'activity')]
        )
    with (
        when_then(
            'kind resolution places it at position ≥2 (a noun slot)',
            'a PytestGivenError says a verb cannot fill the noun slot',
        ),
        pytest.raises(PytestGivenError, match=r'(?i)noun slot'),
    ):
        infer_glossary_kinds(glossary, [_story('S', ('subject', 'action', 'search'))])


@scenario(
    t'{pg["Slot"]} positions alternate verb/noun after the {pg["Actor"].low}',
)
def test_slot_for_maps_odd_positions_to_verb():
    with given('the five positions of a short clause'):
        positions = range(5)
    with when(t'the {pg["Slot"]} rule is applied to each position'):
        slots = [slot_for(i) for i in positions]
    with then(t'position 0 is the actor {pg["Slot"]}, then verb and noun alternate'):
        assert slots == ['actor', 'verb', 'noun', 'verb', 'noun']
