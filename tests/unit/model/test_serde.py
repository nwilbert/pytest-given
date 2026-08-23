import pytest

from pytest_given.model import (
    Activity,
    ActivityId,
    ActivityPath,
    ActivityTermRef,
    ActivityWord,
    Attachment,
    AttachmentRef,
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
    PytestGivenError,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TermId,
    report_from_dict,
    report_to_dict,
)
from pytest_given.model.serde import (
    _activity_part_from_dict,
    _asdict_filtered,
    _narration_part_from_dict,
    _param_table_from_dict,
)


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


def test_activity_term_ref_round_trips():
    story = Story(
        id=StoryId('s'),
        title='S',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(
                    ActivityPath(
                        parts=(
                            ActivityTermRef(term_id=TermId('guest'), display='Guest'),
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
    part = round_tripped.stories[0].activities[0].paths[0].parts[0]
    assert part == ActivityTermRef(term_id=TermId('guest'), display='Guest')


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
                    'skip_reason': None,
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


def test_step_source_is_not_serialized() -> None:
    # Step.source is lint-only capture state; report artifacts must stay
    # byte-identical whether or not it was captured.
    step = Step(
        phase='given',
        narration=Narration(text='g'),
        source=SourceLocation(relpath='tests/t.py', line=3),
    )
    scenario = Scenario(
        id=NodeId('i'), narration=Narration(text='n'), module='m', steps=[step]
    )
    report = ReportData(metadata=_meta(), scenarios=[scenario])
    step_dict = report_to_dict(report)['scenarios'][0]['steps'][0]
    assert 'source' not in step_dict
    assert _round_trip(report).scenarios[0].steps[0].source is None


def test_step_with_attachment_and_children_drops_a_legacy_status_and_error() -> None:
    """A report written before step-level failure was removed still loads.

    Failure lives on the scenario (and, for a parametrized run, on the case);
    a step's `status` / `error` are dropped rather than migrated, since no
    real run ever set them to anything but the defaults.
    """
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
                    'duration_ms': 1,
                    'parameters': None,
                    'error': {
                        'message': 'boom',
                        'frames': [],
                        'error_tail': '- a\n+ b',
                    },
                    'steps': [
                        {
                            'phase': 'then',
                            'narration': {'text': 'check', 'parts': []},
                            'status': 'failed',
                            'attachments': [
                                {
                                    'label': 'log',
                                    'content': 'x',
                                    'content_type': 'text',
                                }
                            ],
                            'error': {
                                'message': 'boom',
                                'frames': [],
                                'error_tail': None,
                            },
                            'children': [
                                {
                                    'phase': 'then',
                                    'narration': {'text': 'inner', 'parts': []},
                                    'status': 'passed',
                                    'attachments': [],
                                    'error': None,
                                    'children': [],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )
    s = report.scenarios[0]
    assert s.error == ErrorInfo(message='boom', error_tail='- a\n+ b')
    assert len(s.steps) == 1
    step = s.steps[0]
    assert isinstance(step, Step)
    assert step.phase == 'then'
    assert not hasattr(step, 'status')
    assert not hasattr(step, 'error')
    assert step.attachments == [
        Attachment(label='log', content='x', content_type='text')
    ]
    assert len(step.children) == 1
    assert step.children[0].narration.text == 'inner'


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
                            {'values': [1, False], 'status': 'passed', 'error': None},
                            {
                                'values': [2, True],
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
        ParameterCase(values=[1, False], status='passed', error=None),
        ParameterCase(
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
    assert parts == [NarrationLiteral(value='hello')]


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
    assert parts == [
        NarrationValue(
            rendered='12.0',
            expression='price * 1.2',
            format_spec='',
            conversion=None,
        )
    ]


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
    assert parts == [
        NarrationPlaceholder(
            name='euros', column_id='euros', format_spec='03d', conversion='r'
        )
    ]


def test_narration_unknown_part_shape_raises() -> None:
    with pytest.raises(PytestGivenError) as exc:
        report_from_dict(
            {
                'metadata': _minimal_metadata_dict(),
                'scenarios': [
                    {
                        'id': 'i',
                        'narration': {
                            'text': 'S',
                            'parts': [{'mystery_field': '?'}],
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
    assert 'narration' in str(exc.value).lower()


def test_report_to_dict_excludes_underscore_fields() -> None:
    """report_to_dict skips fields whose names start with '_' (e.g. _by_id)."""
    report = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[],
    )
    result = report_to_dict(report)
    # No underscore-prefixed keys anywhere in the output.
    assert all(not k.startswith('_') for k in result)
    assert result['metadata']['project'] == 'p'
    assert result['scenarios'] == []
    assert result['glossary'] is None
    assert result['stories'] == []


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
                    parts=[
                        NarrationLiteral(value='Brew '),
                        NarrationPlaceholder(
                            name='cup', column_id='cup', format_spec='', conversion=None
                        ),
                    ],
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


def test_asdict_filtered_handles_dict_values() -> None:
    """_asdict_filtered handles plain dict values (not just lists/dataclasses)."""
    result = _asdict_filtered({'key': 'value', 'nested': {'a': 1}})
    assert result == {'key': 'value', 'nested': {'a': 1}}


def test_activity_part_variants_round_trip():
    parts = (
        ActivityTermRef(term_id=TermId('guest'), display='Guest'),
        ActivityTermRef(term_id=TermId('search'), display='searches'),
        ActivityWord(text='for'),
    )
    path = ActivityPath(parts=parts)
    activity = Activity(id=ActivityId(1), paths=(path,))
    story = Story(id=StoryId('s'), title='S', activities=(activity,))
    report = ReportData(metadata=_meta(), stories=[story])
    rt = _round_trip(report)
    rt_parts = rt.stories[0].activities[0].paths[0].parts
    assert rt_parts == parts


def test_glossary_round_trips_and_rebuilds_index():
    g = Glossary()
    g._register(GlossaryTerm(id=TermId('guest'), kind='actor', canonical='Guest'))
    g._register(GlossaryTerm(id=TermId('room'), kind='object', canonical='Room'))
    report = ReportData(metadata=_meta(), glossary=g)
    rt = _round_trip(report)
    assert rt.glossary is not None
    assert rt.glossary.get(TermId('guest')).canonical == 'Guest'
    assert rt.glossary.get(TermId('room')).kind == 'object'


def test_narration_term_ref_round_trips():
    narration = Narration(
        text='Alice arrives',
        parts=[
            NarrationLiteral(value='Hello '),
            NarrationTermRef(
                term_id=TermId('guest'),
                display='Alice',
                expression='guest',
                param_column='guest',
            ),
        ],
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


def test_scenario_story_id_and_activity_ids_round_trip():
    scn = Scenario(
        id=NodeId('n'),
        narration=Narration(text='x'),
        module='m',
        story_id=StoryId('book'),
        activity_ids=(ActivityId(1), ActivityId(2)),
    )
    report = ReportData(metadata=_meta(), scenarios=[scn])
    rt = _round_trip(report)
    assert rt.scenarios[0].story_id == 'book'
    assert rt.scenarios[0].activity_ids == (1, 2)


def test_step_activity_ids_round_trip():
    scn = Scenario(
        id=NodeId('n'),
        narration=Narration(text='x'),
        module='m',
        steps=[
            Step(
                phase='given',
                narration=Narration(text='s'),
                activity_ids=(ActivityId(7),),
            )
        ],
    )
    report = ReportData(metadata=_meta(), scenarios=[scn])
    rt = _round_trip(report)
    assert rt.scenarios[0].steps[0].activity_ids == (7,)


def test_activity_part_unknown_shape_raises():
    with pytest.raises(PytestGivenError, match='unknown ActivityPart shape'):
        _activity_part_from_dict({'unknown_key': 'x'})


def test_narration_part_unknown_shape_raises():
    """Pre-existing behavior — covered to keep 100% after extending the branch."""
    with pytest.raises(PytestGivenError, match='Unknown narration part shape'):
        _narration_part_from_dict({'mystery': 'x'})


def test_story_source_roundtrips() -> None:
    story = Story(
        id=StoryId('checkout'),
        title='Checkout',
        activities=(
            Activity(
                id=ActivityId(1),
                paths=(ActivityPath(parts=(ActivityWord(text='x'),)),),
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
                values=[
                    200,
                    '2.0',
                    Attachment(
                        label='state', content='{"ml": 200}', content_type='json'
                    ),
                ],
                status='passed',
            ),
            ParameterCase(values=[350, None, None], status='skipped'),
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
        parts=[
            NarrationLiteral(value='costs '),
            NarrationPlaceholder(name='price', column_id='derived:0'),
        ],
    )
    scenario = Scenario(id=NodeId('t.py::t'), narration=narration, module='m')
    restored = _restored(scenario)
    assert restored.narration.parts[1] == narration.parts[1]


def test_a_pre_columns_parameter_table_says_to_re_run_the_suite():
    """`pytest-given report` on a report saved before `names` became `columns`
    used to die with a bare `KeyError: 'columns'`. There is no migration — the
    error has to say so."""
    with pytest.raises(PytestGivenError, match='re-run the suite'):
        _param_table_from_dict({'names': ['cup_size'], 'cases': []})


def test_a_pre_columns_placeholder_says_to_re_run_the_suite():
    """Same vintage of report, reached through a step's narration rather than
    its parameter table: a placeholder gained `column_id` in the same change."""
    with pytest.raises(PytestGivenError, match='re-run the suite'):
        _narration_part_from_dict({'name': 'cup_size'})


def test_metadata_title_defaults_to_none_when_absent() -> None:
    report = report_from_dict({'metadata': _minimal_metadata_dict(), 'scenarios': []})
    assert report.metadata.title is None


def test_metadata_title_round_trips() -> None:
    md = _minimal_metadata_dict() | {'title': 'Coffee Shop Example'}
    report = report_from_dict({'metadata': md, 'scenarios': []})
    assert report.metadata.title == 'Coffee Shop Example'
    assert report_to_dict(report)['metadata']['title'] == 'Coffee Shop Example'
