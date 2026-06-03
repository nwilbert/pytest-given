import dataclasses

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
                    'error': {'message': 'boom', 'diff': '- a\n+ b'},
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
                            'error': {'message': 'boom', 'diff': None},
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
    assert s.error == ErrorInfo(message='boom', diff='- a\n+ b')
    assert len(s.steps) == 1
    step = s.steps[0]
    assert isinstance(step, Step)
    assert step.phase == 'then'
    assert step.status == 'failed'
    assert step.attachments == [
        Attachment(label='log', content='x', content_type='text')
    ]
    assert step.error == ErrorInfo(message='boom', diff=None)
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
                                'error': {'message': 'boom', 'diff': None},
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
            error=ErrorInfo(message='boom', diff=None),
        ),
    ]


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


def test_report_to_dict_matches_dataclasses_asdict() -> None:
    """`report_to_dict` is a thin wrapper over `dataclasses.asdict`."""
    report = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[],
    )
    assert report_to_dict(report) == dataclasses.asdict(report)


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
