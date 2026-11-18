"""How a scenario's steps and parameter table lay out on the HTML pages: the
phase blocks, the block each column belongs to, repr columns, the column
colours and the table's cells."""

# A session that renders no HTML never loads MarkupSafe.
__lazy_modules__ = ['markupsafe']

from collections.abc import Callable
from typing import TYPE_CHECKING

from markupsafe import Markup, escape

from ..model import (
    AttachmentRef,
    CellValue,
    ColumnId,
    NarrationPlaceholder,
    ParameterColumn,
    Scenario,
    Step,
    iter_steps,
)

if TYPE_CHECKING:
    from ..delta import Change

# Maps parameter name to its color index. The index resolves to a color via
# `palette.param_column_colors`, which never runs out.
type ParamColorMap = dict[str, int]


def build_param_color_map(scenarios: list[Scenario]) -> ParamColorMap:
    """One color per column *name* across the report, so a parameter reads the
    same color in every scenario. Attachment columns are excluded — a badge
    needs no value color."""
    color_map: ParamColorMap = {}
    color_idx = 0
    for scenario in scenarios:
        if scenario.parameters is None:
            continue
        for column in scenario.parameters.columns:
            if column.kind == 'attachment':
                continue
            if column.name not in color_map:
                color_map[column.name] = color_idx
                color_idx += 1
    return color_map


def make_param_color_class(
    param_color_map: ParamColorMap | None,
) -> Callable[[ParameterColumn], str]:
    """Jinja filter: a column's colour class, or empty for an attachment
    column or without a map — the one place that decides which columns are
    coloured."""

    def _class(column: ParameterColumn) -> str:
        if param_color_map is None or column.kind == 'attachment':
            return ''
        return f'param-color-{param_color_map[column.name]}'

    return _class


def phase_blocks(steps: list[Step]) -> list[list[Step]]:
    """Top-level steps in runs sharing a phase: one keyword each in the
    narration, and what a phase hover outlines."""
    blocks: list[list[Step]] = []
    for step in steps:
        if blocks and blocks[-1][0].phase == step.phase:
            blocks[-1].append(step)
        else:
            blocks.append([step])
    return blocks


def column_phase_blocks(scenario: Scenario) -> dict[ColumnId, int]:
    """Each parameter-table column's phase block: the one a reader first meets
    it in. A column no step narrates joins the block beside it, the one before
    or, leading the table, the first."""
    assert scenario.parameters is not None
    met_in: dict[ColumnId, int] = {}
    for index, block in enumerate(phase_blocks(scenario.steps)):
        for step in iter_steps(block):
            for part in step.narration.parts:
                if isinstance(part, NarrationPlaceholder):
                    met_in.setdefault(part.column_id, index)
            for attachment in step.attachments:
                if isinstance(attachment, AttachmentRef):
                    met_in.setdefault(attachment.column_id, index)
    columns = scenario.parameters.columns
    known = [met_in[column.id] for column in columns if column.id in met_in]
    if not known:
        return {}
    current = known[0]
    blocks: dict[ColumnId, int] = {}
    for column in columns:
        current = met_in.get(column.id, current)
        blocks[column.id] = current
    return blocks


_REPR_CONVERSIONS = ('r', 'a')


def repr_columns(scenario: Scenario) -> set[ColumnId]:
    """The columns a slot shows as a repr, which its author narrated that way
    because the exact value matters: a padded string, an empty one."""
    step_narrations = (step.narration for step in iter_steps(scenario.steps))
    return {
        part.column_id
        for narration in (scenario.narration, *step_narrations)
        for part in narration.parts
        if isinstance(part, NarrationPlaceholder) and shows_repr(part)
    }


def shows_repr(part: NarrationPlaceholder) -> bool:
    return part.conversion in _REPR_CONVERSIONS


def value_cell(
    column: ParameterColumn,
    value: CellValue,
    block: int | None,
    change: Change | None = None,
    shows_repr: bool = False,
) -> Markup:
    """A parameter table's `<td>` for any column but an attachment one. A
    filter, not a macro: a table has one per cell, and a macro call each cost
    the large report's render a twentieth.

    `data-subst` only where the cell has something to substitute: a generated
    column is blank for a case that recorded no value, and substituting that
    blank would erase the step's {token} instead of replacing it. A `param`
    cell always substitutes, as `None` there is a real parametrize value."""
    column_id = escape(column.id)
    substitutes = column.kind == 'param' or value is not None
    repr_class = 'class="param-repr" ' if shows_repr else ''
    parts = [f'<td {repr_class}data-param="{column_id}"']
    if block is not None:
        parts.append(f' data-block="{block}"')
    if substitutes:
        parts.append(f' data-subst="{column_id}"')
    if isinstance(value, bool):
        parts.append(f' data-boolean="{value}"')
    if change:
        parts.append(f' data-change="{change}"')
    parts.append(f'>{escape(value) if substitutes else ""}</td>')
    return Markup(''.join(parts))
