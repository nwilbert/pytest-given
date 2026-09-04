"""How two cases' step trees are compared, and how they are said to differ.

A step tree reduced to what a grouped tree must share, a narration part reduced
to its template, and the phrasing that names the first difference between two
of them.
"""

from collections.abc import Iterable
from typing import NamedTuple

from ..model import (
    ActivityId,
    Narration,
    NarrationLiteral,
    NarrationPart,
    NarrationPlaceholder,
    NarrationTermRef,
    NarrationValue,
    Phase,
    Step,
    StepPath,
)
from .columns import Format


class StepSignature(NamedTuple):
    """What a grouped tree requires every case's step to share: where it sits,
    its phase, and the activities it claims."""

    path: StepPath
    phase: Phase
    activity_ids: tuple[ActivityId, ...]


class PartKey(NamedTuple):
    """What a part contributes to its narration's template: its kind, the text
    a divergence message names it by, and the rendering details that must match
    without being worth naming."""

    kind: str
    label: str
    detail: Format | None = None


def _shape(indexed: Iterable[tuple[StepPath, Step]]) -> list[StepSignature]:
    """A case's tree reduced to what a grouped tree must share: where each step
    sits, its phase, and the activities it claims.

    Paths carry the nesting, so this needs no recursion — a `walk_steps`
    mapping is already DFS pre-order.

    `activity_ids` is in here because `activity=` is a per-call argument, so
    `given(t'…', activity=a if flag else b)` gives two cases genuinely
    different ids at one path. The grouped tree keeps a single set, and
    `report.coverage` reads exactly that field to credit story coverage — the
    same lie rule 4 refuses a varying term ref to prevent.
    """
    return [
        StepSignature(path, step.phase, step.activity_ids) for path, step in indexed
    ]


def _structure(signature: list[StepSignature]) -> list[tuple[StepPath, Phase]]:
    """The signature without its activities — where the steps sit and what
    phase each is."""
    return [(step.path, step.phase) for step in signature]


def _part_key(part: NarrationPart) -> PartKey:
    """A part reduced to its template.

    Never `rendered`, which is exactly what grouping promotes into a column,
    and never a term ref's `display` — rule 4 governs that, and names it as the
    authoring error it is where a template divergence would only report that
    two cases disagree.
    """
    match part:
        case NarrationLiteral(value=value):
            return PartKey('literal', value)
        case NarrationValue(expression=e, conversion=c, format_spec=f):
            return PartKey('value', e, (c, f))
        case NarrationPlaceholder(name=n, conversion=c, format_spec=f):
            return PartKey('placeholder', n, (c, f))
        case NarrationTermRef(expression=expression):
            return PartKey('term', expression)


def _narration_difference(baseline_keys: list[PartKey], case: Narration) -> str | None:
    """How the case's narration differs from the baseline's keys as a template,
    or None when they agree."""
    case_keys = [_part_key(part) for part in case.parts]
    if [key.kind for key in baseline_keys] != [key.kind for key in case_keys]:
        return 'a differently shaped narration'
    for baseline_key, case_key in zip(baseline_keys, case_keys, strict=True):
        if baseline_key == case_key:
            continue
        if baseline_key.label == case_key.label:
            # Same kind, same label: what differs is the `detail` — the
            # conversion and format spec — so naming the labels would quote
            # the same string twice.
            return (
                f'a different formatting of {baseline_key.label!r} '
                f'({_detail_text(baseline_key)} vs {_detail_text(case_key)})'
            )
        if baseline_key.kind == 'literal':
            return f'different wording ({baseline_key.label!r} vs {case_key.label!r})'
        return f'a different expression ({baseline_key.label!r} vs {case_key.label!r})'
    return None


def _detail_text(key: PartKey) -> str:
    """A part's conversion and format spec as an author wrote them."""
    if key.detail is None:
        return 'no formatting'
    conversion, format_spec = key.detail
    return (
        f'{"!" + conversion if conversion else ""}'
        f'{":" + format_spec if format_spec else ""}'
    ) or 'no formatting'
