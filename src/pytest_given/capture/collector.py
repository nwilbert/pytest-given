"""The recording seam: the `Collector` itself, the ContextVar naming the one
that is active, and the error every step raises when there is none."""

import contextlib
import copy
import time
import warnings
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NoReturn

from ..model import (
    ActivityId,
    Attachment,
    AttachmentLabel,
    ContentType,
    ErrorInfo,
    Narration,
    NodeId,
    Phase,
    PytestGivenError,
    PytestGivenWarning,
    Scenario,
    SourceLocation,
    Status,
    Step,
    Story,
    StoryId,
)
from .source import PACKAGE_ROOT
from .template import Template, narration_from

if TYPE_CHECKING:
    # `steps` imports this module, so the descriptor type can only travel
    # one way at runtime; the annotation still gets the real type.
    from .steps import StepDescriptor


# Lifecycle state of the collector — determines where push_step/attach route,
# and whether it routes anywhere at all. `unannotated` is a test running
# without `@scenario`: steps inside it are legal and do nothing, which is a
# different answer from both `idle` (nothing is running) and `fixture_teardown`
# (something is running but may not record).
type RecordingState = Literal[
    'idle', 'unannotated', 'test', 'fixture_setup', 'fixture_teardown'
]


@dataclass
class FixtureRecording:
    """A captured subtree of steps/attachments for one fixture instance.

    `root` is the labeled step from @given/@when/@then on the fixture; its
    `children` accumulate as the fixture body runs. `stack` mirrors the
    collector's step stack while the recording is active, so nested
    `with given(...)` inside the body works.
    """

    root: Step
    stack: list[Step] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.stack:
            self.stack.append(self.root)


_collector_var: ContextVar[Collector | None] = ContextVar('collector', default=None)


def set_active_collector(collector: Collector | None) -> None:
    _collector_var.set(collector)


def get_active_collector() -> Collector | None:
    return _collector_var.get()


def _no_scenario_error(action: str) -> PytestGivenError:
    """The single wording for "nothing is being recorded right now".

    An idle collector and no collector at all are the same situation to the
    author, so they say the same sentence.
    """
    return PytestGivenError(f'Cannot {action} — no active scenario or fixture.')


def recording_collector(
    kind: Phase | Literal['attach'], subject: str
) -> Collector | None:
    """The collector to record into, or None when the caller should do nothing.

    The one place the "may I record right now?" question is answered, so the
    step `__enter__`, `__exit__`, decorator and `attach` paths cannot drift
    into disagreeing about it. Three outcomes, and only this function knows
    which is which: record into the collector, no-op, or refuse.

    None means an unannotated test, where `with given(...)` and `attach(...)`
    are both legal and both no-ops: not a mistake, just a test with no report
    to appear in. Anywhere else with nothing recording there is no such
    reading, and the call raises.

    Takes the attempt in pieces rather than pre-phrased: recording is the
    common case and needs no sentence at all, so neither message is built on
    the path that succeeds.
    """
    collector = get_active_collector()
    if collector is not None and collector.recording:
        return collector
    if collector is not None and collector.state == 'unannotated':
        warnings.warn(
            _unannotated_warning(kind, subject),
            PytestGivenWarning,
            skip_file_prefixes=(PACKAGE_ROOT,),
        )
        return None
    action = f'attach {subject!r}' if kind == 'attach' else f"enter '{kind}: {subject}'"
    if collector is not None:
        collector.refuse_recording(action)
    raise _no_scenario_error(action)


def _unannotated_warning(kind: Phase | Literal['attach'], subject: str) -> str:
    if kind == 'attach':
        return (
            f"attach('{subject}') called in a test without @scenario — "
            'attachment will not appear in the report.'
        )
    return (
        f"'{kind}: {subject}' recorded in a test without @scenario — "
        'step will not appear in the report.'
    )


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
        self._discovered_stories: dict[StoryId, Story] = {}

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def recording(self) -> bool:
        """Whether a step pushed right now would be recorded — the one answer
        the step `__enter__`, `__exit__` and decorator paths all ask, so they
        cannot drift into disagreeing about it.

        Teardown is *not* recording: a step pushed there raises. Answering True
        for it — as "any state but idle" did — meant this could not be the one
        answer it claims to be, and left the refusal to a second check further
        in.
        """
        return self._state in ('test', 'fixture_setup')

    def enter_unannotated_test(self) -> None:
        """Enter a test running without `@scenario`, where a step is a no-op."""
        self._state = 'unannotated'

    def exit_unannotated_test(self) -> None:
        if self._state == 'unannotated':
            self._state = 'idle'

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

    @contextlib.contextmanager
    def fixture_setup(
        self, recording: FixtureRecording, descriptor: StepDescriptor
    ) -> Iterator[None]:
        """Route recording into `recording` for the duration of the block."""
        with self._routing('fixture_setup', recording, descriptor):
            yield

    @contextlib.contextmanager
    def fixture_teardown(self) -> Iterator[None]:
        """Refuse steps and attachments for the duration of the block.

        Unlike setup, teardown pins no recording: nothing may be recorded from
        it, so there is nowhere for a step to go and no descriptor to match.
        """
        with self._routing('fixture_teardown', None, None):
            yield

    @contextlib.contextmanager
    def _routing(
        self,
        state: RecordingState,
        recording: FixtureRecording | None,
        descriptor: StepDescriptor | None,
    ) -> Iterator[None]:
        """Switch to `state`, and put back whatever that displaced on the way
        out. Nested by construction — a fixture setting up inside another
        fixture's setup restores the outer one's routing when it leaves."""
        previous = (
            self._state,
            self._active_recording,
            self._active_fixture_descriptor,
        )
        self._state = state
        if recording is not None:
            self._active_recording = recording
            self._active_fixture_descriptor = descriptor
        try:
            yield
        finally:
            (
                self._state,
                self._active_recording,
                self._active_fixture_descriptor,
            ) = previous

    def graft_recording(
        self,
        root: Step,
        *,
        override_narration: Narration | None = None,
    ) -> None:
        """Deep-copy a fixture's recorded root into the active scenario's steps.

        When *override_narration* is given (an Annotated label on the fixture
        parameter), it replaces the grafted root's narration; the recorded
        children and attachments are preserved.
        """
        # Grafting runs from the setup hook of an annotated item, which opened
        # the scenario before fixtures ran; nothing closes it until logreport.
        assert self._current_scenario is not None
        grafted = copy.deepcopy(root)
        if override_narration is not None:
            grafted.narration = override_narration
        self._current_scenario.steps.append(grafted)

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
        if not self.recording:
            self.refuse_recording(f"record '{phase}: {narration.text}'")
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
        else:
            # A fixture recording seeds its own stack, so an empty one means
            # 'test' — and `refuse_recording` has ruled out idle and teardown,
            # so that state always has a scenario. Asserted rather than
            # re-tested: the step is already on the stack, so a miss would drop
            # it from the report silently.
            assert self._state == 'test', self._state
            assert self._current_scenario is not None
            self._current_scenario.steps.append(step)
        stack.append(step)
        return step

    def _check_step_activity_scope(
        self,
        phase: Phase,
        activity_ids: tuple[ActivityId, ...],
    ) -> None:
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
        if not self.recording:
            self.refuse_recording(f"attach '{label}'")
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
            Attachment(
                label=AttachmentLabel(label),
                content=content,
                content_type=content_type,
            )
        )

    def refuse_recording(self, action: str) -> NoReturn:
        """Refuse a recording the current state cannot take.

        `action` phrases the attempt ("record 'given: a machine'", "attach
        'log'"), so both refusals name what the author actually wrote. Only
        ever called when `recording` is false, so every path out of here
        raises.
        """
        if self._state == 'fixture_teardown':
            raise PytestGivenError(
                f'Cannot {action} from fixture teardown — teardown is '
                'technical, not narrative.'
            )
        raise _no_scenario_error(action)

    def _target_stack(self) -> list[Step]:
        if self._state == 'fixture_setup' and self._active_recording is not None:
            return self._active_recording.stack
        return self._step_stack

    def records(self, node_id: NodeId) -> bool:
        """Whether this collector holds a scenario for `node_id`.

        True whether it is still open or already finished — the caller asking
        is deciding whether an error is worth the expensive traceback work, and
        that answer does not depend on which.
        """
        return self.active_scenario_id == node_id or node_id in self._scenarios_by_id

    def fail(self, node_id: NodeId, error: ErrorInfo) -> None:
        """Mark `node_id`'s scenario failed, open or finished.

        Both are one operation: a fixture raising past its `yield` errors after
        the call report already ran `finish_scenario`, so there is no active
        scenario left to mark and the run would otherwise report green for
        something pytest counted as an error. Which of the two it is, is this
        collector's business rather than its caller's.

        The first error wins: a call-phase failure is what the reader opened
        the scenario for, and a teardown error after it is the lesser story.
        """
        scenario = self._scenario_for(node_id)
        if scenario is None:
            return
        scenario.status = 'failed'
        if scenario.error is None:
            scenario.error = error

    def _scenario_for(self, node_id: NodeId) -> Scenario | None:
        if self._current_scenario is not None and self._current_scenario.id == node_id:
            return self._current_scenario
        return self._scenarios_by_id.get(node_id)
