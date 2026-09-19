from pytest_given import given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    Scenario,
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
    return ActivityTermRef(term_id=TermId(tid), display=display)


def _term_part(tid):
    return ActivityTermRef(term_id=TermId(tid), display=tid)


def _path(*parts):
    return ActivityPath(parts=parts)


@scenario(
    t'An {pg["Activity"].low} is referenced by its {pg["Term"]("terms")}, '
    t'whatever their surface form',
)
def test_a_refs_collects_term_ids_whatever_the_display():
    with given(
        t'an {pg["Activity"]} written with an {pg["Instance"]} and an '
        t'{pg["Inflection"]}'
    ):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Alice'),
                    _entity('search', 'searches for'),
                    ActivityWord(text='a'),
                    _entity('room', 'Deluxe Suite'),
                ),
            ),
        )
    with when(t'{pg["Coverage"]} collects the {pg["Activity"]} references'):
        refs = a_refs(a)
    with then(t'they are the {pg["Term"]} ids alone; words contribute nothing'):
        assert refs == {TermId('guest'), TermId('search'), TermId('room')}


@scenario(
    t'A branching {pg["Activity"].low} unions references across its '
    t'{pg["Path"]("paths")}',
)
def test_a_refs_unions_across_multi_path_activity():
    with given(t'an {pg["Activity"]} that branches into two {pg["Path"]} alternatives'):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('booking', 'Booking'),
                ),
            ),
        )
    with when(t'{pg["Coverage"]} collects the {pg["Activity"]} references'):
        refs = a_refs(a)
    with then(t'the {pg["Term"]("terms")} of both branches are present'):
        assert TermId('room') in refs
        assert TermId('booking') in refs


def _step(phase, *term_refs, activity_ids=()):
    return Step(
        phase=phase,
        narration=Narration(
            text='x',
            parts=(
                NarrationLiteral(value='x'),
                *list(term_refs),
            ),
        ),
        activity_ids=tuple(ActivityId(i) for i in activity_ids),
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


def _scenario_with_steps(*steps, activity_ids=()):
    return Scenario(
        id=NodeId('test'),
        narration=Narration(text='scn'),
        module='m',
        steps=list(steps),
        story_id=StoryId('story'),
        activity_ids=tuple(ActivityId(i) for i in activity_ids),
    )


@scenario(
    t'An {pg["Instance"].low} and its bare {pg["Term"].low} cover each other',
)
def test_compute_coverage_matches_instance_and_bare_term_both_ways():
    with given(t'an {pg["Activity"]} naming a bare {pg["Actor"]}'):
        bare = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with given(t'the same {pg["Activity"]} naming an {pg["Instance"]} of that actor'):
        instance = Activity(
            id=ActivityId(1),
            paths=(
                _path(
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
            Story(id=StoryId('s'), title='S', activities=(bare,))
        )
        instance_index = build_story_index(
            Story(id=StoryId('s'), title='S', activities=(instance,))
        )
        bare_by_instance = compute_coverage(instance_step, bare_index)
        instance_by_bare = compute_coverage(bare_step, instance_index)
    with then(t'the {pg["Instance"]} {pg["Step"]} covers the bare {pg["Activity"]}'):
        assert ActivityId(1) in bare_by_instance
    with then(t'the bare {pg["Step"]} covers the {pg["Instance"]} {pg["Activity"]}'):
        assert ActivityId(1) in instance_by_bare


@scenario(
    t'Promoting a bare word to a {pg["Verb"].low} ref drops '
    t'{pg["Coverage"].low} from a {pg["Step"].low} that matched',
)
def test_compute_coverage_lost_when_activity_gains_a_term():
    """Widening an activity's identity set silently uncovers it: a step that
    covered the activity before the edit no longer does."""
    with given(t'a {pg["Step"]} naming two {pg["Term ref"]("term refs")}'):
        scenario = _scenario_with_steps(
            _step('when', _term_ref('guest', 'Guest'), _term_ref('room', 'Room'))
        )
    with given(
        t'the same {pg["Activity"]} with that middle slot a bare word, '
        t'then a {pg["Verb"]} ref'
    ):
        bare = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    ActivityWord(text='books'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        promoted = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with when(t'{pg["Coverage"]} is computed against each {pg["Story"]}'):
        before = compute_coverage(
            scenario,
            build_story_index(Story(id=StoryId('s'), title='S', activities=(bare,))),
        )
        after = compute_coverage(
            scenario,
            build_story_index(
                Story(id=StoryId('s'), title='S', activities=(promoted,))
            ),
        )
    with then(t'the two-ref {pg["Activity"]} is covered'):
        assert ActivityId(1) in before
    with then(t'the widened {pg["Activity"]} is no longer covered'):
        assert ActivityId(1) not in after


@scenario(
    t'A {pg["Scenario"].low} {pg["Activity"].low} binding '
    t'constrains {pg["Coverage"].low}',
)
def test_compute_coverage_scenario_constrained_to_activity_ids():
    with given(t'a {pg["Story"]} with two matching activities'):
        a1 = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        a2 = Activity(
            id=ActivityId(2),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', activities=(a1, a2))
    with given(
        t'a {pg["Scenario"]} {pg["Scenario↔activity binding"]("bound")} '
        t'only to activity 1'
    ):
        scenario = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('search', 'search'),
                _term_ref('room', 'Room'),
            ),
            activity_ids=[1],
        )
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} considers only the bound {pg["Activity"]}'):
        assert ActivityId(1) in coverage
        assert ActivityId(2) not in coverage


@scenario(
    t'An {pg["Activity"].low} with two distinct {pg["Term"]("terms")} is '
    t'{pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_true_for_two_distinct_terms():
    with given(t'an {pg["Activity"]} anchored by two distinct {pg["Term"]} refs'):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    ActivityWord(text='x'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is eligible for {pg["Coverage"]} tracking'):
        assert eligible is True


@scenario(
    t'An under-anchored {pg["Activity"].low} is not {pg["Coverage"].low}-eligible',
)
def test_is_coverage_eligible_false_for_one_distinct_term():
    with given(t'an {pg["Activity"]} that mentions only one distinct {pg["Term"]}'):
        # same term twice still counts as one distinct term id
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    ActivityWord(text='greets'),
                    _entity('guest', 'Alice'),
                ),
            ),
        )
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is ineligible — {pg["Coverage"]} needs at least two anchors'):
        assert eligible is False


def test_is_coverage_eligible_false_for_all_bare_activity():
    a = Activity(
        id=ActivityId(1),
        paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
    )
    assert is_coverage_eligible(a) is False


@scenario(
    t'An under-anchored {pg["Activity"].low} is never covered by narration matching',
)
def test_compute_coverage_excludes_under_anchored_activity():
    """An activity with fewer than two distinct terms is excluded from
    narration matching (replaces the old 'empty refs matches every step'
    behavior). An explicit `activity=` pin still reaches it — the sibling
    scenario below."""
    with given(t'a {pg["Story"]} whose {pg["Activity"]} is all bare words'):
        a = Activity(
            id=ActivityId(1),
            paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
        )
        story = Story(id=StoryId('s'), title='S', activities=(a,))
    with given(t'a {pg["Scenario"]} narrating one {pg["Term ref"]}'):
        scenario = _scenario_with_steps(
            _step('given', _term_ref('guest', 'Guest')),
            _step('when'),
        )
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} excludes the under-anchored {pg["Activity"]}'):
        assert ActivityId(1) not in coverage


@scenario(
    t'Nested {pg["Step"]("steps")} are walked for {pg["Coverage"].low}',
)
def test_compute_coverage_nested_steps_are_walked():
    """Steps nested as children are also examined for coverage."""
    with given(t'a {pg["Story"]} with one canonical {pg["Activity"]}'):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', activities=(a,))
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
        t'the nested {pg["Step"]} still counts and the {pg["Activity"]} is covered'
    ):
        assert ActivityId(1) in coverage


@scenario(
    t'An explicit {pg["Step"].low} binding covers an eligible {pg["Activity"].low}',
)
def test_compute_coverage_explicit_step_binding_covers_eligible_activity():
    """An explicit step activity_ids binding covers an eligible (>=2 distinct
    term) activity directly, without narration matching."""
    with given(t'a {pg["Story"]} with a coverage-eligible {pg["Activity"]}'):
        activity = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', activities=(activity,))
    with given(
        t'a {pg["Step"]} {pg["Scenario↔activity binding"]("bound")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} counts it directly, without narration matching'):
        assert ActivityId(1) in coverage


@scenario(
    t'An explicit binding covers an under-anchored {pg["Activity"].low}',
)
def test_compute_coverage_explicit_binding_covers_under_anchored_activity():
    """Eligibility gates narration matching only. An explicit binding says what
    the narration cannot, so it covers an under-anchored activity too."""
    with given(t'a {pg["Story"]} whose {pg["Activity"]} is under-anchored'):
        activity = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Guest'),
                    ActivityWord(text='browses'),
                    ActivityWord(text='listings'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', activities=(activity,))
    with given(
        t'a {pg["Step"]} {pg["Scenario↔activity binding"]("bound")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
    with when(t'{pg["Coverage"]} is computed against the {pg["Story"]}'):
        coverage = compute_coverage(scenario, build_story_index(story))
    with then(t'{pg["Coverage"]} counts it, despite the missing anchors'):
        assert ActivityId(1) in coverage
