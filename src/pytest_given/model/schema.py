"""The report schema: what is serialized into the JSON report.

The runtime-only carriers capture and grouping pass between themselves live in
`runtime.py`, so what reaches a consumer is answerable from this file alone —
which matters because the serializer is reflective over these dataclasses. The
one exception is a field marked `serde_exclude`, which stays in memory and out
of the JSON; `Step.source` is the only one.
"""

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal, NewType

# A parameter-table column's identity — what the DOM keys on and what a
# placeholder or attachment badge points at. Distinct from the column's display
# `name`, which the two conflate for a `param` column: both are the argname
# there, so nothing but the type keeps a header from being passed as an id.
ColumnId = NewType('ColumnId', str)


def param_id(name: str) -> ColumnId:
    """The column id a parametrize argname takes.

    Both packages that mint one derive it the same way and cannot import each
    other: `capture` points a placeholder at a column it has not seen yet,
    `grouping` creates that column later and has to land on the same id.
    """
    return ColumnId(name)


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

    `name` supplies the `{price}` token and the color-palette entry; `column_id`
    identifies the parameter-table column the DOM keys on. For a `param` column
    the two coincide; a `derived` column's id is generated (`derived:0`), so the
    field is always populated rather than falling back to `name`.
    """

    name: str
    column_id: ColumnId
    format_spec: str = ''
    conversion: str | None = None


# Pytest node ID, e.g. "tests/test_billing.py::test_buy_coffee[1-2-3]"
NodeId = NewType('NodeId', str)


def node_base(node_id: str) -> str:
    """A node id (or a bare function segment) without its parametrize tail:
    ``'f.py::t[1-2]' -> 'f.py::t'``, ``'t[1-2]' -> 't'``. Two cases of one
    parametrized function share this; two different functions never do.

    Lives beside `NodeId` because grouping and report both take node ids apart,
    and neither may import the other. Typed `str` rather than `NodeId`: report
    also applies it to a bare function segment, which is no node id.
    """
    return node_id.split('[', 1)[0]


def case_suffix(node_id: str) -> str:
    """The parametrize tail of a node id, brackets included, or ``''`` when it
    has none: ``'f.py::t[1-2]' -> '[1-2]'``, ``'f.py::t' -> ''``."""
    _, bracket, rest = node_id.partition('[')
    return f'{bracket}{rest}'


TermId = NewType('TermId', str)
ActivityId = NewType('ActivityId', int)
StoryId = NewType('StoryId', str)


@dataclass(frozen=True, kw_only=True)
class NarrationTermRef:
    """Reference to a glossary term — kind resolved via glossary[term_id].kind."""

    term_id: TermId
    display: str
    expression: str = ''


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
    parts: tuple[NarrationPart, ...] = ()


# What a glossary term is: who acts, what is acted on, or the action itself.
# None while a term's kind is still deferred to `infer_glossary_kinds`.
type TermKind = Literal['actor', 'object', 'verb']


@dataclass(frozen=True)
class SourceLocation:
    """A file/line pointer to a scenario's test function.

    `relpath` is POSIX-normalized and relative to pytest's rootdir; `line` is
    1-indexed. Stored on Scenario; rootdir is never serialized to avoid
    leaking local paths.
    """

    relpath: str
    line: int


@dataclass(frozen=True, kw_only=True)
class GlossaryTerm:
    id: TermId
    kind: TermKind | None
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


@dataclass(eq=False)
class Glossary:
    """Mutable container of glossary terms with an id-keyed index.

    Storage and atomic write-through, nothing else: this is what the report
    model carries and what the deserializer rebuilds. The user-facing
    registration API is a subclass in `pytest_given.capture.glossary`, which
    needs the caller's source location — capture's business, not the leaf's.

    `eq=False` keeps identity equality and, with it, hashability. Nothing
    compares two glossaries by value, while several places do need to collect
    the distinct ones a story tree reaches — which is a `frozenset` only if
    this is hashable.
    """

    # Public and mutable because the reflective serializer reads it by name.
    # `register` and the constructor are the only writers, and both keep the
    # index current; rebuild by constructing rather than by mutating in place.
    terms: list[GlossaryTerm] = field(default_factory=list)
    _by_id: dict[TermId, GlossaryTerm] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        self._by_id = {term.id: term for term in self.terms}

    def get(self, key: TermId) -> GlossaryTerm | None:
        return self._by_id.get(key)

    def register(self, term: GlossaryTerm) -> None:
        assert self.get(term.id) is None, f'term id {term.id!r} already registered'
        self.terms.append(term)
        self._by_id[term.id] = term


# Step phase
type Phase = Literal['given', 'when', 'then']

# Canonical Given/When/Then order: the alphabet serde validates against and the
# order the lint reports missing phases in.
PHASES: tuple[Phase, ...] = ('given', 'when', 'then')

# How a scenario or one parametrize case came out. A `str` here would let a
# typo ('pass') through every comparison site. Static checking only: serde's
# `cast` at the JSON boundary is a runtime no-op, so a hand-edited report.json
# can still carry any string — the glyph lookup falls back and every
# `== 'passed'` reads false.
type Status = Literal['passed', 'failed', 'skipped']

# A @pytest.mark.parametrize value as captured for the report: JSON primitives
# pass through; anything else (dates, objects) is coerced to its str() when the
# cell is built, since parametrize values only feed display and the JSON sink
# must serialize them.
type ParamValue = str | int | float | bool | None


type ContentType = Literal['text', 'json']

CONTENT_TYPES: tuple[ContentType, ...] = ('text', 'json')


# What an attachment's payload is called: the plain text an author passes as
# `attach(label, content)`. Display *and* identity — the badge shows it, and it
# is what pairs one case's attachment with another's, since position does not
# survive a case attaching the same labels in a different order. Hence rule 5:
# every case of a grouped scenario must attach the same set of them.
AttachmentLabel = NewType('AttachmentLabel', str)


@dataclass(frozen=True)
class Attachment:
    """A labeled blob bound to the step that was active when it was attached."""

    label: AttachmentLabel
    content: str
    content_type: ContentType = 'text'


@dataclass(frozen=True)
class AttachmentRef:
    """A badge pointing at the parameter-table column that holds the payload.

    Emitted in a grouped parametrized scenario when an attachment's content
    varies across cases. Carrying no `content` is the point: the grouped tree
    then *cannot* speak for the baseline case.
    """

    # The column's display name, not the attachment's own label: a label
    # attached twice gives two columns, and a badge repeating the bare label
    # would point the reader at the wrong one.
    label: str
    content_type: ContentType
    column_id: ColumnId


# What may sit on a grouped step: a real payload, or a pointer to a column.
type StepAttachment = Attachment | AttachmentRef


def location_suffix(location: SourceLocation | None) -> str:
    """The `` (filename:line)`` locator appended to a message about a scenario,
    or ``''`` when there is no source location.

    Lives beside `SourceLocation` because lint and grouping both end their
    messages with it, and neither may import the other.
    """
    if location is None:
        return ''
    return f' ({PurePosixPath(location.relpath).name}:{location.line})'


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


@dataclass(frozen=True)
class ErrorInfo:
    message: str
    frames: list[TracebackFrame] = field(default_factory=list)
    error_tail: str | None = None


@dataclass
class Step:
    phase: Phase
    narration: Narration
    children: list[Step] = field(default_factory=list)
    attachments: list[StepAttachment] = field(default_factory=list)
    activity_ids: tuple[ActivityId, ...] = ()
    fixture_name: str | None = None
    # Anchor of the step's body for the narration lint; captured only when
    # lint is enabled, and never serialized so report artifacts stay
    # byte-identical either way.
    source: SourceLocation | None = field(
        default=None, metadata={'serde_exclude': True}
    )


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

    id: ColumnId
    name: str
    kind: ColumnKind


# One table cell. A `param` cell holds the parametrize value as captured, a
# `derived` cell the already-rendered string, an `attachment` cell the payload
# object — which is also how serde tells the two apart on read. `None` is a
# real parametrize value in a `param` cell and "no value here" in a generated
# one: the column's kind disambiguates, never the cell.
type CellValue = ParamValue | Attachment


@dataclass(frozen=True)
class ParameterCase:
    """One parametrize case: its cells, positionally aligned with the table's
    columns."""

    values: list[CellValue]
    status: Status = 'passed'
    error: ErrorInfo | None = None


@dataclass(frozen=True)
class ParameterTable:
    columns: list[ParameterColumn]
    cases: list[ParameterCase] = field(default_factory=list)

    def cells(self, case: ParameterCase) -> list[tuple[ParameterColumn, CellValue]]:
        """A case's cells paired with the columns they sit under.

        `ParameterCase.values` is positionally aligned with `columns`, and
        `strict=True` is what asserts it. Here rather than in either renderer:
        both walk a row, and when only one of them paired strictly, a short
        `values` raised in Markdown and silently truncated the HTML row.
        """
        return list(zip(self.columns, case.values, strict=True))


@dataclass
class Scenario:
    id: NodeId
    narration: Narration
    module: str
    tags: list[str] = field(default_factory=list)
    status: Status = 'passed'
    duration_ms: int = 0
    steps: list[Step] = field(default_factory=list)
    parameters: ParameterTable | None = None
    error: ErrorInfo | None = None
    skip_reason: str | None = None
    source: SourceLocation | None = None
    story_id: StoryId | None = None
    activity_ids: tuple[ActivityId, ...] = ()


@dataclass(frozen=True)
class Metadata:
    project: str
    timestamp: str
    pytest_version: str
    plugin_version: str
    commit_sha: str | None = None
    # Display name for the report. `project` stays the rootdir name because it
    # also feeds the `{project}` source-link variable; renderers fall back to it
    # when no title is configured.
    title: str | None = None


@dataclass(frozen=True)
class ReportData:
    metadata: Metadata
    scenarios: list[Scenario] = field(default_factory=list)
    glossary: Glossary | None = None
    stories: list[Story] = field(default_factory=list)
