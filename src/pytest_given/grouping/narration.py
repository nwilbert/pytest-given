"""A narration rebuilt part by part, each part addressed by its position."""

from collections.abc import Callable
from typing import NewType

from ..model import Narration, NarrationPart, narration_of

# A part's position in its narration's `parts`. Distinct from a `StepPath`
# component, which indexes a step among its siblings: grouping carries both at
# once — the step the part is in, and the part within it — and reaches the same
# position in every other case by this index, so mixing the two silently
# compares the wrong things.
PartIndex = NewType('PartIndex', int)


def rebuilt(
    narration: Narration, part_of: Callable[[PartIndex, NarrationPart], NarrationPart]
) -> Narration:
    """The narration with every part mapped, and its text re-derived from them.

    A part-less narration passes through: its text is all it has, and there is
    nothing to rebuild it from.

    `part_of` takes the part's `PartIndex` as well as the part: a grouping slot
    is identified by its position, and a mapper that does not care ignores it.
    """
    if not narration.parts:
        return narration
    return narration_of(
        part_of(PartIndex(index), part) for index, part in enumerate(narration.parts)
    )
