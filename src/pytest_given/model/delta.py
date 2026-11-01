"""The delta report's JSON schema.

`report/` renders a delta from these dataclasses without importing the `delta/`
package that computes it, so the shape lives in the leaf both depend on.
"""

from dataclasses import dataclass
from typing import Final, Literal

from .schema import (
    ColumnId,
    Glossary,
    GlossaryTerm,
    Metadata,
    NarrationPart,
    NodeId,
    Scenario,
)
from .steps import StepPath

DELTA_SCHEMA_VERSION: Final = 1

type Change = Literal['added', 'removed', 'changed']
type Side = Literal['before', 'after']
type ScenarioPairing = Literal['rename-log', 'node-id', 'title']
type CasePairing = Literal['rename-log', 'case-id', 'values']
type ColumnPairing = Literal['name', 'values']
type TermPairing = Literal['rename-log', 'term-id']
type StepChange = Literal['equal', 'modified', 'added', 'removed']
type Mark = Literal['equal', 'removed', 'added']
type SuggestionOf = Literal['scenario', 'case', 'term']

# In the order a delta lists its counts: what a release brings, then what it took away.
CHANGES: tuple[Change, ...] = ('added', 'changed', 'removed')
SCENARIO_PAIRINGS: tuple[ScenarioPairing, ...] = ('rename-log', 'node-id', 'title')
CASE_PAIRINGS: tuple[CasePairing, ...] = ('rename-log', 'case-id', 'values')
COLUMN_PAIRINGS: tuple[ColumnPairing, ...] = ('name', 'values')
TERM_PAIRINGS: tuple[TermPairing, ...] = ('rename-log', 'term-id')
STEP_CHANGES: tuple[StepChange, ...] = ('equal', 'modified', 'added', 'removed')
MARKS: tuple[Mark, ...] = ('equal', 'removed', 'added')
SUGGESTION_OFS: tuple[SuggestionOf, ...] = ('scenario', 'case', 'term')
# The mark a side's own words carry in a word diff.
SIDE_MARK: Final[dict[Side, Literal['removed', 'added']]] = {
    'before': 'removed',
    'after': 'added',
}


def on_side[T](side: Side, before: T, after: T) -> T:
    return before if side == 'before' else after


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
    words: tuple[DiffSegment, ...] = ()  # modified only
    children: tuple[StepDelta, ...] = ()  # equal and modified only


@dataclass(frozen=True, kw_only=True)
class ColumnPair:
    before: ColumnId | None = None
    after: ColumnId | None = None
    paired_by: ColumnPairing | None = None


@dataclass(frozen=True, kw_only=True)
class CasePair:
    before: NodeId | None = None
    after: NodeId | None = None
    paired_by: CasePairing | None = None
    changed_cells: tuple[ColumnId, ...] = ()  # after ids of paired columns
    id_changed: bool = False
    status_changed: bool = False

    @property
    def changed(self) -> bool:
        """Whether the case reads otherwise on the two sides: unpaired, or
        with a changed cell, ID or status."""
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
    side. Attachment columns are left out."""

    columns: tuple[ColumnPair, ...]
    cases: tuple[CasePair, ...]

    @property
    def changed(self) -> bool:
        """Whether anything but order differs: an unpaired or renamed column,
        an unpaired case, or a paired case with a changed cell, ID or status."""
        return any(
            column.before is None
            or column.after is None
            or column.paired_by == 'values'
            for column in self.columns
        ) or any(case.changed for case in self.cases)


@dataclass(frozen=True, kw_only=True)
class ScenarioDelta:
    change: Change
    before: Scenario | None = None
    after: Scenario | None = None
    paired_by: ScenarioPairing | None = None
    title_changed: bool = False
    steps: tuple[StepDelta, ...] = ()
    parameters: ParameterDelta | None = None

    def on(self, side: Side) -> Scenario | None:
        return on_side(side, self.before, self.after)

    @property
    def shown_side(self) -> Side:
        """After, or before for a removed scenario."""
        return 'before' if self.after is None else 'after'

    @property
    def shown(self) -> Scenario:
        shown = self.on(self.shown_side)
        assert shown is not None
        return shown

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
class IdentityPair:
    before: str
    after: str


@dataclass(frozen=True, kw_only=True)
class Suggestion:
    of: SuggestionOf
    before: str
    after: str
    scenario: IdentityPair | None = None  # for a case


@dataclass(frozen=True, kw_only=True)
class TermFacts:
    other_forms: tuple[str, ...] = ()
    scenario_count: int = 0


@dataclass(frozen=True, kw_only=True)
class TermDelta:
    change: Change
    before: GlossaryTerm | None = None
    after: GlossaryTerm | None = None
    paired_by: TermPairing | None = None
    before_facts: TermFacts | None = None
    after_facts: TermFacts | None = None
    definition: tuple[DiffSegment, ...] = ()  # a changed definition's word diff

    def on(self, side: Side) -> GlossaryTerm | None:
        return on_side(side, self.before, self.after)

    @property
    def shown_side(self) -> Side:
        """After, or before for a removed term."""
        return 'before' if self.after is None else 'after'

    @property
    def shown(self) -> GlossaryTerm:
        shown = self.on(self.shown_side)
        assert shown is not None
        return shown


@dataclass(frozen=True, kw_only=True)
class GlossaryDelta:
    before: Glossary | None = None
    after: Glossary | None = None
    terms: tuple[TermDelta, ...] = ()
    unchanged: tuple[IdentityPair, ...] = ()


@dataclass(frozen=True, kw_only=True)
class DeltaSide:
    metadata: Metadata
    label: str | None = None
    modules: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class DeltaMetadata:
    before: DeltaSide
    after: DeltaSide
    plugin_version: str
    timestamp: str
    kind: Literal['delta'] = 'delta'
    schema_version: int = DELTA_SCHEMA_VERSION


@dataclass(frozen=True, kw_only=True)
class DeltaData:
    metadata: DeltaMetadata
    scenarios: tuple[ScenarioDelta, ...] = ()
    unchanged: tuple[IdentityPair, ...] = ()
    suggestions: tuple[Suggestion, ...] = ()
    glossary: GlossaryDelta = GlossaryDelta()


def _tags_missing(tags: list[str], other: list[str]) -> tuple[str, ...]:
    """The tags `other` lacks, each once, in `tags`' order."""
    others = set(other)
    return tuple(dict.fromkeys(tag for tag in tags if tag not in others))
