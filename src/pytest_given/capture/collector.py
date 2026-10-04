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
    Attachment,
    AttachmentLabel,
    ContentType,
    ErrorInfo,
    Narration,
    NodeId,
    Phase,
    Pin,
    PytestGivenError,
    PytestGivenWarning,
    Scenario,
    SourceLocation,
    Status,
    Step,
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

    None means an unannotated test, where `with given(...)` and `attach(...)`
    are legal no-ops that warn; anywhere else with nothing recording, the call
    raises. Takes the attempt in pieces so no message is built on the common,
    recording path.
    """
    collector = get_active_collector()
    if collector is None:
        raise _no_scenario_error(_attempt(kind, subject))
    if collector.recording:
        return collector
    if collector.state != 'unannotated':
        collector.refuse_recording(_attempt(kind, subject))
    warnings.warn(
        _unannotated_warning(kind, subject),
        PytestGivenWarning,
        skip_file_prefixes=(PACKAGE_ROOT,),
    )
    return None


def _attempt(kind: Phase | Literal['attach'], subject: str) -> str:
    """The attempt as a refusal names it."""
    return f'attach {subject!r}' if kind == 'attach' else f"enter '{kind}: {subject}'"


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
        self._scenarios: dict[NodeId, Scenario] = {}
        self._current_scenario: Scenario | None = None
        self._step_stack: list[Step] = []
        # When the active scenario's clock was started, or None before it is.
        # A single slot rather than a dict keyed by node id: scenarios never
        # overlap.
        self._started_at: float | None = None
        self._state: RecordingState = 'idle'
        self._active_recording: FixtureRecording | None = None
        self._active_fixture_descriptor: StepDescriptor | None = None

    @property
    def state(self) -> RecordingState:
        return self._state

    @property
    def recording(self) -> bool:
        """Whether a step pushed right now would be recorded. Teardown is
        not: a step pushed there raises."""
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
        return list(self._scenarios.values())

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
        story_ids: tuple[StoryId, ...] = (),
        pins: tuple[Pin, ...] | None = None,
    ) -> None:
        self._current_scenario = Scenario(
            id=scenario_id,
            narration=narration_from(name),
            module=module,
            tags=tags,
            source=source,
            story_ids=story_ids,
            pins=pins,
        )
        self._step_stack = []
        self._started_at = None
        self._state = 'test'

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
        xfail_reason: str | None = None,
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
        self._current_scenario.xfail_reason = xfail_reason
        scenario = self._current_scenario
        self._scenarios[scenario.id] = scenario
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
        label: StepDescriptor | None = None,
    ) -> None:
        """Deep-copy a fixture's recorded root into the active scenario's steps.

        *label*, an Annotated label on the fixture parameter, retells the
        grafted root: its narration replaces the root's, and its pins, when
        given (`()` included), the root's pins. The recorded children and
        attachments are preserved.
        """
        # Grafting runs from the setup hook of an annotated item, which opened
        # the scenario before fixtures ran; nothing closes it until logreport.
        assert self._current_scenario is not None
        grafted = copy.deepcopy(root)
        if label is not None:
            grafted.narration = label.narration
            if label.pins is not None:
                grafted.pins = label.pins
        self._current_scenario.steps.append(grafted)

    def graft_leaf_given(
        self, narration: Narration, *, pins: tuple[Pin, ...] | None = None
    ) -> None:
        """Append a childless `given` step to the active scenario.

        Used for Annotated labels on parametrize values and undecorated /
        built-in fixtures — arrangements with no recorded body.
        """
        assert self._current_scenario is not None
        self._current_scenario.steps.append(
            Step(phase='given', narration=narration, pins=pins)
        )

    def push_step(
        self,
        phase: Phase,
        narration: Narration,
        *,
        pins: tuple[Pin, ...] | None = None,
        source: SourceLocation | None = None,
    ) -> Step:
        if not self.recording:
            self.refuse_recording(f"record '{phase}: {narration.text}'")
        stack = self._target_stack()
        if stack and stack[-1].phase != phase:
            raise PytestGivenError(
                f"Cannot nest '{phase}' inside '{stack[-1].phase}'"
                ' — close the open step first, or call a helper without a '
                'phase decorator'
            )
        step = Step(phase=phase, narration=narration, pins=pins, source=source)
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
        return self.active_scenario_id == node_id or node_id in self._scenarios

    def fail(self, node_id: NodeId, error: ErrorInfo) -> None:
        """Mark `node_id`'s scenario failed, open or finished.

        Both are one operation: a fixture raising past its `yield` errors after
        the call report already ran `finish_scenario`, so there is no active
        scenario left to mark and the run would otherwise report green for
        something pytest counted as an error. Which of the two it is, is this
        collector's business rather than its caller's.

        The first error wins: a call-phase failure is what the reader opened
        the scenario for, and a teardown error after it is the lesser story.
        A failed scenario was not expected to fail, so it keeps no xfail reason.
        """
        scenario = self._scenario_for(node_id)
        assert scenario is not None, node_id
        scenario.status = 'failed'
        scenario.xfail_reason = None
        if scenario.error is None:
            scenario.error = error

    def fail_as_expected(
        self, node_id: NodeId, error: ErrorInfo | None, reason: str | None
    ) -> None:
        """Mark `node_id`'s scenario xfailed, open or finished, for a phase
        pytest counted as an expected failure. `error` is None when the phase
        called `pytest.xfail()` itself.

        A failed scenario stays failed, and takes no reason: after a strict
        xpass pytest still fails the run on the call, whatever it makes of the
        teardown.
        """
        scenario = self._scenario_for(node_id)
        assert scenario is not None, node_id
        if scenario.error is None:
            scenario.error = error
        if scenario.status == 'failed':
            return
        scenario.status = 'xfailed'
        scenario.skip_reason = None
        if scenario.xfail_reason is None:
            scenario.xfail_reason = reason

    def _scenario_for(self, node_id: NodeId) -> Scenario | None:
        if self._current_scenario is not None and self._current_scenario.id == node_id:
            return self._current_scenario
        return self._scenarios.get(node_id)
