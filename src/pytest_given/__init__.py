"""pytest-given: Generate interactive HTML reports from GWT tests."""

from __future__ import annotations

import functools
from typing import Any

from pytest_given.step_descriptor import StepDescriptor, get_active_collector

__all__ = ['attach', 'given', 'scenario', 'then', 'when']


def given(text: str) -> StepDescriptor:
    """Create a Given step (context manager or decorator)."""
    return StepDescriptor('given', text)


def when(text: str) -> StepDescriptor:
    """Create a When step (context manager or decorator)."""
    return StepDescriptor('when', text)


def then(text: str) -> StepDescriptor:
    """Create a Then step (context manager or decorator)."""
    return StepDescriptor('then', text)


def attach(label: str, content: str) -> None:
    """Attach text to the current step."""
    collector = get_active_collector()
    if collector is not None:
        collector.attach(label, content)


def scenario(name: str, tags: list[str] | None = None) -> _ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    return _ScenarioDecorator(name, tags or [])


class _ScenarioDecorator:
    def __init__(self, name: str, tags: list[str]) -> None:
        self.name = name
        self.tags = tags

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._scenario = self  # type: ignore[attr-defined]
        return wrapper
