import pytest

from pytest_given import attach, given, scenario, then, when_then
from pytest_given.model import (
    REPORT_SCHEMA_VERSION,
    Attachment,
    AttachmentRef,
    CapturedStep,
    Clause,
    Definition,
    ErrorInfo,
    Glossary,
    GlossaryTerm,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    Pin,
    PytestGivenError,
    ReportData,
    Scenario,
    Sentence,
    SentenceId,
    SentenceName,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    report_from_dict,
    report_to_dict,
)
from tests.ubiquitous_language import pg
from tests.unit.model.builders import every_field_populated


def _round_trip(report):
    return report_from_dict(report_to_dict(report))


def _meta():
    return Metadata(project='p', timestamp='t', pytest_version='8', plugin_version='0')


def _restored(scenario: Scenario) -> Scenario:
    return _round_trip(ReportData(metadata=_meta(), scenarios=[scenario])).scenarios[0]


def _dummy_metadata() -> Metadata:
    return Metadata(
        project='p',
        timestamp='2026-06-18T00:00:00+00:00',
        pytest_version='8.0',
        plugin_version='0.1.0',
        commit_sha=None,
    )


def test_clause_term_ref_round_trips():
    story = Story(
        id=StoryId('s'),
        title='S',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(
                    Clause(
                        parts=(
                            NarrationTermRef(term_id=TermId('guest'), display='Guest'),
                        )
                    ),
                ),
            ),
        ),
    )
    report = ReportData(
        metadata=_dummy_metadata(), scenarios=[], stories=[story], glossary=None
    )
    round_tripped = report_from_dict(report_to_dict(report))
    part = round_tripped.stories[0].sentences[0].clauses[0].parts[0]
    assert part == NarrationTermRef(term_id=TermId('guest'), display='Guest')


def test_glossary_term_kind_can_be_none():
    glossary = Glossary(
        terms=[GlossaryTerm(id=TermId('guest'), kind=None, canonical='Guest')]
    )
    report = ReportData(
        metadata=_dummy_metadata(), scenarios=[], stories=[], glossary=glossary
    )
    round_tripped = report_from_dict(report_to_dict(report))
    assert round_tripped.glossary is not None
    assert round_tripped.glossary.terms[0].kind is None


def _minimal_metadata_dict() -> dict:
    return {
        'project': 'p',
        'timestamp': 't',
        'pytest_version': '9',
        'plugin_version': '0.1',
        'schema_version': REPORT_SCHEMA_VERSION,
    }


def test_empty_report() -> None:
    report = report_from_dict({'metadata': _minimal_metadata_dict(), 'scenarios': []})
    assert report.metadata.project == 'p'
    assert report.metadata.commit_sha is None
    assert report.scenarios == []


def test_metadata_commit_sha_optional() -> None:
    md = _minimal_metadata_dict() | {'commit_sha': 'abc'}
    report = report_from_dict({'metadata': md, 'scenarios': []})
    assert report.metadata.commit_sha == 'abc'


def test_scenario_with_source_and_no_steps() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'tests/t.py::test_x',
                    'narration': {'text': 'S', 'parts': []},
                    'module': 'm',
                    'tags': ['smoke'],
                    'status': 'passed',
                    'duration_ms': 5,
                    'steps': [],
                    'parameters': None,
                    'error': None,
                    'reason': None,
                    'source': {'relpath': 'tests/t.py', 'line': 7},
                }
            ],
        }
    )
    s = report.scenarios[0]
    assert s.id == NodeId('tests/t.py::test_x')
    assert s.narration.text == 'S'
    assert s.tags == ['smoke']
    assert s.duration_ms == 5
    assert s.source == SourceLocation(relpath='tests/t.py', line=7)
    assert s.parameters is None
    assert s.skip_reason is None


def test_an_xfailed_scenario_round_trips_with_its_reason() -> None:
    restored = _restored(
        Scenario(
            id=NodeId('t.py::test_x'),
            narration=Narration(text='x'),
            module='t',
            status='xfailed',
            reason='not implemented yet',
        )
    )
    assert restored.status == 'xfailed'
    assert restored.xfail_reason == 'not implemented yet'


def test_scenario_source_optional_defaults_to_none() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {'text': 'n', 'parts': []},
                    'module': 'm',
                    'tags': [],
                    'status': 'passed',
                    'duration_ms': 0,
                    'steps': [],
                    'parameters': None,
                    'error': None,
                }
            ],
        }
    )
    assert report.scenarios[0].source is None


def test_a_report_of_captured_steps_leaves_their_sources_out() -> None:
    step = CapturedStep(
        phase='given',
        narration=Narration(text='g'),
        children=[
            CapturedStep(
                phase='then',
                narration=Narration(text='t'),
                source=SourceLocation(relpath='tests/t.py', line=4),
            )
        ],
        source=SourceLocation(relpath='tests/t.py', line=3),
    )
    scenario = Scenario(
        id=NodeId('i'), narration=Narration(text='n'), module='m', steps=[step]
    )
    step_dict = report_to_dict(ReportData(metadata=_meta(), scenarios=[scenario]))[
        'scenarios'
    ][0]['steps'][0]
    assert 'source' not in step_dict
    assert 'source' not in step_dict['children'][0]


def test_a_step_with_a_status_is_refused() -> None:
    payload = report_to_dict(every_field_populated())
    payload['scenarios'][0]['steps'][0]['status'] = 'failed'
    with pytest.raises(
        PytestGivenError,
        match=r'scenarios\.0\.steps\.0\.status: Unexpected keyword argument',
    ):
        report_from_dict(payload)


def test_parameter_table_round_trips() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {'text': 'n', 'parts': []},
                    'module': 'm',
                    'tags': [],
                    'status': 'passed',
                    'duration_ms': 0,
                    'steps': [],
                    'error': None,
                    'parameters': {
                        'columns': [
                            {'id': 'euros', 'name': 'euros', 'kind': 'param'},
                            {'id': 'expect', 'name': 'expect', 'kind': 'param'},
                        ],
                        'cases': [
                            {
                                'id': 't.py::test_x[1]',
                                'values': [1, False],
                                'custom_id': False,
                                'status': 'passed',
                                'error': None,
                            },
                            {
                                'id': 't.py::test_x[2]',
                                'values': [2, True],
                                'custom_id': False,
                                'status': 'failed',
                                'error': {
                                    'message': 'boom',
                                    'frames': [],
                                    'error_tail': None,
                                },
                            },
                        ],
                    },
                }
            ],
        }
    )
    pt = report.scenarios[0].parameters
    assert isinstance(pt, ParameterTable)
    assert [c.name for c in pt.columns] == ['euros', 'expect']
    assert pt.cases == [
        ParameterCase(
            id=NodeId('t.py::test_x[1]'), values=[1, False], status='passed', error=None
        ),
        ParameterCase(
            id=NodeId('t.py::test_x[2]'),
            values=[2, True],
            status='failed',
            error=ErrorInfo(message='boom'),
        ),
    ]


def test_error_info_with_frames_round_trips() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {'text': 'n', 'parts': []},
                    'module': 'm',
                    'tags': [],
                    'status': 'failed',
                    'duration_ms': 0,
                    'steps': [],
                    'parameters': None,
                    'error': {
                        'message': 'boom',
                        'frames': [
                            {
                                'path': 'tests/t.py',
                                'lineno': 5,
                                'func': 'test_x',
                                'code': '    assert False',
                                'is_internal': False,
                            },
                            {
                                'path': '.venv/lib/site-packages/_pytest/runner.py',
                                'lineno': 200,
                                'func': 'runtest',
                                'code': '    item.runtest()',
                                'is_internal': True,
                            },
                        ],
                        'error_tail': 'E   assert False',
                    },
                }
            ],
        }
    )
    err = report.scenarios[0].error
    assert err is not None
    assert len(err.frames) == 2
    assert err.frames[0].path == 'tests/t.py'
    assert err.frames[0].func == 'test_x'
    assert err.frames[0].is_internal is False
    assert err.frames[1].is_internal is True
    assert err.error_tail == 'E   assert False'

    roundtripped = report_to_dict(report)
    err_dict = roundtripped['scenarios'][0]['error']
    assert err_dict['frames'][0]['path'] == 'tests/t.py'
    assert err_dict['frames'][1]['is_internal'] is True
    assert err_dict['error_tail'] == 'E   assert False'


def test_narration_literal_part() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {
                        'text': 'S',
                        'parts': [{'value': 'hello'}],
                    },
                    'module': 'm',
                    'tags': [],
                    'status': 'passed',
                    'duration_ms': 0,
                    'steps': [],
                    'parameters': None,
                    'error': None,
                }
            ],
        }
    )
    parts = report.scenarios[0].narration.parts
    assert parts == (NarrationLiteral(value='hello'),)


def test_narration_value_part() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {
                        'text': 'S',
                        'parts': [
                            {
                                'rendered': '12.0',
                                'expression': 'price * 1.2',
                                'format_spec': '',
                                'conversion': None,
                            }
                        ],
                    },
                    'module': 'm',
                    'tags': [],
                    'status': 'passed',
                    'duration_ms': 0,
                    'steps': [],
                    'parameters': None,
                    'error': None,
                }
            ],
        }
    )
    parts = report.scenarios[0].narration.parts
    assert parts == (
        NarrationValue(
            rendered='12.0',
            expression='price * 1.2',
            format_spec='',
            conversion=None,
        ),
    )


def test_narration_placeholder_part() -> None:
    report = report_from_dict(
        {
            'metadata': _minimal_metadata_dict(),
            'scenarios': [
                {
                    'id': 'i',
                    'narration': {
                        'text': 'S',
                        'parts': [
                            {
                                'name': 'euros',
                                'column_id': 'euros',
                                'format_spec': '03d',
                                'conversion': 'r',
                            }
                        ],
                    },
                    'module': 'm',
                    'tags': [],
                    'status': 'passed',
                    'duration_ms': 0,
                    'steps': [],
                    'parameters': None,
                    'error': None,
                }
            ],
        }
    )
    parts = report.scenarios[0].narration.parts
    assert parts == (
        NarrationPlaceholder(
            name='euros', column_id='euros', format_spec='03d', conversion='r'
        ),
    )


def test_a_narration_part_of_no_known_shape_is_refused_at_its_path() -> None:
    payload = report_to_dict(every_field_populated())
    payload['scenarios'][0]['narration']['parts'] = [{'mystery_field': '?'}]
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(payload)
    assert (
        'scenarios.0.narration.parts.0.NarrationLiteral.value: Field required'
        in str(raised.value)
    )


def test_round_trip_via_to_dict() -> None:
    """`report_to_dict` then `report_from_dict` is a no-op."""
    original = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
            commit_sha='deadbeef',
        ),
        scenarios=[
            Scenario(
                id=NodeId('i'),
                narration=Narration(
                    text='S',
                    parts=(
                        NarrationLiteral(value='Brew '),
                        NarrationPlaceholder(
                            name='cup', column_id='cup', format_spec='', conversion=None
                        ),
                    ),
                ),
                module='m',
                tags=['t'],
                status='passed',
                duration_ms=12,
                steps=[
                    Step(
                        phase='given',
                        narration=Narration(text='a thing'),
                        attachments=[Attachment(label='l', content='c')],
                    )
                ],
                source=SourceLocation(relpath='tests/t.py', line=3),
            )
        ],
    )
    deserialized = report_from_dict(report_to_dict(original))
    assert deserialized == original


@pytest.mark.parametrize(
    ('mutate', 'expected'),
    [
        (
            lambda d: d['scenarios'][0].update(status='errored'),
            (
                "scenarios.0.status: Input should be 'passed', 'failed', 'skipped' "
                "or 'xfailed'"
            ),
        ),
        (
            lambda d: d['glossary']['terms'][0].update(kind='thing'),
            "glossary.terms.0.kind: Input should be 'actor', 'object' or 'activity'",
        ),
        (
            lambda d: d['scenarios'][0]['steps'][0].update(phase='so'),
            "scenarios.0.steps.0.phase: Input should be 'given', 'when' or 'then'",
        ),
        (
            lambda d: d['scenarios'][0]['steps'][0]['attachments'][0].update(
                content_type='yaml'
            ),
            (
                'scenarios.0.steps.0.attachments.0.Attachment.content_type: Input '
                "should be 'text' or 'json'"
            ),
        ),
    ],
)
def test_report_from_dict_rejects_an_out_of_range_literal(mutate, expected) -> None:
    payload = report_to_dict(every_field_populated())
    mutate(payload)
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(payload)
    assert expected in str(raised.value)


def test_a_hand_edited_string_bool_reads_by_its_meaning() -> None:
    table = ParameterTable(
        columns=[ParameterColumn(id='a', name='a', kind='param')],
        cases=[ParameterCase(id=NodeId('t.py::t[1]'), values=[1], custom_id=True)],
    )
    scenario = Scenario(
        id=NodeId('t.py::t'),
        narration=Narration(text='x'),
        module='m',
        parameters=table,
    )
    payload = report_to_dict(ReportData(metadata=_meta(), scenarios=[scenario]))
    payload['scenarios'][0]['parameters']['cases'][0]['custom_id'] = 'false'
    parameters = report_from_dict(payload).scenarios[0].parameters
    assert parameters is not None
    assert parameters.cases[0].custom_id is False


def test_clause_part_variants_round_trip():
    parts = (
        NarrationTermRef(term_id=TermId('guest'), display='Guest'),
        NarrationTermRef(term_id=TermId('search'), display='searches'),
        NarrationLiteral(value='for'),
    )
    path = Clause(parts=parts)
    sentence = Sentence(id=SentenceId(1), clauses=(path,))
    story = Story(id=StoryId('s'), title='S', sentences=(sentence,))
    report = ReportData(metadata=_meta(), stories=[story])
    rt = _round_trip(report)
    rt_parts = rt.stories[0].sentences[0].clauses[0].parts
    assert rt_parts == parts


def test_glossary_round_trips_and_rebuilds_index():
    g = Glossary()
    g.register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g.register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    report = ReportData(metadata=_meta(), glossary=g)
    rt = _round_trip(report)
    assert rt.glossary is not None
    assert rt.glossary.get(TermId('guest')).canonical == 'Guest'
    assert rt.glossary.get(TermId('room')).kind == 'object'


def test_narration_term_ref_round_trips():
    narration = Narration(
        text='Alice arrives',
        parts=(
            NarrationLiteral(value='Hello '),
            NarrationTermRef(
                term_id=TermId('guest'),
                display='Alice',
                expression='guest',
            ),
        ),
    )
    scn = Scenario(id=NodeId('n'), narration=narration, module='m')
    report = ReportData(metadata=_meta(), scenarios=[scn])
    rt = _round_trip(report)
    assert rt.scenarios[0].narration.parts == narration.parts


def test_report_data_with_no_glossary_or_stories_round_trips():
    report = ReportData(metadata=_meta())
    rt = _round_trip(report)
    assert rt.glossary is None
    assert rt.stories == []


def test_scenario_story_ids_and_pins_round_trip():
    pins = (
        Pin(story_id=StoryId('book'), sentence_id=SentenceId(1)),
        Pin(story_id=StoryId('book'), sentence_id=SentenceId(2)),
    )
    scn = Scenario(
        id=NodeId('n'),
        narration=Narration(text='x'),
        module='m',
        story_ids=(StoryId('book'),),
        pins=pins,
    )
    report = ReportData(metadata=_meta(), scenarios=[scn])
    rt = _round_trip(report)
    assert rt.scenarios[0].story_ids == (StoryId('book'),)
    assert rt.scenarios[0].pins == pins


def test_not_pinned_and_pinned_to_nothing_round_trip_apart():
    """`null` is "not pinned" and `[]` opts out of narration matching, so the
    two must survive a report replayed through `pytest-given report`."""
    steps = [
        Step(phase='given', narration=Narration(text='unpinned')),
        Step(phase='given', narration=Narration(text='opted out'), pins=()),
    ]
    scn = Scenario(
        id=NodeId('n'), narration=Narration(text='x'), module='m', steps=steps, pins=()
    )
    data = report_to_dict(ReportData(metadata=_meta(), scenarios=[scn]))
    assert [step['pins'] for step in data['scenarios'][0]['steps']] == [None, []]
    replayed = report_from_dict(data).scenarios[0]
    assert replayed.pins == ()
    assert [step.pins for step in replayed.steps] == [None, ()]


def test_sentence_name_round_trips_and_defaults_to_none():
    named = Sentence(id=SentenceId(1), clauses=(), name=SentenceName('cancel'))
    unnamed = Sentence(id=SentenceId(2), clauses=())
    story = Story(id=StoryId('book'), title='Book', sentences=(named, unnamed))
    report = ReportData(metadata=_meta(), stories=[story])
    data = report_to_dict(report)
    assert [one['name'] for one in data['stories'][0]['sentences']] == ['cancel', None]
    del data['stories'][0]['sentences'][1]['name']
    rt = report_from_dict(data)
    assert [one.name for one in rt.stories[0].sentences] == ['cancel', None]


def test_step_pins_round_trip():
    pins = (Pin(story_id=StoryId('book'), sentence_id=SentenceId(7)),)
    scn = Scenario(
        id=NodeId('n'),
        narration=Narration(text='x'),
        module='m',
        steps=[
            Step(
                phase='given',
                narration=Narration(text='s'),
                pins=pins,
            )
        ],
    )
    report = ReportData(metadata=_meta(), scenarios=[scn])
    rt = _round_trip(report)
    assert rt.scenarios[0].steps[0].pins == pins


def test_a_clause_part_of_no_known_shape_is_refused_at_its_path():
    payload = report_to_dict(every_field_populated())
    payload['stories'][0]['sentences'][0]['clauses'][0]['parts'] = [{'unknown': 'x'}]
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(payload)
    assert (
        'stories.0.sentences.0.clauses.0.parts.0.NarrationLiteral.value: Field required'
        in str(raised.value)
    )


def test_a_clause_is_written_in_narration_parts():
    payload = report_to_dict(every_field_populated())
    parts = payload['stories'][0]['sentences'][0]['clauses'][0]['parts']
    assert parts == [
        {'term_id': 'guest', 'display': 'Guest', 'expression': ''},
        {'value': 'books'},
        {'term_id': 'room', 'display': 'Room', 'expression': ''},
    ]


def test_story_source_roundtrips() -> None:
    story = Story(
        id=StoryId('checkout'),
        title='Checkout',
        sentences=(
            Sentence(
                id=SentenceId(1),
                clauses=(Clause(parts=(NarrationLiteral(value='x'),)),),
            ),
        ),
        source=SourceLocation(relpath='conftest.py', line=4),
    )
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
        ),
        stories=[story],
    )
    round_tripped = report_from_dict(report_to_dict(report))
    assert round_tripped.stories[0].source == story.source


def test_none_definition_round_trips():
    term = GlossaryTerm(
        id=TermId('guest'), kind='actor', canonical='Guest', definition=None
    )
    report = ReportData(metadata=_meta(), glossary=Glossary(terms=[term]))
    restored = report_from_dict(report_to_dict(report))
    assert restored.glossary is not None
    assert restored.glossary.terms[0].definition is None


def test_a_definition_with_ref_parts_round_trips():
    definition = Definition(
        'Reserve a **Room**.',
        (
            NarrationLiteral(value='Reserve a '),
            NarrationTermRef(term_id=TermId('room'), display='Room'),
            NarrationLiteral(value='.'),
        ),
    )
    term = GlossaryTerm(
        id=TermId('book'), kind='activity', canonical='book', definition=definition
    )
    report = ReportData(metadata=_meta(), glossary=Glossary(terms=[term]))
    as_dict = report_to_dict(report)
    assert as_dict['glossary']['terms'][0]['definition']['parts'][1] == {  # type: ignore[call-overload, index]
        'term_id': 'room',
        'display': 'Room',
        'expression': '',
    }
    restored = report_from_dict(as_dict)
    assert restored.glossary is not None
    assert restored.glossary.terms[0].definition == definition


def test_a_value_part_in_a_definition_is_refused():
    as_dict = report_to_dict(ReportData(metadata=_meta(), glossary=Glossary()))
    as_dict['glossary'] = {
        'terms': [
            {
                'id': 'book',
                'kind': None,
                'canonical': 'book',
                'definition': {
                    'text': 'x',
                    'parts': [{'rendered': 'x', 'expression': 'x'}],
                },
            }
        ]
    }
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(as_dict)
    assert (
        'glossary.terms.0.definition.parts.0.NarrationLiteral.value: Field required'
        in str(raised.value)
    )


def test_a_definition_whose_parts_do_not_spell_its_text_is_refused_at_its_path():
    payload = report_to_dict(every_field_populated())
    payload['glossary']['terms'][0]['definition'] = {
        'text': 'ab',
        'parts': [{'value': 'a'}],
    }
    with pytest.raises(
        PytestGivenError, match=r'glossary\.terms\.0\.definition: Assertion failed'
    ):
        report_from_dict(payload)


def test_glossary_term_source_roundtrips() -> None:
    g = Glossary(
        terms=[
            GlossaryTerm(
                id=TermId('guest'),
                kind='actor',
                canonical='Guest',
                source=SourceLocation(relpath='conftest.py', line=8),
            ),
        ],
    )
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
        ),
        glossary=g,
    )
    round_tripped = report_from_dict(report_to_dict(report))
    assert round_tripped.glossary is not None
    assert round_tripped.glossary.terms[0].source == g.terms[0].source


def test_round_trip_preserves_column_kinds_and_cell_shapes() -> None:
    table = ParameterTable(
        columns=[
            ParameterColumn(id='cup_size', name='cup_size', kind='param'),
            ParameterColumn(id='derived:0', name='price', kind='derived'),
            ParameterColumn(id='attachment:0', name='state', kind='attachment'),
        ],
        cases=[
            ParameterCase(
                id=NodeId('t.py::test_x[3]'),
                values=[
                    200,
                    '2.0',
                    Attachment(
                        label='state', content='{"ml": 200}', content_type='json'
                    ),
                ],
                status='passed',
            ),
            ParameterCase(
                id=NodeId('t.py::test_x[4]'),
                values=[350, None, None],
                status='skipped',
                custom_id=True,
            ),
        ],
    )
    scenario = Scenario(
        id=NodeId('t.py::test_brew'),
        narration=Narration(text='brew'),
        module='m',
        parameters=table,
    )
    restored = _restored(scenario)
    assert restored.parameters == table


def test_round_trip_preserves_attachment_ref_and_inline_attachment() -> None:
    step = Step(
        phase='when',
        narration=Narration(text='brews'),
        attachments=[
            Attachment(label='inline', content='same everywhere'),
            AttachmentRef(label='state', content_type='json', column_id='attachment:0'),
        ],
    )
    scenario = Scenario(
        id=NodeId('t.py::test_brew'),
        narration=Narration(text='brew'),
        module='m',
        steps=[step],
    )
    restored = _restored(scenario)
    assert restored.steps[0].attachments == step.attachments


def test_round_trip_preserves_placeholder_column_id() -> None:
    narration = Narration(
        text='costs {price}',
        parts=(
            NarrationLiteral(value='costs '),
            NarrationPlaceholder(name='price', column_id='derived:0'),
        ),
    )
    scenario = Scenario(id=NodeId('t.py::t'), narration=narration, module='m')
    restored = _restored(scenario)
    assert restored.narration.parts[1] == narration.parts[1]


def test_metadata_title_defaults_to_none_when_absent() -> None:
    report = report_from_dict({'metadata': _minimal_metadata_dict(), 'scenarios': []})
    assert report.metadata.title is None


def test_metadata_title_round_trips() -> None:
    md = _minimal_metadata_dict() | {'title': 'Coffee Shop Example'}
    report = report_from_dict({'metadata': md, 'scenarios': []})
    assert report.metadata.title == 'Coffee Shop Example'
    assert report_to_dict(report)['metadata']['title'] == 'Coffee Shop Example'


def test_a_fully_populated_report_survives_the_round_trip() -> None:
    """Every field the writer emits, the reader reads back."""
    once = report_to_dict(every_field_populated())
    assert report_to_dict(report_from_dict(once)) == once


def test_report_url_round_trips() -> None:
    report = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0',
            report_url='https://example.org/report.html',
        )
    )
    rebuilt = report_from_dict(report_to_dict(report))
    assert rebuilt.metadata.report_url == 'https://example.org/report.html'


def test_a_report_without_report_url_reads_as_none() -> None:
    data = {'metadata': _minimal_metadata_dict(), 'scenarios': []}
    assert report_from_dict(data).metadata.report_url is None


def test_an_empty_stored_report_url_reads_as_none() -> None:
    data = {
        'metadata': {**_minimal_metadata_dict(), 'report_url': ''},
        'scenarios': [],
    }
    assert report_from_dict(data).metadata.report_url is None


@pytest.mark.parametrize(
    'stored', ['report.html', 'https://example.org/report.html#tag=x']
)
def test_a_stored_report_url_a_citation_cannot_link_is_refused(stored: str) -> None:
    data = {
        'metadata': {**_minimal_metadata_dict(), 'report_url': stored},
        'scenarios': [],
    }
    with pytest.raises(
        PytestGivenError,
        match=(
            r'reports/x\.json is not a valid pytest-given report:\n'
            r'  metadata: report_url must be'
        ),
    ):
        report_from_dict(data, 'reports/x.json')


def test_glossary_term_section_and_avoid_round_trip() -> None:
    g = Glossary()
    g.register(
        GlossaryTerm(
            id=TermId('guest'),
            kind='actor',
            canonical='Guest',
            section='Booking',
            avoid=('Customer', 'Client (old)'),
        )
    )
    g.register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    restored = _round_trip(ReportData(metadata=_meta(), glossary=g))
    assert restored.glossary is not None
    guest = restored.glossary.get(TermId('guest'))
    assert (guest.section, guest.avoid) == ('Booking', ('Customer', 'Client (old)'))
    room = restored.glossary.get(TermId('room'))
    assert (room.section, room.avoid) == (None, ())


@scenario(
    t'A malformed {pg["Report"].l} is refused with the path and reason of each problem',
    tags=['spec/report-schema-validation'],
)
def test_a_malformed_report_lists_the_path_and_reason_of_each_problem():
    with given(
        t'a {pg["Report"].l} dict with an unknown scenario status and a misspelled key'
    ):
        payload = report_to_dict(every_field_populated())
        payload['scenarios'][0]['status'] = 'errored'
        payload['scenarios'][0]['stauts'] = 'passed'
    with (
        when_then('it is read', 'a `PytestGivenError` is raised'),
        pytest.raises(PytestGivenError) as raised,
    ):
        report_from_dict(payload, 'r.json')
    message = str(raised.value)
    with then('the error names the file it read'):
        attach('error', message)
        assert message.startswith('r.json is not a valid pytest-given report:')
    with then("it names the status's path and the statuses it allows"):
        assert (
            "scenarios.0.status: Input should be 'passed', 'failed', 'skipped' or "
            "'xfailed'" in message
        )
    with then("it names the misspelled key's path as unexpected"):
        assert 'scenarios.0.stauts: Unexpected keyword argument' in message
    with then('it links no Pydantic documentation'):
        assert 'errors.pydantic.dev' not in message


@pytest.mark.parametrize(
    ('version', 'named'),
    [
        (None, 'no schema version'),
        (2, 'schema version 2'),
        ('1', "schema version '1'"),
        (True, 'schema version True'),
        (1.0, 'schema version 1.0'),
    ],
)
def test_a_report_of_another_schema_version_is_refused_in_one_line(version, named):
    payload = report_to_dict(ReportData(metadata=_meta()))
    if version is None:
        del payload['metadata']['schema_version']
    else:
        payload['metadata']['schema_version'] = version
    payload['scenarios'] = [{'bogus': 1}]
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(payload, 'old.json')
    assert str(raised.value) == (
        f'old.json is a report of {named}; this pytest-given reads version 1. '
        'Regenerate it by running the suite under this pytest-given.'
    )


def test_a_dict_without_metadata_is_refused_by_validation():
    with pytest.raises(PytestGivenError, match=r'metadata: Field required'):
        report_from_dict({'scenarios': []}, 'x.json')
    with pytest.raises(
        PytestGivenError,
        match=(
            r'^x\.json is not a valid pytest-given report:\n'
            r'  metadata: Input should be'
        ),
    ):
        report_from_dict({'metadata': [], 'scenarios': []}, 'x.json')


def test_a_report_with_many_errors_lists_ten_and_counts_the_rest():
    scenario = Scenario(id=NodeId('t.py::t'), narration=Narration(text='x'), module='m')
    payload = report_to_dict(ReportData(metadata=_meta(), scenarios=[scenario] * 15))
    for scenario_dict in payload['scenarios']:
        scenario_dict['status'] = 'errored'
    with pytest.raises(PytestGivenError) as raised:
        report_from_dict(payload)
    message = str(raised.value)
    assert message.startswith('input is not a valid pytest-given report:\n')
    assert message.count('Input should be') == 10
    assert message.endswith('\n  and 5 more')


def test_a_step_source_in_a_report_is_refused():
    payload = report_to_dict(every_field_populated())
    payload['scenarios'][0]['steps'][0]['source'] = {'relpath': 't.py', 'line': 9}
    with pytest.raises(
        PytestGivenError, match=r'scenarios\.0\.steps\.0\.source: Unexpected keyword'
    ):
        report_from_dict(payload)


def test_report_from_dict_refuses_a_delta_json():
    with pytest.raises(PytestGivenError, match=r'pytest-given delta d.json'):
        report_from_dict({'metadata': {'kind': 'delta'}, 'scenarios': []}, 'd.json')
