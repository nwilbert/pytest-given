from types import SimpleNamespace

import pytest

from pytest_given import Template, given, scenario, then, when, when_then
from pytest_given.capture import collector as collector_mod
from pytest_given.capture.collector import Collector
from pytest_given.model import (
    FixtureRecording,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationValue,
    NodeId,
    PytestGivenError,
    SourceLocation,
    Step,
)
from tests.ubiquitous_language import adopt_pytest_given, pg


def _n(text: str) -> Narration:
    return Narration(text=text)


@scenario(
    t'A {pg["Scenario"].low} records under its {pg["Node ID"]("node ID")}',
)
def test_start_and_finish_scenario() -> None:
    with given(t'a fresh {pg["Collector"]}'):
        collector = Collector()
    with when(t'a {pg["Scenario"]} starts under its {pg["Node ID"]} and finishes'):
        collector.start_scenario('test.py::test_x', 'Test X', 'test_module', ['tag1'])
        recorded = collector.finish_scenario(status='passed')
    with then(t'it carries its {pg["Node ID"]}, name, status and {pg["Tag"]}'):
        assert recorded.id == 'test.py::test_x'
        assert recorded.narration.text == 'Test X'
        assert recorded.status == 'passed'
        assert recorded.tags == ['tag1']


@scenario(
    t'A {pg["Scenario"].low} is timed from past its {pg["Step fixture"].low} setup',
)
def test_duration_excludes_fixture_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    with given(t'a {pg["Collector"]} whose clock reads 100.3s once setup is done'):
        readings = iter([100.3, 100.5])
        collector = Collector()
        collector.start_scenario(NodeId('t::x'), name='x', module='m', tags=[])
    with when('the clock is started past setup and the body runs 0.2s'):
        monkeypatch.setattr(
            collector_mod, 'time', SimpleNamespace(monotonic=lambda: next(readings))
        )
        collector.begin_timing()
        recorded = collector.finish_scenario(status='passed')
        # Undone here rather than at teardown: this session's own Collector
        # finishes *this* scenario before teardown runs, and would otherwise
        # drain the fake clock and abort the run.
        monkeypatch.undo()
    with then('the recorded duration is the body alone, not the setup before it'):
        assert recorded.duration_ms == 200


@scenario(
    t'{pg["Step"]("Steps")} record with their {pg["Phase"]("phases")}',
    story=adopt_pytest_given,
)
def test_collect_steps() -> None:
    collector = Collector()
    with given(t'an {pg["Active scenario"]} in a fresh {pg["Collector"]}'):
        collector.start_scenario('id', 'name', 'mod', [])
    with when(t'a given and a when {pg["Step"]} are pushed', activity=7):
        collector.push_step('given', _n('a machine'))
        collector.pop_step()
        collector.push_step('when', _n('I press start'))
        collector.pop_step()
        recorded = collector.finish_scenario(status='passed')
    with then(t'each {pg["Step"]} carries its {pg["Phase"]}'):
        assert len(recorded.steps) == 2
        assert recorded.steps[0].phase == 'given'
        assert recorded.steps[0].narration.text == 'a machine'
        assert recorded.steps[1].phase == 'when'


def test_nested_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('when', _n('outer'))
    collector.push_step('when', _n('inner'))
    collector.pop_step()
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed')
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
    scenario = collector.finish_scenario(status='passed')
    step = scenario.steps[0]
    assert len(step.attachments) == 1
    assert step.attachments[0].label == 'Log output'
    assert step.attachments[0].content == 'line1\nline2'


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
    collector.finish_scenario(status='passed')
    assert collector.active_scenario_id is None


def test_cross_phase_nesting_raises() -> None:
    """Nesting a different phase inside another raises PytestGivenError, like
    every other lifecycle violation in this file — so callers catching the
    documented public sentinel see this case too."""
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', _n('result is correct'))
    with pytest.raises(
        PytestGivenError,
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
    scenario = collector.finish_scenario(status='passed')
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
    scenario = collector.finish_scenario(status='passed')
    assert len(scenario.steps) == 3


def test_collector_state_transitions_idle_test_idle() -> None:
    collector = Collector()
    assert collector.state == 'idle'
    collector.start_scenario('id', 'name', 'mod', [])
    assert collector.state == 'test'
    collector.finish_scenario(status='passed')
    assert collector.state == 'idle'


def test_enter_fixture_setup_transitions_state() -> None:
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('a shop')))
    token = collector.enter_fixture_setup(recording)
    assert collector.state == 'fixture_setup'
    collector.exit_fixture(token)
    assert collector.state == 'idle'


def test_enter_fixture_setup_nests_inside_test() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    recording = FixtureRecording(root=Step(phase='given', narration=_n('a shop')))
    token = collector.enter_fixture_setup(recording)
    assert collector.state == 'fixture_setup'
    collector.exit_fixture(token)
    assert collector.state == 'test'  # restored


def test_enter_fixture_teardown_transitions_state() -> None:
    collector = Collector()
    token = collector.enter_fixture_teardown()
    assert collector.state == 'fixture_teardown'
    collector.exit_fixture(token)
    assert collector.state == 'idle'


@scenario(
    t'{pg["Step"]("Steps")} pushed during fixture setup record into the '
    t'{pg["Fixture recording"].low}',
    story=adopt_pytest_given,
)
def test_push_step_during_fixture_setup_records_into_recording() -> None:
    collector = Collector()
    with given(t'a {pg["Fixture recording"]} under setup'):
        root = Step(phase='given', narration=_n('a shop'))
        recording = FixtureRecording(root=root)
        token = collector.enter_fixture_setup(recording)
    with when(t'a {pg["Step"]} is pushed inside the fixture body', activity=7):
        collector.push_step('given', _n('with 3 items'))
        collector.pop_step()
        collector.exit_fixture(token)
    with then('it is recorded as a child of the recording root'):
        assert len(root.children) == 1
        assert root.children[0].narration.text == 'with 3 items'


@scenario(
    t'An {pg["Attachment"].low} lands on the {pg["Step"].low} being recorded',
    story=adopt_pytest_given,
)
def test_attach_during_fixture_setup_records_into_recording() -> None:
    collector = Collector()
    with given(t'a {pg["Fixture recording"]} under setup'):
        root = Step(phase='given', narration=_n('a shop'))
        recording = FixtureRecording(root=root)
        token = collector.enter_fixture_setup(recording)
    with when(t'an {pg["Attachment"]} is attached inside the fixture body', activity=6):
        collector.attach('snapshot', 'data')
        collector.exit_fixture(token)
    with then(t'the {pg["Attachment"]} lands on the recording root'):
        assert len(root.attachments) == 1
        assert root.attachments[0].label == 'snapshot'


@scenario(
    t'Fixture-body {pg["Step"]("steps")} do not leak into the '
    t'{pg["Active scenario"].low}',
    story=adopt_pytest_given,
)
def test_push_step_routing_isolates_recording_from_scenario() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    with given(t'an {pg["Active scenario"]} with a {pg["Fixture recording"]}'):
        root = Step(phase='given', narration=_n('a shop'))
        recording = FixtureRecording(root=root)
        token = collector.enter_fixture_setup(recording)
    with when(t'a {pg["Step"]} is pushed inside the fixture body', activity=7):
        collector.push_step('given', _n('fixture-internal'))
        collector.pop_step()
        collector.exit_fixture(token)
        recorded = collector.finish_scenario(status='passed')
    with then('the step lives only in the recording, not the scenario'):
        assert recorded.steps == []
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
        collector.exit_fixture(token)


def test_attach_during_teardown_raises() -> None:
    collector = Collector()
    token = collector.enter_fixture_teardown()
    try:
        with pytest.raises(PytestGivenError, match='fixture teardown'):
            collector.attach('label', 'content')
    finally:
        collector.exit_fixture(token)


def test_attach_during_idle_raises() -> None:
    collector = Collector()
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'):
        collector.attach('label', 'content')


@scenario(
    t'An {pg["Attachment"].low} outside every {pg["Step"].low} is refused',
)
def test_attach_outside_any_step_raises() -> None:
    with given(t'an {pg["Active scenario"]} with no {pg["Step"]} open'):
        collector = Collector()
        collector.start_scenario(NodeId('test.py::test_x'), 'Test X', 'mod', [])
    with (
        when_then(
            t'an {pg["Attachment"].low} is made from the test body',
            t'it is refused rather than dropped',
        ),
        pytest.raises(PytestGivenError, match='no step is open'),
    ):
        collector.attach('config', 'content')


@scenario(
    t'A {pg["Fixture recording"].low} is deep-copied when {pg["Graft"]("grafted")}',
    story=adopt_pytest_given,
)
def test_graft_recording_deep_copies_into_scenario() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    with given(t'a {pg["Fixture recording"]} with a nested child {pg["Step"]}'):
        root = Step(phase='given', narration=_n('a shop'))
        root.children.append(Step(phase='given', narration=_n('with 3 items')))
        recording = FixtureRecording(root=root)
    with when(
        t'a {pg["Graft"]} copies it into the {pg["Active scenario"]}', activity=8
    ):
        collector.graft_recording(recording)
        recorded = collector.finish_scenario(status='passed')
    with then('the scenario gains a deep copy of the recorded steps'):
        assert recorded.steps[0].narration.text == 'a shop'
        assert recorded.steps[0].children[0].narration.text == 'with 3 items'
        # Mutating the recording must not affect the grafted copy.
        root.children[0].narration = _n('mutated')
        assert recorded.steps[0].children[0].narration.text == 'with 3 items'


def test_graft_recording_without_scenario_is_refused() -> None:
    # Grafting only ever runs with a scenario open; the guard is an invariant,
    # not a tolerated case — a silent return would drop the fixture's subtree.
    collector = Collector()
    recording = FixtureRecording(root=Step(phase='given', narration=_n('x')))
    with pytest.raises(AssertionError):
        collector.graft_recording(recording)


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
        collector.exit_fixture(token)


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
    scenario = collector.finish_scenario(status='passed')
    assert scenario.steps[0].narration.text == 'a 200 ml cup'
    assert scenario.steps[0].narration.parts == parts


def test_push_step_with_plain_narration_has_empty_parts() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', _n('plain'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed')
    assert scenario.steps[0].narration.parts == []


def test_start_scenario_with_template_stores_structured_narration() -> None:
    collector = Collector()
    tmpl = Template('Brew {cup_size} ml')
    collector.start_scenario('id', tmpl, 'mod', [])
    collector.push_step('given', _n('a step'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed')
    assert scenario.narration.text == 'Brew {cup_size} ml'  # raw template string
    assert scenario.narration.parts == list(tmpl.parts)


def test_start_scenario_with_plain_str_has_empty_parts() -> None:
    collector = Collector()
    collector.start_scenario('id', 'plain name', 'mod', [])
    collector.push_step('given', _n('a step'))
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed')
    assert scenario.narration.text == 'plain name'
    assert scenario.narration.parts == []


def test_finish_scenario_records_skip_reason() -> None:
    c = Collector()
    c.start_scenario(NodeId('t::x'), name='x', module='m', tags=[])
    s = c.finish_scenario(status='skipped', skip_reason='because')
    assert s.skip_reason == 'because'


def test_finish_scenario_skip_reason_defaults_to_none() -> None:
    c = Collector()
    c.start_scenario(NodeId('t::x'), name='x', module='m', tags=[])
    s = c.finish_scenario(status='passed')
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
    scenario = collector.finish_scenario(status='passed')
    assert scenario.source == src


def test_start_scenario_source_defaults_to_none() -> None:
    collector = Collector()
    collector.start_scenario(
        scenario_id=NodeId('t::y'),
        name='S',
        module='m',
        tags=[],
    )
    scenario = collector.finish_scenario(status='passed')
    assert scenario.source is None


@scenario(
    t'A {pg["Step fixture"].low} failing in teardown fails its finished '
    t'{pg["Scenario"].low}',
)
def test_fail_recorded_scenario_marks_a_finished_scenario_failed() -> None:
    with given(t'a {pg["Scenario"]} that already finished as passed'):
        collector = Collector()
        collector.start_scenario(NodeId('test.py::test_x'), 'Test X', 'mod', [])
        recorded = collector.finish_scenario(status='passed')
    with when('a fixture raises past its yield, after the scenario finished'):
        collector.fail_recorded_scenario(
            NodeId('test.py::test_x'), message='teardown boom'
        )
    with then(t'the recorded {pg["Scenario"].low} carries the failure'):
        assert recorded.status == 'failed'
        assert recorded.error is not None
        assert recorded.error.message == 'teardown boom'


@scenario(
    t'A teardown failure keeps the error the {pg["Scenario"].low} already carries',
)
def test_fail_recorded_scenario_keeps_an_existing_error() -> None:
    with given(t'a {pg["Scenario"]} that already failed in its body'):
        collector = Collector()
        collector.start_scenario(NodeId('test.py::test_x'), 'Test X', 'mod', [])
        collector.fail_scenario(message='body boom')
        recorded = collector.finish_scenario(status='failed')
    with when('its fixture then also fails in teardown'):
        collector.fail_recorded_scenario(
            NodeId('test.py::test_x'), message='teardown boom'
        )
    with then('the body failure is what the report shows'):
        assert recorded.error is not None
        assert recorded.error.message == 'body boom'


@scenario(
    t'A teardown failure under an unknown {pg["Node ID"]} is ignored',
)
def test_fail_recorded_scenario_ignores_unknown_node_id() -> None:
    with given(t'a {pg["Collector"]} that recorded one {pg["Scenario"].low}'):
        collector = Collector()
        collector.start_scenario(NodeId('test.py::test_x'), 'Test X', 'mod', [])
        recorded = collector.finish_scenario(status='passed')
    with when('a teardown fails under a node id no scenario claimed'):
        collector.fail_recorded_scenario(NodeId('test.py::test_other'), message='boom')
    with then('the recorded scenario is untouched'):
        assert recorded.status == 'passed'
        assert recorded.error is None


@scenario(
    t'A leaf given is {pg["Graft"]("grafted")} as a childless given {pg["Step"].low}',
    story=adopt_pytest_given,
)
def test_graft_leaf_given_appends_childless_given_step() -> None:
    collector = Collector()
    with given(t'an {pg["Active scenario"]} is being recorded'):
        collector.start_scenario('id', 'name', 'mod', [])
    with when(t'a leaf {pg["Graft"]} appends a childless {pg["Step"]}', activity=8):
        collector.graft_leaf_given(_n('the name {text}'))
        recorded = collector.finish_scenario(status='passed')
    with then('the step is a given with no children'):
        leaf = recorded.steps[0]
        assert leaf.phase == 'given'
        assert leaf.narration.text == 'the name {text}'
        assert leaf.children == []


@scenario(
    t'{pg["Graft"]("Grafting")} with an override replaces the root label but '
    t'keeps children',
    story=adopt_pytest_given,
)
def test_graft_recording_override_replaces_root_narration_keeps_children() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    with given(t'a {pg["Fixture recording"]} whose root has a label and a child'):
        root = Step(
            phase='given', narration=_n('original label'), fixture_name='machine'
        )
        root.children.append(Step(phase='given', narration=_n('a recorded child')))
        recording = FixtureRecording(root=root)
    with when(t'a {pg["Graft"]} supplies an override {pg["Narration"]}', activity=8):
        collector.graft_recording(recording, override_narration=_n('a fancy machine'))
        recorded = collector.finish_scenario(status='passed')
    with then('the grafted root shows the override text and keeps its children'):
        grafted = recorded.steps[0]
        assert grafted.narration.text == 'a fancy machine'
        assert [c.narration.text for c in grafted.children] == ['a recorded child']
        # The stored recording's root is untouched (deep copy on graft).
        assert recording.root.narration.text == 'original label'


@scenario(
    t'{pg["Graft"]("Grafting")} with no {pg["Active scenario"].low} is refused',
)
def test_graft_leaf_given_without_scenario_is_refused() -> None:
    with given(t'a collector with no {pg["Active scenario"]}'):
        collector = Collector()
    with (
        when_then(
            t'a leaf {pg["Graft"]} runs',
            'the invariant is asserted rather than silently dropping the step',
        ),
        pytest.raises(AssertionError),
    ):
        collector.graft_leaf_given(_n('orphan'))


def test_graft_recording_without_override_is_unchanged() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    recording = FixtureRecording(root=Step(phase='given', narration=_n('kept label')))
    collector.graft_recording(recording)
    scenario = collector.finish_scenario(status='passed')
    assert scenario.steps[0].narration.text == 'kept label'


def test_capture_step_source_defaults_off() -> None:
    assert Collector().capture_step_source is False


def test_push_step_stores_source_when_given() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    loc = SourceLocation(relpath='tests/t.py', line=3)
    step = collector.push_step('given', _n('a thing'), source=loc)
    assert step.source == loc


def test_push_step_source_defaults_to_none() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    step = collector.push_step('given', _n('a thing'))
    assert step.source is None
