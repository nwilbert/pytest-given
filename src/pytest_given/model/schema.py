from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NamedTuple, NewType

if TYPE_CHECKING:
    from ..capture.glossary import Actor, DeferredTermHandle, Verb, WorkObject


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
    """A deferred placeholder — resolved at render time from a per-case mapping.

    `name` supplies the `{price}` token and the colour-palette entry; `column_id`
    identifies the parameter-table column the DOM keys on. For a `param` column
    the two coincide; a `derived` column's id is generated (`derived:0`), so the
    field is always populated rather than falling back to `name`.
    """

    name: str
    column_id: str
    format_spec: str = ''
    conversion: str | None = None


# Pytest node ID, e.g. "tests/test_billing.py::test_buy_coffee[1-2-3]"
NodeId = NewType('NodeId', str)

TermId = NewType('TermId', str)
ActivityId = NewType('ActivityId', int)
StoryId = NewType('StoryId', str)


@dataclass(frozen=True, kw_only=True)
class NarrationTermRef:
    """Reference to a glossary term — kind resolved via glossary[term_id].kind."""

    term_id: TermId
    display: str
    expression: str = ''
    param_column: str | None = None


type NarrationPart = (
    NarrationLiteral | NarrationValue | NarrationPlaceholder | NarrationTermRef
)


@dataclass(frozen=True)
class Narration:
    """The text of a step or scenario, plus optional structured parts.

    `text` is the rendered string for display. `parts` is empty for plain-string
    inputs; non-empty when the source was a t-string or a `Template`, in which
    case the parts reconstruct `text` and carry per-part highlighting metadata.
    """

    text: str
    parts: list[NarrationPart] = field(default_factory=list)


@dataclass(frozen=True, kw_only=True)
class GlossaryTerm:
    id: TermId
    kind: Literal['actor', 'object', 'verb'] | None
    canonical: str
    definition: str | None = None
    source: SourceLocation | None = None


@dataclass(frozen=True, kw_only=True)
class ActivityTermRef:
    """Reference to a glossary term in an activity path. Kind resolved via
    glossary[term_id].kind — mirrors NarrationTermRef. Used for both
    code-defined handles and file-glossary handles (whose kind may be
    inferred post-collection)."""

    term_id: TermId
    display: str


@dataclass(frozen=True, kw_only=True)
class ActivityWord:
    """Bare-string connective (preposition, article, etc.). Carries no kind."""

    text: str


type ActivityPart = ActivityTermRef | ActivityWord


@dataclass(frozen=True, kw_only=True)
class ActivityPath:
    parts: tuple[ActivityPart, ...]


@dataclass(frozen=True, kw_only=True)
class Activity:
    id: ActivityId
    paths: tuple[ActivityPath, ...]


@dataclass(frozen=True, kw_only=True)
class Story:
    id: StoryId
    title: str
    activities: tuple[Activity, ...]
    source: SourceLocation | None = None
    _by_id: dict[ActivityId, Activity] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        index: dict[ActivityId, Activity] = {}
        for activity in self.activities:
            index[activity.id] = activity
        object.__setattr__(self, '_by_id', index)

    def __getitem__(self, key: ActivityId) -> Activity:
        return self._by_id[key]

    def get(self, key: ActivityId) -> Activity | None:
        return self._by_id.get(key)


@dataclass
class Glossary:
    """Mutable container of glossary terms with an id-keyed index.

    The user-facing registration methods (`actor` / `work_object` / `verb`)
    live in `pytest_given.capture.glossary`; this class only owns storage
    and atomic write-through. `_register` is the low-level primitive both
    those methods and the deserializer call.
    """

    terms: list[GlossaryTerm] = field(default_factory=list)
    _by_id: dict[TermId, GlossaryTerm] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        for term in self.terms:
            self._by_id[term.id] = term

    def get(self, key: TermId) -> GlossaryTerm | None:
        return self._by_id.get(key)

    def _register(self, term: GlossaryTerm) -> None:
        if term.id in self._by_id:
            raise ValueError(f'term id {term.id!r} already registered')
        self.terms.append(term)
        self._by_id[term.id] = term

    if TYPE_CHECKING:

        def __call__(
            self, name: str, definition: str | None = None
        ) -> DeferredTermHandle: ...
        def __getitem__(self, name: str) -> DeferredTermHandle: ...
        def actor(self, name: str, definition: str | None = None) -> Actor: ...
        def work_object(
            self, name: str, definition: str | None = None
        ) -> WorkObject: ...
        def verb(self, name: str, definition: str | None = None) -> Verb: ...


# Step phase
type Phase = Literal['given', 'when', 'then']

# Lifecycle state of the collector — determines where push_step/attach route.
type RecordingState = Literal['idle', 'test', 'fixture_setup', 'fixture_teardown']

# A @pytest.mark.parametrize value as captured for the report: JSON primitives
# pass through; anything else (dates, objects) is coerced to its str() when the
# cell is built, since parametrize values only feed display and the JSON sink
# must serialize them.
type ParamValue = str | int | float | bool | None

# A parametrize argument as pytest handed it over — an arbitrary object. Kept
# raw on ParamSpec so grouping can re-apply an interpolation's conversion and
# format spec to the value the t-string actually saw (see the rebound-parameter
# rule in the per-case-columns design).
type RawParamValue = object


class ParamSpec(NamedTuple):
    """Parameter names and raw values for a single parametrized test run."""

    names: list[str]
    values: list[RawParamValue]


# Maps node IDs to their parameter specification
type ParamInfo = dict[NodeId, ParamSpec]


type ContentType = Literal['text', 'json']


@dataclass
class Attachment:
    label: str
    content: str
    content_type: ContentType = 'text'


@dataclass(frozen=True)
class AttachmentRef:
    """A badge pointing at the parameter-table column that holds the payload.

    Emitted in a grouped parametrized scenario when an attachment's content
    varies across cases. Carrying no `content` is the point: the grouped tree
    then *cannot* speak for the baseline case.
    """

    label: str
    content_type: ContentType
    column_id: str


# What may sit on a grouped step: a real payload, or a pointer to a column.
type StepAttachment = Attachment | AttachmentRef


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
    attachments: list[StepAttachment] = field(default_factory=list)
    error: ErrorInfo | None = None
    activity_ids: tuple[ActivityId, ...] = ()
    fixture_name: str | None = None
    # Anchor of the step's body for the narration lint; captured only when
    # lint is enabled, and never serialized so report artifacts stay
    # byte-identical either way.
    source: SourceLocation | None = field(
        default=None, metadata={'serde_exclude': True}
    )


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


# Which kind of variance a parameter-table column records.
type ColumnKind = Literal['param', 'derived', 'attachment']


@dataclass(frozen=True, kw_only=True)
class ParameterColumn:
    """One parameter-table column.

    `id` is what the DOM keys on and what a tree placeholder or attachment
    badge points at; `name` is the display header. They coincide for a `param`
    column; generated ids (`derived:0`, `attachment:0`) cannot collide with a
    parametrize name, which is always a Python identifier.
    """

    id: str
    name: str
    kind: ColumnKind


# One table cell. A `param` cell holds the parametrize value as captured, a
# `derived` cell the already-rendered string, an `attachment` cell the payload
# object — which is also how serde tells the two apart on read. `None` marks a
# case with no value for that column.
type CellValue = ParamValue | Attachment


@dataclass
class ParameterCase:
    values: list[CellValue | None]
    status: str = 'passed'
    error: ErrorInfo | None = None


@dataclass
class ParameterTable:
    columns: list[ParameterColumn]
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
    story_id: StoryId | None = None
    activity_ids: tuple[ActivityId, ...] = ()


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
    glossary: Glossary | None = None
    stories: list[Story] = field(default_factory=list)
