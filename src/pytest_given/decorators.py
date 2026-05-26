import functools
import inspect
import json
import types
import warnings
from string import templatelib
from typing import Any, Self

import pytest

from pytest_given.collector import get_active_collector
from pytest_given.errors import PytestGivenError
from pytest_given.model import Phase
from pytest_given.template import Narration, Template, narration_from


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

    def __init__(
        self,
        phase: Phase,
        text: str | templatelib.Template,
    ) -> None:
        self.phase = phase
        self.narration: Narration = narration_from(text)

    def __enter__(self) -> Self:
        collector = get_active_collector()
        if collector is None or collector.state == 'idle':
            if collector is not None and collector.inside_unannotated_test:
                warnings.warn(
                    f"'{self.phase}: {self.narration.text}' recorded in a test "
                    'without @scenario — step will not appear in the report.',
                    pytest.PytestWarning,
                    stacklevel=2,
                )
                return self
            raise PytestGivenError(
                f"Cannot enter '{self.phase}: {self.narration.text}' — "
                'no active scenario or fixture.'
            )
        collector.push_step(self.phase, self.narration)
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
        if self.narration.parts:
            raise PytestGivenError(
                "@given(t'...') / @given(Template(...)) is not allowed on a "
                "fixture; the fixture's argument values aren't in scope at "
                'decoration time. Use a plain string label, or move the step '
                'into the test body.'
            )
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

    def __init__(self, name: str | Template, tags: list[str]) -> None:
        self.name: str | Template = name
        self.tags = tags

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return wrapper


def given(text: str | templatelib.Template) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    _reject_pytest_given_template(text, 'given')
    return StepDescriptor('given', text)


def when(text: str | templatelib.Template) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    _reject_pytest_given_template(text, 'when')
    return StepDescriptor('when', text)


def then(text: str | templatelib.Template) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    _reject_pytest_given_template(text, 'then')
    return StepDescriptor('then', text)


def _reject_pytest_given_template(text: object, fn_name: str) -> None:
    if isinstance(text, Template):
        raise PytestGivenError(
            f'{fn_name}(Template(...)) is not supported in a test body; use a '
            f't-string for dynamic values, or a plain string for static labels. '
            f'Template is for @scenario(...) (and the future Annotated fixture '
            f'form), where deferred substitution from callspec.params is the '
            f'only sensible option.'
        )


def attach(label: str | templatelib.Template, content: object) -> None:
    """Attach data to the current step.

    If *content* is a ``str`` it is stored verbatim.  Any other type is
    serialised as indented JSON.
    """
    if isinstance(label, Template):
        raise PytestGivenError(
            'attach(Template(...)) is not supported; use a t-string (eager) '
            'or a plain string.'
        )
    if isinstance(label, templatelib.Template):
        label = narration_from(label).text
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


def scenario(
    name: str | Template,
    tags: list[str] | None = None,
) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    if isinstance(name, templatelib.Template):
        raise PytestGivenError(
            't-string in @scenario(...) is not supported; @scenario runs at '
            'module-import time, so the parametrize parameters are not yet in '
            'scope. Use pytest_given.Template(...) for parametrized scenario '
            'names, or a plain string for static names.'
        )
    return ScenarioDecorator(name, tags or [])
