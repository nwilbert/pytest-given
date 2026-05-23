from __future__ import annotations

import functools
import inspect
import json
import types
import warnings
from typing import Any, Self

import pytest

from pytest_given.collector import get_active_collector
from pytest_given.errors import PytestGivenError
from pytest_given.model import Phase


class StepDescriptor:
    """Dual context-manager / decorator for Given/When/Then steps.

    As a context manager:
        with given("a coffee machine"):
            ...

    As a decorator:
        @given("a coffee machine")
        def coffee_machine():
            ...
    """

    def __init__(self, phase: Phase, text: str) -> None:
        self.phase = phase
        self.text = text

    def __enter__(self) -> Self:
        collector = get_active_collector()
        if collector is None or collector.state == 'idle':
            if collector is not None and collector.inside_unannotated_test:
                warnings.warn(
                    f"'{self.phase}: {self.text}' recorded in a test without "
                    '@scenario — step will not appear in the report.',
                    pytest.PytestWarning,
                    stacklevel=2,
                )
                return self
            raise PytestGivenError(
                f"Cannot enter '{self.phase}: {self.text}' — "
                'no active scenario or fixture.'
            )
        collector.push_step(self.phase, self.text)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        collector = get_active_collector()
        if collector is None or collector.inside_unannotated_test:
            return
        collector.pop_step()

    def __call__(self, func: Any) -> Any:
        if inspect.isgeneratorfunction(func):

            @functools.wraps(func)
            def gen_wrapper(*args: Any, **kwargs: Any) -> Any:
                yield from func(*args, **kwargs)

            gen_wrapper._step_descriptor = self  # type: ignore[attr-defined]
            return gen_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return wrapper


class ScenarioDecorator:
    """Decorator that marks a test for inclusion in the report."""

    def __init__(self, name: str, tags: list[str]) -> None:
        self.name = name
        self.tags = tags

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return wrapper


def given(text: str) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text)


def when(text: str) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text)


def then(text: str) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    return StepDescriptor('then', text)


def attach(label: str, content: object) -> None:
    """Attach data to the current step.

    If *content* is a ``str`` it is stored verbatim.  Any other type is
    serialised as indented JSON.
    """
    collector = get_active_collector()
    if collector is None or collector.state == 'idle':
        if collector is not None and collector.inside_unannotated_test:
            warnings.warn(
                f"attach('{label}') called in a test without @scenario — "
                'attachment will not appear in the report.',
                pytest.PytestWarning,
                stacklevel=2,
            )
            return
        raise PytestGivenError(
            f"Cannot attach '{label}' — no active scenario or fixture."
        )
    if isinstance(content, str):
        collector.attach(label, content, content_type='text')
    else:
        collector.attach(
            label,
            json.dumps(content, indent=2, default=str),
            content_type='json',
        )


def scenario(name: str, tags: list[str] | None = None) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    return ScenarioDecorator(name, tags or [])
