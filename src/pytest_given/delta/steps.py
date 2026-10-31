"""Two step trees aligned: which steps are unchanged, reworded, added or removed."""

from collections.abc import Sequence

from ..model import Step, StepDelta, StepPath
from .lcs import lcs_pairs
from .narration import Reading, narrations_equal, similarity, word_diff

MODIFIED_SIMILARITY = 0.5


def align_steps(
    before: list[Step], rb: Reading, after: list[Step], ra: Reading
) -> tuple[StepDelta, ...]:
    return _Alignment(rb, ra).siblings(before, (), after, ())


def steps_changed(deltas: Sequence[StepDelta]) -> bool:
    return any(
        delta.change != 'equal' or steps_changed(delta.children) for delta in deltas
    )


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
        deltas: list[StepDelta] = []
        start_before = start_after = 0
        anchors = lcs_pairs(before, after, self._same)
        for index_before, index_after in [*anchors, (len(before), len(after))]:
            deltas.extend(
                self._unanchored(
                    before[start_before:index_before],
                    before_parent,
                    start_before,
                    after[start_after:index_after],
                    after_parent,
                    start_after,
                )
            )
            if index_before < len(before):
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
            start_before, start_after = index_before + 1, index_after + 1
        return tuple(deltas)

    def _same(self, before: Step, after: Step) -> bool:
        return before.phase == after.phase and narrations_equal(
            before.narration, self.rb, after.narration, self.ra
        )

    def _similar(self, before: Step, after: Step) -> bool:
        return (
            similarity(before.narration, self.rb, after.narration, self.ra)
            >= MODIFIED_SIMILARITY
        )

    def _unanchored(
        self,
        before: list[Step],
        before_parent: StepPath,
        before_start: int,
        after: list[Step],
        after_parent: StepPath,
        after_start: int,
    ) -> list[StepDelta]:
        """The steps between two anchors. Each before step pairs with the first
        after step past the last pairing that reads like it, else it is removed;
        the after steps left unpaired are added."""
        deltas: list[StepDelta] = []
        cursor = 0
        for index, step in enumerate(before):
            before_path = (*before_parent, before_start + index)
            match = next(
                (
                    candidate
                    for candidate in range(cursor, len(after))
                    if self._similar(step, after[candidate])
                ),
                None,
            )
            if match is None:
                deltas.append(StepDelta(change='removed', before=before_path))
                continue
            deltas.extend(
                StepDelta(change='added', after=(*after_parent, after_start + skipped))
                for skipped in range(cursor, match)
            )
            deltas.append(
                self._modified(
                    step,
                    before_path,
                    after[match],
                    (*after_parent, after_start + match),
                )
            )
            cursor = match + 1
        deltas.extend(
            StepDelta(change='added', after=(*after_parent, after_start + skipped))
            for skipped in range(cursor, len(after))
        )
        return deltas

    def _modified(
        self, before: Step, before_path: StepPath, after: Step, after_path: StepPath
    ) -> StepDelta:
        return StepDelta(
            change='modified',
            before=before_path,
            after=after_path,
            phase_changed=before.phase != after.phase,
            words=word_diff(before.narration, self.rb, after.narration, self.ra),
            children=self.siblings(
                before.children, before_path, after.children, after_path
            ),
        )
