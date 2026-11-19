"""A step's position in a recorded tree, and the one depth-first walk that
produces it — shared by lint, report, delta and the grouping pass.

The index lives here rather than in `schema.py` because it is never
serialized: `schema.py` is what reaches the JSON report, and this only ever
addresses a position within it.
"""

from collections.abc import Iterator, Sequence
from typing import Annotated

from annotated_types import Ge, MinLen

from .schema import Narration, Scenario, SchemaDoc, Step

type StepPath = Annotated[
    tuple[Annotated[int, Ge(0)], ...],
    MinLen(1),
    SchemaDoc(
        "A step's position in its scenario: the child index at each depth, "
        'outermost first.'
    ),
]


def walk_steps[T: Step](steps: Sequence[T]) -> Iterator[tuple[StepPath, T]]:
    def descend(steps: Sequence[T], prefix: StepPath) -> Iterator[tuple[StepPath, T]]:
        for index, step in enumerate(steps):
            path = (*prefix, index)
            yield path, step
            yield from descend(step.children, path)

    return descend(steps, ())


def iter_steps[T: Step](steps: Sequence[T]) -> Iterator[T]:
    return (step for _path, step in walk_steps(steps))


def iter_narrations[S: Step](scenario: Scenario[S]) -> Iterator[Narration]:
    """A scenario's own narration followed by every step's, depth-first."""
    yield scenario.narration
    yield from (step.narration for step in iter_steps(scenario.steps))
