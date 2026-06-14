import pytest

from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    Narration,
    NarrationLiteral,
    NarrationPlaceholder,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterTable,
    PytestGivenError,
    ReportData,
    Scenario,
    SourceLocation,
    Step,
    report_from_dict,
    report_to_dict,
)
from pytest_given.model.serde import _asdict_filtered


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


def test_step_with_attachment_and_error_and_children() -> None:
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
    assert step.status == 'failed'
    assert step.attachments == [
        Attachment(label='log', content='x', content_type='text')
    ]
    assert step.error == ErrorInfo(message='boom')
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
                        'names': ['euros', 'expect'],
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
    assert pt.names == ['euros', 'expect']
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
        NarrationPlaceholder(name='euros', format_spec='03d', conversion='r')
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
                            name='cup', format_spec='', conversion=None
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
