from pytest_given.collector import Collector


def test_start_and_finish_scenario() -> None:
    collector = Collector()
    collector.start_scenario('test.py::test_x', 'Test X', 'test_module', ['tag1'])
    scenario = collector.finish_scenario(status='passed', duration_ms=10)
    assert scenario.name == 'Test X'
    assert scenario.status == 'passed'
    assert scenario.duration_ms == 10
    assert scenario.tags == ['tag1']


def test_collect_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', 'a machine')
    collector.pop_step()
    collector.push_step('when', 'I press start')
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 2
    assert scenario.steps[0].phase == 'given'
    assert scenario.steps[0].text == 'a machine'
    assert scenario.steps[1].phase == 'when'


def test_nested_steps() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('when', 'outer')
    collector.push_step('when', 'inner')
    collector.pop_step()
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    assert len(scenario.steps) == 1
    outer = scenario.steps[0]
    assert outer.text == 'outer'
    assert len(outer.children) == 1
    assert outer.children[0].text == 'inner'


def test_attach_to_current_step() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('then', 'check result')
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
    collector.push_step('then', 'should fail')
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
