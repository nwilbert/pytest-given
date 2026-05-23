import pytest

from pytest_given.collector import Collector, set_active_collector
from pytest_given.decorators import StepDescriptor, attach
from pytest_given.errors import PytestGivenError


def test_context_manager_basic() -> None:
    """StepDescriptor exposes phase and text attributes."""
    desc = StepDescriptor('given', 'a coffee machine')
    assert desc.phase == 'given'
    assert desc.text == 'a coffee machine'


def test_decorator_basic() -> None:
    """StepDescriptor works as a function decorator."""
    desc = StepDescriptor('when', 'inserting money')

    @desc
    def insert_money() -> str:
        return 'done'

    assert insert_money() == 'done'
    assert hasattr(insert_money, '_step_descriptor')
    assert insert_money._step_descriptor.text == 'inserting money'


def test_decorator_preserves_function_metadata() -> None:
    """Decorated function keeps its original name and docstring."""
    desc = StepDescriptor('given', 'a machine')

    @desc
    def my_func() -> None:
        """My docstring."""

    assert my_func.__name__ == 'my_func'
    assert my_func.__doc__ == 'My docstring.'


def test_context_manager_records_step_in_collector() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    set_active_collector(collector)
    try:
        desc = StepDescriptor('given', 'a coffee machine')
        with desc:
            pass
        scenario = collector.finish_scenario(status='passed', duration_ms=0)
        assert len(scenario.steps) == 1
        assert scenario.steps[0].text == 'a coffee machine'
    finally:
        set_active_collector(None)


def test_context_manager_without_collector_raises() -> None:
    """Calling with given(...) when no collector is set is a programming error."""
    set_active_collector(None)
    desc = StepDescriptor('given', 'orphan')
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'), desc:
        pass


def test_context_manager_in_idle_collector_raises() -> None:
    """Collector in idle state still raises."""
    collector = Collector()
    set_active_collector(collector)
    try:
        with (
            pytest.raises(PytestGivenError, match='no active scenario'),
            StepDescriptor('given', 'orphan'),
        ):
            pass
    finally:
        set_active_collector(None)


def test_context_manager_unannotated_test_warns_instead_of_raises() -> None:
    """When inside an unannotated test, soft-warn instead of raising."""
    collector = Collector()
    collector.inside_unannotated_test = True
    set_active_collector(collector)
    try:
        with (
            pytest.warns(pytest.PytestWarning, match='without @scenario'),
            StepDescriptor('given', 'noisy'),
        ):
            pass
    finally:
        set_active_collector(None)


def test_attach_without_collector_raises() -> None:
    set_active_collector(None)
    with pytest.raises(PytestGivenError, match='no active scenario or fixture'):
        attach('label', 'content')


def test_attach_unannotated_test_warns_instead_of_raises() -> None:
    collector = Collector()
    collector.inside_unannotated_test = True
    set_active_collector(collector)
    try:
        with pytest.warns(pytest.PytestWarning, match='without @scenario'):
            attach('label', 'content')
    finally:
        set_active_collector(None)


def test_attach_non_string_content_serializes_as_json() -> None:
    collector = Collector()
    collector.start_scenario('id', 'name', 'mod', [])
    collector.push_step('given', 'a step')
    set_active_collector(collector)
    try:
        attach('payload', {'a': 1, 'b': [2, 3]})
    finally:
        set_active_collector(None)
    collector.pop_step()
    scenario = collector.finish_scenario(status='passed', duration_ms=0)
    att = scenario.steps[-1].attachments[0]
    assert att.label == 'payload'
    assert att.content_type == 'json'
    assert '"a": 1' in att.content
    assert '2' in att.content
    assert '3' in att.content
