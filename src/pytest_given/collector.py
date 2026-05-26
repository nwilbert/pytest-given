import copy
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass

from pytest_given.errors import PytestGivenError
from pytest_given.model import (
    Attachment,
    ContentType,
    ErrorInfo,
    FixtureRecording,
    NodeId,
    ParamInfo,
    Phase,
    RecordingState,
    Scenario,
    Step,
)
from pytest_given.template import Narration, Template, narration_from


@dataclass(frozen=True)
class StateToken:
    """Opaque token returned by enter_* methods; pass to exit_* to restore."""

    previous_state: RecordingState
    previous_recording: FixtureRecording | None


type FixtureInstanceKey = tuple[object, object]

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
        self._state: RecordingState = 'idle'
        self._active_recording: FixtureRecording | None = None
        self._recordings: dict[FixtureInstanceKey, FixtureRecording] = {}
        self.inside_unannotated_test: bool = False

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def active_scenario_id(self) -> NodeId | None:
        if self._current_scenario is None:
            return None
        return self._current_scenario.id

    @property
    def scenarios(self) -> list[Scenario]:
        return self._scenarios

    @property
    def current_phase(self) -> Phase | None:
        """The phase of the innermost active step, or None."""
        stack = self._target_stack()
        if stack:
            return stack[-1].phase
        return None

    def start_scenario(
        self,
        scenario_id: NodeId,
        name: str | Template,
        module: str,
        tags: list[str],
    ) -> None:
        self._current_scenario = Scenario(
            id=scenario_id,
            narration=narration_from(name),
            module=module,
            tags=tags,
        )
        self._step_stack = []
        self._state = 'test'
        self.inside_unannotated_test = False

    def finish_scenario(self, status: str, duration_ms: int) -> Scenario:
        assert self._current_scenario is not None
        self._current_scenario.status = status
        self._current_scenario.duration_ms = duration_ms
        scenario = self._current_scenario
        self._scenarios.append(scenario)
        self._current_scenario = None
        self._step_stack = []
        self._state = 'idle'
        return scenario

    def enter_fixture_setup(self, recording: FixtureRecording) -> StateToken:
        token = StateToken(
            previous_state=self._state,
            previous_recording=self._active_recording,
        )
        self._state = 'fixture_setup'
        self._active_recording = recording
        return token

    def exit_fixture_setup(self, token: StateToken) -> None:
        self._state = token.previous_state
        self._active_recording = token.previous_recording

    def enter_fixture_teardown(self) -> StateToken:
        token = StateToken(
            previous_state=self._state,
            previous_recording=self._active_recording,
        )
        self._state = 'fixture_teardown'
        return token

    def exit_fixture_teardown(self, token: StateToken) -> None:
        self._state = token.previous_state
        self._active_recording = token.previous_recording

    def store_recording(
        self, key: FixtureInstanceKey, recording: FixtureRecording
    ) -> None:
        self._recordings[key] = recording

    def get_recording(self, key: FixtureInstanceKey) -> FixtureRecording | None:
        return self._recordings.get(key)

    def recordings(self) -> Iterator[tuple[FixtureInstanceKey, FixtureRecording]]:
        """(key, recording) pairs in storage (setup) order."""
        return iter(self._recordings.items())

    def drop_recording(self, key: FixtureInstanceKey) -> None:
        """Remove a stored recording. Used to bound memory for function-scoped
        recordings once they've been grafted into their owning scenario."""
        self._recordings.pop(key, None)

    def graft_recording(self, recording: FixtureRecording) -> None:
        """Deep-copy the recording's root into the active scenario's steps."""
        if self._current_scenario is None:
            return
        self._current_scenario.steps.append(copy.deepcopy(recording.root))

    def push_step(self, phase: Phase, narration: Narration) -> Step:
        if self._state == 'idle':
            raise PytestGivenError(
                f"Cannot record '{phase}: {narration.text}' — "
                'no active scenario or fixture.'
            )
        if self._state == 'fixture_teardown':
            raise PytestGivenError(
                f"Cannot record '{phase}: {narration.text}' from fixture "
                'teardown — teardown is technical, not narrative.'
            )
        stack = self._target_stack()
        if stack and stack[-1].phase != phase:
            raise RuntimeError(
                f"Cannot nest '{phase}' inside '{stack[-1].phase}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        step = Step(phase=phase, narration=narration)
        if stack:
            stack[-1].children.append(step)
        elif self._state == 'test' and self._current_scenario is not None:
            self._current_scenario.steps.append(step)
        stack.append(step)
        return step

    def pop_step(self) -> Step | None:
        stack = self._target_stack()
        if not stack:
            return None
        # When recording into a fixture, don't pop the root: it's the labeled
        # parent that the test will graft children under.
        if self._state == 'fixture_setup' and len(stack) == 1:
            return None
        return stack.pop()

    def attach(
        self,
        label: str,
        content: str,
        *,
        content_type: ContentType = 'text',
    ) -> None:
        if self._state == 'idle':
            raise PytestGivenError(
                f"Cannot attach '{label}' — no active scenario or fixture."
            )
        if self._state == 'fixture_teardown':
            raise PytestGivenError(
                f"Cannot attach '{label}' from fixture teardown — "
                'teardown is technical, not narrative.'
            )
        stack = self._target_stack()
        if stack:
            stack[-1].attachments.append(
                Attachment(label=label, content=content, content_type=content_type)
            )

    def _target_stack(self) -> list[Step]:
        """Return the step stack that push/pop/attach should mutate, per state."""
        if self._state == 'fixture_setup' and self._active_recording is not None:
            return self._active_recording.stack
        return self._step_stack

    def fail_scenario(self, message: str, diff: str | None = None) -> None:
        if self._current_scenario is not None:
            self._current_scenario.status = 'failed'
            self._current_scenario.error = ErrorInfo(message=message, diff=diff)

    def fail_current_step(self, message: str, diff: str | None = None) -> None:
        if self._step_stack:
            step = self._step_stack[-1]
            step.status = 'failed'
            step.error = ErrorInfo(message=message, diff=diff)
