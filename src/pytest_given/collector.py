from __future__ import annotations

from contextvars import ContextVar

from pytest_given.model import Attachment, ErrorInfo, NodeId, ParamInfo, Scenario, Step

_collector_var: ContextVar[Collector | None] = ContextVar('collector', default=None)


def set_active_collector(collector: Collector | None) -> None:
    """Set the active collector for the current thread."""
    _collector_var.set(collector)


def get_active_collector() -> Collector | None:
    """Get the active collector for the current thread, or None."""
    return _collector_var.get()


class Collector:
    """Collects step data during test execution.

    Maintains a stack of active steps. Context managers push/pop steps.
    Nested context managers create child steps.
    """

    def __init__(self) -> None:
        self._scenarios: list[Scenario] = []
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []
        self.start_times: dict[NodeId, float] = {}
        self.param_info: ParamInfo = {}

    @property
    def active_scenario_id(self) -> NodeId | None:
        if self._current_scenario is None:
            return None
        return self._current_scenario.id

    @property
    def scenarios(self) -> list[Scenario]:
        return self._scenarios

    @property
    def current_phase(self) -> str | None:
        """The phase of the innermost active step, or None."""
        if self._step_stack:
            return self._step_stack[-1].phase
        return None

    def start_scenario(
        self,
        scenario_id: NodeId,
        name: str,
        module: str,
        tags: list[str],
    ) -> None:
        self._current_scenario = Scenario(
            id=scenario_id,
            name=name,
            module=module,
            tags=tags,
        )
        self._step_stack = []

    def finish_scenario(self, status: str, duration_ms: int) -> Scenario:
        assert self._current_scenario is not None
        self._current_scenario.status = status
        self._current_scenario.duration_ms = duration_ms
        scenario = self._current_scenario
        self._scenarios.append(scenario)
        self._current_scenario = None
        self._step_stack = []
        return scenario

    def push_step(self, phase: str, text: str, source: str | None = None) -> Step:
        if self._step_stack and self._step_stack[-1].phase != phase:
            raise RuntimeError(
                f"Cannot nest '{phase}' inside '{self._step_stack[-1].phase}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        step = Step(phase=phase, text=text, source=source)
        if self._step_stack:
            self._step_stack[-1].children.append(step)
        elif self._current_scenario is not None:
            self._current_scenario.steps.append(step)
        self._step_stack.append(step)
        return step

    def pop_step(self) -> Step | None:
        if not self._step_stack:
            return None
        return self._step_stack.pop()

    def attach(self, label: str, content: str) -> None:
        if self._step_stack:
            self._step_stack[-1].attachments.append(
                Attachment(label=label, content=content)
            )

    def fail_scenario(self, message: str, diff: str | None = None) -> None:
        if self._current_scenario is not None:
            self._current_scenario.status = 'failed'
            self._current_scenario.error = ErrorInfo(message=message, diff=diff)

    def fail_current_step(self, message: str, diff: str | None = None) -> None:
        if self._step_stack:
            step = self._step_stack[-1]
            step.status = 'failed'
            step.error = ErrorInfo(message=message, diff=diff)
