"""The two positional indexes into a recorded tree, and the one depth-first
walk that produces them — shared by lint, report and the grouping pass.

`report/` and `lint/` may not import from each other and both need the walk;
`model/` is the leaf they both depend on. The indexes live here rather than in
`schema.py` because neither is ever serialized: `schema.py` is what reaches the
JSON report, and these only ever address a position within it.
"""

from collections.abc import Iterator
from typing import NewType

from .schema import Narration, Scenario, Step

# A position in a step tree: the child index at each level, outermost first.
type StepPath = tuple[int, ...]

# A part's position in its narration's `parts`. Distinct from a `StepPath`
# component, which indexes a step among its siblings: grouping carries both at
# once — the step the part is in, and the part within it — and reaches the same
# position in every other case by this index, so mixing the two silently
# compares the wrong things.
PartIndex = NewType('PartIndex', int)


def walk_steps(steps: list[Step]) -> Iterator[tuple[StepPath, Step]]:
    def descend(steps: list[Step], prefix: StepPath) -> Iterator[tuple[StepPath, Step]]:
        for index, step in enumerate(steps):
            path = (*prefix, index)
            yield path, step
            yield from descend(step.children, path)

    return descend(steps, ())


def iter_steps(steps: list[Step]) -> Iterator[Step]:
    return (step for _path, step in walk_steps(steps))


def step_narrations(steps: list[Step]) -> Iterator[Narration]:
    return (step.narration for _path, step in walk_steps(steps))


def iter_narrations(scenario: Scenario) -> Iterator[Narration]:
    """A scenario's own narration followed by every step's, depth-first."""
    yield scenario.narration
    yield from step_narrations(scenario.steps)
