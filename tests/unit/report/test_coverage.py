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
    t'A {pg["Sentence"].low} is referenced by its {pg["Term"]("terms")}, '
    t'whatever their surface form',
)
def test_a_refs_collects_term_ids_whatever_the_display():
    with given(
        t'a {pg["Sentence"].low} written with an {pg["Instance"].low} and an '
        t'{pg["Inflection"].low}'
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
    with when(t'{pg["Coverage"].low} collects the {pg["Sentence"].low} references'):
        refs = a_refs(a)
    with then(t'they are the {pg["Term"].low} ids alone; words contribute nothing'):
        assert refs == {TermId('guest'), TermId('search'), TermId('room')}


@scenario(
    t'A multi-clause {pg["Sentence"].low} unions references across its '
    t'{pg["Clause"]("clauses")}',
)
def test_a_refs_unions_across_multi_clause_sentence():
    with given(t'a {pg["Sentence"].low} with two {pg["Clause"]("clauses")}'):
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
    with when(t'{pg["Coverage"].low} collects the {pg["Sentence"].low} references'):
        refs = a_refs(a)
    with then(t'the {pg["Term"]("terms")} of both clauses are present'):
        assert TermId('room') in refs
        assert TermId('booking') in refs


@scenario(
    t'A {pg["Sentence"].low} whose {pg["Clause"]("clauses")} start at '
    t'different {pg["Actor"]("actors")} builds and is covered',
)
def test_sentence_with_clauses_from_different_actors_is_covered():
    with given(
        t'a {pg["Sentence"].low} of two {pg["Clause"]("clauses")}: a guest signs the '
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
    with given(t'a {pg["Step"].low} naming both actors, the activity and the register'):
        scenario_ = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('clerk', 'Clerk'),
                _term_ref('sign', 'sign'),
                _term_ref('register', 'Register'),
            )
        )
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'the {pg["Sentence"].low} is covered'):
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
    t'A {pg["Step"].low} is referenced by its {pg["Term"]("terms")}, '
    t'whatever their surface form',
)
def test_s_for_step_collects_term_ids_whatever_the_display():
    with given(
        t'a {pg["Step"].low} naming an {pg["Instance"].low} and an '
        t'{pg["Inflection"].low}'
    ):
        step = _step(
            'when', _term_ref('guest', 'Alice'), _term_ref('search', 'searches for')
        )
    with when(t'{pg["Coverage"].low} collects the {pg["Step"].low} references'):
        refs = s_for_step(step)
    with then(t'they are the {pg["Term"].low} ids alone'):
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
    t'An {pg["Instance"].low} and its bare {pg["Term"].low} cover each other',
)
def test_compute_coverage_matches_instance_and_bare_term_both_ways():
    with given(t'a {pg["Sentence"].low} naming a bare {pg["Actor"].low}'):
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
        t'the same {pg["Sentence"].low} naming an {pg["Instance"].low} of that actor'
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
        t'a {pg["Step"].low} naming the {pg["Instance"].low}, and one naming the bare '
        t'actor'
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
    with when(t'{pg["Coverage"].low} is computed for each pairing'):
        bare_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(bare,))
        )
        instance_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(instance,))
        )
        bare_by_instance = compute_coverage(instance_step, bare_index)
        instance_by_bare = compute_coverage(bare_step, instance_index)
    with then(
        t'the {pg["Instance"].low} {pg["Step"].low} covers the bare '
        t'{pg["Sentence"].low}'
    ):
        assert SentenceId(1) in bare_by_instance
    with then(
        t'the bare {pg["Step"].low} covers the {pg["Instance"].low} '
        t'{pg["Sentence"].low}'
    ):
        assert SentenceId(1) in instance_by_bare


@scenario(
    t'Promoting a bare word to an {pg["Activity"].low} ref drops '
    t'{pg["Coverage"].low} from a {pg["Step"].low} that matched',
)
def test_compute_coverage_lost_when_sentence_gains_a_term():
    """Widening a sentence's identity set silently uncovers it: a step that
    covered the sentence before the edit no longer does."""
    with given(t'a {pg["Step"].low} naming two {pg["Term ref"]("term refs")}'):
        scenario = _scenario_with_steps(
            _step('when', _term_ref('guest', 'Guest'), _term_ref('room', 'Room'))
        )
    with given(
        t'the same {pg["Sentence"].low} with that middle slot a bare word, '
        t'then an {pg["Activity"].low} ref'
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
    with when(t'{pg["Coverage"].low} is computed against each {pg["Story"].low}'):
        before = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(bare,))),
        )
        after = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(promoted,))),
        )
    with then(t'the two-ref {pg["Sentence"].low} is covered'):
        assert SentenceId(1) in before
    with then(t'the widened {pg["Sentence"].low} is no longer covered'):
        assert SentenceId(1) not in after


@scenario(
    t'A {pg["Scenario"].low} {pg["Pin"].low} covers exactly its '
    t'{pg["Sentence"]("sentences")}',
)
def test_compute_coverage_scenario_pin_replaces_matching():
    with given(
        t'a {pg["Story"].low} with a matching and an under-anchored '
        t'{pg["Sentence"].low}'
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
        t'a {pg["Scenario"].low} whose {pg["Step"].low} matches sentence 1 but which '
        t'pins '
        t'sentence 2'
    ):
        scenario_ = _scenario_with_steps(_matching_step(), pins=[2])
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'only the pinned {pg["Sentence"].low} is covered, matching never ran'):
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
    t'A {pg["Step"].low} is narration-matched only where neither it nor its '
    t'{pg["Scenario"].low} {pg["Pin"]("pins")}',
)
@pytest.mark.parametrize(
    ('scenario_pins', 'step_pins', 'covered'),
    [
        (None, None, {1}),
        (None, [2], {2}),
        ([], None, set()),
        ([], [2], {2}),
        ([1], [2], {1, 2}),
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
    covered: set[int],
):
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(
            _scenario_with_steps(_matching_step(pins=step_pins), pins=scenario_pins),
            build_story_index(_search_and_book_story()),
        )
    with then(t'the {pg["Scenario"].low} covers what the {pg["Step"].low} contributes'):
        assert coverage == {SentenceId(sentence_id) for sentence_id in covered}


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


@scenario(
    t'A {pg["Sentence"].low} with two distinct {pg["Term"]("terms")} is '
    t'{pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_true_for_two_distinct_terms():
    with given(
        t'a {pg["Sentence"].low} anchored by two distinct {pg["Term"].low} refs'
    ):
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    ClauseWord(text='x'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with when(t'its {pg["Coverage"].low} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is eligible for {pg["Coverage"].low} tracking'):
        assert eligible is True


@scenario(
    t'An under-anchored {pg["Sentence"].low} is not {pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_false_for_one_distinct_term():
    with given(
        t'a {pg["Sentence"].low} that mentions only one distinct {pg["Term"].low}'
    ):
        # same term twice still counts as one distinct term id
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    ClauseWord(text='greets'),
                    _entity('guest', 'Alice'),
                ),
            ),
        )
    with when(t'its {pg["Coverage"].low} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is ineligible — {pg["Coverage"].low} needs at least two anchors'):
        assert eligible is False


def test_is_coverage_eligible_false_for_all_bare_sentence():
    a = Sentence(
        id=SentenceId(1),
        clauses=(_clause(ClauseWord(text='just'), ClauseWord(text='words')),),
    )
    assert is_coverage_eligible(a) is False


@scenario(
    t'An under-anchored {pg["Sentence"].low} is never covered by narration matching',
)
def test_compute_coverage_excludes_under_anchored_sentence():
    """A sentence with fewer than two distinct terms is excluded from
    narration matching (replaces the old 'empty refs matches every step'
    behavior). A pin still reaches it — the sibling scenario below."""
    with given(t'a {pg["Story"].low} whose {pg["Sentence"].low} is all bare words'):
        a = Sentence(
            id=SentenceId(1),
            clauses=(_clause(ClauseWord(text='just'), ClauseWord(text='words')),),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(a,))
    with given(t'a {pg["Scenario"].low} narrating one {pg["Term ref"].low}'):
        scenario = _scenario_with_steps(
            _step('given', _term_ref('guest', 'Guest')),
            _step('when'),
        )
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"].low} excludes the under-anchored {pg["Sentence"].low}'):
        assert SentenceId(1) not in coverage


@scenario(
    t'Nested {pg["Step"]("steps")} are walked for {pg["Coverage"].low}',
)
def test_compute_coverage_nested_steps_are_walked():
    """Steps nested as children are also examined for coverage."""
    with given(t'a {pg["Story"].low} with one canonical {pg["Sentence"].low}'):
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
    with given(
        t'the covering {pg["Term ref"]("term refs")} in a nested child {pg["Step"].low}'
    ):
        parent = _step('given')
        child = _step(
            'when',
            _term_ref('guest', 'Guest'),
            _term_ref('search', 'search'),
            _term_ref('room', 'Room'),
        )
        parent.children.append(child)
        scenario = _scenario_with_steps(parent)
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(
        t'the nested {pg["Step"].low} still counts and the {pg["Sentence"].low} is '
        t'covered'
    ):
        assert SentenceId(1) in coverage


@scenario(
    t'A {pg["Step"].low} {pg["Pin"].low} covers an eligible {pg["Sentence"].low}',
)
def test_compute_coverage_explicit_step_binding_covers_eligible_sentence():
    """A step pin covers an eligible (>=2 distinct
    term) sentence directly, without narration matching."""
    with given(t'a {pg["Story"].low} with a coverage-eligible {pg["Sentence"].low}'):
        sentence = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(sentence,))
    with given(t'a {pg["Step"].low} {pg["Pin"]("pinning")} it by number'):
        scenario = _scenario_with_steps(_step('when', pins=[1]))
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"].low} counts it directly, without narration matching'):
        assert SentenceId(1) in coverage


@scenario(
    t'A {pg["Pin"].low} covers an under-anchored {pg["Sentence"].low}',
)
def test_compute_coverage_explicit_binding_covers_under_anchored_sentence():
    """Eligibility gates narration matching only. A pin says what
    the narration cannot, so it covers an under-anchored sentence too."""
    with given(t'a {pg["Story"].low} whose {pg["Sentence"].low} is under-anchored'):
        sentence = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    ClauseWord(text='browses'),
                    ClauseWord(text='listings'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(sentence,))
    with given(t'a {pg["Step"].low} {pg["Pin"]("pinning")} it by number'):
        scenario = _scenario_with_steps(_step('when', pins=[1]))
    with when(t'{pg["Coverage"].low} is computed against the {pg["Story"].low}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"].low} counts it, despite the missing anchors'):
        assert SentenceId(1) in coverage
