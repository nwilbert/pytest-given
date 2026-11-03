"""Two step trees aligned: which steps are unchanged, reworded, added or removed."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from ..model import Step, StepDelta, StepPath
from .lcs import lcs_gaps
from .narration import (
    Reading,
    Token,
    similarity,
    token_diff,
    token_lists_equal,
    tokens,
)

MODIFIED_SIMILARITY = 0.5


def align_steps(
    before: list[Step], rb: Reading, after: list[Step], ra: Reading
) -> tuple[StepDelta, ...]:
    return _Alignment(rb, ra).siblings(before, (), after, ())


def steps_changed(deltas: Sequence[StepDelta]) -> bool:
    return any(
        delta.change != 'equal' or steps_changed(delta.children) for delta in deltas
    )


@dataclass(frozen=True)
class _Read:
    """A step with its narration read once, for every comparison it takes part in."""

    step: Step
    tokens: list[Token]
    words: list[Token]
    # Two words can be equal only with the same kind and key.
    word_keys: Counter[tuple[str, str]]


class _Alignment:
    def __init__(self, rb: Reading, ra: Reading) -> None:
        self.rb = rb
        self.ra = ra

    def siblings(
        self,
        before: list[Step],
        before_parent: StepPath,
        after: list[Step],
        after_parent: StepPath,
    ) -> tuple[StepDelta, ...]:
        read_before = [_read(step, self.rb) for step in before]
        read_after = [_read(step, self.ra) for step in after]
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
                before_path = (*before_parent, index_before)
                after_path = (*after_parent, index_after)
                deltas.append(
                    StepDelta(
                        change='equal',
                        before=before_path,
                        after=after_path,
                        children=self.siblings(
                            before[index_before].children,
                            before_path,
                            after[index_after].children,
                            after_path,
                        ),
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
        """The steps between two anchors. Each before step pairs with the first
        after step past the last pairing that reads like it, else it is removed;
        the after steps left unpaired are added."""
        deltas: list[StepDelta] = []
        cursor = after_gap.start
        for index in before_gap:
            before_path = (*before_parent, index)
            match = next(
                (
                    candidate
                    for candidate in range(cursor, after_gap.stop)
                    if _similar(before[index], after[candidate])
                ),
                None,
            )
            if match is None:
                deltas.append(StepDelta(change='removed', before=before_path))
                continue
            deltas.extend(
                StepDelta(change='added', after=(*after_parent, skipped))
                for skipped in range(cursor, match)
            )
            deltas.append(
                self._modified(
                    before[index], before_path, after[match], (*after_parent, match)
                )
            )
            cursor = match + 1
        deltas.extend(
            StepDelta(change='added', after=(*after_parent, skipped))
            for skipped in range(cursor, after_gap.stop)
        )
        return deltas

    def _modified(
        self, before: _Read, before_path: StepPath, after: _Read, after_path: StepPath
    ) -> StepDelta:
        return StepDelta(
            change='modified',
            before=before_path,
            after=after_path,
            words=token_diff(before.tokens, after.tokens),
            children=self.siblings(
                before.step.children, before_path, after.step.children, after_path
            ),
        )


def _read(step: Step, reading: Reading) -> _Read:
    read = tokens(step.narration, reading)
    words = [token for token in read if token.kind != 'space']
    return _Read(step, read, words, Counter((word.kind, word.key) for word in words))


def _same(before: _Read, after: _Read) -> bool:
    return before.step.phase == after.step.phase and token_lists_equal(
        before.tokens, after.tokens
    )


def _similar(before: _Read, after: _Read) -> bool:
    """The shared word keys bound the shared words from above, which rules out
    most dissimilar pairs before the LCS that `similarity` builds."""
    total = len(before.words) + len(after.words)
    if total and 2 * (before.word_keys & after.word_keys).total() < (
        MODIFIED_SIMILARITY * total
    ):
        return False
    return similarity(before.words, after.words) >= MODIFIED_SIMILARITY
