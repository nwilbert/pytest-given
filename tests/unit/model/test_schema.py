import dataclasses

import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPart,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Attachment,
    AttachmentRef,
    ErrorInfo,
    FixtureRecording,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    RecordingState,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    TracebackFrame,
)


def _n(text: str) -> Narration:
    return Narration(text=text)


def test_step_defaults() -> None:
    step = Step(phase='given', narration=_n('a coffee machine'))
    assert step.phase == 'given'
    assert step.narration.text == 'a coffee machine'
    assert step.narration.parts == []
    assert step.children == []
    assert step.attachments == []
    assert step.fixture_name is None


def test_step_fixture_name_is_set_when_provided() -> None:
    step = Step(phase='given', narration=_n('our guest'), fixture_name='alice')
    assert step.fixture_name == 'alice'


def test_step_with_children() -> None:
    child = Step(phase='when', narration=_n('validating coin'))
    parent = Step(phase='when', narration=_n('insert money'), children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].narration.text == 'validating coin'


def test_attachment() -> None:
    att = Attachment(label='Machine log', content='log line 1\nlog line 2')
    assert att.label == 'Machine log'
    assert att.content == 'log line 1\nlog line 2'


def test_error_info_with_frames_and_tail() -> None:
    err = ErrorInfo(
        message='assert 1 == 2',
        frames=[
            TracebackFrame(
                path='tests/test_x.py',
                lineno=10,
                func='test_x',
                code='    assert 1 == 2',
                is_internal=False,
            ),
        ],
        error_tail='E   assert 1 == 2',
    )
    assert err.message == 'assert 1 == 2'
    assert len(err.frames) == 1
    assert err.frames[0].is_internal is False
    assert err.error_tail == 'E   assert 1 == 2'


def test_error_info_defaults() -> None:
    err = ErrorInfo(message='assert False')
    assert err.frames == []
    assert err.error_tail is None


def test_scenario_defaults() -> None:
    s = Scenario(
        id='test_file.py::test_foo',
        narration=_n('Foo scenario'),
        module='test_file',
    )
    assert s.tags == []
    assert s.status == 'passed'
    assert s.duration_ms == 0
    assert s.steps == []
    assert s.parameters is None
    assert s.error is None


def test_parameter_table() -> None:
    case1 = ParameterCase(values=[1, 0], status='passed')
    case2 = ParameterCase(
        values=[2, 1], status='failed', error=ErrorInfo(message='fail')
    )
    table = ParameterTable(
        columns=[
            ParameterColumn(id='euros', name='euros', kind='param'),
            ParameterColumn(id='coffees', name='coffees', kind='param'),
        ],
        cases=[case1, case2],
    )
    assert [c.name for c in table.columns] == ['euros', 'coffees']
    assert len(table.cases) == 2
    assert table.cases[1].error is not None


def test_metadata() -> None:
    m = Metadata(
        project='coffee-shop',
        timestamp='2026-04-09T14:30:00Z',
        pytest_version='9.0',
        plugin_version='0.1.0',
    )
    assert m.project == 'coffee-shop'


def test_report_data() -> None:
    report = ReportData(
        metadata=Metadata(
            project='test',
            timestamp='now',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[],
    )
    assert report.scenarios == []


def test_recording_state_literals() -> None:
    # Type-check sanity: these are the four legal states
    states: list[RecordingState] = ['idle', 'test', 'fixture_setup', 'fixture_teardown']
    assert len(states) == 4


def test_fixture_recording_holds_root_step_and_stack() -> None:
    root = Step(phase='given', narration=_n('a shop'))
    recording = FixtureRecording(root=root)
    assert recording.root is root
    assert recording.stack == [root]


def test_step_narration_defaults_to_plain_text() -> None:
    step = Step(phase='given', narration=_n('hello'))
    assert step.narration.parts == []


def test_step_narration_accepts_parts() -> None:
    parts: list[NarrationPart] = [
        NarrationLiteral(value='Brew '),
        NarrationPlaceholder(name='cup_size', column_id='cup_size'),
        NarrationLiteral(value=' ml'),
    ]
    step = Step(phase='given', narration=Narration(text='Brew 200 ml', parts=parts))
    assert step.narration.parts == parts


def test_scenario_narration_defaults_to_plain_text() -> None:
    s = Scenario(id='id', narration=_n('hello'), module='m')
    assert s.narration.parts == []


def test_scenario_skip_reason_defaults_to_none() -> None:
    s = Scenario(id=NodeId('t::x'), narration=Narration(text='x'), module='m')
    assert s.skip_reason is None


def test_source_location_is_frozen() -> None:
    src = SourceLocation(relpath='tests/test_x.py', line=42)
    assert src.relpath == 'tests/test_x.py'
    assert src.line == 42
    with pytest.raises(dataclasses.FrozenInstanceError):
        src.line = 99  # type: ignore[misc]


def test_scenario_source_defaults_to_none() -> None:
    s = Scenario(
        id=NodeId('test.py::t'),
        narration=_n('n'),
        module='mod',
    )
    assert s.source is None


def test_story_source_defaults_to_none() -> None:
    s = Story(id=StoryId('checkout'), title='Checkout', activities=())
    assert s.source is None


def test_story_carries_source_location() -> None:
    src = SourceLocation(relpath='tests/conftest.py', line=12)
    s = Story(id=StoryId('checkout'), title='Checkout', activities=(), source=src)
    assert s.source == src


def test_glossary_term_source_defaults_to_none() -> None:
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    assert t.source is None


def test_glossary_term_carries_source_location() -> None:
    src = SourceLocation(relpath='tests/conftest.py', line=4)
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest', source=src)
    assert t.source == src


def test_metadata_commit_sha_defaults_to_none() -> None:
    m = Metadata(project='p', timestamp='t', pytest_version='9', plugin_version='0.1')
    assert m.commit_sha is None


# --- Task 1.1: Id aliases + GlossaryTerm ---


def test_glossary_term_is_frozen_and_kw_only() -> None:
    term = GlossaryTerm(
        id=TermId('guest'),
        kind='actor',
        canonical='Guest',
        definition='Person booking accommodation.',
    )
    assert term.id == 'guest'
    assert term.kind == 'actor'
    assert term.canonical == 'Guest'
    assert term.definition == 'Person booking accommodation.'
    with pytest.raises(dataclasses.FrozenInstanceError):
        term.kind = 'verb'  # type: ignore[misc]


def test_glossary_term_definition_defaults_none() -> None:
    term = GlossaryTerm(id=TermId('x'), kind='verb', canonical='x')
    assert term.definition is None


# --- Task 1.2: Activity-part variants + ActivityPart union ---


def test_activity_term_ref_carries_term_id_and_display() -> None:
    part = ActivityTermRef(term_id=TermId('guest'), display='Alice')
    assert part.term_id == 'guest'
    assert part.display == 'Alice'


def test_activity_word_carries_text() -> None:
    part = ActivityWord(text='for')
    assert part.text == 'for'


def test_activity_parts_are_frozen() -> None:
    part = ActivityWord(text='for')
    with pytest.raises(dataclasses.FrozenInstanceError):
        part.text = 'and'  # type: ignore[misc]


def test_activity_part_union_accepts_all_variants() -> None:
    parts: list[ActivityPart] = [
        ActivityTermRef(term_id=TermId('g'), display='Guest'),
        ActivityTermRef(term_id=TermId('s'), display='searches'),
        ActivityWord(text='for'),
    ]
    assert [type(p).__name__ for p in parts] == [
        'ActivityTermRef',
        'ActivityTermRef',
        'ActivityWord',
    ]


# --- Task 1.3: ActivityPath, Activity, Story with _by_id index ---


def test_activity_path_is_frozen_with_parts_tuple() -> None:
    path = ActivityPath(
        parts=(
            ActivityTermRef(term_id=TermId('guest'), display='Guest'),
            ActivityTermRef(term_id=TermId('search'), display='searches for'),
            ActivityTermRef(term_id=TermId('room'), display='Room'),
        )
    )
    assert len(path.parts) == 3


def test_activity_holds_id_and_paths() -> None:
    p = ActivityPath(
        parts=(
            ActivityTermRef(term_id=TermId('g'), display='G'),
            ActivityTermRef(term_id=TermId('s'), display='s'),
            ActivityTermRef(term_id=TermId('o'), display='O'),
        )
    )
    act = Activity(id=ActivityId(1), paths=(p,))
    assert act.id == 1
    assert act.paths == (p,)


def test_story_indexes_activities_by_id() -> None:
    p = ActivityPath(
        parts=(
            ActivityTermRef(term_id=TermId('g'), display='G'),
            ActivityTermRef(term_id=TermId('s'), display='s'),
            ActivityTermRef(term_id=TermId('o'), display='O'),
        )
    )
    a1 = Activity(id=ActivityId(1), paths=(p,))
    a2 = Activity(id=ActivityId(2), paths=(p,))
    story = Story(id=StoryId('book'), title='Book', activities=(a1, a2))
    assert story[ActivityId(1)] is a1
    assert story[ActivityId(2)] is a2
    assert story.get(ActivityId(99)) is None


def test_story_index_excluded_from_repr_and_equality() -> None:
    p = ActivityPath(
        parts=(
            ActivityTermRef(term_id=TermId('g'), display='G'),
            ActivityTermRef(term_id=TermId('s'), display='s'),
            ActivityTermRef(term_id=TermId('o'), display='O'),
        )
    )
    a = Activity(id=ActivityId(1), paths=(p,))
    s1 = Story(id=StoryId('x'), title='X', activities=(a,))
    s2 = Story(id=StoryId('x'), title='X', activities=(a,))
    assert s1 == s2
    assert '_by_id' not in repr(s1)


# --- Task 1.4: Glossary container with atomic write-through ---


def test_glossary_register_appends_and_indexes() -> None:
    g = Glossary()
    t = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    g._register(t)
    assert g.terms == [t]
    assert g.get(TermId('guest')) is t
    assert g.get(TermId('missing')) is None


def test_glossary_register_rejects_id_collision() -> None:
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    with pytest.raises(ValueError, match='already registered'):
        g._register(GlossaryTerm(id=TermId('x'), kind='verb', canonical='X'))


def test_glossary_index_excluded_from_repr_and_equality() -> None:
    g1 = Glossary()
    g1._register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    g2 = Glossary()
    g2._register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    assert g1 == g2
    assert '_by_id' not in repr(g1)


def test_glossary_post_init_indexes_terms_passed_at_construction() -> None:
    t1 = GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest')
    t2 = GlossaryTerm(id=TermId('room'), kind='object', canonical='Room')
    g = Glossary(terms=[t1, t2])
    assert g.get(TermId('guest')) is t1
    assert g.get(TermId('room')) is t2


# --- Task 1.5: NarrationTermRef + extended NarrationPart union ---


def test_narration_term_ref_carries_term_id_display_and_optional_param_column() -> None:
    part = NarrationTermRef(term_id=TermId('guest'), display='Alice')
    assert part.term_id == 'guest'
    assert part.display == 'Alice'
    assert part.param_column is None

    part2 = NarrationTermRef(
        term_id=TermId('guest'), display='Alice', param_column='guest_name'
    )
    assert part2.param_column == 'guest_name'


def test_narration_term_ref_is_assignable_to_narration_part() -> None:
    part: NarrationPart = NarrationTermRef(term_id=TermId('guest'), display='Alice')
    assert isinstance(part, NarrationTermRef)


# --- Task 1.6: Extend ReportData, Scenario, Step with new fields ---


def _meta() -> Metadata:
    return Metadata(
        project='proj',
        timestamp='now',
        pytest_version='8',
        plugin_version='0.1.0',
    )


def test_report_data_defaults_glossary_none_and_stories_empty() -> None:
    rd = ReportData(metadata=_meta())
    assert rd.glossary is None
    assert rd.stories == []


def test_report_data_accepts_glossary_and_stories() -> None:
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('x'), kind='actor', canonical='X'))
    rd = ReportData(metadata=_meta(), glossary=g, stories=[])
    assert rd.glossary is g


def test_scenario_defaults_story_id_none_and_activity_ids_empty() -> None:
    s = Scenario(id=NodeId('n'), narration=Narration(text='t'), module='m')
    assert s.story_id is None
    assert s.activity_ids == ()


def test_scenario_accepts_story_id_and_activity_ids() -> None:
    s = Scenario(
        id=NodeId('n'),
        narration=Narration(text='t'),
        module='m',
        story_id=StoryId('book'),
        activity_ids=(ActivityId(1), ActivityId(2)),
    )
    assert s.story_id == 'book'
    assert s.activity_ids == (1, 2)


def test_step_defaults_activity_ids_empty() -> None:
    step = Step(phase='given', narration=Narration(text='t'))
    assert step.activity_ids == ()


def test_step_accepts_activity_ids() -> None:
    step = Step(
        phase='given',
        narration=Narration(text='t'),
        activity_ids=(ActivityId(3),),
    )
    assert step.activity_ids == (3,)


def test_parameter_table_carries_typed_columns() -> None:
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='derived:0', name='price', kind='derived'),
            ParameterColumn(id='attachment:0', name='machine state', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                values=[
                    200,
                    '2.0',
                    Attachment(
                        label='machine state', content='{}', content_type='json'
                    ),
                ],
                status='passed',
            )
        ],
    )
    assert [c.kind for c in table.columns] == ['param', 'derived', 'attachment']
    assert len(table.cases[0].values) == len(table.columns)


def test_attachment_ref_has_no_content_field() -> None:
    ref = AttachmentRef(
        label='machine state', content_type='json', column_id='attachment:0'
    )
    assert not hasattr(ref, 'content')
    assert ref.column_id == 'attachment:0'
