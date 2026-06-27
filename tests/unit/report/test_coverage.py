import pytest

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
    s_for_step,
)


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


def test_s_for_step_instance_entity_ref_adds_canonical_fallback(g):
    step = _step('when', _term_ref('guest', 'Alice'))
    assert s_for_step(g, step) == {
        Identity('guest', 'alice'),
        Identity('guest', None),
    }


def test_s_for_step_verb_ref_always_canonical(g):
    step = _step('when', _term_ref('search', 'searches for'))
    assert s_for_step(g, step) == {Identity('search', None)}


def test_s_for_step_unknown_term_ref_skipped(g):
    """A NarrationTermRef referencing a term not in the glossary is silently skipped."""
    step = _step('when', _term_ref('unknown', 'something'))
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


def test_compute_coverage_covers_canonical_activity_via_instance_step(g):
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a,))
    scenario = _scenario_with_steps(
        _step(
            'when',
            _term_ref('guest', 'Alice'),
            _term_ref('search', 'searches for'),
            _term_ref('room', 'Room'),
        ),
    )
    coverage = compute_coverage(g, scenario, story)
    assert ActivityId(1) in coverage
    assert len(coverage[ActivityId(1)]) == 1


def test_compute_coverage_does_not_cover_instance_activity_with_canonical_step(g):
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Alice'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a,))
    scenario = _scenario_with_steps(
        _step(
            'when',
            _term_ref('guest', 'Guest'),
            _term_ref('search', 'searches for'),
            _term_ref('room', 'Room'),
        ),
    )
    coverage = compute_coverage(g, scenario, story)
    assert coverage.get(ActivityId(1), set()) == set()


def test_compute_coverage_scenario_constrained_to_activity_ids(g):
    a1 = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    a2 = Activity(
        id=ActivityId(2),
        paths=(
            _path(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a1, a2))
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
    assert ActivityId(1) in coverage
    assert ActivityId(2) not in coverage


def test_compute_coverage_empty_refs_activity_matches_every_step(g):
    """An activity with no identity-bearing parts (only ActivityWord) has
    `a_refs == set()`, which is a subset of every step. The matching code
    preserves this degenerate-but-original semantics so deserialized data
    keeps the same coverage shape it had in-memory."""
    a = Activity(
        id=ActivityId(1),
        paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a,))
    scenario = _scenario_with_steps(
        _step('given', _term_ref('guest', 'Guest')),
        _step('when'),
    )
    coverage = compute_coverage(g, scenario, story)
    assert len(coverage[ActivityId(1)]) == 2


def test_compute_coverage_nested_steps_are_walked(g):
    """Steps nested as children are also examined for coverage."""
    a = Activity(
        id=ActivityId(1),
        paths=(
            _path(
                _entity('guest', 'Guest'), _term_part('search'), _entity('room', 'Room')
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a,))
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
    assert ActivityId(1) in coverage
    assert len(coverage[ActivityId(1)]) == 1
