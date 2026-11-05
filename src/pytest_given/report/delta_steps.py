"""A changed scenario's steps side by side: a row per aligned pair of steps,
each side reading as its own scenario does, under its own phases. Its sides
and a side's runs of a word diff serve the tables and the Glossary tab too."""

from collections.abc import Sequence
from dataclasses import dataclass

from ..model import (
    SIDE_MARK,
    DiffSegment,
    Mark,
    NarrationPart,
    Phase,
    ScenarioDelta,
    Side,
    Step,
    StepChange,
    StepDelta,
    StepPath,
    merged_literals,
    narration_text,
    on_side,
    walk_steps,
)
from .html_renderer import phase_blocks

# A phase block's `data-block`, which its table columns carry too. An after
# block's is its index, and a before block takes the key of the after block its
# steps went to, so a phase hover outlines the phase on both sides.
type BlockKey = str

# Prefixes a before block none of whose steps the after side still has.
_BEFORE_ONLY_BLOCK = 'before:'


@dataclass(frozen=True)
class MarkedRun:
    """A run of one side's text, in that side's own parts."""

    mark: Mark
    parts: tuple[NarrationPart, ...]


@dataclass(frozen=True)
class StepLine:
    """A step as its side shows it."""

    step: Step
    # A modified step's text in runs, the words only this side has marked;
    # empty for any other step.
    words: tuple[MarkedRun, ...] = ()


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
        return on_side(side, self.before, self.after)

    def row_id(self, scenario_idx: int) -> str:
        return f's{scenario_idx}_' + '_'.join(map(str, self.path))


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
        return on_side(side, self.before, self.after)


def steps_view(
    scenario_delta: ScenarioDelta, keys: dict[Side, list[BlockKey]]
) -> StepsView:
    before, after = scenario_delta.paired()
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
    return StepsView(
        before=_side_blocks(top, 'before', keys['before']),
        after=_side_blocks(top, 'after', keys['after']),
    )


def block_keys(scenario_delta: ScenarioDelta) -> dict[Side, list[BlockKey]]:
    """Each side's phase blocks' keys, in order. A before block takes the key
    of the after block holding the first of its steps the after side kept, so
    two before blocks can share one when one phase's steps moved into another."""
    before, after = scenario_delta.paired()
    before_blocks, after_blocks = phase_blocks(before.steps), phase_blocks(after.steps)
    before_of, after_of = _block_of(before_blocks), _block_of(after_blocks)
    paired: dict[int, BlockKey] = {}
    for step_delta in scenario_delta.steps:
        if step_delta.before is not None and step_delta.after is not None:
            paired.setdefault(
                before_of[step_delta.before[0]], str(after_of[step_delta.after[0]])
            )
    return {
        'before': [
            paired.get(index, f'{_BEFORE_ONLY_BLOCK}{index}')
            for index in range(len(before_blocks))
        ],
        'after': [str(index) for index in range(len(after_blocks))],
    }


def side_runs(runs: Sequence[DiffSegment], side: Side) -> tuple[MarkedRun, ...]:
    """One side's text of a word diff: its equal runs and its own changed
    ones, each in that side's own parts."""
    return _joined(
        [
            MarkedRun(run.mark, on_side(side, run.before, run.after))
            for run in runs
            if run.mark in ('equal', SIDE_MARK[side])
        ]
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
        at = on_side(side, step_delta.before, step_delta.after)
        if at is None:
            return None
        step = self.steps[side][at]
        if step_delta.change != 'modified':
            return StepLine(step)
        return StepLine(step, side_runs(step_delta.words, side))


def _block_of(blocks: list[list[Step]]) -> list[int]:
    """Each top-level step's phase block."""
    return [index for index, block in enumerate(blocks) for _ in block]


def _side_blocks(
    rows: list[StepRow], side: Side, keys: list[BlockKey]
) -> list[SideBlock]:
    blocks: list[SideBlock] = []
    opened: SideBlock | None = None  # the phase block last opened
    unopened = iter(keys)
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
                opened = SideBlock(phase, next(unopened), [])
                blocks.append(opened)
        blocks[-1].rows.append(row)
    assert next(unopened, None) is None
    return blocks


def _joined(runs: list[MarkedRun]) -> tuple[MarkedRun, ...]:
    """Runs of one mark merged, and a run of spaces alone between two changes
    of one mark taken into them, so a changed stretch reads as one."""
    joined: list[MarkedRun] = []
    for index, run in enumerate(runs):
        mark = run.mark
        if (
            mark == 'equal'
            and 0 < index < len(runs) - 1
            and runs[index - 1].mark == runs[index + 1].mark
            and narration_text(run.parts).isspace()
        ):
            mark = runs[index - 1].mark
        if joined and joined[-1].mark == mark:
            joined[-1] = MarkedRun(mark, merged_literals(joined[-1].parts + run.parts))
        else:
            joined.append(MarkedRun(mark, run.parts))
    return tuple(joined)
