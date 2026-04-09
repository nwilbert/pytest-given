from pytest_given.step_descriptor import StepDescriptor


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
