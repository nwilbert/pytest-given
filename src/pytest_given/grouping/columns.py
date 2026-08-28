"""The parameter table a group accumulates: its typed columns and their cells.

`GroupContext` is the single registry — column ids, disambiguated names, and
the cell store — threaded through the baseline walk. The rest is cell
construction, which answers to one rule: a `param` cell has to read the way the
placeholder pointing at it rendered, since row hover substitutes the one into
the other.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..capture import try_term_ref
from ..model import (
    Attachment,
    CellValue,
    ColumnKind,
    Narration,
    NarrationPart,
    NarrationPlaceholder,
    NarrationValue,
    NodeId,
    ParameterColumn,
    ParamValue,
    RawParamValue,
    Scenario,
    Step,
    StepPath,
    render_interpolation,
    walk_steps,
)


@dataclass
class GroupContext:
    """Everything the baseline walk needs, plus the columns it accumulates."""

    param_names: list[str]
    comparable: list[Scenario]
    anchor: Scenario
    # Each case's raw parametrize arguments by name. A `Template` slot — in a
    # step or in the scenario name — records no per-case rendering to compare
    # against, so what it renders has to be recomputed from these; see
    # `templatize._reconciled_slot`.
    case_params: dict[NodeId, dict[str, RawParamValue]]
    columns: list[ParameterColumn] = field(default_factory=list)
    cells: dict[str, dict[NodeId, CellValue | None]] = field(default_factory=dict)
    # Each comparable case's tree keyed by position, so "the same position in
    # every other case" is a lookup rather than a parallel descent through
    # several trees. Derived from `comparable` rather than passed alongside it:
    # the two must agree on which cases are in play, and a caller that built
    # one from the other could only ever get that wrong.
    indexed: dict[NodeId, dict[StepPath, Step]] = field(init=False)
    _counts: dict[ColumnKind, int] = field(default_factory=dict)
    _taken_names: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.indexed = {
            case.id: dict(walk_steps(case.steps)) for case in self.comparable
        }
        # The parametrize columns come first and keep their argname as id: a
        # step's placeholder points at them by name (`column_id=expression`),
        # and every generated column is emitted after them by the baseline
        # walk. Creating them here rather than in the caller keeps one column
        # list, one cell store, and one name registry — disambiguation spans
        # the whole table, not the generated columns alone.
        for name in self.param_names:
            self.new_column('param', name)

    def new_column(self, kind: ColumnKind, name: str) -> ParameterColumn:
        """Add a column and return it.

        A `param` column is identified by its argname; generated ids are
        `derived:0`, `attachment:0`, … numbered per kind in emission order. The
        colon makes collision with an argname impossible — those are
        `callspec.params` keys, hence always Python identifiers. The whole
        column comes back rather than its id alone because the caller also
        builds the step tree's pointer at it, which has to carry the
        disambiguated `name` (see `_unique_name`).
        """
        if kind == 'param':
            column_id = name
        else:
            index = self._counts.get(kind, 0)
            self._counts[kind] = index + 1
            column_id = f'{kind}:{index}'
        column = ParameterColumn(id=column_id, name=self._unique_name(name), kind=kind)
        self.columns.append(column)
        self.cells[column_id] = {}
        return column

    def set_cell(
        self, column_id: str, node_id: NodeId, value: CellValue | None
    ) -> None:
        self.cells[column_id][node_id] = value

    def _unique_name(self, name: str) -> str:
        """`name`, or `name #2`, `name #3`, … once it is already taken.

        An id disambiguates two columns in the JSON, but a rendered table shows
        only the name and a Markdown badge carries no id at all — so two
        occurrences of one attachment label, or one expression promoted in two
        steps, need distinct names as well. The first stays bare: a single
        column is the overwhelmingly common case, and suffixing it would churn
        every existing report.

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
    a dataclass repr of the whole `Glossary` — hundreds of characters — in the
    table and the JSON report. JSON primitives pass through; everything else is
    its `str()`, since a cell only ever feeds display and the JSON sink.
    """
    term_ref = try_term_ref(value)
    if term_ref is not None:
        return term_ref.display
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


type Format = tuple[str | None, str]


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

    Both slot kinds count. A step records its interpolations as
    `NarrationValue`; a `Template` — a scenario name, or an
    `Annotated[..., given(Template(...))]` label — records a
    `NarrationPlaceholder` whose spec is just as load-bearing and is likewise
    the only formatting in play when no step interpolates that parameter.

    Only a formatting every slot for that column shares is used. Two slots
    formatting one parameter differently (`{when:%H:%M}` and `{when:%Y-%m-%d}`)
    leave no single text a shared cell could hold; the column keeps its plain
    value and each disagreeing slot gets a column of its own. The trivial
    formatting counts as one of the two, so a column read plainly in one slot
    and formatted in another goes the same way.
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
        if len(formats) == 1 and formats != {(None, '')}
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

    The unformatted path stays `_param_value` rather than `format(value, '')` —
    a glossary term instance has to unwrap to its display, and every cell that
    exists today keeps its current type and text.
    """
    if fmt is None:
        return _param_value(value)
    try:
        return render_interpolation(value, *fmt)
    except Exception:  # noqa: BLE001 — a value whose own rendering raises
        # The step cannot have narrated it either, so there is nothing to
        # agree with; the plain coercion is the honest fallback.
        return _param_value(value)


def cell_text(cell: CellValue | None) -> str:
    """A cell as the renderers print it — what hover substitutes into a slot."""
    assert not isinstance(cell, Attachment), 'a param column holds no attachment'
    return str(cell)
