"""The baseline walk: what every comparable case shares stays inline, and
anything that varies becomes a column plus a pointer at it.

A varying narrated value leaves a `{name}` placeholder behind, a varying
attachment payload a content-less badge. The scenario name is templatized
separately — evaluated once at decoration time, it cannot vary across cases and
so has nothing to be compared against.
"""

from dataclasses import replace

from ..model import (
    Attachment,
    AttachmentRef,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    NodeId,
    Phase,
    Step,
    StepAttachment,
    StepPath,
    narration_text,
    placeholder_mismatch,
)
from .checks import (
    check_attachment_labels,
    check_constant_term_ref,
    check_promotable_expression,
)
from .columns import GroupContext, cell_text


def templatize_steps(
    steps: list[Step], prefix: StepPath, ctx: GroupContext
) -> list[Step]:
    """Walk the baseline tree, promoting anything that varies into a column."""
    out: list[Step] = []
    for index, step in enumerate(steps):
        path = (*prefix, index)
        out.append(
            replace(
                step,
                narration=_templatize_step_narration(step, path, ctx),
                attachments=_templatize_attachments(step, path, ctx),
                children=templatize_steps(step.children, path, ctx),
            )
        )
    return out


def _templatize_attachments(
    step: Step, path: StepPath, ctx: GroupContext
) -> list[StepAttachment]:
    """Baseline attachments, with any whose payload varies promoted to a column.

    Paired **by label** — rule 5 guarantees the label set is shared, making the
    key total, and position does not survive a case attaching the same labels in
    a different order. Same-label attachments pair by occurrence order.

    A non-baseline case may attach a label *more* times than the baseline does
    — rule 5 only checks the label *set*, so a differing count does not raise.
    Once the baseline's own occurrences of a label are exhausted, any further
    occurrence in another case gets a column-only promotion (baseline cell
    blank, no badge — the baseline tree has no slot for an occurrence it never
    recorded), appended right after that label's baseline occurrences so
    column ids keep following the walk.
    """
    check_attachment_labels(step, path, ctx)
    baseline = _by_label(step)
    others = {case.id: _by_label(ctx.indexed[case.id][path]) for case in ctx.comparable}

    out: list[StepAttachment] = []
    seen: dict[str, int] = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        occurrence = seen.get(attachment.label, 0)
        seen[attachment.label] = occurrence + 1
        out.append(_promote_occurrence(attachment, occurrence, others, ctx))
        if occurrence == len(baseline[attachment.label]) - 1:
            _promote_extra_occurrences(attachment.label, baseline, others, ctx)
    return out


def _by_label(step: Step) -> dict[str, list[Attachment]]:
    """That step's attachments grouped by label, in the order it recorded them.

    The one shape everything below reads: a count is a `len`, an occurrence is
    an index, and a label the case never attached is a missing key. (A recorded
    tree holds no `AttachmentRef`s, so nothing here is content-less.)
    """
    out: dict[str, list[Attachment]] = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        out.setdefault(attachment.label, []).append(attachment)
    return out


def _promote_occurrence(
    attachment: Attachment,
    occurrence: int,
    others: dict[NodeId, dict[str, list[Attachment]]],
    ctx: GroupContext,
) -> StepAttachment:
    """The baseline's `occurrence`-th attachment of `attachment.label`: stays
    inline when every comparable case's occurrence matches it byte for byte,
    otherwise promoted to a column with a content-less badge left in its place.
    """
    theirs = {
        node_id: _occurrence(by_label, attachment.label, occurrence)
        for node_id, by_label in others.items()
    }
    if all(
        other is not None
        and (other.content, other.content_type)
        == (attachment.content, attachment.content_type)
        for other in theirs.values()
    ):
        return attachment
    column = ctx.new_column('attachment', attachment.label)
    for node_id, other in theirs.items():
        ctx.set_cell(column.id, node_id, other)
    # The badge is labelled with the *column* name, not the attachment's own
    # label: a label attached twice gives two columns, and a badge repeating
    # the bare label points the reader at the wrong one.
    return AttachmentRef(
        label=column.name,
        content_type=attachment.content_type,
        column_id=column.id,
    )


def _promote_extra_occurrences(
    label: str,
    baseline: dict[str, list[Attachment]],
    others: dict[NodeId, dict[str, list[Attachment]]],
    ctx: GroupContext,
) -> None:
    """Occurrences of `label` past the baseline's own count.

    Every case's occurrences of `label` past the baseline's last one get a
    column each, with every case's occurrence in its own cell and the
    baseline's left `None` — there is no baseline attachment for it, so nothing
    is appended to the grouped step's attachments.

    The count comes from `baseline`, never from `others[first case]`: the
    baseline is the first *passed* case, so a skipped first case would put the
    range at 0 and re-promote occurrences the baseline already carries a badge
    for. The baseline is itself one of `others` — it passed, and trivially
    matches its own structure signature — so `max` never falls below its own
    count. With no passed case at all `others` is empty and there is nothing
    past a baseline nobody can be compared to.
    """
    for occurrence in range(len(baseline.get(label, [])), _max_count(label, others)):
        column = ctx.new_column('attachment', label)
        for node_id, by_label in others.items():
            ctx.set_cell(column.id, node_id, _occurrence(by_label, label, occurrence))


def _max_count(label: str, others: dict[NodeId, dict[str, list[Attachment]]]) -> int:
    """The greatest number of times any comparable case attaches `label`."""
    return max(
        (len(by_label.get(label, [])) for by_label in others.values()), default=0
    )


def _occurrence(
    by_label: dict[str, list[Attachment]], label: str, index: int
) -> Attachment | None:
    """That case's `index`-th attachment carrying `label`, or None when the case
    attached that label fewer times than `index` requires."""
    matching = by_label.get(label, [])
    return matching[index] if index < len(matching) else None


def _templatize_step_narration(
    step: Step, path: StepPath, ctx: GroupContext
) -> Narration:
    """The baseline step's narration with varying values promoted.

    A step with no parts is a `str` narration: rule 1 has already rejected it if
    it varies, so it passes through. Otherwise each part is compared against the
    same position in every comparable case.
    """
    narration = step.narration
    if not narration.parts:
        return narration
    out = [
        _templatize_part(part, index, path, step.phase, ctx)
        for index, part in enumerate(narration.parts)
    ]
    return Narration(text=narration_text(out), parts=out)


def _templatize_part(
    part: NarrationPart, index: int, path: StepPath, phase: Phase, ctx: GroupContext
) -> NarrationPart:
    independent = _case_independent_part(part, ctx.param_names)
    if independent is not None:
        if isinstance(part, NarrationValue) and isinstance(
            independent, NarrationPlaceholder
        ):
            return _templatize_param_value(part, independent, index, path, ctx)
        return independent
    if isinstance(part, NarrationValue):
        return _templatize_value(part, index, path, phase, ctx)
    assert isinstance(part, NarrationTermRef), (
        'a literal or placeholder is case-independent by definition'
    )
    check_constant_term_ref(part, index, path, phase, ctx)
    return part


def _templatize_param_value(
    part: NarrationValue,
    placeholder: NarrationPlaceholder,
    index: int,
    path: StepPath,
    ctx: GroupContext,
) -> NarrationPart:
    """A slot bound to a `param` column: it keeps pointing there when the cell
    reads the way this slot rendered, and gets a column of its own when it does
    not.

    `param_cell_formats` already gave the column the one formatting its
    placeholders agree on, so this is a no-op for every slot in the ordinary
    case. It earns its keep where they disagree — two steps formatting one
    parameter differently — which no shared cell can serve: the odd slot is
    promoted like any other varying value, and the ` #2` suffix keeps its token
    pointing at the column that actually holds its text.
    """
    rendered = {
        case.id: _value_at(ctx.indexed[case.id][path], index) for case in ctx.comparable
    }
    if all(
        text == cell_text(ctx.cells[part.expression][case_id])
        for case_id, text in rendered.items()
    ):
        return placeholder
    column = ctx.new_column('derived', part.expression)
    for case_id, text in rendered.items():
        ctx.set_cell(column.id, case_id, text)
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _templatize_value(
    part: NarrationValue, index: int, path: StepPath, phase: Phase, ctx: GroupContext
) -> NarrationPart:
    """An interpolation no parametrize column binds: kept as it is when every
    case renders it the same, promoted to a `derived` column when they do not."""
    if all(
        _value_at(ctx.indexed[case.id][path], index) == part.rendered
        for case in ctx.comparable
    ):
        # Checked before the cells are collected: nothing varies in the
        # overwhelming majority of parts, and only a promotion needs every
        # case's rendering kept.
        return part
    check_promotable_expression(part, phase, ctx)
    column = ctx.new_column('derived', part.expression)
    for case in ctx.comparable:
        ctx.set_cell(column.id, case.id, _value_at(ctx.indexed[case.id][path], index))
    # The token names the *column*, not the expression: one expression promoted
    # in two steps gives two columns, and `{price}` in both tokens points the
    # reader at the first one twice.
    return NarrationPlaceholder(
        name=column.name,
        column_id=column.id,
        format_spec=part.format_spec,
        conversion=part.conversion,
    )


def _case_independent_part(
    part: NarrationPart, param_names: list[str]
) -> NarrationPart | None:
    """The part as it stands when no other case has a say in it, or None when
    it has to be compared against them first.

    A literal is one by definition, and so is anything a parametrize column
    binds — the column already holds every case's value. That makes this the
    whole of templatizing a *scenario* name, which is evaluated once at
    decoration time and cannot vary; a step's narration reaches its own
    comparison work only past it. One definition, so the placeholder contract
    (`name` and `column_id` both the parametrize name) and the term-ref
    exemption cannot drift between the two callers.
    """
    match part:
        case NarrationLiteral():
            return part
        case NarrationValue(expression=expression, format_spec=fs, conversion=conv):
            if expression not in param_names:
                return None
            return NarrationPlaceholder(
                name=expression,
                column_id=expression,
                format_spec=fs,
                conversion=conv,
            )
        case NarrationPlaceholder(name=name):
            if name not in param_names:
                raise placeholder_mismatch(name, param_names)
            return part
        case NarrationTermRef(expression=expression) if expression in param_names:
            # Exempt: its display varies by construction and the `param` column
            # already holds every case's value. This is what keeps
            # `param_column` alive.
            return replace(part, param_column=expression)
    return None


def _value_at(step: Step, index: int) -> str:
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


def templatize_narration(
    narration: Narration,
    param_names: list[str],
) -> Narration:
    """Convert matching NarrationValue entries to NarrationPlaceholder.

    For the **scenario** narration only — a scenario name is evaluated once at
    decoration time, so it cannot vary across cases and there is nothing to
    compare against other cases the way a step's narration is. That makes it
    exactly `_param_bound_part` and nothing else: a part no parametrize column
    binds stays verbatim, since its rendering is shared across cases.
    """
    if not narration.parts:
        return narration
    out = [
        _case_independent_part(part, param_names) or part for part in narration.parts
    ]
    return replace(narration, parts=out)
