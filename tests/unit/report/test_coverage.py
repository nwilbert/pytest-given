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
    ParameterCase,
    ParameterColumn,
    ParameterTable,
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
    param_case_displays,
    s_for_step,
)
from tests.ubiquitous_language import pg


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


@scenario(
    t'A {pg["Verb"].low} {pg["Activity"].low} ref has one identity '
    t'regardless of {pg["Inflection"].low}',
)
def test_identity_of_activity_term_ref_verb_ignores_display(g):
    with given(t'a {pg["Verb"]} written canonically and as an {pg["Inflection"]}'):
        p1 = ActivityTermRef(term_id=TermId('search'), display='search')
        p2 = ActivityTermRef(term_id=TermId('search'), display='searches for')
    with when(t'{pg["Coverage"]} derives each {pg["Term ref"]} identity'):
        id1 = identity_of_part(g, p1)
        id2 = identity_of_part(g, p2)
    with then('both collapse to the one canonical verb identity'):
        assert id1 == id2 == Identity(term_id='search', instance_id=None)


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


@scenario(
    t'A branching {pg["Activity"].low} unions references across its '
    t'{pg["Path"]("paths")}',
)
def test_a_refs_unions_across_multi_path_activity(g):
    with given(t'an {pg["Activity"]} that branches into two {pg["Path"]} alternatives'):
        a = Activity(
            id=ActivityId(1),
            paths=(
                _path(
                    _entity('guest', 'Alice'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
                _path(
                    _entity('guest', 'Bob'),
                    _term_part('search'),
                    _entity('room', 'Room'),
                ),
            ),
        )
    with when(t'{pg["Coverage"]} collects the {pg["Activity"]} references'):
        refs = a_refs(g, a)
    with then(t'both {pg["Instance"]} identities across the branches are present'):
        assert Identity('guest', 'alice') in refs
        assert Identity('guest', 'bob') in refs


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
    t'An {pg["Instance"].low} {pg["Step"].low} ref adds a canonical fallback',
)
def test_s_for_step_instance_entity_ref_adds_canonical_fallback(g):
    with given(t'a {pg["Step"]} referring to a named {pg["Instance"]}'):
        step = _step('when', _term_ref('guest', 'Alice'))
    with when(t'{pg["Coverage"]} computes the identity set for the {pg["Step"]}'):
        identities = s_for_step(g, step)
    with then(t'it includes the canonical {pg["Term ref"]} fallback'):
        assert identities == {
            Identity('guest', 'alice'),
            Identity('guest', None),
        }


@scenario(
    t'A {pg["Verb"].low} ref always resolves to its canonical identity',
)
def test_s_for_step_verb_ref_always_canonical(g):
    with given(t'a {pg["Step"]} using an {pg["Inflection"]} of a {pg["Verb"]}'):
        step = _step('when', _term_ref('search', 'searches for'))
    with when(t'{pg["Coverage"]} computes its identity set'):
        identities = s_for_step(g, step)
    with then('the identity ignores the surface form and stays canonical'):
        assert identities == {Identity('search', None)}


@scenario(
    t'An unknown {pg["Term ref"].low} is skipped',
    tags=['validation'],
)
def test_s_for_step_unknown_term_ref_skipped(g):
    with given(t'a {pg["Step"]} referencing a {pg["Term"]} not in the glossary'):
        step = _step('when', _term_ref('unknown', 'something'))
    with when(t'{pg["Coverage"]} computes its identity set'):
        identities = s_for_step(g, step)
    with then('the unknown ref contributes nothing to the identity set'):
        assert identities == set()


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
    t'An {pg["Instance"].low} {pg["Step"].low} covers a canonical {pg["Activity"].low}',
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
    with then(t'{pg["Coverage"]} reports the {pg["Activity"]} as covered'):
        assert ActivityId(1) in coverage
        assert len(coverage[ActivityId(1)]) == 1


@scenario(
    t'A canonical {pg["Step"].low} does not cover an {pg["Instance"].low} '
    t'{pg["Activity"].low}',
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
    with then(t'{pg["Coverage"]} leaves the more specific instance activity uncovered'):
        assert coverage.get(ActivityId(1), set()) == set()


@scenario(
    t'Promoting a bare word to a {pg["Verb"].low} ref drops '
    t'{pg["Coverage"].low} from a {pg["Step"].low} that matched',
)
def test_compute_coverage_lost_when_activity_gains_a_term(g):
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
            g, scenario, Story(id=StoryId('s'), title='S', activities=(bare,))
        )
        after = compute_coverage(
            g, scenario, Story(id=StoryId('s'), title='S', activities=(promoted,))
        )
    with then(t'the two-ref {pg["Activity"]} is covered'):
        assert ActivityId(1) in before
    with then(t'the widened {pg["Activity"]} is no longer covered'):
        assert ActivityId(1) not in after


@scenario(
    t'A {pg["Scenario"].low} {pg["Activity"].low} binding '
    t'constrains {pg["Coverage"].low}',
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
    with when(
        t'the {pg["Scenario"]} {pg["Scenario↔activity binding"]("binds")} '
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
        coverage = compute_coverage(g, scenario, story)
    with then(t'{pg["Coverage"]} considers only the bound {pg["Activity"]}'):
        assert ActivityId(1) in coverage
        assert ActivityId(2) not in coverage


@scenario(
    t'An {pg["Activity"].low} with two distinct {pg["Term"]("terms")} is '
    t'{pg["Coverage"].low}-eligible',
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
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is eligible for {pg["Coverage"]} tracking'):
        assert eligible is True


@scenario(
    t'An under-anchored {pg["Activity"].low} is not {pg["Coverage"].low}-eligible',
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
    with when(t'its {pg["Coverage"]} eligibility is checked'):
        eligible = is_coverage_eligible(a)
    with then(t'it is ineligible — {pg["Coverage"]} needs at least two anchors'):
        assert eligible is False


def test_is_coverage_eligible_false_for_all_bare_activity(g):
    a = Activity(
        id=ActivityId(1),
        paths=(_path(ActivityWord(text='just'), ActivityWord(text='words')),),
    )
    assert is_coverage_eligible(a) is False


@scenario(
    t'An under-anchored {pg["Activity"].low} is never reported as covered',
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
    with then(t'{pg["Coverage"]} excludes the under-anchored {pg["Activity"]}'):
        assert ActivityId(1) not in coverage


@scenario(
    t'Nested {pg["Step"]("steps")} are walked for {pg["Coverage"].low}',
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
    t'An explicit {pg["Step"].low} binding covers an eligible {pg["Activity"].low}',
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
    with when(
        t'a {pg["Step"]} {pg["Scenario↔activity binding"]("binds")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
        coverage = compute_coverage(g, scenario, story)
    with then(t'{pg["Coverage"]} counts it directly, without identity matching'):
        assert ActivityId(1) in coverage


@scenario(
    'An explicit binding still requires eligibility',
    tags=['validation'],
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
    with when(
        t'a {pg["Step"]} {pg["Scenario↔activity binding"]("binds")} '
        t'to it explicitly by id'
    ):
        scenario = _scenario_with_steps(_step('when', activity_ids=[1]))
        coverage = compute_coverage(g, scenario, story)
    with then(t'eligibility gates the binding, so {pg["Coverage"]} stays empty'):
        assert ActivityId(1) not in coverage


def test_coverage_finds_an_activity_anchored_on_a_non_baseline_case(
    guest_scenario: tuple[Glossary, Story, Scenario],
) -> None:
    glossary, story, scenario = guest_scenario
    assert ActivityId(1) in compute_coverage(glossary, scenario, story)


def test_coverage_does_not_mix_displays_from_two_cases(
    guest_scenario: tuple[Glossary, Story, Scenario],
) -> None:
    """An activity satisfied only by combining case 1's Alice with case 2's Bob
    is matched by no single case, so it must not be matched at all."""
    glossary, _story, scenario = guest_scenario
    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(term_id=TermId('guest'), display='Alice'),
                            ActivityTermRef(term_id=TermId('guest'), display='Bob'),
                            ActivityTermRef(
                                term_id=TermId('check-in'), display='checks in'
                            ),
                        )
                    ),
                ),
            ),
        ),
    )
    assert compute_coverage(glossary, scenario, story) == {}


def test_param_case_displays_is_empty_without_a_param_linked_pill(
    guest_scenario: tuple[Glossary, Story, Scenario],
) -> None:
    _glossary, _story, scenario = guest_scenario
    scenario.steps[0].narration.parts[0] = NarrationTermRef(
        term_id=TermId('guest'), display='Alice'
    )
    assert param_case_displays(scenario) == []


def test_param_case_displays_is_empty_for_an_unparametrized_scenario() -> None:
    scenario = Scenario(
        id=NodeId('t.py::test_x'), narration=Narration(text='x'), module='m'
    )
    assert param_case_displays(scenario) == []


def test_param_case_displays_skips_non_param_unlinked_and_none_cells() -> None:
    """The per-case filter has three independent reasons to drop a column
    from a case's substitution mapping: it isn't a `param` column even though
    a pill is bound to it (`note`, below — a derived column can share a name
    with a parametrize argname), it's a `param` column but no pill is bound to
    it (`other`, below), or the cell is `None` for a case — a legitimate
    parametrize value, not a missing one, but not something a pill display
    substitutes in."""
    step = Step(
        phase='when',
        narration=Narration(
            text='Alice checks in noteA',
            parts=[
                NarrationTermRef(
                    term_id=TermId('guest'),
                    display='Alice',
                    expression='guest',
                    param_column='guest',
                ),
                NarrationTermRef(
                    term_id=TermId('note'),
                    display='noteA',
                    expression='note',
                    param_column='note',
                ),
            ],
        ),
    )
    scenario = Scenario(
        id=NodeId('t.py::test_check_in'),
        narration=Narration(text='checks in'),
        module='m',
        steps=[step],
        parameters=ParameterTable(
            columns=[
                ParameterColumn(id='guest', name='guest', kind='param'),
                ParameterColumn(id='derived:0', name='note', kind='derived'),
                ParameterColumn(id='attachment:0', name='log', kind='attachment'),
                ParameterColumn(id='other', name='other', kind='param'),
            ],
            cases=[
                ParameterCase(values=['Alice', 'noteA', None, 'X'], status='passed'),
                ParameterCase(values=[None, 'noteB', None, 'Y'], status='passed'),
            ],
        ),
    )
    assert param_case_displays(scenario) == [{'guest': 'Alice'}, {}]


def test_param_case_displays_drops_a_case_that_did_not_pass() -> None:
    """A skipped case ran nothing, so its parametrize value must not stand in
    for a pill: doing so lets it satisfy a story activity and lists it in the
    Glossary as an observed instance of the term."""
    step = Step(
        phase='when',
        narration=Narration(
            text='Alice checks in',
            parts=[
                NarrationTermRef(
                    term_id=TermId('guest'),
                    display='Alice',
                    expression='guest',
                    param_column='guest',
                ),
            ],
        ),
    )
    scenario = Scenario(
        id=NodeId('t.py::test_check_in'),
        narration=Narration(text='checks in'),
        module='m',
        steps=[step],
        parameters=ParameterTable(
            columns=[ParameterColumn(id='guest', name='guest', kind='param')],
            cases=[
                ParameterCase(values=['Alice'], status='passed'),
                ParameterCase(values=['Bob'], status='skipped'),
                ParameterCase(values=['Carol'], status='failed'),
            ],
        ),
    )
    assert param_case_displays(scenario) == [{'guest': 'Alice'}]


def test_s_for_step_drops_a_pill_the_case_has_no_value_for(g) -> None:
    """A pill bound to a parametrize column whose cell this case leaves empty
    has no display *for this case*. Falling back to the one the grouped tree
    carries would hand the case another case's guest, and let it satisfy an
    activity naming that guest."""
    step = _step(
        'when',
        NarrationTermRef(
            term_id=TermId('guest'),
            display='Alice',
            expression='guest',
            param_column='guest',
        ),
    )
    assert s_for_step(g, step, {}) == set()
    assert s_for_step(g, step, {'guest': 'Alice'}) == {
        Identity('guest', 'alice'),
        Identity('guest', None),
    }
