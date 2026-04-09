import json

from pytest_given.model import (
    Attachment,
    ErrorInfo,
    Metadata,
    ParameterCase,
    ParameterTable,
    ReportData,
    Scenario,
    Step,
)
from pytest_given.serializer import serialize_report


def test_serialize_empty_report() -> None:
    report = ReportData(
        metadata=Metadata(
            project='test',
            timestamp='2026-04-09T00:00:00Z',
            pytest_version='9.0',
            plugin_version='0.1.0',
        ),
        scenarios=[],
    )
    data = serialize_report(report)
    assert data['metadata']['project'] == 'test'
    assert data['scenarios'] == []
    json.dumps(data)


def test_serialize_scenario_with_steps() -> None:
    report = ReportData(
        metadata=Metadata(
            project='p',
            timestamp='t',
            pytest_version='9',
            plugin_version='0.1',
        ),
        scenarios=[
            Scenario(
                id='test.py::test_x',
                name='Test X',
                module='test_mod',
                tags=['billing'],
                status='passed',
                duration_ms=42,
                steps=[
                    Step(
                        phase='given',
                        text='a machine',
                        source='fixture',
                    ),
                    Step(
                        phase='when',
                        text='I press start',
                        children=[
                            Step(phase='when', text='validating'),
                        ],
                    ),
                ],
            )
        ],
    )
    data = serialize_report(report)
    scenario = data['scenarios'][0]
    assert scenario['name'] == 'Test X'
    assert scenario['tags'] == ['billing']
    assert len(scenario['steps']) == 2
    assert scenario['steps'][0]['source'] == 'fixture'
    assert len(scenario['steps'][1]['children']) == 1
    json.dumps(data)


def test_serialize_with_parameters() -> None:
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
        ),
        scenarios=[
            Scenario(
                id='test.py::test_param',
                name='Param test',
                module='mod',
                status='failed',
                parameters=ParameterTable(
                    names=['a', 'b'],
                    cases=[
                        ParameterCase(values=[1, 2], status='passed'),
                        ParameterCase(
                            values=[3, 4],
                            status='failed',
                            error=ErrorInfo(message='assert 3 == 4'),
                        ),
                    ],
                ),
            )
        ],
    )
    data = serialize_report(report)
    params = data['scenarios'][0]['parameters']
    assert params['names'] == ['a', 'b']
    assert params['cases'][1]['error']['message'] == 'assert 3 == 4'
    json.dumps(data)


def test_serialize_with_attachments() -> None:
    report = ReportData(
        metadata=Metadata(
            project='p', timestamp='t', pytest_version='9', plugin_version='0.1'
        ),
        scenarios=[
            Scenario(
                id='id',
                name='n',
                module='m',
                steps=[
                    Step(
                        phase='then',
                        text='check',
                        attachments=[Attachment(label='Log', content='data')],
                    )
                ],
            )
        ],
    )
    data = serialize_report(report)
    att = data['scenarios'][0]['steps'][0]['attachments'][0]
    assert att == {'label': 'Log', 'content': 'data'}
    json.dumps(data)
