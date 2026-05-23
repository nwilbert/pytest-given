import pytest

from pytest_given import PytestGivenError


def test_pytest_given_error_is_runtime_error_subclass() -> None:
    assert issubclass(PytestGivenError, RuntimeError)


def test_pytest_given_error_can_be_raised_and_caught() -> None:
    with pytest.raises(PytestGivenError, match='boom'):
        raise PytestGivenError('boom')
