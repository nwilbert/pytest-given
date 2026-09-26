from pytest_given import Glossary, clause, given, scenario, sentence, then, when
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
        t'a {pg["Sentence"]} written with an {pg["Instance"]} and an {pg["Inflection"]}'
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
    with when(t'{pg["Coverage"]} collects the {pg["Sentence"]} references'):
        refs = a_refs(a)
    with then(t'they are the {pg["Term"]} ids alone; words contribute nothing'):
        assert refs == {TermId('guest'), TermId('search'), TermId('room')}


@scenario(
    t'A multi-clause {pg["Sentence"].low} unions references across its '
    t'{pg["Clause"]("clauses")}',
)
def test_a_refs_unions_across_multi_clause_sentence():
    with given(t'a {pg["Sentence"]} with two {pg["Clause"]("clauses")}'):
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
    with when(t'{pg["Coverage"]} collects the {pg["Sentence"]} references'):
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
        t'a {pg["Sentence"]} of two {pg["Clause"]("clauses")}: a guest signs the '
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
    with given(t'a {pg["Step"]} naming both actors, the activity and the register'):
        scenario_ = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('clerk', 'Clerk'),
                _term_ref('sign', 'sign'),
                _term_ref('register', 'Register'),
            )
        )
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'the {pg["Sentence"]} is covered'):
        assert coverage == {built.id}


def _step(phase, *term_refs, pins=()):
    return Step(
        phase=phase,
        narration=Narration(text='x', parts=(NarrationLiteral(value='x'), *term_refs)),
        pins=tuple(Pin(story_id=StoryId('s'), sentence_id=SentenceId(i)) for i in pins),
    )


def _term_ref(tid, display):
    return NarrationTermRef(term_id=TermId(tid), display=display)


@scenario(
    t'A {pg["Step"].low} is referenced by its {pg["Term"]("terms")}, '
    t'whatever their surface form',
)
def test_s_for_step_collects_term_ids_whatever_the_display():
    with given(t'a {pg["Step"]} naming an {pg["Instance"]} and an {pg["Inflection"]}'):
        step = _step(
            'when', _term_ref('guest', 'Alice'), _term_ref('search', 'searches for')
        )
    with when(t'{pg["Coverage"]} collects the {pg["Step"]} references'):
        refs = s_for_step(step)
    with then(t'they are the {pg["Term"]} ids alone'):
        assert refs == {TermId('guest'), TermId('search')}


def _scenario_with_steps(*steps, pins=()):
    return Scenario(
        id=NodeId('test'),
        narration=Narration(text='scn'),
        module='m',
        steps=list(steps),
        story_ids=(StoryId('s'),),
        pins=tuple(Pin(story_id=StoryId('s'), sentence_id=SentenceId(i)) for i in pins),
    )


@scenario(
    t'An {pg["Instance"].low} and its bare {pg["Term"].low} cover each other',
)
def test_compute_coverage_matches_instance_and_bare_term_both_ways():
    with given(t'a {pg["Sentence"]} naming a bare {pg["Actor"]}'):
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
    with given(t'the same {pg["Sentence"]} naming an {pg["Instance"]} of that actor'):
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
        t'a {pg["Step"]} naming the {pg["Instance"]}, and one naming the bare actor'
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
    with when(t'{pg["Coverage"]} is computed for each pairing'):
        bare_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(bare,))
        )
        instance_index = build_story_index(
            Story(id=StoryId('s'), title='S', sentences=(instance,))
        )
        bare_by_instance = compute_coverage(instance_step, bare_index)
        instance_by_bare = compute_coverage(bare_step, instance_index)
    with then(t'the {pg["Instance"]} {pg["Step"]} covers the bare {pg["Sentence"]}'):
        assert SentenceId(1) in bare_by_instance
    with then(t'the bare {pg["Step"]} covers the {pg["Instance"]} {pg["Sentence"]}'):
        assert SentenceId(1) in instance_by_bare


@scenario(
    t'Promoting a bare word to an {pg["Activity"].low} ref drops '
    t'{pg["Coverage"].low} from a {pg["Step"].low} that matched',
)
def test_compute_coverage_lost_when_sentence_gains_a_term():
    """Widening a sentence's identity set silently uncovers it: a step that
    covered the sentence before the edit no longer does."""
    with given(t'a {pg["Step"]} naming two {pg["Term ref"]("term refs")}'):
        scenario = _scenario_with_steps(
            _step('when', _term_ref('guest', 'Guest'), _term_ref('room', 'Room'))
        )
    with given(
        t'the same {pg["Sentence"]} with that middle slot a bare word, '
        t'then an {pg["Activity"]} ref'
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
    with when(t'{pg["Coverage"]} is computed against each {pg["Story"]}'):
        before = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(bare,))),
        )
        after = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', sentences=(promoted,))),
        )
    with then(t'the two-ref {pg["Sentence"]} is covered'):
        assert SentenceId(1) in before
    with then(t'the widened {pg["Sentence"]} is no longer covered'):
        assert SentenceId(1) not in after


@scenario(
    t'A {pg["Scenario"].low} {pg["Pin"].low} covers exactly its '
    t'{pg["Sentence"]("sentences")}',
)
def test_compute_coverage_scenario_pin_replaces_matching():
    with given(
        t'a {pg["Story"]} with a matching and an under-anchored {pg["Sentence"]}'
    ):
        matching = Sentence(
            id=SentenceId(1),
            clauses=(
                _clause(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
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
        t'a {pg["Scenario"]} whose {pg["Step"]} matches sentence 1 but which pins '
        t'sentence 2'
    ):
        scenario_ = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('search', 'search'),
                _term_ref('room', 'Room'),
            ),
            pins=[2],
        )
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario_, build_story_index(story))
    with then(t'only the pinned {pg["Sentence"]} is covered, matching never ran'):
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
    assert (
        compute_coverage(_scenario_with_steps(_step('when', pins=[99])), index) == set()
    )


def test_compute_coverage_matches_a_step_pinned_into_another_story():
    step = _matching_step()
    step.pins = (Pin(story_id=StoryId('t'), sentence_id=SentenceId(1)),)
    coverage = compute_coverage(
        _scenario_with_steps(step), build_story_index(_guest_search_room_story())
    )
    assert coverage == {SentenceId(1)}


def test_compute_coverage_ignores_a_scenario_pin_into_another_story():
    scenario_ = _scenario_with_steps(_matching_step())
    scenario_.pins = (Pin(story_id=StoryId('t'), sentence_id=SentenceId(9)),)
    assert compute_coverage(
        scenario_, build_story_index(_guest_search_room_story())
    ) == {SentenceId(1)}


@scenario(
    t'A {pg["Sentence"].low} with two distinct {pg["Term"]("terms")} is '
    t'{pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_true_for_two_distinct_terms():
    with given(t'a {pg["Sentence"]} anchored by two distinct {pg["Term"]} refs'):
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
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is eligible for {pg["Coverage"]} tracking'):
        assert eligible is True


@scenario(
    t'An under-anchored {pg["Sentence"].low} is not {pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_false_for_one_distinct_term():
    with given(t'a {pg["Sentence"]} that mentions only one distinct {pg["Term"]}'):
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
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is ineligible — {pg["Coverage"]} needs at least two anchors'):
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
    behavior). A pin still reaches it — the sibling
    scenario below."""
    with given(t'a {pg["Story"]} whose {pg["Sentence"]} is all bare words'):
        a = Sentence(
            id=SentenceId(1),
            clauses=(_clause(ClauseWord(text='just'), ClauseWord(text='words')),),
        )
        story = Story(id=StoryId('s'), title='S', sentences=(a,))
    with given(t'a {pg["Scenario"]} narrating one {pg["Term ref"]}'):
        scenario = _scenario_with_steps(
            _step('given', _term_ref('guest', 'Guest')),
            _step('when'),
        )
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} excludes the under-anchored {pg["Sentence"]}'):
        assert SentenceId(1) not in coverage


@scenario(
    t'Nested {pg["Step"]("steps")} are walked for {pg["Coverage"].low}',
)
def test_compute_coverage_nested_steps_are_walked():
    """Steps nested as children are also examined for coverage."""
    with given(t'a {pg["Story"]} with one canonical {pg["Sentence"]}'):
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
        t'the covering {pg["Term ref"]("term refs")} in a nested child {pg["Step"]}'
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
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(
        t'the nested {pg["Step"]} still counts and the {pg["Sentence"]} is covered'
    ):
        assert SentenceId(1) in coverage


@scenario(
    t'An explicit {pg["Step"].low} binding covers an eligible {pg["Sentence"].low}',
)
def test_compute_coverage_explicit_step_binding_covers_eligible_sentence():
    """A step pin covers an eligible (>=2 distinct
    term) sentence directly, without narration matching."""
    with given(t'a {pg["Story"]} with a coverage-eligible {pg["Sentence"]}'):
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
    with given(
        t'a {pg["Step"]} {pg["Scenario↔sentence binding"]("bound")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', pins=[1]))
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} counts it directly, without narration matching'):
        assert SentenceId(1) in coverage


@scenario(
    t'An explicit binding covers an under-anchored {pg["Sentence"].low}',
)
def test_compute_coverage_explicit_binding_covers_under_anchored_sentence():
    """Eligibility gates narration matching only. An explicit binding says what
    the narration cannot, so it covers an under-anchored sentence too."""
    with given(t'a {pg["Story"]} whose {pg["Sentence"]} is under-anchored'):
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
    with given(
        t'a {pg["Step"]} {pg["Scenario↔sentence binding"]("bound")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', pins=[1]))
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} counts it, despite the missing anchors'):
        assert SentenceId(1) in coverage
