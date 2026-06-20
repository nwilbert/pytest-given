import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
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
)
from pytest_given.report.aggregations import (
    build_coverage_maps,
    build_glossary_aggregations,
    build_scenario_slug_index,
    build_term_scenario_index,
    tab_visibility,
)


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


def test_build_glossary_aggregations_collects_instances_and_forms() -> None:
    g = _g()
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Alice'),
                    ActivityTermRef(term_id=TermId('search'), display='searches for'),
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
    aggs = build_glossary_aggregations(rd)
    guest_agg = aggs[TermId('guest')]
    assert 'Alice' in [i.display for i in guest_agg.instances]
    room_agg = aggs[TermId('room')]
    assert 'Deluxe Suite' in [i.display for i in room_agg.instances]
    search_agg = aggs[TermId('search')]
    forms = [f.display for f in search_agg.forms]
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


def test_build_glossary_aggregations_records_story_refs_via_activities() -> None:
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
    aggs = build_glossary_aggregations(rd)
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


def test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance() -> None:
    """A canonical-name entity reference (display == term.canonical) names the
    canonical concept, not a distinct instance — it must not appear in the
    Glossary view's Instances list, whether seen in a scenario step narration
    or in a story activity path."""
    g = _g()
    # Story activity uses bare canonical Guest + canonical Room.
    a = Activity(
        id=ActivityId(1),
        paths=(
            ActivityPath(
                parts=(
                    _ent('guest', 'Guest'),
                    ActivityTermRef(term_id=TermId('search'), display='searches for'),
                    _ent('room', 'Room'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(a,))
    # Scenario narration also references the canonical Guest.
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
    aggs = build_glossary_aggregations(rd)
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


def test_build_glossary_aggregations_kindless_term_records_only_story_ref() -> None:
    """A glossary term with kind=None in a story activity records the story ref
    but does NOT produce an entity instance observation or a verb form entry."""
    g = _g()
    g._register(GlossaryTerm(id=TermId('widget'), kind=None, canonical='Widget'))
    kindless_part = ActivityTermRef(term_id=TermId('widget'), display='My Widget')
    a = Activity(
        id=ActivityId(1),
        paths=(ActivityPath(parts=(kindless_part,)),),
    )
    story = Story(id=StoryId('book'), title='Book', activities=(a,))
    rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    aggs = build_glossary_aggregations(rd)
    assert TermId('widget') in aggs, 'kindless term should still appear in aggregations'
    widget_agg = aggs[TermId('widget')]
    assert widget_agg.stories == [StoryId('book')], 'story ref must be recorded'
    assert widget_agg.instances == [], (
        'kindless term must not produce an entity instance'
    )
    assert widget_agg.forms == [], 'kindless term must not produce a verb form'


def test_glossary_aggregations_annotates_fixture_provenance() -> None:
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
    aggs = build_glossary_aggregations(rd)
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


def test_build_term_scenario_index_dedups_and_includes_scenario_narration() -> None:
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
    index = build_term_scenario_index(rd)
    assert index[TermId('guest')] == [NodeId('test::a')]  # dedup across steps
    assert index[TermId('room')] == [NodeId('test::a')]  # scenario narration counts


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


def test_scenario_slug_keeps_parametrization_tail() -> None:
    rd = ReportData(
        metadata=_meta(), scenarios=[_scn('pkg/test_pour.py::test_pour[water]')]
    )
    index = build_scenario_slug_index(rd)
    assert index[NodeId('pkg/test_pour.py::test_pour[water]')] == 'pour/pour[water]'


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
