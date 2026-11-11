"""The baseline walk: what every comparable case shares stays inline, and
anything that varies becomes a column plus a pointer at it.

A varying narrated value leaves a placeholder behind, a varying
attachment payload a content-less badge. The scenario title is templatized
separately — evaluated once at decoration time, it cannot vary across cases and
so has nothing to be compared against.
"""

from dataclasses import replace

from ..model import (
    CellValue,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    ParameterColumn,
    RawParamValue,
    Step,
    StepPath,
    boolean_phrases,
    param_id,
    placeholder_mismatch,
    rebuilt,
)
from .attachments import templatize_attachments
from .checks import (
    check_constant_term_ref,
    check_promotable_expression,
)
from .columns import (
    ColumnBuilder,
    cell_text,
    leaves_cell_plain,
    param_cell,
)
from .context import Format, PartSite


def templatize_steps(
    steps: list[Step], prefix: StepPath, builder: ColumnBuilder
) -> list[Step]:
    """Walk the baseline tree, promoting anything that varies into a column."""
    out: list[Step] = []
    for index, step in enumerate(steps):
        path = (*prefix, index)
        out.append(
            replace(
                step,
                narration=_templatize_step_narration(step, path, builder),
                attachments=templatize_attachments(step, path, builder),
                children=templatize_steps(step.children, path, builder),
            )
        )
    return out


def _templatize_step_narration(
    step: Step, path: StepPath, builder: ColumnBuilder
) -> Narration:
    """The baseline step's narration with varying values promoted.

    A step with no parts is a `str` narration: rule 1 has already rejected it if
    it varies, so it passes through. Otherwise each part is compared against the
    same position in every comparable case.
    """
    return rebuilt(
        step.narration,
        lambda index, part: _templatize_part(
            part, PartSite(path=path, index=index, phase=step.phase), builder
        ),
    )


def _templatize_part(
    part: NarrationPart, site: PartSite, builder: ColumnBuilder
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
            expression in builder.group.param_names
        ):
            return _templatize_param_value(part, site, builder)
        case NarrationValue():
            return _templatize_value(part, site, builder)
        case NarrationPlaceholder(name=name):
            if name not in builder.group.param_names:
                raise placeholder_mismatch(name, builder.group.param_names)
            # A `Template` slot in a step body (an `Annotated[..., given(...)]`
            # label). It records no per-case rendering, so it reconciles the
            # way the scenario title's slots do rather than the way a
            # `NarrationValue` does.
            return _reconciled_slot(part, builder)
        case NarrationTermRef():
            # Rule 4 requires it to read identically across cases whether a
            # column binds it or not, so it is always compared.
            check_constant_term_ref(part, site, builder.group)
            return part


def _param_slot(part: NarrationValue) -> NarrationPlaceholder:
    return NarrationPlaceholder(
        name=part.expression,
        column_id=param_id(part.expression),
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _templatize_param_value(
    part: NarrationValue, site: PartSite, builder: ColumnBuilder
) -> NarrationPart:
    """A slot bound to a `param` column: it keeps pointing there when the cell
    reads the way this slot rendered, and gets a column of its own when it does
    not.

    `param_cell_formats` already gave the column the one formatting its
    placeholders agree on, so this is a no-op in the ordinary case. It earns
    its keep where two steps format one parameter differently, which no shared
    cell can serve.
    """
    cells = _case_cells(site, builder)
    if builder.reads_as(param_id(part.expression), cells):
        return _param_slot(part)
    return _slot(part, builder.derived(part.expression, cells))


def _templatize_value(
    part: NarrationValue, site: PartSite, builder: ColumnBuilder
) -> NarrationPart:
    """An interpolation no parametrize column binds: kept as it is when every
    case renders it the same, promoted to a `derived` column when they do not."""
    cells = _case_cells(site, builder)
    baseline_cell = _cell_of(part)
    if all(cell == baseline_cell for cell in cells.values()):
        return part
    check_promotable_expression(part, site.phase, builder.group)
    if boolean_phrases(part.format_spec) is None:
        return _slot(part, builder.derived(part.expression, cells))
    return _slot(part, builder.shared_derived(part.expression, cells))


def _case_cells(site: PartSite, builder: ColumnBuilder) -> dict[NodeId, CellValue]:
    """Each comparable case's cell for the interpolation at `site`.

    Rule 6 pins every passed case to the baseline's template, so the part is
    present and is an interpolation wherever the baseline's is.
    """
    out: dict[NodeId, CellValue] = {}
    for node_id, part in builder.group.parts_at(site):
        assert isinstance(part, NarrationValue), (
            'rule 6 admits only cases shaped like the baseline'
        )
        out[node_id] = _cell_of(part)
    return out


def _cell_of(part: NarrationValue) -> CellValue:
    """What a column holds for this interpolation: the text it rendered, or the
    Boolean behind a phrase, which only that text still records."""
    phrases = boolean_phrases(part.format_spec)
    return part.rendered if phrases is None else part.rendered == phrases[0]


def _slot(part: NarrationValue, column: ParameterColumn) -> NarrationPlaceholder:
    """A placeholder pointing at `column`, carrying the part's own formatting.

    The name is the *column's*, not the expression's: one expression promoted
    in two steps can give two columns, and `{price}` in both tokens would point
    the reader at the first one twice. A phrased slot's token shows its phrases
    instead of the name.
    """
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def templatize_scenario_title(
    narration: Narration, builder: ColumnBuilder
) -> Narration:
    """The scenario title as a template, its slots pointed at columns that
    read the way they do.

    A title is evaluated once at decoration time, so it cannot vary and has
    nothing to be compared against: every part stays verbatim but the one a
    parametrize column binds. That slot is then reconciled like any step's —
    a `{price:.2f}` slot over a cell holding `1.5` would read `charge 1.5
    euros` on hover, a sentence no case narrated — and gets a `derived` column
    of its own where the shared cell cannot serve it.
    """
    return rebuilt(
        narration,
        lambda _index, part: _reconciled_slot(
            _title_part(part, builder.group.param_names), builder
        ),
    )


def _title_part(part: NarrationPart, param_names: list[str]) -> NarrationPart:
    """One part of a scenario title: a value a column binds becomes that column's
    slot, a placeholder has to name a column, everything else stands."""
    match part:
        case NarrationValue(expression=expression) if expression in param_names:
            return _param_slot(part)
        case NarrationPlaceholder(name=name):
            # Collection already validated a scenario title's placeholders
            # against this same list, and reported them with a locator this
            # far-downstream raise could not produce.
            assert name in param_names, (
                f'scenario-title placeholder {name!r} is not one of {param_names}'
            )
    return part


def _reconciled_slot(part: NarrationPart, builder: ColumnBuilder) -> NarrationPart:
    """One `Template` slot re-pointed at a column that reads the way it does.

    Shared by the scenario title and by a step's `Template` slots: neither
    records a per-case rendering to compare against, so both recompute what
    the slot renders from each case's raw parameter.
    """
    # Every placeholder that survives `_title_part` names a known column: both
    # callers reject a name absent from `param_names`, and a column exists for
    # each of those.
    if not isinstance(part, NarrationPlaceholder):
        return part
    rendered = _slot_renderings(part, builder.group.case_params)
    if builder.reads_as(part.column_id, rendered):
        return part
    column = builder.derived(part.name, rendered)
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
    """The formatting this slot needs from its cell, or None when it leaves the
    cell plain.

    None is what puts `param_cell` on its unformatted path, whose plain
    coercion unwraps a glossary term instance to its display — where
    `format(value, '')` would render the whole `Glossary` repr and never match
    the cell it is compared with.
    """
    fmt: Format = (part.conversion, part.format_spec)
    return None if leaves_cell_plain(fmt) else fmt
