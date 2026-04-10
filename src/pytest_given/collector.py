from __future__ import annotations

from typing import Any

from pytest_given.model import Attachment, ErrorInfo, Scenario, Step


class Collector:
    """Collects step data during test execution.

    Maintains a stack of active steps. Context managers push/pop steps.
    Nested context managers create child steps.
    """

    def __init__(self) -> None:
        self._scenarios: list[Scenario] = []
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []
        self.start_times: dict[str, float] = {}
        self.param_info: dict[str, tuple[list[str], list[Any]]] = {}

    @property
    def active_scenario_id(self) -> str | None:
        if self._current_scenario is None:
            return None
        return self._current_scenario.id

    @property
    def scenarios(self) -> list[Scenario]:
        return self._scenarios

    def start_scenario(
        self,
        scenario_id: str,
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
        """Mark the current scenario as failed with an error."""
        if self._current_scenario is not None:
            self._current_scenario.status = 'failed'
            self._current_scenario.error = ErrorInfo(message=message, diff=diff)

    def fail_current_step(self, message: str, diff: str | None = None) -> None:
        if self._step_stack:
            step = self._step_stack[-1]
            step.status = 'failed'
            step.error = ErrorInfo(message=message, diff=diff)
