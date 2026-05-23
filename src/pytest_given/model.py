from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, NamedTuple, NewType

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


@dataclass
class ErrorInfo:
    message: str
    diff: str | None = None


@dataclass
class Step:
    phase: Phase
    text: str
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
    name: str
    module: str
    tags: list[str] = field(default_factory=list)
    status: str = 'passed'
    duration_ms: int = 0
    steps: list[Step] = field(default_factory=list)
    parameters: ParameterTable | None = None
    error: ErrorInfo | None = None


@dataclass
class Metadata:
    project: str
    timestamp: str
    pytest_version: str
    plugin_version: str


@dataclass
class ReportData:
    metadata: Metadata
    scenarios: list[Scenario] = field(default_factory=list)
