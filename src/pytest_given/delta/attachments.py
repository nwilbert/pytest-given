"""A step's attachments paired by label, and their content diffed by line and word."""

import operator
from bisect import bisect_left
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import groupby, islice, takewhile

from ..model import Attachment, AttachmentRef, ColumnId, StepAttachment
from .lcs import (
    Anchor,
    anchor_gaps,
    greedy_pairs,
    lcs_gaps,
    lcs_pairs,
    marked_items,
)
from .narration import MODIFIED_SIMILARITY, pieces, similarity
from .order import interleaved
from .schema import AttachmentDelta, LineDelta, TextSegment

# `lcs_pairs` builds a table of len(a) * len(b) cells. Past this many, lines
# align on the lines unique to both sides, a line goes without a word diff, and
# a line diff's similarity checks stop, rather than hang the build.
MAX_LCS_CELLS = 1_000_000


def align_attachments(
    before: Sequence[StepAttachment],
    after: Sequence[StepAttachment],
    column_of: Mapping[ColumnId, ColumnId],
) -> tuple[AttachmentDelta, ...]:
    """`column_of` maps a before column ID to its paired after column ID."""
    rows = interleaved(
        range(len(before)),
        range(len(after)),
        _paired_by_label(before, after, column_of),
    )
    deltas: list[AttachmentDelta] = []
    for before_index, after_index in rows:
        if before_index is None:
            deltas.append(AttachmentDelta(change='added', after=after_index))
        elif after_index is None:
            deltas.append(AttachmentDelta(change='removed', before=before_index))
        else:
            deltas.append(
                _paired(
                    before[before_index],
                    before_index,
                    after[after_index],
                    after_index,
                    column_of,
                )
            )
    return tuple(deltas)


def line_diff(before: str, after: str) -> tuple[LineDelta, ...]:
    """Equal lines come in runs. A trailing newline ends in an empty last line."""
    before_lines, after_lines = before.split('\n'), after.split('\n')
    prefix = _common_length(before_lines, after_lines)
    suffix = _common_length(
        reversed(before_lines[prefix:]), reversed(after_lines[prefix:])
    )
    before_stop, after_stop = len(before_lines) - suffix, len(after_lines) - suffix
    deltas: list[LineDelta] = []
    if prefix:
        deltas.append(LineDelta(change='equal', before=0, after=0, count=prefix))
    deltas.extend(
        _middle(
            before_lines[prefix:before_stop], after_lines[prefix:after_stop], prefix
        )
    )
    if suffix:
        deltas.append(
            LineDelta(
                change='equal', before=before_stop, after=after_stop, count=suffix
            )
        )
    return tuple(deltas)


def _paired_by_label(
    before: Sequence[StepAttachment],
    after: Sequence[StepAttachment],
    column_of: Mapping[ColumnId, ColumnId],
) -> dict[int, int]:
    """Before index to after index. A label's unchanged attachments pair first,
    and the rest between them in order."""
    after_of = _indices_by_label(after)
    pairs: dict[int, int] = {}
    for label, before_indices in _indices_by_label(before).items():
        after_indices = after_of.get(label, [])
        for before_gap, after_gap, anchor in lcs_gaps(
            before_indices,
            after_indices,
            lambda before_index, after_index: _unchanged(
                before[before_index], after[after_index], column_of
            ),
        ):
            pairs.update(
                zip(
                    (before_indices[index] for index in before_gap),
                    (after_indices[index] for index in after_gap),
                    strict=False,
                )
            )
            if anchor is not None:
                pairs[before_indices[anchor[0]]] = after_indices[anchor[1]]
    return pairs


def _indices_by_label(attachments: Sequence[StepAttachment]) -> dict[str, list[int]]:
    indices: dict[str, list[int]] = {}
    for index, attachment in enumerate(attachments):
        indices.setdefault(attachment.label, []).append(index)
    return indices


def _paired(
    before: StepAttachment,
    before_index: int,
    after: StepAttachment,
    after_index: int,
    column_of: Mapping[ColumnId, ColumnId],
) -> AttachmentDelta:
    """A pointer's content is its column's cells, which the parameter table
    compares, so a pointer carries no line diff."""
    if _unchanged(before, after, column_of):
        return AttachmentDelta(change='equal', before=before_index, after=after_index)
    if (
        isinstance(before, Attachment)
        and isinstance(after, Attachment)
        and before.content != after.content
    ):
        return AttachmentDelta(
            change='changed',
            before=before_index,
            after=after_index,
            lines=line_diff(before.content, after.content),
        )
    return AttachmentDelta(change='changed', before=before_index, after=after_index)


def _unchanged(
    before: StepAttachment,
    after: StepAttachment,
    column_of: Mapping[ColumnId, ColumnId],
) -> bool:
    match before, after:
        case Attachment(), Attachment():
            return (before.content_type, before.content) == (
                after.content_type,
                after.content,
            )
        case AttachmentRef(), AttachmentRef():
            return (
                before.content_type == after.content_type
                and column_of.get(before.column_id) == after.column_id
            )
    return False


def _common_length(before: Iterable[str], after: Iterable[str]) -> int:
    return sum(
        1
        for _ in takewhile(
            lambda pair: pair[0] == pair[1], zip(before, after, strict=False)
        )
    )


def _middle(before: list[str], after: list[str], start: int) -> Iterator[LineDelta]:
    """The lines between the common prefix and suffix, which start at `start`
    on both sides."""
    budget = _Budget(MAX_LCS_CELLS)
    run: LineDelta | None = None
    for before_gap, after_gap, anchor in anchor_gaps(
        _line_anchors(before, after), len(before), len(after)
    ):
        if before_gap or after_gap:
            if run is not None:
                yield run
                run = None
            if len(before_gap) * len(after_gap) > MAX_LCS_CELLS:
                yield from _unaligned(before_gap, after_gap, start)
            else:
                yield from _unanchored(
                    before, before_gap, after, after_gap, start, budget
                )
        if anchor is not None:
            index_before, index_after = anchor
            run = (
                LineDelta(
                    change='equal',
                    before=start + index_before,
                    after=start + index_after,
                )
                if run is None
                else replace(run, count=run.count + 1)
            )
    # The middle's last lines differ, so it ends in a gap, which yields the run.
    assert run is None


def _line_anchors(before: list[str], after: list[str]) -> list[Anchor]:
    """The equal lines to align on. Past the LCS budget, the lines found once on
    each side split the middle into stretches the LCS can align, so a few
    scattered changes still leave the lines between them equal. A stretch still
    past the budget gets no anchors, so its lines read as removed, then added."""
    if len(before) * len(after) <= MAX_LCS_CELLS:
        return lcs_pairs(before, after, operator.eq)
    anchors: list[Anchor] = []
    for before_gap, after_gap, anchor in anchor_gaps(
        _unique_anchors(before, after), len(before), len(after)
    ):
        if len(before_gap) * len(after_gap) <= MAX_LCS_CELLS:
            anchors.extend(
                (before_gap.start + index_before, after_gap.start + index_after)
                for index_before, index_after in lcs_pairs(
                    before[before_gap.start : before_gap.stop],
                    after[after_gap.start : after_gap.stop],
                    operator.eq,
                )
            )
        if anchor is not None:
            anchors.append(anchor)
    return anchors


def _unique_anchors(before: list[str], after: list[str]) -> list[Anchor]:
    """The lines found exactly once on each side, paired: the most of them
    that keep one order on both sides."""
    before_counts, after_counts = Counter(before), Counter(after)
    after_index = {
        line: index for index, line in enumerate(after) if after_counts[line] == 1
    }
    pairs = [
        (index, after_index[line])
        for index, line in enumerate(before)
        if before_counts[line] == 1 and line in after_index
    ]
    return _longest_increasing(pairs)


def _longest_increasing(pairs: list[Anchor]) -> list[Anchor]:
    """The longest subsequence of `pairs` whose after indices increase, for
    pairs whose before indices already do."""
    # tails[length - 1]: the position in `pairs` that ends an increasing run of
    # that length with the smallest after index.
    tails: list[int] = []
    previous: list[int | None] = []
    for position, (_, index_after) in enumerate(pairs):
        length = bisect_left(tails, index_after, key=lambda tail: pairs[tail][1])
        previous.append(tails[length - 1] if length else None)
        if length == len(tails):
            tails.append(position)
        else:
            tails[length] = position
    longest: list[Anchor] = []
    link = tails[-1] if tails else None
    while link is not None:
        longest.append(pairs[link])
        link = previous[link]
    return longest[::-1]


def _unaligned(before_gap: range, after_gap: range, start: int) -> Iterator[LineDelta]:
    yield from (
        LineDelta(change='removed', before=start + index) for index in before_gap
    )
    yield from (LineDelta(change='added', after=start + index) for index in after_gap)


class _Budget:
    """The cells the similarity checks of one line diff may still spend, so
    that many long lines in one gap cannot hang the build."""

    def __init__(self, cells: int) -> None:
        self.cells = cells

    def spend(self, cells: int) -> bool:
        """Spends `cells` when that many are left."""
        if cells > self.cells:
            return False
        self.cells -= cells
        return True


@dataclass(frozen=True)
class _Read:
    """A line read once, for every comparison it takes part in."""

    tokens: list[str]
    words: list[str]
    word_counts: Counter[str]


def _unanchored(
    before: list[str],
    before_gap: range,
    after: list[str],
    after_gap: range,
    start: int,
    budget: _Budget,
) -> Iterator[LineDelta]:
    """A before line reading like an after line is modified; the lines left
    unpaired are removed and added."""
    read_before = {index: _read(before[index]) for index in before_gap}
    after_lines = _AfterLines({index: _read(after[index]) for index in after_gap})
    pairs = greedy_pairs(
        before_gap,
        after_gap,
        lambda index_before, cursor: after_lines.first_similar(
            read_before[index_before], cursor, budget
        ),
    )
    for index_before, index_after in pairs:
        if index_after is None:
            assert index_before is not None
            yield LineDelta(change='removed', before=start + index_before)
        elif index_before is None:
            yield LineDelta(change='added', after=start + index_after)
        else:
            yield LineDelta(
                change='modified',
                before=start + index_before,
                after=start + index_after,
                words=_word_diff(
                    read_before[index_before].tokens,
                    after_lines.read[index_after].tokens,
                ),
            )


def _read(line: str) -> _Read:
    split = list(pieces(line))
    words = [piece for kind, piece in split if kind == 'word']
    return _Read([piece for _, piece in split], words, Counter(words))


class _AfterLines:
    """One gap's after lines, indexed by the words they hold, so that a before
    line costs nothing against the after lines it shares no word with."""

    def __init__(self, read: dict[int, _Read]) -> None:
        self.read = read
        self.holding: dict[str, list[int]] = {}
        self.wordless: list[int] = []
        for index, line in read.items():
            for word in line.word_counts:
                self.holding.setdefault(word, []).append(index)
            if not line.words:
                self.wordless.append(index)

    def first_similar(self, before: _Read, cursor: int, budget: _Budget) -> int | None:
        """The shared word counts bound the shared words from above, which rules
        out most dissimilar pairs before the LCS. Each count is charged, and the
        LCS by tokens, which covers the word diff of a pair found similar too."""
        if not before.words:
            # Lines of spaces alone read alike, and like no line with words.
            position = bisect_left(self.wordless, cursor)
            return self.wordless[position] if position < len(self.wordless) else None
        shared: Counter[int] = Counter()
        for word, count in before.word_counts.items():
            holding = self.holding.get(word, [])
            start = bisect_left(holding, cursor)
            if not budget.spend(len(holding) - start):
                return None
            for index in islice(holding, start, None):
                shared[index] += min(count, self.read[index].word_counts[word])
        for index in sorted(shared):
            after = self.read[index]
            total = len(before.words) + len(after.words)
            if 2 * shared[index] / total < MODIFIED_SIMILARITY:
                continue
            if not budget.spend(len(before.tokens) * len(after.tokens)):
                return None
            if (
                similarity(before.words, after.words, operator.eq)
                >= MODIFIED_SIMILARITY
            ):
                return index
        return None


def _word_diff(before: list[str], after: list[str]) -> tuple[TextSegment, ...]:
    return tuple(
        TextSegment(
            mark=mark,
            text=''.join(
                before_token or after_token or ''
                for _, before_token, after_token in run
            ),
        )
        for mark, run in groupby(
            marked_items(before, after, operator.eq), key=operator.itemgetter(0)
        )
    )
