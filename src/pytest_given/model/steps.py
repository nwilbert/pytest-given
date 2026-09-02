"""One depth-first walk over a step tree, shared by lint, report and the
grouping pass. `report/` and `lint/` may not import from each other and both
need it; `model/` is the leaf they both depend on.
"""

from collections.abc import Iterator

from .schema import Narration, Scenario, Step

# A position in a step tree: the child index at each level, outermost first.
type StepPath = tuple[int, ...]


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
