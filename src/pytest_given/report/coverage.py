"""Scenario ↔ story-activity coverage matching."""

from collections.abc import Iterable
from typing import NamedTuple

from ..model import (
    Activity,
    ActivityEntity,
    ActivityId,
    ActivityPart,
    ActivityPlaceholder,
    ActivityTerm,
    ActivityWord,
    Glossary,
    NarrationTermRef,
    NodeId,
    Scenario,
    Step,
    Story,
    TermId,
    id_derive,
)


class Identity(NamedTuple):
    term_id: TermId
    instance_id: str | None


type StepRef = tuple[NodeId, tuple[int, ...]]


def instance_id_of(
    glossary: Glossary,
    term_id: TermId,
    display: str,
) -> str | None:
    """None for the canonical display (or an unknown term), otherwise the
    slug of the display."""
    term = glossary.get(term_id)
    if term is None or display == term.canonical:
        return None
    return id_derive(display)


def identity_of_part(
    glossary: Glossary,
    part: ActivityPart,
) -> Identity | None:
    """Identity contributed by a single ActivityPart. Words/placeholders → None."""
    match part:
        case ActivityEntity(entity_id=tid, display=display):
            return Identity(
                term_id=tid,
                instance_id=instance_id_of(glossary, tid, display),
            )
        case ActivityTerm(term_id=tid):
            return Identity(term_id=tid, instance_id=None)
        case ActivityWord() | ActivityPlaceholder():
            return None


def a_refs(glossary: Glossary, activity: Activity) -> set[Identity] | None:
    """Identity set used for strict A_refs ⊆ S coverage matching.

    Returns None if the activity contains any ActivityPlaceholder (draft),
    signalling "hard-excluded from implicit coverage" per the spec.
    """
    out: set[Identity] = set()
    for p in activity.paths:
        if any(isinstance(part, ActivityPlaceholder) for part in p.parts):
            return None
        for part in p.parts:
            ident = identity_of_part(glossary, part)
            if ident is not None:
                out.add(ident)
    return out


def s_for_step(glossary: Glossary, step: Step) -> set[Identity]:
    """Identity set contributed by a step's narration term refs.

    Applies the canonical-fallback rule: entity instance refs contribute
    both their specific identity and the canonical (term_id, None).
    """
    out: set[Identity] = set()
    for part in step.narration.parts:
        if not isinstance(part, NarrationTermRef):
            continue
        term = glossary.get(part.term_id)
        if term is None:
            continue
        if term.kind == 'verb':
            out.add(Identity(term_id=part.term_id, instance_id=None))
            continue
        inst_id = instance_id_of(glossary, part.term_id, part.display)
        if inst_id is None:
            out.add(Identity(term_id=part.term_id, instance_id=None))
        else:
            out.add(Identity(term_id=part.term_id, instance_id=inst_id))
            out.add(Identity(term_id=part.term_id, instance_id=None))
    return out


def compute_coverage(
    glossary: Glossary,
    scenario: Scenario,
    story: Story,
) -> dict[ActivityId, set[StepRef]]:
    """Per-scenario activity-coverage map.

    Each activity covered by at least one step appears in the result; the
    value is the set of StepRef tuples for the covering steps.

    Scope: if scenario.activity_ids is non-empty, only those activity ids
    can appear in the result. Otherwise every story activity is considered.
    """
    scope = (
        set(scenario.activity_ids)
        if scenario.activity_ids
        else {a.id for a in story.activities}
    )
    activities_in_scope = [a for a in story.activities if a.id in scope]
    refs_by_activity: dict[ActivityId, set[Identity] | None] = {
        a.id: a_refs(glossary, a) for a in activities_in_scope
    }
    result: dict[ActivityId, set[StepRef]] = {}
    for path_index, step in _walk_steps(scenario):
        ref: StepRef = (scenario.id, path_index)
        s_cache: set[Identity] | None = None
        for activity in activities_in_scope:
            if step.activity_ids:
                if activity.id in step.activity_ids:
                    result.setdefault(activity.id, set()).add(ref)
                continue
            refs = refs_by_activity[activity.id]
            if refs is None:
                continue
            if s_cache is None:
                s_cache = s_for_step(glossary, step)
            if refs.issubset(s_cache):
                result.setdefault(activity.id, set()).add(ref)
    return result


def _walk_steps(
    scenario: Scenario,
) -> Iterable[tuple[tuple[int, ...], Step]]:
    """Depth-first walk yielding (index_path, step) for every step in the tree."""

    def _walk(
        steps: list[Step], prefix: tuple[int, ...]
    ) -> Iterable[tuple[tuple[int, ...], Step]]:
        for i, step in enumerate(steps):
            yield (*prefix, i), step
            if step.children:
                yield from _walk(step.children, (*prefix, i))

    return _walk(scenario.steps, ())
