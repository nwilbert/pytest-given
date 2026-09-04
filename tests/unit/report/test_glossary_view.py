"""Unit tests for the Glossary-view rollups (`report/glossary_view.py`)."""

from pytest_given import attach, given, scenario, then, when
from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
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
from pytest_given.report.glossary_view import build_term_crossrefs
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


def test_build_glossary_aggregations_empty_when_no_glossary() -> None:
    rd = ReportData(metadata=_meta())
    assert build_term_crossrefs(rd).aggregations == {}


@scenario(
    t'The {pg["Glossary"].low} view aggregates {pg["Instance"]("instances")} '
    t'and {pg["Verb"].low} forms',
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
                parts=(
                    NarrationTermRef(term_id=TermId('guest'), display='Alice'),
                    NarrationTermRef(term_id=TermId('search'), display='searches'),
                    NarrationTermRef(term_id=TermId('room'), display='Deluxe Suite'),
                ),
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
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the entity terms collect their {pg["Instance"]}s'):
        assert 'Alice' in [i.display for i in aggs[TermId('guest')].instances]
        assert 'Deluxe Suite' in [i.display for i in aggs[TermId('room')].instances]
    with then(t'the verb collects its {pg["Inflection"]} but not its canonical form'):
        forms = list(aggs[TermId('search')].forms)
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
            parts=(NarrationTermRef(term_id=TermId('missing'), display='X'),),
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_term_crossrefs(rd).aggregations
    # missing term has no aggregation entry.
    assert TermId('missing') not in aggs


def test_build_glossary_aggregations_walks_nested_steps() -> None:
    g = _g()
    inner = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=(NarrationTermRef(term_id=TermId('guest'), display='Alice'),),
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
    aggs = build_term_crossrefs(rd).aggregations
    assert 'Alice' in [i.display for i in aggs[TermId('guest')].instances]


@scenario(
    t'{pg["Term"]("Terms")} referenced by an {pg["Activity"].low} record '
    t'the {pg["Story"].low}',
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
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the actor and the verb each list that {pg["Story"]}'):
        assert aggs[TermId('guest')].stories == [StoryId('book')]
        assert aggs[TermId('search')].stories == [StoryId('book')]


@scenario(
    t'A {pg["Story"].low} referencing a {pg["Term"].low} twice lists it once',
)
def test_repeated_references_within_one_story_are_recorded_once() -> None:
    with given(
        t'a {pg["Story"]} whose two {pg["Activity"]("activities")} repeat the '
        t'same {pg["Term"]} and the same {pg["Inflection"]}'
    ):
        g = _g()
        parts = (
            _ent('guest', 'Guest'),
            ActivityTermRef(term_id=TermId('search'), display='searches for'),
            _ent('room', 'Room'),
        )
        story = Story(
            id=StoryId('book'),
            title='Book',
            activities=(
                Activity(id=ActivityId(1), paths=(ActivityPath(parts=parts),)),
                Activity(id=ActivityId(2), paths=(ActivityPath(parts=parts),)),
            ),
        )
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"]} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the {pg["Story"]} and the {pg["Inflection"]} appear once each'):
        assert aggs[TermId('guest')].stories == [StoryId('book')]
        assert list(aggs[TermId('search')].forms) == ['searches for']


def test_build_glossary_aggregations_verb_in_step_not_collected_as_instance() -> None:
    """A verb NarrationTermRef in a scenario step is skipped for instance
    collection (verbs have no instances, only forms from activity paths)."""
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=(NarrationTermRef(term_id=TermId('search'), display='searches'),),
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_term_crossrefs(rd).aggregations
    # Verb terms from scenario steps are not added to aggs as instances.
    assert TermId('search') not in aggs


@scenario(
    t'A canonical entity reference is not an {pg["Instance"].low}',
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
                parts=(NarrationTermRef(term_id=TermId('guest'), display='Guest'),),
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
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'neither entity term records an {pg["Instance"]}'):
        assert aggs[TermId('guest')].instances == []
        assert aggs[TermId('room')].instances == []


def test_build_glossary_aggregations_skips_non_term_ref_narration_parts() -> None:
    """NarrationLiteral / NarrationValue parts in a step are skipped."""
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='plain text step',
            parts=(NarrationLiteral(value='plain text step'),),
        ),
    )
    scn = Scenario(
        id=NodeId('t'),
        narration=Narration(text='s'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    aggs = build_term_crossrefs(rd).aggregations
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
    aggs = build_term_crossrefs(rd).aggregations
    assert TermId('unknown-term') not in aggs


@scenario(
    t'A {pg["Kindless"].low} {pg["Term"].low} records only its {pg["Story"].low} ref',
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
        aggs = build_term_crossrefs(rd).aggregations
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
                parts=(NarrationTermRef(term_id=TermId('guest'), display='Alice'),),
            ),
            fixture_name='alice',
        )
        body_step = Step(
            phase='when',
            narration=Narration(
                text='Alice does',
                parts=(NarrationTermRef(term_id=TermId('guest'), display='Alice'),),
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
        aggs = build_term_crossrefs(rd).aggregations
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
    assert build_term_crossrefs(rd).term_scenarios == {}


def test_build_term_scenario_index_maps_terms_to_scenarios() -> None:
    g = _g()
    step = Step(
        phase='when',
        narration=Narration(
            text='x',
            parts=(
                NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                NarrationTermRef(term_id=TermId('room'), display='Room'),
            ),
        ),
    )
    scn = Scenario(
        id=NodeId('test::a'),
        narration=Narration(text='scn'),
        module='m',
        steps=[step],
    )
    rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    index = build_term_crossrefs(rd).term_scenarios
    assert index[TermId('guest')] == [NodeId('test::a')]
    assert index[TermId('room')] == [NodeId('test::a')]
    assert TermId('search') not in index


@scenario(
    t'The {pg["Term"].low} index maps each {pg["Term"].low} to its '
    t'{pg["Scenario"]("scenarios")} once',
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
                parts=(NarrationTermRef(term_id=TermId('guest'), display='Guest'),),
            ),
        )
        step_two = Step(
            phase='then',
            narration=Narration(
                text='y',
                parts=(NarrationTermRef(term_id=TermId('guest'), display='Guest'),),
            ),
        )
        scn = Scenario(
            id=NodeId('test::a'),
            narration=Narration(
                text='scn',
                parts=(NarrationTermRef(term_id=TermId('room'), display='Room'),),
            ),
            module='m',
            steps=[step_one, step_two],
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], glossary=g)
    with when('the term-scenario index is built'):
        index = build_term_crossrefs(rd).term_scenarios
    with then(t'each {pg["Term"]} maps to the scenario exactly once'):
        assert index[TermId('guest')] == [NodeId('test::a')]  # dedup across steps
        assert index[TermId('room')] == [NodeId('test::a')]  # narration counts
