from __future__ import annotations

import functools
import threading
from typing import Any

# Thread-local stack tracking active phases for cross-phase nesting detection
_phase_stack: threading.local = threading.local()


def _get_phase_stack() -> list[str]:
    if not hasattr(_phase_stack, 'stack'):
        _phase_stack.stack = []
    return _phase_stack.stack


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
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        _get_phase_stack().pop()

    def __call__(self, func: Any) -> Any:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._step_descriptor = self  # type: ignore[attr-defined]
        return wrapper
