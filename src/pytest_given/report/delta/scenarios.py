"""The delta page's listed scenarios: what each one shows of its two sides,
its steps and tables lined up side by side."""

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

from ...model import (
    SIDE_MARK,
    AttachmentRef,
    CasePair,
    CellValue,
    Change,
    ColumnId,
    DeltaData,
    Narration,
    NarrationPart,
    NarrationPlaceholder,
    ParameterCase,
    ParameterColumn,
    ParameterDelta,
    ParameterTable,
    Scenario,
    ScenarioDelta,
    Side,
    Step,
    StepDelta,
    on_side,
)
from ..html_renderer import column_phase_blocks, repr_columns, shown_text
from ..slugs import build_scenario_slug_index
from .steps import BlockKey, StepsView, block_keys, steps_view

type ColumnChange = Literal['added', 'removed']

# Prefixes a removed scenario's slug and a removed term's card ID. A term ID
# never holds a `:`, nor a slug's leading file or directory name.
REMOVED = 'removed:'

# Prefixes a column only the before side has, where the page keys it: the after
# side can hold another column of the same ID.
_BEFORE_ONLY_KEY = 'before:'


@dataclass(frozen=True)
class ReasonRow:
    """A skip or xfail reason as the row shows it, with the before side's
    reason it replaced, if any."""

    status: Literal['skipped', 'xfailed']
    label: str
    reason: str | None
    was: str | None


@dataclass(frozen=True)
class TableColumn:
    column: ParameterColumn
    # A column only this side's table has. Attachment columns stay unmarked.
    change: ColumnChange | None = None
    was: str | None = None  # a renamed column's before name, on the after side


@dataclass(frozen=True)
class TableSide:
    side: Side
    parameters: ParameterTable
    columns: list[TableColumn]
    # Each column's phase block, keyed as the side's steps key theirs.
    column_blocks: dict[ColumnId, BlockKey]
    repr_columns: set[ColumnId]

    @property
    def mark(self) -> Literal['removed', 'added']:
        """The mark a changed cell takes here: the old value faces the new one."""
        return SIDE_MARK[self.side]

    def cells(
        self, case: ParameterCase, pair: CasePair
    ) -> Iterator[
        tuple[ParameterColumn, CellValue, BlockKey | None, ColumnChange | None]
    ]:
        """A case's cells, each with its column's phase block and its change."""
        for (column, value), shown in zip(
            self.parameters.cells(case), self.columns, strict=True
        ):
            changed = shown.change == 'added' or column.id in pair.changed_cells
            yield (
                column,
                value,
                self.column_blocks.get(column.id),
                self.mark if changed else None,
            )


@dataclass(frozen=True)
class TableRow:
    """A case's line across the tables, None on a side without the case."""

    before_case: ParameterCase | None
    after_case: ParameterCase | None
    pair: CasePair

    @property
    def change(self) -> Change | None:
        if self.before_case is None:
            return 'added'
        if self.after_case is None:
            return 'removed'
        return 'changed' if self.pair.changed else None

    def case(self, side: Side) -> ParameterCase | None:
        return on_side(side, self.before_case, self.after_case)


@dataclass(frozen=True)
class TableView:
    """A changed scenario's parameter tables: a side for each table there is,
    the rows lined up by case in the after order."""

    sides: list[TableSide]
    rows: list[TableRow]


@dataclass(frozen=True)
class ListedScenario:
    # A changed scenario's before side carries its columns as the page keys
    # them (`_BeforeKeys`).
    delta: ScenarioDelta
    # Prefixed `REMOVED` for a removed scenario, so a removed and an added
    # scenario sharing one node ID still have a slug each.
    slug: str

    @property
    def change(self) -> Change:
        return self.delta.change

    @property
    def side(self) -> Side:
        return self.delta.shown_side

    @property
    def shown(self) -> Scenario:
        return self.delta.shown

    @property
    def fragment(self) -> str:
        return f'scenario={self.slug}'

    @cached_property
    def title_text(self) -> str:
        return shown_text(self.shown.narration)

    @cached_property
    def steps(self) -> StepsView | None:
        """A changed scenario's steps side by side; None for an added or
        removed one, whose steps read unmarked."""
        if self.change != 'changed':
            return None
        return steps_view(self.delta, self._block_keys)

    @cached_property
    def table(self) -> TableView | None:
        """A changed scenario's tables when they changed; None where a table
        reads unmarked, as in the report, or there is none."""
        if self.change != 'changed':
            return None
        return _table_view(self.delta, self._block_keys)

    @property
    def has_body(self) -> bool:
        before = self.delta.before
        shown = self.shown
        return bool(
            shown.steps
            or (before and before.steps)
            or shown.parameters
            or self.table
            or shown.error
            or self.reasons
        )

    @property
    def reasons(self) -> list[ReasonRow]:
        replaced = self.delta.before if self.delta.reason_changed else None
        rows = [
            _reason_row(
                'skipped',
                'Skipped:',
                self.shown.skip_reason,
                replaced.skip_reason if replaced else None,
            ),
            _reason_row(
                'xfailed',
                'Expected to fail:',
                self.shown.xfail_reason,
                replaced.xfail_reason if replaced else None,
            ),
        ]
        return [row for row in rows if row.reason or row.was]

    @cached_property
    def _block_keys(self) -> dict[Side, list[BlockKey]]:
        return block_keys(self.delta)


def listed_scenarios(delta: DeltaData) -> list[ListedScenario]:
    # Slugged per side, each from the scenarios it shows.
    before_slugs = build_scenario_slug_index(
        [_removed(listed) for listed in delta.scenarios if listed.after is None]
    )
    after_slugs = build_scenario_slug_index(
        [listed.after for listed in delta.scenarios if listed.after is not None]
    )
    return [
        ListedScenario(
            _keyed(listed),
            after_slugs[listed.after.id]
            if listed.after is not None
            else REMOVED + before_slugs[_removed(listed).id],
        )
        for listed in delta.scenarios
    ]


def _removed(scenario_delta: ScenarioDelta) -> Scenario:
    assert scenario_delta.before is not None
    return scenario_delta.before


def _table_view(
    scenario_delta: ScenarioDelta, keys: dict[Side, list[BlockKey]]
) -> TableView | None:
    before, after = scenario_delta.paired()
    parameters = scenario_delta.parameters
    if parameters is None:
        return _lone_table(before, after, keys)
    if not parameters.changed:
        return None
    assert before.parameters is not None
    assert after.parameters is not None
    removed = {pair.before for pair in parameters.columns if pair.after is None}
    added = {pair.after for pair in parameters.columns if pair.before is None}
    before_names = {column.id: column.name for column in before.parameters.columns}
    # Paired by values means renamed: a name and kind each table holds once
    # pairs by name first, and one a table holds twice leaves values more than
    # one column of the kind to choose from there, so none pairs.
    renamed_from = {
        pair.after: before_names[pair.before]
        for pair in parameters.columns
        if pair.paired_by == 'values'
        and pair.before is not None
        and pair.after is not None
    }
    before_cases = {case.id: case for case in before.parameters.cases}
    after_cases = {case.id: case for case in after.parameters.cases}
    return TableView(
        sides=[
            TableSide(
                'before',
                before.parameters,
                [
                    TableColumn(column, 'removed' if column.id in removed else None)
                    for column in before.parameters.columns
                ],
                _column_blocks(before, keys['before']),
                repr_columns(before),
            ),
            TableSide(
                'after',
                after.parameters,
                [
                    TableColumn(
                        column,
                        'added' if column.id in added else None,
                        renamed_from.get(column.id),
                    )
                    for column in after.parameters.columns
                ],
                _column_blocks(after, keys['after']),
                repr_columns(after),
            ),
        ],
        rows=[
            TableRow(
                before_cases[pair.before] if pair.before is not None else None,
                after_cases[pair.after] if pair.after is not None else None,
                pair,
            )
            for pair in parameters.cases
        ],
    )


def _lone_table(
    before: Scenario, after: Scenario, keys: dict[Side, list[BlockKey]]
) -> TableView | None:
    """The one table a scenario gained or lost with its parametrization, every
    case of it added or removed."""
    if before.parameters is not None:
        return TableView(
            [_unmarked_side('before', before, keys['before'])],
            [
                TableRow(case, None, CasePair(before=case.id))
                for case in before.parameters.cases
            ],
        )
    if after.parameters is not None:
        return TableView(
            [_unmarked_side('after', after, keys['after'])],
            [
                TableRow(None, case, CasePair(after=case.id))
                for case in after.parameters.cases
            ],
        )
    return None


def _unmarked_side(side: Side, scenario: Scenario, keys: list[BlockKey]) -> TableSide:
    table = scenario.parameters
    assert table is not None
    return TableSide(
        side,
        table,
        [TableColumn(column) for column in table.columns],
        _column_blocks(scenario, keys),
        repr_columns(scenario),
    )


def _column_blocks(
    scenario: Scenario, keys: list[BlockKey]
) -> dict[ColumnId, BlockKey]:
    return {
        column: keys[block] for column, block in column_phase_blocks(scenario).items()
    }


def _keyed(scenario_delta: ScenarioDelta) -> ScenarioDelta:
    if scenario_delta.change != 'changed':
        return scenario_delta
    parameters = scenario_delta.parameters
    columns = parameters.columns if parameters else ()
    paired = {
        pair.before: pair.after
        for pair in columns
        if pair.before is not None and pair.after is not None
    }
    return _BeforeKeys(paired).scenario_delta(scenario_delta)


@dataclass(frozen=True)
class _BeforeKeys:
    """A changed scenario's before column IDs as the page keys them: a paired
    column's after ID, so a placeholder on either side finds its column in
    both tables, any other prefixed `before:`. `data-param` carries the key."""

    paired: dict[ColumnId, ColumnId]

    def scenario_delta(self, scenario_delta: ScenarioDelta) -> ScenarioDelta:
        before = scenario_delta.before
        assert before is not None
        return dataclasses.replace(
            scenario_delta,
            before=dataclasses.replace(
                before,
                narration=self._narration(before.narration),
                steps=[self._step(step) for step in before.steps],
                parameters=self._table(before.parameters),
            ),
            steps=tuple(self._step_delta(step) for step in scenario_delta.steps),
            parameters=self._parameter_delta(scenario_delta.parameters),
        )

    def _key(self, column_id: ColumnId) -> ColumnId:
        return self.paired.get(column_id) or ColumnId(_BEFORE_ONLY_KEY + column_id)

    def _parts(self, parts: tuple[NarrationPart, ...]) -> tuple[NarrationPart, ...]:
        return tuple(
            dataclasses.replace(part, column_id=self._key(part.column_id))
            if isinstance(part, NarrationPlaceholder)
            else part
            for part in parts
        )

    def _narration(self, narration: Narration) -> Narration:
        return dataclasses.replace(narration, parts=self._parts(narration.parts))

    def _step(self, step: Step) -> Step:
        return dataclasses.replace(
            step,
            narration=self._narration(step.narration),
            children=[self._step(child) for child in step.children],
            attachments=[
                dataclasses.replace(
                    attachment, column_id=self._key(attachment.column_id)
                )
                if isinstance(attachment, AttachmentRef)
                else attachment
                for attachment in step.attachments
            ],
        )

    def _step_delta(self, step_delta: StepDelta) -> StepDelta:
        """A word diff's before parts, which the before side's text reads."""
        return dataclasses.replace(
            step_delta,
            words=tuple(
                dataclasses.replace(segment, before=self._parts(segment.before))
                for segment in step_delta.words
            ),
            children=tuple(self._step_delta(child) for child in step_delta.children),
        )

    def _table(self, table: ParameterTable | None) -> ParameterTable | None:
        if table is None:
            return None
        return dataclasses.replace(
            table,
            columns=[
                dataclasses.replace(column, id=self._key(column.id))
                for column in table.columns
            ],
        )

    def _parameter_delta(
        self, parameters: ParameterDelta | None
    ) -> ParameterDelta | None:
        if parameters is None:
            return None
        return dataclasses.replace(
            parameters,
            columns=tuple(
                dataclasses.replace(pair, before=self._key(pair.before))
                if pair.before is not None
                else pair
                for pair in parameters.columns
            ),
        )


def _reason_row(
    status: Literal['skipped', 'xfailed'],
    label: str,
    reason: str | None,
    replaced: str | None,
) -> ReasonRow:
    return ReasonRow(status, label, reason, replaced if replaced != reason else None)
