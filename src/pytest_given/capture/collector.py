import copy
import time
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
    Status,
    Step,
    Story,
    StoryId,
    TracebackFrame,
)
from .template import Template, narration_from

if TYPE_CHECKING:
    # `steps` imports this module, so the descriptor type can only travel
    # one way at runtime; the annotation still gets the real type.
    from .steps import StepDescriptor


@dataclass(frozen=True)
class StateToken:
    """Opaque token returned by enter_* methods; pass to exit_* to restore."""

    previous_state: RecordingState
    previous_recording: FixtureRecording | None
    previous_fixture_descriptor: StepDescriptor | None


_collector_var: ContextVar[Collector | None] = ContextVar('collector', default=None)


def set_active_collector(collector: Collector | None) -> None:
    _collector_var.set(collector)


def get_active_collector() -> Collector | None:
    return _collector_var.get()


def no_scenario_error(action: str) -> PytestGivenError:
    """The single wording for "nothing is being recorded right now".

    An idle collector and no collector at all are the same situation to the
    author, so they say the same sentence.
    """
    return PytestGivenError(f'Cannot {action} — no active scenario or fixture.')


class Collector:
    """Accumulates a session's scenarios, and the open step stack each one is
    recorded into."""

    def __init__(self, *, capture_step_source: bool = False) -> None:
        # Whether steps record their body's source anchor (narration lint
        # only); off is the zero-cost default — no frame walking happens.
        self.capture_step_source = capture_step_source
        self._scenarios: list[Scenario] = []
        self._scenarios_by_id: dict[NodeId, Scenario] = {}
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []
        # When the active scenario's clock was started, or None before it is.
        # A single slot rather than a dict keyed by node id: scenarios never
        # overlap.
        self._started_at: float | None = None
        self._state: RecordingState = 'idle'
        self._active_recording: FixtureRecording | None = None
        self._active_fixture_descriptor: StepDescriptor | None = None
        self.inside_unannotated_test: bool = False
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
        return list(self._scenarios)

    @property
    def stories(self) -> list[Story]:
        """Every story a scenario declared this session, in discovery order."""
        return list(self._discovered_stories.values())

    @property
    def active_fixture_descriptor(self) -> StepDescriptor | None:
        """The descriptor pinned for the current fixture call, or None.

        Lets a helper-decorator wrapper recognize pytest invoking it as a
        fixture body, whose root step the fixture hook already recorded.
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
        if story is not None:
            self._discovered_stories[story.id] = story

    def begin_timing(self) -> None:
        """Start the active scenario's clock.

        Called once the arrangement pytest owns is done, so the recorded
        duration is the scenario's own and not its fixtures'. Timing lives here
        because the hook that closes a scenario is handed neither a config nor
        an item — this collector is the only thing both ends can see.
        """
        self._started_at = time.monotonic()

    def finish_scenario(
        self,
        status: Status,
        skip_reason: str | None = None,
    ) -> Scenario:
        """Close the active scenario and return it.

        The duration is what `begin_timing` measured — including for a
        scenario that never ran a step, since the setup hookwrapper resumes
        even for a skip or a fixture error. What it times there is hook
        overhead past setup, not the scenario's own work.
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

    def enter_fixture_teardown(self) -> StateToken:
        """Enter the state that refuses steps and attachments.

        Unlike setup, teardown pins no recording: nothing may be recorded from
        it, so there is nowhere for a step to go and no descriptor to match.
        """
        return self._enter('fixture_teardown')

    def exit_fixture(self, token: StateToken) -> None:
        """Put back whatever the matching `enter_*` displaced.

        One exit for both entries: the token carries the whole of what was
        displaced, so leaving setup and leaving teardown are the same act.
        """
        self._state = token.previous_state
        self._active_recording = token.previous_recording
        self._active_fixture_descriptor = token.previous_fixture_descriptor

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
        # Grafting runs from the setup hook of an annotated item, which opened
        # the scenario before fixtures ran; nothing closes it until logreport.
        assert self._current_scenario is not None
        root = copy.deepcopy(recording.root)
        if override_narration is not None:
            root.narration = override_narration
        self._current_scenario.steps.append(root)

    def graft_leaf_given(self, narration: Narration) -> None:
        """Append a childless `given` step to the active scenario.

        Used for Annotated labels on parametrize values and undecorated /
        built-in fixtures — arrangements with no recorded body.
        """
        assert self._current_scenario is not None
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
        elif self._state == 'test':
            # `_require_recordable` has ruled out idle and teardown, so a
            # recordable 'test' state always has a scenario. Asserted rather
            # than re-tested: the step is already on the stack, so a miss
            # would drop it from the report silently.
            assert self._current_scenario is not None
            self._current_scenario.steps.append(step)
        stack.append(step)
        return step

    def _check_step_activity_scope(
        self,
        phase: Phase,
        activity_ids: tuple[ActivityId, ...],
    ) -> None:
        """Validate step activity_ids against the active scenario's story scope."""
        assert self._current_scenario is not None
        story_id = self._current_scenario.story_id
        story = self._discovered_stories[story_id] if story_id is not None else None
        if story is None:
            raise PytestGivenError(
                f'step activity= requires a story on the scenario '
                f'(phase={phase!r}, ids={list(activity_ids)}).'
            )
        scope = self._current_scenario.activity_ids
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
            # rather than dropped: a payload that silently never reaches the
            # report is the one outcome the author cannot notice.
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

        `action` phrases the attempt ("record 'given: a machine'", "attach
        'log'"), so both refusals name what the author actually wrote.
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
            self._current_scenario.error = _error_info(message, frames, error_tail)

    def fail_recorded_scenario(
        self,
        node_id: NodeId,
        message: str,
        frames: list[TracebackFrame] | None = None,
        error_tail: str | None = None,
    ) -> None:
        """Fail a scenario that has already finished — the teardown path.

        A fixture raising past its `yield` errors after the call report ran
        `finish_scenario`, so there is no active scenario left to mark and the
        run would otherwise report green for something pytest counted as an
        error.

        An error already on the scenario is kept: a call-phase failure is what
        the reader opened the scenario for.
        """
        scenario = self._scenarios_by_id[node_id]
        scenario.status = 'failed'
        if scenario.error is None:
            scenario.error = _error_info(message, frames, error_tail)

    def has_scenario(self, node_id: NodeId) -> bool:
        """Whether a finished scenario was recorded for *node_id*."""
        return node_id in self._scenarios_by_id


def _error_info(
    message: str, frames: list[TracebackFrame] | None, error_tail: str | None
) -> ErrorInfo:
    return ErrorInfo(message=message, frames=frames or [], error_tail=error_tail)
