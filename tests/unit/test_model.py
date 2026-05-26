from pytest_given.model import (
    Attachment,
    ErrorInfo,
    FixtureRecording,
    Metadata,
    NodeId,
    ParameterCase,
    ParameterTable,
    RecordingState,
    ReportData,
    Scenario,
    Step,
)
from pytest_given.template import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
)


def _n(text: str) -> Narration:
    return Narration(text=text)


def test_step_defaults() -> None:
    step = Step(phase='given', narration=_n('a coffee machine'))
    assert step.phase == 'given'
    assert step.narration.text == 'a coffee machine'
    assert step.narration.parts == []
    assert step.status == 'passed'
    assert step.children == []
    assert step.attachments == []

    assert step.error is None


def test_step_with_children() -> None:
    child = Step(phase='when', narration=_n('validating coin'))
    parent = Step(phase='when', narration=_n('insert money'), children=[child])
    assert len(parent.children) == 1
    assert parent.children[0].narration.text == 'validating coin'


def test_attachment() -> None:
    att = Attachment(label='Machine log', content='log line 1\nlog line 2')
    assert att.label == 'Machine log'
    assert att.content == 'log line 1\nlog line 2'


def test_error_info() -> None:
    err = ErrorInfo(message='assert 1 == 2', diff='- 1\n+ 2')
    assert err.message == 'assert 1 == 2'
    assert err.diff == '- 1\n+ 2'


def test_error_info_without_diff() -> None:
    err = ErrorInfo(message='assert False')
    assert err.diff is None


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
    table = ParameterTable(names=['euros', 'coffees'], cases=[case1, case2])
    assert table.names == ['euros', 'coffees']
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
        NarrationPlaceholder(name='cup_size'),
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
