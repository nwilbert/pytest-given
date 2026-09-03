"""The baseline walk: what every comparable case shares stays inline, and
anything that varies becomes a column plus a pointer at it.

A varying narrated value leaves a `{name}` placeholder behind, a varying
attachment payload a content-less badge. The scenario name is templatized
separately — evaluated once at decoration time, it cannot vary across cases and
so has nothing to be compared against.
"""

from dataclasses import replace

from ..model import (
    ColumnId,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterColumn,
    PartIndex,
    Phase,
    RawParamValue,
    Step,
    StepPath,
    placeholder_mismatch,
    rebuilt,
)
from .attachments import templatize_attachments
from .checks import (
    check_constant_term_ref,
    check_promotable_expression,
)
from .columns import Format, cell_text, param_cell
from .promotion import Promotion


def templatize_steps(steps: list[Step], prefix: StepPath, ctx: Promotion) -> list[Step]:
    """Walk the baseline tree, promoting anything that varies into a column."""
    out: list[Step] = []
    for index, step in enumerate(steps):
        path = (*prefix, index)
        out.append(
            replace(
                step,
                narration=_templatize_step_narration(step, path, ctx),
                attachments=templatize_attachments(step, path, ctx),
                children=templatize_steps(step.children, path, ctx),
            )
        )
    return out


def _templatize_step_narration(step: Step, path: StepPath, ctx: Promotion) -> Narration:
    """The baseline step's narration with varying values promoted.

    A step with no parts is a `str` narration: rule 1 has already rejected it if
    it varies, so it passes through. Otherwise each part is compared against the
    same position in every comparable case.
    """
    return rebuilt(
        step.narration,
        lambda index, part: _templatize_part(part, index, path, step.phase, ctx),
    )


def _templatize_part(
    part: NarrationPart, index: PartIndex, path: StepPath, phase: Phase, ctx: Promotion
) -> NarrationPart:
    """One baseline part, against the same position in every comparable case.

    A literal has nothing that could vary. A value bound to a parametrize
    column is compared against that cell rather than against the cases, since
    the column already holds every case's.
    """
    match part:
        case NarrationLiteral():
            return part
        case NarrationValue(expression=expression) if (
            expression in ctx.group.param_names
        ):
            return _templatize_param_value(part, index, path, ctx)
        case NarrationValue():
            return _templatize_value(part, index, path, phase, ctx)
        case NarrationPlaceholder(name=name):
            if name not in ctx.group.param_names:
                raise placeholder_mismatch(name, ctx.group.param_names)
            # A `Template` slot in a step body (an `Annotated[..., given(...)]`
            # label). It records no per-case rendering, so it reconciles the
            # way the scenario name's slots do rather than the way a
            # `NarrationValue` does.
            return _reconciled_slot(part, ctx)
        case NarrationTermRef():
            # Rule 4 requires it to read identically across cases whether a
            # column binds it or not, so it is always compared.
            check_constant_term_ref(part, index, path, phase, ctx.group)
            return part


def _param_slot(part: NarrationValue) -> NarrationPlaceholder:
    return NarrationPlaceholder(
        name=part.expression,
        column_id=ColumnId(part.expression),
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _templatize_param_value(
    part: NarrationValue,
    index: PartIndex,
    path: StepPath,
    ctx: Promotion,
) -> NarrationPart:
    """A slot bound to a `param` column: it keeps pointing there when the cell
    reads the way this slot rendered, and gets a column of its own when it does
    not.

    `param_cell_formats` already gave the column the one formatting its
    placeholders agree on, so this is a no-op in the ordinary case. It earns
    its keep where two steps format one parameter differently, which no shared
    cell can serve.
    """
    rendered = {
        case.id: _value_at(ctx.group.indexed[case.id][path], index)
        for case in ctx.group.comparable
    }
    column = _promoted_column(rendered, ColumnId(part.expression), part.expression, ctx)
    if column is None:
        return _param_slot(part)
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _templatize_value(
    part: NarrationValue, index: PartIndex, path: StepPath, phase: Phase, ctx: Promotion
) -> NarrationPart:
    """An interpolation no parametrize column binds: kept as it is when every
    case renders it the same, promoted to a `derived` column when they do not."""
    if all(
        _value_at(ctx.group.indexed[case.id][path], index) == part.rendered
        for case in ctx.group.comparable
    ):
        # Checked before the cells are collected: nothing varies in the
        # overwhelming majority of parts, and only a promotion needs every
        # case's rendering kept.
        return part
    check_promotable_expression(part, phase, ctx.group)
    column = ctx.columns.new_column('derived', part.expression)
    for case in ctx.group.comparable:
        ctx.columns.set_cell(
            column.id, case.id, _value_at(ctx.group.indexed[case.id][path], index)
        )
    # The token names the *column*, not the expression: one expression promoted
    # in two steps gives two columns, and `{price}` in both tokens points the
    # reader at the first one twice.
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _value_at(step: Step, index: PartIndex) -> str:
    """That case's rendering of the interpolation at `index`.

    Rule 6 pins every passed case to the baseline's template, so the part is
    present and is an interpolation wherever the baseline's is — as is the step
    itself, since only comparable cases are indexed.
    """
    part = step.narration.parts[index]
    assert isinstance(part, NarrationValue), (
        'rule 6 admits only cases shaped like the baseline'
    )
    return part.rendered


def templatize_narration(narration: Narration, ctx: Promotion) -> Narration:
    """The **scenario** name as a template, its slots pointed at columns that
    read the way they do.

    A name is evaluated once at decoration time, so it cannot vary and has
    nothing to be compared against: every part stays verbatim but the one a
    parametrize column binds. That slot is then reconciled like any step's —
    a `{price:.2f}` slot over a cell holding `1.5` would read `charge 1.5
    euros` on hover, a sentence no case narrated — and gets a `derived` column
    of its own where the shared cell cannot serve it.
    """
    return rebuilt(
        narration,
        lambda _index, part: _reconciled_slot(
            _name_part(part, ctx.group.param_names), ctx
        ),
    )


def _name_part(part: NarrationPart, param_names: list[str]) -> NarrationPart:
    """One part of a scenario name: a value a column binds becomes that column's
    slot, a placeholder has to name a column, everything else stands."""
    match part:
        case NarrationValue(expression=expression) if expression in param_names:
            return _param_slot(part)
        case NarrationPlaceholder(name=name) if name not in param_names:
            raise placeholder_mismatch(name, param_names)
    return part


def _reconciled_slot(part: NarrationPart, ctx: Promotion) -> NarrationPart:
    """One `Template` slot re-pointed at a column that reads the way it does.

    Shared by the scenario name and by a step's `Template` slots: neither
    records a per-case rendering to compare against, so both recompute what
    the slot renders from each case's raw parameter.
    """
    # Every placeholder that survives `_name_part` names a known column: both
    # callers reject a name absent from `param_names`, and a column exists for
    # each of those.
    if not isinstance(part, NarrationPlaceholder):
        return part
    rendered = _slot_renderings(part, ctx.group.case_params)
    column = _promoted_column(rendered, part.column_id, part.name, ctx)
    if column is None:
        return part
    return replace(part, name=column.name, column_id=column.id)


def _slot_renderings(
    part: NarrationPlaceholder,
    case_params: dict[NodeId, dict[str, RawParamValue]],
) -> dict[NodeId, str]:
    """What this slot renders for each case, built exactly as `param_cell`
    builds the cell it will be compared with.

    Going through `param_cell` rather than `render_interpolation` is what makes
    the comparison meaningful: it unwraps a glossary term instance to its
    display, and a value whose own `__format__` refuses this spec falls back to
    the same plain coercion the cell does, so the two still agree.
    """
    out: dict[NodeId, str] = {}
    for case_id, params in case_params.items():
        assert part.name in params, (
            f'{part.name!r} points at a param column, so every case binds it'
        )
        out[case_id] = cell_text(param_cell(params[part.name], _slot_format(part)))
    return out


def _slot_format(part: NarrationPlaceholder) -> Format | None:
    """The formatting this slot renders its value with, or None when it carries
    none.

    None is what puts `param_cell` on its unformatted path, whose plain
    coercion unwraps a glossary term instance to its display — where
    `format(value, '')` would render the whole `Glossary` repr and never match
    the cell it is compared with.
    """
    if not part.conversion and not part.format_spec:
        return None
    return (part.conversion, part.format_spec)


def _promoted_column(
    rendered: dict[NodeId, str], column_id: ColumnId, name: str, ctx: Promotion
) -> ParameterColumn | None:
    """The `derived` column a slot needs when the cell it points at does not
    read the way the slot renders — or None when that cell already serves it.

    The one compare-and-promote rule, shared by both slot kinds — only where
    the renderings come from differs.
    """
    if ctx.columns.reads_as(column_id, rendered):
        return None
    column = ctx.columns.new_column('derived', name)
    for case_id, text in rendered.items():
        ctx.columns.set_cell(column.id, case_id, text)
    return column
