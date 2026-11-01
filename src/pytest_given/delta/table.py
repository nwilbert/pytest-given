"""Pairing two parameter tables: their columns, then their cases."""

from collections.abc import Callable, Hashable, Sequence

from ..model import (
    Attachment,
    CasePair,
    CasePairing,
    CellValue,
    ColumnId,
    ColumnKind,
    ColumnPair,
    ColumnPairing,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterDelta,
    ParameterTable,
    ParamValue,
    case_id,
)
from .order import interleaved

type CellKey = tuple[str, ParamValue]  # (type name, value): 1, 1.0 and True differ
type CaseCells = dict[ColumnId, CellKey]

_RENAMEABLE_KINDS: tuple[ColumnKind, ...] = ('param', 'derived')


def align_table(
    before: ParameterTable,
    after: ParameterTable,
    case_rewrite: Callable[[str], str],
) -> ParameterDelta:
    """`case_rewrite` maps a before case ID to its rename-log rewrite."""
    alignment = _Alignment(before, after, case_rewrite)
    alignment.pair_columns_by_name()
    alignment.pair_cases()
    alignment.pair_renamed_columns()
    return alignment.delta()


class _Alignment:
    def __init__(
        self,
        before: ParameterTable,
        after: ParameterTable,
        case_rewrite: Callable[[str], str],
    ) -> None:
        self.before = before
        self.after = after
        self.case_rewrite = case_rewrite
        self.before_columns = _comparable(before.columns)
        self.after_columns = _comparable(after.columns)
        self.before_by_id = {case.id: case for case in before.cases}
        self.after_by_id = {case.id: case for case in after.cases}
        self.before_cells = {case.id: cells_of(before, case) for case in before.cases}
        self.after_cells = {case.id: cells_of(after, case) for case in after.cases}
        # Each pairing runs from the before ID to the after ID and how it paired.
        self.columns: dict[ColumnId, tuple[ColumnId, ColumnPairing]] = {}
        self.cases: dict[NodeId, tuple[NodeId, CasePairing]] = {}

    def pair_columns_by_name(self) -> None:
        for before_column, after_column in _unique_matches(
            self.before_columns, self.after_columns, _name_and_kind, _name_and_kind
        ):
            self.columns[before_column.id] = (after_column.id, 'name')

    def pair_cases(self) -> None:
        shared = [
            (column.id, self.columns[column.id][0])
            for column in self.before_columns
            if column.kind == 'param' and column.id in self.columns
        ]
        steps: list[tuple[CasePairing, _CaseKey, _CaseKey]] = [
            ('rename-log', self._rewritten_id, _generated_id),
            ('case-id', _custom_id, _custom_id),
            (
                'values',
                lambda case: (
                    tuple(self.before_cells[case.id][ident] for ident, _ in shared)
                    or None
                ),
                lambda case: (
                    tuple(self.after_cells[case.id][ident] for _, ident in shared)
                    or None
                ),
            ),
            ('case-id', _generated_id, _generated_id),
        ]
        for pairing, before_key, after_key in steps:
            matched_after = {after_id for after_id, _ in self.cases.values()}
            for before_case, after_case in _unique_matches(
                [case for case in self.before.cases if case.id not in self.cases],
                [case for case in self.after.cases if case.id not in matched_after],
                before_key,
                after_key,
            ):
                self.cases[before_case.id] = (after_case.id, pairing)

    def pair_renamed_columns(self) -> None:
        paired_after = {after_id for after_id, _ in self.columns.values()}
        for kind in _RENAMEABLE_KINDS:
            before_unpaired = [
                column
                for column in self.before_columns
                if column.kind == kind and column.id not in self.columns
            ]
            after_unpaired = [
                column
                for column in self.after_columns
                if column.kind == kind and column.id not in paired_after
            ]
            if (
                len(before_unpaired) == 1
                and len(after_unpaired) == 1
                and self._agree_in_paired_cases(before_unpaired[0], after_unpaired[0])
            ):
                self.columns[before_unpaired[0].id] = (after_unpaired[0].id, 'values')

    def delta(self) -> ParameterDelta:
        column_rows = interleaved(
            [column.id for column in self.after_columns],
            [column.id for column in self.before_columns],
            {before_id: after_id for before_id, (after_id, _) in self.columns.items()},
        )
        before_of = {
            after_id: before_id for before_id, (after_id, _) in self.columns.items()
        }
        case_rows = interleaved(
            [case.id for case in self.after.cases],
            [case.id for case in self.before.cases],
            {before_id: after_id for before_id, (after_id, _) in self.cases.items()},
        )
        return ParameterDelta(
            columns=tuple(
                ColumnPair(
                    before=before_id,
                    after=after_id,
                    paired_by=self.columns[before_id][1]
                    if before_id is not None and after_id is not None
                    else None,
                )
                for before_id, after_id in column_rows
            ),
            cases=tuple(self._case_pair(*row, before_of) for row in case_rows),
        )

    def _case_pair(
        self,
        before_id: NodeId | None,
        after_id: NodeId | None,
        before_of: dict[ColumnId, ColumnId],
    ) -> CasePair:
        if before_id is None or after_id is None:
            return CasePair(before=before_id, after=after_id)
        before_case = self.before_by_id[before_id]
        after_case = self.after_by_id[after_id]
        return CasePair(
            before=before_id,
            after=after_id,
            paired_by=self.cases[before_id][1],
            changed_cells=tuple(
                column.id
                for column in self.after_columns
                if column.id in before_of
                and self.before_cells[before_id][before_of[column.id]]
                != self.after_cells[after_id][column.id]
            ),
            id_changed=(before_case.custom_id or after_case.custom_id)
            and case_id(before_id) != case_id(after_id),
            status_changed=before_case.status != after_case.status,
        )

    def _rewritten_id(self, case: ParameterCase) -> str | None:
        rewritten = self.case_rewrite(case_id(case.id))
        return rewritten if rewritten != case_id(case.id) else None

    def _agree_in_paired_cases(
        self, before_column: ParameterColumn, after_column: ParameterColumn
    ) -> bool:
        return bool(self.cases) and all(
            self.before_cells[before_id][before_column.id]
            == self.after_cells[after_id][after_column.id]
            for before_id, (after_id, _) in self.cases.items()
        )


type _CaseKey = Callable[[ParameterCase], Hashable | None]


def _comparable(columns: Sequence[ParameterColumn]) -> list[ParameterColumn]:
    return [column for column in columns if column.kind != 'attachment']


def _name_and_kind(column: ParameterColumn) -> tuple[str, ColumnKind]:
    return (column.name, column.kind)


def _generated_id(case: ParameterCase) -> str:
    return case_id(case.id)


def _custom_id(case: ParameterCase) -> str | None:
    return case_id(case.id) if case.custom_id else None


def _cell_key(value: CellValue) -> CellKey:
    assert not isinstance(value, Attachment)
    return (type(value).__name__, value)


def cells_of(table: ParameterTable, case: ParameterCase) -> CaseCells:
    return {
        column.id: _cell_key(value)
        for column, value in table.cells(case)
        if column.kind != 'attachment'
    }


def _unique_matches[Item](
    before_items: Sequence[Item],
    after_items: Sequence[Item],
    before_key: Callable[[Item], Hashable | None],
    after_key: Callable[[Item], Hashable | None],
) -> list[tuple[Item, Item]]:
    """The items whose key is the only one of its value on each side, in the
    before order."""
    after_by_key = _singles(after_items, after_key)
    return [
        (item, after_by_key[key])
        for key, item in _singles(before_items, before_key).items()
        if key in after_by_key
    ]


def _singles[Item](
    items: Sequence[Item], key_of: Callable[[Item], Hashable | None]
) -> dict[Hashable, Item]:
    grouped: dict[Hashable, list[Item]] = {}
    for item in items:
        key = key_of(item)
        if key is not None:
            grouped.setdefault(key, []).append(item)
    return {key: group[0] for key, group in grouped.items() if len(group) == 1}
