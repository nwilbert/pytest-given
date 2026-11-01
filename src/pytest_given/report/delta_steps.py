"""A changed scenario's steps side by side: a row per aligned pair of steps,
each side reading as its own scenario does, under its own phases."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import groupby
from typing import Literal

from ..model import (
    DiffSegment,
    Mark,
    Narration,
    NarrationLiteral,
    NarrationPart,
    Phase,
    ScenarioDelta,
    Step,
    StepChange,
    StepDelta,
    StepPath,
    walk_steps,
)
from .html_renderer import phase_blocks

type Side = Literal['before', 'after']
# A phase block's `data-block`, which its table columns carry too. An after
# block's is its index, and a before block takes the key of the after block its
# steps went to, so a phase hover outlines the phase on both sides.
type BlockKey = str

# Prefixes a before block none of whose steps the after side still has.
_BEFORE_ONLY_BLOCK = 'before:'
# The mark a side's own changed words carry in a word diff.
_SIDE_MARK: dict[Side, Mark] = {'before': 'removed', 'after': 'added'}


@dataclass(frozen=True)
class StepLine:
    """A step as its side shows it."""

    step: Step
    # A modified step's text in runs, the words only this side has marked.
    # Empty where the step reads unmarked.
    words: tuple[DiffSegment, ...] = ()


@dataclass(frozen=True)
class StepRow:
    """An aligned pair of steps, a line on each side that has its step. An
    added or removed step stands for its whole subtree, so it has no rows
    below it."""

    change: StepChange
    # Its place among the rows, which keys it alike on both sides.
    path: StepPath
    before: StepLine | None
    after: StepLine | None
    children: tuple[StepRow, ...]

    def line(self, side: Side) -> StepLine | None:
        return self.before if side == 'before' else self.after


@dataclass(frozen=True)
class SideBlock:
    """A side's run of rows under one keyword, as the report's phase blocks
    are, or a run of rows the side lacks, which belongs to no phase. A phase
    such a run interrupts goes on after it, under the same key."""

    phase: Phase | None  # None for rows the side lacks
    key: BlockKey | None
    rows: list[StepRow]
    # Goes on with the phase of the block before the rows the side lacks, so
    # it shows no keyword of its own.
    continued: bool = False


@dataclass(frozen=True)
class StepsView:
    before: list[SideBlock]
    after: list[SideBlock]

    def side(self, side: Side) -> list[SideBlock]:
        return self.before if side == 'before' else self.after


def steps_view(scenario_delta: ScenarioDelta) -> StepsView:
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
    rows = _Rows(
        {
            'before': dict(walk_steps(before.steps)),
            'after': dict(walk_steps(after.steps)),
        }
    )
    top = [
        rows.row(step_delta, (index,))
        for index, step_delta in enumerate(scenario_delta.steps)
    ]
    keys = block_keys(scenario_delta)
    return StepsView(
        before=_side_blocks(top, 'before', keys['before']),
        after=_side_blocks(top, 'after', keys['after']),
    )


def block_keys(scenario_delta: ScenarioDelta) -> dict[Side, list[BlockKey]]:
    """Each side's phase blocks' keys, in order. A before block takes the key
    of the after block holding the first of its steps the after side kept."""
    before, after = scenario_delta.before, scenario_delta.after
    assert before is not None
    assert after is not None
    before_of, after_of = _block_of(before.steps), _block_of(after.steps)
    paired: dict[int, BlockKey] = {}
    for step_delta in scenario_delta.steps:
        if step_delta.before is not None and step_delta.after is not None:
            paired.setdefault(
                before_of[step_delta.before[0]], str(after_of[step_delta.after[0]])
            )
    return {
        'before': [
            paired.get(index, f'{_BEFORE_ONLY_BLOCK}{index}')
            for index in range(len(phase_blocks(before.steps)))
        ],
        'after': [str(index) for index in range(len(phase_blocks(after.steps)))],
    }


def side_words(
    narration: Narration, runs: Sequence[DiffSegment]
) -> tuple[DiffSegment, ...]:
    """A side's runs of a word diff, its equal ones and its own changed ones,
    laid over the side's own narration, so the side reads its own text. They
    differ from it where an equal run shows the after side's parts, a term ref
    displayed otherwise, say, and where a space went to the other side's
    change. Where the two don't line up, empty: the step reads unmarked."""
    own = _atoms(narration.parts or (NarrationLiteral(value=narration.text),))
    theirs = [(run.mark, atom) for run in runs for atom in _atoms(run.parts)]
    marked: list[tuple[Mark, NarrationPart]] = []
    mine = their = 0
    while mine < len(own) or their < len(theirs):
        own_space = mine < len(own) and _is_space(own[mine])
        their_space = their < len(theirs) and _is_space(theirs[their][1])
        if own_space or their_space:
            # Spaces compare as a run, whatever their width; a run only this
            # side has is no change of its own.
            mark: Mark = theirs[their][0] if own_space and their_space else 'equal'
            while mine < len(own) and _is_space(own[mine]):
                marked.append((mark, own[mine]))
                mine += 1
            while their < len(theirs) and _is_space(theirs[their][1]):
                their += 1
            continue
        if (
            mine == len(own)
            or their == len(theirs)
            or not _alike(own[mine], theirs[their][1])
        ):
            return ()
        marked.append((theirs[their][0], own[mine]))
        mine += 1
        their += 1
    return tuple(
        DiffSegment(mark=mark, parts=_joined([part for _, part in run]))
        for mark, run in groupby(marked, key=lambda atom: atom[0])
    )


@dataclass(frozen=True)
class _Rows:
    steps: dict[Side, dict[StepPath, Step]]

    def row(self, step_delta: StepDelta, path: StepPath) -> StepRow:
        return StepRow(
            change=step_delta.change,
            path=path,
            before=self._line(step_delta, 'before'),
            after=self._line(step_delta, 'after'),
            children=tuple(
                self.row(child, (*path, index))
                for index, child in enumerate(step_delta.children)
            ),
        )

    def _line(self, step_delta: StepDelta, side: Side) -> StepLine | None:
        at = step_delta.before if side == 'before' else step_delta.after
        if at is None:
            return None
        step = self.steps[side][at]
        if step_delta.change != 'modified':
            return StepLine(step)
        runs = [
            run for run in step_delta.words if run.mark in ('equal', _SIDE_MARK[side])
        ]
        return StepLine(step, side_words(step.narration, runs))


def _block_of(steps: list[Step]) -> list[int]:
    """Each top-level step's phase block."""
    return [index for index, block in enumerate(phase_blocks(steps)) for _ in block]


def _side_blocks(
    rows: list[StepRow], side: Side, keys: list[BlockKey]
) -> list[SideBlock]:
    blocks: list[SideBlock] = []
    opened: SideBlock | None = None  # the phase block last opened
    for row in rows:
        line = row.line(side)
        phase = None if line is None else line.step.phase
        last = blocks[-1] if blocks else None
        if last is None or last.phase != phase:
            if phase is None:
                blocks.append(SideBlock(None, None, []))
            elif opened is not None and opened.phase == phase:
                blocks.append(SideBlock(phase, opened.key, [], continued=True))
            else:
                opened = SideBlock(phase, keys[len(_opened(blocks))], [])
                blocks.append(opened)
        blocks[-1].rows.append(row)
    assert len(_opened(blocks)) == len(keys)
    return blocks


def _opened(blocks: list[SideBlock]) -> list[SideBlock]:
    """The blocks that open a phase, one per phase block of the side."""
    return [
        block for block in blocks if block.phase is not None and not block.continued
    ]


def _atoms(parts: Sequence[NarrationPart]) -> list[NarrationPart]:
    """A literal by the character, any other part whole."""
    atoms: list[NarrationPart] = []
    for part in parts:
        if isinstance(part, NarrationLiteral):
            atoms.extend(NarrationLiteral(value=char) for char in part.value)
        else:
            atoms.append(part)
    return atoms


def _is_space(atom: NarrationPart) -> bool:
    return isinstance(atom, NarrationLiteral) and atom.value.isspace()


def _alike(own: NarrationPart, theirs: NarrationPart) -> bool:
    if isinstance(own, NarrationLiteral):
        return own == theirs
    return type(own) is type(theirs)


def _joined(atoms: list[NarrationPart]) -> tuple[NarrationPart, ...]:
    joined: list[NarrationPart] = []
    for atom in atoms:
        last = joined[-1] if joined else None
        if isinstance(atom, NarrationLiteral) and isinstance(last, NarrationLiteral):
            joined[-1] = NarrationLiteral(value=last.value + atom.value)
        else:
            joined.append(atom)
    return tuple(joined)
