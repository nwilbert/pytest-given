"""The parameter table a group accumulates: its typed columns and their cells.

`ColumnBuilder` is the single registry — column ids, disambiguated names, and
the cell store. The rest is cell construction, which answers to one rule: a
`param` cell has to read the way the placeholder pointing at it rendered, since
row hover substitutes the one into the other.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..capture import try_term_ref
from ..model import (
    Attachment,
    CellValue,
    ColumnId,
    ColumnKind,
    Narration,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    NodeId,
    ParameterCase,
    ParameterColumn,
    ParameterTable,
    ParamValue,
    RawParamValue,
    Scenario,
    render_interpolation,
)
from .context import Group

# A slot's rendering details as the author wrote them: `(conversion,
# format_spec)`. `None` for the pair as a whole means "no formatting at all",
# which `param_cell` renders differently from an empty spec.
type Format = tuple[str | None, str]


def trivial_format(fmt: Format) -> bool:
    """Whether a slot carries no formatting of its own.

    One predicate for both readers: `param_cell_formats` deciding whether a
    column can adopt a shared formatting, and `templatize._slot_format`
    deciding whether to render a cell the plain way. They used to disagree on
    a `('', '')` pair, which only one of them treated as trivial.
    """
    conversion, format_spec = fmt
    return not conversion and not format_spec


def param_id(name: str) -> ColumnId:
    """The column id a parametrize argname takes.

    Its own function because four places used to spell it: the builder that
    creates the column, the fill that seeds its cells, and both of
    `templatize`'s slot paths, which point a placeholder at it by name.
    """
    return ColumnId(name)


@dataclass
class ColumnBuilder:
    """The columns and cells a group's walk accumulates, and the group it reads.

    Both halves of the walk — `templatize` and `attachments` — take this one
    object, which is what it is for, and both call it `builder`. `checks` still
    takes a bare `Group`, so a module that only inspects a group does not also
    carry the ability to add a column to it.
    """

    group: Group
    columns: list[ParameterColumn] = field(default_factory=list)
    cells: dict[ColumnId, dict[NodeId, CellValue]] = field(default_factory=dict)
    _counts: dict[ColumnKind, int] = field(default_factory=dict)
    _taken_names: set[str] = field(default_factory=set)

    def table(self, cases: list[Scenario]) -> ParameterTable:
        """The finished table: the columns, and one row per case.

        The transposition from the cell store to positional rows belongs to
        whatever owns the store, so nothing outside has to know that a row's
        values are ordered by `columns`.
        """
        return ParameterTable(
            columns=self.columns,
            cases=[
                ParameterCase(
                    values=[self.cell(column.id, case.id) for column in self.columns],
                    status=case.status,
                    error=case.error,
                )
                for case in cases
            ],
        )

    def derived(self, name: str, rendered: dict[NodeId, str]) -> ParameterColumn:
        """A new `derived` column, filled with what each case rendered.

        Creating and filling are one act: every promotion does both, and three
        call sites doing them separately is three chances to point a slot at an
        empty column.
        """
        column = self.new_column('derived', name)
        for node_id, text in rendered.items():
            self.set_cell(column.id, node_id, text)
        return column

    @classmethod
    def for_params(cls, group: Group, formats: dict[str, Format]) -> ColumnBuilder:
        """A builder holding the parametrize columns, filled.

        They come first and keep their argname as id: a step's placeholder
        points at them by name (`column_id=expression`), and the walk emits
        generated columns after.

        Filled here rather than after the walk starts: a `param` cell is what
        its slots substitute, so the walk compares against it.
        """
        builder = cls(group=group)
        for name in group.param_names:
            builder.new_column('param', name)
        for case in group.cases:
            for name, value in group.case_params[case.id].items():
                builder.set_cell(
                    param_id(name), case.id, param_cell(value, formats.get(name))
                )
        return builder

    def new_column(self, kind: ColumnKind, name: str) -> ParameterColumn:
        """Add a column and return it.

        A `param` column is identified by its argname; generated ids are
        `derived:0`, `attachment:0`, … numbered per kind in emission order. The
        colon makes collision with an argname impossible — those are
        `callspec.params` keys, hence always Python identifiers.
        """
        if kind == 'param':
            column_id = param_id(name)
        else:
            index = self._counts.get(kind, 0)
            self._counts[kind] = index + 1
            column_id = ColumnId(f'{kind}:{index}')
        column = ParameterColumn(id=column_id, name=self._unique_name(name), kind=kind)
        self.columns.append(column)
        self.cells[column_id] = {}
        return column

    def set_cell(self, column_id: ColumnId, node_id: NodeId, value: CellValue) -> None:
        self.cells[column_id][node_id] = value

    def cell(self, column_id: ColumnId, node_id: NodeId) -> CellValue:
        """That case's cell, or None where it has none.

        Absence is ordinary: a `derived` column is filled from the comparable
        cases only, so a failed or skipped case has no cell in one.
        """
        return self.cells[column_id].get(node_id)

    def reads_as(self, column_id: ColumnId, rendered: dict[NodeId, str]) -> bool:
        """Whether every case's cell in *column_id* already prints the way that
        case rendered it — the question a slot asks before promoting.

        Indexed, not `.get`: the callers pass renderings from the comparable
        cases against a `param` column, which is filled for every case in the
        group, so a missing cell is a broken invariant rather than a case that
        bound nothing.
        """
        cells = self.cells[column_id]
        return all(
            cell_text(cells[node_id]) == text for node_id, text in rendered.items()
        )

    def _unique_name(self, name: str) -> str:
        """`name`, or `name #2`, `name #3`, … once it is already taken.

        A rendered table shows only the name and a Markdown badge carries no id
        at all, so two columns sharing a label need distinct names too. The
        first stays bare, since suffixing it would churn every report that has
        only one.

        The candidate is checked against the names already taken rather than
        counted per name, because a label is arbitrary text and can itself read
        like a suffix — `log`, `log #2`, `log` must still come out distinct.
        """
        candidate = name
        suffix = 1
        while candidate in self._taken_names:
            suffix += 1
            candidate = f'{name} #{suffix}'
        self._taken_names.add(candidate)
        return candidate


def _param_value(value: RawParamValue) -> ParamValue:
    """Coerce a raw parametrize argument into a table cell.

    A glossary term instance unwraps to its display: `str()` on one would store
    a dataclass repr of the whole `Glossary` in the table and the JSON report.
    JSON primitives pass through; everything else is its `str()`.
    """
    term_ref = try_term_ref(value)
    if term_ref is not None:
        return term_ref.display
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def param_cell_formats(
    narrations: Iterable[Narration], param_names: list[str]
) -> dict[str, Format]:
    """The formatting each `param` column's cells are rendered with, for the
    columns whose slots agree on one.

    A cell is not decoration: row hover substitutes it into every slot in the
    scenario card that points at the column, so it has to *be* what those slots
    showed. `t"at {when:%H:%M}"` narrates `14:30` while `str(when)` is
    `2026-08-19 14:30:00`, and splicing the latter in builds a sentence no case
    ever narrated. Rule 3 has already established that the narration is the raw
    value rendered through the interpolation's own conversion and spec, so
    re-applying that spec to the cell reproduces the narrated text exactly.
    Both slot kinds count — a step's `NarrationValue` and a `Template`'s
    `NarrationPlaceholder`.

    Only a formatting every slot for that column shares is used. Two slots
    formatting one parameter differently leave no single text a shared cell
    could hold; the column keeps its plain value and each disagreeing slot gets
    a column of its own. The trivial formatting counts as one of the two.
    """
    seen: dict[str, set[Format]] = {}
    for narration in narrations:
        for part in narration.parts:
            slot = _bound_slot(part, param_names)
            if slot is not None:
                name, fmt = slot
                seen.setdefault(name, set()).add(fmt)
    return {
        name: next(iter(formats))
        for name, formats in seen.items()
        if len(formats) == 1 and not trivial_format(next(iter(formats)))
    }


def _bound_slot(
    part: NarrationPart, param_names: list[str]
) -> tuple[str, Format] | None:
    """The `param` column this part points at and the formatting it renders
    with, or None when the part is not a slot bound to one."""
    if isinstance(part, NarrationValue) and part.expression in param_names:
        return part.expression, (part.conversion, part.format_spec)
    if isinstance(part, NarrationPlaceholder) and part.name in param_names:
        return part.name, (part.conversion, part.format_spec)
    return None


def param_cell(value: RawParamValue, fmt: Format | None) -> ParamValue:
    """One `param` cell: the value rendered the way its placeholders render it,
    or `_param_value`'s plain coercion when they carry no formatting of their
    own or the value refuses this one.

    The unformatted path stays `_param_value` rather than `format(value, '')`,
    so a glossary term instance still unwraps to its display.
    """
    if fmt is None:
        return _param_value(value)
    try:
        return render_interpolation(value, *fmt)
    except Exception:  # noqa: BLE001 — a value whose own rendering raises
        # The step cannot have narrated it either, so there is nothing to
        # agree with; the plain coercion is the honest fallback.
        return _param_value(value)


def cell_text(cell: CellValue) -> str:
    """A cell as the renderers print it — what hover substitutes into a slot."""
    assert not isinstance(cell, Attachment), 'a param column holds no attachment'
    return str(cell)
