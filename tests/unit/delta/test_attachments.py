"""Pairing a step's attachments by label, and diffing their content by line and word."""

import pytest

from pytest_given import given, scenario, then, when
from pytest_given.delta import AttachmentDelta, LineDelta, TextSegment, attachments
from pytest_given.delta.attachments import align_attachments, line_diff
from pytest_given.model import (
    Attachment,
    AttachmentLabel,
    AttachmentRef,
    ColumnId,
    ContentType,
)
from tests.ubiquitous_language import pg


def _payload(
    label: str, content: str, content_type: ContentType = 'text'
) -> Attachment:
    return Attachment(AttachmentLabel(label), content, content_type)


def _pointer(label: str, column: str) -> AttachmentRef:
    return AttachmentRef(label=label, content_type='text', column_id=ColumnId(column))


def test_payloads_pair_by_label_and_unpaired_ones_are_added_or_removed() -> None:
    before = [_payload('a', 'one'), _payload('b', 'two')]
    after = [_payload('b', 'three'), _payload('c', 'four')]

    assert align_attachments(before, after, {}) == (
        AttachmentDelta(change='removed', before=0),
        AttachmentDelta(
            change='changed',
            before=1,
            after=0,
            lines=(
                LineDelta(change='removed', before=0),
                LineDelta(change='added', after=0),
            ),
        ),
        AttachmentDelta(change='added', after=1),
    )


@scenario(
    t'Attachments pair by label in a {pg["Delta report"].l}, a repeated label '
    t'pairing its unchanged ones first',
    tags=['delta'],
)
def test_a_repeated_label_pairs_its_unchanged_attachments_first() -> None:
    with given(
        t'a before {pg["Step"].l} attaching two responses and a receipt, and an '
        t'after one attaching the receipt first and a new response ahead of the '
        t'two'
    ):
        before = [
            _payload('response', '200 OK'),
            _payload('response', '404'),
            _payload('receipt', 'paid'),
        ]
        after = [
            _payload('receipt', 'paid'),
            _payload('response', '201 Created'),
            _payload('response', '200 OK'),
            _payload('response', '404'),
        ]
    with when(t'their {pg["Attachment"].l.s} are aligned'):
        deltas = align_attachments(before, after, {})
    with then('the receipt pairs with the receipt, unchanged'):
        assert deltas[0] == AttachmentDelta(change='equal', before=2, after=0)
    with then('the new response is added'):
        assert deltas[1] == AttachmentDelta(change='added', after=1)
    with then('the two responses pair with their equals, unchanged'):
        assert deltas[2:] == (
            AttachmentDelta(change='equal', before=0, after=2),
            AttachmentDelta(change='equal', before=1, after=3),
        )


def test_a_repeated_label_pairs_its_changed_attachments_in_order() -> None:
    before = [_payload('log', 'a'), _payload('log', 'same'), _payload('log', 'b')]
    after = [_payload('log', 'c'), _payload('log', 'same'), _payload('log', 'd')]

    assert [
        (delta.change, delta.before, delta.after)
        for delta in align_attachments(before, after, {})
    ] == [('changed', 0, 0), ('equal', 1, 1), ('changed', 2, 2)]


def test_equal_payloads_are_equal_and_carry_no_lines() -> None:
    assert align_attachments(
        [_payload('log', 'a\nb')], [_payload('log', 'a\nb')], {}
    ) == (AttachmentDelta(change='equal', before=0, after=0),)


def test_a_changed_content_type_is_changed() -> None:
    assert align_attachments(
        [_payload('doc', '{}', 'json')], [_payload('doc', '{}', 'text')], {}
    ) == (
        AttachmentDelta(
            change='changed',
            before=0,
            after=0,
        ),
    )


def test_two_pointers_are_equal_when_their_columns_pair() -> None:
    before = [_pointer('log', 'log_before')]
    after = [_pointer('log', 'log_after')]

    assert align_attachments(
        before, after, {ColumnId('log_before'): ColumnId('log_after')}
    ) == (AttachmentDelta(change='equal', before=0, after=0),)
    assert align_attachments(
        before, after, {ColumnId('log_before'): ColumnId('other')}
    ) == (AttachmentDelta(change='changed', before=0, after=0),)


def test_a_pointer_paired_with_a_payload_is_changed_without_lines() -> None:
    assert align_attachments([_payload('log', 'a')], [_pointer('log', 'log')], {}) == (
        AttachmentDelta(change='changed', before=0, after=0),
    )


def test_line_diff_keeps_equal_lines_as_runs() -> None:
    assert line_diff('a\nb\nc\nd', 'a\nb\nX\nd') == (
        LineDelta(change='equal', before=0, after=0, count=2),
        LineDelta(change='removed', before=2),
        LineDelta(change='added', after=2),
        LineDelta(change='equal', before=3, after=3, count=1),
    )


@scenario(
    t'A reworded line of a changed attachment carries its word diff in a '
    t'{pg["Delta report"].l}',
    tags=['delta'],
)
def test_a_similar_line_is_modified_with_its_word_diff() -> None:
    with given(
        t'a before and an after {pg["Attachment"].l} whose one line has one word '
        t'reworded'
    ):
        before = [_payload('log', 'the cat sat')]
        after = [_payload('log', 'the dog sat')]
    with when(t'the two {pg["Attachment"].l.s} are aligned'):
        (delta,) = align_attachments(before, after, {})
    with then(t'the {pg["Attachment"].l} is changed and its line is modified'):
        assert delta.change == 'changed'
        assert [(line.change, line.before, line.after) for line in delta.lines] == [
            ('modified', 0, 0)
        ]
    with then('the modified line marks the reworded word removed and added'):
        assert delta.lines[0].words == (
            TextSegment(mark='equal', text='the '),
            TextSegment(mark='removed', text='cat'),
            TextSegment(mark='added', text='dog'),
            TextSegment(mark='equal', text=' sat'),
        )


def test_a_line_pairs_past_an_added_line_and_an_unrelated_one_is_removed() -> None:
    assert line_diff('x\nzzz\nthe cat sat\ny', 'x\nnew\nthe dog sat\ny') == (
        LineDelta(change='equal', before=0, after=0),
        LineDelta(change='removed', before=1),
        LineDelta(change='added', after=1),
        LineDelta(
            change='modified',
            before=2,
            after=2,
            words=(
                TextSegment(mark='equal', text='the '),
                TextSegment(mark='removed', text='cat'),
                TextSegment(mark='added', text='dog'),
                TextSegment(mark='equal', text=' sat'),
            ),
        ),
        LineDelta(change='equal', before=3, after=3),
    )


def test_equal_lines_between_changes_run_together() -> None:
    assert line_diff('a\nb\nc\nd\ne', 'X\nb\nc\nd\nY') == (
        LineDelta(change='removed', before=0),
        LineDelta(change='added', after=0),
        LineDelta(change='equal', before=1, after=1, count=3),
        LineDelta(change='removed', before=4),
        LineDelta(change='added', after=4),
    )


def test_a_word_diff_merges_runs_of_one_mark_only() -> None:
    (line,) = line_diff('keep a b keep', 'keep a c d keep')

    assert line.words == (
        TextSegment(mark='equal', text='keep a '),
        TextSegment(mark='removed', text='b'),
        TextSegment(mark='added', text='c'),
        TextSegment(mark='equal', text=' '),
        TextSegment(mark='added', text='d '),
        TextSegment(mark='equal', text='keep'),
    )


def test_a_large_middle_without_a_unique_line_in_common_is_removed_then_added() -> None:
    before = '\n'.join(f'before {index}' for index in range(1_001))
    after = '\n'.join(f'after {index}' for index in range(1_001))

    lines = line_diff(before, after)

    assert lines == (
        *(LineDelta(change='removed', before=index) for index in range(1_001)),
        *(LineDelta(change='added', after=index) for index in range(1_001)),
    )


def test_a_trailing_newline_gained_is_an_added_empty_line() -> None:
    assert line_diff('a', 'a\n') == (
        LineDelta(change='equal', before=0, after=0, count=1),
        LineDelta(change='added', after=1),
    )


def test_a_large_attachment_diffs_in_runs() -> None:
    before_lines = [f'line {index}' for index in range(20_000)]
    after_lines = list(before_lines)
    after_lines[10_000] = 'replaced'

    lines = line_diff('\n'.join(before_lines), '\n'.join(after_lines))

    assert [line.change for line in lines] == ['equal', 'removed', 'added', 'equal']
    assert lines[0].count + lines[3].count == 19_999


def test_a_line_too_long_to_diff_by_word_is_removed_and_added() -> None:
    words = [f'word{index}' for index in range(50_000)]
    changed = list(words)
    changed[25_000] = 'other'

    assert line_diff(' '.join(words), ' '.join(changed)) == (
        LineDelta(change='removed', before=0),
        LineDelta(change='added', after=0),
    )


def test_a_large_attachment_with_distant_changes_keeps_the_lines_between_equal() -> (
    None
):
    before_lines = [f'line {index}' for index in range(20_000)]
    after_lines = list(before_lines)
    after_lines[100] = 'replaced'
    after_lines[19_900] = 'replaced too'

    lines = line_diff('\n'.join(before_lines), '\n'.join(after_lines))

    assert lines == (
        LineDelta(change='equal', before=0, after=0, count=100),
        LineDelta(change='removed', before=100),
        LineDelta(change='added', after=100),
        LineDelta(change='equal', before=101, after=101, count=19_799),
        LineDelta(change='removed', before=19_900),
        LineDelta(change='added', after=19_900),
        LineDelta(change='equal', before=19_901, after=19_901, count=99),
    )


def test_a_large_middle_anchors_on_unique_lines_that_keep_their_order() -> None:
    before_lines = [f'line {index}' for index in range(2_000)]
    after_lines = [*before_lines[1:], before_lines[0]]

    lines = line_diff('\n'.join(before_lines), '\n'.join(after_lines))

    assert lines == (
        LineDelta(change='removed', before=0),
        LineDelta(change='equal', before=1, after=0, count=1_999),
        LineDelta(change='added', after=1_999),
    )


def test_removed_lines_ahead_of_reworded_ones_leave_them_modified() -> None:
    removed = [f'gone{index} has nothing and more' for index in range(300)]
    kept = [f'item{index} has value{index} and flag{index}' for index in range(600)]
    reworded = [line.replace('flag', 'mark') for line in kept]

    lines = line_diff('\n'.join([*removed, *kept]), '\n'.join(reworded))

    assert [line.change for line in lines] == ['removed'] * 300 + ['modified'] * 600


def test_a_line_of_spaces_alone_is_modified_into_one_and_removed_otherwise() -> None:
    assert [line.change for line in line_diff('a\n \nb', 'a\n  \nb')] == [
        'equal',
        'modified',
        'equal',
    ]
    assert [line.change for line in line_diff('a\n \nb', 'a\nword\nb')] == [
        'equal',
        'removed',
        'added',
        'equal',
    ]


def test_counting_shared_words_stops_once_the_budget_is_spent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(attachments, 'MAX_LCS_CELLS', 50)
    reworded = [f'x y z{index}' for index in range(30)]

    lines = line_diff('x y', '\n'.join(reworded))

    assert lines == (
        LineDelta(change='removed', before=0),
        *(LineDelta(change='added', after=index) for index in range(30)),
    )


def test_similarity_checks_stop_once_their_budget_is_spent() -> None:
    words = [f'word{index}' for index in range(250)]
    reworded = [*words[:-1], 'other']
    reversed_line = ' '.join(reversed(words))

    lines = line_diff(
        ' '.join(words), '\n'.join([*[reversed_line] * 10, ' '.join(reworded)])
    )

    assert lines == (
        LineDelta(change='removed', before=0),
        *(LineDelta(change='added', after=index) for index in range(11)),
    )
