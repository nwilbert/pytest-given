from typing import Annotated

import pytest

from pytest_given import (
    Glossary,
    Template,
    clause,
    given,
    scenario,
    sentence,
    then,
    when,
)
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    ClauseWord,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    Pin,
    Scenario,
    Sentence,
    SentenceId,
    Step,
    Story,
    StoryId,
    TermId,
)
from pytest_given.report.coverage import (
    a_refs,
    build_story_index,
    compute_coverage,
    is_coverage_eligible,
    s_for_step,
)
from tests.ubiquitous_language import pg


def _entity(tid, display):
    return ClauseTermRef(term_id=TermId(tid), display=display)


def _term_part(tid):
    return ClauseTermRef(term_id=TermId(tid), display=tid)


def _clause(*parts):
    return Clause(parts=parts)


@scenario(
    t'A {pg["Sentence"].l} is referenced by its {pg["Term"].l.s}, '
    t'whatever their surface form',
)
def test_a_refs_collects_term_ids_whatever_the_display():
    with given(
        t'a {pg["Sentence"].l} written with an {pg["Instance"].l} and an '
        t'{pg["Inflection"].l}'
    ):
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Alice'),
                    _entity('search', 'searches for'),
                    ClauseWord(text='a'),
                    _entity('room', 'Deluxe Suite'),
                ),
            ),
        )
    with when(t'{pg["Coverage"].l} collects the {pg["Sentence"].l} references'):
        refs = a_refs(a)
    with then(t'they are the {pg["Term"].l} ids alone; words contribute nothing'):
        assert refs == {TermId('guest'), TermId('search'), TermId('room')}


@scenario(
    t'A multi-clause {pg["Sentence"].l} unions references across its '
    t'{pg["Clause"].l.s}',
)
def test_a_refs_unions_across_multi_clause_sentence():
    with given(t'a {pg["Sentence"].l} with two {pg["Clause"].l.s}'):
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('booking', 'Booking'),
                ),
            ),
        )
    with when(t'{pg["Coverage"].l} collects the {pg["Sentence"].l} references'):
        refs = a_refs(a)
    with then(t'the {pg["Term"].l.s} of both clauses are present'):
        assert TermId('room') in refs
        assert TermId('booking') in refs


@scenario(
    t'A {pg["Sentence"].l} whose {pg["Clause"].l.s} start at '
    t'different {pg["Actor"].l.s} builds and is covered',
)
def test_sentence_with_clauses_from_different_actors_is_covered():
    with given(
        t'a {pg["Sentence"].l} of two {pg["Clause"].l.s}: a guest signs the '
        t'register, and a clerk signs the register'
    ):
        g = Glossary()
        guest, clerk = g.actor('Guest'), g.actor('Clerk')
        sign, register = g.activity('sign'), g.work_object('Register')
        unnumbered = sentence(
            clause(guest, sign('signs'), register),
            clause(clerk, sign('signs'), register),
        )
        built = Sentence(id=SentenceId(1), clauses=unnumbered.clauses)
        story = Story(id=StoryId('s'), title='S', sentences=(built,))
    with given(t'a {pg["Step"].l} naming both actors, the activity and the register'):
        scenario_ = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('clerk', 'Clerk'),
                _term_ref('sign', 'sign'),
                _term_ref('register', 'Register'),
            )
        )
    with when(t'{pg["Coverage"].l} is computed against the {pg["Story"].l}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'the {pg["Sentence"].l} is covered'):
        assert coverage == {built.id}


def _step(phase, *term_refs, pins=None, pins_story='s'):
    return Step(
        phase=phase,
        narration=Narration(text='x', parts=(NarrationLiteral(value='x'), *term_refs)),
        pins=_pins(pins, pins_story),
    )


def _pins(sentence_ids, story_id):
    """Pins into `story_id`; None stays None, which is "not pinned"."""
    if sentence_ids is None:
        return None
    return tuple(
        Pin(story_id=StoryId(story_id), sentence_id=SentenceId(sentence_id))
        for sentence_id in sentence_ids
    )


def _term_ref(tid, display):
    return NarrationTermRef(term_id=TermId(tid), display=display)


@scenario(
    t'A {pg["Step"].l} is referenced by its {pg["Term"].l.s}, '
    t'whatever their surface form',
)
def test_s_for_step_collects_term_ids_whatever_the_display():
    with given(
        t'a {pg["Step"].l} naming an {pg["Instance"].l} and an {pg["Inflection"].l}'
    ):
        step = _step(
            'when', _term_ref('guest', 'Alice'), _term_ref('search', 'searches for')
        )
    with when(t'{pg["Coverage"].l} collects the {pg["Step"].l} references'):
        refs = s_for_step(step)
    with then(t'they are the {pg["Term"].l} ids alone'):
        assert refs == {TermId('guest'), TermId('search')}


def _scenario_with_steps(*steps, pins=None, pins_story='s', stories=('s',)):
    return Scenario(
        id=NodeId('test'),
        narration=Narration(text='scn'),
        module='m',
        steps=list(steps),
        story_ids=tuple(StoryId(story_id) for story_id in stories),
        pins=_pins(pins, pins_story),
    )


@scenario(
    t'An {pg["Instance"].l} and its bare {pg["Term"].l} cover each other',
)
def test_compute_coverage_matches_instance_and_bare_term_both_ways():
    with given(t'a {pg["Sentence"].l} naming a bare {pg["Actor"].l}'):
        bare = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with given(
        t'the same {pg["Sentence"].l} naming an {pg["Instance"].l} of that actor'
    ):
        instance = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Alice'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with given(
        t'a {pg["Step"].l} naming the {pg["Instance"].l}, and one naming the bare actor'
    ):
        instance_step = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Alice'),
                _term_ref('search', 'searches for'),
                _term_ref('room', 'Room'),
            ),
        )
        bare_step = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('search', 'searches for'),
                _term_ref('room', 'Room'),
            ),
        )
    with when(t'{pg["Coverage"].l} is computed for each pairing'):
        bare_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(bare,))
        )
        instance_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(instance,))
        )
        bare_by_instance = compute_coverage(instance_step, bare_index)
        instance_by_bare = compute_coverage(bare_step, instance_index)
    with then(
        t'the {pg["Instance"].l} {pg["Step"].l} covers the bare {pg["Sentence"].l}'
    ):
        assert SentenceId(1) in bare_by_instance
    with then(
        t'the bare {pg["Step"].l} covers the {pg["Instance"].l} {pg["Sentence"].l}'
    ):
        assert SentenceId(1) in instance_by_bare


@scenario(
    t'Promoting a bare word to an {pg["Activity"].l} ref drops '
    t'{pg["Coverage"].l} from a {pg["Step"].l} that matched',
)
def test_compute_coverage_lost_when_sentence_gains_a_term():
    """Widening a sentence's identity set silently uncovers it: a step that
    covered the sentence before the edit no longer does."""
    with given(t'a {pg["Step"].l} naming two {pg["Term ref"].l.s}'):
        scenario = _scenario_with_steps(
            _step('when', _term_ref('guest', 'Guest'), _term_ref('room', 'Room'))
        )
    with given(
        t'the same {pg["Sentence"].l} with that middle slot a bare word, '
        t'then an {pg["Activity"].l} ref'
    ):
        bare = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    ClauseWord(text='books'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        promoted = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with when(t'{pg["Coverage"].l} is computed against each {pg["Story"].l}'):
        before = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(bare,))),
        )
        after = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(promoted,))),
        )
    with then(t'the two-ref {pg["Sentence"].l} is covered'):
        assert SentenceId(1) in before
    with then(t'the widened {pg["Sentence"].l} is no longer covered'):
        assert SentenceId(1) not in after


@scenario(
    t'A {pg["Scenario"].l} {pg["Pin"].l} covers exactly its {pg["Sentence"].l.s}',
)
def test_compute_coverage_scenario_pin_replaces_matching():
    with given(
        t'a {pg["Story"].l} with a matching and an under-anchored {pg["Sentence"].l}'
    ):
        matching = _guest_search_room_story().sentences[0]
        under_anchored = Sentence(
            id=SentenceId(2),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    ClauseWord(text='browses'),
                    ClauseWord(text='listings'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(matching, under_anchored))
    with given(
        t'a {pg["Scenario"].l} whose {pg["Step"].l} matches sentence 1 but which '
        t'pins '
        t'sentence 2'
    ):
        scenario_ = _scenario_with_steps(_matching_step(), pins=[2])
    with when(t'{pg["Coverage"].l} is computed against the {pg["Story"].l}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'only the pinned {pg["Sentence"].l} is covered, matching never ran'):
        assert coverage == {SentenceId(2)}


def _guest_search_room_story():
    only = Sentence(
        id=SentenceId(1),
        clauses=(
            _clause(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    return Story(id=StoryId('s'), title='S', sentences=(only,))


def _matching_step(**kwargs):
    return _step(
        'when',
        _term_ref('guest', 'Guest'),
        _term_ref('search', 'search'),
        _term_ref('room', 'Room'),
        **kwargs,
    )


def test_compute_coverage_drops_pins_naming_no_sentence_of_the_story():
    """A replayed report is deserialized unvalidated; a stale pin must not
    put a chip on a sentence that does not exist."""
    index = build_story_index(_guest_search_room_story())
    assert compute_coverage(_scenario_with_steps(pins=[1, 99]), index) == {
        SentenceId(1)
    }
    # The step's narration matches sentence 1, so an empty result shows the
    # stale pin still took the step out of matching rather than falling back.
    assert (
        compute_coverage(_scenario_with_steps(_matching_step(pins=[99])), index)
        == set()
    )


def _search_and_book_story():
    """Sentence 1 is what `_matching_step` narrates; sentence 2 only a pin reaches."""
    booked = Sentence(
        id=SentenceId(2),
        clauses=(
            _clause(
                _entity('guest', 'Guest'),
                ClauseWord(text='books'),
                _entity('booking', 'Booking'),
            ),
        ),
    )
    searched = _guest_search_room_story().sentences[0]
    return Story(id=StoryId('s'), title='S', sentences=(searched, booked))


@scenario(
    t'A {pg["Step"].l} is narration-matched only where neither it nor its '
    t'{pg["Scenario"].l} {pg["Pin"].l.s}',
)
@pytest.mark.parametrize(
    ('scenario_pins', 'step_pins', 'covered'),
    [
        (None, None, [1]),
        (None, [2], [2]),
        ([], None, []),
        ([], [2], [2]),
        ([1], [2], [1, 2]),
    ],
    ids=[
        'nothing-pinned',
        'step-pinned',
        'scenario-pinned',
        'both-pinned',
        'scenario-and-step-pinned',
    ],
)
def test_narration_matching_runs_only_where_nothing_pins(
    scenario_pins: Annotated[
        list[int] | None, given(Template('a scenario with pins={scenario_pins}'))
    ],
    step_pins: Annotated[
        list[int] | None,
        given(Template('a step matching sentence 1, with pins={step_pins}')),
    ],
    covered: list[int],
):
    with when(t'{pg["Coverage"].l} is computed against the {pg["Story"].l}'):
        coverage = compute_coverage(
            _scenario_with_steps(_matching_step(pins=step_pins), pins=scenario_pins),
            build_story_index(_search_and_book_story()),
        )
    with then(t'the {pg["Scenario"].l} covers the {pg["Sentence"].l.s} {covered}'):
        assert sorted(coverage) == covered


def test_compute_coverage_mixes_pinned_and_matched_steps_in_one_story():
    """A pinned step contributes exactly its pins, even where its narration
    fits another sentence; the scenario's other steps are still matched."""
    assert compute_coverage(
        _scenario_with_steps(_matching_step(pins=[2]), _matching_step()),
        build_story_index(_search_and_book_story()),
    ) == {SentenceId(1), SentenceId(2)}


def test_a_step_pinned_into_another_story_is_not_matched_in_this_one():
    step = _matching_step(pins=[1], pins_story='t')
    coverage = compute_coverage(
        _scenario_with_steps(step), build_story_index(_guest_search_room_story())
    )
    assert coverage == set()


def test_a_scenario_pinned_into_another_story_matches_no_step_in_this_one():
    scenario_ = _scenario_with_steps(_matching_step(), pins=[9], pins_story='t')
    assert (
        compute_coverage(scenario_, build_story_index(_guest_search_room_story()))
        == set()
    )


def test_a_scenario_naming_no_story_is_not_matched():
    scenario_ = _scenario_with_steps(_matching_step(), stories=())
    assert (
        compute_coverage(scenario_, build_story_index(_guest_search_room_story()))
        == set()
    )


def _sentence_naming(*term_ids):
    """Sentence 1 referencing these terms, padded with a bare word."""
    parts = (*(_term_part(term_id) for term_id in term_ids), ClauseWord(text='words'))
    return Sentence(id=SentenceId(1), clauses=(_clause(*parts),))


@scenario(
    t'A {pg["Sentence"].l} is {pg["Coverage"].l}-eligible only with two '
    t'distinct {pg["Term"].l.s}',
)
@pytest.mark.parametrize(
    ('term_ids', 'eligible'),
    [
        (['guest', 'room'], True),
        (['guest', 'guest'], False),
        (['guest'], False),
        ([], False),
    ],
)
def test_coverage_eligibility_needs_two_distinct_terms(term_ids, eligible):
    with given(t'a {pg["Sentence"].l} referencing the {pg["Term"].l.s} {term_ids}'):
        sentence = _sentence_naming(*term_ids)
    with when(t'its {pg["Coverage"].l} eligibility is checked'):
        checked = is_coverage_eligible(sentence)
    with then(t'it is eligible: {eligible}'):
        assert checked == eligible


@scenario(
    t'An under-anchored {pg["Sentence"].l} is covered only through a {pg["Pin"].l}',
)
@pytest.mark.parametrize(
    ('term_ids', 'pinned', 'covered'),
    [
        (['guest', 'room'], False, True),
        (['guest', 'room'], True, True),
        (['guest'], False, False),
        (['guest'], True, True),
    ],
)
def test_an_under_anchored_sentence_is_covered_only_through_a_pin(
    term_ids, pinned, covered
):
    """Eligibility gates narration matching only. A pin says what the
    narration cannot, so it covers an under-anchored sentence too."""
    with given(
        t'a {pg["Story"].l} whose {pg["Sentence"].l} references the '
        t'{pg["Term"].l.s} {term_ids}'
    ):
        story = Story(
            id=StoryId('s'), title='S', sentences=(_sentence_naming(*term_ids),)
        )
    with given(
        t'a {pg["Step"].l} narrating those {pg["Term"].l.s}, '
        t'{pg["Pin"]("pinning")} the {pg["Sentence"].l}: {pinned}'
    ):
        step = _step(
            'when',
            *(_term_ref(term_id, term_id) for term_id in term_ids),
            pins=[1] if pinned else None,
        )
    with when(t'{pg["Coverage"].l} is computed against the {pg["Story"].l}'):
        coverage = compute_coverage(
            _scenario_with_steps(step), build_story_index(story)
        )
    with then(t'the {pg["Sentence"].l} is covered: {covered}'):
        assert (SentenceId(1) in coverage) == covered


@scenario(
    t'Nested {pg["Step"].l.s} are walked for {pg["Coverage"].l}',
)
def test_compute_coverage_nested_steps_are_walked():
    """Steps nested as children are also examined for coverage."""
    with given(t'a {pg["Story"].l} with one canonical {pg["Sentence"].l}'):
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(a,))
    with given(t'the covering {pg["Term ref"].l.s} in a nested child {pg["Step"].l}'):
        parent = _step('given')
        child = _step(
            'when',
            _term_ref('guest', 'Guest'),
            _term_ref('search', 'search'),
            _term_ref('room', 'Room'),
        )
        parent.children.append(child)
        scenario = _scenario_with_steps(parent)
    with when(t'{pg["Coverage"].l} is computed against the {pg["Story"].l}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(
        t'the nested {pg["Step"].l} still counts and the {pg["Sentence"].l} is covered'
    ):
        assert SentenceId(1) in coverage
