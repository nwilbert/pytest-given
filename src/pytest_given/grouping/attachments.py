"""Promoting a step's attachments: any whose payload varies becomes a column.

The narration side is `templatize`'s; this is the other half of the same walk,
kept apart because the two share only the `Promotion` they are handed.
"""

from ..model import (
    Attachment,
    AttachmentRef,
    NodeId,
    Step,
    StepAttachment,
    StepPath,
)
from .checks import LabeledAttachments, check_attachment_labels
from .promotion import Promotion


def templatize_attachments(
    step: Step, path: StepPath, ctx: Promotion
) -> list[StepAttachment]:
    """Baseline attachments, with any whose payload varies promoted to a column.

    Paired **by label** — rule 5 guarantees the label set is shared, and
    position does not survive a case attaching the same labels in a different
    order. Same-label attachments pair by occurrence order.

    Rule 5 checks the label *set* only, so another case may attach a label more
    times than the baseline. Those extra occurrences get a column-only
    promotion — no badge, since the baseline tree has no slot for an occurrence
    it never recorded — appended right after that label's baseline occurrences
    so column ids keep following the walk.
    """
    baseline = _by_label(step)
    others = {
        case.id: _by_label(ctx.group.indexed[case.id][path])
        for case in ctx.group.comparable
    }
    check_attachment_labels(baseline, others, ctx.group)

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


def _by_label(step: Step) -> LabeledAttachments:
    """That step's attachments grouped by label, in the order it recorded them —
    the one shape everything below reads: a count is a `len`, an occurrence an
    index, and a label the case never attached a missing key."""
    out: LabeledAttachments = {}
    for attachment in step.attachments:
        assert isinstance(attachment, Attachment), 'a recorded tree holds no refs'
        out.setdefault(attachment.label, []).append(attachment)
    return out


def _promote_occurrence(
    attachment: Attachment,
    occurrence: int,
    others: dict[NodeId, LabeledAttachments],
    ctx: Promotion,
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
    column = ctx.columns.new_column('attachment', attachment.label)
    for node_id, other in theirs.items():
        ctx.columns.set_cell(column.id, node_id, other)
    # The badge is labeled with the *column* name, not the attachment's own
    # label: a label attached twice gives two columns, and a badge repeating
    # the bare label points the reader at the wrong one.
    return AttachmentRef(
        label=column.name,
        content_type=attachment.content_type,
        column_id=column.id,
    )


def _promote_extra_occurrences(
    label: str,
    baseline: LabeledAttachments,
    others: dict[NodeId, LabeledAttachments],
    ctx: Promotion,
) -> None:
    """Occurrences of `label` past the baseline's own count: one column each,
    with the baseline's cell left `None` and nothing appended to the grouped
    step's attachments.

    The count comes from `baseline`, never from `others[first case]`: the
    baseline is the first *passed* case, so a skipped first case would put the
    range at 0 and re-promote occurrences the baseline already carries a badge
    for.
    """
    for occurrence in range(len(baseline.get(label, [])), _max_count(label, others)):
        column = ctx.columns.new_column('attachment', label)
        for node_id, by_label in others.items():
            ctx.columns.set_cell(
                column.id, node_id, _occurrence(by_label, label, occurrence)
            )


def _max_count(label: str, others: dict[NodeId, LabeledAttachments]) -> int:
    """The greatest number of times any comparable case attaches `label`."""
    return max(
        (len(by_label.get(label, [])) for by_label in others.values()), default=0
    )


def _occurrence(
    by_label: LabeledAttachments, label: str, index: int
) -> Attachment | None:
    """That case's `index`-th attachment carrying `label`, or None when the case
    attached that label fewer times than `index` requires."""
    matching = by_label.get(label, [])
    return matching[index] if index < len(matching) else None
