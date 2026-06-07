from dataclasses import dataclass, field
from typing import Any, Literal, NamedTuple, NewType


@dataclass(frozen=True, kw_only=True)
class NarrationLiteral:
    value: str


@dataclass(frozen=True, kw_only=True)
class NarrationValue:
    """A t-string interpolation — value already known at construction time."""

    rendered: str
    expression: str
    format_spec: str = ''
    conversion: str | None = None


@dataclass(frozen=True, kw_only=True)
class NarrationPlaceholder:
    """A deferred placeholder — resolved at render time from a per-case mapping."""

    name: str
    format_spec: str = ''
    conversion: str | None = None


type NarrationPart = NarrationLiteral | NarrationValue | NarrationPlaceholder


@dataclass(frozen=True)
class Narration:
    """The text of a step or scenario, plus optional structured parts.

    `text` is the rendered string for display. `parts` is empty for plain-string
    inputs; non-empty when the source was a t-string or a `Template`, in which
    case the parts reconstruct `text` and carry per-part highlighting metadata.
    """

    text: str
    parts: list[NarrationPart] = field(default_factory=list)


# Pytest node ID, e.g. "tests/test_billing.py::test_buy_coffee[1-2-3]"
NodeId = NewType('NodeId', str)

# Step phase
type Phase = Literal['given', 'when', 'then']

# Lifecycle state of the collector — determines where push_step/attach route.
type RecordingState = Literal['idle', 'test', 'fixture_setup', 'fixture_teardown']

# Arbitrary Python value from @pytest.mark.parametrize (int, str, bool, etc.)
type ParamValue = Any


class ParamSpec(NamedTuple):
    """Parameter names and values for a single parameterized test run."""

    names: list[str]
    values: list[ParamValue]


# Maps node IDs to their parameter specification
type ParamInfo = dict[NodeId, ParamSpec]


type ContentType = Literal['text', 'json']


@dataclass
class Attachment:
    label: str
    content: str
    content_type: ContentType = 'text'


@dataclass(frozen=True)
class SourceLocation:
    """A file/line pointer to a scenario's test function.

    `relpath` is POSIX-normalized and relative to pytest's rootdir; `line` is
    1-indexed. Stored on Scenario; rootdir is never serialized to avoid
    leaking local paths.
    """

    relpath: str
    line: int


@dataclass(frozen=True)
class TracebackFrame:
    """One frame from a parsed pytest short-style traceback.

    `path` is POSIX-normalized (backslashes converted) so renderer logic
    doesn't need per-OS branches. `code` may span multiple lines (caret
    rows, multi-line statements); newlines are preserved verbatim.
    `is_internal` flags pluggy/_pytest/decorator-wrapper frames that the
    UI hides by default.
    """

    path: str
    lineno: int
    func: str
    code: str
    is_internal: bool


@dataclass
class ErrorInfo:
    message: str
    frames: list[TracebackFrame] = field(default_factory=list)
    error_tail: str | None = None


@dataclass
class Step:
    phase: Phase
    narration: Narration
    status: str = 'passed'
    children: list[Step] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    error: ErrorInfo | None = None


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


@dataclass
class ParameterCase:
    values: list[Any]
    status: str = 'passed'
    error: ErrorInfo | None = None


@dataclass
class ParameterTable:
    names: list[str]
    cases: list[ParameterCase] = field(default_factory=list)


@dataclass
class Scenario:
    id: NodeId
    narration: Narration
    module: str
    tags: list[str] = field(default_factory=list)
    status: str = 'passed'
    duration_ms: int = 0
    steps: list[Step] = field(default_factory=list)
    parameters: ParameterTable | None = None
    error: ErrorInfo | None = None
    skip_reason: str | None = None
    source: SourceLocation | None = None


@dataclass
class Metadata:
    project: str
    timestamp: str
    pytest_version: str
    plugin_version: str
    commit_sha: str | None = None


@dataclass
class ReportData:
    metadata: Metadata
    scenarios: list[Scenario] = field(default_factory=list)
