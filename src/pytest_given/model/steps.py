"""One depth-first walk over a step tree, shared by lint, report and the grouping pass.

`report/` and `lint/` may not import from each other and both need this walk;
`model/` is the leaf they both depend on, so it lives here (as `ids.py` does
for id derivation).
"""

from collections.abc import Iterator

from .schema import Narration, Phase, Scenario, Step

# A position in a step tree: the child index at each level, outermost first.
type StepPath = tuple[int, ...]

# A step tree reduced to nested phase tuples — narration text and values
# ignored. Two cases with equal signatures render truthfully in the grouped
# parameter-table view.
type StepSignature = tuple[tuple[Phase, StepSignature], ...]


def walk_steps(
    steps: list[Step], prefix: StepPath = ()
) -> Iterator[tuple[StepPath, Step]]:
    for index, step in enumerate(steps):
        path = (*prefix, index)
        yield path, step
        yield from walk_steps(step.children, path)


def iter_steps(steps: list[Step]) -> Iterator[Step]:
    """Depth-first walk over a step tree, paths discarded."""
    for _path, step in walk_steps(steps):
        yield step


def structure_signature(steps: list[Step]) -> StepSignature:
    """The tree's shape alone — phases and nesting, no narration."""
    return tuple((step.phase, structure_signature(step.children)) for step in steps)


def step_narrations(steps: list[Step]) -> Iterator[Narration]:
    """Every narration in a step tree, depth-first.

    Separate from `iter_narrations` because the grouping pass needs exactly
    this and not the scenario's own: it scans the *baseline* case's steps for
    parameter formatting while taking the name from `group[0]`, which is a
    different scenario whenever the first case did not pass.
    """
    return (step.narration for _path, step in walk_steps(steps))


def iter_narrations(scenario: Scenario) -> Iterator[Narration]:
    """A scenario's own narration followed by every step's, depth-first."""
    yield scenario.narration
    yield from step_narrations(scenario.steps)
