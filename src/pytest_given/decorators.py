from __future__ import annotations

import functools
import types
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from pytest_given.collector import Collector

_phase_stack_var: ContextVar[list[str]] = ContextVar('phase_stack')
_collector_var: ContextVar[Collector | None] = ContextVar('collector', default=None)


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

    def __init__(self, phase: str, text: str) -> None:
        self.phase = phase
        self.text = text

    def __enter__(self) -> Self:
        stack = _get_phase_stack()
        if stack and stack[-1] != self.phase:
            raise RuntimeError(
                f"Cannot nest '{self.phase}' inside '{stack[-1]}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        stack.append(self.phase)
        collector = get_active_collector()
        if collector is not None:
            collector.push_step(self.phase, self.text)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        _get_phase_stack().pop()
        collector = get_active_collector()
        if collector is not None:
            collector.pop_step()

    def __call__(self, func: Any) -> Any:
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


def set_active_collector(collector: Collector | None) -> None:
    """Set the active collector for the current thread."""
    _collector_var.set(collector)


def get_active_collector() -> Collector | None:
    """Get the active collector for the current thread, or None."""
    return _collector_var.get()


def _get_phase_stack() -> list[str]:
    try:
        return _phase_stack_var.get()
    except LookupError:
        stack: list[str] = []
        _phase_stack_var.set(stack)
        return stack
