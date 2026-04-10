"""pytest-given: Generate interactive HTML reports from GWT tests."""

from __future__ import annotations

from pytest_given.decorators import (
    ScenarioDecorator,
    StepDescriptor,
    get_active_collector,
)

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


def scenario(name: str, tags: list[str] | None = None) -> ScenarioDecorator:
    """Mark a test for inclusion in the report."""
    return ScenarioDecorator(name, tags or [])
