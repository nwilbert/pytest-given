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


def _story_placing(term_id, slot, title):
    """A one-sentence story with `term_id` in `slot` and story-local fillers
    elsewhere, so no other term's inference interferes."""
    position = next(index for index in range(3) if slot_for(index) == slot)
    triple = [f'{title}-{index}' for index in range(3)]
    triple[position] = term_id
    return _story(title, triple)


def _infer_term(glossary, stories):
    """The term's inferred kind and the refusal message, one of them empty."""
    try:
        inferred = infer_glossary_kinds(glossary, stories)
    except PytestGivenError as error:
        return None, str(error)
    return _kind(inferred, 'term'), ''


@scenario(
    t'A {pg["Kindless"].l} {pg["Term"].l} takes its kind from the '
    t'{pg["Slot"].l.s} it fills',
    tags=['diagnostics', 'validation'],
)
@pytest.mark.parametrize(
    ('slots', 'conflict', 'kind'),
    [
        ([], False, None),
        (['actor'], False, 'actor'),
        (['verb'], False, 'activity'),
        (['noun'], False, 'object'),
        (['actor', 'noun'], False, 'actor'),
        (['verb', 'actor'], True, None),
        (['verb', 'noun'], True, None),
    ],
)
def test_a_kindless_term_takes_its_kind_from_its_slots(slots, conflict, kind):
    with given(
        t'a {pg["Kindless"].l} {pg["Term"].l} filling the {slots} '
        t'{pg["Slot"].l.s}, one {pg["Story"].l} each'
    ):
        glossary = Glossary(terms=[_term('term')])
        stories = [
            _story_placing('term', slot, f'S{index}')
            for index, slot in enumerate(slots)
        ]
    with when(t'{pg["Kind inference"].l} runs over the {pg["Story"].l.s}'):
        inferred_kind, refusal = _infer_term(glossary, stories)
    with then(t'a conflict naming the {pg["Term"].l} is reported: {conflict}'):
        assert ("term 'Term' is used in incompatible positions" in refusal) == conflict
    with then(t'the inferred kind is {kind}'):
        assert inferred_kind == kind


@scenario(
    t'A declared kind must fit the {pg["Slot"].l} its {pg["Term"].l} fills',
    tags=['diagnostics', 'validation'],
)
@pytest.mark.parametrize(
    ('declared', 'slot', 'outcome'),
    [
        ('actor', 'actor', 'kept'),
        ('activity', 'actor', 'refused'),
        ('object', 'actor', 'refused'),
        ('actor', 'verb', 'refused'),
        ('activity', 'verb', 'kept'),
        ('object', 'verb', 'refused'),
        ('actor', 'noun', 'kept'),
        ('activity', 'noun', 'refused'),
        ('object', 'noun', 'kept'),
    ],
)
def test_a_declared_kind_must_fit_its_slot(declared, slot, outcome):
    with given(t'a {pg["Term"].l} declared as {declared}'):
        glossary = Glossary(terms=[_term('term', declared)])
    with given(t'a {pg["Story"].l} putting it in the {slot} {pg["Slot"].l}'):
        story = _story_placing('term', slot, 'S')
    with when(t'{pg["Kind inference"].l} runs over the {pg["Story"].l}'):
        inferred_kind, refusal = _infer_term(glossary, [story])
    with then(t'the declared kind is {outcome}'):
        assert ('kept' if inferred_kind == declared else 'refused') == outcome
    with then('a refusal names the declared kind and the slot'):
        article = 'an' if slot == 'actor' else 'a'
        assert (
            f"declared kind '{declared}' but appears in {article} {slot} slot"
            in refusal
        ) == (outcome == 'refused')


@scenario(
    t'A {pg["Term"].l} named only in the second {pg["Clause"].l} of a '
    t'{pg["Sentence"].l} gets its kind inferred',
)
def test_infers_kinds_from_a_second_clause():
    with given(t'a glossary of {pg["Kindless"].l} {pg["Term"].l} entries'):
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
        t'a {pg["Sentence"].l} whose second {pg["Clause"].l} starts at another '
        t'{pg["Actor"].l}'
    ):
        sentence = Sentence(
            id=SentenceId(1),
            clauses=(
                clause_of('guest', 'sign', 'register'),
                clause_of('clerk', 'sign', 'register'),
            ),
        )
        story = Story(id=StoryId('S'), title='S', sentences=(sentence,))
    with when(t'{pg["Kind inference"].l} runs over its {pg["Story"].l}'):
        inferred = infer_glossary_kinds(glossary, [story])
    with then(t'the first {pg["Term"].l} of the second clause is an {pg["Actor"].l}'):
        assert _kind(inferred, 'clerk') == 'actor'


@scenario(
    t'A conflict error names only the offending {pg["Story"].l.s}',
    tags=['diagnostics', 'validation'],
)
def test_conflict_where_names_only_offending_stories():
    with given(t'an {pg["Actor"].l} {pg["Term"].l} that also appears in a verb slot'):
        glossary = Glossary(terms=[_term('guest', 'actor'), _term('x'), _term('y')])
        stories = [
            _story('ActorStory', ('guest', 'x', 'y')),  # actor slot (ok)
            _story('VerbStory', ('x', 'guest', 'y')),  # verb slot (violation)
        ]
    with (
        when_then(
            t'{pg["Kind inference"].l} runs over both {pg["Story"].l.s}',
            'a PytestGivenError reports the conflict',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        infer_glossary_kinds(glossary, stories)
    with then('only the offending story is named in the message'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' not in message


@scenario(
    t'A conflict message excludes {pg["Story"].l.s} with an unrelated {pg["Slot"].l}',
    tags=['diagnostics', 'validation'],
)
def test_inferred_conflict_where_excludes_unrelated_slot_stories():
    with given(
        t'a {pg["Kindless"].l} {pg["Term"].l} used in verb, actor and noun slots'
    ):
        glossary = Glossary(terms=[_term('run'), _term('x'), _term('y'), _term('z')])
        stories = [
            _story('VerbStory', ('x', 'run', 'y')),  # verb slot
            _story('ActorStory', ('run', 'x', 'y')),  # actor slot
            _story('NounStory', ('x', 'y', 'run')),  # noun slot only
        ]
    with (
        when_then(
            t'{pg["Kind inference"].l} runs over all three {pg["Story"].l.s}',
            'a PytestGivenError reports the verb-vs-actor conflict',
        ),
        pytest.raises(PytestGivenError) as excinfo,
    ):
        infer_glossary_kinds(glossary, stories)
    with then('only the verb and actor stories are named, not the noun one'):
        message = str(excinfo.value)
        assert 'VerbStory' in message
        assert 'ActorStory' in message
        assert 'NounStory' not in message


@scenario(
    t'{pg["Slot"]} positions alternate verb/noun after the {pg["Actor"].l}',
)
def test_slot_for_maps_odd_positions_to_verb():
    with given('the five positions of a short clause'):
        positions = range(5)
    with when(t'the {pg["Slot"].l} rule is applied to each position'):
        slots = [slot_for(i) for i in positions]
    with then(t'position 0 is the actor {pg["Slot"].l}, then verb and noun alternate'):
        assert slots == ['actor', 'verb', 'noun', 'verb', 'noun']
