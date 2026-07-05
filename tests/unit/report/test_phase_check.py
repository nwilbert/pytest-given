from pytest_given.model import Narration, NodeId, Scenario, Step
from pytest_given.report.phase_check import (
    PhaseViolation,
    find_violations,
    is_ignored,
    missing_phases,
    scenario_phases,
)


def _step(phase, children=()):
    return Step(phase=phase, narration=Narration(text=phase), children=list(children))


def _scenario(node_id, phases, *, status='passed', steps=None):
    return Scenario(
        id=NodeId(node_id),
        narration=Narration(text='S'),
        module='m',
        status=status,
        steps=steps if steps is not None else [_step(p) for p in phases],
    )


def test_scenario_phases_collects_distinct_phases():
    scenario = _scenario('m.py::t', ['given', 'when', 'when', 'then'])
    assert scenario_phases(scenario) == {'given', 'when', 'then'}


def test_scenario_phases_walks_nested_steps():
    # a `then` present only as a child of a `when` still counts
    nested = [_step('when', children=[_step('then')])]
    scenario = _scenario('m.py::t', [], steps=nested)
    assert scenario_phases(scenario) == {'when', 'then'}


def test_missing_phases_complete_returns_empty():
    scenario = _scenario('m.py::t', ['given', 'when', 'then'])
    assert missing_phases(scenario) == ()


def test_missing_phases_reports_missing_when():
    scenario = _scenario('m.py::t', ['given', 'then'])
    assert missing_phases(scenario) == ('when',)


def test_missing_phases_reports_missing_given():
    scenario = _scenario('m.py::t', ['when', 'then'])
    assert missing_phases(scenario) == ('given',)


def test_missing_phases_is_in_canonical_gwt_order():
    scenario = _scenario('m.py::t', ['given'])
    assert missing_phases(scenario) == ('when', 'then')


def test_is_ignored_matches_file_glob():
    assert is_ignored('tests/foo.py::test_a', ['tests/foo.py::*'])


def test_is_ignored_matches_name_convention_glob():
    assert is_ignored('tests/foo.py::test_a_raises', ['*::test_*_raises'])


def test_is_ignored_matches_exact_node_id():
    assert is_ignored('tests/foo.py::test_a', ['tests/foo.py::test_a'])


def test_is_ignored_returns_false_when_no_pattern_matches():
    assert not is_ignored('tests/foo.py::test_a', ['tests/other.py::*'])


def test_find_violations_reports_incomplete_passed_scenario():
    scenarios = [_scenario('m.py::t', ['given', 'then'])]
    assert find_violations(scenarios, []) == [
        PhaseViolation(node_id=NodeId('m.py::t'), missing=('when',))
    ]


def test_find_violations_ignores_complete_scenario():
    scenarios = [_scenario('m.py::t', ['given', 'when', 'then'])]
    assert find_violations(scenarios, []) == []


def test_find_violations_skips_non_passed_scenarios():
    scenarios = [_scenario('m.py::t', ['given', 'then'], status='failed')]
    assert find_violations(scenarios, []) == []


def test_find_violations_skips_ignored_node_ids():
    scenarios = [_scenario('m.py::t', ['given', 'then'])]
    assert find_violations(scenarios, ['m.py::*']) == []
