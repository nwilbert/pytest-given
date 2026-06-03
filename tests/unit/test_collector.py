import pytest

from pytest_given import Template
from pytest_given.collector import Collector
from pytest_given.model import (
    FixtureRecording,
    NodeId,
    PytestGivenError,
    SourceLocation,
    Step,
)
from pytest_given.template import (
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationValue,
)


def _n(text: str) -> Narration:
    return Narration(text=text)


def test_start_and_finish_scenario() -> None:
    collector = Collector()
    collector.start_scenario('test.py::test_x', 'Test X', 'test_module', ['tag1'])
    scenario = collector.finish_scenario(status='passed', duration_ms=10)
    assert scenario.narration.text == 'Test X'
    assert scenario.status == 'passed'
    assert scenario.duration_ms == 10
    assert scenario.tags == ['tag1']


def test_collect_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', _n('a machine'))
    collector.pop_step()
    collector.push_step('when', _n('I press start'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 2
    assert scenario.steps[0].phase == 'given'
    assert scenario.steps[0].narration.text == 'a machine'
    assert scenario.steps[1].phase == 'when'


def test_nested_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('when', _n('outer'))
    collector.push_step('when', _n('inner'))
    collector.pop_step()
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 1
    outer = scenario.steps[0]
    assert outer.narration.text == 'outer'
    assert len(outer.children) == 1
    assert outer.children[0].narration.text == 'inner'


def test_attach_to_current_step() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', _n('check result'))
    collector.attach('Log output', 'line1\nline2')
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    step = scenario.steps[0]
    assert len(step.attachments) == 1
    assert step.attachments[0].label == 'Log output'
    assert step.attachments[0].content == 'line1\nline2'


def test_step_failure() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', _n('should fail'))
    collector.fail_current_step('assert 1 == 2', diff='- 1\n+ 2')
    collector.pop_step()
    scenario = collector.finish_scenario(status='failed', duration_ms=0)
    step = scenario.steps[0]
    assert step.status == 'failed'
    assert step.error is not None
    assert step.error.message == 'assert 1 == 2'


def test_no_active_scenario_returns_none() -> None:
    collector = Collector()
    assert collector.active_scenario_id is None


def test_pop_step_empty_stack() -> None:
    collector = Collector()
    assert collector.pop_step() is None


def test_active_scenario_id_set() -> None:
    collector = Collector()
    collector.start_scenario('test.py::test_x', 'X', 'mod', [])
    assert collector.active_scenario_id == 'test.py::test_x'
    collector.finish_scenario(status='passed', duration_ms=0)
    assert collector.active_scenario_id is None


def test_cross_phase_nesting_raises() -> None:
    """Nesting a different phase inside another raises an error."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', _n('result is correct'))
    with pytest.raises(
        RuntimeError,
        match="Cannot nest 'given' inside 'then'",
    ):
        collector.push_step('given', _n('some precondition'))


def test_same_phase_nesting_allowed() -> None:
    """Nesting the same phase inside itself is allowed."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('when', _n('outer step'))
    collector.push_step('when', _n('inner step'))
    collector.pop_step()
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 1
    assert len(scenario.steps[0].children) == 1


def test_sequential_different_phases_allowed() -> None:
    """Different phases at the top level (not nested) is fine."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', _n('setup'))
    collector.pop_step()
    collector.push_step('when', _n('action'))
    collector.pop_step()
    collector.push_step('then', _n('check'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 3


def test_current_phase() -> None:
    """current_phase reflects the innermost active step."""
    collector = Collector()
    assert collector.current_phase is None
    collector.start_scenario('id', 'name', 'mod', [])
    assert collector.current_phase is None
    collector.push_step('given', _n('a thing'))
    assert collector.current_phase == 'given'
    collector.pop_step()
    assert collector.current_phase is None


def test_collector_starts_idle() -> None:
    collector = Collector()
    assert collector.state == 'idle'


def test_start_scenario_transitions_to_test() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    assert collector.state == 'test'


def test_finish_scenario_returns_to_idle() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.finish_scenario(status='passed', duration_ms=0)
    assert collector.state == 'idle'


def test_enter_fixture_setup_transitions_state() -> None:
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('a shop')))
    token = collector.enter_fixture_setup(recording)
    assert collector.state == 'fixture_setup'
    collector.exit_fixture_setup(token)
    assert collector.state == 'idle'


def test_enter_fixture_setup_nests_inside_test() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    recording = FixtureRecording(root=Step(phase='given', narration=_n('a shop')))
    token = collector.enter_fixture_setup(recording)
    assert collector.state == 'fixture_setup'
    collector.exit_fixture_setup(token)
    assert collector.state == 'test'  # restored


def test_enter_fixture_teardown_transitions_state() -> None:
    collector = Collector()
    token = collector.enter_fixture_teardown()
    assert collector.state == 'fixture_teardown'
    collector.exit_fixture_teardown(token)
    assert collector.state == 'idle'


def test_push_step_during_fixture_setup_records_into_recording() -> None:
    collector = Collector()
    root = Step(phase='given', narration=_n('a shop'))
    recording = FixtureRecording(root=root)
    token = collector.enter_fixture_setup(recording)
    collector.push_step('given', _n('with 3 items'))
    collector.pop_step()
    collector.exit_fixture_setup(token)
    assert len(root.children) == 1
    assert root.children[0].narration.text == 'with 3 items'


def test_attach_during_fixture_setup_records_into_recording() -> None:
    collector = Collector()
    root = Step(phase='given', narration=_n('a shop'))
    recording = FixtureRecording(root=root)
    token = collector.enter_fixture_setup(recording)
    collector.attach('snapshot', 'data')
    collector.exit_fixture_setup(token)
    assert len(root.attachments) == 1
    assert root.attachments[0].label == 'snapshot'


def test_push_step_routing_isolates_recording_from_scenario() -> None:
    """Steps recorded inside fixture setup must NOT leak into the active scenario."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    root = Step(phase='given', narration=_n('a shop'))
    recording = FixtureRecording(root=root)
    token = collector.enter_fixture_setup(recording)
    collector.push_step('given', _n('fixture-internal'))
    collector.pop_step()
    collector.exit_fixture_setup(token)
    # Scenario should still be empty — fixture body's step lives only in recording.
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.steps == []
    assert root.children[0].narration.text == 'fixture-internal'


def test_push_step_during_idle_raises() -> None:
    collector = Collector()
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'):
        collector.push_step('given', _n('orphan'))


def test_push_step_during_teardown_raises() -> None:
    collector = Collector()
    token = collector.enter_fixture_teardown()
    try:
        with pytest.raises(PytestGivenError, match='fixture teardown'):
            collector.push_step('given', _n('teardown step'))
    finally:
        collector.exit_fixture_teardown(token)


def test_attach_during_teardown_raises() -> None:
    collector = Collector()
    token = collector.enter_fixture_teardown()
    try:
        with pytest.raises(PytestGivenError, match='fixture teardown'):
            collector.attach('label', 'content')
    finally:
        collector.exit_fixture_teardown(token)


def test_attach_during_idle_raises() -> None:
    collector = Collector()
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'):
        collector.attach('label', 'content')


def test_store_and_retrieve_recording_by_key() -> None:
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('a shop')))
    collector.store_recording(('fixdef_a', None), recording)
    assert collector.get_recording(('fixdef_a', None)) is recording
    assert collector.get_recording(('fixdef_b', None)) is None


def test_graft_recording_deep_copies_into_scenario() -> None:
    collector = Collector()
    root = Step(phase='given', narration=_n('a shop'))
    root.children.append(Step(phase='given', narration=_n('with 3 items')))
    recording = FixtureRecording(root=root)

    collector.start_scenario('id', 'name', 'mod', [])
    collector.graft_recording(recording)
    scenario = collector.finish_scenario(status='passed', duration_ms=0)

    assert len(scenario.steps) == 1
    assert scenario.steps[0].narration.text == 'a shop'
    assert scenario.steps[0].children[0].narration.text == 'with 3 items'
    # Deep-copy: mutating the recording must not affect the scenario.
    root.children[0].narration = _n('mutated')
    assert scenario.steps[0].children[0].narration.text == 'with 3 items'


def test_graft_recording_with_no_scenario_is_noop() -> None:
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('x')))
    collector.graft_recording(recording)  # should not raise


def test_pop_step_protects_recording_root() -> None:
    """In fixture_setup state, popping the root step is a no-op so it remains
    as the labeled parent for grafting."""
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('label')))
    token = collector.enter_fixture_setup(recording)
    try:
        # Stack has just the root; pop should refuse to remove it.
        assert collector.pop_step() is None
        assert len(recording.stack) == 1
        # A pushed child can still be popped.
        collector.push_step('given', _n('child'))
        popped = collector.pop_step()
        assert popped is not None
        assert popped.narration.text == 'child'
    finally:
        collector.exit_fixture_setup(token)


def test_pop_step_with_empty_stack_returns_none() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    assert collector.pop_step() is None


def test_push_step_with_structured_narration() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    parts: list[NarrationPart] = [
        NarrationLiteral(value='a '),
        NarrationValue(rendered='200', expression='cup_size'),
        NarrationLiteral(value=' ml cup'),
    ]
    narration = Narration(text='a 200 ml cup', parts=parts)
    collector.push_step('given', narration)
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.steps[0].narration.text == 'a 200 ml cup'
    assert scenario.steps[0].narration.parts == parts


def test_push_step_with_plain_narration_has_empty_parts() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', _n('plain'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.steps[0].narration.parts == []


def test_start_scenario_with_template_stores_structured_narration() -> None:
    collector = Collector()
    tmpl = Template('Brew {cup_size} ml')
    collector.start_scenario('id', tmpl, 'mod', [])
    collector.push_step('given', _n('a step'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.narration.text == 'Brew {cup_size} ml'  # raw template string
    assert scenario.narration.parts == list(tmpl.parts)


def test_start_scenario_with_plain_str_has_empty_parts() -> None:
    collector = Collector()
    collector.start_scenario('id', 'plain name', 'mod', [])
    collector.push_step('given', _n('a step'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.narration.text == 'plain name'
    assert scenario.narration.parts == []


def test_finish_scenario_records_skip_reason() -> None:
    c = Collector()
    c.start_scenario(NodeId('t::x'), name='x', module='m', tags=[])
    s = c.finish_scenario(status='skipped', duration_ms=0, skip_reason='because')
    assert s.skip_reason == 'because'


def test_finish_scenario_skip_reason_defaults_to_none() -> None:
    c = Collector()
    c.start_scenario(NodeId('t::x'), name='x', module='m', tags=[])
    s = c.finish_scenario(status='passed', duration_ms=0)
    assert s.skip_reason is None


def test_start_scenario_stores_source() -> None:
    collector = Collector()
    src = SourceLocation(relpath='tests/test_x.py', line=5)
    collector.start_scenario(
        scenario_id=NodeId('tests/test_x.py::test_y'),
        name='S',
        module='m',
        tags=[],
        source=src,
    )
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.source == src


def test_start_scenario_source_defaults_to_none() -> None:
    collector = Collector()
    collector.start_scenario(
        scenario_id=NodeId('t::y'),
        name='S',
        module='m',
        tags=[],
    )
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert scenario.source is None
