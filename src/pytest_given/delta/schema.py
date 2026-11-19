"""The delta report's JSON schema."""

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Annotated, Final, Literal

from annotated_types import Ge

from ..model import (
    SCHEMAS_URL,
    ColumnId,
    ColumnKind,
    Glossary,
    GlossaryTerm,
    Metadata,
    NarrationPart,
    NodeId,
    Scenario,
    ScenarioIdentity,
    SchemaDoc,
    StepPath,
    TermId,
    schema_file_name,
)

type DeltaSchemaVersion = Literal[1]
DELTA_SCHEMA_VERSION: Final[DeltaSchemaVersion] = 1
DELTA_SCHEMA_URL: Final = SCHEMAS_URL + schema_file_name('delta', DELTA_SCHEMA_VERSION)

type Change = Literal['added', 'removed', 'changed']
type ChangedPart = Literal[
    'title', 'steps', 'tags', 'status', 'parameters', 'attachments'
]
type Side = Literal['before', 'after']
type ScenarioPairing = Literal['rename-log', 'node-id', 'title']
type CasePairing = Literal['rename-log', 'case-id', 'values']
type ColumnPairing = Literal['name', 'values']
type TermPairing = Literal['rename-log', 'term-id']
type StepChange = Literal['equal', 'modified', 'added', 'removed']
type Mark = Literal['equal', 'removed', 'added']
type LineChange = Literal['equal', 'modified', 'removed', 'added']
type AttachmentChange = Literal['equal', 'changed', 'added', 'removed']
type SuggestionOf = Literal['scenario', 'case', 'term']

# In the order a delta lists its counts: what a release brings, then what it took away.
CHANGES: tuple[Change, ...] = ('added', 'changed', 'removed')
CHANGED_PARTS: tuple[ChangedPart, ...] = (
    'title',
    'steps',
    'tags',
    'status',
    'parameters',
    'attachments',
)
# The mark a side's own words carry in a word diff.
SIDE_MARK: Final[dict[Side, Literal['removed', 'added']]] = {
    'before': 'removed',
    'after': 'added',
}


def on_side[T](side: Side, before: T, after: T) -> T:
    return before if side == 'before' else after


def other_side(side: Side) -> Side:
    return 'after' if side == 'before' else 'before'


def terms_read_the_same(before: GlossaryTerm, after: GlossaryTerm) -> bool:
    """The same name and definition, which a card and a tooltip show."""
    return (before.canonical, before.definition_text or '') == (
        after.canonical,
        after.definition_text or '',
    )


def change_counts(changes: Iterable[Change]) -> dict[Change, int]:
    counted = Counter(changes)
    return {change: counted[change] for change in CHANGES}


_EQUAL_OR_MODIFIED: Final = SchemaDoc('Only on an equal or modified step.')
_FIRST_LINE: Final = SchemaDoc("The first line's index on its side.")
_ATTACHMENT_INDEX: Final = SchemaDoc("Its index among its step's attachments.")


@dataclass(frozen=True, kw_only=True)
class DiffSegment:
    """A run of one mark, in each side's own parts: an equal run both sides',
    which can differ in a space's width or a term ref's display, a removed run
    the before side's, an added run the after side's."""

    mark: Mark
    before: tuple[NarrationPart, ...] = ()
    after: tuple[NarrationPart, ...] = ()


@dataclass(frozen=True, kw_only=True)
class StepDelta:
    change: StepChange
    before: StepPath | None = None
    after: StepPath | None = None
    words: Annotated[
        tuple[DiffSegment, ...], SchemaDoc("A modified step's word diff.")
    ] = ()
    children: Annotated[tuple[StepDelta, ...], _EQUAL_OR_MODIFIED] = ()
    attachments: Annotated[tuple[AttachmentDelta, ...], _EQUAL_OR_MODIFIED] = ()


def walk_step_deltas(deltas: Iterable[StepDelta]) -> Iterator[StepDelta]:
    for delta in deltas:
        yield delta
        yield from walk_step_deltas(delta.children)


@dataclass(frozen=True, kw_only=True)
class TextSegment:
    mark: Mark
    text: str


@dataclass(frozen=True, kw_only=True)
class LineDelta:
    change: LineChange
    before: Annotated[Annotated[int, Ge(0)] | None, _FIRST_LINE] = None
    after: Annotated[Annotated[int, Ge(0)] | None, _FIRST_LINE] = None
    count: Annotated[
        int, Ge(1), SchemaDoc("An equal run's length. 1 for any other change.")
    ] = 1
    words: Annotated[
        tuple[TextSegment, ...], SchemaDoc("A modified line's word diff.")
    ] = ()


@dataclass(frozen=True, kw_only=True)
class AttachmentDelta:
    change: AttachmentChange
    before: Annotated[Annotated[int, Ge(0)] | None, _ATTACHMENT_INDEX] = None
    after: Annotated[Annotated[int, Ge(0)] | None, _ATTACHMENT_INDEX] = None
    lines: Annotated[
        tuple[LineDelta, ...], SchemaDoc('The line diff of a changed pair of payloads.')
    ] = ()


@dataclass(frozen=True, kw_only=True)
class ColumnPair:
    kind: ColumnKind
    before: ColumnId | None = None
    after: ColumnId | None = None
    paired_by: ColumnPairing | None = None

    @property
    def changed(self) -> bool:
        """Unpaired, or renamed."""
        return self.before is None or self.after is None or self.paired_by == 'values'


@dataclass(frozen=True, kw_only=True)
class CellDelta:
    column: Annotated[ColumnId, SchemaDoc("The after side's column ID.")]
    lines: tuple[LineDelta, ...]


@dataclass(frozen=True, kw_only=True)
class CasePair:
    before: NodeId | None = None
    after: NodeId | None = None
    paired_by: CasePairing | None = None
    changed_cells: Annotated[
        tuple[ColumnId, ...],
        SchemaDoc("The after side's IDs of the paired columns whose cells changed."),
    ] = ()
    changed_attachments: tuple[CellDelta, ...] = ()
    id_changed: bool = False
    status_changed: bool = False

    @property
    def changed(self) -> bool:
        return self.parameters_changed or bool(self.changed_attachments)

    @property
    def parameters_changed(self) -> bool:
        """Unpaired, or with a changed cell, ID or status. An unpaired case's
        attachment cells come and go with it."""
        return (
            self.before is None
            or self.after is None
            or bool(self.changed_cells)
            or self.id_changed
            or self.status_changed
        )


@dataclass(frozen=True, kw_only=True)
class ParameterDelta:
    """The alignment of two parameter tables, for a scenario with one on each
    side. Its changes split between the `parameters` and `attachments` changed
    parts, and order alone changes neither."""

    columns: tuple[ColumnPair, ...]
    cases: tuple[CasePair, ...]

    @property
    def column_of(self) -> dict[ColumnId, ColumnId]:
        """Each paired before column ID to its after column ID."""
        return {
            pair.before: pair.after
            for pair in self.columns
            if pair.before is not None and pair.after is not None
        }

    @property
    def changed(self) -> bool:
        return self.parameters_changed or self.attachments_changed

    @property
    def parameters_changed(self) -> bool:
        return any(
            column.changed for column in self.columns if column.kind != 'attachment'
        ) or any(case.parameters_changed for case in self.cases)

    @property
    def attachments_changed(self) -> bool:
        """An attachment column unpaired, or a paired case's attachment cell
        changed. An attachment column never pairs by values."""
        return any(
            column.changed for column in self.columns if column.kind == 'attachment'
        ) or any(case.changed_attachments for case in self.cases)


class _Sided[T]:
    """A listed entry's two sides: an added one has its after side alone, a
    removed one its before side alone, a changed one both."""

    before: T | None
    after: T | None

    def on(self, side: Side) -> T | None:
        return on_side(side, self.before, self.after)

    @property
    def shown_side(self) -> Side:
        """After, or before for a removed entry."""
        return 'before' if self.after is None else 'after'

    @property
    def shown(self) -> T:
        shown = self.on(self.shown_side)
        assert shown is not None
        return shown

    def paired(self) -> tuple[T, T]:
        """Both sides, of a changed entry."""
        assert self.before is not None
        assert self.after is not None
        return self.before, self.after


@dataclass(frozen=True, kw_only=True)
class ScenarioDelta(_Sided[Scenario]):
    change: Change
    before: Scenario | None = None
    after: Scenario | None = None
    paired_by: ScenarioPairing | None = None
    changed_in: tuple[ChangedPart, ...] = ()
    steps: tuple[StepDelta, ...] = ()
    parameters: ParameterDelta | None = None

    @property
    def title_changed(self) -> bool:
        return 'title' in self.changed_in

    @property
    def tags_added(self) -> tuple[str, ...]:
        if self.before is None or self.after is None:
            return ()
        return _tags_missing(self.after.tags, self.before.tags)

    @property
    def tags_removed(self) -> tuple[str, ...]:
        if self.before is None or self.after is None:
            return ()
        return _tags_missing(self.before.tags, self.after.tags)

    @property
    def status_changed(self) -> bool:
        if self.before is None or self.after is None:
            return False
        return self.before.status != self.after.status

    @property
    def reason_changed(self) -> bool:
        if self.before is None or self.after is None:
            return False
        return (self.before.skip_reason, self.before.xfail_reason) != (
            self.after.skip_reason,
            self.after.xfail_reason,
        )


@dataclass(frozen=True, kw_only=True)
class IdentityPair[Id: str]:
    before: Id
    after: Id


@dataclass(frozen=True, kw_only=True)
class Suggestion:
    of: SuggestionOf
    before: str
    after: str
    scenario: Annotated[
        IdentityPair[ScenarioIdentity] | None,
        SchemaDoc("A case suggestion's scenario."),
    ] = None


@dataclass(frozen=True, kw_only=True)
class TermFacts:
    other_forms: tuple[str, ...] = ()
    scenario_count: int = 0


@dataclass(frozen=True, kw_only=True)
class TermDelta(_Sided[GlossaryTerm]):
    change: Change
    before: GlossaryTerm | None = None
    after: GlossaryTerm | None = None
    paired_by: TermPairing | None = None
    before_facts: TermFacts | None = None
    after_facts: TermFacts | None = None
    definition: Annotated[
        tuple[DiffSegment, ...], SchemaDoc("A changed definition's word diff.")
    ] = ()


@dataclass(frozen=True, kw_only=True)
class GlossaryDelta:
    before: Glossary | None = None
    after: Glossary | None = None
    terms: tuple[TermDelta, ...] = ()
    unchanged: tuple[IdentityPair[TermId], ...] = ()


@dataclass(frozen=True, kw_only=True)
class DeltaSide:
    metadata: Metadata
    label: str | None = None
    modules: tuple[str, ...] = ()
    report_file: Annotated[
        str | None,
        SchemaDoc("The compared report's file name, without the directories."),
    ] = None


@dataclass(frozen=True, kw_only=True)
class DeltaMetadata:
    before: DeltaSide
    after: DeltaSide
    plugin_version: str
    timestamp: Annotated[str, SchemaDoc(format='date-time')]
    title: str | None = None
    kind: Literal['delta'] = 'delta'
    schema_version: DeltaSchemaVersion = DELTA_SCHEMA_VERSION


@dataclass(frozen=True, kw_only=True)
class DeltaData:
    metadata: DeltaMetadata
    scenarios: tuple[ScenarioDelta, ...] = ()
    unchanged: tuple[IdentityPair[ScenarioIdentity], ...] = ()
    suggestions: tuple[Suggestion, ...] = ()
    glossary: GlossaryDelta = GlossaryDelta()


def _tags_missing(tags: list[str], other: list[str]) -> tuple[str, ...]:
    """The tags `other` lacks, each once, in `tags`' order."""
    others = set(other)
    return tuple(dict.fromkeys(tag for tag in tags if tag not in others))
