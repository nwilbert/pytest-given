from pytest_given import given, scenario, then, when
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
from tests._vocab import pg, then_raises, when_raises


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
    return glossary.get(TermId(term_id)).kind


@scenario(
    'Term kinds are inferred from activity-slot positions',
    tags=['kind-inference', 'happy-path'],
)
def test_infers_actor_verb_object_by_position():
    with given(t'a glossary of three {pg["Kindless"]} {pg["Term"]} entries'):
        glossary = Glossary(terms=[_term('guest'), _term('search'), _term('room')])
    with when(t'kind resolution runs over a {pg["Story"]}'):
        resolved = resolve_glossary_kinds(
            glossary, [_story('S', ('guest', 'search', 'room'))]
        )
    with then(
        t'they resolve to {pg["Actor"]}, {pg["Verb"]}, {pg["Work Object"]} by slot'
    ):
        assert _kind(resolved, 'guest') == 'actor'
        assert _kind(resolved, 'search') == 'verb'
        assert _kind(resolved, 'room') == 'object'


@scenario(
    'An actor slot anywhere wins over a noun slot elsewhere',
    tags=['kind-inference', 'inference'],
)
def test_actor_anywhere_beats_object():
    with given(t'a {pg["Term"]} that sits in a noun slot in one {pg["Story"]}'):
        # 'guest' appears at noun slot in story 1, actor slot in story 2
        glossary = Glossary(
            terms=[_term('host'), _term('greet'), _term('guest'), _term('wave')]
        )
    with when(t'the same {pg["Term"]} also appears in an {pg["Actor"]} slot'):
        stories = [
            _story('S1', ('host', 'greet', 'guest')),
            _story('S2', ('guest', 'wave', 'host')),
        ]
        resolved = resolve_glossary_kinds(glossary, stories)
    with then(t'its inferred kind is {pg["Actor"]}'):
        assert _kind(resolved, 'guest') == 'actor'


@scenario(
    'A term used in no story stays kindless',
    tags=['kind-inference', 'inference'],
)
def test_never_used_stays_kindless():
    with given(t'a {pg["Term"]} referenced by no {pg["Story"]}'):
        glossary = Glossary(terms=[_term('orphan')])
    with when('kind resolution runs with no stories'):
        resolved = resolve_glossary_kinds(glossary, [])
    with then(t'the {pg["Term"]} remains {pg["Kindless"]}'):
        assert _kind(resolved, 'orphan') is None


@scenario(
    'A term in both a verb and a noun slot is a conflict',
    tags=['kind-inference', 'validation'],
)
def test_verb_and_noun_conflict_raises():
    with given(t'a {pg["Kindless"]} {pg["Term"]} used in a verb slot and a noun slot'):
        glossary = Glossary(terms=[_term('a'), _term('book'), _term('c'), _term('d')])
        stories = [
            _story('S1', ('a', 'book', 'c')),  # book = verb slot
            _story('S2', ('a', 'd', 'book')),  # book = noun slot
        ]
    with then_raises(
        'kind resolution raises a conflict naming the term',
        PytestGivenError,
        match=r'(?i)book',
    ):
        resolve_glossary_kinds(glossary, stories)


@scenario(
    'A declared kind consistent with its slot is kept',
    tags=['kind-inference', 'happy-path'],
)
def test_declared_kind_verified_and_kept():
    with given(t'a glossary with explicitly declared {pg["Term"]} kinds'):
        glossary = Glossary(
            terms=[
                _term('guest', 'actor'),
                _term('search', 'verb'),
                _term('room', 'object'),
            ]
        )
    with when(t'kind resolution runs over a matching {pg["Story"]}'):
        resolved = resolve_glossary_kinds(
            glossary, [_story('S', ('guest', 'search', 'room'))]
        )
    with then('the declared kinds are verified and preserved'):
        assert _kind(resolved, 'guest') == 'actor'


@scenario(
    'A declared verb in an actor slot is rejected',
    tags=['kind-inference', 'validation'],
)
def test_declared_verb_in_actor_slot_raises():
    with given(t'a {pg["Term"]} declared as a {pg["Verb"]}'):
        glossary = Glossary(terms=[_term('search', 'verb'), _term('x'), _term('y')])
    with then_raises(
        t'placing it in the {pg["Actor"]} slot raises',
        PytestGivenError,
        match=r'(?i)search',
    ):
        resolve_glossary_kinds(glossary, [_story('S', ('search', 'x', 'y'))])


@scenario(
    'A term used as both verb and actor is a conflict',
    tags=['kind-inference', 'validation'],
)
def test_verb_and_actor_conflict_raises():
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
    with then_raises(
        'kind resolution raises a conflict naming the term',
        PytestGivenError,
        match=r'(?i)examine',
    ):
        resolve_glossary_kinds(glossary, stories)


@scenario(
    'A declared work object in an actor slot is rejected',
    tags=['kind-inference', 'validation'],
)
def test_declared_object_in_actor_slot_raises():
    with given(t'a {pg["Term"]} declared as a {pg["Work Object"]}'):
        glossary = Glossary(terms=[_term('room', 'object'), _term('x'), _term('y')])
    with then_raises(
        t'placing it in the {pg["Actor"]} slot raises',
        PytestGivenError,
        match=r'(?i)room',
    ):
        resolve_glossary_kinds(glossary, [_story('S', ('room', 'x', 'y'))])


@scenario(
    'A declared actor in a verb slot is rejected',
    tags=['kind-inference', 'validation'],
)
def test_declared_actor_in_verb_slot_raises():
    with given(t'a {pg["Term"]} declared as an {pg["Actor"]}'):
        glossary = Glossary(
            terms=[_term('subject'), _term('guest', 'actor'), _term('y')]
        )
    with then_raises(
        'placing it at position 1 (verb slot) raises',
        PytestGivenError,
        match=r'(?i)verb slot',
    ):
        resolve_glossary_kinds(glossary, [_story('S', ('subject', 'guest', 'y'))])


@scenario(
    'A conflict error names only the offending stories',
    tags=['kind-inference', 'validation'],
)
def test_conflict_where_names_only_offending_stories():
    with given(t'an {pg["Actor"]} {pg["Term"]} that also appears in a verb slot'):
        glossary = Glossary(terms=[_term('guest', 'actor'), _term('x'), _term('y')])
        stories = [
            _story('ActorStory', ('guest', 'x', 'y')),  # actor slot (ok)
            _story('VerbStory', ('x', 'guest', 'y')),  # verb slot (violation)
        ]
    with when_raises('kind resolution raises', PytestGivenError) as excinfo:
        resolve_glossary_kinds(glossary, stories)
    with then('only the offending story is named in the message'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' not in message


@scenario(
    'A conflict message excludes stories with an unrelated slot',
    tags=['kind-inference', 'validation'],
)
def test_inferred_conflict_where_excludes_unrelated_slot_stories():
    with given(t'a {pg["Kindless"]} {pg["Term"]} used in verb, actor and noun slots'):
        glossary = Glossary(terms=[_term('run'), _term('x'), _term('y'), _term('z')])
        stories = [
            _story('VerbStory', ('x', 'run', 'y')),  # verb slot
            _story('ActorStory', ('run', 'x', 'y')),  # actor slot
            _story('NounStory', ('x', 'y', 'run')),  # noun slot only
        ]
    with when_raises(
        'the verb-vs-actor conflict is raised', PytestGivenError
    ) as excinfo:
        resolve_glossary_kinds(glossary, stories)
    with then('only the verb and actor stories are named, not the noun one'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' in message
        assert 'NounStory' not in message


@scenario(
    'A declared verb in a noun slot is rejected',
    tags=['kind-inference', 'validation'],
)
def test_declared_verb_in_noun_slot_raises():
    with given(t'a {pg["Term"]} declared as a {pg["Verb"]}'):
        glossary = Glossary(
            terms=[_term('subject'), _term('action'), _term('search', 'verb')]
        )
    with then_raises(
        'placing it at position ≥2 (noun slot) raises',
        PytestGivenError,
        match=r'(?i)noun slot',
    ):
        resolve_glossary_kinds(glossary, [_story('S', ('subject', 'action', 'search'))])


@scenario(
    'Slot positions alternate verb/noun after the actor',
    tags=['kind-inference', 'inference'],
)
def test_slot_for_maps_odd_positions_to_verb():
    from pytest_given.capture.kind_resolution import _slot_for

    with given('the slot-inference rule for an activity path'):
        pass
    with then('position 0 is actor, then verb and noun alternate'):
        assert _slot_for(0) == 'actor'
        assert _slot_for(1) == 'verb'
        assert _slot_for(2) == 'noun'
        assert _slot_for(3) == 'verb'
        assert _slot_for(4) == 'noun'
