import pytest

from pytest_given import attach, given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Step,
    Story,
    StoryId,
    TermId,
    report_to_dict,
)
from pytest_given.report.aggregations import (
    build_coverage_maps,
    build_glossary_aggregations,
    build_scenario_slug_index,
    build_story_rollups,
    build_term_scenario_index,
    tab_visibility,
)
from tests.ubiquitous_language import pg


def _ent(tid: str, display: str) -> ActivityTermRef:
    return ActivityTermRef(term_id=TermId(tid), display=display)


def _verb_part(tid: str) -> ActivityTermRef:
    return ActivityTermRef(term_id=TermId(tid), display=tid)


def _g() -> Glossary:
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g._register(GlossaryTerm(id=TermId('search'), kind='verb', canonical='search'))
    return g


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def test_tab_visibility_only_scenarios_visible_with_empty_report() -> None:
    rd = ReportData(metadata=_meta())
    assert tab_visibility(rd) == {
        'scenarios': True,
        'stories': False,
        'glossary': False,
    }


def test_tab_visibility_stories_visible_when_stories_non_empty() -> None:
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    s = Story(id=StoryId('s'), title='S', activities=(a,))
    rd = ReportData(metadata=_meta(), stories=[s])
    assert tab_visibility(rd)['stories'] is True


def test_tab_visibility_glossary_visible_when_glossary_has_terms() -> None:
    rd = ReportData(metadata=_meta(), glossary=_g())
    assert tab_visibility(rd)['glossary'] is True


def test_tab_visibility_glossary_hidden_when_glossary_is_empty() -> None:
    rd = ReportData(metadata=_meta(), glossary=Glossary())
    assert tab_visibility(rd)['glossary'] is False


def test_build_coverage_maps_produces_per_scenario_dicts() -> None:
    g = _g()
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(a,))
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('search'), display='search'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ],
        ),
    )
    scn = Scenario(
        id=NodeId('test::x'),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
        story_id=StoryId('book'),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    maps = build_coverage_maps(rd)
    assert ActivityId(1) in maps[NodeId('test::x')]


def test_build_coverage_maps_empty_for_scenario_without_story() -> None:
    g = _g()
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    maps = build_coverage_maps(rd)
    assert maps[NodeId('t')] == {}


def test_build_coverage_maps_empty_when_no_glossary() -> None:
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn])
    maps = build_coverage_maps(rd)
    assert maps == {NodeId('t'): {}}


def test_build_glossary_aggregations_empty_when_no_glossary() -> None:
    rd = ReportData(metadata=_meta())
    assert build_glossary_aggregations(rd) == {}


@scenario(
    t'The {pg["Glossary"].low} view aggregates {pg["Instance"]("instances")} '
    t'and {pg["Verb"].low} forms',
    tags=['happy-path'],
)
def test_build_glossary_aggregations_collects_instances_and_forms() -> None:
    with given(
        t'a {pg["Report"]} whose {pg["Story"]} and {pg["Scenario"]} reference '
        t'entity {pg["Instance"]}s and an {pg["Inflection"]}'
    ):
        g = _g()
        a = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Alice'),
                        ActivityTermRef(
                            term_id=TermId('search'), display='searches for'
                        ),
                        _ent('room', 'Deluxe Suite'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(a,))
        step = Step(
            phase='when',
            narration=Narration(
                text='x',
                parts=[
                    NarrationTermRef(term_id=TermId('guest'), display='Alice'),
                    NarrationTermRef(term_id=TermId('search'), display='searches'),
                    NarrationTermRef(term_id=TermId('room'), display='Deluxe Suite'),
                ],
            ),
        )
        scn = Scenario(
            id=NodeId('t'),
            narration=Narration(text='s'),
            module='m',
            steps=[step],
            story_id=StoryId('book'),
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
        attach('Report data', report_to_dict(rd))
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_glossary_aggregations(rd)
    with then(t'the entity terms collect their {pg["Instance"]}s'):
        assert 'Alice' in [i.display for i in aggs[TermId('guest')].instances]
        assert 'Deluxe Suite' in [i.display for i in aggs[TermId('room')].instances]
    with then(t'the verb collects its {pg["Inflection"]} but not its canonical form'):
        forms = [f.display for f in aggs[TermId('search')].forms]
        assert 'searches for' in forms
        assert 'search' not in forms


def test_build_glossary_aggregations_skips_unknown_term_in_scenario_narration() -> None:
    """Defensive: a NarrationTermRef whose term_id isn't in the glossary is
    silently skipped (the renderer also defensively falls back)."""
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('missing'), display='X'),
            ],
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_glossary_aggregations(rd)
    # missing term has no aggregation entry.
    assert TermId('missing') not in aggs


def test_build_glossary_aggregations_walks_nested_steps() -> None:
    g = _g()
    inner = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('guest'), display='Alice'),
            ],
        ),
    )
    outer = Step(phase='when', narration=Narration(text='y'), children=[inner])
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[outer],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_glossary_aggregations(rd)
    assert 'Alice' in [i.display for i in aggs[TermId('guest')].instances]


@scenario(
    t'{pg["Term"]("Terms")} referenced by an {pg["Activity"].low} record '
    t'the {pg["Story"].low}',
    tags=['happy-path'],
)
def test_build_glossary_aggregations_records_story_refs_via_activities() -> None:
    with given(
        t'a {pg["Story"]} whose {pg["Activity"]} references an actor and a verb'
    ):
        g = _g()
        a = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        _verb_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(a,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_glossary_aggregations(rd)
    with then(t'the actor and the verb each list that {pg["Story"]}'):
        assert aggs[TermId('guest')].stories == [StoryId('book')]
        assert aggs[TermId('search')].stories == [StoryId('book')]


def test_build_coverage_maps_empty_for_scenario_with_unknown_story_id() -> None:
    """Scenario has a story_id that doesn't match any story in the report."""
    g = _g()
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
        story_id=StoryId('nonexistent'),
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    maps = build_coverage_maps(rd)
    assert maps[NodeId('t')] == {}


def test_build_glossary_aggregations_verb_in_step_not_collected_as_instance() -> None:
    """A verb NarrationTermRef in a scenario step is skipped for instance
    collection (verbs have no instances, only forms from activity paths)."""
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('search'), display='searches'),
            ],
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_glossary_aggregations(rd)
    # Verb terms from scenario steps are not added to aggs as instances.
    assert TermId('search') not in aggs


@scenario(
    t'A canonical entity reference is not an {pg["Instance"].low}',
    tags=['happy-path'],
)
def test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance() -> None:
    with given(
        t'a {pg["Story"]} activity and a {pg["Step"]} referencing entities '
        t'by canonical name only'
    ):
        g = _g()
        a = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        ActivityTermRef(
                            term_id=TermId('search'), display='searches for'
                        ),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(a,))
        step = Step(
            phase='when',
            narration=Narration(
                text='x',
                parts=[NarrationTermRef(term_id=TermId('guest'), display='Guest')],
            ),
        )
        scn = Scenario(
            id=NodeId('t'),
            narration=Narration(text='s'),
            module='m',
            steps=[step],
            story_id=StoryId('book'),
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_glossary_aggregations(rd)
    with then(t'neither entity term records an {pg["Instance"]}'):
        assert aggs[TermId('guest')].instances == []
        assert aggs[TermId('room')].instances == []


def test_build_glossary_aggregations_skips_non_term_ref_narration_parts() -> None:
    """NarrationLiteral / NarrationValue parts in a step are skipped."""
    from pytest_given.model import NarrationLiteral

    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='plain text step',
            parts=[NarrationLiteral(value='plain text step')],
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_glossary_aggregations(rd)
    assert aggs == {}


def test_build_glossary_aggregations_skips_unknown_term_ref_in_activity() -> None:
    """An ActivityTermRef whose term_id isn't in the glossary is silently skipped."""
    g = _g()
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    ActivityTermRef(term_id=TermId('unknown-term'), display='Unknown'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', activities=(a,))
    rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    aggs = build_glossary_aggregations(rd)
    assert TermId('unknown-term') not in aggs


@scenario(
    t'A {pg["Kindless"].low} {pg["Term"].low} records only its {pg["Story"].low} ref',
    tags=['happy-path'],
)
def test_build_glossary_aggregations_kindless_term_records_only_story_ref() -> None:
    with given(
        t'a {pg["Kindless"]} {pg["Term"]} referenced by a {pg["Story"]} activity'
    ):
        g = _g()
        g._register(GlossaryTerm(id=TermId('widget'), kind=None, canonical='Widget'))
        kindless_part = ActivityTermRef(term_id=TermId('widget'), display='My Widget')
        a = Activity(
            id=ActivityId(1),
            paths=(ActivityPath(parts=(kindless_part,)),),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(a,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_glossary_aggregations(rd)
    with then(
        t'the {pg["Term"]} lists the {pg["Story"]} but no {pg["Instance"]} '
        t'and no {pg["Inflection"]}'
    ):
        assert TermId('widget') in aggs, (
            'kindless term should still appear in aggregations'
        )
        widget_agg = aggs[TermId('widget')]
        assert widget_agg.stories == [StoryId('book')], 'story ref must be recorded'
        assert widget_agg.instances == [], (
            'kindless term must not produce an entity instance'
        )
        assert widget_agg.forms == [], 'kindless term must not produce a verb form'


@scenario(
    t'An {pg["Instance"].low} seen in a fixture {pg["Step"].low} '
    t'records its fixture provenance',
    tags=['happy-path'],
)
def test_glossary_aggregations_annotates_fixture_provenance() -> None:
    with given(
        t'a {pg["Scenario"]} whose fixture-sourced {pg["Step"]} names '
        t'an {pg["Instance"]}'
    ):
        g = _g()
        fixture_step = Step(
            phase='given',
            narration=Narration(
                text='our guest Alice',
                parts=[
                    NarrationTermRef(term_id=TermId('guest'), display='Alice'),
                ],
            ),
            fixture_name='alice',
        )
        body_step = Step(
            phase='when',
            narration=Narration(
                text='Alice does',
                parts=[
                    NarrationTermRef(term_id=TermId('guest'), display='Alice'),
                ],
            ),
        )
        scn = Scenario(
            id=NodeId('t'),
            narration=Narration(text='s'),
            module='m',
            steps=[fixture_step, body_step],
            story_id=StoryId('book'),
        )
        a = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        _verb_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', activities=(a,))
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_glossary_aggregations(rd)
    with then(t'the {pg["Instance"]} carries the fixture name'):
        alice = next(i for i in aggs[TermId('guest')].instances if i.display == 'Alice')
        assert alice.fixture_name == 'alice'


def test_build_term_scenario_index_empty_when_no_glossary() -> None:
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn])
    assert build_term_scenario_index(rd) == {}


def test_build_term_scenario_index_maps_terms_to_scenarios() -> None:
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ],
        ),
    )
    scn = Scenario(
        id=NodeId('test::a'),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    index = build_term_scenario_index(rd)
    assert index[TermId('guest')] == [NodeId('test::a')]
    assert index[TermId('room')] == [NodeId('test::a')]
    assert TermId('search') not in index


@scenario(
    t'The {pg["Term"].low} index maps each {pg["Term"].low} to its '
    t'{pg["Scenario"]("scenarios")} once',
    tags=['happy-path'],
)
def test_build_term_scenario_index_dedups_and_includes_scenario_narration() -> None:
    with given(
        t'a {pg["Scenario"]} referencing one {pg["Term"]} in two steps '
        t'and another in its name'
    ):
        g = _g()
        step_one = Step(
            phase='when',
            narration=Narration(
                text='x',
                parts=[NarrationTermRef(term_id=TermId('guest'), display='Guest')],
            ),
        )
        step_two = Step(
            phase='then',
            narration=Narration(
                text='y',
                parts=[NarrationTermRef(term_id=TermId('guest'), display='Guest')],
            ),
        )
        scn = Scenario(
            id=NodeId('test::a'),
            narration=Narration(
                text='scn',
                parts=[NarrationTermRef(term_id=TermId('room'), display='Room')],
            ),
            module='m',
            steps=[step_one, step_two],
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    with when('the term-scenario index is built'):
        index = build_term_scenario_index(rd)
    with then(t'each {pg["Term"]} maps to the scenario exactly once'):
        assert index[TermId('guest')] == [NodeId('test::a')]  # dedup across steps
        assert index[TermId('room')] == [NodeId('test::a')]  # narration counts


def _scn(node_id: str) -> Scenario:
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='s'),
        module='m',
    )


def test_scenario_slug_strips_test_prefix_and_py_and_dir() -> None:
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('examples/hotel-booking/test_hotel_booking.py::test_complete_booking')
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index == {
        NodeId(
            'examples/hotel-booking/test_hotel_booking.py::test_complete_booking'
        ): 'hotel_booking/complete_booking',
    }


def test_scenario_slug_drops_parametrization_tail_when_unique() -> None:
    rd = ReportData(
        metadata=_meta(), scenarios=[_scn('pkg/test_pour.py::test_pour[water]')]
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('pkg/test_pour.py::test_pour[water]')] == 'pour/pour'


def test_scenario_slug_keeps_tail_only_for_colliding_scenarios() -> None:
    # Two scenarios from the same parametrized function (narration varies per
    # case, so they don't merge) would share a slug — both keep their tails.
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('pkg/test_pour.py::test_pour[water]'),
            _scn('pkg/test_pour.py::test_pour[fire]'),
            _scn('pkg/test_pour.py::test_drain[once]'),  # unique base → no tail
        ],
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('pkg/test_pour.py::test_pour[water]')] == 'pour/pour[water]'
    assert index[NodeId('pkg/test_pour.py::test_pour[fire]')] == 'pour/pour[fire]'
    assert index[NodeId('pkg/test_pour.py::test_drain[once]')] == 'pour/drain'


def test_scenario_slug_file_without_test_prefix_kept_verbatim() -> None:
    rd = ReportData(metadata=_meta(), scenarios=[_scn('checks.py::test_run')])
    index = build_scenario_slug_index(rd)
    assert index[NodeId('checks.py::test_run')] == 'checks/run'


def test_scenario_slug_empty_report_is_empty() -> None:
    rd = ReportData(metadata=_meta())
    assert build_scenario_slug_index(rd) == {}


def test_scenario_slug_duplicate_basename_raises() -> None:
    rd = ReportData(
        metadata=_meta(),
        scenarios=[
            _scn('a/test_booking.py::test_make'),
            _scn('b/test_booking.py::test_make'),
        ],
    )
    with pytest.raises(ValueError, match='Duplicate scenario slug'):
        build_scenario_slug_index(rd)


@scenario(
    t'An under-anchored {pg["Activity"].low} is flagged ineligible in rollups',
    tags=['happy-path'],
)
def test_build_story_rollups_flags_under_anchored_activity_ineligible() -> None:
    with given(
        t'a {pg["Story"]} with an anchored and an under-anchored {pg["Activity"]}'
    ):
        g = _g()
        eligible = Activity(
            id=ActivityId(1),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        _verb_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        under_anchored = Activity(
            id=ActivityId(2),
            paths=(
                ActivityPath(
                    parts=(
                        _ent('guest', 'Guest'),
                        ActivityWord(text='browses'),
                        ActivityWord(text='listings'),
                    )
                ),
            ),
        )
        story = Story(
            id=StoryId('book'), title='Book', activities=(eligible, under_anchored)
        )
        rd = ReportData(metadata=_meta(), scenarios=[], stories=[story], glossary=g)
    with when('the story rollups are built'):
        rollups = build_story_rollups(rd, build_coverage_maps(rd))
    with then(t'only the anchored {pg["Activity"]} is {pg["Coverage"]}-eligible'):
        per_activity = rollups[StoryId('book')].per_activity
        assert per_activity[ActivityId(1)].eligible is True
        assert per_activity[ActivityId(2)].eligible is False


def _covering_scn(node_id: str, status: str) -> Scenario:
    """A scenario whose single step references guest/search/room, so it covers
    the guest-search-room activity used across the rollup-count tests."""
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=[
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('search'), display='search'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ],
        ),
    )
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
        story_id=StoryId('book'),
        status=status,
    )


def test_build_story_rollups_counts_passed_failed_and_skipped() -> None:
    g = _g()
    activity = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    _verb_part('search'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(activity,))
    scns = [
        _covering_scn('test::a', 'passed'),
        _covering_scn('test::b', 'passed'),
        _covering_scn('test::c', 'failed'),
        _covering_scn('test::d', 'skipped'),
    ]
    rd = ReportData(metadata=_meta(), scenarios=scns, stories=[story], glossary=g)
    rollups = build_story_rollups(rd, build_coverage_maps(rd))
    cov = rollups[StoryId('book')].per_activity[ActivityId(1)]
    assert cov.total == 4
    assert cov.passed == 2
    assert cov.failed == 1
    assert cov.skipped == 1
