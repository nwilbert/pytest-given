from __future__ import annotations

import functools
import threading
from typing import Any

_local: threading.local = threading.local()


def _get_phase_stack() -> list[str]:
    if not hasattr(_local, 'phase_stack'):
        _local.phase_stack = []
    result: list[str] = _local.phase_stack
    return result


def set_active_collector(collector: Any) -> None:
    """Set the active collector for the current thread."""
    _local.collector = collector


def get_active_collector() -> Any:
    """Get the active collector for the current thread, or None."""
    return getattr(_local, 'collector', None)


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

    def __enter__(self) -> StepDescriptor:
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
        exc_tb: Any,
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
