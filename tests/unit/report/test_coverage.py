import pytest

from pytest_given import given, scenario, then, when
from pytest_given.capture.glossary import id_derive
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    GlossaryTerm,
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
    Identity,
    a_refs,
    compute_coverage,
    identity_of_part,
    instance_id_of,
    is_coverage_eligible,
    s_for_step,
)
from tests._vocab import pg


def _term(kind, name):
    return GlossaryTerm(id=id_derive(name), kind=kind, canonical=name)


@pytest.fixture
def g():
    g = Glossary()
    g._register(_term('actor', 'Guest'))
    g._register(_term('object', 'Room'))
    g._register(_term('verb', 'search'))
    return g


def test_instance_id_of_canonical_returns_none(g):
    assert instance_id_of(g, TermId('guest'), 'Guest') is None


def test_instance_id_of_distinct_display_returns_derived_id(g):
    assert instance_id_of(g, TermId('guest'), 'Alice') == 'alice'


def test_identity_of_activity_term_ref_actor_canonical(g):
    p = ActivityTermRef(term_id=TermId('guest'), display='Guest')
    assert identity_of_part(g, p) == Identity(term_id='guest', instance_id=None)


def test_identity_of_activity_term_ref_actor_instance(g):
    p = ActivityTermRef(term_id=TermId('guest'), display='Alice')
    assert identity_of_part(g, p) == Identity(term_id='guest', instance_id='alice')


def test_identity_of_activity_term_ref_verb_ignores_display(g):
    p1 = ActivityTermRef(term_id=TermId('search'), display='search')
    p2 = ActivityTermRef(term_id=TermId('search'), display='searches for')
    assert identity_of_part(g, p1) == identity_of_part(g, p2)


def test_identity_of_word_is_none(g):
    assert identity_of_part(g, ActivityWord(text='for')) is None


def test_identity_of_activity_term_ref_kindless_uses_instance_identity(g):
    """A term whose kind is None (kindless) falls through to instance-identity
    logic — NOT the verb (term_id, None) path. The returned identity is derived
    from the display string, exactly as for actors and objects."""
    kindless_term = GlossaryTerm(id=TermId('widget'), kind=None, canonical='Widget')
    g._register(kindless_term)
    part = ActivityTermRef(term_id=TermId('widget'), display='My Widget')
    expected_instance_id = id_derive('My Widget')
    result = identity_of_part(g, part)
    assert result == Identity(
        term_id=TermId('widget'), instance_id=expected_instance_id
    )
    assert result != Identity(term_id=TermId('widget'), instance_id=None)


# --- Task 8.2: a_refs ---


def _entity(tid, display):
    return ActivityTermRef(term_id=TermId(tid), display=display)


def _term_part(tid):
    return ActivityTermRef(term_id=TermId(tid), display=tid)


def _path(*parts):
    return ActivityPath(parts=parts)


def test_a_refs_for_canonical_activity(g):
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    assert a_refs(g, a) == {
        Identity('guest', None),
        Identity('search', None),
        Identity('room', None),
    }


def test_a_refs_for_instance_activity(g):
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Alice'),
                _term_part('search'),
                _entity('room', 'Deluxe Suite'),
            ),
        ),
    )
    assert a_refs(g, a) == {
        Identity('guest', 'alice'),
        Identity('search', None),
        Identity('room', 'deluxe-suite'),
    }


def test_a_refs_unions_across_multi_path_activity(g):
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Alice'), _term_part('search'), _entity('room', 'Room')
            ),
            _path(
                _entity('guest', 'Bob'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    assert Identity('guest', 'alice') in a_refs(g, a)
    assert Identity('guest', 'bob') in a_refs(g, a)


# --- Task 8.3: s_for_step and compute_coverage ---


def _step(phase, *term_refs, activity_ids=()):
    return Step(
        phase=phase,
        narration=Narration(
            text='x',
            parts=[NarrationLiteral(value='x'), *list(term_refs)],
        ),
        activity_ids=tuple(ActivityId(i) for i in activity_ids),
    )


def _term_ref(tid, display):
    return NarrationTermRef(term_id=TermId(tid), display=display)


def test_s_for_step_canonical_entity_ref(g):
    step = _step('when', _term_ref('guest', 'Guest'))
    assert s_for_step(g, step) == {Identity('guest', None)}


@scenario(
    'An instance step ref adds a canonical fallback',
    tags=['coverage', 'inference'],
)
def test_s_for_step_instance_entity_ref_adds_canonical_fallback(g):
    with given(t'a {pg["Step"]} referring to a named {pg["Instance"]}'):
        step = _step('when', _term_ref('guest', 'Alice'))
    with then(t'its identity set includes the canonical {pg["Term ref"]} fallback'):
        assert s_for_step(g, step) == {
            Identity('guest', 'alice'),
            Identity('guest', None),
        }


@scenario(
    'A verb ref always resolves to its canonical identity',
    tags=['coverage', 'happy-path'],
)
def test_s_for_step_verb_ref_always_canonical(g):
    with given(t'a {pg["Step"]} using an {pg["Inflection"]} of a {pg["Verb"]}'):
        step = _step('when', _term_ref('search', 'searches for'))
    with then('the identity ignores the surface form and stays canonical'):
        assert s_for_step(g, step) == {Identity('search', None)}


@scenario(
    'An unknown term ref is skipped',
    tags=['coverage', 'validation'],
)
def test_s_for_step_unknown_term_ref_skipped(g):
    with given(t'a {pg["Step"]} referencing a {pg["Term"]} not in the glossary'):
        step = _step('when', _term_ref('unknown', 'something'))
    with then('it contributes nothing to the identity set'):
        assert s_for_step(g, step) == set()


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
    'An instance step covers a canonical activity',
    tags=['coverage', 'happy-path'],
)
def test_compute_coverage_covers_canonical_activity_via_instance_step(g):
    with given(t'a {pg["Story"]} with a canonical {pg["Activity"]}'):
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
    with when(t'a {pg["Scenario"]} step names a specific {pg["Instance"]}'):
        scenario = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Alice'),
                _term_ref('search', 'searches for'),
                _term_ref('room', 'Room'),
            ),
        )
        coverage = compute_coverage(g, scenario, story)
    with then(t'the {pg["Activity"]} is reported as covered'):
        assert ActivityId(1) in coverage
        assert len(coverage[ActivityId(1)]) == 1


@scenario(
    'A canonical step does not cover an instance activity',
    tags=['coverage', 'inference'],
)
def test_compute_coverage_does_not_cover_instance_activity_with_canonical_step(g):
    with given(t'an {pg["Activity"]} anchored to a named {pg["Instance"]}'):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Alice'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
        story = Story(id=StoryId('s'), title='S', activities=(a,))
    with when(t'a {pg["Scenario"]} step only names the canonical {pg["Actor"]}'):
        scenario = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('search', 'searches for'),
                _term_ref('room', 'Room'),
            ),
        )
        coverage = compute_coverage(g, scenario, story)
    with then('the more specific instance activity stays uncovered'):
        assert coverage.get(ActivityId(1), set()) == set()


@scenario(
    'A scenario activity binding constrains coverage',
    tags=['coverage', 'happy-path'],
)
def test_compute_coverage_scenario_constrained_to_activity_ids(g):
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
    with when(t'the {pg["Scenario"]} binds only to activity 1'):
        scenario = _scenario_with_steps(
            _step(
                'when',
                _term_ref('guest', 'Guest'),
                _term_ref('search', 'search'),
                _term_ref('room', 'Room'),
            ),
            activity_ids=[1],
        )
        coverage = compute_coverage(g, scenario, story)
    with then('only the bound activity is considered for coverage'):
        assert ActivityId(1) in coverage
        assert ActivityId(2) not in coverage


@scenario(
    'An activity with two distinct terms is coverage-eligible',
    tags=['coverage', 'inference'],
)
def test_is_coverage_eligible_true_for_two_distinct_terms(g):
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
    with then('it is eligible for coverage tracking'):
        assert is_coverage_eligible(a) is True


@scenario(
    'An under-anchored activity is not coverage-eligible',
    tags=['coverage', 'inference'],
)
def test_is_coverage_eligible_false_for_one_distinct_term(g):
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
    with then('it is not eligible — coverage needs at least two anchors'):
        assert is_coverage_eligible(a) is False


def test_is_coverage_eligible_false_for_all_bare_activity(g):
    a = Activity(
        id=ActivityId(1),
        paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
    )
    assert is_coverage_eligible(a) is False


@scenario(
    'An under-anchored activity is never reported as covered',
    tags=['coverage', 'happy-path'],
)
def test_compute_coverage_excludes_under_anchored_activity(g):
    """An activity with fewer than two distinct terms is excluded from
    matching — it is never reported as covered (replaces the old
    'empty refs matches every step' behaviour)."""
    with given(t'a {pg["Story"]} whose {pg["Activity"]} is all bare words'):
        a = Activity(
            id=ActivityId(1),
            paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
        )
        story = Story(id=StoryId('s'), title='S', activities=(a,))
    with when('coverage is computed against a scenario'):
        scenario = _scenario_with_steps(
            _step('given', _term_ref('guest', 'Guest')),
            _step('when'),
        )
        coverage = compute_coverage(g, scenario, story)
    with then('the under-anchored activity is excluded from coverage'):
        assert ActivityId(1) not in coverage


@scenario(
    'Nested steps are walked for coverage',
    tags=['coverage', 'happy-path'],
)
def test_compute_coverage_nested_steps_are_walked(g):
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
    with when(t'the covering {pg["Term ref"]}s live in a nested child {pg["Step"]}'):
        parent = _step('given')
        child = _step(
            'when',
            _term_ref('guest', 'Guest'),
            _term_ref('search', 'search'),
            _term_ref('room', 'Room'),
        )
        parent.children.append(child)
        scenario = _scenario_with_steps(parent)
        coverage = compute_coverage(g, scenario, story)
    with then(
        t'the nested {pg["Step"]} still counts and the {pg["Activity"]} is covered'
    ):
        assert ActivityId(1) in coverage
        assert len(coverage[ActivityId(1)]) == 1


@scenario(
    'An explicit step binding covers an eligible activity',
    tags=['coverage', 'happy-path'],
)
def test_compute_coverage_explicit_step_binding_covers_eligible_activity(g):
    """An explicit step activity_ids binding covers an eligible (>=2 distinct
    term) activity directly, without identity matching."""
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
    with when(t'a {pg["Step"]} binds to it explicitly by id'):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
        coverage = compute_coverage(g, scenario, story)
    with then('the binding covers it directly, without identity matching'):
        assert ActivityId(1) in coverage


@scenario(
    'An explicit binding still requires eligibility',
    tags=['coverage', 'validation'],
)
def test_compute_coverage_explicit_binding_ignored_for_ineligible_activity(g):
    """An explicit binding to an under-anchored (ineligible) activity is
    ignored — eligibility gates explicit bindings too."""
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
    with when(t'a {pg["Step"]} binds to it explicitly by id'):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
        coverage = compute_coverage(g, scenario, story)
    with then('eligibility gates the binding, so it stays uncovered'):
        assert ActivityId(1) not in coverage
