from pytest_given.collector import Collector
from pytest_given.step_descriptor import StepDescriptor, set_active_collector


def test_context_manager_basic() -> None:
    """StepDescriptor works as a context manager."""
    desc = StepDescriptor('given', 'a coffee machine')
    with desc:
        pass
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


def test_cross_phase_nesting_raises() -> None:
    """Nesting a different phase inside another raises an error."""
    import pytest

    outer = StepDescriptor('then', 'result is correct')
    inner = StepDescriptor('given', 'some precondition')
    with pytest.raises(
        RuntimeError,
        match="Cannot nest 'given' inside 'then'",
    ):
        with outer:
            with inner:
                pass


def test_same_phase_nesting_allowed() -> None:
    """Nesting the same phase inside itself is allowed."""
    outer = StepDescriptor('when', 'outer step')
    inner = StepDescriptor('when', 'inner step')
    with outer:
        with inner:
            pass  # no error


def test_sequential_different_phases_allowed() -> None:
    """Different phases at the top level (not nested) is fine."""
    with StepDescriptor('given', 'setup'):
        pass
    with StepDescriptor('when', 'action'):
        pass
    with StepDescriptor('then', 'check'):
        pass


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


def test_context_manager_without_collector_is_noop() -> None:
    """When no collector is active, context manager still works (no recording)."""
    set_active_collector(None)
    desc = StepDescriptor('given', 'a thing')
    with desc:
        pass  # no error
