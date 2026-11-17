"""A diff's rows (`report/delta/attachments.py`): which lines show, which fold."""

import dataclasses

from pytest_given.delta.attachments import line_diff
from pytest_given.model import Attachment, AttachmentDelta
from pytest_given.report.delta.attachments import (
    CONTEXT_LINES,
    MIN_FOLDED,
    FoldRow,
    LineRow,
    attachment_rows,
    diff_rows,
)
from tests.unit.delta.builders import step


def _text(count: int, edge: str) -> str:
    return '\n'.join([edge, *(f'line {number}' for number in range(count)), edge])


def _shapes(rows: tuple[FoldRow | LineRow, ...]) -> list[str]:
    return [
        f'fold {len(row.rows)}' if isinstance(row, FoldRow) else row.change
        for row in rows
    ]


def test_an_equal_run_folds_beyond_its_context():
    before, after = _text(20, 'old'), _text(20, 'new')
    rows = diff_rows(line_diff(before, after), before, after)
    assert _shapes(rows) == [
        'removed',
        'added',
        *['equal'] * CONTEXT_LINES,
        'fold 14',
        *['equal'] * CONTEXT_LINES,
        'removed',
        'added',
    ]


def test_a_run_at_the_start_keeps_context_only_before_the_change():
    before = '\n'.join([*(f'line {number}' for number in range(20)), 'old'])
    after = before.replace('old', 'new')
    rows = diff_rows(line_diff(before, after), before, after)
    assert _shapes(rows) == ['fold 17', *['equal'] * CONTEXT_LINES, 'removed', 'added']


def test_a_short_run_stays_shown():
    """Nine equal lines leave three hidden, fewer than `MIN_FOLDED`."""
    before, after = _text(9, 'old'), _text(9, 'new')
    rows = diff_rows(line_diff(before, after), before, after)
    assert _shapes(rows) == ['removed', 'added', *['equal'] * 9, 'removed', 'added']


def test_a_run_at_the_end_keeps_context_only_after_the_change():
    before = '\n'.join(['old', *(f'line {number}' for number in range(20))])
    after = before.replace('old', 'new')
    rows = diff_rows(line_diff(before, after), before, after)
    assert _shapes(rows) == ['removed', 'added', *['equal'] * CONTEXT_LINES, 'fold 17']


def test_an_all_equal_diff_folds_into_one_row():
    """A changed content type alone leaves every line equal."""
    text = '\n'.join(f'line {number}' for number in range(MIN_FOLDED))
    assert _shapes(diff_rows(line_diff(text, text), text, text)) == [
        f'fold {MIN_FOLDED}'
    ]


def test_attachment_rows_resolve_each_side():
    old = Attachment(label='body', content='a\nb')
    new = Attachment(label='body', content='a\nc')
    gone = Attachment(label='gone', content='x')
    before = dataclasses.replace(step('given', 'Pay'), attachments=[old, gone])
    after = dataclasses.replace(step('given', 'Pay'), attachments=[new])
    deltas = [
        AttachmentDelta(
            change='changed',
            before=0,
            after=0,
            lines=line_diff(old.content, new.content),
        ),
        AttachmentDelta(change='removed', before=1),
    ]
    changed, removed = attachment_rows(deltas, before, after)
    assert (changed.attachment('before'), changed.attachment('after')) == (old, new)
    assert [
        (row.before, row.after) for row in changed.rows if isinstance(row, LineRow)
    ] == [
        ('a', 'a'),
        ('b', None),
        (None, 'c'),
    ]
    assert (removed.attachment('before'), removed.attachment('after')) == (gone, None)
    assert removed.rows == ()
