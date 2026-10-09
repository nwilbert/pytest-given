"""Unit tests for the Glossary-view rollups (`report/glossary_view.py`)."""

from pytest_given import attach, given, scenario, then, when
from pytest_given.model import (
    Clause,
    ClauseTermRef,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationTermRef,
    NodeId,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    Step,
    Story,
    StoryId,
    TermId,
    report_to_dict,
)
from pytest_given.report.glossary_view import build_glossary_view, build_term_crossrefs
from tests.ubiquitous_language import pg


def _ent(tid: str, display: str) -> ClauseTermRef:
    return ClauseTermRef(term_id=TermId(tid), display=display)


def _activity_part(tid: str) -> ClauseTermRef:
    return ClauseTermRef(term_id=TermId(tid), display=tid)


def _g() -> Glossary:
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g.register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    g.register(GlossaryTerm(id=TermId('search'), kind='activity', canonical='search'))
    return g


def _meta() -> Metadata:
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def test_build_glossary_aggregations_empty_when_no_glossary() -> None:
    rd = ReportData(metadata=_meta())
    assert build_term_crossrefs(rd).aggregations == {}


def test_kind_summaries_use_irregular_plurals() -> None:
    glossary = _g()
    glossary.register(
        GlossaryTerm(id=TermId('book'), kind='activity', canonical='book')
    )
    view = build_glossary_view(ReportData(metadata=_meta(), glossary=glossary))
    assert [kind.summary for kind in view.kinds] == [
        '1 actor',
        '1 work object',
        '2 activities',
    ]


@scenario(
    t'The {pg["Glossary"].l} view aggregates {pg["Instance"].l.s} '
    t'and {pg["Activity"].l} forms',
)
def test_build_glossary_aggregations_collects_instances_and_forms() -> None:
    with given(
        t'a {pg["Report"].l} whose {pg["Story"].l} and {pg["Scenario"].l} '
        t'reference '
        t'entity {pg["Instance"].l.s} and an {pg["Inflection"].l}'
    ):
        g = _g()
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Alice'),
                        ClauseTermRef(term_id=TermId('search'), display='searches for'),
                        _ent('room', 'Deluxe Suite'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(a,))
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
            story_ids=(StoryId('book'),),
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
        attach('Report data', report_to_dict(rd))
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the entity terms collect their {pg["Instance"].l.s}'):
        assert 'Alice' in [i.display for i in aggs[TermId('guest')].instances]
        assert 'Deluxe Suite' in [i.display for i in aggs[TermId('room')].instances]
    with then(
        t'the activity collects its {pg["Inflection"].l} but not its canonical form'
    ):
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
    t'{pg["Term"].s} referenced by a {pg["Sentence"].l} record the {pg["Story"].l}',
)
def test_build_glossary_aggregations_records_story_refs_via_sentences() -> None:
    with given(
        t'a {pg["Story"].l} whose {pg["Sentence"].l} references an actor and an '
        t'activity'
    ):
        g = _g()
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Guest'),
                        _activity_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(a,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the actor and the activity each list that {pg["Story"].l}'):
        assert aggs[TermId('guest')].stories == [StoryId('book')]
        assert aggs[TermId('search')].stories == [StoryId('book')]


@scenario(
    t'A {pg["Story"].l} referencing a {pg["Term"].l} twice lists it once',
)
def test_repeated_references_within_one_story_are_recorded_once() -> None:
    with given(
        t'a {pg["Story"].l} whose two {pg["Sentence"].l.s} repeat the '
        t'same {pg["Term"].l} and the same {pg["Inflection"].l}'
    ):
        g = _g()
        parts = (
            _ent('guest', 'Guest'),
            ClauseTermRef(term_id=TermId('search'), display='searches for'),
            _ent('room', 'Room'),
        )
        story = Story(
            id=StoryId('book'),
            title='Book',
            sentences=(
                Sentence(id=SentenceId(1), clauses=(Clause(parts=parts),)),
                Sentence(id=SentenceId(2), clauses=(Clause(parts=parts),)),
            ),
        )
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the {pg["Story"].l} and the {pg["Inflection"].l} appear once each'):
        assert aggs[TermId('guest')].stories == [StoryId('book')]
        assert list(aggs[TermId('search')].forms) == ['searches for']


def test_build_glossary_aggregations_activity_in_step_not_collected_as_instance() -> (
    None
):
    """An activity NarrationTermRef in a scenario step is skipped for instance
    collection (activities have no instances, only forms from clauses)."""
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
    # Activity terms from scenario steps are not added to aggs as instances.
    assert TermId('search') not in aggs


@scenario(
    t'A canonical entity reference is not an {pg["Instance"].l}, whatever its case',
)
def test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance() -> None:
    with given(
        t'a {pg["Story"].l} sentence referencing entities by canonical name, '
        t'and a {pg["Step"].l} referencing one in lowercase'
    ):
        g = _g()
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Guest'),
                        ClauseTermRef(term_id=TermId('search'), display='searches for'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(a,))
        step = Step(
            phase='when',
            narration=Narration(
                text='x',
                parts=(NarrationTermRef(term_id=TermId('guest'), display='guest'),),
            ),
        )
        scn = Scenario(
            id=NodeId('t'),
            narration=Narration(text='s'),
            module='m',
            steps=[step],
            story_ids=(StoryId('book'),),
        )
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'neither entity term records an {pg["Instance"].l}'):
        assert aggs[TermId('guest')].instances == []
        assert aggs[TermId('room')].instances == []


@scenario(
    t'An {pg["S-form"]} reference is the {pg["Term"].l} itself, '
    t'not an {pg["Instance"].l} or an {pg["Inflection"].l}',
)
def test_build_glossary_aggregations_s_form_ref_is_the_term_itself() -> None:
    with given(
        t'a {pg["Story"].l} {pg["Sentence"].l} referencing an entity and an '
        t'activity by their {pg["S-form"].l.s}, each lowercase and capitalized'
    ):
        clause = Clause(
            parts=(
                _ent('room', 'rooms'),
                _ent('search', 'searches'),
                _ent('room', 'Rooms'),
                _ent('search', 'Searches'),
            )
        )
        story = Story(
            id=StoryId('browse'),
            title='Browse',
            sentences=(Sentence(id=SentenceId(1), clauses=(clause,)),),
        )
        rd = ReportData(metadata=_meta(), stories=[story], glossary=_g())
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(
        t'the entity records no {pg["Instance"].l} '
        t'and the activity no {pg["Inflection"].l}'
    ):
        assert aggs[TermId('room')].instances == []
        assert aggs[TermId('search')].forms == []


def test_a_lowercase_s_form_of_an_all_caps_term_is_the_term_itself() -> None:
    glossary = Glossary()
    glossary.register(GlossaryTerm(id=TermId('sms'), kind='object', canonical='SMS'))
    clause = Clause(parts=(_ent('sms', 'smses'),))
    story = Story(
        id=StoryId('notify'),
        title='Notify',
        sentences=(Sentence(id=SentenceId(1), clauses=(clause,)),),
    )
    rd = ReportData(metadata=_meta(), stories=[story], glossary=glossary)
    assert build_term_crossrefs(rd).aggregations[TermId('sms')].instances == []


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


def test_build_glossary_aggregations_skips_unknown_term_ref_in_sentence() -> None:
    """An ClauseTermRef whose term_id isn't in the glossary is silently skipped."""
    g = _g()
    a = Sentence(
        id=SentenceId(1),
        clauses=(
            Clause(
                parts=(
                    ClauseTermRef(term_id=TermId('unknown-term'), display='Unknown'),
                )
            ),
        ),
    )
    story = Story(id=StoryId('s'), title='S', sentences=(a,))
    rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    aggs = build_term_crossrefs(rd).aggregations
    assert TermId('unknown-term') not in aggs


@scenario(
    t'A {pg["Kindless"].l} {pg["Term"].l} records only its {pg["Story"].l} ref',
)
def test_build_glossary_aggregations_kindless_term_records_only_story_ref() -> None:
    with given(
        t'a {pg["Kindless"].l} {pg["Term"].l} referenced by a {pg["Story"].l} sentence'
    ):
        g = _g()
        g.register(GlossaryTerm(id=TermId('widget'), kind=None, canonical='Widget'))
        kindless_part = ClauseTermRef(term_id=TermId('widget'), display='My Widget')
        a = Sentence(
            id=SentenceId(1),
            clauses=(Clause(parts=(kindless_part,)),),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(a,))
        rd = ReportData(metadata=_meta(), stories=[story], glossary=g)
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(
        t'the {pg["Term"].l} lists the {pg["Story"].l} but no {pg["Instance"].l} '
        t'and no {pg["Inflection"].l}'
    ):
        assert TermId('widget') in aggs, (
            'kindless term should still appear in aggregations'
        )
        widget_agg = aggs[TermId('widget')]
        assert widget_agg.stories == [StoryId('book')], 'story ref must be recorded'
        assert widget_agg.instances == [], (
            'kindless term must not produce an entity instance'
        )
        assert widget_agg.forms == [], 'kindless term must not produce an activity form'


@scenario(
    t'An {pg["Instance"].l} seen in a fixture {pg["Step"].l} '
    t'records its fixture provenance',
)
def test_glossary_aggregations_annotates_fixture_provenance() -> None:
    with given(
        t'a {pg["Scenario"].l} whose fixture-sourced {pg["Step"].l} names '
        t'an {pg["Instance"].l}'
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
            story_ids=(StoryId('book'),),
        )
        a = Sentence(
            id=SentenceId(1),
            clauses=(
                Clause(
                    parts=(
                        _ent('guest', 'Guest'),
                        _activity_part('search'),
                        _ent('room', 'Room'),
                    )
                ),
            ),
        )
        story = Story(id=StoryId('book'), title='Book', sentences=(a,))
        rd = ReportData(metadata=_meta(), scenarios=[scn], stories=[story], glossary=g)
    with when(t'the {pg["Glossary"].l} aggregations are built'):
        aggs = build_term_crossrefs(rd).aggregations
    with then(t'the {pg["Instance"].l} carries the fixture name'):
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
    t'The {pg["Term"].l} index maps each {pg["Term"].l} to its '
    t'{pg["Scenario"].l.s} once',
)
def test_build_term_scenario_index_dedups_and_includes_scenario_narration() -> None:
    with given(
        t'a {pg["Scenario"].l} referencing one {pg["Term"].l} in two steps '
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
    with then(t'each {pg["Term"].l} maps to the scenario exactly once'):
        assert index[TermId('guest')] == [NodeId('test::a')]  # dedup across steps
        assert index[TermId('room')] == [NodeId('test::a')]  # narration counts
