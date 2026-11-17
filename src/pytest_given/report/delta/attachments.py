"""A step's or table cell's attachment diff as rows to show: its line diff
with the long runs of equal lines folded away."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby

from ...model import (
    Attachment,
    AttachmentChange,
    AttachmentDelta,
    LineChange,
    LineDelta,
    Side,
    Step,
    StepAttachment,
    TextSegment,
    on_side,
)

CONTEXT_LINES = 3
MIN_FOLDED = 4  # fewer hidden lines than this stay shown


@dataclass(frozen=True)
class LineRow:
    change: LineChange
    before: str | None  # None where the side lacks the line
    after: str | None
    words: tuple[TextSegment, ...] = ()


@dataclass(frozen=True)
class FoldRow:
    rows: tuple[LineRow, ...]  # the hidden equal lines


type DiffRow = LineRow | FoldRow


@dataclass(frozen=True)
class AttachmentRow:
    change: AttachmentChange
    before: StepAttachment | None
    after: StepAttachment | None
    rows: tuple[DiffRow, ...]  # a changed payload pair's; else ()

    def attachment(self, side: Side) -> StepAttachment | None:
        return on_side(side, self.before, self.after)


def attachment_rows(
    deltas: Sequence[AttachmentDelta], before: Step, after: Step
) -> tuple[AttachmentRow, ...]:
    return tuple(
        _attachment_row(delta, before.attachments, after.attachments)
        for delta in deltas
    )


def diff_rows(
    lines: Sequence[LineDelta], before: str, after: str
) -> tuple[DiffRow, ...]:
    """The line diff's rows, an equal run kept to its context beside a change
    and folded where `MIN_FOLDED` or more lines would hide."""
    before_lines, after_lines = before.split('\n'), after.split('\n')
    rows = [
        row for line in lines for row in _line_rows(line, before_lines, after_lines)
    ]
    folded: list[DiffRow] = []
    position = 0
    for is_equal, group in groupby(rows, key=lambda row: row.change == 'equal'):
        run = tuple(group)
        position += len(run)
        if is_equal:
            folded.extend(
                _folded(
                    run, at_start=position == len(run), at_end=position == len(rows)
                )
            )
        else:
            folded.extend(run)
    return tuple(folded)


def _attachment_row(
    delta: AttachmentDelta,
    before: Sequence[StepAttachment],
    after: Sequence[StepAttachment],
) -> AttachmentRow:
    before_attachment = None if delta.before is None else before[delta.before]
    after_attachment = None if delta.after is None else after[delta.after]
    rows: tuple[DiffRow, ...] = ()
    if delta.lines:
        assert isinstance(before_attachment, Attachment)
        assert isinstance(after_attachment, Attachment)
        rows = diff_rows(
            delta.lines, before_attachment.content, after_attachment.content
        )
    return AttachmentRow(delta.change, before_attachment, after_attachment, rows)


def _line_rows(
    line: LineDelta, before: Sequence[str], after: Sequence[str]
) -> list[LineRow]:
    return [
        LineRow(
            line.change,
            None if line.before is None else before[line.before + offset],
            None if line.after is None else after[line.after + offset],
            line.words,
        )
        for offset in range(line.count)
    ]


def _folded(run: tuple[LineRow, ...], *, at_start: bool, at_end: bool) -> list[DiffRow]:
    lead = 0 if at_start else CONTEXT_LINES
    trail = 0 if at_end else CONTEXT_LINES
    hidden = len(run) - lead - trail
    if hidden < MIN_FOLDED:
        return list(run)
    return [
        *run[:lead],
        FoldRow(run[lead : len(run) - trail]),
        *run[len(run) - trail :],
    ]
