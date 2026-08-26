import copy
import time
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..model import (
    ActivityId,
    Attachment,
    ContentType,
    ErrorInfo,
    FixtureRecording,
    Narration,
    NodeId,
    Phase,
    PytestGivenError,
    RecordingState,
    Scenario,
    SourceLocation,
    Step,
    Story,
    StoryId,
    TracebackFrame,
)
from .template import Template, narration_from

if TYPE_CHECKING:
    # `decorators` imports this module, so the descriptor type can only travel
    # one way at runtime; the annotation still gets the real type.
    from .decorators import StepDescriptor


@dataclass(frozen=True)
class StateToken:
    """Opaque token returned by enter_* methods; pass to exit_* to restore."""

    previous_state: RecordingState
    previous_recording: FixtureRecording | None
    previous_fixture_descriptor: StepDescriptor | None


type FixtureInstanceKey = tuple[object, object]

_collector_var: ContextVar[Collector | None] = ContextVar('collector', default=None)


def set_active_collector(collector: Collector | None) -> None:
    """Set the active collector for the current thread."""
    _collector_var.set(collector)


def get_active_collector() -> Collector | None:
    """Get the active collector for the current thread, or None."""
    return _collector_var.get()


def no_scenario_error(action: str) -> PytestGivenError:
    """The single wording for "nothing is being recorded right now".

    Raised from the collector when a call reaches it in the idle state, and
    from the front doors in `decorators` when there is no collector at all to
    reach — the same situation to the author, so it says the same sentence.
    """
    return PytestGivenError(f'Cannot {action} — no active scenario or fixture.')


class Collector:
    """Collects step data during test execution.

    Maintains a stack of active steps. Context managers push/pop steps.
    Nested context managers create child steps.
    """

    def __init__(self) -> None:
        self._scenarios: list[Scenario] = []
        self._scenarios_by_id: dict[NodeId, Scenario] = {}
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []
        # When the active scenario's clock was started, or None before it is.
        # A single slot rather than a dict keyed by node id: scenarios never
        # overlap, and a dict keeps an entry for every scenario that started
        # but never finished.
        self._started_at: float | None = None
        self._state: RecordingState = 'idle'
        self._active_recording: FixtureRecording | None = None
        self._active_fixture_descriptor: StepDescriptor | None = None
        self._recordings: dict[FixtureInstanceKey, FixtureRecording] = {}
        self.inside_unannotated_test: bool = False
        # Whether steps record their body's source anchor (narration lint
        # only); off is the zero-cost default — no frame walking happens.
        self.capture_step_source: bool = False
        self.active_scenario_story: Story | None = None
        self.active_scenario_activity_ids: tuple[ActivityId, ...] = ()
        self._discovered_stories: dict[StoryId, Story] = {}

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
    def active_fixture_descriptor(self) -> StepDescriptor | None:
        """The descriptor pytest_fixture_setup pinned for the current fixture call.

        Used by StepDescriptor's helper-decorator wrapper to recognize the case
        where pytest is invoking it as a fixture body (in which case
        pytest_fixture_setup has already created the recording's root step from
        the descriptor's narration, and the wrapper must not push a duplicate).
        """
        return self._active_fixture_descriptor

    def start_scenario(
        self,
        scenario_id: NodeId,
        name: str | Template | Narration,
        module: str,
        tags: list[str],
        source: SourceLocation | None = None,
        *,
        story: Story | None = None,
        activity_ids: tuple[ActivityId, ...] = (),
    ) -> None:
        self._current_scenario = Scenario(
            id=scenario_id,
            narration=narration_from(name),
            module=module,
            tags=tags,
            source=source,
            story_id=story.id if story is not None else None,
            activity_ids=activity_ids,
        )
        self._step_stack = []
        self._started_at = None
        self._state = 'test'
        self.inside_unannotated_test = False
        self.active_scenario_story = story
        self.active_scenario_activity_ids = activity_ids
        if story is not None:
            self._discovered_stories[story.id] = story

    def begin_timing(self) -> None:
        """Start the active scenario's clock.

        Called once the arrangement pytest owns is done, so the recorded
        duration is the scenario's own and not its fixtures'. Timing lives here
        rather than in the plugin because the hook that closes a scenario
        (`pytest_runtest_logreport`) is handed neither a config nor an item —
        this collector, reached through the ContextVar, is the only thing both
        ends of the measurement can see.
        """
        self._started_at = time.monotonic()

    def finish_scenario(
        self,
        status: str,
        skip_reason: str | None = None,
    ) -> Scenario:
        """Close the active scenario and return it.

        The duration is what `begin_timing` measured — 0 when the scenario
        never got that far, which is what a setup failure or a mark-based skip
        looks like. Not injectable: the one production caller never passed a
        duration, so an override parameter existed only for tests, and every
        test taking it left `_elapsed_ms` — the code that actually runs —
        unasserted.
        """
        assert self._current_scenario is not None
        self._current_scenario.status = status
        self._current_scenario.duration_ms = self._elapsed_ms()
        self._current_scenario.skip_reason = skip_reason
        scenario = self._current_scenario
        self._scenarios.append(scenario)
        self._scenarios_by_id[scenario.id] = scenario
        self._current_scenario = None
        self._step_stack = []
        self._started_at = None
        self._state = 'idle'
        self.active_scenario_story = None
        self.active_scenario_activity_ids = ()
        return scenario

    def _elapsed_ms(self) -> int:
        """Milliseconds since `begin_timing`, or 0 when it was never called."""
        if self._started_at is None:
            return 0
        return int((time.monotonic() - self._started_at) * 1000)

    def enter_fixture_setup(
        self,
        recording: FixtureRecording,
        descriptor: StepDescriptor | None = None,
    ) -> StateToken:
        """Route recording into `recording` until the matching exit."""
        return self._enter('fixture_setup', recording=recording, descriptor=descriptor)

    def exit_fixture_setup(self, token: StateToken) -> None:
        self._exit(token)

    def enter_fixture_teardown(self) -> StateToken:
        """Enter the state that refuses steps and attachments.

        Unlike setup, teardown pins no recording: nothing may be recorded from
        it, so there is nowhere for a step to go and no descriptor to match.
        """
        return self._enter('fixture_teardown')

    def exit_fixture_teardown(self, token: StateToken) -> None:
        self._exit(token)

    def _enter(
        self,
        state: RecordingState,
        recording: FixtureRecording | None = None,
        descriptor: StepDescriptor | None = None,
    ) -> StateToken:
        """Switch to `state`, returning the token that puts back what it
        displaced. Nested by construction — a fixture setting up inside another
        fixture's setup restores the outer one's routing on the way out."""
        token = StateToken(
            previous_state=self._state,
            previous_recording=self._active_recording,
            previous_fixture_descriptor=self._active_fixture_descriptor,
        )
        self._state = state
        if recording is not None:
            self._active_recording = recording
            self._active_fixture_descriptor = descriptor
        return token

    def _exit(self, token: StateToken) -> None:
        self._state = token.previous_state
        self._active_recording = token.previous_recording
        self._active_fixture_descriptor = token.previous_fixture_descriptor

    def store_recording(
        self, key: FixtureInstanceKey, recording: FixtureRecording
    ) -> None:
        self._recordings[key] = recording

    def recordings(self) -> Iterator[tuple[FixtureInstanceKey, FixtureRecording]]:
        """(key, recording) pairs in storage (setup) order."""
        return iter(self._recordings.items())

    def drop_recording(self, key: FixtureInstanceKey) -> None:
        self._recordings.pop(key, None)

    def graft_recording(
        self,
        recording: FixtureRecording,
        *,
        override_narration: Narration | None = None,
    ) -> None:
        """Deep-copy the recording's root into the active scenario's steps.

        When *override_narration* is given (an Annotated label on the fixture
        parameter), it replaces the grafted root's narration; the recorded
        children and attachments are preserved.
        """
        if self._current_scenario is None:
            return
        root = copy.deepcopy(recording.root)
        if override_narration is not None:
            root.narration = override_narration
        self._current_scenario.steps.append(root)

    def graft_leaf_given(self, narration: Narration) -> None:
        """Append a childless `given` step to the active scenario.

        Used for Annotated labels on parametrize values and undecorated /
        built-in fixtures — arrangements with no recorded body.
        """
        if self._current_scenario is None:
            return
        self._current_scenario.steps.append(Step(phase='given', narration=narration))

    def push_step(
        self,
        phase: Phase,
        narration: Narration,
        *,
        activity_ids: tuple[ActivityId, ...] = (),
        source: SourceLocation | None = None,
    ) -> Step:
        self._require_recordable(f"record '{phase}: {narration.text}'")
        stack = self._target_stack()
        if stack and stack[-1].phase != phase:
            raise PytestGivenError(
                f"Cannot nest '{phase}' inside '{stack[-1].phase}'"
                ' — restructure your test or use a phase-neutral helper'
            )
        if activity_ids:
            self._check_step_activity_scope(phase, activity_ids)
        step = Step(
            phase=phase, narration=narration, activity_ids=activity_ids, source=source
        )
        if stack:
            stack[-1].children.append(step)
        elif self._state == 'test' and self._current_scenario is not None:
            self._current_scenario.steps.append(step)
        stack.append(step)
        return step

    def _check_step_activity_scope(
        self,
        phase: Phase,
        activity_ids: tuple[ActivityId, ...],
    ) -> None:
        """Validate step activity_ids against the active scenario's story scope.

        Lives on Collector (not on StepDescriptor) so every push_step entry
        point — context manager, helper wrapper, future fixture grafting —
        gets the check by construction.
        """
        story = self.active_scenario_story
        if story is None:
            raise PytestGivenError(
                f'step activity= requires a story on the scenario '
                f'(phase={phase!r}, ids={list(activity_ids)}).'
            )
        scope = self.active_scenario_activity_ids
        valid = scope or tuple(a.id for a in story.activities)
        valid_set = set(valid)
        for aid in activity_ids:
            if aid in valid_set:
                continue
            if scope:
                raise PytestGivenError(
                    f'step activity={aid} outside scenario scope '
                    f'(scenario activities={sorted(scope)}).'
                )
            raise PytestGivenError(
                f'step activity={aid} not in story {story.title!r} '
                f'(valid: {sorted(valid_set)}).'
            )

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
        self._require_recordable(f"attach '{label}'")
        stack = self._target_stack()
        if not stack:
            # An attachment binds to the step being recorded, so a test body
            # that attaches before opening one has nowhere to put it. Refused
            # rather than dropped: every other misuse of this API raises, and a
            # payload that silently never reaches the report is the one outcome
            # the author cannot notice.
            raise PytestGivenError(
                f"Cannot attach '{label}' — no step is open. An attachment "
                'binds to the step being recorded; move the call inside a '
                'given/when/then block.'
            )
        stack[-1].attachments.append(
            Attachment(label=label, content=content, content_type=content_type)
        )

    def _require_recordable(self, action: str) -> None:
        """Refuse a recording the current state cannot take.

        Two refusals, and they say different things: idle means nothing is
        being recorded at all, while fixture teardown *is* recording-capable
        and simply has nothing narrative to say. `action` phrases the attempt
        ("record 'given: a machine'", "attach 'log'"), so both messages name
        what the author actually wrote.
        """
        if self._state == 'idle':
            raise no_scenario_error(action)
        if self._state == 'fixture_teardown':
            raise PytestGivenError(
                f'Cannot {action} from fixture teardown — teardown is '
                'technical, not narrative.'
            )

    def _target_stack(self) -> list[Step]:
        """Return the step stack that push/pop/attach should mutate, per state."""
        if self._state == 'fixture_setup' and self._active_recording is not None:
            return self._active_recording.stack
        return self._step_stack

    def fail_scenario(
        self,
        message: str,
        frames: list[TracebackFrame] | None = None,
        error_tail: str | None = None,
    ) -> None:
        if self._current_scenario is not None:
            self._current_scenario.status = 'failed'
            self._current_scenario.error = ErrorInfo(
                message=message,
                frames=frames or [],
                error_tail=error_tail,
            )

    def fail_recorded_scenario(
        self,
        node_id: NodeId,
        message: str,
        frames: list[TracebackFrame] | None = None,
        error_tail: str | None = None,
    ) -> None:
        """Fail a scenario that has already finished — the teardown path.

        A fixture raising past its `yield` errors after the call report ran
        `finish_scenario`, so there is no active scenario left for
        `fail_scenario` to mark and the run would otherwise report green for
        something pytest counted as an error.

        An error already on the scenario is kept: a call-phase failure is what
        the reader opened the scenario for, and pytest reports the teardown
        error separately either way. Unknown ids (an unannotated test, a
        finalizer attributed to a non-scenario item) are ignored.
        """
        scenario = self._scenarios_by_id.get(node_id)
        if scenario is None:
            return
        scenario.status = 'failed'
        if scenario.error is None:
            scenario.error = ErrorInfo(
                message=message,
                frames=frames or [],
                error_tail=error_tail,
            )
