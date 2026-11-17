"""Two step trees aligned: which steps are unchanged, reworded, added or removed."""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Literal

from ..model import (
    AttachmentDelta,
    ColumnId,
    Step,
    StepDelta,
    StepPath,
    walk_step_deltas,
)
from .attachments import align_attachments
from .lcs import greedy_pairs, lcs_gaps
from .narration import (
    MODIFIED_SIMILARITY,
    Reading,
    Token,
    WordKey,
    bag_similarity,
    similarity,
    token_diff,
    token_lists_equal,
    tokens,
    tokens_equal,
    word_counts,
    words_of,
)


def align_steps(
    before: list[Step],
    before_reading: Reading,
    after: list[Step],
    after_reading: Reading,
    column_of: Mapping[ColumnId, ColumnId],
) -> tuple[StepDelta, ...]:
    """`column_of` maps a before column ID to its paired after column ID."""
    return _Alignment(before_reading, after_reading, column_of).siblings(
        before, (), after, ()
    )


def steps_changed(deltas: Sequence[StepDelta]) -> bool:
    return any(delta.change != 'equal' for delta in walk_step_deltas(deltas))


@dataclass(frozen=True)
class _Read:
    """A step with its narration read once, for every comparison it takes part
    in. Only a step between two anchors is compared by its words."""

    step: Step
    tokens: list[Token]

    @cached_property
    def words(self) -> list[Token]:
        return words_of(self.tokens)

    @cached_property
    def word_keys(self) -> Counter[WordKey]:
        return word_counts(self.words)


class _Alignment:
    def __init__(
        self,
        before_reading: Reading,
        after_reading: Reading,
        column_of: Mapping[ColumnId, ColumnId],
    ) -> None:
        self.before_reading = before_reading
        self.after_reading = after_reading
        self.column_of = column_of

    def siblings(
        self,
        before: list[Step],
        before_parent: StepPath,
        after: list[Step],
        after_parent: StepPath,
    ) -> tuple[StepDelta, ...]:
        read_before = [_read(step, self.before_reading) for step in before]
        read_after = [_read(step, self.after_reading) for step in after]
        deltas: list[StepDelta] = []
        for gap_before, gap_after, anchor in lcs_gaps(read_before, read_after, _same):
            deltas.extend(
                self._unanchored(
                    read_before,
                    gap_before,
                    before_parent,
                    read_after,
                    gap_after,
                    after_parent,
                )
            )
            if anchor is not None:
                index_before, index_after = anchor
                deltas.append(
                    self._paired(
                        'equal',
                        read_before[index_before],
                        (*before_parent, index_before),
                        read_after[index_after],
                        (*after_parent, index_after),
                    )
                )
        return tuple(deltas)

    def _unanchored(
        self,
        before: list[_Read],
        before_gap: range,
        before_parent: StepPath,
        after: list[_Read],
        after_gap: range,
        after_parent: StepPath,
    ) -> list[StepDelta]:
        """The steps between two anchors. A before step reading like an after
        step is modified; the steps left unpaired are removed and added."""
        deltas: list[StepDelta] = []
        pairs = greedy_pairs(
            before_gap,
            after_gap,
            lambda index_before, cursor: next(
                (
                    index_after
                    for index_after in range(cursor, after_gap.stop)
                    if _similar(before[index_before], after[index_after])
                ),
                None,
            ),
        )
        for index_before, index_after in pairs:
            if index_after is None:
                assert index_before is not None
                deltas.append(
                    StepDelta(change='removed', before=(*before_parent, index_before))
                )
            elif index_before is None:
                deltas.append(
                    StepDelta(change='added', after=(*after_parent, index_after))
                )
            else:
                deltas.append(
                    self._paired(
                        'modified',
                        before[index_before],
                        (*before_parent, index_before),
                        after[index_after],
                        (*after_parent, index_after),
                    )
                )
        return deltas

    def _paired(
        self,
        change: Literal['equal', 'modified'],
        before: _Read,
        before_path: StepPath,
        after: _Read,
        after_path: StepPath,
    ) -> StepDelta:
        return StepDelta(
            change=change,
            before=before_path,
            after=after_path,
            words=token_diff(before.tokens, after.tokens)
            if change == 'modified'
            else (),
            children=self.siblings(
                before.step.children, before_path, after.step.children, after_path
            ),
            attachments=self._attachments(before.step, after.step),
        )

    def _attachments(self, before: Step, after: Step) -> tuple[AttachmentDelta, ...]:
        return align_attachments(before.attachments, after.attachments, self.column_of)


def _read(step: Step, reading: Reading) -> _Read:
    return _Read(step, tokens(step.narration, reading))


def _same(before: _Read, after: _Read) -> bool:
    return before.step.phase == after.step.phase and token_lists_equal(
        before.tokens, after.tokens
    )


def _similar(before: _Read, after: _Read) -> bool:
    """Across phases only the same text: a reworded Given is not the Then that
    reads like it. The shared word keys bound the shared words from above, which
    rules out most dissimilar pairs before the LCS that `similarity` builds."""
    if before.step.phase != after.step.phase:
        return token_lists_equal(before.tokens, after.tokens)
    if bag_similarity(before.word_keys, after.word_keys) < MODIFIED_SIMILARITY:
        return False
    return similarity(before.words, after.words, tokens_equal) >= MODIFIED_SIMILARITY
